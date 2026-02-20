"""
Adapter PRESENCE_IA — AI_INQUIRY_MODULE
Expose: POST /api/ai-inquiry/run
"""
import logging
import sys
import os
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

log = logging.getLogger(__name__)
router = APIRouter()

# Chemin vers le module EURKAI (résolution relative au projet)
_EURKAI_PATH = Path(__file__).parent.parent.parent.parent.parent.parent / "EURKAI" / "MODULES"
if str(_EURKAI_PATH) not in sys.path and _EURKAI_PATH.exists():
    sys.path.insert(0, str(_EURKAI_PATH))


# ── Schéma de requête ──────────────────────────────────────────────────────────

class AIInquiryRequest(BaseModel):
    payload: dict
    """
    Variables du template. Clés reconnues :
    - profession, city : pour le template
    - prospect_name    : pour la détection de présence
    - website / prospect_website : pour le matching domaine
    """
    question_prompt: str
    """
    Template avec {clés} remplacées par payload.
    Ex: "Quels sont les meilleurs {profession}s à {city} ? Citez des entreprises."
    """
    poll_inquiry_datas: Optional[dict] = None
    """Variantes supplémentaires. Ex: {"city": "Brest"} pour tester une autre ville."""
    output_format: str = "json"
    dry_run: bool = False
    """Si True, aucun appel IA réel (réponses simulées). Utile pour les tests."""


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/api/ai-inquiry/run")
def ai_inquiry_run(req: AIInquiryRequest):
    """
    Interroge plusieurs IA (OpenAI, Anthropic, Gemini) sur un secteur/ville,
    extrait les citations, détecte la présence du prospect.

    Retourne le contrat uniforme EURKAI :
    { success, result: {inquiry_dict, answers, citations, prospect_present, competitors, meta}, message, error }
    """
    try:
        from AI_INQUIRY_MODULE import run
    except ImportError as e:
        log.error("Impossible d'importer AI_INQUIRY_MODULE depuis %s : %s", _EURKAI_PATH, e)
        return {
            "success": False,
            "result": None,
            "message": "Module AI_INQUIRY_MODULE non disponible",
            "error": {"code": "MODULE_NOT_FOUND", "detail": str(e)},
        }

    return run(
        payload=req.payload,
        question_prompt=req.question_prompt,
        poll_inquiry_datas=req.poll_inquiry_datas,
        output_format=req.output_format,
        dry_run=req.dry_run,
    )
