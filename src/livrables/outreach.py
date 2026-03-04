"""
OUTREACH_GENERATOR (07)
Génère des messages de prise de contact quand l'email est absent.
V1 manuel : messages courts (SMS/WhatsApp) et longs (formulaire contact).
"""
import json
import os
from pathlib import Path
from typing import Optional

from ..models import ProspectDB

DIST_DIR = Path(__file__).parent.parent.parent / "dist"
BASE_URL  = os.getenv("BASE_URL", "http://localhost:8001")


def _competitors_str(p: ProspectDB, n: int = 2) -> str:
    try:
        comps = [c.title() for c in json.loads(p.competitors_cited or "[]")[:n]]
    except Exception:
        comps = []
    return comps[0] if len(comps) == 1 else (
        " et ".join(comps) if comps else "vos concurrents"
    )


def generate_outreach(p: ProspectDB) -> dict:
    """
    Génère 3 messages de prise de contact personnalisés.

    Returns:
        {
          "message_court": str,   SMS / WhatsApp (< 320 chars)
          "message_long": str,    Formulaire contact / DM LinkedIn
          "cta_url": str,         URL landing privée
          "files": {...}
        }
    """
    city     = p.city.capitalize()
    prof     = p.profession
    name     = p.name
    comp_str = _competitors_str(p)
    score    = p.ia_visibility_score or 0
    landing  = f"{BASE_URL}/{prof}?t={p.landing_token}"

    # ── Message court — SMS / WhatsApp ────────────────────────────────
    message_court = (
        f"Bonjour {name}, j'ai testé ce que répond ChatGPT quand un client "
        f"cherche un {prof} à {city}. {comp_str} apparaît. Pas vous. "
        f"J'ai préparé un résumé : {landing}"
    )

    # ── Message long — formulaire / DM ───────────────────────────────
    message_long = f"""Bonjour,

J'ai récemment effectué un audit de visibilité IA pour des {prof}s dans la région de {city}.

Le constat est simple : lorsqu'un client potentiel demande à ChatGPT, Claude ou Gemini \
de recommander un {prof} à {city}, {comp_str} est régulièrement cité. {name} n'apparaît pas.

Votre score de visibilité actuel est de {score:.1f}/10.

Ce n'est pas une question de qualité de vos services — c'est une question de signaux \
numériques que les IA utilisent pour identifier les références locales. Quelques actions \
ciblées suffisent généralement à corriger la situation en 2 à 4 mois.

J'ai préparé un rapport personnalisé avec le détail des tests et un plan d'action concret :
{landing}

Bonne journée,
L'équipe PRESENCE_IA"""

    # ── Sauvegarde ────────────────────────────────────────────────────
    out_dir = DIST_DIR / p.prospect_id / "livrables"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "prospect_id": p.prospect_id,
        "name": name,
        "city": city,
        "profession": prof,
        "message_court": message_court,
        "message_long": message_long,
        "cta_url": landing,
    }
    (out_dir / "outreach.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "message_court": message_court,
        "message_long": message_long,
        "cta_url": landing,
        "char_count_court": len(message_court),
        "files": {"json": str(out_dir / "outreach.json")},
    }
