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
        f'background:{"#e94560" if t==active else "#f9fafb"};color:{"#fff" if t==active else "#374151"}">{label}</a>'
        for t, label in tabs
    )
    return f'<div style="background:#fff;border-bottom:1px solid #e5e7eb;padding:0 20px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">' \
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
    ("landing","proof_stat","stat_1_value"):  "Stat 1 — Valeur",
    ("landing","proof_stat","stat_1_label"):  "Stat 1 — Texte",
    ("landing","proof_stat","stat_2_value"):  "Stat 2 — Valeur",
    ("landing","proof_stat","stat_2_label"):  "Stat 2 — Texte",
    ("landing","proof_stat","stat_3_value"):  "Stat 3 — Valeur",
    ("landing","proof_stat","stat_3_label"):  "Stat 3 — Texte",
    ("landing","proof_stat","source_url_1"):   "Source 1 — URL",
    ("landing","proof_stat","source_label_1"): "Source 1 — Texte",
    ("landing","proof_stat","source_url_2"):   "Source 2 — URL",
    ("landing","proof_stat","source_label_2"): "Source 2 — Texte",
    # LANDING PROBLEM
    ("landing","problem","title"):    "Titre",
    ("landing","problem","subtitle"): "Sous-titre / accroche",
    # LANDING PROOF VISUAL
    ("landing","proof_visual","title"):    "Titre section",
    ("landing","proof_visual","subtitle"): "Sous-titre",
    ("landing","proof_visual","step_1"):   "Étape 1",
    ("landing","proof_visual","step_2"):   "Étape 2",
    ("landing","proof_visual","step_3"):   "Étape 3",
    ("landing","proof_visual","step_4"):   "Étape 4",
    ("landing","proof_visual","mention"):  "Mention tests (ex: 9 tests sur 3 jours)",
    # LANDING CTA
    ("landing","cta","title"):     "Titre CTA final",
    ("landing","cta","subtitle"):  "Sous-titre CTA",
    ("landing","cta","btn_label"): "Texte bouton",
    # HOME PROBLEM
    ("home","problem","title"):    "Titre",
    ("home","problem","subtitle"): "Sous-titre / accroche",
}

_SECTION_TITLES = {
    "hero":         "🦸 HERO",
    "proof_stat":   "📊 Preuves statistiques",
    "problem":      "⚠️ Problème / Accroche",
    "proof_visual": "👁 Comment ça marche",
    "evidence":     "📸 Captures d'écran",
    "pricing":      "💶 Tarifs",
    "faq":          "❓ FAQ",
    "cta":          "📣 CTA final",
}

# Catalogue complet des sections disponibles par page
_SECTIONS_CATALOG = {
    "home": [
        {"key": "hero",         "label": "🦸 Hero"},
        {"key": "proof_stat",   "label": "📊 Preuves statistiques"},
        {"key": "problem",      "label": "⚠️ Problème / Accroche"},
        {"key": "proof_visual", "label": "👁 Comment ça marche"},
        {"key": "evidence",     "label": "📸 Captures d'écran"},
        {"key": "pricing",      "label": "💶 Tarifs"},
        {"key": "faq",          "label": "❓ FAQ"},
        {"key": "cta",          "label": "📣 CTA final"},
    ],
    "landing": [
        {"key": "hero",         "label": "🦸 Hero"},
        {"key": "proof_stat",   "label": "📊 Preuves statistiques"},
        {"key": "problem",      "label": "⚠️ Problème / Accroche"},
        {"key": "proof_visual", "label": "👁 Comment ça marche"},
        {"key": "evidence",     "label": "📸 Captures d'écran"},
        {"key": "pricing",      "label": "💶 Tarifs"},
        {"key": "faq",          "label": "❓ FAQ"},
        {"key": "cta",          "label": "📣 CTA final"},
    ],
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
      style="background:#e94560;color:#fff;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-size:13px;margin-top:12px;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
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
      style="background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:5px 8px;border-radius:4px;font-size:11px;width:140px">
    <input id="{uid_q}__city" type="text" placeholder="ville (optionnel)"
      style="background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:5px 8px;border-radius:4px;font-size:11px;width:120px">'''

    return f'''<div class="faq-item" style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:16px;background:#f9fafb;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
  <label style="display:block;color:#6b7280;font-size:11px;margin-bottom:4px">Question {idx}</label>
  <textarea id="{uid_q}" rows="2"
    style="width:100%;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:10px;border-radius:6px;font-size:13px;font-family:'Segoe UI',sans-serif;resize:vertical;margin-bottom:12px"
  >{q_val}</textarea>

  <label style="display:block;color:#6b7280;font-size:11px;margin-bottom:4px">Réponse {idx}</label>
  <textarea id="{uid_a}" rows="3"
    style="width:100%;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:10px;border-radius:6px;font-size:13px;font-family:'Segoe UI',sans-serif;resize:vertical"
  >{a_val}</textarea>

  <div style="display:flex;gap:8px;margin-top:8px;align-items:center;flex-wrap:wrap">
    {variant_inputs}
    <button onclick="saveFaqPair('{page_type}','q{idx}','a{idx}','{uid_q}','{uid_a}',this)"
      style="background:#e94560;color:#fff;border:none;padding:5px 16px;border-radius:4px;cursor:pointer;font-size:12px;font-weight:bold">
      Enregistrer
    </button>
    <span id="{uid_q}__status" style="font-size:11px;color:#6b7280"></span>
  </div>
</div>'''


@router.get("/admin/content", response_class=HTMLResponse)
def content_admin_page(request: Request, db: Session = Depends(get_db),
                       page: str = "home"):
    token = _check_token(request)
    blocks = db_list_content_blocks(db)
    blocks_by_key = {(b.page_type, b.section_key, b.field_key, b.profession, b.city): b.value
                     for b in blocks}

    # Lire la config du layout depuis la DB
    from ...database import db_get_page_layout
    import json as _json
    layout = db_get_page_layout(db, page)
    if layout:
        sections_config = _json.loads(layout.sections_config)
    else:
        # Default si pas encore configuré
        if page == "home":
            sections_config = [
                {"key": "hero", "label": "Hero", "enabled": True, "order": 0},
                {"key": "proof_stat", "label": "Preuves statistiques", "enabled": True, "order": 1},
                {"key": "problem", "label": "Problème", "enabled": True, "order": 2},
                {"key": "proof_visual", "label": "Comment ça marche", "enabled": True, "order": 3},
                {"key": "evidence", "label": "Preuves / Screenshots", "enabled": True, "order": 4},
                {"key": "pricing", "label": "Tarifs", "enabled": True, "order": 5},
                {"key": "faq", "label": "FAQ", "enabled": True, "order": 6},
            ]
        else:
            sections_config = [
                {"key": "hero", "label": "Hero", "enabled": True, "order": 0},
                {"key": "proof_stat", "label": "Preuves statistiques", "enabled": True, "order": 1},
                {"key": "proof_visual", "label": "Preuves visuelles / Étapes", "enabled": True, "order": 2},
                {"key": "faq", "label": "FAQ", "enabled": True, "order": 3},
            ]

    # Filtrer les sections activées et trier par ordre
    sections_enabled = [s for s in sections_config if s.get("enabled", True)]
    sections_enabled.sort(key=lambda s: s.get("order", 0))
    sections = [s["key"] for s in sections_enabled]

    # Masquer profession/ville sur HOME
    show_variants = (page == "landing")

    sections_html = ""
    for sk in sections:
        section_html = _render_section(blocks_by_key, page, sk, show_variants)
        if section_html:
            sections_html += f"""<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
<h3 style="color:#e94560;font-size:14px;margin-bottom:20px">{_SECTION_TITLES.get(sk, sk)}</h3>
{section_html}
</div>"""

    # Section FAQ séparée (dynamique)
    faq_html = _render_faq_section(blocks_by_key, page, show_variants)
    sections_html += f"""<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
<h3 style="color:#e94560;font-size:14px;margin-bottom:20px">{_SECTION_TITLES.get("faq", "FAQ")}</h3>
{faq_html}
</div>"""

    page_tabs = "".join(
        f'<a href="/admin/content?token={token}&page={p}" style="padding:8px 18px;border-radius:6px;'
        f'text-decoration:none;font-size:13px;font-weight:{"bold" if p==page else "normal"};'
        f'background:{"#e94560" if p==page else "#fff"};color:{"#fff" if p==page else "#374151"};border:1px solid {"#e94560" if p==page else "#e5e7eb"}">'
        f'{"🏠 HOME" if p=="home" else "📄 LANDING"}</a>'
        for p in ["home", "landing"]
    )

    variant_note = "" if page == "home" else '''<p style="color:#6b7280;font-size:12px;margin-bottom:24px">
  Les champs profession/ville sont optionnels — laissés vides = texte générique (fallback pour tous).
  Remplis pour créer une variante spécifique ex: "couvreur" + "Rennes".
</p>'''

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Contenus — PRESENCE_IA Admin</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e}}</style>
</head><body>
{_nav("content", token)}
<div style="max-width:860px;margin:0 auto;padding:24px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:12px">
  <h1 style="color:#1a1a2e;font-size:18px">✏️ Contenus éditables</h1>
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
    {page_tabs}
    <button onclick="openLayoutModal()" style="background:#fff;color:#374151;border:1px solid #e5e7eb;padding:8px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:normal">
      ⚙️ Gérer les sections
    </button>
  </div>
</div>
{variant_note}
{sections_html}

<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
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
      style="background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:5px 8px;border-radius:4px;font-size:11px;width:140px">
    <input id="${{PAGE}}__faq__q${{idx}}__city" type="text" placeholder="ville (optionnel)"
      style="background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:5px 8px;border-radius:4px;font-size:11px;width:120px">` : '';

  const html = `<div class="faq-item" style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:16px;background:#f9fafb;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
  <label style="display:block;color:#6b7280;font-size:11px;margin-bottom:4px">Question ${{idx}}</label>
  <textarea id="${{PAGE}}__faq__q${{idx}}" rows="2"
    style="width:100%;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:10px;border-radius:6px;font-size:13px;font-family:'Segoe UI',sans-serif;resize:vertical;margin-bottom:12px"
  ></textarea>

  <label style="display:block;color:#6b7280;font-size:11px;margin-bottom:4px">Réponse ${{idx}}</label>
  <textarea id="${{PAGE}}__faq__a${{idx}}" rows="3"
    style="width:100%;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:10px;border-radius:6px;font-size:13px;font-family:'Segoe UI',sans-serif;resize:vertical"
  ></textarea>

  <div style="display:flex;gap:8px;margin-top:8px;align-items:center;flex-wrap:wrap">
    ${{variant_inputs}}
    <button onclick="saveFaqPair('${{PAGE}}','q${{idx}}','a${{idx}}','${{PAGE}}__faq__q${{idx}}','${{PAGE}}__faq__a${{idx}}',this)"
      style="background:#e94560;color:#fff;border:none;padding:5px 16px;border-radius:4px;cursor:pointer;font-size:12px;font-weight:bold">
      Enregistrer
    </button>
    <span id="${{PAGE}}__faq__q${{idx}}__status" style="font-size:11px;color:#6b7280"></span>
  </div>
</div>`;
  container.insertAdjacentHTML('beforeend', html);
}}

// ── Layout management (modal + drag & drop) ──────────────────────────────────

let layoutSections = [];

async function openLayoutModal() {{
  const modal = document.getElementById('layout-modal');
  modal.style.display = 'flex';
  await loadLayoutSections();
}}

function closeLayoutModal() {{
  document.getElementById('layout-modal').style.display = 'none';
}}

async function loadLayoutSections() {{
  const r = await fetch(`/api/admin/content/layout?page=${{PAGE}}&token=${{T}}`);
  const d = await r.json();
  layoutSections = d.sections;
  renderLayoutSections();
}}

function renderLayoutSections() {{
  const container = document.getElementById('sections-list');
  container.innerHTML = layoutSections.map((s, idx) => `
    <div class="section-item" draggable="true" data-index="${{idx}}"
      style="background:#fff;border:1px solid #e5e7eb;border-radius:6px;padding:12px 16px;margin-bottom:8px;display:flex;align-items:center;gap:12px;cursor:move;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
      <span style="color:#9ca3af;font-size:16px">☰</span>
      <label style="display:flex;align-items:center;gap:8px;flex:1;cursor:pointer;color:#1a1a2e;font-size:14px">
        <input type="checkbox" ${{s.enabled ? 'checked' : ''}} onchange="toggleSection(${{idx}})"
          style="width:16px;height:16px;accent-color:#e94560">
        ${{s.label}}
      </label>
    </div>
  `).join('');

  // Setup drag & drop
  const items = container.querySelectorAll('.section-item');
  items.forEach(item => {{
    item.addEventListener('dragstart', handleDragStart);
    item.addEventListener('dragover', handleDragOver);
    item.addEventListener('drop', handleDrop);
    item.addEventListener('dragend', handleDragEnd);
  }});
}}

let draggedItem = null;

function handleDragStart(e) {{
  draggedItem = this;
  this.style.opacity = '0.4';
}}

function handleDragOver(e) {{
  e.preventDefault();
  return false;
}}

function handleDrop(e) {{
  e.preventDefault();
  if (draggedItem !== this) {{
    const fromIdx = parseInt(draggedItem.dataset.index);
    const toIdx = parseInt(this.dataset.index);
    const [moved] = layoutSections.splice(fromIdx, 1);
    layoutSections.splice(toIdx, 0, moved);
    layoutSections.forEach((s, i) => s.order = i);
    renderLayoutSections();
  }}
  return false;
}}

function handleDragEnd() {{
  this.style.opacity = '1';
}}

function toggleSection(idx) {{
  layoutSections[idx].enabled = !layoutSections[idx].enabled;
}}

function showAddSectionForm() {{
  document.getElementById('add-section-form').style.display = 'block';
  document.getElementById('add-section-btn').style.display = 'none';
  document.getElementById('new-section-key').value = '';
  document.getElementById('new-section-label').value = '';
}}

function cancelAddSection() {{
  document.getElementById('add-section-form').style.display = 'none';
  document.getElementById('add-section-btn').style.display = 'block';
}}

function addNewSection() {{
  const key = document.getElementById('new-section-key').value.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_');
  const label = document.getElementById('new-section-label').value.trim();

  if (!key || !label) {{
    alert('Clé et label obligatoires');
    return;
  }}

  if (layoutSections.find(s => s.key === key)) {{
    alert('Cette clé existe déjà');
    return;
  }}

  const maxOrder = Math.max(...layoutSections.map(s => s.order), -1);
  layoutSections.push({{
    key: key,
    label: label,
    enabled: true,
    order: maxOrder + 1,
    custom: true
  }});

  renderLayoutSections();
  cancelAddSection();
}}

async function saveLayout() {{
  const btn = document.getElementById('save-layout-btn');
  btn.disabled = true;
  btn.textContent = 'Enregistrement...';
  try {{
    const r = await fetch(`/api/admin/content/layout?token=${{T}}`, {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{page_type: PAGE, sections: layoutSections}})
    }});
    if (r.ok) {{
      btn.textContent = '✅ Enregistré';
      setTimeout(() => {{
        closeLayoutModal();
        window.location.reload();
      }}, 800);
    }} else {{
      btn.textContent = '❌ Erreur';
      btn.disabled = false;
    }}
  }} catch(e) {{
    btn.textContent = '❌ ' + e.message;
    btn.disabled = false;
  }}
}}
</script>

<!-- Modal gestion layout -->
<div id="layout-modal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;align-items:center;justify-content:center">
  <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:32px;width:90%;max-width:500px;max-height:80vh;overflow-y:auto;box-shadow:0 10px 25px rgba(0,0,0,0.2)">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
      <h2 style="color:#1a1a2e;font-size:18px">⚙️ Gérer les sections — {page.upper()}</h2>
      <button onclick="closeLayoutModal()" style="background:transparent;border:none;color:#9ca3af;font-size:24px;cursor:pointer;padding:0;line-height:1">&times;</button>
    </div>

    <p style="color:#6b7280;font-size:13px;margin-bottom:20px">
      Glisse-dépose pour réorganiser · Décoche pour masquer une section
    </p>

    <div id="sections-list"></div>

    <div id="add-section-form" style="display:none;background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-top:16px">
      <h3 style="color:#e94560;font-size:14px;margin-bottom:12px">Nouvelle section personnalisée</h3>
      <label style="display:block;color:#6b7280;font-size:12px;margin-bottom:4px">Clé (ex: temoignages, tarifs...)</label>
      <input id="new-section-key" type="text" placeholder="ma_section"
        style="width:100%;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:8px 10px;border-radius:4px;font-size:13px;margin-bottom:12px">
      <label style="display:block;color:#6b7280;font-size:12px;margin-bottom:4px">Label affiché</label>
      <input id="new-section-label" type="text" placeholder="Ma section"
        style="width:100%;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:8px 10px;border-radius:4px;font-size:13px;margin-bottom:12px">
      <div style="display:flex;gap:8px">
        <button onclick="addNewSection()" style="flex:1;background:#e94560;color:#fff;border:none;padding:8px;border-radius:4px;cursor:pointer;font-size:13px">
          Ajouter
        </button>
        <button onclick="cancelAddSection()" style="background:#fff;color:#374151;border:1px solid #e5e7eb;padding:8px 16px;border-radius:4px;cursor:pointer;font-size:13px">
          Annuler
        </button>
      </div>
    </div>

    <button onclick="showAddSectionForm()" id="add-section-btn"
      style="width:100%;background:#fff;border:1px dashed #e5e7eb;color:#6b7280;padding:10px;border-radius:6px;cursor:pointer;font-size:13px;margin-top:16px">
      + Ajouter une section personnalisée
    </button>

    <div style="display:flex;gap:12px;margin-top:24px">
      <button id="save-layout-btn" onclick="saveLayout()"
        style="flex:1;background:#e94560;color:#fff;border:none;padding:12px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:bold">
        Enregistrer
      </button>
      <button onclick="closeLayoutModal()"
        style="background:#fff;color:#374151;border:1px solid #e5e7eb;padding:12px 24px;border-radius:6px;cursor:pointer;font-size:14px">
        Annuler
      </button>
    </div>
  </div>
</div>

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


# ── Gestion du layout (ordre + enabled des sections) ────────────────────────

@router.get("/api/admin/content/layout")
def get_layout(page: str, db: Session = Depends(get_db), token: str = ""):
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")

    from ...database import db_get_page_layout
    import json

    # Sections sauvegardées en DB (ordre + enabled)
    layout = db_get_page_layout(db, page)
    saved = json.loads(layout.sections_config) if layout else []
    saved_keys = {s["key"] for s in saved}

    # Catalogue complet pour cette page
    catalog = _SECTIONS_CATALOG.get(page, [])

    # Résultat = sections sauvegardées (ordre conservé) + sections du catalogue non encore ajoutées
    result = list(saved)
    max_order = max((s.get("order", 0) for s in result), default=-1)
    for cat_s in catalog:
        if cat_s["key"] not in saved_keys:
            max_order += 1
            result.append({
                "key":     cat_s["key"],
                "label":   cat_s["label"],
                "enabled": False,
                "order":   max_order,
            })

    return JSONResponse({"sections": result})


@router.post("/api/admin/content/layout")
async def save_layout(request: Request, db: Session = Depends(get_db)):
    token = request.query_params.get("token")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    
    from ...database import db_upsert_page_layout
    import json
    data = await request.json()
    page_type = data.get("page_type")
    sections = data.get("sections", [])
    
    if not page_type or page_type not in ["home", "landing"]:
        raise HTTPException(400, "page_type invalide")
    
    db_upsert_page_layout(db, page_type, json.dumps(sections))
    return JSONResponse({"ok": True})


@router.delete("/api/admin/content/layout")
async def reset_layout(request: Request, db: Session = Depends(get_db)):
    """Supprime le layout pour forcer le rechargement de la config par défaut"""
    token = request.query_params.get("token")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")

    page_type = request.query_params.get("page_type", "home")
    if page_type not in ["home", "landing"]:
        raise HTTPException(400, "page_type invalide")

    from ...database import db_get_page_layout
    from ...models import PageLayoutDB
    layout = db.query(PageLayoutDB).filter_by(page_type=page_type).first()
    if layout:
        db.delete(layout)
        db.commit()

    return JSONResponse({"ok": True, "message": f"Layout {page_type} réinitialisé"})
