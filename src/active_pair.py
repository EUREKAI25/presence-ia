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
    Sélectionne la prochaine paire :
    1. Toutes les paires actives (ProspectionTargetDB.active=True)
    2. Triées par score profession décroissant (db_score_global)
    3. Première avec au moins 1 prospect disponible pour outbound
    Retourne le nouvel état ou None si toutes saturées.
    """
    from src.models import ProspectionTargetDB, ProfessionDB, ScoringConfigDB
    from src.database import db_score_global

    cfg     = db.query(ScoringConfigDB).filter_by(id="default").first()
    targets = db.query(ProspectionTargetDB).filter_by(active=True).all()

    if not targets:
        log.info("active_pair: aucune cible active dans prospection_targets")
        return None

    scored = []
    for t in targets:
        prof  = db.query(ProfessionDB).filter_by(id=t.profession).first()
        score = db_score_global(prof, cfg) if (prof and cfg) else 0.0
        scored.append((t, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    for t, score in scored:
        if _available_count(db, t.city, t.profession) > 0:
            return set_active_pair(
                city=t.city,
                profession=t.profession,
                score=score,
                target_id=str(t.id),
            )

    log.info("active_pair: toutes les paires sont saturées (0 prospect disponible)")
    return None


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
