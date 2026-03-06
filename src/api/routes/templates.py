"""Admin — /admin/templates : editer les templates email/SMS."""
import json, os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_list_templates, db_get_template, db_update_template
from ._nav import admin_nav, admin_token

router = APIRouter(tags=["Admin Templates"])


def _check(request: Request):
    t = (request.headers.get("X-Admin-Token")
         or request.query_params.get("token")
         or request.cookies.get("admin_token", ""))
    if t != admin_token():
        raise HTTPException(403, "Acces refuse")


@router.get("/admin/templates", response_class=HTMLResponse)
def admin_templates(request: Request, db: Session = Depends(get_db)):
    _check(request)
    token = request.query_params.get("token", admin_token())
    templates = db_list_templates(db)

    CHANNEL_LABEL = {"email": "Email", "sms": "SMS"}
    CHANNEL_COLOR = {"email": "#3b82f6", "sms": "#10b981"}

    cards = ""
    for t in templates:
        ph = json.loads(t.placeholders or "[]")
        ph_html = "".join(
            f'<code style="background:#f1f5f9;padding:1px 5px;border-radius:3px;font-size:11px;margin:2px">{p}</code>'
            for p in ph
        )
        channel_badge = (
            f'<span style="background:{CHANNEL_COLOR.get(t.channel,"#888")};color:#fff;'
            f'padding:2px 8px;border-radius:4px;font-size:11px">{CHANNEL_LABEL.get(t.channel, t.channel)}</span>'
        )
        subject_row = (
            f'<div style="font-size:12px;color:#6b7280;margin-bottom:4px"><b>Objet :</b> {t.subject or "—"}</div>'
            if t.channel == "email" else ""
        )
        preview = (t.body or "")[:120].replace("\n", " ")
        cards += f"""
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
    {channel_badge}
    <strong style="font-size:15px">{t.name}</strong>
    <span style="color:#9ca3af;font-size:11px;margin-left:auto">{t.slug}</span>
  </div>
  {subject_row}
  <div style="font-size:12px;color:#374151;background:#f9fafb;padding:8px;border-radius:4px;margin-bottom:10px;white-space:pre-wrap">{preview}...</div>
  <div style="margin-bottom:12px">{ph_html}</div>
  <a href="/admin/templates/{t.slug}?token={token}"
     style="background:#e94560;color:#fff;padding:6px 14px;border-radius:5px;text-decoration:none;font-size:13px">
    Modifier
  </a>
</div>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Templates — PRESENCE_IA</title>
<style>*{{box-sizing:border-box}}body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;margin:0;color:#1a1a2e}}</style>
</head><body>
{admin_nav(token, "templates")}
<div style="max-width:860px;margin:32px auto;padding:0 20px">
  <h1 style="font-size:18px;margin-bottom:24px">Templates email & SMS</h1>
  {cards}
</div>
</body></html>""")


@router.get("/admin/templates/{slug}", response_class=HTMLResponse)
def admin_template_edit(slug: str, request: Request, db: Session = Depends(get_db)):
    _check(request)
    token = request.query_params.get("token", admin_token())
    t = db_get_template(db, slug)
    if not t:
        raise HTTPException(404, "Template introuvable")

    ph = json.loads(t.placeholders or "[]")
    ph_html = "".join(
        f'<code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px;margin:2px;cursor:pointer" '
        f'onclick="insert(this.innerText)">{p}</code>'
        for p in ph
    )
    subject_field = (
        f"""<div style="margin-bottom:16px">
  <label style="font-size:13px;font-weight:600;display:block;margin-bottom:4px">Objet</label>
  <input name="subject" value="{(t.subject or '').replace('"', '&quot;')}"
         style="width:100%;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px">
</div>"""
        if t.channel == "email" else ""
    )
    html_field = (
        f"""<div style="margin-bottom:16px">
  <label style="font-size:13px;font-weight:600;display:block;margin-bottom:4px">Corps HTML (optionnel)</label>
  <textarea name="body_html" rows="6"
    style="width:100%;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:12px;font-family:monospace">{t.body_html or ''}</textarea>
</div>"""
        if t.channel == "email" else ""
    )

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Modifier — {t.name}</title>
<style>*{{box-sizing:border-box}}body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;margin:0;color:#1a1a2e}}</style>
</head><body>
{admin_nav(token, "templates")}
<div style="max-width:760px;margin:32px auto;padding:0 20px">
  <a href="/admin/templates?token={token}" style="color:#6b7280;font-size:13px;text-decoration:none">&larr; Retour</a>
  <h1 style="font-size:18px;margin:16px 0 4px">{t.name}</h1>
  <div style="font-size:12px;color:#9ca3af;margin-bottom:24px">Slug : {t.slug}</div>

  <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:24px">
    <div style="margin-bottom:16px">
      <label style="font-size:12px;color:#6b7280;display:block;margin-bottom:6px">Placeholders disponibles (cliquer pour injecter)</label>
      <div>{ph_html}</div>
    </div>
    <form id="form">
      {subject_field}
      <div style="margin-bottom:16px">
        <label style="font-size:13px;font-weight:600;display:block;margin-bottom:4px">Corps (texte brut)</label>
        <textarea id="bodyField" name="body" rows="10"
          style="width:100%;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;font-family:monospace">{t.body or ''}</textarea>
      </div>
      {html_field}
      <div style="display:flex;gap:10px;align-items:center">
        <button type="submit"
          style="background:#e94560;color:#fff;border:none;padding:10px 24px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600">
          Enregistrer
        </button>
        <span id="msg" style="font-size:13px;color:#10b981;display:none">Sauvegarde !</span>
      </div>
    </form>
  </div>
</div>
<script>
function insert(txt) {{
  const f = document.getElementById('bodyField');
  const s = f.selectionStart, e = f.selectionEnd;
  f.value = f.value.slice(0,s) + txt + f.value.slice(e);
  f.selectionStart = f.selectionEnd = s + txt.length;
  f.focus();
}}
document.getElementById('form').addEventListener('submit', async function(ev) {{
  ev.preventDefault();
  const fd = new FormData(this);
  const data = Object.fromEntries(fd.entries());
  const r = await fetch('/api/admin/templates/{slug}?token={token}', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(data)
  }});
  if (r.ok) {{
    const msg = document.getElementById('msg');
    msg.style.display = 'inline';
    setTimeout(() => msg.style.display = 'none', 2500);
  }}
}});
</script>
</body></html>""")


@router.post("/api/admin/templates/{slug}")
async def api_update_template(slug: str, request: Request, db: Session = Depends(get_db)):
    _check(request)
    data = await request.json()
    allowed = {"subject", "body", "body_html"}
    updates = {k: v for k, v in data.items() if k in allowed}
    t = db_update_template(db, slug, updates)
    if not t:
        raise HTTPException(404, "Template introuvable")
    return {"ok": True, "slug": t.slug}
