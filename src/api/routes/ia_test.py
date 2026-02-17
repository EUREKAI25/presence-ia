from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...database import get_db, db_get_campaign, db_list_runs, jl
from ...models import IATestRunInput
from ...ia_test import run_campaign, active_models

router = APIRouter(prefix="/api", tags=["IA Test"])


@router.post("/ia-test/run")
def api_run(data: IATestRunInput, db: Session = Depends(get_db)):
    if not db_get_campaign(db, data.campaign_id): raise HTTPException(404, "Campagne introuvable")
    if not active_models() and not data.dry_run:
        raise HTTPException(400, "Aucune clé IA configurée (OPENAI/ANTHROPIC/GEMINI API_KEY)")
    r = run_campaign(db, data.campaign_id, prospect_ids=data.prospect_ids, dry_run=data.dry_run)
    return {"campaign_id": data.campaign_id, "models": active_models(), **r}


@router.get("/prospect/{pid}/runs")
def api_runs(pid: str, db: Session = Depends(get_db)):
    from ...database import db_get_prospect
    if not db_get_prospect(db, pid): raise HTTPException(404, "Prospect introuvable")
    runs = db_list_runs(db, pid)
    return {"prospect_id": pid, "total": len(runs), "runs": [
        {"run_id": r.run_id, "model": r.model, "ts": r.ts.isoformat(),
         "mentioned": r.mentioned_target, "mention_per_query": jl(r.mention_per_query),
         "competitors": jl(r.competitors_entities)[:5]} for r in runs]}
