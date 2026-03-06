"""Routes: /rotation"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import (
    db_create_rotation, db_get_rotation, db_list_rotations, db_update_rotation, get_db,
)
from ...models import EurkaiOutput, RotationStrategyCreate

router = APIRouter(prefix="/rotation", tags=["Rotation"])


@router.post("", response_model=EurkaiOutput)
def create_rotation(payload: RotationStrategyCreate, db: Session = Depends(get_db)):
    obj = db_create_rotation(db, payload.model_dump())
    return EurkaiOutput(success=True, result={
        "id": obj.id, "name": obj.name, "algorithm": obj.algorithm,
    }, message="Rotation strategy created")


@router.get("", response_model=EurkaiOutput)
def list_rotations(project_id: str, db: Session = Depends(get_db)):
    rows = db_list_rotations(db, project_id)
    return EurkaiOutput(success=True, result=[
        {"id": r.id, "name": r.name, "algorithm": r.algorithm,
         "per_mailbox_daily_cap": r.per_mailbox_daily_cap}
        for r in rows
    ], message="OK")


@router.get("/{rotation_id}", response_model=EurkaiOutput)
def get_rotation(rotation_id: str, db: Session = Depends(get_db)):
    obj = db_get_rotation(db, rotation_id)
    if not obj:
        raise HTTPException(404, "Rotation strategy not found")
    return EurkaiOutput(success=True, result={
        "id": obj.id, "name": obj.name, "algorithm": obj.algorithm,
        "per_mailbox_daily_cap": obj.per_mailbox_daily_cap,
        "domain_rotation": obj.domain_rotation,
    }, message="OK")


@router.patch("/{rotation_id}", response_model=EurkaiOutput)
def update_rotation(rotation_id: str, updates: dict, db: Session = Depends(get_db)):
    obj = db_update_rotation(db, rotation_id, updates)
    if not obj:
        raise HTTPException(404, "Rotation strategy not found")
    return EurkaiOutput(success=True, result={"id": rotation_id}, message="Updated")
