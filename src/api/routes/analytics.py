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
    empty = {"sent": 0, "opened": 0, "clicked": 0, "landing": 0, "calendly": 0,
             "bounced": 0, "rdv": 0, "rdv_done": 0, "sales": 0, "revenue": 0.0}
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import (
            ProspectDeliveryDB, DeliveryStatus, MeetingDB, MeetingStatus,
        )
        mdb = MktSession()
        try:
            deliveries = (mdb.query(ProspectDeliveryDB)
                          .filter_by(project_id="presence-ia").all())
            stats = {
                "sent":     sum(1 for d in deliveries if d.delivery_status == DeliveryStatus.sent),
                "opened":   sum(1 for d in deliveries if d.opened_at),
                "clicked":  sum(1 for d in deliveries if d.clicked_at),
                "landing":  sum(1 for d in deliveries if getattr(d, "landing_visited_at", None)),
                "calendly": sum(1 for d in deliveries if getattr(d, "calendly_clicked_at", None)),
                "bounced":  sum(1 for d in deliveries if d.delivery_status == DeliveryStatus.bounced),
                "rdv": 0, "rdv_done": 0, "sales": 0, "revenue": 0.0,
            }
            try:
                meetings = (mdb.query(MeetingDB)
                            .filter_by(project_id="presence-ia").all())
                stats["rdv"]      = len(meetings)
                stats["rdv_done"] = sum(1 for m in meetings if m.status == MeetingStatus.completed)
                stats["sales"]    = sum(1 for m in meetings if (m.deal_value or 0) > 0)
                stats["revenue"]  = sum((m.deal_value or 0) for m in meetings if (m.deal_value or 0) > 0)
            except Exception:
                pass
            return stats
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
    open_rate     = _pct(mkt["opened"],   mkt["sent"])
    landing_rate  = _pct(mkt["landing"],  mkt["sent"])
    calendly_rate = _pct(mkt["calendly"], mkt["sent"])
    rdv_rate      = _pct(mkt["rdv"],      mkt["sent"])
    done_rate     = _pct(mkt["rdv_done"], mkt["rdv"])
    sale_rate     = _pct(mkt["sales"],    mkt["rdv_done"])
    revenue_fmt   = f"{mkt['revenue']:,.0f} €".replace(",", " ") if mkt["revenue"] else "0 €"
    funnel_mkt = "".join([
        _card("Emails envoyés",    str(mkt["sent"]),      "livraisons",                        "#527FB3"),
        _card("Ouvertures email",  open_rate,             f"{mkt['opened']} emails",           "#6366f1"),
        _card("Visites landing",   landing_rate,          f"{mkt['landing']} visites",         "#e9a020"),
        _card("Clics Calendly",    calendly_rate,         f"{mkt['calendly']} clics",          "#f59e0b"),
        _card("RDV confirmés",     rdv_rate,              f"{mkt['rdv']} RDV",                 "#2ecc71"),
        _card("RDV effectués",     done_rate,             f"{mkt['rdv_done']} effectués",      "#10b981"),
        _card("Ventes",            sale_rate,             f"{mkt['sales']} ventes",            "#a855f7"),
        _card("CA généré",         revenue_fmt,           "deal_value cumulé",                 "#ec4899"),
        _card("Bounces",           str(mkt["bounced"]),   "adresses invalides",                "#e94560"),
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


# ── Closers — saisie résultats RDV ────────────────────────────────────────────

@router.get("/admin/closers", response_class=HTMLResponse)
def closers_page(request: Request):
    token = _check_token(request)
    meetings = []
    closers  = []
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import MeetingDB, CloserDB, MeetingStatus
        mdb = MktSession()
        try:
            meetings = (mdb.query(MeetingDB)
                        .filter_by(project_id="presence-ia")
                        .order_by(MeetingDB.scheduled_at.desc()).all())
            closers  = mdb.query(CloserDB).filter_by(project_id="presence-ia").all()
        finally:
            mdb.close()
    except Exception:
        pass

    def _status_badge(m):
        if (m.deal_value or 0) > 0:
            return '<span style="background:#a855f7;color:#fff;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700">VENTE</span>'
        if m.status == "completed":
            return '<span style="background:#10b981;color:#fff;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700">EFFECTUÉ</span>'
        return '<span style="background:#f59e0b;color:#fff;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700">CONFIRMÉ</span>'

    rows = ""
    for m in meetings:
        sched = m.scheduled_at.strftime("%d/%m/%Y %H:%M") if m.scheduled_at else "—"
        closer_name = next((c.name for c in closers if c.id == m.closer_id), "—") if m.closer_id else "—"
        deal = f"{m.deal_value:,.0f} €".replace(",", " ") if (m.deal_value or 0) > 0 else ""
        rows += f"""<tr>
  <td style="padding:8px 10px;font-size:12px">{sched}</td>
  <td style="padding:8px 10px;font-size:12px">{m.prospect_id[:12]}…</td>
  <td style="padding:8px 10px;font-size:12px">{closer_name}</td>
  <td style="padding:8px 10px">{_status_badge(m)}</td>
  <td style="padding:8px 10px;font-size:12px;color:#a855f7;font-weight:700">{deal}</td>
  <td style="padding:8px 10px;font-size:11px;color:#6b7280">{(m.outcome or '')[:60]}</td>
  <td style="padding:8px 6px;text-align:center">
    <button onclick="openEdit('{m.id}','{m.status}','{m.deal_value or ''}','{(m.outcome or '').replace(chr(39), '')}')"
      style="background:#2a2a4e;color:#ccc;border:1px solid #3a3a5e;border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer">
      Modifier
    </button>
  </td>
</tr>"""

    closer_options = "".join(
        f'<option value="{c.id}">{c.name}</option>' for c in closers
    )

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Closers — PRESENCE_IA</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
table{{width:100%;border-collapse:collapse}}
th{{background:#1a1a2e;color:#9ca3af;font-size:11px;text-transform:uppercase;letter-spacing:.8px;padding:10px;text-align:left;border-bottom:1px solid #2a2a4e}}
tr:hover td{{background:rgba(255,255,255,.03)}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100;align-items:center;justify-content:center}}
.modal.open{{display:flex}}
.modal-box{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:28px;width:420px;max-width:95vw}}
label{{display:block;color:#9ca3af;font-size:11px;margin-bottom:4px;margin-top:14px}}
input,select,textarea{{width:100%;background:#0f0f1a;border:1px solid #3a3a5e;color:#e8e8f0;border-radius:6px;padding:8px 10px;font-size:13px}}
.btn-save{{background:#a855f7;color:#fff;border:none;border-radius:8px;padding:10px 24px;font-weight:700;cursor:pointer;margin-top:18px;width:100%}}
.btn-cancel{{background:#2a2a4e;color:#ccc;border:none;border-radius:8px;padding:8px 16px;cursor:pointer;font-size:12px;margin-top:8px;width:100%}}
</style></head><body>
{admin_nav(token, "closers")}
<div style="max-width:1100px;margin:0 auto;padding:24px">
<h1 style="color:#fff;font-size:18px;margin-bottom:24px">👔 Closers — Résultats RDV</h1>

<div style="overflow-x:auto;background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px">
<table>
<thead><tr>
  <th>Date RDV</th><th>Prospect</th><th>Closer</th><th>Statut</th><th>Montant</th><th>Notes</th><th></th>
</tr></thead>
<tbody>{rows or '<tr><td colspan="7" style="padding:24px;text-align:center;color:#555">Aucun RDV encore</td></tr>'}</tbody>
</table>
</div>

</div>

<div class="modal" id="editModal">
<div class="modal-box">
  <h3 style="color:#fff;font-size:15px;margin-bottom:4px">Modifier le RDV</h3>
  <input type="hidden" id="edit_mid">
  <label>Statut</label>
  <select id="edit_status">
    <option value="scheduled">Confirmé (à venir)</option>
    <option value="completed">Effectué</option>
  </select>
  <label>Closer assigné</label>
  <select id="edit_closer"><option value="">— aucun —</option>{closer_options}</select>
  <label>Montant vente (€) — laisser vide si pas de vente</label>
  <input type="number" id="edit_deal" placeholder="ex: 1500" min="0">
  <label>Notes / compte-rendu</label>
  <textarea id="edit_notes" rows="3" placeholder="Résumé du call..."></textarea>
  <button class="btn-save" onclick="saveEdit()">Enregistrer</button>
  <button class="btn-cancel" onclick="closeModal()">Annuler</button>
</div>
</div>

<script>
const TOKEN = '{token}';
function openEdit(mid, status, deal, notes) {{
  document.getElementById('edit_mid').value = mid;
  document.getElementById('edit_status').value = status || 'scheduled';
  document.getElementById('edit_deal').value = deal || '';
  document.getElementById('edit_notes').value = notes || '';
  document.getElementById('editModal').classList.add('open');
}}
function closeModal() {{
  document.getElementById('editModal').classList.remove('open');
}}
async function saveEdit() {{
  const mid = document.getElementById('edit_mid').value;
  const body = {{
    status:     document.getElementById('edit_status').value,
    closer_id:  document.getElementById('edit_closer').value || null,
    deal_value: parseFloat(document.getElementById('edit_deal').value) || null,
    outcome:    document.getElementById('edit_notes').value || null,
  }};
  const r = await fetch(`/admin/closers/${{mid}}?token=${{TOKEN}}`, {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(body)
  }});
  if (r.ok) {{ closeModal(); location.reload(); }}
  else alert('Erreur lors de la sauvegarde');
}}
</script>
</body></html>""")


@router.post("/admin/closers/{meeting_id}")
async def update_meeting(meeting_id: str, request: Request):
    _check_token(request)
    body = await request.json()
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import MeetingDB, MeetingStatus
        from datetime import datetime
        mdb = MktSession()
        try:
            m = mdb.query(MeetingDB).filter_by(id=meeting_id).first()
            if not m:
                raise HTTPException(404, "RDV introuvable")
            if body.get("status"):
                m.status = body["status"]
            if m.status == MeetingStatus.completed and not m.completed_at:
                m.completed_at = datetime.utcnow()
            if "deal_value" in body:
                m.deal_value = body["deal_value"]
            if "outcome" in body:
                m.outcome = body["outcome"]
            if body.get("closer_id"):
                m.closer_id = body["closer_id"]
            mdb.commit()
        finally:
            mdb.close()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
