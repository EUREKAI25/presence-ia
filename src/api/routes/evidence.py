"""
Evidence — screenshots de preuves partagés par ville+profession.

POST /api/evidence/upload?profession=...&city=...&provider=openai|anthropic|gemini
  Body: file=@screenshot.png (multipart)
  → Stocke sous dist/evidence/{profession}/{city}/YYYY-MM-DD_HHMM_provider_rand.png
  → Retourne {url, filename}

GET /api/evidence/latest?profession=...&city=...&limit=6
  → Retourne liste triée du plus récent au plus ancien
"""
import logging
import os
import random
import string
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from ...database import get_db, db_get_or_create_evidence, db_get_evidence, jl, jd

log = logging.getLogger(__name__)
router = APIRouter(tags=["Evidence"])

VALID_PROVIDERS = {"openai", "anthropic", "gemini"}

BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")


def _evidence_dir() -> Path:
    root = Path(os.getenv("UPLOADS_DIR", str(Path(__file__).parent.parent.parent.parent / "dist"))).parent
    return root / "dist" / "evidence"


def _rand(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


# ── Upload ───────────────────────────────────────────────────────────────────

@router.post("/api/evidence/upload")
def upload_evidence(
    profession: str = Query(...),
    city:       str = Query(...),
    provider:   str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if provider not in VALID_PROVIDERS:
        raise HTTPException(400, f"provider doit être parmi {VALID_PROVIDERS}")

    ts = datetime.utcnow()
    filename = f"{ts.strftime('%Y-%m-%d_%H%M')}_{provider}_{_rand()}.png"

    dest_dir = _evidence_dir() / profession.lower() / city.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(file.file.read())

    rel_path = f"evidence/{profession.lower()}/{city.lower()}/{filename}"
    url = f"{os.getenv('BASE_URL', 'http://localhost:8001')}/dist/{rel_path}"

    # Upsert enregistrement DB
    ev = db_get_or_create_evidence(db, profession, city)
    images = jl(ev.images)
    images.insert(0, {
        "ts":       ts.isoformat(),
        "provider": provider,
        "filename": filename,
        "url":      url,
    })
    ev.images = jd(images)
    db.commit()

    log.info("Evidence uploadée : %s / %s / %s", profession, city, filename)
    return {"url": url, "filename": filename, "provider": provider}


# ── Latest ───────────────────────────────────────────────────────────────────

@router.get("/api/evidence/latest")
def get_latest_evidence(
    profession: str = Query(...),
    city:       str = Query(...),
    limit:      int = Query(6, ge=1, le=50),
    db: Session = Depends(get_db),
):
    ev = db_get_evidence(db, profession, city)
    if not ev:
        return []
    images = jl(ev.images)
    return images[:limit]
