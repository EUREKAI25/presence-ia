"""Admin — onglet ANALYTICS."""
import json
import os
from collections import Counter, defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import ContactDB, ProspectDB

router = APIRouter(tags=["Admin Analytics"])


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


def _stat_card(label: str, value: str, sub: str = "", color: str = "#e94560") -> str:
    return f"""<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px;text-align:center">
  <div style="font-size:2rem;font-weight:bold;color:{color}">{value}</div>
  <div style="color:#fff;font-size:13px;margin-top:4px">{label}</div>
  {f'<div style="color:#555;font-size:11px;margin-top:2px">{sub}</div>' if sub else ''}
</div>"""


def _bar(label: str, value: int, max_val: int, color: str = "#e94560") -> str:
    pct = int(value / max_val * 100) if max_val else 0
    return f"""<div style="margin-bottom:10px">
  <div style="display:flex;justify-content:space-between;margin-bottom:4px">
    <span style="color:#ccc;font-size:12px">{label}</span>
    <span style="color:{color};font-size:12px;font-weight:bold">{value}</span>
  </div>
  <div style="background:#1a1a2e;border-radius:4px;height:8px">
    <div style="background:{color};width:{pct}%;height:8px;border-radius:4px"></div>
  </div>
</div>"""


@router.get("/admin/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, db: Session = Depends(get_db)):
    token = _check_token(request)
    contacts = db.query(ContactDB).all()

    # KPIs pipeline IA (table prospects)
    all_prospects = db.query(ProspectDB).all()
    p_total     = len(all_prospects)
    p_tested    = sum(1 for p in all_prospects if p.status in ("TESTED","EMAIL_OK","SCORED","READY_ASSETS","READY_TO_SEND","SENT"))
    p_suspects  = sum(1 for p in all_prospects if p.status in ("EMAIL_OK","SCORED","READY_ASSETS","READY_TO_SEND"))
    p_sent      = sum(1 for p in all_prospects if p.status == "SENT")
    pipeline_cards = "".join([
        _stat_card("Scannés", str(p_total), color="#4b5ea8"),
        _stat_card("Testés", str(p_tested), color="#6366f1"),
        _stat_card("Suspects qualifiés", str(p_suspects), color="#e9a020"),
        _stat_card("Envoyés", str(p_sent), color="#2ecc71"),
    ])

    # Charger les offres depuis offers_module (prix dynamiques depuis DB)
    from offers_module.database import db_list_offers
    offers = db_list_offers(db)
    offer_prices = {o.name: o.price for o in offers}   # name → price
    # Fallback : chercher par nom partiel pour les contacts avec offer_selected = clé legacy
    def _resolve_price(offer_key: str) -> float:
        if offer_key in offer_prices:
            return offer_prices[offer_key]
        key_lower = offer_key.lower()
        for name, price in offer_prices.items():
            if key_lower in name.lower() or name.lower() in key_lower:
                return price
        return 0.0

    total       = len(contacts)
    suspects    = sum(1 for c in contacts if c.status == "SUSPECT")
    prospects   = sum(1 for c in contacts if c.status == "PROSPECT")
    clients     = sum(1 for c in contacts if c.status == "CLIENT")
    sent_count  = sum(1 for c in contacts if c.message_sent)
    read_count  = sum(1 for c in contacts if c.message_read)
    paid_count  = sum(1 for c in contacts if c.paid)

    conv_rate   = f"{clients/total*100:.1f}%" if total else "—"
    open_rate   = f"{read_count/sent_count*100:.1f}%" if sent_count else "—"

    # Revenue — prix lus depuis la DB (plus hardcodés)
    revenue_by_offer: dict = defaultdict(float)
    clients_by_offer: dict = Counter()
    for c in contacts:
        if c.paid and c.offer_selected:
            revenue_by_offer[c.offer_selected] += _resolve_price(c.offer_selected)
            clients_by_offer[c.offer_selected] += 1
    revenue_total = sum(revenue_by_offer.values())

    # Avg acquisition cost
    costs = [c.acquisition_cost for c in contacts if c.acquisition_cost]
    avg_cost = f"{sum(costs)/len(costs):.2f}€" if costs else "—"

    # Clients by city
    city_counter: dict = Counter(c.city for c in contacts if c.paid and c.city)
    max_city = max(city_counter.values(), default=1)

    # Contacts by city (all)
    all_city: dict = Counter(c.city for c in contacts if c.city)
    max_all_city = max(all_city.values(), default=1)

    # Build KPI cards
    rev_display = f"{int(revenue_total)}€" if revenue_total == int(revenue_total) else f"{revenue_total:.2f}€"
    kpis = "".join([
        _stat_card("Total contacts", str(total)),
        _stat_card("Suspects", str(suspects), color="#888"),
        _stat_card("Prospects", str(prospects), color="#e9a020"),
        _stat_card("Clients", str(clients), color="#2ecc71"),
        _stat_card("Taux conversion", conv_rate, f"{paid_count} payés / {total} contacts"),
        _stat_card("Taux ouverture", open_rate, f"{read_count} lus / {sent_count} envoyés"),
        _stat_card("Revenu total", rev_display, sub="Prix depuis admin", color="#2ecc71"),
        _stat_card("Coût acq. moyen", avg_cost),
    ])

    # Revenue by offer bars (offres actives depuis la DB)
    rev_bars = ""
    max_rev = max(revenue_by_offer.values(), default=1)
    if offers:
        for o in offers:
            rev = revenue_by_offer.get(o.name, 0)
            nb  = clients_by_offer.get(o.name, 0)
            price_display = f"{int(o.price)}€" if o.price == int(o.price) else f"{o.price:.2f}€"
            rev_bars += _bar(f"{o.name} ({price_display} — {nb} clients)", int(rev), int(max_rev), "#e94560")
    if not rev_bars:
        rev_bars = '<p style="color:#555;font-size:12px">Aucune offre configurée — <a href="/api/admin/offers" style="color:#e94560">Créer des offres</a></p>'

    # Clients by city bars
    city_bars = "".join(
        _bar(city, count, max_city, "#2ecc71")
        for city, count in sorted(city_counter.items(), key=lambda x: -x[1])[:10]
    ) or '<p style="color:#555;font-size:12px">Aucun client encore</p>'

    # All contacts by city
    all_city_bars = "".join(
        _bar(city, count, max_all_city, "#e9a020")
        for city, count in sorted(all_city.items(), key=lambda x: -x[1])[:10]
    ) or '<p style="color:#555;font-size:12px">Aucun contact encore</p>'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analytics — PRESENCE_IA Admin</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
h2{{color:#fff;font-size:15px;margin:0 0 16px}}</style></head><body>
{_nav("analytics", token)}
<div style="max-width:1100px;margin:0 auto;padding:24px">

<h1 style="color:#fff;font-size:18px;margin-bottom:24px">📊 Analytics</h1>

<h3 style="color:#9ca3af;font-size:12px;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">Pipeline IA</h3>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-bottom:32px">
{pipeline_cards}
</div>
<h3 style="color:#9ca3af;font-size:12px;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">CRM</h3>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-bottom:32px">
{kpis}
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:32px">

<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px">
<h2>💶 Revenu par offre</h2>
{rev_bars}
</div>

<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px">
<h2>🏙 Clients par ville</h2>
{city_bars}
</div>

</div>

<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px;margin-bottom:32px">
<h2>📍 Contacts par ville (tous statuts)</h2>
<div style="columns:2;gap:24px">
{all_city_bars}
</div>
</div>

</div>
</body></html>""")
