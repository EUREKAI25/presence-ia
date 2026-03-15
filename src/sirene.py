"""
Client SIRENE — recherche-entreprises.api.gouv.fr

Architecture en segments : chaque requête = 1 combinaison (NAF × département).
- Suivi dans SireneSegmentDB (status: pending/running/done/error)
- Mise à jour incrémentale via last_date_creation
- Exécution une paire à la fois, dans l'ordre de score décroissant
- Zéro doublon : un siret existant est mis à jour, pas réinséré

Nature juridique scoring :
  EI / micro (1000, 1100)     → score 1.0 — cible principale
  EURL / SARL (5499, 5720)    → score 0.8
  SAS / SASU  (5710, 5308)    → score 0.3
  Autres                       → score 0.1
"""
import json, logging, time, hashlib
from datetime import datetime
from typing import Optional
import urllib.request, urllib.parse

log = logging.getLogger(__name__)

_BASE     = "https://recherche-entreprises.api.gouv.fr/search"
_PER_PAGE = 25
_DELAY    = 0.25   # secondes entre requêtes

# Départements métropolitains + DOM (codes à 2 chiffres sauf DOM)
DEPARTEMENTS = [
    "01","02","03","04","05","06","07","08","09","10",
    "11","12","13","14","15","16","17","18","19","21",
    "22","23","24","25","26","27","28","29","2A","2B",
    "30","31","32","33","34","35","36","37","38","39",
    "40","41","42","43","44","45","46","47","48","49",
    "50","51","52","53","54","55","56","57","58","59",
    "60","61","62","63","64","65","66","67","68","69",
    "70","71","72","73","74","75","76","77","78","79",
    "80","81","82","83","84","85","86","87","88","89",
    "90","91","92","93","94","95","971","972","973","974",
]

# Poids des départements (population relative — simplifié)
# Plus le dept est dense/peuplé, plus il est prioritaire
DEPT_WEIGHT = {
    "75": 3.0, "69": 2.5, "13": 2.5, "59": 2.0, "92": 2.0,
    "93": 1.8, "94": 1.8, "33": 1.7, "31": 1.7, "67": 1.6,
    "44": 1.6, "06": 1.5, "34": 1.5, "76": 1.5, "38": 1.4,
    "78": 1.4, "91": 1.4, "95": 1.4, "77": 1.3, "57": 1.3,
    "974": 1.2, "972": 1.1, "971": 1.1, "973": 1.0,
}

# Scoring nature juridique
NJ_SCORE = {
    "1000": 1.0,  # EI
    "1100": 1.0,  # micro-entreprise
    "1200": 0.9,  # autres personnes physiques
    "5499": 0.8,  # SARL (non cotée)
    "5720": 0.8,  # EURL
    "5710": 0.3,  # SAS
    "5308": 0.3,  # SASU
}
NJ_CIBLE = list(NJ_SCORE.keys())  # on filtre sur ces codes


def _segment_id(profession_id: str, naf: str, dept: str) -> str:
    return f"{profession_id}|{naf}|{dept}"


def _naf_api(code: str) -> str:
    """'4322A' → '43.22A'"""
    code = code.strip().upper()
    if len(code) == 5 and "." not in code:
        return f"{code[:2]}.{code[2:]}"
    return code


def _fetch_segment(naf: str, dept: str, since_date: Optional[str] = None,
                   page: int = 1) -> dict:
    """Une page d'une requête NAF × département, optionnellement filtrée par date."""
    params = {
        "activite_principale": _naf_api(naf),
        "departement":         dept,
        "etat_administratif":  "A",
        "per_page":            str(_PER_PAGE),
        "page":                str(page),
    }
    # Filtre date de création pour mises à jour incrémentales
    if since_date:
        params["date_creation_min"] = since_date
    url = _BASE + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "presence-ia/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log.warning(f"SIRENE fetch error naf={naf} dept={dept} p={page}: {e}")
        return {}


def fetch_segment_complete(naf: str, dept: str,
                           since_date: Optional[str] = None) -> list[dict]:
    """
    Récupère TOUS les établissements d'un segment NAF × département.
    Pagine jusqu'à épuisement (max 400 pages = 10 000 résultats).
    """
    results = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        data = _fetch_segment(naf, dept, since_date, page)
        if not data or "results" not in data:
            break

        total_results = data.get("total_results", 0)
        total_pages   = min(data.get("total_pages", 1), 400)

        for item in data.get("results", []):
            siege = item.get("siege") or {}
            siret = (siege.get("siret") or item.get("siret") or "").strip()
            if not siret:
                continue

            nom  = (item.get("nom_complet") or item.get("nom_raison_sociale")
                    or siege.get("denomination_usuelle") or "").strip() or siret
            ville = (siege.get("libelle_commune") or siege.get("commune") or "").strip().upper()
            cp    = (siege.get("code_postal") or "").strip()
            d     = (siege.get("departement") or cp[:2] if len(cp) >= 2 else dept).strip()
            nj    = (item.get("nature_juridique") or "").strip()
            date_crea = (item.get("date_creation") or "")

            results.append({
                "siret":             siret,
                "raison_sociale":    nom,
                "ville":             ville or None,
                "code_postal":       cp or None,
                "departement":       d or dept,
                "code_naf":          naf,
                "nature_juridique":  nj or None,
                "date_creation":     date_crea or None,
                "nj_score":          NJ_SCORE.get(nj, 0.1),
                "actif":             True,
                "contactable":       False,
            })

        log.debug(f"SIRENE {naf}×{dept} p{page}/{total_pages} → {len(data.get('results',[]))} ({total_results} total)")
        page += 1
        if page <= total_pages:
            time.sleep(_DELAY)

    return results


# ── Gestion des segments ───────────────────────────────────────────────────

def generate_segments(db, profession_ids: list[str] = None) -> int:
    """
    Génère les segments (NAF × département) pour les professions actives.
    Calcule le score de priorité. N'écrase pas les segments déjà done/running.
    Retourne le nb de nouveaux segments créés.
    """
    from .models import SireneSegmentDB, ProfessionDB
    from .database import db_score_global, db_get_scoring_config

    cfg   = db_get_scoring_config(db)
    query = db.query(ProfessionDB).filter_by(actif=True)
    if profession_ids:
        query = query.filter(ProfessionDB.id.in_(profession_ids))
    profs = query.all()

    created = 0
    for prof in profs:
        codes_naf = []
        try:
            codes_naf = json.loads(prof.codes_naf or "[]")
        except Exception:
            pass
        if not codes_naf:
            continue

        prof_score = db_score_global(prof, cfg)

        for naf in codes_naf:
            for dept in DEPARTEMENTS:
                seg_id = _segment_id(prof.id, naf, dept)
                existing = db.query(SireneSegmentDB).filter_by(id=seg_id).first()
                if existing:
                    continue  # déjà en base, on ne réinitialise pas

                dept_weight = DEPT_WEIGHT.get(dept, 1.0)
                score = round(prof_score * dept_weight, 3)

                seg = SireneSegmentDB(
                    id=seg_id,
                    profession_id=prof.id,
                    code_naf=naf,
                    departement=dept,
                    score=score,
                    nj_filter=json.dumps(NJ_CIBLE),
                    status="pending",
                )
                db.add(seg)
                created += 1

    db.commit()
    log.info(f"[SIRENE] {created} nouveaux segments générés")
    return created


def run_next_segment(db) -> Optional[dict]:
    """
    Exécute le prochain segment pending (score desc).
    Retourne un résumé ou None si aucun segment en attente.
    """
    from .models import SireneSegmentDB
    from .database import db_sirene_upsert
    from datetime import datetime as _dt

    seg = (db.query(SireneSegmentDB)
           .filter_by(status="pending")
           .order_by(SireneSegmentDB.score.desc())
           .first())

    if not seg:
        return None

    seg.status = "running"
    db.commit()

    try:
        items = fetch_segment_complete(
            seg.code_naf, seg.departement,
            since_date=seg.last_date_creation
        )

        inserted = 0
        last_date = seg.last_date_creation

        for item in items:
            siret = item.pop("siret")
            nj_score = item.pop("nj_score", 0.1)
            date_crea = item.get("date_creation")

            data = {
                "id":           siret,
                "profession_id": seg.profession_id,
                **item,
            }
            db_sirene_upsert(db, data)
            inserted += 1

            if date_crea and (not last_date or date_crea > last_date):
                last_date = date_crea

        seg.status          = "done"
        seg.nb_results      = len(items)
        seg.nb_inserted     = inserted
        seg.last_fetched_at = _dt.utcnow()
        seg.last_date_creation = last_date
        seg.error_msg       = None
        db.commit()

        result = {
            "segment_id":  seg.id,
            "profession":  seg.profession_id,
            "naf":         seg.code_naf,
            "dept":        seg.departement,
            "nb_results":  len(items),
            "nb_inserted": inserted,
        }
        log.info(f"[SIRENE] Segment {seg.id} → {inserted} suspects")
        return result

    except Exception as e:
        seg.status    = "error"
        seg.error_msg = str(e)
        db.commit()
        log.error(f"[SIRENE] Segment {seg.id} ERREUR: {e}")
        return {"segment_id": seg.id, "error": str(e)}


def segments_stats(db) -> dict:
    """Résumé de l'état de la queue."""
    from .models import SireneSegmentDB
    from sqlalchemy import func

    rows = (db.query(SireneSegmentDB.status, func.count(SireneSegmentDB.id))
            .group_by(SireneSegmentDB.status).all())
    stats = {r[0]: r[1] for r in rows}
    total_suspects = db.query(func.count()).select_from(
        __import__('src.models', fromlist=['SireneSuspectDB']).SireneSuspectDB
    ).scalar() or 0
    return {
        "pending":       stats.get("pending", 0),
        "done":          stats.get("done", 0),
        "running":       stats.get("running", 0),
        "error":         stats.get("error", 0),
        "total_segments": sum(stats.values()),
        "total_suspects": total_suspects,
    }


# ── Qualify all active (legacy — remplacé par le runner de segments) ────────

def qualify_all_active(db, max_per_naf: int = 200) -> dict:
    """Génère les segments si besoin, puis lance le runner en boucle."""
    generated = generate_segments(db)
    log.info(f"[SIRENE] {generated} segments générés, lancement du runner...")
    summary = {}
    while True:
        result = run_next_segment(db)
        if result is None:
            break
        seg_id = result.get("segment_id", "?")
        summary[seg_id] = result.get("nb_inserted", 0)
    return summary
