"""Routes: /reporting"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import db_campaign_stats, db_get_campaign, db_mailbox_stats, db_get_mailbox, get_db
from ...models import EurkaiOutput

router = APIRouter(prefix="/reporting", tags=["Reporting"])


@router.get("/campaigns/{campaign_id}", response_model=EurkaiOutput)
def campaign_report(campaign_id: str, db: Session = Depends(get_db)):
    if not db_get_campaign(db, campaign_id):
        raise HTTPException(404, "Campaign not found")
    stats = db_campaign_stats(db, campaign_id)
    return EurkaiOutput(success=True, result=stats, message="OK")


@router.get("/mailboxes/{mailbox_id}", response_model=EurkaiOutput)
def mailbox_report(mailbox_id: str, window_hours: int = 24, db: Session = Depends(get_db)):
    if not db_get_mailbox(db, mailbox_id):
        raise HTTPException(404, "Mailbox not found")
    stats = db_mailbox_stats(db, mailbox_id, window_hours=window_hours)
    return EurkaiOutput(success=True, result=stats, message="OK")


@router.get("/projects/{project_id}/summary", response_model=EurkaiOutput)
def project_summary(project_id: str, db: Session = Depends(get_db)):
    """Aggregate stats across all campaigns for a project."""
    from ...database import db_list_campaigns, db_list_mailboxes
    campaigns = db_list_campaigns(db, project_id)
    mailboxes = db_list_mailboxes(db, project_id, active_only=False)

    campaign_stats = []
    for c in campaigns:
        s = db_campaign_stats(db, c.id)
        campaign_stats.append({"id": c.id, "name": c.name, "status": c.status, **s})

    return EurkaiOutput(success=True, result={
        "project_id": project_id,
        "total_campaigns": len(campaigns),
        "total_mailboxes": len(mailboxes),
        "active_mailboxes": sum(1 for m in mailboxes if m.is_active),
        "campaigns": campaign_stats,
    }, message="OK")
