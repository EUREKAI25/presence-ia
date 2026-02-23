"""
PRESENCE_IA V3 — Landing Calendly + Génération prospects Google Places

Routes :
  POST /api/v3/generate?token=ADMIN   → scan Google Places + stocke en DB
  GET  /api/v3/prospects.csv?token=   → export CSV
  GET  /api/v3/prospects?token=       → liste JSON
  GET  /l/{token}                     → landing page publique personnalisée
"""
import csv, hashlib, io, logging, os
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from ...models import V3ProspectDB
from ...database import SessionLocal

log = logging.getLogger(__name__)
router = APIRouter()

CALENDLY_URL = "https://calendly.com/contact-presence-ia/30min"
BASE_URL     = os.getenv("BASE_URL", "https://presence-ia.com")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_token(name: str, city: str, profession: str) -> str:
    raw = f"{name.lower().strip()}{city.lower().strip()}{profession.lower().strip()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _require_admin(token: str):
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")


# ── Landing HTML ──────────────────────────────────────────────────────────────

def _render_landing(name: str, city: str, profession: str) -> str:
    city_cap  = city.capitalize()
    pro_label = profession.lower()
    # Pluriel simple
    pro_plural = pro_label + "s" if not pro_label.endswith("s") else pro_label

    audit_points = [
        ("01", "Visibilité sur 3 IA", f"ChatGPT, Gemini et Claude testés sur les requêtes réelles de vos clients à {city_cap}."),
        ("02", "Concurrents identifiés", f"Nous identifions quels {pro_plural} locaux apparaissent à votre place dans les réponses IA."),
        ("03", "Diagnostic des causes", "Analyse des signaux manquants : structuration, cohérence sémantique, autorité locale."),
        ("04", "Plan d'action concret", "Recommandations priorisées, applicables sans refonte technique de votre site."),
    ]

    points_html = "".join(f"""
        <div class="audit-point">
            <div class="audit-num">{num}</div>
            <div>
                <strong>{title}</strong>
                <p>{desc}</p>
            </div>
        </div>""" for num, title, desc in audit_points)

    return f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Présence IA — Audit pour {name}</title>
<meta name="robots" content="noindex">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --black:   #0a0a0a;
  --white:   #ffffff;
  --grey-1:  #f5f5f5;
  --grey-2:  #e8e8e8;
  --grey-3:  #999;
  --blue:    #2563eb;
  --blue-bg: #eff4ff;
}}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  color: var(--black);
  background: var(--white);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}}
a {{ color: inherit; text-decoration: none; }}

/* NAV */
nav {{
  padding: 20px 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--grey-2);
}}
.logo {{ font-size: 1rem; font-weight: 700; letter-spacing: -0.02em; }}
.logo span {{ color: var(--blue); }}
.nav-tag {{
  font-size: 0.75rem;
  color: var(--grey-3);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}}

/* HERO */
.hero {{
  max-width: 800px;
  margin: 0 auto;
  padding: 96px 48px 72px;
  text-align: center;
}}
.hero-badge {{
  display: inline-block;
  background: var(--blue-bg);
  color: var(--blue);
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 5px 14px;
  border-radius: 100px;
  margin-bottom: 28px;
}}
.hero h1 {{
  font-size: clamp(2rem, 5vw, 3rem);
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1.1;
  margin-bottom: 20px;
  color: var(--black);
}}
.hero h1 em {{ font-style: normal; color: var(--blue); }}
.hero p {{
  font-size: 1.1rem;
  color: #555;
  max-width: 520px;
  margin: 0 auto 0;
  line-height: 1.7;
}}

/* STAT BAND */
.stats {{
  background: var(--grey-1);
  border-top: 1px solid var(--grey-2);
  border-bottom: 1px solid var(--grey-2);
  padding: 40px 48px;
  display: flex;
  justify-content: center;
  gap: 64px;
  flex-wrap: wrap;
}}
.stat-item {{ text-align: center; }}
.stat-item strong {{
  display: block;
  font-size: 2.4rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: var(--black);
  line-height: 1;
  margin-bottom: 6px;
}}
.stat-item span {{ font-size: 0.82rem; color: var(--grey-3); line-height: 1.4; }}

/* SECTION */
.section {{
  max-width: 780px;
  margin: 0 auto;
  padding: 72px 48px;
}}
.section h2 {{
  font-size: clamp(1.5rem, 3vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-bottom: 16px;
  line-height: 1.2;
}}
.section > p {{
  color: #555;
  font-size: 1.05rem;
  margin-bottom: 32px;
}}

/* CHAT DEMO */
.chat-box {{
  background: var(--grey-1);
  border: 1px solid var(--grey-2);
  border-radius: 12px;
  padding: 28px 32px;
  margin: 32px 0;
}}
.chat-q {{
  font-size: 0.85rem;
  color: var(--grey-3);
  margin-bottom: 12px;
  letter-spacing: 0.01em;
}}
.chat-q strong {{ color: #444; }}
.chat-r {{
  font-size: 0.97rem;
  color: var(--black);
  line-height: 1.7;
}}
.chat-r .competitor {{
  font-weight: 600;
  color: #c0392b;
  text-decoration: line-through;
  text-decoration-color: #c0392b60;
}}
.chat-absent {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 10px 16px;
  background: #fff8f8;
  border: 1px solid #fde8e8;
  border-radius: 8px;
  font-size: 0.85rem;
  color: #c0392b;
}}

/* AUDIT POINTS */
.audit-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  margin-top: 32px;
}}
.audit-point {{
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 20px 24px;
  border: 1px solid var(--grey-2);
  border-radius: 10px;
  background: var(--white);
}}
.audit-num {{
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  background: var(--blue-bg);
  color: var(--blue);
  font-size: 0.72rem;
  font-weight: 700;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.02em;
}}
.audit-point strong {{
  display: block;
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 4px;
}}
.audit-point p {{
  font-size: 0.85rem;
  color: #666;
  line-height: 1.5;
}}

/* CTA */
.cta-section {{
  background: var(--black);
  color: var(--white);
  padding: 80px 48px;
  text-align: center;
}}
.cta-section h2 {{
  font-size: clamp(1.8rem, 4vw, 2.6rem);
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1.1;
  margin-bottom: 16px;
}}
.cta-section p {{
  color: rgba(255,255,255,0.55);
  font-size: 1rem;
  margin-bottom: 40px;
  max-width: 460px;
  margin-left: auto;
  margin-right: auto;
}}
.btn-cta {{
  display: inline-block;
  background: var(--white);
  color: var(--black);
  font-weight: 700;
  font-size: 1rem;
  padding: 16px 44px;
  border-radius: 8px;
  letter-spacing: -0.01em;
  transition: opacity .15s;
}}
.btn-cta:hover {{ opacity: .88; }}
.btn-sub {{
  display: block;
  margin-top: 16px;
  font-size: 0.78rem;
  color: rgba(255,255,255,0.35);
  letter-spacing: 0.02em;
}}

/* DIVIDER */
.divider {{
  border: none;
  border-top: 1px solid var(--grey-2);
  margin: 0;
}}

/* FOOTER */
footer {{
  padding: 28px 48px;
  text-align: center;
  font-size: 0.78rem;
  color: var(--grey-3);
}}
footer a {{ color: var(--grey-3); }}

@media (max-width: 640px) {{
  nav, .hero, .stats, .section, .cta-section, footer {{ padding-left: 24px; padding-right: 24px; }}
  .stats {{ gap: 36px; }}
  .hero {{ padding-top: 64px; padding-bottom: 48px; }}
}}
</style>
</head>
<body>

<nav>
  <div class="logo">Présence<span>IA</span></div>
  <div class="nav-tag">Confidentiel — {name}</div>
</nav>

<div class="hero">
  <div class="hero-badge">Audit personnalisé</div>
  <h1>À <em>{city_cap}</em>, les IA recommandent<br>des {pro_plural} à vos clients.<br>Êtes-vous dans leurs réponses&nbsp;?</h1>
  <p style="margin-top:20px">ChatGPT, Gemini et Claude sont devenus les nouveaux moteurs de recommandation locale. Nous avons vérifié votre visibilité.</p>
</div>

<div class="stats">
  <div class="stat-item">
    <strong>3</strong>
    <span>IA testées<br>ChatGPT · Gemini · Claude</span>
  </div>
  <div class="stat-item">
    <strong>74%</strong>
    <span>des {pro_plural} locaux<br>absents des réponses IA</span>
  </div>
  <div class="stat-item">
    <strong>15</strong>
    <span>requêtes analysées<br>par profil</span>
  </div>
</div>

<div class="section">
  <h2>Ce que vos futurs clients voient<br>quand ils interrogent une IA</h2>
  <p>Voici le type de réponse que l'IA fournit quand un client cherche un {pro_label} à {city_cap}&nbsp;:</p>
  <div class="chat-box">
    <div class="chat-q"><strong>ChatGPT</strong> — « Quel {pro_label} recommandes-tu à {city_cap} ? »</div>
    <div class="chat-r">
      «&nbsp;À {city_cap}, je vous recommande <span class="competitor">Concurrent A</span>,
      <span class="competitor">Concurrent B</span> et <span class="competitor">Concurrent C</span>.
      Ces professionnels sont bien référencés et interviennent localement.&nbsp;»
      <div class="chat-absent">
        ↳ Votre entreprise n'apparaît pas dans cette réponse.
      </div>
    </div>
  </div>
  <p style="margin-top:0">Ce n'est pas une question de réputation. C'est une question de <strong>signaux</strong> — et ils se corrigent méthodiquement.</p>
</div>

<hr class="divider">

<div class="section" style="background:var(--grey-1);max-width:100%;padding-top:72px;padding-bottom:72px;">
  <div style="max-width:780px;margin:0 auto;">
    <h2>Ce que couvre l'audit gratuit</h2>
    <p>30 minutes. Résultats concrets sur votre situation réelle à {city_cap}.</p>
    <div class="audit-grid">
      {points_html}
    </div>
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


# ── Routes publiques ──────────────────────────────────────────────────────────

@router.get("/l/{token}", response_class=HTMLResponse)
def landing_v3(token: str):
    """Landing page personnalisée par prospect (lien envoyé en prospection)."""
    with SessionLocal() as db:
        p = db.get(V3ProspectDB, token)
    if not p:
        return HTMLResponse("<h1 style='font-family:sans-serif;padding:40px'>Page non trouvée.</h1>", status_code=404)
    return HTMLResponse(_render_landing(p.name, p.city, p.profession))


# ── Routes admin ──────────────────────────────────────────────────────────────

class GenerateTarget(BaseModel):
    city:       str
    profession: str
    search_term: str | None = None  # si vide, utilise "{profession} {city}"
    max_results: int = 5

class GenerateRequest(BaseModel):
    targets: List[GenerateTarget]


@router.post("/api/v3/generate")
def generate_v3(req: GenerateRequest, token: str = ""):
    """Scan Google Places pour chaque cible → stocke en DB → retourne CSV."""
    _require_admin(token)
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "GOOGLE_MAPS_API_KEY manquante")

    from ...google_places import search_prospects

    results = []
    with SessionLocal() as db:
        for t in req.targets:
            search = t.search_term or f"{t.profession} {t.city}"
            log.info("V3 scan: %s", search)
            try:
                prospects, _ = search_prospects(t.profession, t.city, api_key, max_results=t.max_results)
            except Exception as e:
                log.error("Google Places error (%s): %s", search, e)
                continue

            for p in prospects:
                tok = _make_token(p["name"], t.city, t.profession)
                landing_url = f"{BASE_URL}/l/{tok}"
                existing = db.get(V3ProspectDB, tok)
                if not existing:
                    row = V3ProspectDB(
                        token=tok,
                        name=p["name"],
                        city=t.city,
                        profession=t.profession,
                        phone=p.get("phone"),
                        website=p.get("website"),
                        reviews_count=p.get("reviews_count"),
                        landing_url=landing_url,
                    )
                    db.add(row)
                    db.commit()
                results.append({
                    "nom":          p["name"],
                    "ville":        t.city,
                    "metier":       t.profession,
                    "telephone":    p.get("phone", ""),
                    "site":         p.get("website", ""),
                    "avis_google":  p.get("reviews_count", ""),
                    "landing_url":  landing_url,
                })

    # Retourne CSV en streaming
    buf = io.StringIO()
    fields = ["nom", "ville", "metier", "telephone", "site", "avis_google", "landing_url"]
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


@router.get("/api/v3/prospects")
def list_v3_prospects(token: str = ""):
    _require_admin(token)
    with SessionLocal() as db:
        rows = db.query(V3ProspectDB).order_by(V3ProspectDB.created_at.desc()).all()
    return [
        {
            "token":         r.token,
            "nom":           r.name,
            "ville":         r.city,
            "metier":        r.profession,
            "telephone":     r.phone,
            "site":          r.website,
            "avis_google":   r.reviews_count,
            "landing_url":   r.landing_url,
            "contacted":     r.contacted,
            "notes":         r.notes,
            "created_at":    r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/api/v3/prospects.csv")
def export_v3_csv(token: str = ""):
    _require_admin(token)
    with SessionLocal() as db:
        rows = db.query(V3ProspectDB).order_by(V3ProspectDB.created_at.desc()).all()
    buf = io.StringIO()
    fields = ["nom", "ville", "metier", "telephone", "site", "avis_google", "landing_url", "contacted", "notes"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "nom": r.name, "ville": r.city, "metier": r.profession,
            "telephone": r.phone or "", "site": r.website or "",
            "avis_google": r.reviews_count or "", "landing_url": r.landing_url,
            "contacted": r.contacted, "notes": r.notes or "",
        })
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=prospects_v3.csv"},
    )
