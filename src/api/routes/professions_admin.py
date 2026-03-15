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
                         db_sirene_count)
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

    # Comptages SIRENE par profession (une seule requête par profession)
    with SessionLocal() as db2:
        sirene_counts = {p.id: db_sirene_count(db2, profession_id=p.id) for p, _ in profs_scored}

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
            '<span style="background:#dcfce7;color:#166534;font-size:10px;padding:1px 6px;border-radius:10px">actif</span>'
            if p.actif else
            '<span style="background:#f3f4f6;color:#9ca3af;font-size:10px;padding:1px 6px;border-radius:10px">inactif</span>'
        )
        naf    = ", ".join(json.loads(p.codes_naf or "[]")[:3]) or "—"
        termes = ", ".join(json.loads(p.termes_recherche or "[]")[:3]) or "—"
        vc     = f"{p.valeur_client:,}€".replace(",", " ") if p.valeur_client else "—"
        sg_color = "#16a34a" if sg >= 7 else ("#d97706" if sg >= 4 else "#dc2626")
        actif_int = 1 if p.actif else 0
        nb_sirene = sirene_counts.get(p.id, 0)
        sirene_cell = (f'<span style="font-size:12px;font-weight:600;color:#1d4ed8">{nb_sirene:,}</span>'
                       if nb_sirene else '<span style="font-size:11px;color:#d1d5db">—</span>')

        rows_html += f"""
        <tr data-id="{p.id}" data-actif="{actif_int}"
            data-label="{p.label}" data-cat="{p.categorie or ''}"
            data-vis="{p.score_visibilite or 0}" data-conseil="{p.score_conseil_ia or 0}"
            data-valeur="{p.valeur_client or 0}" data-score="{sg}"
            style="border-bottom:1px solid #f3f4f6"
            onclick="editProf('{p.id}',{p.score_visibilite or 'null'},{p.score_conseil_ia or 'null'},{p.valeur_client or 'null'},{'true' if p.actif else 'false'},'{p.label.replace("'", "\\'")}')">
          <td style="padding:8px 10px"><input type="checkbox" class="row-cb" data-id="{p.id}" onclick="event.stopPropagation()" style="margin-right:6px"><span style="font-size:12px;font-weight:600">{p.label}</span></td>
          <td style="padding:8px 6px;font-size:11px;color:#6b7280">{p.categorie}</td>
          <td style="padding:8px 6px">{_bar(p.score_visibilite)}</td>
          <td style="padding:8px 6px">{_bar(p.score_conseil_ia, color="#8b5cf6")}</td>
          <td style="padding:8px 6px;font-size:11px;color:#374151">{vc}</td>
          <td style="padding:8px 6px;font-weight:700;color:{sg_color};font-size:13px">{sg}</td>
          <td style="padding:8px 6px;font-size:10px;color:#9ca3af;max-width:100px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">{naf}</td>
          <td style="padding:8px 6px;font-size:10px;color:#9ca3af;max-width:100px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">{termes}</td>
          <td style="padding:8px 6px">{actif_badge}</td>
          <td style="padding:8px 6px;text-align:right">{sirene_cell}</td>
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
      <span style="font-size:13px;color:#6b7280;font-weight:400;margin-left:8px">{len(profs_scored)} professions · {nb_actifs} actives</span>
    </h1>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
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
    <div style="display:flex;gap:6px;margin-left:auto">
      <button class="btn btn-sm btn-outline" onclick="selectAll(true)">Tout cocher</button>
      <button class="btn btn-sm btn-outline" onclick="selectAll(false)">Tout décocher</button>
      <button class="btn btn-sm btn-green" onclick="bulkToggle(true)">Activer sélection</button>
      <button class="btn btn-sm btn-gray" onclick="bulkToggle(false)">Désactiver sélection</button>
    </div>
  </div>

  <!-- Tableau -->
  <div class="card" style="padding:0;overflow-x:auto">
    <table id="prof-table">
      <thead>
        <tr>
          <th onclick="sortTable('label')">Métier <span class="sort-arrow">↕</span></th>
          <th onclick="sortTable('cat')">Catégorie <span class="sort-arrow">↕</span></th>
          <th onclick="sortTable('vis')" title="Dépendance à la recherche en ligne immédiate (Google, Maps)">Dép. recherche <span class="sort-arrow">↕</span></th>
          <th onclick="sortTable('conseil')" title="Dépendance au conseil IA / comparaison avant achat (ChatGPT, avis...)">Dép. conseil IA <span class="sort-arrow">↕</span></th>
          <th onclick="sortTable('valeur')">Valeur client <span class="sort-arrow">↕</span></th>
          <th onclick="sortTable('score')">Score ▼ <span class="sort-arrow">↕</span></th>
          <th>NAF</th>
          <th>Termes</th>
          <th onclick="sortTable('actif')">Statut <span class="sort-arrow">↕</span></th>
          <th style="text-align:right">Suspects SIRENE</th>
        </tr>
      </thead>
      <tbody id="prof-tbody">{rows_html}</tbody>
    </table>
  </div>
  <div id="bulk-msg" style="margin-top:8px;font-size:12px;color:#16a34a;min-height:16px"></div>
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
      <label style="font-size:12px;display:flex;align-items:center;gap:8px">
        <input id="edit-actif" type="checkbox"> Actif (inclure dans la prospection)
      </label>
    </div>
    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn btn-sm" onclick="saveProf()">Enregistrer</button>
      <button class="btn btn-sm btn-gray" onclick="closeModal()">Annuler</button>
      <span id="edit-msg" style="font-size:12px;color:#16a34a;align-self:center"></span>
    </div>
  </div>
</div>

<!-- Modal qualification -->
<div class="modal" id="qualify-modal">
  <div class="modal-box">
    <h3 style="margin:0 0 12px;font-size:15px;font-weight:700">▶ Lancer la qualification SIRENE</h3>
    <p style="font-size:13px;color:#374151;margin:0 0 8px">Cette opération va :</p>
    <ol style="font-size:12px;color:#374151;margin:0 0 16px;padding-left:18px;line-height:1.8">
      <li>Interroger SIRENE pour chaque profession <strong>active</strong></li>
      <li>Recenser les établissements par ville</li>
      <li>Stocker les suspects dans la base</li>
    </ol>
    <div id="qualify-actifs-info" style="font-size:12px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:10px;margin-bottom:16px;color:#166534"></div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm btn-green" id="qualify-confirm-btn" onclick="launchQualify()">Confirmer et lancer</button>
      <button class="btn btn-sm btn-gray" onclick="document.getElementById('qualify-modal').classList.remove('show')">Annuler</button>
      <span id="qualify-msg" style="font-size:12px;color:#16a34a;align-self:center"></span>
    </div>
  </div>
</div>

<script>
const TOKEN = '{token}';
let sortCol = 'score', sortAsc = false;

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

// ── Sélection ────────────────────────────────────
function selectAll(checked) {{
  document.querySelectorAll('.row-cb').forEach(cb => cb.checked = checked);
}}
function getSelectedIds() {{
  return Array.from(document.querySelectorAll('.row-cb:checked')).map(cb => cb.dataset.id);
}}

// ── Bulk toggle ──────────────────────────────────
async function bulkToggle(actif) {{
  const ids = getSelectedIds();
  if(!ids.length) {{ alert('Aucune ligne sélectionnée'); return; }}
  const msg = document.getElementById('bulk-msg');
  msg.style.color = '#6b7280';
  msg.textContent = `Mise à jour de ${{ids.length}} professions...`;
  let ok = 0;
  for(const id of ids) {{
    const r = await fetch(`/admin/professions/${{id}}?token=${{TOKEN}}`, {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{actif}})
    }});
    if(r.ok) ok++;
  }}
  msg.style.color = '#16a34a';
  msg.textContent = `✓ ${{ok}} professions ${{actif ? 'activées' : 'désactivées'}}`;
  setTimeout(() => location.reload(), 900);
}}

// ── Modal édition ─────────────────────────────────
function editProf(id, vis, conseil, valeur, actif, label) {{
  document.getElementById('edit-id').value = id;
  document.getElementById('modal-title').textContent = 'Modifier — ' + label;
  document.getElementById('edit-visibilite').value = vis || '';
  document.getElementById('edit-conseil').value = conseil || '';
  document.getElementById('edit-valeur').value = valeur || '';
  document.getElementById('edit-actif').checked = actif;
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
    actif:            document.getElementById('edit-actif').checked,
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
function openQualify() {{
  const nb = document.querySelectorAll('tr[data-actif="1"]').length;
  document.getElementById('qualify-actifs-info').textContent =
    nb > 0
      ? `${{nb}} professions actives seront qualifi\u00e9es.`
      : '\u26a0\ufe0f Aucune profession active \u2014 activez des m\u00e9tiers en premier.';
  document.getElementById('qualify-confirm-btn').disabled = nb === 0;
  document.getElementById('qualify-modal').classList.add('show');
}}
async function launchQualify() {{
  document.getElementById('qualify-msg').textContent = '⏳ Lancement...';
  document.getElementById('qualify-confirm-btn').disabled = true;
  const r = await fetch(`/admin/professions/qualify?token=${{TOKEN}}`, {{
    method:'POST', headers:{{'Content-Type':'application/json'}}, body: '{{}}'
  }});
  const d = await r.json();
  if(r.ok) {{
    document.getElementById('qualify-msg').style.color = '#16a34a';
    document.getElementById('qualify-msg').textContent = d.message || '✓ Lancé';
  }} else {{
    document.getElementById('qualify-msg').style.color = '#dc2626';
    document.getElementById('qualify-msg').textContent = d.detail || 'Erreur';
  }}
}}
document.getElementById('qualify-modal').addEventListener('click', function(e) {{
  if(e.target===this) this.classList.remove('show');
}});

// Tri par défaut : score desc
sortTable('score');
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


@router.post("/admin/professions/qualify")
async def launch_qualify(token: str = "", request: Request = None):
    _require_admin(token)
    with SessionLocal() as db:
        profs = [p for p in db_list_professions(db) if p.actif]
    if not profs:
        from fastapi import HTTPException
        raise HTTPException(400, "Aucune profession active")
    import threading
    from ...scheduler import run_sirene_qualify
    t = threading.Thread(target=run_sirene_qualify, kwargs={"max_per_naf": 200}, daemon=True)
    t.start()
    log.info(f"Qualification SIRENE lancée en background pour {len(profs)} professions")
    return JSONResponse({"ok": True, "message": f"✓ Qualification lancée pour {len(profs)} professions — résultats visibles dans quelques minutes"})


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
