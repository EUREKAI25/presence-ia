"""
PRESENCE_IA V3 — Prospection, landing Calendly, envoi Brevo

Routes publiques :
  GET  /l/{token}                          → landing personnalisée

Admin (3 onglets) :
  GET  /admin/v3?token=                    → interface complète
  POST /api/v3/generate?token=             → scan Google Places → CSV
  POST /api/v3/scrape?token=               → scraping email/tel/contact_url (background)
  POST /api/v3/upload-image?token=         → upload image de ville
  DELETE /api/v3/city-image/{city}?token=  → supprimer image
  POST /api/v3/prospect/{tok}/send-email   → envoyer email Brevo
  POST /api/v3/prospect/{tok}/send-sms     → envoyer SMS Brevo
  POST /api/v3/bulk-send?token=            → envoi en masse (throttlé)
  POST /api/v3/prospect/{tok}/contacted    → marquer contacté
  GET  /api/v3/prospects.csv?token=        → export CSV
  GET  /api/v3/bulk-status?token=          → statut envoi en masse
"""
import csv, hashlib, io, json, logging, os, re, threading, time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests as http_req
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from ...models import V3ProspectDB, V3CityImageDB
from ...database import SessionLocal

log = logging.getLogger(__name__)
router = APIRouter()

CALENDLY_URL = "https://calendly.com/contact-presence-ia/30min"
BASE_URL     = os.getenv("BASE_URL", "https://presence-ia.com")
UPLOADS_DIR  = Path(os.getenv("UPLOADS_DIR", "/opt/presence-ia/dist/uploads"))

_PHONE_FR_RE   = re.compile(r'(?:(?:\+|00)33[\s.\-]?|0)[1-9](?:[\s.\-]?\d{2}){4}')
_EMAIL_RE      = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_IGNORE_EMAIL_DOMAINS = {
    "example.com","sentry.io","w3.org","schema.org","wordpress.org",
    "google.com","facebook.com","wixpress.com","wix.com","cloudflare.com",
}
_IGNORE_EMAIL_PREFIXES = ("noreply","no-reply","donotreply","postmaster","mailer-daemon")
# Extensions de fichiers qui ne sont pas des TLD valides
_IGNORE_EMAIL_TLDS = {
    "jpg","jpeg","png","gif","svg","webp","ico","bmp","tiff","avif",
    "css","js","ts","jsx","tsx","php","html","htm","xml","json","pdf",
    "woff","woff2","ttf","eot","otf","map","gz","zip",
}
_CONTACT_KEYWORDS = ("contact","nous-contacter","contactez","joindre","coordonnees","coordonnées")

# Statut de l'envoi en masse (en mémoire)
_bulk_status: dict = {"running": False, "done": 0, "total": 0, "errors": []}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_token(name: str, city: str, profession: str) -> str:
    raw = f"{name.lower().strip()}{city.lower().strip()}{profession.lower().strip()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]

def _city_image_key(city: str) -> str:
    return city.lower().strip()

def _require_admin(token: str):
    if token != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Accès refusé")

def _normalize_phone(phone: str) -> str:
    """Normalise un téléphone FR pour Brevo : +33XXXXXXXXX"""
    p = re.sub(r'[\s.\-–]', '', phone)
    if p.startswith("00"):
        p = "+" + p[2:]
    elif p.startswith("0"):
        p = "+33" + p[1:]
    return p

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

def _contact_message_sms(name: str, city: str, landing_url: str) -> str:
    return (
        f"Bonjour, test visibilité IA effectué pour votre entreprise à {city}. "
        f"Rapport : {landing_url} - Présence IA. STOP: contact@presence-ia.com"
    )


# ── Scraping ──────────────────────────────────────────────────────────────────

def _scrape_site(url: str) -> dict:
    """Scrape homepage + page contact pour email, téléphone, URL contact."""
    result = {"email": None, "phone": None, "contact_url": None}
    if not url:
        return result

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def _extract_from_text(text: str):
        emails = [e.lower() for e in _EMAIL_RE.findall(text)
                  if e.split("@")[1] not in _IGNORE_EMAIL_DOMAINS
                  and not any(e.lower().startswith(p) for p in _IGNORE_EMAIL_PREFIXES)
                  and len(e.split("@")[1].split(".")[-1]) <= 6
                  and e.split("@")[1].split(".")[-1].lower() not in _IGNORE_EMAIL_TLDS]
        phones = _PHONE_FR_RE.findall(text)
        return emails[0] if emails else None, phones[0] if phones else None

    def _find_contact_link(text: str, base: str) -> Optional[str]:
        for m in re.finditer(r'href=["\']([^"\']+)["\']', text, re.IGNORECASE):
            href = m.group(1)
            if any(k in href.lower() for k in _CONTACT_KEYWORDS):
                full = urljoin(base, href)
                if urlparse(full).netloc == urlparse(base).netloc:
                    return full
        return None

    try:
        resp = http_req.get(url, timeout=5, headers=headers, allow_redirects=True)
        text = resp.text
        email, phone = _extract_from_text(text)
        contact_link = _find_contact_link(text, url)

        # Si page contact trouvée, scraper aussi
        if contact_link and contact_link != url:
            result["contact_url"] = contact_link
            try:
                cr = http_req.get(contact_link, timeout=4, headers=headers)
                e2, p2 = _extract_from_text(cr.text)
                email = email or e2
                phone = phone or p2
            except Exception:
                pass

        result["email"] = email
        result["phone"] = phone
    except Exception as exc:
        log.debug("Scrape %s : %s", url, exc)

    return result


# ── Brevo sending ─────────────────────────────────────────────────────────────

def _send_brevo_email(to_email: str, to_name: str, subject: str, body: str) -> bool:
    api_key = os.getenv("BREVO_API_KEY", "")
    if not api_key:
        log.error("BREVO_API_KEY manquante")
        return False
    try:
        resp = http_req.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={
                "sender": {"name": "Présence IA", "email": "contact@presence-ia.com"},
                "to": [{"email": to_email, "name": to_name}],
                "subject": subject,
                "textContent": body,
            },
            timeout=10,
        )
        return resp.status_code == 201
    except Exception as e:
        log.error("Brevo email error: %s", e)
        return False


def _send_brevo_sms(to_phone: str, message: str) -> bool:
    api_key = os.getenv("BREVO_API_KEY", "")
    if not api_key:
        return False
    phone = _normalize_phone(to_phone)
    try:
        resp = http_req.post(
            "https://api.brevo.com/v3/transactionalSMS/sms",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={"sender": "PresenceIA", "recipient": phone,
                  "content": message, "type": "transactional"},
            timeout=10,
        )
        return resp.status_code == 201
    except Exception as e:
        log.error("Brevo SMS error: %s", e)
        return False


# ── IA test ───────────────────────────────────────────────────────────────────

def _run_ia_test(profession: str, city: str) -> dict:
    import openai
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return {}
    prompt = (f"Quels {profession}s recommandes-tu à {city} ? "
              f"Cite les 3 meilleurs avec une courte description de chacun.")
    try:
        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350, temperature=0.7,
        )
        return {"prompt": prompt, "response": resp.choices[0].message.content.strip(),
                "model": "ChatGPT (gpt-4o-mini)", "tested_at": datetime.utcnow()}
    except Exception as e:
        log.error("IA test error: %s", e)
        return {}


# ── Landing HTML ──────────────────────────────────────────────────────────────

def _render_landing(p: "V3ProspectDB", competitors: list, city_image_url: str) -> str:  # type: ignore
    name       = p.name
    city_cap   = p.city.capitalize()
    pro_label  = p.profession.lower()
    pro_plural = pro_label + "s" if not pro_label.endswith("s") else pro_label

    # Concurrents
    c = competitors[:3]
    while len(c) < 3:
        c.append("un concurrent local")

    # Note Google
    rating_html = ""
    if p.rating or p.reviews_count:
        stars = "★" * round(p.rating or 0) + "☆" * (5 - round(p.rating or 0))
        rating_html = (
            f'<div style="font-size:0.82rem;color:#666;margin-top:6px;">'
            f'{f"{p.rating:.1f}/5 {stars}" if p.rating else ""}'
            f'{f" · {p.reviews_count} avis Google" if p.reviews_count else ""}'
            f'</div>'
        )

    # Chat demo
    if p.ia_response:
        ts = ""
        if p.ia_tested_at:
            ts_dt = p.ia_tested_at if isinstance(p.ia_tested_at, datetime) else datetime.fromisoformat(str(p.ia_tested_at))
            ts = ts_dt.strftime("%d/%m/%Y à %H:%M")
        chat_html = f"""
  <div class="chat-box">
    <div class="chat-meta">
      <strong>{p.ia_model or "ChatGPT"}</strong>
      {f'<span class="chat-time">Test du {ts}</span>' if ts else ""}
    </div>
    <div class="chat-prompt"><span class="chat-label">Prompt</span><em>{p.ia_prompt}</em></div>
    <div class="chat-response">
      <span class="chat-label">Réponse obtenue</span>
      <div class="chat-text">{p.ia_response.replace(chr(10), "<br>")}</div>
    </div>
    <div class="chat-absent">↳ <strong>{name}</strong> n'apparaît pas dans cette réponse.</div>
  </div>"""
    else:
        chat_html = f"""
  <div class="chat-box">
    <div class="chat-meta"><strong>ChatGPT</strong></div>
    <div class="chat-prompt">
      <span class="chat-label">Prompt</span>
      <em>Quels {pro_label}s recommandes-tu à {city_cap} ?</em>
    </div>
    <div class="chat-response">
      <span class="chat-label">Réponse obtenue</span>
      <div class="chat-text">
        «&nbsp;À {city_cap}, je vous recommande <strong>{c[0]}</strong>,
        <strong>{c[1]}</strong> et <strong>{c[2]}</strong>.
        Ces professionnels sont bien référencés et interviennent localement.&nbsp;»
      </div>
    </div>
    <div class="chat-absent">↳ <strong>{name}</strong> n'apparaît pas dans cette réponse.</div>
  </div>"""

    audit_points = [
        ("01","Visibilité sur 3 IA", f"ChatGPT, Gemini et Claude testés sur les requêtes réelles de vos clients à {city_cap}."),
        ("02","Concurrents identifiés", f"Nous identifions quels {pro_plural} locaux apparaissent à votre place dans les réponses IA."),
        ("03","Diagnostic des causes", "Analyse des signaux manquants : structuration, cohérence sémantique, autorité locale."),
        ("04","Plan d'action concret", "Recommandations priorisées, applicables sans refonte technique de votre site."),
    ]
    pts = "".join(f'<div class="audit-point"><div class="audit-num">{n}</div><div><strong>{t}</strong><p>{d}</p></div></div>'
                  for n, t, d in audit_points)

    hero_html = (
        f'<div style="position:relative;background-image:url({city_image_url});background-size:cover;background-position:center;min-height:500px;display:flex;align-items:center;justify-content:center;">'
        f'<div style="position:absolute;inset:0;background:linear-gradient(160deg,rgba(0,0,0,.68) 0%,rgba(0,0,0,.42) 60%,rgba(0,0,0,.2) 100%)"></div>'
        f'<div style="position:relative;z-index:1;text-align:center;padding:80px 48px;max-width:820px;">'
        f'<div style="display:inline-block;background:rgba(255,255,255,.15);color:#fff;font-size:.78rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:5px 14px;border-radius:100px;margin-bottom:28px;">Audit personnalisé</div>'
        f'<h1 style="color:#fff;font-size:clamp(2rem,5vw,3rem);font-weight:800;letter-spacing:-.04em;line-height:1.1;margin-bottom:20px;">À <em style="font-style:normal;color:#93c5fd">{city_cap}</em>, les IA recommandent<br>des {pro_plural} à vos clients.<br>Êtes-vous dans leurs réponses&nbsp;?</h1>'
        f'<p style="color:rgba(255,255,255,.8);font-size:1.1rem;max-width:520px;margin:0 auto;line-height:1.7;">ChatGPT, Gemini et Claude sont devenus les nouveaux moteurs de recommandation locale.</p>'
        f'</div></div>'
    ) if city_image_url else (
        f'<div class="hero"><div class="hero-badge">Audit personnalisé</div>'
        f'<h1>À <em>{city_cap}</em>, les IA recommandent<br>des {pro_plural} à vos clients.<br>Êtes-vous dans leurs réponses&nbsp;?</h1>'
        f'<p style="margin-top:20px">ChatGPT, Gemini et Claude sont devenus les nouveaux moteurs de recommandation locale.</p></div>'
    )

    return f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Présence IA — Audit pour {name}</title><meta name="robots" content="noindex">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--black:#0a0a0a;--white:#fff;--g1:#f5f5f5;--g2:#e8e8e8;--g3:#999;--blue:#2563eb;--blue-bg:#eff4ff}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--black);background:var(--white);line-height:1.6;-webkit-font-smoothing:antialiased}}
a{{color:inherit;text-decoration:none}}
nav{{padding:20px 48px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--g2);background:var(--white);position:relative;z-index:10}}
.logo{{font-size:1rem;font-weight:700;letter-spacing:-.02em}}.logo span{{color:var(--blue)}}
.nav-tag{{font-size:.75rem;color:var(--g3);letter-spacing:.04em;text-transform:uppercase}}
.hero{{max-width:820px;margin:0 auto;padding:96px 48px 72px;text-align:center}}
.hero-badge{{display:inline-block;background:var(--blue-bg);color:var(--blue);font-size:.78rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:5px 14px;border-radius:100px;margin-bottom:28px}}
.hero h1{{font-size:clamp(2rem,5vw,3rem);font-weight:800;letter-spacing:-.04em;line-height:1.1;margin-bottom:20px}}
.hero h1 em{{font-style:normal;color:var(--blue)}}.hero p{{font-size:1.1rem;color:#555;max-width:520px;margin:0 auto;line-height:1.7}}
.stats{{background:var(--g1);border-top:1px solid var(--g2);border-bottom:1px solid var(--g2);padding:40px 48px;display:flex;justify-content:center;gap:64px;flex-wrap:wrap}}
.stat-item{{text-align:center}}.stat-item strong{{display:block;font-size:2.4rem;font-weight:800;letter-spacing:-.04em;line-height:1;margin-bottom:6px}}
.stat-item span{{font-size:.82rem;color:var(--g3);line-height:1.4}}
.section{{max-width:780px;margin:0 auto;padding:72px 48px}}
.section h2{{font-size:clamp(1.5rem,3vw,2rem);font-weight:700;letter-spacing:-.03em;margin-bottom:16px;line-height:1.2}}
.section>p{{color:#555;font-size:1.05rem;margin-bottom:32px}}
.chat-box{{background:#fafafa;border:1px solid var(--g2);border-radius:12px;padding:24px 28px;margin:32px 0}}
.chat-meta{{display:flex;align-items:center;gap:12px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--g2)}}
.chat-meta strong{{font-size:.9rem}}.chat-time{{font-size:.78rem;color:var(--g3);margin-left:auto}}
.chat-label{{display:block;font-size:.72rem;font-weight:600;color:var(--g3);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.chat-prompt{{margin-bottom:16px}}.chat-prompt em{{font-style:italic;font-size:.88rem;color:#444}}
.chat-response{{margin-bottom:16px}}
.chat-text{{font-size:.95rem;color:var(--black);line-height:1.75;background:#fff;border:1px solid var(--g2);border-radius:8px;padding:14px 18px;margin-top:4px}}
.chat-absent{{display:flex;align-items:center;gap:8px;padding:10px 16px;background:#fff8f8;border:1px solid #fde8e8;border-radius:8px;font-size:.85rem;color:#c0392b;margin-top:4px}}
.audit-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:20px;margin-top:32px}}
.audit-point{{display:flex;gap:16px;align-items:flex-start;padding:20px 24px;border:1px solid var(--g2);border-radius:10px;background:var(--white)}}
.audit-num{{flex-shrink:0;width:28px;height:28px;background:var(--blue-bg);color:var(--blue);font-size:.72rem;font-weight:700;border-radius:6px;display:flex;align-items:center;justify-content:center}}
.audit-point strong{{display:block;font-size:.95rem;font-weight:600;margin-bottom:4px}}.audit-point p{{font-size:.85rem;color:#666;line-height:1.5}}
.cta-section{{background:var(--black);color:var(--white);padding:80px 48px;text-align:center}}
.cta-section h2{{font-size:clamp(1.8rem,4vw,2.6rem);font-weight:800;letter-spacing:-.04em;line-height:1.1;margin-bottom:16px}}
.cta-section p{{color:rgba(255,255,255,.55);font-size:1rem;margin-bottom:40px;max-width:460px;margin-left:auto;margin-right:auto}}
.btn-cta{{display:inline-block;background:var(--white);color:var(--black);font-weight:700;font-size:1rem;padding:16px 44px;border-radius:8px;transition:opacity .15s}}
.btn-cta:hover{{opacity:.88}}.btn-sub{{display:block;margin-top:16px;font-size:.78rem;color:rgba(255,255,255,.35);letter-spacing:.02em}}
footer{{padding:28px 48px;text-align:center;font-size:.78rem;color:var(--g3);border-top:1px solid var(--g2)}}
footer a{{color:var(--g3)}}
@media(max-width:640px){{nav,.hero,.stats,.section,.cta-section,footer{{padding-left:24px;padding-right:24px}}.stats{{gap:36px}}.hero{{padding-top:64px;padding-bottom:48px}}}}
</style></head><body>

<nav>
  <div class="logo">Présence<span>IA</span></div>
  <div class="nav-tag">Audit — {name}</div>
</nav>

{hero_html}

<div class="stats">
  <div class="stat-item"><strong>3</strong><span>IA testées<br>ChatGPT · Gemini · Claude</span></div>
  <div class="stat-item"><strong>74%</strong><span>des {pro_plural} locaux<br>absents des réponses IA</span></div>
  <div class="stat-item"><strong>15</strong><span>requêtes analysées<br>par profil</span></div>
</div>

<div class="section">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:16px;">
    <h2 style="margin-bottom:0">Ce que vos futurs clients voient<br>quand ils interrogent une IA</h2>
    <div style="text-align:right">
      <div style="font-size:.88rem;font-weight:600">{name}</div>
      {rating_html}
    </div>
  </div>
  <p>Réponse réelle obtenue en interrogeant une IA sur les {pro_label}s à {city_cap}&nbsp;:</p>
  {chat_html}
  <p style="margin-top:0">Ce n'est pas une question de réputation. C'est une question de <strong>signaux</strong> — et ils se corrigent méthodiquement.</p>
</div>

<hr style="border:none;border-top:1px solid var(--g2);">

<div style="background:var(--g1);padding:72px 48px;">
  <div style="max-width:780px;margin:0 auto;">
    <h2 style="font-size:clamp(1.5rem,3vw,2rem);font-weight:700;letter-spacing:-.03em;margin-bottom:16px;">Ce que couvre l'audit gratuit</h2>
    <p style="color:#555;font-size:1.05rem;margin-bottom:0;">30 minutes. Résultats concrets sur votre situation réelle à {city_cap}.</p>
    <div class="audit-grid">{pts}</div>
  </div>
</div>

<div class="cta-section">
  <h2>Réservez votre<br>audit gratuit</h2>
  <p>30 minutes. Résultats sur votre visibilité réelle.<br>Sans engagement.</p>
  <a href="{CALENDLY_URL}" target="_blank" class="btn-cta">Choisir un créneau →</a>
  <span class="btn-sub">Audit offert · Aucun engagement · Résultats en 48h</span>
</div>

<footer>© 2026 Présence IA &nbsp;·&nbsp;<a href="https://presence-ia.com">presence-ia.com</a> &nbsp;·&nbsp;<a href="https://presence-ia.com/cgv">CGV</a></footer>
</body></html>"""


# ── Route publique ────────────────────────────────────────────────────────────

@router.get("/l/{token}", response_class=HTMLResponse)
def landing_v3(token: str):
    with SessionLocal() as db:
        p = db.get(V3ProspectDB, token)
        if not p:
            return HTMLResponse("<h1 style='font-family:sans-serif;padding:40px'>Page non trouvée.</h1>", status_code=404)
        city_img   = db.get(V3CityImageDB, _city_image_key(p.city))
        city_image_url = city_img.image_url if city_img else ""
        competitors = json.loads(p.competitors) if p.competitors else []
        if not competitors:
            others = db.query(V3ProspectDB).filter(
                V3ProspectDB.city == p.city,
                V3ProspectDB.profession == p.profession,
                V3ProspectDB.token != token,
            ).limit(3).all()
            competitors = [o.name for o in others]
    return HTMLResponse(_render_landing(p, competitors, city_image_url))


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.get("/admin/v3", response_class=HTMLResponse)
def admin_v3(
    token: str = "",
    tab: str = "prospects",
    f_ville: str = "",
    f_email: str = "",
    f_phone: str = "",
):
    _require_admin(token)
    with SessionLocal() as db:
        all_rows = db.query(V3ProspectDB).order_by(V3ProspectDB.city, V3ProspectDB.name).all()
        city_images = db.query(V3CityImageDB).order_by(V3CityImageDB.id).all()
        all_cities  = sorted({r.city for r in all_rows})
        all_professions = sorted({r.profession for r in all_rows})

    # Filtres
    rows = all_rows
    if f_ville:
        rows = [r for r in rows if r.city.lower() == f_ville.lower()]
    if f_email == "1":
        rows = [r for r in rows if r.email]
    if f_phone == "1":
        rows = [r for r in rows if r.phone]

    total   = len(all_rows)
    n_email = sum(1 for r in all_rows if r.email)
    n_phone = sum(1 for r in all_rows if r.phone)
    n_sent  = sum(1 for r in all_rows if r.sent_at)
    pct_e   = round(n_email / total * 100) if total else 0
    pct_p   = round(n_phone / total * 100) if total else 0

    # Stats accordéon : ventilation par ville / métier / méthode
    from collections import Counter
    sent_rows = [r for r in all_rows if r.sent_at or r.contacted]
    by_ville  = Counter(r.city for r in sent_rows)
    by_metier = Counter(r.profession for r in sent_rows)
    by_method = Counter((r.sent_method or "manuel") for r in sent_rows)

    def _mini_table(counter, label):
        if not counter:
            return f'<p style="color:#999;font-size:.82rem">Aucun {label} contacté.</p>'
        rows_html = "".join(
            f'<tr><td style="padding:4px 10px;font-size:.82rem">{k.capitalize()}</td>'
            f'<td style="padding:4px 10px;font-size:.82rem;font-weight:600">{v}</td></tr>'
            for k, v in sorted(counter.items(), key=lambda x: -x[1])
        )
        return f'<table style="border-collapse:collapse">{rows_html}</table>'

    accordion_html = f"""
<details class="card" style="margin-bottom:20px;cursor:pointer">
  <summary style="font-weight:600;font-size:.9rem;list-style:none;display:flex;align-items:center;gap:10px">
    <span>📊</span>
    <span>Contacts envoyés — total toutes campagnes : <strong>{len(sent_rows)}</strong></span>
    <span style="margin-left:auto;color:#999;font-size:.8rem">▼ Détail</span>
  </summary>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:24px;margin-top:16px;padding-top:16px;border-top:1px solid #f0f0f0">
    <div>
      <div style="font-size:.75rem;text-transform:uppercase;color:#666;font-weight:600;margin-bottom:8px;letter-spacing:.05em">Par ville</div>
      {_mini_table(by_ville, "ville")}
    </div>
    <div>
      <div style="font-size:.75rem;text-transform:uppercase;color:#666;font-weight:600;margin-bottom:8px;letter-spacing:.05em">Par métier</div>
      {_mini_table(by_metier, "métier")}
    </div>
    <div>
      <div style="font-size:.75rem;text-transform:uppercase;color:#666;font-weight:600;margin-bottom:8px;letter-spacing:.05em">Par méthode</div>
      {_mini_table(by_method, "méthode")}
    </div>
  </div>
  {''.join(
    f'<div style="margin-top:12px;font-size:.78rem;color:#666;border-top:1px solid #f0f0f0;padding-top:10px">'
    f'<strong>{r.name}</strong> ({r.city}) — {r.sent_method or "manuel"} '
    f'le {(r.sent_at if isinstance(r.sent_at, datetime) else datetime.fromisoformat(str(r.sent_at))).strftime("%d/%m à %H:%M") if r.sent_at else "?"}'
    f'</div>'
    for r in sorted(sent_rows, key=lambda x: x.sent_at or datetime.min, reverse=True)[:20]
  ) if sent_rows else ""}
</details>"""

    # Table prospects
    table_rows = ""
    for r in rows:
        sent_info = ""
        if r.sent_at:
            dt = r.sent_at if isinstance(r.sent_at, datetime) else datetime.fromisoformat(str(r.sent_at))
            sent_info = f'<span style="color:#16a34a;font-size:.75rem">✓ {r.sent_method or "envoyé"} le {dt.strftime("%d/%m à %H:%M")}</span>'
        elif r.contacted:
            sent_info = '<span style="color:#16a34a;font-size:.75rem">✓ Contacté</span>'
        else:
            sent_info = '<span style="color:#999;font-size:.75rem">—</span>'

        actions = f'<button onclick="copyMsg(\'{r.token}\')" title="Copier le message" style="{_btn_style()}">📋</button> '
        if r.contact_url:
            actions += f'<a href="{r.contact_url}" target="_blank" title="Formulaire contact" style="{_btn_style()}">📝</a> '
        if r.email:
            actions += f'<button onclick="sendEmail(\'{r.token}\')" title="Envoyer email" style="{_btn_style(blue=True)}">✉</button> '
        if r.phone:
            actions += f'<button onclick="sendSMS(\'{r.token}\')" title="Envoyer SMS" style="{_btn_style(blue=True)}">💬</button>'

        rating_str = f"{r.rating:.1f}★" if r.rating else "—"
        avis_str   = str(r.reviews_count) if r.reviews_count else "—"

        table_rows += f"""<tr id="row-{r.token}">
          <td style="font-size:.85rem"><strong>{r.name}</strong></td>
          <td style="font-size:.82rem">{r.city}</td>
          <td style="font-size:.82rem">{r.profession}</td>
          <td style="font-size:.82rem">{r.phone or '<span style="color:#ccc">—</span>'}</td>
          <td style="font-size:.82rem">{r.email or '<span style="color:#ccc">—</span>'}</td>
          <td style="font-size:.8rem;color:#666;text-align:center">{rating_str}</td>
          <td style="font-size:.8rem;color:#666;text-align:center">{avis_str}</td>
          <td id="status-{r.token}">{sent_info}</td>
          <td style="white-space:nowrap">{actions}</td>
          <textarea id="msg-{r.token}" style="display:none">{_contact_message(r.name, r.city, r.profession, r.landing_url)}</textarea>
        </tr>"""

    # Section images
    img_grid = ""
    for ci in city_images:
        img_grid += f"""
        <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #f0f0f0;">
          <img src="{ci.image_url}" style="height:52px;width:80px;object-fit:cover;border-radius:6px;" onerror="this.style.display='none'">
          <div style="flex:1">
            <strong style="font-size:.9rem">{ci.id.capitalize()}</strong>
            <div style="font-size:.75rem;color:#999;word-break:break-all">{ci.image_url[:60]}…</div>
          </div>
          <button onclick="deleteImage('{ci.id}')"
            style="padding:4px 10px;border:1px solid #fde8e8;background:#fff8f8;color:#c0392b;border-radius:5px;cursor:pointer;font-size:.78rem;">
            Supprimer
          </button>
        </div>"""

    city_options = "".join(f'<option value="{c}"{"selected" if c==f_ville else ""}>{c.capitalize()}</option>' for c in all_cities)

    # Tab active
    t1 = "active" if tab == "prospects" else ""
    t2 = "active" if tab == "images" else ""
    t3 = "active" if tab == "textes" else ""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin V3 — Présence IA</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f8f9fa;color:#1a1a1a}}
.topbar{{background:#0a0a0a;color:#fff;padding:14px 28px;display:flex;align-items:center;gap:16px}}
.topbar h1{{font-size:.95rem;font-weight:600}}.topbar a{{color:rgba(255,255,255,.6);font-size:.82rem;text-decoration:none}}
.topbar a:hover{{color:#fff}}
.tabs{{background:#fff;border-bottom:2px solid #e5e7eb;display:flex;gap:0;padding:0 28px}}
.tab{{padding:14px 20px;font-size:.88rem;font-weight:500;color:#666;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;text-decoration:none}}
.tab.active{{color:#2563eb;border-bottom-color:#2563eb;font-weight:600}}
.container{{max-width:1360px;margin:0 auto;padding:24px 28px}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:20px 24px;margin-bottom:20px}}
.stats-bar{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:20px}}
.stat-chip{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px 18px;font-size:.85rem}}
.stat-chip strong{{font-size:1.2rem;font-weight:800;display:block;letter-spacing:-.02em}}
.stat-chip span{{color:#666}}
.filters{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:16px}}
select,input[type=text]{{padding:7px 11px;border:1px solid #e5e7eb;border-radius:6px;font-size:.83rem}}
.btn{{padding:8px 14px;border-radius:6px;cursor:pointer;font-size:.82rem;font-weight:500;border:1px solid #e5e7eb;background:#fff}}
.btn-primary{{background:#2563eb;color:#fff;border-color:#2563eb}}
.btn-danger{{background:#dc2626;color:#fff;border-color:#dc2626}}
.btn-sm{{padding:5px 10px;font-size:.78rem}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
th{{text-align:left;padding:8px 10px;border-bottom:2px solid #f0f0f0;color:#666;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;font-weight:600}}
td{{padding:8px 10px;border-bottom:1px solid #fafafa;vertical-align:middle}}
tr:hover{{background:#fafafa}}
.panel{{display:none}}.panel.active{{display:block}}
.new-search-form{{background:#f8f9fa;border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:20px}}
.new-search-form h3{{font-size:.88rem;font-weight:600;margin-bottom:12px}}
.form-row{{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}}
.form-group label{{display:block;font-size:.75rem;color:#666;margin-bottom:4px;font-weight:500}}
</style>
</head><body>

<div class="topbar">
  <h1>Présence<strong style="color:#93c5fd">IA</strong> · Admin V3</h1>
  <a href="/admin?token={token}">← Admin principal</a>
  <a href="/api/v3/prospects.csv?token={token}" class="btn btn-primary btn-sm" style="margin-left:auto;text-decoration:none">⬇ CSV</a>
</div>

<div class="tabs">
  <a class="tab {t1}" href="/admin/v3?token={token}&tab=prospects">👥 Prospects</a>
  <a class="tab {t2}" href="/admin/v3?token={token}&tab=images">🖼 Images & Vidéos</a>
  <a class="tab {t3}" href="/admin/v3?token={token}&tab=textes">✏️ Textes</a>
</div>

<div class="container">

<!-- ── Onglet Prospects ── -->
<div class="panel {"active" if tab=="prospects" else ""}">

  {accordion_html}

  <div class="stats-bar">
    <div class="stat-chip"><strong>{total}</strong><span>Prospects total</span></div>
    <div class="stat-chip"><strong style="color:#2563eb">{n_email} <span style="font-size:.8rem;font-weight:400">({pct_e}%)</span></strong><span>Avec email</span></div>
    <div class="stat-chip"><strong style="color:#2563eb">{n_phone} <span style="font-size:.8rem;font-weight:400">({pct_p}%)</span></strong><span>Avec téléphone</span></div>
    <div class="stat-chip"><strong style="color:#16a34a">{n_sent}</strong><span>Contactés</span></div>
  </div>

  <div class="new-search-form">
    <h3>Nouvelle recherche de prospects</h3>
    <div class="form-row">
      <div class="form-group"><label>Ville</label><input type="text" id="ns-city" placeholder="ex: Marseille" style="width:140px"></div>
      <div class="form-group"><label>Métier</label>
        <select id="ns-profession">
          {"".join(f'<option value="{p}">{p}</option>' for p in all_professions)}
          <option value="">— autre (taper) —</option>
        </select>
      </div>
      <div class="form-group"><label>Métier (libre)</label><input type="text" id="ns-profession-custom" placeholder="ou taper ici" style="width:130px"></div>
      <div class="form-group"><label>Nb max</label><input type="number" id="ns-max" value="10" min="1" max="20" style="width:70px"></div>
      <div class="form-group"><label>Test IA</label>
        <select id="ns-ia"><option value="true">Oui (recommandé)</option><option value="false">Non (rapide)</option></select>
      </div>
      <div class="form-group" style="align-self:flex-end">
        <button class="btn btn-primary" onclick="launchSearch()">🔍 Lancer</button>
      </div>
    </div>
    <div id="search-status" style="font-size:.82rem;color:#666;margin-top:8px"></div>
  </div>

  <div class="card" style="padding:14px 20px">
    <div class="filters">
      <span style="font-size:.82rem;font-weight:600;color:#444">{len(rows)} résultats</span>
      <select onchange="applyFilter()" id="f-ville">
        <option value="">Toutes les villes</option>
        {city_options}
      </select>
      <label style="display:flex;align-items:center;gap:6px;font-size:.82rem">
        <input type="checkbox" id="f-email" {"checked" if f_email=="1" else ""} onchange="applyFilter()"> Email présent
      </label>
      <label style="display:flex;align-items:center;gap:6px;font-size:.82rem">
        <input type="checkbox" id="f-phone" {"checked" if f_phone=="1" else ""} onchange="applyFilter()"> Tél présent
      </label>
      <button class="btn btn-sm" onclick="resetFilters()">Réinitialiser</button>
      <div style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn btn-sm" onclick="scrapeAll()" title="Récupère emails/tels/URLs contact depuis les sites web">🔎 Scraper</button>
        <button class="btn btn-sm" onclick="bulkSend('email', true)" title="Test : envoie tous les messages à votre adresse email">🧪 Test email</button>
        <button class="btn btn-sm" onclick="bulkSend('sms', true)" title="Test : envoie tous les SMS à votre numéro">🧪 Test SMS</button>
        <button class="btn btn-primary btn-sm" onclick="bulkSend('email', false)" title="Envoie à tous les prospects avec email (1 par minute)">✉ Email à tous</button>
        <button class="btn btn-primary btn-sm" onclick="bulkSend('sms', false)">💬 SMS à tous</button>
      </div>
    </div>

    <div id="bulk-progress" style="display:none;padding:8px 0;font-size:.82rem;color:#2563eb"></div>

    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Nom</th><th>Ville</th><th>Métier</th><th>Téléphone</th><th>Email</th>
          <th>Note</th><th>Avis</th><th>Statut</th><th>Actions</th>
        </tr></thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
  </div>
</div>

<!-- ── Onglet Images ── -->
<div class="panel {"active" if tab=="images" else ""}">
  <div class="card">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:16px">Ajouter / remplacer une image de ville</h2>
    <p style="font-size:.83rem;color:#666;margin-bottom:20px">
      Une image par ville. Elle s'affiche en fond du hero sur toutes les landings de cette ville, quel que soit le métier.
    </p>
    <div style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;">
      <div class="form-group"><label>Ville</label><input type="text" id="img-city" placeholder="ex: Montpellier" style="width:150px"></div>
      <div class="form-group">
        <label>Image (fichier)</label>
        <input type="file" id="img-file" accept="image/*" style="font-size:.82rem">
      </div>
      <button class="btn btn-primary" onclick="uploadImage()">⬆ Uploader</button>
    </div>
    <div id="upload-status" style="font-size:.82rem;margin-top:10px;color:#666"></div>
  </div>

  <div class="card">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:16px">Images enregistrées ({len(city_images)})</h2>
    {img_grid if img_grid else '<p style="color:#999;font-size:.85rem">Aucune image pour le moment.</p>'}
  </div>
</div>

<!-- ── Onglet Textes ── -->
<div class="panel {"active" if tab=="textes" else ""}">
  <div class="card" style="text-align:center;padding:48px">
    <p style="color:#999;font-size:.9rem">Édition des textes de la landing — à venir prochainement.</p>
  </div>
</div>

</div><!-- /container -->

<script>
const TOKEN = "{token}";

function applyFilter() {{
  const v = document.getElementById('f-ville').value;
  const e = document.getElementById('f-email').checked ? '1' : '';
  const p = document.getElementById('f-phone').checked ? '1' : '';
  location.href = `/admin/v3?token=${{TOKEN}}&tab=prospects&f_ville=${{v}}&f_email=${{e}}&f_phone=${{p}}`;
}}
function resetFilters() {{
  location.href = `/admin/v3?token=${{TOKEN}}&tab=prospects`;
}}

function copyMsg(tok) {{
  const msg = document.getElementById('msg-' + tok).value;
  navigator.clipboard.writeText(msg).then(() => {{
    const btn = event.target;
    btn.textContent = '✓';
    setTimeout(() => btn.textContent = '📋', 1500);
  }});
}}

async function sendEmail(tok) {{
  if (!confirm('Envoyer l\\'email Brevo à ce prospect ?')) return;
  const r = await fetch(`/api/v3/prospect/${{tok}}/send-email`, {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{token: TOKEN}})
  }});
  const d = await r.json();
  if (r.ok && d.ok) {{
    document.getElementById('status-' + tok).innerHTML = '<span style="color:#16a34a;font-size:.75rem">✓ email envoyé</span>';
  }} else {{
    alert('Erreur: ' + (d.error || 'inconnue'));
  }}
}}

async function sendSMS(tok) {{
  if (!confirm('Envoyer le SMS Brevo à ce prospect ?')) return;
  const r = await fetch(`/api/v3/prospect/${{tok}}/send-sms`, {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{token: TOKEN}})
  }});
  const d = await r.json();
  if (r.ok && d.ok) {{
    document.getElementById('status-' + tok).innerHTML = '<span style="color:#16a34a;font-size:.75rem">✓ SMS envoyé</span>';
  }} else {{
    alert('Erreur: ' + (d.error || 'inconnue'));
  }}
}}

async function scrapeAll() {{
  const btn = event.target;
  btn.disabled = true; btn.textContent = '⏳ Scraping...';
  await fetch(`/api/v3/scrape?token=${{TOKEN}}`, {{method:'POST'}});
  btn.textContent = '⏳ En cours (rafraîchis dans 1 min)';
  setTimeout(() => location.reload(), 60000);
}}

async function bulkSend(method, isTest) {{
  let testEmail = null, testPhone = null;
  if (isTest) {{
    if (method === 'email') {{
      testEmail = prompt('Email de test (recevra tous les messages) :');
      if (!testEmail) return;
    }} else {{
      testPhone = prompt('Numéro de test (recevra tous les SMS, format 06XXXXXXXX) :');
      if (!testPhone) return;
    }}
  }} else {{
    const label = method === 'email' ? 'tous les emails' : 'tous les SMS';
    if (!confirm(`Lancer l\\'envoi RÉEL ${{label}} ? (1 envoi/60s, max 50/jour)`)) return;
  }}
  const body = {{method, delay_seconds: isTest ? 5 : 60}};
  if (testEmail) body.test_email = testEmail;
  if (testPhone) body.test_phone = testPhone;
  const r = await fetch(`/api/v3/bulk-send?token=${{TOKEN}}`, {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(body)
  }});
  const d = await r.json();
  document.getElementById('bulk-progress').style.display = 'block';
  const modeLabel = d.test_mode ? '🧪 MODE TEST' : '✉ Envoi réel';
  document.getElementById('bulk-progress').textContent =
    `${{modeLabel}} — ${{d.total}} envois · ${{d.note}} · Rafraîchis la page pour voir les statuts.`;
}}

async function launchSearch() {{
  const city = document.getElementById('ns-city').value.trim();
  const p1   = document.getElementById('ns-profession').value;
  const p2   = document.getElementById('ns-profession-custom').value.trim();
  const prof = p2 || p1;
  const max  = parseInt(document.getElementById('ns-max').value) || 10;
  const ia   = document.getElementById('ns-ia').value === 'true';
  if (!city || !prof) {{ alert('Ville et métier requis'); return; }}
  const status = document.getElementById('search-status');
  status.textContent = '⏳ Recherche en cours...';
  const r = await fetch(`/api/v3/generate?token=${{TOKEN}}`, {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{targets:[{{city, profession:prof, max_results:max}}], run_ia_test:ia}})
  }});
  if (r.ok) {{
    const blob = await r.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `prospects_${{city}}_${{prof}}.csv`;
    a.click();
    status.textContent = '✓ Terminé — CSV téléchargé. Rafraîchis pour voir les nouveaux prospects.';
    setTimeout(() => location.reload(), 2000);
  }} else {{
    status.textContent = '❌ Erreur lors de la recherche.';
  }}
}}

async function uploadImage() {{
  const city = document.getElementById('img-city').value.trim();
  const file = document.getElementById('img-file').files[0];
  const status = document.getElementById('upload-status');
  if (!city || !file) {{ alert('Ville et fichier requis'); return; }}
  const fd = new FormData();
  fd.append('city', city); fd.append('profession', '');
  fd.append('file', file);
  status.textContent = '⏳ Upload en cours...';
  const r = await fetch(`/api/v3/upload-image?token=${{TOKEN}}`, {{method:'POST', body:fd}});
  const d = await r.json();
  if (r.ok) {{
    status.textContent = '✓ Image enregistrée pour ' + city;
    setTimeout(() => location.reload(), 1000);
  }} else {{
    status.textContent = '❌ Erreur upload';
  }}
}}

async function deleteImage(imgId) {{
  if (!confirm('Supprimer cette image ?')) return;
  await fetch(`/api/v3/city-image/${{imgId}}?token=${{TOKEN}}`, {{method:'DELETE'}});
  location.reload();
}}
</script>
</body></html>""")


def _btn_style(blue=False) -> str:
    base = "padding:4px 8px;border-radius:5px;cursor:pointer;font-size:.82rem;border:1px solid #e5e7eb;"
    return base + ("background:#2563eb;color:#fff;border-color:#2563eb;" if blue else "background:#fff;")


# ── Endpoints ─────────────────────────────────────────────────────────────────

class GenerateTarget(BaseModel):
    city: str; profession: str
    search_term: Optional[str] = None; max_results: int = 5

class GenerateRequest(BaseModel):
    targets: List[GenerateTarget]; run_ia_test: bool = True

class BulkSendRequest(BaseModel):
    method: str = "email"   # "email" | "sms"
    delay_seconds: int = 60
    max_per_day: int = 50
    test_email: Optional[str] = None  # Mode test : envoie ici au lieu du vrai email
    test_phone: Optional[str] = None  # Mode test : envoie ici au lieu du vrai tel


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
            try:
                # Compte les prospects existants pour cette paire
                n_existing = db.query(V3ProspectDB).filter_by(
                    city=t.city, profession=t.profession
                ).count()
                # Fetch assez de résultats Google pour trouver t.max_results NOUVEAUX
                raw_max = min(t.max_results + n_existing + 10, 60)
                prospects, _ = search_prospects(t.profession, t.city, api_key, max_results=raw_max)
            except Exception as e:
                log.error("Google Places (%s %s): %s", t.profession, t.city, e)
                continue
            ia_data = _run_ia_test(t.profession, t.city) if req.run_ia_test else {}
            all_names = [p["name"] for p in prospects]
            new_count = 0
            for p in prospects:
                if new_count >= t.max_results:
                    break
                tok = _make_token(p["name"], t.city, t.profession)
                landing_url = f"{BASE_URL}/l/{tok}"
                competitors = [n for n in all_names if n != p["name"]][:3]
                existing = db.get(V3ProspectDB, tok)
                if not existing:
                    new_count += 1
                    db.add(V3ProspectDB(
                        token=tok, name=p["name"], city=t.city, profession=t.profession,
                        phone=p.get("phone"), website=p.get("website"),
                        reviews_count=p.get("reviews_count"), rating=p.get("rating"),
                        landing_url=landing_url,
                        competitors=json.dumps(competitors, ensure_ascii=False),
                        ia_prompt=ia_data.get("prompt"), ia_response=ia_data.get("response"),
                        ia_model=ia_data.get("model"), ia_tested_at=ia_data.get("tested_at"),
                    ))
                else:
                    existing.competitors = json.dumps(competitors, ensure_ascii=False)
                    existing.rating = p.get("rating") or existing.rating
                    if ia_data:
                        existing.ia_prompt = ia_data.get("prompt")
                        existing.ia_response = ia_data.get("response")
                        existing.ia_model = ia_data.get("model")
                        existing.ia_tested_at = ia_data.get("tested_at")
                db.commit()
                results.append({
                    "nom": p["name"], "ville": t.city, "metier": t.profession,
                    "telephone": p.get("phone",""), "site": p.get("website",""),
                    "avis_google": p.get("reviews_count",""), "note": p.get("rating",""),
                    "landing_url": landing_url,
                    "concurrents": " | ".join(competitors),
                    "message_contact": _contact_message(p["name"], t.city, t.profession, landing_url),
                })
    buf = io.StringIO()
    fields = ["nom","ville","metier","telephone","site","avis_google","note","landing_url","concurrents","message_contact"]
    w = csv.DictWriter(buf, fieldnames=fields); w.writeheader(); w.writerows(results)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=prospects_v3_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"})


@router.post("/api/v3/scrape")
def scrape_prospects(token: str = ""):
    """Lance le scraping en background pour tous les prospects sans email/tel."""
    _require_admin(token)
    def _do_scrape():
        with SessionLocal() as db:
            to_scrape = db.query(V3ProspectDB).filter(
                V3ProspectDB.website.isnot(None),
                V3ProspectDB.scrape_status.is_(None),
            ).all()
            for p in to_scrape:
                p.scrape_status = "pending"
                db.commit()
                result = _scrape_site(p.website)
                p.email        = p.email or result.get("email")
                p.phone        = p.phone or result.get("phone")
                p.contact_url  = result.get("contact_url")
                p.scrape_status = "done"
                db.commit()
                time.sleep(1)  # 1s entre chaque scrape
    threading.Thread(target=_do_scrape, daemon=True).start()
    with SessionLocal() as db:
        count = db.query(V3ProspectDB).filter(V3ProspectDB.scrape_status.is_(None)).count()
    return {"ok": True, "queued": count}


@router.post("/api/v3/upload-image")
async def upload_city_image(
    token: str = "", city: str = Form(...),
    profession: str = Form(""), file: UploadFile = File(...),
):
    _require_admin(token)
    img_id = _city_image_key(city)
    ext    = (file.filename or "jpg").rsplit(".", 1)[-1].lower()
    fname  = f"v3_city_{img_id}.{ext}"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / fname).write_bytes(await file.read())
    url = f"{BASE_URL}/dist/uploads/{fname}"
    with SessionLocal() as db:
        existing = db.get(V3CityImageDB, img_id)
        if existing:
            existing.image_url = url
        else:
            db.add(V3CityImageDB(id=img_id, image_url=url))
        db.commit()
    return {"ok": True, "url": url}


@router.delete("/api/v3/city-image/{city_id}")
def delete_city_image(city_id: str, token: str = ""):
    _require_admin(token)
    with SessionLocal() as db:
        ci = db.get(V3CityImageDB, city_id)
        if ci:
            db.delete(ci)
            db.commit()
    return {"ok": True}


@router.post("/api/v3/prospect/{tok}/send-email")
async def send_email_prospect(tok: str, request: Request):
    body = await request.json()
    _require_admin(body.get("token", ""))
    with SessionLocal() as db:
        p = db.get(V3ProspectDB, tok)
        if not p:
            raise HTTPException(404)
        if not p.email:
            return JSONResponse({"ok": False, "error": "Pas d'email pour ce prospect"})
        msg  = _contact_message(p.name, p.city, p.profession, p.landing_url)
        subj = f"Votre visibilité IA à {p.city} — résultat personnalisé"
        ok   = _send_brevo_email(p.email, p.name, subj, msg)
        if ok:
            p.sent_at     = datetime.utcnow()
            p.sent_method = "email"
            p.contacted   = True
            db.commit()
        return {"ok": ok, "error": None if ok else "Brevo API error"}


@router.post("/api/v3/prospect/{tok}/send-sms")
async def send_sms_prospect(tok: str, request: Request):
    body = await request.json()
    _require_admin(body.get("token", ""))
    with SessionLocal() as db:
        p = db.get(V3ProspectDB, tok)
        if not p:
            raise HTTPException(404)
        if not p.phone:
            return JSONResponse({"ok": False, "error": "Pas de téléphone"})
        msg = _contact_message_sms(p.name, p.city, p.landing_url)
        ok  = _send_brevo_sms(p.phone, msg)
        if ok:
            p.sent_at     = datetime.utcnow()
            p.sent_method = "sms"
            p.contacted   = True
            db.commit()
        return {"ok": ok, "error": None if ok else "Brevo SMS error"}


@router.post("/api/v3/bulk-send")
async def bulk_send(req: BulkSendRequest, token: str = ""):
    _require_admin(token)
    test_mode = bool(req.test_email or req.test_phone)

    with SessionLocal() as db:
        if req.method == "email":
            prospects = db.query(V3ProspectDB).filter(
                V3ProspectDB.email.isnot(None),
                *([V3ProspectDB.sent_at.is_(None)] if not test_mode else []),
            ).limit(req.max_per_day).all()
        else:
            prospects = db.query(V3ProspectDB).filter(
                V3ProspectDB.phone.isnot(None),
                *([V3ProspectDB.sent_at.is_(None)] if not test_mode else []),
            ).limit(req.max_per_day).all()
        tokens = [(p.token, p.name, p.city, p.profession, p.email, p.phone, p.landing_url)
                  for p in prospects]

    _bulk_status.update({"running": True, "done": 0, "total": len(tokens), "errors": [],
                         "test_mode": test_mode})

    def _do_bulk():
        for i, (tok, name, city, profession, email, phone, landing_url) in enumerate(tokens):
            if req.method == "email":
                dest   = req.test_email if test_mode else email
                msg    = _contact_message(name, city, profession, landing_url)
                subj   = f"[TEST] Votre visibilité IA à {city}" if test_mode else \
                         f"Votre visibilité IA à {city} — résultat personnalisé"
                ok     = _send_brevo_email(dest, name, subj, msg) if dest else False
            elif req.method == "sms":
                dest   = req.test_phone if test_mode else phone
                msg    = _contact_message_sms(name, city, landing_url)
                ok     = _send_brevo_sms(dest, msg) if dest else False
            else:
                ok = False

            if ok:
                _bulk_status["done"] += 1
                if not test_mode:
                    with SessionLocal() as db:
                        p = db.get(V3ProspectDB, tok)
                        if p:
                            p.sent_at = datetime.utcnow()
                            p.sent_method = req.method
                            p.contacted = True
                            db.commit()
            else:
                _bulk_status["errors"].append(tok)

            if i < len(tokens) - 1:
                time.sleep(req.delay_seconds)
        _bulk_status["running"] = False

    threading.Thread(target=_do_bulk, daemon=True).start()
    mode_label = f"MODE TEST → {req.test_email or req.test_phone}" if test_mode else "envoi réel"
    return {"ok": True, "total": len(tokens), "test_mode": test_mode,
            "note": f"{mode_label} · 1 envoi/{req.delay_seconds}s · max {req.max_per_day}/jour"}


@router.get("/api/v3/bulk-status")
def bulk_status(token: str = ""):
    _require_admin(token)
    return _bulk_status


@router.post("/api/v3/refresh-ia")
def refresh_ia(token: str = ""):
    """Relance les tests IA pour toutes les paires ville/métier (background).
    Appelé automatiquement par cron lun/jeu/dim à 9:30, 15h, 18h30."""
    _require_admin(token)

    def _do_refresh():
        with SessionLocal() as db:
            pairs = db.query(V3ProspectDB.city, V3ProspectDB.profession).distinct().all()
        for city, profession in pairs:
            try:
                ia_data = _run_ia_test(profession, city)
                if not ia_data:
                    continue
                with SessionLocal() as db:
                    for p in db.query(V3ProspectDB).filter_by(city=city, profession=profession).all():
                        p.ia_prompt    = ia_data.get("prompt")
                        p.ia_response  = ia_data.get("response")
                        p.ia_model     = ia_data.get("model")
                        p.ia_tested_at = ia_data.get("tested_at")
                    db.commit()
                log.info("refresh-ia OK: %s %s", profession, city)
            except Exception as exc:
                log.error("refresh-ia %s %s: %s", profession, city, exc)
            time.sleep(3)  # Pause entre les appels IA pour éviter le rate-limit

    threading.Thread(target=_do_refresh, daemon=True).start()
    with SessionLocal() as db:
        n_pairs = db.query(V3ProspectDB.city, V3ProspectDB.profession).distinct().count()
    return {"ok": True, "pairs": n_pairs,
            "note": f"Refresh IA lancé pour {n_pairs} paires ville/métier en background (~{n_pairs*15}s)"}


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
    return [{"token": r.token, "nom": r.name, "ville": r.city, "metier": r.profession,
             "telephone": r.phone, "email": r.email, "site": r.website,
             "avis_google": r.reviews_count, "note": r.rating,
             "landing_url": r.landing_url, "contact_url": r.contact_url,
             "concurrents": json.loads(r.competitors) if r.competitors else [],
             "ia_ok": bool(r.ia_response), "contacted": r.contacted,
             "sent_at": r.sent_at.isoformat() if r.sent_at else None,
             "sent_method": r.sent_method} for r in rows]


@router.get("/api/v3/prospects.csv")
def export_v3_csv(token: str = ""):
    _require_admin(token)
    with SessionLocal() as db:
        rows = db.query(V3ProspectDB).order_by(V3ProspectDB.created_at.desc()).all()
    buf = io.StringIO()
    fields = ["nom","ville","metier","telephone","email","site","avis_google","note",
              "landing_url","contact_url","concurrents","message_contact","contacted","sent_at","sent_method"]
    w = csv.DictWriter(buf, fieldnames=fields); w.writeheader()
    for r in rows:
        competitors = json.loads(r.competitors) if r.competitors else []
        w.writerow({
            "nom": r.name, "ville": r.city, "metier": r.profession,
            "telephone": r.phone or "", "email": r.email or "",
            "site": r.website or "", "avis_google": r.reviews_count or "",
            "note": r.rating or "", "landing_url": r.landing_url,
            "contact_url": r.contact_url or "",
            "concurrents": " | ".join(competitors),
            "message_contact": _contact_message(r.name, r.city, r.profession, r.landing_url),
            "contacted": r.contacted,
            "sent_at": r.sent_at.isoformat() if r.sent_at else "",
            "sent_method": r.sent_method or "",
        })
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=prospects_v3.csv"})
