"""
Patterns de domination — identifie ce qui fait gagner dans un marché local IA.
Analyse l'ensemble des concurrents cités pour extraire les structures communes.
"""


def analyze_domination_patterns(
    competitor_analyses: list[dict],
    gaps: list[dict],
    business_type: str,
    city: str,
) -> dict:
    """
    Analyse les patterns de domination depuis tous les concurrents.

    Returns:
        {
            "total_analyzed":     int,
            "content_prevalence": dict,
            "trust_signals":      dict,
            "content_signals":    [str, ...],
            "winning_formula":    str,
            "opportunities":      [str, ...],
            "dominant_formats":   [str, ...],
            "market_maturity":    str,  # low/medium/high
        }
    """
    comps = [c for c in competitor_analyses if not c.get("error")]

    if not comps:
        return _default_patterns(business_type, city, gaps)

    n = len(comps)

    # ── Prévalence des types de contenu ─────────────────────────────────────
    faq_count   = sum(1 for c in comps if c.get("pages", {}).get("faq"))
    local_count = sum(1 for c in comps if c.get("pages", {}).get("pages_locales"))
    blog_count  = sum(1 for c in comps if c.get("pages", {}).get("blog"))
    svc_count   = sum(1 for c in comps if c.get("pages", {}).get("pages_services"))

    content_prevalence = {
        "faq":         {"count": faq_count,   "pct": round(faq_count / n * 100)},
        "local_pages": {"count": local_count, "pct": round(local_count / n * 100)},
        "blog":        {"count": blog_count,  "pct": round(blog_count / n * 100)},
        "services":    {"count": svc_count,   "pct": round(svc_count / n * 100)},
    }

    # ── Signaux de confiance ─────────────────────────────────────────────────
    ratings = []
    reviews = []
    for c in comps:
        s = c.get("signals", {})
        try:
            r = float(str(s.get("google_rating", "") or "0").replace(",", "."))
            if r > 0:
                ratings.append(r)
        except ValueError:
            pass
        try:
            rv = int(str(s.get("review_count", "") or "0"))
            if rv > 0:
                reviews.append(rv)
        except ValueError:
            pass

    avg_rating  = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
    avg_reviews = round(sum(reviews) / len(reviews))    if reviews else 0
    min_reviews = max(20, round(avg_reviews * 1.3))

    # ── Signaux de contenu observés ──────────────────────────────────────────
    content_signals = []
    if faq_count > 0:
        content_signals.append(
            f"FAQ : présente chez {faq_count}/{n} des concurrents cités "
            f"({content_prevalence['faq']['pct']}%) — signal fort"
        )
    if local_count > 0:
        content_signals.append(
            f"Pages locales : présentes chez {local_count}/{n} concurrents "
            f"({content_prevalence['local_pages']['pct']}%)"
        )
    if blog_count > 0:
        content_signals.append(
            f"Blog / articles : présents chez {blog_count}/{n} concurrents "
            f"({content_prevalence['blog']['pct']}%)"
        )
    if avg_reviews > 0:
        content_signals.append(
            f"Avis Google : moyenne de {avg_reviews} avis chez les concurrents cités "
            f"(seuil de compétition : {min_reviews}+)"
        )

    # ── Formule gagnante ─────────────────────────────────────────────────────
    winning_formula = _build_winning_formula(
        comps, business_type, city, faq_count, local_count, avg_reviews, n
    )

    # ── Opportunités ─────────────────────────────────────────────────────────
    opportunities = _find_opportunities(
        comps, faq_count, local_count, blog_count, n, business_type, city
    )

    # ── Formats dominants ────────────────────────────────────────────────────
    dominant_formats = _dominant_formats(
        faq_count, local_count, blog_count, svc_count, n
    )

    # ── Maturité du marché ───────────────────────────────────────────────────
    maturity = _market_maturity(avg_reviews, faq_count, blog_count, n)

    return {
        "total_analyzed":     n,
        "content_prevalence": content_prevalence,
        "trust_signals": {
            "avg_rating":              avg_rating,
            "avg_reviews":             avg_reviews,
            "min_reviews_to_compete":  min_reviews,
        },
        "content_signals":   content_signals,
        "winning_formula":   winning_formula,
        "opportunities":     opportunities,
        "dominant_formats":  dominant_formats,
        "market_maturity":   maturity,
    }


def _build_winning_formula(comps, bt, city, faq_c, local_c, avg_reviews, n) -> str:
    parts = []

    if faq_c >= n * 0.6:
        parts.append("une FAQ complète et locale")
    elif faq_c > 0:
        parts.append("une FAQ structurée (avantage distinctif car peu en ont)")

    if local_c >= n * 0.5:
        parts.append("des pages dédiées par ville et service")
    elif local_c == 0:
        parts.append("des pages locales (aucun concurrent n'en a — opportunité majeure)")

    if avg_reviews >= 30:
        parts.append(f"un volume d'avis Google solide ({int(avg_reviews)}+ avis)")
    elif avg_reviews >= 10:
        parts.append(f"des avis Google récents et réguliers (seuil : {int(avg_reviews * 1.3)}+)")
    else:
        parts.append("les premiers avis Google (marché peu référencé)")

    # Renforce avec les forces communes des concurrents
    all_strengths = []
    for c in comps:
        all_strengths.extend(c.get("strengths", []))

    if all_strengths:
        parts.append("un contenu clair associant métier, ville et expertise")

    if not parts:
        return (
            f"Dans le marché {bt} à {city}, la visibilité IA se construit sur "
            f"la cohérence : même nom partout, contenu local précis, avis réguliers."
        )

    joined = ", ".join(parts[:-1]) + (f" et {parts[-1]}" if len(parts) > 1 else parts[0])
    return (
        f"Ce qui fait gagner sur {bt} à {city} : {joined}. "
        f"Les concurrents les mieux cités combinent ces signaux de manière cohérente."
    )


def _find_opportunities(comps, faq_c, local_c, blog_c, n, bt, city) -> list:
    ops = []

    if faq_c < n * 0.5:
        ops.append(
            f"FAQ peu répandue ({faq_c}/{n} concurrents) — être le premier avec une FAQ "
            f"complète sur {bt} à {city} = avantage immédiat"
        )
    if local_c < n * 0.4:
        ops.append(
            f"Pages locales sous-développées ({local_c}/{n}) — créer des pages par commune "
            f"autour de {city} sans concurrence directe"
        )
    if blog_c < n * 0.3:
        ops.append(
            f"Peu de contenu de blog ({blog_c}/{n}) — publier 1 article/mois positionne "
            f"durablement face à des concurrents sans stratégie de contenu"
        )
    if not ops:
        ops.append(
            "Marché relativement mature — la domination passe par la régularité : "
            "nouveaux avis mensuels, contenu frais et mise à jour des pages existantes"
        )
    return ops


def _dominant_formats(faq_c, local_c, blog_c, svc_c, n) -> list:
    if n == 0:
        return ["FAQ locale", "Page service {métier} à {ville}", "Données structurées JSON-LD"]

    formats = []
    scored = [
        (svc_c, "Pages de services détaillées (prestations + tarifs)"),
        (local_c, "Pages locales '{métier} à {ville}'"),
        (faq_c,  "FAQ structurée (questions clients réelles)"),
        (blog_c, "Articles de blog ciblés sur le métier et la ville"),
    ]
    for count, label in sorted(scored, reverse=True):
        if count > 0:
            formats.append(label)
    if not formats:
        formats = ["Pages de services", "FAQ locale", "Données structurées"]
    return formats


def _market_maturity(avg_reviews, faq_c, blog_c, n) -> str:
    score = 0
    if avg_reviews >= 30: score += 2
    elif avg_reviews >= 10: score += 1
    if faq_c >= n * 0.5: score += 1
    if blog_c >= n * 0.3: score += 1
    if score <= 1: return "low"
    if score <= 2: return "medium"
    return "high"


def _default_patterns(bt, city, gaps) -> dict:
    """Patterns par défaut quand pas de concurrents analysés."""
    gap_ids = {g.get("gap", "").lower() for g in gaps}

    opportunities = ["Marché non structuré sur les IA — premier arrivé, premier servi"]
    if any("faq" in g for g in gap_ids):
        opportunities.append(f"Créer la première FAQ complète pour {bt} à {city}")
    if any("local" in g for g in gap_ids):
        opportunities.append(f"Créer les premières pages locales dédiées à {city}")

    return {
        "total_analyzed":     0,
        "content_prevalence": {"faq": {"count": 0, "pct": 0}, "local_pages": {"count": 0, "pct": 0}, "blog": {"count": 0, "pct": 0}, "services": {"count": 0, "pct": 0}},
        "trust_signals":      {"avg_rating": 0, "avg_reviews": 0, "min_reviews_to_compete": 20},
        "content_signals":    ["Aucun concurrent analysé — marché ouvert"],
        "winning_formula":    f"Le marché {bt} à {city} est peu structuré sur les IA. Prendre les fondations crée une avance durable.",
        "opportunities":      opportunities,
        "dominant_formats":   ["FAQ locale", "Page service principale", "Données structurées JSON-LD"],
        "market_maturity":    "low",
    }
