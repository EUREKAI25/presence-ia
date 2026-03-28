"""Admin — page Lancer une recherche IA."""
import json
import os
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from ...database import get_db, db_create_prospect, db_create_campaign
from ...models import ProspectDB, ProspectStatus, CampaignDB
from ...scan import get_queries
from ._nav import admin_nav

router = APIRouter(tags=["Admin Scan"])

_MODELS = ["openai", "anthropic", "gemini"]


def _check_token(request: Request) -> str:
    token = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")
    return token


@router.get("/admin/scan", response_class=HTMLResponse)
def scan_page(request: Request):
    token = _check_token(request)

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
{admin_nav(token, "scan")}
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
  const models  = ['openai', 'anthropic', 'gemini'];

  if (!city || !prof)   {{ alert('Ville et métier obligatoires.'); return; }}
  if (!qlines.length)   {{ alert('Aucune requête.'); return; }}

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

    import asyncio

    async def _run_model(model):
        if model not in _CALLERS:
            return None
        api_key_env = _CALLERS[model][1]
        if not os.getenv(api_key_env):
            return {"model": model, "mentioned": False,
                    "mention_per_query": [], "competitors": [],
                    "error": f"Clé {api_key_env} manquante"}
        caller, _ = _CALLERS[model]
        raw, ents, mq, comps, notes = [], [], [], [], []
        mentioned = False
        loop = asyncio.get_event_loop()
        for qi, q in enumerate(queries):
            ans = await loop.run_in_executor(None, lambda caller=caller, q=q, m=model, i=qi: _safe_call(caller, q, m, i, notes))
            raw.append(ans)
            e = extract_entities(ans)
            ents.append([{"type": x["type"], "value": x["value"]} for x in e])
            m_flag = is_mentioned(ans, name)
            mq.append(m_flag)
            if m_flag: mentioned = True
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
        return {"model": model, "mentioned": mentioned, "mention_per_query": mq, "competitors": uc[:10]}

    results = await asyncio.gather(*[_run_model(m) for m in models])
    runs_out = [r for r in results if r is not None]

    prospect.status = ProspectStatus.TESTED.value
    db.commit()

    base_url = os.getenv("BASE_URL", "http://localhost:8001")
    return JSONResponse({
        "prospect_id": prospect.prospect_id,
        "landing_url": f"{base_url}/couvreur?t={prospect.landing_token}",
        "runs": runs_out,
    })


# ── Endpoints runner Playwright Mac ───────────────────────────────────────────

@router.get("/api/ia-pairs")
async def get_ia_pairs(token: str = "", db: Session = Depends(get_db)):
    """Retourne les paires (profession, city) actives à tester — appelé par le runner Mac."""
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")

    from ...models import V3ProspectDB
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=30)

    pairs_raw = (
        db.query(V3ProspectDB.city, V3ProspectDB.profession)
        .filter(V3ProspectDB.created_at >= cutoff)
        .distinct()
        .all()
    )

    from ...scan import get_queries
    pairs = []
    seen = set()
    for city, profession in pairs_raw:
        key = f"{profession}|{city}"
        if key in seen or not city or not profession:
            continue
        seen.add(key)
        queries = get_queries(profession, city)
        pairs.append({"profession": profession, "city": city, "queries": queries})

    return JSONResponse({"pairs": pairs, "count": len(pairs)})


@router.post("/api/ia-results")
async def post_ia_results(request: Request, db: Session = Depends(get_db)):
    """
    Reçoit les résultats Playwright du runner Mac et met à jour ia_results dans v3_prospects.
    Format payload :
    {
      "results": [
        {
          "profession": "pisciniste", "city": "Paris", "query": "...", "tested_at": "...",
          "models": [
            {"platform": "chatgpt", "model": "GPT-4o", "text": "...", "competitors": [...], "ok": true}
          ]
        }
      ]
    }
    """
    data = await request.json()
    token = request.query_params.get("token", "")
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")

    from ...models import V3ProspectDB
    from ...scheduler import _extract_cited_names, _upsert_cited_companies

    results = data.get("results", [])
    updated = 0
    errors  = []

    # Regrouper par (profession, city) pour construire ia_results agrégés
    from collections import defaultdict
    by_pair: dict = defaultdict(list)
    for row in results:
        key = (row.get("profession", ""), row.get("city", ""))
        for m in row.get("models", []):
            platform = m.get("platform", "")
            model_label = {"chatgpt": "ChatGPT", "claude": "Claude", "gemini": "Gemini"}.get(platform, platform)
            by_pair[key].append({
                "model":    model_label,
                "prompt":   row.get("query", ""),
                "response": m.get("text", ""),
            })

    for (profession, city), ia_list in by_pair.items():
        try:
            ia_results_json = json.dumps(ia_list, ensure_ascii=False)
            cited = _extract_cited_names(ia_list)

            prospects = db.query(V3ProspectDB).filter_by(
                city=city, profession=profession
            ).all()

            for p in prospects:
                p.ia_results   = ia_results_json
                p.ia_tested_at = datetime.utcnow()
            db.commit()

            _upsert_cited_companies(db, profession, city, cited)
            updated += len(prospects)
        except Exception as e:
            errors.append(f"{profession}/{city}: {e}")

    return JSONResponse({
        "ok":      True,
        "updated": updated,
        "pairs":   len(by_pair),
        "errors":  errors,
    })
