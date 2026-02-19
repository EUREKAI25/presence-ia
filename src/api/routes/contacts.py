"""Admin — onglet CONTACTS (SUSPECT/PROSPECT/CLIENT)."""
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_list_contacts, db_get_contact, db_create_contact, db_update_contact, db_delete_contact
from ...models import ContactDB

router = APIRouter(tags=["Admin Contacts"])


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


STATUS_COLORS = {"SUSPECT": "#888", "PROSPECT": "#e9a020", "CLIENT": "#2ecc71"}
def _offer_labels(db: Session) -> dict:
    """Labels des offres lus depuis offers_module (pas hardcodés)."""
    from offers_module.database import db_list_offers
    offers = db_list_offers(db)
    return {o.name: o.name for o in offers} if offers else {}


@router.get("/admin/contacts", response_class=HTMLResponse)
def contacts_page(request: Request, db: Session = Depends(get_db)):
    token = _check_token(request)
    contacts = db_list_contacts(db)
    offer_labels = _offer_labels(db)

    rows = ""
    for c in contacts:
        sc = STATUS_COLORS.get(c.status, "#aaa")
        offer = offer_labels.get(c.offer_selected or "", c.offer_selected or "—")
        sent_icon  = "✅" if c.message_sent  else "—"
        read_icon  = "✅" if c.message_read  else "—"
        paid_icon  = "✅" if c.paid          else "—"
        rows += f"""<tr id="row-{c.id}">
  <td>{c.company_name}</td>
  <td style="color:{sc};font-weight:bold">{c.status}</td>
  <td>{c.email or "—"}</td>
  <td>{c.city or "—"}</td>
  <td style="text-align:center">{sent_icon}</td>
  <td style="text-align:center">{read_icon}</td>
  <td style="text-align:center">{paid_icon}</td>
  <td>{offer}</td>
  <td style="color:#aaa">{c.date_added.strftime("%d/%m/%y") if c.date_added else "—"}</td>
  <td style="color:#e9a020">{c.acquisition_cost or "—"}</td>
  <td style="display:flex;gap:6px;flex-wrap:wrap;padding:6px">
    <button onclick="markContact('{c.id}','sent',this)" style="{_btn_style('#2a2a4e')}">📨 Envoyé</button>
    <button onclick="markContact('{c.id}','read',this)" style="{_btn_style('#2a2a4e')}">👁 Lu</button>
    <button onclick="markContact('{c.id}','paid',this)" style="{_btn_style('#1a4a2e')}">💳 Payé</button>
    <button onclick="setStatus('{c.id}',this)" style="{_btn_style('#2a2a4e')}">🔄 Statut</button>
    <button onclick="deleteContact('{c.id}',this)" style="{_btn_style('#4a1a1a')}">🗑</button>
  </td>
</tr>"""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Contacts — PRESENCE_IA Admin</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
table{{border-collapse:collapse;width:100%}}th{{background:#16213e;color:#aaa;padding:10px;font-size:11px;text-align:left}}
td{{padding:9px 10px;border-bottom:1px solid #1a1a2e;font-size:12px;vertical-align:middle}}
tr:hover td{{background:#12122a}}.add-form{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px;margin:20px}}
input,select,textarea{{background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;padding:7px 10px;border-radius:4px;font-size:12px}}
label{{color:#aaa;font-size:11px;display:block;margin-bottom:3px}}</style></head><body>
{_nav("contacts", token)}
<div style="padding:20px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
  <h1 style="color:#fff;font-size:18px">👥 Contacts ({len(contacts)})</h1>
  <button onclick="document.getElementById('add-form').style.display=document.getElementById('add-form').style.display==='none'?'block':'none'"
    style="background:#e94560;color:#fff;border:none;padding:8px 18px;border-radius:6px;cursor:pointer;font-size:13px">+ Nouveau contact</button>
</div>

<div id="add-form" class="add-form" style="display:none">
<h3 style="color:#fff;margin-bottom:16px">Nouveau contact</h3>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px">
  <div><label>Entreprise *</label><input id="n-name" type="text" placeholder="Martin Toiture" style="width:100%"></div>
  <div><label>Email</label><input id="n-email" type="email" placeholder="contact@..." style="width:100%"></div>
  <div><label>Téléphone</label><input id="n-phone" type="text" placeholder="06..." style="width:100%"></div>
  <div><label>Ville</label><input id="n-city" type="text" placeholder="Rennes" style="width:100%"></div>
  <div><label>Profession</label><input id="n-profession" type="text" placeholder="couvreur" style="width:100%"></div>
  <div><label>Statut</label><select id="n-status" style="width:100%"><option value="SUSPECT">SUSPECT</option><option value="PROSPECT">PROSPECT</option><option value="CLIENT">CLIENT</option></select></div>
  <div><label>Offre</label><select id="n-offer" style="width:100%"><option value="">—</option><option value="FLASH">Audit Flash</option><option value="KIT">Kit Visibilité</option><option value="DONE_FOR_YOU">Tout inclus</option></select></div>
  <div><label>Coût acquisition (€)</label><input id="n-cost" type="number" step="0.01" style="width:100%"></div>
</div>
<div style="margin-top:12px"><label>Notes</label><textarea id="n-notes" rows="2" style="width:100%"></textarea></div>
<button onclick="createContact()" style="margin-top:12px;background:#e94560;color:#fff;border:none;padding:10px 24px;border-radius:6px;cursor:pointer;font-size:13px">Créer</button>
<span id="add-status" style="margin-left:12px;font-size:12px"></span>
</div>

<div style="overflow-x:auto">
<table>
<tr><th>Entreprise</th><th>Statut</th><th>Email</th><th>Ville</th><th>Envoyé</th><th>Lu</th><th>Payé</th><th>Offre</th><th>Ajouté</th><th>Acq. €</th><th>Actions</th></tr>
{rows if rows else '<tr><td colspan="11" style="text-align:center;color:#555;padding:40px">Aucun contact</td></tr>'}
</table>
</div>
</div>

<script>
const T = '{token}';
async function api(url, data) {{
  const r = await fetch(url + '?token=' + T, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)}});
  return r.json();
}}
async function markContact(id, action, btn) {{
  btn.disabled=true; btn.textContent='…';
  const r = await api('/admin/contacts/'+id+'/'+action, {{}});
  if(r.ok) location.reload(); else {{ btn.disabled=false; btn.textContent='Erreur'; }}
}}
async function setStatus(id, btn) {{
  const s = prompt('Nouveau statut (SUSPECT/PROSPECT/CLIENT):');
  if(!s) return;
  btn.disabled=true;
  const r = await api('/admin/contacts/'+id+'/set-status', {{status:s.toUpperCase()}});
  if(r.ok) location.reload(); else {{ btn.disabled=false; alert('Erreur: '+JSON.stringify(r)); }}
}}
async function deleteContact(id, btn) {{
  if(!confirm('Supprimer ce contact ?')) return;
  btn.disabled=true;
  const r = await api('/admin/contacts/'+id+'/delete', {{}});
  if(r.ok) document.getElementById('row-'+id).remove();
  else {{ btn.disabled=false; alert('Erreur'); }}
}}
async function createContact() {{
  const data = {{
    company_name: document.getElementById('n-name').value,
    email: document.getElementById('n-email').value||null,
    phone: document.getElementById('n-phone').value||null,
    city: document.getElementById('n-city').value||null,
    profession: document.getElementById('n-profession').value||null,
    status: document.getElementById('n-status').value,
    offer_selected: document.getElementById('n-offer').value||null,
    acquisition_cost: parseFloat(document.getElementById('n-cost').value)||null,
    notes: document.getElementById('n-notes').value||null,
  }};
  if(!data.company_name) {{ document.getElementById('add-status').textContent='Nom requis'; return; }}
  const r = await api('/admin/contacts/create', data);
  if(r.id) location.reload(); else document.getElementById('add-status').textContent='Erreur: '+JSON.stringify(r);
}}
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
