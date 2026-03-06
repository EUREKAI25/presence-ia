"""Routes: /mailboxes"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import (
    db_create_mailbox, db_get_mailbox, db_list_mailboxes,
    db_mailbox_stats, db_update_mailbox, get_db,
)
from ...models import EurkaiOutput, SendingMailboxCreate

router = APIRouter(prefix="/mailboxes", tags=["Mailboxes"])


@router.post("", response_model=EurkaiOutput)
def create_mailbox(payload: SendingMailboxCreate, db: Session = Depends(get_db)):
    obj = db_create_mailbox(db, payload.model_dump())
    return EurkaiOutput(success=True, result={
        "id": obj.id, "email": obj.email, "daily_limit": obj.daily_limit,
    }, message="Mailbox created")


@router.get("", response_model=EurkaiOutput)
def list_mailboxes(project_id: str, domain_id: Optional[str] = None,
                   active_only: bool = True, db: Session = Depends(get_db)):
    rows = db_list_mailboxes(db, project_id, domain_id=domain_id, active_only=active_only)
    return EurkaiOutput(success=True, result=[
        {"id": r.id, "email": r.email, "daily_limit": r.daily_limit,
         "sent_today": r.sent_today or 0, "warmup_status": r.warmup_status,
         "reputation_status": r.reputation_status, "is_active": r.is_active}
        for r in rows
    ], message="OK")


@router.get("/{mailbox_id}", response_model=EurkaiOutput)
def get_mailbox(mailbox_id: str, db: Session = Depends(get_db)):
    obj = db_get_mailbox(db, mailbox_id)
    if not obj:
        raise HTTPException(404, "Mailbox not found")
    return EurkaiOutput(success=True, result={
        "id": obj.id, "email": obj.email, "daily_limit": obj.daily_limit,
        "hourly_limit": obj.hourly_limit, "sent_today": obj.sent_today or 0,
        "warmup_status": obj.warmup_status, "warmup_day": obj.warmup_day,
        "reputation_status": obj.reputation_status, "is_active": obj.is_active,
    }, message="OK")


@router.get("/{mailbox_id}/stats", response_model=EurkaiOutput)
def mailbox_stats(mailbox_id: str, window_hours: int = 24, db: Session = Depends(get_db)):
    if not db_get_mailbox(db, mailbox_id):
        raise HTTPException(404, "Mailbox not found")
    stats = db_mailbox_stats(db, mailbox_id, window_hours=window_hours)
    return EurkaiOutput(success=True, result=stats, message="OK")


@router.patch("/{mailbox_id}", response_model=EurkaiOutput)
def update_mailbox(mailbox_id: str, updates: dict, db: Session = Depends(get_db)):
    obj = db_update_mailbox(db, mailbox_id, updates)
    if not obj:
        raise HTTPException(404, "Mailbox not found")
    return EurkaiOutput(success=True, result={"id": mailbox_id}, message="Updated")


@router.post("/{mailbox_id}/reset-daily", response_model=EurkaiOutput)
def reset_daily(mailbox_id: str, db: Session = Depends(get_db)):
    """Reset sent_today counter (to be called by cron at midnight)."""
    obj = db_update_mailbox(db, mailbox_id, {"sent_today": 0, "sent_this_hour": 0})
    if not obj:
        raise HTTPException(404, "Mailbox not found")
    return EurkaiOutput(success=True, result={"id": mailbox_id}, message="Counters reset")


@router.post("/{mailbox_id}/test-smtp", response_model=EurkaiOutput)
def test_smtp(mailbox_id: str, db: Session = Depends(get_db)):
    """Send a test email via the mailbox SMTP config."""
    obj = db_get_mailbox(db, mailbox_id)
    if not obj:
        raise HTTPException(404, "Mailbox not found")
    try:
        import os
        from ...channels.email.providers.brevo import BrevoProvider
        provider = BrevoProvider(
            api_key=os.environ.get("BREVO_API_KEY", ""),
            smtp_login=os.environ.get("BREVO_SMTP_LOGIN", ""),
            smtp_password=os.environ.get("BREVO_SMTP_PASSWORD", ""),
        )
        result = provider.send(
            mailbox=obj,
            delivery_id="test",
            prospect_id="test@example.com",
            sequence_step_id="test",
        )
        return EurkaiOutput(success=result.get("success", False), result=result, message="SMTP test done")
    except Exception as e:
        raise HTTPException(500, str(e))
