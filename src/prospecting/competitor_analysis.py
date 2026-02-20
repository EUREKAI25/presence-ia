"""
Scénario competitor_analysis — PRESENCE_IA
Pipeline : Build payload → AI_INQUIRY_MODULE → présence → résultat.

Si le prospect est déjà cité par les IA (prospect_present=True) → NOT_ELIGIBLE
Sinon → retourne ses concurrents (prêt à afficher dans audit/landing)
"""
import logging
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Chemin vers AI_INQUIRY_MODULE (EURKAI) ─────────────────────────────────────
_EURKAI_PATH = Path(__file__).parent.parent.parent.parent.parent / "EURKAI" / "MODULES"
if str(_EURKAI_PATH) not in sys.path and _EURKAI_PATH.exists():
    sys.path.insert(0, str(_EURKAI_PATH))

# Template de question par défaut
_DEFAULT_PROMPT = (
    "Tu es un habitant de {city} qui cherche un {profession} local. "
    "Quelles entreprises de {profession} connais-tu ou recommanderais-tu à {city} ? "
    "Cite des noms d'entreprises réelles, pas des plateformes."
)


def run(
    city: str,
    profession: str,
    prospect_name: str,
    prospect_website: Optional[str] = None,
    question_prompt: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    Scénario competitor_analysis.

    Args:
        city: Ville cible (ex: "Rennes")
        profession: Métier (ex: "couvreur")
        prospect_name: Nom du prospect (ex: "Toit Breton")
        prospect_website: URL du prospect pour le matching domaine (optionnel)
        question_prompt: Template custom (optionnel, utilise le défaut si absent)
        dry_run: Si True, pas d'appel IA réel

    Returns:
        Contrat uniforme :
        {
          "success": bool,
          "result": {
            "eligible": bool,
            "prospect_name": str,
            "city": str,
            "profession": str,
            "prospect_present": bool,
            "competitors": [...],
            "inquiry_raw": {...}   # réponse brute AI_INQUIRY_MODULE
          },
          "message": str,
          "error": null | {"code": str, "detail": str}
        }
    """
    try:
        from AI_INQUIRY_MODULE import run as ai_run
    except ImportError as e:
        return {
            "success": False,
            "result": None,
            "message": "AI_INQUIRY_MODULE non disponible",
            "error": {"code": "MODULE_NOT_FOUND", "detail": str(e)},
        }

    # Étape 1 — Build payload
    payload = {
        "city": city,
        "profession": profession,
        "prospect_name": prospect_name,
    }
    if prospect_website:
        payload["website"] = prospect_website

    prompt = question_prompt or _DEFAULT_PROMPT

    # Étape 2 — Appel AI_INQUIRY_MODULE
    inquiry_result = ai_run(
        payload=payload,
        question_prompt=prompt,
        dry_run=dry_run,
    )

    if not inquiry_result.get("success"):
        return inquiry_result  # propage l'erreur

    r = inquiry_result["result"]
    prospect_present: bool = r.get("prospect_present", False)
    competitors: list = r.get("competitors", [])

    # Étape 3 — Eligibilité
    # Prospect déjà cité → pas de potentiel → NOT_ELIGIBLE
    eligible = not prospect_present

    # Étape 4 / 5 — Retourner le résultat
    if prospect_present:
        msg = (
            f"{prospect_name} est déjà cité par les IA à {city} "
            f"({profession}) — NOT_ELIGIBLE"
        )
    else:
        msg = (
            f"{prospect_name} n'est PAS cité — {len(competitors)} concurrent(s) identifié(s) "
            f"à {city} ({profession})"
            + (" [DRY_RUN]" if dry_run else "")
        )

    return {
        "success": True,
        "result": {
            "eligible": eligible,
            "prospect_name": prospect_name,
            "city": city,
            "profession": profession,
            "prospect_present": prospect_present,
            "competitors": competitors,
            "inquiry_raw": r,
        },
        "message": msg,
        "error": None,
    }
