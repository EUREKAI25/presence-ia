"""Admin — onglet CONTACTS (SUSPECT/PROSPECT/CLIENT) — opère sur v3_prospects."""
import os, re, secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from ...database import get_db, SessionLocal
from ...models import V3ProspectDB
from ._nav import admin_nav
from . import v3_mkt_bridge as _mkt
from .v3 import DEPT_PREFECTURE

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


def _list_prospects(db: Session) -> list:
    """Liste tous les v3_prospects (vrais + tests), ordonnés par created_at desc."""
    return db.query(V3ProspectDB).order_by(V3ProspectDB.created_at.desc()).all()


def _get_prospect(db: Session, cid: str):
    """Retourne un V3ProspectDB par token (= cid)."""
    return db.query(V3ProspectDB).filter_by(token=cid).first()


def _tracking_map(contact_ids: list) -> dict:
    """Retourne {token: delivery} avec opened_at/clicked_at/calendly_clicked_at."""
    if not contact_ids:
        return {}
    try:
        db = _mkt._mkt_db()
        if not db:
            return {}
        from marketing_module.models import ProspectDeliveryDB
        rows = (
            db.query(ProspectDeliveryDB)
            .filter(ProspectDeliveryDB.prospect_id.in_(contact_ids))
            .order_by(ProspectDeliveryDB.created_at.desc())
            .all()
        )
        db.close()
        result = {}
        for r in rows:
            if r.prospect_id not in result:
                result[r.prospect_id] = r
        return result
    except Exception:
        return {}


def _image_readiness(db, prospects) -> tuple[set, dict]:
    """
    Retourne (ready_cities, city_to_dept).
    Une seule requête IN pour toutes les villes — évite le N+1 sur SireneSuspectDB.
    """
    from ...models import CityHeaderDB, SireneSuspectDB
    img_cities = {h.city for h in db.query(CityHeaderDB).all()}

    cities = {(c.city or "").lower() for c in prospects if c.city}
    if not cities:
        return set(), {}

    # Une seule requête pour récupérer dept de toutes les villes d'un coup
    city_titles = [c.title() for c in cities]
    rows = (
        db.query(SireneSuspectDB.ville, SireneSuspectDB.departement)
        .filter(
            SireneSuspectDB.ville.in_(city_titles),
            SireneSuspectDB.departement.isnot(None),
        )
        .distinct(SireneSuspectDB.ville)
        .all()
    )
    city_to_dept: dict = {r.ville.lower(): r.departement for r in rows if r.departement}

    ready_cities: set = set()
    for city_l in cities:
        if city_l in img_cities:
            ready_cities.add(city_l)
        else:
            dept = city_to_dept.get(city_l, "")
            if dept:
                prefecture = DEPT_PREFECTURE.get(dept, "").lower()
                if prefecture and prefecture in img_cities:
                    ready_cities.add(city_l)
    return ready_cities, city_to_dept


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
                  status_filter: str = "", search: str = "", show_test: str = ""):
    token = _check_token(request)

    contacts = list(_list_prospects(db))

    # Filtres
    if status_filter:
        contacts = [c for c in contacts if c.status == status_filter]
    if show_test == "0":
        contacts = [c for c in contacts if not c.is_test]
    if search:
        q = search.lower()
        contacts = [c for c in contacts if q in (c.name or "").lower()
                    or q in (c.email or "").lower() or q in (c.city or "").lower()
                    or q in (c.profession or "").lower()]

    tracking = _tracking_map([c.token for c in contacts])
    ready_cities, city_to_dept = _image_readiness(db, contacts)

    # Préfectures / sous-préfectures
    ref_city_types: dict = {}
    try:
        from ...models import RefCityDB
        ref_city_types = {r.city_name: r.city_type for r in db.query(RefCityDB).all()}
    except Exception:
        pass

    # Images manquantes
    missing_cities = []
    for c in contacts:
        city_l = (c.city or "").lower()
        if city_l and city_l not in ready_cities:
            dept = city_to_dept.get(city_l, "")
            prefecture = DEPT_PREFECTURE.get(dept, "") if dept else ""
            entry = (c.city or "").title()
            label = f"{entry} (dept {dept} → préfecture : {prefecture})" if dept else entry
            if label not in missing_cities:
                missing_cities.append(label)

    rows = ""
    for c in contacts:
        badge_style, badge_label = STATUS_BADGE.get(c.status, ("background:#f3f4f6;color:#374151", c.status))
        phone_raw = c.phone or ""
        is_mob = bool(re.match(r"^(\+33[67]|0[67])", re.sub(r"[\s\.\-]", "", phone_raw)))
        phone_display = phone_raw or "—"
        mobile_tag = ' <span style="font-size:9px;background:#d1fae5;color:#065f46;padding:1px 4px;border-radius:3px">mob</span>' if (phone_raw and is_mob) else ""
        sent_style = "background:#dcfce7;color:#166534" if c.contacted else "background:#f3f4f6;color:#6b7280"
        btn_email = (f'<button onclick="sendContactEmail(\'{c.token}\',this)" title="Envoyer email" '
                     f'style="{sent_style};border:1px solid #e5e7eb;border-radius:4px;cursor:pointer;padding:3px 7px;font-size:11px;margin-right:2px">✉</button>'
                     if c.email else "")
        btn_sms = (f'<button onclick="sendContactSMS(\'{c.token}\',this)" title="Envoyer SMS" '
                   f'style="background:#f3f4f6;color:#6b7280;border:1px solid #e5e7eb;border-radius:4px;cursor:pointer;padding:3px 7px;font-size:11px;margin-right:2px">💬</button>'
                   if (phone_raw and is_mob) else "")
        has_email    = "1" if c.email else "0"
        has_mob      = "1" if (phone_raw and is_mob) else "0"
        city_l       = (c.city or "").lower()
        img_ready    = city_l in ready_cities
        is_test      = c.is_test
        row_style    = ("background:#fefce8;border-bottom:1px solid #fde68a" if is_test
                        else "border-bottom:1px solid #f3f4f6" + ("" if img_ready else ";opacity:.45"))
        img_attr     = "1" if img_ready else "0"
        # Badge P / SP
        city_upper   = (c.city or "").strip().upper()
        _ctype       = ref_city_types.get(city_upper, "")
        if _ctype == "prefecture":
            ref_badge = '<span style="font-size:9px;background:#dbeafe;color:#1e40af;padding:1px 5px;border-radius:3px;font-weight:700">P</span>'
            has_p = "1"; has_sp = "0"
        elif _ctype == "sous_prefecture":
            ref_badge = '<span style="font-size:9px;background:#e0f2fe;color:#0369a1;padding:1px 4px;border-radius:3px">SP</span>'
            has_p = "0"; has_sp = "1"
        else:
            ref_badge = '<span style="color:#d1d5db;font-size:10px">—</span>'
            has_p = "0"; has_sp = "0"
        trk = tracking.get(c.token)
        def _trk_icon(val, emoji, label):
            if not val:
                return f'<span title="{label}" style="color:#d1d5db;font-size:13px">{emoji}</span>'
            ts = val.strftime("%d/%m %H:%M")
            return f'<span title="{label} {ts}" style="color:#16a34a;font-size:13px">{emoji}</span>'
        trk_html = (
            _trk_icon(trk.opened_at if trk else None, "👁", "Email ouvert") + " " +
            _trk_icon(getattr(trk, "landing_visited_at", None) if trk else None, "🏠", "Landing visitée") + " " +
            _trk_icon(getattr(trk, "calendly_clicked_at", None) if trk else None, "📅", "Calendly cliqué")
        ) if True else ""
        status_cell = ('<span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;background:#fde68a;color:#92400e">TEST</span>'
                       if is_test else
                       f'<span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;{badge_style}">{badge_label}</span>')
        rows += f"""<tr id="row-{c.token}" data-cid="{c.token}" data-has-email="{has_email}" data-has-mob="{has_mob}" data-has-p="{has_p}" data-has-sp="{has_sp}" data-img-ready="{img_attr}" data-is-test="{'1' if is_test else '0'}" style="{row_style}">
  <td style="padding:8px 6px;text-align:center"><input type="checkbox" class="row-cb" data-cid="{c.token}" style="cursor:pointer"></td>
  <td style="padding:8px 10px;font-size:12px;font-weight:600">{c.name}</td>
  <td style="padding:8px 6px">{status_cell}</td>
  <td style="padding:8px 6px;font-size:11px;color:#374151">{c.email or '<span style="color:#d1d5db">—</span>'}</td>
  <td style="padding:8px 6px;font-size:11px;color:#374151">{phone_display}{mobile_tag}</td>
  <td style="padding:8px 6px;font-size:11px;color:#6b7280">{c.city or "—"}</td>
  <td style="padding:8px 6px;text-align:center">{ref_badge}</td>
  <td style="padding:8px 6px;font-size:11px;color:#6b7280">{c.profession or "—"}</td>
  <td style="padding:8px 6px;font-size:11px;color:#6b7280">{c.created_at.strftime("%d/%m/%y") if c.created_at else "—"}</td>
  <td style="padding:8px 6px;text-align:center;white-space:nowrap">{trk_html}</td>
  <td style="padding:8px 6px;text-align:right;white-space:nowrap">
    {btn_email}{btn_sms}<button onclick="runIATest('{c.token}',this)" title="Lancer test IA (ChatGPT+Gemini+Claude)" style="background:#f3f4f6;border:1px solid #e5e7eb;border-radius:4px;cursor:pointer;padding:3px 7px;font-size:11px;margin-right:2px">🤖</button><button onclick="deleteContact('{c.token}',this)" style="background:#f3f4f6;border:1px solid #e5e7eb;border-radius:4px;cursor:pointer;padding:3px 8px;color:#6b7280;font-size:11px">✕</button>
  </td>
</tr>"""

    all_real = db.query(V3ProspectDB).filter_by(is_test=False).all()
    count_total    = len(all_real)
    count_prospect = sum(1 for c in all_real if c.status == "PROSPECT")
    count_client   = sum(1 for c in all_real if c.status == "CLIENT")

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
        <label style="font-size:11px;font-weight:600;display:block;margin-bottom:3px">Département</label>
        <input type="text" id="lr-dept" placeholder="ex: 33" maxlength="3" style="width:60px;text-align:center">
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
  <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center">
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

  <!-- Barre actions groupées — toujours visible -->
  <div id="bulk-bar" style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px 16px;margin-bottom:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
    <span style="font-size:11px;color:#6b7280;font-weight:600">Sélectionner</span>
    <input type="number" id="bulk-qty" min="1" max="9999" placeholder="max" title="Nombre max à sélectionner (vide = tous)"
           style="width:60px;padding:4px 8px;border:1px solid #d1d5db;border-radius:6px;font-size:12px;text-align:center">
    <button id="fbtn-email" onclick="selectByType('email')" class="btn btn-gray" style="padding:5px 10px;font-size:11px">✉ Email</button>
    <button id="fbtn-mob"   onclick="selectByType('mob')"   class="btn btn-gray" style="padding:5px 10px;font-size:11px">💬 Mobile</button>
    <button id="fbtn-p"     onclick="selectByType('p')"     class="btn btn-gray" style="padding:5px 10px;font-size:11px">📍 P</button>
    <button id="fbtn-sp"    onclick="selectByType('sp')"    class="btn btn-gray" style="padding:5px 10px;font-size:11px">📍 SP</button>
    <button id="fbtn-all"   onclick="selectAll()"           class="btn btn-gray" style="padding:5px 10px;font-size:11px">☑ Tout</button>
    <button id="fbtn-none"  onclick="selectNone()"          class="btn btn-gray" style="padding:5px 10px;font-size:11px">☐ Aucun</button>
    <button id="mode-toggle" onclick="toggleTestMode()" class="btn btn-gray" style="padding:5px 10px;font-size:11px">🧪 Mode test</button>
    <div style="flex:1"></div>
    <span id="bulk-count" style="font-size:12px;color:#6b7280">0 sélectionné(s)</span>
    <button onclick="bulkSendEmail()" class="btn" style="background:#2563eb;padding:5px 12px;font-size:11px">✉ Envoyer email</button>
    <button onclick="bulkSendSMS()" class="btn" style="background:#7c3aed;padding:5px 12px;font-size:11px">💬 Envoyer SMS</button>
    <div id="bulk-progress" style="font-size:11px;color:#6b7280;display:none"></div>
  </div>

  <!-- Table -->
  <div class="card" style="padding:0;overflow-x:auto">
    <table>
      <thead><tr>
        <th style="padding:10px 6px;text-align:center;width:32px"><input type="checkbox" id="cb-all" title="Tout sélectionner" style="cursor:pointer"></th>
        <th style="padding:10px 10px">Entreprise</th>
        <th>Statut</th><th>Email</th><th>Téléphone</th>
        <th>Ville</th>
        <th style="text-align:center;width:36px" title="P = préfecture · SP = sous-préfecture">P/SP</th>
        <th>Métier</th><th>Ajouté</th>
        <th style="text-align:center" title="👁 Email ouvert · 🏠 Landing visitée · 📅 Calendly cliqué">Tracking</th><th></th>
      </tr></thead>
      <tbody>
        {rows if rows else '<tr><td colspan="11" style="text-align:center;color:#9ca3af;padding:40px">Aucun contact</td></tr>'}
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
function toggleNoImg() {{
  const hide = document.getElementById('hide-no-img').checked;
  document.querySelectorAll('tr[data-img-ready="0"]').forEach(tr => {{
    tr.style.display = hide ? 'none' : '';
  }});
}}
async function startLeads() {{
  const prof = document.getElementById('lr-prof').value;
  const qty  = parseInt(document.getElementById('lr-qty').value) || 20;
  const dept = (document.getElementById('lr-dept').value || '').trim() || null;
  document.getElementById('lr-btn').disabled = true;
  document.getElementById('lr-stop').style.display = 'inline-block';
  document.getElementById('lr-status').style.display = 'block';
  document.getElementById('lr-phase').textContent = 'Démarrage…';
  await fetch('/admin/leads/run?token='+T, {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{profession_id: prof, qty: qty, dept: dept}})
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

// ── Mode test / envoi ─────────────────────────────────────────────────────────
let _testMode = false;
function _applyMode() {{
  document.querySelectorAll('.row-cb').forEach(cb => {{
    const isTest = cb.closest('tr').dataset.isTest === '1';
    const disabled = _testMode ? !isTest : isTest;
    cb.disabled = disabled;
    cb.style.cursor  = disabled ? 'not-allowed' : 'pointer';
    cb.style.opacity = disabled ? '0.3' : '1';
    if(disabled) cb.checked = false;
  }});
  const btn = document.getElementById('mode-toggle');
  if(_testMode) {{
    btn.textContent = '🧪 Mode test actif';
    btn.style.background = '#f59e0b'; btn.style.color = '#fff'; btn.style.borderColor = '#f59e0b';
  }} else {{
    btn.textContent = '🧪 Mode test';
    btn.style.background = ''; btn.style.color = ''; btn.style.borderColor = '';
  }}
  _updateBulkBar();
}}
function toggleTestMode() {{ _testMode = !_testMode; selectNone(); _applyMode(); }}

// ── Checkboxes + sélection ────────────────────────────────────────────────────
function _updateBulkBar() {{
  const checked = document.querySelectorAll('.row-cb:checked');
  document.getElementById('bulk-count').textContent = checked.length + ' sélectionné(s)';
}}
document.addEventListener('change', function(e) {{
  if(e.target.id === 'cb-all') {{
    document.querySelectorAll('.row-cb:not(:disabled)').forEach(cb => cb.checked = e.target.checked);
  }}
  if(e.target.classList.contains('row-cb') || e.target.id === 'cb-all') _updateBulkBar();
}});
document.addEventListener('DOMContentLoaded', function() {{ _applyMode(); }});
function _getQty() {{
  const v = parseInt(document.getElementById('bulk-qty').value);
  return (v > 0) ? v : Infinity;
}}
// ── Filtres toggles — deux groupes indépendants ───────────────────────────────
// Groupe GEO  (P, SP)      : OU entre eux
// Groupe CTCT (email, mob) : OU entre eux
// Entre groupes actifs     : ET
const _geoF  = new Set();   // 'p', 'sp'
const _ctctF = new Set();   // 'email', 'mob'
const _GEO_IDS  = ['p','sp'];
const _CTCT_IDS = ['email','mob'];

function _refreshBtn(id) {{
  const b = document.getElementById('fbtn-'+id);
  if (!b) return;
  const on = _geoF.has(id) || _ctctF.has(id);
  b.style.background  = on ? '#1e40af' : '';
  b.style.color       = on ? '#fff'    : '';
  b.style.borderColor = on ? '#1e40af' : '';
  b.style.fontWeight  = on ? '700'     : '';
}}

function _rowMatches(tr) {{
  const geoOk  = _geoF.size  === 0 || [..._geoF].some(t  => tr.dataset['has'+t.charAt(0).toUpperCase()+t.slice(1)] === '1');
  const ctctOk = _ctctF.size === 0 || [..._ctctF].some(t => tr.dataset['has'+t.charAt(0).toUpperCase()+t.slice(1)] === '1');
  return geoOk && ctctOk;
}}

function _applyFilters() {{
  const qty = _getQty(); let n = 0;
  document.querySelectorAll('.row-cb').forEach(cb => {{
    cb.checked = false;
    const tr = cb.closest('tr');
    const isTest = tr.dataset.isTest === '1';
    if (isTest) {{ tr.style.display = ''; return; }}
    const visible = _rowMatches(tr);
    tr.style.display = visible ? '' : 'none';
    if (visible && !cb.disabled && n < qty) {{ cb.checked = true; n++; }}
  }});
  _updateBulkBar();
}}

function selectByType(type) {{
  const set = _GEO_IDS.includes(type) ? _geoF : _ctctF;
  if (set.has(type)) set.delete(type); else set.add(type);
  _refreshBtn(type);
  _applyFilters();
}}

function _clearFilters() {{
  _geoF.clear(); _ctctF.clear();
  [..._GEO_IDS, ..._CTCT_IDS].forEach(id => _refreshBtn(id));
  document.querySelectorAll('.row-cb').forEach(cb => {{ cb.closest('tr').style.display = ''; }});
}}

function selectAll() {{
  _clearFilters();
  const qty = _getQty(); let n = 0;
  document.querySelectorAll('.row-cb:not(:disabled)').forEach(cb => {{
    cb.checked = n < qty; n++;
  }});
  _updateBulkBar();
}}

function selectNone() {{
  _clearFilters();
  document.querySelectorAll('.row-cb').forEach(cb => {{ cb.checked = false; }});
  _updateBulkBar();
}}
function _selectedIds() {{ return [...document.querySelectorAll('.row-cb:checked')].map(cb=>cb.dataset.cid); }}

async function bulkSendEmail() {{
  const ids = _selectedIds();
  if(!ids.length) {{ alert('Aucun contact sélectionné'); return; }}
  if(!confirm('Envoyer un email à ' + ids.length + ' contact(s) ?')) return;
  const prog = document.getElementById('bulk-progress');
  prog.style.display='inline'; prog.textContent='Envoi email en cours…';
  let ok=0, err=0;
  for(const id of ids) {{
    try {{
      const r = await fetch('/admin/contacts/'+id+'/send-email?token='+T, {{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});
      const d = await r.json();
      if(d.ok) ok++; else err++;
    }} catch(e) {{ err++; }}
    prog.textContent = ok+' envoyés, '+err+' erreurs…';
    await new Promise(r=>setTimeout(r,300));
  }}
  prog.textContent = 'Terminé — '+ok+' envoyés, '+err+' erreurs';
}}
async function bulkSendSMS() {{
  const ids = _selectedIds();
  if(!ids.length) {{ alert('Aucun contact sélectionné'); return; }}
  if(!confirm('Envoyer un SMS à ' + ids.length + ' contact(s) ?')) return;
  const prog = document.getElementById('bulk-progress');
  prog.style.display='inline'; prog.textContent='Envoi SMS en cours…';
  let ok=0, err=0;
  for(const id of ids) {{
    try {{
      const r = await fetch('/admin/contacts/'+id+'/send-sms?token='+T, {{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});
      const d = await r.json();
      if(d.ok) ok++; else err++;
    }} catch(e) {{ err++; }}
    prog.textContent = ok+' envoyés, '+err+' erreurs…';
    await new Promise(r=>setTimeout(r,300));
  }}
  prog.textContent = 'Terminé — '+ok+' envoyés, '+err+' erreurs';
}}

// ── Envoi email / SMS par contact ─────────────────────────────────────────────
async function sendContactEmail(id, btn) {{
  if(!confirm("Envoyer l'email ?")) return;
  btn.disabled = true;
  try {{
    const r = await fetch('/admin/contacts/'+id+'/send-email?token='+T, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:'{{}}'}});
    const d = await r.json();
    if(d.ok) {{ btn.style.background='#dcfce7'; btn.style.color='#166534'; btn.title='Email envoyé'; }}
    else {{ alert('Erreur: '+(d.error||'inconnue')); btn.disabled=false; }}
  }} catch(e) {{ btn.disabled=false; alert('Erreur réseau'); }}
}}
async function sendContactSMS(id, btn) {{
  if(!confirm("Envoyer le SMS ?")) return;
  btn.disabled = true;
  try {{
    const r = await fetch('/admin/contacts/'+id+'/send-sms?token='+T, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:'{{}}'}});
    const d = await r.json();
    if(d.ok) {{ btn.style.background='#dcfce7'; btn.style.color='#166534'; btn.title='SMS envoyé'; }}
    else {{ alert('Erreur: '+(d.error||'inconnue')); btn.disabled=false; }}
  }} catch(e) {{ btn.disabled=false; alert('Erreur réseau'); }}
}}
async function runIATest(id, btn) {{
  if(!confirm("Lancer le test IA ? (ChatGPT + Gemini + Claude — ~30 secondes)")) return;
  btn.disabled = true; btn.textContent = '⏳';
  try {{
    const r = await fetch('/api/v3/prospect/'+id+'/run-ia-test', {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{token: T}})
    }});
    const d = await r.json();
    if(d.ok) {{ btn.style.background='#dcfce7'; btn.style.color='#166534'; btn.textContent='🤖'; btn.title='IA testée — '+d.n_results+' résultats'; }}
    else {{ alert('Erreur: '+(d.error||'inconnue')); btn.disabled=false; btn.textContent='🤖'; }}
  }} catch(e) {{ btn.disabled=false; btn.textContent='🤖'; alert('Erreur réseau'); }}
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
    tok = secrets.token_hex(16)
    c = V3ProspectDB(
        token=tok,
        name=data["company_name"],
        email=data.get("email"),
        phone=data.get("phone"),
        city=data.get("city") or "",
        profession=data.get("profession") or "",
        status=data.get("status", "SUSPECT"),
        offer_selected=data.get("offer_selected"),
        acquisition_cost=data.get("acquisition_cost"),
        notes=data.get("notes"),
        landing_url=f"/l/{tok}",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.token, "ok": True}


@router.post("/admin/contacts/{cid}/sent")
def contact_mark_sent(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    c = _get_prospect(db, cid)
    if not c: raise HTTPException(404)
    c.contacted = True
    c.email_sent_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/admin/contacts/{cid}/read")
def contact_mark_read(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    c = _get_prospect(db, cid)
    if not c: raise HTTPException(404)
    if not c.email_opened_at:
        c.email_opened_at = datetime.utcnow()
        db.commit()
    return {"ok": True}


@router.post("/admin/contacts/{cid}/paid")
def contact_mark_paid(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    c = _get_prospect(db, cid)
    if not c: raise HTTPException(404)
    c.paid = True
    c.status = "CLIENT"
    c.date_payment = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/admin/contacts/{cid}/set-status")
async def contact_set_status(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    data = await request.json()
    status = data.get("status", "").upper()
    if status not in ("SUSPECT", "PROSPECT", "CLIENT"):
        raise HTTPException(400, "Statut invalide")
    c = _get_prospect(db, cid)
    if not c: raise HTTPException(404)
    c.status = status
    db.commit()
    return {"ok": True}


@router.post("/admin/contacts/{cid}/delete")
def contact_delete(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    c = _get_prospect(db, cid)
    if not c: raise HTTPException(404)
    db.delete(c)
    db.commit()
    return {"ok": True}


def _preflight_ia_and_image(db, c) -> str | None:
    """
    Garantit que ia_results ET image header existent avant tout envoi.
    Retourne un message d'erreur si impossible, None si OK.
    """
    import json as _j
    from .v3 import _run_ia_test
    # ── 1. IA results — vérifie existence ET qualité (réponses non vides) ───
    def _ia_valid(ia_json):
        if not ia_json: return False
        try:
            results = _j.loads(ia_json)
            return any(r.get("response") for r in results)
        except Exception:
            return False

    if not _ia_valid(c.ia_results):
        try:
            ia_data = _run_ia_test(c.profession or "", c.city or "")
            if ia_data and ia_data.get("results"):
                import json as _j
                ia_json = _j.dumps(ia_data["results"], ensure_ascii=False)
                # Mettre à jour tous les prospects de la même paire
                for p in db.query(V3ProspectDB).filter_by(
                    city=c.city, profession=c.profession
                ).all():
                    p.ia_results   = ia_json
                    p.ia_tested_at = ia_data.get("tested_at")
                db.commit()
            else:
                return "Requêtes IA vides — impossible de générer la landing"
        except Exception as e:
            return f"Erreur requêtes IA : {e}"
    # ── 2. Image header ──────────────────────────────────────────────────────
    try:
        from ...models import RefCityDB
        from ...city_images import fetch_city_header_image
        ref = db.query(RefCityDB).filter_by(
            city_name=(c.city or "").upper()
        ).first()
        if not ref or not ref.header_image_url:
            img_url = fetch_city_header_image(c.city or "")
            if not img_url:
                return f"Image introuvable pour {c.city} — impossible de générer la landing"
    except Exception:
        pass  # image non bloquante si erreur réseau
    return None


@router.post("/admin/contacts/{cid}/send-email")
async def contact_send_email(cid: str, request: Request, db: Session = Depends(get_db)):
    import asyncio
    _check_token(request)
    c = _get_prospect(db, cid)
    if not c: raise HTTPException(404)
    if not c.email:
        return JSONResponse({"ok": False, "error": "Pas d'email"})
    # ── Preflight : IA + image obligatoires avant envoi ──────────────────────
    # run_in_executor → thread séparé, évite de bloquer l'event loop (et le 502)
    err = await asyncio.get_event_loop().run_in_executor(None, _preflight_ia_and_image, db, c)
    if err:
        return JSONResponse({"ok": False, "error": err})
    from .v3 import (_send_brevo_email, _send_brevo_sms, _is_gmail,
                     _contact_message, _contact_message_sms,
                     _DEFAULT_EMAIL_SUBJECT, BASE_URL)
    from ...models import V3LandingTextDB
    lt = db.query(V3LandingTextDB).filter_by(id="__global__").first()
    name       = c.name or ""
    city       = c.city or ""
    profession = c.profession or ""
    landing_url = f"{BASE_URL}/l/{c.token}"
    # Gmail + mobile → forcer SMS
    if _is_gmail(c.email) and c.phone:
        msg = _contact_message_sms(name, city, profession, landing_url)
        delivery_id = _mkt.create_sms_delivery(c.token)
        ok  = _send_brevo_sms(c.phone, msg)
        _mkt.mark_sent(delivery_id, ok)
        if ok:
            c.contacted = True
            c.email_sent_at = datetime.utcnow()
            db.commit()
        return JSONResponse({"ok": ok, "error": None if ok else "Brevo SMS error", "method_used": "sms"})
    tpl      = lt.email_template if lt and lt.email_template else None
    subj_tpl = lt.email_subject  if lt and lt.email_subject  else _DEFAULT_EMAIL_SUBJECT
    metier   = profession.lower()
    metiers  = metier + "s" if metier and not metier.endswith("s") else metier
    ville    = city.title()
    subj = subj_tpl.format(ville=ville, metier=metier, metiers=metiers,
                           city=ville, profession=profession, name=name)
    msg  = _contact_message(name, city, profession, landing_url, tpl)
    delivery_id = _mkt.create_delivery(c.token)
    ok   = _send_brevo_email(c.email, name, subj, msg, delivery_id=delivery_id or "", landing_url=landing_url)
    _mkt.mark_sent(delivery_id, ok)
    if ok:
        c.contacted = True
        c.email_sent_at = datetime.utcnow()
        db.commit()
    return JSONResponse({"ok": ok, "error": None if ok else "Brevo API error"})


@router.post("/admin/contacts/{cid}/send-sms")
async def contact_send_sms(cid: str, request: Request, db: Session = Depends(get_db)):
    import asyncio
    _check_token(request)
    c = _get_prospect(db, cid)
    if not c: raise HTTPException(404)
    if not c.phone:
        return JSONResponse({"ok": False, "error": "Pas de téléphone"})
    err = await asyncio.get_event_loop().run_in_executor(None, _preflight_ia_and_image, db, c)
    if err:
        return JSONResponse({"ok": False, "error": err})
    from .v3 import _send_brevo_sms, _contact_message_sms, BASE_URL
    name       = c.name or ""
    city       = c.city or ""
    profession = c.profession or ""
    landing_url = f"{BASE_URL}/l/{c.token}"
    msg = _contact_message_sms(name, city, profession, landing_url)
    delivery_id = _mkt.create_sms_delivery(c.token)
    ok  = _send_brevo_sms(c.phone, msg)
    _mkt.mark_sent(delivery_id, ok)
    if ok:
        c.contacted = True
        c.email_sent_at = datetime.utcnow()
        db.commit()
    return JSONResponse({"ok": ok, "error": None if ok else "Brevo SMS error"})
