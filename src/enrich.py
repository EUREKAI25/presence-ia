"""
Module ENRICH — Extraction email depuis le site web du prospect.
Scraping léger : homepage uniquement, regex, domaines parasites exclus.
"""
import logging
import re
from typing import Optional

import requests as http

log = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

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


def extract_email_from_website(url: str, timeout: int = 5) -> Optional[str]:
    """
    Télécharge la homepage du site et extrait le premier email valide.
    Retourne None si aucun email exploitable n'est trouvé.
    """
    if not url:
        return None
    try:
        resp = http.get(
            url, timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PRESENCE_IA/1.0)"},
            allow_redirects=True,
        )
        text = resp.text
    except Exception as exc:
        log.debug("Enrich %s : %s", url, exc)
        return None

    for match in _EMAIL_RE.findall(text):
        email = match.lower().strip()
        domain = email.split("@")[1]

        if domain in _IGNORE_DOMAINS:
            continue
        if any(email.startswith(p) for p in _IGNORE_PREFIXES):
            continue
        # Exclure emails avec extensions très longues (artefacts HTML)
        if len(domain.split(".")[-1]) > 6:
            continue

        return email

    return None
