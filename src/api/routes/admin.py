"""
Admin UI — GET /admin  (protégé par ADMIN_TOKEN header ou ?token=)
Interface HTML légère pour piloter le pipeline sans Swagger.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_campaign, db_list_campaigns, db_list_prospects, db_get_prospect, jl
from ...models import ProspectStatus

router = APIRouter(tags=["Admin"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "changeme")


def _check_token(request: Request):
    token = request.headers.get("X-Admin-Token") or request.query_params.get("token")
    if token != ADMIN_TOKEN:
        raise HTTPException(403, "Token admin invalide")


# ── Dashboard HTML ─────────────────────────────────────────────────────────


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    campaigns = db_list_campaigns(db)
    rows = ""
    for c in campaigns:
        ps = db_list_prospects(db, c.campaign_id)
        counts = {}
        for p in ps:
            counts[p.status] = counts.get(p.status, 0) + 1
        eligible = sum(1 for p in ps if p.eligibility_flag)
        rows += f"""<tr>
            <td><a href="/admin/campaign/{c.campaign_id}?token={ADMIN_TOKEN}">{c.campaign_id[:8]}…</a></td>
            <td>{c.profession}</td><td>{c.city}</td>
            <td>{len(ps)}</td><td>{eligible}</td>
            <td style="font-size:11px;color:#aaa">{', '.join(f'{k}:{v}' for k,v in counts.items())}</td>
        </tr>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>PRESENCE_IA — Admin</title>
<style>*{{box-sizing:border-box}}body{{font-family:monospace;background:#0f0f1a;color:#e8e8f0;margin:0;padding:24px}}
h1{{color:#e94560;margin-bottom:20px}}
table{{border-collapse:collapse;width:100%;background:#1a1a2e;border-radius:8px;overflow:hidden}}
th{{background:#16213e;color:#aaa;padding:10px;text-align:left;font-size:12px}}
td{{padding:10px;border-bottom:1px solid #2a2a4e;color:#ddd}}a{{color:#e94560}}
.badge{{display:inline-block;background:#e94560;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px}}</style></head>
<body><h1>PRESENCE_IA — Pipeline Admin</h1>
<table><tr><th>ID</th><th>Profession</th><th>Ville</th><th>Prospects</th><th>Éligibles</th><th>Statuts</th></tr>
{rows or '<tr><td colspan=6 style="color:#666;text-align:center">Aucune campagne</td></tr>'}
</table>
<p style="margin-top:16px;color:#666;font-size:12px">
  <a href="/docs?token={ADMIN_TOKEN}">→ Swagger docs</a> &nbsp;|&nbsp;
  <a href="/admin/scheduler?token={ADMIN_TOKEN}">→ Scheduler status</a>
</p></body></html>""")


# ── Détail campagne ────────────────────────────────────────────────────────


@router.get("/admin/campaign/{cid}", response_class=HTMLResponse)
def admin_campaign(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
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
            <td><a href="/admin/prospect/{p.prospect_id}?token={ADMIN_TOKEN}">{p.name}</a></td>
            <td>{p.city}</td><td>{_pill(p.status)}</td>
            <td>{"✅" if p.eligibility_flag else "—"}</td>
            <td>{p.ia_visibility_score or "—"}</td>
            <td style="font-size:11px">{comps}</td>
        </tr>"""

    token = request.query_params.get("token", ADMIN_TOKEN)
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Campagne {cid[:8]}</title>
<style>*{{box-sizing:border-box}}body{{font-family:monospace;background:#0f0f1a;color:#e8e8f0;margin:0;padding:24px}}
h1{{color:#e94560}}h2{{color:#aaa;font-size:14px;margin:4px 0 20px}}
table{{border-collapse:collapse;width:100%;background:#1a1a2e;border-radius:8px;overflow:hidden}}
th{{background:#16213e;color:#aaa;padding:10px;text-align:left;font-size:12px}}
td{{padding:10px;border-bottom:1px solid #2a2a4e;color:#ddd}}a{{color:#e94560}}</style></head>
<body>
<h1>Campagne — {c.profession} / {c.city}</h1>
<h2>ID: {cid} &nbsp;|&nbsp; {len(ps)} prospects</h2>
<table><tr><th>Nom</th><th>Ville</th><th>Statut</th><th>Éligible</th><th>Score</th><th>Concurrents</th></tr>
{rows or '<tr><td colspan=6 style="color:#666;text-align:center">Aucun prospect</td></tr>'}
</table>
<p style="margin-top:16px"><a href="/admin?token={token}">← Retour</a></p>
</body></html>""")


# ── Détail prospect ────────────────────────────────────────────────────────


@router.get("/admin/prospect/{pid}", response_class=HTMLResponse)
def admin_prospect(pid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    p = db_get_prospect(db, pid)
    if not p:
        raise HTTPException(404, "Prospect introuvable")
    token = request.query_params.get("token", ADMIN_TOKEN)

    assets_form = ""
    if p.status in (ProspectStatus.SCORED.value, ProspectStatus.READY_ASSETS.value):
        assets_form = f"""
<h2 style="color:#aaa;margin-top:32px">Ajouter assets</h2>
<form method="post" action="/api/prospect/{pid}/assets?token={token}"
      style="background:#1a1a2e;padding:20px;border-radius:8px;max-width:600px">
  <label style="display:block;margin-bottom:8px;color:#aaa">video_url</label>
  <input name="video_url" style="width:100%;padding:8px;background:#0f0f1a;border:1px solid #2a2a4e;color:#fff;border-radius:4px;margin-bottom:12px" value="{p.video_url or ''}">
  <label style="display:block;margin-bottom:8px;color:#aaa">screenshot_url</label>
  <input name="screenshot_url" style="width:100%;padding:8px;background:#0f0f1a;border:1px solid #2a2a4e;color:#fff;border-radius:4px;margin-bottom:16px" value="{p.screenshot_url or ''}">
  <button type="submit" style="background:#e94560;color:#fff;border:none;padding:10px 20px;border-radius:4px;cursor:pointer">Enregistrer assets</button>
</form>"""

    mark_ready_btn = ""
    if p.status == ProspectStatus.READY_ASSETS.value and p.video_url and p.screenshot_url:
        mark_ready_btn = f"""
<form method="post" action="/api/prospect/{pid}/mark-ready?token={token}" style="margin-top:12px">
  <button style="background:#2ecc71;color:#0f0f1a;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;font-weight:bold">
    ✓ Marquer READY_TO_SEND
  </button>
</form>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>{p.name}</title>
<style>*{{box-sizing:border-box}}body{{font-family:monospace;background:#0f0f1a;color:#e8e8f0;margin:0;padding:24px}}
h1{{color:#e94560}}dt{{color:#aaa;font-size:12px;margin-top:12px}}dd{{color:#fff;margin:4px 0 0 0}}
.box{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px;max-width:600px;margin:20px 0}}
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
  <dt>Justification</dt><dd style="color:#aaa;font-size:12px">{p.score_justification or '—'}</dd>
</dl></div>
{assets_form}
{mark_ready_btn}
<p style="margin-top:24px">
  <a href="/admin/campaign/{p.campaign_id}?token={token}">← Retour campagne</a>
</p>
</body></html>""")


# ── Scheduler status ───────────────────────────────────────────────────────


@router.get("/admin/scheduler", response_class=HTMLResponse)
def admin_scheduler(request: Request):
    _check_token(request)
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
<meta charset="UTF-8"><title>Scheduler</title>
<style>*{{box-sizing:border-box}}body{{font-family:monospace;background:#0f0f1a;color:#e8e8f0;margin:0;padding:24px}}
h1{{color:#e94560}}table{{border-collapse:collapse;width:100%;background:#1a1a2e;border-radius:8px}}
th{{background:#16213e;color:#aaa;padding:10px;text-align:left;font-size:12px}}
td{{padding:10px;border-bottom:1px solid #2a2a4e;color:#ddd}}a{{color:#e94560}}</style></head>
<body><h1>Scheduler — Jobs actifs</h1>
<table><tr><th>ID</th><th>Prochain run</th><th>Trigger</th></tr>{rows}</table>
<p style="margin-top:16px"><a href="/admin?token={request.query_params.get('token', ADMIN_TOKEN)}">← Retour</a></p>
</body></html>""")
