"""Instagram provider — stub (Graph API)."""
import logging
import os
import requests
from typing import Optional

log = logging.getLogger("mkt.instagram")
GRAPH_API = "https://graph.facebook.com/v19.0"


class InstagramProvider:

    def __init__(self, access_token: Optional[str] = None, ig_user_id: Optional[str] = None):
        self.access_token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        self.ig_user_id   = ig_user_id   or os.getenv("INSTAGRAM_USER_ID", "")

    def publish(self, content: str, media_url: Optional[str] = None,
                media_type: str = "IMAGE", post_id: Optional[str] = None) -> dict:
        if not self.access_token or not self.ig_user_id:
            return {"success": False, "error": "Instagram credentials not configured"}
        try:
            # Step 1: create media container
            payload = {"caption": content, "access_token": self.access_token}
            if media_url:
                payload["image_url" if media_type == "IMAGE" else "video_url"] = media_url
            r = requests.post(f"{GRAPH_API}/{self.ig_user_id}/media", data=payload, timeout=15)
            if r.status_code != 200:
                return {"success": False, "error": r.text}
            container_id = r.json().get("id")

            # Step 2: publish container
            r2 = requests.post(f"{GRAPH_API}/{self.ig_user_id}/media_publish",
                               data={"creation_id": container_id, "access_token": self.access_token},
                               timeout=15)
            if r2.status_code != 200:
                return {"success": False, "error": r2.text}
            return {"success": True, "message_id": r2.json().get("id")}
        except Exception as e:
            log.exception("Instagram publish error: %s", e)
            return {"success": False, "error": str(e)}

    def name(self) -> str:
        return "instagram"
