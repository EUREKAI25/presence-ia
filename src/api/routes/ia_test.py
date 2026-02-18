from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ...database import (
    db_get_campaign, db_get_job, db_list_runs, db_update_job, get_db, jl, new_session
)
from ...models import IATestRunInput, JobDB, JobStatus
from ...ia_test import active_models, run_campaign

router = APIRouter(prefix="/api", tags=["IA Test"])


# ── Worker arrière-plan ───────────────────────────────────────────────────

def _run_job(job_id: str, campaign_id: str, prospect_ids, dry_run: bool):
    """Exécuté hors du thread requête — session DB indépendante."""
    db = new_session()
    try:
        job = db_get_job(db, job_id)
        if not job:
            return

        db_update_job(db, job, status=JobStatus.RUNNING.value, started_at=datetime.utcnow())

        result = run_campaign(db, campaign_id, prospect_ids=prospect_ids or None, dry_run=dry_run)

        db_update_job(db, job,
            status=JobStatus.DONE.value,
            finished_at=datetime.utcnow(),
            total=result.get("total", 0),
            processed=result.get("processed", 0),
            runs_created=result.get("runs_created", 0),
            errors=__import__("json").dumps(result.get("errors", [])),
        )
    except Exception as e:
        db_update_job(db, job,
            status=JobStatus.FAILED.value,
            finished_at=datetime.utcnow(),
            errors=__import__("json").dumps([{"error": str(e)}]),
        )
    finally:
        db.close()


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/ia-test/run", status_code=202)
def api_run(data: IATestRunInput, background_tasks: BackgroundTasks,
            db: Session = Depends(get_db)):
    """
    Lance les tests IA en arrière-plan.
    Réponse immédiate HTTP 202 avec job_id.
    Suivre la progression via GET /api/jobs/{job_id}.
    """
    if not db_get_campaign(db, data.campaign_id):
        raise HTTPException(404, "Campagne introuvable")
    if not active_models() and not data.dry_run:
        raise HTTPException(400, "Aucune clé IA configurée (OPENAI/ANTHROPIC/GEMINI API_KEY)")

    models = active_models() if not data.dry_run else ["openai", "anthropic", "gemini"]

    job = JobDB(
        campaign_id=data.campaign_id,
        dry_run=data.dry_run,
        prospect_ids=__import__("json").dumps(data.prospect_ids or []),
        models_used=__import__("json").dumps(models),
        status=JobStatus.QUEUED.value,
    )
    from ...database import db_create_job
    db_create_job(db, job)

    background_tasks.add_task(
        _run_job, job.job_id, data.campaign_id, data.prospect_ids, data.dry_run
    )

    return JSONResponse(status_code=202, content={
        "job_id":      job.job_id,
        "campaign_id": data.campaign_id,
        "status":      JobStatus.QUEUED.value,
        "queued":      True,
        "models":      models,
        "poll":        f"/api/jobs/{job.job_id}",
    })


@router.get("/prospect/{pid}/runs")
def api_runs(pid: str, db: Session = Depends(get_db)):
    from ...database import db_get_prospect
    if not db_get_prospect(db, pid):
        raise HTTPException(404, "Prospect introuvable")
    runs = db_list_runs(db, pid)
    return {"prospect_id": pid, "total": len(runs), "runs": [
        {"run_id": r.run_id, "model": r.model, "ts": r.ts.isoformat(),
         "mentioned": r.mentioned_target, "mention_per_query": jl(r.mention_per_query),
         "competitors": jl(r.competitors_entities)[:5]} for r in runs]}
