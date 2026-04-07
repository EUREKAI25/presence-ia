"""
Calculs de score, extraction de concurrents et génération de checklist.

Toutes les fonctions prennent la structure canonique retournée par parser.py.
"""

import logging
import re
import unicodedata
from collections import Counter

log = logging.getLogger(__name__)

MODELS = ["chatgpt", "gemini", "claude"]

# ── Score ─────────────────────────────────────────────────────────────────────

def compute_score(queries: list[dict]) -> dict:
    """
    Calcule le score de visibilité IA depuis la liste canonique de requêtes.

    Règle : 1 point par citation (modèle × requête).
    Score = citations_obtenues / citations_possibles × 10, arrondi à 1 décimale.

    Returns:
        {
          "score":            float,  # 0.0 → 10.0
          "total_queries":    int,
          "total_models":     int,    # nb modèles testés
          "total_possible":   int,    # total possible (requêtes × modèles testés)
          "total_citations":  int,    # citations réelles
        }
    """
    total_possible  = 0
    total_citations = 0
    models_used     = set()

    for row in queries:
        for m in MODELS:
            val = row.get(m)
            if val is not None:  # None = modèle non testé → ne compte pas
                total_possible += 1
                models_used.add(m)
                if val:
                    total_citations += 1

    if total_possible == 0:
        return {
            "score": 0.0,
            "total_queries":   len(queries),
            "total_models":    0,
            "total_possible":  0,
            "total_citations": 0,
        }

    score = round(total_citations / total_possible * 10, 1)

    return {
        "score":            score,
        "total_queries":    len(queries),
        "total_models":     len(models_used),
        "total_possible":   total_possible,
        "total_citations":  total_citations,
    }


# ── Concurrents ───────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b(sarl|sas|eurl|sa|sasu|sci|ei|auto entrepreneur)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_competitors(queries: list[dict], own_name: str, top_n: int = 3) -> list[dict]:
    """
    Extrait les entreprises concurrentes citées dans les réponses IA.

    Heuristiques (V1) :
    1. Liens markdown : [Nom Entreprise](http...)
    2. Éléments de liste : - **Nom** ou * Nom ou 1. Nom
    Exclut le nom de l'entreprise auditée.
    Dédoublonne les noms très proches.

    Args:
        queries   : structure canonique avec champ "responses"
        own_name  : nom de l'entreprise (à exclure)
        top_n     : nombre max de concurrents à retourner

    Returns:
        [{"name": str, "count": int}, ...]
    """
    counts: Counter = Counter()
    own_norm = _norm(own_name)

    for row in queries:
        responses = row.get("responses", {})
        for resp in responses.values():
            if not resp:
                continue

            # Liens markdown : [Nom entreprise](http...)
            for m in re.finditer(r'\[([^\]]{3,60})\]\(http', resp):
                raw = m.group(1).strip()
                if raw and not raw.startswith("http"):
                    n = _norm(raw)
                    if n and n != own_norm and len(n) > 3:
                        counts[raw] += 1

            # Éléments de liste : - **Nom** / * Nom / 1. Nom
            for m in re.finditer(
                r'^[-*\d\.]+\s+\*{0,2}([A-ZÀÂÉÈÊËÏÎÔÙÛÜ][^:\n*\[\]]{2,60})\*{0,2}',
                resp, re.MULTILINE
            ):
                raw = m.group(1).strip().rstrip(".,:")
                n = _norm(raw)
                if n and n != own_norm and len(n) > 3 and len(raw) > 3:
                    counts[raw] += 1

    # Dédoublonnage par normalisation
    seen_norms: set[str] = set()
    result = []
    for name, count in counts.most_common(top_n * 3):
        n = _norm(name)
        if n not in seen_norms:
            seen_norms.add(n)
            result.append({"name": name, "count": count})
        if len(result) >= top_n:
            break

    return result


# ── Checklist ─────────────────────────────────────────────────────────────────

_CHECKLIST: dict[str, list[tuple[str, str]]] = {
    "fondations": [
        (
            "Fiche Google Business Profile complète",
            "Description métier, catégories, horaires, photos. "
            "Les IA lisent directement ces données pour recommander des professionnels locaux.",
        ),
        (
            "15 avis Google récents (note ≥ 4,5)",
            "Volume et fraîcheur des avis sont les signaux les plus forts pour ChatGPT et Gemini. "
            "Chaque avis compte — surtout ceux des 90 derniers jours.",
        ),
        (
            "Nom d'entreprise identique partout",
            "Le même nom exact sur votre site, Google, réseaux, annuaires. "
            "La cohérence est le signal de confiance n°1 des IA.",
        ),
        (
            "Page service locale",
            "Une page dédiée '{profession} à {ville}' avec la ville dans le titre H1 et le contenu.",
        ),
        (
            "Numéro de téléphone et adresse sur chaque page",
            "Données NAP (Nom, Adresse, Téléphone) consistantes partout — "
            "critère de base pour que les IA locales vous référencent.",
        ),
    ],
    "contenu": [
        (
            "Page service locale enrichie",
            "Descriptions détaillées, zone d'intervention, tarifs indicatifs "
            "et délais d'intervention sur votre page dédiée.",
        ),
        (
            "FAQ 8 questions",
            "Répondre aux questions posées aux IA : coût, délai, garanties, zone. "
            "Ces réponses alimentent directement les modèles IA.",
        ),
        (
            "3 annuaires locaux",
            "Pages Jaunes, Yelp, et un annuaire de votre secteur. "
            "Chaque mention externe renforce votre présence IA.",
        ),
        (
            "20 avis Google",
            "Campagne de collecte d'avis auprès des clients récents (SMS ou email). "
            "Le seuil de 20 avis est un signal fort pour Claude.",
        ),
        (
            "Balises meta locales",
            "Title et meta description incluant '{profession} à {ville}' sur chaque page service.",
        ),
    ],
    "optimisation": [
        (
            "Références géographiques élargies",
            "Mentionner {ville} et les communes voisines dans vos textes. "
            "Les IA associent votre activité à une zone précise.",
        ),
        (
            "Article blog ciblé",
            "Un article '{profession} à {ville} — guide 2026' "
            "directement indexé et lu par les IA.",
        ),
        (
            "Annuaires premium",
            "Trustpilot, Houzz Premium, annuaires sectoriels. "
            "Signal fort pour Claude et Gemini.",
        ),
        (
            "Schéma JSON-LD LocalBusiness",
            "Balisage structuré sur la page d'accueil et les pages services. "
            "Données machine-readable lues nativement par les IA.",
        ),
        (
            "Re-test dans 6 semaines",
            "Les changements mettent 6 à 10 semaines à être intégrés. "
            "Valider les progrès avant d'ajuster la stratégie.",
        ),
    ],
}


def build_checklist(score: float, profession: str = "", ville: str = "") -> dict:
    """
    Génère une checklist d'actions recommandées selon le score.

    Args:
        score      : score IA 0.0 → 10.0
        profession : pour personnaliser les textes
        ville      : pour personnaliser les textes

    Returns:
        {
          "level":  str,        # "fondations" | "contenu" | "optimisation"
          "title":  str,        # titre de la section
          "items":  [{"title": str, "desc": str}, ...]
        }
    """
    if score < 3:
        level = "fondations"
        title = "Plan d'action — Fondations"
    elif score < 6:
        level = "contenu"
        title = "Plan d'action — Contenu"
    else:
        level = "optimisation"
        title = "Plan d'action — Optimisation"

    items = []
    for t, d in _CHECKLIST[level]:
        d = d.replace("{profession}", profession or "votre métier")
        d = d.replace("{ville}", ville or "votre ville")
        t = t.replace("{profession}", profession or "votre métier")
        t = t.replace("{ville}", ville or "votre ville")
        items.append({"title": t, "desc": d})

    return {"level": level, "title": title, "items": items}
