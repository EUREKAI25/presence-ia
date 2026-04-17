"""
Diagnostic de visibilité IA.
Génère un diagnostic clair et exploitable depuis les données de l'audit.
Aucun appel LLM supplémentaire — 100% basé sur les résultats.
"""

_LEVELS = [
    (0.0,  0.5,  "absent",      "absente des assistants IA"),
    (0.5,  2.5,  "très_faible", "très peu visible sur les assistants IA"),
    (2.5,  5.0,  "faible",      "visible de manière irrégulière"),
    (5.0,  7.0,  "moyen",       "visible mais pas encore systématiquement recommandée"),
    (7.0,  9.0,  "bon",         "bien positionnée dans les assistants IA"),
    (9.0, 10.1,  "excellent",   "excellemment référencée sur les assistants IA"),
]

_PROBLEMS = {
    "absent": [
        {
            "category": "Contenu web insuffisant",
            "detail": (
                "Les assistants IA ne trouvent aucune information fiable sur votre activité. "
                "Votre site ne contient probablement pas assez de texte décrivant clairement "
                "votre métier et votre localisation."
            ),
        },
        {
            "category": "Fiche Google Business Profile absente ou incomplète",
            "detail": (
                "ChatGPT et Gemini s'appuient directement sur Google Business Profile "
                "pour identifier les prestataires locaux. Une fiche absente ou vide "
                "vous rend totalement invisible dans leurs recommandations."
            ),
        },
        {
            "category": "Aucun signal externe",
            "detail": (
                "Vous n'êtes référencé dans aucun annuaire en ligne (Pages Jaunes, Yelp, "
                "annuaires sectoriels). Ces mentions externes sont indispensables pour "
                "qu'une IA vous identifie comme acteur local de confiance."
            ),
        },
        {
            "category": "Association métier/ville non établie",
            "detail": (
                "Les IA ont besoin que votre nom soit explicitement associé à votre métier "
                "et votre ville pour vous recommander. Cette association doit apparaître "
                "dans vos titres, vos pages et vos descriptions en ligne."
            ),
        },
    ],
    "très_faible": [
        {
            "category": "Contenu local insuffisant",
            "detail": (
                "Votre activité est partiellement connue mais pas assez documentée "
                "pour une recommandation systématique. Il manque du contenu décrivant "
                "précisément vos services, votre zone d'intervention et vos avantages."
            ),
        },
        {
            "category": "Peu ou pas d'avis Google récents",
            "detail": (
                "Les avis Google des 90 derniers jours sont le signal de confiance "
                "n°1 pour ChatGPT et Gemini. Leur absence ou leur ancienneté limite "
                "fortement votre présence dans les recommandations IA."
            ),
        },
        {
            "category": "Structure du site non optimisée",
            "detail": (
                "Votre site ne comporte probablement pas de page dédiée à chaque service "
                "dans votre ville. Ces pages permettent aux IA d'associer votre nom "
                "à des services et une localisation précis."
            ),
        },
    ],
    "faible": [
        {
            "category": "FAQ absente ou trop générique",
            "detail": (
                "Les assistants IA répondent aux questions en s'appuyant sur des FAQ "
                "de qualité. Une FAQ de 8 à 10 questions répondant aux interrogations "
                "locales de vos clients améliore significativement vos citations."
            ),
        },
        {
            "category": "Données structurées (JSON-LD) manquantes",
            "detail": (
                "Le balisage JSON-LD LocalBusiness permet aux IA de lire directement "
                "vos informations (nom, adresse, services, horaires) au format structuré. "
                "Son absence vous prive d'un signal technique important."
            ),
        },
        {
            "category": "Signaux externes à diversifier",
            "detail": (
                "Vous êtes cité sur certaines sources mais pas suffisamment diversifiées. "
                "Multiplier les mentions dans des annuaires, articles et guides locaux "
                "consolide et stabilise votre présence IA."
            ),
        },
    ],
    "moyen": [
        {
            "category": "Couverture géographique à élargir",
            "detail": (
                "Votre visibilité est bonne sur certaines formulations mais limitée. "
                "Enrichir votre contenu avec des références aux communes voisines "
                "et aux zones d'intervention élargit votre zone de recommandation."
            ),
        },
        {
            "category": "Fraîcheur du contenu insuffisante",
            "detail": (
                "La mise à jour régulière du contenu est un critère de confiance pour les IA. "
                "Un article récent ou une page de service mise à jour peut faire progresser "
                "votre score de plusieurs points."
            ),
        },
    ],
    "bon": [
        {
            "category": "Optimisation des signaux de confiance",
            "detail": (
                "Votre présence est solide. Pour atteindre l'excellence, concentrez-vous "
                "sur les signaux de confiance avancés : avis récents et réguliers, "
                "mentions dans la presse locale, données structurées complètes."
            ),
        },
    ],
    "excellent": [
        {
            "category": "Maintien de la position",
            "detail": (
                "Votre position est excellente. L'enjeu est de la maintenir face "
                "à une concurrence croissante : nouveaux avis réguliers, "
                "contenu mis à jour trimestriellement, veille concurrentielle active."
            ),
        },
    ],
}


def _score_level(score: float) -> tuple[str, str]:
    for lo, hi, key, label in _LEVELS:
        if lo <= score < hi:
            return key, label
    return "excellent", "excellemment référencée"


def _model_analysis(queries: list[dict]) -> str:
    counts = {"openai": [0, 0], "anthropic": [0, 0], "gemini": [0, 0]}
    labels = {"openai": "ChatGPT", "anthropic": "Claude", "gemini": "Gemini"}

    for row in queries:
        for key, label_key in [("chatgpt", "openai"), ("claude", "anthropic"), ("gemini", "gemini")]:
            val = row.get(key)
            if val is not None:
                counts[label_key][1] += 1
                if val:
                    counts[label_key][0] += 1

    parts = []
    for key, (cited, total) in counts.items():
        if total == 0:
            continue
        pct = round(cited / total * 100)
        lbl = labels[key]
        if pct == 0:
            parts.append(f"{lbl} : absent ({cited}/{total})")
        elif pct == 100:
            parts.append(f"{lbl} : systématiquement cité ({cited}/{total})")
        else:
            parts.append(f"{lbl} : cité dans {pct}% des requêtes ({cited}/{total})")

    return " | ".join(parts) if parts else "Aucun modèle analysé"


def _competitor_context(competitors: list[dict]) -> str:
    if not competitors:
        return (
            "Aucun concurrent local n'est identifié de manière récurrente par les assistants IA. "
            "C'est une opportunité : être le premier à s'imposer sur votre zone."
        )
    names = [c["name"] for c in competitors[:3]]
    if len(names) == 1:
        return (
            f"{names[0]} est régulièrement cité par les assistants IA sur votre zone. "
            "Analyser son positionnement web vous aidera à identifier les leviers prioritaires."
        )
    joined = ", ".join(names[:-1]) + f" et {names[-1]}"
    return (
        f"Les assistants IA citent actuellement {joined} sur votre zone. "
        "Ces entreprises ont un contenu web et/ou des signaux externes plus développés. "
        "Le plan d'action ci-dessous vous permettra de les rejoindre puis de les dépasser."
    )


def _build_summary(
    company_name: str,
    city: str,
    business_type: str,
    score: float,
    level_label: str,
    score_data: dict,
    queries: list[dict],
) -> str:
    cited = score_data.get("total_citations", 0)
    possible = score_data.get("total_possible", 0)
    n = len(queries)

    if score == 0:
        return (
            f"{company_name} n'est citée par aucun assistant IA sur les {n} requêtes testées "
            f"pour {business_type} à {city}. "
            f"L'entreprise est actuellement invisible pour les {possible} opportunités analysées."
        )

    return (
        f"{company_name} est {level_label} pour {business_type} à {city}. "
        f"Elle est citée {cited} fois sur {possible} opportunités testées "
        f"({n} requêtes × {score_data.get('total_models', 0)} modèles IA). "
        f"Score de visibilité : {score}/10."
    )


def generate_diagnostic(
    company_name: str,
    city: str,
    business_type: str,
    score_data: dict,
    queries: list[dict],
    competitors: list[dict],
) -> dict:
    """
    Génère le diagnostic complet de visibilité IA.

    Returns:
        {
            "score_level":        str,
            "summary":            str,
            "model_analysis":     str,
            "competitor_context": str,
            "problems":           [{"category": str, "detail": str}, ...],
        }
    """
    score = score_data.get("score", 0.0)
    level_key, level_label = _score_level(score)

    return {
        "score_level":        level_key,
        "summary":            _build_summary(company_name, city, business_type, score, level_label, score_data, queries),
        "model_analysis":     _model_analysis(queries),
        "competitor_context": _competitor_context(competitors),
        "problems":           _PROBLEMS.get(level_key, _PROBLEMS["faible"]),
    }
