"""Twilio SMS provider — stub prêt à câbler."""
import logging
import os
from typing import Optional

log = logging.getLogger("mkt.twilio")


class TwilioProvider:

    def __init__(self, account_sid: Optional[str] = None,
                 auth_token: Optional[str] = None,
                 from_number: Optional[str] = None):
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token  = auth_token  or os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = from_number or os.getenv("TWILIO_FROM_NUMBER", "")

    def send(self, to_number: str, body: str, delivery_id: Optional[str] = None) -> dict:
        if not self.account_sid or not self.auth_token:
            return {"success": False, "error": "Twilio credentials not configured", "code": "not_configured"}
        try:
            from twilio.rest import Client
            client = Client(self.account_sid, self.auth_token)
            message = client.messages.create(
                body=body,
                from_=self.from_number,
                to=to_number,
            )
            log.info("SMS sent via Twilio: %s → %s (%s)", self.from_number, to_number, message.sid)
            return {"success": True, "message_id": message.sid}
        except ImportError:
            return {"success": False, "error": "twilio package not installed. pip install twilio", "code": "import_error"}
        except Exception as e:
            log.exception("Twilio send error: %s", e)
            return {"success": False, "error": str(e), "code": "unknown"}

    def name(self) -> str:
        return "twilio"
