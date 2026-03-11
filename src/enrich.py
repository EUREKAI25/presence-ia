"""
Module ENRICH — Extraction email + mobile depuis le site web du prospect.
Scraping léger : homepage uniquement, regex, domaines parasites exclus.
"""
import logging
import re
from typing import Optional

import requests as http

log = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

# Numéros de téléphone français (fixe + mobile) : 0X XX XX XX XX ou +33X XX XX XX XX
_PHONE_RE = re.compile(
    r'(?<!\d)(?:\+33\s?|0)(6|7|[1-5])(?:[\s\-\.]?\d{2}){4}(?!\d)'
)

_UA = "Mozilla/5.0 (compatible; PRESENCE_IA/1.0)"


def _classify_phone(raw: str) -> tuple[Optional[str], Optional[str]]:
    """
    Retourne (tel, mobile) depuis un numéro brut.
    Normalise au format 0X XX XX XX XX.
    """
    digits = re.sub(r'\D', '', raw)
    if digits.startswith("33") and len(digits) == 11:
        digits = "0" + digits[2:]
    if len(digits) != 10:
        return None, None
    fmt = " ".join([digits[:2], digits[2:4], digits[4:6], digits[6:8], digits[8:]])
    if digits[1] in ("6", "7"):
        return None, fmt
    return fmt, None

# Domaines à ignorer (librairies JS, CMS, trackers, exemples…)
_IGNORE_DOMAINS = {
    "example.com", "domain.com", "sentry.io", "w3.org", "schema.org",
    "wordpress.org", "google.com", "facebook.com", "twitter.com",
    "instagram.com", "linkedin.com", "youtube.com", "wixpress.com",
    "wix.com", "squarespace.com", "godaddy.com", "ovh.com",
    "cloudflare.com", "jsdelivr.net", "unpkg.com", "cdnjs.com",
}

_IGNORE_PREFIXES = ("noreply", "no-reply", "donotreply", "postmaster",
                    "mailer", "bounce", "info@wordpress", "admin@wordpress")


def _fetch_html(url: str, timeout: int) -> Optional[str]:
    try:
        resp = http.get(url, timeout=timeout, headers={"User-Agent": _UA}, allow_redirects=True)
        return resp.text
    except Exception as exc:
        log.debug("Enrich fetch %s : %s", url, exc)
        return None


def extract_email_from_website(url: str, timeout: int = 5) -> Optional[str]:
    """
    Télécharge la homepage du site et extrait le premier email valide.
    Retourne None si aucun email exploitable n'est trouvé.
    """
    if not url:
        return None
    text = _fetch_html(url, timeout)
    if not text:
        return None

    for match in _EMAIL_RE.findall(text):
        email = match.lower().strip()
        domain = email.split("@")[1]

        if domain in _IGNORE_DOMAINS:
            continue
        if any(email.startswith(p) for p in _IGNORE_PREFIXES):
            continue
        if len(domain.split(".")[-1]) > 6:
            continue

        return email

    return None


def extract_mobile_from_website(url: str, timeout: int = 5) -> Optional[str]:
    """
    Extrait le premier mobile (06/07) trouvé dans la homepage.
    Retourne None si aucun mobile trouvé.
    """
    if not url:
        return None
    text = _fetch_html(url, timeout)
    if not text:
        return None

    for match in _PHONE_RE.findall(text):
        # _PHONE_RE capture le chiffre après 0 en groupe 1
        # On reconstruit le numéro depuis le contexte
        pass

    # Chercher directement les patterns complets
    for m in re.finditer(r'(?<!\d)(?:\+33\s?|0)(6|7|[1-5])(?:[\s\-\.]?\d{2}){4}(?!\d)', text):
        raw = m.group(0)
        _, mobile = _classify_phone(raw)
        if mobile:
            return mobile

    return None


def enrich_website(url: str, timeout: int = 6) -> dict:
    """
    Extrait en une seule requête HTTP : email + mobile depuis la homepage.
    Retourne {"email": str|None, "mobile": str|None}
    """
    if not url:
        return {"email": None, "mobile": None}
    text = _fetch_html(url, timeout)
    if not text:
        return {"email": None, "mobile": None}

    email = None
    for match in _EMAIL_RE.findall(text):
        e = match.lower().strip()
        d = e.split("@")[1]
        if d in _IGNORE_DOMAINS:
            continue
        if any(e.startswith(p) for p in _IGNORE_PREFIXES):
            continue
        if len(d.split(".")[-1]) > 6:
            continue
        email = e
        break

    mobile = None
    for m in re.finditer(r'(?<!\d)(?:\+33\s?|0)(6|7|[1-5])(?:[\s\-\.]?\d{2}){4}(?!\d)', text):
        _, mob = _classify_phone(m.group(0))
        if mob:
            mobile = mob
            break

    return {"email": email, "mobile": mobile}
