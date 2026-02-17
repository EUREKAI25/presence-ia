"""
PRESENCE_IA — FastAPI app
Démarrer : uvicorn src.api.main:app --reload --port 8001
"""
import logging, os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="PRESENCE_IA — Référencement IA", version="1.0.0", docs_url="/docs")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    from ..database import init_db
    init_db()
    log.info("DB initialisée (SQLite)")


@app.get("/health")
def health():
    return {"status": "ok", "service": "presence_ia", "version": "1.0.0"}


@app.get("/", response_class=HTMLResponse)
def root():
    return HTMLResponse("""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>PRESENCE_IA</title>
<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh}
.c{text-align:center;max-width:560px;padding:40px 20px}
h1{font-size:2.2rem;color:#fff;margin-bottom:12px}h1 span{color:#e94560}
p{color:#aaa;margin-bottom:32px;font-size:1.1rem}
.btns{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}
.btn{padding:12px 28px;border-radius:6px;font-weight:bold;text-decoration:none;font-size:1rem}
.btn-primary{background:#e94560;color:#fff}.btn-secondary{background:#1a1a2e;color:#e8e8f0;border:1px solid #2a2a4e}
</style></head><body><div class="c">
<h1>PRESENCE <span>IA</span></h1>
<p>Pipeline d'audit de visibilité IA pour artisans locaux.</p>
<div class="btns">
  <a href="/docs" class="btn btn-primary">API Docs</a>
  <a href="/health" class="btn btn-secondary">Health</a>
</div>
</div></body></html>""")


# ── Routes ──
from .routes import campaign, ia_test, scoring, generate, admin, pipeline

app.include_router(campaign.router)
app.include_router(ia_test.router)
app.include_router(scoring.router)
app.include_router(generate.router)
app.include_router(admin.router)
app.include_router(pipeline.router)
