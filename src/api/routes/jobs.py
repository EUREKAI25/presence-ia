"""
GET /api/jobs/{job_id} — Statut d'un job IA test
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import db_get_job, get_db, jl

router = APIRouter(prefix="/api", tags=["Jobs"])


@router.get("/jobs/{job_id}")
def api_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Statut d'un job de test IA lancé via POST /api/ia-test/run.

    Statuts possibles : QUEUED → RUNNING → DONE | FAILED

    Exemple de réponse DONE :
    {
      "job_id": "...",
      "campaign_id": "...",
      "status": "DONE",
      "progress": {"total": 5, "processed": 5, "runs_created": 15},
      "errors": [],
      "models": ["openai", "anthropic", "gemini"],
      "timestamps": {"created_at": "...", "started_at": "...", "finished_at": "..."}
    }
    """
    job = db_get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job introuvable")

    progress = None
    if job.status in ("RUNNING", "DONE", "FAILED"):
        progress = {
            "total":        job.total,
            "processed":    job.processed,
            "runs_created": job.runs_created,
            "pct":          round(job.processed / job.total * 100) if job.total else 0,
        }

    return {
        "job_id":      job.job_id,
        "campaign_id": job.campaign_id,
        "status":      job.status,
        "dry_run":     job.dry_run,
        "progress":    progress,
        "errors":      jl(job.errors),
        "models":      jl(job.models_used),
        "timestamps": {
            "created_at":  job.created_at.isoformat() if job.created_at  else None,
            "started_at":  job.started_at.isoformat()  if job.started_at  else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        },
    }
