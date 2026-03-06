"""Pinterest provider — stub (Pinterest API v5)."""
import logging
import os
import requests
from typing import Optional

log = logging.getLogger("mkt.pinterest")
PINTEREST_API = "https://api.pinterest.com/v5"


class PinterestProvider:

    def __init__(self, access_token: Optional[str] = None, board_id: Optional[str] = None):
        self.access_token = access_token or os.getenv("PINTEREST_ACCESS_TOKEN", "")
        self.board_id     = board_id     or os.getenv("PINTEREST_BOARD_ID", "")

    def publish(self, title: str, description: str, media_url: str,
                link: Optional[str] = None, board_id: Optional[str] = None) -> dict:
        if not self.access_token:
            return {"success": False, "error": "Pinterest credentials not configured"}
        try:
            payload = {
                "board_id": board_id or self.board_id,
                "title": title,
                "description": description,
                "media_source": {"source_type": "image_url", "url": media_url},
            }
            if link:
                payload["link"] = link
            r = requests.post(
                f"{PINTEREST_API}/pins",
                json=payload,
                headers={"Authorization": f"Bearer {self.access_token}",
                         "Content-Type": "application/json"},
                timeout=15,
            )
            if r.status_code in (200, 201):
                return {"success": True, "message_id": r.json().get("id"),
                        "url": f"https://pinterest.com/pin/{r.json().get('id')}"}
            return {"success": False, "error": r.text}
        except Exception as e:
            log.exception("Pinterest publish error: %s", e)
            return {"success": False, "error": str(e)}

    def name(self) -> str:
        return "pinterest"
