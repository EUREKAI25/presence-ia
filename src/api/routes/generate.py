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

@router.get("/{profession}", response_class=HTMLResponse)
def landing(profession: str, t: str = "", db: Session = Depends(get_db)):
    import os, json as _json
    p = db_get_by_token(db, t)
    if not p: raise HTTPException(404)
    s = _summary(db, p); comps = _comps(p, 3)
    base_url = os.getenv("BASE_URL", "http://localhost:8001")

    # Concurrents par modèle (pour la section démo IA)
    from ...models import TestRunDB as _TRunDB
    _runs = db.query(_TRunDB).filter_by(prospect_id=p.prospect_id).all()
    _cby = {}
    for _r in _runs:
        for _e in jl(_r.competitors_entities):
            if isinstance(_e, str):
                _cby.setdefault(_r.model, [])
                if _e not in _cby[_r.model]:
                    _cby[_r.model].append(_e)
    # Formatage date/heure du test pour la démo
    from datetime import datetime as _dtcls
    _demo_dt_str = s["dates"][0] if s.get("dates") else "récemment"
    if _runs:
        try:
            _ts = str(_runs[0].ts)[:16]
            _dto = _dtcls.fromisoformat(_ts)
            _demo_dt_str = _dto.strftime("%d/%m/%Y à %Hh%M")
        except Exception:
            pass
    _demo_models = [
        ("openai",    "ChatGPT",  "(OpenAI)",    "#10a37f"),
        ("anthropic", "Claude",   "(Anthropic)", "#d97706"),
        ("gemini",    "Gemini",   "(Google)",    "#4285f4"),
    ]

    # Header image de la ville (si uploadée)
    city_header = db_get_header(db, p.city.lower())
    hero_bg = (
        f"background-image:linear-gradient(to bottom,rgba(0,0,15,.78) 0%,rgba(0,0,15,.85) 100%),"
        f"url('{city_header.url}');background-size:cover;background-position:center;"
    ) if city_header else "background:linear-gradient(135deg,#0d0820 0%,#0a1840 50%,#071030 100%);"

    # Content blocks
    L = lambda sk, fk: get_block(db, "landing", sk, fk, profession=p.profession, city=p.city)
    pricing = db_list_offers(db, profession=p.profession)

    # ── Plans ──────────────────────────────────────────────────────────
    plans_html = ""
    for i, o in enumerate(pricing):
        features = _json.loads(o.features or "[]") if isinstance(o.features, str) else (o.features or [])
        # Détecter si la première feature est une mention de mensualités (ex: "puis 5 × 100€/mois")
        monthly_note = ""
        display_feats = features
        if features and features[0].lower().startswith("puis"):
            monthly_note = f'<div class="plan-monthly">{features[0]}</div>'
            display_feats = features[1:]
        li = "".join(f"<li>{f}</li>" for f in display_feats)
        price_int = int(round(o.price))
        is_best = i == 1
        badge = '<span class="badge">Le plus choisi</span>' if is_best else ""
        plans_html += f"""<div class="plan{'  plan--best' if is_best else ''}">
{badge}
<div class="plan-name">{o.name}</div>
<div class="plan-price"><sup>€</sup>{price_int}</div>
{monthly_note}
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
        if c == 0:
            return "Je ne sais pas."
        names = comps[:2]
        label = ", ".join(names)
        if len(comps) > 2:
            label += "..."
        return label

    result_rows = "".join(
        f'<div class="rrow"><span class="rq">{l}</span>'
        f'<span class="rs rs--{"warm" if c>0 else "neutral"}">{_rs_label(c)}</span></div>'
        for l, c in zip(s["ql"], s["qm"]) if l
    )
    n_named = sum(1 for c in s["qm"] if c > 0)
    comp_items = "".join(f'<span class="comp-tag">{c}</span>' for c in comps)

    # ── 3 requêtes de démo ───────────────────────────────────────────────
    _demo_queries = [q for q in s.get("ql", []) if q][:3]

    # ── FAQ (accordéon JS, un à la fois) ────────────────────────────────
    faq_html = "".join(
        f'<div class="faq-item">'
        f'<button class="faq-q" onclick="toggleFaq(this)">{q}<span class="faq-icon">+</span></button>'
        f'<div class="faq-a" hidden>{a}</div>'
        f'</div>'
        for i in range(1, 8)
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
.hero h1{{font-size:clamp(28px,5vw,54px);font-weight:800;color:#fff;max-width:760px;
  margin:0 auto 36px;letter-spacing:-.8px;line-height:1.2;
  text-shadow:0 2px 12px rgba(0,0,0,.5)}}
.hero h1 em{{font-style:normal;font-size:1.2em;display:block;margin-top:4px}}
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
.plan-monthly{{font-size:13px;color:var(--muted);margin-top:-8px;margin-bottom:4px}}

/* STICKY HEADER */
.sticky-nav{{position:sticky;top:0;z-index:100;background:rgba(15,23,42,.96);
  backdrop-filter:blur(10px);border-bottom:1px solid rgba(255,255,255,.08);
  display:flex;align-items:center;justify-content:space-between;
  padding:0 28px;height:58px}}
.sn-logo{{color:#fff;font-weight:800;font-size:1rem;letter-spacing:-.02em;text-decoration:none}}
.sn-logo span{{color:#60a5fa}}
.sn-cta{{background:#2563eb;color:#fff;font-weight:700;font-size:13px;
  padding:9px 20px;border-radius:8px;text-decoration:none;transition:background .15s;white-space:nowrap}}
.sn-cta:hover{{background:#1d4ed8}}

/* FAQ */
.sect-faq{{background:var(--light)}}
.faq-wrap{{max-width:680px;margin-top:40px}}
.faq-item{{background:#fff;border-radius:10px;margin-bottom:8px;border:1px solid var(--border);overflow:hidden}}
.faq-q{{width:100%;text-align:left;padding:18px 20px;font-size:15px;font-weight:600;
  color:var(--txt);background:#fff;border:none;cursor:pointer;
  display:flex;justify-content:space-between;align-items:center;gap:16px;transition:background .1s}}
.faq-q:hover{{background:#f8fafc}}
.faq-q.open{{color:var(--acc)}}
.faq-icon{{flex-shrink:0;font-size:20px;font-weight:300;color:var(--muted);line-height:1}}
.faq-q.open .faq-icon{{color:var(--acc)}}
.faq-a{{padding:0 20px 18px;color:var(--muted);font-size:14px;line-height:1.75}}

/* INTERLUDE */
.interlude{{margin-top:28px;padding:20px 24px;background:linear-gradient(90deg,#fff5f7,#fff);
  border-left:3px solid var(--acc);border-radius:0 8px 8px 0;
  font-size:15px;color:#374151;font-weight:500;line-height:1.6}}

/* STATS BAR */
.stats-bar{{background:#fff;border-bottom:1px solid var(--border);padding:36px 24px}}
.stats-bar__inner{{max-width:820px;margin:0 auto;display:flex;justify-content:center;flex-wrap:wrap;gap:0}}
.stats-bar .stat{{text-align:center;padding:0 44px;border-right:1px solid var(--border)}}
.stats-bar .stat:last-child{{border-right:none}}
.stats-bar .stat__val{{font-size:1.25rem;font-weight:800;color:var(--txt);letter-spacing:-.02em;line-height:1.2}}
.stats-bar .stat__lbl{{font-size:.78rem;color:var(--muted);margin-top:4px;line-height:1.4}}
@media(max-width:600px){{.stats-bar .stat{{border-right:none;border-bottom:1px solid var(--border);padding:16px 0}}.stats-bar .stat:last-child{{border-bottom:none}}}}

/* IA DEMO */
.sect-ia-demo{{background:#f8fafc;border-top:1px solid var(--border);border-bottom:1px solid var(--border)}}
.ia-query-bar{{background:#1e293b;color:#e2e8f0;border-radius:10px;padding:14px 20px;
  font-size:13px;margin-bottom:20px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
.ia-query-ts{{color:#94a3b8;font-size:12px;white-space:nowrap;font-weight:600}}
.ia-query-text{{font-style:italic;color:#f1f5f9;font-size:16px;font-weight:500}}
.ia-columns{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:28px}}
@media(max-width:680px){{.ia-columns{{grid-template-columns:1fr}}}}
.ia-col{{background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px 18px}}
.ia-col__brand{{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)}}
.ia-col__list{{list-style:none;padding:0}}
.ia-col__list li{{font-size:13px;color:#374151;padding:6px 0;border-bottom:1px solid #f1f5f9;
  display:flex;align-items:center;gap:8px}}
.ia-col__list li:last-child{{border-bottom:none}}
.ia-col__list li::before{{content:"";display:inline-block;width:6px;height:6px;
  border-radius:50%;background:var(--acc);flex-shrink:0}}
.ia-col__empty{{font-size:12px;color:var(--muted);font-style:italic}}
.ia-demo-cta{{text-align:center;padding-top:8px;border-top:1px solid var(--border);margin-top:8px}}
.ia-demo-cta__title{{font-size:1.6rem;font-weight:800;color:var(--txt);margin-bottom:10px}}
.ia-demo-cta__sub{{font-size:1rem;color:#374151;margin-bottom:28px;max-width:560px;margin-left:auto;margin-right:auto;line-height:1.7}}

/* PITCH SECTION */
.sect-pitch{{background:#fff}}
.pitch-card{{background:#f8fafc;border:1px solid var(--border);border-radius:12px;
  padding:32px 36px;max-width:680px;margin:0 auto}}
.pitch-card p{{font-size:1.05rem;color:#1f2937;font-weight:500;line-height:1.7;margin-bottom:24px}}
.pitch-list{{list-style:none;padding:0;margin-bottom:28px}}
.pitch-list li{{display:flex;align-items:flex-start;gap:10px;font-size:14px;color:#374151;
  padding:8px 0;border-bottom:1px solid #e2e8f0}}
.pitch-list li:last-child{{border-bottom:none}}
.pitch-list li::before{{content:"→";color:var(--acc);font-weight:700;flex-shrink:0;margin-top:1px}}
.pitch-cta-wrap{{text-align:center}}
.btn-pitch{{display:inline-flex;align-items:center;gap:8px;
  background:linear-gradient(90deg,var(--acc),var(--acc2));color:#fff;
  font-weight:700;font-size:15px;padding:16px 40px;border-radius:50px;
  text-decoration:none;box-shadow:0 4px 20px rgba(232,53,90,.35);transition:all .2s;cursor:pointer;border:none}}
.btn-pitch:hover{{transform:translateY(-2px);box-shadow:0 8px 28px rgba(232,53,90,.45)}}

/* VIDEO + FOOTER */
.video-link{{text-align:center;margin-top:36px}}
.video-link a{{color:var(--muted);font-size:13px}}
footer{{background:#111827;padding:32px 24px;text-align:center;
  color:#6b7280;font-size:11px;letter-spacing:.3px}}
</style>
</head>
<body>

<!-- STICKY NAV -->
<nav class="sticky-nav">
  <a class="sn-logo" href="/">Présence<span>IA</span></a>
  <a class="sn-cta" href="https://calendly.com/contact-presence-ia/30min" target="_blank">Réserver mon audit gratuit</a>
</nav>

<!-- HERO -->
<div class="hero">
  <div class="c">
    <div class="hero-pill">Audit Visibilité IA &mdash; {p.name.upper()}</div>
    <h1>À {p.city}, vos concurrents sont recommandés par les IA.<em>Et vous&nbsp;?</em></h1>
    <button class="hero-cta" onclick="document.getElementById('ia-demo').scrollIntoView({{behavior:'smooth'}})">
      Voir les résultats &darr;
    </button>
  </div>
</div>

<!-- STATS BAR -->
<div class="stats-bar">
  <div class="stats-bar__inner">
    <div class="stat"><div class="stat__val">Des clients perdus</div><div class="stat__lbl">sans même le savoir</div></div>
    <div class="stat"><div class="stat__val">Des concurrents</div><div class="stat__lbl">qui prennent votre place</div></div>
    <div class="stat"><div class="stat__val">Un plan d'action</div><div class="stat__lbl">pour renverser la situation</div></div>
  </div>
</div>

<!-- IA DEMO -->
<section class="sect-ia-demo" id="ia-demo">
  <div class="c">
    <h2 style="font-size:clamp(28px,4vw,44px);margin-bottom:6px">En ce moment</h2>
    <p class="sect-sub" style="margin-bottom:32px">Voici ce que voient vos prospects quand ils consultent leur IA pour trouver un {p.profession} à {p.city}</p>
    {"".join(
      f'<div class="ia-query-bar" style="opacity:{1 - i*0.18:.2f}">'
      f'<span class="ia-query-ts">{_demo_dt_str}</span>'
      f'<span class="ia-query-text">« {q} »</span>'
      f'</div>'
      for i, q in enumerate(_demo_queries or [f"Quel {p.profession} recommandes-tu à {p.city} ?"])
    )}
    <div class="ia-columns">
      {"".join(
        f'<div class="ia-col">'
        f'<div class="ia-col__brand" style="color:{color}">{name}'
        f' <span style="font-size:.78em;font-weight:400;color:#94a3b8">{company}</span></div>'
        f'<ul class="ia-col__list">'
        + ("".join(f'<li>{c}</li>' for c in _cby.get(key, [])[:3]) or '<li class="ia-col__empty">Aucun concurrent cité</li>')
        + f'</ul></div>'
        for key, name, company, color in _demo_models
      )}
    </div>
    <div class="ia-demo-cta">
      <p class="ia-demo-cta__title">Vous n&rsquo;y êtes pas&nbsp;?</p>
      <p class="ia-demo-cta__sub">Réservez votre rendez-vous pour comprendre pourquoi vos concurrents y sont — et comment prendre votre place.<br><strong>On vous envoie gratuitement votre audit.</strong></p>
      <a class="btn-pitch" href="https://calendly.com/contact-presence-ia/30min" target="_blank">Réserver mon rendez-vous gratuit &rarr;</a>
    </div>
  </div>
</section>


<!-- FAQ -->
{f'<section class="sect-faq"><div class="c"><div class="faq-wrap">{faq_html}</div></div></section>' if faq_html else ""}

<footer>
  &copy; 2026 PRESENCE_IA &nbsp;&middot;&nbsp;
  <a href="/cgv" target="_blank" style="color:#9ca3af;text-decoration:underline">Conditions Générales de Vente</a>
</footer>

<script>
function toggleFaq(btn) {{
  const isOpen = btn.classList.contains('open');
  document.querySelectorAll('.faq-q').forEach(b => {{
    b.classList.remove('open');
    b.nextElementSibling.hidden = true;
    b.querySelector('.faq-icon').textContent = '+';
  }});
  if (!isOpen) {{
    btn.classList.add('open');
    btn.nextElementSibling.hidden = false;
    btn.querySelector('.faq-icon').textContent = '−';
  }}
}}
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
