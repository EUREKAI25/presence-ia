"""
Email Enricher — trouve les emails probables par SMTP + Hunter.io (optionnel)
Usage: python -m src.email_enricher [campaign_id]
"""
import os
import re
import smtplib
import socket
import logging
from typing import Optional
from urllib.parse import urlparse

import dns.resolver
import requests

log = logging.getLogger(__name__)

# Patterns à tester, dans l'ordre de probabilité
EMAIL_PATTERNS = ["contact", "info", "devis", "bonjour", "accueil", "hello", "pro"]

# Domaines d'hébergeurs / annuaires = pas de vraie adresse email dessous
SKIP_DOMAINS = {
    "facebook.com", "wixsite.com", "wix.com", "site-solocal.com",
    "google.com", "instagram.com", "pagesjaunes.fr", "leboncoin.fr",
    "maisons-du-monde.com", "houzz.fr",
}


def _extract_domain(website_url: str) -> Optional[str]:
    """Extrait le domaine depuis une URL, ou None si c'est un hébergeur générique."""
    if not website_url:
        return None
    try:
        parsed = urlparse(website_url)
        host = parsed.netloc or parsed.path
        # Supprimer www.
        host = re.sub(r"^www\.", "", host.lower())
        # Supprimer les paramètres UTM résiduels
        host = host.split("?")[0].rstrip("/")
        if not host:
            return None
        # Vérifier si c'est un hébergeur générique
        for skip in SKIP_DOMAINS:
            if host == skip or host.endswith("." + skip):
                return None
        return host
    except Exception:
        return None


def _mx_exists(domain: str) -> bool:
    """Vérifie que le domaine a des enregistrements MX."""
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        return len(answers) > 0
    except Exception:
        return False


def _get_mx_host(domain: str) -> Optional[str]:
    """Retourne l'hôte MX principal (priorité la plus basse = plus haute priorité)."""
    try:
        answers = sorted(dns.resolver.resolve(domain, "MX", lifetime=5), key=lambda r: r.preference)
        return str(answers[0].exchange).rstrip(".")
    except Exception:
        return None


def _smtp_verify(email: str, mx_host: str, timeout: int = 8) -> str:
    """
    Vérifie l'existence d'une adresse email via SMTP RCPT TO.
    Retourne: "valid" | "invalid" | "catchall" | "unknown"
    """
    try:
        with smtplib.SMTP(timeout=timeout) as smtp:
            smtp.connect(mx_host, 25)
            smtp.ehlo("presence-ia.com")
            # Test avec une adresse aléatoire pour détecter le catch-all
            smtp.mail("verify@presence-ia.com")
            code_probe, _ = smtp.rcpt("xqzjunk_catchall_probe@" + email.split("@")[1])
            if code_probe == 250:
                # Serveur en catch-all, on ne peut pas distinguer
                smtp.rset()
                smtp.mail("verify@presence-ia.com")
                code_real, _ = smtp.rcpt(email)
                return "catchall" if code_real == 250 else "invalid"
            # Pas de catch-all — tester l'adresse réelle
            smtp.rset()
            smtp.mail("verify@presence-ia.com")
            code_real, _ = smtp.rcpt(email)
            return "valid" if code_real == 250 else "invalid"
    except smtplib.SMTPConnectError:
        return "unknown"
    except smtplib.SMTPServerDisconnected:
        return "unknown"
    except OSError:
        return "unknown"
    except Exception as e:
        log.debug("SMTP error for %s: %s", email, e)
        return "unknown"


def find_email_smtp(domain: str) -> tuple[Optional[str], str]:
    """
    Essaie les patterns email sur un domaine via SMTP.
    Retourne (email, statut) où statut = "valid"|"catchall"|"probable"|"not_found"
    """
    if not _mx_exists(domain):
        return None, "no_mx"

    mx_host = _get_mx_host(domain)
    if not mx_host:
        return None, "no_mx"

    results = []
    for pattern in EMAIL_PATTERNS:
        email = f"{pattern}@{domain}"
        status = _smtp_verify(email, mx_host)
        log.info("  %s → %s", email, status)
        if status == "valid":
            return email, "valid"
        if status == "catchall":
            # On garde le premier catch-all (pattern le plus probable)
            if not results:
                results.append((email, "catchall"))
        elif status == "unknown":
            if not results:
                results.append((email, "probable"))

    if results:
        return results[0]
    return None, "not_found"


def find_email_hunter(domain: str, company_name: str = "") -> tuple[Optional[str], str]:
    """
    Cherche l'email via Hunter.io Domain Search API.
    Retourne (email, statut) ou (None, "no_api_key") si pas de clé.
    """
    api_key = os.getenv("HUNTER_API_KEY", "")
    if not api_key:
        return None, "no_api_key"

    try:
        r = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": api_key, "limit": 5},
            timeout=10,
        )
        data = r.json()
        emails = data.get("data", {}).get("emails", [])
        if emails:
            # Trier par score de confiance
            best = max(emails, key=lambda e: e.get("confidence", 0))
            return best["value"], f"hunter:{best.get('confidence', 0)}%"
        # Essayer l'email générique du domain
        generic = data.get("data", {}).get("pattern")
        if generic and data.get("data", {}).get("emails"):
            return None, "hunter:no_email"
        return None, "hunter:not_found"
    except Exception as e:
        log.warning("Hunter API error: %s", e)
        return None, "hunter:error"


def enrich_prospect_email(website: str, company_name: str = "") -> dict:
    """
    Enrichit un prospect avec email SMTP + Hunter.
    Retourne un dict avec les résultats des deux méthodes.
    """
    domain = _extract_domain(website)
    if not domain:
        return {"domain": None, "smtp_email": None, "smtp_status": "skip", "hunter_email": None, "hunter_status": "skip"}

    log.info("Enrichissement %s (domaine: %s)", company_name or website, domain)

    smtp_email, smtp_status = find_email_smtp(domain)
    hunter_email, hunter_status = find_email_hunter(domain, company_name)

    return {
        "domain": domain,
        "smtp_email": smtp_email,
        "smtp_status": smtp_status,
        "hunter_email": hunter_email,
        "hunter_status": hunter_status,
        "best_email": smtp_email if smtp_status == "valid" else (hunter_email or smtp_email),
    }


def enrich_campaign(campaign_id: str, dry_run: bool = False):
    """Enrichit tous les prospects d'une campagne sans email."""
    import sys
    sys.path.insert(0, ".")
    from src.database import SessionLocal
    from src.models import ProspectDB

    db = SessionLocal()
    try:
        prospects = (
            db.query(ProspectDB)
            .filter(ProspectDB.campaign_id == campaign_id, ProspectDB.email.is_(None))
            .all()
        )
        print(f"\n=== Enrichissement email — {len(prospects)} prospects ===\n")

        results = []
        for p in prospects:
            r = enrich_prospect_email(p.website or "", p.name)
            results.append({"name": p.name, **r})

            # Choisir le meilleur email
            best = r.get("best_email")
            smtp_s = r["smtp_status"]
            hunter_s = r["hunter_status"]

            status_icon = {
                "valid": "✅", "catchall": "~", "probable": "?",
                "not_found": "❌", "no_mx": "❌", "skip": "⏭",
            }.get(smtp_s, "?")

            print(f"{status_icon} {p.name[:35]:<35}  SMTP={r['smtp_email'] or '—':30}  Hunter={r['hunter_email'] or '—'}")

            if best and not dry_run:
                p.email = best
                db.commit()
                print(f"   → Sauvegardé : {best} ({smtp_s})")

        # Résumé
        valid   = sum(1 for r in results if r["smtp_status"] == "valid")
        catchall= sum(1 for r in results if r["smtp_status"] == "catchall")
        probable= sum(1 for r in results if r["smtp_status"] == "probable")
        skipped = sum(1 for r in results if r["smtp_status"] == "skip")
        no_mx   = sum(1 for r in results if r["smtp_status"] == "no_mx")

        print(f"\n--- Résumé ---")
        print(f"✅ Confirmés SMTP : {valid}")
        print(f"~  Catch-all      : {catchall}")
        print(f"?  Probables      : {probable}")
        print(f"⏭  Ignorés (hébergeurs) : {skipped}")
        print(f"❌ Pas de MX / non trouvé : {no_mx}")
        print(f"\nTotal avec email à contacter : {valid + catchall + probable}")

        return results
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    campaign_id = sys.argv[1] if len(sys.argv) > 1 else "f61a9fed-1730-446a-a48c-8e480a28166d"
    dry = "--dry" in sys.argv
    enrich_campaign(campaign_id, dry_run=dry)
