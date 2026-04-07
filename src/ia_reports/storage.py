"""
Persistance des snapshots IA dans la table ia_snapshots.

Fonctions :
  save_snapshot(...)         → enregistre un snapshot en DB, retourne l'id
  load_last_snapshot(...)    → charge le snapshot le plus récent
  load_snapshot_history(...) → liste tous les snapshots d'un prospect
  ensure_table(engine)       → crée la table si elle n'existe pas (idempotent)

La table ia_snapshots doit exister (créée par init_db() via IaSnapshotDB).
La migration est idempotente : la fonction ensure_table() vérifie avant de créer.
"""

import json
import logging
from datetime import datetime

log = logging.getLogger(__name__)


# ── Import modèle — compatible package et standalone ──────────────────────────

def _get_model():
    """Charge IaSnapshotDB — robuste face aux deux contextes d'import."""
    try:
        from ..models import IaSnapshotDB
        return IaSnapshotDB
    except ImportError:
        pass
    try:
        from src.models import IaSnapshotDB
        return IaSnapshotDB
    except ImportError:
        pass
    raise ImportError(
        "Impossible d'importer IaSnapshotDB. "
        "Vérifiez que src/models.py contient bien ce modèle."
    )


# ── Migration idempotente ─────────────────────────────────────────────────────

def ensure_table(engine) -> None:
    """
    Crée la table ia_snapshots si elle n'existe pas.
    Idempotent — peut être appelé plusieurs fois sans effet de bord.

    Args:
        engine : instance SQLAlchemy Engine
    """
    try:
        from ..models import Base
    except ImportError:
        from src.models import Base

    # create_all ne recrée pas les tables existantes
    IaSnapshotDB = _get_model()
    IaSnapshotDB.__table__.create(bind=engine, checkfirst=True)
    log.debug("ensure_table: ia_snapshots prête")


# ── Sauvegarde ────────────────────────────────────────────────────────────────

def save_snapshot(
    db,
    prospect_token: str,
    score_data: dict,
    queries: list[dict],
    competitors: list[dict],
    html: str,
    report_type: str = "audit",
) -> int:
    """
    Enregistre un snapshot dans ia_snapshots.

    Args:
        db             : session SQLAlchemy
        prospect_token : token du prospect V3
        score_data     : dict retourné par scoring.compute_score()
        queries        : structure canonique retournée par parser.parse_ia_results()
        competitors    : liste retournée par scoring.extract_competitors()
        html           : HTML du rapport généré
        report_type    : "audit" | "monthly"

    Returns:
        int : id du snapshot créé
    """
    IaSnapshotDB = _get_model()

    # Sérialise les queries en enlevant les réponses brutes (trop volumineuses)
    matrix_lite = [
        {k: v for k, v in q.items() if k != "responses"}
        for q in queries
    ]

    snap = IaSnapshotDB(
        prospect_token   = prospect_token,
        report_type      = report_type,
        score            = int(score_data["score"]),
        nb_mentions      = score_data["total_citations"],
        nb_total         = score_data["total_possible"],
        matrix_json      = json.dumps(matrix_lite, ensure_ascii=False),
        competitors_json = json.dumps(competitors, ensure_ascii=False),
        report_html      = html,
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    log.info("Snapshot sauvegardé : token=%s type=%s score=%s id=%s",
             prospect_token, report_type, score_data["score"], snap.id)
    return snap.id


# ── Lecture ───────────────────────────────────────────────────────────────────

def load_last_snapshot(db, prospect_token: str) -> dict | None:
    """
    Charge le snapshot le plus récent pour un prospect.

    Returns:
        dict avec les clés :
          score, date, nb_mentions, nb_total, queries, competitors
        ou None si aucun snapshot trouvé.
    """
    IaSnapshotDB = _get_model()
    snap = (
        db.query(IaSnapshotDB)
        .filter(IaSnapshotDB.prospect_token == prospect_token)
        .order_by(IaSnapshotDB.created_at.desc())
        .first()
    )
    if not snap:
        return None

    queries = []
    if snap.matrix_json:
        try:
            queries = json.loads(snap.matrix_json)
        except Exception:
            pass

    competitors = []
    if snap.competitors_json:
        try:
            competitors = json.loads(snap.competitors_json)
        except Exception:
            pass

    date_str = ""
    if snap.created_at:
        months = ["", "janvier", "février", "mars", "avril", "mai", "juin",
                  "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        d = snap.created_at
        date_str = f"{d.day} {months[d.month]} {d.year}"

    return {
        "snapshot_id":  snap.id,
        "report_type":  snap.report_type,
        "score":        snap.score,
        "date":         date_str,
        "nb_mentions":  snap.nb_mentions,
        "nb_total":     snap.nb_total,
        "queries":      queries,
        "competitors":  competitors,
    }


def load_snapshot_history(db, prospect_token: str) -> list[dict]:
    """
    Retourne tous les snapshots d'un prospect, du plus ancien au plus récent.

    Returns:
        list[dict] : [{snapshot_id, report_type, score, date, nb_mentions, nb_total}, ...]
    """
    IaSnapshotDB = _get_model()
    snaps = (
        db.query(IaSnapshotDB)
        .filter(IaSnapshotDB.prospect_token == prospect_token)
        .order_by(IaSnapshotDB.created_at.asc())
        .all()
    )

    months = ["", "janvier", "février", "mars", "avril", "mai", "juin",
              "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

    result = []
    for s in snaps:
        d      = s.created_at
        date_s = f"{d.day} {months[d.month]} {d.year}" if d else ""
        result.append({
            "snapshot_id": s.id,
            "report_type": s.report_type,
            "score":       s.score,
            "date":        date_s,
            "nb_mentions": s.nb_mentions,
            "nb_total":    s.nb_total,
        })

    return result


def count_snapshots(db, prospect_token: str) -> int:
    """Retourne le nombre de snapshots existants pour un prospect."""
    IaSnapshotDB = _get_model()
    return (
        db.query(IaSnapshotDB)
        .filter(IaSnapshotDB.prospect_token == prospect_token)
        .count()
    )
