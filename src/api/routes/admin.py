"""
Admin UI — GET /admin  (protégé par ADMIN_TOKEN header ou ?token=)
Interface HTML légère pour piloter le pipeline sans Swagger.
"""
import os
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_campaign, db_list_campaigns, db_list_prospects, db_get_prospect, jl, db_dashboard_stats
from ...models import ProspectStatus, ProspectDB
from ._nav import admin_nav

router = APIRouter(tags=["Admin"])


def _check_token(request: Request):
    """Retourne None si valide, RedirectResponse vers login si invalide."""
    token = (request.headers.get("X-Admin-Token")
             or request.query_params.get("token")
             or request.cookies.get("admin_token", ""))
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        return RedirectResponse("/admin/login", status_code=302)
    return None


def _admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "changeme")


# ── Dashboard HTML ─────────────────────────────────────────────────────────


def _period_bounds(period: str, date_from: str = None, date_to: str = None):
    """Retourne (dt_from, dt_to, label, prev_from, prev_to) pour une période."""
    today = date.today()
    if period == "exercice":
        # Exercice en cours : démarre le 1er mars
        year = today.year if today.month >= 3 else today.year - 1
        dt_from = datetime(year, 3, 1)
        dt_to   = datetime.combine(today, datetime.max.time())
        label   = f"Exercice {year}-{year+1}"
        delta   = dt_to - dt_from
        prev_from = dt_from - delta
        prev_to   = dt_from
    elif period == "mois":
        dt_from = datetime(today.year, today.month, 1)
        dt_to   = datetime.combine(today, datetime.max.time())
        label   = today.strftime("%B %Y")
        # Mois précédent
        if today.month == 1:
            prev_from = datetime(today.year - 1, 12, 1)
            prev_to   = datetime(today.year, 1, 1)
        else:
            prev_from = datetime(today.year, today.month - 1, 1)
            prev_to   = dt_from
    elif period == "semaine":
        monday = today - timedelta(days=today.weekday())
        dt_from = datetime.combine(monday, datetime.min.time())
        dt_to   = datetime.combine(today, datetime.max.time())
        label   = f"Semaine du {monday.strftime('%d/%m')}"
        prev_from = dt_from - timedelta(weeks=1)
        prev_to   = dt_from
    elif period == "custom" and date_from and date_to:
        dt_from = datetime.strptime(date_from, "%Y-%m-%d")
        dt_to   = datetime.strptime(date_to,   "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        label   = f"{date_from} → {date_to}"
        delta   = dt_to - dt_from
        prev_from = dt_from - delta - timedelta(seconds=1)
        prev_to   = dt_from
    else:  # défaut = exercice
        return _period_bounds("exercice")
    return dt_from, dt_to, label, prev_from, prev_to


def _delta_html(curr: int, prev: int) -> str:
    if prev == 0:
        return '<span style="color:#6b7280;font-size:10px">—</span>'
    d = curr - prev
    pct = d / prev * 100
    color = "#16a34a" if d >= 0 else "#dc2626"
    arrow = "▲" if d >= 0 else "▼"
    return f'<span style="color:{color};font-size:10px;font-weight:600">{arrow} {abs(pct):.0f}%</span>'


def _kpi(label, val, sub="", delta_html="", color="#e94560"):
    return (
        f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px">'
        f'<div style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">{label}</div>'
        f'<div style="font-size:26px;font-weight:700;color:{color};line-height:1">{val}</div>'
        f'{"<div style=margin-top:6px;display:flex;align-items:center;gap:8px>" + (f"<span style=font-size:11px;color:#6b7280>{sub}</span>" if sub else "") + delta_html + "</div>" if sub or delta_html else ""}'
        f'</div>'
    )


def _pct(a, b):
    return f"{a/b*100:.0f}%" if b else "—"


def _funnel_arrow():
    return '<div style="display:flex;align-items:center;justify-content:center;color:#d1d5db;font-size:18px;padding:0 2px">→</div>'


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db),
                    period: str = "exercice", date_from: str = None, date_to: str = None):
    if (r := _check_token(request)) is not None: return r
    token = _admin_token()

    dt_from, dt_to, period_label, prev_from, prev_to = _period_bounds(period, date_from, date_to)

    s  = db_dashboard_stats(db, dt_from, dt_to)
    sp = db_dashboard_stats(db, prev_from, prev_to)

    nav = admin_nav(token, "")

    # ── Funnel prospection ──
    funnel_items = [
        ("Suspects SIRENE", s["suspects"], sp["suspects"], "#6366f1", f"total : {s['suspects_total']:,}"),
        ("Enrichis",        s["enrichis"],      sp["enrichis"],      "#8b5cf6", _pct(s["enrichis"], s["suspects"]) + " des suspects"),
        ("Contactables",    s["contactables"],  sp["contactables"],  "#0ea5e9", _pct(s["contactables"], s["enrichis"]) + " des enrichis"),
        ("Contactés",       s["contactes"],     sp["contactes"],     "#10b981", _pct(s["contactes"], s["contactables"]) + " des contactables"),
        ("Envoyés",         s["envoyes"],        sp["envoyes"],      "#f59e0b", _pct(s["envoyes"], s["contactes"]) + " des contactés"),
    ]
    funnel_html = '<div style="display:grid;grid-template-columns:repeat(5,1fr) repeat(4,auto);gap:4px;align-items:center">'
    for i, (lbl, val, prev, col, sub) in enumerate(funnel_items):
        funnel_html += _kpi(lbl, f"{val:,}", sub, _delta_html(val, prev), col)
        if i < len(funnel_items) - 1:
            funnel_html += _funnel_arrow()
    funnel_html += "</div>"

    # ── Funnel conversion ──
    conv_items = [
        ("Ouvertures",  s["ouvertures"], sp["ouvertures"], "#6366f1", _pct(s["ouvertures"], s["envoyes"]) + " des envoyés"),
        ("Clics",       s["clics"],      sp["clics"],      "#8b5cf6", _pct(s["clics"], s["envoyes"]) + " des envoyés"),
        ("Réponses +",  s["reponses"],   sp["reponses"],   "#0ea5e9", _pct(s["reponses"], s["envoyes"]) + " des envoyés"),
        ("RDV pris",    s["rdv"],        sp["rdv"],        "#10b981", _pct(s["rdv"], s["reponses"]) + " des réponses"),
        ("Deals signés",s["deals"],      sp["deals"],      "#e94560", _pct(s["deals"], s["rdv"]) + " des RDV"),
    ]
    conv_html = '<div style="display:grid;grid-template-columns:repeat(5,1fr) repeat(4,auto);gap:4px;align-items:center">'
    for i, (lbl, val, prev, col, sub) in enumerate(conv_items):
        conv_html += _kpi(lbl, f"{val:,}", sub, _delta_html(val, prev), col)
        if i < len(conv_items) - 1:
            conv_html += _funnel_arrow()
    conv_html += "</div>"

    # ── Taux global ──
    taux_html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">'
    taux_html += _kpi("Taux réponse",    _pct(s["reponses"], s["envoyes"]),  "réponses / envoyés",    color="#6366f1")
    taux_html += _kpi("Taux RDV",        _pct(s["rdv"], s["envoyes"]),       "RDV / envoyés",         color="#0ea5e9")
    taux_html += _kpi("Taux closing",    _pct(s["deals"], s["rdv"]),         "deals / RDV",           color="#10b981")
    taux_html += _kpi("Conv. globale",   _pct(s["deals"], s["envoyes"]),     "deals / envoyés",       color="#e94560")
    taux_html += "</div>"

    # ── Closers ──
    top_rows = "".join(
        f'<tr style="border-bottom:1px solid #f3f4f6">'
        f'<td style="padding:7px 10px;font-size:13px;font-weight:600">{i+1}. {c["name"]}</td>'
        f'<td style="padding:7px 10px;font-size:13px;color:#e94560;font-weight:700">{c["deals"]}</td>'
        f'</tr>'
        for i, c in enumerate(s["top_closers"])
    ) or '<tr><td colspan="2" style="padding:12px;color:#9ca3af;font-size:12px">Aucune donnée</td></tr>'

    closers_html = (
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px">'
        + _kpi("Closers actifs", s["closers_actifs"], color="#374151")
        + _kpi("RDV période",    s["rdv"],    _pct(s["rdv"], s["envoyes"]) + " des envoyés",    _delta_html(s["rdv"], sp["rdv"]),    "#10b981")
        + _kpi("Deals période",  s["deals"],  _pct(s["deals"], s["rdv"]) + " des RDV",          _delta_html(s["deals"], sp["deals"]), "#e94560")
        + f'</div>'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="border-bottom:2px solid #e5e7eb">'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Closer</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Deals</th>'
        f'</tr></thead><tbody>{top_rows}</tbody></table>'
    )

    # ── Breakdown métier × ville ──
    bk_rows = "".join(
        f'<tr style="border-bottom:1px solid #f3f4f6">'
        f'<td style="padding:7px 10px;font-size:12px;font-weight:600">{r["profession"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;color:#6b7280">{r["ville"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;color:#0ea5e9">{r["contactables"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;color:#10b981">{r["contactes"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;color:#6b7280">{_pct(r["contactes"],r["contactables"])}</td>'
        f'</tr>'
        for r in s["breakdown"]
    ) or '<tr><td colspan="5" style="padding:12px;color:#9ca3af;font-size:12px">Aucune donnée</td></tr>'

    breakdown_html = (
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="border-bottom:2px solid #e5e7eb">'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Métier</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Ville</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Contactables</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Contactés</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Taux</th>'
        f'</tr></thead><tbody>{bk_rows}</tbody></table>'
    )

    # ── Sélecteurs de période ──
    def _pill(p, label):
        active = period == p
        bg = "#e94560" if active else "#f3f4f6"
        col = "#fff" if active else "#374151"
        return f'<a href="/admin?token={token}&period={p}" style="background:{bg};color:{col};border-radius:20px;padding:5px 14px;font-size:12px;font-weight:600;text-decoration:none;white-space:nowrap">{label}</a>'

    period_selector = (
        f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
        + _pill("exercice", "Exercice")
        + _pill("mois", "Ce mois")
        + _pill("semaine", "Cette semaine")
        + f'<form method="get" action="/admin" style="display:flex;gap:6px;align-items:center">'
        + f'<input type="hidden" name="token" value="{token}">'
        + f'<input type="hidden" name="period" value="custom">'
        + f'<input type="date" name="date_from" value="{date_from or ""}" style="border:1px solid #d1d5db;border-radius:6px;padding:4px 8px;font-size:12px">'
        + f'<input type="date" name="date_to"   value="{date_to   or ""}" style="border:1px solid #d1d5db;border-radius:6px;padding:4px 8px;font-size:12px">'
        + f'<button type="submit" style="background:#374151;color:#fff;border:none;border-radius:6px;padding:5px 12px;font-size:12px;cursor:pointer">Go</button>'
        + f'</form>'
        + f'</div>'
    )

    return HTMLResponse(f"""<!DOCTYPE html><html><head>
<meta charset="utf-8"><title>Dashboard — PRESENCE IA</title>
{nav}
<style>
body{{font-family:system-ui,sans-serif;background:#f9fafb;color:#111}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px}}
h2{{font-size:13px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.06em;margin:0 0 14px}}
</style>
</head><body>
<div style="padding:24px;max-width:1400px">

  <!-- En-tête + filtres période -->
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:12px">
    <div>
      <h1 style="font-size:20px;font-weight:700;margin:0">Dashboard</h1>
      <span style="font-size:12px;color:#6b7280">{period_label} — vs période précédente</span>
    </div>
    {period_selector}
  </div>

  <!-- Funnel prospection -->
  <div class="card">
    <h2>Funnel prospection</h2>
    {funnel_html}
  </div>

  <!-- Funnel conversion -->
  <div class="card">
    <h2>Funnel conversion</h2>
    {conv_html}
  </div>

  <!-- Taux clés -->
  <div class="card">
    <h2>Taux clés</h2>
    {taux_html}
  </div>

  <!-- Closers + Breakdown -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div class="card">
      <h2>Closers</h2>
      {closers_html}
    </div>
    <div class="card" style="overflow-x:auto">
      <h2>Par métier × ville</h2>
      {breakdown_html}
    </div>
  </div>

</div>
</body></html>""")


@router.get("/admin/campaigns", response_class=HTMLResponse)
def admin_campaigns(request: Request, db: Session = Depends(get_db)):
    if (r := _check_token(request)) is not None: return r
    campaigns = db_list_campaigns(db)
    rows = ""
    for c in campaigns:
        ps = db_list_prospects(db, c.campaign_id)
        counts = {}
        for p in ps:
            counts[p.status] = counts.get(p.status, 0) + 1
        eligible = sum(1 for p in ps if p.eligibility_flag)
        rows += f"""<tr>
            <td><a href="/admin/campaign/{c.campaign_id}?token={_admin_token()}">{c.campaign_id[:8]}…</a></td>
            <td>{c.profession}</td><td>{c.city}</td>
            <td>{len(ps)}</td><td>{eligible}</td>
            <td style="font-size:11px;color:#6b7280">{', '.join(f'{k}:{v}' for k,v in counts.items())}</td>
        </tr>"""

    token = _admin_token()
    nav = admin_nav(token)
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>PRESENCE_IA — Admin</title>
<style>*{{box-sizing:border-box}}body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e;margin:0}}
h1{{color:#1a1a2e;margin-bottom:20px;font-size:18px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);border:1px solid #e5e7eb}}
th{{background:#f9fafb;color:#6b7280;padding:10px;text-align:left;font-size:12px}}
td{{padding:10px;border-bottom:1px solid #e5e7eb;color:#1a1a2e}}a{{color:#e94560}}
.badge{{display:inline-block;background:#e94560;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px}}</style></head>
<body>
{nav}
<div style="padding:24px">
<h1>Pipeline — Campagnes</h1>
<table><tr><th>ID</th><th>Profession</th><th>Ville</th><th>Prospects</th><th>Éligibles</th><th>Statuts</th></tr>
{rows or '<tr><td colspan=6 style="color:#9ca3af;text-align:center">Aucune campagne</td></tr>'}
</table>
<p style="margin-top:16px;color:#9ca3af;font-size:12px">
  <a href="/docs">→ Swagger docs</a> &nbsp;|&nbsp;
  <a href="/admin/scheduler?token={token}">→ Scheduler status</a>
</p></div></body></html>""")


# ── Détail campagne ────────────────────────────────────────────────────────


@router.get("/admin/campaign/{cid}", response_class=HTMLResponse)
def admin_campaign(cid: str, request: Request, db: Session = Depends(get_db)):
    if (r := _check_token(request)) is not None: return r
    c = db_get_campaign(db, cid)
    if not c:
        raise HTTPException(404, "Campagne introuvable")
    ps = db_list_prospects(db, cid)

    def _pill(s):
        color = {"SCANNED": "#3498db", "TESTED": "#9b59b6", "SCORED": "#2ecc71",
                 "READY_TO_SEND": "#f39c12", "SENT_MANUAL": "#27ae60"}.get(s, "#666")
        return f'<span style="background:{color};color:#fff;padding:2px 7px;border-radius:4px;font-size:11px">{s}</span>'

    rows = ""
    for p in ps:
        comps = ", ".join(jl(p.competitors_cited)[:3]) or "—"
        rows += f"""<tr>
            <td><a href="/admin/prospect/{p.prospect_id}?token={_admin_token()}">{p.name}</a></td>
            <td>{p.city}</td><td>{_pill(p.status)}</td>
            <td>{"✅" if p.eligibility_flag else "—"}</td>
            <td>{p.ia_visibility_score or "—"}</td>
            <td style="font-size:11px">{comps}</td>
        </tr>"""

    token = request.query_params.get("token", _admin_token())
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Campagne {cid[:8]}</title>
<style>*{{box-sizing:border-box}}body{{font-family:monospace;background:#f9fafb;color:#1a1a2e;margin:0;padding:24px}}
h1{{color:#1a1a2e}}h2{{color:#6b7280;font-size:14px;margin:4px 0 20px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);border:1px solid #e5e7eb}}
th{{background:#f9fafb;color:#6b7280;padding:10px;text-align:left;font-size:12px}}
td{{padding:10px;border-bottom:1px solid #e5e7eb;color:#1a1a2e}}a{{color:#e94560}}</style></head>
<body>
<h1>Campagne — {c.profession} / {c.city}</h1>
<h2>ID: {cid} &nbsp;|&nbsp; {len(ps)} prospects</h2>
<table><tr><th>Nom</th><th>Ville</th><th>Statut</th><th>Éligible</th><th>Score</th><th>Concurrents</th></tr>
{rows or '<tr><td colspan=6 style="color:#9ca3af;text-align:center">Aucun prospect</td></tr>'}
</table>
<p style="margin-top:16px"><a href="/admin?token={token}">← Retour</a></p>
</body></html>""")


# ── Détail prospect ────────────────────────────────────────────────────────


@router.get("/admin/prospect/{pid}", response_class=HTMLResponse)
def admin_prospect(pid: str, request: Request, db: Session = Depends(get_db)):
    if (r := _check_token(request)) is not None: return r
    p = db_get_prospect(db, pid)
    if not p:
        raise HTTPException(404, "Prospect introuvable")
    token = request.query_params.get("token", _admin_token())

    assets_form = ""
    if p.status in (ProspectStatus.SCORED.value, ProspectStatus.READY_ASSETS.value):
        assets_form = f"""
<h2 style="color:#6b7280;margin-top:32px">Ajouter assets</h2>
<form method="post" action="/api/prospect/{pid}/assets?token={token}"
      style="background:#fff;padding:20px;border-radius:8px;max-width:600px;border:1px solid #e5e7eb;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
  <label style="display:block;margin-bottom:8px;color:#6b7280">video_url</label>
  <input name="video_url" style="width:100%;padding:8px;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;border-radius:4px;margin-bottom:12px" value="{p.video_url or ''}">
  <label style="display:block;margin-bottom:8px;color:#6b7280">screenshot_url</label>
  <input name="screenshot_url" style="width:100%;padding:8px;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;border-radius:4px;margin-bottom:16px" value="{p.screenshot_url or ''}">
  <button type="submit" style="background:#e94560;color:#fff;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,0.1)">Enregistrer assets</button>
</form>"""

    mark_ready_btn = ""
    if p.status == ProspectStatus.READY_ASSETS.value and p.video_url and p.screenshot_url:
        mark_ready_btn = f"""
<form method="post" action="/api/prospect/{pid}/mark-ready?token={token}" style="margin-top:12px">
  <button style="background:#2ecc71;color:#fff;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;font-weight:bold;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
    ✓ Marquer READY_TO_SEND
  </button>
</form>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>{p.name}</title>
<style>*{{box-sizing:border-box}}body{{font-family:monospace;background:#f9fafb;color:#1a1a2e;margin:0;padding:24px}}
h1{{color:#1a1a2e}}dt{{color:#6b7280;font-size:12px;margin-top:12px}}dd{{color:#1a1a2e;margin:4px 0 0 0}}
.box{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;max-width:600px;margin:20px 0;box-shadow:0 1px 3px rgba(0,0,0,0.1)}}
a{{color:#e94560}}</style></head>
<body>
<h1>{p.name}</h1>
<div class="box"><dl>
  <dt>ID</dt><dd>{p.prospect_id}</dd>
  <dt>Statut</dt><dd>{p.status}</dd>
  <dt>Ville</dt><dd>{p.city}</dd>
  <dt>Profession</dt><dd>{p.profession}</dd>
  <dt>Score IA</dt><dd>{p.ia_visibility_score or '—'}/10</dd>
  <dt>Éligible</dt><dd>{"✅ OUI" if p.eligibility_flag else "❌ NON"}</dd>
  <dt>Concurrents</dt><dd>{', '.join(jl(p.competitors_cited)) or '—'}</dd>
  <dt>video_url</dt><dd>{p.video_url or '—'}</dd>
  <dt>screenshot_url</dt><dd>{p.screenshot_url or '—'}</dd>
  <dt>Justification</dt><dd style="color:#6b7280;font-size:12px">{p.score_justification or '—'}</dd>
</dl></div>
{assets_form}
{mark_ready_btn}
<p style="margin-top:24px">
  <a href="/admin/campaign/{p.campaign_id}?token={token}">← Retour campagne</a>
</p>
</body></html>""")


# ── Send Queue ─────────────────────────────────────────────────────────────


@router.get("/admin/send-queue", response_class=HTMLResponse)
def admin_send_queue(request: Request, db: Session = Depends(get_db)):
    if (r := _check_token(request)) is not None: return r
    token = request.query_params.get("token", _admin_token())

    # Tous les prospects éligibles (SCORED, READY_ASSETS, READY_TO_SEND, SENT_MANUAL)
    _ok_statuses = {
        ProspectStatus.SCORED.value,
        ProspectStatus.READY_ASSETS.value,
        ProspectStatus.READY_TO_SEND.value,
        ProspectStatus.SENT_MANUAL.value,
    }
    prospects: list[ProspectDB] = (
        db.query(ProspectDB)
        .filter(ProspectDB.eligibility_flag == True)
        .filter(ProspectDB.status.in_(_ok_statuses))
        .filter(ProspectDB.paid == False)
        .order_by(ProspectDB.ia_visibility_score.desc().nullslast())
        .all()
    )

    def _check(val):
        return "✅" if val else "❌"

    def _pill(s):
        color = {
            "SCORED": "#3498db", "READY_ASSETS": "#9b59b6",
            "READY_TO_SEND": "#f39c12", "SENT_MANUAL": "#27ae60",
        }.get(s, "#666")
        return f'<span style="background:{color};color:#fff;padding:2px 7px;border-radius:4px;font-size:11px">{s}</span>'

    rows = ""
    for p in prospects:
        c1 = (jl(p.competitors_cited) or ["—"])[0]
        email_cell = (
            f'<code style="color:#2ecc71;font-size:11px">{p.email}</code>'
            if p.email else
            f'<button onclick="enrichEmail(\'{p.prospect_id}\')" '
            f'style="background:#fff;color:#374151;border:1px solid #e5e7eb;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:11px">'
            f'Enrichir</button>'
        )
        send_btn = ""
        if p.email and p.status != ProspectStatus.SENT_MANUAL.value:
            send_btn = (
                f'<button onclick="sendEmail(\'{p.prospect_id}\')" '
                f'style="background:#e94560;color:#fff;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px;margin-left:4px">'
                f'Envoyer</button>'
            )
        rows += f"""<tr id="row-{p.prospect_id}">
          <td><a href="/admin/prospect/{p.prospect_id}?token={token}" style="color:#e94560">{p.name}</a></td>
          <td>{p.city}</td>
          <td style="font-size:11px;color:#6b7280">{p.profession}</td>
          <td>{_pill(p.status)}</td>
          <td style="text-align:center">{p.ia_visibility_score or '—'}</td>
          <td style="font-size:11px">{c1}</td>
          <td>{email_cell}{send_btn}</td>
          <td style="text-align:center">
            {_check(p.proof_image_url)}
            <label style="cursor:pointer;color:#6b7280;font-size:11px" title="Upload preuve">
              <input type="file" accept="image/*" style="display:none"
                     onchange="uploadFile(this,'{p.prospect_id}','proof-image')">
              📎
            </label>
          </td>
          <td style="text-align:center">
            {_check(p.city_image_url)}
            <label style="cursor:pointer;color:#6b7280;font-size:11px" title="Upload photo ville">
              <input type="file" accept="image/*" style="display:none"
                     onchange="uploadFile(this,'{p.prospect_id}','city-image')">
              📎
            </label>
          </td>
          <td style="min-width:180px">
            <input id="vid-{p.prospect_id}" type="text"
              value="{p.video_url or ''}"
              placeholder="Lien Dropbox…"
              style="width:100%;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:4px 6px;border-radius:4px;font-size:11px">
            <button onclick="saveVideoUrl('{p.prospect_id}')"
              style="margin-top:4px;background:#fff;color:#374151;border:1px solid #e5e7eb;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:11px;width:100%">
              Enregistrer
            </button>
          </td>
        </tr>"""

    js = f"""
<script>
const TOKEN = '{token}';

async function enrichEmail(pid) {{
  const r = await fetch(`/admin/prospect/${{pid}}/enrich-email?token=${{TOKEN}}`, {{method:'POST'}});
  const d = await r.json();
  location.reload();
}}

async function sendEmail(pid) {{
  if (!confirm('Envoyer cet email via Brevo ?')) return;
  const r = await fetch(`/admin/prospect/${{pid}}/send-email?token=${{TOKEN}}`, {{method:'POST'}});
  const d = await r.json();
  if (d.sent) {{ alert('✅ Email envoyé à ' + d.email); location.reload(); }}
  else {{ alert('❌ Erreur : ' + (d.detail || JSON.stringify(d))); }}
}}

async function uploadFile(input, pid, type) {{
  const fd = new FormData();
  fd.append('file', input.files[0]);
  const r = await fetch(`/admin/prospect/${{pid}}/upload-${{type}}?token=${{TOKEN}}`, {{
    method: 'POST', body: fd
  }});
  const d = await r.json();
  if (d.url) {{ alert('✅ Uploadé : ' + d.url); location.reload(); }}
  else {{ alert('❌ Erreur upload'); }}
}}

async function saveVideoUrl(pid) {{
  const url = document.getElementById('vid-' + pid).value.trim();
  if (!url) {{ alert('URL vide'); return; }}
  const fd = new FormData(); fd.append('video_url', url);
  const r = await fetch(`/admin/prospect/${{pid}}/upload-video?token=${{TOKEN}}`, {{
    method: 'POST', body: fd
  }});
  const d = await r.json();
  if (d.url) {{ alert('✅ Vidéo enregistrée'); }}
  else {{ alert('❌ Erreur : ' + JSON.stringify(d)); }}
}}
</script>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Send Queue — PRESENCE_IA</title>
<style>*{{box-sizing:border-box}}body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e;margin:0}}
h1{{color:#1a1a2e;margin-bottom:4px;font-size:18px}}h2{{color:#6b7280;font-size:13px;margin:0 0 20px}}
.wrap{{padding:24px;max-width:1400px;margin:0 auto}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);border:1px solid #e5e7eb}}
th{{background:#f9fafb;color:#6b7280;padding:10px;text-align:left;font-size:11px}}
td{{padding:8px 10px;border-bottom:1px solid #e5e7eb;color:#1a1a2e;vertical-align:middle}}
a{{color:#e94560}}code{{font-size:11px}}</style></head>
<body>
{admin_nav(token, "send-queue")}
<div class="wrap">
<h1>Send Queue</h1>
<h2>{len(prospects)} prospects éligibles</h2>
<table>
  <tr>
    <th>Nom</th><th>Ville</th><th>Métier</th><th>Statut</th>
    <th>Score</th><th>Concurrent #1</th><th>Email</th>
    <th>Preuve</th><th>Ville img</th><th>Vidéo</th>
  </tr>
  {rows or '<tr><td colspan=10 style="text-align:center;color:#9ca3af;padding:20px">Aucun prospect éligible</td></tr>'}
</table>
{js}
</div></body></html>""")


# ── Scheduler status ───────────────────────────────────────────────────────


@router.get("/admin/scheduler", response_class=HTMLResponse)
def admin_scheduler(request: Request):
    token = request.query_params.get("token", "") or request.cookies.get("admin_token", "")
    if (r := _check_token(request)) is not None: return r
    try:
        from ...scheduler import scheduler_status
        jobs = scheduler_status()
    except Exception as e:
        jobs = [{"id": "error", "next_run": str(e), "trigger": "—"}]

    rows = "".join(
        f'<tr><td>{j["id"]}</td><td>{j["next_run"]}</td><td>{j["trigger"]}</td></tr>'
        for j in jobs
    )
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Scheduler — PRESENCE_IA</title>
<style>*{{box-sizing:border-box}}body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e;margin:0}}
.wrap{{padding:24px;max-width:960px;margin:0 auto}}
h1{{color:#1a1a2e;font-size:18px;margin-bottom:4px}}
p.sub{{color:#6b7280;font-size:13px;margin-bottom:20px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1);border:1px solid #e5e7eb}}
th{{background:#f9fafb;color:#6b7280;padding:10px;text-align:left;font-size:12px}}
td{{padding:10px;border-bottom:1px solid #e5e7eb;color:#1a1a2e}}a{{color:#e94560}}</style></head>
<body>
{admin_nav(token, "scheduler")}
<div class="wrap">
<h1>Planificateur</h1>
<p class="sub">Jobs APScheduler actifs — prospections automatiques et tâches récurrentes</p>
<table><tr><th>ID</th><th>Prochain run</th><th>Trigger</th></tr>{rows}</table>
</div></body></html>""")
