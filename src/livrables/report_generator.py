"""
Génération automatique de rapports HTML clients.

  generate_audit_report(prospect, db)   → HTML audit initial (audit_template.html) + snapshot
  generate_monthly_report(prospect, db) → HTML rapport mensuel (report_template.html) + snapshot
  run_monthly(db)                       → génère rapports pour tous les clients actifs

Structure ia_results attendue (JSON stocké en DB) :
  [
    {"model": "ChatGPT", "prompt": "...", "response": "...", "tested_at": "..."},
    {"model": "Gemini",  "prompt": "...", "response": "...", "tested_at": "..."},
    {"model": "Claude",  "prompt": "...", "response": "...", "tested_at": "..."},
    ...  # 3 prompts × 3 modèles = 9 entrées max
  ]
"""

import json
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "deliverables"
AUDIT_TEMPLATE = TEMPLATE_DIR / "audit" / "audit_template.html"
REPORT_TEMPLATE = TEMPLATE_DIR / "reports" / "report_template.html"

MODELS = ["ChatGPT", "Gemini", "Claude"]

# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_ia_results(prospect) -> list:
    raw = getattr(prospect, "ia_results", None)
    if not raw:
        return []
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return []


def _norm(s: str) -> str:
    """Normalise une chaîne pour comparaison souple."""
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    # Retire suffixes légaux fréquents
    s = re.sub(r"\b(sarl|sas|eurl|sa|sasu|sci|ei|auto entrepreneur)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _is_cited(name: str, response: str) -> bool:
    """Vérifie si le nom de l'entreprise apparaît dans la réponse IA."""
    if not name or not response:
        return False
    name_norm = _norm(name)
    resp_norm = _norm(response)
    # Cherche au moins 2 mots significatifs du nom dans la réponse
    words = [w for w in name_norm.split() if len(w) >= 3]
    if not words:
        return False
    matches = sum(1 for w in words if w in resp_norm)
    # Majorité stricte : plus de la moitié des mots doivent matcher
    # (évite les faux positifs sur mots génériques comme "plomberie")
    return matches > len(words) // 2


def _extract_competitors(ia_results: list, own_name: str) -> list[tuple[str, int]]:
    """
    Extrait les noms d'entreprises cités dans les réponses IA (hors nom propre).
    Retourne [(nom, nb_citations), ...] trié par fréquence décroissante.
    """
    counts: Counter = Counter()
    own_norm = _norm(own_name)

    for entry in ia_results:
        response = entry.get("response", "")
        # Liens markdown : [Nom Entreprise](http...)
        for m in re.finditer(r'\[([^\]]{3,60})\]\(http', response):
            raw = m.group(1).strip()
            if raw and not raw.startswith("http"):
                norm = _norm(raw)
                if norm and norm != own_norm and len(norm) > 3:
                    counts[raw] += 1
        # Éléments de liste : - **Nom** ou * Nom ou 1. Nom
        for m in re.finditer(
            r'^[-*\d\.]+\s+\*{0,2}([A-ZÀÂÉÈÊËÏÎÔÙÛÜ][^:\n*\[\]]{2,60})\*{0,2}',
            response, re.MULTILINE
        ):
            raw = m.group(1).strip().rstrip(".,:")
            norm = _norm(raw)
            if norm and norm != own_norm and len(norm) > 3 and len(raw) > 3:
                counts[raw] += 1

    # Dédoublonne les noms très proches (ex: "Dupont Plomberie" vs "Dupont Plomberie SARL")
    seen_norms = set()
    result = []
    for name, count in counts.most_common(10):
        n = _norm(name)
        if n not in seen_norms:
            seen_norms.add(n)
            result.append((name, count))
    return result[:5]


def _build_query_matrix(ia_results: list, prospect_name: str) -> list[dict]:
    """
    Organise les résultats par prompt.
    Retourne une liste de dicts :
      {
        "query": str,         # texte du prompt
        "ChatGPT": bool,      # cité ?
        "Gemini": bool,
        "Claude": bool,
        "tested_at": str,
      }
    """
    # Groupe par prompt
    by_prompt: dict[str, dict] = {}
    for entry in ia_results:
        prompt = entry.get("prompt", "")
        model  = entry.get("model", "")
        if prompt not in by_prompt:
            by_prompt[prompt] = {"query": prompt, "tested_at": entry.get("tested_at", "")}
        if model in MODELS:
            by_prompt[prompt][model] = _is_cited(prospect_name, entry.get("response", ""))

    rows = list(by_prompt.values())
    # Tronque le prompt pour affichage (retire le formatage "{profession} à {city}")
    for row in rows:
        q = row["query"]
        # Nettoie les artefacts de formatage restants
        q = re.sub(r'\{[^}]+\}', '', q).strip()
        row["query_display"] = q if q else row["query"]
        # Valeur par défaut si modèle absent
        for m in MODELS:
            row.setdefault(m, None)  # None = modèle non testé

    return rows[:5]  # max 5 requêtes dans le template


def _score(query_matrix: list[dict]) -> tuple[int, int, int]:
    """
    Calcule le score de visibilité.
    Retourne (score_10, nb_mentions, nb_total_tests).
    """
    total = 0
    cited = 0
    for row in query_matrix:
        for m in MODELS:
            if row.get(m) is not None:
                total += 1
                if row[m]:
                    cited += 1
    if total == 0:
        return 0, 0, 0
    score = round(cited / total * 10)
    return score, cited, total


def _today_fr() -> str:
    today = date.today()
    months = ["", "janvier", "février", "mars", "avril", "mai", "juin",
              "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{today.day} {months[today.month]} {today.year}"


def _result_label(cited: Optional[bool]) -> tuple[str, str]:
    """Retourne (classe_css, icône) pour une cellule — texte dans la légende uniquement."""
    if cited is True:
        return "cited", "✓"
    if cited is False:
        return "not-cited", "✗"
    return "not-cited", "—"


def _delta_icon(delta: int) -> str:
    if delta > 0:
        return "↑"
    if delta < 0:
        return "↓"
    return "→"


def _build_actions_html(actions_done: list[dict]) -> str:
    """Génère le HTML des items de timeline — aucun item vide."""
    TAG_CSS = {"done": "tag-done", "progress": "tag-progress", "todo": "tag-todo"}
    TAG_LABEL = {"done": "Fait", "progress": "En cours", "todo": "À faire"}
    ICON_DEFAULT = {"done": "✅", "progress": "🔄", "todo": "⭕"}

    rows = []
    for a in (actions_done or []):
        title = a.get("title", "").strip()
        if not title:
            continue
        status = a.get("status", "done")
        icon   = a.get("icon", ICON_DEFAULT.get(status, "✅"))
        date   = a.get("date", "")
        desc   = a.get("desc", "")
        css    = TAG_CSS.get(status, "tag-done")
        label  = TAG_LABEL.get(status, "Fait")

        rows.append(
            f'<li>'
            f'<div class="tl-date">{_esc(date)}</div>'
            f'<div class="tl-icon">{icon}</div>'
            f'<div class="tl-content">'
            f'<div class="tl-title">{_esc(title)} <span class="tag {css}">{label}</span></div>'
            f'<div class="tl-desc">{_esc(desc)}</div>'
            f'</div></li>'
        )
    return "\n".join(rows)


def _build_steps_html(next_actions: list[dict]) -> str:
    """Génère le HTML des prochaines étapes — aucun item vide."""
    rows = []
    for i, a in enumerate(next_actions or [], start=1):
        title = a.get("title", "").strip()
        if not title:
            continue
        desc = a.get("desc", "")
        rows.append(
            f'<li>'
            f'<div class="step-num">{i}</div>'
            f'<div>'
            f'<div class="step-title">{_esc(title)}</div>'
            f'<div class="step-desc">{_esc(desc)}</div>'
            f'</div></li>'
        )
    return "\n".join(rows)


# ── Génération audit ──────────────────────────────────────────────────────────

def generate_audit_report(prospect, next_step: str = "") -> str:
    """
    Génère le rapport d'audit HTML pour un prospect V3.

    Args:
        prospect   : instance V3ProspectDB
        next_step  : texte de la prochaine étape (adapté à l'offre vendue)

    Returns:
        str : HTML complet prêt à envoyer
    """
    ia_results = _load_ia_results(prospect)
    matrix     = _build_query_matrix(ia_results, prospect.name)
    score, nb_mentions, nb_total = _score(matrix)

    competitors = _load_competitors(prospect)
    if not competitors and ia_results:
        competitors = _extract_competitors(ia_results, prospect.name)

    if not next_step:
        next_step = (
            "Nos équipes démarrent l'implémentation cette semaine. "
            "Vous recevrez un rapport de suivi à M+1."
        )

    html = AUDIT_TEMPLATE.read_text(encoding="utf-8")

    # ── Variables globales ────────────────────────────────────────────────────
    html = html.replace("{{NOM_ENTREPRISE}}", _esc(prospect.name))
    html = html.replace("{{PROFESSION}}",     _esc(prospect.profession.capitalize()))
    html = html.replace("{{VILLE}}",          _esc(prospect.city.capitalize()))
    html = html.replace("{{DATE_AUDIT}}",     _today_fr())
    html = html.replace("{{SCORE}}",          str(score))
    html = html.replace("{{NB_MENTIONS}}",    str(nb_mentions))
    html = html.replace("{{NB_TOTAL}}",       str(nb_total))
    html = html.replace("{{PROCHAINE_ETAPE}}", _esc(next_step))
    html = html.replace("{{NOM_CMS}}", _esc(getattr(prospect, "cms", None) or "votre CMS"))

    # ── Tableau des requêtes (5 lignes max) ───────────────────────────────────
    for i in range(1, 6):
        if i <= len(matrix):
            row = matrix[i - 1]
            html = html.replace(f"{{{{REQUETE_{i}}}}}", _esc(row["query_display"]))
            for model_key in [("ChatGPT", "GPT"), ("Gemini", "GEMINI"), ("Claude", "CLAUDE")]:
                model_name, tpl_key = model_key
                css, label = _result_label(row.get(model_name))
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", css)
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", label)
        else:
            # Ligne absente — efface sans laisser de contenu
            html = html.replace(f"{{{{REQUETE_{i}}}}}", "")
            for tpl_key in ["GPT", "GEMINI", "CLAUDE"]:
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", "not-cited")
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", "")

    # ── Concurrents (3 max) ───────────────────────────────────────────────────
    for j in range(1, 4):
        if j <= len(competitors):
            name, count = competitors[j - 1]
            label = f"{_esc(name)} — cité {count} fois"
        else:
            label = ""
        html = html.replace(f"{{{{CONCURRENT_{j}}}}}", label)

    return html


# ── Génération rapport mensuel ────────────────────────────────────────────────

def generate_monthly_report(
    prospect,
    previous_data: dict,
    actions_done: Optional[list[dict]] = None,
    next_actions: Optional[list[dict]] = None,
    periode: str = "",
    note: str = "",
) -> str:
    """
    Génère le rapport de suivi mensuel HTML.

    Args:
        prospect       : instance V3ProspectDB (avec ia_results à jour)
        previous_data  : dict issu du rapport précédent :
                         {
                           "score": int,
                           "date": str,          # ex: "7 avril 2026"
                           "nb_mentions": int,
                           "nb_total": int,
                           "matrix": list[dict], # même format que _build_query_matrix
                         }
        actions_done   : [{date, icon, title, tag, desc}, ...]
        next_actions   : [{title, desc}, ...]
        periode        : ex: "mai 2026"
        note           : texte libre de suivi

    Returns:
        str : HTML complet
    """
    ia_results = _load_ia_results(prospect)
    matrix     = _build_query_matrix(ia_results, prospect.name)
    score, nb_mentions, nb_total = _score(matrix)

    prev_score = previous_data.get("score", 0)
    prev_date  = previous_data.get("date", "")
    prev_matrix = previous_data.get("matrix", [])

    delta_val = score - prev_score
    if delta_val > 0:
        delta_text  = f"+{delta_val} point{'s' if delta_val > 1 else ''} ↑"
        delta_class = "positive"
    elif delta_val < 0:
        delta_text  = f"{delta_val} point{'s' if abs(delta_val) > 1 else ''} ↓"
        delta_class = "negative"
    else:
        delta_text  = "Stable →"
        delta_class = "neutral"

    if not periode:
        today = date.today()
        months = ["", "janvier", "février", "mars", "avril", "mai", "juin",
                  "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        periode = f"{months[today.month]} {today.year}"

    html = REPORT_TEMPLATE.read_text(encoding="utf-8")

    # ── Variables globales ────────────────────────────────────────────────────
    html = html.replace("{{NOM_ENTREPRISE}}",  _esc(prospect.name))
    html = html.replace("{{PROFESSION}}",      _esc(prospect.profession.capitalize()))
    html = html.replace("{{VILLE}}",           _esc(prospect.city.capitalize()))
    html = html.replace("{{PERIODE}}",         _esc(periode))
    html = html.replace("{{DATE_RETEST}}",     _today_fr())
    html = html.replace("{{DATE_AUDIT_INITIAL}}", _esc(prev_date))
    html = html.replace("{{SCORE_INITIAL}}",   str(prev_score))
    html = html.replace("{{SCORE_ACTUEL}}",    str(score))
    html = html.replace("{{DELTA_CLASS}}",     delta_class)
    html = html.replace("{{DELTA_TEXTE}}",     _esc(delta_text))
    html = html.replace("{{SCORE_ICON}}",      _delta_icon(delta_val))
    html = html.replace("{{NB_CITATIONS_ACTUEL}}", str(nb_mentions))
    html = html.replace("{{NB_TOTAL}}",        str(nb_total))

    # KPIs optionnels (passés via previous_data)
    reviews   = previous_data.get("reviews_count", "—")
    annuaires = previous_data.get("annuaires_count", "—")
    html = html.replace("{{NB_NOUVEAUX_AVIS}}", str(reviews))
    html = html.replace("{{NB_ANNUAIRES}}",     str(annuaires))

    # ── Prochain re-test ─────────────────────────────────────────────────────
    next_retest   = previous_data.get("next_retest", "")
    prochain_mois = previous_data.get("prochain_mois", "")
    html = html.replace("{{DATE_PROCHAIN_RETEST}}", _esc(next_retest) if next_retest else "à définir")
    html = html.replace("{{PROCHAIN_MOIS}}",        _esc(prochain_mois) if prochain_mois else "prochain")

    # ── Tableau des requêtes avec évolution ──────────────────────────────────
    prev_by_query = {_norm(r.get("query_display", r.get("query", ""))): r
                     for r in prev_matrix}

    for i in range(1, 6):
        if i <= len(matrix):
            row = matrix[i - 1]
            html = html.replace(f"{{{{REQUETE_{i}}}}}", _esc(row["query_display"]))

            for model_name, tpl_key in [("ChatGPT", "GPT"), ("Gemini", "GEMINI"), ("Claude", "CLAUDE")]:
                css, label = _result_label(row.get(model_name))
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", css)
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", label)

            # Évolution vs rapport précédent
            prev_row  = prev_by_query.get(_norm(row["query_display"]), {})
            curr_cited = sum(1 for m in MODELS if row.get(m) is True)
            prev_cited = sum(1 for m in MODELS if prev_row.get(m) is True)
            diff = curr_cited - prev_cited
            if diff > 0:
                evol = f"↑ +{diff}"
            elif diff < 0:
                evol = f"↓ {diff}"
            else:
                evol = "→"
            html = html.replace(f"{{{{EVOL_{i}}}}}", evol)

        else:
            # Ligne absente — efface les placeholders sans laisser de ligne vide visible
            html = html.replace(f"{{{{REQUETE_{i}}}}}", "")
            for tpl_key in ["GPT", "GEMINI", "CLAUDE"]:
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", "not-cited")
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", "")
            html = html.replace(f"{{{{EVOL_{i}}}}}", "")

    # ── Actions réalisées — HTML généré dynamiquement (pas de row vide) ──────
    html = html.replace("{{ACTIONS_HTML}}", _build_actions_html(actions_done))

    # ── Prochaines étapes — idem ─────────────────────────────────────────────
    html = html.replace("{{STEPS_HTML}}", _build_steps_html(next_actions))

    # ── Note libre ───────────────────────────────────────────────────────────
    if not note:
        sign = "+" if delta_val >= 0 else ""
        note = (
            f"Les IA intègrent les nouvelles données avec 6 à 10 semaines de délai. "
            f"Les actions menées ce mois devraient se refléter dans le prochain re-test. "
            f"Score actuel : {score}/10 ({sign}{delta_val} points)."
        )
    html = html.replace("{{NOTE_LIBRE}}", _esc(note))

    return html


# ── Helpers HTML ──────────────────────────────────────────────────────────────

def _esc(s) -> str:
    """Échappe les caractères HTML basiques."""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _load_competitors(prospect) -> list[tuple[str, int]]:
    """Charge les concurrents depuis le champ competitors (JSON list[str])."""
    raw = getattr(prospect, "competitors", None)
    if not raw:
        return []
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, list):
            # Peut être list[str] ou list[dict]
            result = []
            for item in data:
                if isinstance(item, str):
                    result.append((item, 1))
                elif isinstance(item, dict):
                    name = item.get("name", item.get("nom", ""))
                    count = item.get("count", item.get("nb", 1))
                    if name:
                        result.append((name, count))
            return result[:5]
    except Exception:
        pass
    return []


# ── Export snapshot pour rapport suivant ─────────────────────────────────────

def build_snapshot(prospect, period: str = "") -> dict:
    """
    Construit le dict previous_data (sans DB) — utile pour les tests.
    """
    ia_results = _load_ia_results(prospect)
    matrix     = _build_query_matrix(ia_results, prospect.name)
    score, nb_mentions, nb_total = _score(matrix)

    return {
        "score":       score,
        "date":        _today_fr(),
        "period":      period,
        "nb_mentions": nb_mentions,
        "nb_total":    nb_total,
        "matrix":      matrix,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE COMPLET — avec persistance DB (ia_snapshots)
# ══════════════════════════════════════════════════════════════════════════════

# ── Checklist dynamique selon score ──────────────────────────────────────────

_CHECKLIST = {
    "fondations": [
        ("Fiche Google Business Profile complète",
         "Description métier, catégories, horaires, photos — les IA lisent directement ces données pour recommander des professionnels."),
        ("15 avis Google récents (note ≥ 4,5)",
         "Volume et fraîcheur des avis sont les signaux les plus forts pour ChatGPT et Gemini. Chaque avis compte."),
        ("Nom d'entreprise identique partout",
         "Le même nom exact sur votre site, Google, réseaux, annuaires. La cohérence est le signal de confiance n°1 des IA."),
        ("Page service locale",
         "Une page dédiée '{profession} à {ville}' avec la ville dans le titre H1 et le contenu."),
    ],
    "contenu": [
        ("Page service locale enrichie",
         "Ajouter descriptions détaillées, zone d'intervention, tarifs indicatifs sur votre page dédiée."),
        ("FAQ 8 questions",
         "Répondre aux questions posées aux IA : combien ça coûte, quel délai, quelles garanties. Ces réponses alimentent directement les modèles."),
        ("3 annuaires locaux",
         "Pages Jaunes, Yelp, et un annuaire de votre secteur. Chaque mention externe renforce votre présence IA."),
        ("20 avis Google",
         "Campagne de collecte d'avis auprès des clients récents (SMS ou email). Le seuil de 20 avis est un signal fort pour Claude."),
    ],
    "optimisation": [
        ("Références géographiques élargies",
         "Mentionner {ville} et les communes voisines dans vos textes. Les IA associent votre activité à une zone précise."),
        ("Article blog ciblé",
         "Un article '{profession} à {ville} — guide 2026' directement indexé et lu par les IA."),
        ("Annuaires premium",
         "Trustpilot, Houzz Premium, annuaires sectoriels. Signal fort pour Claude et Gemini."),
        ("Re-test dans 6 semaines",
         "Les changements mettent 6 à 10 semaines à être intégrés. Valider les progrès avant d'ajuster."),
    ],
}


def _build_dynamic_checklist(score: int, profession: str, ville: str) -> tuple[str, str]:
    """
    Retourne (titre_section, html_items) selon le score.
    """
    if score < 3:
        level = "fondations"
        titre = "Plan d'action — Fondations"
    elif score < 6:
        level = "contenu"
        titre = "Plan d'action — Contenu"
    else:
        level = "optimisation"
        titre = "Plan d'action — Optimisation"

    items = _CHECKLIST[level]
    html_parts = []
    for i, (title, desc) in enumerate(items, start=1):
        desc = desc.replace("{profession}", profession).replace("{ville}", ville)
        html_parts.append(
            f'<li><div class="check-num">{i}</div>'
            f'<div><div class="check-title">{_esc(title)}</div>'
            f'<div class="check-desc">{_esc(desc)}</div></div></li>'
        )
    return titre, "\n".join(html_parts)


# ── Persistance snapshots ─────────────────────────────────────────────────────

def _get_snapshot_model():
    """Import IaSnapshotDB compatible package et test-standalone."""
    try:
        from ..models import IaSnapshotDB
    except ImportError:
        from src.models import IaSnapshotDB  # test standalone
    return IaSnapshotDB


def _save_snapshot(db, prospect, matrix: list, score: int, nb_mentions: int,
                   nb_total: int, competitors: list, html: str,
                   report_type: str = "audit") -> None:
    """Enregistre le snapshot dans ia_snapshots."""
    IaSnapshotDB = _get_snapshot_model()
    snap = IaSnapshotDB(
        prospect_token   = prospect.token,
        report_type      = report_type,
        score            = score,
        nb_mentions      = nb_mentions,
        nb_total         = nb_total,
        matrix_json      = json.dumps(matrix, ensure_ascii=False),
        competitors_json = json.dumps(competitors, ensure_ascii=False),
        report_html      = html,
    )
    db.add(snap)
    db.commit()


def _load_last_snapshot(db, token: str) -> Optional[dict]:
    """
    Charge le snapshot le plus récent pour un prospect.
    Retourne un dict compatible avec previous_data, ou None.
    """
    IaSnapshotDB = _get_snapshot_model()
    snap = (
        db.query(IaSnapshotDB)
        .filter(IaSnapshotDB.prospect_token == token)
        .order_by(IaSnapshotDB.created_at.desc())
        .first()
    )
    if not snap:
        return None
    return {
        "score":       snap.score,
        "date":        snap.created_at.strftime("%-d %B %Y") if snap.created_at else "",
        "nb_mentions": snap.nb_mentions,
        "nb_total":    snap.nb_total,
        "matrix":      json.loads(snap.matrix_json) if snap.matrix_json else [],
    }


# ── generate_audit_report avec DB ────────────────────────────────────────────

def generate_audit_report(prospect, db=None, next_step: str = "") -> str:
    """
    Génère le rapport d'audit HTML pour un prospect V3.
    Si db est fourni : sauvegarde le snapshot en ia_snapshots.

    Args:
        prospect  : instance V3ProspectDB
        db        : session SQLAlchemy (optionnel)
        next_step : texte de la prochaine étape

    Returns:
        str : HTML complet
    """
    ia_results  = _load_ia_results(prospect)
    matrix      = _build_query_matrix(ia_results, prospect.name)
    score, nb_mentions, nb_total = _score(matrix)

    competitors = _load_competitors(prospect)
    if not competitors and ia_results:
        competitors = _extract_competitors(ia_results, prospect.name)

    if not next_step:
        next_step = (
            "Nos équipes démarrent l'implémentation cette semaine. "
            "Vous recevrez un rapport de suivi à M+1."
        )

    # Checklist dynamique selon score
    titre_checklist, checklist_html = _build_dynamic_checklist(
        score,
        profession = prospect.profession.lower(),
        ville      = prospect.city.capitalize(),
    )

    html = AUDIT_TEMPLATE.read_text(encoding="utf-8")

    html = html.replace("{{NOM_ENTREPRISE}}",  _esc(prospect.name))
    html = html.replace("{{PROFESSION}}",      _esc(prospect.profession.capitalize()))
    html = html.replace("{{VILLE}}",           _esc(prospect.city.capitalize()))
    html = html.replace("{{DATE_AUDIT}}",      _today_fr())
    html = html.replace("{{SCORE}}",           str(score))
    html = html.replace("{{NB_MENTIONS}}",     str(nb_mentions))
    html = html.replace("{{NB_TOTAL}}",        str(nb_total))
    html = html.replace("{{PROCHAINE_ETAPE}}", _esc(next_step))
    html = html.replace("{{NOM_CMS}}",         _esc(getattr(prospect, "cms", None) or "votre CMS"))
    html = html.replace("{{CHECKLIST_TITRE}}", _esc(titre_checklist))
    html = html.replace("{{CHECKLIST_HTML}}",  checklist_html)

    for i in range(1, 6):
        if i <= len(matrix):
            row = matrix[i - 1]
            html = html.replace(f"{{{{REQUETE_{i}}}}}", _esc(row["query_display"]))
            for model_name, tpl_key in [("ChatGPT", "GPT"), ("Gemini", "GEMINI"), ("Claude", "CLAUDE")]:
                css, label = _result_label(row.get(model_name))
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", css)
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", label)
        else:
            html = html.replace(f"{{{{REQUETE_{i}}}}}", "")
            for tpl_key in ["GPT", "GEMINI", "CLAUDE"]:
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", "not-cited")
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", "")

    for j in range(1, 4):
        if j <= len(competitors):
            name, count = competitors[j - 1]
            html = html.replace(f"{{{{CONCURRENT_{j}}}}}", _esc(f"{name} — cité {count} fois"))
        else:
            html = html.replace(f"{{{{CONCURRENT_{j}}}}}", "")

    if db is not None:
        try:
            _save_snapshot(db, prospect, matrix, score, nb_mentions, nb_total,
                           competitors, html, report_type="audit")
        except Exception as e:
            log.error("generate_audit_report: snapshot save failed: %s", e)

    return html


# ── generate_monthly_report avec DB ──────────────────────────────────────────

def generate_monthly_report(
    prospect,
    db=None,
    previous_data: Optional[dict] = None,
    actions_done: Optional[list] = None,
    next_actions: Optional[list] = None,
    periode: str = "",
    note: str = "",
) -> str:
    """
    Génère le rapport mensuel HTML.
    Si db est fourni : charge le dernier snapshot + sauvegarde le nouveau.
    Si previous_data est fourni directement : l'utilise en priorité (rétrocompat).

    Args:
        prospect      : instance V3ProspectDB
        db            : session SQLAlchemy (optionnel)
        previous_data : dict snapshot précédent (prioritaire sur DB si fourni)
        actions_done  : [{date, title, desc, status}, ...]
        next_actions  : [{title, desc}, ...]
        periode       : ex: "mai 2026"
        note          : texte libre de suivi

    Returns:
        str : HTML complet
    """
    # Données précédentes
    if previous_data is None:
        previous_data = _load_last_snapshot(db, prospect.token) if db else {}
    previous_data = previous_data or {}

    ia_results  = _load_ia_results(prospect)
    matrix      = _build_query_matrix(ia_results, prospect.name)
    score, nb_mentions, nb_total = _score(matrix)

    competitors = _load_competitors(prospect)
    if not competitors and ia_results:
        competitors = _extract_competitors(ia_results, prospect.name)

    prev_score  = previous_data.get("score", 0)
    prev_date   = previous_data.get("date", "")
    prev_matrix = previous_data.get("matrix", [])

    delta_val = score - prev_score
    if delta_val > 0:
        delta_text  = f"+{delta_val} point{'s' if delta_val > 1 else ''}"
        delta_class = "positive"
    elif delta_val < 0:
        delta_text  = f"{delta_val} point{'s' if abs(delta_val) > 1 else ''}"
        delta_class = "negative"
    else:
        delta_text  = "Stable"
        delta_class = "neutral"

    if not periode:
        today = date.today()
        months = ["", "janvier", "février", "mars", "avril", "mai", "juin",
                  "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        periode = f"{months[today.month]} {today.year}"

    html = REPORT_TEMPLATE.read_text(encoding="utf-8")

    html = html.replace("{{NOM_ENTREPRISE}}",     _esc(prospect.name))
    html = html.replace("{{PROFESSION}}",         _esc(prospect.profession.capitalize()))
    html = html.replace("{{VILLE}}",              _esc(prospect.city.capitalize()))
    html = html.replace("{{PERIODE}}",            _esc(periode))
    html = html.replace("{{DATE_RETEST}}",        _today_fr())
    html = html.replace("{{DATE_AUDIT_INITIAL}}", _esc(prev_date))
    html = html.replace("{{SCORE_INITIAL}}",      str(prev_score))
    html = html.replace("{{SCORE_ACTUEL}}",       str(score))
    html = html.replace("{{DELTA_CLASS}}",        delta_class)
    html = html.replace("{{DELTA_TEXTE}}",        _esc(delta_text))
    html = html.replace("{{SCORE_ICON}}",         _delta_icon(delta_val))
    html = html.replace("{{NB_CITATIONS_ACTUEL}}", str(nb_mentions))
    html = html.replace("{{NB_TOTAL}}",           str(nb_total))
    html = html.replace("{{NB_NOUVEAUX_AVIS}}",   str(previous_data.get("reviews_count", "—")))
    html = html.replace("{{NB_ANNUAIRES}}",       str(previous_data.get("annuaires_count", "—")))
    html = html.replace("{{DATE_PROCHAIN_RETEST}}", _esc(previous_data.get("next_retest", "à définir")))

    # Numéro du test (audit = 1, mensuel 1 = 2, etc.)
    if db is not None:
        try:
            IaSnapshotDB = _get_snapshot_model()
            snap_count = db.query(IaSnapshotDB).filter(
                IaSnapshotDB.prospect_token == prospect.token
            ).count()
            num_test = snap_count + 1  # +1 car le snapshot courant n'est pas encore sauvegardé
        except Exception:
            num_test = 2
    else:
        num_test = 2

    html = html.replace("{{NUM_TEST}}",      str(num_test))
    html = html.replace("{{PROCHAIN_MOIS}}", str(num_test + 1))

    # Tableau avec évolution
    prev_by_query = {_norm(r.get("query_display", r.get("query", ""))): r for r in prev_matrix}
    for i in range(1, 6):
        if i <= len(matrix):
            row = matrix[i - 1]
            html = html.replace(f"{{{{REQUETE_{i}}}}}", _esc(row["query_display"]))
            for model_name, tpl_key in [("ChatGPT", "GPT"), ("Gemini", "GEMINI"), ("Claude", "CLAUDE")]:
                css, label = _result_label(row.get(model_name))
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", css)
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", label)
            prev_row   = prev_by_query.get(_norm(row["query_display"]), {})
            curr_cited = sum(1 for m in MODELS if row.get(m) is True)
            prev_cited = sum(1 for m in MODELS if prev_row.get(m) is True)
            diff = curr_cited - prev_cited
            html = html.replace(f"{{{{EVOL_{i}}}}}", f"↑ +{diff}" if diff > 0 else (f"↓ {diff}" if diff < 0 else "→"))
        else:
            html = html.replace(f"{{{{REQUETE_{i}}}}}", "")
            for tpl_key in ["GPT", "GEMINI", "CLAUDE"]:
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", "not-cited")
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", "")
            html = html.replace(f"{{{{EVOL_{i}}}}}", "")

    html = html.replace("{{ACTIONS_HTML}}", _build_actions_html(actions_done))
    html = html.replace("{{STEPS_HTML}}",   _build_steps_html(next_actions))

    if not note:
        sign = "+" if delta_val >= 0 else ""
        note = (
            f"Les IA intègrent les nouvelles données avec 6 à 10 semaines de délai. "
            f"Score actuel : {score}/10 ({sign}{delta_val} points vs mois précédent)."
        )
    html = html.replace("{{NOTE_LIBRE}}", _esc(note))

    if db is not None:
        try:
            _save_snapshot(db, prospect, matrix, score, nb_mentions, nb_total,
                           competitors, html, report_type="monthly")
        except Exception as e:
            log.error("generate_monthly_report: snapshot save failed: %s", e)

    return html


# ── run_monthly ───────────────────────────────────────────────────────────────

def run_monthly(db) -> list[dict]:
    """
    Génère les rapports mensuels pour tous les clients actifs.
    Un client actif = a des ia_results ET au moins un snapshot (audit fait).

    Returns:
        list[dict] : [{token, name, score, delta, ok, error}, ...]
    """
    try:
        from ..models import V3ProspectDB, IaSnapshotDB
    except ImportError:
        from src.models import V3ProspectDB, IaSnapshotDB

    # Prospects avec ia_results et au moins 1 snapshot (ont eu un audit)
    tokens_with_snap = {
        row[0] for row in db.query(IaSnapshotDB.prospect_token).distinct().all()
    }
    if not tokens_with_snap:
        log.info("[run_monthly] Aucun snapshot trouvé — aucun rapport généré")
        return []

    prospects = (
        db.query(V3ProspectDB)
        .filter(
            V3ProspectDB.token.in_(tokens_with_snap),
            V3ProspectDB.ia_results.isnot(None),
        )
        .all()
    )

    results = []
    for p in prospects:
        try:
            html = generate_monthly_report(p, db=db)
            # Score du rapport généré = snapshot le plus récent qu'on vient d'insérer
            snap = (
                db.query(IaSnapshotDB)
                .filter(IaSnapshotDB.prospect_token == p.token)
                .order_by(IaSnapshotDB.created_at.desc())
                .first()
            )
            results.append({
                "token": p.token,
                "name":  p.name,
                "score": snap.score if snap else 0,
                "ok":    True,
                "error": None,
            })
            log.info("[run_monthly] %s → score %s", p.name, snap.score if snap else "?")
        except Exception as e:
            log.error("[run_monthly] %s → ERREUR: %s", p.name, e)
            results.append({"token": p.token, "name": p.name, "score": 0, "ok": False, "error": str(e)})

    return results
