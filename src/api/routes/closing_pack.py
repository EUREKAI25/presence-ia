"""Routes /closing_pack, /closing_pack/exemple/* et /recap."""
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

CLOSER_TOKEN = os.getenv("CLOSER_TOKEN", "closer-secret")
_ROOT = Path(__file__).parent.parent.parent.parent / "RESOURCES"
_FICHE_PATH = _ROOT / "FICHE_PRODUIT_PRESENCE_IA.html"
_EXEMPLES_DIR = _ROOT / "exemples"

router = APIRouter(tags=["Closing Pack"])

VALID_SLUG = re.compile(r'^[a-z0-9_-]+$')


@router.get("/closing_pack", response_class=HTMLResponse)
def closing_pack(t: str = ""):
    if not t or t != CLOSER_TOKEN:
        raise HTTPException(403, "Accès refusé")
    if not _FICHE_PATH.exists():
        raise HTTPException(404, "Fiche produit introuvable")
    return _FICHE_PATH.read_text(encoding="utf-8")


@router.get("/closing_pack/exemple/{slug}", response_class=HTMLResponse)
def closing_pack_exemple(slug: str, t: str = ""):
    if not t or t != CLOSER_TOKEN:
        raise HTTPException(403, "Accès refusé")
    if not VALID_SLUG.match(slug):
        raise HTTPException(400, "Slug invalide")
    filepath = _EXEMPLES_DIR / f"{slug}.html"
    if not filepath.exists():
        raise HTTPException(404, f"Exemple '{slug}' introuvable")
    return filepath.read_text(encoding="utf-8")


@router.get("/recap", response_class=HTMLResponse)
def recap_coach():
    """Page de récap publique pour partage avec coach / partenaires."""
    filepath = _EXEMPLES_DIR / "recap_coach.html"
    if not filepath.exists():
        raise HTTPException(404, "Récap introuvable")
    return filepath.read_text(encoding="utf-8")
