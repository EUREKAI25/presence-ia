"""
google_calendar.py — Intégration Google Calendar API (OAuth2 refresh token).

Usage :
    from .google_calendar import gcal_create_event, gcal_generate_ics

    event = gcal_create_event(
        title="Audit Présence IA — Dupont Plomberie",
        start_iso="2026-04-15T10:00:00",
        end_iso="2026-04-15T10:20:00",
        attendee_email="prospect@exemple.com",
        attendee_name="Jean Dupont",
        description="Audit de visibilité IA — 20 min",
    )
    # event = {"id": "...", "html_link": "...", "meet_link": "...", "ics_uid": "..."}
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("gcal")

TIMEZONE = "Europe/Paris"


def _get_access_token() -> str:
    """Échange le refresh token contre un access token via OAuth2."""
    import requests as _req
    resp = _req.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id":     os.getenv("GOOGLE_CALENDAR_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET", ""),
            "refresh_token": os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN", ""),
            "grant_type":    "refresh_token",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def gcal_create_event(
    title: str,
    start_iso: str,
    end_iso: str,
    attendee_email: str,
    attendee_name: str = "",
    description: str = "",
    add_meet: bool = False,
) -> dict:
    """
    Crée un événement dans Google Calendar et invite le prospect.
    Retourne un dict avec les clés :
        id, html_link, meet_link (si add_meet=True), ics_uid
    Lève une exception si la création échoue.
    """
    import requests as _req

    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    access_token = _get_access_token()

    body: dict = {
        "summary":     title,
        "description": description,
        "start":       {"dateTime": start_iso, "timeZone": TIMEZONE},
        "end":         {"dateTime": end_iso,   "timeZone": TIMEZONE},
        "reminders":   {"useDefault": False, "overrides": [
            {"method": "email",  "minutes": 60},
            {"method": "popup",  "minutes": 15},
        ]},
        "status": "confirmed",
        "sendUpdates": "none",
    }

    if add_meet:
        body["conferenceData"] = {
            "createRequest": {
                "requestId":             f"presence-ia-{int(datetime.now(timezone.utc).timestamp())}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    params = {"conferenceDataVersion": 1} if add_meet else {}

    resp = _req.post(
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=body,
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    meet_link = ""
    if add_meet:
        meet_link = (
            data.get("conferenceData", {})
                .get("entryPoints", [{}])[0]
                .get("uri", "")
        )

    log.info("GCal event créé : %s → %s", data.get("id", "?"), title)
    return {
        "id":        data["id"],
        "html_link": data.get("htmlLink", ""),
        "meet_link": meet_link,
        "ics_uid":   data.get("iCalUID", ""),
    }


def gcal_generate_ics(
    title: str,
    start_iso: str,
    end_iso: str,
    organizer_email: str,
    attendee_email: str,
    attendee_name: str = "",
    description: str = "",
    uid: str = "",
) -> str:
    """
    Génère le contenu d'un fichier .ics (iCalendar) compatible tous clients.
    start_iso / end_iso : "2026-04-15T10:00:00" (heure locale Paris)
    """
    import re
    from datetime import timedelta

    # Convertir en UTC pour le .ics
    from zoneinfo import ZoneInfo
    paris = ZoneInfo("Europe/Paris")
    utc   = timezone.utc

    def _to_utc_str(iso: str) -> str:
        dt_local = datetime.fromisoformat(iso).replace(tzinfo=paris)
        dt_utc   = dt_local.astimezone(utc)
        return dt_utc.strftime("%Y%m%dT%H%M%SZ")

    dt_start = _to_utc_str(start_iso)
    dt_end   = _to_utc_str(end_iso)
    now_utc  = datetime.now(utc).strftime("%Y%m%dT%H%M%SZ")
    uid_val  = uid or f"presence-ia-{dt_start}@presence-ia.com"

    # Échapper le texte pour .ics
    def _esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Présence IA//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uid_val}",
        f"DTSTAMP:{now_utc}",
        f"DTSTART:{dt_start}",
        f"DTEND:{dt_end}",
        f"SUMMARY:{_esc(title)}",
        f"DESCRIPTION:{_esc(description)}",
        f"ORGANIZER;CN=Présence IA:mailto:{organizer_email}",
        f"ATTENDEE;CN={_esc(attendee_name)};RSVP=TRUE:mailto:{attendee_email}",
        "STATUS:CONFIRMED",
        "SEQUENCE:0",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


def gcal_google_add_url(
    title: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
) -> str:
    """Génère un lien 'Ajouter à Google Agenda' (pas besoin d'API)."""
    from urllib.parse import urlencode
    from zoneinfo import ZoneInfo

    paris = ZoneInfo("Europe/Paris")
    utc   = timezone.utc

    def _fmt(iso: str) -> str:
        dt = datetime.fromisoformat(iso).replace(tzinfo=paris).astimezone(utc)
        return dt.strftime("%Y%m%dT%H%M%SZ")

    params = {
        "action":  "TEMPLATE",
        "text":    title,
        "dates":   f"{_fmt(start_iso)}/{_fmt(end_iso)}",
        "details": description,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)
