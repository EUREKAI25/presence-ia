"""
Génération HTML des rapports clients.

  render_audit_html(...)   → injecte audit_template.html
  render_monthly_html(...) → injecte report_template.html
  select_cms_guide(...)    → retourne le chemin du guide CMS adapté
  save_html(...)           → écrit le HTML sur disque
"""

import logging
import re
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

# ── Chemins templates et ressources ───────────────────────────────────────────

_ROOT = Path(__file__).parent.parent.parent
AUDIT_TEMPLATE   = _ROOT / "deliverables" / "audit" / "audit_template.html"
REPORT_TEMPLATE  = _ROOT / "deliverables" / "reports" / "report_template.html"
RESOURCES_DIR    = _ROOT / "RESOURCES"
OUTPUT_AUDITS    = _ROOT / "deliverables" / "generated" / "audits"
OUTPUT_REPORTS   = _ROOT / "deliverables" / "generated" / "reports"

# Mapping CMS → fichier guide
_CMS_GUIDES = {
    "wordpress":   RESOURCES_DIR / "GUIDE_WORDPRESS_VISIBILITE_IA.html",
    "wix":         RESOURCES_DIR / "GUIDE_WIX_VISIBILITE_IA.html",
    "shopify":     RESOURCES_DIR / "GUIDE_SHOPIFY_VISIBILITE_IA.html",
    "squarespace": RESOURCES_DIR / "GUIDE_VISIBILITE_IA_PREMIUM.html",
    "webflow":     RESOURCES_DIR / "GUIDE_VISIBILITE_IA_PREMIUM.html",
    "premium":     RESOURCES_DIR / "GUIDE_VISIBILITE_IA_PREMIUM.html",
}
_CMS_DEFAULT = RESOURCES_DIR / "GUIDE_WORDPRESS_VISIBILITE_IA.html"


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _esc(s) -> str:
    """Échappe les caractères HTML basiques."""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _today_fr() -> str:
    today = date.today()
    months = ["", "janvier", "février", "mars", "avril", "mai", "juin",
              "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{today.day} {months[today.month]} {today.year}"


def _result_cell(cited: bool | None) -> tuple[str, str]:
    """(class_css, icône) pour une cellule du tableau de résultats."""
    if cited is True:
        return "cited", "✓"
    if cited is False:
        return "not-cited", "✗"
    return "not-cited", "—"  # None = non testé


def _delta_icon(delta: float) -> str:
    if delta > 0:
        return "↑"
    if delta < 0:
        return "↓"
    return "→"


# ── CMS guide ─────────────────────────────────────────────────────────────────

def select_cms_guide(cms: str | None = None, website: str | None = None) -> Path:
    """
    Retourne le chemin du guide CMS le plus adapté au prospect.

    Logique :
    1. Utilise le champ cms s'il est connu (valeurs de cms_detector.py)
    2. Essaie de détecter depuis l'URL du site (wix.com, myshopify.com, etc.)
    3. Fallback : guide WordPress (CMS le plus courant)

    Args:
        cms     : valeur du champ cms en DB (ex: "wordpress", "wix", "shopify")
        website : URL du site pour détection par URL

    Returns:
        Path vers le guide HTML
    """
    # 1. Champ cms connu
    if cms:
        cms_lower = cms.lower().strip()
        if cms_lower in _CMS_GUIDES:
            guide = _CMS_GUIDES[cms_lower]
            if guide.exists():
                log.debug("select_cms_guide: cms=%s → %s", cms_lower, guide.name)
                return guide

    # 2. Détection via URL
    if website:
        w = website.lower()
        if "wix.com" in w or "wixsite.com" in w or "wixstatic.com" in w:
            return _CMS_GUIDES.get("wix", _CMS_DEFAULT)
        if "shopify.com" in w or "myshopify.com" in w:
            return _CMS_GUIDES.get("shopify", _CMS_DEFAULT)
        if "squarespace.com" in w:
            return _CMS_GUIDES.get("squarespace", _CMS_DEFAULT)
        if "webflow.io" in w or "webflow.com" in w:
            return _CMS_GUIDES.get("webflow", _CMS_DEFAULT)

    # 3. Fallback WordPress
    log.debug("select_cms_guide: cms inconnu (%s), fallback WordPress", cms)
    return _CMS_DEFAULT


# ── Audit HTML ────────────────────────────────────────────────────────────────

def _build_checklist_html(checklist: dict) -> str:
    """Génère le HTML de la checklist à partir du dict retourné par scoring.build_checklist."""
    parts = []
    for i, item in enumerate(checklist["items"], start=1):
        parts.append(
            f'<li>'
            f'<div class="check-num">{i}</div>'
            f'<div>'
            f'<div class="check-title">{_esc(item["title"])}</div>'
            f'<div class="check-desc">{_esc(item["desc"])}</div>'
            f'</div></li>'
        )
    return "\n".join(parts)


def render_audit_html(
    name: str,
    profession: str,
    city: str,
    cms: str,
    score_data: dict,
    queries: list[dict],
    competitors: list[dict],
    checklist: dict,
    next_step: str = "",
) -> str:
    """
    Génère le HTML complet de l'audit initial.

    Args:
        name        : nom de l'entreprise
        profession  : profession (ex: "plombier")
        city        : ville (ex: "Lyon")
        cms         : CMS détecté (pour la mention dans le template)
        score_data  : dict retourné par scoring.compute_score()
        queries     : liste canonique retournée par parser.parse_ia_results()
        competitors : liste retournée par scoring.extract_competitors()
        checklist   : dict retourné par scoring.build_checklist()
        next_step   : texte de la prochaine étape (adapté à l'offre vendue)

    Returns:
        str : HTML complet
    """
    if not AUDIT_TEMPLATE.exists():
        raise FileNotFoundError(f"Template manquant : {AUDIT_TEMPLATE}")

    if not next_step:
        next_step = (
            "Nos équipes démarrent l'implémentation cette semaine. "
            "Vous recevrez un rapport de suivi à M+1."
        )

    html = AUDIT_TEMPLATE.read_text(encoding="utf-8")

    # Variables globales
    html = html.replace("{{NOM_ENTREPRISE}}",  _esc(name))
    html = html.replace("{{PROFESSION}}",      _esc(profession.capitalize()))
    html = html.replace("{{VILLE}}",           _esc(city.capitalize()))
    html = html.replace("{{DATE_AUDIT}}",      _today_fr())
    html = html.replace("{{SCORE}}",           str(int(score_data["score"])))
    html = html.replace("{{NB_MENTIONS}}",     str(score_data["total_citations"]))
    html = html.replace("{{NB_TOTAL}}",        str(score_data["total_possible"]))
    html = html.replace("{{PROCHAINE_ETAPE}}", _esc(next_step))
    html = html.replace("{{NOM_CMS}}",         _esc(cms or "votre CMS"))
    html = html.replace("{{CHECKLIST_TITRE}}", _esc(checklist["title"]))
    html = html.replace("{{CHECKLIST_HTML}}",  _build_checklist_html(checklist))

    # Tableau des requêtes (5 lignes max)
    for i in range(1, 6):
        if i <= len(queries):
            row = queries[i - 1]
            html = html.replace(f"{{{{REQUETE_{i}}}}}", _esc(row.get("query_display", row["query"])))
            for model_key, tpl_key in [("chatgpt", "GPT"), ("gemini", "GEMINI"), ("claude", "CLAUDE")]:
                css, label = _result_cell(row.get(model_key))
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", css)
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", label)
        else:
            html = html.replace(f"{{{{REQUETE_{i}}}}}", "")
            for tpl_key in ["GPT", "GEMINI", "CLAUDE"]:
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", "not-cited")
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", "")

    # Concurrents (3 max)
    for j in range(1, 4):
        if j <= len(competitors):
            c = competitors[j - 1]
            label = f"{_esc(c['name'])} — cité {c['count']} fois"
        else:
            label = ""
        html = html.replace(f"{{{{CONCURRENT_{j}}}}}", label)

    return html


# ── Rapport mensuel HTML ──────────────────────────────────────────────────────

def _build_actions_html(actions_done: list[dict] | None) -> str:
    """HTML des actions réalisées — aucun item vide."""
    TAG_CSS   = {"done": "tag-done", "progress": "tag-progress", "todo": "tag-todo"}
    TAG_LABEL = {"done": "Fait", "progress": "En cours", "todo": "À faire"}
    ICONS     = {"done": "✅", "progress": "🔄", "todo": "⭕"}

    parts = []
    for a in (actions_done or []):
        title = a.get("title", "").strip()
        if not title:
            continue
        status = a.get("status", "done")
        icon   = a.get("icon") or ICONS.get(status, "✅")
        d      = a.get("date", "")
        desc   = a.get("desc", "")
        parts.append(
            f'<li>'
            f'<div class="tl-date">{_esc(d)}</div>'
            f'<div class="tl-icon">{icon}</div>'
            f'<div class="tl-content">'
            f'<div class="tl-title">{_esc(title)} '
            f'<span class="tag {TAG_CSS.get(status, "tag-done")}">'
            f'{TAG_LABEL.get(status, "Fait")}</span></div>'
            f'<div class="tl-desc">{_esc(desc)}</div>'
            f'</div></li>'
        )
    return "\n".join(parts)


def _build_steps_html(next_actions: list[dict] | None) -> str:
    """HTML des prochaines étapes — aucun item vide."""
    parts = []
    for i, a in enumerate(next_actions or [], start=1):
        title = a.get("title", "").strip()
        if not title:
            continue
        desc = a.get("desc", "")
        parts.append(
            f'<li>'
            f'<div class="step-num">{i}</div>'
            f'<div>'
            f'<div class="step-title">{_esc(title)}</div>'
            f'<div class="step-desc">{_esc(desc)}</div>'
            f'</div></li>'
        )
    return "\n".join(parts)


def render_monthly_html(
    name: str,
    profession: str,
    city: str,
    current: dict,    # score_data + queries du mois courant
    previous: dict,   # snapshot du mois précédent (peut être vide)
    num_test: int = 2,
    periode: str = "",
    actions_done: list[dict] | None = None,
    next_actions: list[dict] | None = None,
    note: str = "",
    reviews_count = "—",
    annuaires_count = "—",
    next_retest: str = "à définir",
) -> str:
    """
    Génère le HTML complet du rapport mensuel de suivi.

    Args:
        name          : nom de l'entreprise
        profession    : profession
        city          : ville
        current       : {"score_data": dict, "queries": list[dict]}
        previous      : {"score": float, "date": str, "queries": list[dict]}
                        (issu du dernier snapshot — peut être {} si premier rapport)
        num_test      : numéro du test (audit=1, mensuel 1=2, mensuel 2=3, ...)
        periode       : ex: "mai 2026"
        actions_done  : [{date, title, desc, status, icon}, ...]
        next_actions  : [{title, desc}, ...]
        note          : texte libre
        reviews_count : nb avis Google ajoutés
        annuaires_count : nb annuaires référencés
        next_retest   : date du prochain re-test

    Returns:
        str : HTML complet
    """
    if not REPORT_TEMPLATE.exists():
        raise FileNotFoundError(f"Template manquant : {REPORT_TEMPLATE}")

    score_data  = current["score_data"]
    queries     = current["queries"]
    score       = score_data["score"]

    prev_score  = previous.get("score", 0)
    prev_date   = previous.get("date", "")
    prev_queries = previous.get("queries", [])

    delta_val = round(score - prev_score, 1)
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

    # Variables globales
    html = html.replace("{{NOM_ENTREPRISE}}",     _esc(name))
    html = html.replace("{{PROFESSION}}",         _esc(profession.capitalize()))
    html = html.replace("{{VILLE}}",              _esc(city.capitalize()))
    html = html.replace("{{PERIODE}}",            _esc(periode))
    html = html.replace("{{DATE_RETEST}}",        _today_fr())
    html = html.replace("{{DATE_AUDIT_INITIAL}}", _esc(prev_date))
    html = html.replace("{{SCORE_INITIAL}}",      str(int(prev_score)))
    html = html.replace("{{SCORE_ACTUEL}}",       str(int(score)))
    html = html.replace("{{DELTA_CLASS}}",        delta_class)
    html = html.replace("{{DELTA_TEXTE}}",        _esc(delta_text))
    html = html.replace("{{SCORE_ICON}}",         _delta_icon(delta_val))
    html = html.replace("{{NB_CITATIONS_ACTUEL}}", str(score_data["total_citations"]))
    html = html.replace("{{NB_TOTAL}}",           str(score_data["total_possible"]))
    html = html.replace("{{NB_NOUVEAUX_AVIS}}",   str(reviews_count))
    html = html.replace("{{NB_ANNUAIRES}}",       str(annuaires_count))
    html = html.replace("{{DATE_PROCHAIN_RETEST}}", _esc(next_retest))
    html = html.replace("{{NUM_TEST}}",           str(num_test))
    html = html.replace("{{PROCHAIN_MOIS}}",      str(num_test + 1))

    # Tableau avec évolution vs mois précédent
    prev_by_query = {
        row.get("query_display", row.get("query", "")): row
        for row in prev_queries
    }

    for i in range(1, 6):
        if i <= len(queries):
            row = queries[i - 1]
            qd  = row.get("query_display", row["query"])
            html = html.replace(f"{{{{REQUETE_{i}}}}}", _esc(qd))

            for model_key, tpl_key in [("chatgpt", "GPT"), ("gemini", "GEMINI"), ("claude", "CLAUDE")]:
                css, label = _result_cell(row.get(model_key))
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", css)
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", label)

            # Évolution : compare nb de citations actuelles vs précédentes pour cette requête
            prev_row   = prev_by_query.get(qd, {})
            curr_cited = sum(1 for m in ["chatgpt", "gemini", "claude"] if row.get(m) is True)
            prev_cited = sum(1 for m in ["chatgpt", "gemini", "claude"] if prev_row.get(m) is True)
            diff = curr_cited - prev_cited
            evol = f"↑ +{diff}" if diff > 0 else (f"↓ {diff}" if diff < 0 else "→")
            html = html.replace(f"{{{{EVOL_{i}}}}}", evol)

        else:
            html = html.replace(f"{{{{REQUETE_{i}}}}}", "")
            for tpl_key in ["GPT", "GEMINI", "CLAUDE"]:
                html = html.replace(f"{{{{CITE_{tpl_key}_{i}}}}}", "not-cited")
                html = html.replace(f"{{{{RESULTAT_{tpl_key}_{i}}}}}", "")
            html = html.replace(f"{{{{EVOL_{i}}}}}", "")

    # Actions et étapes dynamiques
    html = html.replace("{{ACTIONS_HTML}}", _build_actions_html(actions_done))
    html = html.replace("{{STEPS_HTML}}",   _build_steps_html(next_actions))

    # Note libre
    if not note:
        sign = "+" if delta_val >= 0 else ""
        note = (
            "Les IA intègrent les nouvelles données avec 6 à 10 semaines de délai. "
            f"Les actions menées ce mois devraient se refléter dans le prochain test. "
            f"Score actuel : {int(score)}/10 ({sign}{int(delta_val)} pts vs mois précédent)."
        )
    html = html.replace("{{NOTE_LIBRE}}", _esc(note))

    return html


# ── Sauvegarde fichier ────────────────────────────────────────────────────────

def save_html(html: str, directory: Path, filename: str) -> Path:
    """
    Écrit le HTML dans directory/filename.
    Crée le répertoire si nécessaire.
    Retourne le chemin absolu du fichier créé.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(html, encoding="utf-8")
    log.info("HTML écrit : %s", path)
    return path
