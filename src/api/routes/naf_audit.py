"""
Admin — Audit des codes NAF : vérifie que chaque code retourne
les bons types d'entreprises via l'API SIRENE en temps réel.

GET  /admin/naf-audit          → page principale
POST /admin/naf-audit/test     → teste un NAF (retourne 5 exemples SIRENE)
POST /admin/naf-audit/fix      → met à jour les codes NAF d'une profession
"""
import json, logging, time
import urllib.request, urllib.parse

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...database import SessionLocal
from ._nav import admin_nav, admin_token

log    = logging.getLogger(__name__)
router = APIRouter()

_BASE_SIRENE = "https://recherche-entreprises.api.gouv.fr/search"


def _require_admin(token: str):
    if token != admin_token():
        from fastapi import HTTPException
        raise HTTPException(403, "Non autorisé")


def _naf_api(code: str) -> str:
    code = code.strip().upper()
    if len(code) == 5 and "." not in code:
        return f"{code[:2]}.{code[2:]}"
    return code


def _sample_sirene(naf: str, n: int = 6) -> list[str]:
    """Retourne n noms d'entreprises réelles pour ce code NAF (Paris)."""
    params = {
        "activite_principale": _naf_api(naf),
        "departement": "75",
        "etat_administratif": "A",
        "per_page": str(n),
        "page": "1",
    }
    url = _BASE_SIRENE + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "presence-ia/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        names = []
        for item in data.get("results", []):
            siege = item.get("siege") or {}
            nom = (item.get("nom_complet") or item.get("nom_raison_sociale")
                   or siege.get("denomination_usuelle") or "").strip()
            if nom:
                names.append(nom)
        return names[:n]
    except Exception as e:
        log.warning(f"SIRENE test {naf}: {e}")
        return []


@router.get("/admin/naf-audit", response_class=HTMLResponse)
def naf_audit_page(token: str = ""):
    _require_admin(token)

    with SessionLocal() as db:
        from ...models import ProfessionDB
        profs = db.query(ProfessionDB).order_by(ProfessionDB.label).all()

    # Regrouper par NAF unique → liste de professions
    naf_to_profs: dict[str, list] = {}
    prof_data = []
    for p in profs:
        codes = []
        try:
            codes = json.loads(p.codes_naf or "[]")
        except Exception:
            pass
        prof_data.append({"id": p.id, "label": p.label, "codes": codes})
        for c in codes:
            naf_to_profs.setdefault(c, []).append(p.label)

    prof_rows = "".join(
        f'<tr data-id="{p["id"]}">'
        f'<td style="padding:8px 10px;font-size:12px;font-weight:600">{p["label"]}</td>'
        f'<td style="padding:8px 10px;font-size:11px;font-family:monospace;color:#6b7280">'
        f'{", ".join(p["codes"]) or "—"}</td>'
        f'<td style="padding:8px 10px">'
        f'<button onclick="testProf(\'{p["id"]}\',{json.dumps(p["codes"])},\'{p["label"]}\')" '
        f'style="background:#f3f4f6;border:1px solid #e5e7eb;border-radius:4px;padding:3px 10px;'
        f'font-size:11px;cursor:pointer;color:#374151">Tester →</button>'
        f'</td>'
        f'<td style="padding:8px 10px" id="result-{p["id"]}"></td>'
        f'</tr>'
        for p in prof_data
    )

    nav = admin_nav(token, "naf-audit")
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Audit NAF</title>
{nav}
<style>
body{{font-family:system-ui,sans-serif;background:#f9fafb;color:#111;margin:0}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;margin:16px 24px}}
table{{width:100%;border-collapse:collapse}}
th{{background:#f1f5f9;font-size:11px;font-weight:700;text-transform:uppercase;
    letter-spacing:.05em;padding:8px 10px;text-align:left;color:#64748b;
    position:sticky;top:0;z-index:1}}
tr:hover td{{background:#fafafa}}
.tag-naf{{background:#eff6ff;color:#1d4ed8;padding:2px 6px;border-radius:4px;
          font-size:10px;font-family:monospace;font-weight:700;margin-right:3px}}
.sample-ok{{color:#166534;font-size:11px}}
.sample-warn{{color:#92400e;font-size:11px}}
input[type=text]{{border:1px solid #d1d5db;border-radius:6px;padding:6px 10px;
                  font-size:13px;outline:none;width:100%;box-sizing:border-box}}
input:focus{{border-color:#e94560}}
.btn{{background:#e94560;color:#fff;border:none;border-radius:6px;
      padding:8px 16px;font-size:13px;font-weight:600;cursor:pointer}}
.btn:hover{{background:#c73652}}
.btn-green{{background:#16a34a}}.btn-green:hover{{background:#15803d}}
.btn-sm{{padding:4px 10px;font-size:11px}}
/* Modal */
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);
        z-index:2000;align-items:center;justify-content:center}}
.modal.show{{display:flex}}
.modal-box{{background:#fff;border-radius:10px;padding:24px;width:640px;
            max-width:95vw;max-height:85vh;overflow-y:auto}}
</style></head><body>
<div style="padding:20px 24px 0">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
    <h2 style="font-size:18px;font-weight:700;margin:0">Audit codes NAF</h2>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" onclick="testAll()" id="btn-all">
        ▶ Tester toutes ({len(prof_data)})
      </button>
    </div>
  </div>
  <p style="color:#6b7280;font-size:13px;margin:0 0 16px">
    Cliquez "Tester →" pour voir les vraies entreprises SIRENE correspondant à chaque code NAF.
    Si les noms ne ressemblent pas au métier → le code est à corriger.
  </p>

  <div class="card" style="padding:0;overflow:hidden">
    <div style="padding:10px 14px;border-bottom:1px solid #e5e7eb;display:flex;gap:8px;align-items:center">
      <input type="text" id="q-filter" placeholder="Filtrer par métier..." oninput="filterRows()"
             style="width:280px">
      <span id="test-progress" style="font-size:12px;color:#6b7280"></span>
    </div>
    <div style="overflow-y:auto;max-height:calc(100vh - 180px)">
    <table>
      <thead><tr>
        <th style="width:25%">Métier</th>
        <th style="width:15%">Codes NAF</th>
        <th style="width:8%">Test</th>
        <th>Entreprises SIRENE trouvées (Paris)</th>
      </tr></thead>
      <tbody id="prof-tbody">{prof_rows}</tbody>
    </table>
    </div>
  </div>
</div>

<!-- Modal correction NAF -->
<div class="modal" id="fix-modal">
  <div class="modal-box">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h3 style="margin:0;font-size:15px;font-weight:700" id="fix-modal-title">Corriger les codes NAF</h3>
      <button onclick="closeFixModal()" style="background:none;border:none;font-size:18px;
              cursor:pointer;color:#9ca3af">✕</button>
    </div>
    <p style="font-size:12px;color:#6b7280;margin:0 0 12px" id="fix-modal-desc"></p>

    <div style="margin-bottom:16px">
      <label style="font-size:12px;font-weight:600;display:block;margin-bottom:6px">
        Codes NAF actuels (séparés par virgule)
      </label>
      <input type="text" id="fix-naf-input" placeholder="ex: 4329B, 4399C">
    </div>

    <div id="fix-preview" style="margin-bottom:16px"></div>

    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" onclick="previewNaf()">Prévisualiser</button>
      <button class="btn btn-sm btn-green" id="fix-save-btn" onclick="saveNaf()" disabled>
        ✓ Enregistrer
      </button>
      <button onclick="closeFixModal()" style="background:#f3f4f6;border:1px solid #e5e7eb;
              border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer">Annuler</button>
    </div>
  </div>
</div>

<script>
const TOKEN = '{token}';
let _fixProfId = '';
let _fixProfLabel = '';

function filterRows() {{
  const q = document.getElementById('q-filter').value.toLowerCase();
  document.querySelectorAll('#prof-tbody tr').forEach(tr => {{
    tr.style.display = tr.dataset.id && tr.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}

async function testProf(profId, codes, label) {{
  const cell = document.getElementById('result-' + profId);
  cell.innerHTML = '<span style="color:#9ca3af;font-size:11px">⏳ test SIRENE...</span>';

  const res = await fetch('/admin/naf-audit/test?token='+TOKEN, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{codes}})
  }});
  const d = await res.json();

  if (!d.results || d.results.length === 0) {{
    cell.innerHTML = '<span style="color:#dc2626;font-size:11px">⚠ Aucun résultat SIRENE</span>'
      + ` <button onclick="openFixModal('${{profId}}','${{label.replace(/'/g,"\\'")}}',${{JSON.stringify(codes)}})" `
      + 'class="btn btn-sm" style="background:#fee2e2;color:#991b1b;border:none">Corriger</button>';
    return;
  }}

  // Afficher les noms avec bouton corriger
  const names = d.results.map(r =>
    `<span style="display:inline-block;background:#f8fafc;border:1px solid #e5e7eb;`
    + `border-radius:4px;padding:1px 6px;font-size:11px;margin:1px">${{r}}</span>`
  ).join(' ');

  cell.innerHTML = names
    + ` <button onclick="openFixModal('${{profId}}','${{label.replace(/'/g,"\\'")}}',${{JSON.stringify(codes)}})" `
    + 'style="background:#f3f4f6;border:1px solid #e5e7eb;border-radius:4px;padding:2px 8px;'
    + 'font-size:10px;cursor:pointer;color:#6b7280;margin-left:6px">Modifier NAF</button>';
}}

let _allQueue = [];
let _allRunning = false;

async function testAll() {{
  _allQueue = [...document.querySelectorAll('#prof-tbody tr[data-id]')]
    .filter(tr => tr.style.display !== 'none')
    .map(tr => tr.dataset.id);
  document.getElementById('btn-all').disabled = true;
  await _runQueue();
  document.getElementById('btn-all').disabled = false;
}}

async function _runQueue() {{
  const profs = {json.dumps([{"id": p["id"], "codes": p["codes"], "label": p["label"]} for p in prof_data])};
  const profMap = Object.fromEntries(profs.map(p => [p.id, p]));

  let done = 0;
  const total = _allQueue.length;

  for (const profId of _allQueue) {{
    const p = profMap[profId];
    if (p) await testProf(p.id, p.codes, p.label);
    done++;
    document.getElementById('test-progress').textContent = done + ' / ' + total;
    await new Promise(r => setTimeout(r, 300)); // petit délai SIRENE
  }}
  document.getElementById('test-progress').textContent = '✓ ' + total + ' testés';
}}

function openFixModal(profId, label, currentCodes) {{
  _fixProfId = profId;
  _fixProfLabel = label;
  document.getElementById('fix-modal-title').textContent = 'Corriger NAF — ' + label;
  document.getElementById('fix-modal-desc').textContent =
    'Codes actuels : ' + (currentCodes.join(', ') || '—') +
    '. Entrez les nouveaux codes et prévisualisez avant d\u2019enregistrer.';
  document.getElementById('fix-naf-input').value = currentCodes.join(', ');
  document.getElementById('fix-preview').innerHTML = '';
  document.getElementById('fix-save-btn').disabled = true;
  document.getElementById('fix-modal').classList.add('show');
}}

function closeFixModal() {{
  document.getElementById('fix-modal').classList.remove('show');
}}

async function previewNaf() {{
  const raw = document.getElementById('fix-naf-input').value;
  const codes = raw.split(/[,\\s]+/).map(c => c.trim().toUpperCase()).filter(Boolean);
  if (!codes.length) return;

  document.getElementById('fix-preview').innerHTML = '<span style="color:#9ca3af;font-size:11px">⏳ test SIRENE...</span>';

  const res = await fetch('/admin/naf-audit/test?token='+TOKEN, {{
    method: 'POST', headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{codes}})
  }});
  const d = await res.json();

  let html = '<div style="margin-top:8px">';
  for (const [naf, names] of Object.entries(d.by_naf || {{}})) {{
    html += `<div style="margin-bottom:8px">
      <span class="tag-naf">${{naf}}</span>
      ${{names.length === 0
        ? '<span style="color:#dc2626;font-size:11px">⚠ Aucun résultat</span>'
        : names.map(n => `<span style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:4px;`
            + `padding:1px 6px;font-size:11px;margin:1px;display:inline-block">${{n}}</span>`).join('')
      }}
    </div>`;
  }}
  html += '</div>';
  document.getElementById('fix-preview').innerHTML = html;
  document.getElementById('fix-save-btn').disabled = false;
}}

async function saveNaf() {{
  const raw = document.getElementById('fix-naf-input').value;
  const codes = raw.split(/[,\\s]+/).map(c => c.trim().toUpperCase()).filter(Boolean);

  const res = await fetch('/admin/naf-audit/fix?token='+TOKEN, {{
    method: 'POST', headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{profession_id: _fixProfId, codes}})
  }});
  const d = await res.json();
  if (d.ok) {{
    closeFixModal();
    // Rafraîchir la cellule NAF dans le tableau
    const row = document.querySelector(`tr[data-id="${{_fixProfId}}"]`);
    if (row) row.querySelectorAll('td')[1].textContent = codes.join(', ');
    // Re-tester automatiquement
    await testProf(_fixProfId, codes, _fixProfLabel);
  }}
}}
</script>
</body></html>""")


@router.post("/admin/naf-audit/test")
async def naf_test(request: Request, token: str = ""):
    _require_admin(token)
    data  = await request.json()
    codes = data.get("codes", [])

    by_naf: dict[str, list] = {}
    all_names: list[str]    = []

    for naf in codes:
        names = _sample_sirene(naf, n=6)
        by_naf[naf] = names
        all_names.extend(names)
        time.sleep(0.15)

    return JSONResponse({"results": all_names[:12], "by_naf": by_naf})


@router.post("/admin/naf-audit/fix")
async def naf_fix(request: Request, token: str = ""):
    _require_admin(token)
    data          = await request.json()
    profession_id = data.get("profession_id", "")
    codes         = data.get("codes", [])

    if not profession_id or not codes:
        return JSONResponse({"error": "profession_id et codes requis"}, status_code=400)

    with SessionLocal() as db:
        from ...models import ProfessionDB
        prof = db.query(ProfessionDB).filter_by(id=profession_id).first()
        if not prof:
            return JSONResponse({"error": "Profession introuvable"}, status_code=404)
        prof.codes_naf = json.dumps(codes, ensure_ascii=False)
        db.commit()

    log.info(f"NAF corrigé : {profession_id} → {codes}")
    return JSONResponse({"ok": True})
