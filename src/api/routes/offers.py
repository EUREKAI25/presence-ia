"""Admin — onglet OFFRES (OfferDB via offers_module)."""
import json
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db

router = APIRouter(tags=["Admin Offers"])


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


@router.get("/admin/offers", response_class=HTMLResponse)
def offers_page(request: Request, db: Session = Depends(get_db)):
    token = _check_token(request)
    from offers_module.database import db_list_offers
    from offers_module.models import OfferDB

    # Inclure offres inactives aussi
    all_offers = db.query(OfferDB).order_by(OfferDB.price).all()

    cards = ""
    for o in all_offers:
        features = json.loads(o.features or "[]") if isinstance(o.features, str) else (o.features or [])
        features_txt = "\n".join(features)
        active_lbl = "✅ Active" if o.active else "❌ Inactive"
        price_display = f"{int(o.price)}€" if o.price == int(o.price) else f"{o.price}€"
        cards += f"""<div style="background:#1a1a2e;border:1px solid {'#2ecc71' if o.active else '#2a2a4e'};border-radius:10px;padding:24px;margin-bottom:20px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
  <h3 style="color:#fff">{o.name} — {price_display}</h3>
  <span style="color:{'#2ecc71' if o.active else '#888'};font-size:12px">{active_lbl}</span>
</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px">
  <div>
    <label style="color:#aaa;font-size:11px;display:block;margin-bottom:3px">Nom</label>
    <input id="name-{o.id}" value="{o.name}" style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:13px">
  </div>
  <div>
    <label style="color:#aaa;font-size:11px;display:block;margin-bottom:3px">Prix (€)</label>
    <input id="price-{o.id}" type="number" step="0.01" value="{o.price}" style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:13px">
  </div>
  <div>
    <label style="color:#aaa;font-size:11px;display:block;margin-bottom:3px">Stripe Price ID</label>
    <input id="stripe-{o.id}" value="{o.stripe_price_id or ''}" placeholder="price_..." style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:13px">
  </div>
  <div>
    <label style="color:#aaa;font-size:11px;display:block;margin-bottom:3px">Profession cible</label>
    <input id="profession-{o.id}" value="{o.profession or ''}" placeholder="couvreur (vide=générique)" style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:13px">
  </div>
  <div style="display:flex;align-items:flex-end;padding-bottom:2px">
    <label style="display:flex;align-items:center;gap:6px;color:#aaa;font-size:12px;cursor:pointer">
      <input id="active-{o.id}" type="checkbox" {'checked' if o.active else ''} style="width:auto"> Active
    </label>
  </div>
</div>
<div>
  <label style="color:#aaa;font-size:11px;display:block;margin-bottom:3px">Points inclus (un par ligne)</label>
  <textarea id="features-{o.id}" rows="4" style="width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:12px;font-family:monospace">{features_txt}</textarea>
</div>
<div style="margin-top:12px;display:flex;gap:10px;align-items:center">
  <button onclick="saveOffer('{o.id}',this)" style="background:#e94560;color:#fff;border:none;padding:8px 22px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:bold">💾 Enregistrer</button>
  <span id="status-{o.id}" style="font-size:12px;color:#aaa"></span>
</div>
</div>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Offres — PRESENCE_IA Admin</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}</style>
</head><body>
{_nav("offers", token)}
<div style="max-width:960px;margin:0 auto;padding:24px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
  <h1 style="color:#fff;font-size:18px">💶 Offres</h1>
  <button onclick="newOffer(this)" style="background:#2ecc71;color:#0f0f1a;border:none;padding:8px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:bold">+ Nouvelle offre</button>
</div>
<p style="color:#aaa;font-size:13px;margin-bottom:24px">Les offres actives apparaissent sur la home et les landing pages.</p>
{cards}
</div>
<script>
const T = '{token}';
async function saveOffer(id, btn) {{
  btn.disabled = true; btn.textContent = '…';
  const g = k => document.getElementById(k+'-'+id);
  const features = g('features').value.split('\\n').map(s=>s.trim()).filter(Boolean);
  const data = {{
    name:           g('name').value,
    price:          parseFloat(g('price').value) || 0,
    stripe_price_id: g('stripe').value || null,
    profession:     g('profession').value || null,
    active:         g('active').checked,
    features,
  }};
  const r = await fetch('/api/admin/offers/'+id+'?token='+T, {{
    method:'PUT', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)
  }});
  btn.disabled = false; btn.textContent = '💾 Enregistrer';
  const st = document.getElementById('status-'+id);
  st.textContent = r.ok ? '✅ Enregistré' : '❌ Erreur';
  setTimeout(()=>{{ st.textContent=''; }}, 2000);
}}
async function newOffer(btn) {{
  const name = prompt('Nom de l\\'offre :'); if (!name) return;
  const price = parseFloat(prompt('Prix (€) :')); if (!price) return;
  btn.disabled = true;
  const r = await fetch('/api/admin/offers?token='+T, {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{name, price, features:[], active:true}})
  }});
  btn.disabled = false;
  if (r.ok) location.reload();
  else alert('Erreur création');
}}
</script>
</body></html>""")
