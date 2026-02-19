"""Admin — page Lancer une recherche IA."""
import json
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_create_prospect, db_create_campaign
from ...models import ProspectDB, ProspectStatus, CampaignDB
from ...scan import get_queries

router = APIRouter(tags=["Admin Scan"])

_MODELS = [
    ("openai",    "ChatGPT (GPT-4o mini)"),
    ("anthropic", "Anthropic (Claude Haiku)"),
    ("gemini",    "Gemini (2.0 Flash)"),
]


def _check_token(request: Request) -> str:
    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    return token


def _nav(token: str) -> str:
    tabs = [
        ("contacts",   "👥 Contacts"),
        ("offers",     "💶 Offres"),
        ("analytics",  "📊 Analytics"),
        ("evidence",   "📸 Preuves"),
        ("headers",    "🖼 Headers"),
        ("content",    "✏️ Contenus"),
        ("send-queue", "📤 Envoi"),
        ("scan",       "🔍 Nouvelle recherche"),
    ]
    links = "".join(
        f'<a href="/admin/{t}?token={token}" style="padding:10px 18px;border-radius:6px;text-decoration:none;'
        f'font-size:13px;font-weight:{"bold" if t=="scan" else "normal"};'
        f'background:{"#e94560" if t=="scan" else "transparent"};color:#fff">{label}</a>'
        for t, label in tabs
    )
    return f'<div style="background:#0a0a15;border-bottom:1px solid #1a1a2e;padding:0 20px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">' \
           f'<a href="/admin?token={token}" style="color:#e94560;font-weight:bold;font-size:15px;padding:12px 16px 12px 0;text-decoration:none">⚡ PRESENCE_IA</a>' \
           f'{links}</div>'


@router.get("/admin/scan", response_class=HTMLResponse)
def scan_page(request: Request):
    token = _check_token(request)

    models_checks = "".join(
        f'<label style="display:flex;align-items:center;gap:8px;margin-bottom:10px;color:#ccc;font-size:14px;cursor:pointer">'
        f'<input type="checkbox" name="models" value="{mid}" checked '
        f'style="width:16px;height:16px;accent-color:#e94560"> {label}</label>'
        for mid, label in _MODELS
    )

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nouvelle recherche — PRESENCE_IA</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
.wrap{{max-width:720px;margin:0 auto;padding:32px 24px}}
h1{{color:#fff;font-size:20px;margin-bottom:8px}}
.sub{{color:#6b7280;font-size:13px;margin-bottom:32px}}
.card{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:28px;margin-bottom:20px}}
.card h2{{color:#e94560;font-size:13px;text-transform:uppercase;letter-spacing:1px;margin-bottom:20px}}
label.field{{display:block;color:#9ca3af;font-size:12px;margin-bottom:6px;margin-top:16px}}
label.field:first-of-type{{margin-top:0}}
input[type=text],textarea,select{{width:100%;background:#0f0f1a;border:1px solid #2a2a4e;
  color:#e8e8f0;border-radius:6px;padding:10px 12px;font-size:14px;font-family:inherit}}
input[type=text]:focus,textarea:focus{{outline:none;border-color:#e94560}}
textarea{{resize:vertical;min-height:120px}}
.btn{{background:linear-gradient(90deg,#e8355a,#ff7043);color:#fff;border:none;
  padding:14px 32px;border-radius:8px;font-size:15px;font-weight:700;cursor:pointer;
  width:100%;margin-top:8px;transition:opacity .2s}}
.btn:disabled{{opacity:.5;cursor:not-allowed}}
.btn:hover:not(:disabled){{opacity:.9}}
.log{{background:#0a0a15;border:1px solid #1a1a2e;border-radius:8px;padding:16px;
  font-family:monospace;font-size:12px;color:#6b7280;min-height:80px;
  max-height:400px;overflow-y:auto;white-space:pre-wrap;display:none}}
.log.active{{display:block}}
.tag{{display:inline-block;background:#1a1a2e;border:1px solid #2a2a4e;
  color:#9ca3af;border-radius:4px;padding:3px 10px;font-size:12px;margin:3px}}
.result-ok{{color:#2ecc71}}.result-err{{color:#e94560}}
</style>
</head><body>
{_nav(token)}
<div class="wrap">
<h1>🔍 Nouvelle recherche IA</h1>
<p class="sub">Crée un prospect ad-hoc et lance les tests multi-IA immédiatement.</p>

<div class="card">
  <h2>Cible</h2>
  <label class="field">Ville</label>
  <input type="text" id="city" placeholder="ex: Brest" value="Brest">
  <label class="field">Métier</label>
  <input type="text" id="profession" placeholder="ex: couvreur" value="couvreur">
  <label class="field">Nom du prospect (optionnel)</label>
  <input type="text" id="name" placeholder="ex: TOIT'URIEN — laissez vide pour test anonyme">
</div>

<div class="card">
  <h2>Requêtes testées</h2>
  <p style="color:#6b7280;font-size:12px;margin-bottom:12px">
    Générées automatiquement depuis ville + métier. Modifiables librement — une par ligne.
  </p>
  <textarea id="queries" placeholder="Chargement..."></textarea>
  <button onclick="regenQueries()" style="margin-top:8px;background:transparent;border:1px solid #2a2a4e;
    color:#9ca3af;padding:6px 14px;border-radius:6px;font-size:12px;cursor:pointer">
    ↺ Regénérer depuis ville + métier
  </button>
</div>

<div class="card">
  <h2>Moteurs IA</h2>
  {models_checks}
</div>

<button class="btn" id="runBtn" onclick="runScan()">Lancer la recherche →</button>

<div class="log" id="log"></div>
</div>

<script>
const T = '{token}';

function getQueries() {{
  const city = document.getElementById('city').value.trim();
  const prof = document.getElementById('profession').value.trim();
  return [
    `Quel est le meilleur ${{prof}} à ${{city}} ?`,
    `J'ai besoin d'un ${{prof}} à ${{city}}, tu peux m'en recommander ?`,
    `Qui sont les ${{prof}}s les mieux notés à ${{city}} ?`,
    `Quelles entreprises de ${{prof}} sont connues à ${{city}} ?`,
    `Donne-moi des noms de ${{prof}}s ou d'entreprises à ${{city}}`,
  ];
}}

function regenQueries() {{
  document.getElementById('queries').value = getQueries().join('\\n');
}}

function log(msg, cls='') {{
  const el = document.getElementById('log');
  el.classList.add('active');
  el.textContent += (cls === 'result-ok' ? '✅ ' : cls === 'result-err' ? '❌ ' : '▸ ') + msg + '\\n';
  el.scrollTop = el.scrollHeight;
}}

async function runScan() {{
  const city    = document.getElementById('city').value.trim();
  const prof    = document.getElementById('profession').value.trim();
  const name    = document.getElementById('name').value.trim() || `[TEST] ${{prof}} ${{city}}`;
  const qlines  = document.getElementById('queries').value.trim().split('\\n').filter(l => l.trim());
  const models  = [...document.querySelectorAll('input[name=models]:checked')].map(c => c.value);

  if (!city || !prof)   {{ alert('Ville et métier obligatoires.'); return; }}
  if (!qlines.length)   {{ alert('Aucune requête.'); return; }}
  if (!models.length)   {{ alert('Sélectionnez au moins un moteur.'); return; }}

  const btn = document.getElementById('runBtn');
  btn.disabled = true; btn.textContent = 'Recherche en cours…';
  document.getElementById('log').textContent = '';

  log(`Cible : ${{name}} — ${{prof}} à ${{city}}`);
  log(`Moteurs : ${{models.join(', ')}}`);
  log(`${{qlines.length}} requêtes envoyées...`);
  log('');

  try {{
    const r = await fetch('/api/admin/scan/run', {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{ city, profession: prof, name, queries: qlines, models, token: T }})
    }});
    const d = await r.json();
    if (!r.ok) {{ log(d.detail || 'Erreur serveur', 'result-err'); return; }}

    log('');
    for (const run of d.runs) {{
      log(`${{run.model.toUpperCase()}} — mentionné : ${{run.mentioned ? 'OUI' : 'non'}}`, run.mentioned ? 'result-ok' : '');
      log(`  Par requête : ${{run.mention_per_query.map((m,i) => (m?'✓':'✗')+' Q'+(i+1)).join('  ')}}`);
      if (run.competitors.length) {{
        log(`  Concurrents : ${{run.competitors.join(', ')}}`);
      }}
    }}
    log('');
    log(`Terminé. ${{d.runs.filter(r=>r.mentioned).length}}/${{d.runs.length}} modèles citent le prospect.`, 'result-ok');
    if (d.landing_url) log(`Landing : ${{d.landing_url}}`);
  }} catch(e) {{
    log('Erreur : ' + e.message, 'result-err');
  }} finally {{
    btn.disabled = false; btn.textContent = 'Lancer la recherche →';
  }}
}}

// Init
regenQueries();
</script>
</body></html>""")


@router.post("/api/admin/scan/run")
async def run_scan(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    token = data.get("token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")

    city       = data.get("city", "").strip()
    profession = data.get("profession", "").strip()
    name       = data.get("name", f"[TEST] {profession} {city}").strip()
    queries    = data.get("queries", [])
    models     = data.get("models", ["openai", "anthropic", "gemini"])

    if not city or not profession:
        raise HTTPException(400, "Ville et métier requis")
    if not queries:
        raise HTTPException(400, "Requêtes vides")

    # Créer une campagne + prospect ad-hoc
    campaign = CampaignDB(
        campaign_id=str(uuid.uuid4()),
        profession=profession,
        city=city,
        max_prospects=1,
        mode="manual",
    )
    db.add(campaign); db.commit(); db.refresh(campaign)

    import secrets as _sec
    prospect = ProspectDB(
        prospect_id=str(uuid.uuid4()),
        campaign_id=campaign.campaign_id,
        name=name,
        city=city,
        profession=profession,
        landing_token=_sec.token_hex(12),
        status=ProspectStatus.TESTING.value,
    )
    db.add(prospect); db.commit(); db.refresh(prospect)

    # Lancer les tests sur les modèles sélectionnés
    from ...ia_test import _CALLERS, is_mentioned, extract_entities, competitors_from, _safe_call
    from ...database import db_create_run, jd
    from ...models import TestRunDB
    from datetime import datetime

    runs_out = []
    for model in models:
        if model not in _CALLERS:
            continue
        api_key_env = _CALLERS[model][1]
        if not os.getenv(api_key_env):
            runs_out.append({"model": model, "mentioned": False,
                             "mention_per_query": [], "competitors": [],
                             "error": f"Clé {api_key_env} manquante"})
            continue

        caller, _ = _CALLERS[model]
        raw, ents, mq, comps, notes = [], [], [], [], []
        mentioned = False

        for qi, q in enumerate(queries):
            ans = _safe_call(caller, q, model, qi, notes)
            raw.append(ans)
            e = extract_entities(ans)
            ents.append([{"type": x["type"], "value": x["value"]} for x in e])
            m = is_mentioned(ans, name)
            mq.append(m)
            if m: mentioned = True
            comps.extend(competitors_from(e, name, None))

        seen: set = set()
        uc = [c for c in comps if not (c.lower() in seen or seen.add(c.lower()))]

        run = TestRunDB(
            run_id=str(uuid.uuid4()),
            campaign_id=campaign.campaign_id,
            prospect_id=prospect.prospect_id,
            ts=datetime.utcnow(),
            model=model,
            queries=jd(queries),
            raw_answers=jd(raw),
            extracted_entities=jd(ents),
            mentioned_target=mentioned,
            mention_per_query=jd(mq),
            competitors_entities=jd(uc[:20]),
            notes="; ".join(notes) or None,
        )
        db_create_run(db, run)
        runs_out.append({
            "model": model,
            "mentioned": mentioned,
            "mention_per_query": mq,
            "competitors": uc[:10],
        })

    prospect.status = ProspectStatus.TESTED.value
    db.commit()

    base_url = os.getenv("BASE_URL", "http://localhost:8001")
    return JSONResponse({
        "prospect_id": prospect.prospect_id,
        "landing_url": f"{base_url}/couvreur?t={prospect.landing_token}",
        "runs": runs_out,
    })
