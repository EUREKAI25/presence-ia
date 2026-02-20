"""
PRESENCE_IA — FastAPI app
Démarrer : uvicorn src.api.main:app --reload --port 8001
"""
import logging, os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="PRESENCE_IA — Référencement IA", version="1.0.0", docs_url="/docs")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def redirect_403_to_login(request: Request, call_next):
    """Redirige les 403 sur /admin/* vers /admin/login pour les navigateurs."""
    response = await call_next(request)
    path = request.url.path
    accept = request.headers.get("accept", "")
    is_browser = "text/html" in accept
    if (response.status_code == 403
            and path.startswith("/admin")
            and not path.startswith("/api/admin")
            and is_browser):
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/admin/login", status_code=303)
    return response


@app.on_event("startup")
def startup():
    from ..database import init_db
    init_db()
    log.info("DB initialisée (SQLite)")

    # offers_module — branché sur la même DB SQLite
    from offers_module import init_module as offers_init
    db_path = os.getenv("DB_PATH", str(Path(__file__).parent.parent.parent / "data" / "presence_ia.db"))
    offers_init(db_url=f"sqlite:///{db_path}")
    log.info("offers_module initialisé")

    # Scheduler — prospection automatique toutes les heures
    try:
        from ..scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        log.warning("Scheduler non démarré : %s", e)

    # Montage fichiers statiques (créé si absent, silencieux si permission refusée)
    dist_root = Path(__file__).parent.parent.parent / "dist"
    for sub, route, name in [
        ("uploads", "/dist/uploads", "uploads"),
        ("evidence", "/dist/evidence", "evidence"),
        ("headers",  "/dist/headers",  "headers"),
    ]:
        d = dist_root / sub
        try:
            d.mkdir(parents=True, exist_ok=True)
            app.mount(route, StaticFiles(directory=str(d)), name=name)
            log.info("Static %s monté sur %s", name, d)
        except Exception as e:
            log.warning("Impossible de monter %s : %s", route, e)


@app.on_event("shutdown")
def shutdown():
    try:
        from ..scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


@app.get("/health")
def health():
    return {"status": "ok", "service": "presence_ia", "version": "1.0.0"}


# ── CGV (PDF statique uploadé depuis l'admin) ─────────────────────────────
_CGV_PATH = Path(__file__).parent.parent.parent / "dist" / "cgv.pdf"

@app.get("/cgv")
def cgv():
    from fastapi.responses import FileResponse, HTMLResponse
    if _CGV_PATH.exists():
        return FileResponse(str(_CGV_PATH), media_type="application/pdf")
    return HTMLResponse("<p style='font-family:sans-serif;padding:40px'>CGV non disponibles pour le moment.</p>", status_code=404)

@app.post("/api/admin/cgv")
async def upload_cgv(request: Request):
    from fastapi import Request as _R
    from fastapi.responses import JSONResponse
    import shutil
    admin_token = request.query_params.get("token","")
    if admin_token != os.getenv("ADMIN_TOKEN","changeme"):
        from fastapi import HTTPException
        raise HTTPException(403, "Accès refusé")
    body = await request.body()
    if not body:
        raise HTTPException(400, "Fichier vide")
    _CGV_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CGV_PATH.write_bytes(body)
    log.info("CGV uploadé — %d octets", len(body))
    return JSONResponse({"ok": True, "size": len(body)})


@app.get("/", response_class=HTMLResponse)
def root(db=None):
    from ..database import get_block, SessionLocal, db_get_page_layout
    import json as _json
    _db = SessionLocal()
    try:
        # Layout — sections activables/désactivables
        layout = db_get_page_layout(_db, "home")
        if layout:
            sections_config = _json.loads(layout.sections_config)
        else:
            # Config par défaut si pas encore configuré
            sections_config = [
                {"key": "hero", "label": "Hero", "enabled": True, "order": 0},
                {"key": "proof_stat", "label": "Preuves statistiques", "enabled": True, "order": 1},
                {"key": "problem", "label": "Problème", "enabled": True, "order": 2},
                {"key": "proof_visual", "label": "Comment ça marche", "enabled": True, "order": 3},
                {"key": "evidence", "label": "Preuves / Screenshots", "enabled": True, "order": 4},
                {"key": "pricing", "label": "Tarifs", "enabled": True, "order": 5},
                {"key": "faq", "label": "FAQ", "enabled": True, "order": 6},
            ]

        # Filtrer les sections activées
        sections_enabled = {s["key"]: s.get("enabled", True) for s in sections_config}

        B = lambda sk, fk, **kw: get_block(_db, "home", sk, fk, **kw)
        from offers_module.database import db_list_offers
        pricing = db_list_offers(_db)

        # HERO
        h_title    = B("hero","title").replace("\n","<br>")
        h_sub      = B("hero","subtitle")
        h_cta1     = B("hero","cta_primary")
        h_cta2     = B("hero","cta_secondary")
        # PROOF STAT
        s1v = B("proof_stat","stat_1_value"); s1l = B("proof_stat","stat_1_label").replace("\n","<br>")
        s2v = B("proof_stat","stat_2_value"); s2l = B("proof_stat","stat_2_label").replace("\n","<br>")
        s3v = B("proof_stat","stat_3_value"); s3l = B("proof_stat","stat_3_label").replace("\n","<br>")
        src1u = B("proof_stat","source_url_1"); src1l = B("proof_stat","source_label_1")
        src2u = B("proof_stat","source_url_2"); src2l = B("proof_stat","source_label_2")
        sources_html = ""
        if src1u and src1l:
            sources_html += f'<a href="{src1u}" target="_blank" style="color:#555;font-size:11px;margin-right:16px">↗ {src1l}</a>'
        if src2u and src2l:
            sources_html += f'<a href="{src2u}" target="_blank" style="color:#555;font-size:11px">↗ {src2l}</a>'
        # PROOF VISUAL steps
        pv_title = B("proof_visual","title"); pv_sub = B("proof_visual","subtitle")
        steps = [B("proof_visual",f"step_{i}") for i in range(1,5)]
        steps_html = "".join(f'<div class="step"><div class="step-num">{i+1}</div><p style="color:#aaa;font-size:.9rem">{s}</p></div>' for i,s in enumerate(steps) if s)
        # FAQ
        faqs = [(B("faq",f"q{i}"), B("faq",f"a{i}")) for i in range(1,5)]
        faq_html = "".join(f'<div class="faq-item"><h3 style="color:#fff;font-size:1rem;margin-bottom:8px">{q}</h3><p style="color:#aaa;font-size:.9rem">{a}</p></div>' for q,a in faqs if q)
        # CTA
        cta_title = B("cta","title"); cta_sub = B("cta","subtitle"); cta_btn = B("cta","btn_label")
        # PREUVES — 6 dernières images toutes villes confondues
        from ..database import db_get_evidence, jl as _jl
        from ..models import CityEvidenceDB
        _PROVIDER_LABELS = {"openai": "ChatGPT", "anthropic": "Claude", "gemini": "Gemini"}
        _all_ev = _db.query(CityEvidenceDB).all()
        _all_imgs = []
        for _ev in _all_ev:
            for _img in _jl(_ev.images):
                _img["_profession"] = _ev.profession
                _img["_city"] = _ev.city
                _all_imgs.append(_img)
        _all_imgs.sort(key=lambda x: x.get("ts",""), reverse=True)
        _latest_imgs = _all_imgs[:6]
        evidence_html = ""
        if _latest_imgs:
            _cards = "".join(
                f'<a href="{_i.get("url","")}" target="_blank" style="display:block;border-radius:8px;overflow:hidden;border:1px solid #2a2a4e">'
                f'<img src="{_i.get("processed_url") or _i.get("url","")}" '
                f'style="width:100%;aspect-ratio:16/9;object-fit:cover;display:block" loading="lazy">'
                f'<div style="padding:6px 8px;background:#1a1a2e;font-size:10px;color:#666">'
                f'{_i.get("ts","")[:10]} · {_PROVIDER_LABELS.get(_i.get("provider",""), _i.get("provider",""))} · {_i.get("_city","").title()}'
                f'</div></a>'
                for _i in _latest_imgs
            )
            evidence_html = f"""<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px;margin-top:24px">{_cards}</div>"""
        # PRICING dynamique (OfferDB)
        plans_html = ""
        import json as _json
        for o in pricing:
            features = _json.loads(o.features or "[]") if isinstance(o.features, str) else (o.features or [])
            li = "".join(f"<li>{b}</li>" for b in features)
            price_display = f"{int(o.price)}€" if o.price == int(o.price) else f"{o.price}€"
            plans_html += f'''<div class="plan">
<h3 style="color:#fff;margin-bottom:8px">{o.name}</h3>
<div class="price">{price_display}</div>
<ul style="list-style:none;margin:20px 0 24px">{li}</ul>
<button onclick="startCheckout('{o.id}')" class="btn-plan">Commander</button>
</div>'''
    finally:
        _db.close()

    _css = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#fafafa;color:#1a1a2e;line-height:1.6}
a{color:#e94560;text-decoration:none}
nav{display:flex;justify-content:space-between;align-items:center;padding:20px 40px;border-bottom:1px solid #e5e7eb;position:sticky;top:0;background:rgba(255,255,255,0.95);backdrop-filter:blur(10px);z-index:100;box-shadow:0 1px 3px rgba(0,0,0,0.05)}
.logo{font-size:1.3rem;font-weight:bold;color:#1a1a2e}.logo span{color:#e94560}
.nav-cta{background:#e94560;color:#fff;padding:10px 22px;border-radius:6px;font-weight:bold;font-size:.9rem}
.hero{text-align:center;padding:100px 20px 80px;max-width:800px;margin:0 auto;background:linear-gradient(180deg,#fff 0%,#fef5f7 100%)}
.hero-badge{display:inline-block;background:#fff;border:1px solid #e94560;color:#e94560;padding:6px 16px;border-radius:20px;font-size:.85rem;margin-bottom:24px;box-shadow:0 2px 4px rgba(233,69,96,0.1)}
.hero h1{font-size:clamp(2rem,5vw,3.2rem);color:#1a1a2e;margin-bottom:20px;line-height:1.2}
.hero h1 span{color:#e94560}
.hero p{font-size:1.15rem;color:#6b7280;max-width:580px;margin:0 auto 36px}
.hero-btns{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}
.btn-primary{background:linear-gradient(90deg,#e94560,#ff7043);color:#fff;padding:16px 36px;border-radius:8px;font-weight:bold;font-size:1.05rem;border:none;cursor:pointer;box-shadow:0 4px 12px rgba(233,69,96,0.25)}
.btn-secondary{background:#fff;color:#1a1a2e;padding:16px 36px;border-radius:8px;font-weight:bold;font-size:1.05rem;border:1px solid #d1d5db;box-shadow:0 2px 4px rgba(0,0,0,0.05)}
.btn-primary:hover{opacity:0.9;transform:translateY(-2px)}.btn-secondary:hover{border-color:#e94560;color:#e94560}
.proof{background:linear-gradient(180deg,#fef5f7 0%,#fff 100%);padding:28px 20px;text-align:center;border-top:1px solid #ffe5ec;border-bottom:1px solid #ffe5ec}
.proof p{color:#6b7280;font-size:.9rem;margin-bottom:12px}
.proof-stats{display:flex;gap:48px;justify-content:center;flex-wrap:wrap}
.stat{text-align:center}.stat strong{display:block;font-size:1.8rem;font-weight:bold;color:#e94560}
.stat span{font-size:.85rem;color:#6b7280}
section{padding:80px 20px;max-width:900px;margin:0 auto}
h2{font-size:clamp(1.5rem,3vw,2.2rem);color:#1a1a2e;margin-bottom:16px;max-width:800px}
.sub{color:#6b7280;font-size:1.05rem;margin-bottom:48px;max-width:700px}
.chat-demo{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:28px;margin:0 auto 60px;max-width:600px;box-shadow:0 4px 12px rgba(0,0,0,0.08)}
.chat-q{color:#6b7280;font-size:.9rem;margin-bottom:12px}
.chat-q strong{color:#1a1a2e}
.chat-r{background:#f9fafb;border-left:3px solid #e94560;border-radius:6px;padding:16px;font-size:.9rem;color:#374151}
.chat-r .bad{color:#e94560;font-weight:bold}.chat-r .good{color:#2ecc71;font-weight:bold}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:24px;margin-top:48px}
.step{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:28px;box-shadow:0 2px 8px rgba(0,0,0,0.06);transition:transform 0.2s}
.step:hover{transform:translateY(-4px);box-shadow:0 4px 16px rgba(0,0,0,0.1)}
.step-num{font-size:2rem;font-weight:bold;color:#e94560;margin-bottom:12px}
.step h3{color:#1a1a2e;margin-bottom:8px;font-size:1rem}
.step p{color:#6b7280;font-size:.9rem}
.pricing{background:linear-gradient(180deg,#fff 0%,#f9fafb 100%);padding:80px 20px;border-top:1px solid #e5e7eb}
.pricing-inner{max-width:960px;margin:0 auto;text-align:center}
.plans{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px;margin-top:48px;text-align:left}
.plan{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:32px;position:relative;box-shadow:0 2px 8px rgba(0,0,0,0.06);transition:transform 0.2s}
.plan:hover{transform:translateY(-4px);box-shadow:0 4px 16px rgba(0,0,0,0.1)}
.plan.best{border-color:#e94560;box-shadow:0 4px 16px rgba(233,69,96,0.15)}
.plan.best::before{content:"Recommandé";position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:#e94560;color:#fff;padding:4px 16px;border-radius:20px;font-size:.8rem;font-weight:bold;white-space:nowrap}
.plan h3{color:#1a1a2e;margin-bottom:8px}
.price{font-size:2.4rem;font-weight:bold;color:#e94560;margin:12px 0}
.price span{font-size:1rem;color:#6b7280}
.plan ul{list-style:none;margin:20px 0 24px}
.plan ul li{padding:7px 0;color:#374151;border-bottom:1px solid #e5e7eb;font-size:.9rem}
.plan ul li::before{content:"✓ ";color:#2ecc71}
.btn-plan{display:block;background:linear-gradient(90deg,#e94560,#ff7043);color:#fff;padding:14px;border-radius:6px;font-weight:bold;text-align:center;border:none;cursor:pointer;box-shadow:0 2px 8px rgba(233,69,96,0.25)}
.btn-plan.ghost{background:#fff;border:1px solid #e94560;color:#e94560}
.btn-plan:hover{opacity:0.9;transform:translateY(-2px)}
.faq{max-width:720px;margin:0 auto}
.faq-item{border-bottom:1px solid #e5e7eb;padding:20px 0}
.faq-item h3{color:#1a1a2e;font-size:1rem;margin-bottom:8px}
.faq-item p{color:#6b7280;font-size:.9rem}
.section-problem{background:linear-gradient(135deg,#fff5f7 0%,#fff 100%);padding:80px 20px;margin:60px 0}
.section-howto{background:#fff;padding:80px 20px}
.section-evidence{background:linear-gradient(180deg,#fafafa 0%,#fff 100%);padding:80px 20px;margin:60px 0}
.cta-final{background:linear-gradient(135deg,#e94560,#ff7043);padding:80px 20px;text-align:center}
.cta-final h2{font-size:clamp(1.5rem,3vw,2rem);color:#fff;margin-bottom:16px}
.cta-final p{color:#fff;margin-bottom:32px;opacity:0.9}
footer{background:#f9fafb;padding:32px 20px;text-align:center;color:#6b7280;font-size:.85rem;border-top:1px solid #e5e7eb}
footer a{color:#e94560}
"""
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Présence IA — Votre entreprise visible dans ChatGPT, Gemini et Claude</title>
<meta name="description" content="Testez votre visibilité dans les IA et corrigez-la. Audit personnalisé pour artisans et PME locales.">
<style>{_css}</style>
</head>
<body>

<!-- NAV -->
<nav>
  <div class="logo">Présence<span>IA</span></div>
</nav>

<!-- HERO -->
<div class="hero">
  <div class="hero-badge">Nouveau — Audit IA pour artisans &amp; PME</div>
  <h1>{h_title}</h1>
  <p>{h_sub}</p>
  <div class="hero-btns">
    <a href="#contact" class="btn-primary">{h_cta1}</a>
    <a href="#comment" class="btn-secondary">{h_cta2}</a>
  </div>
</div>

<!-- PROOF -->
<div class="proof">
  <p>Résultats observés sur nos derniers audits</p>
  <div class="proof-stats">
    <div class="stat"><strong>{s1v}</strong><span>{s1l}</span></div>
    <div class="stat"><strong>{s2v}</strong><span>{s2l}</span></div>
    <div class="stat"><strong>{s3v}</strong><span>{s3l}</span></div>
  </div>
  {sources_html}
</div>

{f'''<!-- PROBLÈME -->
<div class="section-problem">
<section>
  <h2>Les recherches changent. Les IA répondent à la place de Google.</h2>
  <p class="sub">Vos clients posent désormais leurs questions à une IA. Si vous n'apparaissez pas dans les réponses, vous n'existez pas pour eux.</p>
  <div class="chat-demo">
    <div class="chat-q"><strong>Question posée à ChatGPT :</strong><br>"Quel couvreur recommandes-tu à Lyon 3e ?"</div>
    <div class="chat-r">
      "Je vous recommande <span class="bad">Martin Toiture</span>, <span class="bad">Couverture Rhône</span> et <span class="bad">Lyon Toit Pro</span>.<br>
      Ces entreprises sont bien notées et interviennent rapidement dans le 3e arrondissement."<br><br>
      <span style="color:#666;font-size:.85rem">→ Votre entreprise n'est pas mentionnée.</span>
    </div>
  </div>
</section>
</div>''' if sections_enabled.get("problem", True) else ""}

{f'''<!-- COMMENT ÇA MARCHE -->
<div class="section-howto">
<section id="comment">
  <h2>{pv_title}</h2>
  <p class="sub">{pv_sub}</p>
  <div class="steps">
    {steps_html}
  </div>
</section>
</div>''' if sections_enabled.get("proof_visual", True) else ""}

<!-- PREUVES -->
{f'''<div class="section-evidence">
<section style="padding:60px 20px;max-width:900px;margin:0 auto">
<h2 style="color:#1a1a2e;font-size:clamp(1.4rem,3vw,2rem);margin-bottom:8px">Captures réelles de nos tests</h2>
<p style="color:#6b7280;font-size:1rem;margin-bottom:0">Ces screenshots ont été pris lors de nos audits — ce que les IA répondent vraiment.</p>
{evidence_html}
</section>
</div>''' if evidence_html and sections_enabled.get("evidence", True) else ""}

{f'''<!-- PRICING -->
<div class="pricing" id="tarifs">
  <div class="pricing-inner">
    <h2>Tarifs transparents</h2>
    <p class="sub">Sans abonnement caché. Sans engagement.</p>
    <div class="plans">
      {plans_html}
    </div>
  </div>
</div>''' if sections_enabled.get("pricing", True) else ""}

{f'''<!-- FAQ -->
<section>
  <h2>Questions fréquentes</h2>
  <div class="faq">
    {faq_html}
  </div>
</section>''' if sections_enabled.get("faq", True) else ""}

<script>
async function startCheckout(offerId) {{
  try {{
    const r = await fetch('/api/checkout/' + offerId, {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        success_url: window.location.origin + '/success',
        cancel_url: window.location.href,
      }})
    }});
    const data = await r.json();
    if (data.checkout_url) window.location.href = data.checkout_url;
  }} catch(e) {{
    alert('Erreur lors du paiement. Veuillez réessayer.');
  }}
}}
</script>

<footer>
  © 2026 Présence IA — <a href="/cgv">Conditions Générales de Vente</a><br>
  <span style="font-size:.8rem">Les résultats IA peuvent varier selon les modèles et les dates de test.</span>
</footer>

</body></html>""")


# ── Routes ──
from .routes import campaign, ia_test, scoring, generate, admin, pipeline, jobs, upload, evidence, stripe_routes, contacts, offers, analytics, content, headers, scan_admin, prospection_admin, login
from offers_module import router as offers_router

app.include_router(campaign.router)
app.include_router(ia_test.router)
app.include_router(scoring.router)
app.include_router(generate.router)
app.include_router(admin.router)
app.include_router(pipeline.router)
app.include_router(jobs.router)
app.include_router(upload.router)
app.include_router(evidence.router)
app.include_router(stripe_routes.router)
app.include_router(contacts.router)
app.include_router(offers.router)
app.include_router(offers_router)
app.include_router(analytics.router)
app.include_router(content.router)
app.include_router(headers.router)
app.include_router(login.router)
app.include_router(scan_admin.router)
app.include_router(prospection_admin.router)
