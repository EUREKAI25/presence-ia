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
_DETAIL_FIELDS   = "name,website,formatted_phone_number,user_ratings_total,rating"

# Statuts Google qui signifient "pas de résultat" (pas une erreur)
_EMPTY_STATUSES = {"ZERO_RESULTS"}
# Statuts OK
_OK_STATUSES    = {"OK"}

# ── Nettoyage des noms Google Places ──────────────────────────────────────

# Séparateurs marketing forts (flèches, barres, emoji entouré d'espaces, tiret+majuscule)
_NAME_SEP = re.compile(
    r'\s*[➽➜►▶→|·—–]\s*'
    r'|\s+[\u2600-\u27ff\U0001f000-\U0001ffff✨⭐🔥💎]\s+'
    r'|\s+-\s+(?=[A-Z])'
)
# Emojis/décorations en fin de chaîne
_TRAILING_JUNK = re.compile(r'[\s\u2000-\u206f\u2600-\u27ff\U0001f000-\U0001ffff✨⭐🔥💎]+$')
# Fragments d'adresse (Route de X, Rue X, etc.)
_ADDRESS_TAIL = re.compile(
    r'\s+(?:Route|Rue|Avenue|Av\.|Boulevard|Bd|Allée|Impasse|ZA|ZI|Zone(?:\s+\w+)?)\b.*$',
    re.IGNORECASE,
)
# Articles/conjonctions français : on ne coupe PAS le nom quand le tail commence par eux
_FR_CONNECTORS = re.compile(r'^(?:et|de|du|des|de\s+la|au|aux|le|la|les)\s', re.IGNORECASE)


def _clean_name(name: str, city: str = "") -> str:
    """
    Garde uniquement la partie commerciale du nom.
    Applique par ordre :
      1. Séparateurs marketing forts (➽, |, ·, —, emoji…)
      2. Référence à la ville ("à Montpellier", "Nantes Route de…")
      3. Fragments d'adresse (Route de, Rue, Boulevard…)
      4. Descriptif de service en minuscules (≥ 2 mots, hors articles/conjonctions)
    """
    if not name:
        return name

    part = name

    # 1. Séparateurs forts
    part = _NAME_SEP.split(part)[0]
    part = _TRAILING_JUNK.sub("", part).strip()

    # 2. Ville : "à {city}" ou "{city}" en fin/milieu, + tout ce qui suit
    if city:
        c = re.escape(city.strip())
        part = re.sub(rf'\s+(?:à\s+)?{c}\b.*$', '', part, flags=re.IGNORECASE).strip()

    # 3. Adresse
    part = _ADDRESS_TAIL.sub("", part).strip()

    # 4. Queue descriptive en minuscules (≥ 2 mots, sauf si elle commence par un connecteur)
    #    ex: "rénovation de piscine" → supprimé ; "et salles de bains" → conservé
    m = re.search(r'(\s+[a-zàâéèêëîïôùûüçœæ]\S*)(\s+\S+)+$', part)
    if m:
        tail = m.group(0).strip()
        if not _FR_CONNECTORS.match(tail):
            part = part[: m.start()].strip()

    return part or name


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
        name     = _clean_name(place.get("name", ""), city=city)

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
            "rating":        details.get("rating") or place.get("rating"),
        })

    return prospects, reasons
