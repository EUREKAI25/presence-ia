from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from ...database import get_db, db_get_campaign, db_get_prospect, db_get_by_token, db_get_evidence, db_get_header, get_block, jl
from offers_module.database import db_list_offers
from ...models import GenerateInput, AssetsInput
from ...generate import audit_generate, email_generate, video_script, generate_campaign, landing_url, _summary, _comps
from ...assets import set_assets, mark_ready

router = APIRouter(tags=["Generate & Assets"])


@router.post("/api/generate/campaign")
def api_gen_campaign(data: GenerateInput, db: Session = Depends(get_db)):
    if not db_get_campaign(db, data.campaign_id): raise HTTPException(404, "Campagne introuvable")
    return generate_campaign(db, data.campaign_id, data.prospect_ids)


@router.post("/api/generate/prospect/{pid}/audit", response_class=HTMLResponse)
def api_audit(pid: str, db: Session = Depends(get_db)):
    p = db_get_prospect(db, pid)
    if not p: raise HTTPException(404)
    return HTMLResponse(audit_generate(db, p))


@router.post("/api/generate/prospect/{pid}/email")
def api_email(pid: str, db: Session = Depends(get_db)):
    p = db_get_prospect(db, pid)
    if not p: raise HTTPException(404)
    return email_generate(db, p)


@router.post("/api/generate/prospect/{pid}/video-script")
def api_video(pid: str, db: Session = Depends(get_db)):
    p = db_get_prospect(db, pid)
    if not p: raise HTTPException(404)
    return {"script": video_script(p)}


@router.post("/api/prospect/{pid}/assets")
def api_assets(pid: str, assets: AssetsInput, db: Session = Depends(get_db)):
    try: p = set_assets(db, pid, assets)
    except ValueError as e: raise HTTPException(400, str(e))
    return {"prospect_id": p.prospect_id, "status": p.status,
            "video_url": p.video_url, "screenshot_url": p.screenshot_url}


@router.post("/api/prospect/{pid}/mark-ready")
def api_mark_ready(pid: str, db: Session = Depends(get_db)):
    try: p = mark_ready(db, pid)
    except ValueError as e: raise HTTPException(400, str(e))
    return {"prospect_id": p.prospect_id, "status": p.status, "landing_url": landing_url(p)}


# ── Landing page ──────────────────────────────────────────────────────

@router.get("/couvreur", response_class=HTMLResponse)
def landing(t: str, db: Session = Depends(get_db)):
    import os, json as _json
    p = db_get_by_token(db, t)
    if not p: raise HTTPException(404)
    s = _summary(db, p); comps = _comps(p, 3)
    base_url = os.getenv("BASE_URL", "http://localhost:8001")
    n_queries = sum(1 for q in s["ql"] if q)
    models_str = ", ".join(s["models"]) or "—"

    # Header image de la ville (si uploadée)
    city_header = db_get_header(db, p.city.lower())
    hero_bg = (
        f"background-image:linear-gradient(to bottom,rgba(15,10,50,.35) 0%,rgba(10,18,60,.65) 100%),"
        f"url('{city_header.url}');background-size:cover;background-position:center;"
    ) if city_header else "background:linear-gradient(135deg,#1a0a4e 0%,#0e2560 50%,#0d1f5c 100%);"

    # Content blocks
    L = lambda sk, fk: get_block(db, "landing", sk, fk, profession=p.profession, city=p.city)
    pricing = db_list_offers(db, profession=p.profession)

    # ── Plans ──────────────────────────────────────────────────────────
    plans_html = ""
    for i, o in enumerate(pricing):
        features = _json.loads(o.features or "[]") if isinstance(o.features, str) else (o.features or [])
        li = "".join(f"<li>{f}</li>" for f in features)
        price_int = int(round(o.price))
        is_best = i == 1
        badge = '<span class="badge">Le plus choisi</span>' if is_best else ""
        plans_html += f"""<div class="plan{'  plan--best' if is_best else ''}">
{badge}
<div class="plan-name">{o.name}</div>
<div class="plan-price"><sup>€</sup>{price_int}</div>
<div class="plan-divider"></div>
<ul class="plan-feats">{li}</ul>
<button class="plan-btn" onclick="checkout(this,'{o.id}')">Choisir ce plan &rarr;</button>
</div>"""

    # ── Evidence ────────────────────────────────────────────────────────
    _PROV = {"openai": "ChatGPT", "anthropic": "Claude", "gemini": "Gemini"}
    ev = db_get_evidence(db, p.profession.lower(), p.city.lower())
    ev_images = sorted(jl(ev.images), key=lambda x: x.get("ts",""), reverse=True)[:6] if ev else []
    ev_section = ""
    if ev_images:
        from datetime import datetime as _dt
        _day_fr = ['lundi','mardi','mercredi','jeudi','vendredi','samedi','dimanche']
        def _ev_date(ts_str, provider):
            try:
                dt = _dt.fromisoformat(ts_str[:16])
                now = _dt.now()
                diff = (now - dt).days
                if diff == 0:   label = f"aujourd'hui a {dt.strftime('%Hh%M')}"
                elif diff == 1: label = f"hier a {dt.strftime('%Hh%M')}"
                elif diff < 7:  label = f"{_day_fr[dt.weekday()]} dernier a {dt.strftime('%Hh%M')}"
                else:           label = f"le {dt.strftime('%d/%m')} a {dt.strftime('%Hh%M')}"
            except Exception:
                label = ts_str[:10]
            return f"{_PROV.get(provider, provider)} \u2014 {label}"

        cards_json = "[" + ",".join(
            f'{{"bg":"{img.get("processed_url") or img.get("url","")}","orig":"{img.get("url","")}","meta":"{_ev_date(img.get("ts",""), img.get("provider",""))}"}}'
            for img in ev_images
        ) + "]"
        ev_section = f"""<section class="sect-ev">
<div class="c">
  <p class="sect-label">Preuves</p>
  <h2>Nos tests en conditions reelles</h2>
  <p class="sect-sub">Captures horodatees des reponses des IA sur les {p.profession}s a {p.city}.</p>
  <div class="ev-carousel">
    <div class="ev-track" id="ev-track"></div>
    <div class="ev-nav">
      <button class="ev-arrow" id="ev-prev" onclick="evNav(-1)" aria-label="Precedent">&larr;</button>
      <span class="ev-counter" id="ev-counter"></span>
      <button class="ev-arrow" id="ev-next" onclick="evNav(1)" aria-label="Suivant">&rarr;</button>
    </div>
  </div>
</div>
</section>
<script>
(function(){{
  const imgs = {cards_json};
  let cur = 0;
  const track = document.getElementById('ev-track');
  const counter = document.getElementById('ev-counter');
  const prevBtn = document.getElementById('ev-prev');
  const nextBtn = document.getElementById('ev-next');
  function render(){{
    const visible = imgs.slice(cur, cur+2);
    track.innerHTML = visible.map(img => `
      <div class="ev-card">
        <div class="ev-img" style="background-image:url('${{img.bg}}')" >
          <span class="ev-badge">Capture officielle</span>
          <a href="${{img.orig}}" target="_blank" class="ev-link"></a>
          <div class="ev-meta">${{img.meta}}</div>
        </div>
      </div>`).join('');
    counter.textContent = (cur+1) + '\u2013' + Math.min(cur+2, imgs.length) + ' / ' + imgs.length;
    prevBtn.disabled = cur === 0;
    nextBtn.disabled = cur + 2 >= imgs.length;
  }}
  window.evNav = function(dir){{ cur = Math.max(0, Math.min(cur + dir*2, imgs.length - 1)); render(); }};
  render();
}})();
</script>"""

    # ── Résultats requêtes ───────────────────────────────────────────────
    def _rs_label(c):
        if c > 0:
            return f"{c} concurrent{'s' if c > 1 else ''} deja en place"
        return "Personne n'est encore present"

    result_rows = "".join(
        f'<div class="rrow"><span class="rq">{l}</span>'
        f'<span class="rs rs--{"warm" if c>0 else "neutral"}">{_rs_label(c)}</span></div>'
        for l, c in zip(s["ql"], s["qm"]) if l
    )
    n_named = sum(1 for c in s["qm"] if c > 0)
    comp_items = "".join(f'<span class="comp-tag">{c}</span>' for c in comps)

    # ── FAQ ──────────────────────────────────────────────────────────────
    faq_html = "".join(
        f'<details class="faq"><summary>{q}</summary><p>{a}</p></details>'
        for i in range(1, 5)
        for q, a in [(L("faq", f"q{i}"), L("faq", f"a{i}"))]
        if q
    )

    video_html = (
        f'<p class="video-link"><a href="{p.video_url}" target="_blank">Voir la demo video (90s)</a></p>'
        if p.video_url else ""
    )

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{p.name} — Audit Visibilite IA</title>
<style>
:root{{
  --acc:#e8355a;--acc2:#ff7043;--green:#16a34a;
  --txt:#111827;--muted:#6b7280;--light:#f3f4f8;
  --border:#e5e7eb;--card:#ffffff;--shadow:0 4px 24px rgba(0,0,0,.08)
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,'Segoe UI',Helvetica,sans-serif;background:#fff;color:var(--txt);line-height:1.65}}
a{{color:inherit;text-decoration:none}}
.c{{max-width:920px;margin:0 auto;padding:0 28px}}

/* HERO */
.hero{{min-height:72vh;display:flex;align-items:center;justify-content:center;text-align:center;
  {hero_bg}
  padding:80px 24px 64px;position:relative}}
.hero::after{{content:"";position:absolute;bottom:0;left:0;right:0;height:80px;
  background:linear-gradient(transparent,#fff);pointer-events:none}}
.hero-pill{{display:inline-block;background:rgba(255,255,255,.15);backdrop-filter:blur(8px);
  color:#fff;font-size:11px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;
  padding:6px 18px;border-radius:30px;border:1px solid rgba(255,255,255,.25);margin-bottom:28px}}
.hero h1{{font-size:clamp(30px,5.5vw,58px);font-weight:800;color:#fff;max-width:760px;
  margin:0 auto 8px;letter-spacing:-.8px;line-height:1.1}}
.hero-name{{display:block;font-size:.55em;font-weight:600;color:rgba(255,255,255,.7);
  letter-spacing:.5px;margin-bottom:4px;text-transform:uppercase}}
.hero-sub{{color:rgba(255,255,255,.65);font-size:16px;max-width:480px;margin:16px auto 40px}}
.hero-cta{{display:inline-flex;align-items:center;gap:8px;
  background:#fff;color:var(--txt);font-weight:700;font-size:14px;
  padding:14px 30px;border-radius:50px;box-shadow:0 4px 20px rgba(0,0,0,.25);
  cursor:pointer;border:none;transition:transform .2s,box-shadow .2s}}
.hero-cta:hover{{transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,0,0,.3)}}

/* SECTIONS communes */
section{{padding:80px 0}}
.sect-label{{font-size:11px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;
  color:var(--acc);margin-bottom:10px}}
section h2{{font-size:clamp(24px,3.8vw,40px);font-weight:800;color:var(--txt);
  letter-spacing:-.4px;margin-bottom:12px;line-height:1.15}}
.sect-sub{{color:var(--muted);font-size:15px;max-width:560px;margin-bottom:44px}}

/* RÉSULTATS */
.sect-results{{background:#fff}}
.results-intro{{font-size:clamp(20px,2.4vw,22px);line-height:clamp(28px,3.4vw,30px);
  color:#1f2937;font-weight:400;max-width:720px;margin-bottom:32px}}
.results-meta{{display:inline-flex;align-items:center;gap:8px;background:var(--light);
  color:var(--muted);font-size:12px;padding:6px 14px;border-radius:6px;margin-bottom:36px}}
.rrow{{display:flex;justify-content:space-between;align-items:center;
  padding:14px 0;border-bottom:1px solid var(--border);gap:16px}}
.rrow:last-child{{border-bottom:none}}
.rq{{color:#374151;font-size:14px;flex:1}}
.rs{{font-size:11px;font-weight:600;padding:5px 16px;border-radius:20px;
  letter-spacing:.3px;white-space:nowrap}}
.rs--neutral{{background:#f0f4ff;color:#4b5ea8}}
.rs--warm{{background:#fff4ec;color:#b45309}}
.comps-wrap{{margin-top:28px;padding:20px;background:var(--light);border-radius:10px}}
.comps-label{{font-size:12px;color:var(--muted);margin-bottom:10px;font-weight:600}}
.comp-tag{{display:inline-block;background:#fff;border:1px solid var(--border);
  color:var(--txt);font-size:12px;padding:5px 14px;border-radius:20px;margin:3px}}

/* EVIDENCE CAROUSEL */
.sect-ev{{background:var(--light)}}
.ev-carousel{{margin-top:8px}}
.ev-track{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
@media(max-width:600px){{.ev-track{{grid-template-columns:1fr}}}}
.ev-card{{border-radius:12px;overflow:hidden;box-shadow:var(--shadow)}}
.ev-img{{position:relative;aspect-ratio:16/9;background-size:cover;background-position:center top}}
.ev-badge{{position:absolute;top:10px;left:10px;background:rgba(30,40,100,.75);
  backdrop-filter:blur(4px);color:#fff;font-size:9px;font-weight:700;
  padding:3px 10px;border-radius:4px;letter-spacing:1px;text-transform:uppercase}}
.ev-link{{position:absolute;inset:0}}
.ev-meta{{position:absolute;bottom:0;left:0;right:0;padding:10px 14px;
  background:linear-gradient(transparent,rgba(0,0,0,.75));font-size:11px;color:#e0e0e0;pointer-events:none}}
.ev-nav{{display:flex;align-items:center;gap:16px;justify-content:center}}
.ev-arrow{{background:#fff;border:1.5px solid var(--border);color:var(--txt);
  width:40px;height:40px;border-radius:50%;font-size:16px;cursor:pointer;
  transition:all .2s;display:flex;align-items:center;justify-content:center}}
.ev-arrow:hover:not(:disabled){{background:var(--txt);color:#fff;border-color:var(--txt)}}
.ev-arrow:disabled{{opacity:.3;cursor:default}}
.ev-counter{{font-size:13px;color:var(--muted);min-width:60px;text-align:center}}

/* PLANS */
.sect-plans{{background:#fff}}
.plans-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px;margin-top:52px;align-items:start}}
.plan{{background:var(--card);border:1.5px solid var(--border);border-radius:16px;
  padding:32px 26px;position:relative;transition:box-shadow .25s,transform .25s}}
.plan:hover{{box-shadow:0 8px 32px rgba(0,0,0,.1);transform:translateY(-3px)}}
.plan--best{{border-color:var(--acc);box-shadow:0 8px 40px rgba(232,53,90,.15)}}
.plan--best:hover{{box-shadow:0 12px 48px rgba(232,53,90,.22)}}
.badge{{position:absolute;top:-13px;left:50%;transform:translateX(-50%);
  background:linear-gradient(90deg,var(--acc),var(--acc2));color:#fff;
  font-size:10px;font-weight:700;padding:5px 18px;border-radius:20px;
  letter-spacing:.8px;white-space:nowrap;box-shadow:0 4px 12px rgba(232,53,90,.4)}}
.plan-name{{font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:1px;margin-bottom:8px}}
.plan-price{{font-size:52px;font-weight:900;color:var(--txt);letter-spacing:-2px;line-height:1}}
.plan-price sup{{font-size:22px;font-weight:700;vertical-align:top;margin-top:10px;letter-spacing:0}}
.plan-price sub{{font-size:14px;font-weight:400;color:var(--muted);letter-spacing:0}}
.plan-divider{{height:1px;background:var(--border);margin:24px 0}}
.plan-feats{{list-style:none;padding:0;margin-bottom:28px}}
.plan-feats li{{font-size:13px;color:#374151;padding:7px 0 7px 24px;position:relative;
  border-bottom:1px solid var(--border)}}
.plan-feats li:last-child{{border-bottom:none}}
.plan-feats li::before{{content:"";position:absolute;left:0;top:50%;transform:translateY(-50%);
  width:10px;height:10px;border-radius:50%;background:var(--light);border:2px solid var(--green)}}
.plan--best .plan-feats li::before{{border-color:var(--acc)}}
.plan-btn{{width:100%;padding:15px;border-radius:10px;border:none;cursor:pointer;
  font-size:14px;font-weight:700;letter-spacing:.3px;transition:all .2s}}
.plan:not(.plan--best) .plan-btn{{background:var(--light);color:var(--txt)}}
.plan:not(.plan--best) .plan-btn:hover{{background:#e5e7eb}}
.plan--best .plan-btn{{background:linear-gradient(90deg,var(--acc),var(--acc2));color:#fff;
  box-shadow:0 4px 16px rgba(232,53,90,.35)}}
.plan--best .plan-btn:hover{{box-shadow:0 6px 22px rgba(232,53,90,.5);transform:translateY(-1px)}}
.plans-note{{text-align:center;color:var(--muted);font-size:12px;margin-top:24px}}

/* FAQ */
.sect-faq{{background:var(--light)}}
.faq-wrap{{max-width:680px;margin-top:40px}}
.faq{{background:#fff;border-radius:10px;margin-bottom:10px;
  border:1px solid var(--border);overflow:hidden}}
.faq summary{{font-size:15px;font-weight:600;color:var(--txt);cursor:pointer;
  padding:18px 20px;list-style:none;display:flex;justify-content:space-between;align-items:center}}
.faq summary::after{{content:"+";font-size:20px;color:var(--muted);font-weight:300;flex-shrink:0;margin-left:16px}}
.faq[open] summary::after{{content:"−";color:var(--acc)}}
.faq p{{color:var(--muted);font-size:14px;padding:0 20px 18px;line-height:1.7}}

/* INTERLUDE */
.interlude{{margin-top:28px;padding:20px 24px;background:linear-gradient(90deg,#fff5f7,#fff);
  border-left:3px solid var(--acc);border-radius:0 8px 8px 0;
  font-size:15px;color:#374151;font-weight:500;line-height:1.6}}

/* VIDEO + FOOTER */
.video-link{{text-align:center;margin-top:36px}}
.video-link a{{color:var(--muted);font-size:13px}}
footer{{background:#111827;padding:32px 24px;text-align:center;
  color:#6b7280;font-size:11px;letter-spacing:.3px}}
</style>
</head>
<body>

<!-- HERO -->
<div class="hero">
  <div class="c">
    <div class="hero-pill">Audit Visibilite IA &mdash; {p.city}</div>
    <h1><span class="hero-name">{p.name}</span>On a testé vos chances<br>d&rsquo;être recommandé par les IA</h1>
    <p class="hero-sub">{n_queries} requetes testees sur {len(s["models"])} modeles &mdash; {models_str}</p>
    <button class="hero-cta" onclick="document.getElementById('resultats').scrollIntoView({{behavior:'smooth'}})">
      Voir les resultats &darr;
    </button>
  </div>
</div>

<!-- RÉSULTATS -->
<section class="sect-results" id="resultats">
  <div class="c">
    <p class="results-intro">Nous avons simulé les recherches que font vos futurs clients sur ChatGPT, Claude et Gemini pour trouver un {p.profession} à {p.city}.<br>Voici ce que ces IA leur répondent...</p>
    <div class="results-meta">{models_str} &nbsp;&middot;&nbsp; {", ".join(s["dates"])}</div>
    {result_rows}
    {f'<div class="comps-wrap"><p class="comps-label">Nommes a votre place :</p>{comp_items}</div>' if comps else ""}
    {"<p class='interlude'>Sur " + str(n_queries) + " requetes testees, " + str(n_named) + " citent un concurrent directement. Chaque mention perdue, c&rsquo;est un client qui appelle quelqu&rsquo;un d&rsquo;autre.</p>" if n_named > 0 else ""}
    {video_html}
  </div>
</section>

<!-- PREUVES -->
{ev_section}

<!-- PLANS -->
<section class="sect-plans" id="plans">
  <div class="c">
    <p class="sect-label">Offres</p>
    <h2>Agissez avant que vos concurrents le fassent</h2>
    <p class="sect-sub">Les IA apprennent en permanence. Etre cite demain depend de ce que vous faites aujourd&rsquo;hui. Choisissez le plan adapte a votre ambition.</p>
    <div class="plans-grid">
      {plans_html}
    </div>
    <p class="plans-note">Paiement securise Stripe &middot; Satisfait ou rembourse 7 jours</p>
  </div>
</section>

<!-- FAQ -->
{f'<section class="sect-faq"><div class="c"><p class="sect-label">FAQ</p><h2>Questions frequentes</h2><div class="faq-wrap">{faq_html}</div></div></section>' if faq_html else ""}

<footer>
  Resultats bases sur tests repetes horodates. Les reponses IA peuvent varier. &copy; PRESENCE_IA
</footer>

<script>
async function checkout(btn, offerId) {{
  const orig = btn.textContent;
  btn.disabled = true; btn.textContent = 'Redirection…';
  try {{
    const r = await fetch('/api/stripe/checkout-session?token={t}&offer_id=' + encodeURIComponent(offerId), {{method:'POST'}});
    const d = await r.json();
    if (d.checkout_url) {{ window.location.href = d.checkout_url; }}
    else {{ btn.disabled = false; btn.textContent = orig; }}
  }} catch(e) {{ btn.disabled = false; btn.textContent = orig; }}
}}
</script>
</body></html>""")
