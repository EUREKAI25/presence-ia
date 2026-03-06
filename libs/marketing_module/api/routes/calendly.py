"""Routes: /calendly — Setup et gestion webhooks Calendly."""
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...models import EurkaiOutput

router = APIRouter(prefix="/calendly", tags=["Calendly"])


class CalendlySetupRequest(BaseModel):
    project_id: str
    base_url: str  # ex: "https://presence-ia.com"
    scope: str = "user"  # "user" ou "organization"


@router.post("/setup", response_model=EurkaiOutput)
def setup_webhook(payload: CalendlySetupRequest):
    """
    Enregistre automatiquement le webhook Calendly pour un projet.
    Idempotent : ne crée pas de doublon si déjà actif.
    """
    token = os.environ.get("CALENDLY_TOKEN", "")
    if not token:
        raise HTTPException(500, "CALENDLY_TOKEN non configuré")
    try:
        from ...channels.calendly.client import CalendlyClient
        client = CalendlyClient(token=token)
        result = client.setup_webhook_for_project(
            project_id=payload.project_id,
            base_url=payload.base_url,
            scope=payload.scope,
        )
        return EurkaiOutput(success=True, result=result, message=result["message"])
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/webhooks", response_model=EurkaiOutput)
def list_webhooks():
    """Liste les webhooks Calendly actifs."""
    token = os.environ.get("CALENDLY_TOKEN", "")
    if not token:
        raise HTTPException(500, "CALENDLY_TOKEN non configuré")
    try:
        from ...channels.calendly.client import CalendlyClient
        client = CalendlyClient(token=token)
        user = client.get_current_user()
        webhooks = client.list_webhooks(
            organization_uri=user["organization_uri"],
            user_uri=user["uri"],
        )
        return EurkaiOutput(success=True, result={
            "user": user,
            "webhooks": webhooks,
            "count": len(webhooks),
        }, message="OK")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/webhooks/{webhook_uuid}", response_model=EurkaiOutput)
def delete_webhook(webhook_uuid: str):
    """Supprime un webhook Calendly."""
    token = os.environ.get("CALENDLY_TOKEN", "")
    if not token:
        raise HTTPException(500, "CALENDLY_TOKEN non configuré")
    try:
        from ...channels.calendly.client import CalendlyClient
        client = CalendlyClient(token=token)
        ok = client.delete_webhook(webhook_uuid)
        return EurkaiOutput(success=ok, result={"uuid": webhook_uuid},
                            message="Deleted" if ok else "Not found")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/event-types", response_model=EurkaiOutput)
def list_event_types():
    """Liste les types de RDV Calendly (liens de réservation)."""
    token = os.environ.get("CALENDLY_TOKEN", "")
    if not token:
        raise HTTPException(500, "CALENDLY_TOKEN non configuré")
    try:
        from ...channels.calendly.client import CalendlyClient
        client = CalendlyClient(token=token)
        user = client.get_current_user()
        event_types = client.list_event_types(user["uri"])
        return EurkaiOutput(success=True, result={
            "user": user["name"],
            "scheduling_url": user["scheduling_url"],
            "event_types": event_types,
        }, message="OK")
    except Exception as e:
        raise HTTPException(500, str(e))
