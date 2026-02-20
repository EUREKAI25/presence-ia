"""
CMS Blocks — textes éditables home + landing.
GET  /api/cms/blocks?prefix=landing.&locale=fr
POST /api/cms/block/upsert {key, value, locale}
GET  /admin/cms         → UI admin
"""
import os
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from ...database import get_db

log = logging.getLogger(__name__)
router = APIRouter(tags=["CMS"])

# ── Seed initial ───────────────────────────────────────────────────────────────
_SEED: list = [
    # Home
    ("home.hero.title",         "Votre entreprise visible\ndans ChatGPT, Gemini et Claude",        "fr"),
    ("home.hero.subtitle",      "Testez gratuitement si les IA vous recommandent. Sinon, on corrige ça.", "fr"),
    ("home.hero.cta_primary",   "Tester ma visibilité",  "fr"),
    ("home.hero.cta_secondary", "Voir comment ça marche","fr"),
    # Landing couvreur (exemple)
    ("landing.couvreur.hero.title",    "Les meilleurs couvreurs de {city} recommandés par l'IA", "fr"),
    ("landing.couvreur.hero.subtitle", "Découvrez quel artisan apparaît en premier dans ChatGPT, Claude et Gemini.", "fr"),
    ("landing.couvreur.cta",           "Vérifier ma présence", "fr"),
    # Landing générique
    ("landing.generic.hero.title",    "Votre {profession} visible dans les IA", "fr"),
    ("landing.generic.hero.subtitle", "Testez si vous apparaissez dans ChatGPT, Claude et Gemini à {city}.", "fr"),
    ("landing.generic.cta",           "Lancer l'audit gratuit", "fr"),
]


def seed_cms_blocks(db: Session):
    """Insère les blocs CMS par défaut si absents."""
    from ...models import CmsBlockDB
    for key, value, locale in _SEED:
        exists = db.query(CmsBlockDB).filter_by(key=key, locale=locale).first()
        if not exists:
            db.add(CmsBlockDB(key=key, value=value, locale=locale))
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        log.warning("seed_cms_blocks: %s", e)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _check_token(request: Request) -> str:
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
        ("cms",        "🧩 CMS"),
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
    return (
        f'<div style="background:#fff;border-bottom:1px solid #e5e7eb;padding:0 20px;'
        f'display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
        f'<a href="/admin?token={token}" style="color:#e94560;font-weight:bold;font-size:15px;'
        f'padding:12px 16px 12px 0;text-decoration:none">⚡ PRESENCE_IA</a>'
        f'{links}</div>'
    )


# ── Schémas ────────────────────────────────────────────────────────────────────

class CmsUpsertRequest(BaseModel):
    key: str
    value: str
    locale: str = "fr"


# ── Endpoints API ──────────────────────────────────────────────────────────────

@router.get("/api/cms/blocks")
def cms_list_blocks(
    prefix: str = Query("", description="Filtrer par préfixe de clé, ex: landing."),
    locale: str = Query("fr"),
    db: Session = Depends(get_db),
):
    """Liste les blocs CMS filtrés par préfixe + locale."""
    from ...models import CmsBlockDB
    q = db.query(CmsBlockDB).filter(CmsBlockDB.locale == locale)
    if prefix:
        q = q.filter(CmsBlockDB.key.startswith(prefix))
    blocks = q.order_by(CmsBlockDB.key).all()
    return [
        {"key": b.key, "value": b.value, "locale": b.locale, "updated_at": b.updated_at.isoformat()}
        for b in blocks
    ]


@router.post("/api/cms/block/upsert")
def cms_upsert_block(req: CmsUpsertRequest, db: Session = Depends(get_db)):
    """Crée ou met à jour un bloc CMS (key + locale = clé composite)."""
    from ...models import CmsBlockDB
    existing = db.query(CmsBlockDB).filter_by(key=req.key, locale=req.locale).first()
    if existing:
        existing.value = req.value
        existing.updated_at = datetime.utcnow()
    else:
        db.add(CmsBlockDB(key=req.key, value=req.value, locale=req.locale))
    db.commit()
    return {
        "success": True,
        "result": {"key": req.key, "locale": req.locale},
        "message": f"Bloc '{req.key}' [{req.locale}] sauvegardé",
        "error": None,
    }


# ── UI Admin ───────────────────────────────────────────────────────────────────

@router.get("/admin/cms", response_class=HTMLResponse)
def cms_admin_page(request: Request, db: Session = Depends(get_db)):
    token = _check_token(request)
    from ...models import CmsBlockDB

    # Seed si vide
    count = db.query(CmsBlockDB).count()
    if count == 0:
        seed_cms_blocks(db)

    all_blocks = db.query(CmsBlockDB).order_by(CmsBlockDB.key).all()

    # Grouper par préfixe (home / landing / etc.)
    groups: dict = {}
    for b in all_blocks:
        prefix = b.key.split(".")[0]
        groups.setdefault(prefix, []).append(b)

    rows_html = ""
    for prefix, blocks in sorted(groups.items()):
        rows_html += f'<tr><td colspan="4" style="background:#f3f4f6;font-size:12px;font-weight:bold;color:#6b7280;padding:8px 12px;text-transform:uppercase;letter-spacing:1px">{prefix}</td></tr>'
        for b in blocks:
            rows_html += f"""<tr>
  <td style="padding:10px 12px;font-size:12px;font-family:monospace;color:#374151">{b.key}</td>
  <td style="padding:10px 12px;font-size:12px;color:#6b7280">{b.locale}</td>
  <td style="padding:6px 12px">
    <textarea id="v_{b.id}" style="width:100%;min-height:48px;border:1px solid #e5e7eb;border-radius:4px;padding:6px;font-size:12px;resize:vertical;font-family:inherit"
      onchange="markDirty('{b.id}')">{b.value}</textarea>
  </td>
  <td style="padding:10px 12px;text-align:center">
    <button onclick="saveBlock('{b.id}','{b.key}','{b.locale}')"
      id="btn_{b.id}"
      style="background:#e94560;color:#fff;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;font-size:12px">
      Sauver
    </button>
  </td>
</tr>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CMS — PRESENCE_IA Admin</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e;line-height:1.5}}
table{{width:100%;border-collapse:collapse}}
tr:hover td{{background:#fef5f7}}
th{{background:#f3f4f6;padding:10px 12px;text-align:left;font-size:12px;color:#6b7280;font-weight:600;border-bottom:1px solid #e5e7eb}}
td{{border-bottom:1px solid #f3f4f6;vertical-align:top}}
.toast{{position:fixed;bottom:24px;right:24px;background:#1a1a2e;color:#fff;padding:12px 20px;border-radius:8px;font-size:13px;display:none;z-index:999}}
</style>
</head><body>
{_nav("cms", token)}
<div style="max-width:1100px;margin:0 auto;padding:24px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:12px">
    <h1 style="font-size:18px;color:#1a1a2e">🧩 CMS Blocks ({len(all_blocks)} blocs)</h1>
    <div style="display:flex;gap:10px">
      <button onclick="addBlock()"
        style="background:#e94560;color:#fff;border:none;padding:8px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:bold">
        + Nouveau bloc
      </button>
      <button onclick="seedBlocks()"
        style="background:#fff;border:1px solid #e5e7eb;color:#374151;padding:8px 18px;border-radius:6px;cursor:pointer;font-size:13px">
        Réinitialiser seed
      </button>
    </div>
  </div>

  <!-- Formulaire nouveau bloc -->
  <div id="new-block-form" style="display:none;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:24px;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
    <h3 style="font-size:14px;margin-bottom:14px;color:#1a1a2e">Nouveau bloc CMS</h3>
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:10px;margin-bottom:10px">
      <div>
        <label style="font-size:11px;color:#6b7280;display:block;margin-bottom:4px">Clé *</label>
        <input id="new-key" type="text" placeholder="landing.hero.title"
          style="width:100%;border:1px solid #e5e7eb;border-radius:4px;padding:8px;font-size:13px">
      </div>
      <div>
        <label style="font-size:11px;color:#6b7280;display:block;margin-bottom:4px">Locale</label>
        <select id="new-locale" style="width:100%;border:1px solid #e5e7eb;border-radius:4px;padding:8px;font-size:13px">
          <option value="fr">fr</option>
          <option value="en">en</option>
          <option value="es">es</option>
          <option value="it">it</option>
        </select>
      </div>
    </div>
    <div style="margin-bottom:14px">
      <label style="font-size:11px;color:#6b7280;display:block;margin-bottom:4px">Valeur *</label>
      <textarea id="new-value" rows="3" placeholder="Texte du bloc..."
        style="width:100%;border:1px solid #e5e7eb;border-radius:4px;padding:8px;font-size:13px;resize:vertical"></textarea>
    </div>
    <div style="display:flex;gap:10px">
      <button onclick="createBlock()"
        style="background:#e94560;color:#fff;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px">
        Créer
      </button>
      <button onclick="document.getElementById('new-block-form').style.display='none'"
        style="background:#fff;border:1px solid #e5e7eb;color:#374151;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px">
        Annuler
      </button>
    </div>
  </div>

  <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.06)">
    <table>
      <thead>
        <tr>
          <th>Clé</th>
          <th style="width:60px">Locale</th>
          <th>Valeur</th>
          <th style="width:80px">Action</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const T = '{token}';
function toast(msg, ok=true) {{
  const el = document.getElementById('toast');
  el.textContent = (ok ? '✅ ' : '❌ ') + msg;
  el.style.display = 'block';
  el.style.background = ok ? '#1a1a2e' : '#c0392b';
  setTimeout(() => el.style.display = 'none', 2500);
}}
function markDirty(id) {{
  const btn = document.getElementById('btn_'+id);
  if (btn) {{ btn.style.background = '#ff7043'; btn.textContent = 'Sauver *'; }}
}}
async function saveBlock(id, key, locale) {{
  const val = document.getElementById('v_'+id).value;
  const btn = document.getElementById('btn_'+id);
  btn.disabled = true; btn.textContent = '…';
  const r = await fetch('/api/cms/block/upsert', {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{key, value: val, locale}})
  }});
  const d = await r.json();
  if (d.success) {{
    btn.style.background = '#27ae60'; btn.textContent = '✓ Sauvé';
    btn.disabled = false;
    setTimeout(() => {{
      btn.style.background = '#e94560'; btn.textContent = 'Sauver';
    }}, 2000);
    toast('Sauvé : ' + key);
  }} else {{
    btn.disabled = false; btn.textContent = 'Réessayer';
    toast('Erreur', false);
  }}
}}
function addBlock() {{
  document.getElementById('new-block-form').style.display = 'block';
  document.getElementById('new-key').focus();
}}
async function createBlock() {{
  const key = document.getElementById('new-key').value.trim();
  const value = document.getElementById('new-value').value;
  const locale = document.getElementById('new-locale').value;
  if (!key) {{ toast('Clé requise', false); return; }}
  const r = await fetch('/api/cms/block/upsert', {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{key, value, locale}})
  }});
  const d = await r.json();
  if (d.success) {{ toast('Créé : ' + key); setTimeout(() => location.reload(), 800); }}
  else toast('Erreur', false);
}}
async function seedBlocks() {{
  if (!confirm('Réinitialiser les blocs seed (sans écraser les existants) ?')) return;
  toast('Seed en cours…');
  setTimeout(() => location.reload(), 1000);
}}
</script>
</body></html>""")
