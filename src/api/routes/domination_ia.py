"""
Routes API — Domination IA (9000€).
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()

_JOBS: dict[str, dict] = {}


def _admin_ok(request: Request) -> bool:
    token = request.query_params.get("token") or request.headers.get("X-Admin-Token", "")
    import os
    return token == os.getenv("ADMIN_TOKEN", "admin")


@router.get("/admin/domination-ia", response_class=HTMLResponse)
async def admin_domination_ia(request: Request):
    if not _admin_ok(request):
        return HTMLResponse("<h1>403</h1>", status_code=403)

    token = request.query_params.get("token", "admin")
    history_rows = ""
    for jid, job in sorted(_JOBS.items(), key=lambda x: x[1].get("created_at", ""), reverse=True)[:20]:
        status = job.get("status", "pending")
        score  = job.get("score", "—")
        name   = job.get("company_name", "")
        city   = job.get("city", "")
        color  = {"done": "#10b981", "error": "#ef4444", "running": "#f59e0b"}.get(status, "#94a3b8")
        result_link = f'<a href="/api/domination-ia/result/{jid}?token={token}" style="color:#818cf8" target="_blank">Voir livrable</a>' if status == "done" else "—"
        monthly_link = f'<a href="/api/domination-ia/monthly/{jid}?token={token}" style="color:#a78bfa" target="_blank">Rapport mensuel</a>' if status == "done" else "—"
        history_rows += f"""<tr>
          <td style="color:#94a3b8;font-size:0.8rem">{jid[:8]}…</td>
          <td>{name} / {city}</td>
          <td><span style="color:{color};font-weight:600">{status}</span></td>
          <td>{score}/10</td>
          <td>{result_link}</td>
          <td>{monthly_link}</td>
        </tr>"""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Admin — Domination IA</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#0f172a; color:#e2e8f0; padding:40px; }}
  .card {{ background:#1e293b; border-radius:12px; padding:28px; margin-bottom:24px; }}
  label {{ display:block; color:#94a3b8; font-size:0.85rem; margin-bottom:6px; margin-top:16px; }}
  input {{ width:100%; background:#0f172a; border:1px solid #334155; border-radius:6px;
           padding:10px 14px; color:#e2e8f0; font-size:0.95rem; }}
  button {{ margin-top:20px; background:#6366f1; color:#fff; border:none; border-radius:8px;
            padding:12px 28px; font-size:1rem; cursor:pointer; font-weight:600; }}
  button:hover {{ background:#818cf8; }}
  #status-box {{ margin-top:20px; padding:16px; background:#0f172a; border-radius:8px;
                 display:none; color:#94a3b8; }}
  table {{ width:100%; border-collapse:collapse; }}
  td, th {{ padding:10px 12px; text-align:left; border-bottom:1px solid #0f172a; }}
  th {{ font-size:0.8rem; text-transform:uppercase; color:#64748b; }}
  h1 {{ font-size:1.5rem; margin-bottom:4px; color:#fff; }}
  h3 {{ font-size:0.9rem; color:#64748b; margin-bottom:20px; }}
</style>
</head>
<body>
<div style="max-width:860px;margin:0 auto">
  <div class="card" style="background:linear-gradient(135deg,#1e1b4b,#312e81);border:1px solid #4338ca33">
    <h1>🏆 Domination IA — 9000€</h1>
    <h3>Stratégie complète · Tous concurrents · Plan 12 mois · Boucle mensuelle</h3>
  </div>

  <div class="card">
    <h2 style="margin-bottom:20px;font-size:1.1rem">Générer un livrable</h2>
    <label>Nom de l'entreprise</label>
    <input id="cn" placeholder="Ex : Plomberie Dupont" />
    <label>Ville</label>
    <input id="ci" placeholder="Ex : Lyon" />
    <label>Métier / secteur</label>
    <input id="bt" placeholder="Ex : plombier" />
    <label>Site web</label>
    <input id="ws" placeholder="Ex : https://dupont-plomberie.fr" />
    <label>Villes alentour (optionnel, séparées par virgule)</label>
    <input id="nc" placeholder="Ex : Villeurbanne, Vénissieux, Décines" />
    <button onclick="launch()">Générer le livrable Domination IA</button>
    <div id="status-box"></div>
  </div>

  <div class="card">
    <h2 style="margin-bottom:16px;font-size:1rem">Historique des livrables</h2>
    <table>
      <tr><th>ID</th><th>Client</th><th>Statut</th><th>Score</th><th>Livrable</th><th>Rapport mensuel</th></tr>
      {history_rows or '<tr><td colspan="6" style="color:#475569;text-align:center">Aucun livrable généré</td></tr>'}
    </table>
  </div>
</div>
<script>
async function launch() {{
  const body = {{
    company_name:   document.getElementById('cn').value,
    city:           document.getElementById('ci').value,
    business_type:  document.getElementById('bt').value,
    website:        document.getElementById('ws').value,
    nearby_cities:  document.getElementById('nc').value.split(',').map(s=>s.trim()).filter(Boolean),
  }};
  if (!body.company_name || !body.city || !body.business_type) {{
    alert('Veuillez remplir les 3 premiers champs.'); return;
  }}
  const box = document.getElementById('status-box');
  box.style.display = 'block';
  box.textContent = 'Lancement en cours…';

  const resp = await fetch('/api/domination-ia/run?token={token}', {{
    method: 'POST', headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify(body),
  }});
  const {{job_id}} = await resp.json();
  box.textContent = `Job lancé : ${{job_id}} — En cours (5-8 min)…`;

  const poll = setInterval(async () => {{
    const r = await fetch(`/api/domination-ia/status/${{job_id}}?token={token}`);
    const d = await r.json();
    if (d.status === 'done') {{
      clearInterval(poll);
      box.innerHTML = `✅ Terminé — Score : ${{d.score}}/10 — <a href="/api/domination-ia/result/${{job_id}}?token={token}" style="color:#818cf8" target="_blank">Voir le livrable</a>`;
      location.reload();
    }} else if (d.status === 'error') {{
      clearInterval(poll);
      box.textContent = `❌ Erreur : ${{d.error}}`;
    }} else {{
      box.textContent = `En cours… (${{d.step || 'analyse'}})`;
    }}
  }}, 8000);
}}
</script>
</body>
</html>""")


@router.post("/api/domination-ia/run")
async def run_domination(request: Request, background_tasks: BackgroundTasks):
    if not _admin_ok(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    data = await request.json()
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {
        "status":       "running",
        "created_at":   datetime.utcnow().isoformat(),
        "company_name": data.get("company_name", ""),
        "city":         data.get("city", ""),
        "step":         "init",
    }
    background_tasks.add_task(_run_job, job_id, data)
    return JSONResponse({"job_id": job_id})


async def _run_job(job_id: str, data: dict):
    try:
        from ...domination_ia.pipeline import run_pipeline

        _JOBS[job_id]["step"] = "pipeline"
        result = run_pipeline(
            company_name=data.get("company_name", ""),
            city=data.get("city", ""),
            business_type=data.get("business_type", ""),
            website=data.get("website", ""),
            nearby_cities=data.get("nearby_cities") or None,
            skip_ia=data.get("skip_ia", False),
            skip_competitors=data.get("skip_competitors", False),
        )

        score = result.get("score_data", {}).get("score", 0.0)
        _JOBS[job_id].update({
            "status":       "done",
            "score":        score,
            "nb_competitors": len(result.get("all_competitor_analyses", [])),
            "nb_gaps":      len(result.get("gaps", [])),
            "step":         "done",
            "result":       result,
        })
    except Exception as exc:
        _JOBS[job_id].update({"status": "error", "error": str(exc)})


@router.get("/api/domination-ia/status/{job_id}")
async def status_domination(job_id: str, request: Request):
    if not _admin_ok(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)
    job = _JOBS.get(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({
        "job_id":         job_id,
        "status":         job.get("status"),
        "score":          job.get("score"),
        "nb_competitors": job.get("nb_competitors"),
        "nb_gaps":        job.get("nb_gaps"),
        "step":           job.get("step"),
        "error":          job.get("error"),
    })


@router.get("/api/domination-ia/result/{job_id}", response_class=HTMLResponse)
async def result_domination(job_id: str, request: Request):
    if not _admin_ok(request):
        return HTMLResponse("<h1>403</h1>", status_code=403)
    job = _JOBS.get(job_id)
    if not job or job.get("status") != "done":
        return HTMLResponse("<h1>Not ready</h1>", status_code=404)
    html = job["result"].get("domination_deliverable_html", "<p>Livrable non disponible</p>")
    return HTMLResponse(html)


@router.get("/api/domination-ia/monthly/{job_id}", response_class=HTMLResponse)
async def monthly_report(job_id: str, request: Request):
    if not _admin_ok(request):
        return HTMLResponse("<h1>403</h1>", status_code=403)
    job = _JOBS.get(job_id)
    if not job or job.get("status") != "done":
        return HTMLResponse("<h1>Not ready</h1>", status_code=404)
    html = job["result"].get("monthly_report_html", "<p>Rapport non disponible</p>")
    return HTMLResponse(html)


@router.post("/api/domination-ia/from-prospect/{token}")
async def from_prospect(token: str, request: Request, background_tasks: BackgroundTasks):
    """Lance le pipeline depuis un prospect V3 existant."""
    try:
        from ...db.models import V3ProspectDB
        from sqlalchemy.orm import Session
        from ...db.session import get_db

        db: Session = next(get_db())
        prospect = db.query(V3ProspectDB).filter(V3ProspectDB.token == token).first()
        if not prospect:
            return JSONResponse({"error": "prospect not found"}, status_code=404)

        ia_results = prospect.ia_results or []
        job_id = str(uuid.uuid4())
        data = {
            "company_name":  prospect.company_name,
            "city":          prospect.city,
            "business_type": prospect.business_type,
            "website":       prospect.website or "",
        }
        _JOBS[job_id] = {
            "status": "running", "created_at": datetime.utcnow().isoformat(),
            **data, "step": "init",
        }
        background_tasks.add_task(_run_job, job_id, {**data, "skip_ia": bool(ia_results)})
        return JSONResponse({"job_id": job_id})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
