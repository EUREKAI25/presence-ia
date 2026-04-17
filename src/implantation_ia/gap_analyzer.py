"""
Analyse des écarts — client vs TOP 3 concurrents.
Compare la situation du client avec ce que font les concurrents cités par les IA.
"""

# Écarts détectables depuis l'analyse concurrents + score client
_GAP_RULES = [
    {
        "id":       "faq_manquante",
        "gap":      "FAQ absente ou insuffisante",
        "check":    lambda comps, score: any(c.get("pages", {}).get("faq") for c in comps) and score < 5,
        "impact":   "Les IA répondent aux requêtes locales en s'appuyant directement sur les FAQ de qualité. Vos concurrents en ont une, pas vous.",
        "priority": "high",
    },
    {
        "id":       "pages_locales_manquantes",
        "gap":      "Pages de services locales absentes",
        "check":    lambda comps, score: any(c.get("pages", {}).get("pages_locales") for c in comps) and score < 6,
        "impact":   "Vos concurrents ont des pages dédiées '{métier} à {ville}'. Ces pages sont la source principale de citation pour ChatGPT et Gemini.",
        "priority": "high",
    },
    {
        "id":       "avis_insuffisants",
        "gap":      "Volume d'avis Google insuffisant",
        "check":    lambda comps, score: any(
            int(c.get("signals", {}).get("review_count", 0) or 0) > 20
            for c in comps
        ) and score < 7,
        "impact":   "Vos concurrents ont accumulé plus d'avis Google récents. Le volume et la fraîcheur des avis sont des signaux décisifs pour les IA.",
        "priority": "high",
    },
    {
        "id":       "blog_absent",
        "gap":      "Contenu de blog / articles locaux absents",
        "check":    lambda comps, score: any(c.get("pages", {}).get("blog") for c in comps) and score < 7,
        "impact":   "Vos concurrents publient du contenu frais sur leur métier et leur ville. Ce contenu est lu et indexé par les IA.",
        "priority": "medium",
    },
    {
        "id":       "site_absent",
        "gap":      "Présence web insuffisante ou site non structuré",
        "check":    lambda comps, score: score < 3,
        "impact":   "Les assistants IA ne trouvent pas de source fiable sur votre activité. Vos concurrents ont un site structuré qui leur donne une avance significative.",
        "priority": "high",
    },
    {
        "id":       "contenu_services_faible",
        "gap":      "Contenu de services trop générique",
        "check":    lambda comps, score: any(c.get("pages", {}).get("pages_services") for c in comps) and score < 5,
        "impact":   "Vos concurrents décrivent précisément leurs prestations avec des détails locaux. Ce niveau de détail rend leur contenu plus crédible pour les IA.",
        "priority": "medium",
    },
    {
        "id":       "signaux_confiance_faibles",
        "gap":      "Signaux de confiance insuffisants",
        "check":    lambda comps, score: any(c.get("signals", {}).get("google_rating") for c in comps) and score < 6,
        "impact":   "Vos concurrents affichent des notes et certifications qui rassurent les IA. Ces signaux de confiance conditionnent leur recommandation.",
        "priority": "medium",
    },
    {
        "id":       "jsonld_manquant",
        "gap":      "Données structurées JSON-LD absentes",
        "check":    lambda comps, score: score < 8,
        "impact":   "Le balisage LocalBusiness permet aux IA de lire vos informations directement en format structuré. Son absence est un désavantage technique constant.",
        "priority": "low",
    },
]


def _enrich_gap(gap: dict, business_type: str, city: str) -> dict:
    return {
        "gap":      gap["gap"].replace("{métier}", business_type).replace("{ville}", city),
        "impact":   gap["impact"].replace("{métier}", business_type).replace("{ville}", city),
        "priority": gap["priority"],
    }


def generate_gap_analysis(
    score_data: dict,
    competitor_analyses: list[dict],
    business_type: str,
    city: str,
) -> list[dict]:
    """
    Génère l'analyse des écarts entre le client et les TOP 3 concurrents.

    Args:
        score_data          : retourné par scoring.compute_score()
        competitor_analyses : retourné par analyze_top_competitors()
        business_type       : type d'activité
        city                : ville

    Returns:
        [{gap, impact, priority}, ...] — priorité décroissante
    """
    score = score_data.get("score", 0.0)
    comps = [c for c in competitor_analyses if not c.get("error")]

    # Si pas de concurrents analysés, utiliser les règles basées sur le score seul
    if not comps:
        comps_fallback = [{"pages": {}, "signals": {}}]
        triggered = [
            _enrich_gap(rule, business_type, city)
            for rule in _GAP_RULES
            if rule["check"](comps_fallback, score)
        ]
    else:
        triggered = [
            _enrich_gap(rule, business_type, city)
            for rule in _GAP_RULES
            if rule["check"](comps, score)
        ]

    # Trier par priorité : high > medium > low
    order = {"high": 0, "medium": 1, "low": 2}
    triggered.sort(key=lambda x: order.get(x["priority"], 9))

    return triggered


def build_competitor_summary(competitor_analyses: list[dict]) -> list[dict]:
    """
    Construit un résumé structuré de chaque concurrent pour le livrable.

    Returns:
        [{name, website, count, has_faq, has_local_pages, review_count, google_rating, strengths, why_cited}, ...]
    """
    result = []
    for c in competitor_analyses:
        pages   = c.get("pages", {})
        signals = c.get("signals", {})
        result.append({
            "name":             c.get("name", ""),
            "website":          c.get("website", ""),
            "count":            c.get("count", 0),
            "has_faq":          bool(pages.get("faq")),
            "has_local_pages":  bool(pages.get("pages_locales")),
            "has_blog":         bool(pages.get("blog")),
            "has_services":     bool(pages.get("pages_services")),
            "google_rating":    signals.get("google_rating", ""),
            "review_count":     signals.get("review_count", ""),
            "years_experience": signals.get("years_experience", ""),
            "strengths":        c.get("strengths", [])[:3],
            "why_cited":        c.get("why_cited", ""),
            "error":            c.get("error"),
        })
    return result
