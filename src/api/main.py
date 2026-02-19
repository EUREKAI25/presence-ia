"""
PRESENCE_IA — FastAPI app
Démarrer : uvicorn src.api.main:app --reload --port 8001
"""
import logging, os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="PRESENCE_IA — Référencement IA", version="1.0.0", docs_url="/docs")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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

    # Montage fichiers statiques (créé si absent, silencieux si permission refusée)
    dist_root = Path(__file__).parent.parent.parent / "dist"
    for sub, route, name in [
        ("uploads", "/dist/uploads", "uploads"),
        ("evidence", "/dist/evidence", "evidence"),
    ]:
        d = dist_root / sub
        try:
            d.mkdir(parents=True, exist_ok=True)
            app.mount(route, StaticFiles(directory=str(d)), name=name)
            log.info("Static %s monté sur %s", name, d)
        except Exception as e:
            log.warning("Impossible de monter %s : %s", route, e)


@app.get("/health")
def health():
    return {"status": "ok", "service": "presence_ia", "version": "1.0.0"}


@app.get("/", response_class=HTMLResponse)
def root(db=None):
    from ..database import get_block, SessionLocal
    _db = SessionLocal()
    try:
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
body{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0;line-height:1.6}
a{color:#e94560;text-decoration:none}
nav{display:flex;justify-content:space-between;align-items:center;padding:20px 40px;border-bottom:1px solid #1a1a2e;position:sticky;top:0;background:#0f0f1a;z-index:100}
.logo{font-size:1.3rem;font-weight:bold;color:#fff}.logo span{color:#e94560}
.nav-cta{background:#e94560;color:#fff;padding:10px 22px;border-radius:6px;font-weight:bold;font-size:.9rem}
.hero{text-align:center;padding:100px 20px 80px;max-width:800px;margin:0 auto}
.hero-badge{display:inline-block;background:#1a1a2e;border:1px solid #e94560;color:#e94560;padding:6px 16px;border-radius:20px;font-size:.85rem;margin-bottom:24px}
.hero h1{font-size:clamp(2rem,5vw,3.2rem);color:#fff;margin-bottom:20px;line-height:1.2}
.hero h1 span{color:#e94560}
.hero p{font-size:1.15rem;color:#aaa;max-width:580px;margin:0 auto 36px}
.hero-btns{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}
.btn-primary{background:#e94560;color:#fff;padding:16px 36px;border-radius:8px;font-weight:bold;font-size:1.05rem}
.btn-secondary{background:transparent;color:#e8e8f0;padding:16px 36px;border-radius:8px;font-weight:bold;font-size:1.05rem;border:1px solid #2a2a4e}
.btn-primary:hover{background:#c73652}.btn-secondary:hover{border-color:#e94560;color:#e94560}
.proof{background:#080810;padding:28px 20px;text-align:center;border-top:1px solid #1a1a2e;border-bottom:1px solid #1a1a2e}
.proof p{color:#666;font-size:.9rem;margin-bottom:12px}
.proof-stats{display:flex;gap:48px;justify-content:center;flex-wrap:wrap}
.stat{text-align:center}.stat strong{display:block;font-size:1.8rem;font-weight:bold;color:#fff}
.stat span{font-size:.85rem;color:#666}
section{padding:80px 20px;max-width:960px;margin:0 auto}
h2{font-size:clamp(1.5rem,3vw,2.2rem);color:#fff;margin-bottom:16px}
.sub{color:#aaa;font-size:1.05rem;margin-bottom:48px}
.chat-demo{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:28px;margin:0 auto 60px;max-width:600px}
.chat-q{color:#aaa;font-size:.9rem;margin-bottom:12px}
.chat-q strong{color:#e8e8f0}
.chat-r{background:#0f0f1a;border-radius:8px;padding:16px;font-size:.9rem;color:#ccc}
.chat-r .bad{color:#e94560;font-weight:bold}.chat-r .good{color:#2ecc71;font-weight:bold}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:24px;margin-top:48px}
.step{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:28px}
.step-num{font-size:2rem;font-weight:bold;color:#e94560;margin-bottom:12px}
.step h3{color:#fff;margin-bottom:8px;font-size:1rem}
.step p{color:#aaa;font-size:.9rem}
.pricing{background:#080810;padding:80px 20px;border-top:1px solid #1a1a2e}
.pricing-inner{max-width:960px;margin:0 auto;text-align:center}
.plans{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px;margin-top:48px;text-align:left}
.plan{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:32px;position:relative}
.plan.best{border-color:#e94560}
.plan.best::before{content:"Recommandé";position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:#e94560;color:#fff;padding:4px 16px;border-radius:20px;font-size:.8rem;font-weight:bold;white-space:nowrap}
.plan h3{color:#fff;margin-bottom:8px}
.price{font-size:2.4rem;font-weight:bold;color:#e94560;margin:12px 0}
.price span{font-size:1rem;color:#aaa}
.plan ul{list-style:none;margin:20px 0 24px}
.plan ul li{padding:7px 0;color:#ccc;border-bottom:1px solid #2a2a4e;font-size:.9rem}
.plan ul li::before{content:"✓ ";color:#2ecc71}
.btn-plan{display:block;background:#e94560;color:#fff;padding:14px;border-radius:6px;font-weight:bold;text-align:center}
.btn-plan.ghost{background:transparent;border:1px solid #e94560;color:#e94560}
.faq{max-width:720px;margin:0 auto}
.faq-item{border-bottom:1px solid #1a1a2e;padding:20px 0}
.faq-item h3{color:#fff;font-size:1rem;margin-bottom:8px}
.faq-item p{color:#aaa;font-size:.9rem}
.cta-final{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:80px 20px;text-align:center;border-top:1px solid #2a2a4e}
.cta-final h2{font-size:clamp(1.5rem,3vw,2rem);color:#fff;margin-bottom:16px}
.cta-final p{color:#aaa;margin-bottom:32px}
footer{background:#080810;padding:32px 20px;text-align:center;color:#444;font-size:.85rem;border-top:1px solid #1a1a2e}
footer a{color:#666}
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

<!-- PROBLÈME -->
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

<!-- COMMENT ÇA MARCHE -->
<section id="comment" style="padding-top:0">
  <h2>{pv_title}</h2>
  <p class="sub">{pv_sub}</p>
  <div class="steps">
    {steps_html}
  </div>
</section>

<!-- PRICING -->
<div class="pricing" id="tarifs">
  <div class="pricing-inner">
    <h2>Tarifs transparents</h2>
    <p class="sub">Sans abonnement caché. Sans engagement.</p>
    <div class="plans">
      {plans_html}
    </div>
  </div>
</div>

<!-- FAQ -->
<section>
  <h2>Questions fréquentes</h2>
  <div class="faq">
    {faq_html}
  </div>
</section>

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
from .routes import campaign, ia_test, scoring, generate, admin, pipeline, jobs, upload, evidence, stripe_routes, contacts, offers, analytics, content
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
