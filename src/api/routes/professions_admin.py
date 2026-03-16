"""
Admin — Référentiel métiers + pondération scoring.
GET  /admin/professions          → liste avec scores + filtres
POST /admin/professions/bulk     → activer/désactiver une liste d'ids
POST /admin/professions/{id}     → modifier une profession (scores, actif...)
POST /admin/professions/scoring  → modifier les poids du score global
POST /admin/professions/qualify  → déclencher qualification SIRENE pour les actifs
"""
import json, logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...database import (SessionLocal, db_list_professions, db_update_profession,
                         db_get_scoring_config, db_update_scoring_config, db_score_global,
                         db_sirene_count, db_segment_stats, db_segment_list, db_suspects_list)
from ._nav import admin_nav, admin_token

log    = logging.getLogger(__name__)
router = APIRouter()


def _require_admin(token: str):
    if token != admin_token():
        from fastapi import HTTPException
        raise HTTPException(403, "Non autorisé")


def _bar(score, max_val=10, color="#e94560"):
    if score is None:
        return '<span style="color:#9ca3af;font-size:11px">—</span>'
    pct = int(score / max_val * 100)
    return (
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<div style="width:60px;height:6px;background:#f3f4f6;border-radius:3px">'
        f'<div style="width:{pct}%;height:100%;background:{color};border-radius:3px"></div>'
        f'</div>'
        f'<span style="font-size:11px;color:#374151">{score}</span>'
        f'</div>'
    )


@router.get("/admin/professions", response_class=HTMLResponse)
def professions_page(token: str = "", cat: str = "", q: str = "", actif: str = "", request: Request = None):
    _require_admin(token)
    with SessionLocal() as db:
        profs = db_list_professions(db)
        cfg   = db_get_scoring_config(db)

    cats = sorted(set(p.categorie for p in profs))
    if cat:
        profs = [p for p in profs if p.categorie == cat]
    if q:
        ql = q.lower()
        profs = [p for p in profs if ql in p.label.lower() or ql in (p.categorie or "").lower()]
    if actif == "1":
        profs = [p for p in profs if p.actif]
    elif actif == "0":
        profs = [p for p in profs if not p.actif]

    profs_scored = [(p, db_score_global(p, cfg)) for p in profs]
    profs_scored.sort(key=lambda x: x[1], reverse=True)

    # Professions aux NAF ambigus (partagés par plusieurs professions)
    with SessionLocal() as db_naf:
        from .naf_audit import _get_ambiguous_nafs
        ambig_map = _get_ambiguous_nafs(db_naf)
    ambig_prof_ids = {p["id"] for plist in ambig_map.values() for p in plist}
    nb_ambig = len(ambig_prof_ids)

    # Comptages SIRENE par profession (une seule requête par profession) + total global
    with SessionLocal() as db2:
        sirene_counts = {p.id: db_sirene_count(db2, profession_id=p.id) for p, _ in profs_scored}
        total_suspects_global = db_sirene_count(db2)

    nb_actifs = sum(1 for p, _ in profs_scored if p.actif)

    cat_opts = "".join(
        f'<option value="{c}" {"selected" if cat==c else ""}>{c}</option>'
        for c in cats
    )
    actif_opts = (
        f'<option value="" {"selected" if actif=="" else ""}>Tous statuts</option>'
        f'<option value="1" {"selected" if actif=="1" else ""}>Actifs seulement</option>'
        f'<option value="0" {"selected" if actif=="0" else ""}>Inactifs seulement</option>'
    )

    rows_html = ""
    for p, sg in profs_scored:
        actif_badge = (
            '<span class="actif-badge" style="background:#dcfce7;color:#166534;font-size:10px;padding:1px 6px;border-radius:10px">actif</span>'
            if p.actif else
            '<span class="actif-badge" style="background:#f3f4f6;color:#9ca3af;font-size:10px;padding:1px 6px;border-radius:10px">inactif</span>'
        )
        naf    = ", ".join(json.loads(p.codes_naf or "[]")[:3]) or "—"
        termes = ", ".join(json.loads(p.termes_recherche or "[]")[:3]) or "—"
        kw_sirene = json.loads(p.mots_cles_sirene or "[]")
        kw_cell = (
            f'<span style="color:#16a34a;font-size:10px" title="{", ".join(kw_sirene)}">✓ {", ".join(kw_sirene[:2])}{"…" if len(kw_sirene)>2 else ""}</span>'
            if kw_sirene else
            f'<span onclick="event.stopPropagation();generateKeywords(\'{p.id}\')" style="color:#f59e0b;font-size:10px;cursor:pointer" title="Générer mots-clés SIRENE">⚠ générer</span>'
        )
        vc     = f"{p.valeur_client:,}€".replace(",", " ") if p.valeur_client else "—"
        sg_color = "#16a34a" if sg >= 7 else ("#d97706" if sg >= 4 else "#dc2626")
        actif_int = 1 if p.actif else 0
        nb_sirene = sirene_counts.get(p.id, 0)
        suspects_url = f"/admin/suspects?profession_id={p.id}&token={token}"
        if nb_sirene:
            sirene_cell = f'<a href="{suspects_url}" style="font-size:12px;font-weight:600;color:#1d4ed8;text-decoration:none" title="Voir les suspects">{nb_sirene:,}</a>'
            label_link  = f'<a href="{suspects_url}" style="color:inherit;text-decoration:none;font-size:12px;font-weight:600" title="Voir {nb_sirene:,} suspects">{p.label}</a>'
        else:
            sirene_cell = f'<span onclick="quickQualify(\'{p.id}\')" style="font-size:11px;color:#9ca3af;cursor:pointer" title="Lancer la qualification">—</span>'
            label_link  = f'<span style="font-size:12px;font-weight:600">{p.label}</span>'

        checked = "checked" if p.actif else ""
        ambig_attr = ' data-ambig="1"' if p.id in ambig_prof_ids else ''
        ambig_style = ";background:#fff7ed" if p.id in ambig_prof_ids else ""
        rows_html += f"""
        <tr data-id="{p.id}" data-actif="{actif_int}" data-has-kw="{'1' if kw_sirene else '0'}"
            data-label="{p.label}" data-cat="{p.categorie or ''}"
            data-vis="{p.score_visibilite or 0}" data-conseil="{p.score_conseil_ia or 0}"
            data-valeur="{p.valeur_client or 0}" data-score="{sg}"{ambig_attr}
            style="border-bottom:1px solid #f3f4f6{ambig_style}">
          <td style="padding:8px 10px"><input type="checkbox" class="row-cb" data-id="{p.id}" {checked} onclick="toggleActif(event,this)" style="margin-right:6px;width:15px;height:15px;cursor:pointer">{label_link}</td>
          <td style="padding:8px 6px;font-size:11px;color:#6b7280">{p.categorie}</td>
          <td style="padding:8px 6px">{_bar(p.score_visibilite)}</td>
          <td style="padding:8px 6px">{_bar(p.score_conseil_ia, color="#8b5cf6")}</td>
          <td style="padding:8px 6px;font-size:11px;color:#374151">{vc}</td>
          <td style="padding:8px 6px;font-weight:700;color:{sg_color};font-size:13px">{sg}</td>
          <td style="padding:8px 6px;font-size:10px;color:#9ca3af;max-width:100px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">{naf}</td>
          <td style="padding:8px 6px;font-size:10px;color:#9ca3af;max-width:100px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">{termes}</td>
          <td style="padding:8px 6px;max-width:110px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">{kw_cell}</td>
          <td style="padding:8px 6px">{actif_badge}</td>
          <td style="padding:8px 6px;text-align:right" class="sirene-count">{sirene_cell}</td>
          <td style="padding:8px 6px;text-align:center"><button onclick="event.stopPropagation();editProf('{p.id}',{p.score_visibilite or 'null'},{p.score_conseil_ia or 'null'},{p.valeur_client or 'null'},'{p.label.replace("'", "\\'")}');" style="background:#f3f4f6;border:1px solid #e5e7eb;border-radius:4px;cursor:pointer;padding:3px 7px;color:#6b7280;font-size:11px" title="Modifier les scores">Scores</button></td>
        </tr>"""

    nav = admin_nav(token, "professions")
    return HTMLResponse(f"""<!DOCTYPE html><html><head>
<meta charset="utf-8"><title>Référentiel métiers</title>
{nav}
<style>
body{{font-family:system-ui,sans-serif;background:#f9fafb;color:#111}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px}}
input[type=text],input[type=number],select{{border:1px solid #d1d5db;border-radius:6px;padding:6px 10px;font-size:13px;outline:none}}
input:focus,select:focus{{border-color:#e94560}}
.btn{{background:#e94560;color:#fff;border:none;border-radius:6px;padding:8px 16px;font-size:13px;cursor:pointer;font-weight:600}}
.btn:hover{{background:#c73652}}
.btn-sm{{padding:5px 10px;font-size:12px}}
.btn-green{{background:#16a34a}}.btn-green:hover{{background:#15803d}}
.btn-gray{{background:#6b7280}}.btn-gray:hover{{background:#4b5563}}
.btn-outline{{background:#fff;color:#374151;border:1px solid #d1d5db}}.btn-outline:hover{{background:#f3f4f6}}
.hidden{{display:none!important}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;font-size:11px;color:#6b7280;font-weight:600;padding:8px 10px;border-bottom:2px solid #e5e7eb;white-space:nowrap;cursor:pointer;user-select:none}}
th:hover{{color:#111;background:#f9fafb}}
th .sort-arrow{{margin-left:4px;opacity:.4}}
th.sorted .sort-arrow{{opacity:1}}
tr:hover{{background:#fafafa;cursor:pointer}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:2000;align-items:center;justify-content:center}}
.modal.show{{display:flex}}
.modal-box{{background:#fff;border-radius:10px;padding:24px;width:440px;max-width:95vw}}
</style>
</head><body>
<div style="padding:24px">

  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px">
    <h1 style="font-size:18px;font-weight:700;margin:0">Référentiel métiers
      <span style="font-size:13px;color:#6b7280;font-weight:400;margin-left:8px">{len(profs_scored)} professions · {nb_actifs} actives · <span style="color:#1d4ed8">{total_suspects_global:,}</span> suspects</span>
    </h1>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn btn-sm btn-blue" onclick="generateKeywords()" title="Générer mots_cles_sirene via LLM pour les professions sans mots-clés">🔑 Mots-clés SIRENE</button>
      <button class="btn btn-sm btn-green" onclick="openQualify()">▶ Lancer qualification</button>
      <button class="btn btn-sm btn-outline" onclick="document.getElementById('scoring-panel').classList.toggle('hidden')">⚙ Pondération</button>
    </div>
  </div>

  <!-- Pondération scoring -->
  <div id="scoring-panel" class="card hidden" style="margin-bottom:16px">
    <h3 style="margin:0 0 12px;font-size:14px;font-weight:700">Pondération du score global</h3>
    <form id="scoring-form" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <label style="font-size:12px">Dép. recherche (actuel: {cfg.w_visibilite})
        <input name="w_visibilite" type="number" step="0.05" min="0" max="1" value="{cfg.w_visibilite}" style="width:100%;margin-top:4px">
      </label>
      <label style="font-size:12px">Dép. conseil IA (actuel: {cfg.w_conseil_ia})
        <input name="w_conseil_ia" type="number" step="0.05" min="0" max="1" value="{cfg.w_conseil_ia}" style="width:100%;margin-top:4px">
      </label>
      <label style="font-size:12px">Concurrence (actuel: {cfg.w_concurrence})
        <input name="w_concurrence" type="number" step="0.05" min="0" max="1" value="{cfg.w_concurrence}" style="width:100%;margin-top:4px">
      </label>
      <label style="font-size:12px">Valeur client (actuel: {cfg.w_valeur})
        <input name="w_valeur" type="number" step="0.05" min="0" max="1" value="{cfg.w_valeur}" style="width:100%;margin-top:4px">
      </label>
    </form>
    <div style="margin-top:12px;display:flex;gap:8px">
      <button class="btn btn-sm" onclick="saveScoringWeights()">Enregistrer</button>
      <span id="scoring-msg" style="font-size:12px;color:#16a34a;align-self:center"></span>
    </div>
  </div>

  <!-- Filtres + actions bulk -->
  <div class="card" style="padding:12px 16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <input type="text" placeholder="Rechercher..." value="{q}" id="q-input" style="width:180px"
      onkeydown="if(event.key==='Enter') applyFilters()">
    <select id="cat-sel" onchange="applyFilters()">
      <option value="">Toutes catégories</option>
      {cat_opts}
    </select>
    <select id="actif-sel" onchange="applyFilters()">
      {actif_opts}
    </select>
    <label style="display:flex;align-items:center;gap:6px;font-size:12px;cursor:pointer;white-space:nowrap;margin-left:8px;color:#374151">
      <input type="checkbox" id="hide-ambig" onchange="applyAmbigFilter()" style="width:14px;height:14px;cursor:pointer;accent-color:#e94560">
      Masquer NAF litigieux
      <span style="background:#fee2e2;color:#991b1b;border-radius:10px;padding:1px 7px;font-size:11px">{nb_ambig}</span>
    </label>
    <span id="bulk-msg" style="font-size:12px;color:#16a34a;margin-left:auto"></span>
  </div>

  <!-- Tableau -->
  <div class="card" style="padding:0;overflow-x:auto">
    <table id="prof-table">
      <thead>
        <tr>
          <th><input type="checkbox" id="th-cb" onclick="toggleAll(this)" style="width:15px;height:15px;cursor:pointer" title="Tout activer / désactiver"> Métier <span class="sort-arrow" onclick="sortTable('label')" style="cursor:pointer">↕</span></th>
          <th onclick="sortTable('cat')">Catégorie <span class="sort-arrow">↕</span></th>
          <th onclick="sortTable('vis')" title="Dépendance à la recherche en ligne immédiate (Google, Maps)">Dép. recherche <span class="sort-arrow">↕</span></th>
          <th onclick="sortTable('conseil')" title="Dépendance au conseil IA / comparaison avant achat (ChatGPT, avis...)">Dép. conseil IA <span class="sort-arrow">↕</span></th>
          <th onclick="sortTable('valeur')">Valeur client <span class="sort-arrow">↕</span></th>
          <th id="th-score" onclick="sortTable('score')">Score ▼ <span class="sort-arrow">↕</span></th>
          <th>NAF</th>
          <th>Termes</th>
          <th title="Mots-clés étymologiques pour filtre raison sociale SIRENE">Mots-clés SIRENE</th>
          <th onclick="sortTable('actif')">Statut <span class="sort-arrow">↕</span></th>
          <th style="text-align:right">Suspects SIRENE</th>
          <th></th>
        </tr>
      </thead>
      <tbody id="prof-tbody">{rows_html}</tbody>
    </table>
  </div>
</div>

<!-- Modal édition -->
<div class="modal" id="edit-modal">
  <div class="modal-box">
    <h3 style="margin:0 0 16px;font-size:15px;font-weight:700" id="modal-title">Modifier</h3>
    <input type="hidden" id="edit-id">
    <div style="display:grid;gap:12px">
      <label style="font-size:12px">Dép. recherche en ligne (1-10)
        <input id="edit-visibilite" type="number" min="1" max="10" style="width:100%;margin-top:4px">
      </label>
      <label style="font-size:12px">Dép. conseil IA / comparaison (1-10)
        <input id="edit-conseil" type="number" min="1" max="10" style="width:100%;margin-top:4px">
      </label>
      <label style="font-size:12px">Valeur client estimée (€)
        <input id="edit-valeur" type="number" min="0" style="width:100%;margin-top:4px">
      </label>
    </div>
    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn btn-sm" onclick="saveProf()">Enregistrer</button>
      <button class="btn btn-sm btn-gray" onclick="closeModal()">Annuler</button>
      <span id="edit-msg" style="font-size:12px;color:#16a34a;align-self:center"></span>
    </div>
  </div>
</div>

<!-- Modale de progression qualification -->
<div class="modal" id="qualify-modal">
  <div class="modal-box" style="width:520px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h3 id="qualify-modal-title" style="margin:0;font-size:15px;font-weight:700">⏳ Qualification en cours...</h3>
      <button onclick="document.getElementById('qualify-modal').classList.remove('show')" style="background:none;border:none;font-size:18px;cursor:pointer;color:#9ca3af">✕</button>
    </div>
    <!-- Tableau par profession -->
    <table style="width:100%;border-collapse:collapse;margin-bottom:14px">
      <thead>
        <tr style="border-bottom:2px solid #e5e7eb">
          <th style="text-align:left;font-size:11px;color:#9ca3af;font-weight:600;padding:6px 8px">Métier</th>
          <th style="text-align:right;font-size:11px;color:#9ca3af;font-weight:600;padding:6px 8px">Suspects</th>
          <th style="text-align:right;font-size:11px;color:#9ca3af;font-weight:600;padding:6px 8px">Segments</th>
        </tr>
      </thead>
      <tbody id="qualify-prof-rows"></tbody>
    </table>
    <div id="qualify-progress-bar" style="height:5px;background:#f3f4f6;border-radius:3px;margin-bottom:12px;overflow:hidden">
      <div id="qualify-progress-fill" style="height:100%;background:#2563eb;border-radius:3px;width:0%;transition:width .5s"></div>
    </div>
    <div style="display:flex;justify-content:flex-end;gap:8px">
      <a href="/admin/sirene/segments?token={token}" style="font-size:11px;color:#3b82f6;align-self:center">Voir segments →</a>
      <button class="btn btn-sm btn-gray" onclick="document.getElementById('qualify-modal').classList.remove('show')">Fermer</button>
    </div>
  </div>
</div>

<script>
const TOKEN = '{token}';
let sortCol = 'score', sortAsc = false;

// ── Masquer / afficher NAF litigieux ─────────────
function applyAmbigFilter() {{
  const hide = document.getElementById('hide-ambig').checked;
  localStorage.setItem('hide_ambig_nafs', hide ? '1' : '0');
  document.querySelectorAll('#prof-tbody tr[data-ambig="1"]').forEach(tr => {{
    tr.style.display = hide ? 'none' : '';
  }});
}}
// Restaurer l'état depuis localStorage au chargement
(function() {{
  const saved = localStorage.getItem('hide_ambig_nafs');
  if (saved === '1') {{
    const cb = document.getElementById('hide-ambig');
    if (cb) {{ cb.checked = true; applyAmbigFilter(); }}
  }}
}})();

// ── Filtres ──────────────────────────────────────
function applyFilters() {{
  const q   = document.getElementById('q-input').value;
  const cat = document.getElementById('cat-sel').value;
  const act = document.getElementById('actif-sel').value;
  let url = `/admin/professions?token=${{TOKEN}}&q=${{encodeURIComponent(q)}}&cat=${{encodeURIComponent(cat)}}`;
  if(act) url += `&actif=${{act}}`;
  location.href = url;
}}

// ── Tri colonnes (client-side) ────────────────────
function sortTable(col) {{
  if(sortCol === col) sortAsc = !sortAsc;
  else {{ sortCol = col; sortAsc = col === 'label' || col === 'cat'; }}
  const tbody = document.getElementById('prof-tbody');
  const rows  = Array.from(tbody.querySelectorAll('tr'));
  rows.sort((a, b) => {{
    let va = a.dataset[col] || '', vb = b.dataset[col] || '';
    const num = !isNaN(va) && !isNaN(vb);
    if(num) {{ va = parseFloat(va); vb = parseFloat(vb); }}
    else    {{ va = va.toLowerCase(); vb = vb.toLowerCase(); }}
    if(va < vb) return sortAsc ? -1 : 1;
    if(va > vb) return sortAsc ? 1 : -1;
    return 0;
  }});
  rows.forEach(r => tbody.appendChild(r));
  // Mettre à jour les flèches
  document.querySelectorAll('th').forEach(th => {{
    th.classList.remove('sorted');
    const arrow = th.querySelector('.sort-arrow');
    if(arrow) arrow.textContent = '↕';
  }});
  const ths = document.querySelectorAll('th');
  const colMap = {{'label':0,'cat':1,'vis':2,'conseil':3,'valeur':4,'score':5,'actif':8}};
  const idx = colMap[col];
  if(idx !== undefined) {{
    ths[idx].classList.add('sorted');
    const arrow = ths[idx].querySelector('.sort-arrow');
    if(arrow) arrow.textContent = sortAsc ? '↑' : '↓';
  }}
}}

// ── Toggle actif (clic sur checkbox ligne) ───────
async function toggleActif(e, cb) {{
  e.stopPropagation();
  const id    = cb.dataset.id;
  const actif = cb.checked;
  const row   = cb.closest('tr');
  const msg   = document.getElementById('bulk-msg');
  const r = await fetch(`/admin/professions/${{id}}?token=${{TOKEN}}`, {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{actif}})
  }});
  if(r.ok) {{
    row.dataset.actif = actif ? '1' : '0';
    const badge = row.querySelector('.actif-badge');
    if(badge) {{
      badge.textContent = actif ? 'actif' : 'inactif';
      badge.style.background = actif ? '#dcfce7' : '#f3f4f6';
      badge.style.color = actif ? '#166534' : '#9ca3af';
    }}
    // Mettre à jour la checkbox du th
    const allCbs = document.querySelectorAll('.row-cb');
    const allChecked = Array.from(allCbs).every(c => c.checked);
    document.getElementById('th-cb').checked = allChecked;
    msg.style.color = '#16a34a';
    msg.textContent = actif ? `✓ ${{id}} activé` : `✓ ${{id}} désactivé`;
  }} else {{
    cb.checked = !actif; // rollback
    msg.style.color = '#dc2626';
    msg.textContent = 'Erreur';
  }}
}}

// ── Toggle all (checkbox th) ──────────────────────
async function toggleAll(thCb) {{
  const actif = thCb.checked;
  const cbs   = document.querySelectorAll('.row-cb');
  const msg   = document.getElementById('bulk-msg');
  msg.style.color = '#6b7280';
  msg.textContent = `Mise à jour de ${{cbs.length}} professions...`;
  let ok = 0;
  for(const cb of cbs) {{
    cb.checked = actif;
    const id = cb.dataset.id;
    const r = await fetch(`/admin/professions/${{id}}?token=${{TOKEN}}`, {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{actif}})
    }});
    if(r.ok) {{ ok++; cb.closest('tr').dataset.actif = actif ? '1' : '0'; }}
  }}
  msg.style.color = '#16a34a';
  msg.textContent = `✓ ${{ok}} professions ${{actif ? 'activées' : 'désactivées'}}`;
}}

// ── Modal édition ─────────────────────────────────
function editProf(id, vis, conseil, valeur, label) {{
  document.getElementById('edit-id').value = id;
  document.getElementById('modal-title').textContent = 'Scores — ' + label;
  document.getElementById('edit-visibilite').value = vis || '';
  document.getElementById('edit-conseil').value = conseil || '';
  document.getElementById('edit-valeur').value = valeur || '';
  document.getElementById('edit-modal').classList.add('show');
}}
function closeModal() {{
  document.getElementById('edit-modal').classList.remove('show');
  document.getElementById('edit-msg').textContent = '';
}}
async function saveProf() {{
  const id   = document.getElementById('edit-id').value;
  const data = {{
    score_visibilite: parseInt(document.getElementById('edit-visibilite').value) || null,
    score_conseil_ia: parseInt(document.getElementById('edit-conseil').value) || null,
    valeur_client:    parseInt(document.getElementById('edit-valeur').value) || null,
  }};
  const r = await fetch(`/admin/professions/${{id}}?token=${{TOKEN}}`, {{
    method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)
  }});
  if(r.ok) {{ document.getElementById('edit-msg').textContent='✓ Enregistré'; setTimeout(()=>location.reload(),800); }}
  else {{ document.getElementById('edit-msg').style.color='#dc2626'; document.getElementById('edit-msg').textContent='Erreur'; }}
}}
document.getElementById('edit-modal').addEventListener('click', function(e) {{
  if(e.target===this) closeModal();
}});

// ── Qualification SIRENE ──────────────────────────
let _pollInterval = null;
let _qualifyProfIds = [];
let _profLabels = {{}};
function stopPolling() {{ if(_pollInterval) {{ clearInterval(_pollInterval); _pollInterval = null; }} }}

function _updateQualifyTable(by_prof, segs_by_prof, running) {{
  const tbody = document.getElementById('qualify-prof-rows');
  if (!tbody) return;
  // Progress global (sur les professions en cours seulement)
  let totalDone = 0, totalSegs = 0;
  tbody.innerHTML = _qualifyProfIds.map(pid => {{
    const label    = _profLabels[pid] || pid;
    const suspects = (by_prof[pid] || 0).toLocaleString('fr-FR');
    const segs     = segs_by_prof ? segs_by_prof[pid] : null;
    const segDone  = segs ? segs.done  : 0;
    const segTotal = segs ? segs.total : 0;
    totalDone  += segDone;
    totalSegs  += segTotal;
    const segDone100 = segTotal > 0 && segDone >= segTotal;
    const segStr = segTotal > 0
      ? `${{segDone.toLocaleString('fr-FR')}} / ${{segTotal.toLocaleString('fr-FR')}} ${{segDone100 ? '<span style="color:#16a34a">✓</span>' : '<span style="color:#d97706">⏳</span>'}}`
      : '—';
    const suspectsHtml = by_prof[pid] !== undefined
      ? `<strong style="font-size:15px;color:#1d4ed8">${{suspects}}</strong>`
      : '<span style="color:#9ca3af">—</span>';
    return `<tr style="border-bottom:1px solid #f3f4f6">
      <td style="padding:8px 8px;font-size:13px;font-weight:600">${{label}}</td>
      <td style="padding:8px 8px;text-align:right">${{suspectsHtml}}</td>
      <td style="padding:8px 8px;text-align:right;font-size:12px;color:#374151">${{segStr}}</td>
    </tr>`;
  }}).join('');
  // Barre de progression
  if(totalSegs > 0) {{
    document.getElementById('qualify-progress-fill').style.width =
      Math.round(totalDone / totalSegs * 100) + '%';
  }}
}}

async function openQualify() {{
  const activeRows = [...document.querySelectorAll('tr[data-id][data-actif="1"][data-has-kw="1"]')]
    .filter(r => r.style.display !== 'none');
  _qualifyProfIds = activeRows.map(r => r.dataset.id);
  _profLabels = {{}};
  activeRows.forEach(r => {{ _profLabels[r.dataset.id] = r.dataset.label; }});

  if(_qualifyProfIds.length === 0) {{
    alert("Aucune profession active dans la vue \u2014 cochez des m\u00e9tiers d\u2019abord.");
    return;
  }}
  const btn = document.querySelector('[onclick="openQualify()"]');
  btn.disabled = true;
  btn.textContent = '\u23f3 Lancement...';

  document.getElementById('qualify-modal-title').textContent = '\u23f3 Qualification en cours...';
  document.getElementById('qualify-progress-fill').style.width = '0%';
  _updateQualifyTable({{}}, {{}}, true);
  document.getElementById('qualify-modal').classList.add('show');

  const r = await fetch(`/admin/professions/qualify?token=${{TOKEN}}`, {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{profession_ids: _qualifyProfIds}})
  }});
  if(!r.ok) {{
    const d = await r.json().catch(()=>({{}}));
    document.getElementById('qualify-modal-title').innerHTML =
      `<span style="color:#dc2626">\u274c ${{d.detail || 'Erreur'}}</span>`;
    btn.disabled = false; btn.textContent = '\u25b6 Lancer qualification';
    return;
  }}
  btn.textContent = '\u23f3 En cours...';

  _pollInterval = setInterval(async () => {{
    try {{
      const profIds = _qualifyProfIds.join(',');
      const pr = await fetch(`/admin/professions/qualify-status?token=${{TOKEN}}&profs=${{profIds}}`);
      const pd = await pr.json();

      _updateQualifyTable(pd.by_prof || {{}}, pd.segs_by_prof || {{}}, pd.running);

      // MAJ cellules tableau principal
      document.querySelectorAll('tr[data-id]').forEach(row => {{
        const cnt = (pd.by_prof || {{}})[row.dataset.id];
        const cell = row.querySelector('.sirene-count');
        if(cell && cnt !== undefined) {{
          const url = `/admin/suspects?profession_id=${{row.dataset.id}}&token=${{TOKEN}}`;
          cell.innerHTML = cnt > 0
            ? `<a href="${{url}}" style="font-size:12px;font-weight:600;color:#1d4ed8;text-decoration:none">${{cnt.toLocaleString('fr-FR')}}</a>`
            : '<span style="font-size:11px;color:#d1d5db">\u2014</span>';
        }}
      }});

      if(pd.done && !pd.running) {{
        stopPolling();
        document.getElementById('qualify-modal-title').innerHTML =
          '<span style="color:#16a34a;font-weight:700">\u2713 Qualification termin\u00e9e</span>';
        btn.disabled = false; btn.textContent = '\u25b6 Lancer qualification';
      }}
    }} catch(e) {{}}
  }}, 4000);
}}

// Serveur déjà trié par score desc — on indique juste la flèche sans re-trier
(function() {{
  const th = document.getElementById('th-score');
  if(th) {{ const a = th.querySelector('.sort-arrow'); if(a) a.textContent = '\u2193'; th.classList.add('sorted'); }}
}})();

async function quickQualify(profId) {{
  const row = document.querySelector(`tr[data-id="${{profId}}"]`);
  _qualifyProfIds = [profId];
  _profLabels = {{}};
  if(row) _profLabels[profId] = row.dataset.label || profId;
  document.getElementById('qualify-modal-title').textContent = '\u23f3 Qualification en cours...';
  document.getElementById('qualify-progress-fill').style.width = '0%';
  _updateQualifyTable({{}}, {{}}, true);
  document.getElementById('qualify-modal').classList.add('show');
  const r = await fetch('/admin/professions/qualify?token={token}', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{profession_ids:[profId]}})
  }});
  if(r.ok) {{
    _pollInterval = setInterval(async () => {{
      try {{
        const pr = await fetch(`/admin/professions/qualify-status?token=${{TOKEN}}&profs=${{profId}}`);
        const pd = await pr.json();
        _updateQualifyTable(pd.by_prof || {{}}, pd.segs_by_prof || {{}}, pd.running);
        const cnt = (pd.by_prof || {{}})[profId];
        if(cnt !== undefined) {{
          const cell = row ? row.querySelector('.sirene-count') : null;
          if(cell) {{
            const url = `/admin/suspects?profession_id=${{profId}}&token=${{TOKEN}}`;
            cell.innerHTML = cnt > 0
              ? `<a href="${{url}}" style="font-size:12px;font-weight:600;color:#1d4ed8;text-decoration:none">${{cnt.toLocaleString('fr-FR')}}</a>`
              : '<span style="font-size:11px;color:#d1d5db">\u2014</span>';
          }}
        }}
        if(pd.done && !pd.running) {{
          stopPolling();
          document.getElementById('qualify-modal-title').innerHTML =
            '<span style="color:#16a34a;font-weight:700">\u2713 Qualification termin\u00e9e</span>';
        }}
      }} catch(e) {{}}
    }}, 4000);
  }}
}}

async function generateKeywords(profId, force) {{
  const url = '/admin/sirene/generate-keywords?token='+TOKEN
    + (profId ? '&profession_id='+encodeURIComponent(profId) : '')
    + (force ? '&force=true' : '');
  try {{
    const r = await fetch(url, {{method:'POST'}});
    const d = await r.json();
    if (d.ok) {{
      const nb = Object.keys(d.results || {{}}).length;
      alert(d.message || ('\u2713 ' + nb + ' profession(s) traitée(s)'));
      if (!d.message) location.reload();
    }} else {{
      alert('Erreur: ' + (d.detail || JSON.stringify(d)));
    }}
  }} catch(e) {{
    alert('Erreur: ' + e.message);
  }}
}}
</script>
</body></html>""")


@router.post("/admin/professions/scoring")
async def update_scoring(token: str = "", request: Request = None):
    _require_admin(token)
    data = await request.json()
    allowed = {"w_visibilite", "w_conseil_ia", "w_concurrence", "w_valeur"}
    updates = {k: float(v) for k, v in data.items() if k in allowed}
    with SessionLocal() as db:
        db_update_scoring_config(db, updates)
    return JSONResponse({"ok": True})


@router.get("/admin/professions/qualify-status")
def qualify_status(token: str = "", profs: str = ""):
    _require_admin(token)
    from ...scheduler import _sirene_qualify_state
    from ...database import db_segment_stats
    from ...models import SireneSegmentDB
    from sqlalchemy import func
    state = _sirene_qualify_state()
    prof_ids = [p.strip() for p in profs.split(",") if p.strip()] if profs else []
    with SessionLocal() as db:
        total = db_sirene_count(db)
        seg_stats = db_segment_stats(db)
        by_prof = {pid: db_sirene_count(db, profession_id=pid) for pid in prof_ids}
        # Segments done/total par profession (uniquement celles demandées)
        segs_by_prof = {}
        for pid in prof_ids:
            rows = (db.query(SireneSegmentDB.status, func.count(SireneSegmentDB.id))
                    .filter(SireneSegmentDB.profession_id == pid)
                    .group_by(SireneSegmentDB.status).all())
            counts = {r[0]: r[1] for r in rows}
            segs_by_prof[pid] = {
                "done":  counts.get("done", 0),
                "total": sum(counts.values()),
            }
    return JSONResponse({
        "total":        total,
        "done":         state.get("done", True),
        "running":      state.get("running", False),
        "by_prof":      by_prof,
        "segs_by_prof": segs_by_prof,
    })


@router.post("/admin/professions/qualify")
async def launch_qualify(token: str = "", request: Request = None):
    _require_admin(token)
    body = {}
    if request:
        try:
            body = await request.json()
        except Exception:
            pass
    profession_ids = body.get("profession_ids") or None  # None = toutes les actives
    if profession_ids is not None and not isinstance(profession_ids, list):
        profession_ids = None
    with SessionLocal() as db:
        profs = [p for p in db_list_professions(db) if p.actif]
        if profession_ids:
            profs = [p for p in profs if p.id in profession_ids]
    if not profs:
        from fastapi import HTTPException
        raise HTTPException(400, "Aucune profession active dans la sélection")
    import threading
    from ...scheduler import run_sirene_qualify
    t = threading.Thread(target=run_sirene_qualify,
                         kwargs={"profession_ids": profession_ids}, daemon=True)
    t.start()
    log.info(f"Qualification SIRENE lancée pour {len(profs)} professions: {[p.id for p in profs]}")
    return JSONResponse({"ok": True, "message": f"✓ Qualification lancée pour {len(profs)} profession(s)"})


@router.get("/admin/sirene/segments")
def sirene_segments_page(token: str = "", status: str = "", q: str = ""):
    _require_admin(token)
    TOKEN = token
    with SessionLocal() as db:
        stats = db_segment_stats(db)
        segments = db_segment_list(db, status=status or None, limit=200)

    status_colors = {
        "pending": ("#fef3c7","#92400e","En attente"),
        "running": ("#dbeafe","#1e40af","En cours"),
        "done":    ("#d1fae5","#065f46","Terminé"),
        "error":   ("#fee2e2","#991b1b","Erreur"),
    }

    rows = []
    for seg in segments:
        sc = status_colors.get(seg.status, ("#f3f4f6","#374151", seg.status))
        badge = f'<span style="padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;background:{sc[0]};color:{sc[1]}">{sc[2]}</span>'
        last_fetch = seg.last_fetched_at.strftime("%d/%m %H:%M") if seg.last_fetched_at else "—"
        last_date  = seg.last_date_creation or "—"
        err_cell   = f'<span title="{seg.error_msg or ""}" style="color:#dc2626;font-size:11px">⚠ {(seg.error_msg or "")[:40]}</span>' if seg.error_msg else ""
        rows.append(f"""<tr>
          <td style="padding:6px 8px;font-size:12px;font-weight:500">{seg.profession_id}</td>
          <td style="padding:6px 8px;font-size:12px;font-family:monospace">{seg.code_naf}</td>
          <td style="padding:6px 8px;font-size:12px;text-align:center">{seg.departement}</td>
          <td style="padding:6px 8px;font-size:12px;text-align:right">{seg.score:.3f}</td>
          <td style="padding:6px 8px;text-align:center">{badge}</td>
          <td style="padding:6px 8px;font-size:12px;text-align:right">{seg.nb_results or 0:,}</td>
          <td style="padding:6px 8px;font-size:12px;text-align:right">{seg.nb_inserted or 0:,}</td>
          <td style="padding:6px 8px;font-size:12px;color:#6b7280">{last_fetch}</td>
          <td style="padding:6px 8px;font-size:12px;color:#6b7280">{last_date}</td>
          <td style="padding:6px 8px">{err_cell}</td>
        </tr>""")

    rows_html = "\n".join(rows) if rows else '<tr><td colspan="10" style="padding:20px;text-align:center;color:#9ca3af">Aucun segment — lancez une qualification</td></tr>'

    filter_tabs = ""
    for skey, (bg, fg, label) in status_colors.items():
        cnt = stats.get(skey, 0)
        active_style = f"border-bottom:2px solid {fg};" if status == skey else ""
        filter_tabs += f'<a href="/admin/sirene/segments?token={TOKEN}&status={skey}" style="text-decoration:none;padding:6px 14px;font-size:12px;font-weight:600;color:{fg};{active_style}">{label} ({cnt:,})</a>'

    nav = admin_nav(TOKEN)
    total_segs  = stats.get("total_segments", 0)
    total_susp  = stats.get("total_suspects", 0)
    pending     = stats.get("pending", 0)
    done_segs   = stats.get("done", 0)
    error_segs  = stats.get("error", 0)

    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>SIRENE — Segments</title>
<style>
  body{{font-family:system-ui,sans-serif;margin:0;background:#f9fafb;color:#111}}
  .topbar{{background:#1e293b;color:#f8fafc;padding:10px 24px;display:flex;align-items:center;gap:20px}}
  .topbar a{{color:#94a3b8;text-decoration:none;font-size:13px}}
  .card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin:16px 24px}}
  table{{width:100%;border-collapse:collapse}}
  th{{background:#f1f5f9;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;padding:8px;text-align:left;color:#64748b;position:sticky;top:0}}
  tr:hover td{{background:#f8fafc}}
  .stat-box{{display:inline-flex;flex-direction:column;align-items:center;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 20px;min-width:110px}}
  .stat-val{{font-size:22px;font-weight:700;color:#1e293b}}
  .stat-lbl{{font-size:11px;color:#64748b;margin-top:2px}}
  .btn{{padding:7px 16px;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;border:none}}
  .btn-blue{{background:#2563eb;color:#fff}}.btn-blue:hover{{background:#1d4ed8}}
  .btn-gray{{background:#e5e7eb;color:#374151}}.btn-gray:hover{{background:#d1d5db}}
</style></head><body>
<div class="topbar">
  <strong style="font-size:15px;color:#f8fafc">PRESENCE IA</strong>
  {nav}
</div>

<div style="padding:20px 24px 0">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
    <h2 style="margin:0;font-size:18px">Segments SIRENE</h2>
    <div style="display:flex;gap:8px">
      <button class="btn btn-blue" onclick="runNext()">&#9654; Exécuter prochain</button>
      <a href="/admin/sirene/segments?token={TOKEN}" class="btn btn-gray">Rafraîchir</a>
    </div>
  </div>

  <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px">
    <div class="stat-box"><span class="stat-val">{total_segs:,}</span><span class="stat-lbl">Total segments</span></div>
    <div class="stat-box"><span class="stat-val" style="color:#d97706">{pending:,}</span><span class="stat-lbl">En attente</span></div>
    <div class="stat-box"><span class="stat-val" style="color:#059669">{done_segs:,}</span><span class="stat-lbl">Terminés</span></div>
    <div class="stat-box"><span class="stat-val" style="color:#dc2626">{error_segs:,}</span><span class="stat-lbl">Erreurs</span></div>
    <div class="stat-box"><span class="stat-val" style="color:#2563eb">{total_susp:,}</span><span class="stat-lbl">Suspects total</span></div>
  </div>

  <div class="card" style="padding:0;overflow:hidden">
    <div style="display:flex;gap:0;border-bottom:1px solid #e5e7eb;padding:0 8px">
      <a href="/admin/sirene/segments?token={TOKEN}" style="text-decoration:none;padding:6px 14px;font-size:12px;font-weight:600;color:#374151;{'border-bottom:2px solid #374151;' if not status else ''}">Tous ({total_segs:,})</a>
      {filter_tabs}
    </div>
    <div style="overflow-x:auto;max-height:65vh;overflow-y:auto">
    <table>
      <thead><tr>
        <th>Profession</th><th>NAF</th><th style="text-align:center">Dept</th>
        <th style="text-align:right">Score</th><th style="text-align:center">Statut</th>
        <th style="text-align:right">Résultats</th><th style="text-align:right">Insérés</th>
        <th>Dernier fetch</th><th>Dernière date</th><th>Erreur</th>
      </tr></thead>
      <tbody id="seg-tbody">{rows_html}</tbody>
    </table>
    </div>
  </div>
</div>

<div id="toast" style="display:none;position:fixed;bottom:24px;right:24px;background:#1e293b;color:#f8fafc;padding:10px 20px;border-radius:8px;font-size:13px;z-index:1000"></div>

<script>
const TOKEN = '{TOKEN}';
function toast(msg, ok=true) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.background = ok ? '#065f46' : '#991b1b';
  t.style.display = 'block';
  setTimeout(() => t.style.display='none', 3500);
}}
async function runNext() {{
  const r = await fetch('/admin/sirene/run-next?token='+TOKEN, {{method:'POST'}});
  const d = await r.json();
  if (d.ok) {{
    toast(d.message || 'Segment exécuté');
    setTimeout(() => location.reload(), 1200);
  }} else {{
    toast(d.detail || 'Erreur', false);
  }}
}}

</script>
</body></html>"""
    return HTMLResponse(html)


@router.post("/admin/sirene/generate-keywords")
def sirene_generate_keywords(token: str = "", profession_id: str = "", force: bool = False):
    """Génère mots_cles_sirene via LLM.
    - profession_id fourni : exécution synchrone (1 profession, rapide).
    - Sans profession_id : lancé en arrière-plan (283 professions, long)."""
    _require_admin(token)
    import threading
    from ...sirene_keywords import generate_sirene_keywords

    if profession_id:
        # 1 profession → synchrone, réponse immédiate
        with SessionLocal() as db:
            results = generate_sirene_keywords(db, profession_id=profession_id, force=force)
        return JSONResponse({"ok": True, "results": results})
    else:
        # Toutes les professions → arrière-plan pour éviter timeout nginx
        def _do():
            with SessionLocal() as db:
                generate_sirene_keywords(db, force=force)
        threading.Thread(target=_do, daemon=True).start()
        return JSONResponse({"ok": True, "results": {}, "message": "Génération lancée en arrière-plan — recharge la page dans quelques minutes"})


@router.post("/admin/sirene/run-next")
def sirene_run_next(token: str = ""):
    _require_admin(token)
    import threading
    from ...sirene import run_next_segment as _run_next
    def _do():
        with SessionLocal() as db:
            _run_next(db)
    threading.Thread(target=_do, daemon=True).start()
    return JSONResponse({"ok": True, "message": "Segment lancé en arrière-plan"})


NJ_LABEL = {
    "1000": "EI", "1100": "Micro-entreprise", "1200": "Pers. physique",
    "5499": "SARL", "5720": "EURL", "5710": "SAS", "5308": "SASU",
    "6532": "SELARL",
}

@router.get("/admin/suspects", response_class=HTMLResponse)
def suspects_page(token: str = "", profession_id: str = "", dept: str = "",
                  search: str = "", page: int = 1):
    _require_admin(token)
    per_page = 100

    with SessionLocal() as db:
        total, items = db_suspects_list(
            db, profession_id=profession_id or None,
            dept=dept or None, search=search or None,
            page=page, per_page=per_page
        )
        # Label de la profession
        if profession_id:
            from ...models import ProfessionDB
            prof = db.query(ProfessionDB).filter_by(id=profession_id).first()
            prof_label = prof.label if prof else profession_id
        else:
            prof_label = "Tous métiers"

    total_pages = max(1, (total + per_page - 1) // per_page)

    def page_link(p, label=None):
        label = label or str(p)
        active = "font-weight:700;color:#1d4ed8;" if p == page else "color:#6b7280;"
        return f'<a href="/admin/suspects?token={token}&profession_id={profession_id}&dept={dept}&search={search}&page={p}" style="text-decoration:none;padding:4px 8px;{active}">{label}</a>'

    pages_html = page_link(max(1, page-1), "‹")
    for p in range(max(1, page-2), min(total_pages+1, page+3)):
        pages_html += page_link(p)
    pages_html += page_link(min(total_pages, page+1), "›")

    rows = []
    for s in items:
        nj = NJ_LABEL.get(s.nature_juridique or "", s.nature_juridique or "—")
        enrichi = '<span style="color:#16a34a">✓</span>' if s.enrichi_at else '<span style="color:#d1d5db">—</span>'
        contactable = '<span style="color:#16a34a">✓</span>' if s.contactable else '<span style="color:#d1d5db">—</span>'
        rows.append(f"""<tr>
          <td style="padding:6px 8px;font-size:11px;color:#9ca3af;font-family:monospace">{s.id}</td>
          <td style="padding:6px 8px;font-size:12px;font-weight:500">{s.raison_sociale}</td>
          <td style="padding:6px 8px;font-size:12px">{s.ville or "—"}</td>
          <td style="padding:6px 8px;font-size:12px;text-align:center">{s.departement or "—"}</td>
          <td style="padding:6px 8px;font-size:11px;color:#6b7280">{nj}</td>
          <td style="padding:6px 8px;font-size:11px;color:#6b7280">{s.date_creation or "—"}</td>
          <td style="padding:6px 8px;text-align:center">{enrichi}</td>
          <td style="padding:6px 8px;text-align:center">{contactable}</td>
        </tr>""")

    rows_html = "\n".join(rows) if rows else '<tr><td colspan="8" style="padding:24px;text-align:center;color:#9ca3af">Aucun suspect trouvé</td></tr>'
    nav = admin_nav(token, "professions")

    qualify_btn = ""
    if profession_id and total == 0:
        qualify_btn = f'<a href="/admin/professions?token={token}" onclick="..." style="background:#e94560;color:#fff;padding:8px 16px;border-radius:6px;font-size:13px;font-weight:600;text-decoration:none">▶ Lancer la qualification</a>'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>Suspects — {prof_label}</title>
{nav}
<style>
body{{font-family:system-ui,sans-serif;background:#f9fafb;color:#111;margin:0}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin:16px 24px}}
table{{width:100%;border-collapse:collapse}}
th{{background:#f1f5f9;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;padding:8px;text-align:left;color:#64748b;position:sticky;top:0}}
tr:hover td{{background:#f8fafc}}
input[type=text],select{{border:1px solid #d1d5db;border-radius:6px;padding:6px 10px;font-size:13px;outline:none}}
input:focus,select:focus{{border-color:#e94560}}
</style></head><body>
<div style="padding:20px 24px 0">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap">
    <a href="/admin/professions?token={token}" style="color:#6b7280;text-decoration:none;font-size:13px">← Référentiel</a>
    <h2 style="margin:0;font-size:18px">{prof_label}
      <span style="font-size:13px;font-weight:400;color:#6b7280;margin-left:8px">{total:,} suspects</span>
    </h2>
    {qualify_btn}
  </div>

  <form method="get" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
    <input type="hidden" name="token" value="{token}">
    <input type="hidden" name="profession_id" value="{profession_id}">
    <input type="text" name="search" value="{search}" placeholder="Rechercher (nom, ville)..." style="width:220px">
    <input type="text" name="dept" value="{dept}" placeholder="Département (ex: 75)" style="width:120px">
    <button type="submit" style="background:#e94560;color:#fff;border:none;border-radius:6px;padding:7px 14px;font-size:13px;cursor:pointer">Filtrer</button>
    {"" if not (search or dept) else f'<a href="/admin/suspects?token={token}&profession_id={profession_id}" style="padding:7px 12px;font-size:13px;color:#6b7280;text-decoration:none;border:1px solid #d1d5db;border-radius:6px">Réinitialiser</a>'}
  </form>

  <div class="card" style="padding:0;overflow:hidden">
    <div style="overflow-x:auto;max-height:70vh;overflow-y:auto">
    <table>
      <thead><tr>
        <th>SIRET</th><th>Raison sociale</th><th>Ville</th>
        <th style="text-align:center">Dept</th><th>Forme jur.</th>
        <th>Date création</th><th style="text-align:center">Enrichi</th>
        <th style="text-align:center">Contactable</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    <div style="padding:10px 16px;display:flex;align-items:center;justify-content:space-between;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280">
      <span>Page {page} / {total_pages} · {total:,} résultats</span>
      <div>{pages_html}</div>
    </div>
  </div>
</div>
</body></html>""")


@router.post("/admin/professions/{prof_id}")
async def update_profession(prof_id: str, token: str = "", request: Request = None):
    _require_admin(token)
    data = await request.json()
    allowed = {"score_visibilite", "score_conseil_ia", "score_concurrence", "valeur_client", "actif",
               "codes_naf", "termes_recherche", "notes_ia", "problematique", "mission"}
    updates = {k: v for k, v in data.items() if k in allowed}
    for field in ("codes_naf", "termes_recherche"):
        if field in updates and isinstance(updates[field], list):
            updates[field] = json.dumps(updates[field], ensure_ascii=False)
    with SessionLocal() as db:
        obj = db_update_profession(db, prof_id, updates)
    if not obj:
        from fastapi import HTTPException
        raise HTTPException(404, "Profession introuvable")
    return JSONResponse({"ok": True})
