"""Admin — onglet CONTENUS : édition des textes HOME + LANDING depuis l'admin."""
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_list_content_blocks, set_block
from ...models import ContentBlockDB

router = APIRouter(tags=["Admin Content"])


def _check_token(request: Request):
    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    return token


def _nav(active: str, token: str) -> str:
    tabs = [
        ("contacts",  "👥 Contacts"),
        ("offers",    "💶 Offres"),
        ("analytics", "📊 Analytics"),
        ("evidence",  "📸 Preuves"),
        ("content",   "✏️ Contenus"),
        ("send-queue","📤 Envoi"),
    ]
    links = "".join(
        f'<a href="/admin/{t}?token={token}" style="padding:10px 18px;border-radius:6px;text-decoration:none;'
        f'font-size:13px;font-weight:{"bold" if t==active else "normal"};'
        f'background:{"#e94560" if t==active else "transparent"};color:#fff">{label}</a>'
        for t, label in tabs
    )
    return f'''<div style="background:#0a0a15;border-bottom:1px solid #1a1a2e;padding:0 20px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
  <a href="/admin?token={token}" style="color:#e94560;font-weight:bold;font-size:15px;padding:12px 16px 12px 0;text-decoration:none">⚡ PRESENCE_IA</a>
  {links}
</div>'''


_FIELD_LABELS = {
    # HOME HERO
    ("home","hero","title"):         "Titre principal",
    ("home","hero","subtitle"):      "Sous-titre",
    ("home","hero","cta_primary"):   "Bouton principal (texte)",
    ("home","hero","cta_secondary"): "Bouton secondaire (texte)",
    # HOME PROOF STAT
    ("home","proof_stat","stat_1_value"): "Stat 1 — Valeur (ex: 87%)",
    ("home","proof_stat","stat_1_label"): "Stat 1 — Label",
    ("home","proof_stat","stat_2_value"): "Stat 2 — Valeur",
    ("home","proof_stat","stat_2_label"): "Stat 2 — Label",
    ("home","proof_stat","stat_3_value"): "Stat 3 — Valeur",
    ("home","proof_stat","stat_3_label"): "Stat 3 — Label",
    ("home","proof_stat","source_url_1"):   "Source 1 — URL",
    ("home","proof_stat","source_label_1"): "Source 1 — Texte affiché",
    ("home","proof_stat","source_url_2"):   "Source 2 — URL",
    ("home","proof_stat","source_label_2"): "Source 2 — Texte affiché",
    # HOME PROOF VISUAL
    ("home","proof_visual","title"):    "Titre section",
    ("home","proof_visual","subtitle"): "Sous-titre section",
    ("home","proof_visual","step_1"):   "Étape 1",
    ("home","proof_visual","step_2"):   "Étape 2",
    ("home","proof_visual","step_3"):   "Étape 3",
    ("home","proof_visual","step_4"):   "Étape 4",
    # HOME FAQ
    ("home","faq","q1"): "Question 1", ("home","faq","a1"): "Réponse 1",
    ("home","faq","q2"): "Question 2", ("home","faq","a2"): "Réponse 2",
    ("home","faq","q3"): "Question 3", ("home","faq","a3"): "Réponse 3",
    ("home","faq","q4"): "Question 4", ("home","faq","a4"): "Réponse 4",
    # HOME CTA
    ("home","cta","title"):     "Titre CTA final",
    ("home","cta","subtitle"):  "Sous-titre CTA",
    ("home","cta","btn_label"): "Texte bouton",
    # LANDING HERO
    ("landing","hero","title_tpl"):    "Template titre ({city}, {profession})",
    ("landing","hero","subtitle_tpl"): "Template sous-titre ({n_queries}, {n_models}, {models})",
    ("landing","hero","cta_label"):    "Texte bouton CTA",
    # LANDING PROOF VISUAL
    ("landing","proof_visual","mention"): "Mention tests (ex: 9 tests sur 3 jours)",
    # LANDING PROOF STAT
    ("landing","proof_stat","source_url_1"):   "Source 1 — URL",
    ("landing","proof_stat","source_label_1"): "Source 1 — Texte",
    ("landing","proof_stat","source_url_2"):   "Source 2 — URL",
    ("landing","proof_stat","source_label_2"): "Source 2 — Texte",
    # LANDING FAQ
    ("landing","faq","q1"): "Question 1", ("landing","faq","a1"): "Réponse 1",
    ("landing","faq","q2"): "Question 2", ("landing","faq","a2"): "Réponse 2",
}

_SECTION_TITLES = {
    "hero": "🦸 HERO",
    "proof_stat": "📊 Preuves statistiques",
    "proof_visual": "👁 Preuves visuelles / Étapes",
    "faq": "❓ FAQ",
    "cta": "📣 CTA final",
}

_ROWS = {
    ("landing","hero","title_tpl"): 2,
    ("landing","hero","subtitle_tpl"): 2,
    ("home","hero","title"): 3,
}


def _render_section(blocks_by_key: dict, page_type: str, section_key: str, token: str) -> str:
    fields = [(k, v) for (pt, sk, fk), v in _FIELD_LABELS.items()
              if pt == page_type and sk == section_key
              for k in [fk] if True]
    # reconstruct ordered list from _FIELD_LABELS
    fields = [(fk, label) for (pt, sk, fk), label in _FIELD_LABELS.items()
              if pt == page_type and sk == section_key]

    html = ""
    for field_key, label in fields:
        value = blocks_by_key.get((page_type, section_key, field_key, None, None), "")
        rows  = _ROWS.get((page_type, section_key, field_key), 2)
        uid   = f"{page_type}__{section_key}__{field_key}"
        html += f"""<div style="margin-bottom:20px">
  <label style="display:block;color:#aaa;font-size:11px;margin-bottom:4px">{label}</label>
  <textarea id="{uid}" rows="{rows}"
    style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;
           padding:10px;border-radius:6px;font-size:13px;font-family:'Segoe UI',sans-serif;resize:vertical"
  >{value}</textarea>
  <div style="display:flex;gap:8px;margin-top:6px;align-items:center">
    <input id="{uid}__prof" type="text" placeholder="profession (optionnel)"
      style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:5px 8px;border-radius:4px;font-size:11px;width:140px">
    <input id="{uid}__city" type="text" placeholder="ville (optionnel)"
      style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:5px 8px;border-radius:4px;font-size:11px;width:120px">
    <button onclick="saveBlock('{page_type}','{section_key}','{field_key}','{uid}',this)"
      style="background:#e94560;color:#fff;border:none;padding:5px 16px;border-radius:4px;cursor:pointer;font-size:12px;font-weight:bold">
      Enregistrer
    </button>
    <span id="{uid}__status" style="font-size:11px;color:#aaa"></span>
  </div>
</div>"""
    return html


@router.get("/admin/content", response_class=HTMLResponse)
def content_admin_page(request: Request, db: Session = Depends(get_db),
                       page: str = "home"):
    token = _check_token(request)
    blocks = db_list_content_blocks(db)
    blocks_by_key = {(b.page_type, b.section_key, b.field_key, b.profession, b.city): b.value
                     for b in blocks}

    # Déterminer les sections à afficher selon la page
    sections_home    = ["hero", "proof_stat", "proof_visual", "faq", "cta"]
    sections_landing = ["hero", "proof_stat", "proof_visual", "faq"]
    sections = sections_home if page == "home" else sections_landing

    sections_html = ""
    for sk in sections:
        section_html = _render_section(blocks_by_key, page, sk, token)
        if section_html:
            sections_html += f"""<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:24px;margin-bottom:20px">
<h3 style="color:#e94560;font-size:14px;margin-bottom:20px">{_SECTION_TITLES.get(sk, sk)}</h3>
{section_html}
</div>"""

    page_tabs = "".join(
        f'<a href="/admin/content?token={token}&page={p}" style="padding:8px 18px;border-radius:6px;'
        f'text-decoration:none;font-size:13px;font-weight:{"bold" if p==page else "normal"};'
        f'background:{"#1a1a2e" if p==page else "transparent"};color:#fff;border:1px solid {"#e94560" if p==page else "#2a2a4e"}">'
        f'{"🏠 HOME" if p=="home" else "📄 LANDING"}</a>'
        for p in ["home", "landing"]
    )

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Contenus — PRESENCE_IA Admin</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}</style>
</head><body>
{_nav("content", token)}
<div style="max-width:860px;margin:0 auto;padding:24px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
  <h1 style="color:#fff;font-size:18px">✏️ Contenus éditables</h1>
  <div style="display:flex;gap:8px">{page_tabs}</div>
</div>
<p style="color:#555;font-size:12px;margin-bottom:24px">
  Les champs profession/ville sont optionnels — laissés vides = texte générique (fallback pour tous).
  Remplis pour créer une variante spécifique ex: "couvreur" + "Rennes".
</p>
{sections_html}

<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:24px;margin-bottom:20px">
<h3 style="color:#e94560;font-size:14px;margin-bottom:16px">📄 CGV (PDF)</h3>
<p style="color:#9ca3af;font-size:12px;margin-bottom:16px">Le PDF sera accessible sur <code style="color:#e94560">/cgv</code> et lié automatiquement dans le footer de chaque landing.</p>
<input type="file" id="cgv-file" accept="application/pdf" style="display:none" onchange="uploadCGV(this)">
<button onclick="document.getElementById('cgv-file').click()" style="background:#e94560;color:#fff;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-size:13px">
  Uploader les CGV (PDF)
</button>
<span id="cgv-status" style="margin-left:12px;font-size:12px;color:#9ca3af"></span>
</div>
</div><!-- /max-width -->
<script>
async function uploadCGV(input) {{
  const file = input.files[0];
  if (!file) return;
  const status = document.getElementById('cgv-status');
  status.textContent = 'Envoi en cours...';
  try {{
    const r = await fetch('/api/admin/cgv?token={token}', {{method:'POST', body: await file.arrayBuffer(), headers:{{'Content-Type':'application/pdf'}}}});
    const d = await r.json();
    status.textContent = d.ok ? '✅ CGV uploadées (' + Math.round(d.size/1024) + ' ko)' : '❌ Erreur';
  }} catch(e) {{ status.textContent = '❌ ' + e.message; }}
}}
const T = '{token}';
async function saveBlock(page_type, section_key, field_key, uid, btn) {{
  const value    = document.getElementById(uid).value;
  const profession = document.getElementById(uid+'__prof').value.trim().toLowerCase() || null;
  const city     = document.getElementById(uid+'__city').value.trim().toLowerCase() || null;
  const status   = document.getElementById(uid+'__status');
  btn.disabled = true; btn.textContent = '…';
  const r = await fetch('/admin/content/update?token='+T, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{page_type, section_key, field_key, value, profession, city}})
  }});
  const d = await r.json();
  btn.disabled = false; btn.textContent = 'Enregistrer';
  status.textContent = d.ok ? '✅ Enregistré' : '❌ Erreur';
  status.style.color = d.ok ? '#2ecc71' : '#e94560';
  setTimeout(() => {{ status.textContent = ''; }}, 2000);
}}
</script>
</body></html>""")


@router.post("/admin/content/update")
async def content_update(request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    data = await request.json()
    required = ["page_type", "section_key", "field_key", "value"]
    for f in required:
        if f not in data:
            raise HTTPException(400, f"{f} requis")
    set_block(db,
              page_type=data["page_type"],
              section_key=data["section_key"],
              field_key=data["field_key"],
              value=data["value"],
              profession=data.get("profession"),
              city=data.get("city"))
    return {"ok": True}


@router.post("/api/contact-capture")
async def contact_capture(request: Request, db: Session = Depends(get_db)):
    """CTA HOME — formulaire email → ContactDB SUSPECT."""
    from ...models import ContactDB
    from ...database import db_create_contact
    data = await request.json()
    email = (data.get("email") or "").strip()
    if not email or "@" not in email:
        raise HTTPException(400, "Email invalide")
    existing = db.query(ContactDB).filter_by(email=email).first()
    if not existing:
        db_create_contact(db, ContactDB(company_name=email, email=email, status="SUSPECT"))
    return {"ok": True}
