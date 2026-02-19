"""Admin — contenus éditables (home + landing)."""
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_list_content_blocks, set_block

router = APIRouter(tags=["Admin Content"])


def _check_token(request: Request):
    token = (request.query_params.get("token")
             or request.cookies.get("admin_token", ""))
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    return token


def _nav(active: str, token: str) -> str:
    tabs = [
        ("contacts",   "👥 Contacts"),
        ("offers",     "💶 Offres"),
        ("analytics",  "📊 Analytics"),
        ("evidence",   "📸 Preuves"),
        ("headers",    "🖼 Headers"),
        ("content",    "✏️ Contenus"),
        ("send-queue", "📤 Envoi"),
        ("scan",       "🔍 Recherche"),
        ("prospection","🎯 Prospection"),
    ]
    links = "".join(
        f'<a href="/admin/{t}?token={token}" style="padding:10px 18px;border-radius:6px;text-decoration:none;'
        f'font-size:13px;font-weight:{"bold" if t==active else "normal"};'
        f'background:{"#e94560" if t==active else "transparent"};color:#fff">{label}</a>'
        for t, label in tabs
    )
    return f'<div style="background:#0a0a15;border-bottom:1px solid #1a1a2e;padding:0 20px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">' \
           f'<a href="/admin?token={token}" style="color:#e94560;font-weight:bold;font-size:15px;padding:12px 16px 12px 0;text-decoration:none">⚡ PRESENCE_IA</a>' \
           f'{links}</div>'


# Labels des champs fixes (sauf FAQ qui est dynamique)
_FIELD_LABELS = {
    # HOME HERO
    ("home","hero","title"):          "Titre principal",
    ("home","hero","subtitle"):       "Sous-titre",
    ("home","hero","cta_primary"):    "Bouton principal (texte)",
    ("home","hero","cta_secondary"):  "Bouton secondaire (texte)",
    # HOME PROOF STAT
    ("home","proof_stat","stat_1_value"):  "Stat 1 — Valeur",
    ("home","proof_stat","stat_1_label"):  "Stat 1 — Texte",
    ("home","proof_stat","stat_2_value"):  "Stat 2 — Valeur",
    ("home","proof_stat","stat_2_label"):  "Stat 2 — Texte",
    ("home","proof_stat","stat_3_value"):  "Stat 3 — Valeur",
    ("home","proof_stat","stat_3_label"):  "Stat 3 — Texte",
    ("home","proof_stat","source_url_1"):   "Source 1 — URL",
    ("home","proof_stat","source_label_1"): "Source 1 — Texte",
    ("home","proof_stat","source_url_2"):   "Source 2 — URL",
    ("home","proof_stat","source_label_2"): "Source 2 — Texte",
    # HOME PROOF VISUAL
    ("home","proof_visual","title"):    "Titre section",
    ("home","proof_visual","subtitle"): "Sous-titre section",
    ("home","proof_visual","step_1"):   "Étape 1",
    ("home","proof_visual","step_2"):   "Étape 2",
    ("home","proof_visual","step_3"):   "Étape 3",
    ("home","proof_visual","step_4"):   "Étape 4",
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


def _render_field(page_type, section_key, field_key, label, value, show_variants=True):
    """Rendu d'un champ de texte avec bouton Enregistrer."""
    rows = _ROWS.get((page_type, section_key, field_key), 2)
    uid = f"{page_type}__{section_key}__{field_key}"
    variant_inputs = ""
    if show_variants:
        variant_inputs = f"""
    <input id="{uid}__prof" type="text" placeholder="profession (optionnel)"
      style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:5px 8px;border-radius:4px;font-size:11px;width:140px">
    <input id="{uid}__city" type="text" placeholder="ville (optionnel)"
      style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:5px 8px;border-radius:4px;font-size:11px;width:120px">"""

    return f"""<div style="margin-bottom:20px">
  <label style="display:block;color:#aaa;font-size:11px;margin-bottom:4px">{label}</label>
  <textarea id="{uid}" rows="{rows}"
    style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;
           padding:10px;border-radius:6px;font-size:13px;font-family:'Segoe UI',sans-serif;resize:vertical"
  >{value}</textarea>
  <div style="display:flex;gap:8px;margin-top:6px;align-items:center">
    {variant_inputs}
    <button onclick="saveBlock('{page_type}','{section_key}','{field_key}','{uid}',this)"
      style="background:#e94560;color:#fff;border:none;padding:5px 16px;border-radius:4px;cursor:pointer;font-size:12px;font-weight:bold">
      Enregistrer
    </button>
    <span id="{uid}__status" style="font-size:11px;color:#aaa"></span>
  </div>
</div>"""


def _render_section(blocks_by_key: dict, page_type: str, section_key: str, show_variants: bool) -> str:
    """Rendu d'une section (hero/proof_stat/etc.). FAQ est traité séparément."""
    if section_key == "faq":
        return ""  # FAQ sera rendu à part avec son propre système dynamique

    fields = [(fk, label) for (pt, sk, fk), label in _FIELD_LABELS.items()
              if pt == page_type and sk == section_key]

    html = ""
    for field_key, label in fields:
        value = blocks_by_key.get((page_type, section_key, field_key, None, None), "")
        html += _render_field(page_type, section_key, field_key, label, value, show_variants)
    return html


def _render_faq_section(blocks_by_key: dict, page_type: str, show_variants: bool) -> str:
    """Rendu de la section FAQ avec + pour ajouter des items."""
    # Récupérer toutes les FAQ existantes depuis blocks_by_key
    faq_items = {}
    for (pt, sk, fk, prof, city), value in blocks_by_key.items():
        if pt == page_type and sk == "faq" and prof is None and city is None:
            if fk.startswith("q"):
                idx = fk[1:]
                if idx not in faq_items:
                    faq_items[idx] = {}
                faq_items[idx]["q"] = value
            elif fk.startswith("a"):
                idx = fk[1:]
                if idx not in faq_items:
                    faq_items[idx] = {}
                faq_items[idx]["a"] = value

    # S'il n'y a aucune FAQ, créer q1/a1 par défaut
    if not faq_items:
        faq_items = {"1": {"q": "", "a": ""}}

    # Trier par index
    sorted_items = sorted(faq_items.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999)

    html = '<div id="faq-container">'
    for idx, qa in sorted_items:
        q_val = qa.get("q", "")
        a_val = qa.get("a", "")
        html += _render_faq_item(page_type, idx, q_val, a_val, show_variants)
    html += '</div>'

    html += f'''<button onclick="addFaqItem()"
      style="background:#2a2a4e;color:#fff;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-size:13px;margin-top:12px">
      + Ajouter une FAQ
    </button>'''
    return html


def _render_faq_item(page_type: str, idx: str, q_val: str, a_val: str, show_variants: bool) -> str:
    """Rendu d'un item FAQ (question + réponse)."""
    uid_q = f"{page_type}__faq__q{idx}"
    uid_a = f"{page_type}__faq__a{idx}"
    variant_inputs = ""
    if show_variants:
        variant_inputs = f'''
    <input id="{uid_q}__prof" type="text" placeholder="profession (optionnel)"
      style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:5px 8px;border-radius:4px;font-size:11px;width:140px">
    <input id="{uid_q}__city" type="text" placeholder="ville (optionnel)"
      style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:5px 8px;border-radius:4px;font-size:11px;width:120px">'''

    return f'''<div class="faq-item" style="border:1px solid #2a2a4e;border-radius:8px;padding:16px;margin-bottom:16px;background:#0a0a15">
  <label style="display:block;color:#aaa;font-size:11px;margin-bottom:4px">Question {idx}</label>
  <textarea id="{uid_q}" rows="2"
    style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:10px;border-radius:6px;font-size:13px;font-family:'Segoe UI',sans-serif;resize:vertical;margin-bottom:12px"
  >{q_val}</textarea>

  <label style="display:block;color:#aaa;font-size:11px;margin-bottom:4px">Réponse {idx}</label>
  <textarea id="{uid_a}" rows="3"
    style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:10px;border-radius:6px;font-size:13px;font-family:'Segoe UI',sans-serif;resize:vertical"
  >{a_val}</textarea>

  <div style="display:flex;gap:8px;margin-top:8px;align-items:center;flex-wrap:wrap">
    {variant_inputs}
    <button onclick="saveFaqPair('{page_type}','q{idx}','a{idx}','{uid_q}','{uid_a}',this)"
      style="background:#e94560;color:#fff;border:none;padding:5px 16px;border-radius:4px;cursor:pointer;font-size:12px;font-weight:bold">
      Enregistrer
    </button>
    <span id="{uid_q}__status" style="font-size:11px;color:#aaa"></span>
  </div>
</div>'''


@router.get("/admin/content", response_class=HTMLResponse)
def content_admin_page(request: Request, db: Session = Depends(get_db),
                       page: str = "home"):
    token = _check_token(request)
    blocks = db_list_content_blocks(db)
    blocks_by_key = {(b.page_type, b.section_key, b.field_key, b.profession, b.city): b.value
                     for b in blocks}

    # Déterminer les sections à afficher selon la page
    sections_home    = ["hero", "proof_stat", "proof_visual", "cta"]
    sections_landing = ["hero", "proof_stat", "proof_visual"]
    sections = sections_home if page == "home" else sections_landing

    # Masquer profession/ville sur HOME
    show_variants = (page == "landing")

    sections_html = ""
    for sk in sections:
        section_html = _render_section(blocks_by_key, page, sk, show_variants)
        if section_html:
            sections_html += f"""<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:24px;margin-bottom:20px">
<h3 style="color:#e94560;font-size:14px;margin-bottom:20px">{_SECTION_TITLES.get(sk, sk)}</h3>
{section_html}
</div>"""

    # Section FAQ séparée (dynamique)
    faq_html = _render_faq_section(blocks_by_key, page, show_variants)
    sections_html += f"""<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:24px;margin-bottom:20px">
<h3 style="color:#e94560;font-size:14px;margin-bottom:20px">{_SECTION_TITLES.get("faq", "FAQ")}</h3>
{faq_html}
</div>"""

    page_tabs = "".join(
        f'<a href="/admin/content?token={token}&page={p}" style="padding:8px 18px;border-radius:6px;'
        f'text-decoration:none;font-size:13px;font-weight:{"bold" if p==page else "normal"};'
        f'background:{"#1a1a2e" if p==page else "transparent"};color:#fff;border:1px solid {"#e94560" if p==page else "#2a2a4e"}">'
        f'{"🏠 HOME" if p=="home" else "📄 LANDING"}</a>'
        for p in ["home", "landing"]
    )

    variant_note = "" if page == "home" else '''<p style="color:#555;font-size:12px;margin-bottom:24px">
  Les champs profession/ville sont optionnels — laissés vides = texte générique (fallback pour tous).
  Remplis pour créer une variante spécifique ex: "couvreur" + "Rennes".
</p>'''

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
{variant_note}
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
const T = '{token}';
const PAGE = '{page}';
const SHOW_VARIANTS = {str(show_variants).lower()};
let faqCounter = {max([int(k) for k in [x[2][1:] for x in blocks_by_key.keys() if x[0] == page and x[1] == "faq" and x[2].startswith("q")] if k.isdigit()], default=0) + 1};

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

async function saveBlock(page_type, section_key, field_key, uid, btn) {{
  const value    = document.getElementById(uid).value;
  const prof_el  = document.getElementById(uid+'__prof');
  const city_el  = document.getElementById(uid+'__city');
  const profession = prof_el ? (prof_el.value.trim().toLowerCase() || null) : null;
  const city     = city_el ? (city_el.value.trim().toLowerCase() || null) : null;
  const status   = document.getElementById(uid+'__status');
  btn.disabled = true; btn.textContent = '…';
  const r = await fetch('/admin/content/update?token='+T, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{page_type, section_key, field_key, value, profession, city}})
  }});
  const d = await r.json();
  status.textContent = d.ok ? '✅ Enregistré' : '❌ ' + (d.detail || 'Erreur');
  btn.disabled = false; btn.textContent = 'Enregistrer';
  setTimeout(() => {{ status.textContent = ''; }}, 3000);
}}

async function saveFaqPair(page_type, q_key, a_key, uid_q, uid_a, btn) {{
  const q_value = document.getElementById(uid_q).value;
  const a_value = document.getElementById(uid_a).value;
  const prof_el = document.getElementById(uid_q+'__prof');
  const city_el = document.getElementById(uid_q+'__city');
  const profession = prof_el ? (prof_el.value.trim().toLowerCase() || null) : null;
  const city     = city_el ? (city_el.value.trim().toLowerCase() || null) : null;
  const status   = document.getElementById(uid_q+'__status');

  btn.disabled = true; btn.textContent = '…';

  // Enregistrer question
  let r = await fetch('/admin/content/update?token='+T, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{page_type, section_key:'faq', field_key:q_key, value:q_value, profession, city}})
  }});
  if (!r.ok) {{
    status.textContent = '❌ Erreur question';
    btn.disabled = false; btn.textContent = 'Enregistrer';
    return;
  }}

  // Enregistrer réponse
  r = await fetch('/admin/content/update?token='+T, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{page_type, section_key:'faq', field_key:a_key, value:a_value, profession, city}})
  }});

  status.textContent = r.ok ? '✅ Enregistré' : '❌ Erreur réponse';
  btn.disabled = false; btn.textContent = 'Enregistrer';
  setTimeout(() => {{ status.textContent = ''; }}, 3000);
}}

function addFaqItem() {{
  const idx = faqCounter++;
  const container = document.getElementById('faq-container');
  const variant_inputs = SHOW_VARIANTS ? `
    <input id="${{PAGE}}__faq__q${{idx}}__prof" type="text" placeholder="profession (optionnel)"
      style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:5px 8px;border-radius:4px;font-size:11px;width:140px">
    <input id="${{PAGE}}__faq__q${{idx}}__city" type="text" placeholder="ville (optionnel)"
      style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:5px 8px;border-radius:4px;font-size:11px;width:120px">` : '';

  const html = `<div class="faq-item" style="border:1px solid #2a2a4e;border-radius:8px;padding:16px;margin-bottom:16px;background:#0a0a15">
  <label style="display:block;color:#aaa;font-size:11px;margin-bottom:4px">Question ${{idx}}</label>
  <textarea id="${{PAGE}}__faq__q${{idx}}" rows="2"
    style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:10px;border-radius:6px;font-size:13px;font-family:'Segoe UI',sans-serif;resize:vertical;margin-bottom:12px"
  ></textarea>

  <label style="display:block;color:#aaa;font-size:11px;margin-bottom:4px">Réponse ${{idx}}</label>
  <textarea id="${{PAGE}}__faq__a${{idx}}" rows="3"
    style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:10px;border-radius:6px;font-size:13px;font-family:'Segoe UI',sans-serif;resize:vertical"
  ></textarea>

  <div style="display:flex;gap:8px;margin-top:8px;align-items:center;flex-wrap:wrap">
    ${{variant_inputs}}
    <button onclick="saveFaqPair('${{PAGE}}','q${{idx}}','a${{idx}}','${{PAGE}}__faq__q${{idx}}','${{PAGE}}__faq__a${{idx}}',this)"
      style="background:#e94560;color:#fff;border:none;padding:5px 16px;border-radius:4px;cursor:pointer;font-size:12px;font-weight:bold">
      Enregistrer
    </button>
    <span id="${{PAGE}}__faq__q${{idx}}__status" style="font-size:11px;color:#aaa"></span>
  </div>
</div>`;
  container.insertAdjacentHTML('beforeend', html);
}}
</script>
</body></html>""")


@router.post("/admin/content/update")
async def update_content(request: Request, db: Session = Depends(get_db)):
    token = request.query_params.get("token")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")

    data = await request.json()
    page_type   = data.get("page_type")
    section_key = data.get("section_key")
    field_key   = data.get("field_key")
    value       = data.get("value", "")
    profession  = data.get("profession")
    city        = data.get("city")

    if not page_type or not section_key or not field_key:
        raise HTTPException(400, "page_type/section_key/field_key requis")

    set_block(
        db,
        page_type=page_type,
        section_key=section_key,
        field_key=field_key,
        value=value,
        profession=profession,
        city=city,
    )
    return JSONResponse({"ok": True})
