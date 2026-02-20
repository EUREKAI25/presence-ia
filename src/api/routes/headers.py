"""
City Headers — image header par ville.

POST /api/headers/upload?city=...         → upload + processing 16:9 WEBP
GET  /api/headers/{city}                  → URL publique du header
DELETE /api/headers/{city}?token=...      → suppression
GET  /admin/headers                       → onglet admin
"""
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_header, db_upsert_header, db_delete_header, db_list_headers

log = logging.getLogger(__name__)
router = APIRouter(tags=["Headers"])

HEADERS_SUBPATH = "dist/headers"


def _headers_dir() -> Path:
    root = Path(os.getenv("UPLOADS_DIR", str(Path(__file__).parent.parent.parent.parent / "dist"))).parent
    d = root / HEADERS_SUBPATH
    d.mkdir(parents=True, exist_ok=True)
    return d


def _base_url() -> str:
    return os.getenv("BASE_URL", "http://localhost:8001")


def _check_token(request: Request):
    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    return token


def _process_header(src: Path, dest: Path) -> bool:
    """Resize + center-crop 16:9 → WEBP 2400px."""
    try:
        from PIL import Image
        img = Image.open(src).convert("RGB")
        w, h = img.size
        if w != 2400:
            ratio = 2400 / w
            img = img.resize((2400, int(h * ratio)), Image.LANCZOS)
        w, h = img.size
        target_h = int(w * 9 / 16)
        if h >= target_h:
            top = (h - target_h) // 2
            img = img.crop((0, top, w, top + target_h))
        img.save(dest, "WEBP", quality=88)
        return True
    except Exception as e:
        log.warning("Pillow header processing failed: %s", e)
        return False


def _nav(active: str, token: str) -> str:
    tabs = [
        ("contacts",  "👥 Contacts"),
        ("offers",    "💶 Offres"),
        ("analytics", "📊 Analytics"),
        ("evidence",  "📸 Preuves"),
        ("headers",   "🖼 Headers"),
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


# ── API publique ──────────────────────────────────────────────────────────────

@router.get("/api/headers/{city}")
def get_header(city: str, db: Session = Depends(get_db)):
    row = db_get_header(db, city)
    if not row:
        raise HTTPException(404, f"Aucun header pour la ville '{city}'")
    return {"city": row.city, "url": row.url, "filename": row.filename}


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/api/headers/upload")
def upload_header(
    city: str = Query(...),
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    _check_token(request)
    city_slug = city.lower().strip().replace(" ", "-")
    filename  = f"{city_slug}.webp"
    dest      = _headers_dir() / filename

    # Sauvegarder d'abord le fichier brut en tmp
    raw_bytes = file.file.read()
    tmp = _headers_dir() / f"_tmp_{city_slug}.orig"
    tmp.write_bytes(raw_bytes)

    # Traitement 16:9 WEBP 2400px
    ok = _process_header(tmp, dest)
    tmp.unlink(missing_ok=True)

    if not ok:
        # Fallback : sauvegarder tel quel
        dest.write_bytes(raw_bytes)
        log.warning("Header %s sauvegardé sans traitement Pillow", city_slug)

    url = f"{_base_url()}/{HEADERS_SUBPATH}/{filename}"
    row = db_upsert_header(db, city_slug, filename, url)
    log.info("Header uploadé pour %s → %s", city_slug, dest)
    return {"city": row.city, "url": row.url, "filename": row.filename}


@router.delete("/api/headers/{city}")
def delete_header_api(city: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    row = db_get_header(db, city)
    if not row:
        raise HTTPException(404)
    f = _headers_dir() / row.filename
    if f.exists():
        f.unlink()
    db_delete_header(db, city)
    return {"ok": True}


# ── Admin page ────────────────────────────────────────────────────────────────

@router.get("/admin/headers", response_class=HTMLResponse)
def headers_admin_page(request: Request, db: Session = Depends(get_db)):
    token = _check_token(request)
    headers = db_list_headers(db)

    # Ville actuellement définie pour la landing
    from ...database import get_block
    current_landing_city = get_block(db, "landing", "config", "header_city", default="")

    cards = ""
    for h in headers:
        is_landing = (h.city == current_landing_city)
        badge = '<span style="background:#e94560;color:#fff;font-size:10px;padding:2px 7px;border-radius:10px;margin-left:8px">Landing</span>' if is_landing else ""
        use_btn_style = "background:#1a4a1a;color:#4ade80" if is_landing else "background:#0f0f1a;color:#aaa;border:1px solid #2a2a4e"
        use_btn_label = "✅ Landing active" if is_landing else "🖼 Utiliser pour la landing"
        cards += f"""<div style="background:#1a1a2e;border:1px solid {'#e94560' if is_landing else '#2a2a4e'};border-radius:8px;padding:16px;position:relative">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <span style="color:#fff;font-weight:bold;font-size:14px">{h.city.title()}{badge}</span>
    <button onclick="deleteHeader('{h.city}',this)"
      style="background:#4a1a1a;color:#e94560;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px">
      🗑 Supprimer
    </button>
  </div>
  <a href="{h.url}" target="_blank">
    <img src="{h.url}" style="width:100%;border-radius:6px;max-height:160px;object-fit:cover" loading="lazy"
         onerror="this.style.display='none'">
  </a>
  <div style="font-size:10px;color:#555;margin-top:6px;word-break:break-all">{h.url}</div>
  <div style="display:flex;gap:6px;margin-top:8px">
    <button onclick="setLandingHeader('{h.city}',this)"
      style="{use_btn_style};border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px;flex:1">
      {use_btn_label}
    </button>
    <button onclick="navigator.clipboard.writeText('{h.url}')"
      style="background:#0f0f1a;color:#aaa;border:1px solid #2a2a4e;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px">
      📋
    </button>
  </div>
</div>"""

    empty = '<p style="color:#555;font-size:13px;padding:40px;text-align:center">Aucun header défini</p>' if not headers else ""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Headers — PRESENCE_IA Admin</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
input{{background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px 12px;border-radius:6px;font-size:13px}}</style>
</head><body>
{_nav("headers", token)}
<div style="max-width:960px;margin:0 auto;padding:24px">

<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;gap:24px;flex-wrap:wrap">
  <div>
    <h1 style="color:#fff;font-size:18px;margin-bottom:4px">🖼 Headers par ville</h1>
    <p style="color:#aaa;font-size:12px">Format attendu : 2400×1350 (16:9). L'image est automatiquement redimensionnée et convertie en WEBP.</p>
    <p style="color:#555;font-size:11px;margin-top:4px">Stockage : /dist/headers/{{city}}.webp — accessible via /dist/headers/{{city}}.webp</p>
  </div>
  <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px;min-width:320px">
    <h3 style="color:#fff;font-size:14px;margin-bottom:14px">Uploader / remplacer un header</h3>
    <div style="margin-bottom:10px">
      <label style="color:#aaa;font-size:11px;display:block;margin-bottom:4px">Ville *</label>
      <input id="h-city" type="text" placeholder="rennes" style="width:100%">
    </div>
    <div style="margin-bottom:14px">
      <label style="color:#aaa;font-size:11px;display:block;margin-bottom:4px">Image (PNG/JPG/WEBP)</label>
      <input id="h-file" type="file" accept="image/*" style="width:100%">
    </div>
    <button onclick="uploadHeader(this)"
      style="background:#e94560;color:#fff;border:none;padding:10px 24px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:bold;width:100%">
      Uploader
    </button>
    <div id="upload-status" style="margin-top:8px;font-size:12px;color:#aaa"></div>
  </div>
</div>

<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px">
{cards}
</div>
{empty}
</div>

<script>
const T = '{token}';
async function uploadHeader(btn) {{
  const city = document.getElementById('h-city').value.trim();
  const fileInput = document.getElementById('h-file');
  const status = document.getElementById('upload-status');
  if (!city) {{ status.textContent = '⚠️ Ville requise'; return; }}
  if (!fileInput.files.length) {{ status.textContent = '⚠️ Fichier requis'; return; }}
  btn.disabled = true; btn.textContent = '…';
  status.textContent = 'Upload en cours…';
  const form = new FormData();
  form.append('file', fileInput.files[0]);
  const r = await fetch('/api/headers/upload?city=' + encodeURIComponent(city) + '&token=' + T, {{
    method: 'POST', body: form
  }});
  btn.disabled = false; btn.textContent = 'Uploader';
  if (r.ok) {{ status.textContent = '✅ Uploadé'; location.reload(); }}
  else {{ const d = await r.json(); status.textContent = '❌ ' + (d.detail || 'Erreur'); }}
}}
async function deleteHeader(city, btn) {{
  if (!confirm('Supprimer le header de ' + city + ' ?')) return;
  btn.disabled = true; btn.textContent = '…';
  const r = await fetch('/api/headers/' + city + '?token=' + T, {{ method: 'DELETE' }});
  if (r.ok) location.reload();
  else {{ btn.disabled = false; btn.textContent = '❌ Erreur'; }}
}}
async function setLandingHeader(city, btn) {{
  btn.disabled = true; btn.textContent = '…';
  const r = await fetch('/admin/content/update?token=' + T, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{page_type:'landing', section_key:'config', field_key:'header_city', value:city, profession:null, city:null}})
  }});
  if (r.ok) location.reload();
  else {{ btn.disabled = false; btn.textContent = '❌ Erreur'; }}
}}
</script>
</body></html>""")
