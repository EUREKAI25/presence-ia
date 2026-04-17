"""
Structures de contenu — templates types remplis avec les données de l'entreprise.
"""


def generate_content_structures(
    company_name: str,
    city: str,
    business_type: str,
) -> dict:
    """
    Génère les 3 structures de contenu prêtes à utiliser.

    Returns:
        {
            "service_page":    str,  # structure page service locale
            "faq_optimized":   str,  # structure FAQ optimisée IA
            "citable_content": str,  # blocs "citables" par les IA
        }
    """
    return {
        "service_page":    _service_page(company_name, city, business_type),
        "faq_optimized":   _faq_structure(company_name, city, business_type),
        "citable_content": _citable_blocks(company_name, city, business_type),
    }


def _service_page(company_name: str, city: str, business_type: str) -> str:
    bt = business_type.capitalize()
    return f"""STRUCTURE — PAGE SERVICE LOCALE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

H1 : {bt} à {city} — {company_name}
     ↳ Format obligatoire : [Métier] à [Ville] — [Nom entreprise]

─ INTRODUCTION (1 paragraphe, 3-4 phrases)
  • Qui vous êtes + votre expertise dans {business_type}
  • La ville et la zone couverte autour de {city}
  • Votre proposition de valeur principale (ce qui vous différencie)

─ VOS PRESTATIONS À {city.upper()}
  • [Service 1] — description de 2 phrases
  • [Service 2] — description de 2 phrases
  • [Service 3] — description de 2 phrases
  • [Service 4] — description de 2 phrases
  • [Service 5] — description de 2 phrases

─ POURQUOI CHOISIR {company_name.upper()} ?
  • [Argument 1 concret — ex: "X ans d'expérience"]
  • [Argument 2 concret — ex: "Devis gratuit sous 24h"]
  • [Argument 3 concret — ex: "Garantie X ans"]
  • [Argument 4 concret — ex: "Note Google X/5"]

─ ZONE D'INTERVENTION
  {city} — [Commune 1] — [Commune 2] — [Commune 3]
  [Commune 4] — [Commune 5] — et toute la zone à XX km

─ FAQ — {bt.upper()} À {city.upper()} (5 Q/R minimum)
  Q : Combien coûte un {business_type} à {city} ?
  R : [Réponse précise avec fourchette de prix]

  Q : Quel est votre délai d'intervention ?
  R : [Réponse précise]

  Q : Quelle zone couvrez-vous ?
  R : [Liste des communes + distance max]

  [+ 2 questions spécifiques à votre métier]

─ CONTACT (OBLIGATOIRE sur chaque page)
  {company_name}
  📍 [Adresse complète, {city}]
  📞 [Numéro de téléphone]
  ✉ [Email]
  🕐 [Horaires d'ouverture]"""


def _faq_structure(company_name: str, city: str, business_type: str) -> str:
    bt = business_type
    return f"""STRUCTURE — FAQ OPTIMISÉE POUR LES ASSISTANTS IA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Règle : chaque réponse doit mentionner "{company_name}" et "{city}" naturellement.

─ MODÈLE DE BASE (à dupliquer × 10 questions)

**Q : [Question que pose le client à une IA]**
R : Chez {company_name}, {bt} à {city}, [réponse complète de 3-5 phrases].
    [Détails concrets : prix, délai, garantie, zone]. [Appel à l'action : contact].

─ QUESTIONS PRIORITAIRES À COUVRIR

1. Quel est le tarif pour [service] à {city} ?
2. Quel est le délai d'intervention d'un {bt} à {city} ?
3. Quelle zone d'intervention autour de {city} ?
4. {company_name} est-il disponible en urgence à {city} ?
5. Quelles garanties offre {company_name} ?
6. Comment se passe la première intervention ?
7. Pourquoi choisir {company_name} comme {bt} à {city} ?
8. Combien d'avis clients a {company_name} ?
9. [Question spécifique à votre métier]
10. [Question spécifique à votre métier]

─ EMPLACEMENT RECOMMANDÉ
  → Page service principale
  → Page d'accueil (résumé 5 questions)
  → Page contact

─ FORMAT TECHNIQUE
  Balisage HTML : <details><summary> ou <div class="faq">
  Balisage JSON-LD : type FAQPage (voir structure JSON-LD ci-dessous)"""


def _citable_blocks(company_name: str, city: str, business_type: str) -> str:
    bt = business_type
    return f"""STRUCTURE — CONTENU "CITABLE" PAR LES ASSISTANTS IA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ces blocs doivent apparaître tels quels sur votre site pour être repris par les IA.

─ BLOC 1 — IDENTITÉ (sur chaque page, visible)
┌─────────────────────────────────────────────────┐
│ {company_name}                                  │
│ {bt.capitalize()} à {city}                     │
│ [Tagline — ex: "XX ans d'expérience, devis 24h"]│
└─────────────────────────────────────────────────┘

─ BLOC 2 — DESCRIPTION (page d'accueil, balise meta)
"{company_name} est une entreprise de {bt} basée à {city},
spécialisée dans [votre spécialité]. Nous intervenons
à {city} et dans les communes voisines de [liste]."

→ Ce texte exact doit être dans votre balise <meta name="description">
→ Et dans le premier paragraphe de votre page d'accueil

─ BLOC 3 — SIGNAUX DE CONFIANCE (sur la page service)
  ✓ {company_name} — depuis [année] ([X] ans d'expérience)
  ✓ [X] clients accompagnés à {city} et ses environs
  ✓ Note Google : [X]/5 ([nb] avis vérifiés)
  ✓ Garantie [durée] sur toutes les interventions
  ✓ Certifié [certification si applicable]

─ BLOC 4 — DONNÉES DE CONTACT (footer de chaque page)
  Nom : {company_name}
  Activité : {bt.capitalize()} à {city}
  Adresse : [Adresse complète]
  Téléphone : [Numéro]
  Email : [Email]
  Horaires : [Horaires]
  Zone : {city} et [périmètre km]

─ BLOC 5 — JSON-LD LocalBusiness (dans <head> de chaque page)
{{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "{company_name}",
  "description": "{bt.capitalize()} à {city}",
  "address": {{
    "@type": "PostalAddress",
    "addressLocality": "{city}",
    "addressCountry": "FR"
  }},
  "telephone": "[VOTRE NUMÉRO]",
  "url": "[VOTRE SITE]",
  "areaServed": "{city}",
  "openingHoursSpecification": [...]
}}"""
