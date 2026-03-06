"""Routes: /campaigns"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import (
    db_campaign_stats, db_create_campaign, db_get_campaign,
    db_list_campaigns, db_update_campaign, get_db,
)
from ...models import CampaignCreate, CampaignStatus, EurkaiOutput

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post("", response_model=EurkaiOutput)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    obj = db_create_campaign(db, payload.model_dump())
    return EurkaiOutput(success=True, result={
        "id": obj.id, "name": obj.name, "status": obj.status,
    }, message="Campaign created")


@router.get("", response_model=EurkaiOutput)
def list_campaigns(project_id: str, status: Optional[str] = None, db: Session = Depends(get_db)):
    rows = db_list_campaigns(db, project_id, status=status)
    return EurkaiOutput(success=True, result=[
        {"id": r.id, "name": r.name, "status": r.status,
         "channels": r.channels, "created_at": r.created_at.isoformat()}
        for r in rows
    ], message="OK")


@router.get("/{campaign_id}", response_model=EurkaiOutput)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    obj = db_get_campaign(db, campaign_id)
    if not obj:
        raise HTTPException(404, "Campaign not found")
    return EurkaiOutput(success=True, result={
        "id": obj.id, "name": obj.name, "status": obj.status,
        "channels": obj.channels, "project_id": obj.project_id,
        "rotation_strategy_id": obj.rotation_strategy_id,
        "stop_on_reply": obj.stop_on_reply, "stop_on_meeting": obj.stop_on_meeting,
        "created_at": obj.created_at.isoformat(),
    }, message="OK")


@router.get("/{campaign_id}/stats", response_model=EurkaiOutput)
def campaign_stats(campaign_id: str, db: Session = Depends(get_db)):
    if not db_get_campaign(db, campaign_id):
        raise HTTPException(404, "Campaign not found")
    stats = db_campaign_stats(db, campaign_id)
    return EurkaiOutput(success=True, result=stats, message="OK")


@router.patch("/{campaign_id}", response_model=EurkaiOutput)
def update_campaign(campaign_id: str, updates: dict, db: Session = Depends(get_db)):
    obj = db_update_campaign(db, campaign_id, updates)
    if not obj:
        raise HTTPException(404, "Campaign not found")
    return EurkaiOutput(success=True, result={"id": campaign_id, "status": obj.status}, message="Updated")


@router.post("/{campaign_id}/activate", response_model=EurkaiOutput)
def activate_campaign(campaign_id: str, db: Session = Depends(get_db)):
    obj = db_update_campaign(db, campaign_id, {"status": CampaignStatus.active})
    if not obj:
        raise HTTPException(404, "Campaign not found")
    return EurkaiOutput(success=True, result={"id": campaign_id, "status": obj.status}, message="Activated")


@router.post("/{campaign_id}/pause", response_model=EurkaiOutput)
def pause_campaign(campaign_id: str, db: Session = Depends(get_db)):
    obj = db_update_campaign(db, campaign_id, {"status": CampaignStatus.paused})
    if not obj:
        raise HTTPException(404, "Campaign not found")
    return EurkaiOutput(success=True, result={"id": campaign_id, "status": obj.status}, message="Paused")


@router.post("/{campaign_id}/stop", response_model=EurkaiOutput)
def stop_campaign(campaign_id: str, db: Session = Depends(get_db)):
    obj = db_update_campaign(db, campaign_id, {"status": CampaignStatus.stopped})
    if not obj:
        raise HTTPException(404, "Campaign not found")
    return EurkaiOutput(success=True, result={"id": campaign_id, "status": obj.status}, message="Stopped")
