"""
Route /preview — Test page_builder avant déploiement complet
"""
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from ...database import SessionLocal

router = APIRouter()


@router.get("/preview", response_class=HTMLResponse)
def preview_page(
    page_type: str = Query("home", description="Type de page (home, landing)"),
    preset: str = Query("default", description="Design preset (default, thalasso, myhealthprac)")
):
    """
    Prévisualisation page avec page_builder EURKAI (version simple MVP).

    Usage:
    - /preview → Page home avec preset default
    - /preview?preset=thalasso → Page home avec design thalasso
    - /preview?preset=myhealthprac → Landing myhealthprac
    """
    from ..page_builder_simple import build_page_simple

    db = SessionLocal()
    try:
        html = build_page_simple(db, page_type, design_preset=preset)
        return HTMLResponse(html)
    finally:
        db.close()
