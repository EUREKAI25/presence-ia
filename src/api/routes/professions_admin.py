"""
Admin — Référentiel métiers + pondération scoring.
GET  /admin/professions          → liste avec scores + filtres
POST /admin/professions/{id}     → modifier une profession (scores, actif...)
POST /admin/professions/scoring  → modifier les poids du score global
"""
import json, logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...database import (SessionLocal, db_list_professions, db_update_profession,
                         db_get_scoring_config, db_update_scoring_config, db_score_global)
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
def professions_page(token: str = "", cat: str = "", q: str = "", request: Request = None):
    _require_admin(token)
    with SessionLocal() as db:
        profs = db_list_professions(db)
        cfg   = db_get_scoring_config(db)

    # Filtres
    cats = sorted(set(p.categorie for p in profs))
    if cat:
        profs = [p for p in profs if p.categorie == cat]
    if q:
        ql = q.lower()
        profs = [p for p in profs if ql in p.label.lower() or ql in (p.categorie or "").lower()]

    # Trier par score global desc
    profs_scored = [(p, db_score_global(p, cfg)) for p in profs]
    profs_scored.sort(key=lambda x: x[1], reverse=True)

    # Filtres HTML
    cat_opts = "".join(
        f'<option value="{c}" {"selected" if cat==c else ""}>{c}</option>'
        for c in cats
    )

    # Tableau
    rows_html = ""
    for p, sg in profs_scored:
        actif_badge = (
            '<span style="background:#dcfce7;color:#166534;font-size:10px;padding:1px 6px;border-radius:10px">actif</span>'
            if p.actif else
            '<span style="background:#f3f4f6;color:#9ca3af;font-size:10px;padding:1px 6px;border-radius:10px">inactif</span>'
        )
        naf = ", ".join(json.loads(p.codes_naf or "[]")[:3]) or "—"
        termes = ", ".join(json.loads(p.termes_recherche or "[]")[:3]) or "—"
        vc = f"{p.valeur_client:,}€".replace(",", " ") if p.valeur_client else "—"
        sg_color = "#16a34a" if sg >= 7 else ("#d97706" if sg >= 4 else "#dc2626")

        rows_html += f"""
        <tr style="border-bottom:1px solid #f3f4f6" onclick="editProf('{p.id}',{p.score_visibilite or 'null'},{p.score_conseil_ia or 'null'},{p.valeur_client or 'null'},{'true' if p.actif else 'false'},'{p.label}')">
          <td style="padding:8px 10px;font-size:12px;font-weight:600">{p.label}</td>
          <td style="padding:8px 6px;font-size:11px;color:#6b7280">{p.categorie}</td>
          <td style="padding:8px 6px">{_bar(p.score_visibilite)}</td>
          <td style="padding:8px 6px">{_bar(p.score_conseil_ia, color="#8b5cf6")}</td>
          <td style="padding:8px 6px;font-size:11px;color:#374151">{vc}</td>
          <td style="padding:8px 6px;font-weight:700;color:{sg_color};font-size:13px">{sg}</td>
          <td style="padding:8px 6px;font-size:10px;color:#9ca3af;max-width:120px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">{naf}</td>
          <td style="padding:8px 6px;font-size:10px;color:#9ca3af;max-width:120px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">{termes}</td>
          <td style="padding:8px 6px">{actif_badge}</td>
        </tr>"""

    nav = admin_nav(token, "professions")
    return HTMLResponse(f"""<!DOCTYPE html><html><head>
<meta charset="utf-8"><title>Référentiel métiers</title>
{nav}
<style>
body{{font-family:system-ui,sans-serif;background:#f9fafb;color:#111}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px}}
input,select{{border:1px solid #d1d5db;border-radius:6px;padding:6px 10px;font-size:13px;outline:none}}
input:focus,select:focus{{border-color:#e94560}}
.btn{{background:#e94560;color:#fff;border:none;border-radius:6px;padding:8px 16px;font-size:13px;cursor:pointer;font-weight:600}}
.btn:hover{{background:#c73652}}
.btn-sm{{padding:5px 10px;font-size:12px}}
.btn-secondary{{background:#6b7280}}
.btn-secondary:hover{{background:#4b5563}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;font-size:11px;color:#6b7280;font-weight:600;padding:8px 10px;border-bottom:2px solid #e5e7eb;white-space:nowrap}}
tr:hover{{background:#fafafa;cursor:pointer}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:2000;align-items:center;justify-content:center}}
.modal.show{{display:flex}}
.modal-box{{background:#fff;border-radius:10px;padding:24px;width:420px;max-width:95vw}}
</style>
</head><body>
<div style="padding:24px">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
    <h1 style="font-size:18px;font-weight:700;margin:0">Référentiel métiers
      <span style="font-size:13px;color:#6b7280;font-weight:400;margin-left:8px">{len(profs_scored)} professions</span>
    </h1>
    <button class="btn btn-sm" onclick="document.getElementById('scoring-panel').classList.toggle('hidden')">⚙️ Pondération</button>
  </div>

  <!-- Pondération scoring -->
  <div id="scoring-panel" class="card hidden" style="margin-bottom:16px">
    <h3 style="margin:0 0 12px;font-size:14px;font-weight:700">Pondération du score global</h3>
    <form id="scoring-form" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <label style="font-size:12px">Visibilité (actuel: {cfg.w_visibilite})
        <input name="w_visibilite" type="number" step="0.05" min="0" max="1" value="{cfg.w_visibilite}" style="width:100%;margin-top:4px">
      </label>
      <label style="font-size:12px">Conseil IA (actuel: {cfg.w_conseil_ia})
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

  <!-- Filtres -->
  <div class="card" style="padding:12px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
    <input type="text" placeholder="Recherche..." value="{q}"
      onkeydown="if(event.key==='Enter'){{location.href='/admin/professions?token={token}&cat='+encodeURIComponent(document.getElementById('cat-sel').value)+'&q='+encodeURIComponent(this.value)}}"
      style="width:200px" id="q-input">
    <select id="cat-sel" onchange="location.href='/admin/professions?token={token}&cat='+encodeURIComponent(this.value)+'&q='+encodeURIComponent(document.getElementById('q-input').value)">
      <option value="">Toutes catégories</option>
      {cat_opts}
    </select>
    <span style="font-size:11px;color:#9ca3af;margin-left:auto">Score = visibilité×{cfg.w_visibilite} + conseil_ia×{cfg.w_conseil_ia} + concurrence×{cfg.w_concurrence} + valeur×{cfg.w_valeur}</span>
  </div>

  <!-- Tableau -->
  <div class="card" style="padding:0;overflow-x:auto">
    <table>
      <thead>
        <tr>
          <th>Métier</th><th>Catégorie</th>
          <th>Visibilité</th><th>Conseil IA</th>
          <th>Valeur client</th><th>Score</th>
          <th>NAF</th><th>Termes</th><th>Statut</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>

<!-- Modal édition -->
<div class="modal" id="edit-modal">
  <div class="modal-box">
    <h3 style="margin:0 0 16px;font-size:15px;font-weight:700" id="modal-title">Modifier</h3>
    <input type="hidden" id="edit-id">
    <div style="display:grid;gap:12px">
      <label style="font-size:12px">Score visibilité (1-10)
        <input id="edit-visibilite" type="number" min="1" max="10" style="width:100%;margin-top:4px">
      </label>
      <label style="font-size:12px">Score conseil IA (1-10)
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
      <button class="btn btn-sm btn-secondary" onclick="closeModal()">Annuler</button>
      <span id="edit-msg" style="font-size:12px;color:#16a34a;align-self:center"></span>
    </div>
  </div>
</div>

<script>
const TOKEN = '{token}';
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
  const id = document.getElementById('edit-id').value;
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
async function saveScoringWeights() {{
  const form = document.getElementById('scoring-form');
  const data = Object.fromEntries(new FormData(form).entries());
  Object.keys(data).forEach(k => data[k] = parseFloat(data[k]));
  const r = await fetch(`/admin/professions/scoring?token=${{TOKEN}}`, {{
    method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)
  }});
  if(r.ok) {{ document.getElementById('scoring-msg').textContent='✓ Enregistré'; setTimeout(()=>location.reload(),800); }}
}}
document.getElementById('edit-modal').addEventListener('click', function(e) {{
  if(e.target===this) closeModal();
}});
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


@router.post("/admin/professions/{prof_id}")
async def update_profession(prof_id: str, token: str = "", request: Request = None):
    _require_admin(token)
    data = await request.json()
    allowed = {"score_visibilite", "score_conseil_ia", "score_concurrence", "valeur_client", "actif",
               "codes_naf", "termes_recherche", "notes_ia", "problematique", "mission"}
    updates = {k: v for k, v in data.items() if k in allowed}
    # Sérialiser les listes en JSON si nécessaire
    for field in ("codes_naf", "termes_recherche"):
        if field in updates and isinstance(updates[field], list):
            updates[field] = json.dumps(updates[field], ensure_ascii=False)
    with SessionLocal() as db:
        obj = db_update_profession(db, prof_id, updates)
    if not obj:
        from fastapi import HTTPException
        raise HTTPException(404, "Profession introuvable")
    return JSONResponse({"ok": True})
