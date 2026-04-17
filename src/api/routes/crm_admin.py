"""Admin — onglet CRM : pipeline prospects → RDV → deal + gestion closers."""
import os
import json
from pathlib import Path
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

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
        "contacted":       ("#9ca3af", "Contacté"),
        "applied":         ("#6366f1", "Candidature"),
        "reviewing":       ("#f59e0b", "En cours"),
        "waitlist":        ("#a78bfa", "Liste d'attente"),
        "accepted_locked": ("#0ea5e9", "Accepté — démarre lundi"),
        "accepted_trial":  ("#8b5cf6", "Accepté — semaine test"),
        "validated":       ("#2ecc71", "Validé"),
        "rejected":        ("#e94560", "Refusé"),
    }
    color, label = m.get(stage, ("#9ca3af", stage))
    return _badge(label, color)


def _send_recruit_email(to_email: str, to_name: str, stage: str) -> bool:
    """Envoie un email de décision au candidat selon le stage."""
    import requests as _req
    api_key = os.getenv("BREVO_API_KEY", "")
    if not api_key or not to_email:
        return False

    first = to_name.split()[0] if to_name else "Bonjour"

    subjects = {
        "accepted_locked": "Confirmation – démarrage lundi",
        "accepted_trial":  "Démarrage lundi – semaine test",
        "waitlist":        "Suite à votre candidature",
        "rejected":        "Suite à votre candidature",
        "validated":       "Votre candidature Présence IA a été retenue",
    }
    bodies = {
        "accepted_locked": (
            f"Bonjour,\n\n"
            "Merci pour votre candidature et votre enregistrement.\n\n"
            "Je vous confirme que nous vous retenons pour démarrer lundi avec nous.\n\n"
            "Vous allez recevoir un second email avec vos accès à votre espace privé, dans lequel vous trouverez :\n"
            "- le détail de l'offre\n"
            "- les éléments clés pour vos rendez-vous\n"
            "- les réponses aux objections principales\n\n"
            "Je vous invite à prendre le temps de vous approprier ces éléments avant vos premiers appels.\n\n"
            "À très vite,\nNathalie"
        ),
        "accepted_trial": (
            f"Bonjour,\n\n"
            "Merci pour votre candidature, votre profil nous a beaucoup intéressés.\n\n"
            "Nous vous proposons de démarrer lundi avec nous, avec une première semaine de test.\n\n"
            "Vous allez recevoir un second email avec vos accès à votre espace privé, dans lequel vous trouverez :\n"
            "- le détail de l'offre\n"
            "- les éléments clés pour vos rendez-vous\n"
            "- les réponses aux objections principales\n\n"
            "L'objectif est que vous puissiez vous approprier ces éléments avant vos premiers appels.\n\n"
            "En fonction des résultats, nous ajusterons ensuite la taille de l'équipe.\n\n"
            "À très vite,\nNathalie"
        ),
        "waitlist": (
            f"Bonjour,\n\n"
            "Merci pour votre candidature, elle a retenu toute mon attention.\n\n"
            "Je ne peux pas vous intégrer dès lundi, car nous limitons volontairement le nombre de closers pour le lancement.\n\n"
            "En revanche, votre profil m'intéresse vraiment et j'aimerais pouvoir vous intégrer dès que le volume se stabilise dans les prochaines semaines.\n\n"
            "Je me permets donc de revenir vers vous rapidement si une place se libère.\n\n"
            "À bientôt,\nNathalie"
        ),
        "rejected": (
            f"Bonjour,\n\n"
            "Merci pour votre candidature et le temps que vous y avez consacré.\n\n"
            "Nous avons fait le choix d'avancer avec un nombre très limité de profils pour le lancement, "
            "ce qui ne nous permet malheureusement pas de donner suite pour le moment.\n\n"
            "Je vous souhaite le meilleur pour la suite.\n\n"
            "Nathalie"
        ),
        "validated": (
            f"Bonjour,\n\n"
            "Votre candidature a été retenue. Vous allez recevoir vos accès très prochainement.\n\n"
            "À très bientôt,\nNathalie"
        ),
    }
    subject = subjects.get(stage)
    body    = bodies.get(stage)
    if not subject or not body:
        return False
    sender_name  = os.getenv("SENDER_NAME",  "Nathalie — Présence IA")
    sender_email = os.getenv("SENDER_EMAIL", "contact@presence-ia.online")
    try:
        resp = _req.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={
                "sender":      {"name": sender_name, "email": sender_email},
                "to":          [{"email": to_email, "name": to_name}],
                "subject":     subject,
                "textContent": body,
            },
            timeout=8,
        )
        return resp.status_code == 201
    except Exception:
        return False


def _send_access_email(to_email: str, to_name: str, portal_url: str) -> bool:
    """Envoie l'email d'accès au portail closer."""
    import requests as _req
    api_key = os.getenv("BREVO_API_KEY", "")
    if not api_key or not to_email:
        return False
    body = (
        f"Bonjour,\n\n"
        f"Voici vos accès à votre espace :\n\n"
        f"{portal_url}\n\n"
        f"Je vous invite à consulter en priorité :\n"
        f"- le détail de l'offre\n"
        f"- les objections\n"
        f"- la structure des appels\n\n"
        f"À très vite\n\nNathalie"
    )
    sender_name  = os.getenv("SENDER_NAME",  "Nathalie — Présence IA")
    sender_email = os.getenv("SENDER_EMAIL", "contact@presence-ia.online")
    try:
        resp = _req.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={
                "sender":      {"name": sender_name, "email": sender_email},
                "to":          [{"email": to_email, "name": to_name}],
                "subject":     "Accès à votre espace closer",
                "textContent": body,
            },
            timeout=8,
        )
        return resp.status_code == 201
    except Exception:
        return False


def _create_closer_and_send_access(mdb, app) -> str | None:
    """Crée CloserDB si inexistant, envoie email accès. Retourne le token closer."""
    from marketing_module.models import CloserDB
    from datetime import datetime
    import os as _os

    existing = mdb.query(CloserDB).filter_by(
        project_id=app.project_id, email=app.email
    ).first()
    if existing:
        closer = existing
    else:
        _full = f"{app.first_name or ''} {app.last_name or ''}".strip() or (app.email or "Closer")
        closer = CloserDB(
            project_id=app.project_id,
            name=_full,
            first_name=app.first_name,
            last_name=app.last_name,
            email=app.email,
            phone=app.phone,
            commission_rate=0.18,
            is_active=True,
            contact_id=app.contact_id,
        )
        mdb.add(closer)
        mdb.flush()

    app.access_granted = True
    mdb.commit()

    base_url = _os.getenv("BASE_URL", "https://presence-ia.com")
    portal_url = f"{base_url}/closer/{closer.token}"
    _name = f"{app.first_name or ''} {app.last_name or ''}".strip() or "Closer"
    _send_access_email(app.email, _name, portal_url)
    return closer.token


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
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:16px 20px;text-align:center;box-shadow:0 1px 4px rgba(82,127,179,.07)">'
        f'<div style="font-size:1.8rem;font-weight:700;color:{c}">{v}</div>'
        f'<div style="color:#6b7280;font-size:11px;margin-top:4px">{l}</div>'
        f'<div style="color:#9ca3af;font-size:10px">{s}</div></div>'
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
        bg  = "#527fb3" if active else "#f0f4f8"
        col = "#fff"    if active else "#6b7280"
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
                f'<div style="color:#6b7280;font-size:10px;margin-top:3px">{m["scheduled_at"]}{deal}</div>'
                f'<div style="color:#9ca3af;font-size:10px">{m["notes"][:40] if m["notes"] else ""}</div>'
            )
            update_btn = (
                f'<select onchange="updateMeeting(\'{m["id"]}\',this.value,\'{token}\')" '
                f'style="font-size:10px;padding:2px 4px;background:#fff;color:#394455;border:1px solid #d1d5db;border-radius:4px;margin-top:4px">'
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
            f'<tr style="border-bottom:1px solid #f0f4f8">'
            f'<td style="padding:10px 12px">'
            f'  <a href="/admin/crm/prospect/{r["token"]}?token={token}" '
            f'style="color:#394455;font-size:13px;font-weight:500;text-decoration:none">{r["name"]}</a>'
            f'  <div style="color:#6b7280;font-size:11px">{r["city"]} · {r["profession"]}</div>'
            f'  <div style="color:#9ca3af;font-size:10px">{r["email"]}</div>'
            f'</td>'
            f'<td style="padding:10px 12px;color:#6b7280;font-size:11px">'
            f'  {r["sent_at"]}<br>{r["sent_method"]}'
            f'</td>'
            f'<td style="padding:10px 12px">{delivery_badge}<br>{landing_link}</td>'
            f'<td style="padding:10px 12px">{meeting_html}</td>'
            f'</tr>'
        )

    rows_html = "".join(_row(r) for r in rows) or (
        '<tr><td colspan="4" style="padding:40px;text-align:center;color:#9ca3af">'
        'Aucun prospect contacté pour l\'instant</td></tr>'
    )

    table_view = f"""
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(82,127,179,.07)">
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
            f'style="background:#fff;border:1px solid #e2e8f0;border-radius:6px;'
            f'padding:10px;margin-bottom:8px;cursor:pointer;transition:border-color .15s;box-shadow:0 1px 3px rgba(82,127,179,.06)" '
            f'onmouseover="this.style.borderColor=\'#527fb3\'" '
            f'onmouseout="this.style.borderColor=\'#e2e8f0\'">'
            f'<div style="color:#394455;font-size:12px;font-weight:600">{r["name"]}</div>'
            f'<div style="color:#6b7280;font-size:10px;margin-top:2px">{r["city"]} · {r["profession"]}</div>'
            f'{deal_str}'
            f'<div style="color:#9ca3af;font-size:10px;margin-top:4px">{r["sent_at"]}</div>'
            f'</div>'
        )

    kanban_cols = ""
    for stage_key, stage_label, stage_color in STAGES:
        cards = by_stage[stage_key]
        cards_html = "".join(_kanban_card(r) for r in cards)
        kanban_cols += (
            f'<div class="kcol" data-stage="{stage_key}" '
            f'style="flex:0 0 200px;background:#f8fafc;border:1px solid #e2e8f0;'
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
body{{font-family:'Segoe UI',sans-serif;background:#f8fafc;color:#394455}}
table{{width:100%;border-collapse:collapse}}
th{{padding:10px 12px;text-align:left;color:#6b7280;font-size:10px;font-weight:600;
   letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #e2e8f0}}
tr:hover{{background:#f0f4f8}}
.kcard.dragging{{opacity:.5;transform:scale(.97)}}
</style></head><body>
{admin_nav(token, "crm")}
<div style="max-width:1200px;margin:0 auto;padding:24px">

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
<h1 style="color:#394455;font-size:18px">CRM — Pipeline</h1>
<a href="/admin/crm/closers?token={token}" style="color:#527fb3;font-size:12px;text-decoration:none">Gérer les closers →</a>
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
        f'<tr style="border-bottom:1px solid #f0f4f8">'
        f'<td style="padding:8px 12px;color:#394455;font-size:12px">{_fmt(d.created_at)}</td>'
        f'<td style="padding:8px 12px">{_delivery_badge({"delivery_status":d.delivery_status,"opened_at":d.opened_at,"clicked_at":d.clicked_at,"reply_status":d.reply_status,"bounce_type":d.bounce_type})}</td>'
        f'<td style="padding:8px 12px;color:#6b7280;font-size:11px">{_fmt(d.opened_at)}</td>'
        f'<td style="padding:8px 12px;color:#6b7280;font-size:11px">{_fmt(d.clicked_at)}</td>'
        f'<td style="padding:8px 12px;color:#6b7280;font-size:11px">{_fmt(getattr(d,"landing_visited_at",None))}</td>'
        f'</tr>'
        for d in deliveries
    ) or '<tr><td colspan="5" style="padding:20px;color:#9ca3af;text-align:center">Aucune livraison</td></tr>'

    mtg_rows = "".join(
        f'<tr style="border-bottom:1px solid #f0f4f8">'
        f'<td style="padding:8px 12px;color:#394455;font-size:12px">{_fmt(m.scheduled_at)}</td>'
        f'<td style="padding:8px 12px">{_status_badge(m.status)}</td>'
        f'<td style="padding:8px 12px;color:#6b7280;font-size:11px">{m.deal_value or "—"}</td>'
        f'<td style="padding:8px 12px;color:#6b7280;font-size:11px">{getattr(m,"outcome","") or (m.notes or "—")}</td>'
        f'</tr>'
        for m in meetings
    ) or '<tr><td colspan="4" style="padding:20px;color:#9ca3af;text-align:center">Aucun RDV</td></tr>'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>{p.name} — CRM</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#f8fafc;color:#394455}}
table{{width:100%;border-collapse:collapse}}
th{{padding:8px 12px;text-align:left;color:#6b7280;font-size:10px;
   font-weight:600;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #e2e8f0}}
tr:hover{{background:#f0f4f8}}
</style></head><body>
{admin_nav(admin_token, "crm")}
<div style="max-width:900px;margin:0 auto;padding:24px">
<a href="/admin/crm?token={admin_token}" style="color:#527fb3;font-size:12px;text-decoration:none">← CRM</a>
<h1 style="color:#394455;font-size:18px;margin:16px 0 4px">{p.name}</h1>
<p style="color:#6b7280;font-size:13px">{p.city} · {p.profession} · {p.email}</p>
{f'<p style="color:#6b7280;font-size:12px;margin-top:4px">📞 {p.phone}</p>' if p.phone else ""}

<div style="margin:24px 0 16px">
  <div style="color:#6b7280;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;margin-bottom:12px">Rapports IA</div>
  <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
    <button onclick="iaAction('{p.token}','audit',this)"
      style="background:#e94560;color:#fff;border:none;padding:10px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600">
      📊 Générer audit
    </button>
    <button onclick="iaAction('{p.token}','monthly',this)"
      style="background:#1e3a5f;color:#fff;border:none;padding:10px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600">
      📅 Rapport mensuel
    </button>
    <button onclick="iaAction('{p.token}','bundle',this)"
      style="background:#16a34a;color:#fff;border:none;padding:10px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600">
      📦 Bundle complet
    </button>
    <button onclick="iaAction('{p.token}','content',this)"
      style="background:#7c3aed;color:#fff;border:none;padding:10px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600">
      ✍ Générer contenus
    </button>
    <button onclick="togglePublish('{p.token}')"
      style="background:#0e7490;color:#fff;border:none;padding:10px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600">
      🚀 Publier sur le site
    </button>
    <a href="/api/reports/v3/{p.token}/audit" target="_blank"
      style="background:#2a2a4e;color:#9ca3af;border:1px solid #3a3a6e;padding:10px 18px;border-radius:6px;text-decoration:none;font-size:13px">
      👁 Voir audit HTML
    </a>
    <button onclick="iaMesh('{p.token}',this)"
      style="background:#78350f;color:#fde68a;border:none;padding:10px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600">
      🔗 Maillage interne
    </button>
  </div>
  <div id="ia-result-{p.token}" style="margin-top:12px;display:none;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px;font-size:13px"></div>

  <!-- Credentials WP — visibles uniquement pour la publication -->
  <div id="wp-creds-{p.token}" style="margin-top:10px;display:none;flex-wrap:wrap;gap:8px;align-items:center">
    <input id="wp-user-{p.token}" placeholder="Identifiant WP"
      style="padding:8px 12px;border-radius:6px;border:1px solid #d1d5db;background:#fff;color:#394455;font-size:13px;width:160px">
    <input id="wp-pass-{p.token}" placeholder="Application Password"
      style="padding:8px 12px;border-radius:6px;border:1px solid #d1d5db;background:#fff;color:#394455;font-size:13px;width:240px">
    <button onclick="iaPublish('{p.token}',this)"
      style="background:#0e7490;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600">Publier</button>
    <span style="color:#6b7280;font-size:11px">WP → Profil → Application Passwords · Laisser vide pour package manuel</span>
  </div>
</div>

<script>
async function iaAction(token, action, btn) {{
  const resultEl = document.getElementById('ia-result-' + token);
  const origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = '⏳ En cours…';
  resultEl.style.display = 'none';
  try {{
    const r = await fetch('/api/ia-reports/' + token + '/' + action, {{method:'POST', headers:{{'Content-Type':'application/json'}}}});
    const data = await r.json();
    resultEl.style.display = 'block';
    if (data.success) {{
      const res = data.result;
      let html = '<span style="color:#16a34a;font-weight:700">✓ ' + data.message + '</span><br>';
      if (res.score !== undefined) html += '<span style="color:#9ca3af">Score : <strong style="color:#fff">' + res.score + '/10</strong>';
      if (res.delta !== undefined) html += ' &nbsp;Δ <strong style="color:' + (res.delta>=0?'#16a34a':'#ef4444') + '">' + (res.delta>=0?'+':'') + res.delta + '</strong>';
      if (res.score !== undefined) html += '</span><br>';
      if (res.audit_path) html += '<span style="color:#527FB3;font-size:12px">📄 ' + res.audit_path.split('/').slice(-1)[0] + '</span><br>';
      if (res.report_path) html += '<span style="color:#527FB3;font-size:12px">📄 ' + res.report_path.split('/').slice(-1)[0] + '</span><br>';
      if (res.errors && res.errors.length) html += '<span style="color:#f87171;font-size:12px">⚠ ' + res.errors.join(' / ') + '</span>';
      resultEl.innerHTML = html;
    }} else {{
      resultEl.innerHTML = '<span style="color:#ef4444">✗ Erreur : ' + (data.error?.detail || data.error?.code || 'inconnue') + '</span>';
    }}
  }} catch(e) {{
    resultEl.style.display = 'block';
    resultEl.innerHTML = '<span style="color:#ef4444">✗ ' + e.message + '</span>';
  }}
  btn.disabled = false;
  btn.textContent = origText;
}}

function togglePublish(token) {{
  const el = document.getElementById('wp-creds-' + token);
  el.style.display = el.style.display === 'none' ? 'flex' : 'none';
}}

async function iaPublish(token, btn) {{
  const resultEl  = document.getElementById('ia-result-' + token);
  const origText  = btn.textContent;
  const username  = document.getElementById('wp-user-' + token).value;
  const appPass   = document.getElementById('wp-pass-' + token).value;
  btn.disabled    = true;
  btn.textContent = '⏳ Publication…';
  resultEl.style.display = 'none';
  const body = {{}};
  if (username) body.username = username;
  if (appPass)  body.app_password = appPass;
  try {{
    const r = await fetch('/api/ia-reports/' + token + '/publish', {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify(body)
    }});
    const data = await r.json();
    resultEl.style.display = 'block';
    if (data.success) {{
      const res = data.result;
      let html = '<span style="color:#16a34a;font-weight:700">✓ ' + data.message + '</span><br>';
      if (res.url) html += '<a href="' + res.url + '" target="_blank" style="color:#38bdf8">' + res.url + '</a><br>';
      if (res.edit_url) html += '<a href="' + res.edit_url + '" target="_blank" style="color:#9ca3af;font-size:12px">✏ Modifier dans WP</a><br>';
      if (res.visibility) {{
        const badge = res.visibility === 'discreet'
          ? '<span style="background:#14532d;color:#4ade80;padding:2px 10px;border-radius:20px;font-size:12px;font-weight:700">🟢 Page publiée (discrète)</span>'
          : '<span style="background:#1e3a5f;color:#60a5fa;padding:2px 10px;border-radius:20px;font-size:12px;font-weight:700">🔵 Page publiée (intégrée)</span>';
        html += badge + '<br>';
      }}
      if (res.menu_note) html += '<span style="color:#fbbf24;font-size:12px">ℹ ' + res.menu_note + '</span><br>';
      if (res.publish_date) html += '<span style="color:#6b7280;font-size:11px">Publié le ' + res.publish_date + '</span><br>';
      if (res.score !== undefined) html += '<span style="color:#9ca3af">Score : <strong style="color:#fff">' + res.score + '/10</strong>';
      if (res.delta !== undefined) html += ' &nbsp;Δ <strong style="color:' + (res.delta>=0?'#16a34a':'#ef4444') + '">' + (res.delta>=0?'+':'') + res.delta + '</strong>';
      if (res.score !== undefined) html += '</span><br>';
      if (res.audit_path) html += '<span style="color:#527FB3;font-size:12px">📄 ' + res.audit_path.split('/').slice(-1)[0] + '</span><br>';
      if (res.report_path) html += '<span style="color:#527FB3;font-size:12px">📄 ' + res.report_path.split('/').slice(-1)[0] + '</span><br>';
      if (res.method === 'manual' && res.instructions) {{
        html += '<details style="margin-top:8px"><summary style="color:#fbbf24;cursor:pointer;font-size:12px">📋 Instructions publication manuelle</summary>';
        html += '<pre style="white-space:pre-wrap;font-size:11px;color:#9ca3af;margin-top:8px">' + res.instructions + '</pre></details>';
      }}
      if (res.errors && res.errors.length) html += '<span style="color:#f87171;font-size:12px">⚠ ' + res.errors.join(' / ') + '</span>';
      resultEl.innerHTML = html;
    }} else {{
      resultEl.innerHTML = '<span style="color:#ef4444">✗ ' + (data.error?.detail || 'Erreur inconnue') + '</span>';
    }}
  }} catch(e) {{
    resultEl.style.display = 'block';
    resultEl.innerHTML = '<span style="color:#ef4444">✗ ' + e.message + '</span>';
  }}
  btn.disabled = false;
  btn.textContent = origText;
}}

async function iaMesh(token, btn) {{
  const resultEl = document.getElementById('ia-result-' + token);
  const origText = btn.textContent;
  btn.disabled   = true;
  btn.textContent = '⏳ Calcul…';
  resultEl.style.display = 'none';
  try {{
    const r   = await fetch('/api/ia-reports/' + token + '/mesh', {{method:'POST', headers:{{'Content-Type':'application/json'}}}});
    const res = await r.json();
    resultEl.style.display = 'block';
    if (res.success) {{
      let html = '<span style="color:#4ade80">🔗 ' + (res.message || 'Maillage mis à jour') + '</span>';
      if (res.result && res.result.pages && res.result.pages.length > 0) {{
        html += '<div style="margin-top:10px;display:flex;flex-direction:column;gap:8px">';
        for (const pg of res.result.pages) {{
          if (pg.links_count === 0) continue;
          html += '<div style="background:#0f0f1a;border:1px solid #2a2a4e;border-radius:4px;padding:8px 12px">';
          html += '<div style="color:#e8e8f0;font-weight:600;font-size:12px;margin-bottom:6px">' + (pg.title || pg.url || 'Page #' + pg.id) + '</div>';
          for (const lk of pg.links) {{
            html += '<div style="color:#9ca3af;font-size:12px;padding:2px 0">→ <a href="' + lk.url + '" target="_blank" style="color:#60a5fa;text-decoration:none">' + lk.anchor + '</a>';
            html += ' <span style="color:#4b5563;font-style:italic">(' + lk.reason + ')</span></div>';
          }}
          if (pg.patch_html) {{
            html += '<details style="margin-top:6px"><summary style="color:#fde68a;font-size:11px;cursor:pointer">HTML du bloc à injecter</summary>';
            html += '<pre style="color:#9ca3af;font-size:10px;overflow-x:auto;margin:4px 0;white-space:pre-wrap">' + pg.patch_html.replace(/</g,'&lt;') + '</pre></details>';
          }}
          html += '</div>';
        }}
        html += '</div>';
      }} else if (res.result && res.result.pages_updated === 0) {{
        html += '<div style="color:#9ca3af;font-size:12px;margin-top:6px">Aucune page publiée dans l\'index pour ce prospect.<br>Publiez d\'abord une page via 🚀 Publier sur le site.</div>';
      }}
      resultEl.innerHTML = html;
    }} else {{
      const err = res.error ? (res.error.detail || JSON.stringify(res.error)) : 'Erreur inconnue';
      resultEl.innerHTML = '<span style="color:#ef4444">✗ ' + err + '</span>';
    }}
  }} catch(e) {{
    resultEl.style.display = 'block';
    resultEl.innerHTML = '<span style="color:#ef4444">✗ ' + e.message + '</span>';
  }}
  btn.disabled = false;
  btn.textContent = origText;
}}
</script>

<div style="margin:24px 0 12px;color:#6b7280;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase">Livraisons emails</div>
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;margin-bottom:24px;box-shadow:0 1px 4px rgba(82,127,179,.07)">
<table><thead><tr><th>Date</th><th>Statut</th><th>Ouverture</th><th>Clic</th><th>Landing</th></tr></thead>
<tbody>{del_rows}</tbody></table></div>

<div style="margin-bottom:12px;color:#6b7280;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase">RDV Calendly</div>
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(82,127,179,.07)">
<table><thead><tr><th>Date RDV</th><th>Statut</th><th>Deal</th><th>Résultat / Notes</th></tr></thead>
<tbody>{mtg_rows}</tbody></table></div>
</div></body></html>""")


# ─────────────────────────────────────────────────────────────────────────────
# Admin — gestion closers + candidatures
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/admin/crm/closers", response_class=HTMLResponse)
def crm_closers(request: Request):
    token        = _check_token(request)
    stage_filter = request.query_params.get("stage", "")

    closers = []
    applications = []
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import CloserDB, CloserApplicationDB
        with MktSession() as mdb:
            closers = mdb.query(CloserDB).filter_by(project_id="presence-ia").all()
            q = mdb.query(CloserApplicationDB).filter(
                CloserApplicationDB.project_id == "presence-ia",
            )
            if stage_filter:
                q = q.filter(CloserApplicationDB.stage == stage_filter)
            applications = q.order_by(CloserApplicationDB.created_at.desc()).all()
    except Exception:
        pass

    # Counts par stage pour filtres
    stage_counts: dict = {}
    for a in applications:
        stage_counts[a.stage] = stage_counts.get(a.stage, 0) + 1
    total_apps = len(applications)

    _STAGE_FILTERS = [
        ("",               "Tous",              "#6b7280"),
        ("applied",        "Candidatures",      "#6366f1"),
        ("reviewing",      "En cours",          "#f59e0b"),
        ("accepted_locked","Accepté lundi",     "#0ea5e9"),
        ("accepted_trial", "Semaine test",      "#8b5cf6"),
        ("waitlist",       "Liste d'attente",   "#a78bfa"),
        ("rejected",       "Refusés",           "#e94560"),
    ]
    filter_btns = "".join(
        f'<a href="/admin/crm/closers?token={token}&stage={s}" '
        f'style="padding:5px 12px;border-radius:20px;font-size:11px;font-weight:600;'
        f'text-decoration:none;border:1px solid {c};'
        f'background:{"" + c + "20" if stage_filter == s else "#f8fafc"};'
        f'color:{c if stage_filter == s else "#6b7280"}">'
        f'{l}</a>'
        for s, l, c in _STAGE_FILTERS
    )

    closer_rows = "".join(
        f'<tr>'
        f'<td style="padding:10px 12px;color:#394455;font-size:12px">{c.name}</td>'
        f'<td style="padding:10px 12px;color:#6b7280;font-size:11px">{c.email or "—"}</td>'
        f'<td style="padding:10px 12px;color:#6b7280;font-size:11px">{c.commission_rate*100:.0f}%</td>'
        f'<td style="padding:10px 12px">{"<span style=\'color:#2ecc71\'>Actif</span>" if c.is_active else "<span style=\'color:#e94560\'>Inactif</span>"}</td>'
        f'<td style="padding:10px 12px">'
        f'<a href="/closer/{getattr(c,"token",c.id) or c.id}?preview=1" target="_blank" style="color:#527FB3;font-size:10px;margin-right:8px">↗ Portail</a>'
        f'<a href="/closer/{getattr(c,"token",c.id) or c.id}/agenda" target="_blank" style="color:#996d2e;font-size:10px">📅 Agenda</a>'
        f'</td>'
        f'</tr>'
        for c in closers
    ) or '<tr><td colspan="5" style="padding:20px;color:#9ca3af;text-align:center">Aucun closer</td></tr>'

    def _yn(val, yes="✓", no="—", yes_color="#2ecc71", no_color="#9ca3af"):
        return (f'<span style="color:{yes_color};font-weight:600">{yes}</span>' if val
                else f'<span style="color:{no_color}">{no}</span>')

    app_rows = "".join(
        f'<tr>'
        f'<td style="padding:10px 12px;color:#394455;font-size:12px">'
        f'{(a.first_name or "") + " " + (a.last_name or "")}'.strip()
        + f' <span style="color:#9ca3af;font-size:10px">{a.city or ""}</span></td>'
        f'<td style="padding:10px 12px;color:#6b7280;font-size:11px">{a.email or "—"}</td>'
        f'<td style="padding:10px 12px">{_app_stage_badge(a.stage)}</td>'
        f'<td style="padding:10px 12px;text-align:center">{_yn(getattr(a,"response_sent",False))}</td>'
        f'<td style="padding:10px 12px;text-align:center">{_yn(getattr(a,"access_granted",False))}</td>'
        f'<td style="padding:10px 12px;color:#6b7280;font-size:11px">'
        f'{a.applied_at.strftime("%d/%m/%y") if a.applied_at else "—"}'
        f'</td>'
        f'<td style="padding:10px 12px">'
        f'<a href="/admin/crm/application/{a.id}?token={token}" style="color:#527FB3;font-size:10px">Voir →</a>'
        f'</td>'
        f'</tr>'
        for a in applications
    ) or '<tr><td colspan="7" style="padding:20px;color:#9ca3af;text-align:center">Aucune candidature</td></tr>'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Closers — CRM</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#f8fafc;color:#394455}}
table{{width:100%;border-collapse:collapse}}
th{{padding:10px 12px;text-align:left;color:#6b7280;font-size:10px;font-weight:600;
   letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #e2e8f0}}
tr:hover{{background:#f0f4f8}}
</style></head><body>
{admin_nav(token, "crm")}
<div style="max-width:1200px;margin:0 auto;padding:24px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
  <h1 style="color:#394455;font-size:18px">Closers <span style="color:#9ca3af;font-size:13px;font-weight:400">— {total_apps} candidature(s)</span></h1>
  <div style="display:flex;gap:16px;align-items:center">
    <a href="/admin/crm/closer-messages?token={token}" style="color:#527fb3;font-size:12px;text-decoration:none">Messages recrutement →</a>
    <a href="/admin/crm?token={token}" style="color:#527fb3;font-size:12px;text-decoration:none">← CRM</a>
  </div>
</div>

<!-- Aperçu pages publiques -->
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;margin-bottom:20px;box-shadow:0 1px 4px rgba(82,127,179,.07)">
  <p style="color:#6b7280;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px">Pages closer</p>
  <div style="display:flex;gap:10px;flex-wrap:wrap">
    <a href="/closer/" target="_blank" style="padding:7px 14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;color:#6b7280;font-size:12px;text-decoration:none">🌐 Présentation</a>
    <a href="/closer/recruit" target="_blank" style="padding:7px 14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;color:#6b7280;font-size:12px;text-decoration:none">📝 Candidature</a>
    <a href="/closer/demo" target="_blank" style="padding:7px 14px;background:#527fb310;border:1px solid #527fb330;border-radius:6px;color:#527fb3;font-size:12px;text-decoration:none">👤 Portail aperçu</a>
  </div>
</div>

<!-- Filtres par stage -->
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">{filter_btns}</div>

<!-- Closers actifs -->
<h2 style="color:#6b7280;font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:12px">Closers actifs ({len(closers)})</h2>
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;margin-bottom:32px;box-shadow:0 1px 4px rgba(82,127,179,.07)">
<table><thead><tr><th>Nom</th><th>Email</th><th>Commission</th><th>Statut</th><th></th></tr></thead>
<tbody>{closer_rows}</tbody></table></div>

<!-- Candidatures -->
<h2 style="color:#6b7280;font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:12px">Candidatures</h2>
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(82,127,179,.07)">
<table><thead><tr>
  <th>Candidat</th><th>Email</th><th>Statut</th>
  <th style="text-align:center">Email envoyé</th>
  <th style="text-align:center">Accès créé</th>
  <th>Date</th><th></th>
</tr></thead>
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
    _stage_opts = [
        ("contacted",       "Contacté",          "#9ca3af"),
        ("applied",         "Candidature",       "#6366f1"),
        ("reviewing",       "En cours",          "#f59e0b"),
        ("accepted_locked", "Accepté — lundi",   "#0ea5e9"),
        ("accepted_trial",  "Semaine test",      "#8b5cf6"),
        ("waitlist",        "Liste d'attente",   "#a78bfa"),
        ("rejected",        "Refuser",           "#e94560"),
    ]
    stage_btns = "".join(
        f'<a href="/admin/crm/application/{app.id}/set-stage/{s}?token={token}" '
        f'style="display:inline-block;padding:8px 16px;border-radius:6px;font-size:12px;font-weight:600;'
        f'text-decoration:none;cursor:pointer;'
        f'background:{c + "20" if app.stage == s else "#f8fafc"};'
        f'color:{c};border:1px solid {c if app.stage == s else "#e2e8f0"}">{l}</a>'
        for s, l, c in _stage_opts
    )
    response_sent  = getattr(app, "response_sent",  False)
    access_granted = getattr(app, "access_granted", False)

    video_block = (f'<div style="margin-top:12px"><a href="{app.video_url}" target="_blank" '
                   f'style="color:#527FB3;font-size:13px">▶ Voir la vidéo</a></div>') if app.video_url else ""
    audio_block = (f'<div style="margin-top:8px"><audio controls src="{app.audio_url}" '
                   f'style="width:100%"></audio></div>') if app.audio_url else ""

    stage_label = dict((s, l) for s, l, c in _stage_opts).get(app.stage, app.stage)
    stage_color = dict((s, c) for s, l, c in _stage_opts).get(app.stage, "#9ca3af")

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
<title>{name} — Candidature</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#f8fafc;color:#394455}}
</style></head><body>
{admin_nav(token, "crm")}
<div style="max-width:800px;margin:0 auto;padding:24px">
<a href="/admin/crm/closers?token={token}" style="color:#527FB3;font-size:12px;text-decoration:none">← Closers</a>
<div style="margin:16px 0;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
  <h1 style="color:#394455;font-size:18px">{name}</h1>
  <span style="font-size:11px;font-weight:700;color:{stage_color};background:{stage_color}20;padding:3px 10px;border-radius:20px;border:1px solid {stage_color}40">{stage_label}</span>
</div>
<p style="color:#6b7280;font-size:13px">{app.city or "—"} · {app.country or "FR"} · {app.email or "—"}</p>
{f'<p style="color:#6b7280;font-size:12px;margin-top:4px">📞 {app.phone}</p>' if app.phone else ""}
{f'<p style="margin-top:8px"><a href="{app.linkedin_url}" target="_blank" style="color:#527FB3;font-size:12px">LinkedIn →</a></p>' if app.linkedin_url else ""}

<!-- Statuts -->
<div style="margin:24px 0 8px">
  <p style="color:#6b7280;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">Changer le statut</p>
  <div style="display:flex;gap:8px;flex-wrap:wrap">{stage_btns}</div>
</div>

<!-- Actions -->
<div style="margin:16px 0 24px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;box-shadow:0 1px 4px rgba(82,127,179,.07)">
  <p style="color:#6b7280;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Actions</p>
  <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
    <span style="font-size:12px;color:#6b7280">
      Email réponse : {"<span style='color:#2ecc71;font-weight:600'>envoyé</span>" if response_sent else "<span style='color:#9ca3af'>non envoyé</span>"}
      &nbsp;·&nbsp;
      Accès portail : {"<span style='color:#2ecc71;font-weight:600'>créé</span>" if access_granted else "<span style='color:#9ca3af'>non créé</span>"}
    </span>
  </div>
  <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">
    <button onclick="sendAccess()" id="btn-access"
      style="padding:8px 16px;background:#0ea5e920;border:1px solid #0ea5e9;border-radius:6px;
             color:#0ea5e9;font-size:12px;font-weight:600;cursor:pointer">
      Envoyer email accès portail
    </button>
  </div>
  <div id="action-result" style="display:none;margin-top:8px;font-size:12px"></div>
</div>

{f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-top:24px;box-shadow:0 1px 4px rgba(82,127,179,.07)"><p style="color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Message de présentation</p><p style="color:#394455;font-size:13px;line-height:1.6">{app.message}</p></div>' if app.message else ""}

{video_block}
{audio_block}

<div style="margin-top:24px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:16px;box-shadow:0 1px 4px rgba(82,127,179,.07)">
<p style="color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Notes admin</p>
<textarea id="notes" rows="4" style="width:100%;background:#f8fafc;color:#394455;border:1px solid #d1d5db;border-radius:4px;padding:8px;font-size:13px;resize:vertical">{app.admin_notes or ""}</textarea>
<button onclick="saveNotes()" style="margin-top:8px;padding:6px 14px;background:linear-gradient(135deg,#996d2e,#ffbd5c);border:none;border-radius:4px;color:#fff;font-size:12px;cursor:pointer;font-weight:600">Sauvegarder les notes</button>
</div>

</div>
<script>
async function saveNotes() {{
  const notes = document.getElementById('notes').value;
  const r = await fetch('/admin/crm/application/{app.id}/notes?token={token}', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{notes}})
  }});
  if (r.ok) alert('Notes sauvegardées');
}}
async function sendAccess() {{
  const btn = document.getElementById('btn-access');
  const res = document.getElementById('action-result');
  btn.disabled = true;
  btn.textContent = '⏳ Envoi...';
  const r = await fetch('/api/admin/closer/application/{app.id}/send-access?token={token}', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}}
  }});
  const d = await r.json();
  res.style.display = 'block';
  res.style.color = d.ok ? '#2ecc71' : '#e94560';
  res.textContent = d.ok ? '✓ Email accès envoyé + compte créé' : ('Erreur : ' + (d.error || ''));
  btn.disabled = false;
  btn.textContent = 'Envoyer email accès portail';
}}
</script>
</body></html>""")


@router.get("/admin/crm/application/{app_id}/set-stage/{stage}")
def set_application_stage_get(app_id: str, stage: str, request: Request):
    """Validation candidature via lien direct (GET + redirect)."""
    from fastapi.responses import RedirectResponse
    token = _check_token(request)
    _DECISION_STAGES = ("accepted_locked", "accepted_trial", "waitlist", "rejected", "validated")
    try:
        from marketing_module.database import SessionLocal as MktSession, db_update_application
        from marketing_module.models import CloserApplicationDB
        from datetime import datetime
        updates = {"stage": stage}
        if stage in ("validated", "accepted_locked", "accepted_trial"):
            updates["validated_at"] = datetime.utcnow()
        elif stage == "reviewing":
            updates["reviewed_at"] = datetime.utcnow()
        with MktSession() as mdb:
            db_update_application(mdb, app_id, updates)
            app = mdb.query(CloserApplicationDB).filter_by(id=app_id).first()
            if app and app.email and stage in _DECISION_STAGES:
                _name = f"{app.first_name or ''} {app.last_name or ''}".strip() or "Candidat"
                ok = _send_recruit_email(app.email, _name, stage)
                if ok:
                    db_update_application(mdb, app_id, {"response_sent": True})
            if stage in ("accepted_locked", "accepted_trial", "validated") and app:
                _create_closer_and_send_access(mdb, app)
    except Exception:
        pass
    return RedirectResponse(f"/admin/crm/application/{app_id}?token={token}", status_code=303)


@router.post("/admin/crm/application/{app_id}/stage")
async def set_application_stage(app_id: str, request: Request):
    _check_token(request)
    data  = await request.json()
    stage = data.get("stage", "")
    _DECISION_STAGES = ("accepted_locked", "accepted_trial", "waitlist", "rejected", "validated")
    try:
        from marketing_module.database import SessionLocal as MktSession, db_update_application
        from marketing_module.models import CloserApplicationDB
        from datetime import datetime
        updates = {"stage": stage}
        if stage in ("validated", "accepted_locked", "accepted_trial"):
            updates["validated_at"] = datetime.utcnow()
        elif stage == "reviewing":
            updates["reviewed_at"] = datetime.utcnow()
        with MktSession() as mdb:
            db_update_application(mdb, app_id, updates)
            app = mdb.query(CloserApplicationDB).filter_by(id=app_id).first()
            if app and app.email and stage in _DECISION_STAGES:
                _name = f"{app.first_name or ''} {app.last_name or ''}".strip() or "Candidat"
                ok = _send_recruit_email(app.email, _name, stage)
                if ok:
                    db_update_application(mdb, app_id, {"response_sent": True})
            if stage in ("accepted_locked", "accepted_trial", "validated") and app:
                _create_closer_and_send_access(mdb, app)
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


@router.post("/api/admin/closer/application/{app_id}/send-access")
async def send_closer_access(app_id: str, request: Request):
    """Envoie manuellement l'email d'accès portail closer."""
    _check_token(request)
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import CloserApplicationDB
        with MktSession() as mdb:
            app = mdb.query(CloserApplicationDB).filter_by(id=app_id).first()
            if not app:
                return JSONResponse({"ok": False, "error": "introuvable"})
            token_closer = _create_closer_and_send_access(mdb, app)
        return JSONResponse({"ok": True, "token": token_closer})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# Messages de recrutement closers
# ─────────────────────────────────────────────────────────────────────────────

_MESSAGES_FILE   = Path(__file__).parent.parent.parent.parent / "data" / "closer_messages.json"
_POST_IMAGE_DIR  = Path(__file__).parent.parent.parent.parent / "data"
_POST_IMAGE_STEM = "closer_post_image"

_DEFAULT_MESSAGES = {
    "post_groupe": (
        "Je recrute des closers indépendants 🚀\n\n"
        "On aide les artisans et PME locales à apparaître sur ChatGPT et les IA.\n"
        "Les RDV sont fournis et qualifiés — votre job : closer.\n\n"
        "✅ Aucune prospection de votre côté\n"
        "✅ Commission 18% + bonus\n"
        "✅ 100% télétravail\n\n"
        "Répondez « closing » si ça vous intéresse, je vous envoie les infos."
    ),
    "dm_suivi": (
        "Bonjour [Prénom],\n\n"
        "Merci pour votre intérêt ! Voici le lien pour candidater et voir tous les détails :\n"
        "👉 https://presence-ia.com/closer/recruit\n\n"
        "N'hésitez pas si vous avez des questions."
    ),
    "dm_individuel": "",
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

    # Vérifier si une image est déjà uploadée
    existing_image = next(_POST_IMAGE_DIR.glob(f"{_POST_IMAGE_STEM}.*"), None)
    img_html = ""
    if existing_image:
        img_html = (
            f'<img src="/admin/crm/closer-messages/image?token={token}" '
            f'style="max-width:100%;max-height:220px;border-radius:6px;border:1px solid #2a2a4e;margin-top:10px;display:block">'
        )

    def _ta(key, label, hint, rows=6):
        val = msgs.get(key, "").replace("&", "&amp;").replace("<", "&lt;")
        return (
            f'<div style="margin-bottom:24px">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">'
            f'  <label style="color:#9ca3af;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase">{label}</label>'
            f'  <div style="display:flex;gap:6px">'
            f'    <span id="saved_{key}" style="color:#10b981;font-size:10px;display:none;align-self:center">✓</span>'
            f'    <button type="button" onclick="copyField(\'{key}\')" '
            f'    style="padding:3px 10px;background:#1a1a2e;border:1px solid #2a2a4e;'
            f'    border-radius:4px;color:#9ca3af;font-size:10px;cursor:pointer">Copier</button>'
            f'  </div>'
            f'</div>'
            f'<p style="color:#555;font-size:11px;margin-bottom:6px">{hint}</p>'
            f'<textarea id="{key}" rows="{rows}" '
            f'oninput="autoSave(\'{key}\')" '
            f'style="width:100%;background:#1a1a2e;border:1px solid #2a2a4e;border-radius:6px;'
            f'padding:10px 12px;color:#e8e8f0;font-size:13px;font-family:inherit;'
            f'resize:vertical;outline:none;line-height:1.6">{val}</textarea>'
            f'</div>'
        )

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Messages recrutement</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
.wrap{{max-width:720px;margin:0 auto;padding:24px}}
.link-card{{display:flex;align-items:center;justify-content:space-between;
            background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;
            padding:12px 16px;margin-bottom:8px}}
.sep{{height:1px;background:#2a2a4e;margin:28px 0}}
.toast{{position:fixed;bottom:24px;right:24px;background:#2ecc71;color:#0f0f1a;
        padding:10px 20px;border-radius:6px;font-size:13px;font-weight:600;
        opacity:0;transition:opacity .3s;pointer-events:none}}
.toast.show{{opacity:1}}
textarea:focus{{border-color:#6366f1!important;outline:none}}
</style></head><body>
{admin_nav(token, "crm/closer-messages")}
<div class="wrap">

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:28px">
  <div>
    <h1 style="color:#fff;font-size:18px;margin-bottom:4px">Messages recrutement closers</h1>
    <p style="color:#555;font-size:12px">Post groupe → attendre "closing" → DM avec lien</p>
  </div>
  <a href="/admin/crm/closers?token={token}" style="color:#527FB3;font-size:12px;text-decoration:none">← Closers</a>
</div>

<!-- Liens -->
<p style="color:#9ca3af;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px">Liens à partager</p>
<div class="link-card">
  <div>
    <div style="color:#e8e8f0;font-size:12px;font-weight:600">Page présentation</div>
    <span style="color:#527FB3;font-size:11px;font-family:monospace">presence-ia.com/closer/</span>
  </div>
  <div style="display:flex;gap:8px">
    <a href="/closer/" target="_blank" style="padding:4px 10px;background:#6366f120;border:1px solid #6366f140;border-radius:4px;color:#6366f1;font-size:11px;text-decoration:none">Voir ↗</a>
    <button onclick="copyText('https://presence-ia.com/closer/')" style="padding:4px 10px;background:#1a1a2e;border:1px solid #2a2a4e;border-radius:4px;color:#9ca3af;font-size:11px;cursor:pointer">Copier</button>
  </div>
</div>
<div class="link-card">
  <div>
    <div style="color:#e8e8f0;font-size:12px;font-weight:600">Formulaire de candidature</div>
    <span style="color:#527FB3;font-size:11px;font-family:monospace">presence-ia.com/closer/recruit</span>
  </div>
  <div style="display:flex;gap:8px">
    <a href="/closer/recruit" target="_blank" style="padding:4px 10px;background:#6366f120;border:1px solid #6366f140;border-radius:4px;color:#6366f1;font-size:11px;text-decoration:none">Voir ↗</a>
    <button onclick="copyText('https://presence-ia.com/closer/recruit')" style="padding:4px 10px;background:#1a1a2e;border:1px solid #2a2a4e;border-radius:4px;color:#9ca3af;font-size:11px;cursor:pointer">Copier</button>
  </div>
</div>

<div class="sep"></div>

<!-- Image post -->
<div style="margin-bottom:28px">
  <label style="color:#9ca3af;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;display:block;margin-bottom:8px">Image du post</label>
  <p style="color:#555;font-size:11px;margin-bottom:10px">Image à joindre au post Facebook/LinkedIn. Formats acceptés : JPG, PNG, WebP.</p>
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <label style="padding:6px 16px;background:#1a1a2e;border:1px solid #2a2a4e;border-radius:6px;color:#9ca3af;font-size:12px;cursor:pointer">
      Uploader une image
      <input type="file" id="imgFile" accept="image/*" style="display:none" onchange="uploadImg(this)">
    </label>
    {'<a href="/admin/crm/closer-messages/image?token='+token+'" download style="padding:6px 16px;background:#6366f120;border:1px solid #6366f140;border-radius:6px;color:#6366f1;font-size:12px;text-decoration:none">Télécharger ↓</a>' if existing_image else ''}
    <span id="img-status" style="color:#10b981;font-size:11px;display:none"></span>
  </div>
  <div id="img-preview">
    {img_html}
  </div>
</div>

<div class="sep"></div>

<!-- Messages -->
{_ta("post_groupe",    "1 — Post groupe (LinkedIn / Facebook / Instagram)",
     "Message public. Les gens qui répondent « closing » reçoivent ensuite le DM.", rows=9)}
{_ta("dm_suivi",       "2 — DM de suivi (envoyé à chaque personne intéressée)",
     "Envoyé manuellement après qu'ils ont répondu. Le lien /closer/recruit doit être dedans.", rows=6)}
{_ta("dm_individuel",  "3 — DM individuel (optionnel — approche directe)",
     "Pour contacter quelqu'un spécifiquement, sans passer par le post.", rows=6)}

</div>
<div class="toast" id="toast"></div>
<script>
function copyText(t){{navigator.clipboard.writeText(t).then(()=>toast('Copié ✓'))}}
function copyField(id){{navigator.clipboard.writeText(document.getElementById(id).value).then(()=>toast('Copié ✓'))}}
function toast(m){{const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000)}}
var _timers={{}};
function autoSave(key){{
  clearTimeout(_timers[key]);
  _timers[key]=setTimeout(async function(){{
    const d={{}};['post_groupe','dm_suivi','dm_individuel'].forEach(k=>d[k]=document.getElementById(k).value);
    const r=await fetch('/admin/crm/closer-messages?token={token}',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(d)}});
    if(r.ok){{const s=document.getElementById('saved_'+key);s.style.display='inline';setTimeout(()=>s.style.display='none',1800);}}
  }},800);
}}
async function uploadImg(inp){{
  if(!inp.files[0]) return;
  const fd=new FormData(); fd.append('file',inp.files[0]);
  const r=await fetch('/admin/crm/closer-messages/image?token={token}',{{method:'POST',body:fd}});
  if(r.ok){{
    const s=document.getElementById('img-status'); s.textContent='Image uploadée ✓'; s.style.display='inline';
    setTimeout(()=>s.style.display='none',2500);
    const preview=document.getElementById('img-preview');
    const img=document.createElement('img');
    img.src=URL.createObjectURL(inp.files[0]);
    img.style.cssText='max-width:100%;max-height:220px;border-radius:6px;border:1px solid #2a2a4e;margin-top:10px;display:block';
    preview.innerHTML=''; preview.appendChild(img);
    // Ajouter bouton télécharger si absent
    if(!document.getElementById('dl-btn')){{
      const a=document.createElement('a');
      a.id='dl-btn'; a.href='/admin/crm/closer-messages/image?token={token}';
      a.download=''; a.textContent='Télécharger ↓';
      a.style.cssText='padding:6px 16px;background:#6366f120;border:1px solid #6366f140;border-radius:6px;color:#6366f1;font-size:12px;text-decoration:none;margin-left:10px';
      inp.parentElement.parentElement.querySelector('div').appendChild(a);
    }}
  }}
}}
</script>
</body></html>"""
    )


@router.post("/admin/crm/closer-messages")
async def save_closer_messages(request: Request):
    _check_token(request)
    data = await request.json()
    allowed = {"post_groupe", "dm_suivi", "dm_individuel"}
    try:
        _save_closer_messages({k: v for k, v in data.items() if k in allowed})
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


@router.post("/admin/crm/closer-messages/image")
async def upload_post_image(request: Request, file: UploadFile = File(...)):
    _check_token(request)
    import shutil, mimetypes
    ext = Path(file.filename).suffix.lower() or ".jpg"
    # Supprimer l'ancienne image (toutes extensions)
    for old in _POST_IMAGE_DIR.glob(f"{_POST_IMAGE_STEM}.*"):
        old.unlink(missing_ok=True)
    dest = _POST_IMAGE_DIR / f"{_POST_IMAGE_STEM}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return JSONResponse({"ok": True, "filename": dest.name})


@router.get("/admin/crm/closer-messages/image")
def download_post_image(request: Request):
    _check_token(request)
    for p in _POST_IMAGE_DIR.glob(f"{_POST_IMAGE_STEM}.*"):
        return FileResponse(str(p), filename=p.name)
    from fastapi import HTTPException
    raise HTTPException(404, "Aucune image uploadée")


# ─────────────────────────────────────────────────────────────────────────────
# Contenu portail closer (offre, script, objections, fiche RDV, commissions)
# ─────────────────────────────────────────────────────────────────────────────

_CONTENT_FILE = Path(__file__).parent.parent.parent.parent / "data" / "closer_content.json"

_DEFAULT_CONTENT: dict = {
    "offer_title":    "Présence IA — Visibilité locale sur les IA",
    "offer_price":    "497 €/an",
    "offer_pitch":    (
        "Présence IA permet aux artisans et PME locales d'apparaître quand leurs clients "
        "cherchent sur ChatGPT, Google AI ou les assistants vocaux.\n\n"
        "Ex : « Plombier urgence Lyon » → le prospect voit votre client dans la réponse de l'IA.\n\n"
        "Le service inclut : audit de présence IA, optimisation des fiches, "
        "création de contenu optimisé IA, suivi mensuel."
    ),
    "pitch_script":   (
        "1. ACCROCHE (30s)\n"
        "« Vous avez déjà cherché un artisan sur ChatGPT ? Vos clients, oui. »\n\n"
        "2. PROBLÈME (1 min)\n"
        "« Aujourd'hui 40% des recherches locales passent par une IA. "
        "Si vous n'y êtes pas, vous perdez des clients sans le savoir. »\n\n"
        "3. SOLUTION (1 min)\n"
        "« Présence IA vous positionne sur ces recherches. "
        "On optimise votre présence pour que les IA vous recommandent. »\n\n"
        "4. PREUVE (1 min)\n"
        "« Nos clients voient en moyenne 3x plus de mentions dans les réponses IA "
        "après 30 jours. »\n\n"
        "5. OFFRE + PRIX (30s)\n"
        "« C'est 497€/an. Soit 1,36€/jour pour être visible là où vos clients cherchent. »\n\n"
        "6. CLOSING\n"
        "« On commence quand ? Je vous envoie le contrat aujourd'hui. »"
    ),
    "objections":     (
        "« C'est trop cher »\n"
        "→ « C'est 1,36€/jour. Un client de plus par mois couvre largement l'investissement. »\n\n"
        "« Je ne sais pas si mes clients utilisent ChatGPT »\n"
        "→ « Vos clients ont moins de 40 ans ? Ils l'utilisent. Et même les plus âgés commencent. »\n\n"
        "« J'ai déjà un site »\n"
        "→ « Super, mais Google et les IA sont deux choses différentes. "
        "Un site bien référencé sur Google peut être invisible sur ChatGPT. »\n\n"
        "« Je vais y réfléchir »\n"
        "→ « Bien sûr. Qu'est-ce qui vous ferait pencher d'un côté ou de l'autre ? »\n\n"
        "« Je dois en parler à mon associé »\n"
        "→ « Bien sûr. On peut fixer un appel avec vous deux si vous voulez — "
        "ça vous évite de tout ré-expliquer. »"
    ),
    "rdv_guide":      (
        "AVANT LE CALL\n"
        "- Vérifier le nom, la ville, le secteur du prospect (dans votre portail)\n"
        "- Chercher rapidement sur ChatGPT : « [métier] [ville] » → noter s'il apparaît ou pas\n"
        "- Avoir le contrat prêt à envoyer\n\n"
        "PENDANT\n"
        "- Commencer par écouter : « Dites-moi, comment vous faites pour trouver de nouveaux clients en ce moment ? »\n"
        "- Ne pas pitcher avant d'avoir compris leur situation\n"
        "- Montrer l'exemple en direct (partager l'écran si possible)\n\n"
        "FIN DU CALL\n"
        "- Demander une décision claire : oui / non / quand\n"
        "- Si oui : envoyer le contrat dans la minute\n"
        "- Si non : noter la raison dans les notes du RDV"
    ),
    "commission_info": (
        "Taux : 18% du deal HT\n\n"
        "Commissions par offre :\n"
        "Audit Flash IA (97€) → 17€\n"
        "Kit Autonome (500€) → 90€\n"
        "Tout Inclus (3 500€) → 630€\n"
        "Domination IA Locale (9 000€) → 1 620€\n\n"
        "Paiement : versé le 10 du mois suivant la signature du client\n"
        "Condition : client non remboursé dans les 14 jours"
    ),
    # ── Bonus mensuel (Phase 2 — désactivé au lancement) ──────────────────────
    # Quand bonus_enabled=true : le top closer du mois reçoit +bonus_rate rétroactif
    # sur tous ses deals du mois → taux effectif 18%+4% = 22% → jusqu'à 1980€/deal
    "bonus_enabled":  False,
    "bonus_rate":     0.04,   # +4% rétroactif sur le mois pour le top closer
    "bonus_top_n":    1,      # nombre de closers qui reçoivent le bonus
}


def _load_closer_content() -> dict:
    try:
        if _CONTENT_FILE.exists():
            return json.loads(_CONTENT_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return dict(_DEFAULT_CONTENT)


def _save_closer_content(data: dict):
    _CONTENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONTENT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/admin/crm/closer-content", response_class=HTMLResponse)
def closer_content_page(request: Request):
    """Éditeur du contenu des pages closers (offre, script, objections, fiche RDV)."""
    token = _check_token(request)
    c = _load_closer_content()

    _FIELDS = [
        ("offer_title",    "Titre de l'offre",          1,
         "Affiché en haut du portail closer"),
        ("offer_price",    "Prix",                       1,
         "Ex : 497 €/an"),
        ("offer_pitch",    "Pitch de l'offre",           6,
         "Description de l'offre que le closer lit avant chaque RDV"),
        ("pitch_script",   "Script de vente",            14,
         "Les étapes du call, visibles dans la fiche RDV"),
        ("objections",     "Réponses aux objections",    12,
         "Affiché dans l'onglet Ressources du portail closer"),
        ("rdv_guide",      "Fiche RDV type",             10,
         "Aide-mémoire affiché dans chaque fiche de rendez-vous"),
        ("commission_info","Infos commissions",          6,
         "Affiché dans le portail closer, onglet Commissions"),
    ]

    def _row(key, label, rows, hint):
        val = c.get(key, "").replace("&", "&amp;").replace("<", "&lt;")
        if rows == 1:
            inp = (f'<input id="{key}" value="{val}" '
                   f'style="width:100%;background:#1a1a2e;border:1px solid #2a2a4e;border-radius:6px;'
                   f'padding:9px 12px;color:#e8e8f0;font-size:13px;outline:none">')
        else:
            inp = (f'<textarea id="{key}" rows="{rows}" '
                   f'style="width:100%;background:#1a1a2e;border:1px solid #2a2a4e;border-radius:6px;'
                   f'padding:10px 12px;color:#e8e8f0;font-size:13px;font-family:inherit;'
                   f'resize:vertical;outline:none;line-height:1.6">{val}</textarea>')
        return (
            f'<div style="margin-bottom:24px">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px">'
            f'  <label style="color:#9ca3af;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase">{label}</label>'
            f'  <span style="color:#444;font-size:10px">{hint}</span>'
            f'</div>'
            f'{inp}'
            f'</div>'
        )

    fields_html = "".join(_row(*f) for f in _FIELDS)
    field_ids   = [f[0] for f in _FIELDS]

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Contenu portail closer</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
input:focus,textarea:focus{{border-color:#6366f1!important;outline:none}}
.toast{{position:fixed;bottom:24px;right:24px;background:#2ecc71;color:#0f0f1a;
        padding:10px 20px;border-radius:6px;font-size:13px;font-weight:600;
        opacity:0;transition:opacity .3s;pointer-events:none}}
.toast.show{{opacity:1}}
</style></head><body>
{admin_nav(token, "crm/closer-content")}
<div style="max-width:820px;margin:0 auto;padding:24px">

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
  <h1 style="color:#fff;font-size:18px">Contenu portail closer</h1>
  <a href="/admin/crm/closers?token={token}" style="color:#527FB3;font-size:12px;text-decoration:none">← Closers</a>
</div>
<p style="color:#555;font-size:12px;margin-bottom:28px">
  Ce contenu est affiché dans le portail individuel de chaque closer (script, offre, objections, fiche RDV).
</p>

{fields_html}

<button onclick="save()" style="padding:10px 28px;background:#6366f1;border:none;border-radius:6px;
  color:#fff;font-size:13px;font-weight:600;cursor:pointer">Sauvegarder</button>

</div>
<div class="toast" id="toast"></div>
<script>
function toast(m){{const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000)}}
async function save(){{
  const ids={field_ids};
  const d={{}};ids.forEach(k=>{{const el=document.getElementById(k);if(el)d[k]=el.value}});
  const r=await fetch('/admin/crm/closer-content?token={token}',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(d)}});
  toast(r.ok?'Sauvegardé ✓':'Erreur !');
}}
</script>
</body></html>"""
    )


@router.post("/admin/crm/closer-content")
async def save_closer_content_route(request: Request):
    _check_token(request)
    data = await request.json()
    allowed = {"offer_title", "offer_price", "offer_pitch", "pitch_script",
               "objections", "rdv_guide", "commission_info",
               "bonus_enabled", "bonus_rate", "bonus_top_n"}
    try:
        payload = {}
        for k, v in data.items():
            if k not in allowed:
                continue
            if k == "bonus_enabled":
                payload[k] = bool(v)
            elif k in ("bonus_rate", "bonus_top_n"):
                payload[k] = float(v) if k == "bonus_rate" else int(v)
            else:
                payload[k] = v
        existing = _load_closer_content()
        existing.update(payload)
        _save_closer_content(existing)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


@router.get("/admin/crm/paiements", response_class=HTMLResponse)
def crm_paiements(request: Request):
    """Admin — demandes de paiement closers + génération SEPA XML."""
    token = _check_token(request)

    from src.api.routes.closer_public import _load_payment_requests, _save_payment_requests
    reqs = _load_payment_requests()

    pending = [r for r in reqs if r.get("status") == "pending"]
    paid    = [r for r in reqs if r.get("status") == "paid"]

    total_pending = sum(r.get("amount", 0) for r in pending)

    def _req_row(r, is_pending=True):
        iban_display = r.get("iban", "—")
        if len(iban_display) > 10:
            iban_display = iban_display[:4] + " •••• " + iban_display[-4:]
        actions = ""
        if is_pending:
            actions = (
                f'<button onclick="markPaid(\'{r["id"]}\')" '
                f'style="padding:4px 10px;background:#2ecc71;border:none;border-radius:4px;'
                f'color:#0f0f1a;font-size:10px;font-weight:600;cursor:pointer">Marquer payé</button>'
            )
        paid_note = f'<div style="color:#6b7280;font-size:10px">{r.get("paid_at","")[:10]}</div>' if r.get("paid_at") else ""
        return (
            f'<tr style="border-bottom:1px solid #1a1a2e">'
            f'<td style="padding:10px 14px;color:#fff;font-size:12px">{r.get("closer_name","—")}</td>'
            f'<td style="padding:10px 14px;color:#2ecc71;font-size:13px;font-weight:600">{r.get("amount",0):.2f}€</td>'
            f'<td style="padding:10px 14px;color:#9ca3af;font-size:11px;font-family:monospace">{iban_display}</td>'
            f'<td style="padding:10px 14px;color:#9ca3af;font-size:11px">{r.get("requested_at","")[:10]}</td>'
            f'<td style="padding:10px 14px">{paid_note}{actions}</td>'
            f'</tr>'
        )

    pending_rows = "".join(_req_row(r, True) for r in pending) or \
        '<tr><td colspan="5" style="padding:20px;color:#555;text-align:center">Aucune demande en attente</td></tr>'
    paid_rows = "".join(_req_row(r, False) for r in paid[-20:]) or \
        '<tr><td colspan="5" style="padding:20px;color:#555;text-align:center">Aucun paiement effectué</td></tr>'

    company_iban = os.getenv("COMPANY_IBAN", "")
    sepa_warning = "" if company_iban else (
        '<div style="background:#f59e0b15;border:1px solid #f59e0b40;border-radius:6px;'
        'padding:10px 14px;margin-bottom:20px;color:#f59e0b;font-size:12px">'
        '⚠ Variable d\'environnement <code>COMPANY_IBAN</code> non configurée — '
        'nécessaire pour générer le fichier SEPA.</div>'
    )

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Paiements Closers</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
table{{width:100%;border-collapse:collapse}}
th{{padding:8px 14px;text-align:left;color:#9ca3af;font-size:10px;font-weight:600;
   letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #2a2a4e}}
tr:hover{{background:#111127}}
</style></head><body>
{admin_nav(token, "crm/paiements")}
<div style="max-width:1000px;margin:0 auto;padding:24px">

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
  <div>
    <h1 style="color:#fff;font-size:18px;margin-bottom:4px">Paiements Closers</h1>
    <p style="color:#6b7280;font-size:12px">Virement SEPA — téléchargez le fichier XML pour import dans Boursorama.</p>
  </div>
  <a href="/admin/crm/closers?token={token}" style="color:#527FB3;font-size:12px;text-decoration:none">← Closers</a>
</div>

{sepa_warning}

<!-- Résumé -->
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:28px">
  <div style="background:#1a1a2e;border:1px solid #f59e0b40;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#f59e0b">{len(pending)}</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Demandes en attente</div>
  </div>
  <div style="background:#1a1a2e;border:1px solid #2ecc7140;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#2ecc71">{total_pending:.2f}€</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Total à verser</div>
  </div>
  <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#9ca3af">{len(paid)}</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Paiements effectués</div>
  </div>
</div>

<!-- Demandes en attente -->
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
  <h2 style="color:#fff;font-size:14px;font-weight:700">Demandes en attente ({len(pending)})</h2>
  {(
    f'<button onclick="downloadSepa()" style="padding:8px 18px;background:#6366f1;border:none;'
    f'border-radius:6px;color:#fff;font-size:12px;font-weight:600;cursor:pointer">'
    f'Générer fichier SEPA XML ↓</button>'
  ) if pending else ""}
</div>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden;margin-bottom:32px">
<table><thead><tr>
  <th>Closer</th><th>Montant</th><th>IBAN</th><th>Date demande</th><th>Action</th>
</tr></thead>
<tbody>{pending_rows}</tbody></table></div>

<!-- Historique -->
<h2 style="color:#9ca3af;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Historique paiements</h2>
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(82,127,179,.07)">
<table><thead><tr>
  <th>Closer</th><th>Montant</th><th>IBAN</th><th>Date demande</th><th>Versé le</th>
</tr></thead>
<tbody>{paid_rows}</tbody></table></div>

</div>
<script>
async function markPaid(id){{
  if(!confirm('Marquer ce paiement comme versé ?')) return;
  const r=await fetch('/api/admin/closers/payment/'+id+'/mark-paid?token={token}',{{method:'POST'}});
  const d=await r.json();
  if(d.ok) location.reload();
  else alert(d.error||'Erreur');
}}
async function downloadSepa(){{
  const a=document.createElement('a');
  a.href='/api/admin/closers/sepa-xml?token={token}';
  a.download='virements_closers.xml';
  a.click();
}}
</script>
</body></html>""")


@router.post("/api/admin/closers/payment/{req_id}/mark-paid")
async def mark_payment_paid(req_id: str, request: Request):
    """Marque une demande de paiement comme versée et met à jour CommissionDB."""
    _check_token(request)
    from datetime import datetime as _dt
    from src.api.routes.closer_public import _load_payment_requests, _save_payment_requests

    reqs = _load_payment_requests()
    req = next((r for r in reqs if r.get("id") == req_id), None)
    if not req:
        return JSONResponse({"ok": False, "error": "Demande introuvable"})

    req["status"] = "paid"
    req["paid_at"] = _dt.utcnow().isoformat()
    _save_payment_requests(reqs)

    # Mettre à jour CommissionDB
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import CommissionDB
        with MktSession() as mdb:
            comms = mdb.query(CommissionDB).filter_by(
                project_id="presence-ia", closer_id=req.get("closer_id", "")
            ).all()
            for c in comms:
                if getattr(c, "status", "") != "paid":
                    c.status = "paid"
                    c.paid_at = _dt.utcnow()
            mdb.commit()
    except Exception:
        pass

    return JSONResponse({"ok": True})


@router.get("/api/admin/closers/sepa-xml")
def generate_sepa_xml(request: Request):
    """Génère un fichier SEPA pain.001.001.03 pour tous les paiements en attente."""
    from fastapi import HTTPException
    from fastapi.responses import Response
    _check_token(request)

    from src.api.routes.closer_public import _load_payment_requests
    reqs = [r for r in _load_payment_requests() if r.get("status") == "pending"]
    if not reqs:
        raise HTTPException(400, "Aucune demande en attente")

    company_iban = os.getenv("COMPANY_IBAN", "")
    company_bic  = os.getenv("COMPANY_BIC", "BOUSFRPPXXX")
    company_name = os.getenv("COMPANY_NAME", "PRESENCE IA")
    if not company_iban:
        raise HTTPException(400, "Variable COMPANY_IBAN non configurée")

    from datetime import datetime as _dt, date as _date, timedelta as _td
    now       = _dt.utcnow()
    exec_date = (_date.today() + _td(days=2)).isoformat()
    msg_id    = f"PRESIAI-{now.strftime('%Y%m%d%H%M%S')}"
    total     = sum(r.get("amount", 0) for r in reqs)

    def _tx(r, idx):
        name  = r.get("closer_name", "Closer")[:70]
        iban  = r.get("iban", "").replace(" ", "")
        amt   = f'{r.get("amount", 0):.2f}'
        end2end = f"COMM-{r['id'][:12].upper()}"
        ref   = f"Commission Closer Presence IA {now.strftime('%m/%Y')}"[:140]
        return (
            f'      <CdtTrfTxInf>'
            f'<PmtId><EndToEndId>{end2end}</EndToEndId></PmtId>'
            f'<Amt><InstdAmt Ccy="EUR">{amt}</InstdAmt></Amt>'
            f'<Cdtr><Nm>{name}</Nm></Cdtr>'
            f'<CdtrAcct><Id><IBAN>{iban}</IBAN></Id></CdtrAcct>'
            f'<RmtInf><Ustrd>{ref}</Ustrd></RmtInf>'
            f'</CdtTrfTxInf>'
        )

    transactions = "\n".join(_tx(r, i) for i, r in enumerate(reqs))
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>{msg_id}</MsgId>
      <CreDtTm>{now.strftime('%Y-%m-%dT%H:%M:%S')}</CreDtTm>
      <NbOfTxs>{len(reqs)}</NbOfTxs>
      <CtrlSum>{total:.2f}</CtrlSum>
      <InitgPty><Nm>{company_name}</Nm></InitgPty>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>{msg_id}-001</PmtInfId>
      <PmtMtd>TRF</PmtMtd>
      <NbOfTxs>{len(reqs)}</NbOfTxs>
      <CtrlSum>{total:.2f}</CtrlSum>
      <PmtTpInf><SvcLvl><Cd>SEPA</Cd></SvcLvl></PmtTpInf>
      <ReqdExctnDt>{exec_date}</ReqdExctnDt>
      <Dbtr><Nm>{company_name}</Nm></Dbtr>
      <DbtrAcct><Id><IBAN>{company_iban}</IBAN></Id></DbtrAcct>
      <DbtrAgt><FinInstnId><BIC>{company_bic}</BIC></FinInstnId></DbtrAgt>
{transactions}
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>"""

    filename = f"virements_closers_{now.strftime('%Y%m%d')}.xml"
    return Response(
        content=xml.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/admin/closers/apply-bonus")
async def apply_monthly_bonus(request: Request):
    """Phase 2 — calcule et enregistre la prime mensuelle du top closer.
    Appel : POST /api/admin/closers/apply-bonus?month=2026-04&token=XXX
    Retourne le détail du calcul sans modifier la DB si dry_run=true."""
    _check_token(request)
    from datetime import datetime as _dt
    import calendar

    params = request.query_params
    month_str = params.get("month", _dt.utcnow().strftime("%Y-%m"))
    dry_run   = params.get("dry_run", "false").lower() == "true"

    content = _load_closer_content()
    if not content.get("bonus_enabled"):
        return JSONResponse({"ok": False, "error": "bonus_enabled=false — activez d'abord le bonus dans les paramètres"})

    bonus_rate = float(content.get("bonus_rate", 0.04))
    top_n      = int(content.get("bonus_top_n", 1))

    try:
        year, month = int(month_str[:4]), int(month_str[5:7])
        date_from = _dt(year, month, 1)
        date_to   = _dt(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)
    except Exception:
        return JSONResponse({"ok": False, "error": f"Format month invalide : {month_str} (attendu YYYY-MM)"})

    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import MeetingDB, CloserDB
        with MktSession() as mdb:
            meetings = (
                mdb.query(MeetingDB)
                .filter(MeetingDB.status == "completed")
                .filter(MeetingDB.scheduled_at.between(date_from, date_to))
                .all()
            )
            if not meetings:
                return JSONResponse({"ok": True, "month": month_str, "bonuses": [],
                                     "note": "Aucun deal signé ce mois"})

            # Agréger par closer
            from collections import defaultdict
            by_closer: dict = defaultdict(lambda: {"deals": 0, "ca": 0.0, "closer_id": ""})
            for m in meetings:
                cid = m.closer_id or "inconnu"
                by_closer[cid]["closer_id"] = cid
                by_closer[cid]["deals"] += 1
                by_closer[cid]["ca"] += float(m.deal_value or 0)

            ranked = sorted(by_closer.values(), key=lambda x: x["ca"], reverse=True)
            top_closers = ranked[:top_n]

            bonuses = []
            for c in top_closers:
                prime = round(c["ca"] * bonus_rate, 2)
                bonuses.append({
                    "closer_id":   c["closer_id"],
                    "deals":       c["deals"],
                    "ca":          c["ca"],
                    "bonus_rate":  f"+{bonus_rate*100:.0f}%",
                    "prime":       prime,
                    "taux_effectif": f"{(0.18 + bonus_rate)*100:.0f}%",
                })

            if not dry_run:
                # Stocker dans un fichier JSON (pas de table CommissionDB dédiée pour l'instant)
                bonus_log_path = Path(__file__).parent.parent.parent.parent / "data" / "bonus_log.json"
                log = []
                if bonus_log_path.exists():
                    try:
                        log = json.loads(bonus_log_path.read_text())
                    except Exception:
                        pass
                for b in bonuses:
                    log.append({"month": month_str, **b})
                bonus_log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2))

            return JSONResponse({
                "ok": True, "month": month_str, "dry_run": dry_run,
                "bonuses": bonuses,
                "note": "dry_run=true — rien n'a été enregistré" if dry_run else "Bonus enregistrés dans data/bonus_log.json"
            })
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# Admin — Créneaux RDV
# ─────────────────────────────────────────────────────────────────────────────

def _gcal_sync(project_id: str) -> tuple[int, str]:
    """
    Synchronise les créneaux depuis Google Calendar.
    Crée un SlotDB de 20 min par event trouvé sur les 14 prochains jours.
    Variables d'env requises (OAuth2) :
      GOOGLE_CALENDAR_ID           ex: nathalie@presence-ia.com
      GOOGLE_CALENDAR_CLIENT_ID
      GOOGLE_CALENDAR_CLIENT_SECRET
      GOOGLE_CALENDAR_REFRESH_TOKEN
    Retourne (nb créneaux créés/mis à jour, message).
    """
    import datetime as _dt
    cal_id        = os.getenv("GOOGLE_CALENDAR_ID", "")
    client_id     = os.getenv("GOOGLE_CALENDAR_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET", "")
    refresh_token = os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN", "")
    if not cal_id or not client_id or not client_secret or not refresh_token:
        return 0, "Variables GOOGLE_CALENDAR_ID / CLIENT_ID / CLIENT_SECRET / REFRESH_TOKEN non configurées."

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GRequest
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        creds.refresh(GRequest())
        service = build("calendar", "v3", credentials=creds)

        now       = _dt.datetime.utcnow()
        time_min  = now.isoformat() + "Z"
        time_max  = (now + _dt.timedelta(days=14)).isoformat() + "Z"

        result = service.events().list(
            calendarId=cal_id,
            timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy="startTime",
            maxResults=500,
        ).execute()
        events = result.get("items", [])
    except Exception as e:
        return 0, f"Erreur Google Calendar : {e}"

    from marketing_module.database import SessionLocal as MktSession, db_create_slot, db_get_slot
    from marketing_module.models import SlotDB, SlotStatus

    created = 0
    with MktSession() as mdb:
        for ev in events:
            start_raw = ev.get("start", {}).get("dateTime")
            if not start_raw:
                continue
            try:
                import datetime as _dt2
                starts_at = _dt2.datetime.fromisoformat(start_raw.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                continue

            event_id = ev.get("id", "")

            # Découper en tranches de 20 min si l'event est plus long
            end_raw = ev.get("end", {}).get("dateTime", start_raw)
            try:
                ends_ev = _dt2.datetime.fromisoformat(end_raw.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                ends_ev = starts_at + _dt2.timedelta(minutes=20)

            slot_start = starts_at
            slice_idx  = 0
            while slot_start < ends_ev:
                slot_end = slot_start + _dt2.timedelta(minutes=20)
                slice_id = f"{event_id}-{slice_idx}"

                existing = mdb.query(SlotDB).filter_by(
                    project_id=project_id, calendar_event_id=slice_id
                ).first()
                if not existing:
                    db_create_slot(mdb, {
                        "project_id":        project_id,
                        "starts_at":         slot_start,
                        "ends_at":           slot_end,
                        "status":            SlotStatus.available,
                        "calendar_event_id": slice_id,
                        "notes":             ev.get("summary", ""),
                    })
                    created += 1
                slot_start = slot_end
                slice_idx  += 1

    return created, f"{created} créneau(x) importé(s) depuis Google Calendar."


@router.get("/admin/crm/slots", response_class=HTMLResponse)
def admin_slots(request: Request):
    token = _check_token(request)
    import datetime as _dt

    from marketing_module.database import SessionLocal as MktSession, db_list_slots, db_list_closers
    from marketing_module.models import SlotStatus

    PROJECT_ID = "presence-ia"
    now  = _dt.datetime.utcnow()
    week = now + _dt.timedelta(days=14)

    slots   = []
    closers = {}
    try:
        with MktSession() as mdb:
            slots   = db_list_slots(mdb, PROJECT_ID, from_dt=now, to_dt=week)
            for c in db_list_closers(mdb, PROJECT_ID, active_only=False):
                closers[c.id] = c.name
    except Exception:
        pass

    STATUS_COLORS = {
        "available": ("#2ecc71", "Disponible"),
        "booked":    ("#8b5cf6", "Réservé"),
        "claimed":   ("#6366f1", "Pris"),
        "completed": ("#9ca3af", "Terminé"),
        "cancelled": ("#e94560", "Annulé"),
    }

    rows = ""
    for s in slots:
        color, label = STATUS_COLORS.get(s.status, ("#555", s.status))
        closer_name = closers.get(s.closer_id, "—") if s.closer_id else "—"
        rows += (
            f'<tr style="border-bottom:1px solid #1a1a2e">'
            f'<td style="padding:8px 12px;color:#fff;font-size:12px">{s.starts_at.strftime("%d/%m %H:%M")}</td>'
            f'<td style="padding:8px 12px;color:#9ca3af;font-size:12px">{s.ends_at.strftime("%H:%M")}</td>'
            f'<td style="padding:8px 12px"><span style="background:{color}20;color:{color};'
            f'font-size:10px;font-weight:600;padding:2px 7px;border-radius:10px">{label}</span></td>'
            f'<td style="padding:8px 12px;color:#9ca3af;font-size:12px">{closer_name}</td>'
            f'<td style="padding:8px 12px;color:#555;font-size:11px">{s.notes or ""}</td>'
            f'<td style="padding:8px 12px">'
            f'<button onclick="deleteSlot(\'{s.id}\')" '
            f'style="background:#e9456020;color:#e94560;border:none;padding:3px 8px;'
            f'border-radius:4px;font-size:10px;cursor:pointer">Suppr.</button></td>'
            f'</tr>'
        )

    if not rows:
        rows = '<tr><td colspan="6" style="padding:30px;text-align:center;color:#555">Aucun créneau sur les 14 prochains jours</td></tr>'

    gcal_configured = bool(os.getenv("GOOGLE_CALENDAR_ID") and os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN"))
    gcal_badge = (
        f'<span style="background:#2ecc7120;color:#2ecc71;font-size:10px;padding:2px 7px;border-radius:10px">Google Calendar configuré</span>'
        if gcal_configured else
        f'<span style="background:#e9456020;color:#e94560;font-size:10px;padding:2px 7px;border-radius:10px">Google Calendar non configuré (GOOGLE_CALENDAR_ID + GOOGLE_CALENDAR_REFRESH_TOKEN requis)</span>'
    )

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Créneaux RDV — Admin</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
table{{width:100%;border-collapse:collapse}}
tr:hover{{background:#111127}}
input{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:4px;padding:6px 10px;
       color:#e8e8f0;font-size:12px;outline:none}}
input:focus{{border-color:#6366f1}}
</style></head><body>
{admin_nav(token, "crm/slots")}
<div style="max-width:900px;margin:0 auto;padding:24px">

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:8px">
  <h1 style="color:#fff;font-size:18px">Créneaux RDV</h1>
  <div style="display:flex;gap:8px;flex-wrap:wrap">
    <button onclick="syncGcal()" style="background:#1a1a2e;border:1px solid #2a2a4e;
      color:#9ca3af;padding:7px 14px;border-radius:6px;font-size:12px;cursor:pointer">
      ↻ Sync Google Calendar
    </button>
    <button onclick="showAddForm()" style="background:#6366f1;border:none;
      color:#fff;padding:7px 14px;border-radius:6px;font-size:12px;cursor:pointer">
      + Ajouter manuellement
    </button>
  </div>
</div>
<p style="color:#555;font-size:12px;margin-bottom:8px">14 prochains jours — {len(slots)} créneau(x)</p>
<div style="margin-bottom:20px">{gcal_badge}</div>

<!-- Formulaire ajout manuel -->
<div id="add-form" style="display:none;background:#1a1a2e;border:1px solid #2a2a4e;
  border-radius:8px;padding:16px;margin-bottom:20px">
  <p style="color:#9ca3af;font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Nouveau créneau</p>
  <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end">
    <div>
      <label style="color:#6b7280;font-size:10px;display:block;margin-bottom:4px">Date/Heure début</label>
      <input type="datetime-local" id="new-starts" style="width:180px">
    </div>
    <div>
      <label style="color:#6b7280;font-size:10px;display:block;margin-bottom:4px">Note (optionnel)</label>
      <input type="text" id="new-notes" placeholder="ex: Créneau dispo" style="width:200px">
    </div>
    <button onclick="addSlot()" style="background:#6366f1;border:none;color:#fff;
      padding:7px 16px;border-radius:6px;font-size:12px;cursor:pointer">Créer</button>
    <button onclick="document.getElementById('add-form').style.display='none'"
      style="background:#1a1a2e;border:1px solid #2a2a4e;color:#9ca3af;padding:7px 12px;
      border-radius:6px;font-size:12px;cursor:pointer">Annuler</button>
  </div>
</div>

<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(82,127,179,.07)">
<table>
<thead><tr>
  <th style="padding:8px 12px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Début</th>
  <th style="padding:8px 12px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Fin</th>
  <th style="padding:8px 12px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Statut</th>
  <th style="padding:8px 12px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Closer</th>
  <th style="padding:8px 12px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Note</th>
  <th style="padding:8px 12px;border-bottom:1px solid #2a2a4e"></th>
</tr></thead>
<tbody id="slots-body">{rows}</tbody>
</table>
</div>

<div id="toast" style="position:fixed;bottom:24px;right:24px;background:#2ecc71;color:#0f0f1a;
  padding:10px 20px;border-radius:6px;font-size:13px;font-weight:600;opacity:0;
  transition:opacity .3s;pointer-events:none"></div>

</div>
<script>
function toast(m,err){{
  const t=document.getElementById('toast');
  t.textContent=m;t.style.background=err?'#e94560':'#2ecc71';
  t.style.opacity=1;setTimeout(()=>t.style.opacity=0,2500);
}}
function showAddForm(){{document.getElementById('add-form').style.display='block'}}

async function addSlot(){{
  const starts=document.getElementById('new-starts').value;
  const notes=document.getElementById('new-notes').value;
  if(!starts){{toast('Indiquez une date',true);return}}
  const r=await fetch('/admin/crm/slots?token={token}',{{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{starts_at:starts,notes:notes}})
  }});
  const d=await r.json();
  if(d.ok){{toast('Créneau créé ✓');setTimeout(()=>location.reload(),800)}}
  else toast('Erreur : '+(d.error||'?'),true);
}}

async function deleteSlot(id){{
  if(!confirm('Supprimer ce créneau ?'))return;
  const r=await fetch('/admin/crm/slots/'+id+'?token={token}',{{method:'DELETE'}});
  const d=await r.json();
  if(d.ok){{toast('Supprimé ✓');setTimeout(()=>location.reload(),600)}}
  else toast('Erreur',true);
}}

async function syncGcal(){{
  const btn=event.target;btn.textContent='Sync en cours…';btn.disabled=true;
  const r=await fetch('/admin/crm/slots/sync?token={token}',{{method:'POST'}});
  const d=await r.json();
  btn.textContent='↻ Sync Google Calendar';btn.disabled=false;
  toast(d.message||(d.ok?'Sync OK':'Erreur'),!d.ok);
  if(d.ok&&d.created>0)setTimeout(()=>location.reload(),1200);
}}
</script>
</body></html>""")


@router.post("/admin/crm/slots", response_class=JSONResponse)
async def admin_create_slot(request: Request):
    token = _check_token(request)
    import datetime as _dt
    try:
        data = await request.json()
        starts_raw = data.get("starts_at", "")
        notes = data.get("notes", "") or None

        starts_at = _dt.datetime.fromisoformat(starts_raw)
        ends_at   = starts_at + _dt.timedelta(minutes=20)

        from marketing_module.database import SessionLocal as MktSession, db_create_slot
        from marketing_module.models import SlotStatus
        with MktSession() as mdb:
            slot = db_create_slot(mdb, {
                "project_id": "presence-ia",
                "starts_at":  starts_at,
                "ends_at":    ends_at,
                "status":     SlotStatus.available,
                "notes":      notes,
            })
        return JSONResponse({"ok": True, "id": slot.id})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@router.delete("/admin/crm/slots/{slot_id}", response_class=JSONResponse)
def admin_delete_slot(slot_id: str, request: Request):
    _check_token(request)
    try:
        from marketing_module.database import SessionLocal as MktSession, db_delete_slot
        with MktSession() as mdb:
            ok = db_delete_slot(mdb, slot_id)
        return JSONResponse({"ok": ok})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


@router.post("/admin/crm/slots/sync", response_class=JSONResponse)
def admin_sync_gcal(request: Request):
    _check_token(request)
    created, message = _gcal_sync("presence-ia")
    return JSONResponse({"ok": True, "created": created, "message": message})
