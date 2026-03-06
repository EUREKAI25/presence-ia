"""Routes: /send"""
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Channel, EurkaiOutput
from ...module import execute_send_batch

router = APIRouter(prefix="/send", tags=["Send"])


class BatchSendRequest(BaseModel):
    project_id: str
    campaign_id: str
    prospect_ids: list[str]
    sequence_step_id: str
    channel: str = Channel.email
    scheduled_at: Optional[str] = None
    dry_run: bool = False


@router.post("/batch", response_model=EurkaiOutput)
def batch_send(payload: BatchSendRequest, db: Session = Depends(get_db)):
    """
    Trigger a batch send for a list of prospect IDs.
    Channel-aware: dispatches to email (Brevo) or SMS (Twilio) provider.
    """
    from datetime import datetime

    scheduled_at = None
    if payload.scheduled_at:
        try:
            scheduled_at = datetime.fromisoformat(payload.scheduled_at)
        except ValueError:
            raise HTTPException(400, "Invalid scheduled_at format (use ISO 8601)")

    if payload.channel == Channel.email:
        from ...channels.email.providers.brevo import BrevoProvider
        provider = BrevoProvider(
            api_key=os.environ.get("BREVO_API_KEY", ""),
            smtp_login=os.environ.get("BREVO_SMTP_LOGIN", ""),
            smtp_password=os.environ.get("BREVO_SMTP_PASSWORD", ""),
        )
    elif payload.channel == Channel.sms:
        from ...channels.sms.providers.twilio import TwilioProvider
        provider = TwilioProvider(
            account_sid=os.environ.get("TWILIO_ACCOUNT_SID", ""),
            auth_token=os.environ.get("TWILIO_AUTH_TOKEN", ""),
            from_number=os.environ.get("TWILIO_FROM_NUMBER", ""),
        )
    else:
        raise HTTPException(400, f"Unsupported channel for batch send: {payload.channel}")

    return execute_send_batch(
        db=db,
        project_id=payload.project_id,
        campaign_id=payload.campaign_id,
        prospect_ids=payload.prospect_ids,
        sequence_step_id=payload.sequence_step_id,
        channel_provider=provider,
        channel=payload.channel,
        scheduled_at=scheduled_at,
        dry_run=payload.dry_run,
    )
