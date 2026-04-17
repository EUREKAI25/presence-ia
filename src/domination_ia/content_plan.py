"""
Plan de contenu continu — système de production mensuel.
Génère un plan 3 mois détaillé + calendrier 12 mois.
"""

from datetime import date, timedelta
import calendar


def build_content_plan(
    patterns: dict,
    gaps: list[dict],
    business_type: str,
    city: str,
    nearby_cities: list[str] | None = None,
) -> dict:
    """
    Génère le plan de contenu mensuel.

    Returns:
        {
            "monthly_quota":    dict,   # objectifs mensuels
            "month_1":          list,   # détail mois 1
            "month_2":          list,   # détail mois 2
            "month_3":          list,   # détail mois 3
            "calendar_12":      list,   # 1 ligne / mois sur 12 mois
            "local_pages":      list,   # pages locales à créer
            "faq_topics":       list,   # sujets FAQ à couvrir
            "blog_topics":      list,   # sujets blog à couvrir
            "content_signals":  list,   # signaux contextuels
        }
    """
    cities = nearby_cities or _nearby_cities_default(city)
    gap_ids = {g.get("gap", "").lower() for g in gaps}
    maturity = patterns.get("market_maturity", "low")
    prevalence = patterns.get("content_prevalence", {})

    monthly_quota = _monthly_quota(maturity)
    local_pages   = _local_pages(business_type, city, cities)
    faq_topics    = _faq_topics(business_type, city, gap_ids)
    blog_topics   = _blog_topics(business_type, city)

    month_1 = _month_detail(1, business_type, city, gap_ids, local_pages, faq_topics, blog_topics)
    month_2 = _month_detail(2, business_type, city, gap_ids, local_pages, faq_topics, blog_topics)
    month_3 = _month_detail(3, business_type, city, gap_ids, local_pages, faq_topics, blog_topics)

    calendar_12 = _calendar_12(business_type, city, local_pages, blog_topics, maturity)

    content_signals = _content_signals(prevalence, maturity, len(local_pages), len(faq_topics))

    return {
        "monthly_quota":   monthly_quota,
        "month_1":         month_1,
        "month_2":         month_2,
        "month_3":         month_3,
        "calendar_12":     calendar_12,
        "local_pages":     local_pages,
        "faq_topics":      faq_topics,
        "blog_topics":     blog_topics,
        "content_signals": content_signals,
    }


def _monthly_quota(maturity: str) -> dict:
    if maturity == "low":
        return {
            "pages_locales":   2,
            "articles_blog":   1,
            "faq_questions":   3,
            "avis_cibles":     5,
            "annuaires":       2,
            "description":     "Marché peu mature — volume fort pour s'installer rapidement",
        }
    if maturity == "medium":
        return {
            "pages_locales":   1,
            "articles_blog":   1,
            "faq_questions":   2,
            "avis_cibles":     5,
            "annuaires":       1,
            "description":     "Marché en développement — rythme régulier pour consolider",
        }
    return {
        "pages_locales":   1,
        "articles_blog":   2,
        "faq_questions":   2,
        "avis_cibles":     8,
        "annuaires":       1,
        "description":     "Marché mature — contenu frais et avis réguliers pour maintenir la position",
    }


def _nearby_cities_default(city: str) -> list[str]:
    return [
        f"communes autour de {city}",
        f"agglomération de {city}",
        f"zone périurbaine de {city}",
        f"secteur nord de {city}",
        f"secteur sud de {city}",
    ]


def _local_pages(bt: str, city: str, cities: list[str]) -> list[dict]:
    pages = [{
        "title":    f"{bt.capitalize()} à {city}",
        "url_slug": f"{bt.lower().replace(' ', '-')}-{city.lower().replace(' ', '-')}",
        "priority": "high",
        "month":    1,
        "type":     "service_local",
    }]
    for i, c in enumerate(cities[:8], start=1):
        pages.append({
            "title":    f"{bt.capitalize()} à {c}",
            "url_slug": f"{bt.lower().replace(' ', '-')}-{c.lower().replace(' ', '-')}",
            "priority": "medium" if i <= 3 else "low",
            "month":    1 + (i - 1) // 2,
            "type":     "service_local",
        })
    return pages


def _faq_topics(bt: str, city: str, gap_ids: set) -> list[dict]:
    base = [
        {"question": f"Pourquoi choisir un {bt} à {city} ?",         "priority": "high"},
        {"question": f"Quel est le tarif d'un {bt} à {city} ?",       "priority": "high"},
        {"question": f"Comment trouver un {bt} de confiance à {city} ?", "priority": "high"},
        {"question": f"Quelle est la différence entre les {bt}s à {city} ?", "priority": "medium"},
        {"question": f"Un {bt} à {city} se déplace-t-il à domicile ?", "priority": "medium"},
        {"question": f"Quels sont les délais d'intervention pour un {bt} à {city} ?", "priority": "medium"},
        {"question": f"Comment préparer l'intervention d'un {bt} ?",   "priority": "low"},
        {"question": f"Un {bt} à {city} peut-il intervenir en urgence ?", "priority": "low"},
        {"question": f"Quelles garanties offre un {bt} à {city} ?",    "priority": "low"},
        {"question": f"Comment évaluer la qualité d'un {bt} à {city} ?", "priority": "low"},
    ]
    if "faq" in gap_ids:
        for item in base[:3]:
            item["priority"] = "high"
    return base


def _blog_topics(bt: str, city: str) -> list[dict]:
    return [
        {"title": f"Guide complet : choisir son {bt} à {city}",        "month": 1, "type": "guide"},
        {"title": f"Tarifs {bt} à {city} — ce qu'il faut savoir",      "month": 2, "type": "prix"},
        {"title": f"Les 5 erreurs à éviter quand on cherche un {bt}",  "month": 2, "type": "conseil"},
        {"title": f"{bt.capitalize()} à {city} : témoignages clients", "month": 3, "type": "social_proof"},
        {"title": f"Tout savoir sur {bt} : questions fréquentes",      "month": 3, "type": "faq"},
        {"title": f"Comparatif {bt} à {city} et alentours",            "month": 4, "type": "comparatif"},
        {"title": f"Quand faire appel à un {bt} ? Les bons moments",   "month": 5, "type": "conseil"},
        {"title": f"{bt.capitalize()} à {city} : actu et tendances",   "month": 6, "type": "actualite"},
        {"title": f"Intervention urgente {bt} à {city} — ce qu'on fait", "month": 7, "type": "service"},
        {"title": f"Top 3 raisons de choisir notre {bt} à {city}",     "month": 8, "type": "social_proof"},
        {"title": f"{bt.capitalize()} professionnel à {city} — certifications", "month": 9, "type": "expertise"},
        {"title": f"Bilan annuel : {bt} à {city} en chiffres",         "month": 12, "type": "bilan"},
    ]


def _month_detail(
    month: int,
    bt: str,
    city: str,
    gap_ids: set,
    local_pages: list[dict],
    faq_topics: list[dict],
    blog_topics: list[dict],
) -> list[dict]:
    items = []

    # Pages locales du mois
    for p in local_pages:
        if p["month"] == month:
            items.append({
                "semaine": 1,
                "type":    "page_locale",
                "titre":   p["title"],
                "objectif": f"Créer la page {p['title']} (500+ mots, FAQ intégrée, JSON-LD)",
                "effort":  "3-4h",
                "impact":  "high",
            })

    # Articles blog du mois
    for b in blog_topics:
        if b["month"] == month:
            items.append({
                "semaine": 2,
                "type":    "blog",
                "titre":   b["title"],
                "objectif": f"Publier l'article « {b['title']} » (800+ mots, mots-clés locaux)",
                "effort":  "2-3h",
                "impact":  "medium",
            })

    # FAQ du mois (1 par semaine en mois 1, puis 1 tous les 2 mois)
    if month == 1:
        for i, faq in enumerate(faq_topics[:3], start=1):
            items.append({
                "semaine": i + 1,
                "type":    "faq",
                "titre":   faq["question"],
                "objectif": f"Ajouter Q/R dans la section FAQ : « {faq['question'][:60]}... »",
                "effort":  "30min",
                "impact":  "high" if faq["priority"] == "high" else "medium",
            })
    elif month <= 3:
        for faq in faq_topics[(month - 1) * 2:(month - 1) * 2 + 2]:
            items.append({
                "semaine": 3,
                "type":    "faq",
                "titre":   faq["question"],
                "objectif": f"Ajouter Q/R dans la FAQ",
                "effort":  "30min",
                "impact":  "medium",
            })

    # Avis Google
    items.append({
        "semaine": 4,
        "type":    "avis",
        "titre":   "Campagne avis Google",
        "objectif": "Envoyer 10-15 demandes d'avis (SMS ou email post-intervention)",
        "effort":  "30min",
        "impact":  "high",
    })

    if not items:
        items.append({
            "semaine": 1,
            "type":    "maintenance",
            "titre":   "Mise à jour contenu",
            "objectif": f"Mettre à jour les pages existantes {bt} à {city} (dates, tarifs, horaires)",
            "effort":  "1h",
            "impact":  "medium",
        })

    return sorted(items, key=lambda x: x["semaine"])


def _calendar_12(
    bt: str,
    city: str,
    local_pages: list[dict],
    blog_topics: list[dict],
    maturity: str,
) -> list[dict]:
    months = [
        "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
    ]
    today = date.today()
    cal = []

    for i, name in enumerate(months, start=1):
        pages  = [p["title"] for p in local_pages if p["month"] == i]
        blogs  = [b["title"] for b in blog_topics if b["month"] == i]
        status = "actif" if i <= 3 else ("planifié" if i <= 6 else "anticipé")

        cal.append({
            "month_num":  i,
            "month_name": name,
            "status":     status,
            "pages":      pages[:2],
            "blog":       blogs[0] if blogs else None,
            "avis":       5 if maturity == "low" else 8,
            "focus":      _month_focus(i, maturity),
        })

    return cal


def _month_focus(month: int, maturity: str) -> str:
    focuses = {
        1: "Fondations — pages principales + FAQ de base",
        2: "Expansion — premières pages locales + premier article",
        3: "Autorité — avis Google + annuaires",
        4: "Consolidation — mise à jour pages + nouveau contenu",
        5: "Profondeur — pages communes + FAQ enrichie",
        6: "Bilan mi-parcours — audit IA + ajustements stratégiques",
        7: "Accélération — contenu estival / saisonnier",
        8: "Notoriété — avis + mentions partenaires",
        9: "Rentrée — nouveau blog + pages mises à jour",
        10: "Harvest — récolte des positions acquises",
        11: "Pré-bilan — audit + corrections avant fin d'année",
        12: "Bilan annuel — rapport + plan N+1",
    }
    return focuses.get(month, "Maintenance et production régulière")


def _content_signals(prevalence: dict, maturity: str, nb_pages: int, nb_faq: int) -> list[str]:
    signals = []
    faq_pct = prevalence.get("faq", {}).get("pct", 0)
    blog_pct = prevalence.get("blog", {}).get("pct", 0)

    if faq_pct < 50:
        signals.append(f"Opportunité FAQ : seulement {faq_pct}% des concurrents en ont une — premier avantage à saisir")
    if blog_pct < 30:
        signals.append(f"Opportunité blog : seulement {blog_pct}% des concurrents publient — 1 article/mois suffit pour dominer")
    if maturity == "low":
        signals.append(f"Marché peu structuré : {nb_pages} pages locales à créer sans résistance directe")
    signals.append(f"Plan couvre {nb_faq} questions FAQ sur 12 mois — base solide pour toutes les requêtes clients IA")

    return signals
