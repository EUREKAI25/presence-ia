"""Admin — Pages hub des 4 sections principales.

Routes :
    GET  /admin/leads-hub      → Leads : métriques + liens
    GET  /admin/marketing      → Marketing : stats globales email/SMS
    GET  /admin/closers-hub    → Closers : CA, commissions, perfs
    GET  /admin/finances       → Finances : revenus, coûts, marge
    POST /admin/finances/costs → Sauvegarde coûts (JSON local)
"""
import json, os, logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ...database import get_db, SessionLocal
from ...models import V3ProspectDB, V3CityImageDB, LeadProvisioningConfigDB, SireneSegmentDB
from ._nav import admin_nav, admin_token

router = APIRouter(tags=["Admin Hub"])
log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
_COSTS_FILE = _DATA_DIR / "admin_costs.json"


# ── Auth ────────────────────────────────────────────────────────────────────

def _check(request: Request):
    token = (request.query_params.get("token")
             or request.cookies.get("admin_token", ""))
    if token != admin_token():
        return None, RedirectResponse("/admin/login", status_code=302)
    return token, None


# ── Helpers UI ──────────────────────────────────────────────────────────────

def _kpi(label, val, sub="", color="#e94560"):
    return (
        f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:18px 20px">'
        f'<div style="font-size:10px;color:#9ca3af;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:8px">{label}</div>'
        f'<div style="font-size:28px;font-weight:700;color:{color};line-height:1">{val}</div>'
        f'{"<div style=margin-top:6px;font-size:11px;color:#9ca3af>" + sub + "</div>" if sub else ""}'
        f'</div>'
    )


def _stat_row(label, val, pct="", color="#374151"):
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'padding:9px 0;border-bottom:1px solid #f3f4f6">'
        f'<span style="font-size:13px;color:#374151">{label}</span>'
        f'<span style="font-size:13px;font-weight:600;color:{color}">{val}'
        f'{"&nbsp;<span style=font-size:11px;color:#9ca3af>" + pct + "</span>" if pct else ""}'
        f'</span></div>'
    )


def _section_link(href, label, desc=""):
    return (
        f'<a href="{href}" style="display:block;padding:12px 16px;background:#fff;'
        f'border:1px solid #e5e7eb;border-radius:8px;text-decoration:none;'
        f'transition:border-color .15s" '
        f'onmouseover="this.style.borderColor=\'#e94560\'" '
        f'onmouseout="this.style.borderColor=\'#e5e7eb\'">'
        f'<div style="font-size:13px;font-weight:600;color:#374151">{label}</div>'
        f'{"<div style=font-size:11px;color:#9ca3af;margin-top:2px>" + desc + "</div>" if desc else ""}'
        f'</a>'
    )


def _page(title, active, token, body):
    nav = admin_nav(token, active)
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="utf-8"><title>{title} — PRESENCE IA</title>
{nav}
<style>
body{{font-family:system-ui,sans-serif;background:#f9fafb;color:#111}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px}}
h2{{font-size:13px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.06em;margin:0 0 14px}}
h1{{font-size:20px;font-weight:700;margin:0 0 4px}}
.grid-4{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}}
.grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}}
.grid-2{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:16px}}
@media(max-width:900px){{.grid-4,.grid-3{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:560px){{.grid-4,.grid-3,.grid-2{{grid-template-columns:1fr}}}}
.links-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}}
@media(max-width:700px){{.links-grid{{grid-template-columns:1fr 1fr}}}}
</style>
</head><body>
<div style="padding:24px;max-width:1200px">
{body}
</div>
</body></html>""")


# ── Mkt stats helper (copie légère de analytics.py) ─────────────────────────

def _mkt_stats() -> dict:
    empty = {"sent": 0, "opened": 0, "clicked": 0, "landing": 0,
             "calendly": 0, "bounced": 0, "rdv": 0, "rdv_done": 0,
             "sales": 0, "revenue": 0.0}
    try:
        from marketing_module.database import SessionLocal as MktSess
        from marketing_module.models import ProspectDeliveryDB, DeliveryStatus, MeetingDB, MeetingStatus
        mdb = MktSess()
        try:
            dl = mdb.query(ProspectDeliveryDB).filter_by(project_id="presence-ia").all()
            s = {
                "sent":     sum(1 for d in dl if d.delivery_status == DeliveryStatus.sent),
                "opened":   sum(1 for d in dl if d.opened_at),
                "clicked":  sum(1 for d in dl if d.clicked_at),
                "landing":  sum(1 for d in dl if getattr(d, "landing_visited_at", None)),
                "calendly": sum(1 for d in dl if getattr(d, "calendly_clicked_at", None)),
                "bounced":  sum(1 for d in dl if d.delivery_status == DeliveryStatus.bounced),
                "rdv": 0, "rdv_done": 0, "sales": 0, "revenue": 0.0,
            }
            mtgs = mdb.query(MeetingDB).filter_by(project_id="presence-ia").all()
            s["rdv"]      = len(mtgs)
            s["rdv_done"] = sum(1 for m in mtgs if m.status == MeetingStatus.completed)
            s["sales"]    = sum(1 for m in mtgs if (m.deal_value or 0) > 0)
            s["revenue"]  = sum((m.deal_value or 0) for m in mtgs)
            return s
        finally:
            mdb.close()
    except Exception:
        return empty


def _pct(a, b):
    return f"{a/b*100:.0f}%" if b else "—"


# ── Coûts helpers ────────────────────────────────────────────────────────────

def _load_costs() -> list:
    try:
        if _COSTS_FILE.exists():
            return json.loads(_COSTS_FILE.read_text())
    except Exception:
        pass
    return []


def _save_costs(costs: list):
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _COSTS_FILE.write_text(json.dumps(costs, ensure_ascii=False, indent=2))


# ── /admin/leads-hub ─────────────────────────────────────────────────────────

@router.get("/admin/leads-hub", response_class=HTMLResponse)
def leads_hub(request: Request, db: Session = Depends(get_db)):
    token, redir = _check(request)
    if redir: return redir

    prospects = db.query(V3ProspectDB).all()
    total      = len(prospects)
    enrichis   = sum(1 for p in prospects if p.email)
    contactes  = sum(1 for p in prospects if p.contacted)
    ia_tested  = sum(1 for p in prospects if p.ia_results or p.ia_tested_at)
    non_cont   = enrichis - contactes

    mkt = _mkt_stats()
    rdv = mkt["rdv"]
    deals = mkt["sales"]

    kpis = (
        f'<div class="grid-4">'
        + _kpi("Suspects", f"{total:,}", "dans la base", "#6366f1")
        + _kpi("Enrichis (email)", f"{enrichis:,}", _pct(enrichis, total) + " des suspects", "#8b5cf6")
        + _kpi("Contactés", f"{contactes:,}", _pct(contactes, enrichis) + " des enrichis", "#10b981")
        + _kpi("Non contactés", f"{non_cont:,}", "avec email — à traiter", "#e94560" if non_cont > 0 else "#9ca3af")
        + f'</div>'
    )

    funnel_rows = (
        _stat_row("Suspects scannés",  f"{total:,}")
        + _stat_row("Avec email",       f"{enrichis:,}", _pct(enrichis, total))
        + _stat_row("IA testés",        f"{ia_tested:,}", _pct(ia_tested, total))
        + _stat_row("Landing envoyée",  f"{contactes:,}", _pct(contactes, enrichis))
        + _stat_row("RDV pris",         f"{rdv:,}", _pct(rdv, contactes))
        + _stat_row("Deals signés",     f"{deals:,}", _pct(deals, rdv), "#e94560")
    )

    links = (
        f'<div class="links-grid">'
        + _section_link(f"/admin/contacts?token={token}", "Contacts", "Tableau complet des prospects")
        + _section_link(f"/admin/prospection?token={token}", "Automation", "Paramétrage requêtes + enrichissement")
        + _section_link(f"/admin/suspects?token={token}", "Suspects SIRENE", "Base suspects brute")
        + _section_link(f"/admin/scheduler?token={token}", "Scheduler", "Jobs automatiques")
        + f'</div>'
    )

    body = f"""
    <h1>Leads</h1>
    <p style="color:#6b7280;font-size:13px;margin-bottom:20px">Vue d'ensemble du pipeline de prospection</p>
    {kpis}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
      <div class="card">
        <h2>Funnel complet</h2>
        {funnel_rows}
      </div>
      <div class="card">
        <h2>Accès rapide</h2>
        {links}
      </div>
    </div>
    """
    return _page("Leads", "leads-hub", token, body)


# ── /admin/marketing ─────────────────────────────────────────────────────────

@router.get("/admin/marketing", response_class=HTMLResponse)
def marketing_hub(request: Request, db: Session = Depends(get_db)):
    token, redir = _check(request)
    if redir: return redir

    m = _mkt_stats()
    prospects = db.query(V3ProspectDB).all()
    contactes = sum(1 for p in prospects if p.contacted)

    kpis = (
        f'<div class="grid-4">'
        + _kpi("Envoyés", f"{m['sent']:,}", "emails livrés", "#6366f1")
        + _kpi("Ouvertures", _pct(m["opened"], m["sent"]), f"{m['opened']:,} emails", "#8b5cf6")
        + _kpi("Clics", _pct(m["clicked"], m["sent"]), f"{m['clicked']:,} clics", "#0ea5e9")
        + _kpi("RDV", f"{m['rdv']:,}", _pct(m["rdv"], m["sent"]) + " des envoyés", "#10b981")
        + f'</div>'
    )

    kpis2 = (
        f'<div class="grid-4">'
        + _kpi("Visites landing", _pct(m["landing"], m["sent"]), f"{m['landing']:,} visites", "#f59e0b")
        + _kpi("Clics Calendly", _pct(m["calendly"], m["sent"]), f"{m['calendly']:,}", "#f97316")
        + _kpi("RDV effectués", f"{m['rdv_done']:,}", _pct(m["rdv_done"], m["rdv"]) + " des RDV", "#16a34a")
        + _kpi("Ventes", f"{m['sales']:,}", _pct(m["sales"], m["rdv_done"]) + " des RDV done", "#e94560")
        + f'</div>'
    )

    detail_rows = (
        _stat_row("Contacts traités", f"{contactes:,}")
        + _stat_row("Emails envoyés", f"{m['sent']:,}")
        + _stat_row("Taux ouverture", _pct(m["opened"], m["sent"]))
        + _stat_row("Taux clic", _pct(m["clicked"], m["sent"]))
        + _stat_row("Bounce", f"{m['bounced']:,}", "", "#dc2626" if m["bounced"] > 0 else "#374151")
        + _stat_row("RDV confirmés", f"{m['rdv']:,}")
        + _stat_row("RDV effectués", f"{m['rdv_done']:,}")
        + _stat_row("Ventes", f"{m['sales']:,}", color="#16a34a")
        + _stat_row("CA généré", f"{m['revenue']:,.0f} €", color="#16a34a")
    )

    links = (
        f'<div class="links-grid">'
        + _section_link(f"/admin/campaigns?token={token}", "Campagnes", "Historique et résultats")
        + _section_link(f"/admin/contacts?token={token}", "Contacts", "Gérer les contacts")
        + _section_link(f"/admin/scheduler?token={token}", "Scheduler", "Automation envois")
        + f'</div>'
    )

    body = f"""
    <h1>Marketing</h1>
    <p style="color:#6b7280;font-size:13px;margin-bottom:20px">Stats globales email + SMS — toutes campagnes</p>
    {kpis}
    {kpis2}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div class="card">
        <h2>Détail complet</h2>
        {detail_rows}
      </div>
      <div class="card">
        <h2>Accès rapide</h2>
        {links}
      </div>
    </div>
    """
    return _page("Marketing", "marketing", token, body)


# ── /admin/closers-hub ───────────────────────────────────────────────────────

@router.get("/admin/closers-hub", response_class=HTMLResponse)
def closers_hub(request: Request, db: Session = Depends(get_db)):
    token, redir = _check(request)
    if redir: return redir

    m = _mkt_stats()

    # Ventilation par offre depuis MeetingDB
    offer_breakdown: dict = {}
    closer_perfs: dict = {}
    nb_closers_actifs = 0
    commissions_dues = 0.0
    try:
        from marketing_module.database import SessionLocal as MktSess
        from marketing_module.models import MeetingDB, MeetingStatus, CloserDB
        mdb = MktSess()
        try:
            mtgs = mdb.query(MeetingDB).filter_by(project_id="presence-ia").all()
            for mt in mtgs:
                if (mt.deal_value or 0) > 0:
                    offer_name = getattr(mt, "offer_name", None) or "—"
                    if offer_name not in offer_breakdown:
                        offer_breakdown[offer_name] = {"nb": 0, "ca": 0.0}
                    offer_breakdown[offer_name]["nb"]  += 1
                    offer_breakdown[offer_name]["ca"]  += mt.deal_value or 0
                closer_id = getattr(mt, "closer_id", None) or "—"
                if closer_id not in closer_perfs:
                    closer_perfs[closer_id] = {"rdv": 0, "deals": 0, "ca": 0.0}
                closer_perfs[closer_id]["rdv"] += 1
                if (mt.deal_value or 0) > 0:
                    closer_perfs[closer_id]["deals"] += 1
                    closer_perfs[closer_id]["ca"]    += mt.deal_value or 0

            try:
                actifs = mdb.query(CloserDB).filter_by(project_id="presence-ia", status="active").count()
                nb_closers_actifs = actifs
            except Exception:
                nb_closers_actifs = len([k for k in closer_perfs if k != "—"])

            commissions_dues = m["revenue"] * 0.18
        finally:
            mdb.close()
    except Exception:
        nb_closers_actifs = 0

    ca_fmt  = f"{m['revenue']:,.0f} €".replace(",", " ")
    com_fmt = f"{commissions_dues:,.0f} €".replace(",", " ")
    marge_pct = 82  # 100% - 18% commission

    kpis = (
        f'<div class="grid-4">'
        + _kpi("CA total", ca_fmt, "deals signés", "#16a34a")
        + _kpi("Marge", f"{marge_pct}%", com_fmt + " commissions", "#0ea5e9")
        + _kpi("Commissions", com_fmt, f"18% · {m['sales']} deals", "#f59e0b")
        + _kpi("Closers actifs", str(nb_closers_actifs), f"{m['rdv']} RDV · {m['sales']} deals", "#6366f1")
        + f'</div>'
    )

    # Ventilation par offre
    if offer_breakdown:
        off_rows = "".join(
            _stat_row(
                name,
                f"{data['ca']:,.0f} €".replace(",", " "),
                f"{data['nb']} deal{'s' if data['nb'] > 1 else ''}",
                "#16a34a"
            )
            for name, data in sorted(offer_breakdown.items(), key=lambda x: -x[1]["ca"])
        )
    else:
        off_rows = '<p style="color:#9ca3af;font-size:12px;padding:8px 0">Aucun deal signé</p>'

    # Top closers
    if closer_perfs and any(k != "—" for k in closer_perfs):
        closer_rows = "".join(
            f'<tr style="border-bottom:1px solid #f3f4f6">'
            f'<td style="padding:8px 10px;font-size:12px;font-weight:600">{cid}</td>'
            f'<td style="padding:8px 10px;font-size:12px;color:#6b7280">{data["rdv"]}</td>'
            f'<td style="padding:8px 10px;font-size:12px;color:#e94560;font-weight:700">{data["deals"]}</td>'
            f'<td style="padding:8px 10px;font-size:12px;color:#16a34a">{data["ca"]:,.0f} €</td>'
            f'</tr>'
            for cid, data in sorted(closer_perfs.items(), key=lambda x: -x[1]["deals"])
            if cid != "—"
        )
        closer_table = (
            f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr style="border-bottom:2px solid #e5e7eb">'
            f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#9ca3af">Closer</th>'
            f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#9ca3af">RDV</th>'
            f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#9ca3af">Deals</th>'
            f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#9ca3af">CA</th>'
            f'</tr></thead><tbody>{closer_rows}</tbody></table>'
        )
    else:
        closer_table = '<p style="color:#9ca3af;font-size:12px;padding:8px 0">Aucune donnée closer</p>'

    links = (
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px">'
        + _section_link(f"/admin/crm?token={token}", "Pipeline", "Prospects → RDV → Deal")
        + _section_link(f"/admin/crm/closers?token={token}", "Liste closers", "Gestion & candidatures")
        + _section_link(f"/admin/closer/recruit?token={token}", "Recrutement", "Page candidature")
        + _section_link(f"/admin/rdv?token={token}", "RDV", "Calendrier")
        + f'</div>'
    )

    body = f"""
    <h1>Closers</h1>
    <p style="color:#6b7280;font-size:13px;margin-bottom:20px">Performance commerciale et commissions</p>
    {kpis}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
      <div class="card">
        <h2>Ventilation par offre</h2>
        {off_rows}
      </div>
      <div class="card">
        <h2>Top closers</h2>
        {closer_table}
      </div>
    </div>
    <div class="card">
      <h2>Navigation</h2>
      {links}
    </div>
    """
    return _page("Closers", "closers-hub", token, body)


# ── /admin/finances ──────────────────────────────────────────────────────────

@router.get("/admin/finances", response_class=HTMLResponse)
def finances_hub(request: Request, db: Session = Depends(get_db)):
    token, redir = _check(request)
    if redir: return redir

    m = _mkt_stats()
    costs = _load_costs()

    # CA par offre depuis meeting data
    offer_ca: dict = {}
    ia_cost_data: dict = {}
    try:
        from marketing_module.database import SessionLocal as MktSess
        from marketing_module.models import MeetingDB
        mdb = MktSess()
        try:
            for mt in mdb.query(MeetingDB).filter_by(project_id="presence-ia").all():
                if (mt.deal_value or 0) > 0:
                    name = getattr(mt, "offer_name", None) or "—"
                    offer_ca[name] = offer_ca.get(name, 0.0) + (mt.deal_value or 0)
        finally:
            mdb.close()
    except Exception:
        pass

    # IA cost estimation (nb prospects × coût moyen)
    total_prospects = db.query(V3ProspectDB).count()
    ia_tested = db.query(V3ProspectDB).filter(
        V3ProspectDB.ia_results.isnot(None)
    ).count()
    # Estimation : ~0.005€ par test IA (Anthropic Claude Haiku)
    ia_cost_est = ia_tested * 0.005
    cost_per_lead_ia = ia_cost_est / max(ia_tested, 1)

    # Coûts saisis manuellement
    total_costs_recur = sum(c["montant"] for c in costs if c.get("type_freq") == "recurrent")
    total_costs_ponct = sum(c["montant"] for c in costs if c.get("type_freq") == "ponctuel")
    total_costs_mkt   = sum(c["montant"] for c in costs if c.get("type") == "marketing")
    total_costs_ia_m  = sum(c["montant"] for c in costs if c.get("type") == "ia")
    total_costs       = sum(c["montant"] for c in costs)

    ca_total   = m["revenue"]
    marge_brute = ca_total - total_costs
    marge_pct   = marge_brute / ca_total * 100 if ca_total else 0

    ca_fmt   = f"{ca_total:,.0f} €".replace(",", " ")
    mg_fmt   = f"{marge_brute:,.0f} €".replace(",", " ")
    mg_pct   = f"{marge_pct:.1f}%"
    cost_fmt = f"{total_costs:,.0f} €".replace(",", " ")

    kpis = (
        f'<div class="grid-4">'
        + _kpi("CA total", ca_fmt, f"{m['sales']} deals", "#16a34a")
        + _kpi("Coûts déclarés", cost_fmt, f"récurrents: {total_costs_recur:.0f} €", "#f59e0b")
        + _kpi("Marge brute", mg_fmt, mg_pct, "#0ea5e9" if marge_brute >= 0 else "#e94560")
        + _kpi("LTV estimée", ca_fmt, "à affiner avec renouvellements", "#6366f1")
        + f'</div>'
    )

    # Revenus par offre
    if offer_ca:
        rev_rows = "".join(
            _stat_row(name, f"{ca:,.0f} €".replace(",", " "), color="#16a34a")
            for name, ca in sorted(offer_ca.items(), key=lambda x: -x[1])
        )
    else:
        rev_rows = '<p style="color:#9ca3af;font-size:12px;padding:8px 0">Aucun CA enregistré</p>'

    # IA cost tracking
    ia_rows = (
        _stat_row("Tests IA effectués", f"{ia_tested:,}")
        + _stat_row("Coût IA estimé", f"~{ia_cost_est:.2f} €", "(~0.005€/test)", "#f59e0b")
        + _stat_row("Coût IA / lead", f"~{cost_per_lead_ia:.4f} €")
        + _stat_row("Coût IA déclaré", f"{total_costs_ia_m:.2f} €")
        + _stat_row("Coût marketing", f"{total_costs_mkt:.2f} €")
        + _stat_row("Coût / deal signé", f"{total_costs / max(m['sales'], 1):.2f} €" if m['sales'] else "—",
                    color="#e94560")
    )

    # Coûts enregistrés
    if costs:
        cost_rows = "".join(
            f'<tr style="border-bottom:1px solid #f3f4f6">'
            f'<td style="padding:7px 10px;font-size:12px">{c.get("label","—")}</td>'
            f'<td style="padding:7px 10px;font-size:12px;color:#6b7280">{c.get("type","—")}</td>'
            f'<td style="padding:7px 10px;font-size:12px;color:#6b7280">'
            f'{"récurrent" if c.get("type_freq")=="recurrent" else "ponctuel"}</td>'
            f'<td style="padding:7px 10px;font-size:12px;font-weight:600;color:#374151">'
            f'{c.get("montant",0):,.2f} €</td>'
            f'<td style="padding:7px 10px">'
            f'<form method="post" action="/admin/finances/costs/delete" style="display:inline">'
            f'<input type="hidden" name="token" value="{token}">'
            f'<input type="hidden" name="idx" value="{costs.index(c)}">'
            f'<button type="submit" style="background:none;border:none;color:#e94560;'
            f'font-size:11px;cursor:pointer;padding:0">✕</button></form></td>'
            f'</tr>'
            for c in costs
        )
        cost_table = (
            f'<table style="width:100%;border-collapse:collapse;margin-bottom:16px">'
            f'<thead><tr style="border-bottom:2px solid #e5e7eb">'
            f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#9ca3af">Label</th>'
            f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#9ca3af">Type</th>'
            f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#9ca3af">Fréquence</th>'
            f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#9ca3af">Montant</th>'
            f'<th></th>'
            f'</tr></thead><tbody>{cost_rows}</tbody></table>'
        )
    else:
        cost_table = '<p style="color:#9ca3af;font-size:12px;margin-bottom:12px">Aucun coût enregistré</p>'

    # Résultat
    result_rows = (
        _stat_row("CA total", ca_fmt, color="#16a34a")
        + _stat_row("Coûts déclarés", f"− {cost_fmt}", color="#e94560")
        + _stat_row("Commissions closers (18%)", f"− {m['revenue']*0.18:,.0f} €".replace(",", " "), color="#f59e0b")
        + _stat_row("Marge nette estimée",
                    f"{marge_brute - m['revenue']*0.18:,.0f} €".replace(",", " "),
                    f"{(marge_brute - m['revenue']*0.18)/ca_total*100:.1f}%" if ca_total else "—",
                    "#16a34a" if marge_brute >= 0 else "#e94560")
    )

    cost_form = f"""
    <form method="post" action="/admin/finances/costs" style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr auto;gap:8px;align-items:end">
      <input type="hidden" name="token" value="{token}">
      <div>
        <label style="font-size:11px;color:#9ca3af;display:block;margin-bottom:4px">Label</label>
        <input type="text" name="label" required placeholder="ex: Anthropic API"
               style="width:100%;border:1px solid #d1d5db;border-radius:6px;padding:7px 10px;font-size:13px">
      </div>
      <div>
        <label style="font-size:11px;color:#9ca3af;display:block;margin-bottom:4px">Type</label>
        <select name="type" style="width:100%;border:1px solid #d1d5db;border-radius:6px;padding:7px 10px;font-size:13px">
          <option value="ia">IA</option>
          <option value="marketing">Marketing</option>
          <option value="autre">Autre</option>
        </select>
      </div>
      <div>
        <label style="font-size:11px;color:#9ca3af;display:block;margin-bottom:4px">Fréquence</label>
        <select name="type_freq" style="width:100%;border:1px solid #d1d5db;border-radius:6px;padding:7px 10px;font-size:13px">
          <option value="recurrent">Récurrent</option>
          <option value="ponctuel">Ponctuel</option>
        </select>
      </div>
      <div>
        <label style="font-size:11px;color:#9ca3af;display:block;margin-bottom:4px">Montant (€)</label>
        <input type="number" name="montant" step="0.01" min="0" required placeholder="0.00"
               style="width:100%;border:1px solid #d1d5db;border-radius:6px;padding:7px 10px;font-size:13px">
      </div>
      <button type="submit" style="background:#e94560;color:#fff;border:none;border-radius:6px;
              padding:8px 16px;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap">
        + Ajouter
      </button>
    </form>
    """

    body = f"""
    <h1>Finances</h1>
    <p style="color:#6b7280;font-size:13px;margin-bottom:20px">Revenus, coûts et rentabilité</p>
    {kpis}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
      <div class="card">
        <h2>CA par offre</h2>
        {rev_rows}
      </div>
      <div class="card">
        <h2>IA Cost Tracking</h2>
        {ia_rows}
      </div>
    </div>
    <div class="card" style="margin-bottom:16px">
      <h2>Coûts déclarés</h2>
      {cost_table}
      {cost_form}
    </div>
    <div class="card">
      <h2>Résultat</h2>
      {result_rows}
    </div>
    """
    return _page("Finances", "finances", token, body)


@router.post("/admin/finances/costs")
async def finances_add_cost(request: Request):
    form = await request.form()
    token = form.get("token", "")
    if token != admin_token():
        return RedirectResponse("/admin/login", status_code=302)
    try:
        costs = _load_costs()
        costs.append({
            "label":     str(form.get("label", "")).strip(),
            "type":      str(form.get("type", "autre")),
            "type_freq": str(form.get("type_freq", "ponctuel")),
            "montant":   float(form.get("montant", 0)),
            "added_at":  datetime.utcnow().isoformat(),
        })
        _save_costs(costs)
    except Exception as e:
        log.warning("finances/costs error: %s", e)
    return RedirectResponse(f"/admin/finances?token={token}", status_code=303)


@router.post("/admin/finances/costs/delete")
async def finances_delete_cost(request: Request):
    form = await request.form()
    token = form.get("token", "")
    if token != admin_token():
        return RedirectResponse("/admin/login", status_code=302)
    try:
        idx = int(form.get("idx", -1))
        costs = _load_costs()
        if 0 <= idx < len(costs):
            costs.pop(idx)
            _save_costs(costs)
    except Exception as e:
        log.warning("finances/costs/delete error: %s", e)
    return RedirectResponse(f"/admin/finances?token={token}", status_code=303)


# ── Pipeline health ──────────────────────────────────────────────────────────

@router.get("/admin/pipeline-health", response_class=HTMLResponse)
async def pipeline_health(request: Request):
    token, redir = _check(request)
    if redir:
        return redir

    from sqlalchemy import func
    from datetime import timedelta

    db = SessionLocal()
    now = datetime.utcnow()

    cfg = db.get(LeadProvisioningConfigDB, "default")
    stuck_segs = db.query(SireneSegmentDB).filter(SireneSegmentDB.status == "running").all()

    from ...models import SireneSuspectDB
    available = (
        db.query(SireneSuspectDB.profession_id, func.count().label("n"))
        .filter(SireneSuspectDB.provisioned_at.is_(None), SireneSuspectDB.actif == True)
        .group_by(SireneSuspectDB.profession_id)
        .order_by(func.count().desc())
        .limit(20)
        .all()
    )

    v3_history = []
    for d in range(7, 0, -1):
        day_start = (now - timedelta(days=d)).replace(hour=0, minute=0, second=0)
        day_end = day_start + timedelta(days=1)
        count = db.query(func.count(V3ProspectDB.token)).filter(
            V3ProspectDB.created_at >= day_start,
            V3ProspectDB.created_at < day_end,
        ).scalar()
        v3_history.append((day_start.strftime("%d/%m"), count))

    db.close()

    alerts = []
    if cfg and cfg.last_run:
        age_h = (now - cfg.last_run).total_seconds() / 3600
        if age_h > 26:
            alerts.append(f"⚠️ provision_leads n'a pas tourné depuis {age_h:.0f}h")
    if stuck_segs:
        alerts.append(f"⚠️ {len(stuck_segs)} segment(s) bloqué(s) en status=running")
    if not available:
        alerts.append("⚠️ Aucun suspect disponible à provisionner")

    alert_html = "".join(
        f'<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:12px 16px;margin-bottom:10px;color:#b91c1c">{a}</div>'
        for a in alerts
    ) or '<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:12px 16px;color:#166534">✅ Aucune alerte — pipeline opérationnel</div>'

    if cfg:
        last_run_str = cfg.last_run.strftime("%Y-%m-%d %H:%M UTC") if cfg.last_run else "jamais"
        age_str = f"{(now - cfg.last_run).total_seconds() / 3600:.1f}h" if cfg.last_run else "—"
        cfg_html = f"""
        <table style="width:100%;border-collapse:collapse;font-size:14px">
          <tr><td style="padding:8px;color:#6b7280">Active</td><td style="padding:8px;font-weight:600">{'✅ oui' if cfg.active else '❌ non'}</td></tr>
          <tr style="background:#f9fafb"><td style="padding:8px;color:#6b7280">Jours</td><td style="padding:8px">{cfg.days or '(tous)'}</td></tr>
          <tr><td style="padding:8px;color:#6b7280">hour_utc</td><td style="padding:8px">{cfg.hour_utc} {'— toutes les heures éligibles' if cfg.hour_utc == -1 else ''}</td></tr>
          <tr style="background:#f9fafb"><td style="padding:8px;color:#6b7280">Leads/run</td><td style="padding:8px">{cfg.leads_per_run}</td></tr>
          <tr><td style="padding:8px;color:#6b7280">Dernier run</td><td style="padding:8px">{last_run_str} <span style="color:#9ca3af">({age_str})</span></td></tr>
          <tr style="background:#f9fafb"><td style="padding:8px;color:#6b7280">Dernière production</td><td style="padding:8px">{cfg.last_count} leads</td></tr>
        </table>"""
    else:
        cfg_html = "<p style='color:#ef4444'>Config introuvable</p>"

    stuck_html = "".join(
        f'<div style="font-family:monospace;font-size:13px;padding:4px 0;color:#b91c1c">{s.profession_id}|{s.code_naf}|{s.departement}</div>'
        for s in stuck_segs
    ) or '<span style="color:#6b7280;font-size:13px">Aucun</span>'

    avail_rows = "".join(
        f'<tr style="{"" if i%2 else "background:#f9fafb"}"><td style="padding:6px 12px">{r.profession_id}</td><td style="padding:6px 12px;text-align:right;font-weight:600">{r.n:,}</td></tr>'
        for i, r in enumerate(available)
    )
    avail_html = f'<table style="width:100%;border-collapse:collapse;font-size:13px">{avail_rows}</table>'

    max_v = max((c for _, c in v3_history), default=1) or 1
    bars = "".join(
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">'
        f'<span style="width:40px;font-size:12px;color:#6b7280">{d}</span>'
        f'<div style="background:#1e3a5f;height:20px;width:{max(1, int(c/max_v*200))}px;border-radius:3px"></div>'
        f'<span style="font-size:13px;color:#374151">{c}</span>'
        f'</div>'
        for d, c in v3_history
    )

    body = f"""
    <h1 style="font-size:22px;font-weight:700;margin-bottom:24px">Pipeline Health</h1>
    <div style="margin-bottom:24px">{alert_html}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
      <div>
        <div class="card"><h2>Config provision_leads</h2>{cfg_html}</div>
        <div class="card" style="margin-top:24px"><h2>Segments bloqués</h2>{stuck_html}</div>
      </div>
      <div>
        <div class="card"><h2>V3 créés / 7 jours</h2>{bars}</div>
        <div class="card" style="margin-top:24px"><h2>Suspects disponibles (top 20)</h2>{avail_html}</div>
      </div>
    </div>
    <div style="margin-top:24px">
      <form method="post" action="/admin/pipeline-health/force-provision" style="display:inline">
        <input type="hidden" name="token" value="{token}">
        <button type="submit" style="background:#1e3a5f;color:#fff;padding:10px 20px;border:none;border-radius:8px;cursor:pointer;font-size:14px">
          ▶ Force-run provision_leads maintenant
        </button>
      </form>
    </div>"""

    return _page("Pipeline Health", "", token, body)


@router.post("/admin/pipeline-health/force-provision")
async def pipeline_force_provision(request: Request):
    form = await request.form()
    token = form.get("token", "")
    if token != admin_token():
        return RedirectResponse("/admin/login", status_code=302)
    from ... import scheduler as sched_mod
    import threading
    threading.Thread(target=sched_mod._job_provision_leads, kwargs={"force": True}, daemon=True).start()
    return RedirectResponse(f"/admin/pipeline-health?token={token}", status_code=303)
