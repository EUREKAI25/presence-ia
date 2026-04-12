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

    # Toutes les paires ayant du stock outbound dispo
    pairs = (
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
        .group_by(V3ProspectDB.city, V3ProspectDB.profession)
        .all()
    )

    if not pairs:
        log.info("active_pair: aucune paire disponible dans V3ProspectDB")
        return None

    # Score combiné = score_métier (0-10) × 2  +  log(stock)
    scored = []
    for p in pairs:
        prof       = db.query(ProfessionDB).filter(ProfessionDB.label == p.profession).first()
        prof_score = db_score_global(prof, cfg) if (prof and cfg) else 0.0
        combined   = prof_score * 2 + math.log1p(p.n)
        scored.append((p, prof_score, combined))

    scored.sort(key=lambda x: x[2], reverse=True)
    best, best_prof_score, _ = scored[0]

    log.info(
        "active_pair: %d paires dispo — meilleure = %s / %s (stock=%d, score=%.1f)",
        len(pairs), best.profession, best.city, best.n, best_prof_score,
    )
    return set_active_pair(
        city=best.city,
        profession=best.profession,
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
    """Nombre de prospects disponibles pour outbound sur cette paire."""
    from src.models import V3ProspectDB
    from sqlalchemy import or_
    return db.query(V3ProspectDB).filter(
        V3ProspectDB.city       == city,
        V3ProspectDB.profession == profession,
        V3ProspectDB.email.isnot(None),
        V3ProspectDB.sent_at.is_(None),
        # NULL NOT IN (...) = NULL en SQL → exclut à tort les lignes sans statut
        or_(
            V3ProspectDB.email_status.is_(None),
            V3ProspectDB.email_status.notin_(["bounced", "unsubscribed"]),
        ),
    ).count()
