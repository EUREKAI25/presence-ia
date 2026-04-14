"""
Leads Runner — pipeline unifié : qualification SIRENE + enrichissement → V3ProspectDB

POST /admin/leads/run    { profession_id, qty, dept? }
GET  /admin/leads/status → état en temps réel
POST /admin/leads/stop   → demande d'arrêt propre

Logique :
1. Phase 1 — qualifie des segments SIRENE jusqu'à avoir qty×5 suspects non encore tentés
2. Phase 2 — enrichit (Google Places + scraping) uniquement les suspects enrichi_at IS NULL
   Marque chaque suspect enrichi_at=now() AVANT l'appel API → jamais retraité
3. Boucle jusqu'à qty contacts OU plus de segments disponibles
"""
import json, logging, os, secrets, threading
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...database import SessionLocal, db_suspects_list
from ._nav import admin_token

log    = logging.getLogger(__name__)
router = APIRouter()

_STATE: dict = {
    "running": False, "phase": "", "stop_requested": False,
    "profession_id": "", "qty": 0,
    "suspects": 0, "segments_done": 0, "segments_total": 0,
    "processed": 0, "enriched": 0, "contacts": 0,
    "results": [], "finished_at": None, "error": None,
}
_LOCK = threading.Lock()


def _require_admin(token: str):
    if token != admin_token():
        from fastapi import HTTPException
        raise HTTPException(403, "Non autorisé")


@router.post("/admin/leads/run")
async def leads_run(request: Request, token: str = ""):
    _require_admin(token)
    from fastapi import HTTPException
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    profession_id = body.get("profession_id", "")
    qty           = int(body.get("qty", 20))
    dept          = body.get("dept") or None

    if not profession_id:
        raise HTTPException(400, "profession_id requis")
    if _STATE["running"]:
        raise HTTPException(409, "Pipeline déjà en cours")

    with _LOCK:
        _STATE.update({
            "running": True, "phase": "qualification SIRENE", "stop_requested": False,
            "profession_id": profession_id, "qty": qty,
            "suspects": 0, "segments_done": 0, "segments_total": 0,
            "processed": 0, "enriched": 0, "contacts": 0,
            "results": [], "finished_at": None, "error": None,
        })

    threading.Thread(target=_run_pipeline, args=(profession_id, qty, dept), daemon=True).start()
    return JSONResponse({"ok": True})


@router.get("/admin/leads/status")
def leads_status(token: str = ""):
    _require_admin(token)
    with _LOCK:
        return JSONResponse(dict(_STATE))


@router.post("/admin/leads/stop")
def leads_stop(token: str = ""):
    _require_admin(token)
    with _LOCK:
        _STATE["stop_requested"] = True
    return JSONResponse({"ok": True})


# ── Pipeline interne ──────────────────────────────────────────────────────────

def _run_pipeline(profession_id: str, qty: int, dept: Optional[str]):
    try:
        while True:
            if _STATE["stop_requested"]:
                break

            # Phase 1 : qualifier jusqu'à avoir qty×5 suspects non encore tentés
            has_untried = _phase1_qualify(profession_id, qty, dept)
            if _STATE["stop_requested"]:
                break

            if not has_untried:
                # Aucun suspect dispo et plus de segments → terminé
                break

            # Phase 2 : enrichir uniquement les suspects non tentés
            _phase2_enrich(profession_id, qty, dept)

            with _LOCK:
                contacts_done = _STATE["contacts"]

            if contacts_done >= qty:
                break

            # Pas assez de leads — vérifier s'il reste des segments
            from ...sirene import segments_stats
            with SessionLocal() as db_:
                stats = segments_stats(db_)
            pending = stats.get("total_segments", 0) - stats.get("done", 0)
            if pending <= 0:
                log.info("[LEADS] Plus de segments disponibles, arrêt")
                break

            log.info("[LEADS] %d/%d leads — %d segments restants, relance qualification",
                     contacts_done, qty, pending)

    except Exception as e:
        log.error("[LEADS] Erreur pipeline: %s", e)
        with _LOCK:
            _STATE["error"] = str(e)
    finally:
        with _LOCK:
            _STATE["running"]     = False
            _STATE["phase"]       = "done"
            _STATE["finished_at"] = datetime.utcnow().isoformat()


def _count_untried(profession_id: str, dept: Optional[str] = None) -> int:
    """Nombre de suspects non encore tentés pour cette profession (et dept optionnel)."""
    from ...models import SireneSuspectDB
    from sqlalchemy import func
    with SessionLocal() as db:
        q = db.query(func.count(SireneSuspectDB.id)).filter(
            SireneSuspectDB.profession_id == profession_id,
            SireneSuspectDB.enrichi_at.is_(None),
        )
        if dept:
            q = q.filter(SireneSuspectDB.departement == dept)
        return q.scalar() or 0


def _phase1_qualify(profession_id: str, qty_wanted: int, dept: Optional[str] = None) -> bool:
    """Qualifie des segments jusqu'à avoir qty_wanted×5 suspects non encore tentés.
    Retourne True si des suspects non tentés sont disponibles."""
    from ...sirene import generate_segments, run_next_segment, segments_stats

    target  = qty_wanted * 5
    dept_ids = [dept] if dept else None

    untried = _count_untried(profession_id, dept)
    if untried >= target:
        with _LOCK:
            _STATE["suspects"] = untried
            _STATE["phase"]    = "enrichissement"
        return True

    with _LOCK:
        _STATE["phase"] = "qualification SIRENE"

    with SessionLocal() as db:
        generated = generate_segments(db, profession_ids=[profession_id])
        log.info("[LEADS] %d segments générés/vérifiés", generated)

    while True:
        if _STATE["stop_requested"]:
            break

        with SessionLocal() as db:
            result = run_next_segment(db, profession_ids=[profession_id], dept_ids=dept_ids)
            stats  = segments_stats(db)

        if result is None:
            break  # plus de segments pending

        with _LOCK:
            _STATE["segments_done"]  = stats.get("done", 0)
            _STATE["segments_total"] = stats.get("total_segments", 0)

        untried = _count_untried(profession_id, dept)
        with _LOCK:
            _STATE["suspects"] = untried

        if untried >= target:
            break

    untried = _count_untried(profession_id, dept)
    with _LOCK:
        _STATE["suspects"] = untried
    return untried > 0


def _phase2_enrich(profession_id: str, qty: int, dept: Optional[str]):
    """Enrichit les suspects enrichi_at IS NULL jusqu'à qty contacts créés."""
    from ...gemini_places import fetch_company_info
    from ...enrich import enrich_website
    from ...models import V3ProspectDB, ProfessionDB, SireneSuspectDB
    from ...api.routes.enrich_admin import _valid_email, _is_mobile

    gemini_key = os.getenv("GEMINI_API_KEY", "")

    with _LOCK:
        _STATE["phase"] = "enrichissement"
        contacts_created = _STATE["contacts"]

    with SessionLocal() as db:
        prof       = db.query(ProfessionDB).filter_by(id=profession_id).first()
        prof_label = prof.label if prof else profession_id
        kw_sirene  = json.loads(prof.mots_cles_sirene or "[]") if prof else []
        kw_lower   = [k.lower() for k in kw_sirene]

    BATCH = 50

    while contacts_created < qty:
        if _STATE["stop_requested"]:
            break

        # Récupère le prochain batch de suspects non encore tentés
        with SessionLocal() as db:
            q = db.query(SireneSuspectDB).filter(
                SireneSuspectDB.profession_id == profession_id,
                SireneSuspectDB.enrichi_at.is_(None),
            )
            if dept:
                q = q.filter(SireneSuspectDB.departement == dept)
            rows = q.limit(BATCH).all()
            # Extraire les données avant fermeture session
            suspects = [(s.id, s.raison_sociale, s.ville, s.departement) for s in rows]

        if not suspects:
            break  # plus rien à traiter

        # Mise à jour du compteur suspects restants
        with _LOCK:
            _STATE["suspects"] = _count_untried(profession_id, dept)

        for s_id, raison_sociale, ville, s_dept in suspects:
            if contacts_created >= qty or _STATE["stop_requested"]:
                break

            # ── Marquer immédiatement comme "tenté" ──────────────────────────
            with SessionLocal() as db:
                s_obj = db.get(SireneSuspectDB, s_id)
                if s_obj:
                    s_obj.enrichi_at = datetime.utcnow()
                    db.commit()

            # Filtre de sécurité mots-clés SIRENE
            if kw_lower:
                nom_l = (raison_sociale or "").lower()
                if not any(kw in nom_l for kw in kw_lower):
                    with _LOCK:
                        _STATE["processed"] += 1
                    continue

            ville_str = ville or ""
            entry = {"name": raison_sociale, "city": ville_str,
                     "contact": False, "email": None, "mobile": None}
            try:
                details = fetch_company_info(raison_sociale, ville_str, gemini_key) if gemini_key else {}
                website = details.get("website") or ""
                phone   = details.get("formatted_phone_number") or ""

                email = None
                mobile = None
                fixe = None

                if website:
                    scraped     = enrich_website(website, timeout=5)
                    email       = _valid_email(scraped.get("email"))
                    scraped_mob = scraped.get("mobile") or ""
                    if scraped_mob and _is_mobile(scraped_mob):
                        mobile = scraped_mob
                    elif phone and _is_mobile(phone):
                        mobile = phone
                    else:
                        mobile = None
                    fixe = phone if phone and not _is_mobile(phone) else None
                elif phone:
                    # Pas de site web mais Gemini a trouvé un téléphone → on prend quand même
                    if _is_mobile(phone):
                        mobile = phone
                    else:
                        fixe = phone

                # Contact valide = email OU mobile OU fixe (on ne perd plus les landlines)
                has_contact = bool(email or mobile or fixe)
                entry.update({"email": email, "mobile": mobile or fixe, "contact": has_contact})

                if has_contact:
                    tok = secrets.token_hex(16)
                    with SessionLocal() as db2:
                        db2.add(V3ProspectDB(
                            token=tok, name=raison_sociale, city=ville_str,
                            profession=prof_label, phone=mobile or fixe,
                            website=website or None, email=email,
                            rating=details.get("rating"),
                            reviews_count=details.get("user_ratings_total"),
                            landing_url=f"/l/{tok}", scrape_status="done",
                            status="PROSPECT",
                            notes=f"siret:{s_id} | dept:{s_dept or ''} | web:{website or ''}"
                                  + (f" | mobile:{mobile}" if mobile else "")
                                  + (f" | fixe:{fixe}" if fixe else ""),
                        ))
                        s_src = db2.get(SireneSuspectDB, s_id)
                        if s_src:
                            s_src.contactable = True
                        db2.commit()
                    contacts_created += 1
                    with _LOCK:
                        _STATE["contacts"] = contacts_created
                        _STATE["enriched"] += 1
                else:
                    with _LOCK:
                        _STATE["enriched"] += 1

            except Exception as e:
                log.warning("[LEADS] %s: %s", raison_sociale, e)

            with _LOCK:
                _STATE["processed"] += 1
                _STATE["results"].append(entry)
                if len(_STATE["results"]) > 100:
                    _STATE["results"] = _STATE["results"][-100:]

        # Mise à jour suspects restants après chaque batch
        with _LOCK:
            _STATE["suspects"] = _count_untried(profession_id)
