"""
REF_IA — FastAPI app
Démarrer : uvicorn src.api.main:app --reload --port 8001
"""
import logging, os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="REF_IA — Référencement IA", version="1.0.0", docs_url="/docs")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    from ..database import init_db
    init_db()
    log.info("DB initialisée (SQLite)")


@app.get("/health")
def health():
    return {"status": "ok", "service": "ref_ia", "version": "1.0.0"}


# ── Routes ──
from .routes import campaign, ia_test, scoring, generate, admin, pipeline

app.include_router(campaign.router)
app.include_router(ia_test.router)
app.include_router(scoring.router)
app.include_router(generate.router)
app.include_router(admin.router)
app.include_router(pipeline.router)
