"""
Module ASSETS GATE — gate stricte READY_TO_SEND
POST /api/prospect/{id}/assets
POST /api/prospect/{id}/mark-ready
"""
from sqlalchemy.orm import Session
from .database import db_get_prospect
from .models import AssetsInput, ProspectDB, ProspectStatus


def set_assets(db: Session, pid: str, assets: AssetsInput) -> ProspectDB:
    p = db_get_prospect(db, pid)
    if not p: raise ValueError(f"Prospect {pid} introuvable")
    if not assets.video_url.strip():      raise ValueError("video_url obligatoire")
    if not assets.screenshot_url.strip(): raise ValueError("screenshot_url obligatoire")
    p.video_url      = assets.video_url.strip()
    p.screenshot_url = assets.screenshot_url.strip()
    if p.status == ProspectStatus.SCORED.value:
        p.status = ProspectStatus.READY_ASSETS.value
    db.commit(); db.refresh(p); return p


def mark_ready(db: Session, pid: str) -> ProspectDB:
    p = db_get_prospect(db, pid)
    if not p: raise ValueError(f"Prospect {pid} introuvable")
    errs = []
    if not p.video_url:                              errs.append("video_url manquante")
    if not p.screenshot_url:                         errs.append("screenshot_url manquante")
    if not p.eligibility_flag:                       errs.append("EMAIL_OK = False")
    if p.status != ProspectStatus.READY_ASSETS.value: errs.append(f"statut '{p.status}' ≠ READY_ASSETS")
    if errs: raise ValueError("Gate bloquée : " + " | ".join(errs))
    p.status = ProspectStatus.READY_TO_SEND.value
    db.commit(); db.refresh(p); return p
