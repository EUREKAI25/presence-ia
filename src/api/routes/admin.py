"""
Admin UI — GET /admin  (protégé par ADMIN_TOKEN header ou ?token=)
Interface HTML légère pour piloter le pipeline sans Swagger.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_campaign, db_list_campaigns, db_list_prospects, db_get_prospect, jl
from ...models import ProspectStatus, ProspectDB

router = APIRouter(tags=["Admin"])


def _admin_nav(token: str, active: str = "") -> str:
    tabs = [
        ("contacts",   "👥 Contacts"),
        ("offers",     "💶 Offres"),
        ("analytics",  "📊 Analytics"),
        ("evidence",   "📸 Preuves"),
        ("headers",    "🖼 Headers"),
        ("content",    "✏️ Contenus"),
        ("send-queue", "📤 Envoi"),
    ]
    links = "".join(
        f'<a href="/admin/{t}?token={token}" style="padding:10px 18px;border-radius:6px;text-decoration:none;'
        f'font-size:13px;font-weight:{"bold" if t==active else "normal"};'
        f'background:{"#e94560" if t==active else "#f9fafb"};color:{"#fff" if t==active else "#374151"}">{label}</a>'
        for t, label in tabs
    )
    return f'''<div style="background:#fff;border-bottom:1px solid #e5e7eb;padding:0 20px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
  <a href="/admin?token={token}" style="color:#e94560;font-weight:bold;font-size:15px;padding:12px 16px 12px 0;text-decoration:none">⚡ PRESENCE_IA</a>
  {links}
</div>'''


def _check_token(request: Request):
    token = (request.headers.get("X-Admin-Token")
             or request.query_params.get("token")
             or request.cookies.get("admin_token", ""))
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Token admin invalide")


def _admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "changeme")


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
            <td><a href="/admin/campaign/{c.campaign_id}?token={_admin_token()}">{c.campaign_id[:8]}…</a></td>
            <td>{c.profession}</td><td>{c.city}</td>
            <td>{len(ps)}</td><td>{eligible}</td>
            <td style="font-size:11px;color:#6b7280">{', '.join(f'{k}:{v}' for k,v in counts.items())}</td>
        </tr>"""

    token = _admin_token()
    nav = _admin_nav(token)
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
    _check_token(request)
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
    _check_token(request)
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
<style>*{{box-sizing:border-box}}body{{font-family:monospace;background:#f9fafb;color:#1a1a2e;margin:0;padding:24px}}
h1{{color:#1a1a2e;margin-bottom:4px}}h2{{color:#6b7280;font-size:13px;margin:0 0 20px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);border:1px solid #e5e7eb}}
th{{background:#f9fafb;color:#6b7280;padding:10px;text-align:left;font-size:11px}}
td{{padding:8px 10px;border-bottom:1px solid #e5e7eb;color:#1a1a2e;vertical-align:middle}}
a{{color:#e94560}}code{{font-size:11px}}</style></head>
<body>
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
<p style="margin-top:16px;color:#9ca3af;font-size:12px">
  <a href="/admin?token={token}">← Dashboard</a> &nbsp;|&nbsp;
  <a href="/admin/scheduler?token={token}">→ Scheduler</a>
</p>
{js}
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
<style>*{{box-sizing:border-box}}body{{font-family:monospace;background:#f9fafb;color:#1a1a2e;margin:0;padding:24px}}
h1{{color:#1a1a2e}}table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1);border:1px solid #e5e7eb}}
th{{background:#f9fafb;color:#6b7280;padding:10px;text-align:left;font-size:12px}}
td{{padding:10px;border-bottom:1px solid #e5e7eb;color:#1a1a2e}}a{{color:#e94560}}</style></head>
<body><h1>Scheduler — Jobs actifs</h1>
<table><tr><th>ID</th><th>Prochain run</th><th>Trigger</th></tr>{rows}</table>
<p style="margin-top:16px"><a href="/admin?token={request.query_params.get('token', _admin_token())}">← Retour</a></p>
</body></html>""")
