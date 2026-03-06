"""Routes: /warmup"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import db_create_warmup, db_get_warmup, db_list_warmups, db_update_warmup, get_db
from ...models import EurkaiOutput, WarmupStrategyCreate
from ...module import apply_warmup_step

router = APIRouter(prefix="/warmup", tags=["Warmup"])


@router.post("", response_model=EurkaiOutput)
def create_warmup(payload: WarmupStrategyCreate, db: Session = Depends(get_db)):
    obj = db_create_warmup(db, payload.model_dump())
    return EurkaiOutput(success=True, result={"id": obj.id, "name": obj.name}, message="Warmup strategy created")


@router.get("", response_model=EurkaiOutput)
def list_warmups(project_id: str, db: Session = Depends(get_db)):
    rows = db_list_warmups(db, project_id)
    return EurkaiOutput(success=True, result=[
        {"id": r.id, "name": r.name, "max_daily_volume": r.max_daily_volume,
         "total_days": r.total_days}
        for r in rows
    ], message="OK")


@router.get("/{warmup_id}", response_model=EurkaiOutput)
def get_warmup(warmup_id: str, db: Session = Depends(get_db)):
    obj = db_get_warmup(db, warmup_id)
    if not obj:
        raise HTTPException(404, "Warmup strategy not found")
    return EurkaiOutput(success=True, result={
        "id": obj.id, "name": obj.name, "max_daily_volume": obj.max_daily_volume,
        "total_days": obj.total_days, "ramp_schedule": obj.ramp_schedule,
        "health_rules": obj.health_rules, "auto_pause_on_issue": obj.auto_pause_on_issue,
    }, message="OK")


@router.patch("/{warmup_id}", response_model=EurkaiOutput)
def update_warmup(warmup_id: str, updates: dict, db: Session = Depends(get_db)):
    obj = db_update_warmup(db, warmup_id, updates)
    if not obj:
        raise HTTPException(404, "Warmup strategy not found")
    return EurkaiOutput(success=True, result={"id": warmup_id}, message="Updated")


@router.post("/mailboxes/{mailbox_id}/step", response_model=EurkaiOutput)
def step_warmup(mailbox_id: str, db: Session = Depends(get_db)):
    """Advance warmup by one day (called by scheduler)."""
    return apply_warmup_step(db, mailbox_id)
