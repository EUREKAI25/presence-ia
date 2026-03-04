"""
Routes retest mensuel — chantier 10F
POST /api/retest/prospect/{pid}/run
GET  /api/retest/prospect/{pid}/history
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db, db_get_prospect
from ...livrables.monthly_retest import run_retest, get_retest_history

router = APIRouter(tags=["Retest"])


@router.post("/api/retest/prospect/{pid}/run")
def api_retest_run(pid: str, dry_run: bool = False, db: Session = Depends(get_db)):
    if not db_get_prospect(db, pid):
        raise HTTPException(404, "Prospect introuvable")
    return run_retest(db, pid, dry_run=dry_run)


@router.get("/api/retest/prospect/{pid}/history")
def api_retest_history(pid: str, db: Session = Depends(get_db)):
    if not db_get_prospect(db, pid):
        raise HTTPException(404, "Prospect introuvable")
    history = get_retest_history(db, pid)
    return {
        "success": True,
        "result": {"prospect_id": pid, "history": history, "count": len(history)},
        "message": f"{len(history)} run(s) trouvé(s)",
        "error": None,
    }
