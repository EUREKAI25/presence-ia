"""
Stratégie de domination — 3 axes : contenu / structure / autorité.
Construit depuis les patterns + situation du client.
"""


def build_domination_strategy(
    patterns: dict,
    score_data: dict,
    gaps: list[dict],
    business_type: str,
    city: str,
) -> dict:
    """
    Génère la stratégie de domination sur 3 axes.

    Returns:
        {
            "positioning": str,
            "axes":        [{"axis", "title", "goal", "actions", "kpi"}, ...],
            "moat":        str,   # avantage défendable long terme
            "timeline":    str,
        }
    """
    score    = score_data.get("score", 0.0)
    maturity = patterns.get("market_maturity", "low")
    opps     = patterns.get("opportunities", [])

    positioning = _positioning(business_type, city, score, maturity)
    axes        = [
        _axis_content(patterns, gaps, business_type, city),
        _axis_structure(patterns, gaps, business_type, city),
        _axis_authority(patterns, gaps, business_type, city),
    ]
    moat     = _competitive_moat(patterns, business_type, city)
    timeline = _timeline(score, maturity)

    return {
        "positioning": positioning,
        "axes":        axes,
        "moat":        moat,
        "timeline":    timeline,
    }


def _positioning(bt, city, score, maturity) -> str:
    if score < 2:
        return (
            f"Objectif : devenir LA référence de {bt} à {city} sur les assistants IA. "
            f"Partir de zéro est un avantage : les bases posées aujourd'hui "
            f"génèrent une avance que les concurrents devront des mois à rattraper."
        )
    if score < 5:
        return (
            f"Objectif : passer de 'visible occasionnellement' à 'recommandé systématiquement' "
            f"pour {bt} à {city}. La présence existe — il faut la rendre fiable et durable."
        )
    if score < 8:
        return (
            f"Objectif : consolider la position acquise et creuser l'écart "
            f"avec les concurrents sur {bt} à {city}. "
            f"La domination passe par la régularité et la profondeur de contenu."
        )
    return (
        f"Objectif : maintenir la position de référence sur {bt} à {city} "
        f"et anticiper les challengers émergents. Stratégie défensive + expansion sur les zones voisines."
    )


def _axis_content(patterns, gaps, bt, city) -> dict:
    prevalence = patterns.get("content_prevalence", {})
    faq_pct    = prevalence.get("faq", {}).get("pct", 0)
    blog_pct   = prevalence.get("blog", {}).get("pct", 0)
    local_pct  = prevalence.get("local_pages", {}).get("pct", 0)

    actions = [
        f"Créer 1 page service dédiée '{bt.capitalize()} à {city}' (500+ mots, FAQ intégrée)",
        f"Publier 1 article de blog ciblé par mois ('{bt} à {city}' + sujets connexes)",
        f"Créer des pages pour les 5 communes principales autour de {city}",
    ]

    if faq_pct < 60:
        actions.insert(0, f"Créer LA FAQ de référence (10 Q/R) — peu de concurrents en ont une")
    if blog_pct < 30:
        actions.append("Viser 1 article tous les 6 semaines minimum — peu de concurrents publient")

    goal = (
        f"Devenir la source de référence sur {bt} à {city} : "
        f"plus de contenu, mieux structuré, plus régulier que tous les concurrents."
    )
    kpi = "Score IA > 7/10 d'ici 3 mois · 10+ pages de contenu d'ici 6 mois"

    return {
        "axis":    "contenu",
        "title":   "Axe 1 — Contenu",
        "goal":    goal,
        "actions": actions,
        "kpi":     kpi,
    }


def _axis_structure(patterns, gaps, bt, city) -> dict:
    gap_ids = {g.get("gap", "").lower() for g in gaps}

    actions = [
        f"Balise title : '{bt.capitalize()} à {city} — [Nom entreprise]' sur chaque page service",
        "Meta description personnalisée sur chaque page (150 chars, ville + métier + CTA)",
        "Balisage JSON-LD LocalBusiness + FAQPage sur toutes les pages",
        "Cohérence NAP (Nom, Adresse, Téléphone) : même format sur site, GBP, annuaires",
    ]

    if any("local" in g for g in gap_ids):
        actions.append(f"Créer des URL de type /services/{bt.lower().replace(' ','-')}-{city.lower()}/")

    goal = (
        "Rendre le site lisible par les IA en quelques secondes : "
        "chaque page communique clairement qui vous êtes, où vous êtes et ce que vous faites."
    )
    kpi = "100% des pages service avec JSON-LD · Cohérence NAP sur 5+ sources"

    return {
        "axis":    "structure",
        "title":   "Axe 2 — Structure",
        "goal":    goal,
        "actions": actions,
        "kpi":     kpi,
    }


def _axis_authority(patterns, gaps, bt, city) -> dict:
    trust   = patterns.get("trust_signals", {})
    min_rev = trust.get("min_reviews_to_compete", 25)
    avg_rev = trust.get("avg_reviews", 0)

    actions = [
        f"Atteindre {min_rev} avis Google (objectif mensuel : +5 avis)",
        "Campagne SMS / email de demande d'avis après chaque intervention",
        f"S'inscrire sur 5 annuaires locaux avec infos identiques à la fiche GBP",
        "Demander des mentions à 3 partenaires locaux (fournisseurs, associations, syndicats)",
    ]

    if avg_rev < 10:
        actions.insert(0, "Obtenir les 10 premiers avis Google : base indispensable pour les IA")

    goal = (
        "Bâtir une réputation numérique que les IA ne peuvent pas ignorer : "
        "avis nombreux et récents, citations multiples, présence diversifiée."
    )
    kpi = f"{min_rev}+ avis Google · Note ≥ 4,5/5 · 5+ sources externes"

    return {
        "axis":    "autorité",
        "title":   "Axe 3 — Autorité",
        "goal":    goal,
        "actions": actions,
        "kpi":     kpi,
    }


def _competitive_moat(patterns, bt, city) -> str:
    opps = patterns.get("opportunities", [])
    if not opps:
        return (
            f"L'avantage défendable sur {bt} à {city} : la régularité. "
            f"Un concurrent peut copier un contenu — il ne peut pas copier 12 mois de constance."
        )

    if "FAQ" in opps[0] or "premier" in opps[0].lower():
        return (
            f"Être le premier à déployer une FAQ complète et un contenu structuré "
            f"sur {bt} à {city} crée une avance de 6-12 mois sur les concurrents. "
            f"Les IA mémorisent les sources stables — une fois en tête, rester en tête est plus facile."
        )

    return (
        f"La domination durable sur {bt} à {city} repose sur l'accumulation : "
        f"chaque mois, un nouveau contenu, de nouveaux avis, une nouvelle commune couverte. "
        f"Les concurrents inactifs perdent du terrain naturellement."
    )


def _timeline(score, maturity) -> str:
    if score < 2 and maturity == "low":
        return "Résultats visibles en 4-6 semaines · Domination installée en 3-4 mois"
    if score < 5:
        return "Progression significative en 6-8 semaines · Position dominante en 4-6 mois"
    return "Consolidation en 4-8 semaines · Avance creusée sur 6-12 mois"
