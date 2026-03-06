"""Brevo email provider — SMTP relay + REST API."""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import requests

from ....models import DnsStatus, SendingMailboxDB
from .base import AbstractEmailProvider

log = logging.getLogger("mkt.brevo")
BREVO_API_BASE = "https://api.brevo.com/v3"


class BrevoProvider(AbstractEmailProvider):

    def __init__(self, api_key: Optional[str] = None,
                 smtp_host: Optional[str] = None, smtp_port: Optional[int] = None):
        self.api_key   = api_key   or os.getenv("BREVO_API_KEY", "")
        self.smtp_host = smtp_host or os.getenv("BREVO_SMTP_HOST", "smtp-relay.brevo.com")
        self.smtp_port = smtp_port or int(os.getenv("BREVO_SMTP_PORT", "587"))
        if not self.api_key:
            raise ValueError("BREVO_API_KEY required")

    def _headers(self) -> dict:
        return {"api-key": self.api_key, "Content-Type": "application/json"}

    def send(self, mailbox: SendingMailboxDB, to_email: str, to_name: str,
             subject: str, body_html: str, body_text: Optional[str] = None,
             reply_to: Optional[str] = None, headers: Optional[dict] = None) -> dict:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"{mailbox.local_part} <{mailbox.email}>"
            msg["To"]      = f"{to_name} <{to_email}>" if to_name else to_email
            if reply_to:
                msg["Reply-To"] = reply_to
            for k, v in (headers or {}).items():
                msg[k] = v
            if body_text:
                msg.attach(MIMEText(body_text, "plain", "utf-8"))
            if body_html:
                msg.attach(MIMEText(body_html, "html", "utf-8"))

            username = mailbox.username or mailbox.email
            password = mailbox.password_enc or ""

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
                smtp.ehlo(); smtp.starttls(); smtp.login(username, password)
                smtp.sendmail(mailbox.email, to_email, msg.as_string())

            return {"success": True, "message_id": f"brevo-{mailbox.email}-{to_email}"}
        except smtplib.SMTPAuthenticationError as e:
            return {"success": False, "error": f"Auth failed: {e}", "code": "auth_error"}
        except smtplib.SMTPRecipientsRefused as e:
            return {"success": False, "error": f"Recipient refused: {e}", "code": "bounce_hard"}
        except Exception as e:
            log.exception("Brevo send error: %s", e)
            return {"success": False, "error": str(e), "code": "unknown"}

    def validate_domain(self, domain_name: str) -> dict:
        resp = requests.get(f"{BREVO_API_BASE}/senders/domains",
                            headers=self._headers(), timeout=10)
        if resp.status_code != 200:
            return {"success": False, "error": resp.text}
        for d in resp.json().get("domains", []):
            if d.get("domain_name") == domain_name or d.get("name") == domain_name:
                return {
                    "success": True,
                    "spf":   DnsStatus.valid if d.get("spf_verified")  else DnsStatus.invalid,
                    "dkim":  DnsStatus.valid if d.get("dkim_verified") else DnsStatus.invalid,
                    "dmarc": DnsStatus.valid if d.get("dmarc_configured") else DnsStatus.unknown,
                    "raw": d,
                }
        return {"success": False, "error": f"Domain {domain_name} not found in Brevo"}

    def get_sending_stats(self, mailbox_email: str, window_hours: int = 24) -> dict:
        from datetime import datetime, timedelta, timezone
        start = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).strftime("%Y-%m-%d")
        resp = requests.get(f"{BREVO_API_BASE}/smtp/statistics/aggregatedReport",
                            params={"startDate": start, "tag": mailbox_email},
                            headers=self._headers(), timeout=10)
        if resp.status_code != 200:
            return {"sent": 0, "bounced": 0, "opened": 0, "clicked": 0}
        data = resp.json()
        return {
            "sent":    data.get("delivered", 0),
            "bounced": data.get("hardBounces", 0) + data.get("softBounces", 0),
            "opened":  data.get("uniqueOpens", 0),
            "clicked": data.get("uniqueClicks", 0),
        }

    def name(self) -> str:
        return "brevo"
