"""Routes CRM: /crm/closers, /crm/meetings, /crm/commissions, /crm/tasks"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import (
    db_create_closer, db_create_meeting, db_create_task,
    db_get_closer, db_get_meeting, db_get_task,
    db_list_closers, db_list_meetings, db_list_commissions, db_list_tasks,
    db_update_closer, db_update_meeting, db_update_commission, db_update_task,
    db_create_commission, get_db,
)
from ...models import (
    CloserCreate, CloserOut, CommissionCreate, CommissionStatus,
    EurkaiOutput, MeetingCreate, MeetingOut, MeetingStatus, TaskCreate,
)
from ...crm.module import complete_meeting, closer_dashboard

router = APIRouter(prefix="/crm", tags=["CRM"])


# ── Closers ────────────────────────────────────────────────────────────────────

@router.post("/closers", response_model=EurkaiOutput)
def create_closer(payload: CloserCreate, db: Session = Depends(get_db)):
    obj = db_create_closer(db, payload.model_dump())
    return EurkaiOutput(success=True, result=CloserOut.model_validate(obj).model_dump(), message="Closer created")

@router.get("/closers", response_model=EurkaiOutput)
def list_closers(project_id: str, active_only: bool = True, db: Session = Depends(get_db)):
    rows = db_list_closers(db, project_id, active_only=active_only)
    return EurkaiOutput(success=True, result=[CloserOut.model_validate(r).model_dump() for r in rows], message="OK")

@router.get("/closers/{closer_id}", response_model=EurkaiOutput)
def get_closer(closer_id: str, db: Session = Depends(get_db)):
    obj = db_get_closer(db, closer_id)
    if not obj: raise HTTPException(404, "Closer not found")
    return EurkaiOutput(success=True, result=CloserOut.model_validate(obj).model_dump(), message="OK")

@router.get("/closers/{closer_id}/dashboard", response_model=EurkaiOutput)
def closer_dash(closer_id: str, project_id: str, db: Session = Depends(get_db)):
    data = closer_dashboard(db, project_id, closer_id)
    return EurkaiOutput(success=True, result=data, message="OK")

@router.patch("/closers/{closer_id}", response_model=EurkaiOutput)
def update_closer(closer_id: str, updates: dict, db: Session = Depends(get_db)):
    obj = db_update_closer(db, closer_id, updates)
    if not obj: raise HTTPException(404, "Closer not found")
    return EurkaiOutput(success=True, result=CloserOut.model_validate(obj).model_dump(), message="Updated")


# ── Meetings ───────────────────────────────────────────────────────────────────

@router.post("/meetings", response_model=EurkaiOutput)
def create_meeting(payload: MeetingCreate, db: Session = Depends(get_db)):
    obj = db_create_meeting(db, payload.model_dump())
    return EurkaiOutput(success=True, result=MeetingOut.model_validate(obj).model_dump(), message="Meeting created")

@router.get("/meetings", response_model=EurkaiOutput)
def list_meetings(project_id: str, closer_id: Optional[str] = None,
                  status: Optional[str] = None, db: Session = Depends(get_db)):
    rows = db_list_meetings(db, project_id, closer_id=closer_id, status=status)
    return EurkaiOutput(success=True, result=[MeetingOut.model_validate(r).model_dump() for r in rows], message="OK")

@router.get("/meetings/{meeting_id}", response_model=EurkaiOutput)
def get_meeting(meeting_id: str, db: Session = Depends(get_db)):
    obj = db_get_meeting(db, meeting_id)
    if not obj: raise HTTPException(404, "Meeting not found")
    return EurkaiOutput(success=True, result=MeetingOut.model_validate(obj).model_dump(), message="OK")

@router.post("/meetings/{meeting_id}/complete", response_model=EurkaiOutput)
def complete_meeting_route(meeting_id: str, deal_value: float,
                           notes: Optional[str] = None, db: Session = Depends(get_db)):
    return complete_meeting(db, meeting_id, deal_value, notes)

@router.patch("/meetings/{meeting_id}", response_model=EurkaiOutput)
def update_meeting(meeting_id: str, updates: dict, db: Session = Depends(get_db)):
    obj = db_update_meeting(db, meeting_id, updates)
    if not obj: raise HTTPException(404, "Meeting not found")
    return EurkaiOutput(success=True, result=MeetingOut.model_validate(obj).model_dump(), message="Updated")


# ── Commissions ────────────────────────────────────────────────────────────────

@router.get("/commissions", response_model=EurkaiOutput)
def list_commissions(project_id: str, closer_id: Optional[str] = None,
                     status: Optional[str] = None, db: Session = Depends(get_db)):
    rows = db_list_commissions(db, project_id, closer_id=closer_id, status=status)
    return EurkaiOutput(success=True, result=[
        {"id": r.id, "closer_id": r.closer_id, "meeting_id": r.meeting_id,
         "amount": r.amount, "rate": r.rate, "deal_value": r.deal_value,
         "status": r.status, "created_at": r.created_at.isoformat()}
        for r in rows
    ], message="OK")

@router.post("/commissions/{commission_id}/approve", response_model=EurkaiOutput)
def approve_commission(commission_id: str, db: Session = Depends(get_db)):
    obj = db_update_commission(db, commission_id, {"status": CommissionStatus.approved})
    if not obj: raise HTTPException(404, "Commission not found")
    return EurkaiOutput(success=True, result={"id": commission_id, "status": obj.status}, message="Approved")

@router.post("/commissions/{commission_id}/pay", response_model=EurkaiOutput)
def pay_commission(commission_id: str, db: Session = Depends(get_db)):
    from datetime import datetime
    obj = db_update_commission(db, commission_id, {
        "status": CommissionStatus.paid, "paid_at": datetime.utcnow()
    })
    if not obj: raise HTTPException(404, "Commission not found")
    return EurkaiOutput(success=True, result={"id": commission_id, "status": obj.status}, message="Paid")


# ── Tasks ──────────────────────────────────────────────────────────────────────

@router.post("/tasks", response_model=EurkaiOutput)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    obj = db_create_task(db, payload.model_dump())
    return EurkaiOutput(success=True, result={"id": obj.id, "title": obj.title}, message="Task created")

@router.get("/tasks", response_model=EurkaiOutput)
def list_tasks(project_id: str, closer_id: Optional[str] = None,
               prospect_id: Optional[str] = None, db: Session = Depends(get_db)):
    rows = db_list_tasks(db, project_id, closer_id=closer_id, prospect_id=prospect_id)
    return EurkaiOutput(success=True, result=[
        {"id": t.id, "title": t.title, "status": t.status, "prospect_id": t.prospect_id,
         "closer_id": t.closer_id, "due_at": t.due_at.isoformat() if t.due_at else None}
        for t in rows
    ], message="OK")

@router.patch("/tasks/{task_id}", response_model=EurkaiOutput)
def update_task(task_id: str, updates: dict, db: Session = Depends(get_db)):
    obj = db_update_task(db, task_id, updates)
    if not obj: raise HTTPException(404, "Task not found")
    return EurkaiOutput(success=True, result={"id": task_id, "status": obj.status}, message="Updated")
