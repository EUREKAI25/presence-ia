"""
Admin UI — GET /admin  (protégé par ADMIN_TOKEN header ou ?token=)
Interface HTML légère pour piloter le pipeline sans Swagger.
"""
import os
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_get_campaign, db_list_campaigns, db_list_prospects, db_get_prospect, jl, db_dashboard_stats, db_cost_stats
from ...models import ProspectStatus, ProspectDB, V3ProspectDB, V3CityImageDB, ProspectionTargetDB
from ._nav import admin_nav


import unicodedata as _uc

def _norm_city(s):
    s = s.lower().strip()
    return ''.join(c for c in _uc.normalize('NFD', s) if _uc.category(c) != 'Mn')

_PREFECTURES_NORM = {
    'bourg-en-bresse','laon','moulins','digne-les-bains','gap','nice',
    'privas','charleville-mezieres','foix','troyes','carcassonne','rodez',
    'marseille','caen','aurillac','angouleme','la rochelle','bourges',
    'tulle','ajaccio','bastia','dijon','saint-brieuc','gueret',
    'perigueux','besancon','valence','evreux','chartres','quimper',
    'nimes','toulouse','auch','bordeaux','montpellier','rennes',
    'chateauroux','tours','grenoble','lons-le-saunier','mont-de-marsan',
    'blois','saint-etienne','le puy-en-velay','nantes','orleans',
    'cahors','agen','mende','angers','saint-lo','chalons-en-champagne',
    'chaumont','laval','nancy','bar-le-duc','vannes','metz','nevers',
    'lille','beauvais','alencon','arras','clermont-ferrand','pau',
    'tarbes','perpignan','strasbourg','colmar','lyon','vesoul',
    'macon','le mans','chambery','annecy','paris','rouen','melun',
    'versailles','niort','amiens','albi','montauban','toulon',
    'avignon','la roche-sur-yon','poitiers','limoges','epinal',
    'auxerre','belfort','evry-courcouronnes','nanterre','bobigny',
    'creteil','cergy','pontoise','basse-terre','fort-de-france',
    'cayenne','saint-denis','mamoudzou',
}

def _build_alerts(db, token: str = "") -> tuple[str, str]:
    """
    Calcule les alertes prioritaires.
    Retourne (alerts_html, modals_html).
    - Alerte images : affichée seulement si prospection active OU images manquantes bloquantes
    - Alerte bloqués IA : seulement si ia_results null ET job refresh_ia désactivé (vrai blocage)
    """
    items = []
    modals = []

    # 1. Scoring IA désactivé + leads en attente (vrai blocage — job refresh_ia commenté)
    try:
        sans_scoring = db.query(V3ProspectDB).filter(
            V3ProspectDB.email.isnot(None),
            V3ProspectDB.ia_results.is_(None),
            V3ProspectDB.sent_at.is_(None),
        ).count()
        if sans_scoring > 0:
            items.append(("pipeline",
                f"{sans_scoring} leads avec email bloqués — scoring IA désactivé (job refresh_ia off)",
                "/admin/scheduler"))
    except Exception:
        pass

    # 2. Villes sans visuel — UNIQUEMENT si prospection active (ProspectionTargetDB active=True)
    try:
        from ...models import CityHeaderDB
        prospection_active = db.query(ProspectionTargetDB).filter(
            ProspectionTargetDB.active == True
        ).first() is not None

        cities_with_image = {h.city.lower() for h in db.query(CityHeaderDB).all()}
        ready_leads = db.query(V3ProspectDB.city).filter(
            V3ProspectDB.email.isnot(None),
            V3ProspectDB.contacted == False,
        ).distinct().all()
        sans_visuel = sorted({
            city for (city,) in ready_leads
            if city and city.lower() not in cities_with_image
            and _norm_city(city) in _PREFECTURES_NORM
        })
        if sans_visuel and prospection_active:
            modal_id = "modal_images"
            cities_html = "".join(
                f'<div style="display:flex;align-items:center;justify-content:space-between;'
                f'padding:8px 0;border-bottom:1px solid #fee2e2">'
                f'<span style="font-size:13px;color:#374151;font-weight:600">{c}</span>'
                f'<label style="background:#ef4444;color:#fff;border-radius:5px;padding:5px 12px;'
                f'font-size:12px;cursor:pointer;white-space:nowrap">'
                f'&#128247; Upload'
                f'<input type="file" accept="image/*" style="display:none" '
                f'onchange="uploadCityHeaderFile(\'{c}\',\'{token}\',this)">'
                f'</label>'
                f'</div>'
                for c in sans_visuel
            )
            modals.append(f'''
<div id="{modal_id}" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;align-items:center;justify-content:center">
  <div style="background:#fff;border-radius:12px;padding:24px;width:420px;max-height:80vh;overflow-y:auto;position:relative">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h3 style="margin:0;font-size:15px;color:#991b1b">Images manquantes — {len(sans_visuel)} préfecture(s)</h3>
      <button onclick="document.getElementById('{modal_id}').style.display='none'"
        style="background:none;border:none;font-size:18px;cursor:pointer;color:#6b7280">✕</button>
    </div>
    <p style="font-size:12px;color:#6b7280;margin:0 0 14px">
      Ces villes ont des leads prêts mais pas d'image — la landing page ne peut pas être affichée.
    </p>
    {cities_html}
  </div>
</div>''')
            items.append(("visuel",
                f"{len(sans_visuel)} préfecture(s) sans image — landing bloquée",
                None, modal_id))
    except Exception:
        pass

    # 3. RDV passés non traités
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import MeetingDB, MeetingStatus
        from datetime import datetime as _dt
        mdb = MktSession()
        try:
            non_traites = mdb.query(MeetingDB).filter(
                MeetingDB.project_id == "presence-ia",
                MeetingDB.status == MeetingStatus.scheduled,
                MeetingDB.scheduled_at < _dt.utcnow()
            ).count()
            if non_traites > 0:
                items.append(("rdv", f"{non_traites} RDV passés non traités", "/admin/crm"))
        finally:
            mdb.close()
    except Exception:
        pass

    # 4. Clés API invalides
    try:
        import os as _os, requests as _req
        _API_CHECKS = [
            ("OpenAI",    _os.getenv("OPENAI_API_KEY", ""),
             "https://api.openai.com/v1/models",
             lambda k: {"Authorization": f"Bearer {k}"}),
            ("Gemini",    _os.getenv("GEMINI_API_KEY", ""), None, None),
            ("Anthropic", _os.getenv("ANTHROPIC_API_KEY", ""),
             "https://api.anthropic.com/v1/models",
             lambda k: {"x-api-key": k, "anthropic-version": "2023-06-01"}),
        ]
        bad_keys = []
        for _name, _key, _url, _hfn in _API_CHECKS:
            if not _key:
                bad_keys.append(_name)
                continue
            try:
                if _name == "Gemini":
                    _url = f"https://generativelanguage.googleapis.com/v1beta/models?key={_key}"
                    _r = _req.get(_url, timeout=4)
                else:
                    _r = _req.get(_url, headers=_hfn(_key), timeout=4)
                if _r.status_code in (401, 403):
                    bad_keys.append(_name)
            except Exception:
                pass
        if bad_keys:
            items.append(("apikey", f"Clés API invalides : {', '.join(bad_keys)}", "/admin/scheduler"))
    except Exception:
        pass

    modals_html = "\n".join(modals)

    # Pas d'alertes → retourner chaîne vide (zone non affichée)
    if not items:
        return "", modals_html

    color_map = {
        "visuel":   ("#fef2f2", "#991b1b", "#ef4444"),
        "rdv":      ("#fff7ed", "#9a3412", "#f97316"),
        "pipeline": ("#fef3c7", "#92400e", "#d97706"),
        "apikey":   ("#fef2f2", "#991b1b", "#dc2626"),
    }
    rows = ""
    for item in items:
        kind, msg = item[0], item[1]
        href     = item[2] if len(item) > 2 else None
        modal_id = item[3] if len(item) > 3 else None
        bg, txt, dot_col = color_map.get(kind, ("#fef9c3", "#713f12", "#eab308"))

        if modal_id:
            rows += (
                f'<div onclick="document.getElementById(\'{modal_id}\').style.display=\'flex\'" '
                f'style="display:flex;align-items:center;gap:10px;padding:9px 12px;'
                f'background:{bg};border-radius:6px;cursor:pointer;margin-bottom:0">'
                f'<span style="width:7px;height:7px;border-radius:50%;background:{dot_col};flex-shrink:0"></span>'
                f'<span style="color:{txt};font-size:13px;font-weight:600;flex:1">{msg}</span>'
                f'<span style="color:{txt};font-size:12px;white-space:nowrap">&#128247; Uploader →</span>'
                f'</div>'
            )
        else:
            rows += (
                f'<a href="{href}?token={token}" '
                f'style="display:flex;align-items:center;gap:10px;padding:9px 12px;'
                f'background:{bg};border-radius:6px;text-decoration:none;margin-bottom:0">'
                f'<span style="width:7px;height:7px;border-radius:50%;background:{dot_col};flex-shrink:0"></span>'
                f'<span style="color:{txt};font-size:13px;font-weight:600;flex:1">{msg}</span>'
                f'<span style="color:{txt};font-size:12px;white-space:nowrap">→</span>'
                f'</a>'
            )

    alerts_zone = (
        f'<div style="background:#fff7ed;border:1.5px solid #fed7aa;border-radius:8px;'
        f'padding:14px 16px;display:flex;flex-direction:column;gap:8px">'
        f'<div style="font-size:11px;font-weight:700;color:#c2410c;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:2px">&#9888; Alertes à traiter</div>'
        f'{rows}'
        f'</div>'
    )
    return alerts_zone, modals_html

def _build_cron_section(db, token: str = "") -> str:
    """Section Pipeline — statut des jobs cron (last_run + next_run)."""
    from datetime import datetime as _dt
    now = _dt.utcnow()

    def _fmt_dt(dt) -> str:
        if dt is None:
            return '<span style="color:#9ca3af">—</span>'
        if hasattr(dt, "tzinfo") and dt.tzinfo:
            from datetime import timezone
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        delta = now - dt
        if delta.total_seconds() < 60:
            return '<span style="color:#16a34a">à l\'instant</span>'
        if delta.total_seconds() < 3600:
            return f'<span style="color:#16a34a">il y a {int(delta.total_seconds()//60)} min</span>'
        if delta.days == 0:
            return f'il y a {int(delta.total_seconds()//3600)}h'
        return dt.strftime("%d/%m %H:%M")

    def _fmt_next(dt) -> str:
        if dt is None:
            return '<span style="color:#9ca3af">désactivé</span>'
        if hasattr(dt, "tzinfo") and dt.tzinfo:
            from datetime import timezone
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        delta = dt - now
        if delta.total_seconds() < 0:
            return '<span style="color:#ef4444">en retard</span>'
        if delta.total_seconds() < 3600:
            return f'<span style="color:#f59e0b">dans {int(delta.total_seconds()//60)} min</span>'
        if delta.days == 0:
            return f'dans {int(delta.total_seconds()//3600)}h'
        return f'dans {delta.days}j'

    # Récupérer ProspectionTargetDB.last_run pour le job prospection
    try:
        last_prospect = db.query(ProspectionTargetDB).filter(
            ProspectionTargetDB.active == True,
            ProspectionTargetDB.last_run.isnot(None)
        ).order_by(ProspectionTargetDB.last_run.desc()).first()
        last_prospect_run = last_prospect.last_run if last_prospect else None
        prospect_count   = last_prospect.last_count if last_prospect else 0
    except Exception:
        last_prospect_run, prospect_count = None, 0

    # EnrichmentConfigDB + LeadProvisioningConfigDB
    try:
        from ...models import EnrichmentConfigDB, LeadProvisioningConfigDB
        enc = db.get(EnrichmentConfigDB, "default")
        prc = db.get(LeadProvisioningConfigDB, "default")
    except Exception:
        enc = prc = None

    # Last outbound (max sent_at)
    try:
        from sqlalchemy import func as _func
        last_sent = db.query(_func.max(V3ProspectDB.sent_at)).scalar()
    except Exception:
        last_sent = None

    # Jobs scheduler (next_run)
    try:
        from ...scheduler import get_jobs_status
        jobs_map = {j["id"]: j for j in get_jobs_status()}
    except Exception:
        jobs_map = {}

    def _row(label, last_run_dt, next_run_dt, freq, detail="", status_ok=True):
        dot = '#16a34a' if status_ok else '#ef4444'
        return (
            f'<tr style="border-bottom:1px solid #f3f4f6">'
            f'<td style="padding:8px 10px;font-size:13px;font-weight:600;display:flex;align-items:center;gap:8px">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:{dot};flex-shrink:0;display:inline-block"></span>'
            f'{label}</td>'
            f'<td style="padding:8px 10px;font-size:12px;color:#6b7280">{freq}</td>'
            f'<td style="padding:8px 10px;font-size:12px">{_fmt_dt(last_run_dt)}'
            f'{"<br><span style=font-size:11px;color:#9ca3af>" + detail + "</span>" if detail else ""}</td>'
            f'<td style="padding:8px 10px;font-size:12px">{_fmt_next(next_run_dt)}</td>'
            f'</tr>'
        )

    # Scoring IA — job désactivé
    scoring_row = (
        f'<tr style="border-bottom:1px solid #f3f4f6;background:#fef9c3">'
        f'<td style="padding:8px 10px;font-size:13px;font-weight:600;display:flex;align-items:center;gap:8px">'
        f'<span style="width:7px;height:7px;border-radius:50%;background:#d97706;flex-shrink:0;display:inline-block"></span>'
        f'Scoring IA (paires)</td>'
        f'<td style="padding:8px 10px;font-size:12px;color:#6b7280">Lun/Jeu/Dim 3×/jour</td>'
        f'<td style="padding:8px 10px;font-size:12px">—</td>'
        f'<td style="padding:8px 10px;font-size:12px;color:#d97706;font-weight:600">⚠ Job désactivé</td>'
        f'</tr>'
    )

    enrich_ok  = enc.active if enc else False
    enrich_run = enc.last_run if enc else None
    enrich_count = f"{enc.last_count} suspects" if enc else ""
    prov_ok    = prc.active if prc else False
    prov_run   = prc.last_run if prc else None

    rows = (
        _row("Prospection Google Places", last_prospect_run,
             jobs_map.get("run_due_targets", {}).get("next_run"),
             "toutes les heures",
             f"{prospect_count} trouvés" if prospect_count else "")
        + _row("Enrichissement SIRENE→Places", enrich_run,
               jobs_map.get("auto_enrich", {}).get("next_run"),
               "toutes les heures",
               enrich_count, enrich_ok)
        + scoring_row
        + _row("Provisioning leads", prov_run,
               jobs_map.get("provision_leads", {}).get("next_run"),
               "toutes les heures", "", prov_ok)
        + _row("Envoi emails (outbound)", last_sent,
               jobs_map.get("outbound", {}).get("next_run"),
               "tous les jours à 9h UTC")
        + _row("Email warming", None,
               jobs_map.get("email_warming", {}).get("next_run"),
               "~toutes les 4h")
    )

    return (
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="border-bottom:2px solid #e5e7eb">'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Job</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Fréquence</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Dernier run</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Prochain run</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>'
    )


router = APIRouter(tags=["Admin"])


def _check_token(request: Request):
    """Retourne None si valide, RedirectResponse vers login si invalide."""
    token = (request.headers.get("X-Admin-Token")
             or request.query_params.get("token")
             or request.cookies.get("admin_token", ""))
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        return RedirectResponse("/admin/login", status_code=302)
    return None


def _admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "changeme")


# ── Dashboard HTML ─────────────────────────────────────────────────────────


def _period_bounds(period: str, date_from: str = None, date_to: str = None):
    """Retourne (dt_from, dt_to, label, prev_from, prev_to) pour une période."""
    today = date.today()
    if period == "exercice":
        # Exercice en cours : démarre le 1er mars
        year = today.year if today.month >= 3 else today.year - 1
        dt_from = datetime(year, 3, 1)
        dt_to   = datetime.combine(today, datetime.max.time())
        label   = f"Exercice {year}-{year+1}"
        delta   = dt_to - dt_from
        prev_from = dt_from - delta
        prev_to   = dt_from
    elif period == "mois":
        dt_from = datetime(today.year, today.month, 1)
        dt_to   = datetime.combine(today, datetime.max.time())
        label   = today.strftime("%B %Y")
        # Mois précédent
        if today.month == 1:
            prev_from = datetime(today.year - 1, 12, 1)
            prev_to   = datetime(today.year, 1, 1)
        else:
            prev_from = datetime(today.year, today.month - 1, 1)
            prev_to   = dt_from
    elif period == "semaine":
        monday = today - timedelta(days=today.weekday())
        dt_from = datetime.combine(monday, datetime.min.time())
        dt_to   = datetime.combine(today, datetime.max.time())
        label   = f"Semaine du {monday.strftime('%d/%m')}"
        prev_from = dt_from - timedelta(weeks=1)
        prev_to   = dt_from
    elif period == "custom" and date_from and date_to:
        dt_from = datetime.strptime(date_from, "%Y-%m-%d")
        dt_to   = datetime.strptime(date_to,   "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        label   = f"{date_from} → {date_to}"
        delta   = dt_to - dt_from
        prev_from = dt_from - delta - timedelta(seconds=1)
        prev_to   = dt_from
    else:  # défaut = exercice
        return _period_bounds("exercice")
    return dt_from, dt_to, label, prev_from, prev_to


def _delta_html(curr: int, prev: int) -> str:
    if prev == 0:
        return '<span style="color:#6b7280;font-size:10px">—</span>'
    d = curr - prev
    pct = d / prev * 100
    color = "#16a34a" if d >= 0 else "#dc2626"
    arrow = "▲" if d >= 0 else "▼"
    return f'<span style="color:{color};font-size:10px;font-weight:600">{arrow} {abs(pct):.0f}%</span>'


def _kpi(label, val, sub="", delta_html="", color="#e94560"):
    return (
        f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px">'
        f'<div style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">{label}</div>'
        f'<div style="font-size:26px;font-weight:700;color:{color};line-height:1">{val}</div>'
        f'{"<div style=margin-top:6px;display:flex;align-items:center;gap:8px>" + (f"<span style=font-size:11px;color:#6b7280>{sub}</span>" if sub else "") + delta_html + "</div>" if sub or delta_html else ""}'
        f'</div>'
    )


def _pct(a, b):
    return f"{a/b*100:.0f}%" if b else "—"


def _funnel_arrow():
    return '<div style="display:flex;align-items:center;justify-content:center;color:#d1d5db;font-size:18px;padding:0 2px">→</div>'


def _build_slot_coverage(need: dict | None) -> str:
    """Card pilotage pipeline — couverture créneaux Calendly + statut outbound."""
    if not need:
        return ""

    statut     = need["statut"]
    taux       = need["taux_couverture"]
    proche     = need["proche"]
    bootstrap  = need["bootstrap"]
    source     = need.get("source_slots", "config")

    statut_colors = {
        "saturated": ("#fef2f2", "#ef4444", "Saturé"),
        "running":   ("#f0fdf4", "#16a34a", "En cours"),
        "idle":      ("#f9fafb", "#6b7280", "En attente"),
    }
    bg, col, label = statut_colors.get(statut, ("#f9fafb", "#6b7280", statut))

    # Barre de progression couverture
    pct_bar   = min(100, taux)
    bar_col   = "#ef4444" if taux >= 85 else ("#16a34a" if taux >= 70 else "#f59e0b")

    # Zones (proche / moyen / lointain)
    def _zone(name, data):
        t = data["total"]
        r = data["reserves"]
        d = data["disponibles"]
        pct = round(r / t * 100) if t > 0 else 0
        return (
            f'<div style="text-align:center;padding:8px 12px;background:#f9fafb;border-radius:6px">'
            f'<div style="font-size:10px;color:#9ca3af;font-weight:600;text-transform:uppercase;margin-bottom:3px">{name}</div>'
            f'<div style="font-size:16px;font-weight:800;color:#374151">{r}<span style="font-size:11px;color:#9ca3af">/{t}</span></div>'
            f'<div style="font-size:11px;color:#6b7280">{d} dispo · {pct}%</div>'
            f'</div>'
        )

    zones = (
        _zone("J+2→J+4 ★", proche)
        + _zone("J+5→J+7", need["moyen"])
        + _zone("J+8→J+14", need["lointain"])
    )

    bootstrap_badge = (
        f'<span style="background:#fef9c3;color:#854d0e;font-size:10px;font-weight:700;'
        f'padding:2px 7px;border-radius:10px;margin-left:8px">BOOTSTRAP 2%</span>'
        if bootstrap else ""
    )
    source_badge = (
        f'<span style="font-size:10px;color:#9ca3af;margin-left:6px">({source})</span>'
    )

    return (
        f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'<span style="font-size:12px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.05em">Pilotage pipeline</span>'
        f'{bootstrap_badge}{source_badge}'
        f'</div>'
        f'<span style="background:{bg};color:{col};font-size:11px;font-weight:700;padding:3px 10px;border-radius:12px;border:1px solid {col}20">{label}</span>'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;margin-bottom:14px">'
        + _kpi("Couverture proche", f"{taux:.0f}%", "objectif 70–85%", color=bar_col)
        + _kpi("Leads en file", f'{need["leads_en_file"]:,}', "scorés IA · non envoyés", color="#6366f1")
        + _kpi("Leads nécessaires", f'{need["leads_necessaires"]:,}', f'slots dispo / {need["taux_conversion"]*100:.0f}%', color="#0ea5e9")
        + _kpi("À générer", f'{need["leads_manquants"]:,}', "cap prochain run", color="#e94560" if need["leads_manquants"] > 0 else "#10b981")
        + f'</div>'
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px">{zones}</div>'
        f'<div style="background:#f3f4f6;border-radius:6px;height:8px;overflow:hidden">'
        f'<div style="background:{bar_col};height:100%;width:{pct_bar:.0f}%;transition:width .3s"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;margin-top:4px">'
        f'<span style="font-size:10px;color:#9ca3af">0%</span>'
        f'<span style="font-size:10px;color:#f59e0b;font-weight:600">70% min</span>'
        f'<span style="font-size:10px;color:#ef4444;font-weight:600">85% stop</span>'
        f'<span style="font-size:10px;color:#9ca3af">100%</span>'
        f'</div>'
        f'</div>'
    )


def _build_cost_section(costs: dict) -> str:
    """Accordéon coûts API — Google Places + Gemini."""
    cpl = f"${costs['cost_per_lead']:.4f}" if costs["cost_per_lead"] is not None else "—"
    total_fmt = f"${costs['total_cost']:.4f}"

    job_rows = "".join(
        f'<tr style="border-bottom:1px solid #1a1a2e">'
        f'<td style="padding:7px 10px;font-size:12px;color:#9ca3af">{j["date"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;font-weight:600">{j["job_id"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;color:#6b7280">{j["paire"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;text-align:right;color:#0ea5e9">{j["google"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;text-align:right;color:#8b5cf6">{j["gemini"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;text-align:right;color:#10b981">{j["leads"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;text-align:right;font-weight:700;color:#e94560">${j["cost"]:.4f}</td>'
        f'</tr>'
        for j in costs["recent_jobs"]
    ) or f'<tr><td colspan="7" style="padding:14px;color:#6b7280;font-size:12px;text-align:center">Aucune donnée — le tracking démarre au prochain job d\'enrichissement</td></tr>'

    return (
        f'<details style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;margin-bottom:12px;overflow:hidden">'
        f'<summary style="padding:11px 16px;cursor:pointer;font-size:13px;font-weight:700;display:flex;align-items:center;gap:10px;list-style:none">'
        f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#0ea5e9;flex-shrink:0"></span>'
        f'Coûts API'
        f'<span style="margin-left:auto;font-size:12px;font-weight:400;color:#6b7280">'
        f'Total {total_fmt} · {costs["total_google"]} appels Places · coût/lead {cpl}'
        f'</span>'
        f'</summary>'
        f'<div style="border-top:1px solid #f3f4f6;padding:14px 16px">'
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px">'
        + _kpi("Total coût", total_fmt, "Google Places cumulé", color="#e94560")
        + _kpi("Appels Places", f'{costs["total_google"]:,}', f'@$0.017/appel', color="#0ea5e9")
        + _kpi("Leads générés", f'{costs["total_leads"]:,}', "contacts créés", color="#10b981")
        + _kpi("Coût / lead", cpl, "coût total ÷ leads", color="#8b5cf6")
        + f'</div>'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="border-bottom:2px solid #e5e7eb">'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Date</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Job</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Paire</th>'
        f'<th style="text-align:right;padding:7px 10px;font-size:11px;color:#0ea5e9">Places</th>'
        f'<th style="text-align:right;padding:7px 10px;font-size:11px;color:#8b5cf6">Gemini</th>'
        f'<th style="text-align:right;padding:7px 10px;font-size:11px;color:#10b981">Leads</th>'
        f'<th style="text-align:right;padding:7px 10px;font-size:11px;color:#e94560">Coût $</th>'
        f'</tr></thead><tbody>{job_rows}</tbody></table>'
        f'</div>'
        f'</details>'
    )


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db),
                    period: str = "exercice", date_from: str = None, date_to: str = None):
    if (r := _check_token(request)) is not None: return r
    token = _admin_token()

    dt_from, dt_to, period_label, prev_from, prev_to = _period_bounds(period, date_from, date_to)

    s  = db_dashboard_stats(db, dt_from, dt_to)
    sp = db_dashboard_stats(db, prev_from, prev_to)
    costs = db_cost_stats(db)

    # Slot coverage (Calendly)
    try:
        from ...scheduler import compute_outbound_need
        slot_need = compute_outbound_need()
    except Exception:
        slot_need = None

    nav = admin_nav(token, "")
    alerts_html, modals_html = _build_alerts(db, token)
    cron_html = _build_cron_section(db, token)

    # ── Entonnoir 1 : Acquisition ──
    n_acq = [
        ("Suspects SIRENE",  s["suspects_total"],   0,              "#6366f1", f"total DB · période : {s['suspects']:,}"),
        ("Site trouvé",      s["enrichis"],          sp["enrichis"], "#8b5cf6", _pct(s["enrichis"], s["suspects_total"]) + " des suspects"),
        ("Email / mobile",   s["contactables_total"],sp["contactables"],"#0ea5e9",_pct(s["contactables_total"], s["enrichis"]) + " des enrichis"),
        ("Scoré IA",         s["ia_scored"],         0,              "#06b6d4", f"en file · {s['sans_scoring_ia']} sans score"),
        ("Envoyés",          s["envoyes"],           sp["envoyes"],  "#10b981", _pct(s["envoyes"], s["contactables_total"]) + " des contactables"),
    ]
    funnel_html = '<div style="display:grid;grid-template-columns:repeat(5,1fr) repeat(4,auto);gap:4px;align-items:center">'
    for i, (lbl, val, prev, col, sub) in enumerate(n_acq):
        funnel_html += _kpi(lbl, f"{val:,}", sub, _delta_html(val, prev), col)
        if i < len(n_acq) - 1:
            funnel_html += _funnel_arrow()
    funnel_html += "</div>"

    # ── Entonnoir 2 : Conversion ──
    conv_items = [
        ("Envoyés",      s["envoyes"],    sp["envoyes"],    "#6366f1", "base"),
        ("Ouverts",      s["ouvertures"], sp["ouvertures"], "#8b5cf6", _pct(s["ouvertures"], s["envoyes"]) + " des envoyés"),
        ("Réponses +",   s["reponses"],   sp["reponses"],   "#0ea5e9", _pct(s["reponses"], s["envoyes"]) + " des envoyés"),
        ("RDV pris",     s["rdv"],        sp["rdv"],        "#10b981", _pct(s["rdv"], s["reponses"]) + " des réponses"),
        ("Deals signés", s["deals"],      sp["deals"],      "#e94560", _pct(s["deals"], s["rdv"]) + " des RDV"),
    ]
    conv_html = '<div style="display:grid;grid-template-columns:repeat(5,1fr) repeat(4,auto);gap:4px;align-items:center">'
    for i, (lbl, val, prev, col, sub) in enumerate(conv_items):
        conv_html += _kpi(lbl, f"{val:,}", sub, _delta_html(val, prev), col)
        if i < len(conv_items) - 1:
            conv_html += _funnel_arrow()
    conv_html += "</div>"

    # ── CA par offre ──
    ca_total = s.get("ca_total", 0.0)
    ca_par_offre = s.get("ca_par_offre", {})
    ca_rows = "".join(
        f'<tr style="border-bottom:1px solid #f3f4f6">'
        f'<td style="padding:7px 10px;font-size:13px">{offre}</td>'
        f'<td style="padding:7px 10px;font-size:13px;font-weight:700;color:#16a34a">{ca:,.0f} €</td>'
        f'</tr>'
        for offre, ca in sorted(ca_par_offre.items(), key=lambda x: -x[1])
    ) or '<tr><td colspan="2" style="padding:12px;color:#9ca3af;font-size:12px">Aucune vente sur la période</td></tr>'
    ca_fmt = f"{ca_total:,.0f} €".replace(",", "\u202f")

    # Offres en cards inline
    _nb_deals_total = max(s["deals"], 1)
    offre_cards = "".join(
        f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:10px 14px">'
        f'<div style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px">{offre}</div>'
        f'<div style="font-size:17px;font-weight:800;color:#16a34a">{ca:,.0f}\u202f€</div>'
        f'<div style="font-size:11px;color:#9ca3af;margin-top:2px">'
        f'{ca/ca_total*100:.0f}% du CA\u00a0·\u00a0'
        f'{round(ca_par_offre.get(offre, 0) / (ca / max(ca, 1)))} deal(s) '
        f'({0}%)</div>'
        f'</div>'
        for offre, ca in sorted(ca_par_offre.items(), key=lambda x: -x[1])
    ) if ca_par_offre else f'<div style="font-size:12px;color:#9ca3af">Aucune vente sur la période</div>'

    # Reconstruction correcte avec nb deals par offre depuis ca_rows
    offre_cards = ""
    deal_counts: dict = {}
    for offre, ca in sorted(ca_par_offre.items(), key=lambda x: -x[1]):
        n = deal_counts.get(offre, 1)
        pct_ca   = f"{ca / ca_total * 100:.0f}%" if ca_total else "—"
        pct_deal = f"{n / _nb_deals_total * 100:.0f}%" if _nb_deals_total else "—"
        offre_cards += (
            f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:10px 14px">'
            f'<div style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px">{offre}</div>'
            f'<div style="font-size:17px;font-weight:800;color:#16a34a">{ca:,.0f}\u202f€</div>'
            f'<div style="font-size:11px;color:#9ca3af;margin-top:2px">{pct_ca} du CA · {n} deal(s) ({pct_deal})</div>'
            f'</div>'
        )
    if not offre_cards:
        offre_cards = '<div style="font-size:12px;color:#9ca3af">Aucune vente sur la période</div>'

    ca_block = (
        f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:18px 20px">'
        f'<div style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px">CA total · {period_label}</div>'
        f'<div style="font-size:28px;font-weight:800;color:#16a34a;line-height:1;margin-bottom:4px">{ca_fmt}</div>'
        f'<div style="font-size:11px;color:#9ca3af;margin-bottom:14px">{s["deals"]} deal(s)</div>'
        f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px">{offre_cards}</div>'
        f'</div>'
    )

    # ── Taux clés ──
    taux_html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">'
    taux_html += _kpi("Taux ouverture",  _pct(s["ouvertures"], s["envoyes"]),  "ouverts / envoyés",   color="#6366f1")
    taux_html += _kpi("Taux RDV",        _pct(s["rdv"], s["envoyes"]),         "RDV / envoyés",        color="#0ea5e9")
    taux_html += _kpi("Taux closing",    _pct(s["deals"], s["rdv"]),           "deals / RDV",          color="#10b981")
    taux_html += _kpi("Conv. globale",   _pct(s["deals"], s["envoyes"]),       "deals / envoyés",      color="#e94560")
    taux_html += "</div>"

    # ── Closers ──
    top_rows = "".join(
        f'<tr style="border-bottom:1px solid #f3f4f6">'
        f'<td style="padding:7px 10px;font-size:13px;font-weight:600">{i+1}. {c["name"]}</td>'
        f'<td style="padding:7px 10px;font-size:13px;color:#e94560;font-weight:700">{c["deals"]}</td>'
        f'</tr>'
        for i, c in enumerate(s["top_closers"])
    ) or '<tr><td colspan="2" style="padding:12px;color:#9ca3af;font-size:12px">Aucune donnée</td></tr>'

    closers_html = (
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px">'
        + _kpi("Closers actifs", s["closers_actifs"], color="#374151")
        + _kpi("RDV période",    s["rdv"],    _pct(s["rdv"], s["envoyes"]) + " des envoyés",    _delta_html(s["rdv"], sp["rdv"]),    "#10b981")
        + _kpi("Deals période",  s["deals"],  _pct(s["deals"], s["rdv"]) + " des RDV",          _delta_html(s["deals"], sp["deals"]), "#e94560")
        + f'</div>'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="border-bottom:2px solid #e5e7eb">'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Closer</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Deals</th>'
        f'</tr></thead><tbody>{top_rows}</tbody></table>'
    )

    # ── Breakdown métier × ville ──
    bk_rows = "".join(
        f'<tr style="border-bottom:1px solid #f3f4f6">'
        f'<td style="padding:7px 10px;font-size:12px;font-weight:600">{r["profession"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;color:#6b7280">{r["ville"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;color:#0ea5e9">{r["contactables"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;color:#10b981">{r["contactes"]}</td>'
        f'<td style="padding:7px 10px;font-size:12px;color:#6b7280">{_pct(r["contactes"],r["contactables"])}</td>'
        f'</tr>'
        for r in [r for r in s["breakdown"] if _norm_city(r["ville"]) in _PREFECTURES_NORM][:20]
    ) or '<tr><td colspan="5" style="padding:12px;color:#9ca3af;font-size:12px">Aucune donnée</td></tr>'

    breakdown_html = (
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="border-bottom:2px solid #e5e7eb">'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Métier</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Ville</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Contactables</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Contactés</th>'
        f'<th style="text-align:left;padding:7px 10px;font-size:11px;color:#6b7280">Taux</th>'
        f'</tr></thead><tbody>{bk_rows}</tbody></table>'
    )

    # ── Sélecteurs de période ──
    def _pill(p, label):
        active = period == p
        bg = "#e94560" if active else "#f3f4f6"
        col = "#fff" if active else "#374151"
        return f'<a href="/admin?token={token}&period={p}" style="background:{bg};color:{col};border-radius:20px;padding:5px 14px;font-size:12px;font-weight:600;text-decoration:none;white-space:nowrap">{label}</a>'

    period_selector = (
        f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
        + _pill("exercice", "Exercice")
        + _pill("mois", "Ce mois")
        + _pill("semaine", "Cette semaine")
        + f'<form method="get" action="/admin" style="display:flex;gap:6px;align-items:center">'
        + f'<input type="hidden" name="token" value="{token}">'
        + f'<input type="hidden" name="period" value="custom">'
        + f'<input type="date" name="date_from" value="{date_from or ""}" style="border:1px solid #d1d5db;border-radius:6px;padding:4px 8px;font-size:12px">'
        + f'<input type="date" name="date_to"   value="{date_to   or ""}" style="border:1px solid #d1d5db;border-radius:6px;padding:4px 8px;font-size:12px">'
        + f'<button type="submit" style="background:#374151;color:#fff;border:none;border-radius:6px;padding:5px 12px;font-size:12px;cursor:pointer">Go</button>'
        + f'</form>'
        + f'</div>'
    )

    return HTMLResponse(f"""<!DOCTYPE html><html><head>
<meta charset="utf-8"><title>Dashboard — PRESENCE IA</title>
{nav}
<style>
body{{font-family:system-ui,sans-serif;background:#f9fafb;color:#111}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px}}
h2{{font-size:13px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.06em;margin:0 0 14px}}
</style>
</head><body>
{modals_html}
<script>
function uploadCityHeaderFile(city, token, input) {{
  if (!input.files || !input.files[0]) return;
  const fd = new FormData();
  fd.append('file', input.files[0]);
  fd.append('city', city);
  fd.append('token', token);
  fetch('/admin/upload-city-header', {{method:'POST', body:fd}})
    .then(r => r.json())
    .then(d => {{
      if (d.ok) {{
        input.closest('div').querySelector('label').textContent = '✓ ' + city;
        input.closest('div').querySelector('label').style.background = '#16a34a';
      }} else alert('Erreur upload : ' + (d.error || 'inconnue'));
    }});
}}
</script>
<div style="padding:24px;max-width:1400px">

  <!-- En-tête + filtres période -->
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:12px">
    <div>
      <h1 style="font-size:20px;font-weight:700;margin:0">Dashboard</h1>
      <span style="font-size:12px;color:#6b7280">{period_label} — vs période précédente</span>
    </div>
    {period_selector}
  </div>

  <!-- CA + Alertes (côte à côte si alertes, pleine largeur sinon) -->
  {'<div style="display:grid;grid-template-columns:3fr 2fr;gap:12px;margin-bottom:12px">' + ca_block + alerts_html + '</div>' if alerts_html else '<div style="margin-bottom:12px">' + ca_block + '</div>'}

  <!-- Taux clés -->
  <div style="margin-bottom:12px">{taux_html}</div>

  <!-- Pilotage pipeline (slots Calendly) -->
  {_build_slot_coverage(slot_need)}

  <!-- Pipeline / crons (accordéon natif <details>) -->
  <details style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;margin-bottom:12px;overflow:hidden">
    <summary style="padding:11px 16px;cursor:pointer;font-size:13px;font-weight:700;display:flex;align-items:center;gap:10px;list-style:none">
      <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#16a34a;flex-shrink:0"></span>
      Pipeline &amp; crons
    </summary>
    <div style="border-top:1px solid #f3f4f6;padding:14px 16px">{cron_html}</div>
  </details>

  <!-- Entonnoir acquisition -->
  <div style="font-size:10px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;padding-left:2px">Acquisition</div>
  <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-bottom:12px">{funnel_html}</div>

  <!-- Entonnoir conversion -->
  <div style="font-size:10px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;padding-left:2px">Conversion</div>
  <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-bottom:12px">{conv_html}</div>

  <!-- Coûts API (accordéon) -->
  {_build_cost_section(costs)}

</div>
</body></html>""")


@router.get("/admin/campaigns", response_class=HTMLResponse)
def admin_campaigns(request: Request, db: Session = Depends(get_db)):
    if (r := _check_token(request)) is not None: return r
    campaigns = db_list_campaigns(db)
    rows = ""
    for c in campaigns:
        ps = db_list_prospects(db, c.campaign_id)
        counts = {}
        for p in ps:
            counts[p.status] = counts.get(p.status, 0) + 1
        eligible = sum(1 for p in ps if p.eligibility_flag)
        rows += f"""<tr>
            <td><a href="/admin/campaign/{c.campaign_id}?token={_admin_token()}">{c.campaign_id[:8]}…</a></td>
            <td>{c.profession}</td><td>{c.city}</td>
            <td>{len(ps)}</td><td>{eligible}</td>
            <td style="font-size:11px;color:#6b7280">{', '.join(f'{k}:{v}' for k,v in counts.items())}</td>
        </tr>"""

    token = _admin_token()
    nav = admin_nav(token)
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>PRESENCE_IA — Admin</title>
<style>*{{box-sizing:border-box}}body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e;margin:0}}
h1{{color:#1a1a2e;margin-bottom:20px;font-size:18px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);border:1px solid #e5e7eb}}
th{{background:#f9fafb;color:#6b7280;padding:10px;text-align:left;font-size:12px}}
td{{padding:10px;border-bottom:1px solid #e5e7eb;color:#1a1a2e}}a{{color:#e94560}}
.badge{{display:inline-block;background:#e94560;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px}}</style></head>
<body>
{nav}
<div style="padding:24px">
<h1>Pipeline — Campagnes</h1>
<table><tr><th>ID</th><th>Profession</th><th>Ville</th><th>Prospects</th><th>Éligibles</th><th>Statuts</th></tr>
{rows or '<tr><td colspan=6 style="color:#9ca3af;text-align:center">Aucune campagne</td></tr>'}
</table>
<p style="margin-top:16px;color:#9ca3af;font-size:12px">
  <a href="/docs">→ Swagger docs</a> &nbsp;|&nbsp;
  <a href="/admin/scheduler?token={token}">→ Scheduler status</a>
</p></div></body></html>""")


# ── Détail campagne ────────────────────────────────────────────────────────


@router.get("/admin/campaign/{cid}", response_class=HTMLResponse)
def admin_campaign(cid: str, request: Request, db: Session = Depends(get_db)):
    if (r := _check_token(request)) is not None: return r
    c = db_get_campaign(db, cid)
    if not c:
        raise HTTPException(404, "Campagne introuvable")
    ps = db_list_prospects(db, cid)

    def _pill(s):
        color = {"SCANNED": "#3498db", "TESTED": "#9b59b6", "SCORED": "#2ecc71",
                 "READY_TO_SEND": "#f39c12", "SENT_MANUAL": "#27ae60"}.get(s, "#666")
        return f'<span style="background:{color};color:#fff;padding:2px 7px;border-radius:4px;font-size:11px">{s}</span>'

    rows = ""
    for p in ps:
        comps = ", ".join(jl(p.competitors_cited)[:3]) or "—"
        rows += f"""<tr>
            <td><a href="/admin/prospect/{p.prospect_id}?token={_admin_token()}">{p.name}</a></td>
            <td>{p.city}</td><td>{_pill(p.status)}</td>
            <td>{"✅" if p.eligibility_flag else "—"}</td>
            <td>{p.ia_visibility_score or "—"}</td>
            <td style="font-size:11px">{comps}</td>
        </tr>"""

    token = request.query_params.get("token", _admin_token())
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Campagne {cid[:8]}</title>
<style>*{{box-sizing:border-box}}body{{font-family:monospace;background:#f9fafb;color:#1a1a2e;margin:0;padding:24px}}
h1{{color:#1a1a2e}}h2{{color:#6b7280;font-size:14px;margin:4px 0 20px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);border:1px solid #e5e7eb}}
th{{background:#f9fafb;color:#6b7280;padding:10px;text-align:left;font-size:12px}}
td{{padding:10px;border-bottom:1px solid #e5e7eb;color:#1a1a2e}}a{{color:#e94560}}</style></head>
<body>
<h1>Campagne — {c.profession} / {c.city}</h1>
<h2>ID: {cid} &nbsp;|&nbsp; {len(ps)} prospects</h2>
<table><tr><th>Nom</th><th>Ville</th><th>Statut</th><th>Éligible</th><th>Score</th><th>Concurrents</th></tr>
{rows or '<tr><td colspan=6 style="color:#9ca3af;text-align:center">Aucun prospect</td></tr>'}
</table>
<p style="margin-top:16px"><a href="/admin?token={token}">← Retour</a></p>
</body></html>""")


# ── Détail prospect ────────────────────────────────────────────────────────


@router.get("/admin/prospect/{pid}", response_class=HTMLResponse)
def admin_prospect(pid: str, request: Request, db: Session = Depends(get_db)):
    if (r := _check_token(request)) is not None: return r
    p = db_get_prospect(db, pid)
    if not p:
        raise HTTPException(404, "Prospect introuvable")
    token = request.query_params.get("token", _admin_token())

    assets_form = ""
    if p.status in (ProspectStatus.SCORED.value, ProspectStatus.READY_ASSETS.value):
        assets_form = f"""
<h2 style="color:#6b7280;margin-top:32px">Ajouter assets</h2>
<form method="post" action="/api/prospect/{pid}/assets?token={token}"
      style="background:#fff;padding:20px;border-radius:8px;max-width:600px;border:1px solid #e5e7eb;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
  <label style="display:block;margin-bottom:8px;color:#6b7280">video_url</label>
  <input name="video_url" style="width:100%;padding:8px;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;border-radius:4px;margin-bottom:12px" value="{p.video_url or ''}">
  <label style="display:block;margin-bottom:8px;color:#6b7280">screenshot_url</label>
  <input name="screenshot_url" style="width:100%;padding:8px;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;border-radius:4px;margin-bottom:16px" value="{p.screenshot_url or ''}">
  <button type="submit" style="background:#e94560;color:#fff;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,0.1)">Enregistrer assets</button>
</form>"""

    mark_ready_btn = ""
    if p.status == ProspectStatus.READY_ASSETS.value and p.video_url and p.screenshot_url:
        mark_ready_btn = f"""
<form method="post" action="/api/prospect/{pid}/mark-ready?token={token}" style="margin-top:12px">
  <button style="background:#2ecc71;color:#fff;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;font-weight:bold;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
    ✓ Marquer READY_TO_SEND
  </button>
</form>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>{p.name}</title>
<style>*{{box-sizing:border-box}}body{{font-family:monospace;background:#f9fafb;color:#1a1a2e;margin:0;padding:24px}}
h1{{color:#1a1a2e}}dt{{color:#6b7280;font-size:12px;margin-top:12px}}dd{{color:#1a1a2e;margin:4px 0 0 0}}
.box{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;max-width:600px;margin:20px 0;box-shadow:0 1px 3px rgba(0,0,0,0.1)}}
a{{color:#e94560}}</style></head>
<body>
<h1>{p.name}</h1>
<div class="box"><dl>
  <dt>ID</dt><dd>{p.prospect_id}</dd>
  <dt>Statut</dt><dd>{p.status}</dd>
  <dt>Ville</dt><dd>{p.city}</dd>
  <dt>Profession</dt><dd>{p.profession}</dd>
  <dt>Score IA</dt><dd>{p.ia_visibility_score or '—'}/10</dd>
  <dt>Éligible</dt><dd>{"✅ OUI" if p.eligibility_flag else "❌ NON"}</dd>
  <dt>Concurrents</dt><dd>{', '.join(jl(p.competitors_cited)) or '—'}</dd>
  <dt>video_url</dt><dd>{p.video_url or '—'}</dd>
  <dt>screenshot_url</dt><dd>{p.screenshot_url or '—'}</dd>
  <dt>Justification</dt><dd style="color:#6b7280;font-size:12px">{p.score_justification or '—'}</dd>
</dl></div>
{assets_form}
{mark_ready_btn}
<p style="margin-top:24px">
  <a href="/admin/campaign/{p.campaign_id}?token={token}">← Retour campagne</a>
</p>
</body></html>""")


# ── Send Queue ─────────────────────────────────────────────────────────────


@router.get("/admin/send-queue", response_class=HTMLResponse)
def admin_send_queue(request: Request, db: Session = Depends(get_db)):
    if (r := _check_token(request)) is not None: return r
    token = request.query_params.get("token", _admin_token())

    # Tous les prospects éligibles (SCORED, READY_ASSETS, READY_TO_SEND, SENT_MANUAL)
    _ok_statuses = {
        ProspectStatus.SCORED.value,
        ProspectStatus.READY_ASSETS.value,
        ProspectStatus.READY_TO_SEND.value,
        ProspectStatus.SENT_MANUAL.value,
    }
    prospects: list[ProspectDB] = (
        db.query(ProspectDB)
        .filter(ProspectDB.eligibility_flag == True)
        .filter(ProspectDB.status.in_(_ok_statuses))
        .filter(ProspectDB.paid == False)
        .order_by(ProspectDB.ia_visibility_score.desc().nullslast())
        .all()
    )

    def _check(val):
        return "✅" if val else "❌"

    def _pill(s):
        color = {
            "SCORED": "#3498db", "READY_ASSETS": "#9b59b6",
            "READY_TO_SEND": "#f39c12", "SENT_MANUAL": "#27ae60",
        }.get(s, "#666")
        return f'<span style="background:{color};color:#fff;padding:2px 7px;border-radius:4px;font-size:11px">{s}</span>'

    rows = ""
    for p in prospects:
        c1 = (jl(p.competitors_cited) or ["—"])[0]
        email_cell = (
            f'<code style="color:#2ecc71;font-size:11px">{p.email}</code>'
            if p.email else
            f'<button onclick="enrichEmail(\'{p.prospect_id}\')" '
            f'style="background:#fff;color:#374151;border:1px solid #e5e7eb;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:11px">'
            f'Enrichir</button>'
        )
        send_btn = ""
        if p.email and p.status != ProspectStatus.SENT_MANUAL.value:
            send_btn = (
                f'<button onclick="sendEmail(\'{p.prospect_id}\')" '
                f'style="background:#e94560;color:#fff;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px;margin-left:4px">'
                f'Envoyer</button>'
            )
        rows += f"""<tr id="row-{p.prospect_id}">
          <td><a href="/admin/prospect/{p.prospect_id}?token={token}" style="color:#e94560">{p.name}</a></td>
          <td>{p.city}</td>
          <td style="font-size:11px;color:#6b7280">{p.profession}</td>
          <td>{_pill(p.status)}</td>
          <td style="text-align:center">{p.ia_visibility_score or '—'}</td>
          <td style="font-size:11px">{c1}</td>
          <td>{email_cell}{send_btn}</td>
          <td style="text-align:center">
            {_check(p.proof_image_url)}
            <label style="cursor:pointer;color:#6b7280;font-size:11px" title="Upload preuve">
              <input type="file" accept="image/*" style="display:none"
                     onchange="uploadFile(this,'{p.prospect_id}','proof-image')">
              📎
            </label>
          </td>
          <td style="text-align:center">
            {_check(p.city_image_url)}
            <label style="cursor:pointer;color:#6b7280;font-size:11px" title="Upload photo ville">
              <input type="file" accept="image/*" style="display:none"
                     onchange="uploadFile(this,'{p.prospect_id}','city-image')">
              📎
            </label>
          </td>
          <td style="min-width:180px">
            <input id="vid-{p.prospect_id}" type="text"
              value="{p.video_url or ''}"
              placeholder="Lien Dropbox…"
              style="width:100%;background:#fff;border:1px solid #e5e7eb;color:#1a1a2e;padding:4px 6px;border-radius:4px;font-size:11px">
            <button onclick="saveVideoUrl('{p.prospect_id}')"
              style="margin-top:4px;background:#fff;color:#374151;border:1px solid #e5e7eb;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:11px;width:100%">
              Enregistrer
            </button>
          </td>
        </tr>"""

    js = f"""
<script>
const TOKEN = '{token}';

async function enrichEmail(pid) {{
  const r = await fetch(`/admin/prospect/${{pid}}/enrich-email?token=${{TOKEN}}`, {{method:'POST'}});
  const d = await r.json();
  location.reload();
}}

async function sendEmail(pid) {{
  if (!confirm('Envoyer cet email via Brevo ?')) return;
  const r = await fetch(`/admin/prospect/${{pid}}/send-email?token=${{TOKEN}}`, {{method:'POST'}});
  const d = await r.json();
  if (d.sent) {{ alert('✅ Email envoyé à ' + d.email); location.reload(); }}
  else {{ alert('❌ Erreur : ' + (d.detail || JSON.stringify(d))); }}
}}

async function uploadFile(input, pid, type) {{
  const fd = new FormData();
  fd.append('file', input.files[0]);
  const r = await fetch(`/admin/prospect/${{pid}}/upload-${{type}}?token=${{TOKEN}}`, {{
    method: 'POST', body: fd
  }});
  const d = await r.json();
  if (d.url) {{ alert('✅ Uploadé : ' + d.url); location.reload(); }}
  else {{ alert('❌ Erreur upload'); }}
}}

async function saveVideoUrl(pid) {{
  const url = document.getElementById('vid-' + pid).value.trim();
  if (!url) {{ alert('URL vide'); return; }}
  const fd = new FormData(); fd.append('video_url', url);
  const r = await fetch(`/admin/prospect/${{pid}}/upload-video?token=${{TOKEN}}`, {{
    method: 'POST', body: fd
  }});
  const d = await r.json();
  if (d.url) {{ alert('✅ Vidéo enregistrée'); }}
  else {{ alert('❌ Erreur : ' + JSON.stringify(d)); }}
}}
</script>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Send Queue — PRESENCE_IA</title>
<style>*{{box-sizing:border-box}}body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e;margin:0}}
h1{{color:#1a1a2e;margin-bottom:4px;font-size:18px}}h2{{color:#6b7280;font-size:13px;margin:0 0 20px}}
.wrap{{padding:24px;max-width:1400px;margin:0 auto}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);border:1px solid #e5e7eb}}
th{{background:#f9fafb;color:#6b7280;padding:10px;text-align:left;font-size:11px}}
td{{padding:8px 10px;border-bottom:1px solid #e5e7eb;color:#1a1a2e;vertical-align:middle}}
a{{color:#e94560}}code{{font-size:11px}}</style></head>
<body>
{admin_nav(token, "send-queue")}
<div class="wrap">
<h1>Send Queue</h1>
<h2>{len(prospects)} prospects éligibles</h2>
<table>
  <tr>
    <th>Nom</th><th>Ville</th><th>Métier</th><th>Statut</th>
    <th>Score</th><th>Concurrent #1</th><th>Email</th>
    <th>Preuve</th><th>Ville img</th><th>Vidéo</th>
  </tr>
  {rows or '<tr><td colspan=10 style="text-align:center;color:#9ca3af;padding:20px">Aucun prospect éligible</td></tr>'}
</table>
{js}
</div></body></html>""")


# ── Scheduler status ───────────────────────────────────────────────────────


@router.get("/admin/scheduler", response_class=HTMLResponse)
def admin_scheduler(request: Request):
    token = request.query_params.get("token", "") or request.cookies.get("admin_token", "")
    if (r := _check_token(request)) is not None: return r
    try:
        from ...scheduler import scheduler_status
        jobs = scheduler_status()
    except Exception as e:
        jobs = [{"id": "error", "next_run": str(e), "trigger": "—"}]

    rows = "".join(
        f'<tr><td>{j["id"]}</td><td>{j["next_run"]}</td><td>{j["trigger"]}</td></tr>'
        for j in jobs
    )
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Scheduler — PRESENCE_IA</title>
<style>*{{box-sizing:border-box}}body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e;margin:0}}
.wrap{{padding:24px;max-width:960px;margin:0 auto}}
h1{{color:#1a1a2e;font-size:18px;margin-bottom:4px}}
p.sub{{color:#6b7280;font-size:13px;margin-bottom:20px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1);border:1px solid #e5e7eb}}
th{{background:#f9fafb;color:#6b7280;padding:10px;text-align:left;font-size:12px}}
td{{padding:10px;border-bottom:1px solid #e5e7eb;color:#1a1a2e}}a{{color:#e94560}}</style></head>
<body>
{admin_nav(token, "scheduler")}
<div class="wrap">
<h1>Planificateur</h1>
<p class="sub">Jobs APScheduler actifs — prospections automatiques et tâches récurrentes</p>
<table><tr><th>ID</th><th>Prochain run</th><th>Trigger</th></tr>{rows}</table>
</div></body></html>""")


# ── Outbound Stats ─────────────────────────────────────────────────────────────

@router.get("/admin/outbound-stats", response_class=HTMLResponse)
def admin_outbound_stats(request: Request, db: Session = Depends(get_db)):
    if (r := _check_token(request)) is not None: return r
    token = _admin_token()

    from datetime import date as _date, timedelta as _td
    from sqlalchemy import func, case

    # ── Totaux globaux ─────────────────────────────────────────────────────────
    rows = db.query(V3ProspectDB).filter(V3ProspectDB.email_status.isnot(None)).all()
    total_sent      = sum(1 for r in rows if r.email_status in ("sent","delivered","opened","bounced"))
    total_delivered = sum(1 for r in rows if r.email_status in ("delivered","opened"))
    total_opened    = sum(1 for r in rows if r.email_status == "opened")
    total_bounced   = sum(1 for r in rows if r.email_status == "bounced")

    open_rate   = round(total_opened   / total_delivered * 100, 1) if total_delivered else 0
    bounce_rate = round(total_bounced  / total_sent      * 100, 1) if total_sent      else 0

    # ── Breakdown 7 derniers jours ─────────────────────────────────────────────
    today = _date.today()
    days  = [(today - _td(days=i)) for i in range(6, -1, -1)]

    day_rows = []
    for d in days:
        d_start = datetime(d.year, d.month, d.day)
        d_end   = d_start + _td(days=1)
        day_sent     = sum(1 for r in rows if r.email_sent_at   and d_start <= r.email_sent_at   < d_end)
        day_opened   = sum(1 for r in rows if r.email_opened_at and d_start <= r.email_opened_at < d_end)
        day_bounced  = sum(1 for r in rows if r.email_bounced_at and d_start <= r.email_bounced_at < d_end)
        day_rows.append((d.strftime("%d/%m"), day_sent, day_opened, day_bounced))

    # ── Breakdown par sender ───────────────────────────────────────────────────
    sender_map: dict = {}
    for r in rows:
        if not r.email_sent_at:
            continue
        sender = getattr(r, "sent_method", None) or "?"
        # sent_method = 'brevo' pour tous — on utilise le domaine sender si dispo
        # Pas de sender stocké par prospect : on montre la distribution par statut
    # (sender non stocké par prospect — bloc remplacé par distribution statuts)
    status_dist = {}
    for r in rows:
        s = r.email_status or "unknown"
        status_dist[s] = status_dist.get(s, 0) + 1

    # ── HTML ───────────────────────────────────────────────────────────────────
    def _kpi_card(label, value, sub="", color="#4f46e5"):
        return f"""<div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px;min-width:130px">
<div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px">{label}</div>
<div style="font-size:28px;font-weight:700;color:{color}">{value}</div>
{"<div style='font-size:12px;color:#9ca3af;margin-top:2px'>"+sub+"</div>" if sub else ""}
</div>"""

    kpis = (
        _kpi_card("Envoyés",    total_sent,      "",              "#1e3a5f") +
        _kpi_card("Delivered",  total_delivered, f"{round(total_delivered/total_sent*100,1) if total_sent else 0}% des envoyés", "#0ea5e9") +
        _kpi_card("Ouverts",    total_opened,    f"{open_rate}% des delivered", "#10b981") +
        _kpi_card("Bounced",    total_bounced,   f"{bounce_rate}% des envoyés", "#ef4444")
    )

    day_table_rows = "".join(
        f"<tr><td>{d}</td><td>{s}</td><td>{o}</td><td>{b}</td></tr>"
        for d, s, o, b in day_rows
    )

    status_dist_rows = "".join(
        f"<tr><td>{st}</td><td>{cnt}</td></tr>"
        for st, cnt in sorted(status_dist.items(), key=lambda x: -x[1])
    )

    eligible_total = db.query(V3ProspectDB).filter(
        V3ProspectDB.ia_results.isnot(None),
        V3ProspectDB.email.isnot(None),
    ).count()

    nav = admin_nav(token, "outbound")
    return HTMLResponse(f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Outbound — Présence IA</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f9fafb;margin:0;padding:0;color:#1a1a2e}}
.wrap{{max-width:900px;margin:0 auto;padding:24px}}
h1{{font-size:22px;font-weight:700;margin:0 0 4px}}
.sub{{color:#6b7280;font-size:13px;margin:0 0 24px}}
.kpis{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:28px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;
       box-shadow:0 1px 3px rgba(0,0,0,.08);border:1px solid #e5e7eb;margin-bottom:24px}}
th{{background:#f9fafb;color:#6b7280;padding:10px 12px;text-align:left;font-size:12px;font-weight:600}}
td{{padding:9px 12px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:14px}}
tr:last-child td{{border-bottom:none}}
h2{{font-size:15px;font-weight:600;color:#374151;margin:24px 0 10px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600}}
</style></head><body>
{nav}
<div class="wrap">
<h1>Outbound — Performance</h1>
<p class="sub">Emails envoyés depuis job_outbound — tracking Brevo &nbsp;·&nbsp;
  <span style="color:#6366f1">{eligible_total:,} prospects éligibles en DB</span></p>

<div class="kpis">{kpis}</div>

<h2>7 derniers jours</h2>
<table>
<tr><th>Date</th><th>Envoyés</th><th>Ouverts</th><th>Bounced</th></tr>
{day_table_rows}
</table>

<h2>Distribution statuts</h2>
<table>
<tr><th>Statut</th><th>Nombre</th></tr>
{status_dist_rows if status_dist_rows else '<tr><td colspan="2" style="color:#9ca3af;text-align:center">Aucun envoi pour l\'instant</td></tr>'}
</table>

<p style="font-size:12px;color:#9ca3af;margin-top:8px">
  Webhook Brevo : <code>POST /webhooks/brevo</code> &nbsp;·&nbsp;
  Sender rotation : 25 adresses &nbsp;·&nbsp;
  <a href="/admin/outbound-stats?token={token}" style="color:#6366f1">↺ Rafraîchir</a>
</p>
</div></body></html>""")
