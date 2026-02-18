"""Admin — onglet OFFRES (PricingConfig éditable)."""
import json
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_list_pricing, db_get_pricing, db_update_pricing
from ...models import PricingConfigDB

router = APIRouter(tags=["Admin Offers"])


def _check_token(request: Request):
    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    return token


def _nav(active: str, token: str) -> str:
    tabs = [
        ("contacts", "👥 Contacts"),
        ("offers", "💶 Offres"),
        ("analytics", "📊 Analytics"),
        ("evidence", "📸 Preuves"),
        ("send-queue", "📤 Envoi"),
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


@router.get("/admin/offers", response_class=HTMLResponse)
def offers_page(request: Request, db: Session = Depends(get_db)):
    token = _check_token(request)
    offers = db.query(PricingConfigDB).order_by(PricingConfigDB.sort_order).all()

    cards = ""
    for o in offers:
        bullets = json.loads(o.bullets or "[]")
        bullets_txt = "\n".join(bullets)
        highlighted = "✅" if o.highlighted else "☐"
        active_lbl  = "✅ Active" if o.active else "❌ Inactive"
        cards += f"""<div style="background:#1a1a2e;border:1px solid {'#e94560' if o.highlighted else '#2a2a4e'};border-radius:10px;padding:24px;margin-bottom:20px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
  <h3 style="color:#fff">{o.key} — {o.title}</h3>
  <span style="color:#2ecc71;font-size:12px">{active_lbl}</span>
</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px">
  <div>
    <label style="color:#aaa;font-size:11px;display:block;margin-bottom:3px">Titre</label>
    <input id="title-{o.key}" value="{o.title}" style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:13px">
  </div>
  <div>
    <label style="color:#aaa;font-size:11px;display:block;margin-bottom:3px">Prix affiché</label>
    <input id="price_text-{o.key}" value="{o.price_text}" style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:13px">
  </div>
  <div>
    <label style="color:#aaa;font-size:11px;display:block;margin-bottom:3px">Prix € (Stripe)</label>
    <input id="price_eur-{o.key}" type="number" step="0.01" value="{o.price_eur}" style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:13px">
  </div>
  <div>
    <label style="color:#aaa;font-size:11px;display:block;margin-bottom:3px">Stripe Price ID</label>
    <input id="stripe_price_id-{o.key}" value="{o.stripe_price_id or ''}" placeholder="price_..." style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:13px">
  </div>
  <div>
    <label style="color:#aaa;font-size:11px;display:block;margin-bottom:3px">Ordre (sort)</label>
    <input id="sort_order-{o.key}" type="number" value="{o.sort_order}" style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:13px">
  </div>
  <div style="display:flex;gap:16px;align-items:flex-end;padding-bottom:2px">
    <label style="display:flex;align-items:center;gap:6px;color:#aaa;font-size:12px;cursor:pointer">
      <input id="highlighted-{o.key}" type="checkbox" {'checked' if o.highlighted else ''} style="width:auto"> Recommandé
    </label>
    <label style="display:flex;align-items:center;gap:6px;color:#aaa;font-size:12px;cursor:pointer">
      <input id="active-{o.key}" type="checkbox" {'checked' if o.active else ''} style="width:auto"> Active
    </label>
  </div>
</div>
<div>
  <label style="color:#aaa;font-size:11px;display:block;margin-bottom:3px">Points inclus (un par ligne)</label>
  <textarea id="bullets-{o.key}" rows="5" style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:12px;font-family:monospace">{bullets_txt}</textarea>
</div>
<div style="margin-top:12px;display:flex;gap:10px;align-items:center">
  <button onclick="saveOffer('{o.key}',this)" style="background:#e94560;color:#fff;border:none;padding:8px 22px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:bold">💾 Enregistrer</button>
  <span id="status-{o.key}" style="font-size:12px;color:#aaa"></span>
</div>
</div>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Offres — PRESENCE_IA Admin</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}</style>
</head><body>
{_nav("offers", token)}
<div style="max-width:960px;margin:0 auto;padding:24px">
<h1 style="color:#fff;font-size:18px;margin-bottom:8px">💶 Offres tarifaires</h1>
<p style="color:#aaa;font-size:13px;margin-bottom:24px">Modifie les offres ici — la landing page et la home les lisent en temps réel depuis la base.</p>
{cards}
</div>
<script>
const T = '{token}';
async function saveOffer(key, btn) {{
  btn.disabled = true; btn.textContent = '…';
  const el = id => document.getElementById(id+'-'+key);
  const bullets = el('bullets').value.split('\\n').map(s=>s.trim()).filter(s=>s);
  const data = {{
    title:           el('title').value,
    price_text:      el('price_text').value,
    price_eur:       parseFloat(el('price_eur').value) || 0,
    stripe_price_id: el('stripe_price_id').value || null,
    sort_order:      parseInt(el('sort_order').value) || 0,
    highlighted:     el('highlighted').checked,
    active:          el('active').checked,
    bullets:         JSON.stringify(bullets),
  }};
  const r = await fetch('/admin/offers/'+key+'/update?token='+T, {{
    method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)
  }});
  const res = await r.json();
  btn.disabled = false; btn.textContent = '💾 Enregistrer';
  document.getElementById('status-'+key).textContent = res.ok ? '✅ Enregistré' : '❌ Erreur';
  setTimeout(() => {{ document.getElementById('status-'+key).textContent = ''; }}, 2000);
}}
</script>
</body></html>""")


@router.post("/admin/offers/{key}/update")
async def offer_update(key: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    o = db_get_pricing(db, key.upper())
    if not o:
        raise HTTPException(404, "Offre introuvable")
    data = await request.json()
    allowed = ["title", "price_text", "price_eur", "stripe_price_id", "sort_order", "highlighted", "active", "bullets"]
    updates = {k: v for k, v in data.items() if k in allowed}
    db_update_pricing(db, o, **updates)
    return {"ok": True}


@router.get("/api/pricing")
def api_pricing(db: Session = Depends(get_db)):
    """Endpoint public — retourne les offres actives pour la landing."""
    offers = db_list_pricing(db)
    result = []
    for o in offers:
        result.append({
            "key": o.key,
            "title": o.title,
            "price_text": o.price_text,
            "price_eur": o.price_eur,
            "bullets": json.loads(o.bullets or "[]"),
            "highlighted": o.highlighted,
            "stripe_price_id": o.stripe_price_id,
        })
    return result
