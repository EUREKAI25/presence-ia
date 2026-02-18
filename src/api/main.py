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
    return HTMLResponse("""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Présence IA — Votre entreprise visible dans ChatGPT, Gemini et Claude</title>
<meta name="description" content="Testez votre visibilité dans les IA et corrigez-la. Audit personnalisé pour artisans et PME locales.">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0;line-height:1.6}
a{color:#e94560;text-decoration:none}
/* NAV */
nav{display:flex;justify-content:space-between;align-items:center;padding:20px 40px;border-bottom:1px solid #1a1a2e;position:sticky;top:0;background:#0f0f1a;z-index:100}
.logo{font-size:1.3rem;font-weight:bold;color:#fff}.logo span{color:#e94560}
.nav-cta{background:#e94560;color:#fff;padding:10px 22px;border-radius:6px;font-weight:bold;font-size:.9rem}
/* HERO */
.hero{text-align:center;padding:100px 20px 80px;max-width:800px;margin:0 auto}
.hero-badge{display:inline-block;background:#1a1a2e;border:1px solid #e94560;color:#e94560;padding:6px 16px;border-radius:20px;font-size:.85rem;margin-bottom:24px}
.hero h1{font-size:clamp(2rem,5vw,3.2rem);color:#fff;margin-bottom:20px;line-height:1.2}
.hero h1 span{color:#e94560}
.hero p{font-size:1.15rem;color:#aaa;max-width:580px;margin:0 auto 36px}
.hero-btns{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}
.btn-primary{background:#e94560;color:#fff;padding:16px 36px;border-radius:8px;font-weight:bold;font-size:1.05rem}
.btn-secondary{background:transparent;color:#e8e8f0;padding:16px 36px;border-radius:8px;font-weight:bold;font-size:1.05rem;border:1px solid #2a2a4e}
.btn-primary:hover{background:#c73652}.btn-secondary:hover{border-color:#e94560;color:#e94560}
/* PROOF */
.proof{background:#080810;padding:28px 20px;text-align:center;border-top:1px solid #1a1a2e;border-bottom:1px solid #1a1a2e}
.proof p{color:#666;font-size:.9rem;margin-bottom:12px}
.proof-stats{display:flex;gap:48px;justify-content:center;flex-wrap:wrap}
.stat{text-align:center}.stat strong{display:block;font-size:1.8rem;font-weight:bold;color:#fff}
.stat span{font-size:.85rem;color:#666}
/* PROBLEM */
section{padding:80px 20px;max-width:960px;margin:0 auto}
h2{font-size:clamp(1.5rem,3vw,2.2rem);color:#fff;margin-bottom:16px}
.sub{color:#aaa;font-size:1.05rem;margin-bottom:48px}
/* CHAT DEMO */
.chat-demo{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:28px;margin:0 auto 60px;max-width:600px}
.chat-q{color:#aaa;font-size:.9rem;margin-bottom:12px}
.chat-q strong{color:#e8e8f0}
.chat-r{background:#0f0f1a;border-radius:8px;padding:16px;font-size:.9rem;color:#ccc}
.chat-r .bad{color:#e94560;font-weight:bold}.chat-r .good{color:#2ecc71;font-weight:bold}
/* STEPS */
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:24px;margin-top:48px}
.step{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:28px}
.step-num{font-size:2rem;font-weight:bold;color:#e94560;margin-bottom:12px}
.step h3{color:#fff;margin-bottom:8px;font-size:1rem}
.step p{color:#aaa;font-size:.9rem}
/* PRICING */
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
/* FAQ */
.faq{max-width:720px;margin:0 auto}
.faq-item{border-bottom:1px solid #1a1a2e;padding:20px 0}
.faq-item h3{color:#fff;font-size:1rem;margin-bottom:8px}
.faq-item p{color:#aaa;font-size:.9rem}
/* CTA FINAL */
.cta-final{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:80px 20px;text-align:center;border-top:1px solid #2a2a4e}
.cta-final h2{font-size:clamp(1.5rem,3vw,2rem);color:#fff;margin-bottom:16px}
.cta-final p{color:#aaa;margin-bottom:32px}
/* FOOTER */
footer{background:#080810;padding:32px 20px;text-align:center;color:#444;font-size:.85rem;border-top:1px solid #1a1a2e}
footer a{color:#666}
</style>
</head>
<body>

<!-- NAV -->
<nav>
  <div class="logo">Présence<span>IA</span></div>
  <a href="#contact" class="nav-cta">Demander mon audit</a>
</nav>

<!-- HERO -->
<div class="hero">
  <div class="hero-badge">Nouveau — Audit IA pour artisans &amp; PME</div>
  <h1>Quand vos clients demandent à ChatGPT,<br><span>il cite vos concurrents.</span> Pas vous.</h1>
  <p>Nous testons votre visibilité sur 3 IA et 5 requêtes. Rapport en 48h. Plan d'action concret.</p>
  <div class="hero-btns">
    <a href="#contact" class="btn-primary">Tester ma visibilité — 97€</a>
    <a href="#comment" class="btn-secondary">Comment ça marche</a>
  </div>
</div>

<!-- PROOF -->
<div class="proof">
  <p>Résultats observés sur nos derniers audits</p>
  <div class="proof-stats">
    <div class="stat"><strong>87%</strong><span>des artisans testés<br>sont invisibles sur les IA</span></div>
    <div class="stat"><strong>3 IA</strong><span>testées simultanément<br>ChatGPT · Gemini · Claude</span></div>
    <div class="stat"><strong>48h</strong><span>délai de livraison<br>rapport + plan d'action</span></div>
  </div>
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
  <h2>Comment fonctionne l'audit</h2>
  <p class="sub">Un test automatisé, rigoureux, répété sur les 3 grandes IA du marché.</p>
  <div class="steps">
    <div class="step"><div class="step-num">1</div><h3>On simule vos clients</h3><p>5 requêtes différentes posées à ChatGPT, Gemini et Claude. Comme si c'était un vrai client.</p></div>
    <div class="step"><div class="step-num">2</div><h3>On analyse les réponses</h3><p>Êtes-vous cité ? Qui est cité à votre place ? Combien de fois ? Sur quelle IA ?</p></div>
    <div class="step"><div class="step-num">3</div><h3>Score de visibilité /10</h3><p>Un score clair, des données concrètes, les concurrents identifiés.</p></div>
    <div class="step"><div class="step-num">4</div><h3>Plan d'action</h3><p>Checklist priorisée pour corriger votre visibilité. Applicable sans agence.</p></div>
  </div>
</section>

<!-- PRICING -->
<div class="pricing" id="tarifs">
  <div class="pricing-inner">
    <h2>Tarifs transparents</h2>
    <p class="sub">Sans abonnement caché. Sans engagement.</p>
    <div class="plans">
      <div class="plan">
        <h3>Audit Flash</h3>
        <div class="price">97€ <span>une fois</span></div>
        <ul>
          <li>Test sur 3 IA × 5 requêtes</li>
          <li>Score visibilité /10</li>
          <li>Concurrents identifiés</li>
          <li>Rapport PDF + vidéo 90s</li>
          <li>Checklist 8 points</li>
        </ul>
        <a href="#contact" class="btn-plan ghost">Commander</a>
      </div>
      <div class="plan best">
        <h3>Kit Visibilité IA</h3>
        <div class="price">500€ <span>+ 90€/mois × 6</span></div>
        <ul>
          <li>Audit complet inclus</li>
          <li>Kit contenu optimisé IA</li>
          <li>Suivi mensuel 6 mois</li>
          <li>Re-tests trimestriels</li>
          <li>Dashboard résultats</li>
          <li>Support prioritaire</li>
        </ul>
        <a href="#contact" class="btn-plan">Démarrer</a>
      </div>
      <div class="plan">
        <h3>Tout inclus</h3>
        <div class="price">3 500€ <span>forfait</span></div>
        <ul>
          <li>Audit + Kit inclus</li>
          <li>Rédaction contenus</li>
          <li>Citations locales</li>
          <li>Optimisation fiches</li>
          <li>Garantie résultats 6 mois</li>
        </ul>
        <a href="#contact" class="btn-plan ghost">Me contacter</a>
      </div>
    </div>
  </div>
</div>

<!-- FAQ -->
<section>
  <h2>Questions fréquentes</h2>
  <div class="faq">
    <div class="faq-item">
      <h3>Pourquoi les IA ne me citent-elles pas ?</h3>
      <p>Les IA s'appuient sur des données publiques : avis Google, contenu de votre site, mentions dans des articles. Si ces signaux sont absents ou faibles, vous êtes invisible.</p>
    </div>
    <div class="faq-item">
      <h3>Ça fonctionne pour quel type d'entreprise ?</h3>
      <p>Artisans (couvreurs, plombiers, électriciens…), restaurants, cabinets médicaux, commerces locaux. Toute entreprise dont les clients cherchent localement.</p>
    </div>
    <div class="faq-item">
      <h3>Combien de temps pour voir des résultats ?</h3>
      <p>L'audit est livré en 48h. Les améliorations de visibilité IA sont généralement visibles en 4 à 12 semaines selon les actions mises en place.</p>
    </div>
    <div class="faq-item">
      <h3>Est-ce que vous envoyez les emails à ma place ?</h3>
      <p>Non. Nous produisons les contenus et le plan d'action. Vous gardez le contrôle total sur ce qui est envoyé et publié.</p>
    </div>
  </div>
</section>

<!-- CTA FINAL -->
<div class="cta-final" id="contact">
  <h2>Votre audit en 48h — 97€</h2>
  <p>Entrez votre email, on vous envoie le lien de commande et on démarre le test.</p>
  <form style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap;max-width:480px;margin:0 auto"
        onsubmit="event.preventDefault();this.innerHTML='<p style=color:#2ecc71;font-size:1.1rem>✓ Reçu ! Vous recevrez un email sous 24h.</p>'">
    <input type="email" placeholder="votre@email.fr" required
           style="flex:1;min-width:220px;padding:14px 18px;background:#1a1a2e;border:1px solid #2a2a4e;color:#fff;border-radius:8px;font-size:1rem">
    <button type="submit"
            style="background:#e94560;color:#fff;border:none;padding:14px 28px;border-radius:8px;font-weight:bold;font-size:1rem;cursor:pointer">
      Démarrer →
    </button>
  </form>
  <p style="margin-top:16px;color:#444;font-size:.85rem">Pas d'appel requis. Pas d'engagement.</p>
</div>

<footer>
  © 2026 Présence IA — <a href="/docs">API</a> · <a href="/health">Status</a><br>
  <span style="font-size:.8rem">Les résultats IA peuvent varier selon les modèles et les dates de test.</span>
</footer>

</body></html>""")


# ── Routes ──
from .routes import campaign, ia_test, scoring, generate, admin, pipeline, jobs

app.include_router(campaign.router)
app.include_router(ia_test.router)
app.include_router(scoring.router)
app.include_router(generate.router)
app.include_router(admin.router)
app.include_router(pipeline.router)
app.include_router(jobs.router)
