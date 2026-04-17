"""
Routes Implantation IA — génération du livrable 3500€.
"""
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

log = logging.getLogger(__name__)
router = APIRouter()

_JOBS: dict[str, dict] = {}


def _admin_ok(request: Request) -> bool:
    token = request.query_params.get("token", "") or request.headers.get("X-Admin-Token", "")
    return token == os.getenv("ADMIN_TOKEN", "changeme")


# ── Page admin ───────────────────────────────────────────────────────────────

@router.get("/admin/implantation-ia", response_class=HTMLResponse)
def admin_implantation_page(request: Request):
    if not _admin_ok(request):
        raise HTTPException(403)

    recent = sorted(
        [j for j in _JOBS.values() if j.get("status") in ("done", "running", "error")],
        key=lambda j: j.get("created_at", ""),
        reverse=True,
    )[:20]

    rows = ""
    for j in recent:
        status = j["status"]
        badge_color = {"done": "#38a169", "running": "#d69e2e", "error": "#e53e3e"}.get(status, "#718096")
        dl_link = ""
        if status == "done" and j.get("result", {}).get("deliverable_path"):
            jid   = j["id"]
            score = j["result"].get("score", 0)
            nb_c  = len(j["result"].get("competitor_summaries", []))
            nb_g  = len(j["result"].get("gaps", []))
            dl_link = (
                f'<a href="/api/implantation-ia/result/{jid}" target="_blank" '
                f'style="color:#667eea;text-decoration:none">📄 Livrable</a>'
                f' — Score: <strong>{score}/10</strong>'
                f' · {nb_c} concurrents · {nb_g} écarts'
            )
        elif status == "error":
            dl_link = f'<span style="color:#e53e3e">{j.get("error","")[:80]}</span>'
        elif status == "running":
            dl_link = '<span style="color:#d69e2e">En cours… (3-5 min)</span>'

        rows += f"""<tr>
<td style="padding:10px 14px">{j.get('company_name','')}</td>
<td style="padding:10px 14px">{j.get('city','')}</td>
<td style="padding:10px 14px">{j.get('business_type','')}</td>
<td style="padding:10px 14px">
  <span style="background:{badge_color};color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">{status}</span>
</td>
<td style="padding:10px 14px;font-size:13px">{j.get('created_at','')[:16]}</td>
<td style="padding:10px 14px;font-size:13px">{dl_link}</td>
</tr>"""

    token = request.query_params.get("token", "")
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Implantation IA — Admin</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:#f7fafc;color:#2d3748;font-size:15px}}
  .hdr{{background:linear-gradient(135deg,#1a202c,#2d3748);color:#fff;
        padding:20px 32px;display:flex;align-items:center;gap:16px}}
  .hdr a{{color:rgba(255,255,255,.7);text-decoration:none;font-size:14px}}
  .wrap{{max-width:980px;margin:32px auto;padding:0 24px}}
  label{{display:block;font-size:13px;font-weight:600;color:#4a5568;margin-bottom:4px}}
  input{{width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:6px;font-size:14px;outline:none}}
  input:focus{{border-color:#667eea}}
  .btn{{background:linear-gradient(135deg,#1a202c,#4a5568);color:#fff;border:none;
        padding:12px 28px;border-radius:8px;font-size:15px;font-weight:700;cursor:pointer}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden}}
  th{{background:#edf2f7;padding:10px 14px;text-align:left;font-size:13px;font-weight:700;color:#4a5568}}
  tr:hover td{{background:#f7fafc}}
</style>
</head>
<body>
<div class="hdr">
  <a href="/admin/hub?token={token}">← Hub</a>
  <span style="opacity:.4">|</span>
  <strong>Implantation IA — Générer un livrable 3 500€</strong>
</div>
<div class="wrap">

<div style="background:#fff;border-radius:12px;padding:28px;box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:32px">
  <h2 style="font-size:18px;font-weight:800;margin-bottom:6px">Générer un livrable Implantation IA</h2>
  <p style="color:#718096;font-size:14px;margin-bottom:20px">
    Inclut : audit IA + analyse TOP 3 concurrents + analyse des écarts + stratégie + contenus prêts à intégrer
  </p>
  <form id="form" style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div>
      <label>Nom de l'entreprise *</label>
      <input id="company_name" required placeholder="ex: Plomberie Dupont">
    </div>
    <div>
      <label>Ville *</label>
      <input id="city" required placeholder="ex: Lyon">
    </div>
    <div>
      <label>Type d'activité / métier *</label>
      <input id="business_type" required placeholder="ex: plombier, couvreur, électricien">
    </div>
    <div>
      <label>Site web (optionnel)</label>
      <input id="website" placeholder="https://...">
    </div>
    <div style="grid-column:1/-1;display:flex;gap:16px;align-items:center;margin-top:8px">
      <button class="btn" type="button" onclick="launch()">🚀 Générer le livrable Implantation</button>
      <div id="status" style="font-size:14px;color:#718096"></div>
    </div>
  </form>
</div>

<div style="background:#fff;border-radius:12px;padding:24px;box-shadow:0 1px 4px rgba(0,0,0,.08)">
  <h2 style="font-size:16px;font-weight:800;margin-bottom:16px">Livrables récents</h2>
  <table>
    <thead>
      <tr><th>Entreprise</th><th>Ville</th><th>Métier</th><th>Statut</th><th>Date</th><th>Résultat</th></tr>
    </thead>
    <tbody id="tbody">{rows}</tbody>
  </table>
</div>

</div>
<script>
async function launch() {{
  const company = document.getElementById('company_name').value.trim();
  const city    = document.getElementById('city').value.trim();
  const bt      = document.getElementById('business_type').value.trim();
  const site    = document.getElementById('website').value.trim();
  if (!company || !city || !bt) {{ alert('Entreprise, ville et métier sont obligatoires.'); return; }}

  document.getElementById('status').textContent = '⏳ Lancement…';

  const r = await fetch('/api/implantation-ia/run?token={token}', {{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{company_name:company, city, business_type:bt, website:site}})
  }});
  const data = await r.json();
  if (!r.ok) {{ document.getElementById('status').textContent = '❌ ' + (data.detail || 'Erreur'); return; }}

  const jobId = data.job_id;
  document.getElementById('status').textContent = '⏳ Pipeline IA + analyse concurrents en cours (3-5 min)…';

  const poll = setInterval(async () => {{
    const rp = await fetch('/api/implantation-ia/status/' + jobId + '?token={token}');
    const dp = await rp.json();
    if (dp.status === 'done') {{
      clearInterval(poll);
      document.getElementById('status').innerHTML =
        '✅ Terminé ! Score: <strong>' + dp.score + '/10</strong> · ' +
        dp.nb_competitors + ' concurrents · ' + dp.nb_gaps + ' écarts — ' +
        '<a href="/api/implantation-ia/result/' + jobId + '?token={token}" target="_blank">📄 Voir le livrable</a>';
      location.reload();
    }} else if (dp.status === 'error') {{
      clearInterval(poll);
      document.getElementById('status').textContent = '❌ Erreur : ' + dp.error;
    }}
  }}, 6000);
}}
</script>
</body>
</html>""")


# ── API endpoints ─────────────────────────────────────────────────────────────

@router.post("/api/implantation-ia/run")
async def run_pipeline_endpoint(request: Request, background_tasks: BackgroundTasks):
    if not _admin_ok(request):
        raise HTTPException(403)

    body = await request.json()
    company_name  = (body.get("company_name") or "").strip()
    city          = (body.get("city") or "").strip()
    business_type = (body.get("business_type") or "").strip()
    website       = (body.get("website") or "").strip()

    if not company_name or not city or not business_type:
        raise HTTPException(400, "company_name, city et business_type sont obligatoires")

    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {
        "id": job_id, "status": "running",
        "company_name": company_name, "city": city,
        "business_type": business_type, "website": website,
        "created_at": datetime.utcnow().isoformat(),
        "result": None, "error": None,
    }
    background_tasks.add_task(_run_job, job_id, company_name, city, business_type, website)
    return {"job_id": job_id, "status": "running"}


def _run_job(job_id: str, company_name: str, city: str, business_type: str, website: str):
    try:
        from ...implantation_ia.pipeline import run_pipeline
    except ImportError:
        from src.implantation_ia.pipeline import run_pipeline

    try:
        result = run_pipeline(
            company_name=company_name, city=city,
            business_type=business_type, website=website,
        )
        if result["ok"]:
            _JOBS[job_id].update({
                "status": "done", "result": result,
                "score": result["score"],
                "nb_competitors": len(result.get("competitor_summaries", [])),
                "nb_gaps": len(result.get("gaps", [])),
            })
        else:
            _JOBS[job_id].update({"status": "error", "error": result.get("error", "")})
    except Exception as e:
        log.error("[implantation_ia] job %s échoué : %s", job_id, e)
        _JOBS[job_id].update({"status": "error", "error": str(e)})


@router.get("/api/implantation-ia/status/{job_id}")
def job_status(job_id: str, request: Request):
    if not _admin_ok(request):
        raise HTTPException(403)
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(404)
    return {
        "job_id":         job_id,
        "status":         job["status"],
        "score":          job.get("score"),
        "nb_competitors": job.get("nb_competitors", 0),
        "nb_gaps":        job.get("nb_gaps", 0),
        "error":          job.get("error"),
    }


@router.get("/api/implantation-ia/result/{job_id}", response_class=HTMLResponse)
def job_result_html(job_id: str, request: Request):
    if not _admin_ok(request):
        raise HTTPException(403)
    job = _JOBS.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(404)
    return HTMLResponse(job["result"].get("deliverable_html", "<p>Non disponible</p>"))


@router.get("/api/implantation-ia/result/{job_id}/json")
def job_result_json(job_id: str, request: Request):
    if not _admin_ok(request):
        raise HTTPException(403)
    job = _JOBS.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(404)
    return JSONResponse(job["result"].get("deliverable_json", {}))


@router.post("/api/implantation-ia/from-prospect/{token}")
async def run_from_prospect(token: str, request: Request, background_tasks: BackgroundTasks):
    """Lance le pipeline depuis un prospect V3 existant (réutilise ses ia_results)."""
    if not _admin_ok(request):
        raise HTTPException(403)

    from ...database import SessionLocal
    from ...models import V3ProspectDB
    db = SessionLocal()
    try:
        p = db.query(V3ProspectDB).filter(V3ProspectDB.token == token).first()
        if not p:
            raise HTTPException(404, "Prospect introuvable")

        import json as _json
        ia_results = None
        if p.ia_results:
            try:
                ia_results = _json.loads(p.ia_results) if isinstance(p.ia_results, str) else p.ia_results
            except Exception:
                pass

        job_id = str(uuid.uuid4())
        cn = p.name or token
        bt = p.profession or ""
        c  = p.city or ""
        ws = getattr(p, "website", "") or getattr(p, "url", "") or ""

        _JOBS[job_id] = {
            "id": job_id, "status": "running",
            "company_name": cn, "city": c, "business_type": bt, "website": ws,
            "created_at": datetime.utcnow().isoformat(), "result": None, "error": None,
        }
        background_tasks.add_task(_run_job_with_existing, job_id, cn, c, bt, ws, ia_results)
        return {"job_id": job_id, "status": "running", "prospect": cn}
    finally:
        db.close()


def _run_job_with_existing(job_id, company_name, city, business_type, website, existing):
    try:
        from ...implantation_ia.pipeline import run_pipeline
    except ImportError:
        from src.implantation_ia.pipeline import run_pipeline
    try:
        result = run_pipeline(
            company_name=company_name, city=city, business_type=business_type,
            website=website, existing_ia_results=existing,
        )
        if result["ok"]:
            _JOBS[job_id].update({
                "status": "done", "result": result, "score": result["score"],
                "nb_competitors": len(result.get("competitor_summaries", [])),
                "nb_gaps": len(result.get("gaps", [])),
            })
        else:
            _JOBS[job_id].update({"status": "error", "error": result.get("error", "")})
    except Exception as e:
        _JOBS[job_id].update({"status": "error", "error": str(e)})
