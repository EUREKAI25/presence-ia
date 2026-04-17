"""
Plan d'action structuré — adapté au score de visibilité.
Format JSON exploitable directement par le livrable.
"""

_PLANS = {
    "absent": [
        {
            "priority": "high",
            "action": "Créer ou compléter la fiche Google Business Profile",
            "impact": "Signal n°1 lu par ChatGPT et Gemini pour recommander un prestataire local",
            "difficulty": "easy",
        },
        {
            "priority": "high",
            "action": "Créer une page service dédiée '{business_type} à {city}' sur votre site",
            "impact": "Associe explicitement votre nom à votre métier et votre ville",
            "difficulty": "medium",
        },
        {
            "priority": "high",
            "action": "Uniformiser votre nom d'entreprise partout (site, Google, réseaux, annuaires)",
            "impact": "La cohérence NAP (Nom, Adresse, Téléphone) est un critère fondamental de confiance",
            "difficulty": "easy",
        },
        {
            "priority": "high",
            "action": "Vous inscrire sur Pages Jaunes, Yelp et 2 annuaires sectoriels",
            "impact": "Chaque mention externe est une nouvelle source de citation pour les IA",
            "difficulty": "easy",
        },
        {
            "priority": "high",
            "action": "Collecter 10 avis Google récents (SMS ou email post-chantier)",
            "impact": "Volume et fraîcheur des avis sont les signaux les plus forts pour les IA locales",
            "difficulty": "easy",
        },
        {
            "priority": "medium",
            "action": "Ajouter une FAQ de 8 questions sur votre page de service",
            "impact": "Les IA répondent aux requêtes en s'appuyant directement sur les FAQ de qualité",
            "difficulty": "medium",
        },
        {
            "priority": "medium",
            "action": "Installer le balisage JSON-LD LocalBusiness sur votre site",
            "impact": "Données machine-readable lues nativement par tous les assistants IA",
            "difficulty": "medium",
        },
        {
            "priority": "low",
            "action": "Rédiger un article de blog '{business_type} à {city} — guide 2026'",
            "impact": "Contenu long format indexé et lu par les IA — renforce l'autorité locale",
            "difficulty": "hard",
        },
    ],
    "très_faible": [
        {
            "priority": "high",
            "action": "Enrichir votre fiche Google Business Profile (photos, description, catégories)",
            "impact": "Une fiche complète multiplie les recommandations ChatGPT/Gemini",
            "difficulty": "easy",
        },
        {
            "priority": "high",
            "action": "Créer ou réécrire la page '{business_type} à {city}' avec 500+ mots",
            "impact": "Contenu dense et localisé = signal fort pour toutes les IA",
            "difficulty": "medium",
        },
        {
            "priority": "high",
            "action": "Lancer une collecte d'avis Google (objectif : 15 avis en 30 jours)",
            "impact": "Les avis récents sont le levier le plus rapide pour progresser",
            "difficulty": "easy",
        },
        {
            "priority": "high",
            "action": "Ajouter une FAQ de 10 questions sur votre page principale",
            "impact": "Les FAQ bien structurées alimentent directement les réponses des assistants IA",
            "difficulty": "medium",
        },
        {
            "priority": "medium",
            "action": "S'inscrire sur 3 annuaires avec les mêmes informations exactes",
            "impact": "Multiplication des sources = meilleure confiance accordée par les IA",
            "difficulty": "easy",
        },
        {
            "priority": "medium",
            "action": "Ajouter les balises title et meta description avec '{business_type} à {city}'",
            "impact": "Signaux SEO lus par les IA pour associer votre activité à votre zone",
            "difficulty": "easy",
        },
        {
            "priority": "medium",
            "action": "Installer le balisage JSON-LD LocalBusiness",
            "impact": "Données structurées lues nativement par tous les modèles IA",
            "difficulty": "medium",
        },
        {
            "priority": "low",
            "action": "Demander des recommandations à des partenaires locaux",
            "impact": "Les liens entrants de sites locaux renforcent votre ancrage géographique",
            "difficulty": "hard",
        },
    ],
    "faible": [
        {
            "priority": "high",
            "action": "Créer ou réécrire la FAQ avec 10 questions locales spécifiques à {city}",
            "impact": "Signal direct pour les IA qui reformulent des réponses depuis des FAQ de qualité",
            "difficulty": "medium",
        },
        {
            "priority": "high",
            "action": "Installer le balisage JSON-LD LocalBusiness complet",
            "impact": "Données structurées manquantes — gain rapide et durable",
            "difficulty": "medium",
        },
        {
            "priority": "high",
            "action": "Porter votre note Google à 4,5+ avec 20+ avis récents",
            "impact": "Note et volume d'avis = critères de sélection des IA pour recommander",
            "difficulty": "medium",
        },
        {
            "priority": "medium",
            "action": "Créer une page par service principal avec la ville dans le titre",
            "impact": "Spécialisation du contenu par service = meilleure citation sur les requêtes ciblées",
            "difficulty": "medium",
        },
        {
            "priority": "medium",
            "action": "Mentionner les communes voisines dans vos textes de service",
            "impact": "Élargit la zone de recommandation des IA à votre périmètre réel",
            "difficulty": "easy",
        },
        {
            "priority": "medium",
            "action": "Rédiger un article de blog récent sur votre activité à {city}",
            "impact": "Le contenu frais est un signal de confiance pour les IA",
            "difficulty": "hard",
        },
        {
            "priority": "low",
            "action": "Viser des annuaires premium (Trustpilot, annuaires sectoriels premium)",
            "impact": "Citations dans des sources à forte autorité — signal fort pour Claude",
            "difficulty": "hard",
        },
    ],
    "moyen": [
        {
            "priority": "high",
            "action": "Élargir la couverture géographique dans vos textes (communes voisines de {city})",
            "impact": "Chaque commune mentionnée = nouvelle zone de recommandation potentielle",
            "difficulty": "easy",
        },
        {
            "priority": "high",
            "action": "Mettre à jour votre contenu de service (refonte ou enrichissement)",
            "impact": "La fraîcheur du contenu est un critère de confiance croissant pour les IA",
            "difficulty": "medium",
        },
        {
            "priority": "medium",
            "action": "Viser 30+ avis Google avec relance mensuelle des clients",
            "impact": "Volume critique pour déclencher des recommandations systématiques",
            "difficulty": "medium",
        },
        {
            "priority": "medium",
            "action": "Publier 1 article de blog par trimestre ciblé {business_type} {city}",
            "impact": "Contenu frais et localisé — signal régulier envoyé aux IA",
            "difficulty": "hard",
        },
        {
            "priority": "medium",
            "action": "Obtenir des citations dans la presse locale ou des blogs sectoriels",
            "impact": "Backlinks de qualité = signal d'autorité fort pour Claude et Gemini",
            "difficulty": "hard",
        },
        {
            "priority": "low",
            "action": "Compléter le balisage structuré avec FAQPage et Service en JSON-LD",
            "impact": "Données enrichies = meilleure compréhension de votre activité par les IA",
            "difficulty": "medium",
        },
    ],
    "bon": [
        {
            "priority": "high",
            "action": "Maintenir 5+ nouveaux avis Google par mois",
            "impact": "La fraîcheur des avis préserve votre position face à la concurrence montante",
            "difficulty": "medium",
        },
        {
            "priority": "medium",
            "action": "Publier du contenu récent (article, actualité) tous les 2 mois",
            "impact": "Signal de présence active — différenciateur sur le long terme",
            "difficulty": "medium",
        },
        {
            "priority": "medium",
            "action": "Surveiller les concurrents cités par les IA et analyser leur contenu",
            "impact": "Identifier les gaps avant qu'ils vous dépassent",
            "difficulty": "easy",
        },
        {
            "priority": "low",
            "action": "Explorer les plateformes premium (Houzz, Trustpilot, sectoriels)",
            "impact": "Diversification des sources = résilience de votre positionnement IA",
            "difficulty": "hard",
        },
    ],
    "excellent": [
        {
            "priority": "medium",
            "action": "Maintien actif : 3+ avis Google par mois + contenu mis à jour trimestriellement",
            "impact": "Protège votre avantage concurrentiel sur le long terme",
            "difficulty": "easy",
        },
        {
            "priority": "low",
            "action": "Veille mensuelle sur les concurrents cités par les IA",
            "impact": "Anticiper les challengers émergents sur votre zone",
            "difficulty": "easy",
        },
    ],
}


def generate_action_plan(
    score_level: str,
    business_type: str,
    city: str,
) -> list[dict]:
    """
    Génère un plan d'action structuré adapté au niveau de score.

    Returns:
        [{priority, action, impact, difficulty}, ...]
    """
    plan = _PLANS.get(score_level, _PLANS["faible"])
    return [
        {
            "priority":   item["priority"],
            "action":     item["action"].replace("{business_type}", business_type).replace("{city}", city),
            "impact":     item["impact"],
            "difficulty": item["difficulty"],
        }
        for item in plan
    ]
