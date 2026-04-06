"""Admin — onglet OFFRES (OfferDB via offers_module)."""
import json
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db
from ._nav import admin_nav

router = APIRouter(tags=["Admin Offers"])


def _check_token(request: Request):
    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    return token


@router.get("/admin/offers", response_class=HTMLResponse)
def offers_page(request: Request, db: Session = Depends(get_db)):
    token = _check_token(request)
    from offers_module.database import db_list_offers
    from offers_module.models import OfferDB

    # Inclure offres inactives aussi
    all_offers = db.query(OfferDB).order_by(OfferDB.price).all()

    inp  = "width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:13px"
    ta   = "width:100%;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:8px;border-radius:4px;font-size:12px;font-family:monospace"
    lbl  = "color:#aaa;font-size:11px;display:block;margin-bottom:3px"
    sect = "color:#6366f1;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin:18px 0 10px;border-top:1px solid #2a2a4e;padding-top:14px"

    cards = ""
    for o in all_offers:
        features = json.loads(o.features or "[]") if isinstance(o.features, str) else (o.features or [])
        features_txt = "\n".join(features)
        meta     = json.loads(o.meta or "{}") if isinstance(o.meta, str) else (o.meta or {})
        mods_txt = json.dumps(meta.get("eurkai_modules", []), ensure_ascii=False, indent=2)
        not_inc  = "\n".join(meta.get("not_included", []))
        price_display = f"{int(o.price)}€" if o.price == int(o.price) else f"{o.price}€"

        cards += f"""<div style="background:#1a1a2e;border:1px solid {'#2ecc71' if o.active else '#2a2a4e'};border-radius:10px;padding:24px;margin-bottom:20px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
  <h3 style="color:#fff">{o.name} — {price_display}</h3>
  <span style="color:{'#2ecc71' if o.active else '#888'};font-size:12px">{'✅ Active' if o.active else '❌ Inactive'}</span>
</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:16px">
  <div><label style="{lbl}">Nom</label><input id="name-{o.id}" value="{o.name}" style="{inp}"></div>
  <div><label style="{lbl}">Prix (€)</label><input id="price-{o.id}" type="number" step="1" value="{int(o.price)}" style="{inp}"></div>
  <div><label style="{lbl}">Stripe Price ID</label><input id="stripe-{o.id}" value="{o.stripe_price_id or ''}" placeholder="price_..." style="{inp}"></div>
  <div><label style="{lbl}">Durée (mois)</label><input id="duration-{o.id}" type="number" value="{meta.get('duration_months', 0)}" style="{inp}"></div>
  <div><label style="{lbl}">Fréquence exec.</label>
    <select id="freq-{o.id}" style="{inp}">
      {''.join(f'<option value="{v}" {"selected" if meta.get("execution_frequency") == v else ""}>{v}</option>' for v in ["once","monthly","quarterly"])}
    </select>
  </div>
  <div><label style="{lbl}">Quantité exec.</label><input id="qty-{o.id}" type="number" value="{meta.get('execution_qty', 1)}" style="{inp}"></div>
  <div style="display:flex;align-items:flex-end;padding-bottom:8px">
    <label style="display:flex;align-items:center;gap:6px;color:#aaa;font-size:12px;cursor:pointer">
      <input id="active-{o.id}" type="checkbox" {'checked' if o.active else ''} style="width:auto"> Active (visible home)
    </label>
  </div>
</div>
<div><label style="{lbl}">Points inclus (un par ligne)</label>
  <textarea id="features-{o.id}" rows="4" style="{ta}">{features_txt}</textarea>
</div>
<div style="{sect}">Textes commerciaux</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div><label style="{lbl}">Résumé closer</label>
    <textarea id="closer-{o.id}" rows="3" style="{ta}">{meta.get('description_closer', '')}</textarea>
  </div>
  <div><label style="{lbl}">Résumé checkout</label>
    <textarea id="checkout-{o.id}" rows="3" style="{ta}">{meta.get('description_checkout', '')}</textarea>
  </div>
</div>
<div style="margin-top:10px"><label style="{lbl}">Cible</label>
  <input id="target-{o.id}" value="{meta.get('target', '')}" style="{inp}">
</div>
<div style="margin-top:10px"><label style="{lbl}">Résultat promis</label>
  <input id="result-{o.id}" value="{meta.get('result_promised', '')}" style="{inp}">
</div>
<div style="margin-top:10px"><label style="{lbl}">Non inclus (un par ligne)</label>
  <textarea id="notinc-{o.id}" rows="3" style="{ta}">{not_inc}</textarea>
</div>
<div style="margin-top:10px"><label style="{lbl}">Argumentaire upgrade</label>
  <input id="upgrade-{o.id}" value="{meta.get('upgrade_pitch', '')}" style="{inp}">
</div>
<div style="{sect}">Modules EURKAI (JSON)</div>
<div><textarea id="modules-{o.id}" rows="6" style="{ta}">{mods_txt}</textarea></div>
<div style="margin-top:14px;display:flex;gap:10px;align-items:center">
  <button onclick="saveOffer('{o.id}',this)" style="background:#e94560;color:#fff;border:none;padding:8px 22px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:bold">💾 Enregistrer</button>
  <span id="status-{o.id}" style="font-size:12px;color:#aaa"></span>
</div>
</div>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Offres — PRESENCE_IA Admin</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}</style>
</head><body>
{admin_nav(token, "offers")}
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
  let eurkai_modules = [];
  try {{ eurkai_modules = JSON.parse(g('modules').value); }} catch(e) {{}}
  const not_included = g('notinc').value.split('\\n').map(s=>s.trim()).filter(Boolean);
  const meta = {{
    description_closer:  g('closer').value,
    description_checkout: g('checkout').value,
    target:              g('target').value,
    result_promised:     g('result').value,
    duration_months:     parseInt(g('duration').value) || 0,
    execution_frequency: g('freq').value,
    execution_qty:       parseInt(g('qty').value) || 1,
    not_included,
    upgrade_pitch:       g('upgrade').value,
    eurkai_modules,
  }};
  const data = {{
    name:            g('name').value,
    price:           parseFloat(g('price').value) || 0,
    stripe_price_id: g('stripe').value || null,
    active:          g('active').checked,
    features,
    meta:            JSON.stringify(meta),
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
