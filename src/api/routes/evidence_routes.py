"""
Evidence Routes — nouvelles routes complémentaires à evidence.py
GET  /api/evidence         → list par profession+city
POST /api/evidence/register → register une preuve via URL
POST /api/evidence/refresh-index → scan disque + sync DB
"""
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...database import get_db

log = logging.getLogger(__name__)
router = APIRouter(tags=["Evidence"])


# ── Schémas ────────────────────────────────────────────────────────────────────

class RegisterEvidenceRequest(BaseModel):
    profession: str
    city: str
    model: str = "openai"
    """Modèle IA source : openai | anthropic | gemini"""
    ts: Optional[str] = None
    """Timestamp ISO. Défaut : maintenant."""
    file_url: str
    """URL de la preuve (déjà uploadée ou accessible)."""
    meta: Optional[dict] = None
    """Métadonnées supplémentaires optionnelles."""


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/api/evidence")
def evidence_list(
    profession: str = Query(...),
    city: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Liste les preuves pour (profession, city), triées par date décroissante.
    """
    from ...evidence.manager import list_evidence
    return list_evidence(db, profession, city, limit=limit)


@router.post("/api/evidence/register")
def evidence_register(req: RegisterEvidenceRequest, db: Session = Depends(get_db)):
    """
    Enregistre une preuve via URL (pas d'upload — URL déjà accessible).
    Retourne l'evidence_id généré.
    """
    from ...evidence.manager import register_evidence
    evidence_id = register_evidence(
        db=db,
        profession=req.profession,
        city=req.city,
        model=req.model,
        ts=req.ts,
        file_url=req.file_url,
        meta=req.meta,
    )
    return {
        "success": True,
        "result": {"evidence_id": evidence_id},
        "message": f"Preuve enregistrée pour {req.profession}/{req.city}",
        "error": None,
    }


@router.post("/api/evidence/refresh-index")
def evidence_refresh_index(db: Session = Depends(get_db)):
    """
    Scanne le répertoire dist/evidence/ sur le disque et synchronise la DB.
    Ajoute les fichiers non encore enregistrés.
    """
    from ...evidence.manager import refresh_index

    evidence_root = Path(
        os.getenv("UPLOADS_DIR", str(Path(__file__).parent.parent.parent.parent / "dist"))
    ).parent / "dist" / "evidence"

    stats = refresh_index(db, evidence_root=evidence_root)
    return {
        "success": True,
        "result": stats,
        "message": (
            f"Index actualisé : {stats['new']} nouveau(x), "
            f"{stats['scanned']} scanné(s), "
            f"{stats['skipped']} ignoré(s)"
        ),
        "error": None,
    }
