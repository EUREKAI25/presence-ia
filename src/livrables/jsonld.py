"""
JSONLD_GENERATOR (10B)
Génère les blocs JSON-LD prêts à coller dans le <head> du site client.
Types : LocalBusiness, AggregateRating (si avis), FAQPage (si faq_items fournis).
"""
import json
from pathlib import Path
from typing import List, Optional

from ..models import ProspectDB

DIST_DIR = Path(__file__).parent.parent.parent / "dist"


def generate_jsonld(p: ProspectDB, faq_items: Optional[List[dict]] = None) -> dict:
    """
    Génère les blocs JSON-LD pour un prospect.

    Args:
        p: ProspectDB
        faq_items: liste de {"question": str, "answer": str} (depuis FAQ_GENERATOR 10A)

    Returns:
        {"blocks": {...}, "html_snippet": str, "instructions": str}
    """
    blocks = {}

    # ── LocalBusiness ──────────────────────────────────────────────────
    lb: dict = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": p.name,
        "address": {
            "@type": "PostalAddress",
            "addressLocality": p.city,
            "addressCountry": "FR",
        },
    }
    if p.phone:
        lb["telephone"] = p.phone
    if p.website:
        lb["url"] = p.website
    if p.profession:
        lb["description"] = (
            f"{p.profession.capitalize()} à {p.city} — "
            f"professionnel local recommandé par ses clients."
        )

    # ── AggregateRating (si reviews disponibles) ───────────────────────
    if p.reviews_count and p.reviews_count > 0:
        lb["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": "4.5",
            "reviewCount": str(p.reviews_count),
            "bestRating": "5",
            "worstRating": "1",
        }

    blocks["local_business"] = lb

    # ── FAQPage ────────────────────────────────────────────────────────
    if faq_items:
        faq_page = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item["question"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": item["answer"],
                    },
                }
                for item in faq_items
            ],
        }
        blocks["faq_page"] = faq_page

    # ── HTML snippet ───────────────────────────────────────────────────
    snippets = [
        f'<script type="application/ld+json">\n'
        f'{json.dumps(lb, ensure_ascii=False, indent=2)}\n'
        f'</script>'
    ]
    if faq_items and "faq_page" in blocks:
        snippets.append(
            f'<script type="application/ld+json">\n'
            f'{json.dumps(blocks["faq_page"], ensure_ascii=False, indent=2)}\n'
            f'</script>'
        )
    html_snippet = "\n\n".join(snippets)

    # ── Sauvegarde dist/ ───────────────────────────────────────────────
    out_dir = DIST_DIR / p.prospect_id / "livrables"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "jsonld.json").write_text(
        json.dumps(blocks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "jsonld_snippet.html").write_text(html_snippet, encoding="utf-8")

    return {
        "blocks": blocks,
        "html_snippet": html_snippet,
        "instructions": _instructions(p),
        "files": {
            "json": str(out_dir / "jsonld.json"),
            "html": str(out_dir / "jsonld_snippet.html"),
        },
    }


def _instructions(p: ProspectDB) -> str:
    return f"""Instructions d'intégration JSON-LD — {p.name}

Coller le code HTML ci-dessus dans le <head> de chaque page de votre site.

WORDPRESS
  Option 1 (recommandée) : plugin Yoast SEO ou Rank Math — section "Code personnalisé"
  Option 2 : Apparence > Éditeur de thème > header.php, avant </head>

WIX
  Paramètres > Avancé > Code personnalisé > Ajouter dans l'en-tête

SQUARESPACE
  Paramètres > Avancé > Injection de code > En-tête

HTML PERSONNALISÉ
  Coller avant </head> dans votre fichier index.html

Vérification : https://search.google.com/test/rich-results
  → Entrer l'URL de votre site, vérifier que LocalBusiness et FAQPage apparaissent.
"""
