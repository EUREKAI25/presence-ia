"""
active_pair.py — Gestion de la paire active (Chantier C)

Sélection automatique : meilleure paire disponible par score décroissant.
Une seule paire active à la fois. Saturation → passage à la paire suivante.
Override admin : forcer une paire spécifique ou réinitialiser.

État stocké dans data/active_pair_state.json (lecture à chaque requête, pas de
cache process — compatible multi-process/redémarrage).
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_STATE_FILE = Path(__file__).parent.parent / "data" / "active_pair_state.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── Lecture / écriture état ───────────────────────────────────────────────────

def get_active_pair() -> dict | None:
    """
    Retourne la paire active courante :
      {city, profession, target_id, score, started_at, override}
    ou None si aucune paire sélectionnée.
    """
    try:
        if _STATE_FILE.exists():
            state = json.loads(_STATE_FILE.read_text())
            if state.get("city") and state.get("profession"):
                return state
    except Exception:
        pass
    return None


def set_active_pair(city: str, profession: str, score: float = 0.0,
                    target_id: str = "", override: bool = False) -> dict:
    """Définit une nouvelle paire active. Écrase l'état précédent."""
    state = {
        "city":       city,
        "profession": profession,
        "target_id":  target_id,
        "score":      round(score, 1),
        "started_at": _now_iso(),
        "override":   override,
    }
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    log.info("active_pair: nouvelle paire — %s / %s (score=%.1f)", profession, city, score)
    return state


def clear_active_pair(reason: str = "saturation"):
    """Efface la paire active (saturation ou reset admin)."""
    if _STATE_FILE.exists():
        _STATE_FILE.unlink()
    log.info("active_pair: effacée (%s)", reason)


# ── Sélection automatique ─────────────────────────────────────────────────────

def select_next_pair(db) -> dict | None:
    """
    Sélectionne la prochaine paire directement depuis V3ProspectDB :
    - Uniquement les paires avec ≥1 prospect dispo (ia_results + email + not sent)
    - Classées par score_métier × log(stock) décroissant
    Indépendant de ProspectionTargetDB (qui pilote Google Places, pas l'outbound).
    """
    import math
    from src.models import ProfessionDB, ScoringConfigDB, V3ProspectDB
    from src.database import db_score_global
    from sqlalchemy import func, or_

    cfg = db.query(ScoringConfigDB).filter_by(id="default").first()

    # Index profession : id ET label → ProfessionDB (gère slug et label)
    all_profs = db.query(ProfessionDB).filter(ProfessionDB.actif == True).all()
    _prof_idx: dict = {}
    for p in all_profs:
        _prof_idx[p.id.strip().lower()]    = p
        _prof_idx[p.label.strip().lower()] = p

    # Vérifier si refs_only est actif (défaut True)
    refs_only = True
    if cfg and hasattr(cfg, "outbound_refs_only"):
        refs_only = bool(cfg.outbound_refs_only)

    # Stock email dispo
    _email_q = (
        db.query(V3ProspectDB.city, V3ProspectDB.profession, func.count().label("n"))
        .filter(
            V3ProspectDB.email.isnot(None),
            V3ProspectDB.sent_at.is_(None),
            V3ProspectDB.ia_results.isnot(None),
            or_(
                V3ProspectDB.email_status.is_(None),
                V3ProspectDB.email_status.notin_(["bounced", "unsubscribed"]),
            ),
        )
    )
    if refs_only:
        _email_q = _email_q.filter(V3ProspectDB.city_reference.isnot(None))
    email_pairs = _email_q.group_by(V3ProspectDB.city, V3ProspectDB.profession).all()

    # Stock SMS dispo (phone sans email)
    _sms_q = (
        db.query(V3ProspectDB.city, V3ProspectDB.profession, func.count().label("n"))
        .filter(
            V3ProspectDB.phone.isnot(None),
            V3ProspectDB.email.is_(None),
            V3ProspectDB.sent_at.is_(None),
            V3ProspectDB.ia_results.isnot(None),
        )
    )
    if refs_only:
        _sms_q = _sms_q.filter(V3ProspectDB.city_reference.isnot(None))
    sms_pairs = _sms_q.group_by(V3ProspectDB.city, V3ProspectDB.profession).all()

    # Fusionner email + SMS par (city, profession)
    stock: dict = {}
    for r in email_pairs:
        stock[(r.city, r.profession)] = stock.get((r.city, r.profession), 0) + r.n
    for r in sms_pairs:
        stock[(r.city, r.profession)] = stock.get((r.city, r.profession), 0) + r.n

    if not stock:
        log.info("active_pair: aucune paire disponible dans V3ProspectDB")
        return None

    # Score combiné = score_métier (0-10) × 2  +  log(stock)
    scored = []
    for (city, profession), n in stock.items():
        prof       = _prof_idx.get(profession.strip().lower())
        prof_score = db_score_global(prof, cfg) if (prof and cfg) else 0.0
        combined   = prof_score * 2 + math.log1p(n)
        scored.append(((city, profession, n), prof_score, combined))

    scored.sort(key=lambda x: x[2], reverse=True)
    (best_city, best_profession, best_n), best_prof_score, _ = scored[0]

    log.info(
        "active_pair: %d paires dispo — meilleure = %s / %s (stock=%d, score=%.1f)",
        len(stock), best_profession, best_city, best_n, best_prof_score,
    )
    return set_active_pair(
        city=best_city,
        profession=best_profession,
        score=best_prof_score,
        target_id="auto",
    )


# ── Saturation ────────────────────────────────────────────────────────────────

def check_saturation(db) -> dict | None:
    """
    Vérifie si la paire active est saturée (0 prospect disponible).
    Si saturée → efface + sélectionne la suivante.
    Si aucune paire active → sélectionne la meilleure.
    Retourne l'état actif (inchangé ou nouveau) ou None.
    """
    state = get_active_pair()

    if not state:
        return select_next_pair(db)

    if _available_count(db, state["city"], state["profession"]) == 0:
        log.info(
            "active_pair: saturée — %s / %s → passage à la suivante",
            state["profession"], state["city"],
        )
        clear_active_pair("saturation")
        return select_next_pair(db)

    return state


def _available_count(db, city: str, profession: str) -> int:
    """Nombre de prospects disponibles pour outbound (email + SMS) sur cette paire."""
    from src.models import V3ProspectDB, ScoringConfigDB
    from sqlalchemy import or_
    cfg = db.query(ScoringConfigDB).filter_by(id="default").first()
    refs_only = True
    if cfg and hasattr(cfg, "outbound_refs_only"):
        refs_only = bool(cfg.outbound_refs_only)

    email_q = db.query(V3ProspectDB).filter(
        V3ProspectDB.city       == city,
        V3ProspectDB.profession == profession,
        V3ProspectDB.email.isnot(None),
        V3ProspectDB.sent_at.is_(None),
        or_(
            V3ProspectDB.email_status.is_(None),
            V3ProspectDB.email_status.notin_(["bounced", "unsubscribed"]),
        ),
    )
    sms_q = db.query(V3ProspectDB).filter(
        V3ProspectDB.city       == city,
        V3ProspectDB.profession == profession,
        V3ProspectDB.phone.isnot(None),
        V3ProspectDB.email.is_(None),
        V3ProspectDB.sent_at.is_(None),
    )
    if refs_only:
        email_q = email_q.filter(V3ProspectDB.city_reference.isnot(None))
        sms_q   = sms_q.filter(V3ProspectDB.city_reference.isnot(None))
    return email_q.count() + sms_q.count()
