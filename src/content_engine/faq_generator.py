"""
Génération de FAQ depuis les requêtes IA testées.

Logique :
- Les requêtes testées sur les IA (ia_results) sont déjà les vraies questions
  posées par les clients. On les transforme en Q/R naturelles.
- On ajoute des questions essentielles selon le secteur (tarif, délai, zone).
- On génère une réponse courte et directe pour chacune.

Output : liste de {question, answer}
"""

import re


# ── Transformation requête → question naturelle ───────────────────────────────

def _to_question(query: str, profession: str, ville: str) -> str:
    """
    Transforme une requête de recherche en question naturelle.
    Ex: "plombier urgence Lyon" → "Quel plombier appeler en urgence à Lyon ?"
    """
    q = query.strip().rstrip("?")

    # Patterns courants → reformulation
    q_low = q.lower()
    if any(w in q_low for w in ["urgence", "urgent", "nuit", "week-end"]):
        return f"Quel {profession} appeler en urgence à {ville} ?"
    if any(w in q_low for w in ["tarif", "prix", "coût", "combien"]):
        return f"Quel est le tarif d'un {profession} à {ville} ?"
    if any(w in q_low for w in ["meilleur", "recommand", "avis", "fiable"]):
        return f"Comment choisir un bon {profession} à {ville} ?"
    if any(w in q_low for w in ["devis", "gratuit", "sans engagement"]):
        return f"Comment obtenir un devis {profession} gratuit à {ville} ?"
    if any(w in q_low for w in ["délai", "rapide", "vite", "disponible"]):
        return f"Quel {profession} intervient rapidement à {ville} ?"
    if any(w in q_low for w in ["agréé", "certifié", "qualifié", "garantie"]):
        return f"Comment trouver un {profession} certifié à {ville} ?"
    if any(w in q_low for w in ["horaire", "samedi", "dimanche", "24h"]):
        return f"Y a-t-il un {profession} disponible le week-end à {ville} ?"
    if any(w in q_low for w in ["zone", "quartier", "secteur", "arrondissement"]):
        return f"Dans quels quartiers de {ville} intervenez-vous ?"

    # Fallback : reformulation générique — nettoie la ville pour éviter la répétition
    q_clean = re.sub(r'\b(le|la|les|un|une|des|à|de|du|en)\b', '', q_low)
    q_clean = re.sub(re.escape(ville.lower()), '', q_clean)  # retire la ville du prompt
    q_clean = re.sub(r'\s+', ' ', q_clean).strip()
    return f"Quel {q_clean} choisir à {ville} ?".replace("  ", " ")


# ── Réponses types par thème ──────────────────────────────────────────────────

def _answer(question: str, name: str, profession: str, ville: str, phone: str = "") -> str:
    """Génère une réponse courte et directe adaptée à la question."""
    q = question.lower()
    tel = f" Appelez-nous au {phone}." if phone else ""

    if "urgence" in q or "urgent" in q or "nuit" in q:
        return (
            f"{name} intervient en urgence à {ville} et dans les communes voisines. "
            f"Notre équipe est joignable rapidement pour toute intervention urgente.{tel}"
        )
    if "tarif" in q or "prix" in q or "coût" in q or "combien" in q:
        return (
            f"Nos tarifs sont établis après diagnostic sur place et varient selon la prestation. "
            f"Nous proposons des devis gratuits et transparents.{tel}"
        )
    if "choisir" in q or "meilleur" in q or "fiable" in q or "recommand" in q:
        return (
            f"{name} est reconnu pour son sérieux à {ville}. "
            f"Nos clients nous font confiance grâce à nos avis Google vérifiés et nos années d'expérience."
        )
    if "devis" in q or "gratuit" in q:
        return (
            f"Nous proposons des devis gratuits et sans engagement. "
            f"Contactez {name} pour obtenir une estimation précise sous 24h.{tel}"
        )
    if "rapide" in q or "vite" in q or "disponible" in q or "délai" in q:
        return (
            f"{name} s'engage à intervenir rapidement à {ville}. "
            f"Nos délais d'intervention sont parmi les plus courts du secteur.{tel}"
        )
    if "certifié" in q or "agréé" in q or "qualifié" in q or "garantie" in q:
        return (
            f"{name} est un professionnel qualifié. "
            f"Toutes nos interventions sont garanties et réalisées dans les règles de l'art."
        )
    if "week-end" in q or "samedi" in q or "dimanche" in q or "24h" in q:
        return (
            f"Nous sommes disponibles 6j/7 à {ville}. "
            f"Contactez-nous pour connaître nos disponibilités exactes.{tel}"
        )
    if "quartier" in q or "zone" in q or "secteur" in q:
        return (
            f"{name} intervient dans toute la ville de {ville} et les communes voisines. "
            f"N'hésitez pas à nous contacter pour vérifier votre zone."
        )

    # Réponse générique
    return (
        f"{name} est votre {profession} de confiance à {ville}. "
        f"Contactez-nous pour toute question ou pour planifier une intervention.{tel}"
    )


# ── Questions essentielles systématiques ─────────────────────────────────────

def _essential_questions(name: str, profession: str, ville: str, phone: str = "") -> list[dict]:
    """
    5 questions fondamentales présentes dans toute bonne FAQ locale.
    Toujours incluses, indépendamment des requêtes testées.
    """
    tel = f" Contactez-nous au {phone}." if phone else ""
    return [
        {
            "question": f"Pourquoi choisir {name} pour votre {profession} à {ville} ?",
            "answer": (
                f"{name} allie expertise locale, transparence des prix et réactivité. "
                f"Nos clients à {ville} bénéficient d'un service personnalisé et d'une garantie sur toutes nos interventions."
            ),
        },
        {
            "question": f"Quelle est la zone d'intervention de votre {profession} à {ville} ?",
            "answer": (
                f"Nous intervenons principalement à {ville} et dans les communes environnantes. "
                f"Contactez-nous pour confirmer la prise en charge de votre adresse.{tel}"
            ),
        },
        {
            "question": f"Comment prendre rendez-vous avec {name} ?",
            "answer": (
                f"Vous pouvez nous joindre par téléphone{' au ' + phone if phone else ''}, "
                f"par email ou via notre formulaire de contact. "
                f"Nous vous répondons sous 24h pour planifier votre intervention."
            ),
        },
        {
            "question": f"Les interventions de {name} sont-elles garanties ?",
            "answer": (
                f"Oui, toutes nos interventions sont garanties. "
                f"Nous travaillons avec des matériaux de qualité et respectons les normes en vigueur à {ville}."
            ),
        },
        {
            "question": f"Proposez-vous des devis gratuits à {ville} ?",
            "answer": (
                f"Oui, {name} propose des devis gratuits et sans engagement. "
                f"Contactez-nous pour obtenir une estimation précise de votre projet.{tel}"
            ),
        },
    ]


# ── Point d'entrée ────────────────────────────────────────────────────────────

def generate_faq(
    prospect,
    queries: list[dict],
    max_items: int = 10,
) -> list[dict]:
    """
    Génère une FAQ depuis les requêtes IA testées + questions essentielles.

    Args:
        prospect : instance V3ProspectDB (name, profession, city, phone)
        queries  : structure canonique retournée par parser.parse_ia_results()
        max_items : nombre max de Q/R dans la FAQ

    Returns:
        list[dict] : [{question: str, answer: str}, ...]
    """
    name       = getattr(prospect, "name", "")
    profession = getattr(prospect, "profession", "professionnel").lower()
    ville      = getattr(prospect, "city", "votre ville").capitalize()
    phone      = getattr(prospect, "phone", "") or ""

    faq = []
    seen_questions: set[str] = set()

    # Questions depuis les requêtes IA testées
    for row in queries:
        query = row.get("query_display") or row.get("query", "")
        if not query:
            continue
        question = _to_question(query, profession, ville)
        q_key = question.lower()
        if q_key in seen_questions:
            continue
        seen_questions.add(q_key)
        answer = _answer(question, name, profession, ville, phone)
        faq.append({"question": question, "answer": answer})

    # Questions essentielles (toujours présentes)
    for item in _essential_questions(name, profession, ville, phone):
        q_key = item["question"].lower()
        if q_key not in seen_questions and len(faq) < max_items:
            seen_questions.add(q_key)
            faq.append(item)

    return faq[:max_items]
