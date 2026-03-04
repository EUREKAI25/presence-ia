"""
Route GET /client/{prospect_id}?t=token — chantier 10G
Dashboard client sécurisé par landing_token.

Sections :
1. Score actuel + historique
2. Dernier test (requêtes × résultats IA)
3. Concurrents détectés
4. Checklist de progression (items statiques)
5. Livrables disponibles
6. Prochain re-test prévu
"""
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_prospect, db_list_runs, jl

DIST_DIR = Path(__file__).parent.parent.parent.parent / "dist"

router = APIRouter(tags=["Client Dashboard"])

# 10 items de checklist (statiques — progression côté client via livrable interactif)
_CHECKLIST_ITEMS = [
    ("JSON-LD LocalBusiness", "Très élevé"),
    ("Google Business Profile optimisé", "Très élevé"),
    ("40+ avis Google avec réponses", "Très élevé"),
    ("5-10 pages FAQ optimisées IA", "Élevé"),
    ("H1 : métier + ville", "Élevé"),
    ("NAP cohérent sur le web", "Moyen"),
    ("Citations 15-20 plateformes", "Moyen"),
    ("Page À propos optimisée", "Moyen"),
    ("Article presse locale", "Moyen"),
    ("Mentions forums et blogs", "Faible"),
]

_IMPACT_COLORS = {
    "Très élevé": ("#dcfce7", "#16a34a"),
    "Élevé":      ("#dbeafe", "#1d4ed8"),
    "Moyen":      ("#fef9c3", "#854d0e"),
    "Faible":     ("#f3f4f6", "#6b7280"),
}


def _next_retest() -> str:
    today = date.today()
    if today.month == 12:
        nxt = date(today.year + 1, 1, 1)
    else:
        nxt = date(today.year, today.month + 1, 1)
    return nxt.strftime("%d/%m/%Y")


def _score_history_svg(history: list[dict]) -> str:
    """Génère un graphique SVG inline simple du score dans le temps."""
    if len(history) < 2:
        return ""
    w, h = 400, 60
    vals = [e["score"] for e in history]
    max_v = max(vals) or 10
    pts = []
    n = len(vals)
    for i, v in enumerate(vals):
        x = int(w * i / (n - 1))
        y = int(h - (v / 10) * h)
        pts.append(f"{x},{y}")
    path = " ".join(pts)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;overflow:visible">'
        f'<polyline points="{path}" fill="none" stroke="#e94560" stroke-width="2.5" stroke-linejoin="round"/>'
        + "".join(
            f'<circle cx="{x.split(",")[0]}" cy="{x.split(",")[1]}" r="3" fill="#e94560"/>'
            for x in pts
        )
        + f"</svg>"
    )


def _history_rows(runs: list) -> str:
    rows = ""
    for r in sorted(runs, key=lambda x: x.ts, reverse=True):
        mentions = jl(r.mention_per_query)
        score = round(sum(1 for m in mentions if m) / max(len(mentions), 1) * 10, 1) if mentions else 0
        is_retest = (r.notes or "").startswith("retest:")
        badge = '<span style="background:#dbeafe;color:#1d4ed8;padding:2px 8px;border-radius:10px;font-size:10px">Retest</span>' if is_retest else ""
        mention_str = " ".join(["✅" if m else "❌" for m in mentions]) or "—"
        rows += (
            f"<tr>"
            f'<td style="padding:8px;font-size:12px;color:#6b7280">{r.ts.strftime("%d/%m/%Y")}</td>'
            f'<td style="padding:8px"><span style="font-size:18px;font-weight:700;color:#e94560">{score:.1f}</span><span style="font-size:10px;color:#6b7280">/10</span></td>'
            f'<td style="padding:8px;font-size:12px">{mention_str}</td>'
            f'<td style="padding:8px">{badge}</td>'
            f"</tr>"
        )
    return rows or '<tr><td colspan="4" style="padding:12px;color:#6b7280;text-align:center;font-size:13px">Aucun test effectué</td></tr>'


def _last_run_detail(run) -> str:
    if not run:
        return '<p style="color:#6b7280;font-size:13px">Aucun test disponible.</p>'
    queries = jl(run.queries)
    mentions = jl(run.mention_per_query)
    rows = ""
    for i, q in enumerate(queries):
        m = mentions[i] if i < len(mentions) else False
        icon = "✅ Cité" if m else "❌ Non cité"
        color = "#16a34a" if m else "#dc2626"
        rows += (
            f"<tr>"
            f'<td style="padding:8px;font-size:13px;color:#374151">{q}</td>'
            f'<td style="padding:8px;font-weight:600;color:{color};font-size:12px">{icon}</td>'
            f"</tr>"
        )
    return (
        f'<table style="border-collapse:collapse;width:100%">'
        f'<tr><th style="background:#f3f4f6;color:#6b7280;font-size:11px;padding:8px;text-align:left;font-weight:600">Requête</th>'
        f'<th style="background:#f3f4f6;color:#6b7280;font-size:11px;padding:8px;text-align:left;font-weight:600">Résultat</th></tr>'
        f"{rows}</table>"
    )


def _competitors_html(runs: list) -> str:
    comps = set()
    for r in runs:
        for c in jl(r.competitors_entities):
            comps.add(c)
    if not comps:
        return '<p style="color:#6b7280;font-size:13px">Aucun concurrent identifié pour le moment.</p>'
    return "".join(
        f'<span style="display:inline-block;background:#fee2e2;color:#dc2626;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:600;margin:3px">{c}</span>'
        for c in sorted(comps)
    )


def _checklist_html() -> str:
    rows = ""
    for title, impact in _CHECKLIST_ITEMS:
        bg, fg = _IMPACT_COLORS.get(impact, ("#f3f4f6", "#6b7280"))
        rows += (
            f'<li style="padding:8px 0;border-bottom:1px solid #f3f4f6;display:flex;align-items:center;justify-content:space-between">'
            f'<span style="font-size:13px;color:#374151">{title}</span>'
            f'<span style="background:{bg};color:{fg};padding:2px 10px;border-radius:10px;font-size:10px;font-weight:600;white-space:nowrap;margin-left:12px">{impact}</span>'
            f"</li>"
        )
    return f'<ul style="list-style:none">{rows}</ul>'


def _livrables_html(prospect_id: str) -> str:
    livr_dir = DIST_DIR / prospect_id / "livrables"
    items = []
    if livr_dir.exists():
        for f in sorted(livr_dir.iterdir()):
            if f.suffix == ".html":
                label = f.stem.replace("_", " ").replace("-", " ").capitalize()
                items.append(label)
    audit = DIST_DIR / prospect_id / "audit.html"
    if audit.exists():
        items.insert(0, "Audit IA")
    if not items:
        return '<p style="color:#6b7280;font-size:13px">Les livrables seront disponibles après le premier test complet.</p>'
    return "".join(
        f'<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #f3f4f6">'
        f'<span style="font-size:16px">📄</span>'
        f'<span style="font-size:13px;color:#374151">{item}</span>'
        f'<span style="font-size:11px;color:#16a34a;margin-left:auto;font-weight:600">Disponible</span>'
        f"</div>"
        for item in items
    )


@router.get("/client/{prospect_id}", response_class=HTMLResponse)
def client_dashboard(prospect_id: str, t: str = "", db: Session = Depends(get_db)):
    p = db_get_prospect(db, prospect_id)
    if not p or p.landing_token != t:
        raise HTTPException(404, "Page introuvable")

    runs = db_list_runs(db, prospect_id)
    runs_sorted = sorted(runs, key=lambda r: r.ts, reverse=True)
    last_run = runs_sorted[0] if runs_sorted else None

    score_now = p.ia_visibility_score or 0

    # Score history data for chart
    history = []
    for r in sorted(runs, key=lambda x: x.ts):
        mentions = jl(r.mention_per_query)
        s = round(sum(1 for m in mentions if m) / max(len(mentions), 1) * 10, 1) if mentions else 0
        history.append({"ts": r.ts.strftime("%d/%m/%y"), "score": s, "is_retest": (r.notes or "").startswith("retest:")})

    svg_chart = _score_history_svg(history)
    history_rows = _history_rows(runs)
    last_run_detail = _last_run_detail(last_run)
    competitors_html = _competitors_html(runs)
    checklist_html = _checklist_html()
    livrables_html = _livrables_html(prospect_id)
    next_retest = _next_retest()
    nb_runs = len(runs)
    city_cap = p.city.capitalize()
    prof_cap = p.profession.capitalize()

    return f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mon espace — {p.name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e}}
.header{{background:linear-gradient(135deg,#1a0a4e,#0e2560);color:#fff;padding:28px 40px}}
.header h1{{font-size:20px;font-weight:800;margin-bottom:4px}}
.header p{{color:rgba(255,255,255,.7);font-size:13px}}
.body{{max-width:900px;margin:0 auto;padding:28px 20px}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:22px;margin-bottom:18px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.card h2{{color:#e94560;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:14px}}
.score-big{{font-size:56px;font-weight:900;letter-spacing:-2px;color:#e94560;line-height:1}}
.score-sub{{font-size:12px;color:#6b7280;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}}
table{{border-collapse:collapse;width:100%}}
th{{background:#f3f4f6;color:#6b7280;font-size:11px;padding:8px;text-align:left;font-weight:600}}
.badge-next{{background:#1a0a4e;color:#fff;padding:8px 20px;border-radius:6px;font-size:13px;font-weight:600;display:inline-block}}
</style>
</head>
<body>
<div class="header">
  <h1>Mon espace visibilité IA — {p.name}</h1>
  <p>{prof_cap} à {city_cap} &nbsp;·&nbsp; {nb_runs} test(s) effectué(s)</p>
</div>

<div class="body">

  <div class="card">
    <h2>Score de visibilité IA</h2>
    <div style="display:flex;align-items:flex-end;gap:32px;flex-wrap:wrap">
      <div>
        <div class="score-big">{score_now:.1f}</div>
        <div class="score-sub">Score actuel / 10</div>
      </div>
      <div style="flex:1;min-width:200px">
        {svg_chart if svg_chart else '<p style="color:#6b7280;font-size:12px">Historique disponible après plusieurs tests</p>'}
        <div style="display:flex;justify-content:space-between;font-size:11px;color:#6b7280;margin-top:4px">
          {f'<span>{history[0]["ts"]}</span><span>{history[-1]["ts"]}</span>' if len(history) >= 2 else ""}
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Historique des tests</h2>
    <table>
      <tr><th>Date</th><th>Score</th><th>Citations</th><th>Type</th></tr>
      {history_rows}
    </table>
  </div>

  <div class="card">
    <h2>Dernier test — détail des requêtes</h2>
    {last_run_detail}
  </div>

  <div class="card">
    <h2>Concurrents détectés</h2>
    {competitors_html}
  </div>

  <div class="card">
    <h2>Checklist de progression (10 actions)</h2>
    <p style="font-size:12px;color:#6b7280;margin-bottom:12px">Actions classées par impact sur votre visibilité IA.</p>
    {checklist_html}
  </div>

  <div class="card">
    <h2>Livrables disponibles</h2>
    {livrables_html}
  </div>

  <div class="card">
    <h2>Prochain re-test prévu</h2>
    <p style="font-size:13px;color:#374151;margin-bottom:12px">
      Votre visibilité est re-testée automatiquement chaque mois.
    </p>
    <span class="badge-next">📅 Prochain re-test : {next_retest}</span>
  </div>

</div>
</body></html>"""
