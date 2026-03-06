"""Routes: /domains"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import (
    db_create_domain, db_get_domain, db_list_domains,
    db_update_domain, get_db,
)
from ...models import DnsStatus, EurkaiOutput, SendingDomainCreate

router = APIRouter(prefix="/domains", tags=["Domains"])


@router.post("", response_model=EurkaiOutput)
def create_domain(payload: SendingDomainCreate, db: Session = Depends(get_db)):
    obj = db_create_domain(db, payload.model_dump())
    return EurkaiOutput(success=True, result={"id": obj.id, "domain": obj.domain,
                                               "dns_status": obj.dns_status}, message="Domain created")


@router.get("", response_model=EurkaiOutput)
def list_domains(project_id: str, db: Session = Depends(get_db)):
    rows = db_list_domains(db, project_id)
    return EurkaiOutput(success=True, result=[
        {"id": r.id, "domain": r.domain, "role": r.role,
         "dns_status": r.dns_status, "verified_at": r.verified_at.isoformat() if r.verified_at else None}
        for r in rows
    ], message="OK")


@router.get("/{domain_id}", response_model=EurkaiOutput)
def get_domain(domain_id: str, db: Session = Depends(get_db)):
    obj = db_get_domain(db, domain_id)
    if not obj:
        raise HTTPException(404, "Domain not found")
    return EurkaiOutput(success=True, result={"id": obj.id, "domain": obj.domain,
                                               "role": obj.role, "dns_status": obj.dns_status}, message="OK")


@router.post("/{domain_id}/validate", response_model=EurkaiOutput)
def validate_domain(domain_id: str, db: Session = Depends(get_db)):
    """Trigger DNS validation via Brevo API."""
    obj = db_get_domain(db, domain_id)
    if not obj:
        raise HTTPException(404, "Domain not found")
    try:
        from ...channels.email.providers.brevo import BrevoProvider
        import os
        provider = BrevoProvider(
            api_key=os.environ.get("BREVO_API_KEY", ""),
            smtp_login=os.environ.get("BREVO_SMTP_LOGIN", ""),
            smtp_password=os.environ.get("BREVO_SMTP_PASSWORD", ""),
        )
        result = provider.validate_domain(obj.domain)
        if result.get("authenticated"):
            from datetime import datetime
            db_update_domain(db, domain_id, {
                "dns_status": DnsStatus.verified,
                "verified_at": datetime.utcnow(),
            })
        return EurkaiOutput(success=True, result=result, message="Validation done")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/{domain_id}", response_model=EurkaiOutput)
def update_domain(domain_id: str, updates: dict, db: Session = Depends(get_db)):
    obj = db_update_domain(db, domain_id, updates)
    if not obj:
        raise HTTPException(404, "Domain not found")
    return EurkaiOutput(success=True, result={"id": obj.id, "dns_status": obj.dns_status}, message="Updated")
