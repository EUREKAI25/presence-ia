"""
STRATEGIC_DOSSIER (10E)
Génère le dossier stratégique complet (HTML exportable PDF) :
  1. RCA — pourquoi absent des IA
  2. Analyse concurrents cités
  3. Plan d'action 3-6 mois
  4. Projections de score
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from ..database import db_list_runs, jl
from ..models import ProspectDB

DIST_DIR = Path(__file__).parent.parent.parent / "dist"

_MODEL_LABEL = {"openai": "ChatGPT", "anthropic": "Claude", "gemini": "Gemini"}


def _rca_items(p: ProspectDB) -> List[str]:
    """Construit les causes racines basées sur les données du prospect."""
    score = p.ia_visibility_score or 0
    causes = []
    if not p.reviews_count or p.reviews_count < 40:
        n = p.reviews_count or 0
        causes.append(
            f"<strong>Volume d'avis insuffisant</strong> — {n} avis Google détectés "
            f"(objectif : 40+). Les IA pondèrent fortement le nombre et la récence des avis "
            f"pour identifier les références locales."
        )
    causes.append(
        "<strong>Données structurées absentes ou incomplètes</strong> — "
        "Le site ne contient probablement pas de JSON-LD LocalBusiness, "
        "ce qui prive les LLMs d'un signal d'identification direct."
    )
    causes.append(
        "<strong>Contenu sémantique insuffisant</strong> — "
        f"Les pages du site ne positionnent pas explicitement {p.name} "
        f"comme {p.profession} à {p.city}. Les LLMs ont besoin d'entités nommées "
        f"claires et répétées (nom + métier + ville)."
    )
    if score < 3:
        causes.append(
            "<strong>Absence de citations tierces</strong> — "
            "Peu ou pas de mentions sur des plateformes locales (PagesJaunes, Yelp, etc.), "
            "blogs, ou presse locale. Ces citations constituent des signaux d'autorité "
            "indépendants essentiels pour les IA."
        )
    causes.append(
        "<strong>Pas de contenu FAQ optimisé</strong> — "
        "Aucune page ne répond directement aux questions que posent vos clients aux IA. "
        "Sans ces pages, les LLMs ne peuvent pas vous associer aux requêtes testées."
    )
    return causes


def _action_plan(p: ProspectDB) -> List[dict]:
    """Plan d'action priorisé sur 3-6 mois."""
    return [
        {
            "mois": "M1",
            "priorite": "Critique",
            "action": "Intégrer les données structurées JSON-LD",
            "detail": f"LocalBusiness + AggregateRating sur {p.website or 'votre site'}. Impact rapide.",
            "impact_estime": "+1 à +2 pts de score",
        },
        {
            "mois": "M1",
            "priorite": "Critique",
            "action": "Compléter Google Business Profile à 100 %",
            "detail": f"Description, photos, horaires, services. Mention explicite de {p.profession} à {p.city}.",
            "impact_estime": "+1 pt de score",
        },
        {
            "mois": "M1–M2",
            "priorite": "Haute",
            "action": "Publier 5 pages FAQ ciblées",
            "detail": "Une page par requête testée lors de l'audit. 300-500 mots chacune.",
            "impact_estime": "+1 à +2 pts de score",
        },
        {
            "mois": "M1–M3",
            "priorite": "Haute",
            "action": f"Atteindre {max(40, (p.reviews_count or 0) + 10)} avis Google",
            "detail": "Système de collecte post-intervention. Répondre à tous les avis.",
            "impact_estime": "+1 pt de score",
        },
        {
            "mois": "M2",
            "priorite": "Moyenne",
            "action": "Auditer et corriger la cohérence NAP",
            "detail": "Vérifier Nom/Adresse/Téléphone sur toutes les plateformes.",
            "impact_estime": "+0.5 pt de score",
        },
        {
            "mois": "M2–M3",
            "priorite": "Moyenne",
            "action": "Créer des citations sur 15-20 plateformes locales",
            "detail": "PagesJaunes, Yelp, Houzz, Cylex, Kompass, annuaires métier.",
            "impact_estime": "+1 pt de score",
        },
        {
            "mois": "M3–M6",
            "priorite": "Moyenne",
            "action": "Obtenir 1 article de presse locale",
            "detail": f"Un article mentionnant {p.name} dans la presse de {p.city}.",
            "impact_estime": "+0.5 à +1 pt de score",
        },
        {
            "mois": "M4–M6",
            "priorite": "Faible",
            "action": "Réécrire les pages principales du site",
            "detail": "Accueil, À propos, Services — entités nommées et sémantique IA-first.",
            "impact_estime": "+1 pt de score",
        },
    ]


def _score_projection(p: ProspectDB) -> dict:
    score = p.ia_visibility_score or 0
    return {
        "baseline": round(score, 1),
        "m3": min(10.0, round(score + 3.0, 1)),
        "m6": min(10.0, round(score + 5.5, 1)),
    }


def generate_dossier(db: Session, p: ProspectDB) -> dict:
    """
    Génère le dossier stratégique HTML complet.

    Returns:
        {"html": str, "file": str, "summary": {...}}
    """
    runs = db_list_runs(db, p.prospect_id)
    competitors = [c.title() for c in jl(p.competitors_cited)][:5]
    score = p.ia_visibility_score or 0
    proj = _score_projection(p)
    rca = _rca_items(p)
    plan = _action_plan(p)
    now = datetime.now().strftime("%d/%m/%Y")

    # ── RCA HTML ───────────────────────────────────────────────────────
    rca_html = "".join(
        f'<div class="rca-item"><span class="rca-num">{i+1}</span>'
        f'<p>{cause}</p></div>'
        for i, cause in enumerate(rca)
    )

    # ── Concurrents HTML ───────────────────────────────────────────────
    comp_rows = ""
    if competitors:
        for c in competitors:
            models_citing = [
                _MODEL_LABEL.get(r.model, r.model)
                for r in runs
                if c.lower() in jl(r.competitors_entities).__str__().lower()
            ]
            models_str = ", ".join(set(models_citing)) or "—"
            comp_rows += (
                f'<tr><td class="td-name">{c}</td>'
                f'<td class="td-models">{models_str}</td>'
                f'<td class="td-signal">À analyser</td></tr>'
            )
    else:
        comp_rows = '<tr><td colspan="3" style="color:#6b7280;text-align:center">Aucun concurrent identifié lors des tests</td></tr>'

    # ── Plan HTML ──────────────────────────────────────────────────────
    prio_cls = {"Critique": "prio-red", "Haute": "prio-orange", "Moyenne": "prio-yellow", "Faible": "prio-gray"}
    plan_rows = "".join(
        f'<tr>'
        f'<td class="td-mois">{a["mois"]}</td>'
        f'<td><span class="prio {prio_cls.get(a["priorite"], "prio-gray")}">{a["priorite"]}</span></td>'
        f'<td><strong>{a["action"]}</strong><br><small style="color:#6b7280">{a["detail"]}</small></td>'
        f'<td class="td-impact">{a["impact_estime"]}</td>'
        f'</tr>'
        for a in plan
    )

    # ── Projections HTML ───────────────────────────────────────────────
    bar_w = lambda s: max(4, int(s / 10 * 100))
    proj_html = f"""
<div class="proj-grid">
  <div class="proj-card">
    <div class="proj-label">Aujourd'hui</div>
    <div class="proj-score">{proj['baseline']}<span>/10</span></div>
    <div class="proj-bar"><div class="proj-fill proj-fill--current" style="width:{bar_w(proj['baseline'])}%"></div></div>
  </div>
  <div class="proj-card">
    <div class="proj-label">Dans 3 mois</div>
    <div class="proj-score proj-score--target">{proj['m3']}<span>/10</span></div>
    <div class="proj-bar"><div class="proj-fill proj-fill--m3" style="width:{bar_w(proj['m3'])}%"></div></div>
  </div>
  <div class="proj-card">
    <div class="proj-label">Dans 6 mois</div>
    <div class="proj-score proj-score--target">{proj['m6']}<span>/10</span></div>
    <div class="proj-bar"><div class="proj-fill proj-fill--m6" style="width:{bar_w(proj['m6'])}%"></div></div>
  </div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dossier Stratégique — {p.name}</title>
<style>
:root {{
  --acc:#e8355a; --txt:#111827; --muted:#6b7280;
  --light:#f9fafb; --border:#e5e7eb; --green:#16a34a;
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,'Segoe UI',sans-serif; background:#fff; color:var(--txt); }}
.page {{ max-width:860px; margin:0 auto; padding:48px 32px; }}
@media print {{ .page {{ padding:24px 0; }} }}
.cover {{ border-bottom:4px solid var(--acc); padding-bottom:40px; margin-bottom:48px; }}
.cover h1 {{ font-size:32px; font-weight:900; letter-spacing:-.5px; margin-bottom:8px; }}
.cover .subtitle {{ color:var(--muted); font-size:15px; }}
.cover .meta {{ margin-top:20px; display:flex; gap:24px; flex-wrap:wrap; }}
.cover .meta-item {{ background:var(--light); border:1px solid var(--border);
  padding:12px 20px; border-radius:8px; }}
.cover .meta-item .label {{ font-size:11px; font-weight:700; text-transform:uppercase;
  letter-spacing:1px; color:var(--muted); margin-bottom:4px; }}
.cover .meta-item .value {{ font-size:18px; font-weight:800; color:var(--txt); }}
.score-badge {{ display:inline-flex; align-items:baseline; gap:4px;
  background:linear-gradient(135deg,#fff0f3,#fff); border:2px solid var(--acc);
  border-radius:12px; padding:12px 24px; }}
.score-badge .n {{ font-size:48px; font-weight:900; color:var(--acc); line-height:1; }}
.score-badge .denom {{ font-size:20px; color:var(--muted); }}
section {{ margin-bottom:56px; }}
section h2 {{ font-size:22px; font-weight:800; border-left:4px solid var(--acc);
  padding-left:16px; margin-bottom:24px; }}
.rca-item {{ display:flex; gap:16px; align-items:flex-start;
  padding:16px; background:var(--light); border-radius:10px; margin-bottom:12px; }}
.rca-num {{ min-width:28px; height:28px; background:var(--acc); color:#fff;
  border-radius:50%; display:flex; align-items:center; justify-content:center;
  font-size:12px; font-weight:800; flex-shrink:0; }}
.rca-item p {{ font-size:14px; line-height:1.7; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
th {{ background:#111827; color:#fff; padding:10px 14px; text-align:left;
  font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:1px; }}
td {{ padding:12px 14px; border-bottom:1px solid var(--border); vertical-align:top; }}
tr:last-child td {{ border-bottom:none; }}
.td-name {{ font-weight:600; }}
.td-models {{ color:var(--muted); font-size:13px; }}
.td-impact {{ font-size:13px; color:var(--green); font-weight:600; }}
.td-mois {{ font-weight:700; color:var(--acc); white-space:nowrap; }}
.prio {{ font-size:10px; font-weight:700; padding:3px 10px; border-radius:20px;
  text-transform:uppercase; letter-spacing:.5px; white-space:nowrap; }}
.prio-red {{ background:#fee2e2; color:#b91c1c; }}
.prio-orange {{ background:#ffedd5; color:#c2410c; }}
.prio-yellow {{ background:#fef3c7; color:#92400e; }}
.prio-gray {{ background:var(--light); color:var(--muted); border:1px solid var(--border); }}
.proj-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:20px; }}
.proj-card {{ background:var(--light); border:1.5px solid var(--border);
  border-radius:12px; padding:24px; text-align:center; }}
.proj-label {{ font-size:12px; font-weight:700; text-transform:uppercase;
  letter-spacing:1px; color:var(--muted); margin-bottom:12px; }}
.proj-score {{ font-size:40px; font-weight:900; color:var(--txt); line-height:1; margin-bottom:16px; }}
.proj-score span {{ font-size:16px; font-weight:400; color:var(--muted); }}
.proj-score--target {{ color:var(--green); }}
.proj-bar {{ background:var(--border); border-radius:99px; height:8px; overflow:hidden; }}
.proj-fill {{ height:100%; border-radius:99px; }}
.proj-fill--current {{ background:var(--acc); }}
.proj-fill--m3 {{ background:#f59e0b; }}
.proj-fill--m6 {{ background:var(--green); }}
.justification {{ background:var(--light); border-left:4px solid var(--muted);
  padding:16px 20px; border-radius:0 8px 8px 0; font-size:14px;
  color:#374151; line-height:1.7; margin-top:20px; }}
footer {{ margin-top:60px; padding-top:24px; border-top:1px solid var(--border);
  font-size:12px; color:var(--muted); text-align:center; }}
@media print {{
  .proj-grid {{ grid-template-columns:repeat(3,1fr) !important; }}
}}
</style>
</head>
<body>
<div class="page">

  <!-- COUVERTURE -->
  <div class="cover">
    <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:2px;
      color:var(--acc);margin-bottom:16px">PRESENCE_IA — Dossier Stratégique</div>
    <h1>Plan de Visibilité IA<br>{p.name}</h1>
    <p class="subtitle">{p.profession.capitalize()} à {p.city.capitalize()} · Édition du {now}</p>
    <div class="meta">
      <div class="meta-item">
        <div class="label">Score actuel</div>
        <div class="value">{score:.1f}/10</div>
      </div>
      <div class="meta-item">
        <div class="label">IA testées</div>
        <div class="value">{len(set(r.model for r in runs)) or 3}</div>
      </div>
      <div class="meta-item">
        <div class="label">Concurrents détectés</div>
        <div class="value">{len(competitors)}</div>
      </div>
      <div class="meta-item">
        <div class="label">Actions prioritaires</div>
        <div class="value">{len(plan)}</div>
      </div>
    </div>
  </div>

  <!-- SECTION 1 — RCA -->
  <section>
    <h2>1. Pourquoi vous n'apparaissez pas dans les IA</h2>
    <p style="color:var(--muted);font-size:14px;margin-bottom:24px">
      Analyse des signaux manquants identifiés lors de l'audit de {p.name}.
    </p>
    {rca_html}
    {f'<div class="justification">{p.score_justification}</div>' if p.score_justification else ''}
  </section>

  <!-- SECTION 2 — CONCURRENTS -->
  <section>
    <h2>2. Qui est cité à votre place</h2>
    <p style="color:var(--muted);font-size:14px;margin-bottom:20px">
      Entreprises détectées dans les réponses IA lors des tests.
    </p>
    <table>
      <tr><th>Concurrent</th><th>IA qui les citent</th><th>Signal détecté</th></tr>
      {comp_rows}
    </table>
  </section>

  <!-- SECTION 3 — PLAN D'ACTION -->
  <section>
    <h2>3. Plan d'action — 6 mois</h2>
    <p style="color:var(--muted);font-size:14px;margin-bottom:20px">
      Actions classées par priorité et impact estimé sur le score de visibilité IA.
    </p>
    <table>
      <tr><th>Période</th><th>Priorité</th><th>Action</th><th>Impact estimé</th></tr>
      {plan_rows}
    </table>
  </section>

  <!-- SECTION 4 — PROJECTIONS -->
  <section>
    <h2>4. Projections de score</h2>
    <p style="color:var(--muted);font-size:14px;margin-bottom:24px">
      Estimation basée sur la mise en œuvre complète du plan d'action.
      Les résultats réels peuvent varier selon la vitesse d'exécution.
    </p>
    {proj_html}
  </section>

  <footer>
    © 2026 PRESENCE_IA — {p.name} · {p.city.capitalize()} · {now}<br>
    Document confidentiel — Usage client uniquement
  </footer>
</div>
</body>
</html>"""

    out_dir = DIST_DIR / p.prospect_id / "livrables"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "dossier_strategique.html"
    out_file.write_text(html, encoding="utf-8")

    return {
        "html": html,
        "file": str(out_file),
        "summary": {
            "score_baseline": proj["baseline"],
            "score_m3": proj["m3"],
            "score_m6": proj["m6"],
            "rca_count": len(rca),
            "competitors": competitors,
            "actions": len(plan),
        },
    }
