"""Admin — onglet CRM : pipeline prospects → RDV → deal + gestion closers."""
import os
import json
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ._nav import admin_nav
from ...database import SessionLocal
from ...models import V3ProspectDB

router = APIRouter(tags=["Admin CRM"])


def _check_token(request: Request) -> str:
    from fastapi import HTTPException
    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    return token


def _badge(text: str, color: str) -> str:
    return (f'<span style="background:{color}20;color:{color};font-size:10px;font-weight:600;'
            f'padding:2px 7px;border-radius:10px;white-space:nowrap">{text}</span>')


def _status_badge(status: str) -> str:
    m = {
        "scheduled": ("#f59e0b", "RDV planifié"),
        "completed":  ("#2ecc71", "Signé"),
        "no_show":    ("#e94560", "No-show"),
        "cancelled":  ("#9ca3af", "Annulé"),
    }
    color, label = m.get(status, ("#6366f1", status))
    return _badge(label, color)


def _app_stage_badge(stage: str) -> str:
    m = {
        "contacted": ("#9ca3af", "Contacté"),
        "applied":   ("#6366f1", "Candidature"),
        "reviewing": ("#f59e0b", "En cours"),
        "validated": ("#2ecc71", "Validé"),
        "rejected":  ("#e94560", "Refusé"),
    }
    color, label = m.get(stage, ("#9ca3af", stage))
    return _badge(label, color)


def _delivery_badge(d: dict) -> str:
    status = d.get("delivery_status", "")
    opened  = d.get("opened_at")
    clicked = d.get("clicked_at")
    reply   = d.get("reply_status", "none")
    bounce  = d.get("bounce_type", "none")

    if bounce in ("hard", "soft"):
        return _badge("Bounce", "#e94560")
    if reply == "positive":
        return _badge("Répondu", "#2ecc71")
    if clicked:
        return _badge("Clic ✓", "#2ecc71")
    if opened:
        return _badge("Ouvert", "#f59e0b")
    if status == "sent":
        return _badge("Envoyé", "#6366f1")
    if status == "failed":
        return _badge("Échec", "#e94560")
    return _badge("En attente", "#9ca3af")


def _load_crm_data() -> dict:
    """Fusionne V3ProspectDB + ProspectDeliveryDB + MeetingDB."""
    prospects_map = {}
    with SessionLocal() as db:
        for p in db.query(V3ProspectDB).filter(V3ProspectDB.contacted == True).order_by(
            V3ProspectDB.sent_at.desc()
        ).limit(300).all():
            prospects_map[p.token] = {
                "token":      p.token,
                "name":       p.name or "—",
                "city":       p.city or "—",
                "profession": p.profession or "—",
                "email":      p.email or "",
                "phone":      p.phone or "",
                "landing_url": p.landing_url or "",
                "sent_at":    p.sent_at.strftime("%d/%m %H:%M") if p.sent_at else "—",
                "sent_method": p.sent_method or "—",
                "delivery":   None,
                "meeting":    None,
            }

    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import ProspectDeliveryDB, MeetingDB
        with MktSession() as mdb:
            for d in mdb.query(ProspectDeliveryDB).filter_by(project_id="presence-ia").all():
                pid = d.prospect_id
                if pid in prospects_map:
                    prospects_map[pid]["delivery"] = {
                        "delivery_status": d.delivery_status,
                        "opened_at":       d.opened_at,
                        "clicked_at":      d.clicked_at,
                        "landing_visited_at": getattr(d, "landing_visited_at", None),
                        "calendly_clicked_at": getattr(d, "calendly_clicked_at", None),
                        "reply_status":    d.reply_status,
                        "bounce_type":     d.bounce_type,
                    }
            for m in mdb.query(MeetingDB).filter_by(project_id="presence-ia").all():
                pid = m.prospect_id
                if pid in prospects_map:
                    prospects_map[pid]["meeting"] = {
                        "id":           m.id,
                        "status":       m.status,
                        "scheduled_at": m.scheduled_at.strftime("%d/%m/%y %H:%M") if m.scheduled_at else "—",
                        "deal_value":   m.deal_value,
                        "notes":        m.notes or "",
                        "closer_id":    m.closer_id,
                    }
    except Exception:
        pass

    return list(prospects_map.values())


def _derive_stage(r: dict) -> str:
    """Dérive le stage kanban d'un prospect depuis ses données."""
    if r.get("meeting"):
        m = r["meeting"]
        if m["status"] == "completed":
            return "closed"
        return "rdv"
    d = r.get("delivery") or {}
    if d.get("calendly_clicked_at"):
        return "calendly_clicked"
    if d.get("landing_visited_at") or d.get("clicked_at"):
        return "landing_visited"
    if d.get("opened_at"):
        return "opened"
    return "contacted"


# ─────────────────────────────────────────────────────────────────────────────
# Route principale CRM
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/admin/crm", response_class=HTMLResponse)
def crm_page(request: Request, view: str = "table"):
    token = _check_token(request)
    rows  = _load_crm_data()

    # Compteurs pipeline
    n_sent    = len(rows)
    n_opened  = sum(1 for r in rows if r["delivery"] and r["delivery"].get("opened_at"))
    n_clicked = sum(1 for r in rows if r["delivery"] and r["delivery"].get("clicked_at"))
    n_rdv     = sum(1 for r in rows if r["meeting"])
    n_signed  = sum(1 for r in rows if r["meeting"] and r["meeting"]["status"] == "completed")

    def _pct(a, b):
        return f"{a/b*100:.0f}%" if b else "—"

    pipeline_html = "".join([
        f'<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px 20px;text-align:center">'
        f'<div style="font-size:1.8rem;font-weight:700;color:{c}">{v}</div>'
        f'<div style="color:#ccc;font-size:11px;margin-top:4px">{l}</div>'
        f'<div style="color:#555;font-size:10px">{s}</div></div>'
        for v, l, s, c in [
            (n_sent,    "Contactés",      "landings envoyées",             "#527FB3"),
            (n_opened,  "Ont ouvert",     _pct(n_opened, n_sent),          "#6366f1"),
            (n_clicked, "Ont cliqué",     _pct(n_clicked, n_sent),         "#e9a020"),
            (n_rdv,     "RDV pris",       _pct(n_rdv, n_sent),             "#2ecc71"),
            (n_signed,  "Signés",         _pct(n_signed, n_rdv) + " des RDV", "#e94560"),
        ]
    ])

    # Tabs vue
    def _tab(slug, label, cur):
        active = slug == cur
        bg  = "#6366f1" if active else "#1a1a2e"
        col = "#fff"    if active else "#9ca3af"
        return (f'<a href="/admin/crm?token={token}&view={slug}" '
                f'style="padding:7px 16px;border-radius:6px;text-decoration:none;'
                f'font-size:12px;font-weight:600;background:{bg};color:{col}">{label}</a>')

    tabs_html = (
        f'<div style="display:flex;gap:8px;margin-bottom:20px">'
        f'{_tab("table","Tableau",view)}'
        f'{_tab("kanban","Kanban",view)}'
        f'</div>'
    )

    # ── VUE TABLE ──────────────────────────────────────────────────────────────
    def _row(r):
        meeting_html = ""
        if r["meeting"]:
            m = r["meeting"]
            deal = f' — {int(m["deal_value"])}€' if m.get("deal_value") else ""
            meeting_html = (
                f'<div>{_status_badge(m["status"])}</div>'
                f'<div style="color:#9ca3af;font-size:10px;margin-top:3px">{m["scheduled_at"]}{deal}</div>'
                f'<div style="color:#555;font-size:10px">{m["notes"][:40] if m["notes"] else ""}</div>'
            )
            update_btn = (
                f'<select onchange="updateMeeting(\'{m["id"]}\',this.value,\'{token}\')" '
                f'style="font-size:10px;padding:2px 4px;background:#0f0f1a;color:#ccc;border:1px solid #2a2a4e;border-radius:4px;margin-top:4px">'
                f'<option value="">— statut —</option>'
                f'<option value="completed">✓ Signé</option>'
                f'<option value="no_show">✗ No-show</option>'
                f'<option value="cancelled">Annulé</option>'
                f'</select>'
            )
            meeting_html += update_btn
        else:
            meeting_html = '<span style="color:#444;font-size:11px">—</span>'

        delivery_badge = _delivery_badge(r["delivery"]) if r["delivery"] else _badge("Non tracké", "#374151")

        landing_link = (
            f'<a href="{r["landing_url"]}" target="_blank" '
            f'style="color:#527FB3;font-size:10px;text-decoration:none">↗ landing</a>'
            if r["landing_url"] else ""
        )

        return (
            f'<tr style="border-bottom:1px solid #1a1a2e">'
            f'<td style="padding:10px 12px">'
            f'  <a href="/admin/crm/prospect/{r["token"]}?token={token}" '
            f'style="color:#fff;font-size:13px;font-weight:500;text-decoration:none">{r["name"]}</a>'
            f'  <div style="color:#6b7280;font-size:11px">{r["city"]} · {r["profession"]}</div>'
            f'  <div style="color:#444;font-size:10px">{r["email"]}</div>'
            f'</td>'
            f'<td style="padding:10px 12px;color:#9ca3af;font-size:11px">'
            f'  {r["sent_at"]}<br>{r["sent_method"]}'
            f'</td>'
            f'<td style="padding:10px 12px">{delivery_badge}<br>{landing_link}</td>'
            f'<td style="padding:10px 12px">{meeting_html}</td>'
            f'</tr>'
        )

    rows_html = "".join(_row(r) for r in rows) or (
        '<tr><td colspan="4" style="padding:40px;text-align:center;color:#555">'
        'Aucun prospect contacté pour l\'instant</td></tr>'
    )

    table_view = f"""
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden">
<table>
<thead><tr>
  <th>Prospect</th>
  <th>Envoi</th>
  <th>Engagement</th>
  <th>RDV / Deal</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>
</div>"""

    # ── VUE KANBAN ─────────────────────────────────────────────────────────────
    STAGES = [
        ("contacted",        "Contacté",        "#527FB3"),
        ("opened",           "Ouvert",          "#6366f1"),
        ("landing_visited",  "Landing visitée", "#e9a020"),
        ("calendly_clicked", "Calendly cliqué", "#f59e0b"),
        ("rdv",              "RDV planifié",    "#2ecc71"),
        ("closed",           "Signé",           "#e94560"),
    ]

    # Grouper les prospects par stage
    by_stage: dict[str, list] = {s[0]: [] for s in STAGES}
    for r in rows:
        stage = _derive_stage(r)
        by_stage.get(stage, by_stage["contacted"]).append(r)

    def _kanban_card(r):
        meeting = r.get("meeting") or {}
        deal_str = f'<div style="color:#2ecc71;font-size:10px">{int(meeting["deal_value"])}€</div>' if meeting.get("deal_value") else ""
        return (
            f'<div class="kcard" draggable="true" '
            f'data-token="{r["token"]}" data-stage="{_derive_stage(r)}" '
            f'onclick="window.location=\'/admin/crm/prospect/{r["token"]}?token={token}\'" '
            f'style="background:#0f0f1a;border:1px solid #2a2a4e;border-radius:6px;'
            f'padding:10px;margin-bottom:8px;cursor:pointer;transition:border-color .15s" '
            f'onmouseover="this.style.borderColor=\'#6366f1\'" '
            f'onmouseout="this.style.borderColor=\'#2a2a4e\'">'
            f'<div style="color:#fff;font-size:12px;font-weight:600">{r["name"]}</div>'
            f'<div style="color:#6b7280;font-size:10px;margin-top:2px">{r["city"]} · {r["profession"]}</div>'
            f'{deal_str}'
            f'<div style="color:#444;font-size:10px;margin-top:4px">{r["sent_at"]}</div>'
            f'</div>'
        )

    kanban_cols = ""
    for stage_key, stage_label, stage_color in STAGES:
        cards = by_stage[stage_key]
        cards_html = "".join(_kanban_card(r) for r in cards)
        kanban_cols += (
            f'<div class="kcol" data-stage="{stage_key}" '
            f'style="flex:0 0 200px;background:#1a1a2e;border:1px solid #2a2a4e;'
            f'border-radius:8px;padding:12px;min-height:400px" '
            f'ondragover="event.preventDefault()" '
            f'ondrop="dropCard(event,\'{stage_key}\')">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">'
            f'<span style="font-size:11px;font-weight:700;color:{stage_color}">{stage_label}</span>'
            f'<span style="background:{stage_color}20;color:{stage_color};font-size:10px;'
            f'padding:1px 7px;border-radius:10px">{len(cards)}</span>'
            f'</div>'
            f'<div class="kcards">{cards_html}</div>'
            f'</div>'
        )

    kanban_view = f"""
<div style="overflow-x:auto;padding-bottom:16px">
<div style="display:flex;gap:12px;min-width:max-content">
{kanban_cols}
</div>
</div>"""

    content = table_view if view == "table" else kanban_view

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CRM — PRESENCE_IA Admin</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
table{{width:100%;border-collapse:collapse}}
th{{padding:10px 12px;text-align:left;color:#9ca3af;font-size:10px;font-weight:600;
   letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #2a2a4e}}
tr:hover{{background:#111127}}
.kcard.dragging{{opacity:.5;transform:scale(.97)}}
</style></head><body>
{admin_nav(token, "crm")}
<div style="max-width:1200px;margin:0 auto;padding:24px">

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
<h1 style="color:#fff;font-size:18px">CRM — Pipeline</h1>
<a href="/admin/crm/closers?token={token}" style="color:#9ca3af;font-size:12px;text-decoration:none">Gérer les closers →</a>
</div>

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:32px">
{pipeline_html}
</div>

{tabs_html}

{content}

</div>

<script>
async function updateMeeting(id, status, token) {{
  if (!status) return;
  const r = await fetch(`/mkt/crm/meetings/${{id}}`, {{
    method: 'PATCH',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{status}})
  }});
  if (r.ok) location.reload();
  else alert('Erreur mise à jour');
}}

// Kanban drag & drop
let _dragToken = null;
document.querySelectorAll('.kcard').forEach(card => {{
  card.addEventListener('dragstart', e => {{
    _dragToken = card.dataset.token;
    card.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
  }});
  card.addEventListener('dragend', () => card.classList.remove('dragging'));
}});

async function dropCard(e, newStage) {{
  e.preventDefault();
  if (!_dragToken) return;
  // Mise à jour optimiste : déplacer la carte visuellement
  const card = document.querySelector(`.kcard[data-token="${{_dragToken}}"]`);
  const col   = document.querySelector(`.kcol[data-stage="${{newStage}}"] .kcards`);
  if (card && col) {{
    col.appendChild(card);
    card.dataset.stage = newStage;
    // Mettre à jour compteurs
    document.querySelectorAll('.kcol').forEach(c => {{
      const count = c.querySelectorAll('.kcard').length;
      const badge = c.querySelector('span:last-child');
      if (badge) badge.textContent = count;
    }});
  }}
  // Appel API pour persister
  try {{
    await fetch('/admin/crm/journey', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{token: _dragToken, stage: newStage, admin_token: '{token}'}})
    }});
  }} catch(err) {{}}
  _dragToken = null;
}}
</script>
</body></html>""")


@router.post("/admin/crm/journey")
async def update_journey(request: Request):
    """Met à jour le stage kanban d'un prospect."""
    data = await request.json()
    if data.get("admin_token") != os.getenv("ADMIN_TOKEN", "changeme"):
        from fastapi import HTTPException
        raise HTTPException(403, "Accès refusé")
    token = data.get("token")
    stage = data.get("stage")
    if not token or not stage:
        return JSONResponse({"ok": False, "error": "token et stage requis"})
    try:
        from marketing_module.database import SessionLocal as MktSession, db_upsert_journey
        with MktSession() as mdb:
            db_upsert_journey(mdb, "presence-ia", token, {"stage": stage})
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


@router.get("/admin/crm/prospect/{token}", response_class=HTMLResponse)
def crm_prospect_detail(token: str, request: Request):
    """Fiche prospect détaillée (livraisons, RDV, notes)."""
    admin_token = _check_token(request)
    with SessionLocal() as db:
        p = db.get(V3ProspectDB, token)
    if not p:
        return HTMLResponse("<p>Prospect introuvable</p>", status_code=404)

    deliveries = []
    meetings   = []
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import ProspectDeliveryDB, MeetingDB
        with MktSession() as mdb:
            deliveries = mdb.query(ProspectDeliveryDB).filter_by(
                project_id="presence-ia", prospect_id=token
            ).order_by(ProspectDeliveryDB.created_at.desc()).all()
            meetings = mdb.query(MeetingDB).filter_by(
                project_id="presence-ia", prospect_id=token
            ).order_by(MeetingDB.scheduled_at.desc()).all()
    except Exception:
        pass

    def _fmt(dt):
        return dt.strftime("%d/%m/%y %H:%M") if dt else "—"

    del_rows = "".join(
        f'<tr style="border-bottom:1px solid #1a1a2e">'
        f'<td style="padding:8px 12px;color:#ccc;font-size:12px">{_fmt(d.created_at)}</td>'
        f'<td style="padding:8px 12px">{_delivery_badge({"delivery_status":d.delivery_status,"opened_at":d.opened_at,"clicked_at":d.clicked_at,"reply_status":d.reply_status,"bounce_type":d.bounce_type})}</td>'
        f'<td style="padding:8px 12px;color:#9ca3af;font-size:11px">{_fmt(d.opened_at)}</td>'
        f'<td style="padding:8px 12px;color:#9ca3af;font-size:11px">{_fmt(d.clicked_at)}</td>'
        f'<td style="padding:8px 12px;color:#9ca3af;font-size:11px">{_fmt(getattr(d,"landing_visited_at",None))}</td>'
        f'</tr>'
        for d in deliveries
    ) or '<tr><td colspan="5" style="padding:20px;color:#555;text-align:center">Aucune livraison</td></tr>'

    mtg_rows = "".join(
        f'<tr style="border-bottom:1px solid #1a1a2e">'
        f'<td style="padding:8px 12px;color:#ccc;font-size:12px">{_fmt(m.scheduled_at)}</td>'
        f'<td style="padding:8px 12px">{_status_badge(m.status)}</td>'
        f'<td style="padding:8px 12px;color:#9ca3af;font-size:11px">{m.deal_value or "—"}</td>'
        f'<td style="padding:8px 12px;color:#9ca3af;font-size:11px">{getattr(m,"outcome","") or (m.notes or "—")}</td>'
        f'</tr>'
        for m in meetings
    ) or '<tr><td colspan="4" style="padding:20px;color:#555;text-align:center">Aucun RDV</td></tr>'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>{p.name} — CRM</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
table{{width:100%;border-collapse:collapse}}
th{{padding:8px 12px;text-align:left;color:#9ca3af;font-size:10px;
   font-weight:600;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #2a2a4e}}
</style></head><body>
{admin_nav(admin_token, "crm")}
<div style="max-width:900px;margin:0 auto;padding:24px">
<a href="/admin/crm?token={admin_token}" style="color:#527FB3;font-size:12px;text-decoration:none">← CRM</a>
<h1 style="color:#fff;font-size:18px;margin:16px 0 4px">{p.name}</h1>
<p style="color:#9ca3af;font-size:13px">{p.city} · {p.profession} · {p.email}</p>
{f'<p style="color:#9ca3af;font-size:12px;margin-top:4px">📞 {p.phone}</p>' if p.phone else ""}

<div style="margin:24px 0 12px;color:#9ca3af;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase">Livraisons emails</div>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden;margin-bottom:24px">
<table><thead><tr><th>Date</th><th>Statut</th><th>Ouverture</th><th>Clic</th><th>Landing</th></tr></thead>
<tbody>{del_rows}</tbody></table></div>

<div style="margin-bottom:12px;color:#9ca3af;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase">RDV Calendly</div>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden">
<table><thead><tr><th>Date RDV</th><th>Statut</th><th>Deal</th><th>Résultat / Notes</th></tr></thead>
<tbody>{mtg_rows}</tbody></table></div>
</div></body></html>""")


# ─────────────────────────────────────────────────────────────────────────────
# Admin — gestion closers + candidatures
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/admin/crm/closers", response_class=HTMLResponse)
def crm_closers(request: Request):
    token = _check_token(request)

    closers = []
    applications = []
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import CloserDB, CloserApplicationDB
        with MktSession() as mdb:
            closers = mdb.query(CloserDB).filter_by(project_id="presence-ia").all()
            applications = mdb.query(CloserApplicationDB).filter_by(project_id="presence-ia")\
                .order_by(CloserApplicationDB.created_at.desc()).all()
    except Exception:
        pass

    closer_rows = "".join(
        f'<tr style="border-bottom:1px solid #1a1a2e">'
        f'<td style="padding:10px 12px;color:#fff;font-size:12px">{c.name}</td>'
        f'<td style="padding:10px 12px;color:#9ca3af;font-size:11px">{c.email or "—"}</td>'
        f'<td style="padding:10px 12px;color:#9ca3af;font-size:11px">{c.commission_rate*100:.0f}%</td>'
        f'<td style="padding:10px 12px">'
        f'{"<span style=\'color:#2ecc71\'>Actif</span>" if c.is_active else "<span style=\'color:#e94560\'>Inactif</span>"}'
        f'</td>'
        f'<td style="padding:10px 12px">'
        f'<a href="/closer/{getattr(c,"token",c.id) or c.id}?preview=1" target="_blank" style="color:#527FB3;font-size:10px">↗ Portail</a>'
        f'</td>'
        f'</tr>'
        for c in closers
    ) or '<tr><td colspan="5" style="padding:20px;color:#555;text-align:center">Aucun closer</td></tr>'

    app_rows = "".join(
        f'<tr style="border-bottom:1px solid #1a1a2e">'
        f'<td style="padding:10px 12px;color:#fff;font-size:12px">'
        f'{(a.first_name or "") + " " + (a.last_name or "")}'.strip() + f' <span style="color:#444;font-size:10px">{a.city or ""}</span></td>'
        f'<td style="padding:10px 12px;color:#9ca3af;font-size:11px">{a.email or "—"}</td>'
        f'<td style="padding:10px 12px">{_app_stage_badge(a.stage)}</td>'
        f'<td style="padding:10px 12px;color:#9ca3af;font-size:11px">'
        f'{a.applied_at.strftime("%d/%m/%y") if a.applied_at else "—"}'
        f'</td>'
        f'<td style="padding:10px 12px">'
        f'<a href="/admin/crm/application/{a.id}?token={token}" style="color:#527FB3;font-size:10px">Voir →</a>'
        f'</td>'
        f'</tr>'
        for a in applications
    ) or '<tr><td colspan="5" style="padding:20px;color:#555;text-align:center">Aucune candidature</td></tr>'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Closers — CRM</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
table{{width:100%;border-collapse:collapse}}
th{{padding:10px 12px;text-align:left;color:#9ca3af;font-size:10px;font-weight:600;
   letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #2a2a4e}}
tr:hover{{background:#111127}}
</style></head><body>
{admin_nav(token, "crm")}
<div style="max-width:1100px;margin:0 auto;padding:24px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
  <h1 style="color:#fff;font-size:18px">Closers</h1>
  <div style="display:flex;gap:16px;align-items:center">
    <a href="/admin/crm/closer-messages?token={token}" style="color:#6366f1;font-size:12px;text-decoration:none">Messages recrutement →</a>
    <a href="/admin/crm?token={token}" style="color:#527FB3;font-size:12px;text-decoration:none">← CRM</a>
  </div>
</div>

<h2 style="color:#9ca3af;font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:12px">Closers actifs</h2>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden;margin-bottom:32px">
<table><thead><tr><th>Nom</th><th>Email</th><th>Commission</th><th>Statut</th><th></th></tr></thead>
<tbody>{closer_rows}</tbody></table></div>

<h2 style="color:#9ca3af;font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:12px">Candidatures</h2>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden">
<table><thead><tr><th>Candidat</th><th>Email</th><th>Statut</th><th>Date</th><th></th></tr></thead>
<tbody>{app_rows}</tbody></table></div>
</div></body></html>""")


@router.get("/admin/crm/application/{app_id}", response_class=HTMLResponse)
def crm_application_detail(app_id: str, request: Request):
    """Fiche candidature avec validation en un clic."""
    token = _check_token(request)

    app = None
    try:
        from marketing_module.database import SessionLocal as MktSession, db_get_application
        with MktSession() as mdb:
            app = db_get_application(mdb, app_id)
    except Exception:
        pass

    if not app:
        return HTMLResponse("<p>Candidature introuvable</p>", status_code=404)

    name = f"{app.first_name or ''} {app.last_name or ''}".strip() or "—"
    stage_btns = "".join(
        f'<button onclick="setStage(\'{app.id}\',\'{s}\')" '
        f'style="padding:8px 16px;border:none;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;'
        f'background:{("" if app.stage!=s else "#6366f1")};color:{"#fff" if app.stage==s else "#9ca3af"};'
        f'border:1px solid {"#6366f1" if app.stage==s else "#2a2a4e"}">{l}</button>'
        for s, l in [("contacted","Contacté"),("applied","Candidature"),
                     ("reviewing","En cours"),("validated","✓ Valider"),("rejected","✗ Refuser")]
    )

    video_block = (f'<div style="margin-top:12px"><a href="{app.video_url}" target="_blank" '
                   f'style="color:#527FB3">▶ Voir la vidéo</a></div>') if app.video_url else ""
    audio_block = (f'<div style="margin-top:8px"><audio controls src="{app.audio_url}" '
                   f'style="width:100%"></audio></div>') if app.audio_url else ""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>{name} — Candidature</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
</style></head><body>
{admin_nav(token, "crm")}
<div style="max-width:800px;margin:0 auto;padding:24px">
<a href="/admin/crm/closers?token={token}" style="color:#527FB3;font-size:12px;text-decoration:none">← Closers</a>
<h1 style="color:#fff;font-size:18px;margin:16px 0 4px">{name}</h1>
<p style="color:#9ca3af;font-size:13px">{app.city or "—"} · {app.country or "FR"} · {app.email or "—"}</p>
{f'<p style="color:#9ca3af;font-size:12px;margin-top:4px">📞 {app.phone}</p>' if app.phone else ""}
{f'<p style="margin-top:8px"><a href="{app.linkedin_url}" target="_blank" style="color:#527FB3;font-size:12px">LinkedIn →</a></p>' if app.linkedin_url else ""}

<div style="margin:24px 0 12px;display:flex;gap:8px;flex-wrap:wrap">
{stage_btns}
</div>

{f'<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;margin-top:24px"><p style="color:#9ca3af;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Message de présentation</p><p style="color:#ccc;font-size:13px;line-height:1.6">{app.message}</p></div>' if app.message else ""}

{video_block}
{audio_block}

<div style="margin-top:24px;background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px">
<p style="color:#9ca3af;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Notes admin</p>
<textarea id="notes" rows="4" style="width:100%;background:#0f0f1a;color:#ccc;border:1px solid #2a2a4e;border-radius:4px;padding:8px;font-size:13px;resize:vertical">{app.admin_notes or ""}</textarea>
<button onclick="saveNotes()" style="margin-top:8px;padding:6px 14px;background:#6366f1;border:none;border-radius:4px;color:#fff;font-size:12px;cursor:pointer">Sauvegarder les notes</button>
</div>

</div>
<script>
async function setStage(id, stage) {{
  const r = await fetch('/admin/crm/application/' + id + '/stage?token={token}', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{stage}})
  }});
  if (r.ok) location.reload();
}}
async function saveNotes() {{
  const notes = document.getElementById('notes').value;
  await fetch('/admin/crm/application/{app.id}/notes?token={token}', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{notes}})
  }});
  alert('Notes sauvegardées');
}}
</script>
</body></html>""")


@router.post("/admin/crm/application/{app_id}/stage")
async def set_application_stage(app_id: str, request: Request):
    _check_token(request)
    data = await request.json()
    stage = data.get("stage")
    try:
        from marketing_module.database import SessionLocal as MktSession, db_update_application
        from datetime import datetime
        updates = {"stage": stage}
        if stage == "validated":
            updates["validated_at"] = datetime.utcnow()
        elif stage == "reviewing":
            updates["reviewed_at"] = datetime.utcnow()
        with MktSession() as mdb:
            db_update_application(mdb, app_id, updates)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


@router.post("/admin/crm/application/{app_id}/notes")
async def save_application_notes(app_id: str, request: Request):
    _check_token(request)
    data = await request.json()
    try:
        from marketing_module.database import SessionLocal as MktSession, db_update_application
        with MktSession() as mdb:
            db_update_application(mdb, app_id, {"admin_notes": data.get("notes", "")})
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# Messages de recrutement closers
# ─────────────────────────────────────────────────────────────────────────────

_MESSAGES_FILE = Path(__file__).parent.parent.parent.parent / "data" / "closer_messages.json"

_DEFAULT_MESSAGES = {
    "linkedin_dm": (
        "Bonjour [Prénom],\n\n"
        "Je développe un réseau de closers indépendants pour Présence IA — "
        "on aide les artisans et PME locales à apparaître sur ChatGPT et les IA.\n\n"
        "Les RDV sont fournis, qualifiés, chauds. Votre rôle : closer.\n"
        "Commission : 18% par deal + bonus.\n\n"
        "Ça vous intéresse d'en savoir plus ? Je vous envoie le détail."
    ),
    "instagram_dm": (
        "Hello [Prénom] 👋\n\n"
        "Je recrute des closers pour un projet IA en pleine croissance.\n"
        "RDV fournis + formation complète. Commission attractive.\n\n"
        "Dispo pour en discuter ?"
    ),
    "facebook_dm": (
        "Bonjour [Prénom],\n\n"
        "Je développe une équipe de commerciaux indépendants dans le secteur de l'IA locale.\n"
        "Vous travaillez à distance, les prospects sont déjà qualifiés.\n\n"
        "Intéressé(e) par une opportunité en closing ?\n"
        "Plus d'infos ici : https://presence-ia.com/closer"
    ),
    "email_subject": "Opportunité closing — IA locale (RDV fournis)",
    "email_body": (
        "Bonjour [Prénom],\n\n"
        "Je me permets de vous contacter car votre profil correspond à ce que je recherche "
        "pour développer mon équipe commerciale.\n\n"
        "Je dirige Présence IA, une solution qui permet aux artisans et PME locales "
        "d'apparaître sur ChatGPT, Google AI et les assistants vocaux.\n\n"
        "Je recrute des closers indépendants :\n"
        "- RDV qualifiés fournis (vous n'avez pas à prospecter)\n"
        "- Formation script + objections incluse\n"
        "- Commission 18% par deal signé\n"
        "- 100% télétravail\n\n"
        "Si vous êtes intéressé(e), vous pouvez candidater directement ici :\n"
        "https://presence-ia.com/closer/recruit\n\n"
        "Cordialement,"
    ),
    "notes": "",
}


def _load_closer_messages() -> dict:
    try:
        if _MESSAGES_FILE.exists():
            return json.loads(_MESSAGES_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return dict(_DEFAULT_MESSAGES)


def _save_closer_messages(data: dict):
    _MESSAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MESSAGES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/admin/crm/closer-messages", response_class=HTMLResponse)
def closer_messages_page(request: Request):
    """Éditeur des messages de recrutement closers + liens publics."""
    token = _check_token(request)
    msgs = _load_closer_messages()

    # Closers actifs pour les liens individuels
    closer_links = ""
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import CloserDB
        with MktSession() as mdb:
            closers = mdb.query(CloserDB).filter_by(
                project_id="presence-ia", is_active=True
            ).all()
        if closers:
            rows = "".join(
                f'<tr style="border-bottom:1px solid #2a2a4e">'
                f'<td style="padding:8px 12px;color:#e8e8f0;font-size:12px">{c.name}</td>'
                f'<td style="padding:8px 12px">'
                f'<a href="/closer/{getattr(c,"token",c.id) or c.id}" target="_blank" '
                f'style="color:#527FB3;font-size:11px;font-family:monospace">'
                f'presence-ia.com/closer/{getattr(c,"token",c.id) or c.id}</a></td>'
                f'<td style="padding:8px 12px">'
                f'<button onclick="copyText(\'presence-ia.com/closer/{getattr(c,"token",c.id) or c.id}\')" '
                f'style="padding:3px 10px;background:#1a1a2e;border:1px solid #2a2a4e;'
                f'border-radius:4px;color:#9ca3af;font-size:10px;cursor:pointer">Copier</button>'
                f'</td></tr>'
                for c in closers
            )
            closer_links = f"""
<h2 style="color:#9ca3af;font-size:10px;letter-spacing:.08em;text-transform:uppercase;margin:28px 0 10px">
Portails individuels closers</h2>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden">
<table style="width:100%;border-collapse:collapse">
<thead><tr>
  <th style="padding:8px 12px;text-align:left;color:#555;font-size:10px;font-weight:600;
             letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #2a2a4e">Closer</th>
  <th style="padding:8px 12px;text-align:left;color:#555;font-size:10px;font-weight:600;
             letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #2a2a4e">Lien portail</th>
  <th style="border-bottom:1px solid #2a2a4e"></th>
</tr></thead>
<tbody>{rows}</tbody>
</table></div>"""
    except Exception:
        pass

    def _field(key, label, placeholder="", rows=6):
        val = msgs.get(key, "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
        tag = "input" if rows == 1 else "textarea"
        if rows == 1:
            return (
                f'<div class="field"><label for="{key}">{label}</label>'
                f'<input id="{key}" name="{key}" value="{val}" placeholder="{placeholder}"></div>'
            )
        return (
            f'<div class="field"><label for="{key}">{label}</label>'
            f'<div style="position:relative">'
            f'<textarea id="{key}" name="{key}" rows="{rows}" placeholder="{placeholder}">{val}</textarea>'
            f'<button type="button" onclick="copyField(\'{key}\')" '
            f'style="position:absolute;top:8px;right:8px;padding:3px 10px;'
            f'background:#0f0f1a;border:1px solid #2a2a4e;border-radius:4px;'
            f'color:#9ca3af;font-size:10px;cursor:pointer">Copier</button>'
            f'</div></div>'
        )

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Messages recrutement — Closers</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
.wrap{{max-width:860px;margin:0 auto;padding:24px}}
h1{{color:#fff;font-size:18px}}
.field{{margin-bottom:20px}}
label{{display:block;color:#9ca3af;font-size:11px;font-weight:600;
       letter-spacing:.08em;text-transform:uppercase;margin-bottom:6px}}
textarea,input{{width:100%;background:#1a1a2e;border:1px solid #2a2a4e;border-radius:6px;
  padding:10px 12px;color:#e8e8f0;font-size:13px;font-family:inherit;
  resize:vertical;outline:none;line-height:1.6}}
textarea:focus,input:focus{{border-color:#6366f1}}
.save-btn{{padding:10px 24px;background:#6366f1;border:none;border-radius:6px;
           color:#fff;font-size:13px;font-weight:600;cursor:pointer}}
.save-btn:hover{{background:#5254cc}}
.link-card{{display:flex;align-items:center;justify-content:space-between;
            background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;
            padding:12px 16px;margin-bottom:8px}}
.link-url{{color:#527FB3;font-size:12px;font-family:monospace;text-decoration:none}}
.copy-btn{{padding:4px 12px;background:#0f0f1a;border:1px solid #2a2a4e;border-radius:4px;
           color:#9ca3af;font-size:11px;cursor:pointer}}
.section-sep{{height:1px;background:#2a2a4e;margin:28px 0}}
.toast{{position:fixed;bottom:24px;right:24px;background:#2ecc71;color:#0f0f1a;
        padding:10px 20px;border-radius:6px;font-size:13px;font-weight:600;
        opacity:0;transition:opacity .3s;pointer-events:none}}
.toast.show{{opacity:1}}
</style></head><body>
{admin_nav(token, "crm/closer-messages")}
<div class="wrap">

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
  <h1>Messages recrutement closers</h1>
  <a href="/admin/crm/closers?token={token}" style="color:#527FB3;font-size:12px;text-decoration:none">← Closers</a>
</div>

<!-- ── Liens publics ───────────────────────────────── -->
<h2 style="color:#9ca3af;font-size:10px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px">
Pages publiques</h2>

<div class="link-card">
  <div>
    <div style="color:#e8e8f0;font-size:12px;font-weight:600;margin-bottom:2px">Page de présentation</div>
    <a href="/closer/" target="_blank" class="link-url">presence-ia.com/closer/</a>
  </div>
  <div style="display:flex;gap:8px">
    <a href="/closer/" target="_blank"
       style="padding:4px 12px;background:#6366f120;border:1px solid #6366f140;border-radius:4px;
              color:#6366f1;font-size:11px;text-decoration:none">Voir ↗</a>
    <button class="copy-btn" onclick="copyText('https://presence-ia.com/closer/')">Copier lien</button>
  </div>
</div>

<div class="link-card">
  <div>
    <div style="color:#e8e8f0;font-size:12px;font-weight:600;margin-bottom:2px">Formulaire de candidature</div>
    <a href="/closer/recruit" target="_blank" class="link-url">presence-ia.com/closer/recruit</a>
  </div>
  <div style="display:flex;gap:8px">
    <a href="/closer/recruit" target="_blank"
       style="padding:4px 12px;background:#6366f120;border:1px solid #6366f140;border-radius:4px;
              color:#6366f1;font-size:11px;text-decoration:none">Voir ↗</a>
    <button class="copy-btn" onclick="copyText('https://presence-ia.com/closer/recruit')">Copier lien</button>
  </div>
</div>

{closer_links}

<div class="section-sep"></div>

<!-- ── Éditeur messages ───────────────────────────── -->
<h2 style="color:#9ca3af;font-size:10px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:20px">
Mes messages de recrutement</h2>

<form id="msg-form">
  {_field("linkedin_dm",    "LinkedIn — Message direct", rows=8)}
  {_field("instagram_dm",   "Instagram — Message direct", rows=5)}
  {_field("facebook_dm",    "Facebook — DM / post groupe", rows=6)}
  {_field("email_subject",  "Email — Objet", rows=1)}
  {_field("email_body",     "Email — Corps", rows=10)}
  {_field("notes",          "Notes internes (mémo perso, non envoyé)", rows=4)}

  <button type="button" class="save-btn" onclick="saveMessages()">Sauvegarder</button>
</form>

</div>
<div class="toast" id="toast">Sauvegardé ✓</div>

<script>
function copyText(txt) {{
  navigator.clipboard.writeText(txt).then(() => showToast('Lien copié ✓'));
}}
function copyField(id) {{
  const v = document.getElementById(id).value;
  navigator.clipboard.writeText(v).then(() => showToast('Copié ✓'));
}}
function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2000);
}}
async function saveMessages() {{
  const fields = ['linkedin_dm','instagram_dm','facebook_dm','email_subject','email_body','notes'];
  const data = {{}};
  fields.forEach(f => {{ data[f] = document.getElementById(f).value; }});
  const r = await fetch('/admin/crm/closer-messages?token={token}', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(data)
  }});
  if (r.ok) showToast('Sauvegardé ✓');
  else showToast('Erreur !');
}}
</script>
</body></html>"""
    )


@router.post("/admin/crm/closer-messages")
async def save_closer_messages(request: Request):
    """Sauvegarde les messages de recrutement."""
    _check_token(request)
    data = await request.json()
    allowed = {"linkedin_dm", "instagram_dm", "facebook_dm",
                "email_subject", "email_body", "notes"}
    cleaned = {k: v for k, v in data.items() if k in allowed}
    try:
        _save_closer_messages(cleaned)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})
