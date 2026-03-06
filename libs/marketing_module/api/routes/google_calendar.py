"""
Routes Google Calendar — bloquer/débloquer des créneaux, lister les événements.
Toutes les credentials sont lues depuis l'environnement (secrets.env).
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...channels.google_calendar.client import GoogleCalendarClient

router = APIRouter(prefix="/gcal", tags=["google-calendar"])


def _client() -> GoogleCalendarClient:
    return GoogleCalendarClient()


# ── Schémas ────────────────────────────────────────────────────────────────────

class SlotIn(BaseModel):
    title: str
    start: str   # ISO 8601 : "2026-04-08T09:00:00"
    end:   str   # ISO 8601 : "2026-04-08T10:00:00"
    description: Optional[str] = "Indisponible — Présence IA"
    calendar_id: Optional[str] = None


class SlotsIn(BaseModel):
    slots: list[SlotIn]
    calendar_id: Optional[str] = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/calendars")
def list_calendars():
    """Lister tous les agendas du compte Google connecté."""
    try:
        return _client().list_calendars()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/events")
def list_events(
    time_min: str,
    time_max: str,
    calendar_id: Optional[str] = None,
):
    """
    Lister les événements sur une période.
    time_min / time_max : ISO 8601, ex. "2026-04-01T00:00:00"
    """
    try:
        tmin = datetime.fromisoformat(time_min)
        tmax = datetime.fromisoformat(time_max)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Format date invalide : {e}")

    try:
        client = _client()
        return client.list_events(tmin, tmax, calendar_id=calendar_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/block")
def block_slot(slot: SlotIn):
    """Créer un événement bloquant (Calendly détecte automatiquement)."""
    try:
        start = datetime.fromisoformat(slot.start)
        end   = datetime.fromisoformat(slot.end)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Format date invalide : {e}")

    try:
        evt = _client().create_blocking_event(
            title=slot.title,
            start=start,
            end=end,
            description=slot.description or "Indisponible — Présence IA",
            calendar_id=slot.calendar_id,
        )
        return evt
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/block-batch")
def block_slots_batch(body: SlotsIn):
    """Bloquer plusieurs créneaux en une requête."""
    raw = [s.model_dump() for s in body.slots]
    if body.calendar_id:
        for s in raw:
            s.setdefault("calendar_id", body.calendar_id)
    try:
        return _client().block_slots(raw, calendar_id=body.calendar_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/events/{event_id}")
def delete_event(event_id: str, calendar_id: Optional[str] = None):
    """Supprimer un événement bloquant (libère le créneau Calendly)."""
    try:
        ok = _client().delete_event(event_id, calendar_id=calendar_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        return {"deleted": event_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
