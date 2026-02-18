"""
Upload + enrichissement email + envoi Brevo
Routes :
  POST /admin/prospect/{pid}/upload-proof-image
  POST /admin/prospect/{pid}/upload-city-image
  POST /admin/prospect/{pid}/upload-video
  POST /admin/prospect/{pid}/enrich-email
  POST /admin/prospect/{pid}/send-email
"""
import logging
import os
from pathlib import Path

import requests as http
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_prospect
from ...enrich import extract_email_from_website
from ...generate import landing_url

log = logging.getLogger(__name__)

router = APIRouter(tags=["Upload"])

BASE_URL     = os.getenv("BASE_URL", "http://localhost:8001")
SENDER_NAME  = os.getenv("SENDER_NAME", "PRESENCE_IA")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "contact@presence-ia.com")

# Répertoire de stockage des fichiers uploadés
_DEFAULT_UPLOADS = str(Path(__file__).parent.parent.parent.parent / "dist" / "uploads")


def _uploads_dir() -> Path:
    return Path(os.getenv("UPLOADS_DIR", _DEFAULT_UPLOADS))


def _check_token(request: Request):
    token = request.headers.get("X-Admin-Token") or request.query_params.get("token")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Token admin invalide")


def _get_prospect_or_404(db: Session, pid: str):
    p = db_get_prospect(db, pid)
    if not p:
        raise HTTPException(404, f"Prospect {pid} introuvable")
    return p


def _upload_file(pid: str, filename: str, file: UploadFile) -> str:
    """Sauvegarde le fichier, retourne l'URL publique."""
    dest_dir = _uploads_dir() / pid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    content = file.file.read()
    dest.write_bytes(content)
    return f"{os.getenv('BASE_URL', 'http://localhost:8001')}/dist/uploads/{pid}/{filename}"


# ── Upload proof image ───────────────────────────────────────────────────────

@router.post("/admin/prospect/{pid}/upload-proof-image")
def upload_proof_image(
    pid: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _check_token(request)
    p = _get_prospect_or_404(db, pid)
    url = _upload_file(pid, "proof.jpg", file)
    p.proof_image_url = url
    db.commit()
    return {"url": url, "prospect_id": pid}


# ── Upload city image ────────────────────────────────────────────────────────

@router.post("/admin/prospect/{pid}/upload-city-image")
def upload_city_image(
    pid: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _check_token(request)
    p = _get_prospect_or_404(db, pid)
    url = _upload_file(pid, "city.jpg", file)
    p.city_image_url = url
    db.commit()
    return {"url": url, "prospect_id": pid}


# ── Upload vidéo (fichier) ou enregistrer URL ────────────────────────────────

@router.post("/admin/prospect/{pid}/upload-video")
def upload_video(
    pid: str,
    request: Request,
    video_url: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    _check_token(request)
    p = _get_prospect_or_404(db, pid)

    if file and file.filename:
        url = _upload_file(pid, "video.mp4", file)
    elif video_url:
        url = video_url
    else:
        raise HTTPException(400, "Fournir un fichier ou une video_url")

    p.video_url = url
    db.commit()
    return {"url": url, "prospect_id": pid}


# ── Enrichissement email ─────────────────────────────────────────────────────

@router.post("/admin/prospect/{pid}/enrich-email")
def enrich_email(
    pid: str,
    request: Request,
    db: Session = Depends(get_db),
):
    _check_token(request)
    p = _get_prospect_or_404(db, pid)

    if not p.website:
        raise HTTPException(400, "Prospect sans site web — enrichissement impossible")

    email = extract_email_from_website(p.website)
    if email:
        p.email = email
        db.commit()
        return {"email": email, "found": True}

    return {"email": None, "found": False}


# ── Envoi email Brevo ────────────────────────────────────────────────────────

@router.post("/admin/prospect/{pid}/send-email")
def send_email(
    pid: str,
    request: Request,
    db: Session = Depends(get_db),
):
    _check_token(request)
    p = _get_prospect_or_404(db, pid)

    if not p.email:
        raise HTTPException(400, "Email prospect manquant — enrichir d'abord")
    brevo_key = os.getenv("BREVO_API_KEY", "")
    if not brevo_key:
        raise HTTPException(500, "BREVO_API_KEY non configurée")

    import json as _json
    from ...generate import email_generate
    ed = email_generate(db, p)

    payload = {
        "sender":    {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to":        [{"email": p.email, "name": p.name}],
        "subject":   ed["subject"],
        "textContent": ed["body"],
    }

    resp = http.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": brevo_key, "Content-Type": "application/json"},
        data=_json.dumps(payload),
        timeout=10,
    )

    if resp.status_code not in (200, 201):
        log.error("Brevo error %s: %s", resp.status_code, resp.text)
        raise HTTPException(502, f"Brevo API error {resp.status_code}")

    p.status = "SENT_MANUAL"
    db.commit()
    return {"sent": True, "email": p.email, "subject": ed["subject"],
            "message_id": resp.json().get("messageId")}
