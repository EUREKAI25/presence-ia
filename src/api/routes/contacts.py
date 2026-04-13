"""Admin — onglet CONTACTS (SUSPECT/PROSPECT/CLIENT)."""
import os, re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_list_contacts, db_get_contact, db_create_contact, db_update_contact, db_delete_contact, SessionLocal
from ...models import ContactDB
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


def _tracking_map(contact_ids: list) -> dict:
    """Retourne {contact_id: delivery} avec opened_at/clicked_at/calendly_clicked_at."""
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


def _image_readiness(db, contacts) -> tuple[set, dict]:
    """
    Retourne (ready_cities, city_to_dept).
    Une seule requête IN pour toutes les villes — évite le N+1 sur SireneSuspectDB.
    """
    from ...models import CityHeaderDB, SireneSuspectDB
    img_cities = {h.city for h in db.query(CityHeaderDB).all()}

    cities = {(c.city or "").lower() for c in contacts if c.city}
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
                  status_filter: str = "", search: str = ""):
    token = _check_token(request)
    contacts = [c for c in db_list_contacts(db)
                if "[TEST]" not in (c.company_name or "").upper()]

    # Filtres
    if status_filter:
        contacts = [c for c in contacts if c.status == status_filter]
    if search:
        q = search.lower()
        contacts = [c for c in contacts if q in (c.company_name or "").lower()
                    or q in (c.email or "").lower() or q in (c.city or "").lower()
                    or q in (c.profession or "").lower()]

    tracking = _tracking_map([c.id for c in contacts])
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
        sent_style = "background:#dcfce7;color:#166534" if c.message_sent else "background:#f3f4f6;color:#6b7280"
        btn_email = (f'<button onclick="sendContactEmail(\'{c.id}\',this)" title="Envoyer email" '
                     f'style="{sent_style};border:1px solid #e5e7eb;border-radius:4px;cursor:pointer;padding:3px 7px;font-size:11px;margin-right:2px">✉</button>'
                     if c.email else "")
        btn_sms = (f'<button onclick="sendContactSMS(\'{c.id}\',this)" title="Envoyer SMS" '
                   f'style="background:#f3f4f6;color:#6b7280;border:1px solid #e5e7eb;border-radius:4px;cursor:pointer;padding:3px 7px;font-size:11px;margin-right:2px">💬</button>'
                   if (phone_raw and is_mob) else "")
        has_email    = "1" if c.email else "0"
        has_mob      = "1" if (phone_raw and is_mob) else "0"
        city_l       = (c.city or "").lower()
        img_ready    = city_l in ready_cities
        is_test      = "TEST" in (c.company_name or "").upper()
        row_style    = "border-bottom:1px solid #f3f4f6" + ("" if (img_ready or is_test) else ";opacity:.45")
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
        trk = tracking.get(c.id)
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
        rows += f"""<tr id="row-{c.id}" data-cid="{c.id}" data-has-email="{has_email}" data-has-mob="{has_mob}" data-has-p="{has_p}" data-has-sp="{has_sp}" data-img-ready="{img_attr}" style="{row_style}">
  <td style="padding:8px 6px;text-align:center"><input type="checkbox" class="row-cb" data-cid="{c.id}" style="cursor:pointer"></td>
  <td style="padding:8px 10px;font-size:12px;font-weight:600">{c.company_name}</td>
  <td style="padding:8px 6px"><span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;{badge_style}">{badge_label}</span></td>
  <td style="padding:8px 6px;font-size:11px;color:#374151">{c.email or '<span style="color:#d1d5db">—</span>'}</td>
  <td style="padding:8px 6px;font-size:11px;color:#374151">{phone_display}{mobile_tag}</td>
  <td style="padding:8px 6px;font-size:11px;color:#6b7280">{c.city or "—"}</td>
  <td style="padding:8px 6px;text-align:center">{ref_badge}</td>
  <td style="padding:8px 6px;font-size:11px;color:#6b7280">{c.profession or "—"}</td>
  <td style="padding:8px 6px;font-size:11px;color:#6b7280">{c.date_added.strftime("%d/%m/%y") if c.date_added else "—"}</td>
  <td style="padding:8px 6px;text-align:center;white-space:nowrap">{trk_html}</td>
  <td style="padding:8px 6px;text-align:right;white-space:nowrap">
    {btn_email}{btn_sms}<button onclick="deleteContact('{c.id}',this)" style="background:#f3f4f6;border:1px solid #e5e7eb;border-radius:4px;cursor:pointer;padding:3px 8px;color:#6b7280;font-size:11px">✕</button>
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
        <!-- Profils de test (hors DB) -->
        <tr style="background:#f1f5f9">
          <td colspan="11" style="padding:4px 10px;font-size:10px;color:#64748b;font-weight:700;letter-spacing:.05em">
            TEST — SMS : <input id="test-phone" type="text" placeholder="06…" style="font-size:10px;padding:2px 6px;width:110px;border:1px solid #cbd5e1;border-radius:4px;margin-left:4px">
          </td>
        </tr>
        <tr style="background:#fefce8;border-top:1px solid #fde68a">
          <td style="padding:6px 6px;text-align:center"><span style="font-size:9px;background:#92400e;color:#fff;padding:1px 4px;border-radius:3px">T</span></td>
          <td style="padding:6px 10px;font-size:11px;font-weight:600;color:#78350f">Pisciniste · Paris</td>
          <td style="padding:6px 6px"><span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;background:#fde68a;color:#92400e">TEST</span></td>
          <td style="padding:6px 6px;font-size:11px">nathalie.brigitte@gmail.com</td>
          <td style="padding:6px 6px;font-size:11px;color:#9ca3af">—</td>
          <td style="padding:6px 6px;font-size:11px">Paris</td>
          <td style="padding:6px 6px;text-align:center"><span style="font-size:9px;background:#dbeafe;color:#1e40af;padding:1px 5px;border-radius:3px;font-weight:700">P</span></td>
          <td style="padding:6px 6px;font-size:11px;color:#6b7280">Pisciniste</td>
          <td style="padding:6px 6px;font-size:11px;color:#9ca3af">—</td>
          <td></td>
          <td style="padding:6px 6px;white-space:nowrap">
            <button onclick="testProfile(this,'nathalie.brigitte@gmail.com','Pisciniste','Paris','email')"   class="btn" style="background:#2563eb;padding:2px 7px;font-size:10px;margin-right:2px">✉</button>
            <button onclick="testProfile(this,'nathalie.brigitte@gmail.com','Pisciniste','Paris','sms')"     class="btn" style="background:#7c3aed;padding:2px 7px;font-size:10px;margin-right:2px">💬</button>
            <button onclick="testProfile(this,'nathalie.brigitte@gmail.com','Pisciniste','Paris','preview')" class="btn" style="background:#374151;padding:2px 7px;font-size:10px">📋</button>
            <span class="test-res" style="display:block;font-size:9px;color:#6b7280;margin-top:2px"></span>
          </td>
        </tr>
        <tr style="background:#fefce8;border-top:1px solid #fde68a">
          <td style="padding:6px 6px;text-align:center"><span style="font-size:9px;background:#92400e;color:#fff;padding:1px 4px;border-radius:3px">T</span></td>
          <td style="padding:6px 10px;font-size:11px;font-weight:600;color:#78350f">Fleuriste événementiel · Bordeaux</td>
          <td style="padding:6px 6px"><span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;background:#fde68a;color:#92400e">TEST</span></td>
          <td style="padding:6px 6px;font-size:11px">nathaliecbrigitte@gmail.com</td>
          <td style="padding:6px 6px;font-size:11px;color:#9ca3af">—</td>
          <td style="padding:6px 6px;font-size:11px">Bordeaux</td>
          <td style="padding:6px 6px;text-align:center"><span style="font-size:9px;background:#dbeafe;color:#1e40af;padding:1px 5px;border-radius:3px;font-weight:700">P</span></td>
          <td style="padding:6px 6px;font-size:11px;color:#6b7280">Fleuriste événementiel</td>
          <td style="padding:6px 6px;font-size:11px;color:#9ca3af">—</td>
          <td></td>
          <td style="padding:6px 6px;white-space:nowrap">
            <button onclick="testProfile(this,'nathaliecbrigitte@gmail.com','Fleuriste événementiel','Bordeaux','email')"   class="btn" style="background:#2563eb;padding:2px 7px;font-size:10px;margin-right:2px">✉</button>
            <button onclick="testProfile(this,'nathaliecbrigitte@gmail.com','Fleuriste événementiel','Bordeaux','sms')"     class="btn" style="background:#7c3aed;padding:2px 7px;font-size:10px;margin-right:2px">💬</button>
            <button onclick="testProfile(this,'nathaliecbrigitte@gmail.com','Fleuriste événementiel','Bordeaux','preview')" class="btn" style="background:#374151;padding:2px 7px;font-size:10px">📋</button>
            <span class="test-res" style="display:block;font-size:9px;color:#6b7280;margin-top:2px"></span>
          </td>
        </tr>
        <tr style="background:#fefce8;border-top:1px solid #fde68a">
          <td style="padding:6px 6px;text-align:center"><span style="font-size:9px;background:#92400e;color:#fff;padding:1px 4px;border-radius:3px">T</span></td>
          <td style="padding:6px 10px;font-size:11px;font-weight:600;color:#78350f">Consultant communication · Antibes</td>
          <td style="padding:6px 6px"><span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;background:#fde68a;color:#92400e">TEST</span></td>
          <td style="padding:6px 6px;font-size:11px">contact@nathaliebrigitte.com</td>
          <td style="padding:6px 6px;font-size:11px;color:#9ca3af">—</td>
          <td style="padding:6px 6px;font-size:11px">Antibes</td>
          <td style="padding:6px 6px;text-align:center"><span style="font-size:9px;background:#e0f2fe;color:#0369a1;padding:1px 4px;border-radius:3px">SP</span></td>
          <td style="padding:6px 6px;font-size:11px;color:#6b7280">Consultant en communication</td>
          <td style="padding:6px 6px;font-size:11px;color:#9ca3af">—</td>
          <td></td>
          <td style="padding:6px 6px;white-space:nowrap">
            <button onclick="testProfile(this,'contact@nathaliebrigitte.com','Consultant en communication','Antibes','email')"   class="btn" style="background:#2563eb;padding:2px 7px;font-size:10px;margin-right:2px">✉</button>
            <button onclick="testProfile(this,'contact@nathaliebrigitte.com','Consultant en communication','Antibes','sms')"     class="btn" style="background:#7c3aed;padding:2px 7px;font-size:10px;margin-right:2px">💬</button>
            <button onclick="testProfile(this,'contact@nathaliebrigitte.com','Consultant en communication','Antibes','preview')" class="btn" style="background:#374151;padding:2px 7px;font-size:10px">📋</button>
            <span class="test-res" style="display:block;font-size:9px;color:#6b7280;margin-top:2px"></span>
          </td>
        </tr>
        <tr style="background:#fefce8;border-top:1px solid #fde68a">
          <td style="padding:6px 6px;text-align:center"><span style="font-size:9px;background:#92400e;color:#fff;padding:1px 4px;border-radius:3px">T</span></td>
          <td style="padding:6px 10px;font-size:11px;font-weight:600;color:#78350f">Chef cuisinier · Mende <span style="font-size:9px;font-weight:400;color:#9ca3af">(sans visuel)</span></td>
          <td style="padding:6px 6px"><span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;background:#fde68a;color:#92400e">TEST</span></td>
          <td style="padding:6px 6px;font-size:11px">contact@presence-ia.com</td>
          <td style="padding:6px 6px;font-size:11px;color:#9ca3af">—</td>
          <td style="padding:6px 6px;font-size:11px">Mende</td>
          <td style="padding:6px 6px;text-align:center"><span style="font-size:9px;background:#dbeafe;color:#1e40af;padding:1px 5px;border-radius:3px;font-weight:700">P</span></td>
          <td style="padding:6px 6px;font-size:11px;color:#6b7280">Chef cuisinier événementiel</td>
          <td style="padding:6px 6px;font-size:11px;color:#9ca3af">—</td>
          <td></td>
          <td style="padding:6px 6px;white-space:nowrap">
            <button onclick="testProfile(this,'contact@presence-ia.com','Chef cuisinier événementiel','Mende','email')"   class="btn" style="background:#2563eb;padding:2px 7px;font-size:10px;margin-right:2px">✉</button>
            <button onclick="testProfile(this,'contact@presence-ia.com','Chef cuisinier événementiel','Mende','sms')"     class="btn" style="background:#7c3aed;padding:2px 7px;font-size:10px;margin-right:2px">💬</button>
            <button onclick="testProfile(this,'contact@presence-ia.com','Chef cuisinier événementiel','Mende','preview')" class="btn" style="background:#374151;padding:2px 7px;font-size:10px">📋</button>
            <span class="test-res" style="display:block;font-size:9px;color:#6b7280;margin-top:2px"></span>
          </td>
        </tr>
        <tr style="border-bottom:3px solid #e5e7eb"><td colspan="11"></td></tr>
        <!-- Contacts DB -->
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

// ── Mode test ─────────────────────────────────────────────────────────────────
(function() {{
  const ph = localStorage.getItem('test_phone') || '';
  document.getElementById('test-phone').value = ph;
}})();
document.getElementById('test-phone').addEventListener('change', function() {{ localStorage.setItem('test_phone', this.value); }});

function _fmtTestResult(d, label) {{
  const ia   = 'IA: '+d.ia_ok+'/'+d.ia_total;
  const img  = 'img: '+(d.has_image ? (d.img_source==='cache'?'✓cache':'✓Unsplash') : '✗');
  const trm  = d.terme ? 'terme: <em>'+d.terme+'</em>' : '';
  return label + ' · ' + ia + ' · ' + img + (trm ? ' · '+trm : '');
}}
async function testProfile(btn, email, profession, city, action) {{
  const resCell = btn.closest('td').querySelector('.test-res');
  resCell.innerHTML = '⏳ IA en cours…'; resCell.style.color = '#6b7280';
  if (action === 'email') {{
    const r = await fetch('/admin/contacts/test/send-email?token='+T, {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{email, profession, city}})
    }});
    const d = await r.json();
    if (d.ok) {{
      resCell.innerHTML = _fmtTestResult(d, '✓ Envoyé');
      resCell.style.color = '#16a34a';
    }} else {{
      resCell.innerHTML = _fmtTestResult(d, '✗ '+(d.error||'erreur'));
      resCell.style.color = '#dc2626';
    }}
  }} else if (action === 'sms') {{
    const phone = document.getElementById('test-phone').value.trim();
    if (!phone) {{ resCell.innerHTML = '⚠ Numéro requis'; resCell.style.color='#f59e0b'; return; }}
    const r = await fetch('/admin/contacts/test/send-sms?token='+T, {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{phone, profession, city}})
    }});
    const d = await r.json();
    if (d.ok) {{
      resCell.innerHTML = _fmtTestResult(d, '✓ SMS envoyé');
      resCell.style.color = '#16a34a';
    }} else {{
      resCell.innerHTML = _fmtTestResult(d, '✗ '+(d.error||'erreur'));
      resCell.style.color = '#dc2626';
    }}
  }} else {{
    const r = await fetch('/admin/contacts/test/preview-sms?token='+T, {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{profession, city}})
    }});
    const d = await r.json();
    if (d.preview) {{
      resCell.innerHTML = _fmtTestResult(d, '📋')
        + '<br><strong>Message :</strong> ' + d.preview.split('\\n').join('<br>');
      resCell.style.color = '#374151';
    }} else {{
      resCell.innerHTML = '✗ '+(d.error||'erreur');
      resCell.style.color = '#dc2626';
    }}
  }}
}}

// ── Checkboxes + sélection ────────────────────────────────────────────────────
function _updateBulkBar() {{
  const checked = document.querySelectorAll('.row-cb:checked');
  document.getElementById('bulk-count').textContent = checked.length + ' sélectionné(s)';
  // La barre reste toujours visible — pas de masquage
}}
document.addEventListener('change', function(e) {{
  if(e.target.id === 'cb-all') {{
    document.querySelectorAll('.row-cb').forEach(cb => cb.checked = e.target.checked);
  }}
  if(e.target.classList.contains('row-cb') || e.target.id === 'cb-all') _updateBulkBar();
}});
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
    const visible = _rowMatches(tr);
    tr.style.display = visible ? '' : 'none';
    if (visible && n < qty) {{ cb.checked = true; n++; }}
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
  document.querySelectorAll('.row-cb').forEach(cb => {{ cb.checked = n < qty; n++; }});
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
  prog.style.display='inline'; prog.textContent='Envoi en cours…';
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


@router.post("/admin/contacts/test/send-email")
async def contact_test_email(request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    data       = await request.json()
    email      = data.get("email", "").strip()
    profession = data.get("profession", "Pisciniste").strip() or "Pisciniste"
    city       = data.get("city", "Paris").strip() or "Paris"
    if not email:
        return JSONResponse({"ok": False, "error": "email requis"})
    from ...scheduler import _outbound_send_one
    result = _outbound_send_one(profession, city, email=email, dry_run=False)
    return JSONResponse(result)


@router.post("/admin/contacts/test/preview-sms")
async def contact_preview_sms(request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    data       = await request.json()
    profession = data.get("profession", "Pisciniste").strip() or "Pisciniste"
    city       = data.get("city", "Paris").strip() or "Paris"
    from ...scheduler import _outbound_send_one
    # dry_run=True : pipeline complet (IA + image + formatage), sans envoi
    result = _outbound_send_one(profession, city, email="preview@test", dry_run=True)
    return JSONResponse({
        "preview":       result.get("body", ""),
        "chars":         len(result.get("body", "")),
        "ia_ok":         result.get("ia_ok", 0),
        "ia_total":      result.get("ia_total", 0),
        "ia_errors":     result.get("ia_errors", []),
        "has_image":     result.get("has_image", False),
        "img_source":    result.get("img_source"),
        "terme":         result.get("terme", ""),
    })


@router.post("/admin/contacts/test/send-sms")
async def contact_test_sms(request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    data       = await request.json()
    phone      = data.get("phone", "").strip()
    profession = data.get("profession", "Pisciniste").strip() or "Pisciniste"
    city       = data.get("city", "Paris").strip() or "Paris"
    if not phone:
        return JSONResponse({"ok": False, "error": "phone requis"})
    from ...scheduler import _outbound_send_one
    result = _outbound_send_one(profession, city, phone=phone, dry_run=False)
    return JSONResponse(result)


@router.post("/admin/contacts/{cid}/send-email")
async def contact_send_email(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    c = db_get_contact(db, cid)
    if not c: raise HTTPException(404)
    if not c.email:
        return JSONResponse({"ok": False, "error": "Pas d'email"})
    from .v3 import _send_brevo_email, _contact_message, _DEFAULT_EMAIL_SUBJECT, BASE_URL, CALENDLY_URL
    from ...models import V3LandingTextDB, V3ProspectDB
    lt = db.query(V3LandingTextDB).filter_by(id="__global__").first()
    tpl      = lt.email_template if lt and lt.email_template else None
    subj_tpl = lt.email_subject  if lt and lt.email_subject  else _DEFAULT_EMAIL_SUBJECT
    name       = c.company_name or ""
    city       = c.city or ""
    profession = c.profession or ""
    metier     = profession.lower()
    metiers    = metier + "s" if metier and not metier.endswith("s") else metier
    subj = subj_tpl.format(ville=city, metier=metier, metiers=metiers,
                           city=city, profession=profession, name=name)
    # Cherche un prospect V3 associé pour la landing personnalisée
    v3 = db.query(V3ProspectDB).filter(
        (V3ProspectDB.name == name) | (V3ProspectDB.phone == (c.phone or ""))
    ).first()
    landing_url = f"{BASE_URL}/l/{v3.token}" if v3 else CALENDLY_URL
    msg  = _contact_message(name, city, profession, landing_url, tpl)
    delivery_id = _mkt.create_delivery(c.id)
    ok   = _send_brevo_email(c.email, name, subj, msg, delivery_id=delivery_id or "", landing_url=landing_url)
    _mkt.mark_sent(delivery_id, ok)
    if ok:
        db_update_contact(db, c, message_sent=True, date_message_sent=datetime.utcnow())
    return JSONResponse({"ok": ok, "error": None if ok else "Brevo API error"})


@router.post("/admin/contacts/{cid}/send-sms")
async def contact_send_sms(cid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    c = db_get_contact(db, cid)
    if not c: raise HTTPException(404)
    if not c.phone:
        return JSONResponse({"ok": False, "error": "Pas de téléphone"})
    from .v3 import _send_brevo_sms, _contact_message_sms
    from ...models import V3ProspectDB
    name       = c.company_name or ""
    city       = c.city or ""
    profession = c.profession or ""
    # Récupérer la landing_url depuis V3ProspectDB si dispo
    base_url = os.getenv("BASE_URL", "https://presence-ia.com")
    v3 = db.query(V3ProspectDB).filter_by(
        name=name, city=city
    ).first() if name else None
    landing_url = (base_url + v3.landing_url) if v3 and v3.landing_url else ""
    msg = _contact_message_sms(name, city, profession, landing_url)
    delivery_id = _mkt.create_sms_delivery(c.id)
    ok  = _send_brevo_sms(c.phone, msg)
    _mkt.mark_sent(delivery_id, ok)
    if ok:
        db_update_contact(db, c, message_sent=True, date_message_sent=datetime.utcnow())
    return JSONResponse({"ok": ok, "error": None if ok else "Brevo SMS error"})
