"""Routes webhooks: Calendly + bounce/reply/open/click"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import (
    BounceInput, CalendlyWebhookPayload, DeliveryResultInput,
    EurkaiOutput, ReplyInput,
)
from ...module import handle_bounce, handle_click, handle_open, handle_reply
from ...crm.module import handle_calendly_webhook

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/calendly", response_model=EurkaiOutput)
def calendly_webhook(payload: CalendlyWebhookPayload,
                     project_id: str,
                     campaign_id: Optional[str] = None,
                     db: Session = Depends(get_db)):
    """
    Calendly webhook endpoint.
    Configure dans Calendly : POST /mkt/webhooks/calendly?project_id=presence-ia
    Events : invitee.created, invitee.canceled
    """
    return handle_calendly_webhook(
        db=db,
        project_id=project_id,
        payload={"event": payload.event, "payload": payload.payload},
        campaign_id=campaign_id,
    )


@router.post("/delivery", response_model=EurkaiOutput)
def webhook_delivery(payload: DeliveryResultInput, db: Session = Depends(get_db)):
    from ...database import db_update_delivery, db_get_delivery
    from datetime import datetime
    delivery = db_get_delivery(db, payload.delivery_id)
    if not delivery:
        raise HTTPException(404, "Delivery not found")
    updates = {"delivery_status": payload.status,
               "provider_message_id": payload.provider_message_id,
               "error_message": payload.error_message}
    from ...models import DeliveryStatus
    if payload.status == DeliveryStatus.sent:
        updates["sent_at"] = datetime.utcnow()
    db_update_delivery(db, payload.delivery_id, updates)
    return EurkaiOutput(success=True, result={"delivery_id": payload.delivery_id}, message="Updated")


@router.post("/bounce", response_model=EurkaiOutput)
def webhook_bounce(payload: BounceInput, db: Session = Depends(get_db)):
    return handle_bounce(db, payload.delivery_id, payload.bounce_type, payload.error_message or "")


@router.post("/reply", response_model=EurkaiOutput)
def webhook_reply(payload: ReplyInput, db: Session = Depends(get_db)):
    return handle_reply(db, payload.delivery_id, payload.reply_status)


@router.get("/open/{delivery_id}", response_model=EurkaiOutput)
def webhook_open(delivery_id: str, db: Session = Depends(get_db)):
    return handle_open(db, delivery_id)


@router.get("/click/{delivery_id}", response_model=EurkaiOutput)
def webhook_click(delivery_id: str, db: Session = Depends(get_db)):
    return handle_click(db, delivery_id)
