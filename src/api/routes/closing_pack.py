"""Route /closing_pack — Fiche produit réservée aux closers."""
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

CLOSER_TOKEN = os.getenv("CLOSER_TOKEN", "closer-secret")
_FICHE_PATH = Path(__file__).parent.parent.parent.parent / "RESOURCES" / "FICHE_PRODUIT_PRESENCE_IA.html"

router = APIRouter(tags=["Closing Pack"])


@router.get("/closing_pack", response_class=HTMLResponse)
def closing_pack(t: str = ""):
    if not t or t != CLOSER_TOKEN:
        raise HTTPException(403, "Accès refusé")
    if not _FICHE_PATH.exists():
        raise HTTPException(404, "Fiche produit introuvable")
    return _FICHE_PATH.read_text(encoding="utf-8")
