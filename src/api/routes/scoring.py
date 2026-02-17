from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...database import get_db, db_get_campaign, db_get_prospect, jl
from ...models import ScoringRunInput
from ...scoring import run_scoring

router = APIRouter(prefix="/api", tags=["Scoring"])


@router.post("/scoring/run")
def api_scoring(data: ScoringRunInput, db: Session = Depends(get_db)):
    if not db_get_campaign(db, data.campaign_id): raise HTTPException(404, "Campagne introuvable")
    return {"campaign_id": data.campaign_id, **run_scoring(db, data.campaign_id, data.prospect_ids)}


@router.get("/prospect/{pid}/score")
def api_score(pid: str, db: Session = Depends(get_db)):
    p = db_get_prospect(db, pid)
    if not p: raise HTTPException(404, "Prospect introuvable")
    return {"prospect_id": pid, "name": p.name, "score": p.ia_visibility_score,
            "eligible": p.eligibility_flag, "competitors": jl(p.competitors_cited),
            "justification": p.score_justification, "status": p.status}
