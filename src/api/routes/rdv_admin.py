"""
RDV — page fusionnée : Créneaux (agenda) + Résultats (outcomes closers).

GET /admin/rdv  → vue combinée
POST/DELETE /admin/rdv/slots/* → gestion créneaux (proxy vers crm_admin)
POST /admin/rdv/meetings/{id}  → mise à jour résultat
POST /admin/rdv/sync           → sync Calendly / Google Calendar
"""
import os
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from ._nav import admin_nav

log    = logging.getLogger(__name__)
router = APIRouter(tags=["RDV"])

PROJECT_ID = "presence-ia"


def _check_token(request: Request) -> str:
    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    return token


# ── Page principale ────────────────────────────────────────────────────────────

@router.get("/admin/rdv", response_class=HTMLResponse)
def rdv_page(request: Request):
    token = _check_token(request)

    slots, closers_map, meetings, closers_list = [], {}, [], []
    try:
        from marketing_module.database import SessionLocal as MktSession, db_list_slots, db_list_closers
        from marketing_module.models import SlotStatus
        now  = datetime.utcnow()
        week = now + timedelta(days=14)
        with MktSession() as mdb:
            slots       = db_list_slots(mdb, PROJECT_ID, from_dt=now, to_dt=week)
            closers_list = db_list_closers(mdb, PROJECT_ID, active_only=False)
            closers_map  = {c.id: c.name for c in closers_list}
            from marketing_module.models import MeetingDB
            meetings = (mdb.query(MeetingDB)
                        .filter_by(project_id=PROJECT_ID)
                        .order_by(MeetingDB.scheduled_at.desc())
                        .limit(50).all())
            # détacher
            meetings = [(m.id, m.scheduled_at, m.status,
                         m.deal_value, m.outcome, m.closer_id,
                         m.notes, m.calendly_event_id) for m in meetings]
    except Exception as e:
        log.warning("rdv_page load: %s", e)

    STATUS_COLORS = {
        "available": ("#2ecc71", "Disponible"),
        "booked":    ("#8b5cf6", "Réservé"),
        "claimed":   ("#6366f1", "Pris"),
        "completed": ("#9ca3af", "Terminé"),
        "cancelled": ("#e94560", "Annulé"),
    }

    # ── Créneaux ──
    slot_rows = ""
    for s in slots:
        color, label = STATUS_COLORS.get(s.status, ("#555", s.status))
        cn = closers_map.get(s.closer_id, "—") if s.closer_id else "—"
        slot_rows += (
            f'<tr><td>{s.starts_at.strftime("%d/%m %H:%M")}</td>'
            f'<td>{s.ends_at.strftime("%H:%M")}</td>'
            f'<td><span style="background:{color}20;color:{color};font-size:10px;'
            f'font-weight:600;padding:2px 7px;border-radius:10px">{label}</span></td>'
            f'<td>{cn}</td><td style="color:#555;font-size:11px">{s.notes or ""}</td>'
            f'<td><button onclick="deleteSlot(\'{s.id}\')" '
            f'style="background:#e9456020;color:#e94560;border:none;padding:3px 8px;'
            f'border-radius:4px;font-size:10px;cursor:pointer">Suppr.</button></td></tr>'
        )
    if not slot_rows:
        slot_rows = '<tr><td colspan="6" style="padding:24px;text-align:center;color:#555">Aucun créneau sur les 14 prochains jours</td></tr>'

    gcal_ok = bool(os.getenv("GOOGLE_CALENDAR_ID") and os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN"))
    gcal_badge = (
        '<span style="background:#2ecc7120;color:#2ecc71;font-size:10px;padding:2px 7px;border-radius:10px">Google Calendar connecté</span>'
        if gcal_ok else
        '<span style="background:#f59e0b20;color:#f59e0b;font-size:10px;padding:2px 7px;border-radius:10px">Sync auto Calendly active · Google Calendar non configuré</span>'
    )

    # ── Résultats meetings ──
    closer_options = "".join(f'<option value="{c.id}">{c.name}</option>' for c in closers_list)

    def _m_badge(status, deal_value):
        if (deal_value or 0) > 0:
            return '<span style="background:#a855f720;color:#a855f7;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700">VENTE</span>'
        if status == "completed":
            return '<span style="background:#10b98120;color:#10b981;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700">EFFECTUÉ</span>'
        return '<span style="background:#f59e0b20;color:#f59e0b;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700">CONFIRMÉ</span>'

    mtg_rows = ""
    for mid, sched_at, status, deal_value, outcome, closer_id, notes, cal_id in meetings:
        sched = sched_at.strftime("%d/%m/%Y %H:%M") if sched_at else "—"
        cn    = closers_map.get(closer_id, "—") if closer_id else "—"
        deal  = f'{deal_value:,.0f} €'.replace(",", " ") if (deal_value or 0) > 0 else ""
        safe_outcome = (outcome or "").replace("'", "")
        mtg_rows += (
            f'<tr>'
            f'<td style="padding:8px 10px;font-size:12px">{sched}</td>'
            f'<td style="padding:8px 10px;font-size:11px;color:#6b7280">{notes or (cal_id or "")[:12]}</td>'
            f'<td style="padding:8px 10px">{_m_badge(status, deal_value)}</td>'
            f'<td style="padding:8px 10px;font-size:12px">{cn}</td>'
            f'<td style="padding:8px 10px;font-size:12px;color:#a855f7;font-weight:700">{deal}</td>'
            f'<td style="padding:8px 10px;font-size:11px;color:#6b7280">{(outcome or "")[:50]}</td>'
            f'<td style="padding:8px 6px;text-align:center">'
            f'<button onclick="openEdit(\'{mid}\',\'{status}\',\'{deal_value or ""}\',\'{safe_outcome}\')"'
            f' style="background:#2a2a4e;color:#ccc;border:1px solid #3a3a5e;border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer">'
            f'Modifier</button></td></tr>'
        )
    if not mtg_rows:
        mtg_rows = '<tr><td colspan="7" style="padding:24px;text-align:center;color:#555">Aucun RDV enregistré</td></tr>'

    th = 'style="padding:8px 10px;text-align:left;color:#9ca3af;font-size:10px;text-transform:uppercase;letter-spacing:.8px;border-bottom:1px solid #2a2a4e"'
    th2 = 'style="padding:8px 12px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;border-bottom:1px solid #2a2a4e"'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RDV — PRESENCE_IA Admin</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
table{{width:100%;border-collapse:collapse}}
tr:hover td{{background:rgba(255,255,255,.02)}}
h2{{color:#fff;font-size:15px;margin-bottom:16px}}
.panel{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden;margin-bottom:32px}}
.panel-head{{padding:14px 16px;border-bottom:1px solid #2a2a4e;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}}
.btn{{border:none;border-radius:6px;padding:7px 14px;font-size:12px;cursor:pointer;font-weight:600}}
.btn-primary{{background:#6366f1;color:#fff}}
.btn-ghost{{background:#1a1a2e;border:1px solid #2a2a4e;color:#9ca3af}}
input,select,textarea{{width:100%;background:#0f0f1a;border:1px solid #3a3a5e;color:#e8e8f0;border-radius:6px;padding:8px 10px;font-size:13px}}
label{{display:block;color:#9ca3af;font-size:11px;margin-bottom:4px;margin-top:12px}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100;align-items:center;justify-content:center}}
.modal.open{{display:flex}}
.modal-box{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:28px;width:420px;max-width:95vw}}
#add-form{{display:none;padding:16px;border-top:1px solid #2a2a4e}}
</style></head><body>
{admin_nav(token, "rdv")}
<div style="max-width:1000px;margin:0 auto;padding:24px">
<h1 style="color:#fff;font-size:18px;margin-bottom:24px">📅 RDV</h1>

<!-- ── Créneaux ── -->
<div class="panel">
  <div class="panel-head">
    <div>
      <h2 style="margin:0">Agenda — {len(slots)} créneau(x) sur 14 jours</h2>
      <div style="margin-top:6px">{gcal_badge}</div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn btn-ghost" onclick="syncCal()">↻ Sync Calendly</button>
      <button class="btn btn-primary" onclick="document.getElementById('add-form').style.display='block'">+ Ajouter</button>
    </div>
  </div>
  <div id="add-form">
    <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end">
      <div><label>Date/Heure début</label><input type="datetime-local" id="new-starts" style="width:180px"></div>
      <div><label>Note (optionnel)</label><input type="text" id="new-notes" placeholder="ex: Créneau dispo" style="width:200px"></div>
      <button class="btn btn-primary" onclick="addSlot()">Créer</button>
      <button class="btn btn-ghost" onclick="document.getElementById('add-form').style.display='none'">Annuler</button>
    </div>
  </div>
  <table>
    <thead><tr>
      <th {th2}>Début</th><th {th2}>Fin</th><th {th2}>Statut</th>
      <th {th2}>Closer</th><th {th2}>Note</th><th {th2}></th>
    </tr></thead>
    <tbody>{slot_rows}</tbody>
  </table>
</div>

<!-- ── Résultats ── -->
<div class="panel">
  <div class="panel-head">
    <h2 style="margin:0">Résultats des RDV</h2>
  </div>
  <table>
    <thead><tr>
      <th {th}>Date RDV</th><th {th}>Prospect</th><th {th}>Statut</th>
      <th {th}>Closer</th><th {th}>Montant</th><th {th}>Notes</th><th {th}></th>
    </tr></thead>
    <tbody>{mtg_rows}</tbody>
  </table>
</div>

</div>

<!-- Modal édition résultat -->
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
  <button onclick="saveEdit()"
    style="background:#a855f7;color:#fff;border:none;border-radius:8px;padding:10px 24px;font-weight:700;cursor:pointer;margin-top:18px;width:100%">
    Enregistrer
  </button>
  <button onclick="document.getElementById('editModal').classList.remove('open')"
    style="background:#2a2a4e;color:#ccc;border:none;border-radius:8px;padding:8px 16px;cursor:pointer;font-size:12px;margin-top:8px;width:100%">
    Annuler
  </button>
</div>
</div>

<div id="toast" style="position:fixed;bottom:24px;right:24px;background:#2ecc71;color:#0f0f1a;
  padding:10px 20px;border-radius:6px;font-size:13px;font-weight:600;opacity:0;
  transition:opacity .3s;pointer-events:none"></div>

<script>
const TOKEN = '{token}';
function toast(m,err){{
  const t=document.getElementById('toast');
  t.textContent=m;t.style.background=err?'#e94560':'#2ecc71';
  t.style.opacity=1;setTimeout(()=>t.style.opacity=0,2500);
}}
async function addSlot(){{
  const starts=document.getElementById('new-starts').value;
  const notes=document.getElementById('new-notes').value;
  if(!starts){{toast('Indiquez une date',true);return}}
  const r=await fetch('/admin/crm/slots?token='+TOKEN,{{
    method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{starts_at:starts,notes:notes}})
  }});
  const d=await r.json();
  if(d.ok){{toast('Créneau créé ✓');setTimeout(()=>location.reload(),800)}}
  else toast('Erreur: '+(d.error||'?'),true);
}}
async function deleteSlot(id){{
  if(!confirm('Supprimer ce créneau ?'))return;
  const r=await fetch('/admin/crm/slots/'+id+'?token='+TOKEN,{{method:'DELETE'}});
  const d=await r.json();
  if(d.ok){{toast('Supprimé ✓');setTimeout(()=>location.reload(),600)}}
  else toast('Erreur',true);
}}
async function syncCal(){{
  const btn=event.target;btn.textContent='Sync…';btn.disabled=true;
  const r=await fetch('/admin/crm/slots/sync?token='+TOKEN,{{method:'POST'}});
  const d=await r.json();
  btn.textContent='↻ Sync Calendly';btn.disabled=false;
  toast(d.message||(d.ok?'Sync OK':'Erreur'),!d.ok);
  if(d.ok&&d.created>0)setTimeout(()=>location.reload(),1200);
}}
function openEdit(mid,status,deal,notes){{
  document.getElementById('edit_mid').value=mid;
  document.getElementById('edit_status').value=status||'scheduled';
  document.getElementById('edit_deal').value=deal||'';
  document.getElementById('edit_notes').value=notes||'';
  document.getElementById('editModal').classList.add('open');
}}
async function saveEdit(){{
  const mid=document.getElementById('edit_mid').value;
  const body={{
    status:    document.getElementById('edit_status').value,
    closer_id: document.getElementById('edit_closer').value||null,
    deal_value:parseFloat(document.getElementById('edit_deal').value)||null,
    outcome:   document.getElementById('edit_notes').value||null,
  }};
  const r=await fetch('/admin/closers/'+mid+'?token='+TOKEN,{{
    method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)
  }});
  if(r.ok){{document.getElementById('editModal').classList.remove('open');toast('Enregistré ✓');setTimeout(()=>location.reload(),800)}}
  else toast('Erreur lors de la sauvegarde',true);
}}
</script>
</body></html>""")
