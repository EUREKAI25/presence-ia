"""
Génération de données structurées JSON-LD pour la visibilité IA et SEO.

Blocs générés :
  LocalBusiness  — entité entreprise locale (lu directement par les IA)
  FAQPage        — questions/réponses (signal fort pour ChatGPT et Gemini)

Les JSON-LD sont à insérer dans le <head> des pages web du prospect.
"""

import json
from datetime import date


def generate_schema(
    prospect,
    faq_items: list[dict] | None = None,
) -> dict:
    """
    Génère les blocs JSON-LD pour un prospect.

    Args:
        prospect  : instance V3ProspectDB
        faq_items : liste [{question, answer}] retournée par faq_generator

    Returns:
        {
          "local_business": dict,  # JSON-LD LocalBusiness
          "faq_page":       dict,  # JSON-LD FAQPage (None si pas de FAQ)
          "html_snippet":   str,   # <script> tags prêts à coller dans <head>
          "instructions":   str,   # message d'instructions pour le client
        }
    """
    name       = getattr(prospect, "name", "")
    profession = getattr(prospect, "profession", "")
    ville      = getattr(prospect, "city", "").capitalize()
    phone      = getattr(prospect, "phone", "") or ""
    website    = getattr(prospect, "website", "") or getattr(prospect, "url", "") or ""
    rating     = getattr(prospect, "rating", None)
    address    = getattr(prospect, "address", "") or ""

    # ── LocalBusiness ─────────────────────────────────────────────────────────
    local_business: dict = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": name,
        "description": f"{profession.capitalize()} à {ville}. Devis gratuit, intervention rapide.",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": ville,
            "addressCountry": "FR",
        },
        "areaServed": {
            "@type": "City",
            "name": ville,
        },
    }

    if phone:
        local_business["telephone"] = phone
    if website:
        local_business["url"] = website
    if address:
        local_business["address"]["streetAddress"] = address

    # Note et avis Google si disponibles
    if rating:
        try:
            local_business["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": str(float(rating)),
                "bestRating": "5",
                "worstRating": "1",
                "ratingCount": "1",  # Valeur conservative — à mettre à jour avec le vrai nombre
            }
        except (ValueError, TypeError):
            pass

    # Mapping profession → @type Schema.org
    _type_map = {
        "plombier": "Plumber",
        "plomberie": "Plumber",
        "électricien": "Electrician",
        "électricité": "Electrician",
        "serrurier": "Locksmith",
        "peintre": "HousePainter",
        "menuisier": "Carpenter",
        "chauffagiste": "HVACBusiness",
        "architecte": "Architect",
        "dentiste": "Dentist",
        "médecin": "Physician",
        "avocat": "Attorney",
        "comptable": "AccountingService",
        "restaurant": "Restaurant",
        "hôtel": "Hotel",
        "salon": "BeautySalon",
        "coiffeur": "HairSalon",
        "garagiste": "AutoRepair",
    }
    for key, schema_type in _type_map.items():
        if key in profession.lower():
            local_business["@type"] = schema_type
            break

    # ── FAQPage ───────────────────────────────────────────────────────────────
    faq_page = None
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

    # ── HTML snippet ──────────────────────────────────────────────────────────
    lb_script = (
        f'<script type="application/ld+json">\n'
        f'{json.dumps(local_business, ensure_ascii=False, indent=2)}\n'
        f'</script>'
    )
    faq_script = ""
    if faq_page:
        faq_script = (
            f'\n<script type="application/ld+json">\n'
            f'{json.dumps(faq_page, ensure_ascii=False, indent=2)}\n'
            f'</script>'
        )

    html_snippet = lb_script + faq_script

    instructions = (
        f"Copiez-collez le code ci-dessus dans le <head> de votre page d'accueil "
        f"et de votre page '{profession} à {ville}'.\n"
        f"Sur WordPress : utilisez le plugin 'Insert Headers and Footers' → section Header.\n"
        f"Sur Wix : Paramètres → SEO avancé → Balises personnalisées → Ajouter une balise → Code.\n"
        f"Sur Shopify : Thème → Modifier le code → layout/theme.liquid → coller avant </head>."
    )

    return {
        "local_business": local_business,
        "faq_page":       faq_page,
        "html_snippet":   html_snippet,
        "instructions":   instructions,
    }
