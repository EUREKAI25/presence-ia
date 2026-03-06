"""
GoogleCalendarClient — API Google Calendar v3
Créer/supprimer des événements bloquants pour synchronisation Calendly.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger("mkt.gcal")

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarClient:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        calendar_id: Optional[str] = None,
    ):
        self.client_id = client_id or os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "")
        self.refresh_token = refresh_token or os.environ.get("GOOGLE_CALENDAR_REFRESH_TOKEN", "")
        self.calendar_id = calendar_id or os.environ.get("GOOGLE_CALENDAR_ID", "primary")
        self._access_token: Optional[str] = None

    # ── Auth ───────────────────────────────────────────────────────────────────

    def _get_access_token(self) -> str:
        """Obtenir un access token via refresh token (OAuth2)."""
        r = requests.post(GOOGLE_TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }, timeout=10)
        r.raise_for_status()
        self._access_token = r.json()["access_token"]
        return self._access_token

    def _headers(self) -> dict:
        token = self._get_access_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ── Calendriers ────────────────────────────────────────────────────────────

    def list_calendars(self) -> list[dict]:
        """Lister tous les agendas du compte."""
        r = requests.get(f"{GOOGLE_CALENDAR_API}/users/me/calendarList",
                         headers=self._headers(), timeout=10)
        r.raise_for_status()
        return [
            {"id": c["id"], "summary": c["summary"],
             "primary": c.get("primary", False)}
            for c in r.json().get("items", [])
        ]

    # ── Événements ─────────────────────────────────────────────────────────────

    def create_blocking_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        description: str = "Bloqué via Présence IA",
        calendar_id: Optional[str] = None,
    ) -> dict:
        """
        Créer un événement bloquant dans Google Agenda.
        Calendly détecte automatiquement l'événement et bloque le créneau.
        """
        cal_id = calendar_id or self.calendar_id
        tz = "Europe/Paris"

        body = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": tz},
            "end":   {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"),   "timeZone": tz},
            "transparency": "opaque",   # marque comme "occupé"
            "status": "confirmed",
        }
        r = requests.post(
            f"{GOOGLE_CALENDAR_API}/calendars/{cal_id}/events",
            headers=self._headers(), json=body, timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        log.info("Événement créé : %s (%s → %s)", title, start, end)
        return {"id": data["id"], "summary": data["summary"],
                "start": data["start"]["dateTime"], "end": data["end"]["dateTime"],
                "html_link": data.get("htmlLink")}

    def delete_event(self, event_id: str, calendar_id: Optional[str] = None) -> bool:
        """Supprimer un événement bloquant."""
        cal_id = calendar_id or self.calendar_id
        r = requests.delete(
            f"{GOOGLE_CALENDAR_API}/calendars/{cal_id}/events/{event_id}",
            headers=self._headers(), timeout=10,
        )
        ok = r.status_code in (200, 204)
        if ok:
            log.info("Événement supprimé : %s", event_id)
        return ok

    def list_events(
        self,
        time_min: datetime,
        time_max: datetime,
        calendar_id: Optional[str] = None,
    ) -> list[dict]:
        """Lister les événements sur une période."""
        cal_id = calendar_id or self.calendar_id
        params = {
            "timeMin": time_min.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeMax": time_max.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        r = requests.get(
            f"{GOOGLE_CALENDAR_API}/calendars/{cal_id}/events",
            headers=self._headers(), params=params, timeout=10,
        )
        r.raise_for_status()
        return [
            {"id": e["id"], "summary": e.get("summary", ""),
             "start": e["start"].get("dateTime", e["start"].get("date")),
             "end":   e["end"].get("dateTime", e["end"].get("date"))}
            for e in r.json().get("items", [])
        ]

    def block_slots(self, slots: list[dict], calendar_id: Optional[str] = None) -> list[dict]:
        """
        Bloquer plusieurs créneaux d'un coup.
        slots = [{"title": str, "start": "2026-04-08T09:00:00", "end": "2026-04-08T10:00:00"}, ...]
        """
        results = []
        for s in slots:
            start = datetime.fromisoformat(s["start"])
            end   = datetime.fromisoformat(s["end"])
            evt = self.create_blocking_event(
                title=s.get("title", "Indisponible"),
                start=start, end=end,
                calendar_id=calendar_id,
            )
            results.append(evt)
        return results
