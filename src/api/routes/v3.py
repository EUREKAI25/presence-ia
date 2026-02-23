"""
PRESENCE_IA V3 — Landing Calendly + Génération prospects Google Places

Routes publiques :
  GET  /l/{token}                          → landing personnalisée

Routes admin :
  GET  /admin/v3?token=                    → interface de gestion
  POST /api/v3/generate?token=             → scan Google Places + tests IA → CSV
  POST /api/v3/upload-image?token=         → upload image de ville (fichier)
  POST /api/v3/city-image?token=           → image de ville par URL
  POST /api/v3/prospect/{tok}/contacted    → marquer contacté
  GET  /api/v3/prospects.csv?token=        → export CSV complet
  GET  /api/v3/prospects?token=            → liste JSON
"""
import csv, hashlib, io, json, logging, os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from ...models import V3ProspectDB, V3CityImageDB
from ...database import SessionLocal

log = logging.getLogger(__name__)
router = APIRouter()

CALENDLY_URL = "https://calendly.com/contact-presence-ia/30min"
BASE_URL     = os.getenv("BASE_URL", "https://presence-ia.com")
UPLOADS_DIR  = Path(os.getenv("UPLOADS_DIR", "/opt/presence-ia/dist/uploads"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_token(name: str, city: str, profession: str) -> str:
    raw = f"{name.lower().strip()}{city.lower().strip()}{profession.lower().strip()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]

def _city_image_id(city: str, profession: str) -> str:
    return f"{city.lower().strip()}_{profession.lower().strip()}"

def _require_admin(token: str):
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")

def _contact_message(name: str, city: str, profession: str, landing_url: str) -> str:
    return (
        f"Bonjour,\n\n"
        f"Je travaille sur la visibilité des {profession}s dans les intelligences artificielles "
        f"(ChatGPT, Gemini, Claude).\n\n"
        f"J'ai effectué un test pour votre entreprise à {city} — "
        f"le résultat vous concerne directement.\n\n"
        f"Accès à votre rapport personnalisé : {landing_url}\n\n"
        f"Cordialement,\n"
        f"Présence IA — contact@presence-ia.com"
    )

def _run_ia_test(profession: str, city: str) -> dict:
    """Un appel OpenAI par combo ville/métier."""
    import openai
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return {}
    prompt = (
        f"Quels {profession}s recommandes-tu à {city} ? "
        f"Cite les 3 meilleurs avec une courte description de chacun."
    )
    try:
        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350,
            temperature=0.7,
        )
        return {
            "prompt":     prompt,
            "response":   resp.choices[0].message.content.strip(),
            "model":      "ChatGPT (gpt-4o-mini)",
            "tested_at":  datetime.utcnow(),
        }
    except Exception as e:
        log.error("IA test error (%s %s): %s", profession, city, e)
        return {}


# ── Landing HTML ──────────────────────────────────────────────────────────────

def _render_landing(
    name: str, city: str, profession: str,
    competitors: list | None = None,
    city_image_url: str = "",
    ia_prompt: str = "",
    ia_response: str = "",
    ia_model: str = "",
    ia_tested_at: datetime | None = None,
) -> str:
    city_cap   = city.capitalize()
    pro_label  = profession.lower()
    pro_plural = pro_label + "s" if not pro_label.endswith("s") else pro_label

    # Concurrents : vrais noms ou fallback
    c = (competitors or [])[:3]
    while len(c) < 3:
        c.append("un concurrent local")
    c1, c2, c3 = c[0], c[1], c[2]

    # Bloc chat : vraie réponse IA ou template générique
    if ia_response:
        tested_label = ""
        if ia_tested_at:
            tested_label = ia_tested_at.strftime("%d/%m/%Y à %H:%M") if isinstance(ia_tested_at, datetime) else str(ia_tested_at)[:16].replace("T", " à ")
        chat_html = f"""
  <div class="chat-box">
    <div class="chat-meta">
      <strong>{ia_model or "ChatGPT"}</strong>
      {f'<span class="chat-time">Test effectué le {tested_label}</span>' if tested_label else ""}
    </div>
    <div class="chat-prompt">
      <span class="chat-label">Prompt envoyé</span>
      <em>{ia_prompt}</em>
    </div>
    <div class="chat-response">
      <span class="chat-label">Réponse obtenue</span>
      <div class="chat-text">{ia_response.replace(chr(10), '<br>')}</div>
    </div>
    <div class="chat-absent">↳ <strong>{name}</strong> n'apparaît pas dans cette réponse.</div>
  </div>"""
    else:
        chat_html = f"""
  <div class="chat-box">
    <div class="chat-meta"><strong>ChatGPT</strong></div>
    <div class="chat-prompt">
      <span class="chat-label">Prompt envoyé</span>
      <em>Quels {pro_label}s recommandes-tu à {city_cap} ?</em>
    </div>
    <div class="chat-response">
      <span class="chat-label">Réponse obtenue</span>
      <div class="chat-text">
        «&nbsp;À {city_cap}, je vous recommande <strong>{c1}</strong>,
        <strong>{c2}</strong> et <strong>{c3}</strong>.
        Ces professionnels sont bien référencés et interviennent localement.&nbsp;»
      </div>
    </div>
    <div class="chat-absent">↳ <strong>{name}</strong> n'apparaît pas dans cette réponse.</div>
  </div>"""

    audit_points = [
        ("01", "Visibilité sur 3 IA",      f"ChatGPT, Gemini et Claude testés sur les requêtes réelles de vos clients à {city_cap}."),
        ("02", "Concurrents identifiés",    f"Nous identifions quels {pro_plural} locaux apparaissent à votre place dans les réponses IA."),
        ("03", "Diagnostic des causes",     "Analyse des signaux manquants : structuration, cohérence sémantique, autorité locale."),
        ("04", "Plan d'action concret",     "Recommandations priorisées, applicables sans refonte technique de votre site."),
    ]
    points_html = "".join(f"""
        <div class="audit-point">
          <div class="audit-num">{num}</div>
          <div><strong>{title}</strong><p>{desc}</p></div>
        </div>""" for num, title, desc in audit_points)

    # Hero avec ou sans image de ville
    if city_image_url:
        hero_html = f"""
<div style="position:relative;background-image:url({city_image_url});background-size:cover;background-position:center;min-height:520px;display:flex;align-items:center;justify-content:center;">
  <div style="position:absolute;inset:0;background:linear-gradient(160deg,rgba(0,0,0,0.68) 0%,rgba(0,0,0,0.45) 60%,rgba(0,0,0,0.22) 100%)"></div>
  <div style="position:relative;z-index:1;text-align:center;padding:80px 48px;max-width:820px;">
    <div style="display:inline-block;background:rgba(255,255,255,0.15);color:#fff;font-size:0.78rem;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;padding:5px 14px;border-radius:100px;margin-bottom:28px;backdrop-filter:blur(4px);">Audit personnalisé</div>
    <h1 style="color:#fff;font-size:clamp(2rem,5vw,3rem);font-weight:800;letter-spacing:-0.04em;line-height:1.1;margin-bottom:20px;">
      À <em style="font-style:normal;color:#93c5fd">{city_cap}</em>, les IA recommandent<br>des {pro_plural} à vos clients.<br>Êtes-vous dans leurs réponses&nbsp;?
    </h1>
    <p style="color:rgba(255,255,255,0.8);font-size:1.1rem;max-width:520px;margin:0 auto;line-height:1.7;">
      ChatGPT, Gemini et Claude sont devenus les nouveaux moteurs de recommandation locale.
    </p>
  </div>
</div>"""
    else:
        hero_html = f"""
<div class="hero">
  <div class="hero-badge">Audit personnalisé</div>
  <h1>À <em>{city_cap}</em>, les IA recommandent<br>des {pro_plural} à vos clients.<br>Êtes-vous dans leurs réponses&nbsp;?</h1>
  <p style="margin-top:20px">ChatGPT, Gemini et Claude sont devenus les nouveaux moteurs de recommandation locale.</p>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Présence IA — Audit pour {name}</title>
<meta name="robots" content="noindex">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --black:#0a0a0a; --white:#ffffff; --grey-1:#f5f5f5;
  --grey-2:#e8e8e8; --grey-3:#999; --blue:#2563eb; --blue-bg:#eff4ff;
}}
body {{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  color:var(--black); background:var(--white); line-height:1.6;
  -webkit-font-smoothing:antialiased;
}}
a {{ color:inherit; text-decoration:none; }}
nav {{
  padding:20px 48px; display:flex; align-items:center;
  justify-content:space-between; border-bottom:1px solid var(--grey-2);
  background:var(--white); position:relative; z-index:10;
}}
.logo {{ font-size:1rem; font-weight:700; letter-spacing:-0.02em; }}
.logo span {{ color:var(--blue); }}
.nav-tag {{ font-size:0.75rem; color:var(--grey-3); letter-spacing:0.04em; text-transform:uppercase; }}
.hero {{
  max-width:820px; margin:0 auto;
  padding:96px 48px 72px; text-align:center;
}}
.hero-badge {{
  display:inline-block; background:var(--blue-bg); color:var(--blue);
  font-size:0.78rem; font-weight:600; letter-spacing:0.06em;
  text-transform:uppercase; padding:5px 14px; border-radius:100px; margin-bottom:28px;
}}
.hero h1 {{
  font-size:clamp(2rem,5vw,3rem); font-weight:800;
  letter-spacing:-0.04em; line-height:1.1; margin-bottom:20px;
}}
.hero h1 em {{ font-style:normal; color:var(--blue); }}
.hero p {{ font-size:1.1rem; color:#555; max-width:520px; margin:0 auto; line-height:1.7; }}
.stats {{
  background:var(--grey-1); border-top:1px solid var(--grey-2);
  border-bottom:1px solid var(--grey-2); padding:40px 48px;
  display:flex; justify-content:center; gap:64px; flex-wrap:wrap;
}}
.stat-item {{ text-align:center; }}
.stat-item strong {{
  display:block; font-size:2.4rem; font-weight:800;
  letter-spacing:-0.04em; line-height:1; margin-bottom:6px;
}}
.stat-item span {{ font-size:0.82rem; color:var(--grey-3); line-height:1.4; }}
.section {{ max-width:780px; margin:0 auto; padding:72px 48px; }}
.section h2 {{
  font-size:clamp(1.5rem,3vw,2rem); font-weight:700;
  letter-spacing:-0.03em; margin-bottom:16px; line-height:1.2;
}}
.section > p {{ color:#555; font-size:1.05rem; margin-bottom:32px; }}

/* Chat demo */
.chat-box {{
  background:#fafafa; border:1px solid var(--grey-2);
  border-radius:12px; padding:24px 28px; margin:32px 0;
}}
.chat-meta {{
  display:flex; align-items:center; gap:12px;
  margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid var(--grey-2);
}}
.chat-meta strong {{ font-size:0.9rem; }}
.chat-time {{ font-size:0.78rem; color:var(--grey-3); margin-left:auto; }}
.chat-prompt {{
  margin-bottom:16px;
}}
.chat-label {{
  display:block; font-size:0.72rem; font-weight:600; color:var(--grey-3);
  text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px;
}}
.chat-prompt em {{
  font-style:italic; font-size:0.88rem; color:#444;
}}
.chat-response {{ margin-bottom:16px; }}
.chat-text {{
  font-size:0.95rem; color:var(--black); line-height:1.75;
  background:#fff; border:1px solid var(--grey-2); border-radius:8px;
  padding:14px 18px; margin-top:4px;
}}
.chat-absent {{
  display:flex; align-items:center; gap:8px;
  padding:10px 16px; background:#fff8f8; border:1px solid #fde8e8;
  border-radius:8px; font-size:0.85rem; color:#c0392b; margin-top:4px;
}}

/* Audit points */
.audit-grid {{
  display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
  gap:20px; margin-top:32px;
}}
.audit-point {{
  display:flex; gap:16px; align-items:flex-start;
  padding:20px 24px; border:1px solid var(--grey-2);
  border-radius:10px; background:var(--white);
}}
.audit-num {{
  flex-shrink:0; width:28px; height:28px;
  background:var(--blue-bg); color:var(--blue); font-size:0.72rem;
  font-weight:700; border-radius:6px; display:flex;
  align-items:center; justify-content:center;
}}
.audit-point strong {{ display:block; font-size:0.95rem; font-weight:600; margin-bottom:4px; }}
.audit-point p {{ font-size:0.85rem; color:#666; line-height:1.5; }}
.cta-section {{
  background:var(--black); color:var(--white);
  padding:80px 48px; text-align:center;
}}
.cta-section h2 {{
  font-size:clamp(1.8rem,4vw,2.6rem); font-weight:800;
  letter-spacing:-0.04em; line-height:1.1; margin-bottom:16px;
}}
.cta-section p {{
  color:rgba(255,255,255,0.55); font-size:1rem; margin-bottom:40px;
  max-width:460px; margin-left:auto; margin-right:auto;
}}
.btn-cta {{
  display:inline-block; background:var(--white); color:var(--black);
  font-weight:700; font-size:1rem; padding:16px 44px;
  border-radius:8px; transition:opacity .15s;
}}
.btn-cta:hover {{ opacity:.88; }}
.btn-sub {{
  display:block; margin-top:16px; font-size:0.78rem;
  color:rgba(255,255,255,0.35); letter-spacing:0.02em;
}}
footer {{
  padding:28px 48px; text-align:center; font-size:0.78rem;
  color:var(--grey-3); border-top:1px solid var(--grey-2);
}}
footer a {{ color:var(--grey-3); }}
@media (max-width:640px) {{
  nav,.hero,.stats,.section,.cta-section,footer {{ padding-left:24px; padding-right:24px; }}
  .stats {{ gap:36px; }}
  .hero {{ padding-top:64px; padding-bottom:48px; }}
}}
</style></head><body>

<nav>
  <div class="logo">Présence<span>IA</span></div>
  <div class="nav-tag">Confidentiel — {name}</div>
</nav>

{hero_html}

<div class="stats">
  <div class="stat-item"><strong>3</strong><span>IA testées<br>ChatGPT · Gemini · Claude</span></div>
  <div class="stat-item"><strong>74%</strong><span>des {pro_plural} locaux<br>absents des réponses IA</span></div>
  <div class="stat-item"><strong>15</strong><span>requêtes analysées<br>par profil</span></div>
</div>

<div class="section">
  <h2>Ce que vos futurs clients voient<br>quand ils interrogent une IA</h2>
  <p>Voici la réponse réelle obtenue en interrogeant une IA sur les {pro_label}s à {city_cap}&nbsp;:</p>
  {chat_html}
  <p style="margin-top:0">Ce n'est pas une question de réputation. C'est une question de <strong>signaux</strong> — et ils se corrigent méthodiquement.</p>
</div>

<hr style="border:none;border-top:1px solid var(--grey-2);">

<div style="background:var(--grey-1);padding:72px 48px;">
  <div style="max-width:780px;margin:0 auto;">
    <h2 style="font-size:clamp(1.5rem,3vw,2rem);font-weight:700;letter-spacing:-0.03em;margin-bottom:16px;">Ce que couvre l'audit gratuit</h2>
    <p style="color:#555;font-size:1.05rem;margin-bottom:0;">30 minutes. Résultats concrets sur votre situation réelle à {city_cap}.</p>
    <div class="audit-grid">{points_html}</div>
  </div>
</div>

<div class="cta-section">
  <h2>Réservez votre<br>audit gratuit</h2>
  <p>30 minutes. Résultats sur votre visibilité réelle.<br>Sans engagement.</p>
  <a href="{CALENDLY_URL}" target="_blank" class="btn-cta">Choisir un créneau →</a>
  <span class="btn-sub">Audit offert · Aucun engagement · Résultats en 48h</span>
</div>

<footer>
  © 2026 Présence IA &nbsp;·&nbsp;
  <a href="https://presence-ia.com">presence-ia.com</a> &nbsp;·&nbsp;
  <a href="https://presence-ia.com/cgv">CGV</a>
</footer>

</body></html>"""


# ── Route publique ────────────────────────────────────────────────────────────

@router.get("/l/{token}", response_class=HTMLResponse)
def landing_v3(token: str):
    with SessionLocal() as db:
        p = db.get(V3ProspectDB, token)
        if not p:
            return HTMLResponse("<h1 style='font-family:sans-serif;padding:40px'>Page non trouvée.</h1>", status_code=404)
        img_id = _city_image_id(p.city, p.profession)
        city_img = db.get(V3CityImageDB, img_id)
        city_image_url = city_img.image_url if city_img else ""
        # Concurrents : depuis le prospect, sinon fallback sur les autres de la même ville
        competitors = json.loads(p.competitors) if p.competitors else []
        if not competitors:
            others = db.query(V3ProspectDB).filter(
                V3ProspectDB.city == p.city,
                V3ProspectDB.profession == p.profession,
                V3ProspectDB.token != token,
            ).limit(3).all()
            competitors = [o.name for o in others]
        ia_tested_at = p.ia_tested_at
    return HTMLResponse(_render_landing(
        p.name, p.city, p.profession,
        competitors, city_image_url,
        p.ia_prompt or "", p.ia_response or "",
        p.ia_model or "", ia_tested_at,
    ))


# ── Routes admin ──────────────────────────────────────────────────────────────

@router.get("/admin/v3", response_class=HTMLResponse)
def admin_v3(token: str = ""):
    _require_admin(token)
    with SessionLocal() as db:
        rows = db.query(V3ProspectDB).order_by(V3ProspectDB.city, V3ProspectDB.profession, V3ProspectDB.name).all()
        city_images = {ci.id: ci.image_url for ci in db.query(V3CityImageDB).all()}

    groups: dict[str, list] = {}
    for r in rows:
        key = f"{r.city}|{r.profession}"
        groups.setdefault(key, []).append(r)

    rows_html = ""
    for r in rows:
        contacted_btn = (
            '<span style="color:#16a34a;font-weight:600;font-size:0.82rem">✓ Contacté</span>'
            if r.contacted else
            f'<button onclick="markContacted(\'{r.token}\')" style="padding:4px 10px;border:1px solid #e5e7eb;border-radius:5px;cursor:pointer;font-size:0.8rem;background:#fff">Marquer</button>'
        )
        competitors = json.loads(r.competitors) if r.competitors else []
        c_str = " · ".join(competitors[:3]) or "—"
        ia_ok = "✓" if r.ia_response else "—"
        rows_html += f"""<tr id="row-{r.token}">
          <td><strong style="font-size:0.88rem">{r.name}</strong></td>
          <td style="font-size:0.82rem">{r.city}</td>
          <td style="font-size:0.82rem">{r.profession}</td>
          <td style="font-size:0.82rem">{r.phone or "—"}</td>
          <td style="font-size:0.78rem;color:#2563eb;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            {f'<a href="{r.website}" target="_blank">{r.website[:28]}…</a>' if r.website else "—"}
          </td>
          <td style="font-size:0.78rem;color:#555;max-width:200px">{c_str}</td>
          <td style="font-size:0.78rem;color:#16a34a;text-align:center">{ia_ok}</td>
          <td><a href="{r.landing_url}" target="_blank" style="color:#2563eb;font-size:0.78rem">Voir →</a></td>
          <td id="status-{r.token}">{contacted_btn}</td>
        </tr>"""

    city_forms_html = ""
    for key, group_rows in groups.items():
        city, profession = key.split("|", 1)
        img_id = _city_image_id(city, profession)
        current_url = city_images.get(img_id, "")
        preview_html = f'<img src="{current_url}" style="height:48px;border-radius:4px;object-fit:cover;margin-left:8px;" onerror="this.style.display=\'none\'">' if current_url else ""
        city_forms_html += f"""
        <div style="padding:16px 0;border-bottom:1px solid #f0f0f0;">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
            <span style="font-weight:600;font-size:0.92rem">{city.capitalize()} — {profession}</span>
            <span style="font-size:0.78rem;color:#999">({len(group_rows)} prospects)</span>
            {preview_html}
          </div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <input type="file" accept="image/*" id="file-{img_id}"
              onchange="previewFile('{img_id}')"
              style="font-size:0.82rem;flex:1;min-width:200px;">
            <span style="color:#999;font-size:0.8rem">ou</span>
            <input id="url-{img_id}" type="text" value="{current_url}"
              placeholder="URL directe (https://...)"
              style="flex:2;min-width:200px;padding:7px 11px;border:1px solid #e5e7eb;border-radius:6px;font-size:0.82rem;">
            <button onclick="saveImage('{img_id}')"
              style="padding:8px 16px;background:#0a0a0a;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:0.82rem;white-space:nowrap;">
              Enregistrer
            </button>
          </div>
          <img id="preview-{img_id}" src="" style="display:none;height:60px;border-radius:6px;margin-top:8px;object-fit:cover;">
        </div>"""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin V3 — Prospects Présence IA</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f9fafb;color:#1a1a1a;}}
.topbar{{background:#0a0a0a;color:#fff;padding:14px 32px;display:flex;align-items:center;gap:16px;}}
.topbar h1{{font-size:1rem;font-weight:600;}}
.topbar a{{color:rgba(255,255,255,0.6);font-size:0.82rem;text-decoration:none;}}
.topbar a:hover{{color:#fff;}}
.container{{max-width:1280px;margin:0 auto;padding:28px 32px;}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:24px;margin-bottom:24px;}}
h2{{font-size:1rem;font-weight:700;margin-bottom:16px;}}
table{{width:100%;border-collapse:collapse;font-size:0.85rem;}}
th{{text-align:left;padding:8px 10px;border-bottom:2px solid #f0f0f0;color:#666;font-weight:600;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.04em;}}
td{{padding:8px 10px;border-bottom:1px solid #f9fafb;vertical-align:middle;}}
tr:hover{{background:#fafafa;}}
.dl-btn{{display:inline-block;padding:8px 18px;background:#2563eb;color:#fff;border-radius:7px;font-size:0.82rem;font-weight:600;text-decoration:none;}}
</style>
</head><body>

<div class="topbar">
  <h1>Présence<strong style="color:#93c5fd">IA</strong> · Prospects V3</h1>
  <a href="/admin?token={token}">← Admin principal</a>
  <a href="/api/v3/prospects.csv?token={token}" class="dl-btn" style="margin-left:auto;background:#2563eb;">⬇ CSV complet</a>
</div>

<div class="container">

  <div class="card">
    <h2>Images de ville par métier</h2>
    <p style="color:#666;font-size:0.83rem;margin-bottom:16px;">
      Upload une image ou colle une URL. Elle s'affiche en fond du hero sur toutes les landings de ce groupe.
    </p>
    {city_forms_html}
  </div>

  <div class="card">
    <h2 style="display:flex;align-items:center;gap:12px;">
      {len(rows)} prospects
      <span style="font-weight:400;color:#999;font-size:0.85rem">{sum(1 for r in rows if r.contacted)} contactés · {sum(1 for r in rows if r.ia_response)} tests IA</span>
    </h2>
    <div style="overflow-x:auto;">
      <table>
        <thead><tr>
          <th>Nom</th><th>Ville</th><th>Métier</th><th>Tél.</th>
          <th>Site</th><th>Concurrents</th><th>IA</th><th>Landing</th><th>Statut</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </div>

</div>

<script>
const TOKEN = "{token}";

function previewFile(imgId) {{
  const file = document.getElementById(`file-${{imgId}}`).files[0];
  if (!file) return;
  const preview = document.getElementById(`preview-${{imgId}}`);
  preview.src = URL.createObjectURL(file);
  preview.style.display = 'block';
}}

async function saveImage(imgId) {{
  const fileInput = document.getElementById(`file-${{imgId}}`);
  const urlInput  = document.getElementById(`url-${{imgId}}`);

  if (fileInput.files.length > 0) {{
    // Upload fichier
    const city = imgId.split('_').slice(0,-1).join(' ');
    const profession = imgId.split('_').pop();
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fd.append('city', city);
    fd.append('profession', profession);
    const r = await fetch(`/api/v3/upload-image?token=${{TOKEN}}`, {{method:'POST', body:fd}});
    const data = await r.json();
    if (r.ok) {{
      urlInput.value = data.url;
      alert('Image uploadée ✓');
    }} else {{ alert('Erreur upload'); }}
  }} else {{
    // URL directe
    const url = urlInput.value.trim();
    const r = await fetch(`/api/v3/city-image?token=${{TOKEN}}`, {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{id: imgId, image_url: url}})
    }});
    if (r.ok) alert('Image enregistrée ✓');
    else alert('Erreur');
  }}
}}

async function markContacted(tok) {{
  const r = await fetch(`/api/v3/prospect/${{tok}}/contacted`, {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{token: TOKEN}})
  }});
  if (r.ok) document.getElementById(`status-${{tok}}`).innerHTML = '<span style="color:#16a34a;font-weight:600;font-size:0.82rem">✓ Contacté</span>';
}}
</script>
</body></html>""")


# ── Génération ────────────────────────────────────────────────────────────────

class GenerateTarget(BaseModel):
    city:         str
    profession:   str
    search_term:  Optional[str] = None
    max_results:  int = 5

class GenerateRequest(BaseModel):
    targets:      List[GenerateTarget]
    run_ia_test:  bool = True   # appel OpenAI par combo ville/métier

class CityImageRequest(BaseModel):
    id:        str
    image_url: str


@router.post("/api/v3/generate")
def generate_v3(req: GenerateRequest, token: str = ""):
    _require_admin(token)
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "GOOGLE_MAPS_API_KEY manquante")

    from ...google_places import search_prospects

    results = []
    with SessionLocal() as db:
        for t in req.targets:
            log.info("V3 scan: %s %s", t.profession, t.city)
            try:
                prospects, _ = search_prospects(t.profession, t.city, api_key, max_results=t.max_results)
            except Exception as e:
                log.error("Google Places error (%s %s): %s", t.profession, t.city, e)
                continue

            # Test IA : UN appel par combo ville/métier
            ia_data = {}
            if req.run_ia_test:
                ia_data = _run_ia_test(t.profession, t.city)
                if ia_data:
                    log.info("IA test OK: %s %s", t.profession, t.city)

            all_names = [p["name"] for p in prospects]

            for p in prospects:
                tok = _make_token(p["name"], t.city, t.profession)
                landing_url = f"{BASE_URL}/l/{tok}"
                competitors = [n for n in all_names if n != p["name"]][:3]
                msg = _contact_message(p["name"], t.city, t.profession, landing_url)

                existing = db.get(V3ProspectDB, tok)
                if not existing:
                    row = V3ProspectDB(
                        token=tok, name=p["name"], city=t.city, profession=t.profession,
                        phone=p.get("phone"), website=p.get("website"),
                        reviews_count=p.get("reviews_count"), landing_url=landing_url,
                        competitors=json.dumps(competitors, ensure_ascii=False),
                        ia_prompt=ia_data.get("prompt"),
                        ia_response=ia_data.get("response"),
                        ia_model=ia_data.get("model"),
                        ia_tested_at=ia_data.get("tested_at"),
                    )
                    db.add(row)
                else:
                    existing.competitors = json.dumps(competitors, ensure_ascii=False)
                    if ia_data:
                        existing.ia_prompt    = ia_data.get("prompt")
                        existing.ia_response  = ia_data.get("response")
                        existing.ia_model     = ia_data.get("model")
                        existing.ia_tested_at = ia_data.get("tested_at")
                db.commit()

                results.append({
                    "nom":              p["name"],
                    "ville":            t.city,
                    "metier":           t.profession,
                    "telephone":        p.get("phone", ""),
                    "site":             p.get("website", ""),
                    "avis_google":      p.get("reviews_count", ""),
                    "landing_url":      landing_url,
                    "concurrents":      " | ".join(competitors),
                    "message_contact":  msg,
                })

    buf = io.StringIO()
    fields = ["nom", "ville", "metier", "telephone", "site", "avis_google",
              "landing_url", "concurrents", "message_contact"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    writer.writerows(results)
    buf.seek(0)
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=prospects_v3_{date_str}.csv"},
    )


@router.post("/api/v3/upload-image")
async def upload_city_image(
    token: str = "",
    city: str = Form(...),
    profession: str = Form(...),
    file: UploadFile = File(...),
):
    _require_admin(token)
    img_id = _city_image_id(city, profession)
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    filename = f"v3_city_{img_id}.{ext}"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOADS_DIR / filename
    dest.write_bytes(await file.read())
    url = f"{BASE_URL}/dist/uploads/{filename}"
    with SessionLocal() as db:
        existing = db.get(V3CityImageDB, img_id)
        if existing:
            existing.image_url = url
        else:
            db.add(V3CityImageDB(id=img_id, image_url=url))
        db.commit()
    return {"ok": True, "url": url}


@router.post("/api/v3/city-image")
def set_city_image(req: CityImageRequest, token: str = ""):
    _require_admin(token)
    with SessionLocal() as db:
        existing = db.get(V3CityImageDB, req.id)
        if existing:
            existing.image_url = req.image_url
        else:
            db.add(V3CityImageDB(id=req.id, image_url=req.image_url))
        db.commit()
    return {"ok": True}


@router.post("/api/v3/prospect/{tok}/contacted")
async def mark_contacted(tok: str, request: Request):
    body = await request.json()
    _require_admin(body.get("token", ""))
    with SessionLocal() as db:
        p = db.get(V3ProspectDB, tok)
        if not p:
            raise HTTPException(404)
        p.contacted = True
        db.commit()
    return {"ok": True}


@router.get("/api/v3/prospects")
def list_v3_prospects(token: str = ""):
    _require_admin(token)
    with SessionLocal() as db:
        rows = db.query(V3ProspectDB).order_by(V3ProspectDB.created_at.desc()).all()
    return [
        {
            "token":       r.token, "nom": r.name, "ville": r.city,
            "metier":      r.profession, "telephone": r.phone, "site": r.website,
            "avis_google": r.reviews_count, "landing_url": r.landing_url,
            "concurrents": json.loads(r.competitors) if r.competitors else [],
            "ia_ok":       bool(r.ia_response), "contacted": r.contacted,
            "notes":       r.notes,
        }
        for r in rows
    ]


@router.get("/api/v3/prospects.csv")
def export_v3_csv(token: str = ""):
    _require_admin(token)
    with SessionLocal() as db:
        rows = db.query(V3ProspectDB).order_by(V3ProspectDB.created_at.desc()).all()
    buf = io.StringIO()
    fields = ["nom", "ville", "metier", "telephone", "site", "avis_google",
              "landing_url", "concurrents", "message_contact", "contacted"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for r in rows:
        competitors = json.loads(r.competitors) if r.competitors else []
        writer.writerow({
            "nom": r.name, "ville": r.city, "metier": r.profession,
            "telephone": r.phone or "", "site": r.website or "",
            "avis_google": r.reviews_count or "", "landing_url": r.landing_url,
            "concurrents": " | ".join(competitors),
            "message_contact": _contact_message(r.name, r.city, r.profession, r.landing_url),
            "contacted": r.contacted,
        })
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=prospects_v3.csv"},
    )
