"""Routes: /compliance"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import (
    db_create_rule, db_get_rule, db_list_rules, db_update_rule, get_db,
)
from ...models import ComplianceRuleCreate, EurkaiOutput
from ...module import check_compliance

router = APIRouter(prefix="/compliance", tags=["Compliance"])


@router.post("/rules", response_model=EurkaiOutput)
def create_rule(payload: ComplianceRuleCreate, db: Session = Depends(get_db)):
    obj = db_create_rule(db, payload.model_dump())
    return EurkaiOutput(success=True, result={
        "id": obj.id, "name": obj.name, "rule_type": obj.rule_type,
    }, message="Compliance rule created")


@router.get("/rules", response_model=EurkaiOutput)
def list_rules(project_id: str, db: Session = Depends(get_db)):
    rows = db_list_rules(db, project_id)
    return EurkaiOutput(success=True, result=[
        {"id": r.id, "name": r.name, "rule_type": r.rule_type, "scope": r.scope,
         "threshold": r.threshold, "action_on_trigger": r.action_on_trigger}
        for r in rows
    ], message="OK")


@router.get("/rules/{rule_id}", response_model=EurkaiOutput)
def get_rule(rule_id: str, db: Session = Depends(get_db)):
    obj = db_get_rule(db, rule_id)
    if not obj:
        raise HTTPException(404, "Rule not found")
    return EurkaiOutput(success=True, result={
        "id": obj.id, "name": obj.name, "rule_type": obj.rule_type,
        "scope": obj.scope, "threshold": obj.threshold,
        "window_hours": obj.window_hours, "action_on_trigger": obj.action_on_trigger,
    }, message="OK")


@router.patch("/rules/{rule_id}", response_model=EurkaiOutput)
def update_rule(rule_id: str, updates: dict, db: Session = Depends(get_db)):
    obj = db_update_rule(db, rule_id, updates)
    if not obj:
        raise HTTPException(404, "Rule not found")
    return EurkaiOutput(success=True, result={"id": rule_id}, message="Updated")


@router.post("/check", response_model=EurkaiOutput)
def check(project_id: str, mailbox_id: str, campaign_id: str, db: Session = Depends(get_db)):
    """Evaluate all compliance rules for a mailbox/campaign pair."""
    triggered = check_compliance(db, project_id, mailbox_id, campaign_id)
    return EurkaiOutput(success=True, result={"triggered": triggered,
                                               "count": len(triggered)}, message="OK")
