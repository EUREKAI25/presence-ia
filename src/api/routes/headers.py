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
from ._nav import admin_nav

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

    url = f"/{HEADERS_SUBPATH}/{filename}"
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

    # Villes manquantes : dans V3ProspectDB mais sans header (ni directe ni préfecture)
    from ...models import V3ProspectDB, CityHeaderDB
    try:
        from ...api.routes.v3 import DEPT_PREFECTURE
    except Exception:
        DEPT_PREFECTURE = {}
    img_cities = {h.city for h in headers}
    contact_cities = {(c.city or "").lower().strip().replace(" ", "-")
                      for c in db.query(V3ProspectDB).all() if c.city}
    # Dériver le département depuis le code postal
    def _dept_from_cp(cp: str) -> str:
        if not cp:
            return ""
        cp = cp.strip()
        if cp.startswith("971") or cp.startswith("972") or cp.startswith("973") or cp.startswith("974"):
            return cp[:3]
        if cp.startswith("20"):  # Corse — approximation
            return "2A" if int(cp) < 20200 else "2B"
        return cp[:2]

    from ...models import SireneSuspectDB
    city_dept: dict = {}
    for city_l in contact_cities:
        if city_l in img_cities:
            continue
        ville_search       = city_l.replace("-", " ")   # "aspach michelbach"
        ville_search_hyph  = city_l                      # "aspach-michelbach"
        from sqlalchemy import or_ as _or
        # 1. Via SireneSuspectDB.departement (champ direct)
        s = db.query(SireneSuspectDB).filter(
            _or(
                SireneSuspectDB.ville.ilike(ville_search),
                SireneSuspectDB.ville.ilike(ville_search_hyph),
            ),
            SireneSuspectDB.departement.isnot(None),
        ).first()
        if s and s.departement:
            city_dept[city_l] = s.departement
            continue
        # 2. Via SireneSuspectDB.code_postal (fallback)
        s2 = db.query(SireneSuspectDB).filter(
            _or(
                SireneSuspectDB.ville.ilike(ville_search),
                SireneSuspectDB.ville.ilike(ville_search_hyph),
            ),
            SireneSuspectDB.code_postal.isnot(None),
        ).first()
        if s2 and s2.code_postal:
            d = _dept_from_cp(s2.code_postal)
            if d:
                city_dept[city_l] = d
                continue
        # 3. Via V3ProspectDB.notes (format "dept:XX")
        c_row = db.query(V3ProspectDB).filter(
            V3ProspectDB.city.ilike(ville_search),
            V3ProspectDB.notes.isnot(None),
        ).first()
        if c_row and c_row.notes:
            import re
            m = re.search(r"dept:(\w+)", c_row.notes)
            if m:
                city_dept[city_l] = m.group(1)

    missing_items = []
    for city_l in sorted(contact_cities):
        if city_l in img_cities:
            continue
        dept = city_dept.get(city_l, "")
        pref = DEPT_PREFECTURE.get(dept, "").lower().replace(" ", "-") if dept else ""
        if pref and pref in img_cities:
            continue  # couverte par la préfecture
        missing_items.append((city_l, dept, pref))

    if missing_items:
        missing_rows = "".join(
            f'<tr>'
            f'<td style="padding:6px 10px;font-size:12px;color:#fff">{c.replace("-"," ").title()}</td>'
            f'<td style="padding:6px 10px;font-size:11px;color:#9ca3af">{d or "?"}</td>'
            f'<td style="padding:6px 10px;font-size:11px;color:#f59e0b">'
            f'{"→ ajouter " + p.replace("-"," ").title() + " (préfecture dept " + d + ")" if p else ("dept " + d + " — préfecture inconnue") if d else "code postal absent de la DB"}'
            f'</td>'
            f'<td style="padding:6px 10px">'
            f'<button onclick="document.getElementById(\'h-city\').value=\'{c}\';document.getElementById(\'h-city\').focus()" '
            f'style="background:#2a2a4e;color:#aaa;border:1px solid #3a3a5e;border-radius:4px;padding:3px 8px;font-size:10px;cursor:pointer">'
            f'Remplir ↑</button></td>'
            f'</tr>'
            for c, d, p in missing_items
        )
        missing_panel = f"""<div style="background:#1a1500;border:1px solid #f59e0b40;border-radius:8px;padding:16px;margin-bottom:24px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
  <span style="color:#f59e0b;font-weight:700;font-size:13px">⚠️ {len(missing_items)} ville(s) sans image</span>
  <span style="color:#6b7280;font-size:11px">Ces contacts seront grisés dans la liste</span>
</div>
<table style="width:100%;border-collapse:collapse">
<thead><tr>
  <th style="text-align:left;color:#6b7280;font-size:10px;padding:4px 10px;border-bottom:1px solid #2a1a00">Ville</th>
  <th style="text-align:left;color:#6b7280;font-size:10px;padding:4px 10px;border-bottom:1px solid #2a1a00">Dept</th>
  <th style="text-align:left;color:#6b7280;font-size:10px;padding:4px 10px;border-bottom:1px solid #2a1a00">Fallback préfecture</th>
  <th style="border-bottom:1px solid #2a1a00"></th>
</tr></thead>
<tbody>{missing_rows}</tbody>
</table>
</div>"""
    else:
        missing_panel = '<div style="background:#001a0a;border:1px solid #2ecc7140;border-radius:8px;padding:12px;margin-bottom:24px;color:#2ecc71;font-size:12px">✓ Toutes les villes de contacts ont une image</div>'

    cards = ""
    for h in headers:
        img_url = h.url if h.url.startswith("http") else h.url
        cards += f"""<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <span style="color:#fff;font-weight:bold;font-size:14px">{h.city.title()}</span>
    <button onclick="deleteHeader('{h.city}',this)"
      style="background:#4a1a1a;color:#e94560;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px">
      🗑 Supprimer
    </button>
  </div>
  <a href="{img_url}" target="_blank">
    <img src="{img_url}" style="width:100%;border-radius:6px;max-height:160px;object-fit:cover" loading="lazy"
         onerror="this.style.display='none'">
  </a>
  <div style="font-size:10px;color:#555;margin-top:6px;word-break:break-all">{img_url}</div>
  <div style="margin-top:8px">
    <button onclick="navigator.clipboard.writeText('{img_url}')"
      style="background:#0f0f1a;color:#aaa;border:1px solid #2a2a4e;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px">
      📋 Copier URL
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
{admin_nav(token, "headers")}
<div style="max-width:960px;margin:0 auto;padding:24px">

{missing_panel}

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
  const file = fileInput.files[0];
  const allowed = ['image/jpeg','image/png','image/webp','image/gif'];
  if (!allowed.includes(file.type)) {{
    status.textContent = '❌ Format invalide — utilisez JPG, PNG ou WEBP uniquement'; return;
  }}
  if (file.size > 20 * 1024 * 1024) {{
    status.textContent = '❌ Fichier trop lourd (' + (file.size/1024/1024).toFixed(1) + ' Mo) — max 20 Mo'; return;
  }}
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

</script>
</body></html>""")
