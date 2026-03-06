"""
CalendlyClient — API Calendly v2
Gestion des webhooks, event types et invités.
"""
import logging
import os
from typing import Optional

import requests

log = logging.getLogger("mkt.calendly")

CALENDLY_API_BASE = "https://api.calendly.com"


class CalendlyClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("CALENDLY_TOKEN", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: dict = None) -> dict:
        r = self.session.get(f"{CALENDLY_API_BASE}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, payload: dict) -> dict:
        r = self.session.post(f"{CALENDLY_API_BASE}{path}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> bool:
        r = self.session.delete(f"{CALENDLY_API_BASE}{path}", timeout=10)
        return r.status_code in (200, 204)

    # ── Identity ───────────────────────────────────────────────────────────────

    def get_current_user(self) -> dict:
        """Return current user + organization URIs."""
        data = self._get("/users/me")
        return {
            "uri": data["resource"]["uri"],
            "name": data["resource"]["name"],
            "email": data["resource"]["email"],
            "organization_uri": data["resource"]["current_organization"],
            "scheduling_url": data["resource"]["scheduling_url"],
        }

    # ── Event types ────────────────────────────────────────────────────────────

    def list_event_types(self, user_uri: str, active_only: bool = True) -> list[dict]:
        """List all event types (booking links) for the user."""
        params = {"user": user_uri}
        if active_only:
            params["active"] = "true"
        data = self._get("/event_types", params=params)
        return [
            {
                "uri": et["uri"],
                "name": et["name"],
                "slug": et["slug"],
                "duration": et["duration"],
                "scheduling_url": et["scheduling_url"],
                "active": et["active"],
            }
            for et in data.get("collection", [])
        ]

    # ── Webhooks ───────────────────────────────────────────────────────────────

    def list_webhooks(self, organization_uri: str, user_uri: Optional[str] = None) -> list[dict]:
        """List existing webhook subscriptions."""
        params = {"organization": organization_uri, "scope": "organization"}
        if user_uri:
            params["user"] = user_uri
            params["scope"] = "user"
        data = self._get("/webhook_subscriptions", params=params)
        return [
            {
                "uri": w["uri"],
                "uuid": w["uri"].split("/")[-1],
                "callback_url": w["callback_url"],
                "events": w["events"],
                "state": w["state"],
                "created_at": w["created_at"],
            }
            for w in data.get("collection", [])
        ]

    def register_webhook(
        self,
        callback_url: str,
        organization_uri: str,
        user_uri: str,
        events: list[str] = None,
        scope: str = "user",
    ) -> dict:
        """
        Register a webhook subscription.
        scope: "user" (events for this user only) or "organization" (all users in org)
        """
        if events is None:
            events = ["invitee.created", "invitee.canceled"]

        payload = {
            "url": callback_url,
            "events": events,
            "organization": organization_uri,
            "scope": scope,
        }
        if scope == "user":
            payload["user"] = user_uri

        data = self._post("/webhook_subscriptions", payload)
        resource = data.get("resource", {})
        return {
            "uri": resource.get("uri"),
            "uuid": resource.get("uri", "").split("/")[-1],
            "callback_url": resource.get("callback_url"),
            "events": resource.get("events"),
            "state": resource.get("state"),
            "created_at": resource.get("created_at"),
        }

    def delete_webhook(self, webhook_uuid: str) -> bool:
        """Delete a webhook subscription by UUID."""
        return self._delete(f"/webhook_subscriptions/{webhook_uuid}")

    def setup_webhook_for_project(
        self,
        project_id: str,
        base_url: str,
        scope: str = "user",
    ) -> dict:
        """
        Full setup: get user info, check existing webhooks, register if missing.
        base_url: e.g. "https://presence-ia.com"
        Returns {"created": bool, "webhook": dict, "user": dict, "event_types": list}
        """
        user = self.get_current_user()
        callback_url = f"{base_url}/mkt/webhooks/calendly?project_id={project_id}"

        # Check if already registered
        existing = self.list_webhooks(
            organization_uri=user["organization_uri"],
            user_uri=user["uri"],
        )
        for w in existing:
            if w["callback_url"] == callback_url and w["state"] == "active":
                log.info("Webhook already registered: %s", w["uri"])
                event_types = self.list_event_types(user["uri"])
                return {
                    "created": False,
                    "webhook": w,
                    "user": user,
                    "event_types": event_types,
                    "message": "Webhook already active",
                }

        # Register new webhook
        webhook = self.register_webhook(
            callback_url=callback_url,
            organization_uri=user["organization_uri"],
            user_uri=user["uri"],
            scope=scope,
        )
        event_types = self.list_event_types(user["uri"])
        log.info("Webhook registered: %s → %s", webhook.get("uuid"), callback_url)
        return {
            "created": True,
            "webhook": webhook,
            "user": user,
            "event_types": event_types,
            "message": f"Webhook registered for project '{project_id}'",
        }
