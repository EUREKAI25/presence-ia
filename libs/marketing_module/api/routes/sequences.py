"""Routes: /sequences"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import (
    db_create_sequence, db_create_sequence_step, db_get_sequence,
    db_get_sequence_step, db_list_sequences, db_list_sequence_steps,
    db_update_sequence, db_update_sequence_step, get_db,
)
from ...models import EurkaiOutput, SequenceCreate, SequenceStepCreate

router = APIRouter(prefix="/sequences", tags=["Sequences"])


# ── Sequences ──────────────────────────────────────────────────────────────────

@router.post("", response_model=EurkaiOutput)
def create_sequence(payload: SequenceCreate, db: Session = Depends(get_db)):
    obj = db_create_sequence(db, payload.model_dump())
    return EurkaiOutput(success=True, result={"id": obj.id, "name": obj.name}, message="Sequence created")


@router.get("", response_model=EurkaiOutput)
def list_sequences(project_id: str, campaign_id: Optional[str] = None, db: Session = Depends(get_db)):
    rows = db_list_sequences(db, project_id, campaign_id=campaign_id)
    return EurkaiOutput(success=True, result=[
        {"id": r.id, "name": r.name, "campaign_id": r.campaign_id, "is_active": r.is_active}
        for r in rows
    ], message="OK")


@router.get("/{sequence_id}", response_model=EurkaiOutput)
def get_sequence(sequence_id: str, db: Session = Depends(get_db)):
    obj = db_get_sequence(db, sequence_id)
    if not obj:
        raise HTTPException(404, "Sequence not found")
    steps = db_list_sequence_steps(db, sequence_id)
    return EurkaiOutput(success=True, result={
        "id": obj.id, "name": obj.name, "campaign_id": obj.campaign_id,
        "is_active": obj.is_active,
        "steps": [
            {"id": s.id, "step_number": s.step_number, "channel": s.channel,
             "delay_days": s.delay_days, "subject": s.subject, "body_html": s.body_html,
             "body_text": s.body_text, "sms_body": s.sms_body}
            for s in steps
        ],
    }, message="OK")


@router.patch("/{sequence_id}", response_model=EurkaiOutput)
def update_sequence(sequence_id: str, updates: dict, db: Session = Depends(get_db)):
    obj = db_update_sequence(db, sequence_id, updates)
    if not obj:
        raise HTTPException(404, "Sequence not found")
    return EurkaiOutput(success=True, result={"id": sequence_id}, message="Updated")


# ── Steps ──────────────────────────────────────────────────────────────────────

@router.post("/{sequence_id}/steps", response_model=EurkaiOutput)
def create_step(sequence_id: str, payload: SequenceStepCreate, db: Session = Depends(get_db)):
    if not db_get_sequence(db, sequence_id):
        raise HTTPException(404, "Sequence not found")
    data = payload.model_dump()
    data["sequence_id"] = sequence_id
    obj = db_create_sequence_step(db, data)
    return EurkaiOutput(success=True, result={
        "id": obj.id, "step_number": obj.step_number, "channel": obj.channel,
    }, message="Step created")


@router.get("/{sequence_id}/steps", response_model=EurkaiOutput)
def list_steps(sequence_id: str, db: Session = Depends(get_db)):
    if not db_get_sequence(db, sequence_id):
        raise HTTPException(404, "Sequence not found")
    steps = db_list_sequence_steps(db, sequence_id)
    return EurkaiOutput(success=True, result=[
        {"id": s.id, "step_number": s.step_number, "channel": s.channel,
         "delay_days": s.delay_days, "subject": s.subject}
        for s in steps
    ], message="OK")


@router.patch("/{sequence_id}/steps/{step_id}", response_model=EurkaiOutput)
def update_step(sequence_id: str, step_id: str, updates: dict, db: Session = Depends(get_db)):
    obj = db_update_sequence_step(db, step_id, updates)
    if not obj:
        raise HTTPException(404, "Step not found")
    return EurkaiOutput(success=True, result={"id": step_id}, message="Updated")
