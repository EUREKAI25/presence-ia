"""
Leads Runner — pipeline unifié : qualification SIRENE + enrichissement → ContactDB

POST /admin/leads/run    { profession_id, qty, dept? }
GET  /admin/leads/status → état en temps réel
POST /admin/leads/stop   → demande d'arrêt propre

Logique :
1. Génère les segments si nécessaire
2. Qualifie (run_next_segment) jusqu'à avoir des suspects
3. Enrichit (Google Places + scraping) jusqu'à avoir qty contacts
4. Stoppe dès que qty atteint OU plus de suspects disponibles
"""
import json, logging, os, secrets, threading
from datetime import datetime
from typing import Optional

from fastapi import APIRouter
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
async def leads_run(request, token: str = ""):
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
            "running": True, "phase": "qualification", "stop_requested": False,
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
        _phase1_qualify(profession_id, qty)
        if not _STATE["stop_requested"]:
            _phase2_enrich(profession_id, qty, dept)
    except Exception as e:
        log.error("[LEADS] Erreur pipeline: %s", e)
        with _LOCK:
            _STATE["error"] = str(e)
    finally:
        with _LOCK:
            _STATE["running"]     = False
            _STATE["phase"]       = "done"
            _STATE["finished_at"] = datetime.utcnow().isoformat()


def _phase1_qualify(profession_id: str, qty_wanted: int):
    """Qualifie jusqu'à avoir au moins qty_wanted × 5 suspects (ratio enrichissement ~20%)."""
    from ...sirene import generate_segments, run_next_segment, segments_stats

    with SessionLocal() as db:
        # Vérifier si on a déjà assez de suspects
        from ...models import SireneSuspectDB
        from sqlalchemy import func
        nb_existing = db.query(func.count(SireneSuspectDB.id)).filter_by(
            profession_id=profession_id
        ).scalar() or 0

    target = qty_wanted * 5  # marge pour le taux d'échec enrichissement
    if nb_existing >= target:
        with _LOCK:
            _STATE["suspects"] = nb_existing
            _STATE["phase"]    = "enrichissement"
        return

    with _LOCK:
        _STATE["phase"] = "qualification SIRENE"

    with SessionLocal() as db:
        generated = generate_segments(db, profession_ids=[profession_id])
        log.info("[LEADS] %d segments générés", generated)

    while True:
        if _STATE["stop_requested"]:
            break

        with SessionLocal() as db:
            result = run_next_segment(db, profession_ids=[profession_id])
            stats  = segments_stats(db)

        if result is None:
            break

        with _LOCK:
            _STATE["suspects"]       = stats.get("total_suspects", 0)
            _STATE["segments_done"]  = stats.get("done", 0)
            _STATE["segments_total"] = stats.get("total_segments", 0)

        if _STATE["suspects"] >= target:
            break


def _phase2_enrich(profession_id: str, qty: int, dept: Optional[str]):
    """Enrichit les suspects jusqu'à qty contacts créés dans ContactDB."""
    from ...google_places import fetch_text_search, fetch_place_details
    from ...enrich import enrich_website
    from ...models import V3ProspectDB, ContactDB, ProfessionDB
    from ...api.routes.enrich_admin import _valid_email, _is_mobile

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")

    with _LOCK:
        _STATE["phase"] = "enrichissement"

    with SessionLocal() as db:
        prof = db.query(ProfessionDB).filter_by(id=profession_id).first()
        prof_label = prof.label if prof else profession_id

    BATCH = 50
    page  = 1
    contacts_created = 0

    while contacts_created < qty:
        if _STATE["stop_requested"]:
            break

        with SessionLocal() as db:
            _, suspects = db_suspects_list(db, profession_id=profession_id, dept=dept,
                                           page=page, per_page=BATCH)
        if not suspects:
            break

        for s in suspects:
            if contacts_created >= qty or _STATE["stop_requested"]:
                break

            ville = s.ville or ""
            entry = {"name": s.raison_sociale, "city": ville, "contact": False,
                     "email": None, "mobile": None}
            try:
                places = fetch_text_search(
                    f"{s.raison_sociale} {ville}".strip(), "", api_key, max_results=1
                ) if api_key else []

                if places:
                    details = fetch_place_details(places[0].get("place_id", ""), api_key) if api_key else {}
                    website = details.get("website") or ""
                    phone   = details.get("formatted_phone_number") or ""

                    if website:
                        scraped = enrich_website(website, timeout=5)
                        email   = _valid_email(scraped.get("email"))
                        scraped_mob = scraped.get("mobile") or ""
                        if scraped_mob and _is_mobile(scraped_mob):
                            mobile = scraped_mob
                        elif phone and _is_mobile(phone):
                            mobile = phone
                        else:
                            mobile = None
                        fixe = phone if phone and not _is_mobile(phone) else None

                        has_contact = bool(email or mobile)
                        entry.update({"email": email, "mobile": mobile, "contact": has_contact})

                        if has_contact:
                            tok = secrets.token_hex(16)
                            with SessionLocal() as db2:
                                db2.add(V3ProspectDB(
                                    token=tok, name=s.raison_sociale, city=ville,
                                    profession=prof_label, phone=mobile or fixe,
                                    website=website, email=email,
                                    rating=details.get("rating"),
                                    reviews_count=details.get("user_ratings_total"),
                                    landing_url=f"/v3/{tok}", scrape_status="done",
                                ))
                                db2.add(ContactDB(
                                    company_name=s.raison_sociale, email=email,
                                    phone=mobile or fixe, city=ville,
                                    profession=prof_label, status="PROSPECT",
                                    notes=f"siret:{s.id} | web:{website}"
                                          + (f" | mobile:{mobile}" if mobile else "")
                                          + (f" | fixe:{fixe}" if fixe else ""),
                                ))
                                db2.commit()
                            contacts_created += 1
                            with _LOCK:
                                _STATE["contacts"] = contacts_created
                                _STATE["enriched"] += 1
                        else:
                            with _LOCK:
                                _STATE["enriched"] += 1

            except Exception as e:
                log.warning("[LEADS] %s: %s", s.raison_sociale, e)

            with _LOCK:
                _STATE["processed"] += 1
                _STATE["results"].append(entry)
                if len(_STATE["results"]) > 100:
                    _STATE["results"] = _STATE["results"][-100:]

        page += 1
