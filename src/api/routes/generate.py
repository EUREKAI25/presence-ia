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

    # Données IA par requête (accordéon)
    from ...models import TestRunDB as _TRunDB
    from datetime import datetime as _dtcls
    _runs = db.query(_TRunDB).filter_by(prospect_id=p.prospect_id).all()
    _latest_by_model = {}
    for _r in sorted(_runs, key=lambda r: str(r.ts)):
        _latest_by_model[_r.model] = _r
    _ref_run = next(iter(_latest_by_model.values()), None)
    _demo_dt_str = s["dates"][0] if s.get("dates") else "récemment"
    if _ref_run:
        try:
            _dto = _dtcls.fromisoformat(str(_ref_run.ts)[:16])
            _demo_dt_str = _dto.strftime("%d/%m/%Y à %Hh%M")
        except Exception:
            pass
    _demo_models = [
        ("openai",    "ChatGPT",  "(OpenAI)",    "#10a37f"),
        ("anthropic", "Claude",   "(Anthropic)", "#d97706"),
        ("gemini",    "Gemini",   "(Google)",    "#4285f4"),
    ]
    _all_queries = jl(_ref_run.queries) if _ref_run else []
    _queries_data = []
    for _qi, _q in enumerate(_all_queries[:3]):
        _q_comps = {}
        for _model_key, _, _, _ in _demo_models:
            _r = _latest_by_model.get(_model_key)
            if _r:
                _ents = jl(_r.extracted_entities)
                if _qi < len(_ents):
                    _qe = _ents[_qi]
                    if isinstance(_qe, list):
                        _q_comps[_model_key] = [
                            e["value"] for e in _qe
                            if isinstance(e, dict) and e.get("type") == "company"
                        ][:3]
        _queries_data.append({"query": _q, "models": _q_comps})
    if not _queries_data:
        _queries_data = [{"query": f"Quel {p.profession} recommandes-tu à {p.city} ?", "models": {}}]

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

    # ── Accordéon IA démo (3 requêtes réelles, par modèle) ──────────────
    _acc_items = []
    for _idx, _qd in enumerate(_queries_data):
        _cols = "".join(
            f'<div class="ia-col">'
            f'<div class="ia-col__brand" style="color:{_color}">{_name}'
            f' <span style="font-size:.78em;font-weight:400;color:#94a3b8">{_company}</span></div>'
            f'<ul class="ia-col__list">'
            + ("".join(f"<li>{c}</li>" for c in _qd["models"].get(_key, []))
               or '<li class="ia-col__empty">Aucun concurrent cité</li>')
            + f'</ul></div>'
            for _key, _name, _company, _color in _demo_models
        )
        _open_cls = " open" if _idx == 0 else ""
        _icon = "−" if _idx == 0 else "+"
        _hidden_attr = "" if _idx == 0 else " hidden"
        _acc_items.append(
            f'<div class="acc-item{_open_cls}">'
            f'<button class="acc-q" onclick="toggleAcc(this)">'
            f'<span class="acc-ts">{_demo_dt_str}</span>'
            f'<span class="acc-text">« {_qd["query"]} »</span>'
            f'<span class="acc-icon">{_icon}</span></button>'
            f'<div class="acc-body"{_hidden_attr}>'
            f'<div class="ia-columns">{_cols}</div>'
            f'</div></div>'
        )
    _accordion_html = "\n".join(_acc_items)

    # ── FAQ (accordéon JS, un à la fois) ────────────────────────────────
    _faq_pairs = [
        (L("faq", f"q{i}"), L("faq", f"a{i}"))
        for i in range(1, 8)
        if L("faq", f"q{i}")
    ]
    faq_html = ""
    for _fi, (_fq, _fa) in enumerate(_faq_pairs):
        _open_faq = " open" if _fi == 0 else ""
        _hidden_faq = "" if _fi == 0 else " hidden"
        _icon_faq = "−" if _fi == 0 else "+"
        faq_html += (
            f'<div class="faq-item">'
            f'<button class="faq-q{_open_faq}" onclick="toggleFaq(this)">{_fq}'
            f'<span class="faq-icon">{_icon_faq}</span></button>'
            f'<div class="faq-a"{_hidden_faq}>{_fa}</div>'
            f'</div>'
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
.hero h1{{font-size:clamp(20px,3.5vw,40px);font-weight:800;color:#fff;max-width:760px;
  margin:0 auto 36px;letter-spacing:-.8px;line-height:1.25;
  text-shadow:0 2px 12px rgba(0,0,0,.5)}}
.hero h1 em{{font-style:normal;font-size:1.35em;display:block;margin-top:24px;letter-spacing:-.5px}}
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
.sect-sub{{color:var(--muted);font-size:clamp(17px,2vw,20px);max-width:760px;margin-bottom:44px}}

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
.stats-bar .stat__icon{{font-size:30px;line-height:1;margin-bottom:8px;display:flex;justify-content:center}}
.stats-bar .stat__val{{font-size:1.25rem;font-weight:800;color:var(--txt);letter-spacing:-.02em;line-height:1.2}}
.stats-bar .stat__lbl{{font-size:.78rem;color:var(--muted);margin-top:4px;line-height:1.4}}
@media(max-width:600px){{.stats-bar .stat{{border-right:none;border-bottom:1px solid var(--border);padding:16px 0}}.stats-bar .stat:last-child{{border-bottom:none}}}}

/* IA DEMO */
.sect-ia-demo{{background:#f8fafc;border-top:1px solid var(--border);border-bottom:1px solid var(--border)}}
.ia-accordion{{margin-bottom:28px}}
.acc-item{{background:#1e293b;border-radius:10px;margin-bottom:10px;overflow:hidden}}
.acc-q{{width:100%;text-align:left;background:transparent;border:none;cursor:pointer;
  padding:16px 20px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
.acc-ts{{color:#94a3b8;font-size:13px;white-space:nowrap;font-weight:600;flex-shrink:0}}
.acc-text{{font-style:italic;color:#f1f5f9;font-size:17px;font-weight:500;flex:1}}
.acc-icon{{background:#334155;color:#94a3b8;font-size:15px;font-weight:800;flex-shrink:0;margin-left:auto;transition:all .15s;min-width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;line-height:1}}
.acc-item.open .acc-icon{{background:#2563eb;color:#fff}}
.acc-body{{padding:0 16px 16px}}
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
.ia-insight{{background:#fff;border:2px solid var(--border);border-radius:12px;padding:22px 26px;margin:28px 0 14px}}
.ia-insight__title{{font-size:1.15rem;font-weight:800;color:var(--txt);margin-bottom:8px}}
.ia-insight__text{{font-size:14px;color:var(--muted);line-height:1.65}}
.ia-explain{{font-size:13.5px;color:#374151;background:#f0f9ff;border-left:3px solid #0ea5e9;
  padding:14px 20px;border-radius:0 8px 8px 0;margin-bottom:6px;line-height:1.65}}
.ia-mention{{text-align:center;font-size:11.5px;color:var(--muted);margin:6px 0 28px;letter-spacing:.2px}}
.ia-demo-cta{{text-align:center;padding-top:8px;border-top:1px solid var(--border);margin-top:8px}}
.ia-demo-cta__limit{{font-size:12px;color:var(--muted);margin-top:14px;font-style:italic}}

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

/* PRE-FAQ */
.sect-pre-faq{{background:linear-gradient(135deg,#0d0820 0%,#0a1840 100%);padding:72px 24px}}
.pre-faq-title{{font-size:clamp(22px,3.5vw,34px);font-weight:800;color:#fff;margin-bottom:16px;letter-spacing:-.3px;line-height:1.2}}
.pre-faq-text{{font-size:15px;color:#94a3b8;margin-bottom:32px;max-width:500px;margin-left:auto;margin-right:auto;line-height:1.7}}

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
  <a class="sn-cta" href="#book" onclick="event.preventDefault();document.getElementById('book').scrollIntoView({{behavior:'smooth'}})">Réserver mon audit gratuit</a>
</nav>

<!-- HERO -->
<div class="hero">
  <div class="c">
    <div class="hero-pill">Audit Visibilité IA &mdash; {p.name.upper()}*</div>
    <h1>À {p.city}, ChatGPT et Gemini recommandent des {p.profession}s.<em>Mais pas vous.</em></h1>
    <button class="hero-cta" onclick="document.getElementById('ia-demo').scrollIntoView({{behavior:'smooth'}})">
      Voir les résultats &darr;
    </button>
  </div>
  <p style="position:absolute;bottom:88px;right:28px;font-size:10px;color:rgba(255,255,255,.45);letter-spacing:.2px;z-index:2">*Analyse réalisée sur ChatGPT, Claude et Gemini</p>
</div>

<!-- STATS BAR -->
<div class="stats-bar">
  <div class="stats-bar__inner">
    <div class="stat">
      <div class="stat__icon"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#e8355a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="17" y1="8" x2="23" y2="14"/><line x1="23" y1="8" x2="17" y2="14"/></svg></div>
      <div class="stat__val">Des clients perdus</div><div class="stat__lbl">sans même le savoir</div>
    </div>
    <div class="stat">
      <div class="stat__icon"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#e8355a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg></div>
      <div class="stat__val">Des concurrents</div><div class="stat__lbl">qui prennent votre place</div>
    </div>
    <div class="stat">
      <div class="stat__icon"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#e8355a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg></div>
      <div class="stat__val">Un plan d'action</div><div class="stat__lbl">pour renverser la situation</div>
    </div>
  </div>
</div>

<!-- IA DEMO -->
<section class="sect-ia-demo" id="ia-demo">
  <div class="c">
    <h2 style="font-size:clamp(28px,4vw,44px);margin-bottom:6px">En ce moment</h2>
    <p class="sect-sub" style="margin-bottom:32px">Voici ce que voient vos prospects quand ils consultent leur IA pour trouver un {p.profession} à {p.city}</p>
    <div class="ia-accordion">
      {_accordion_html}
    </div>
    <div class="ia-insight">
      <h3 class="ia-insight__title">Votre entreprise n&rsquo;apparaît dans aucune réponse.</h3>
      <p class="ia-insight__text">Lorsque vos prospects demandent un {p.profession} à {p.city} à leur IA, ce sont ces entreprises qui sont recommandées.</p>
    </div>
    <div class="ia-explain">
      Les IA recommandent les entreprises pour lesquelles elles trouvent des informations fiables et structurées sur Internet.
    </div>
    <p class="ia-mention">Analyse réalisée sur ChatGPT, Claude et Gemini.</p>
    <div class="ia-demo-cta">
      <a class="btn-pitch" href="#book" onclick="event.preventDefault();document.getElementById('book').scrollIntoView({{behavior:'smooth'}})">Réserver mon audit gratuit &rarr;</a>
      <p class="ia-demo-cta__limit">Nous analysons un nombre limité d&rsquo;entreprises par secteur et par ville.</p>
    </div>
  </div>
</section>


<!-- PRE-FAQ -->
<section class="sect-pre-faq">
  <div class="c" style="text-align:center">
    <h2 class="pre-faq-title">Comprendre pourquoi votre entreprise n&rsquo;apparaît pas.</h2>
    <p class="pre-faq-text">Recevez votre audit et découvrez comment les IA choisissent les entreprises qu&rsquo;elles recommandent.</p>
    <a class="btn-pitch" href="#book" onclick="event.preventDefault();document.getElementById('book').scrollIntoView({{behavior:'smooth'}})">Réserver mon audit gratuit &rarr;</a>
  </div>
</section>

<!-- FAQ -->
{f'<section class="sect-faq"><div class="c"><div class="faq-wrap">{faq_html}</div></div></section>' if faq_html else ""}

<!-- RÉSERVER -->
<section class="sect-book" id="book" style="background:#fff;padding:80px 0">
  <div class="c" style="text-align:center">
    <p class="sect-label">Audit gratuit</p>
    <h2 style="margin-bottom:12px">Réserver votre créneau</h2>
    <p class="sect-sub" style="max-width:520px;margin:0 auto 32px">Choisissez un horaire — l&rsquo;audit est offert, sans engagement.</p>
    <div id="booking-widget">
      <div class="calendly-inline-widget"
           data-url="https://calendly.com/contact-presence-ia/20min?hide_gdpr_banner=1&primary_color=e8355a"
           style="min-width:320px;height:680px;"></div>
    </div>
    <div id="booking-confirm" style="display:none;padding:48px 32px;background:linear-gradient(135deg,#f0fdf4,#dcfce7);border-radius:16px;max-width:520px;margin:0 auto;border:2px solid #86efac">
      <div style="font-size:52px;margin-bottom:20px">✅</div>
      <h3 style="color:#15803d;font-size:1.5rem;font-weight:800;margin-bottom:12px">Rendez-vous confirmé&nbsp;!</h3>
      <p style="color:#166534;font-size:16px;line-height:1.75">Votre créneau est réservé. Vous recevrez une confirmation par email avec les détails de votre audit IA.</p>
    </div>
  </div>
</section>
<link href="https://assets.calendly.com/assets/external/widget.css" rel="stylesheet">
<script src="https://assets.calendly.com/assets/external/widget.js" type="text/javascript" async></script>

<footer>
  &copy; 2026 PRESENCE_IA &nbsp;&middot;&nbsp;
  <a href="/cgv" target="_blank" style="color:#9ca3af;text-decoration:underline">Conditions Générales de Vente</a>
</footer>

<script>
function toggleAcc(btn) {{
  const item = btn.closest('.acc-item');
  const isOpen = item.classList.contains('open');
  document.querySelectorAll('.acc-item').forEach(i => {{
    i.classList.remove('open');
    i.querySelector('.acc-body').hidden = true;
    i.querySelector('.acc-icon').textContent = '+';
  }});
  if (!isOpen) {{
    item.classList.add('open');
    item.querySelector('.acc-body').hidden = false;
    item.querySelector('.acc-icon').textContent = '−';
  }}
}}
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
window.addEventListener('message', function(e) {{
  if (e.origin === 'https://calendly.com' && e.data && e.data.event === 'calendly.event_scheduled') {{
    document.getElementById('booking-widget').style.display = 'none';
    const confirm = document.getElementById('booking-confirm');
    confirm.style.display = 'block';
    confirm.scrollIntoView({{behavior:'smooth'}});
  }}
}});
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
