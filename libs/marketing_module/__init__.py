"""
EURKAI — MARKETING_MODULE
Unified multi-channel marketing: email (Brevo), SMS (Twilio), social (Instagram/Pinterest) + CRM.

Mount as FastAPI sub-app:
    from marketing_module.api.main import app as mkt_app
    parent_app.mount("/mkt", mkt_app)

Or run standalone:
    uvicorn marketing_module.api.main:app --port 8100
"""
from .api.main import app
from .module import execute_send_batch, choose_next_mailbox, check_compliance
from .crm.module import handle_calendly_webhook, complete_meeting

__version__ = "1.0.0"

__all__ = [
    "app",
    "execute_send_batch",
    "choose_next_mailbox",
    "check_compliance",
    "handle_calendly_webhook",
    "complete_meeting",
]
