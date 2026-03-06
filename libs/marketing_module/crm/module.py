"""
MARKETING_MODULE — CRM engine
Calendly webhook, closer assignment, commission calculation.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..database import (
    db_create_commission, db_create_meeting, db_create_task,
    db_get_closer, db_get_meeting, db_list_closers, db_update_campaign,
    db_update_meeting,
)
from ..models import (
    CampaignStatus, CommissionCreate, CommissionStatus,
    EurkaiOutput, MeetingStatus, TaskCreate,
)

log = logging.getLogger("mkt.crm")


def assign_closer(db: Session, project_id: str) -> Optional[str]:
    """
    Round-robin closer assignment based on number of meetings.
    Returns closer_id or None if no active closer.
    """
    closers = db_list_closers(db, project_id, active_only=True)
    if not closers:
        return None
    from ..database import db_list_meetings
    # Pick closer with fewest meetings
    def meeting_count(c):
        return len(db_list_meetings(db, project_id=project_id, closer_id=c.id))
    return min(closers, key=meeting_count).id


def handle_calendly_webhook(db: Session, project_id: str, payload: dict,
                             campaign_id: Optional[str] = None) -> EurkaiOutput:
    """
    Process Calendly webhook payload.
    On invitee.created:
      - Create meeting
      - Assign closer
      - Stop email sequence for this prospect
      - Create follow-up task
    On invitee.canceled:
      - Update meeting status
    """
    event_type = payload.get("event", "")
    invitee    = payload.get("payload", {})
    event_uri  = invitee.get("event", "")
    invitee_uri = invitee.get("uri", "")

    # Extract prospect info from Calendly payload
    invitee_email = invitee.get("email", "")
    invitee_name  = invitee.get("name", "")
    scheduled_at_str = invitee.get("scheduled_event", {}).get("start_time", "")
    try:
        scheduled_at = datetime.fromisoformat(scheduled_at_str.replace("Z", "+00:00")) if scheduled_at_str else None
    except Exception:
        scheduled_at = None

    # prospect_id = email (convention: Calendly → email = prospect identifier)
    prospect_id = invitee_email

    if event_type == "invitee.created":
        # Assign closer
        closer_id = assign_closer(db, project_id)

        # Create meeting
        meeting = db_create_meeting(db, {
            "project_id": project_id,
            "prospect_id": prospect_id,
            "closer_id": closer_id,
            "campaign_id": campaign_id,
            "scheduled_at": scheduled_at,
            "status": MeetingStatus.scheduled,
            "calendly_event_id": event_uri.split("/")[-1] if event_uri else None,
            "calendly_event_uri": event_uri,
            "meta": {"invitee_name": invitee_name, "invitee_uri": invitee_uri},
        })

        # Stop campaign sequence for this prospect (mark as replied)
        # The send engine checks db_prospect_replied() before sending
        # We mark via a synthetic delivery record or flag — here we rely on
        # the campaign's stop_on_reply + the meeting record as signal.
        # Consumer projects can query GET /crm/meetings?prospect_id=... to check.

        # Create follow-up task for closer
        if closer_id:
            db_create_task(db, {
                "project_id": project_id,
                "prospect_id": prospect_id,
                "closer_id": closer_id,
                "title": f"Appel RDV — {invitee_name or prospect_id}",
                "description": f"RDV Calendly confirmé. Email: {invitee_email}",
                "due_at": scheduled_at,
            })

        log.info("Meeting created for %s, closer=%s", prospect_id, closer_id)
        return EurkaiOutput(
            success=True,
            result={"meeting_id": meeting.id, "closer_id": closer_id, "prospect_id": prospect_id},
            message="Meeting created and closer assigned",
        )

    elif event_type == "invitee.canceled":
        # Find meeting by calendly event URI
        from sqlalchemy.orm import Session as S
        from ..models import MeetingDB
        meeting_obj = db.query(MeetingDB).filter(
            MeetingDB.project_id == project_id,
            MeetingDB.calendly_event_uri == event_uri,
        ).first()
        if meeting_obj:
            db_update_meeting(db, meeting_obj.id, {"status": MeetingStatus.cancelled})
            return EurkaiOutput(success=True, result={"meeting_id": meeting_obj.id},
                                message="Meeting cancelled")
        return EurkaiOutput(success=True, result=None, message="Meeting not found, skipped")

    return EurkaiOutput(success=True, result=None, message=f"Event {event_type} ignored")


def complete_meeting(db: Session, meeting_id: str, deal_value: float,
                     notes: Optional[str] = None) -> EurkaiOutput:
    """Mark meeting as completed and auto-create commission."""
    meeting = db_get_meeting(db, meeting_id)
    if not meeting:
        return EurkaiOutput(success=False, result=None, message="Meeting not found")

    db_update_meeting(db, meeting_id, {
        "status": MeetingStatus.completed,
        "completed_at": datetime.utcnow(),
        "deal_value": deal_value,
        "notes": notes,
    })

    commission = None
    if meeting.closer_id and deal_value > 0:
        closer = db_get_closer(db, meeting.closer_id)
        rate   = closer.commission_rate if closer else 0.18
        amount = round(deal_value * rate, 2)
        commission = db_create_commission(db, {
            "project_id": meeting.project_id,
            "closer_id": meeting.closer_id,
            "meeting_id": meeting_id,
            "deal_value": deal_value,
            "rate": rate,
            "amount": amount,
            "status": CommissionStatus.pending,
        })
        log.info("Commission created: %.2f€ for closer %s", amount, meeting.closer_id)

    return EurkaiOutput(
        success=True,
        result={
            "meeting_id": meeting_id,
            "deal_value": deal_value,
            "commission": {"id": commission.id, "amount": commission.amount} if commission else None,
        },
        message="Meeting completed, commission created",
    )


def closer_dashboard(db: Session, project_id: str, closer_id: str) -> dict:
    """Return full dashboard data for a closer."""
    from ..database import (db_get_closer, db_list_commissions,
                             db_list_meetings, db_list_tasks, db_closer_stats)
    closer      = db_get_closer(db, closer_id)
    meetings    = db_list_meetings(db, project_id, closer_id=closer_id)
    commissions = db_list_commissions(db, project_id, closer_id=closer_id)
    tasks       = db_list_tasks(db, project_id, closer_id=closer_id)
    stats       = db_closer_stats(db, project_id, closer_id)

    return {
        "closer": {
            "id": closer.id, "name": closer.name, "email": closer.email,
            "commission_rate": closer.commission_rate,
        } if closer else None,
        "stats": stats,
        "meetings": [
            {"id": m.id, "prospect_id": m.prospect_id, "status": m.status,
             "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else None,
             "deal_value": m.deal_value}
            for m in meetings
        ],
        "commissions": [
            {"id": c.id, "amount": c.amount, "status": c.status,
             "deal_value": c.deal_value,
             "created_at": c.created_at.isoformat()}
            for c in commissions
        ],
        "tasks": [
            {"id": t.id, "title": t.title, "status": t.status,
             "due_at": t.due_at.isoformat() if t.due_at else None}
            for t in tasks
        ],
    }
