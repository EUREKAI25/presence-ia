"""
Analyse des concurrents TOP 3 via IA + web search.
1 requête par concurrent → analyse structurée de leur présence en ligne.
"""
import logging
import os
import re
from typing import Optional

log = logging.getLogger(__name__)


def _get_caller():
    """Retourne le meilleur caller disponible (OpenAI > Gemini > Anthropic)."""
    try:
        from ..ia_test import _openai_api, _gemini_api, _anthropic_api
    except ImportError:
        from src.ia_test import _openai_api, _gemini_api, _anthropic_api

    if os.getenv("OPENAI_API_KEY"):
        return _openai_api
    if os.getenv("GEMINI_API_KEY"):
        return _gemini_api
    if os.getenv("ANTHROPIC_API_KEY"):
        return _anthropic_api
    raise RuntimeError("Aucune clé API IA disponible pour l'analyse concurrents")


_PAGE_TYPES = [
    ("page_accueil",   ["accueil", "page d'accueil", "homepage", "site web"]),
    ("pages_services", ["page service", "pages services", "prestations", "nos services"]),
    ("pages_locales",  ["page locale", "pages locales", "zone d'intervention", "ville"]),
    ("faq",            ["faq", "questions fréquentes", "q/r", "questions-réponses"]),
    ("blog",           ["blog", "article", "actualité", "guide"]),
    ("avis",           ["avis", "témoignages", "note google", "notes"]),
]

_SIGNAL_PATTERNS = {
    "google_rating": re.compile(r'(\d[\.,]\d)\s*/?\s*5', re.I),
    "review_count":  re.compile(r'(\d+)\s+avis', re.I),
    "years":         re.compile(r'(\d+)\s*ans?\s*d.expérience', re.I),
}


def _extract_pages(text: str) -> dict:
    text_low = text.lower()
    return {
        ptype: any(kw in text_low for kw in keywords)
        for ptype, keywords in _PAGE_TYPES
    }


def _extract_signals(text: str) -> dict:
    signals = {}
    m = _SIGNAL_PATTERNS["google_rating"].search(text)
    if m:
        signals["google_rating"] = m.group(1).replace(",", ".")
    m = _SIGNAL_PATTERNS["review_count"].search(text)
    if m:
        signals["review_count"] = m.group(1)
    m = _SIGNAL_PATTERNS["years"].search(text)
    if m:
        signals["years_experience"] = m.group(1)
    return signals


def _extract_website(text: str) -> str:
    urls = re.findall(r'https?://[^\s\)\]\,\"\'<>]+', text)
    for url in urls:
        # Filtre les URLs génériques (Google, Yelp, etc.)
        if not any(x in url for x in ["google", "yelp", "pagesjaunes", "facebook", "instagram", "linkedin"]):
            return url.rstrip("/.,")
    return ""


def _extract_strengths(text: str) -> list[str]:
    """Extrait les points forts depuis la réponse IA."""
    strengths = []
    for line in text.split("\n"):
        line = line.strip()
        if len(line) < 20 or len(line) > 200:
            continue
        # Lignes avec marqueurs de liste ou mots forts
        if (
            line.startswith(("-", "•", "·", "✓", "✔", "*"))
            or re.match(r"^\d+[.)]\s", line)
            or any(kw in line.lower() for kw in ["fort", "avantage", "distingue", "explique", "raison", "bien positionné"])
        ):
            cleaned = re.sub(r"^[-•·✓✔*\d.)\s]+", "", line).strip()
            if cleaned and len(cleaned) > 15:
                strengths.append(cleaned)
    return strengths[:5]


def _build_query(name: str, city: str, business_type: str) -> str:
    return (
        f"Analyse la présence en ligne de \"{name}\", {business_type} à {city}. "
        f"Recherche leur site web et réponds avec ces 5 points précis :\n"
        f"1. URL de leur site web officiel\n"
        f"2. Types de pages présentes sur leur site (accueil, services locaux, FAQ, blog, pages par ville)\n"
        f"3. Leur note Google et nombre d'avis clients (si disponible)\n"
        f"4. Leurs principaux signaux de confiance visibles en ligne\n"
        f"5. Ce qui explique qu'une IA les recommande en premier pour {business_type} à {city}\n"
        f"Sois précis et concret — pas de généralités."
    )


def analyze_competitor(
    name: str,
    city: str,
    business_type: str,
    caller=None,
) -> dict:
    """
    Analyse un concurrent via IA + web search.

    Returns:
        {
            "name":        str,
            "website":     str,
            "pages":       {page_accueil, pages_services, pages_locales, faq, blog, avis},
            "signals":     {google_rating, review_count, years_experience},
            "strengths":   [str, ...],
            "why_cited":   str,
            "raw":         str,
            "error":       str | None,
        }
    """
    if caller is None:
        try:
            caller = _get_caller()
        except RuntimeError as e:
            return {"name": name, "error": str(e), "website": "", "pages": {}, "signals": {}, "strengths": [], "why_cited": "", "raw": ""}

    query = _build_query(name, city, business_type)
    log.info("[competitor] Analyse de %s…", name)

    try:
        raw = caller(query)
    except Exception as e:
        log.error("[competitor] Erreur pour %s : %s", name, e)
        return {"name": name, "error": str(e), "website": "", "pages": {}, "signals": {}, "strengths": [], "why_cited": "", "raw": ""}

    website   = _extract_website(raw)
    pages     = _extract_pages(raw)
    signals   = _extract_signals(raw)
    strengths = _extract_strengths(raw)

    # Extrait la partie "pourquoi cité" depuis la réponse (point 5)
    why_cited = ""
    lines = [l.strip() for l in raw.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if "5" in line[:5] or "explique" in line.lower() or "recommande" in line.lower():
            next_lines = [l for l in lines[i+1:i+4] if len(l) > 20]
            if next_lines:
                why_cited = next_lines[0]
            break
    if not why_cited and strengths:
        why_cited = strengths[0]

    log.info("[competitor] %s → site: %s | pages: %s | signaux: %s",
             name, website or "non trouvé", sum(pages.values()), len(signals))

    return {
        "name":      name,
        "website":   website,
        "pages":     pages,
        "signals":   signals,
        "strengths": strengths,
        "why_cited": why_cited,
        "raw":       raw,
        "error":     None,
    }


def analyze_top_competitors(
    competitors: list[dict],
    city: str,
    business_type: str,
    top_n: int = 3,
    caller=None,
) -> list[dict]:
    """
    Analyse les N premiers concurrents.

    Args:
        competitors : [{name, count}, ...] retourné par scoring.extract_competitors()
        top_n       : nombre de concurrents à analyser

    Returns:
        [competitor_analysis, ...]
    """
    if not competitors:
        log.warning("[competitor] Aucun concurrent à analyser")
        return []

    if caller is None:
        try:
            caller = _get_caller()
        except RuntimeError as e:
            log.warning("[competitor] Pas de caller disponible : %s", e)
            return [{"name": c["name"], "count": c.get("count", 0), "error": str(e)} for c in competitors[:top_n]]

    results = []
    for comp in competitors[:top_n]:
        analysis = analyze_competitor(comp["name"], city, business_type, caller)
        analysis["count"] = comp.get("count", 0)
        results.append(analysis)

    return results
