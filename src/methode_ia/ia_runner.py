"""
IA Runner — exécute les requêtes de visibilité pour une entreprise donnée.
Autonome : ne nécessite pas de prospect en DB.
"""
import logging
import os
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

_FALLBACK_TEMPLATES = [
    "Qui est le meilleur {metier} à {ville} ?",
    "{metier} de confiance à {ville}, qui recommandes-tu ?",
    "J'ai besoin d'un {metier} à {ville}, tu connais quelqu'un de bien ?",
    "Recommande-moi un {metier} sérieux dans la ville de {ville}",
    "Quel {metier} à {ville} est reconnu pour son sérieux et son expertise ?",
    "Cherche un bon {metier} à {ville} pour un particulier",
    "{metier} réputé à {ville} avec de bons avis — qui choisir ?",
]


def _get_queries(business_type: str, city: str, max_queries: int) -> list[str]:
    """Génère les requêtes depuis les templates DB ou fallback."""
    try:
        from ..scan import get_queries
        return get_queries(business_type, city)[:max_queries]
    except Exception:
        return [
            tpl.replace("{metier}", business_type).replace("{ville}", city)
            for tpl in _FALLBACK_TEMPLATES[:max_queries]
        ]


def _has_key(env_var: str) -> bool:
    return bool(os.getenv(env_var))


def run_ia_queries(
    company_name: str,
    city: str,
    business_type: str,
    website: Optional[str] = None,
    max_queries: int = 7,
) -> list[dict]:
    """
    Exécute les requêtes IA pour une entreprise et retourne les résultats bruts.

    Returns:
        ia_results Format A : [{model, prompt, response, tested_at}, ...]
    """
    queries = _get_queries(business_type, city, max_queries)
    log.info("[methode_ia] %d requêtes générées pour %s/%s", len(queries), business_type, city)

    try:
        from ..ia_test import _openai_api, _anthropic_api, _gemini_api
    except ImportError:
        from src.ia_test import _openai_api, _anthropic_api, _gemini_api

    model_map = []
    if _has_key("OPENAI_API_KEY"):
        model_map.append(("openai", _openai_api))
    if _has_key("ANTHROPIC_API_KEY"):
        model_map.append(("anthropic", _anthropic_api))
    if _has_key("GEMINI_API_KEY"):
        model_map.append(("gemini", _gemini_api))

    if not model_map:
        raise RuntimeError(
            "Aucune clé API IA configurée "
            "(OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY)"
        )

    results = []
    for query in queries:
        for model_key, caller in model_map:
            ts = datetime.utcnow().isoformat()
            try:
                response = caller(query)
                log.info("[methode_ia] %s — %d chars", model_key, len(response or ""))
            except Exception as e:
                log.error("[methode_ia] %s erreur sur '%s': %s", model_key, query[:60], e)
                response = f"[ERREUR] {e}"

            results.append({
                "model":     model_key,
                "prompt":    query,
                "response":  response or "",
                "tested_at": ts,
            })

    log.info("[methode_ia] %d résultats collectés (%d requêtes × %d modèles)",
             len(results), len(queries), len(model_map))
    return results
