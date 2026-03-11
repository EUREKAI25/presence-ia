"""
Module CMS_DETECTOR — Détection du CMS depuis le HTML/headers d'un site.
Retourne une chaîne normalisée : wordpress | wix | squarespace | webflow |
shopify | jimdo | prestashop | joomla | drupal | typo3 | unknown
"""
import logging
import re
from typing import Optional

import requests as http

log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; PRESENCE_IA/1.0)"

# ── Signatures ─────────────────────────────────────────────────────────────
# (nom, liste de patterns regex sur le HTML brut + headers)

_SIGNATURES: list[tuple[str, list[str]]] = [
    ("wordpress",    [r"wp-content", r"wp-includes", r"/wp-json/",
                      r'generator.*WordPress', r'wordpress\.org']),
    ("wix",          [r"wixsite\.com", r"static\.wixstatic\.com",
                      r"wix\.com/lpviral", r'"wix"']),
    ("squarespace",  [r"squarespace\.com", r"sqspcdn\.com",
                      r'generator.*Squarespace']),
    ("webflow",      [r"webflow\.com", r"assets-global\.website-files\.com",
                      r'generator.*Webflow']),
    ("shopify",      [r"cdn\.shopify\.com", r"myshopify\.com",
                      r'Shopify\.theme']),
    ("jimdo",        [r"jimdosite\.com", r"jimdofree\.com",
                      r'jimdo\.com']),
    ("prestashop",   [r"prestashop", r"/modules/ps_", r"themeforest.*prestashop"]),
    ("joomla",       [r'generator.*Joomla', r'joomla\.org', r'/components/com_']),
    ("drupal",       [r'generator.*Drupal', r'drupal\.org', r'drupal\.js']),
    ("typo3",        [r'typo3', r'TYPO3']),
]

_COMPILED = [
    (name, [re.compile(p, re.IGNORECASE) for p in patterns])
    for name, patterns in _SIGNATURES
]


def detect_cms(url: str, timeout: int = 6) -> str:
    """
    Télécharge la homepage et retourne le CMS détecté.
    Retourne 'unknown' si aucune signature trouvée ou si le site est inaccessible.
    """
    if not url:
        return "unknown"
    try:
        resp = http.get(
            url, timeout=timeout,
            headers={"User-Agent": _UA},
            allow_redirects=True,
        )
        # Combine HTML + headers en une seule chaîne à analyser
        headers_str = " ".join(f"{k}: {v}" for k, v in resp.headers.items())
        haystack = resp.text[:60_000] + " " + headers_str  # 60Ko suffisent

    except Exception as exc:
        log.debug("CMS detect %s : %s", url, exc)
        return "unknown"

    for name, patterns in _COMPILED:
        if any(p.search(haystack) for p in patterns):
            return name

    return "unknown"
