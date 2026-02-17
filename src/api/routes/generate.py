from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from ...database import get_db, db_get_campaign, db_get_prospect, db_get_by_token
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
    p = db_get_by_token(db, t)
    if not p: raise HTTPException(404)
    s = _summary(db, p); comps = _comps(p, 2)
    ss = p.screenshot_url and f'<img src="{p.screenshot_url}" style="width:100%;border-radius:8px;margin:16px 0">' or ""
    qrows = "".join(
        f'<tr><td>{l}</td><td style="color:{"#e94560" if c>0 else "#2ecc71"};font-weight:bold">{"Cité" if c>0 else "Non cité"}</td></tr>'
        for l, c in zip(s["ql"], s["qm"]) if l)
    comp_html = "".join(f'<li style="color:#e94560;padding:6px 0">{c}</li>' for c in comps)
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Audit IA — {p.city}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
.hero{{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:80px 20px;text-align:center}}
.hero h1{{font-size:clamp(24px,4vw,42px);color:#fff;max-width:720px;margin:0 auto 16px}}
.hero h1 span{{color:#e94560}}.hero p{{color:#aaa;font-size:17px;max-width:560px;margin:0 auto}}
.c{{max-width:880px;margin:0 auto;padding:0 20px}}section{{padding:60px 20px}}h2{{color:#fff;margin-bottom:16px}}
.box{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:28px;margin:20px 0}}
table{{border-collapse:collapse;width:100%}}th{{background:#16213e;color:#aaa;padding:10px;font-size:12px;text-align:left}}
td{{padding:11px;border-bottom:1px solid #2a2a4e;color:#ddd}}.plans{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px;margin:30px 0}}
.plan{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:26px;position:relative}}
.plan.best{{border-color:#e94560}}.plan h3{{color:#fff;margin-bottom:8px}}.price{{font-size:38px;font-weight:bold;color:#e94560;margin:10px 0}}
.price span{{font-size:15px;color:#aaa}}.plan ul{{list-style:none;padding:0;margin:16px 0}}
.plan ul li{{padding:5px 0;color:#ccc;border-bottom:1px solid #2a2a4e}}.plan ul li::before{{content:"✓ ";color:#2ecc71}}
.btn{{display:block;background:#e94560;color:#fff;padding:14px;border-radius:6px;font-weight:bold;text-align:center;text-decoration:none;margin-top:14px}}
footer{{background:#0a0a15;padding:24px;text-align:center;color:#555;font-size:12px;border-top:1px solid #1a1a2e}}</style></head><body>
<div class="hero"><div class="c">
<h1>À <span>{p.city}</span>, les IA recommandent vos concurrents. Pas vous.</h1>
<p>Résultats de {s['runs']} tests répétés + plan clair pour corriger ça.</p></div></div>
<section><div class="c"><div class="box"><h2>📊 {p.name} — Résultats des tests</h2>
{ss}<p style="color:#aaa;margin-bottom:16px">Sur {s['runs']} runs — {", ".join(s['models'])}</p>
<table><tr><th>Requête</th><th>Résultat</th></tr>{qrows}</table>
{"<h3 style='color:#fff;margin-top:24px'>Cités à votre place :</h3><ul style='list-style:none;padding:0'>" + comp_html + "</ul>" if comps else ""}
</div></div></section>
<section style="background:#0a0a15"><div class="c"><h2 style="text-align:center">Que voulez-vous faire ?</h2>
<div class="plans">
<div class="plan"><h3>Audit Complet</h3><div class="price">97€ <span>une fois</span></div>
<ul><li>Rapport complet</li><li>Vidéo 90s perso</li><li>Plan d'action</li><li>Checklist 8 points</li></ul>
<a href="#contact" class="btn">Recevoir mon audit</a></div>
<div class="plan best"><h3>Kit Visibilité IA</h3><div class="price">500€ <span>+ 90€/mois×6</span></div>
<ul><li>Audit inclus</li><li>Kit contenu IA</li><li>Suivi 6 mois</li><li>Dashboard résultats</li></ul>
<a href="#contact" class="btn">Démarrer</a></div>
<div class="plan"><h3>On fait tout</h3><div class="price">3 500€ <span>forfait</span></div>
<ul><li>Tout inclus</li><li>Rédaction contenus</li><li>Citations locales</li><li>Garantie 6 mois</li></ul>
<a href="#contact" class="btn">Me contacter</a></div></div>
<p style="text-align:center;color:#666;font-size:13px;margin-top:16px">Pas d'appel requis.</p></div></section>
<footer>Les réponses IA peuvent varier ; résultats basés sur tests répétés horodatés ({", ".join(s["dates"])}).<br>© PRESENCE_IA</footer>
</body></html>""")
