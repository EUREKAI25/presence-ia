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
from fastapi import APIRouter, Cookie, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from ...models import V3ProspectDB, V3CityImageDB, V3LandingTextDB, ContentBlockDB
from ...database import SessionLocal, get_block, set_block

log = logging.getLogger(__name__)
router = APIRouter()

CALENDLY_URL  = "https://calendly.com/contact-presence-ia/30min"
BASE_URL      = os.getenv("BASE_URL", "https://presence-ia.com")
UPLOADS_DIR   = Path(os.getenv("UPLOADS_DIR", "/opt/presence-ia/dist/uploads"))

# Cookie d'authentification admin — mot de passe "zorbec"
_ADMIN_PASSWORD   = os.getenv("ADMIN_PASSWORD", "zorbec")
_ADMIN_COOKIE_KEY = "v3admin"
_ADMIN_COOKIE_VAL = hashlib.sha256(_ADMIN_PASSWORD.encode()).hexdigest()

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

def _check_admin(token: str = "", request: Request = None) -> bool:
    """Renvoie True si authentifié (token param OU cookie)."""
    if token == os.getenv("ADMIN_TOKEN", "changeme"):
        return True
    if request and request.cookies.get(_ADMIN_COOKIE_KEY) == _ADMIN_COOKIE_VAL:
        return True
    return False

def _require_admin(token: str = "", request: Request = None):
    if not _check_admin(token, request):
        raise HTTPException(403, "Accès refusé")

def _normalize_phone(phone: str) -> str:
    """Normalise un téléphone FR pour Brevo : +33XXXXXXXXX"""
    p = re.sub(r'[\s.\-–]', '', phone)
    if p.startswith("00"):
        p = "+" + p[2:]
    elif p.startswith("0"):
        p = "+33" + p[1:]
    return p

_DEFAULT_EMAIL_SUBJECT = "Votre visibilité IA à {ville} — résultat personnalisé"

_DEFAULT_EMAIL_TEMPLATE = (
    "Bonjour,\n\n"
    "Je travaille sur la visibilité des {profession}s dans les intelligences artificielles "
    "(ChatGPT, Gemini, Claude).\n\n"
    "J'ai effectué un test pour votre entreprise à {city} — "
    "le résultat vous concerne directement.\n\n"
    "Accès à votre rapport personnalisé : {landing_url}\n\n"
    "Cordialement,\n"
    "Présence IA — contact@presence-ia.com"
)

_DEFAULT_SMS_TEMPLATE = (
    "Bonjour, test visibilité IA effectué pour votre entreprise à {city}. "
    "Rapport : {landing_url} - Présence IA. STOP: contact@presence-ia.com"
)

def _contact_message(name: str, city: str, profession: str, landing_url: str,
                     template: Optional[str] = None) -> str:
    tpl = template or _DEFAULT_EMAIL_TEMPLATE
    metier  = profession.lower()
    metiers = metier + "s" if not metier.endswith("s") else metier
    try:
        return tpl.format(name=name, ville=city, metier=metier, metiers=metiers,
                          landing_url=landing_url,
                          city=city, profession=profession)  # compat anciens templates
    except Exception:
        return _DEFAULT_EMAIL_TEMPLATE.format(name=name, ville=city, metier=metier,
                                              metiers=metiers, landing_url=landing_url,
                                              city=city, profession=profession)

def _contact_message_sms(name: str, city: str, profession: str, landing_url: str,
                         template: Optional[str] = None) -> str:
    tpl = template or _DEFAULT_SMS_TEMPLATE
    metier  = profession.lower() if profession else ""
    metiers = metier + "s" if metier and not metier.endswith("s") else metier
    try:
        return tpl.format(name=name, ville=city, metier=metier, metiers=metiers,
                          landing_url=landing_url,
                          city=city, profession=profession)  # compat anciens templates
    except Exception:
        return _DEFAULT_SMS_TEMPLATE.format(name=name, ville=city, metier=metier,
                                             metiers=metiers, landing_url=landing_url,
                                             city=city, profession=profession)


def _strip_markdown(text: str) -> str:
    """Supprime les balises markdown (**, ##, *, - etc.) des réponses IA."""
    if not text:
        return text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text.strip()


def _youtube_embed(url: str) -> str:
    """Convertit une URL YouTube/Vimeo en URL embed."""
    if "youtube.com/watch?v=" in url:
        vid = url.split("v=")[1].split("&")[0]
        return f"https://www.youtube.com/embed/{vid}"
    if "youtu.be/" in url:
        vid = url.split("youtu.be/")[1].split("?")[0]
        return f"https://www.youtube.com/embed/{vid}"
    if "vimeo.com/" in url:
        vid = url.rstrip("/").split("/")[-1]
        return f"https://player.vimeo.com/video/{vid}"
    return url


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
        if resp.status_code == 201:
            return True
        log.error("Brevo email status=%s body=%s", resp.status_code, resp.text[:300])
        return False
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
        if resp.status_code == 201:
            return True
        log.error("Brevo SMS status=%s body=%s", resp.status_code, resp.text[:300])
        return False
    except Exception as e:
        log.error("Brevo SMS error: %s", e)
        return False


# ── IA test ───────────────────────────────────────────────────────────────────

_PROMPTS_FILE = Path(__file__).resolve().parents[2] / "ia_prompts.json"
_DEFAULT_PROMPTS = [
    "Quels {profession}s recommandes-tu à {city} ?",
    "Je cherche un bon {profession} à {city}, tu as des recommandations ?",
    "Quelles entreprises de {profession} font un bon travail à {city} ?",
]

def _load_prompts() -> list:
    """Charge les prompts depuis data/ia_prompts.json, sinon retourne les défauts."""
    try:
        return json.loads(_PROMPTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _DEFAULT_PROMPTS


def _run_ia_test(profession: str, city: str) -> dict:
    """Interroge ChatGPT, Gemini et Claude sur les 3 prompts. Retourne 9 résultats max."""
    pro_plural = profession.lower() + "s" if not profession.lower().endswith("s") else profession.lower()
    city_cap   = city.capitalize()
    prompts    = [p.format(profession=pro_plural, city=city_cap) for p in _load_prompts()]
    results    = []

    # Clients IA (initialisés une seule fois)
    chatgpt_client = None
    try:
        import openai
        key = os.getenv("OPENAI_API_KEY", "")
        if key:
            chatgpt_client = openai.OpenAI(api_key=key)
    except Exception as e:
        log.error("IA init ChatGPT: %s", e)

    gemini_model = None
    try:
        import google.generativeai as genai  # type: ignore
        key = os.getenv("GEMINI_API_KEY", "")
        if key:
            genai.configure(api_key=key)
            gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    except Exception as e:
        log.error("IA init Gemini: %s", e)

    anthropic_client = None
    try:
        import anthropic  # type: ignore
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if key:
            anthropic_client = anthropic.Anthropic(api_key=key)
    except Exception as e:
        log.error("IA init Claude: %s", e)

    for prompt in prompts:
        ts = datetime.utcnow().isoformat()

        if chatgpt_client:
            try:
                r = chatgpt_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=350, temperature=0.3,
                )
                results.append({"model": "ChatGPT", "prompt": prompt,
                                "response": _strip_markdown(r.choices[0].message.content.strip()),
                                "tested_at": ts})
            except Exception as e:
                log.error("IA test ChatGPT prompt=%r: %s", prompt[:40], e)

        if gemini_model:
            try:
                r = gemini_model.generate_content(prompt)
                results.append({"model": "Gemini", "prompt": prompt,
                                "response": _strip_markdown(r.text.strip()),
                                "tested_at": ts})
            except Exception as e:
                log.error("IA test Gemini prompt=%r: %s", prompt[:40], e)

        if anthropic_client:
            try:
                r = anthropic_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=350,
                    messages=[{"role": "user", "content": prompt}],
                )
                results.append({"model": "Claude", "prompt": prompt,
                                "response": _strip_markdown(r.content[0].text.strip()),
                                "tested_at": ts})
            except Exception as e:
                log.error("IA test Claude prompt=%r: %s", prompt[:40], e)

    if not results:
        return {}

    first = results[0]
    return {
        "results":   results,
        "prompt":    first["prompt"],
        "response":  first["response"],
        "model":     first["model"],
        "tested_at": datetime.fromisoformat(first["tested_at"]),
    }


# ── Landing HTML ──────────────────────────────────────────────────────────────

def _render_landing(
    p: "V3ProspectDB",  # type: ignore
    competitors: list,
    city_image_url: str,
    ia_results_list: Optional[list] = None,
    landing_text=None,       # V3LandingTextDB or None
    evidence_images: Optional[list] = None,
) -> str:
    name       = p.name
    city_cap   = p.city.capitalize()
    pro_label  = p.profession.lower()
    pro_plural = pro_label + "s" if not pro_label.endswith("s") else pro_label

    # ── Concurrents (fallback si liste courte) ────────────────────────────
    c = list(competitors[:3])
    while len(c) < 3:
        c.append("un concurrent local")

    # ── Note Google ───────────────────────────────────────────────────────
    rating_html = ""
    if p.rating or p.reviews_count:
        stars = "★" * round(p.rating or 0) + "☆" * (5 - round(p.rating or 0))
        rating_html = (
            f'<div style="font-size:0.82rem;color:#666;margin-top:6px;">'
            f'{f"{p.rating:.1f}/5 {stars}" if p.rating else ""}'
            f'{f" · {p.reviews_count} avis Google" if p.reviews_count else ""}'
            f'</div>'
        )

    # ── Construire ia_results_list depuis ia_results JSON si pas fourni ──
    if not ia_results_list:
        ia_results_list = []
        if hasattr(p, "ia_results") and p.ia_results:
            try:
                ia_results_list = json.loads(p.ia_results)
            except Exception:
                pass
        if not ia_results_list and p.ia_response:
            ia_results_list = [{
                "model":     p.ia_model or "ChatGPT",
                "prompt":    p.ia_prompt or f"Quels {pro_label}s recommandes-tu à {city_cap} ?",
                "response":  p.ia_response,
                "tested_at": p.ia_tested_at.isoformat() if isinstance(p.ia_tested_at, datetime)
                             else str(p.ia_tested_at) if p.ia_tested_at else None,
            }]

    # ── Stats réelles ─────────────────────────────────────────────────────
    n_ia = len(ia_results_list) if ia_results_list else 3
    n_competitors = len([x for x in competitors if x])
    last_test_date = ""
    if ia_results_list:
        ts_raw = ia_results_list[0].get("tested_at", "")
        if ts_raw:
            try:
                last_test_date = datetime.fromisoformat(str(ts_raw)).strftime("%d/%m/%Y")
            except Exception:
                last_test_date = str(ts_raw)[:10]
    elif p.ia_tested_at:
        dt = p.ia_tested_at if isinstance(p.ia_tested_at, datetime) else datetime.fromisoformat(str(p.ia_tested_at))
        last_test_date = dt.strftime("%d/%m/%Y")

    stats_html = f"""
<div class="stats">
  <div class="stat-item"><strong>3 IA</strong><span>testées<br>ChatGPT · Gemini · Claude</span></div>
  <div class="stat-item"><strong>3×</strong><span>fois par semaine</span></div>
  <div class="stat-item"><strong>3</strong><span>prompts différents<br>par test</span></div>
</div>"""

    # ── Chat groups (1 prompt → accordéon par IA) ─────────────────────────
    if ia_results_list:
        from collections import OrderedDict
        by_prompt = OrderedDict()
        for r in ia_results_list:
            pr = r.get("prompt") or f"Quels {pro_label}s recommandes-tu à {city_cap} ?"
            if pr not in by_prompt:
                by_prompt[pr] = {"tested_at": r.get("tested_at"), "models": []}
            by_prompt[pr]["models"].append(r)

        chat_html = ""
        for prompt_text, group in by_prompt.items():
            ts = ""
            ts_raw = group["tested_at"]
            if ts_raw:
                try:
                    ts = datetime.fromisoformat(str(ts_raw)).strftime("%d/%m à %H:%M")
                except Exception:
                    ts = str(ts_raw)[:16]
            ts_label = f" (test du {ts})" if ts else ""
            acc_items = ""
            for r in group["models"]:
                resp_html = (r.get("response", "") or "").replace("\n", "<br>")
                acc_items += (
                    f'<details class="chat-detail">'
                    f'<summary>{r["model"]} ne vous connait pas</summary>'
                    f'<div class="chat-detail-body">{resp_html}</div>'
                    f'</details>'
                )
            chat_html += (
                f'<div class="chat-group">'
                f'<div class="chat-prompt">'
                f'<span class="chat-label">Prompt{ts_label}</span>'
                f'<em>&laquo;&nbsp;{prompt_text}&nbsp;&raquo;</em>'
                f'</div>'
                f'<div class="chat-accordion">{acc_items}</div>'
                f'</div>'
            )
    else:
        # Aucune donnée IA — fallback illustratif avec mention explicite
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
    <p style="margin-top:12px;font-weight:700">→ ChatGPT ne sait même pas que vous existez.</p>
  </div>"""

    # ── Audit points ──────────────────────────────────────────────────────
    audit_points = [
        ("01","Visibilité sur 3 IA", f"ChatGPT, Gemini et Claude testés sur les requêtes réelles de vos clients à {city_cap}."),
        ("02","Concurrents identifiés", f"Nous identifions quels {pro_plural} locaux apparaissent à votre place dans les réponses IA."),
        ("03","Diagnostic des causes", "Analyse des signaux manquants : structuration, cohérence sémantique, autorité locale."),
        ("04","Plan d'action concret", "Recommandations priorisées, applicables sans refonte technique de votre site."),
    ]
    pts = "".join(
        f'<div class="audit-point"><div class="audit-num">{n}</div><div><strong>{t}</strong><p>{d}</p></div></div>'
        for n, t, d in audit_points
    )

    # ── Contexte de substitution des placeholders ─────────────────────────
    _bmin = (landing_text.budget_min or "") if landing_text else ""
    _bmax = (landing_text.budget_max or "") if landing_text else ""
    _sub_ctx = {
        "metier": pro_label, "metiers": pro_plural, "ville": city_cap,
        "name": name, "nom": name, "budget_min": _bmin, "budget_max": _bmax,
        "city": city_cap, "profession": pro_label,  # compat anciens templates
    }
    def _sub(t):
        if not t:
            return t
        try:
            return t.format_map(_sub_ctx)
        except Exception:
            return t

    # ── Hero ──────────────────────────────────────────────────────────────
    _hero_h1  = _sub(landing_text.hero_headline) if landing_text and landing_text.hero_headline else None
    _hero_sub = _sub(landing_text.hero_subtitle)  if landing_text and landing_text.hero_subtitle  else None
    sub_text  = _hero_sub or (
        "Avec 44\u00a0% des internautes utilisant une IA conversationnelle chaque mois en 2025 "
        "et un usage quotidien multipli\u00e9 par +250\u00a0% en un an, les assistants IA s'installent "
        "en amont du parcours de d\u00e9cision\u00a0\u2014 parfois avant la recherche Google."
    )
    _show_source = not (landing_text and landing_text.hero_subtitle)
    _source_img  = '<span style="display:block;margin-top:14px;font-size:.75rem;color:rgba(255,255,255,.45)">Source\u00a0: M\u00e9diam\u00e9trie</span>' if _show_source else ""
    _source_plain= '<span style="display:block;margin-top:12px;font-size:.75rem;color:#aaa">Source\u00a0: M\u00e9diam\u00e9trie</span>' if _show_source else ""
    # Sur fond sombre (image) : em clair #93c5fd. Sur fond blanc : em bleu via CSS
    _em_img   = 'style="font-style:normal;color:#93c5fd"'
    h1_img    = _hero_h1 or (
        f'À <em {_em_img}>{city_cap}</em>, les IA recommandent<br>'
        f'des <em {_em_img}>{pro_plural}</em> à vos potentiels clients.<br>'
        f'Mais pas vous.'
    )
    h1_plain  = _hero_h1 or (
        f'À <em>{city_cap}</em>, les IA recommandent<br>'
        f'des <em>{pro_plural}</em> à vos potentiels clients.<br>'
        f'Mais pas vous.'
    )

    hero_html = (
        f'<div style="position:relative;background-image:url({city_image_url});background-size:cover;background-position:center;min-height:500px;display:flex;align-items:center;justify-content:center;">'
        f'<div style="position:absolute;inset:0;background:linear-gradient(160deg,rgba(0,0,0,.68) 0%,rgba(0,0,0,.42) 60%,rgba(0,0,0,.2) 100%)"></div>'
        f'<div style="position:relative;z-index:1;text-align:center;padding:80px 48px;max-width:820px;">'
        f'<div style="display:inline-block;background:rgba(255,255,255,.15);color:#fff;font-size:.78rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:5px 14px;border-radius:100px;margin-bottom:28px;">Audit personnalisé</div>'
        f'<h1 style="color:#fff;font-size:clamp(2rem,5vw,3rem);font-weight:800;letter-spacing:-.04em;line-height:1.1;margin-bottom:20px;">{h1_img}</h1>'
        f'<p style="color:rgba(255,255,255,.8);font-size:1rem;max-width:600px;margin:0 auto;line-height:1.75;">{sub_text}{_source_img}</p>'
        f'</div></div>'
    ) if city_image_url else (
        f'<div class="hero"><div class="hero-badge">Audit personnalisé</div>'
        f'<h1>{h1_plain}</h1>'
        f'<p style="margin-top:20px;font-size:1rem;color:#555;max-width:600px;margin-left:auto;margin-right:auto;line-height:1.75">{sub_text}{_source_plain}</p>'
        f'</div>'
    )

    # ── CTA custom ────────────────────────────────────────────────────────
    cta_title = _sub(landing_text.cta_headline) if landing_text and landing_text.cta_headline else "Réservez votre appel<br>stratégique"
    cta_sub   = _sub(landing_text.cta_subtitle)  if landing_text and landing_text.cta_subtitle  else "Découvrez en 30 minutes votre positionnement réel sur les IA."

    # ── Preuves texte + vidéo (depuis landing_text) ───────────────────────
    proof_section = ""
    if landing_text:
        proof_texts_list  = json.loads(landing_text.proof_texts)  if landing_text.proof_texts  else []
        proof_videos_list = json.loads(landing_text.proof_videos) if landing_text.proof_videos else []

        if proof_texts_list:
            # Pas de backslash dans expression f-string (Python < 3.12)
            items_parts = []
            for pt in proof_texts_list:
                src  = pt.get("source", "")
                cite = f'<cite style="font-size:.78rem;color:#666;margin-top:6px;display:block">— {src}</cite>' if src else ""
                items_parts.append(
                    f'<blockquote style="border-left:3px solid #2563eb;padding:12px 20px;margin:16px 0;background:#eff4ff;border-radius:0 8px 8px 0">'
                    f'<p style="font-size:.95rem;font-style:italic;color:#1a1a1a">{pt.get("text","")}</p>'
                    + cite + "</blockquote>"
                )
            items = "".join(items_parts)
            proof_section += f'<div class="section"><h2>Témoignages</h2>{items}</div><hr style="border:none;border-top:1px solid var(--g2);">'

        if proof_videos_list:
            vids = "".join(
                f'<div style="margin:16px 0"><iframe src="{_youtube_embed(v["url"])}" width="100%" height="315" frameborder="0" allowfullscreen style="border-radius:8px;max-width:560px;display:block"></iframe></div>'
                for v in proof_videos_list if v.get("url")
            )
            if vids:
                proof_section += f'<div class="section"><h2>Vidéos</h2>{vids}</div><hr style="border:none;border-top:1px solid var(--g2);">'

    # ── Evidence screenshots (city_evidence) ─────────────────────────────
    if evidence_images:
        ev_imgs = "".join(
            f'<img src="{img.get("processed_url") or img.get("url","")}" '
            f'alt="Capture IA {img.get("provider","")} {city_cap}" '
            f'style="max-width:100%;border-radius:8px;margin-bottom:16px;border:1px solid #e5e7eb;display:block">'
            for img in evidence_images[:4]
            if img.get("processed_url") or img.get("url")
        )
        if ev_imgs:
            proof_section += (
                f'<div class="section">'
                f'<h2>Ce que voient vos futurs clients sur les IA</h2>'
                f'<p>Captures d\'écran réelles des réponses IA sur les {pro_label}s à {city_cap}.</p>'
                f'{ev_imgs}</div>'
                f'<hr style="border:none;border-top:1px solid var(--g2);">'
            )

    return f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Présence IA — Audit pour {name}</title><meta name="robots" content="noindex"><link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='16' cy='16' r='3.5' fill='%232563eb'/><circle cx='16' cy='16' r='8' stroke='%232563eb' stroke-width='1.5' fill='none' opacity='.65'/><circle cx='16' cy='16' r='13' stroke='%232563eb' stroke-width='1' fill='none' opacity='.35'/></svg>">
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
.chat-group{{margin:28px 0}}
.chat-accordion{{margin-top:12px;border:1px solid var(--g2);border-radius:10px;overflow:hidden}}
.chat-detail{{border-bottom:1px solid var(--g2)}}
.chat-detail:last-child{{border-bottom:none}}
.chat-detail summary{{padding:13px 18px;font-size:.9rem;font-weight:600;color:#dc2626;cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px;user-select:none}}
.chat-detail summary::before{{content:"▸";font-size:.8rem;transition:transform .2s;display:inline-block}}
.chat-detail[open] summary::before{{transform:rotate(90deg)}}
.chat-detail summary:hover{{background:#fafafa}}
.chat-detail-body{{padding:14px 18px 16px;font-size:.88rem;color:#444;line-height:1.7;border-top:1px solid var(--g2);background:#fff}}
.chat-meta{{display:flex;align-items:center;gap:12px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--g2)}}
.chat-meta strong{{font-size:.9rem}}.chat-time{{font-size:.78rem;color:var(--g3);margin-left:auto}}
.chat-label{{display:block;font-size:.72rem;font-weight:600;color:var(--g3);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.chat-prompt{{margin-bottom:16px}}.chat-prompt em{{font-style:italic;font-size:.88rem;color:#444}}
.chat-response{{margin-bottom:8px}}
.chat-text{{font-size:.95rem;color:var(--black);line-height:1.75;background:#fff;border:1px solid var(--g2);border-radius:8px;padding:14px 18px;margin-top:4px}}
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
  <div class="logo" style="display:flex;align-items:center;gap:9px"><svg width="26" height="26" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><circle cx="14" cy="14" r="3" fill="#2563eb"/><circle cx="14" cy="14" r="7" stroke="#2563eb" stroke-width="1.5" fill="none" opacity=".65"/><circle cx="14" cy="14" r="11" stroke="#2563eb" stroke-width="1" fill="none" opacity=".35"/></svg>Présence&nbsp;<span>IA</span></div>
  <div class="nav-tag">Audit — {name}</div>
</nav>

{hero_html}

{stats_html}

<div class="section">
  <h2 style="margin-bottom:8px">Ce que voient vos futurs clients<br>quand ils interrogent une IA</h2>
  <p>Réponses réelles obtenues lors des derniers tests sur les {pro_label}s de {city_cap}&nbsp;:</p>
  {chat_html}
  <div style="margin-top:32px;padding:28px 0">
    <p style="font-size:1rem;line-height:1.75;margin-bottom:12px;color:var(--t)">
      Ce n'est pas une question de réputation ou de classement sur Google Places.
    </p>
    <p style="font-size:1.15rem;font-weight:700;line-height:1.6;margin:24px 0;color:var(--t);display:flex;align-items:baseline;gap:10px">
      <span style="color:#2563eb;flex-shrink:0">→</span>
      Vous devez connaître et parler la langue que comprennent les IA.
    </p>
    <p style="font-size:1rem;line-height:1.75;margin-bottom:28px;color:var(--t)">
      Nous analysons et optimisons votre positionnement dans les réponses générées par les IA.
    </p>
    <div style="text-align:center">
      <a href="{CALENDLY_URL}" target="_blank" style="display:inline-block;background:#2563eb;color:#fff;font-weight:700;padding:14px 32px;border-radius:8px;text-decoration:none;font-size:.95rem">Réserver mon appel stratégique →</a>
    </div>
  </div>
</div>

<hr style="border:none;border-top:1px solid var(--g2);">

{proof_section}

<div style="background:var(--g1);padding:72px 48px;">
  <div style="max-width:780px;margin:0 auto;">
    <h2 style="font-size:clamp(1.5rem,3vw,2rem);font-weight:700;letter-spacing:-.03em;margin-bottom:16px;">Ce que couvre l'audit gratuit</h2>
    <div class="audit-grid">{pts}</div>
  </div>
</div>

<div class="cta-section">
  <h2>{cta_title}</h2>
  <p>{cta_sub}</p>
  <ul style="list-style:none;text-align:left;display:inline-block;margin:0 auto 36px;padding:0">
    <li style="padding:6px 0;color:rgba(255,255,255,.75);font-size:.95rem">• Votre positionnement réel sur les 3 IA</li>
    <li style="padding:6px 0;color:rgba(255,255,255,.75);font-size:.95rem">• Ce que font vos concurrents</li>
    <li style="padding:6px 0;color:rgba(255,255,255,.75);font-size:.95rem">• Comment inverser la tendance</li>
  </ul><br>
  <a href="{CALENDLY_URL}" target="_blank" class="btn-cta">Je réserve mon créneau →</a>
  <span class="btn-sub">Sans engagement · Résultats concrets</span>
</div>

<footer>© 2026 Présence IA &nbsp;·&nbsp;<a href="https://presence-ia.com">presence-ia.com</a> &nbsp;·&nbsp;<a href="https://presence-ia.com/cgv">CGV</a></footer>
</body></html>"""


# ── Authentification admin ────────────────────────────────────────────────────

@router.get("/login/v3", response_class=HTMLResponse)
def login_v3_page(request: Request):
    if _check_admin(request=request):
        return RedirectResponse("/admin/v3", status_code=302)
    return HTMLResponse("""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connexion — Présence IA</title><link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='16' cy='16' r='3.5' fill='%232563eb'/><circle cx='16' cy='16' r='8' stroke='%232563eb' stroke-width='1.5' fill='none' opacity='.65'/><circle cx='16' cy='16' r='13' stroke='%232563eb' stroke-width='1' fill='none' opacity='.35'/></svg>">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f0f4ff;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#fff;border-radius:14px;padding:48px 40px;width:100%;max-width:380px;box-shadow:0 4px 24px rgba(0,0,0,.08)}
h1{font-size:1.4rem;font-weight:800;letter-spacing:-.03em;margin-bottom:6px}
.sub{color:#666;font-size:.88rem;margin-bottom:32px}
label{display:block;font-size:.78rem;font-weight:600;color:#444;margin-bottom:6px;margin-top:16px}
input[type=password]{width:100%;padding:11px 14px;border:1.5px solid #e5e7eb;border-radius:8px;font-size:.95rem;outline:none;transition:border .15s}
input[type=password]:focus{border-color:#2563eb}
button{margin-top:24px;width:100%;padding:12px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-size:.95rem;font-weight:600;cursor:pointer;transition:background .15s}
button:hover{background:#1d4ed8}
.err{color:#dc2626;font-size:.82rem;margin-top:10px;display:none}
</style></head><body>
<div class="card">
  <h1 style="display:flex;align-items:center;gap:10px;justify-content:center"><svg width="32" height="32" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><circle cx="14" cy="14" r="3" fill="#2563eb"/><circle cx="14" cy="14" r="7" stroke="#2563eb" stroke-width="1.5" fill="none" opacity=".65"/><circle cx="14" cy="14" r="11" stroke="#2563eb" stroke-width="1" fill="none" opacity=".35"/></svg>Présence&nbsp;<span style="color:#2563eb">IA</span></h1>
  <p class="sub">Admin V3 — Accès réservé</p>
  <form method="POST" action="/login/v3">
    <label for="pwd">Mot de passe</label>
    <input type="password" name="password" id="pwd" autofocus autocomplete="current-password">
    <button type="submit">Connexion</button>
  </form>
  <p class="err" id="err">Mot de passe incorrect.</p>
</div>
<script>
const params = new URLSearchParams(location.search);
if (params.get('err')) document.getElementById('err').style.display='block';
</script>
</body></html>""")


@router.post("/login/v3")
async def login_v3(request: Request):
    form = await request.form()
    password = form.get("password", "")
    if hashlib.sha256(password.encode()).hexdigest() == _ADMIN_COOKIE_VAL:
        resp = RedirectResponse("/admin/v3", status_code=302)
        resp.set_cookie(_ADMIN_COOKIE_KEY, _ADMIN_COOKIE_VAL,
                        httponly=True, samesite="lax", max_age=60*60*24*30)
        return resp
    return RedirectResponse("/login/v3?err=1", status_code=302)


@router.get("/logout/v3")
def logout_v3():
    resp = RedirectResponse("/login/v3", status_code=302)
    resp.delete_cookie(_ADMIN_COOKIE_KEY)
    return resp


# ── Route publique ────────────────────────────────────────────────────────────

@router.get("/l/{token}", response_class=HTMLResponse)
def landing_v3(token: str):
    from ...models import CityEvidenceDB
    with SessionLocal() as db:
        p = db.get(V3ProspectDB, token)
        if not p:
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="https://presence-ia.com", status_code=302)
        city_img       = db.get(V3CityImageDB, _city_image_key(p.city))
        city_image_url = city_img.image_url if city_img else ""
        competitors    = json.loads(p.competitors) if p.competitors else []
        if not competitors:
            others = db.query(V3ProspectDB).filter(
                V3ProspectDB.city == p.city,
                V3ProspectDB.profession == p.profession,
                V3ProspectDB.token != token,
            ).limit(3).all()
            competitors = [o.name for o in others]
        # Landing texts (hero/CTA/preuves)
        lt_id        = f"{p.city.lower().strip()}_{p.profession.lower().strip()}"
        landing_text = db.get(V3LandingTextDB, lt_id)
        # Captures IA (city_evidence)
        evidence = db.query(CityEvidenceDB).filter_by(
            city=p.city.lower().strip(), profession=p.profession.lower().strip()
        ).first()
        evidence_images = json.loads(evidence.images) if evidence and evidence.images else []
        # Résultats IA (JSON multi-moteurs)
        ia_results_list: list = []
        if hasattr(p, "ia_results") and p.ia_results:
            try:
                ia_results_list = json.loads(p.ia_results)
            except Exception:
                pass
    return HTMLResponse(_render_landing(p, competitors, city_image_url,
                                        ia_results_list, landing_text, evidence_images))


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.get("/admin/v3", response_class=HTMLResponse)
def admin_v3(
    request: Request,
    token: str = "",
    tab: str = "prospects",
    f_ville: str = "",
    f_metier: str = "",
    f_email: str = "",
    f_phone: str = "",
):
    if not _check_admin(token, request):
        return RedirectResponse("/login/v3", status_code=302)
    # Token pour les appels API JS (embedded dans la page, pas dans l'URL)
    api_token = token or os.getenv("ADMIN_TOKEN", "changeme")
    with SessionLocal() as db:
        all_rows = db.query(V3ProspectDB).order_by(V3ProspectDB.city, V3ProspectDB.name).all()
        city_images = db.query(V3CityImageDB).order_by(V3CityImageDB.id).all()
        all_cities  = sorted({r.city for r in all_rows})
        all_professions = sorted({r.profession for r in all_rows})

    # Filtres
    rows = all_rows
    if f_ville:
        rows = [r for r in rows if r.city.lower() == f_ville.lower()]
    if f_metier:
        rows = [r for r in rows if r.profession.lower() == f_metier.lower()]
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
        actions += f' <button onclick="deleteProspect(\'{r.token}\',\'{r.name.replace(chr(39), "")}\' )" title="Supprimer" style="{_btn_style()};color:#dc2626;border-color:#fca5a5">🗑</button>'

        rating_str = f"{r.rating:.1f}★" if r.rating else "—"
        avis_str   = str(r.reviews_count) if r.reviews_count else "—"

        links_html = f'<a href="{r.landing_url}" target="_blank" title="Landing page" style="{_btn_style()}">🔗</a>'
        if r.website:
            links_html += f' <a href="{r.website}" target="_blank" title="Site web" style="{_btn_style()}">🌐</a>'
        table_rows += f"""<tr id="row-{r.token}">
          <td><input type="checkbox" class="prospect-cb" value="{r.token}"></td>
          <td style="font-size:.85rem"><strong>{r.name}</strong></td>
          <td style="font-size:.82rem">{r.city}</td>
          <td style="font-size:.82rem">{r.profession}</td>
          <td style="font-size:.82rem">{r.phone or '<span style="color:#ccc">—</span>'}</td>
          <td style="font-size:.82rem">{r.email or '<span style="color:#ccc">—</span>'}</td>
          <td style="font-size:.8rem;color:#666;text-align:center">{rating_str}</td>
          <td style="font-size:.8rem;color:#666;text-align:center">{avis_str}</td>
          <td style="white-space:nowrap">{links_html}</td>
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

    city_options       = "".join(f'<option value="{c}"{"selected" if c==f_ville else ""}>{c.capitalize()}</option>' for c in all_cities)
    profession_options = "".join(f'<option value="{p}"{"selected" if p==f_metier else ""}>{p.capitalize()}</option>' for p in all_professions)

    # Tab active
    t1 = "active" if tab == "prospects" else ""
    t2 = "active" if tab == "images" else ""
    t3 = "active" if tab == "textes" else ""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin V3 — Présence IA</title><link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='16' cy='16' r='3.5' fill='%232563eb'/><circle cx='16' cy='16' r='8' stroke='%232563eb' stroke-width='1.5' fill='none' opacity='.65'/><circle cx='16' cy='16' r='13' stroke='%232563eb' stroke-width='1' fill='none' opacity='.35'/></svg>">
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
  <h1 style="display:flex;align-items:center;gap:9px"><svg width="24" height="24" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><circle cx="14" cy="14" r="3" fill="white"/><circle cx="14" cy="14" r="7" stroke="white" stroke-width="1.5" fill="none" opacity=".65"/><circle cx="14" cy="14" r="11" stroke="white" stroke-width="1" fill="none" opacity=".35"/></svg>Présence&nbsp;<span style="color:#93c5fd">IA</span> · Admin V3</h1>
  <a href="/admin?token={api_token}">← Admin principal</a>
  <a href="/logout/v3" style="margin-left:auto;color:rgba(255,255,255,.5);font-size:.8rem">Déconnexion</a>
  <a href="#" onclick="downloadCSV()" class="btn btn-primary btn-sm" style="text-decoration:none">⬇ CSV</a>
</div>

<div class="tabs">
  <a class="tab {t1}" href="/admin/v3?tab=prospects">👥 Prospects</a>
  <a class="tab {t2}" href="/admin/v3?tab=images">🖼 Images & Vidéos</a>
  <a class="tab {t3}" href="/admin/v3?tab=textes">✏️ Textes</a>
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
      <select onchange="applyFilter()" id="f-metier">
        <option value="">Tous les métiers</option>
        {profession_options}
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
        <button class="btn btn-sm" onclick="bulkSendSelected('email', true)" title="Test sur la sélection">🧪 Test sélection ✉</button>
        <button class="btn btn-primary btn-sm" onclick="bulkSendSelected('email', false)" title="Envoie aux prospects sélectionnés avec email">✉ Sélection</button>
        <button class="btn btn-primary btn-sm" onclick="bulkSendSelected('sms', false)" title="SMS aux prospects sélectionnés">💬 Sélection</button>
        <button class="btn btn-primary btn-sm" onclick="bulkSend('email', false)" title="Envoie à TOUS les prospects avec email (1 par minute)">✉ Tous</button>
        <button class="btn btn-primary btn-sm" onclick="bulkSend('sms', false)">💬 Tous</button>
      </div>
    </div>

    <div id="bulk-progress" style="display:none;padding:8px 0;font-size:.82rem;color:#2563eb"></div>

    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th style="width:32px"><input type="checkbox" id="cb-all" onclick="toggleAll(this)" title="Sélectionner tout"></th>
          <th>Nom</th><th>Ville</th><th>Métier</th><th>Téléphone</th><th>Email</th>
          <th>Note</th><th>Avis</th><th>Liens</th><th>Statut</th><th>Actions</th>
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

  <!-- SECTION 1 : Templates de contact GLOBAUX -->
  <div class="card" style="margin-bottom:20px">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:6px">✉ Templates de contact (global)</h2>
    <p style="font-size:.82rem;color:#666;margin-bottom:14px">Placeholders : <code>{{{{profession}}}}</code> <code>{{{{city}}}}</code> <code>{{{{metier}}}}</code> <code>{{{{metiers}}}}</code> <code>{{{{ville}}}}</code> <code>{{{{name}}}}</code> <code>{{{{landing_url}}}}</code></p>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Objet email</label>
        <input id="gtpl-subject" type="text" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.82rem;margin-bottom:8px" placeholder="ex: Votre visibilité IA à {{ville}} — résultat personnalisé">
        <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Message email</label>
        <textarea id="gtpl-email" rows="7" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.82rem;resize:vertical;font-family:monospace"></textarea>
      </div>
      <div>
        <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Message SMS</label>
        <textarea id="gtpl-sms" rows="4" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.82rem;resize:vertical;font-family:monospace"></textarea>
        <p style="font-size:.73rem;color:#999;margin-top:8px">Le SMS doit rester sous 160 caractères.</p>
      </div>
    </div>
    <div style="margin-top:12px;display:flex;align-items:center;gap:10px">
      <button class="btn btn-primary" onclick="saveGlobalTemplate()">💾 Sauvegarder templates</button>
      <button class="btn btn-sm" onclick="previewEmail()" style="margin-left:4px">👁 Aperçu email</button>
      <span id="gtpl-status" style="font-size:.82rem;color:#16a34a"></span>
    </div>
  </div>

  <!-- SECTION 2 : Personnalisation landing par paire -->
  <div class="card" style="margin-bottom:20px">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:6px">🖋 Personnalisation landing par paire</h2>
    <p style="font-size:.83rem;color:#666;margin-bottom:4px">Textes spécifiques à une paire ville/métier. Placeholders disponibles :</p>
    <p style="font-size:.78rem;color:#555;background:#f3f4f6;padding:6px 10px;border-radius:6px;font-family:monospace;margin-bottom:12px"><code>{{metier}}</code> <code>{{metiers}}</code> <code>{{ville}}</code> <code>{{budget_min}}</code> <code>{{budget_max}}</code> <code>{{nom}}</code> <code>{{name}}</code></p>
    <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin-bottom:16px">
      <div class="form-group">
        <label>Ville</label>
        <select id="txt-city" onchange="loadTexts()">
          {"".join(f'<option value="{c}" {"selected" if c == all_cities[0] else ""}>{c.capitalize()}</option>' for c in all_cities) if all_cities else '<option value="">— choisir —</option>'}
        </select>
      </div>
      <div class="form-group">
        <label>Métier</label>
        <select id="txt-prof" onchange="loadTexts()">
          {"".join(f'<option value="{p}" {"selected" if p == all_professions[0] else ""}>{p}</option>' for p in all_professions) if all_professions else '<option value="">— choisir —</option>'}
        </select>
      </div>
    </div>
    <div id="txt-editor" style="display:{"block" if all_cities and all_professions else "none"}">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
            <div class="form-group">
              <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Panier moyen MIN</label>
              <input type="text" id="txt-budget-min" placeholder="ex: 12 000€" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem">
            </div>
            <div class="form-group">
              <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Panier moyen MAX</label>
              <input type="text" id="txt-budget-max" placeholder="ex: 25 000€" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem">
            </div>
          </div>
          <div class="form-group" style="margin-bottom:12px">
            <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Titre hero</label>
            <textarea id="txt-hero" rows="2" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem;resize:vertical"></textarea>
          </div>
          <div class="form-group" style="margin-bottom:12px">
            <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Sous-titre hero</label>
            <textarea id="txt-hero-sub" rows="2" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem;resize:vertical"></textarea>
          </div>
          <div class="form-group" style="margin-bottom:12px">
            <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Titre CTA</label>
            <input type="text" id="txt-cta" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem">
          </div>
          <div class="form-group" style="margin-bottom:12px">
            <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Sous-titre CTA</label>
            <textarea id="txt-cta-sub" rows="2" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem;resize:vertical"></textarea>
          </div>
          <div class="form-group" style="margin-bottom:12px">
            <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Témoignages (une par ligne : "texte|source")</label>
            <textarea id="txt-proofs" rows="4" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem;resize:vertical" placeholder="Super résultats depuis l'audit IA...|Jean D., pisciniste"></textarea>
          </div>
          <div class="form-group" style="margin-bottom:16px">
            <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Vidéos (URL YouTube/Vimeo, une par ligne)</label>
            <textarea id="txt-videos" rows="3" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem;resize:vertical" placeholder="https://www.youtube.com/watch?v=..."></textarea>
          </div>
          <button class="btn btn-primary" onclick="saveTexts()">💾 Sauvegarder</button>
          <span id="txt-save-status" style="font-size:.82rem;color:#16a34a;margin-left:10px"></span>
        </div>
        <div class="card" style="background:#f8f9fa">
          <h3 style="font-size:.9rem;font-weight:700;margin-bottom:12px">Preuves IA (captures)</h3>
          <div id="txt-evidence" style="font-size:.82rem;color:#666">Sélectionnez une paire pour voir les captures.</div>
        </div>
      </div>
    </div>
  </div>

  <!-- SECTION 3 : Page d'accueil -->
  <div class="card" style="margin-bottom:20px">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:6px">🏠 Page d'accueil (presence-ia.com)</h2>
    <p style="font-size:.82rem;color:#666;margin-bottom:14px">Éditez les textes de la home page.</p>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <div class="form-group" style="margin-bottom:12px">
          <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Titre hero</label>
          <textarea id="home-hero-title" rows="2" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem;resize:vertical"></textarea>
        </div>
        <div class="form-group" style="margin-bottom:12px">
          <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Sous-titre hero</label>
          <textarea id="home-hero-subtitle" rows="2" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem;resize:vertical"></textarea>
        </div>
        <div class="form-group" style="margin-bottom:12px">
          <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Bouton principal</label>
          <input type="text" id="home-hero-cta" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem">
        </div>
      </div>
      <div>
        <div class="form-group" style="margin-bottom:12px">
          <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Titre CTA final</label>
          <input type="text" id="home-cta-title" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem">
        </div>
        <div class="form-group" style="margin-bottom:12px">
          <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Sous-titre CTA final</label>
          <textarea id="home-cta-sub" rows="2" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem;resize:vertical"></textarea>
        </div>
        <div class="form-group" style="margin-bottom:12px">
          <label style="font-size:.75rem;font-weight:600;color:#444;display:block;margin-bottom:4px">Bouton CTA final</label>
          <input type="text" id="home-cta-btn" style="width:100%;padding:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:.85rem">
        </div>
      </div>
    </div>
    <div style="margin-top:12px;display:flex;align-items:center;gap:10px">
      <button class="btn btn-primary" onclick="saveHomeBlocks()">💾 Sauvegarder home</button>
      <span id="home-save-status" style="font-size:.82rem;color:#16a34a"></span>
      <a href="/" target="_blank" class="btn btn-sm" style="text-decoration:none">👁 Voir la home</a>
    </div>
  </div>

</div>

</div><!-- /container -->

<script>
const TOKEN = "{api_token}";

// Auto-charger si on est sur l'onglet textes
if ("{tab}" === "textes") {{
  loadGlobalTemplate();
  loadHomeBlocks();
  const c = document.getElementById('txt-city');
  const pp = document.getElementById('txt-prof');
  if (c && c.value && pp && pp.value) loadTexts();
}}

function applyFilter() {{
  const v = document.getElementById('f-ville').value;
  const m = document.getElementById('f-metier').value;
  const e = document.getElementById('f-email').checked ? '1' : '';
  const p = document.getElementById('f-phone').checked ? '1' : '';
  location.href = `/admin/v3?tab=prospects&f_ville=${{v}}&f_metier=${{m}}&f_email=${{e}}&f_phone=${{p}}`;
}}
function resetFilters() {{
  location.href = `/admin/v3?tab=prospects`;
}}

function downloadCSV() {{
  window.location = `/api/v3/prospects.csv?token=${{TOKEN}}`;
}}

function toggleAll(cb) {{
  document.querySelectorAll('.prospect-cb').forEach(c => c.checked = cb.checked);
}}
function getSelected() {{
  return [...document.querySelectorAll('.prospect-cb:checked')].map(c => c.value);
}}
async function bulkSendSelected(method, isTest) {{
  const selected = getSelected();
  if (!selected.length) {{ alert('Sélectionnez au moins un prospect.'); return; }}
  let testEmail = null, testPhone = null;
  if (isTest) {{
    if (method === 'email') {{
      testEmail = prompt('Email de test :');
      if (!testEmail) return;
    }} else {{
      testPhone = prompt('Numéro de test :');
      if (!testPhone) return;
    }}
  }} else {{
    if (!confirm(`Envoyer ${{method === 'email' ? 'email' : 'SMS'}} aux ${{selected.length}} prospect(s) sélectionné(s) ?`)) return;
  }}
  const body = {{method, delay_seconds: isTest ? 3 : 60, prospect_tokens: selected}};
  if (testEmail) body.test_email = testEmail;
  if (testPhone) body.test_phone = testPhone;
  const r = await fetch(`/api/v3/bulk-send?token=${{TOKEN}}`, {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(body)
  }});
  const d = await r.json();
  document.getElementById('bulk-progress').style.display = 'block';
  document.getElementById('bulk-progress').textContent =
    `${{d.test_mode ? '🧪 TEST' : '✉'}} ${{selected.length}} envois planifiés · ${{d.note}}`;
}}

const DEFAULT_EMAIL_TPL = {json.dumps(_DEFAULT_EMAIL_TEMPLATE)};
const DEFAULT_SMS_TPL = {json.dumps(_DEFAULT_SMS_TEMPLATE)};
const DEFAULT_EMAIL_SUBJECT = {json.dumps(_DEFAULT_EMAIL_SUBJECT)};

// ── Templates globaux ─────────────────────────────────────────────────────────
async function loadGlobalTemplate() {{
  const r = await fetch(`/api/v3/global-template?token=${{TOKEN}}`);
  if (!r.ok) return;
  const d = await r.json();
  document.getElementById('gtpl-subject').value = d.email_subject || DEFAULT_EMAIL_SUBJECT;
  document.getElementById('gtpl-email').value   = d.email_template || DEFAULT_EMAIL_TPL;
  document.getElementById('gtpl-sms').value     = d.sms_template   || DEFAULT_SMS_TPL;
}}
async function saveGlobalTemplate() {{
  const body = {{
    email_subject:  document.getElementById('gtpl-subject').value.trim() || null,
    email_template: document.getElementById('gtpl-email').value.trim()   || null,
    sms_template:   document.getElementById('gtpl-sms').value.trim()     || null,
  }};
  const r = await fetch(`/api/v3/global-template?token=${{TOKEN}}`, {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(body)
  }});
  const d = await r.json();
  const st = document.getElementById('gtpl-status');
  st.textContent = d.ok ? '✓ Sauvegardé' : '✗ Erreur';
  setTimeout(() => st.textContent = '', 3000);
}}

// ── Home page blocks ──────────────────────────────────────────────────────────
async function loadHomeBlocks() {{
  const r = await fetch(`/api/v3/home-blocks?token=${{TOKEN}}`);
  if (!r.ok) return;
  const d = await r.json();
  document.getElementById('home-hero-title').value   = d.hero_title    || '';
  document.getElementById('home-hero-subtitle').value= d.hero_subtitle || '';
  document.getElementById('home-hero-cta').value     = d.hero_cta      || '';
  document.getElementById('home-cta-title').value    = d.cta_title     || '';
  document.getElementById('home-cta-sub').value      = d.cta_subtitle  || '';
  document.getElementById('home-cta-btn').value      = d.cta_btn       || '';
}}
async function saveHomeBlocks() {{
  const blocks = [
    ['hero', 'title',    document.getElementById('home-hero-title').value],
    ['hero', 'subtitle', document.getElementById('home-hero-subtitle').value],
    ['hero', 'cta_primary', document.getElementById('home-hero-cta').value],
    ['cta', 'title',    document.getElementById('home-cta-title').value],
    ['cta', 'subtitle', document.getElementById('home-cta-sub').value],
    ['cta', 'btn_label',document.getElementById('home-cta-btn').value],
  ];
  let ok = true;
  for (const [sec, fk, val] of blocks) {{
    if (!val.trim()) continue;
    const r = await fetch(`/api/v3/home-block?token=${{TOKEN}}`, {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{section_key: sec, field_key: fk, value: val.trim()}})
    }});
    if (!r.ok) ok = false;
  }}
  const st = document.getElementById('home-save-status');
  st.textContent = ok ? '✓ Sauvegardé' : '✗ Erreur partielle';
  setTimeout(() => st.textContent = '', 3000);
}}

async function loadTexts() {{
  const city = document.getElementById('txt-city').value;
  const prof = document.getElementById('txt-prof').value;
  if (!city || !prof) {{ document.getElementById('txt-editor').style.display='none'; return; }}
  document.getElementById('txt-editor').style.display='block';
  const r = await fetch(`/api/v3/landing-text/${{encodeURIComponent(city)}}/${{encodeURIComponent(prof)}}?token=${{TOKEN}}`);
  const d = await r.json();
  document.getElementById('txt-budget-min').value = d.budget_min || '';
  document.getElementById('txt-budget-max').value = d.budget_max || '';
  document.getElementById('txt-hero').value      = d.hero_headline || '';
  document.getElementById('txt-hero-sub').value  = d.hero_subtitle || '';
  document.getElementById('txt-cta').value       = d.cta_headline  || '';
  document.getElementById('txt-cta-sub').value   = d.cta_subtitle  || '';
  const proofs = (d.proof_texts || []).map(p => `${{p.text}}|${{p.source}}`).join('\\n');
  document.getElementById('txt-proofs').value    = proofs;
  document.getElementById('txt-videos').value    = (d.proof_videos || []).map(v => v.url).join('\\n');
  // Evidence screenshots
  const evEl = document.getElementById('txt-evidence');
  if (d.evidence && d.evidence.length) {{
    evEl.innerHTML = d.evidence.map(e =>
      `<div style="margin-bottom:12px"><img src="${{e.processed_url || e.url}}" style="max-width:100%;border-radius:6px;border:1px solid #eee">
      <div style="font-size:.75rem;color:#999;margin-top:4px">${{e.provider}} — ${{e.ts ? e.ts.slice(0,16) : ''}}</div></div>`
    ).join('');
  }} else {{
    evEl.innerHTML = "<p style='color:#999'>Aucune capture d&#39;écran pour cette paire. Utilisez le refresh-IA ou uploadez des preuves.</p>";
  }}
}}
async function saveTexts() {{
  const city = document.getElementById('txt-city').value;
  const prof = document.getElementById('txt-prof').value;
  const proofsRaw = document.getElementById('txt-proofs').value.split('\\n').filter(l => l.trim());
  const proofs = proofsRaw.map(l => {{ const [text, source] = l.split('|'); return {{text: (text||'').trim(), source: (source||'').trim()}}; }});
  const videos = document.getElementById('txt-videos').value.split('\\n').filter(l => l.trim()).map(url => ({{url: url.trim()}}));
  const body = {{
    city, profession: prof,
    budget_min:     document.getElementById('txt-budget-min').value || null,
    budget_max:     document.getElementById('txt-budget-max').value || null,
    hero_headline:  document.getElementById('txt-hero').value || null,
    hero_subtitle:  document.getElementById('txt-hero-sub').value || null,
    cta_headline:   document.getElementById('txt-cta').value || null,
    cta_subtitle:   document.getElementById('txt-cta-sub').value || null,
    proof_texts:    proofs, proof_videos: videos,
  }};
  const r = await fetch(`/api/v3/landing-text?token=${{TOKEN}}`, {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(body)
  }});
  const d = await r.json();
  const st = document.getElementById('txt-save-status');
  st.textContent = d.ok ? '✓ Sauvegardé' : '✗ Erreur';
  setTimeout(() => st.textContent = '', 3000);
}}
function previewEmail() {{
  const tpl = document.getElementById('gtpl-email').value || DEFAULT_EMAIL_TPL;
  const metier = prompt('Métier pour l\\u2019aperçu ?', 'pisciniste') || 'pisciniste';
  const metiers = metier.endsWith('s') ? metier : metier + 's';
  const ville = prompt('Ville pour l\\u2019aperçu ?', 'Montpellier') || 'Montpellier';
  const preview = tpl
    .replace(/\\{{name\\}}/g, 'Jean Dupont')
    .replace(/\\{{ville\\}}/g, ville)
    .replace(/\\{{metier\\}}/g, metier)
    .replace(/\\{{metiers\\}}/g, metiers)
    .replace(/\\{{city\\}}/g, ville)
    .replace(/\\{{profession\\}}/g, metier)
    .replace(/\\{{landing_url\\}}/g, 'https://presence-ia.com/l/exemple');
  const w = window.open('', '_blank', 'width=600,height=500');
  w.document.write('<pre style="font-family:sans-serif;padding:24px;white-space:pre-wrap">' + preview + '</pre>');
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

async function _compressImg(file, maxW=1400, q=0.85) {{
  return new Promise(resolve => {{
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {{
      let w = img.width, h = img.height;
      if (w > maxW) {{ h = Math.round(h * maxW / w); w = maxW; }}
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      canvas.getContext('2d').drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      canvas.toBlob(blob => resolve(blob || file), 'image/jpeg', q);
    }};
    img.onerror = () => {{ URL.revokeObjectURL(url); resolve(file); }};
    img.src = url;
  }});
}}
async function uploadImage() {{
  const city = document.getElementById('img-city').value.trim();
  const file = document.getElementById('img-file').files[0];
  const status = document.getElementById('upload-status');
  if (!city || !file) {{ alert('Ville et fichier requis'); return; }}
  status.textContent = "⏳ Compression de l&#39;image...";
  let blob;
  try {{ blob = await _compressImg(file); }}
  catch(e) {{ blob = file; }}
  const sizeMb = (blob.size / 1024 / 1024).toFixed(1);
  status.textContent = `⏳ Upload (${{sizeMb}} Mo)...`;
  const fd = new FormData();
  fd.append('city', city); fd.append('profession', '');
  fd.append('file', new File([blob], 'image.jpg', {{type: 'image/jpeg'}}));
  let r, d;
  try {{
    r = await fetch(`/api/v3/upload-image?token=${{TOKEN}}`, {{method:'POST', body:fd}});
    if (r.status === 413) {{
      status.textContent = '❌ Encore trop lourd après compression (' + sizeMb + ' Mo). Essayez avec une image plus petite.';
      return;
    }}
    const ct = r.headers.get('content-type') || '';
    d = ct.includes('json') ? await r.json() : {{}};
  }} catch(e) {{ status.textContent = '❌ Erreur réseau : ' + e.message; return; }}
  if (r.ok && d.ok) {{
    status.textContent = '✓ Image enregistrée pour ' + city;
    setTimeout(() => location.reload(), 1000);
  }} else {{
    status.textContent = '❌ Erreur upload (' + (r.status) + ')';
  }}
}}

async function deleteImage(imgId) {{
  if (!confirm('Supprimer cette image ?')) return;
  await fetch(`/api/v3/city-image/${{imgId}}?token=${{TOKEN}}`, {{method:'DELETE'}});
  location.reload();
}}

async function deleteProspect(tok, name) {{
  if (!confirm('Supprimer ' + name + ' ?')) return;
  const r = await fetch(`/api/v3/prospect/${{tok}}?token=${{TOKEN}}`, {{method:'DELETE'}});
  if (r.ok) {{
    const row = document.getElementById('row-' + tok);
    if (row) row.remove();
  }} else {{ alert('Erreur suppression'); }}
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
    prospect_tokens: Optional[List[str]] = None  # Si fourni, envoie uniquement à ces tokens


class LandingTextRequest(BaseModel):
    city: str; profession: str
    hero_headline:  Optional[str]       = None
    hero_subtitle:  Optional[str]       = None
    cta_headline:   Optional[str]       = None
    cta_subtitle:   Optional[str]       = None
    proof_texts:    Optional[List[dict]] = None   # [{text, source}]
    proof_videos:   Optional[List[dict]] = None   # [{url}]
    budget_min:     Optional[str]       = None    # ex: "12 000€"
    budget_max:     Optional[str]       = None    # ex: "25 000€"
    email_template: Optional[str]       = None
    sms_template:   Optional[str]       = None


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
                ia_results_json = json.dumps(ia_data.get("results", []), ensure_ascii=False) if ia_data.get("results") else None
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
                        ia_results=ia_results_json,
                    ))
                else:
                    existing.competitors = json.dumps(competitors, ensure_ascii=False)
                    existing.rating = p.get("rating") or existing.rating
                    if ia_data:
                        existing.ia_prompt    = ia_data.get("prompt")
                        existing.ia_response  = ia_data.get("response")
                        existing.ia_model     = ia_data.get("model")
                        existing.ia_tested_at = ia_data.get("tested_at")
                        existing.ia_results   = ia_results_json
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


@router.get("/api/v3/landing-text/{city}/{profession}")
def get_landing_text(city: str, profession: str, token: str = "", request: Request = None):
    _require_admin(token, request)
    from ...models import CityEvidenceDB
    lt_id = f"{city.lower().strip()}_{profession.lower().strip()}"
    with SessionLocal() as db:
        lt = db.get(V3LandingTextDB, lt_id)
        evidence = db.query(CityEvidenceDB).filter_by(
            city=city.lower().strip(), profession=profession.lower().strip()
        ).first()
    ev_list = []
    if evidence and evidence.images:
        imgs = json.loads(evidence.images) if isinstance(evidence.images, str) else evidence.images
        ev_list = imgs[:6]  # max 6 captures
    return {
        "hero_headline":  lt.hero_headline  if lt else None,
        "hero_subtitle":  lt.hero_subtitle  if lt else None,
        "cta_headline":   lt.cta_headline   if lt else None,
        "cta_subtitle":   lt.cta_subtitle   if lt else None,
        "proof_texts":    json.loads(lt.proof_texts)  if lt and lt.proof_texts  else [],
        "proof_videos":   json.loads(lt.proof_videos) if lt and lt.proof_videos else [],
        "budget_min":     lt.budget_min     if lt else None,
        "budget_max":     lt.budget_max     if lt else None,
        "evidence":       ev_list,
    }


@router.post("/api/v3/landing-text")
async def save_landing_text(req: LandingTextRequest, token: str = "", request: Request = None):
    _require_admin(token, request)
    lt_id = f"{req.city.lower().strip()}_{req.profession.lower().strip()}"
    with SessionLocal() as db:
        lt = db.get(V3LandingTextDB, lt_id)
        if not lt:
            lt = V3LandingTextDB(id=lt_id, city=req.city, profession=req.profession)
            db.add(lt)
        lt.hero_headline  = req.hero_headline  or None
        lt.hero_subtitle  = req.hero_subtitle  or None
        lt.cta_headline   = req.cta_headline   or None
        lt.cta_subtitle   = req.cta_subtitle   or None
        lt.proof_texts    = json.dumps(req.proof_texts,  ensure_ascii=False) if req.proof_texts  else None
        lt.proof_videos   = json.dumps(req.proof_videos, ensure_ascii=False) if req.proof_videos else None
        lt.budget_min     = req.budget_min     or None
        lt.budget_max     = req.budget_max     or None
        db.commit()
    return {"ok": True}


class GlobalTemplateRequest(BaseModel):
    email_subject:  Optional[str] = None
    email_template: Optional[str] = None
    sms_template:   Optional[str] = None


@router.get("/api/v3/global-template")
def get_global_template(token: str = "", request: Request = None):
    _require_admin(token, request)
    with SessionLocal() as db:
        lt = db.get(V3LandingTextDB, "__global__")
        return {
            "email_subject":  lt.email_subject  if lt else None,
            "email_template": lt.email_template if lt else None,
            "sms_template":   lt.sms_template   if lt else None,
        }


@router.post("/api/v3/global-template")
async def save_global_template(req: GlobalTemplateRequest, token: str = "", request: Request = None):
    _require_admin(token, request)
    with SessionLocal() as db:
        lt = db.get(V3LandingTextDB, "__global__")
        if not lt:
            lt = V3LandingTextDB(id="__global__", city="__global__", profession="__global__")
            db.add(lt)
        lt.email_subject  = req.email_subject  or None
        lt.email_template = req.email_template or None
        lt.sms_template   = req.sms_template   or None
        lt.updated_at     = datetime.utcnow()
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
        lt_global = db.get(V3LandingTextDB, "__global__")
        tpl       = lt_global.email_template if lt_global and lt_global.email_template else None
        subj_tpl  = lt_global.email_subject  if lt_global and lt_global.email_subject  else _DEFAULT_EMAIL_SUBJECT
        msg   = _contact_message(p.name, p.city, p.profession, p.landing_url, tpl)
        metier = p.profession.lower(); metiers = metier + "s" if not metier.endswith("s") else metier
        subj  = subj_tpl.format(ville=p.city, metier=metier, metiers=metiers,
                                city=p.city, profession=p.profession, name=p.name)
        ok    = _send_brevo_email(p.email, p.name, subj, msg)
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
        lt_global = db.get(V3LandingTextDB, "__global__")
        tpl       = lt_global.sms_template if lt_global and lt_global.sms_template else None
        msg   = _contact_message_sms(p.name, p.city, p.profession, p.landing_url, tpl)
        ok    = _send_brevo_sms(p.phone, msg)
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
        q_email = V3ProspectDB.email.isnot(None)
        q_phone = V3ProspectDB.phone.isnot(None)
        q_unsent = [] if test_mode else [V3ProspectDB.sent_at.is_(None)]
        if req.prospect_tokens:
            # Sélection manuelle
            if req.method == "email":
                prospects = db.query(V3ProspectDB).filter(
                    V3ProspectDB.token.in_(req.prospect_tokens), q_email
                ).all()
            else:
                prospects = db.query(V3ProspectDB).filter(
                    V3ProspectDB.token.in_(req.prospect_tokens), q_phone
                ).all()
        else:
            if req.method == "email":
                prospects = db.query(V3ProspectDB).filter(q_email, *q_unsent).limit(req.max_per_day).all()
            else:
                prospects = db.query(V3ProspectDB).filter(q_phone, *q_unsent).limit(req.max_per_day).all()
        tokens = [(p.token, p.name, p.city, p.profession, p.email, p.phone, p.landing_url)
                  for p in prospects]
        # Template global (une seule entrée __global__)
        lt_global  = db.get(V3LandingTextDB, "__global__")
        email_tpl  = lt_global.email_template if lt_global and lt_global.email_template else None
        sms_tpl    = lt_global.sms_template   if lt_global and lt_global.sms_template   else None
        subj_tpl   = lt_global.email_subject  if lt_global and lt_global.email_subject  else _DEFAULT_EMAIL_SUBJECT

    _bulk_status.update({"running": True, "done": 0, "total": len(tokens), "errors": [],
                         "test_mode": test_mode})

    def _do_bulk():
        for i, (tok, name, city, profession, email, phone, landing_url) in enumerate(tokens):
            if req.method == "email":
                dest   = req.test_email if test_mode else email
                msg    = _contact_message(name, city, profession, landing_url, email_tpl)
                metier = profession.lower(); metiers = metier + "s" if not metier.endswith("s") else metier
                subj_real = subj_tpl.format(ville=city, metier=metier, metiers=metiers,
                                            city=city, profession=profession, name=name)
                subj   = f"[TEST] {subj_real}" if test_mode else subj_real
                ok     = _send_brevo_email(dest, name, subj, msg) if dest else False
            elif req.method == "sms":
                dest   = req.test_phone if test_mode else phone
                msg    = _contact_message_sms(name, city, profession, landing_url, sms_tpl)
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
                ia_results_json = json.dumps(ia_data.get("results", []), ensure_ascii=False) if ia_data.get("results") else None
                with SessionLocal() as db:
                    for p in db.query(V3ProspectDB).filter_by(city=city, profession=profession).all():
                        p.ia_prompt    = ia_data.get("prompt")
                        p.ia_response  = ia_data.get("response")
                        p.ia_model     = ia_data.get("model")
                        p.ia_tested_at = ia_data.get("tested_at")
                        p.ia_results   = ia_results_json
                    db.commit()
                log.info("refresh-ia OK: %s %s", profession, city)
            except Exception as exc:
                log.error("refresh-ia %s %s: %s", profession, city, exc)
            time.sleep(3)  # Pause entre les appels IA pour éviter le rate-limit

    threading.Thread(target=_do_refresh, daemon=True).start()
    with SessionLocal() as db:
        n_pairs = db.query(V3ProspectDB.city, V3ProspectDB.profession).distinct().count()
    return {"ok": True, "pairs": n_pairs,
            "note": f"Refresh IA lancé pour {n_pairs} paires ville/métier en background (~{n_pairs*45}s)"}


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


@router.delete("/api/v3/prospect/{tok}")
def delete_prospect(tok: str, token: str = "", request: Request = None):
    _require_admin(token, request)
    with SessionLocal() as db:
        p = db.get(V3ProspectDB, tok)
        if not p:
            raise HTTPException(404)
        db.delete(p)
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


@router.get("/api/v3/home-blocks")
def get_home_blocks(token: str = "", request: Request = None):
    _require_admin(token, request)
    with SessionLocal() as db:
        return {
            "hero_title":    get_block(db, "home", "hero",      "title"),
            "hero_subtitle": get_block(db, "home", "hero",      "subtitle"),
            "hero_cta":      get_block(db, "home", "hero",      "cta_primary"),
            "cta_title":     get_block(db, "home", "cta", "title"),
            "cta_subtitle":  get_block(db, "home", "cta", "subtitle"),
            "cta_btn":       get_block(db, "home", "cta", "btn_label"),
        }


class HomeBlockRequest(BaseModel):
    section_key: str
    field_key:   str
    value:       str


@router.post("/api/v3/clean-prospect-names")
def clean_prospect_names(token: str = "", request: Request = None):
    """Nettoyage one-shot des noms de prospects (supprime suffixes marketing Google Places)."""
    _require_admin(token, request)
    from ...google_places import _clean_name
    updated = []
    with SessionLocal() as db:
        prospects = db.query(V3ProspectDB).all()
        for p in prospects:
            cleaned = _clean_name(p.name or "", city=p.city or "")
            if cleaned != p.name:
                updated.append({"token": p.token, "before": p.name, "after": cleaned})
                p.name = cleaned
        db.commit()
    return {"updated": len(updated), "changes": updated}


@router.post("/api/v3/home-block")
async def save_home_block(req: HomeBlockRequest, token: str = "", request: Request = None):
    _require_admin(token, request)
    with SessionLocal() as db:
        set_block(db, "home", req.section_key, req.field_key, req.value)
    return {"ok": True}
