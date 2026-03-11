"""Admin — Prospection automatique (Google Places + pipeline IA)."""
import csv, io, json, os, uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from ...database import (get_db, db_create_campaign, db_create_prospect, jd,
                          db_get_header,
                          db_list_metier_configs, db_get_metier_config,
                          db_upsert_metier_config, db_delete_metier_config,
                          db_list_ia_query_templates, db_upsert_ia_query_template,
                          db_delete_ia_query_template)
from ...models import (CampaignDB, ProspectDB, ProspectStatus, ProspectionTargetDB)

router = APIRouter(tags=["Admin Prospection"])

_FREQ_LABELS = {
    "daily":    "Quotidien",
    "2x_week":  "2× / semaine",
    "weekly":   "1× / semaine",
    "2x_month": "2× / mois",
    "monthly":  "Mensuel",
}
_FREQ_DAYS = {
    "daily": 1, "2x_week": 3, "weekly": 7, "2x_month": 15, "monthly": 30,
}


def _check_token(request: Request) -> str:
    t = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if t != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Token invalide")
    return t


def _nav(token: str, active: str = "prospection") -> str:
    tabs = [
        ("contacts",    "👥 Contacts"),
        ("offers",      "💶 Offres"),
        ("analytics",   "📊 Analytics"),
        ("evidence",    "📸 Preuves"),
        ("headers",     "🖼 Headers"),
        ("content",     "✏️ Contenus"),
        ("send-queue",  "📤 Envoi"),
        ("scan",        "🔍 Test ponctuel"),
        ("prospection", "🎯 Prospection"),
    ]
    links = "".join(
        f'<a href="/admin/{t}?token={token}" style="padding:10px 18px;border-radius:6px;text-decoration:none;'
        f'font-size:13px;font-weight:{"bold" if t==active else "normal"};'
        f'background:{"#e94560" if t==active else "transparent"};color:#fff">{label}</a>'
        for t, label in tabs
    )
    return (f'<div style="background:#0a0a15;border-bottom:1px solid #1a1a2e;padding:0 20px;'
            f'display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
            f'<a href="/admin?token={token}" style="color:#e94560;font-weight:bold;font-size:15px;'
            f'padding:12px 16px 12px 0;text-decoration:none">⚡ PRESENCE_IA</a>'
            f'{links}</div>')


def _next_run(target: ProspectionTargetDB) -> str:
    if not target.active:
        return "—"
    if not target.last_run:
        return "Dès maintenant"
    delta = _FREQ_DAYS.get(target.frequency, 7)
    next_dt = target.last_run + timedelta(days=delta)
    now = datetime.utcnow()
    if next_dt <= now:
        return "Dès maintenant"
    diff = (next_dt - now).days
    return "Aujourd'hui" if diff == 0 else f"Dans {diff}j"


def _btn(color: str) -> str:
    return (f"background:transparent;border:1px solid {color};color:{color};"
            f"padding:4px 10px;border-radius:5px;font-size:11px;cursor:pointer;margin-left:4px")


# ── Page principale ────────────────────────────────────────────────────────────

@router.get("/admin/prospection", response_class=HTMLResponse)
def prospection_page(request: Request, db: Session = Depends(get_db)):
    token   = _check_token(request)
    targets = db.query(ProspectionTargetDB).order_by(ProspectionTargetDB.created_at.desc()).all()
    metiers = db_list_metier_configs(db)
    queries = db_list_ia_query_templates(db)

    # ── Tableau ciblages ──
    rows = ""
    for t in targets:
        last   = t.last_run.strftime("%d/%m %Hh%M") if t.last_run else "Jamais"
        next_r = _next_run(t)
        dot    = "🟢" if t.active else "⚫"
        rows += f"""<tr data-id="{t.id}">
  <td style="color:#fff;font-weight:600">{t.name}</td>
  <td style="color:#ccc">{t.city}</td>
  <td style="color:#ccc">{t.profession}</td>
  <td style="color:#9ca3af">{_FREQ_LABELS.get(t.frequency, t.frequency)}</td>
  <td style="color:#9ca3af;text-align:center">{t.max_prospects}</td>
  <td style="color:#9ca3af">{last} {f"({t.last_count} trouvés)" if t.last_count else ""}</td>
  <td style="color:#9ca3af">{next_r}</td>
  <td>{dot}</td>
  <td style="white-space:nowrap">
    <button onclick="runNow('{t.id}',this)" style="{_btn('#2ecc71')}">▶ Lancer</button>
    <button onclick="toggle('{t.id}',{str(t.active).lower()},this)" style="{_btn('#e9a020')}">{"Désactiver" if t.active else "Activer"}</button>
    <button onclick="del_('{t.id}',this)" style="{_btn('#e94560')}">✕</button>
  </td>
</tr>"""

    # ── Tableau métiers ──
    metier_rows = ""
    for m in metiers:
        cities_for_metier = [t.city for t in targets if t.profession.lower() == m.metier.lower()]
        city_tags = "".join(
            f'<span style="background:#1a2a3e;color:#60a5fa;padding:2px 8px;border-radius:4px;'
            f'font-size:11px;margin:2px;display:inline-block">{c}</span>'
            for c in cities_for_metier
        ) or '<span style="color:#555;font-size:11px">aucune ville</span>'
        metier_rows += f"""<tr data-metier="{m.metier}">
  <td style="color:#fff;font-weight:600">{m.metier}</td>
  <td><input type="text" value="{m.problematique}" data-field="problematique" data-metier="{m.metier}"
       style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;border-radius:5px;
              padding:5px 8px;font-size:12px;width:100%" onblur="saveMetier(this)"></td>
  <td><input type="text" value="{m.mission}" data-field="mission" data-metier="{m.metier}"
       style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;border-radius:5px;
              padding:5px 8px;font-size:12px;width:100%" onblur="saveMetier(this)"></td>
  <td>{city_tags}</td>
  <td><button onclick="delMetier('{m.metier}',this)" style="{_btn('#e94560')}">✕</button></td>
</tr>"""

    # ── Liste requêtes IA ──
    query_items = ""
    for q in queries:
        checked = "checked" if q.active else ""
        query_items += f"""<div class="q-row" data-id="{q.id}" style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
  <span style="color:#555;font-size:12px;min-width:20px">{q.order}</span>
  <input type="checkbox" {checked} onchange="toggleQuery('{q.id}',this.checked)"
         style="width:auto;accent-color:#e94560;cursor:pointer">
  <input type="text" value="{q.template}" data-id="{q.id}"
         style="flex:1;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;
                border-radius:5px;padding:7px 10px;font-size:12px;font-family:monospace"
         onblur="saveQuery(this)">
  <button onclick="delQuery('{q.id}',this)" style="{_btn('#e94560')}">✕</button>
</div>"""

    freq_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in _FREQ_LABELS.items())
    target_opts = "".join(f'<option value="{t.id}">{t.name} ({t.profession} / {t.city})</option>' for t in targets)
    metier_opts = "".join(f'<option value="{m.metier}">{m.metier}</option>' for m in metiers)

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prospection — PRESENCE_IA</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
.wrap{{max-width:1200px;margin:0 auto;padding:28px 20px}}
h1{{color:#fff;font-size:20px;margin-bottom:6px}}
.sub{{color:#6b7280;font-size:13px;margin-bottom:28px}}
.card{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:24px;margin-bottom:20px}}
.card h2{{color:#e94560;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:18px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:.8px;
    padding:8px 12px;border-bottom:1px solid #2a2a4e;text-align:left}}
td{{padding:8px 12px;border-bottom:1px solid #1a1a2e;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:rgba(255,255,255,.02)}}
label.f{{display:block;color:#9ca3af;font-size:12px;margin-bottom:5px;margin-top:14px}}
label.f:first-of-type{{margin-top:0}}
input[type=text],input[type=number],select,textarea{{
  width:100%;background:#0f0f1a;border:1px solid #2a2a4e;
  color:#e8e8f0;border-radius:6px;padding:9px 12px;font-size:13px;font-family:inherit}}
input:focus,select:focus,textarea:focus{{outline:none;border-color:#e94560}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
.grid4{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:16px}}
.btn-add{{background:linear-gradient(90deg,#e8355a,#ff7043);color:#fff;border:none;
  padding:11px 24px;border-radius:7px;font-size:13px;font-weight:700;cursor:pointer;margin-top:16px}}
.btn-add:hover{{opacity:.9}}
.btn-sm{{background:#1a2a3e;color:#60a5fa;border:1px solid #2a3a5e;
  padding:6px 14px;border-radius:5px;font-size:12px;cursor:pointer}}
.btn-sm:hover{{background:#1e3a5e}}
.log{{background:#0a0a15;border:1px solid #1a1a2e;border-radius:8px;padding:14px;
  font-family:monospace;font-size:12px;color:#6b7280;min-height:60px;
  max-height:300px;overflow-y:auto;white-space:pre-wrap;margin-top:16px;display:none}}
.log.on{{display:block}}
.hint{{background:#0f0f1a;border:1px solid #2a2a4e;border-radius:6px;
  padding:10px 14px;font-size:11px;color:#6b7280;font-family:monospace;line-height:1.8}}
.placeholder{{color:#e94560}}
.ok{{color:#2ecc71}}.err{{color:#e94560}}.warn{{color:#e9a020}}
.section-title{{color:#9ca3af;font-size:11px;text-transform:uppercase;letter-spacing:1px;
  margin:20px 0 10px;padding-bottom:6px;border-bottom:1px solid #2a2a4e}}
</style>
</head><body>
{_nav(token)}
<div class="wrap">
<h1>🎯 Prospection automatique</h1>
<p class="sub">Google Places → tests IA → suspects qualifiés. Le scheduler vérifie toutes les heures.</p>

<!-- ── SECTION 1 : MÉTIERS ─────────────────────────────────────────── -->
<div class="card">
  <h2>Métiers configurés</h2>
  <p style="color:#6b7280;font-size:12px;margin-bottom:16px">
    Chaque métier définit les placeholders <code style="color:#e94560">{{problematique}}</code>
    et <code style="color:#e94560">{{mission}}</code> utilisés dans les requêtes IA.
    Les champs sont sauvegardés automatiquement à la sortie du champ.
  </p>

  <table>
    <thead><tr>
      <th>Métier</th><th>Problématique</th><th>Mission</th><th>Villes actives</th><th></th>
    </tr></thead>
    <tbody id="metier-tbody">
      {metier_rows or '<tr><td colspan="5" style="color:#555;text-align:center;padding:20px">Aucun métier — ajoutez-en un ci-dessous</td></tr>'}
    </tbody>
  </table>

  <p class="section-title">Ajouter un métier</p>
  <div class="grid3">
    <div>
      <label class="f">Métier</label>
      <input type="text" id="m_metier" placeholder="ex: couvreur">
    </div>
    <div>
      <label class="f">Problématique client</label>
      <input type="text" id="m_probl" placeholder="ex: fuite de toiture">
    </div>
    <div>
      <label class="f">Mission</label>
      <input type="text" id="m_mission" placeholder="ex: refaire ma toiture">
    </div>
  </div>
  <button class="btn-add" onclick="addMetier()">+ Ajouter ce métier</button>
  <div class="log" id="log-metier"></div>
</div>

<!-- ── SECTION 2 : REQUÊTES IA ────────────────────────────────────── -->
<div class="card">
  <h2>Requêtes IA <span style="color:#6b7280;font-size:11px;font-weight:normal">— envoyées à ChatGPT / Claude / Gemini pour chaque prospect</span></h2>

  <div class="hint" style="margin-bottom:16px">
    Placeholders disponibles :
    <span class="placeholder">{{metier}}</span> &nbsp;
    <span class="placeholder">{{ville}}</span> &nbsp;
    <span class="placeholder">{{problematique}}</span> (défini par métier) &nbsp;
    <span class="placeholder">{{mission}}</span> (défini par métier)
  </div>

  <div id="queries-list">{query_items or '<p style="color:#555;font-size:13px">Aucune requête</p>'}</div>

  <div style="display:flex;gap:10px;margin-top:16px;align-items:flex-end">
    <div style="flex:1">
      <label class="f">Nouvelle requête</label>
      <input type="text" id="new_query" placeholder="ex: Quel {metier} pour {mission} à {ville} ?">
    </div>
    <button class="btn-sm" style="margin-bottom:1px" onclick="addQuery()">+ Ajouter</button>
  </div>
  <div class="log" id="log-queries"></div>
</div>

<!-- ── SECTION 3 : CIBLAGES ──────────────────────────────────────── -->
<div class="card">
  <h2>Ciblages configurés</h2>
  <table>
    <thead><tr>
      {"".join(f'<th>{h}</th>' for h in ["Nom","Ville","Métier","Fréquence","Max","Dernier run","Prochain","","Actions"])}
    </tr></thead>
    <tbody>
      {rows or '<tr><td colspan="9" style="color:#555;text-align:center;padding:24px">Aucun ciblage — ajoutez-en un ci-dessous</td></tr>'}
    </tbody>
  </table>
  <div class="log" id="log-run"></div>
</div>

<!-- ── AJOUTER UN CIBLAGE ────────────────────────────────────────── -->
<div class="card">
  <h2>Ajouter un ciblage</h2>
  <div class="grid4">
    <div>
      <label class="f">Nom du ciblage</label>
      <input type="text" id="n_name" placeholder="ex: brest-couvreurs">
    </div>
    <div>
      <label class="f">Ville</label>
      <input type="text" id="n_city" placeholder="ex: Brest">
    </div>
    <div>
      <label class="f">Métier</label>
      <select id="n_prof">
        <option value="">— Sélectionner —</option>
        {metier_opts}
        <option value="__custom__">✏️ Autre…</option>
      </select>
    </div>
    <div id="n_prof_custom_wrap" style="display:none">
      <label class="f">Métier (saisie libre)</label>
      <input type="text" id="n_prof_custom" placeholder="ex: électricien">
    </div>
  </div>
  <div class="grid2" style="margin-top:0">
    <div>
      <label class="f">Fréquence</label>
      <select id="n_freq">{freq_opts}</select>
    </div>
    <div>
      <label class="f">Nb prospects max par run</label>
      <input type="number" id="n_max" value="20" min="1" max="100">
    </div>
  </div>
  <button class="btn-add" onclick="addTarget()">+ Ajouter ce ciblage</button>
  <div class="log" id="log-add"></div>
</div>

<!-- ── IMPORT CSV ────────────────────────────────────────────────── -->
<div class="card">
  <h2>Import CSV de prospects</h2>
  <div class="grid2">
    <div>
      <label class="f">Ciblage cible</label>
      <select id="csv_target">
        <option value="">— Sélectionner —</option>
        {target_opts}
      </select>
    </div>
    <div>
      <label class="f">Fichier CSV</label>
      <input type="file" id="csv_file" accept=".csv">
    </div>
  </div>
  <div class="hint" style="margin-top:12px">
    Colonnes : <span style="color:#e94560">name</span> (obligatoire) —
    city, profession, website, phone, reviews_count (optionnels, héritent du ciblage)
  </div>
  <button class="btn-add" onclick="importCSV()">Importer →</button>
  <div class="log" id="log-csv"></div>
</div>

</div><!-- /wrap -->

<script>
const T = '{token}';

function logTo(id, msg, cls='') {{
  const el = document.getElementById(id);
  el.classList.add('on');
  const pfx = cls==='ok' ? '✅ ' : cls==='err' ? '❌ ' : cls==='warn' ? '⚠️ ' : '▸ ';
  el.textContent += pfx + msg + '\\n';
  el.scrollTop = el.scrollHeight;
}}

// ── Métiers ──

async function addMetier() {{
  const metier = document.getElementById('m_metier').value.trim();
  const probl  = document.getElementById('m_probl').value.trim();
  const miss   = document.getElementById('m_mission').value.trim();
  if (!metier) {{ alert('Le métier est obligatoire.'); return; }}
  const r = await fetch('/api/admin/prospection/metiers', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, metier, problematique:probl, mission:miss }})
  }});
  if (r.ok) {{ logTo('log-metier','Métier sauvegardé','ok'); setTimeout(()=>location.reload(),600); }}
  else {{ const d=await r.json(); logTo('log-metier', d.detail||'Erreur','err'); }}
}}

async function saveMetier(input) {{
  const metier = input.dataset.metier;
  const field  = input.dataset.field;
  const row    = input.closest('tr');
  const probl  = row.querySelector('[data-field=problematique]').value;
  const miss   = row.querySelector('[data-field=mission]').value;
  const r = await fetch('/api/admin/prospection/metiers', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, metier, problematique:probl, mission:miss }})
  }});
  input.style.borderColor = r.ok ? '#2ecc71' : '#e94560';
  setTimeout(()=>{{ input.style.borderColor=''; }}, 1500);
}}

async function delMetier(metier, btn) {{
  if (!confirm(`Supprimer le métier "${{metier}}" ?`)) return;
  const r = await fetch(`/api/admin/prospection/metiers/${{encodeURIComponent(metier)}}?token=${{T}}`, {{method:'DELETE'}});
  if (r.ok) btn.closest('tr').remove();
  else alert('Erreur');
}}

// ── Requêtes IA ──

async function addQuery() {{
  const tpl = document.getElementById('new_query').value.trim();
  if (!tpl) {{ alert('Requête vide'); return; }}
  const order = document.querySelectorAll('.q-row').length;
  const r = await fetch('/api/admin/prospection/queries', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, template:tpl, active:true, order }})
  }});
  if (r.ok) {{ logTo('log-queries','Requête ajoutée','ok'); setTimeout(()=>location.reload(),500); }}
  else {{ const d=await r.json(); logTo('log-queries',d.detail||'Erreur','err'); }}
}}

async function saveQuery(input) {{
  const tid = input.dataset.id;
  const row = input.closest('.q-row');
  const active = row.querySelector('input[type=checkbox]').checked;
  const order  = parseInt(row.querySelector('span').textContent) || 0;
  const r = await fetch(`/api/admin/prospection/queries/${{tid}}`, {{
    method:'PUT', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, template:input.value, active, order }})
  }});
  input.style.borderColor = r.ok ? '#2ecc71' : '#e94560';
  setTimeout(()=>{{ input.style.borderColor=''; }}, 1500);
}}

async function toggleQuery(tid, active) {{
  const row   = document.querySelector(`.q-row[data-id="${{tid}}"]`);
  const input = row.querySelector('input[type=text]');
  const order = parseInt(row.querySelector('span').textContent) || 0;
  await fetch(`/api/admin/prospection/queries/${{tid}}`, {{
    method:'PUT', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, template:input.value, active, order }})
  }});
}}

async function delQuery(tid, btn) {{
  if (!confirm('Supprimer cette requête ?')) return;
  const r = await fetch(`/api/admin/prospection/queries/${{tid}}?token=${{T}}`, {{method:'DELETE'}});
  if (r.ok) btn.closest('.q-row').remove();
  else alert('Erreur');
}}

// ── Ciblages ──

document.getElementById('n_prof').addEventListener('change', function() {{
  const wrap = document.getElementById('n_prof_custom_wrap');
  wrap.style.display = this.value === '__custom__' ? 'block' : 'none';
}});

async function addTarget() {{
  const name = document.getElementById('n_name').value.trim();
  const city = document.getElementById('n_city').value.trim();
  const sel  = document.getElementById('n_prof').value;
  const prof = sel === '__custom__'
    ? document.getElementById('n_prof_custom').value.trim()
    : sel;
  const freq = document.getElementById('n_freq').value;
  const max  = parseInt(document.getElementById('n_max').value) || 20;
  if (!name || !city || !prof) {{ alert('Nom, ville et métier obligatoires.'); return; }}
  logTo('log-add', `Ajout : ${{name}} — ${{prof}} à ${{city}}...`);
  const r = await fetch('/api/admin/prospection/targets', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, name, city, profession:prof, frequency:freq, max_prospects:max }})
  }});
  const d = await r.json();
  if (r.ok) {{ logTo('log-add','Ciblage créé — rechargement...','ok'); setTimeout(()=>location.reload(),800); }}
  else logTo('log-add', d.detail||'Erreur','err');
}}

async function toggle(id, active, btn) {{
  const r = await fetch(`/api/admin/prospection/targets/${{id}}/toggle?token=${{T}}`, {{method:'POST'}});
  if (r.ok) location.reload();
  else alert('Erreur');
}}

async function del_(id, btn) {{
  if (!confirm('Supprimer ce ciblage ?')) return;
  const r = await fetch(`/api/admin/prospection/targets/${{id}}?token=${{T}}`, {{method:'DELETE'}});
  if (r.ok) btn.closest('tr').remove();
  else alert('Erreur');
}}

async function runNow(id, btn) {{
  btn.disabled = true; btn.textContent = '…';
  logTo('log-run', `Lancement du ciblage ${{id}}...`);
  const r = await fetch(`/api/admin/prospection/targets/${{id}}/run?token=${{T}}`, {{method:'POST'}});
  const d = await r.json();
  btn.disabled = false; btn.textContent = '▶ Lancer';
  if (r.ok) {{
    logTo('log-run', `${{d.imported}} prospects importés.`, 'ok');
    if (d.reasons?.length) logTo('log-run', 'Exclus: ' + d.reasons.join(' | '), 'warn');
  }} else {{
    logTo('log-run', d.detail || 'Erreur', 'err');
  }}
}}

async function importCSV() {{
  const tid  = document.getElementById('csv_target').value;
  const file = document.getElementById('csv_file').files[0];
  if (!tid)  {{ alert('Sélectionnez un ciblage.'); return; }}
  if (!file) {{ alert('Sélectionnez un fichier CSV.'); return; }}
  const text = await file.text();
  logTo('log-csv', `Import ${{file.name}}...`);
  const r = await fetch(`/api/admin/prospection/targets/${{tid}}/import-csv?token=${{T}}`, {{
    method:'POST', headers:{{'Content-Type':'text/plain'}}, body: text
  }});
  const d = await r.json();
  if (r.ok) logTo('log-csv', `${{d.imported}} importés, ${{d.skipped}} ignorés.`, 'ok');
  else logTo('log-csv', d.detail||'Erreur', 'err');
}}
</script>
</body></html>""")


# ── API — Métiers ──────────────────────────────────────────────────────────────

@router.post("/api/admin/prospection/metiers")
async def upsert_metier(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    if data.get("token") != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403)
    metier = (data.get("metier") or "").strip().lower()
    if not metier:
        raise HTTPException(400, "Métier obligatoire")
    row = db_upsert_metier_config(
        db, metier,
        data.get("problematique", ""),
        data.get("mission", ""),
    )
    return {"metier": row.metier, "problematique": row.problematique, "mission": row.mission}


@router.delete("/api/admin/prospection/metiers/{metier}")
def delete_metier(metier: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    if not db_delete_metier_config(db, metier):
        raise HTTPException(404)
    return {"deleted": True}


# ── API — Requêtes IA ──────────────────────────────────────────────────────────

@router.post("/api/admin/prospection/queries")
async def add_query(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    if data.get("token") != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403)
    tid = str(uuid.uuid4())
    row = db_upsert_ia_query_template(
        db, tid,
        data.get("template", "").strip(),
        data.get("active", True),
        data.get("order", 0),
    )
    return {"id": row.id, "template": row.template}


@router.put("/api/admin/prospection/queries/{tid}")
async def update_query(tid: str, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    if data.get("token") != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403)
    row = db_upsert_ia_query_template(
        db, tid,
        data.get("template", "").strip(),
        data.get("active", True),
        data.get("order", 0),
    )
    return {"id": row.id, "template": row.template}


@router.delete("/api/admin/prospection/queries/{tid}")
def delete_query(tid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    if not db_delete_ia_query_template(db, tid):
        raise HTTPException(404)
    return {"deleted": True}


# ── API — Ciblages ─────────────────────────────────────────────────────────────

@router.post("/api/admin/prospection/targets")
async def create_target(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    if data.get("token") != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403)
    t = ProspectionTargetDB(
        id=str(uuid.uuid4()),
        name=data["name"],
        city=data["city"],
        profession=data["profession"],
        frequency=data.get("frequency", "weekly"),
        max_prospects=int(data.get("max_prospects", 20)),
        active=True,
        created_at=datetime.utcnow(),
    )
    db.add(t); db.commit(); db.refresh(t)
    return {"id": t.id, "name": t.name}


@router.post("/api/admin/prospection/targets/{tid}/toggle")
def toggle_target(tid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    t = db.query(ProspectionTargetDB).filter_by(id=tid).first()
    if not t: raise HTTPException(404)
    t.active = not t.active; db.commit()
    return {"active": t.active}


@router.delete("/api/admin/prospection/targets/{tid}")
def delete_target(tid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    t = db.query(ProspectionTargetDB).filter_by(id=tid).first()
    if not t: raise HTTPException(404)
    db.delete(t); db.commit()
    return {"deleted": True}


@router.post("/api/admin/prospection/targets/{tid}/run")
def run_target(tid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    t = db.query(ProspectionTargetDB).filter_by(id=tid).first()
    if not t: raise HTTPException(404)
    return _run_prospection(db, t)


@router.post("/api/admin/prospection/targets/{tid}/import-csv")
async def import_csv(tid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    target = db.query(ProspectionTargetDB).filter_by(id=tid).first()
    if not target: raise HTTPException(404)
    body = await request.body()
    text = body.decode("utf-8", errors="replace")
    sep = ";" if text.count(";") > text.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=sep)
    campaign = _get_or_create_campaign(db, target)
    imported, skipped = 0, 0
    for row in reader:
        name = (row.get("name") or row.get("nom") or "").strip()
        if not name:
            skipped += 1; continue
        p = ProspectDB(
            prospect_id=str(uuid.uuid4()),
            campaign_id=campaign.campaign_id,
            name=name,
            city=(row.get("city") or row.get("ville") or target.city).strip(),
            profession=(row.get("profession") or row.get("metier") or target.profession).strip(),
            website=(row.get("website") or row.get("site") or "").strip() or None,
            phone=(row.get("phone") or row.get("telephone") or "").strip() or None,
            reviews_count=int(row["reviews_count"]) if (row.get("reviews_count") or "").strip().isdigit() else None,
            status=ProspectStatus.SCHEDULED.value,
        )
        db.add(p); imported += 1
    db.commit()
    return {"imported": imported, "skipped": skipped}


# ── Helpers internes ───────────────────────────────────────────────────────────

def _get_or_create_campaign(db: Session, target: ProspectionTargetDB) -> CampaignDB:
    existing = db.query(CampaignDB).filter_by(profession=target.profession, city=target.city).first()
    if existing:
        return existing
    c = CampaignDB(
        campaign_id=str(uuid.uuid4()),
        profession=target.profession,
        city=target.city,
        max_prospects=target.max_prospects,
        mode="auto",
    )
    db.add(c); db.commit(); db.refresh(c)
    return c


def _run_prospection(db: Session, target: ProspectionTargetDB) -> dict:
    """Lance Google Places → enrichissement → import prospects."""

    # Vérification image de ville AVANT de lancer (évite de faire tourner Places pour rien)
    city_header = db_get_header(db, target.city.lower())
    if not city_header:
        raise HTTPException(
            400,
            f"⚠️ Image de fond manquante pour la ville « {target.city} ».\n"
            f"Ajoutez-la dans Admin → Headers avant de lancer ce ciblage."
        )

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "GOOGLE_MAPS_API_KEY non configurée dans le .env")

    from ...google_places import search_prospects_enriched
    prospects_data, reasons = search_prospects_enriched(
        target.profession, target.city, api_key, max_results=target.max_prospects
    )

    campaign = _get_or_create_campaign(db, target)
    existing_names = {
        p.name.lower()
        for p in db.query(ProspectDB).filter_by(campaign_id=campaign.campaign_id).all()
    }

    new_prospects = []
    for pd in prospects_data:
        if pd["name"].lower() in existing_names:
            continue
        p = ProspectDB(
            prospect_id=str(uuid.uuid4()),
            campaign_id=campaign.campaign_id,
            name=pd["name"],
            city=target.city,
            profession=target.profession,
            website=pd.get("website"),
            phone=pd.get("tel"),
            mobile=pd.get("mobile"),
            email=pd.get("email"),
            cms=pd.get("cms"),
            reviews_count=pd.get("reviews_count"),
            status=ProspectStatus.SCHEDULED.value,
        )
        db.add(p)
        new_prospects.append(p)
        existing_names.add(pd["name"].lower())

    db.commit()
    target.last_run   = datetime.utcnow()
    target.last_count = len(new_prospects)
    db.commit()

    return {
        "target_id": target.id,
        "imported":  len(new_prospects),
        "reasons":   reasons[:5],
    }


# ── Scheduler (appelé toutes les heures par APScheduler) ──────────────────────

def run_due_targets(db: Session):
    import logging
    log = logging.getLogger(__name__)
    targets = db.query(ProspectionTargetDB).filter_by(active=True).all()
    for t in targets:
        delta_days = _FREQ_DAYS.get(t.frequency, 7)
        if t.last_run and (datetime.utcnow() - t.last_run) < timedelta(days=delta_days):
            continue
        try:
            res = _run_prospection(db, t)
            log.info("Prospection auto '%s' : %d prospects importés", t.name, res["imported"])
        except Exception as e:
            log.error("Prospection auto '%s' erreur : %s", t.name, e)
