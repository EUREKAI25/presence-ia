"""
MARKETING_MODULE — FastAPI application
Mount as sub-app: app.mount("/mkt", mkt_app)
Or run standalone: uvicorn marketing_module.api.main:app
"""
import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..database import init_db
from .routes import (
    calendly_router, campaigns_router, compliance_router, crm_router, domains_router,
    mailboxes_router, reporting_router, rotation_router, send_router,
    sequences_router, social_router, warmup_router, webhooks_router,
)

log = logging.getLogger("mkt.api")

MKT_API_PREFIX = os.environ.get("MKT_API_PREFIX", "/mkt")

app = FastAPI(
    title="EURKAI — Marketing Module",
    version="1.0.0",
    description="Unified multi-channel marketing: email, SMS, social + CRM",
    root_path=MKT_API_PREFIX,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    log.info("MARKETING_MODULE started — DB initialized")


# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(domains_router)
app.include_router(mailboxes_router)
app.include_router(warmup_router)
app.include_router(rotation_router)
app.include_router(campaigns_router)
app.include_router(sequences_router)
app.include_router(send_router)
app.include_router(compliance_router)
app.include_router(reporting_router)
app.include_router(social_router)
app.include_router(crm_router)
app.include_router(webhooks_router)
app.include_router(calendly_router)


@app.get("/health")
def health():
    return {"status": "ok", "module": "marketing"}
