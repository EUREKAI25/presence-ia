"""
Module GOOGLE_PLACES — Récupération automatique de prospects
Google Places API : Text Search + Place Details
"""
import logging, re
from typing import Dict, List, Optional, Tuple

import requests

log = logging.getLogger(__name__)

_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
_DETAILS_URL     = "https://maps.googleapis.com/maps/api/place/details/json"
_DETAIL_FIELDS   = "name,website,formatted_phone_number,user_ratings_total"

# Statuts Google qui signifient "pas de résultat" (pas une erreur)
_EMPTY_STATUSES = {"ZERO_RESULTS"}
# Statuts OK
_OK_STATUSES    = {"OK"}


# ── Helpers ───────────────────────────────────────────────────────────────

def _domain(url: str) -> str:
    """Domaine normalisé pour déduplication (ex: 'dupont-toiture.fr')."""
    if not url:
        return ""
    u = re.sub(r"^https?://(?:www\.)?", "", url.lower()).split("/")[0].split("?")[0]
    return u if "." in u else ""


# ── Appels API ────────────────────────────────────────────────────────────

def fetch_text_search(profession: str, city: str, api_key: str,
                      max_results: int = 20) -> List[Dict]:
    """
    Text Search : "{profession} {city}" → liste de places (place_id, name, user_ratings_total).
    Une seule page (20 résultats max) — suffisant pour le pipeline de prospection.
    """
    query  = f"{profession} {city}"
    params = {"query": query, "key": api_key, "language": "fr"}

    resp = requests.get(_TEXT_SEARCH_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    status = data.get("status", "")
    if status in _EMPTY_STATUSES:
        return []
    if status not in _OK_STATUSES:
        log.error("Places TextSearch status=%s msg=%s", status, data.get("error_message", ""))
        raise ValueError(f"Google Places API: {status} — {data.get('error_message', '')}")

    return data.get("results", [])[:max_results]


def fetch_place_details(place_id: str, api_key: str) -> Dict:
    """Place Details → website, phone, user_ratings_total."""
    params = {
        "place_id": place_id,
        "fields":   _DETAIL_FIELDS,
        "key":      api_key,
        "language": "fr",
    }
    resp = requests.get(_DETAILS_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    status = data.get("status", "")
    if status not in _OK_STATUSES:
        log.warning("Place Details status=%s place_id=%s", status, place_id)
        return {}
    return data.get("result", {})


# ── Pipeline complet ──────────────────────────────────────────────────────

def search_prospects(profession: str, city: str, api_key: str,
                     max_results: int = 30) -> Tuple[List[Dict], List[str]]:
    """
    Text Search → Place Details → filtre (website requis) → dédupe par domaine.

    Retourne:
        prospects : list[{name, website, phone, reviews_count}]
        reasons   : list[str]  — raisons de rejet (pour debug/log)
    """
    # On fetch 3× plus que nécessaire pour compenser le filtrage
    raw = fetch_text_search(profession, city, api_key, max_results=min(max_results * 3, 60))

    prospects: List[Dict] = []
    reasons:   List[str]  = []
    seen_domains: set     = set()

    for place in raw:
        if len(prospects) >= max_results:
            break

        place_id = place.get("place_id", "")
        name     = place.get("name", "")

        try:
            details = fetch_place_details(place_id, api_key)
        except Exception as exc:
            log.warning("Détails %s (%s): %s", place_id, name, exc)
            reasons.append(f"{name}: erreur détails ({exc})")
            continue

        website = details.get("website") or ""

        if not website:
            reasons.append(f"{name}: pas de site web")
            continue

        d = _domain(website)
        if not d:
            reasons.append(f"{name}: domaine invalide ({website})")
            continue

        if d in seen_domains:
            reasons.append(f"{name}: doublon ({d})")
            continue

        seen_domains.add(d)
        prospects.append({
            "name":          name,
            "website":       website,
            "phone":         details.get("formatted_phone_number"),
            "reviews_count": details.get("user_ratings_total")
                             or place.get("user_ratings_total"),
        })

    return prospects, reasons
