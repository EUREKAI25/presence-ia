"""
Evidence — screenshots de preuves partagés par ville+profession.
Pillow : resize 1600px wide → center crop 16:9 → WEBP.

POST /api/evidence/upload?profession=...&city=...&provider=openai|anthropic|gemini
GET  /api/evidence/latest?profession=...&city=...&limit=6
GET  /admin/evidence            → onglet admin avec preview + delete
POST /admin/evidence/{id}/delete
"""
import logging
import os
import random
import string
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_or_create_evidence, db_get_evidence, jl, jd

log = logging.getLogger(__name__)
router = APIRouter(tags=["Evidence"])

VALID_PROVIDERS = {"openai", "anthropic", "gemini"}

PROVIDER_LABELS = {"openai": "ChatGPT", "anthropic": "Claude", "gemini": "Gemini"}


def _evidence_dir() -> Path:
    root = Path(os.getenv("UPLOADS_DIR", str(Path(__file__).parent.parent.parent.parent / "dist"))).parent
    return root / "dist" / "evidence"


def _rand(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _base_url() -> str:
    return os.getenv("BASE_URL", "http://localhost:8001")


def _process_image(src: Path, dest: Path) -> bool:
    """Resize to 1600px wide → center crop 16:9 → save as WEBP. Returns True on success."""
    try:
        from PIL import Image
        img = Image.open(src).convert("RGB")
        # 1. Resize width to 1600px, keep aspect ratio
        w, h = img.size
        if w != 1600:
            ratio = 1600 / w
            img = img.resize((1600, int(h * ratio)), Image.LANCZOS)
        w, h = img.size
        # 2. Center crop to 16:9
        target_h = int(w * 9 / 16)
        if h >= target_h:
            top  = (h - target_h) // 2
            img  = img.crop((0, top, w, top + target_h))
        # 3. Save as WEBP
        img.save(dest, "WEBP", quality=85)
        return True
    except Exception as e:
        log.warning("Pillow processing failed: %s", e)
        return False


# ── Upload ───────────────────────────────────────────────────────────────────

@router.post("/api/evidence/upload")
def upload_evidence(
    profession: str = Query(...),
    city:       str = Query(...),
    provider:   str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if provider not in VALID_PROVIDERS:
        raise HTTPException(400, f"provider doit être parmi {VALID_PROVIDERS}")

    ts       = datetime.utcnow()
    rand_id  = _rand()
    ts_str   = ts.strftime('%Y-%m-%d_%H%M')
    filename = f"{ts_str}_{provider}_{rand_id}.png"
    proc_fn  = f"{ts_str}_{provider}_{rand_id}.webp"

    dest_dir = _evidence_dir() / profession.lower() / city.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Sauvegarder l'original
    dest_orig = dest_dir / filename
    dest_orig.write_bytes(file.file.read())

    # Traitement Pillow → WEBP 16:9
    dest_proc = dest_dir / proc_fn
    processed_ok = _process_image(dest_orig, dest_proc)

    base = _base_url()
    prefix = f"{base}/dist/evidence/{profession.lower()}/{city.lower()}"
    url           = f"{prefix}/{filename}"
    processed_url = f"{prefix}/{proc_fn}" if processed_ok else None

    # Upsert enregistrement DB
    ev = db_get_or_create_evidence(db, profession, city)
    images = jl(ev.images)
    images.insert(0, {
        "ts":              ts.isoformat(),
        "provider":        provider,
        "filename":        filename,
        "url":             url,
        "processed_url":   processed_url,
        "processed_fn":    proc_fn if processed_ok else None,
    })
    ev.images = jd(images)
    db.commit()

    log.info("Evidence uploadée : %s / %s / %s", profession, city, filename)
    return {
        "url": url,
        "filename": filename,
        "provider": provider,
        "processed_url": processed_url,
    }


# ── Latest ───────────────────────────────────────────────────────────────────

@router.get("/api/evidence/latest")
def get_latest_evidence(
    profession: str = Query(...),
    city:       str = Query(...),
    limit:      int = Query(6, ge=1, le=50),
    db: Session = Depends(get_db),
):
    ev = db_get_evidence(db, profession, city)
    if not ev:
        return []
    return jl(ev.images)[:limit]


# ── Admin onglet ──────────────────────────────────────────────────────────────

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


@router.get("/admin/evidence", response_class=HTMLResponse)
def evidence_admin_page(request: Request, db: Session = Depends(get_db)):
    from ...database import db_get_evidence as _get_ev
    import sqlalchemy as sa
    from ...models import CityEvidenceDB

    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")

    # Récupérer toutes les entrées evidence
    all_ev = db.query(CityEvidenceDB).all()

    sections = ""
    total_imgs = 0
    for ev in all_ev:
        images = jl(ev.images)
        if not images:
            continue
        total_imgs += len(images)
        cards = ""
        for i, img in enumerate(images):
            orig_url = img.get("url", "")
            proc_url = img.get("processed_url", "")
            provider = PROVIDER_LABELS.get(img.get("provider",""), img.get("provider",""))
            ts_disp  = img.get("ts","")[:16].replace("T"," ")
            fn       = img.get("filename","")

            orig_html = f'<a href="{orig_url}" target="_blank"><img src="{orig_url}" style="width:100%;border-radius:4px;max-height:120px;object-fit:cover" loading="lazy"></a>' if orig_url else '<div style="background:#0f0f1a;height:120px;border-radius:4px;display:flex;align-items:center;justify-content:center;color:#555;font-size:11px">Pas d\'original</div>'
            proc_html = f'<a href="{proc_url}" target="_blank"><img src="{proc_url}" style="width:100%;border-radius:4px;max-height:120px;object-fit:cover" loading="lazy"></a>' if proc_url else '<div style="background:#0f0f1a;height:120px;border-radius:4px;display:flex;align-items:center;justify-content:center;color:#555;font-size:11px">Pas de processed</div>'

            cards += f"""<div style="background:#0f0f1a;border:1px solid #2a2a4e;border-radius:6px;padding:12px;position:relative">
  <div style="font-size:10px;color:#888;margin-bottom:8px">{ts_disp} — {provider}</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
    <div>
      <div style="font-size:9px;color:#555;margin-bottom:3px">Original</div>
      {orig_html}
    </div>
    <div>
      <div style="font-size:9px;color:#2ecc71;margin-bottom:3px">WEBP 16:9</div>
      {proc_html}
    </div>
  </div>
  <div style="font-size:10px;color:#555;word-break:break-all;margin-bottom:6px">{fn}</div>
  <button onclick="delEvidence('{ev.profession}','{ev.city}',{i},this)"
    style="background:#4a1a1a;color:#e94560;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px;width:100%">
    🗑 Supprimer
  </button>
</div>"""

        sections += f"""<div style="margin-bottom:32px">
<h3 style="color:#fff;font-size:14px;margin-bottom:12px">
  {ev.profession.title()} — {ev.city.title()}
  <span style="color:#555;font-size:11px;margin-left:8px">({len(images)} image{"s" if len(images)!=1 else ""})</span>
</h3>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px">
{cards}
</div>
</div>"""

    empty = '<p style="color:#555;font-size:13px;padding:40px;text-align:center">Aucune preuve uploadée</p>' if not sections else ""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Preuves — PRESENCE_IA Admin</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
input,select{{background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px 12px;border-radius:6px;font-size:13px}}</style>
</head><body>
{_nav("evidence", token)}
<div style="max-width:1200px;margin:0 auto;padding:24px">

<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:28px;gap:24px;flex-wrap:wrap">
  <h1 style="color:#fff;font-size:18px;align-self:center">📸 Preuves ({total_imgs} images)</h1>
  <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px;min-width:380px">
    <h3 style="color:#fff;font-size:14px;margin-bottom:14px">Uploader des preuves</h3>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">
      <div>
        <label style="color:#aaa;font-size:11px;display:block;margin-bottom:4px">Profession *</label>
        <input id="up-profession" type="text" placeholder="couvreur" style="width:100%">
      </div>
      <div>
        <label style="color:#aaa;font-size:11px;display:block;margin-bottom:4px">Ville *</label>
        <input id="up-city" type="text" placeholder="rennes" style="width:100%">
      </div>
    </div>
    <div style="margin-bottom:10px">
      <label style="color:#aaa;font-size:11px;display:block;margin-bottom:4px">Modèle IA</label>
      <select id="up-provider" style="width:100%">
        <option value="openai">ChatGPT (OpenAI)</option>
        <option value="anthropic">Claude (Anthropic)</option>
        <option value="gemini">Gemini (Google)</option>
      </select>
    </div>
    <div style="margin-bottom:14px">
      <label style="color:#aaa;font-size:11px;display:block;margin-bottom:4px">Images (PNG/JPG — multiple)</label>
      <input id="up-files" type="file" accept="image/*" multiple style="width:100%">
    </div>
    <button onclick="uploadEvidence(this)"
      style="background:#e94560;color:#fff;border:none;padding:10px 24px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:bold;width:100%">
      Uploader
    </button>
    <div id="up-status" style="margin-top:8px;font-size:12px;color:#aaa"></div>
  </div>
</div>

{sections}{empty}
</div>
<script>
const T = '{token}';
async function uploadEvidence(btn) {{
  const profession = document.getElementById('up-profession').value.trim().toLowerCase();
  const city       = document.getElementById('up-city').value.trim().toLowerCase();
  const provider   = document.getElementById('up-provider').value;
  const files      = document.getElementById('up-files').files;
  const status     = document.getElementById('up-status');
  if (!profession || !city) {{ status.textContent = '⚠️ Profession et ville requises'; return; }}
  if (!files.length) {{ status.textContent = '⚠️ Sélectionner au moins un fichier'; return; }}
  btn.disabled = true; btn.textContent = '…';
  let done = 0, errors = 0;
  for (const file of files) {{
    const form = new FormData();
    form.append('file', file);
    try {{
      const r = await fetch(
        `/api/evidence/upload?profession=${{encodeURIComponent(profession)}}&city=${{encodeURIComponent(city)}}&provider=${{provider}}&token=`+T,
        {{ method: 'POST', body: form }}
      );
      if (r.ok) done++; else errors++;
    }} catch(e) {{ errors++; }}
    status.textContent = `${{done}}/${{files.length}} uploadé(s)…`;
  }}
  btn.disabled = false; btn.textContent = 'Uploader';
  status.textContent = `✅ ${{done}} image(s) uploadée(s)${{errors ? ' — ' + errors + ' erreur(s)' : ''}}`;
  if (done > 0) setTimeout(() => location.reload(), 1200);
}}
async function delEvidence(profession, city, idx, btn) {{
  if(!confirm('Supprimer cette image ?')) return;
  btn.disabled = true; btn.textContent = '…';
  const r = await fetch('/admin/evidence/delete?token='+T, {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{profession, city, index: idx}})
  }});
  const d = await r.json();
  if(d.ok) location.reload();
  else {{ btn.disabled = false; btn.textContent = '❌ Erreur'; }}
}}
</script>
</body></html>""")


@router.post("/admin/evidence/delete")
async def evidence_delete(request: Request, db: Session = Depends(get_db)):
    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403)
    data       = await request.json()
    profession = data.get("profession", "")
    city       = data.get("city", "")
    index      = data.get("index", -1)

    ev = db_get_evidence(db, profession, city)
    if not ev:
        raise HTTPException(404)
    images = jl(ev.images)
    if index < 0 or index >= len(images):
        raise HTTPException(400, "Index invalide")

    img = images[index]
    # Supprimer les fichiers physiques
    base_dir = _evidence_dir() / profession.lower() / city.lower()
    for key in ("filename", "processed_fn"):
        fn = img.get(key)
        if fn:
            f = base_dir / fn
            if f.exists():
                f.unlink()

    images.pop(index)
    ev.images = jd(images)
    db.commit()
    return {"ok": True}
