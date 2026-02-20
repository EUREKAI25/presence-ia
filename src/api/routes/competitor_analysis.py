"""
Adapter PRESENCE_IA — competitor_analysis
Expose: POST /api/competitor-analysis/run
"""
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

log = logging.getLogger(__name__)
router = APIRouter()


class CompetitorAnalysisRequest(BaseModel):
    city: str
    profession: str
    prospect_name: str
    prospect_website: Optional[str] = None
    question_prompt: Optional[str] = None
    """Template custom. Si absent, utilise le prompt par défaut du module."""
    dry_run: bool = False


@router.post("/api/competitor-analysis/run")
def competitor_analysis_run(req: CompetitorAnalysisRequest):
    """
    Pipeline competitor_analysis :
    1. Build payload
    2. Appelle AI_INQUIRY_MODULE
    3. Si prospect_present → eligible=False (NOT_ELIGIBLE)
    4. Sinon → retourne competitors + eligible=True

    Retourne le contrat uniforme EURKAI.
    """
    from ...prospecting.competitor_analysis import run

    return run(
        city=req.city,
        profession=req.profession,
        prospect_name=req.prospect_name,
        prospect_website=req.prospect_website,
        question_prompt=req.question_prompt,
        dry_run=req.dry_run,
    )
