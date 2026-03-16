"""Admin — onglet CONTACTS (SUSPECT/PROSPECT/CLIENT)."""
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_list_contacts, db_get_contact, db_create_contact, db_update_contact, db_delete_contact
from ...models import ContactDB
from ._nav import admin_nav

router = APIRouter(tags=["Admin Contacts"])


def _check_token(request: Request):
    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    return token


def _offer_labels(db: Session) -> dict:
    """Labels des offres lus depuis offers_module (pas hardcodés)."""
    from offers_module.database import db_list_offers
    offers = db_list_offers(db)
    return {o.name: o.name for o in offers} if offers else {}


def _prof_options(db) -> str:
    """Professions avec mots_cles_sirene — prêtes pour leads runner."""
    from ...models import ProfessionDB
    profs = db.query(ProfessionDB).filter(
        ProfessionDB.mots_cles_sirene.isnot(None)
    ).order_by(ProfessionDB.label).all()
    if not profs:
        return '<option value="">Aucune profession prête</option>'
    return "".join(f'<option value="{p.id}">{p.label}</option>' for p in profs)


STATUS_BADGE = {
    "SUSPECT":  ("background:#fef9c3;color:#854d0e", "Suspect"),
    "PROSPECT": ("background:#dbeafe;color:#1e40af", "Prospect"),
    "CLIENT":   ("background:#dcfce7;color:#166534", "Client"),
}

@router.get("/admin/contacts", response_class=HTMLResponse)
def contacts_page(request: Request, db: Session = Depends(get_db),
                  status_filter: str = "", search: str = ""):
    token = _check_token(request)
    contacts = db_list_contacts(db)

    # Filtres
    if status_filter:
        contacts = [c for c in contacts if c.status == status_filter]
    if search:
        q = search.lower()
        contacts = [c for c in contacts if q in (c.company_name or "").lower()
                    or q in (c.email or "").lower() or q in (c.city or "").lower()
                    or q in (c.profession or "").lower()]

    rows = ""
    for c in contacts:
        badge_style, badge_label = STATUS_BADGE.get(c.status, ("background:#f3f4f6;color:#374151", c.status))
        import re
        phone_raw = c.phone or ""
        is_mob = bool(re.match(r"^(\+33[67]|0[67])", re.sub(r"[\s\.\-]", "", phone_raw)))
        phone_display = phone_raw or "—"
        mobile_tag = ' <span style="font-size:9px;background:#d1fae5;color:#065f46;padding:1px 4px;border-radius:3px">mob</span>' if (phone_raw and is_mob) else ""
        rows += f"""<tr id="row-{c.id}" style="border-bottom:1px solid #f3f4f6">
  <td style="padding:8px 10px;font-size:12px;font-weight:600">{c.company_name}</td>
  <td style="padding:8px 6px"><span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;{badge_style}">{badge_label}</span></td>
  <td style="padding:8px 6px;font-size:11px;color:#374151">{c.email or '<span style="color:#d1d5db">—</span>'}</td>
  <td style="padding:8px 6px;font-size:11px;color:#374151">{phone_display}{mobile_tag}</td>
  <td style="padding:8px 6px;font-size:11px;color:#6b7280">{c.city or "—"}</td>
  <td style="padding:8px 6px;font-size:11px;color:#6b7280">{c.profession or "—"}</td>
  <td style="padding:8px 6px;font-size:11px;color:#6b7280">{c.date_added.strftime("%d/%m/%y") if c.date_added else "—"}</td>
  <td style="padding:8px 6px;text-align:right">
    <button onclick="deleteContact('{c.id}',this)" style="background:#f3f4f6;border:1px solid #e5e7eb;border-radius:4px;cursor:pointer;padding:3px 8px;color:#6b7280;font-size:11px">✕</button>
  </td>
</tr>"""

    count_total    = len(db_list_contacts(db))
    count_prospect = sum(1 for c in db_list_contacts(db) if c.status == "PROSPECT")
    count_client   = sum(1 for c in db_list_contacts(db) if c.status == "CLIENT")

    nav = admin_nav(token, "contacts")
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Contacts</title>
{nav}
<style>
body{{font-family:system-ui,sans-serif;background:#f9fafb;color:#111;margin:0}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px;margin:16px 24px}}
input,select{{border:1px solid #d1d5db;border-radius:6px;padding:7px 10px;font-size:12px}}
.btn{{background:#e94560;color:#fff;border:none;border-radius:6px;padding:8px 16px;font-size:12px;font-weight:600;cursor:pointer;text-decoration:none;display:inline-block}}
.btn-gray{{background:#f3f4f6;color:#374151;border:1px solid #e5e7eb}}
table{{width:100%;border-collapse:collapse}}
th{{font-size:11px;font-weight:600;color:#6b7280;text-align:left;padding:8px 6px;border-bottom:2px solid #f3f4f6}}
tr:hover td{{background:#fafafa}}
</style></head><body>
<div style="padding:20px 24px 0">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
    <div>
      <h2 style="font-size:18px;font-weight:700;margin:0 0 4px">Contacts</h2>
      <span style="font-size:12px;color:#6b7280">{count_total} total · {count_prospect} prospects · {count_client} clients</span>
    </div>
    <div style="display:flex;gap:8px">
      <button onclick="document.getElementById('leads-panel').classList.toggle('hidden')" class="btn" style="background:#16a34a">+ Obtenir des leads</button>
      <button onclick="document.getElementById('add-panel').classList.toggle('hidden')" class="btn btn-gray">+ Manuel</button>
    </div>
  </div>

  <!-- Widget leads runner -->
  <div id="leads-panel" class="card hidden" style="margin-bottom:12px">
    <h3 style="font-size:13px;font-weight:700;margin:0 0 12px">Obtenir des leads qualifiés</h3>
    <div style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">
      <div>
        <label style="font-size:11px;font-weight:600;display:block;margin-bottom:3px">Métier</label>
        <select id="lr-prof" style="min-width:180px">
          {_prof_options(db)}
        </select>
      </div>
      <div>
        <label style="font-size:11px;font-weight:600;display:block;margin-bottom:3px">Leads voulus</label>
        <input type="number" id="lr-qty" value="20" min="1" max="200" style="width:80px">
      </div>
      <button id="lr-btn" onclick="startLeads()" class="btn" style="background:#16a34a">▶ Lancer</button>
      <button id="lr-stop" onclick="stopLeads()" class="btn btn-gray" style="display:none">⏹ Stopper</button>
    </div>
    <div id="lr-status" style="margin-top:10px;font-size:12px;color:#6b7280;display:none">
      <span id="lr-phase" style="font-weight:600"></span> —
      <span id="lr-suspects"></span> suspects ·
      <span id="lr-processed"></span> traités ·
      <span style="color:#16a34a;font-weight:700"><span id="lr-contacts">0</span> leads</span>
    </div>
  </div>

  <!-- Filtres -->
  <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
    <input type="text" placeholder="Rechercher…" id="q" value="{search}"
      onkeydown="if(event.key==='Enter')applyFilter()"
      style="flex:1;min-width:160px;max-width:300px">
    <select id="sf" onchange="applyFilter()">
      <option value="" {"selected" if not status_filter else ""}>Tous statuts</option>
      <option value="SUSPECT"  {"selected" if status_filter=="SUSPECT"  else ""}>Suspects</option>
      <option value="PROSPECT" {"selected" if status_filter=="PROSPECT" else ""}>Prospects</option>
      <option value="CLIENT"   {"selected" if status_filter=="CLIENT"   else ""}>Clients</option>
    </select>
  </div>

  <!-- Formulaire ajout manuel -->
  <div id="add-panel" class="card hidden" style="margin-bottom:12px">
    <h3 style="font-size:13px;font-weight:700;margin:0 0 12px">Nouveau contact manuel</h3>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px">
      <div><label style="font-size:11px;font-weight:600;display:block;margin-bottom:3px">Entreprise *</label><input id="n-name" type="text" style="width:100%"></div>
      <div><label style="font-size:11px;font-weight:600;display:block;margin-bottom:3px">Email</label><input id="n-email" type="email" style="width:100%"></div>
      <div><label style="font-size:11px;font-weight:600;display:block;margin-bottom:3px">Mobile</label><input id="n-phone" type="text" placeholder="06…" style="width:100%"></div>
      <div><label style="font-size:11px;font-weight:600;display:block;margin-bottom:3px">Ville</label><input id="n-city" type="text" style="width:100%"></div>
      <div><label style="font-size:11px;font-weight:600;display:block;margin-bottom:3px">Profession</label><input id="n-profession" type="text" style="width:100%"></div>
      <div><label style="font-size:11px;font-weight:600;display:block;margin-bottom:3px">Statut</label>
        <select id="n-status" style="width:100%"><option value="PROSPECT">Prospect</option><option value="SUSPECT">Suspect</option><option value="CLIENT">Client</option></select>
      </div>
    </div>
    <button onclick="createContact()" class="btn" style="margin-top:10px">Créer</button>
    <span id="add-status" style="margin-left:10px;font-size:11px;color:#6b7280"></span>
  </div>

  <!-- Table -->
  <div class="card" style="padding:0;overflow-x:auto">
    <table>
      <thead><tr>
        <th style="padding:10px 10px">Entreprise</th>
        <th>Statut</th><th>Email</th><th>Téléphone</th>
        <th>Ville</th><th>Métier</th><th>Ajouté</th><th></th>
      </tr></thead>
      <tbody>
        {rows if rows else '<tr><td colspan="8" style="text-align:center;color:#9ca3af;padding:40px">Aucun contact</td></tr>'}
      </tbody>
    </table>
  </div>
</div>

<script>
const T = '{token}';
function applyFilter() {{
  const q  = document.getElementById('q').value;
  const sf = document.getElementById('sf').value;
  location.href = '/admin/contacts?token='+T+'&search='+encodeURIComponent(q)+'&status_filter='+sf;
}}
async function deleteContact(id, btn) {{
  if(!confirm('Supprimer ce contact ?')) return;
  btn.disabled=true;
  const r = await fetch('/admin/contacts/'+id+'/delete?token='+T, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:'{{}}'}});
  const d = await r.json();
  if(d.ok) document.getElementById('row-'+id).remove();
  else {{ btn.disabled=false; alert('Erreur'); }}
}}
async function createContact() {{
  const data = {{
    company_name: document.getElementById('n-name').value,
    email: document.getElementById('n-email').value||null,
    phone: document.getElementById('n-phone').value||null,
    city:  document.getElementById('n-city').value||null,
    profession: document.getElementById('n-profession').value||null,
    status: document.getElementById('n-status').value,
  }};
  if(!data.company_name) {{ document.getElementById('add-status').textContent='Nom requis'; return; }}
  const r = await fetch('/admin/contacts/create?token='+T, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)}});
  const d = await r.json();
  if(d.id) location.reload(); else document.getElementById('add-status').textContent='Erreur';
}}

// ── Leads runner ──────────────────────────────────────────────────────────────
let _lrPoll = null;
async function startLeads() {{
  const prof = document.getElementById('lr-prof').value;
  const qty  = parseInt(document.getElementById('lr-qty').value) || 20;
  document.getElementById('lr-btn').disabled = true;
  document.getElementById('lr-stop').style.display = 'inline-block';
  document.getElementById('lr-status').style.display = 'block';
  document.getElementById('lr-phase').textContent = 'Démarrage…';
  await fetch('/admin/leads/run?token='+T, {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{profession_id: prof, qty: qty}})
  }});
  _lrPoll = setInterval(_pollLeads, 2000);
}}
async function stopLeads() {{
  await fetch('/admin/leads/stop?token='+T, {{method:'POST'}});
}}
async function _pollLeads() {{
  try {{
    const r = await fetch('/admin/leads/status?token='+T);
    const d = await r.json();
    document.getElementById('lr-phase').textContent    = d.phase || '';
    document.getElementById('lr-suspects').textContent = d.suspects || 0;
    document.getElementById('lr-processed').textContent= d.processed || 0;
    document.getElementById('lr-contacts').textContent = d.contacts || 0;
    if (!d.running) {{
      clearInterval(_lrPoll);
      document.getElementById('lr-btn').disabled = false;
      document.getElementById('lr-stop').style.display = 'none';
      document.getElementById('lr-phase').textContent = '\u2713 Terminé — ' + (d.contacts||0) + ' leads';
      if (d.contacts > 0) setTimeout(() => location.reload(), 1500);
    }}
  }} catch(e) {{}}
}}
// Reprendre polling si pipeline en cours
(async function() {{
  try {{
    const r = await fetch('/admin/leads/status?token='+T);
    const d = await r.json();
    if (d.running) {{
      document.getElementById('leads-panel').classList.remove('hidden');
      document.getElementById('lr-btn').disabled = true;
      document.getElementById('lr-stop').style.display = 'inline-block';
      document.getElementById('lr-status').style.display = 'block';
      _lrPoll = setInterval(_pollLeads, 2000);
    }}
  }} catch(e) {{}}
}})();
</script>
</body></html>""")


def _btn_style(bg: str) -> str:
    return f"background:{bg};color:#ccc;border:none;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:11px"


# ── API endpoints pour les actions AJAX ──────────────────────────────────────

@router.post("/admin/contacts/create")
async def contact_create_async(request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    data = await request.json()
    if not data.get("company_name"):
        raise HTTPException(400, "company_name requis")
    c = ContactDB(
        company_name=data["company_name"],
        email=data.get("email"),
        phone=data.get("phone"),
        city=data.get("city"),
        profession=data.get("profession"),
        status=data.get("status", "SUSPECT"),
        offer_selected=data.get("offer_selected"),
        acquisition_cost=data.get("acquisition_cost"),
        notes=data.get("notes"),
    )
    db_create_contact(db, c)
    return {"id": c.id, "ok": True}


@router.post("/admin/contacts/{cid}/sent")
def contact_mark_sent(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    c = db_get_contact(db, cid)
    if not c: raise HTTPException(404)
    db_update_contact(db, c, message_sent=True, date_message_sent=datetime.utcnow())
    return {"ok": True}


@router.post("/admin/contacts/{cid}/read")
def contact_mark_read(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    c = db_get_contact(db, cid)
    if not c: raise HTTPException(404)
    db_update_contact(db, c, message_read=True, date_message_read=datetime.utcnow())
    return {"ok": True}


@router.post("/admin/contacts/{cid}/paid")
def contact_mark_paid(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    c = db_get_contact(db, cid)
    if not c: raise HTTPException(404)
    db_update_contact(db, c, paid=True, status="CLIENT", date_payment=datetime.utcnow())
    return {"ok": True}


@router.post("/admin/contacts/{cid}/set-status")
async def contact_set_status(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    data = await request.json()
    status = data.get("status", "").upper()
    if status not in ("SUSPECT", "PROSPECT", "CLIENT"):
        raise HTTPException(400, "Statut invalide")
    c = db_get_contact(db, cid)
    if not c: raise HTTPException(404)
    db_update_contact(db, c, status=status)
    return {"ok": True}


@router.post("/admin/contacts/{cid}/delete")
def contact_delete(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    c = db_get_contact(db, cid)
    if not c: raise HTTPException(404)
    db_delete_contact(db, c)
    return {"ok": True}
