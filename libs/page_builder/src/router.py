"""
Router FastAPI — endpoints page_builder v0.2.

POST /page-builder/render    → ManifestPage → HTMLResponse
POST /page-builder/validate  → ManifestPage → {"valid": bool, "error"?}
GET  /page-builder/catalog   → liste des blocs disponibles + leurs JSON schemas
GET  /page-builder/i18n/{lang} → catalog i18n pour une langue
"""
import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError

from .manifest.schema import ManifestPage
from .manifest.parser import parse_manifest, _BLOCK_REGISTRY
from .renderer.html import render_page

router = APIRouter(prefix="/page-builder", tags=["page_builder"])

_I18N_DIR = Path(__file__).parent.parent / "i18n"


@router.post("/render", response_class=HTMLResponse, summary="Rend un manifest en HTML")
def render(manifest: ManifestPage) -> HTMLResponse:
    """Reçoit un ManifestPage JSON, retourne le HTML complet de la page."""
    page = parse_manifest(manifest)
    html = render_page(page)
    return HTMLResponse(content=html)


@router.post("/validate", summary="Valide un manifest sans le rendre")
def validate(manifest: ManifestPage) -> dict:
    """Valide la structure d'un manifest (types, champs requis, blocs connus)."""
    try:
        parse_manifest(manifest)
        return {"valid": True}
    except (ValidationError, ValueError) as e:
        return {"valid": False, "error": str(e)}


@router.get("/catalog", summary="Liste les blocs disponibles et leurs schemas")
def catalog() -> JSONResponse:
    """Retourne le catalogue des blocs v0.2 avec leurs JSON schemas Pydantic."""
    from . import blocks as blks
    from ..blocks import (
        HeroBlock, NavBarBlock, StatBlock, StepsBlock, FAQBlock,
        PricingBlock, CTABlock, ImageBlock, TestimonialBlock, ContentBlock, FooterBlock,
    )

    block_classes = [
        HeroBlock, NavBarBlock, StatBlock, StepsBlock, FAQBlock,
        PricingBlock, CTABlock, ImageBlock, TestimonialBlock, ContentBlock, FooterBlock,
    ]

    catalog_data = []
    for cls in block_classes:
        catalog_data.append({
            "block_type":  cls.model_fields["block_type"].default,
            "schema":      cls.model_json_schema(),
        })

    return JSONResponse({"blocks": catalog_data})


@router.get("/i18n/{lang}", summary="Retourne le catalog i18n pour une langue")
def i18n_catalog(lang: str) -> JSONResponse:
    """Retourne le contenu du fichier i18n/{lang}.json."""
    path = _I18N_DIR / f"{lang}.json"
    if not path.exists():
        return JSONResponse({"error": f"Langue '{lang}' non disponible"}, status_code=404)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(data)
