"""Admin — onglet ANALYTICS (données V3ProspectDB)."""
import os
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import V3ProspectDB
from ._nav import admin_nav

router = APIRouter(tags=["Admin Analytics"])


def _check_token(request: Request):
    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    return token


def _card(label: str, value: str, sub: str = "", color: str = "#e94560") -> str:
    return (
        f'<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px;text-align:center">'
        f'<div style="font-size:2rem;font-weight:bold;color:{color}">{value}</div>'
        f'<div style="color:#fff;font-size:13px;margin-top:4px">{label}</div>'
        + (f'<div style="color:#666;font-size:11px;margin-top:2px">{sub}</div>' if sub else "")
        + "</div>"
    )


def _bar(label: str, value: int, max_val: int, color: str = "#e94560") -> str:
    pct = int(value / max_val * 100) if max_val else 0
    return (
        f'<div style="margin-bottom:10px">'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:4px">'
        f'<span style="color:#ccc;font-size:12px">{label}</span>'
        f'<span style="color:{color};font-size:12px;font-weight:bold">{value}</span></div>'
        f'<div style="background:#0f0f1a;border-radius:4px;height:8px">'
        f'<div style="background:{color};width:{pct}%;height:8px;border-radius:4px"></div></div></div>'
    )


def _pct(num: int, denom: int) -> str:
    return f"{num/denom*100:.0f}%" if denom else "—"


def _mkt_delivery_stats() -> dict:
    """Lit les stats de livraison depuis marketing.db (graceful si absent)."""
    empty = {"sent": 0, "opened": 0, "clicked": 0, "bounced": 0, "rdv": 0}
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import (
            ProspectDeliveryDB, DeliveryStatus, MeetingDB,
        )
        mdb = MktSession()
        try:
            deliveries = (mdb.query(ProspectDeliveryDB)
                          .filter_by(project_id="presence-ia").all())
            meetings   = (mdb.query(MeetingDB)
                          .filter_by(project_id="presence-ia").all())
            return {
                "sent":    sum(1 for d in deliveries if d.delivery_status == DeliveryStatus.sent),
                "opened":  sum(1 for d in deliveries if d.opened_at),
                "clicked": sum(1 for d in deliveries if d.clicked_at),
                "bounced": sum(1 for d in deliveries if d.delivery_status == DeliveryStatus.bounced),
                "rdv":     len(meetings),
            }
        finally:
            mdb.close()
    except Exception:
        return empty


@router.get("/admin/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, db: Session = Depends(get_db)):
    token = _check_token(request)
    prospects = db.query(V3ProspectDB).all()
    mkt = _mkt_delivery_stats()

    total      = len(prospects)
    with_email = sum(1 for p in prospects if p.email)
    ia_tested  = sum(1 for p in prospects if p.ia_tested_at or p.ia_results)
    contacted  = sum(1 for p in prospects if p.contacted)

    # Taux de conversion du funnel
    rate_email    = _pct(with_email, total)
    rate_ia       = _pct(ia_tested, total)
    rate_contact  = _pct(contacted, total)

    funnel = "".join([
        _card("Scannés", str(total), "total prospects Google Places", "#4b5ea8"),
        _card("Avec email", str(with_email), f"{rate_email} des scannés", "#6366f1"),
        _card("IA testés", str(ia_tested), f"{rate_ia} des scannés", "#e9a020"),
        _card("Landing envoyée", str(contacted), f"{rate_contact} des scannés", "#2ecc71"),
    ])

    # Funnel email tracking (depuis marketing.db)
    open_rate  = _pct(mkt["opened"],  mkt["sent"])
    click_rate = _pct(mkt["clicked"], mkt["sent"])
    rdv_rate   = _pct(mkt["rdv"],     mkt["sent"])
    funnel_mkt = "".join([
        _card("Emails envoyés",  str(mkt["sent"]),    "livraisons marketing.db", "#527FB3"),
        _card("Ouvertures",      str(mkt["opened"]),  f"{open_rate} des envoyés",  "#6366f1"),
        _card("Clics landing",   str(mkt["clicked"]), f"{click_rate} des envoyés", "#e9a020"),
        _card("RDV Calendly",    str(mkt["rdv"]),     f"{rdv_rate} des envoyés",   "#2ecc71"),
        _card("Bounces",         str(mkt["bounced"]), "adresses invalides",         "#e94560"),
    ])

    # Par métier
    by_profession = Counter(p.profession for p in prospects if p.profession)
    max_pro = max(by_profession.values(), default=1)
    pro_bars = "".join(
        _bar(pro, count, max_pro, "#6366f1")
        for pro, count in sorted(by_profession.items(), key=lambda x: -x[1])[:15]
    ) or '<p style="color:#555;font-size:12px">Aucune donnée</p>'

    # Par ville
    by_city = Counter(p.city for p in prospects if p.city)
    max_city = max(by_city.values(), default=1)
    city_bars = "".join(
        _bar(city, count, max_city, "#e9a020")
        for city, count in sorted(by_city.items(), key=lambda x: -x[1])[:15]
    ) or '<p style="color:#555;font-size:12px">Aucune donnée</p>'

    # Contactés par ville
    contacted_city = Counter(p.city for p in prospects if p.contacted and p.city)
    max_cc = max(contacted_city.values(), default=1)
    cc_bars = "".join(
        _bar(city, count, max_cc, "#2ecc71")
        for city, count in sorted(contacted_city.items(), key=lambda x: -x[1])[:10]
    ) or '<p style="color:#555;font-size:12px">Aucun envoi encore</p>'

    # Méthode d'envoi
    methods = Counter(p.sent_method for p in prospects if p.contacted and p.sent_method)
    max_m = max(methods.values(), default=1)
    method_bars = "".join(
        _bar(m, n, max_m, "#e94560")
        for m, n in sorted(methods.items(), key=lambda x: -x[1])
    ) or '<p style="color:#555;font-size:12px">Aucun envoi encore</p>'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analytics — PRESENCE_IA Admin</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
h2{{color:#fff;font-size:15px;margin:0 0 16px}}
.section-label{{color:#9ca3af;font-size:11px;letter-spacing:1px;text-transform:uppercase;margin:0 0 12px}}
.grid-4{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:32px}}
.grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-bottom:32px}}
.panel{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px}}
@media(max-width:700px){{.grid-3{{grid-template-columns:1fr}}}}
</style></head><body>
{admin_nav(token, "analytics")}
<div style="max-width:1100px;margin:0 auto;padding:24px">

<h1 style="color:#fff;font-size:18px;margin-bottom:24px">📊 Analytics</h1>

<p class="section-label">Funnel prospects V3</p>
<div class="grid-4">{funnel}</div>

<p class="section-label" style="margin-top:8px">Tracking email (marketing module)</p>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-bottom:32px">{funnel_mkt}</div>

<div class="grid-3">
  <div class="panel"><h2>🎯 Par métier</h2>{pro_bars}</div>
  <div class="panel"><h2>🏙 Par ville (total)</h2>{city_bars}</div>
  <div class="panel">
    <div style="margin-bottom:24px"><h2>✉️ Landings envoyées / ville</h2>{cc_bars}</div>
    <h2>📡 Canal d'envoi</h2>{method_bars}
  </div>
</div>

</div></body></html>""")
