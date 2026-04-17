"""
Stratégie d'implantation — transforme les écarts en plan d'exécution concret.
3 phases : immédiat / court terme / optimisation
"""


def build_strategy(
    gaps: list[dict],
    competitor_summaries: list[dict],
    business_type: str,
    city: str,
) -> dict:
    """
    Génère la stratégie d'implantation depuis les écarts et l'analyse concurrents.

    Returns:
        {
            "phases": [
                {"phase": "immediate", "label": str, "steps": [str, ...]},
                {"phase": "short_term", "label": str, "steps": [str, ...]},
                {"phase": "optimization", "label": str, "steps": [str, ...]},
            ],
            "pages_to_create":   [str, ...],
            "pages_to_optimize": [str, ...],
            "content_to_produce": [str, ...],
            "competitive_edge":  str,
        }
    """
    bt = business_type
    c  = city

    high_gaps   = [g for g in gaps if g["priority"] == "high"]
    medium_gaps = [g for g in gaps if g["priority"] == "medium"]
    low_gaps    = [g for g in gaps if g["priority"] == "low"]

    # ── Phase 1 : Immédiat (0-2 semaines) ─────────────────────────────────
    immediate = _build_immediate(high_gaps, bt, c, competitor_summaries)

    # ── Phase 2 : Court terme (2-6 semaines) ──────────────────────────────
    short_term = _build_short_term(medium_gaps, bt, c, competitor_summaries)

    # ── Phase 3 : Optimisation (6-12 semaines) ────────────────────────────
    optimization = _build_optimization(low_gaps, bt, c, competitor_summaries)

    # ── Pages à créer / optimiser ─────────────────────────────────────────
    pages_to_create = _pages_to_create(gaps, bt, c)
    pages_to_optimize = _pages_to_optimize(gaps, bt, c)
    content_to_produce = _content_to_produce(gaps, bt, c)

    # ── Avantage concurrentiel ────────────────────────────────────────────
    competitive_edge = _competitive_edge(competitor_summaries, bt, c)

    return {
        "phases": [
            {"phase": "immediate",    "label": "Phase 1 — Immédiat (0-2 semaines)",      "steps": immediate},
            {"phase": "short_term",   "label": "Phase 2 — Court terme (2-6 semaines)",    "steps": short_term},
            {"phase": "optimization", "label": "Phase 3 — Optimisation (6-12 semaines)",  "steps": optimization},
        ],
        "pages_to_create":    pages_to_create,
        "pages_to_optimize":  pages_to_optimize,
        "content_to_produce": content_to_produce,
        "competitive_edge":   competitive_edge,
    }


def _build_immediate(high_gaps: list, bt: str, c: str, comps: list) -> list[str]:
    steps = []
    gap_ids = {g.get("gap", "").lower() for g in high_gaps}

    if any("faq" in g for g in gap_ids):
        steps.append(f"Créer une FAQ de 10 questions sur votre page principale ({bt} à {c})")

    if any("pages" in g and "local" in g for g in gap_ids):
        steps.append(f"Créer une page dédiée '{bt.capitalize()} à {c}' avec 600+ mots")

    if any("avis" in g for g in gap_ids):
        steps.append(f"Lancer une campagne de collecte d'avis Google (objectif : 15 avis en 2 semaines)")

    if any("présence" in g or "site" in g for g in gap_ids):
        steps.append(f"Vérifier et compléter la fiche Google Business Profile")
        steps.append(f"Uniformiser le nom '{bt.capitalize()}' sur tous les supports")

    if not steps:
        steps = [
            f"Compléter la fiche Google Business Profile avec photos et description",
            f"Vérifier la cohérence NAP (Nom, Adresse, Téléphone) sur tous les supports",
            f"Demander 5 avis Google à vos meilleurs clients actuels",
        ]

    return steps


def _build_short_term(medium_gaps: list, bt: str, c: str, comps: list) -> list[str]:
    steps = []
    gap_ids = {g.get("gap", "").lower() for g in medium_gaps}

    if any("blog" in g or "article" in g for g in gap_ids):
        steps.append(f"Rédiger un article '{bt.capitalize()} à {c} — guide complet 2026'")

    if any("service" in g or "contenu" in g for g in gap_ids):
        steps.append(f"Enrichir les pages de services avec descriptions détaillées et tarifs indicatifs")
        steps.append(f"Ajouter la zone d'intervention et les communes voisines sur toutes les pages")

    if any("confiance" in g or "signal" in g for g in gap_ids):
        steps.append(f"Afficher les certifications et garanties sur la page d'accueil")
        steps.append(f"Créer une page 'À propos' avec historique et équipe")

    # Pages locales supplémentaires depuis les concurrents
    if comps and any(c_s.get("has_local_pages") for c_s in comps):
        steps.append(f"Créer des pages pour les 3 communes principales autour de {c}")

    if not steps:
        steps = [
            f"Créer une page de blog avec 1 article ciblé sur {bt} à {c}",
            f"Ajouter un formulaire de devis en ligne",
            f"S'inscrire sur 3 annuaires locaux supplémentaires",
        ]

    return steps


def _build_optimization(low_gaps: list, bt: str, c: str, comps: list) -> list[str]:
    steps = []
    gap_ids = {g.get("gap", "").lower() for g in low_gaps}

    if any("json" in g or "structur" in g for g in gap_ids):
        steps.append(f"Installer le balisage JSON-LD LocalBusiness + FAQPage sur toutes les pages")

    steps.append(f"Lancer une relance mensuelle d'avis Google (objectif : +5 avis/mois)")
    steps.append(f"Publier 1 article de blog par mois sur {bt} à {c}")

    if comps:
        comp_with_blog = [c_s for c_s in comps if c_s.get("has_blog")]
        if comp_with_blog:
            steps.append(f"Créer une stratégie de contenu mensuelle (inspirée de {comp_with_blog[0]['name']} qui publie régulièrement)")

    steps.append(f"Re-test IA dans 8 semaines pour mesurer la progression")

    return steps


def _pages_to_create(gaps: list, bt: str, c: str) -> list[str]:
    pages = [f"Page service : '{bt.capitalize()} à {c}'"]
    gap_ids = {g.get("gap", "").lower() for g in gaps}

    if any("blog" in g or "article" in g for g in gap_ids):
        pages.append(f"Article blog : '{bt.capitalize()} à {c} — guide 2026'")

    if any("local" in g for g in gap_ids):
        pages.extend([
            f"Page service locale : '{bt.capitalize()} — {c} et communes voisines'",
        ])

    pages.append(f"Page FAQ dédiée : 'Questions sur {bt.lower()} à {c}'")
    return pages


def _pages_to_optimize(gaps: list, bt: str, c: str) -> list[str]:
    return [
        "Page d'accueil — ajouter '{bt} à {c}' dans le H1 et la meta description".replace("{bt}", bt).replace("{c}", c),
        "Page 'Nos services' — enrichir avec détails locaux et tarifs indicatifs",
        "Page 'Contact' — ajouter zone d'intervention et horaires détaillés",
    ]


def _content_to_produce(gaps: list, bt: str, c: str) -> list[str]:
    content = [
        f"FAQ 10 questions '{bt.capitalize()} à {c}'",
        f"Texte page service 600 mots avec FAQ intégrée",
        f"Description Google Business Profile optimisée",
        f"Balises meta (title + description) pour chaque page service",
        f"Snippet JSON-LD LocalBusiness",
    ]
    if any("blog" in g.get("gap", "").lower() for g in gaps):
        content.append(f"Article blog 800 mots : '{bt.capitalize()} à {c} — tout savoir'")
    return content


def _competitive_edge(comps: list, bt: str, c: str) -> str:
    """Identifie l'avantage concurrentiel possible face aux TOP 3."""
    if not comps:
        return (
            f"Aucun concurrent fortement établi n'est identifié sur {bt} à {c}. "
            f"C'est une opportunité : en mettant en place rapidement les bonnes bases, "
            f"vous pouvez devenir la référence locale avant que d'autres s'imposent."
        )

    comp_names = [c_s["name"] for c_s in comps[:2] if c_s.get("name")]
    names_str  = " et ".join(comp_names) if comp_names else "vos concurrents"

    weaknesses = []
    if not all(c_s.get("has_faq") for c_s in comps):
        weaknesses.append("ils n'ont pas tous une FAQ complète")
    if not all(c_s.get("has_blog") for c_s in comps):
        weaknesses.append("peu d'entre eux publient du contenu régulier")
    if not any(c_s.get("years_experience") for c_s in comps):
        weaknesses.append("leur expérience est peu mise en avant")

    if weaknesses:
        weak_str = ", ".join(weaknesses)
        return (
            f"{names_str} sont bien positionnés mais présentent des failles : {weak_str}. "
            f"En comblant ces lacunes avec une stratégie de contenu régulière et une FAQ complète, "
            f"vous pouvez les rejoindre puis les dépasser en 2-3 mois."
        )

    return (
        f"{names_str} sont des concurrents solides. "
        f"Votre avantage sera la régularité : nouveaux avis mensuels, contenu frais, "
        f"et une FAQ plus complète et mieux structurée que la leur."
    )
