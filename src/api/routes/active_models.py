"""
Endpoints — modèles IA actifs par provider
GET /api/openai_active_llm
GET /api/anthropic_active_llm
GET /api/google_active_llm

Retourne le modèle actuellement utilisé par le système + le dernier modèle disponible chez le provider.
"""
import os
import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Active Models"])
log = logging.getLogger(__name__)


def _latest_openai() -> dict:
    import openai
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    models = [m.id for m in client.models.list().data
              if m.id.startswith("gpt-") and "realtime" not in m.id and "audio" not in m.id]
    # Priorité : chatgpt-4o-latest > gpt-4o > autres
    preferred = ["chatgpt-4o-latest", "gpt-4o", "gpt-4-turbo"]
    latest = next((p for p in preferred if p in models), sorted(models)[-1] if models else "gpt-4o")
    current = os.getenv("OPENAI_MODEL", "gpt-4o")
    return {"provider": "openai", "current_model": current, "latest_available": latest, "models": sorted(models)}


def _latest_anthropic() -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    models = [m.id for m in client.models.list().data]
    # Priorité : claude-opus > claude-sonnet > claude-haiku (dernier en date)
    sonnet = sorted([m for m in models if "sonnet" in m], reverse=True)
    opus   = sorted([m for m in models if "opus" in m],   reverse=True)
    latest = (opus[0] if opus else None) or (sonnet[0] if sonnet else None) or (models[0] if models else "claude-sonnet-4-6")
    current = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    return {"provider": "anthropic", "current_model": current, "latest_available": latest, "models": sorted(models)}


def _latest_google() -> dict:
    import google.generativeai as g
    g.configure(api_key=os.getenv("GEMINI_API_KEY"))
    models = [m.name.replace("models/", "") for m in g.list_models()
              if "generateContent" in (m.supported_generation_methods or [])]
    # Priorité : gemini-2.0 > gemini-1.5 > autres
    flash2  = sorted([m for m in models if "gemini-2" in m and "flash" in m], reverse=True)
    flash15 = sorted([m for m in models if "gemini-1.5" in m and "flash" in m], reverse=True)
    latest  = (flash2[0] if flash2 else None) or (flash15[0] if flash15 else None) or (models[0] if models else "gemini-2.0-flash")
    current = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    return {"provider": "google", "current_model": current, "latest_available": latest, "models": sorted(models)}


@router.get("/api/openai_active_llm")
def openai_active_llm():
    try:
        data = _latest_openai()
        return JSONResponse({"ok": True, **data})
    except Exception as e:
        log.error("openai_active_llm: %s", e)
        return JSONResponse({"ok": False, "provider": "openai", "error": str(e)}, status_code=500)


@router.get("/api/anthropic_active_llm")
def anthropic_active_llm():
    try:
        data = _latest_anthropic()
        return JSONResponse({"ok": True, **data})
    except Exception as e:
        log.error("anthropic_active_llm: %s", e)
        return JSONResponse({"ok": False, "provider": "anthropic", "error": str(e)}, status_code=500)


@router.get("/api/google_active_llm")
def google_active_llm():
    try:
        data = _latest_google()
        return JSONResponse({"ok": True, **data})
    except Exception as e:
        log.error("google_active_llm: %s", e)
        return JSONResponse({"ok": False, "provider": "google", "error": str(e)}, status_code=500)
