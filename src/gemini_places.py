"""
GEMINI_PLACES — Enrichissement entreprise via Gemini + Google Search grounding.
Remplace Google Places API pour trouver site web + téléphone d'une entreprise connue.
"""
import os, re, json, logging, requests
from typing import Dict

log = logging.getLogger(__name__)

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def fetch_company_info(name: str, city: str, api_key: str = None) -> Dict:
    """
    Cherche le site web et téléphone d'une entreprise via Gemini + Search Grounding.
    Retourne dict avec website, formatted_phone_number (même interface que fetch_place_details).
    """
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {}

    prompt = (
        f"Trouve le site web officiel et le numéro de téléphone de l'entreprise "
        f"'{name}' située à {city} en France. "
        f"Réponds UNIQUEMENT en JSON strict, sans texte autour : "
        f'{{ "website": "https://...", "phone": "0X XX XX XX XX" }} '
        f"Si introuvable, mets null."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}], "role": "user"}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 256},
    }

    try:
        r = requests.post(
            f"{_GEMINI_URL}?key={api_key}",
            json=payload,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return {}
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)

        m = re.search(r'\{[^{}]+\}', text, re.DOTALL)
        if not m:
            log.debug("gemini_places: pas de JSON pour %s / %s", name, city)
            return {}

        info = json.loads(m.group(0))
        website = info.get("website") or ""
        phone   = info.get("phone") or ""

        if website and not website.startswith("http"):
            website = f"https://{website}"

        return {
            "website":                  website if website and "." in website else None,
            "formatted_phone_number":   phone or None,
            "rating":                   None,
            "user_ratings_total":       None,
        }
    except Exception as e:
        log.warning("gemini_places %s/%s: %s", name, city, e)
        return {}
