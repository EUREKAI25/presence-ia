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
from ._nav import admin_nav
from ...database import SessionLocal, get_block, set_block
from . import v3_mkt_bridge as _mkt

log = logging.getLogger(__name__)
router = APIRouter()

CALENDLY_URL  = "https://calendly.com/contact-presence-ia/20min"
BASE_URL      = os.getenv("BASE_URL", "https://presence-ia.com")

# Préfectures par département — fallback image si pas d'image spécifique à la ville
DEPT_PREFECTURE: dict[str, str] = {
    "01":"Bourg-en-Bresse","02":"Laon","03":"Moulins","04":"Digne-les-Bains","05":"Gap",
    "06":"Nice","07":"Privas","08":"Charleville-Mézières","09":"Foix","10":"Troyes",
    "11":"Carcassonne","12":"Rodez","13":"Marseille","14":"Caen","15":"Aurillac",
    "16":"Angoulême","17":"La Rochelle","18":"Bourges","19":"Tulle",
    "2A":"Ajaccio","2B":"Bastia",
    "21":"Dijon","22":"Saint-Brieuc","23":"Guéret","24":"Périgueux","25":"Besançon",
    "26":"Valence","27":"Évreux","28":"Chartres","29":"Quimper","30":"Nîmes",
    "31":"Toulouse","32":"Auch","33":"Bordeaux","34":"Montpellier","35":"Rennes",
    "36":"Châteauroux","37":"Tours","38":"Grenoble","39":"Lons-le-Saunier",
    "40":"Mont-de-Marsan","41":"Blois","42":"Saint-Étienne","43":"Le Puy-en-Velay",
    "44":"Nantes","45":"Orléans","46":"Cahors","47":"Agen","48":"Mende",
    "49":"Angers","50":"Saint-Lô","51":"Châlons-en-Champagne","52":"Chaumont",
    "53":"Laval","54":"Nancy","55":"Bar-le-Duc","56":"Vannes","57":"Metz",
    "58":"Nevers","59":"Lille","60":"Beauvais","61":"Alençon","62":"Arras",
    "63":"Clermont-Ferrand","64":"Pau","65":"Tarbes","66":"Perpignan",
    "67":"Strasbourg","68":"Colmar","69":"Lyon","70":"Vesoul","71":"Mâcon",
    "72":"Le Mans","73":"Chambéry","74":"Annecy","75":"Paris","76":"Rouen",
    "77":"Melun","78":"Versailles","79":"Niort","80":"Amiens","81":"Albi",
    "82":"Montauban","83":"Toulon","84":"Avignon","85":"La Roche-sur-Yon",
    "86":"Poitiers","87":"Limoges","88":"Épinal","89":"Auxerre","90":"Belfort",
    "91":"Évry-Courcouronnes","92":"Nanterre","93":"Bobigny","94":"Créteil","95":"Cergy",
    "971":"Basse-Terre","972":"Fort-de-France","973":"Cayenne","974":"Saint-Denis","976":"Mamoudzou",
}
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
    "Lorsque vos éventuels clients demandent à leur IA préférée quel {metier} choisir à {ville}, "
    "plusieurs entreprises apparaissent.\n\n"
    "Pas la vôtre.\n\n"
    "Nous avons analysé votre visibilité réelle dans les réponses des IA, "
    "ainsi que celle de vos concurrents.\n\n"
    "Le résultat est assez parlant...\n\n"
    "👉 Voir l'analyse :\n"
    "{landing_url}"
)

_DEFAULT_SMS_TEMPLATE = (
    "{metiers} \u00e0 {ville}, ChatGPT cite vos concurrents, pas vous. "
    "Voir : {landing_url} STOP"
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
    """Scrape homepage + page contact pour email, téléphone, URL contact, CMS."""
    result = {"email": None, "phone": None, "contact_url": None, "cms": None}
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

        # Détecter le CMS depuis le HTML + headers déjà téléchargés (pas de requête supplémentaire)
        try:
            from ..cms_detector import _COMPILED as _CMS_COMPILED
            resp_headers_str = " ".join(f"{k}: {v}" for k, v in resp.headers.items())
            haystack = text[:60_000] + " " + resp_headers_str
            for _cms_name, _cms_patterns in _CMS_COMPILED:
                if any(p.search(haystack) for p in _cms_patterns):
                    result["cms"] = _cms_name
                    break
        except Exception:
            pass

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

def _body_to_html(plain: str, landing_url: str = "", delivery_id: str = "") -> str:
    """Convertit le corps texte en HTML avec tracking pixel et lien cliquable."""
    import html as _html
    tracked_url = landing_url
    if delivery_id and landing_url:
        from urllib.parse import quote as _q
        tracked_url = f"{BASE_URL}/l/track/click/{delivery_id}?url={_q(landing_url, safe='')}"
    lines = _html.escape(plain).replace("\n", "<br>\n")
    if delivery_id and landing_url:
        escaped_orig = _html.escape(landing_url)
        escaped_tracked = _html.escape(tracked_url)
        lines = lines.replace(escaped_orig,
                              f'<a href="{escaped_tracked}">{escaped_orig}</a>')
    pixel = ""
    if delivery_id:
        pixel = (f'<img src="{BASE_URL}/l/track/open/{delivery_id}" '
                 f'width="1" height="1" alt="" style="display:none">')
    return (f'<!DOCTYPE html><html><body style="font-family:sans-serif;font-size:14px;color:#333">'
            f'{lines}{pixel}</body></html>')


def _send_brevo_email(to_email: str, to_name: str, subject: str, body: str,
                      delivery_id: str = "", landing_url: str = "") -> bool:
    api_key = os.getenv("BREVO_API_KEY", "")
    if not api_key:
        log.error("BREVO_API_KEY manquante")
        return False
    html_body = _body_to_html(body, landing_url=landing_url, delivery_id=delivery_id)
    try:
        resp = http_req.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={
                "sender": {"name": os.getenv("SENDER_NAME", "Présence IA"), "email": os.getenv("SENDER_EMAIL", "contact@presence-ia.online")},
                "to": [{"email": to_email, "name": to_name}],
                "subject": subject,
                "textContent": body,
                "htmlContent": html_body,
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
            json={"sender": os.getenv("SMS_SENDER", "PresenceIA"), "recipient": phone,
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
    city_cap   = city.capitalize()
    prompts    = [p.format(profession=profession.lower(), city=city_cap) for p in _load_prompts()]
    results    = []

    # ── Clients IA — modèles identiques aux versions web utilisées par les prospects ──
    # ChatGPT : gpt-4o-search-preview (web search intégré, comme ChatGPT web)
    # Gemini  : gemini-2.0-flash avec Google Search Grounding
    # Claude  : claude-sonnet-4-6 (modèle par défaut sur Claude.ai)

    chatgpt_client = None
    try:
        import openai
        key = os.getenv("OPENAI_API_KEY", "")
        if key:
            chatgpt_client = openai.OpenAI(api_key=key)
    except Exception as e:
        log.error("IA init ChatGPT: %s", e)

    # Gemini : REST API direct (bypass SDK trop vieux pour Google Search Grounding)
    gemini_key = os.getenv("GEMINI_API_KEY", "")

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
                # gpt-4o-search-preview : même modèle + web search que ChatGPT web
                r = chatgpt_client.chat.completions.create(
                    model="gpt-4o-search-preview",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=600,
                )
                results.append({"model": "ChatGPT", "prompt": prompt,
                                "response": _strip_markdown(r.choices[0].message.content.strip()),
                                "tested_at": ts})
            except Exception as e:
                log.error("IA test ChatGPT prompt=%r: %s", prompt[:40], e)
                # Fallback gpt-4o sans web search
                try:
                    r = chatgpt_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=600, temperature=0.3,
                    )
                    results.append({"model": "ChatGPT", "prompt": prompt,
                                    "response": _strip_markdown(r.choices[0].message.content.strip()),
                                    "tested_at": ts})
                except Exception as e2:
                    log.error("IA test ChatGPT fallback: %s", e2)

        if gemini_key:
            try:
                # REST API direct → Google Search Grounding (SDK trop vieux sur VPS)
                resp = http_req.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "tools": [{"googleSearch": {}}],
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                results.append({"model": "Gemini", "prompt": prompt,
                                "response": _strip_markdown(text.strip()),
                                "tested_at": ts})
            except Exception as e:
                log.error("IA test Gemini REST prompt=%r: %s", prompt[:40], e)

        if anthropic_client:
            try:
                # claude-sonnet-4-6 + web_search intégré (comme Claude.ai web)
                r = anthropic_client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
                    messages=[{"role": "user", "content": prompt}],
                )
                # Extraire uniquement les blocs texte (ignorer web_search_tool_result)
                text_parts = [b.text for b in r.content if getattr(b, "type", "") == "text"]
                response_text = "\n".join(text_parts).strip()
                if not response_text and r.content:
                    response_text = getattr(r.content[0], "text", "")
                results.append({"model": "Claude", "prompt": prompt,
                                "response": _strip_markdown(response_text),
                                "tested_at": ts})
            except Exception as e:
                log.error("IA test Claude prompt=%r: %s", prompt[:40], e)
                # Fallback sans web search
                try:
                    r = anthropic_client.messages.create(
                        model="claude-sonnet-4-6", max_tokens=600,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    results.append({"model": "Claude", "prompt": prompt,
                                    "response": _strip_markdown(r.content[0].text.strip()),
                                    "tested_at": ts})
                except Exception as e2:
                    log.error("IA test Claude fallback: %s", e2)

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

    # Chercher label_pluriel + termes_recherche dans le référentiel
    _pro_plural = None
    _termes     = []
    try:
        import json as _json
        from ...database import SessionLocal as _SL
        from ...models import ProfessionDB as _PDB
        with _SL() as _db:
            _pobj = (_db.query(_PDB)
                     .filter(_PDB.label.ilike(p.profession))
                     .first())
            if _pobj:
                _pro_plural = _pobj.label_pluriel.lower() if _pobj.label_pluriel else None
                _termes     = _json.loads(_pobj.termes_recherche or "[]")
    except Exception:
        pass
    pro_plural = _pro_plural or (pro_label + "s" if not pro_label.endswith("s") else pro_label)

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
                "prompt":    p.ia_prompt or (_termes and f"Tu connais quelqu'un pour {_termes[0]} à {city_cap} ?" or f"Quels {pro_plural} recommandes-tu à {city_cap} ?"),
                "response":  p.ia_response,
                "tested_at": p.ia_tested_at.isoformat() if isinstance(p.ia_tested_at, datetime)
                             else str(p.ia_tested_at) if p.ia_tested_at else None,
            }]

    # ── Stats réelles ─────────────────────────────────────────────────────
    n_ia = len(ia_results_list) if ia_results_list else 3
    n_competitors = len([x for x in competitors if x])
    last_test_date = ""
    if ia_results_list:
        ts_raw = max((r.get("tested_at") or "" for r in ia_results_list), default="")
        if ts_raw:
            try:
                last_test_date = datetime.fromisoformat(str(ts_raw)).strftime("%d/%m/%Y")
            except Exception:
                last_test_date = str(ts_raw)[:10]
    elif p.ia_tested_at:
        dt = p.ia_tested_at if isinstance(p.ia_tested_at, datetime) else datetime.fromisoformat(str(p.ia_tested_at))
        last_test_date = dt.strftime("%d/%m/%Y")

    stats_html = """<div class="stats-bar">
  <div class="stats-bar__inner">
    <div class="stat">
      <div class="stat__icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="17" y1="8" x2="23" y2="14"/><line x1="23" y1="8" x2="17" y2="14"/></svg></div>
      <div class="stat__val" style="color:#f87171">Des clients perdus</div>
      <div class="stat__lbl">sans même le savoir</div>
    </div>
    <div class="stat">
      <div class="stat__icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg></div>
      <div class="stat__val" style="color:#a78bfa">Des concurrents</div>
      <div class="stat__lbl">qui prennent votre place</div>
    </div>
    <div class="stat">
      <div class="stat__icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg></div>
      <div class="stat__val" style="color:#34d399">Un plan d'action</div>
      <div class="stat__lbl">pour renverser la situation</div>
    </div>
  </div>
</div>"""

    def _ia_accordion_label(model: str, response: str, prospect_name: str, profession: str) -> str:
        """Deux phrases : 'ne vous cite pas' si d'autres sont cités, 'ne connaît aucun' si personne."""
        resp_l = (response or "").lower()
        # Le prospect est cité (rare mais possible)
        if prospect_name and prospect_name.lower() in resp_l:
            return f"{model} vous cite ✓"
        # L'IA ne connaît aucun professionnel local — uniquement si elle ne cite vraiment personne
        # Note: "sans connaître vos besoins" peut précéder une vraie liste → on l'exclut
        no_reco = ["je n'ai pas", "je ne dispose pas", "aucune recommandation",
                   "je ne connais pas", "je ne peux pas fournir",
                   "je ne suis pas en mesure", "il m'est difficile",
                   "je vous recommande de consulter",
                   "je n'ai aucune information"]
        # Exclure "pages jaunes"/"google maps" si une vraie entreprise est aussi citée
        has_entity = bool(re.search(r'[A-Z][a-zàâéèêëîïôùûü]{2,}', response or ""))
        if any(s in resp_l for s in no_reco) and not has_entity:
            return f"{model} ne connaît aucun {profession.lower()}"
        if not has_entity and ("pages jaunes" in resp_l or "google maps" in resp_l):
            return f"{model} ne connaît aucun {profession.lower()}"
        # L'IA cite d'autres entreprises mais pas le prospect
        return f"{model} ne vous cite pas"

    # Mots/débuts qui indiquent que ce N'EST PAS un nom d'entreprise
    _REJECT_STARTS = {
        "définir", "demander", "consulter", "choisir", "vérifier", "comparer",
        "contacter", "obtenir", "utiliser", "faire", "trouver", "chercher",
        "prendre", "privilégier", "éviter", "noter", "savoir", "pensez",
        "il ", "elle ", "vous ", "nous ",
    }
    _REJECT_CONTAINS = {
        "listés", "listées", "listée", "témoigne", "témoignage",
        "trustup", "travaux.com", "houzz", "habitatpresto", "pages jaunes",
        "besoins", "plusieurs devis", "avis clients", "clairement",
        "annuaire", "recommandé par", "recommandée par",
    }

    def _is_company_name(n: str) -> bool:
        """Retourne False si n ressemble à du texte de conseil/plateforme."""
        nl = n.lower().strip()
        if not nl:
            return False
        for start in _REJECT_STARTS:
            if nl.startswith(start):
                return False
        for kw in _REJECT_CONTAINS:
            if kw in nl:
                return False
        # Trop de mots → phrase de conseil, pas un nom d'entreprise
        if len(nl.split()) > 6:
            return False
        return True

    def _extract_competitors_from_response(response: str) -> list:
        """Extrait les noms d'entreprises depuis une réponse IA (markdown + texte Gemini)."""
        names: list = []
        seen: set = set()
        # Markdown links: [Nom](url)
        for m in re.finditer(r'\[([^\]]{3,80})\]\(https?://', response):
            n = m.group(1).strip()
            if n and not n.startswith("http") and n.lower() not in seen and _is_company_name(n):
                names.append(n); seen.add(n.lower())
        # Bold: **Nom** ou **Nom :**
        for m in re.finditer(r'\*\*([^*]{3,80})\*\*', response):
            n = m.group(1).strip().rstrip(":")
            if n and n.lower() not in seen and _is_company_name(n):
                names.append(n); seen.add(n.lower())
        # Gemini format: "   CompanyName : description" (2-4 espaces d'indentation + colon)
        for m in re.finditer(r'^\s{2,4}([A-Za-z\u00C0-\u024F][^\n:]{1,60}?)\s*:', response, re.MULTILINE):
            n = m.group(1).strip()
            if 1 <= len(n.split()) <= 6 and n.lower() not in seen and _is_company_name(n):
                names.append(n); seen.add(n.lower())
        # Gemini plain bullet: "   Aqua by - Charonne\n" (sans colon après le nom)
        for m in re.finditer(r'^\s{2,4}([A-Z\u00C0-\u024F][^\n:]{2,60}?)\s*$', response, re.MULTILINE):
            n = m.group(1).strip()
            if 1 <= len(n.split()) <= 6 and n.lower() not in seen and _is_company_name(n):
                names.append(n); seen.add(n.lower())
        # "incluent A, B et C." (liste en fin de réponse Gemini)
        m_inc = re.search(r'incluent\s+(.+?)\.', response)
        if m_inc:
            for part in re.split(r',\s*|\s+et\s+', m_inc.group(1)):
                n = part.strip()
                if n and n.lower() not in seen and _is_company_name(n):
                    names.append(n); seen.add(n.lower())
        return names[:7]

    # ── Chat groups (1 prompt → accordéon par IA) ─────────────────────────
    _any_empty = False
    if ia_results_list:
        from collections import OrderedDict
        by_prompt = OrderedDict()
        for r in ia_results_list:
            pr = r.get("prompt") or f"Quels {pro_label}s recommandes-tu à {city_cap} ?"
            if pr not in by_prompt:
                by_prompt[pr] = {"tested_at": r.get("tested_at"), "models": []}
            else:
                # garder la date la plus récente
                cur = by_prompt[pr]["tested_at"] or ""
                new_ts = r.get("tested_at") or ""
                if new_ts > cur:
                    by_prompt[pr]["tested_at"] = new_ts
            by_prompt[pr]["models"].append(r)

        _DEMO_COLS = [
            ("chatgpt", "ChatGPT", "(OpenAI)",    "#10a37f"),
            ("claude",  "Claude",  "(Anthropic)", "#d97706"),
            ("gemini",  "Gemini",  "(Google)",    "#4285f4"),
        ]
        chat_html = ""
        _any_empty = False
        for _i, (prompt_text, group) in enumerate(by_prompt.items()):
            ts = ""
            ts_raw = group["tested_at"]
            if ts_raw:
                try:    ts = datetime.fromisoformat(str(ts_raw)).strftime("%d/%m/%Y à %Hh%M")
                except Exception: ts = str(ts_raw)[:16]
            model_map = {(r.get("model") or "").lower(): r for r in group["models"]}
            cols = ""
            for _key, _nm, _co, _color in _DEMO_COLS:
                r = model_map.get(_key)
                if r:
                    lbl = _ia_accordion_label(_nm, r.get("response", ""), p.name, p.profession)
                    _resp = r.get("response", "")
                    _competitors = _extract_competitors_from_response(_resp)
                    if "vous cite ✓" in lbl:
                        items_html = f'<li class="ia-col__cited">{name} ✓</li>'
                        for _cn in _competitors:
                            if _cn.lower() != name.lower():
                                items_html += f'<li>{_cn}</li>'
                    elif _competitors:
                        items_html = "".join(f'<li>{_cn}</li>' for _cn in _competitors)
                    else:
                        items_html = '<li class="ia-col__empty">Aucun concurrent cité</li>'
                else:
                    items_html = '<li class="ia-col__empty">Aucun concurrent cité</li>'
                cols += (
                    f'<div class="ia-col">'
                    f'<div class="ia-col__brand" style="color:{_color}">{_nm} <span style="font-size:.78em;font-weight:400;color:#94a3b8">{_co}</span></div>'
                    f'<ul class="ia-col__list">{items_html}</ul>'
                    f'</div>'
                )
            _open = " open" if _i == 0 else ""
            _icon = "−" if _i == 0 else "+"
            _hidden = "" if _i == 0 else " hidden"
            _ts_span = f'<span class="acc-ts">{ts}</span>' if ts else ""
            if 'ia-col__empty' in cols:
                _any_empty = True
            chat_html += (
                f'<div class="acc-item{_open}">'
                f'<button class="acc-q" onclick="toggleAcc(this)">'
                f'{_ts_span}'
                f'<span class="acc-text">« {prompt_text} »</span>'
                f'<span class="acc-icon">{_icon}</span>'
                f'</button>'
                f'<div class="acc-body"{_hidden}><div class="ia-columns">{cols}</div></div>'
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

    # ── Audit points (inutilisé, conservé pour compatibilité) ─────────────
    pts = ""

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

    _bg_style = f"background-image:linear-gradient(to bottom,rgba(0,0,15,.78) 0%,rgba(0,0,15,.85) 100%),url('{city_image_url}')" if city_image_url else ""
    hero_html = (
        f'<div class="hero" style="{_bg_style}">'
        f'<div class="c">'
        f'<div class="hero-pill">Audit Visibilité IA — {name}</div>'
        f'<h1>À <em>{city_cap}</em>,<br>les IA recommandent des <em>{pro_plural}</em>.<em>Mais pas vous.</em></h1>'
        f'<button class="hero-cta" onclick="document.getElementById(\'ia-demo-title\').scrollIntoView({{behavior:\'smooth\'}})">Voir les résultats ↓</button>'
        f'</div></div>'
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

    from ._gtm import gtm_head, gtm_body, gtm_push
    _calendly_tracked = f"/l/track/calendly/{p.token}"

    return f"""<!DOCTYPE html><html lang="fr"><head>
{gtm_head()}
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} — Audit Visibilité IA</title><meta name="robots" content="noindex"><link rel="icon" href="/assets/favicon.png">
<style>
:root{{--acc:#e8355a;--acc2:#ff7043;--green:#16a34a;--txt:#111827;--muted:#6b7280;--light:#f3f4f8;--border:#e5e7eb;--card:#ffffff;--shadow:0 4px 24px rgba(0,0,0,.08)}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,'Segoe UI',Helvetica,sans-serif;background:#fff;color:var(--txt);line-height:1.65}}
a{{color:inherit;text-decoration:none}}
.c{{max-width:920px;margin:0 auto;padding:0 28px}}
.sticky-nav{{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(15,23,42,.95);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,.06);display:flex;align-items:center;justify-content:space-between;padding:0 28px;height:58px}}
.sn-logo{{color:#fff;font-weight:800;font-size:1rem;letter-spacing:-.02em;text-decoration:none;display:flex;align-items:center}}
.sn-cta{{background:#527FB3;color:#fff;font-weight:700;font-size:13px;padding:9px 20px;border-radius:8px;text-decoration:none;transition:background .15s;white-space:nowrap}}
.sn-cta:hover{{background:#3d6a9a}}
@media(max-width:640px){{.sn-cta{{font-size:11px;padding:6px 12px}}}}
.hero{{min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center;background-size:cover;background-position:center;padding:120px 24px 64px;position:relative}}
.hero::after{{content:"";position:absolute;bottom:0;left:0;right:0;height:80px;background:linear-gradient(transparent,#fff);pointer-events:none}}
.hero-pill{{display:inline-block;background:rgba(255,255,255,.15);backdrop-filter:blur(8px);color:#fff;font-size:11px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;padding:6px 18px;border-radius:30px;border:1px solid rgba(255,255,255,.25);margin-bottom:28px}}
.hero h1{{font-size:clamp(22px,3.8vw,42px);font-weight:800;color:#fff;max-width:820px;margin:0 auto 36px;letter-spacing:-.8px;line-height:1.25;text-shadow:0 2px 12px rgba(0,0,0,.5)}}
.hero h1 em{{font-style:normal;color:#93c5fd}}
.hero h1 em:last-child{{font-style:normal;color:#fff;font-size:.85em;display:block;margin-top:8px}}
.hero-cta{{display:inline-flex;align-items:center;gap:8px;background:#fff;color:var(--txt);font-weight:700;font-size:14px;padding:14px 30px;border-radius:50px;box-shadow:0 4px 20px rgba(0,0,0,.25);cursor:pointer;border:none;transition:transform .2s,box-shadow .2s}}
.hero-cta:hover{{transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,0,0,.3)}}
section{{padding:80px 0}}
.sect-label{{font-size:11px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--acc);margin-bottom:10px}}
section h2{{font-size:clamp(24px,3.8vw,40px);font-weight:800;color:var(--txt);letter-spacing:-.4px;margin-bottom:12px;line-height:1.15}}
.sect-sub{{color:var(--muted);font-size:18px;max-width:680px;margin-bottom:44px;line-height:1.5}}
.stats-bar{{background:#fff;border-bottom:1px solid var(--border);padding:40px 24px}}
.stats-bar__inner{{max-width:820px;margin:0 auto;display:flex;justify-content:center;flex-wrap:wrap;gap:0}}
.stats-bar .stat{{text-align:center;padding:0 44px;border-right:1px solid var(--border)}}
.stats-bar .stat:last-child{{border-right:none}}
.stats-bar .stat__icon{{display:flex;justify-content:center;margin-bottom:10px}}
.stats-bar .stat__val{{font-size:1.1rem;font-weight:800;letter-spacing:-.02em;line-height:1.2}}
.stats-bar .stat__lbl{{font-size:.78rem;color:var(--muted);margin-top:4px;line-height:1.4}}
@media(max-width:600px){{.stats-bar .stat{{border-right:none;border-bottom:1px solid var(--border);padding:20px 0}}.stats-bar .stat:last-child{{border-bottom:none}}}}
.sect-ia-demo{{background:#f8fafc;border-top:1px solid var(--border);border-bottom:1px solid var(--border)}}
.ia-accordion{{margin-bottom:28px}}
.acc-item{{background:#1e293b;border-radius:10px;margin-bottom:10px;overflow:hidden}}
.acc-q{{width:100%;text-align:left;background:transparent;border:none;cursor:pointer;padding:16px 20px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
.acc-ts{{color:#94a3b8;font-size:13px;white-space:nowrap;font-weight:600;flex-shrink:0}}
.acc-text{{font-style:italic;color:#f1f5f9;font-size:15px;font-weight:500;flex:1}}
.acc-icon{{color:#64748b;font-size:20px;font-weight:300;flex-shrink:0;margin-left:auto;transition:color .15s}}
.acc-item.open .acc-icon{{color:#60a5fa}}
.acc-body{{padding:0 16px 16px}}
.ia-columns{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:28px}}
@media(max-width:680px){{.ia-columns{{grid-template-columns:1fr}}}}
.ia-col{{background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px 18px}}
.ia-col__brand{{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)}}
.ia-col__list{{list-style:none;padding:0}}
.ia-col__list li{{font-size:13px;color:#374151;padding:6px 0;border-bottom:1px solid #f1f5f9;display:flex;align-items:center;gap:8px}}
.ia-col__list li:last-child{{border-bottom:none}}
.ia-col__list li::before{{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--acc);flex-shrink:0}}
.ia-col__empty{{font-size:12px;color:var(--muted);font-style:italic}}
.ia-empty-notice{{font-size:13px;color:#94a3b8;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:12px 16px;margin-top:14px;line-height:1.6}}
.ia-insight{{background:#fff;border:2px solid var(--border);border-radius:12px;padding:22px 26px;margin:28px 0 14px}}
.ia-insight__title{{font-size:1.15rem;font-weight:800;color:var(--txt);margin-bottom:8px}}
.ia-insight__text{{font-size:14px;color:var(--muted);line-height:1.65}}
.ia-explain{{font-size:13.5px;color:#374151;background:#f0f9ff;border-left:3px solid #0ea5e9;padding:14px 20px;border-radius:0 8px 8px 0;margin-bottom:6px;line-height:1.65}}
.ia-mention{{text-align:center;font-size:11.5px;color:var(--muted);margin:6px 0 28px;letter-spacing:.2px}}
.ia-demo-cta{{text-align:center;padding-top:8px;border-top:1px solid var(--border);margin-top:8px}}
.ia-demo-cta__limit{{font-size:12px;color:var(--muted);margin-top:14px;font-style:italic}}
.btn-pitch{{display:inline-flex;align-items:center;gap:8px;background:linear-gradient(90deg,var(--acc),var(--acc2));color:#fff;font-weight:700;font-size:15px;padding:16px 40px;border-radius:50px;text-decoration:none;box-shadow:0 4px 20px rgba(232,53,90,.35);transition:all .2s;cursor:pointer;border:none}}
.btn-pitch:hover{{transform:translateY(-2px);box-shadow:0 8px 28px rgba(232,53,90,.45)}}
.sect-pre-faq{{background:linear-gradient(135deg,#0d0820 0%,#0a1840 100%);padding:72px 24px}}
.pre-faq-title{{font-size:clamp(22px,3.5vw,34px);font-weight:800;color:#fff;margin-bottom:16px;letter-spacing:-.3px;line-height:1.2}}
.pre-faq-text{{font-size:15px;color:#94a3b8;margin-bottom:32px;max-width:500px;margin-left:auto;margin-right:auto;line-height:1.7}}
.sect-faq{{background:var(--light)}}
.faq-wrap{{max-width:680px;margin-top:40px}}
.faq-item{{background:#fff;border-radius:10px;margin-bottom:8px;border:1px solid var(--border);overflow:hidden}}
.faq-q{{width:100%;text-align:left;padding:18px 20px;font-size:15px;font-weight:600;color:var(--txt);background:#fff;border:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:16px;transition:background .1s}}
.faq-q:hover{{background:#f8fafc}}
.faq-q.open{{color:var(--acc)}}
.faq-icon{{flex-shrink:0;font-size:20px;font-weight:300;color:var(--muted);line-height:1}}
.faq-q.open .faq-icon{{color:var(--acc)}}
.faq-a{{padding:0 20px 18px;color:var(--muted);font-size:14px;line-height:1.75}}
footer{{background:#111827;padding:32px 24px;text-align:center;color:#6b7280;font-size:11px;letter-spacing:.3px}}
footer a{{color:#9ca3af;text-decoration:underline}}
</style></head><body>
{gtm_body()}
{gtm_push("landing_visit", page_type="prospect_landing", city=p.city, profession=p.profession)}

<nav class="sticky-nav">
  <a class="sn-logo" href="/"><img src="/assets/logo-white.svg" alt="Présence IA" style="height:44px;width:auto;display:block;filter:brightness(0) invert(1)"></a>
  <a class="sn-cta" href="{_calendly_tracked}" target="_blank" data-gtm-event="calendly_click">Réserver mon audit gratuit</a>
</nav>

{hero_html}

{stats_html}

<section class="sect-ia-demo" id="ia-demo">
  <div class="c">
    <p class="sect-sub" id="ia-demo-title"><svg style="display:inline-block;vertical-align:middle;margin-right:8px;flex-shrink:0" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#111827" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>Voici ce que voient vos prospects en ce moment même quand ils consultent leur IA pour trouver un {pro_label} à {city_cap} :</p>
    <div class="ia-accordion">
      {chat_html}
    </div>
    <div class="ia-insight">
      <h3 class="ia-insight__title">Votre entreprise n'apparaît dans aucune réponse.</h3>
      <p class="ia-insight__text">Lorsque vos prospects demandent un {pro_label} à {city_cap} à leur IA, ce sont vos concurrents qui sont recommandés.</p>
      <p class="ia-insight__text" style="margin-top:10px">Une partie de la demande se dirige donc naturellement vers eux — sans que vous en ayez conscience.</p>
      {'<p class="ia-insight__text" style="margin-top:10px">Lorsque les intelligences artificielles ne savent même pas quelles entreprises recommander, cela signifie simplement que les signaux nécessaires ne sont pas encore suffisamment clairs... et que le marché est encore largement ouvert !</p>' if _any_empty else ''}
    </div>
    <div class="ia-explain">
      <p>Les IA recommandent les entreprises pour lesquelles elles trouvent des informations fiables et structurées sur Internet et c'est précisément ce que nous analysons lors de l'audit.</p>
      <p style="margin-top:10px">Que savent les IA aujourd'hui de votre entreprise ? Pourquoi elles recommandent vos concurrents à votre place ?</p>
    </div>
    <p class="ia-mention">Analyse réalisée sur ChatGPT, Claude et Gemini.</p>
    <div class="ia-demo-cta">
      <a class="btn-pitch" href="{_calendly_tracked}" target="_blank" data-gtm-event="calendly_click">Réserver mon audit gratuit →</a>
      <p class="ia-demo-cta__limit">Nous analysons un nombre limité d'entreprises par secteur et par ville.</p>
    </div>
  </div>
</section>

<section class="sect-pre-faq">
  <div class="c" style="text-align:center">
    <h2 class="pre-faq-title">Comprendre pourquoi votre entreprise n'apparaît pas.</h2>
    <p class="pre-faq-text">Recevez votre audit et découvrez comment les IA choisissent les entreprises qu'elles recommandent.</p>
    <a class="btn-pitch" href="{_calendly_tracked}" target="_blank" data-gtm-event="calendly_click">Réserver mon audit gratuit →</a>
  </div>
</section>

<section class="sect-faq"><div class="c"><div class="faq-wrap">
  <div class="faq-item"><button class="faq-q" onclick="toggleFaq(this)">Pourquoi les IA ne me recommandent-elles pas ?<span class="faq-icon">+</span></button><div class="faq-a" hidden>La plupart des entreprises n'ont pas les informations qu'une IA attend pour les recommander : fiche Google incomplète, site peu structuré, pas assez de mentions en ligne. L'audit identifie précisément ce qui vous manque.</div></div>
  <div class="faq-item"><button class="faq-q" onclick="toggleFaq(this)">Est-ce que je reçois un plan d'action ?<span class="faq-icon">+</span></button><div class="faq-a" hidden>Oui. En plus de l'analyse, vous recevez une liste d'actions concrètes classées par priorité. Chaque point est expliqué simplement — pas de jargon technique.</div></div>
  <div class="faq-item"><button class="faq-q" onclick="toggleFaq(this)">Combien de temps pour voir des résultats ?<span class="faq-icon">+</span></button><div class="faq-a" hidden>Les premières améliorations sont généralement visibles en 4 à 8 semaines. Cela dépend des actions mises en place et de l'ancienneté de votre présence en ligne.</div></div>
  <div class="faq-item"><button class="faq-q" onclick="toggleFaq(this)">L'appel est-il payant ?<span class="faq-icon">+</span></button><div class="faq-a" hidden>Non. L'appel de 20 minutes et votre audit sont entièrement gratuits. Si vous souhaitez un accompagnement, nous vous proposerons une offre à l'issue de l'échange.</div></div>
</div></div></section>

<div style="text-align:center;padding:40px 24px 56px">
  <a class="btn-pitch" href="{_calendly_tracked}" target="_blank" data-gtm-event="calendly_click">Réserver mon audit gratuit →</a>
</div>

<footer>
  © 2026 Présence IA &nbsp;·&nbsp;
  <a href="/mentions" target="_blank">Mentions légales</a>
</footer>
<script>
function toggleAcc(btn) {{
  const item = btn.closest('.acc-item');
  const isOpen = item.classList.contains('open');
  document.querySelectorAll('.acc-item').forEach(function(i) {{
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
  document.querySelectorAll('.faq-q').forEach(function(b) {{
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
</script>
</body></html>"""


# ── Authentification admin ────────────────────────────────────────────────────

@router.get("/login/v3", response_class=HTMLResponse)
def login_v3_page(request: Request):
    if _check_admin(request=request):
        return RedirectResponse("/admin/v3", status_code=302)
    return HTMLResponse("""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connexion — Présence IA</title><link rel="icon" href="/assets/favicon.png">
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
  <img src="/assets/logo.svg" alt="Présence IA" style="height:44px;width:auto;display:block;margin:0 auto 4px">
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


# ── Routes tracking email ─────────────────────────────────────────────────────

@router.get("/l/track/open/{delivery_id}")
def track_open(delivery_id: str):
    """Pixel de tracking open — 1×1 GIF transparent."""
    from fastapi.responses import Response
    _mkt.record_open(delivery_id)
    gif = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
           b"!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
           b"\x00\x00\x02\x02D\x01\x00;")
    return Response(content=gif, media_type="image/gif",
                    headers={"Cache-Control": "no-store, no-cache"})


@router.get("/l/track/click/{delivery_id}")
def track_click(delivery_id: str, url: str = ""):
    """Tracking clic → redirige vers l'URL d'origine."""
    _mkt.record_click(delivery_id)
    if url:
        return RedirectResponse(url, status_code=302)
    return RedirectResponse(BASE_URL, status_code=302)


# ── Route publique ────────────────────────────────────────────────────────────

@router.get("/l/track/calendly/{token}")
def track_calendly(token: str):
    """Tracking clic Calendly + redirect."""
    _mkt.record_calendly_click(token)
    return RedirectResponse(CALENDLY_URL, status_code=302)


@router.get("/l/{token}", response_class=HTMLResponse)
def landing_v3(token: str):
    from ...models import CityEvidenceDB
    # Tracking landing visit (silencieux)
    _mkt.record_landing_visit(token)
    with SessionLocal() as db:
        p = db.get(V3ProspectDB, token)
        if not p:
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="https://presence-ia.com", status_code=302)
        from ...database import db_get_header
        city_slug = (p.city or "").lower().strip().replace(" ", "-")
        header = db_get_header(db, city_slug)
        if not header:
            # Fallback : image de la préfecture du département
            from ...models import SireneSuspectDB
            suspect = db.query(SireneSuspectDB).filter(
                SireneSuspectDB.ville == p.city,
                SireneSuspectDB.departement.isnot(None),
            ).first()
            if suspect and suspect.departement:
                prefecture = DEPT_PREFECTURE.get(suspect.departement, "")
                if prefecture:
                    header = db_get_header(db, prefecture.lower().strip().replace(" ", "-"))
        base_url = os.getenv("BASE_URL", "https://presence-ia.com")
        city_image_url = (header.url if header.url.startswith("http") else base_url + header.url) if header else ""
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
        if r.cms:
            links_html += f'<br><span style="font-size:10px;background:#f0f4ff;border:1px solid #dbe4ff;border-radius:3px;padding:1px 5px;color:#4263eb;white-space:nowrap">{r.cms}</span>'
        table_rows += f"""<tr id="row-{r.token}" data-email="{'1' if r.email else '0'}" data-phone="{'1' if r.phone else '0'}" data-sent="{'1' if r.contacted else '0'}">
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
<title>Admin V3 — Présence IA</title><link rel="icon" href="/assets/favicon.png">
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
{admin_nav(api_token, "v3")}
<div class="topbar">
  <h1 style="font-size:.95rem;font-weight:600">Admin V3</h1>
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
    <div class="stat-chip"><strong id="stat-total">{total}</strong><span>Prospects total</span></div>
    <div class="stat-chip"><strong id="stat-email" style="color:#2563eb">{n_email} <span id="stat-email-pct" style="font-size:.8rem;font-weight:400">({pct_e}%)</span></strong><span>Avec email</span></div>
    <div class="stat-chip"><strong id="stat-phone" style="color:#2563eb">{n_phone} <span id="stat-phone-pct" style="font-size:.8rem;font-weight:400">({pct_p}%)</span></strong><span>Avec téléphone</span></div>
    <div class="stat-chip"><strong id="stat-sent" style="color:#16a34a">{n_sent}</strong><span>Contactés</span></div>
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
      <span id="results-count" style="font-size:.82rem;font-weight:600;color:#444">{len(rows)} résultats</span>
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
        <button class="btn btn-danger btn-sm" onclick="deleteSelected()" title="Supprimer les prospects sélectionnés">🗑 Supprimer sélection</button>
      </div>
    </div>

    <div id="bulk-progress" style="display:none;padding:8px 0;font-size:.82rem;color:#2563eb"></div>

    <div style="overflow-x:auto">
      <table id="prospects-table">
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
      testEmail = prompt('Email de test :', 'nathalie.brigitte@gmail.com');
      if (!testEmail) return;
    }} else {{
      testPhone = prompt('Numéro de test :', '+393514459617');
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
      testEmail = prompt('Email de test (recevra tous les messages) :', 'nathalie.brigitte@gmail.com');
      if (!testEmail) return;
    }} else {{
      testPhone = prompt('Numéro de test (recevra tous les SMS) :', '+393514459617');
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
  const allowed = ['image/jpeg','image/png','image/webp','image/gif'];
  if (!allowed.includes(file.type)) {{ status.textContent = '❌ Format invalide — JPG, PNG ou WEBP uniquement'; return; }}
  if (file.size > 50*1024*1024) {{ status.textContent = '❌ Fichier trop lourd (' + (file.size/1024/1024).toFixed(1) + ' Mo) — max 50 Mo avant compression'; return; }}
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

function refreshStats() {{
  const rows = [...document.querySelectorAll('#prospects-table tbody tr')];
  const total = rows.length;
  const nEmail = rows.filter(r => r.dataset.email === '1').length;
  const nPhone = rows.filter(r => r.dataset.phone === '1').length;
  const nSent  = rows.filter(r => r.dataset.sent  === '1').length;
  const pctE = total ? Math.round(nEmail / total * 100) : 0;
  const pctP = total ? Math.round(nPhone / total * 100) : 0;
  document.getElementById('stat-total').textContent = total;
  document.getElementById('stat-email').childNodes[0].textContent = nEmail + ' ';
  document.getElementById('stat-email-pct').textContent = '(' + pctE + '%)';
  document.getElementById('stat-phone').childNodes[0].textContent = nPhone + ' ';
  document.getElementById('stat-phone-pct').textContent = '(' + pctP + '%)';
  document.getElementById('stat-sent').textContent = nSent;
  document.getElementById('results-count').textContent = total + ' résultats';
}}
async function deleteProspect(tok, name) {{
  if (!confirm('Supprimer ' + name + ' ?')) return;
  const r = await fetch(`/api/v3/prospect/${{tok}}?token=${{TOKEN}}`, {{method:'DELETE'}});
  if (r.ok) {{
    const row = document.getElementById('row-' + tok);
    if (row) row.remove();
    refreshStats();
  }} else {{ alert('Erreur suppression'); }}
}}
async function deleteSelected() {{
  const selected = getSelected();
  if (!selected.length) {{ alert('Sélectionnez au moins un prospect.'); return; }}
  if (!confirm(`Supprimer ${{selected.length}} prospect(s) sélectionné(s) ? Cette action est irréversible.`)) return;
  const prog = document.getElementById('bulk-progress');
  prog.style.display = 'block';
  prog.textContent = 'Suppression en cours…';
  let done = 0, errors = 0;
  await Promise.all(selected.map(async tok => {{
    const r = await fetch(`/api/v3/prospect/${{tok}}?token=${{TOKEN}}`, {{method:'DELETE'}});
    if (r.ok) {{ done++; const row = document.getElementById('row-' + tok); if (row) row.remove(); }}
    else errors++;
  }}));
  refreshStats();
  prog.textContent = `✅ ${{done}} supprimé(s)${{errors ? ' — ' + errors + ' erreur(s)' : ''}}`;
  document.getElementById('cb-all').checked = false;
  setTimeout(() => {{ prog.style.display = 'none'; }}, 3000);
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
                # Toujours fetch le max (60) pour avoir assez de candidats après filtrage
                prospects, _ = search_prospects(t.profession, t.city, api_key, max_results=60)
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
                    # Scrape inline : email + CMS depuis le site
                    phone   = p.get("phone")
                    website = p.get("website")
                    scraped = _scrape_site(website) if website else {}
                    email       = scraped.get("email")
                    scrape_phone = scraped.get("phone")
                    contact_url = scraped.get("contact_url")
                    cms         = scraped.get("cms")
                    phone = phone or scrape_phone  # compléter avec tél du site si Google n'en avait pas

                    # Filtrage : seulement les leads qu'on peut contacter
                    if not phone and not email:
                        log.debug("Prospect écarté (pas de contact) : %s", p["name"])
                        continue

                    new_count += 1
                    db.add(V3ProspectDB(
                        token=tok, name=p["name"], city=t.city, profession=t.profession,
                        phone=phone, website=website,
                        email=email, contact_url=contact_url, cms=cms,
                        scrape_status="done",
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
                    phone   = existing.phone or p.get("phone")
                    email   = existing.email
                    cms     = existing.cms
                db.commit()
                results.append({
                    "nom": p["name"], "ville": t.city, "metier": t.profession,
                    "telephone": phone or "", "email": email or "",
                    "cms": cms or "",
                    "site": p.get("website",""),
                    "avis_google": p.get("reviews_count",""), "note": p.get("rating",""),
                    "landing_url": landing_url,
                    "concurrents": " | ".join(competitors),
                    "message_contact": _contact_message(p["name"], t.city, t.profession, landing_url),
                })
    buf = io.StringIO()
    fields = ["nom","ville","metier","telephone","email","cms","site","avis_google","note","landing_url","concurrents","message_contact"]
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
                try:
                    from ..cms_detector import detect_cms
                    cms = detect_cms(p.website)
                    p.cms = cms if cms and cms != "unknown" else None
                except Exception:
                    pass
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
        abs_url   = (p.landing_url or "")
        if abs_url and abs_url.startswith("/"):
            abs_url = BASE_URL + abs_url
        msg   = _contact_message(p.name, p.city, p.profession, abs_url, tpl)
        metier = p.profession.lower(); metiers = metier + "s" if not metier.endswith("s") else metier
        subj  = subj_tpl.format(ville=p.city, metier=metier, metiers=metiers,
                                city=p.city, profession=p.profession, name=p.name)
        delivery_id = _mkt.create_delivery(p.token)
        ok    = _send_brevo_email(p.email, p.name, subj, msg,
                                  delivery_id=delivery_id or "",
                                  landing_url=abs_url)
        _mkt.mark_sent(delivery_id, ok, error="" if ok else "Brevo API error")
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
            abs_lu = landing_url or ""
            if abs_lu.startswith("/"): abs_lu = BASE_URL + abs_lu
            if req.method == "email":
                dest   = req.test_email if test_mode else email
                msg    = _contact_message(name, city, profession, abs_lu, email_tpl)
                metier = profession.lower(); metiers = metier + "s" if not metier.endswith("s") else metier
                subj_real = subj_tpl.format(ville=city, metier=metier, metiers=metiers,
                                            city=city, profession=profession, name=name)
                subj   = f"[TEST] {subj_real}" if test_mode else subj_real
                delivery_id = _mkt.create_delivery(tok) if not test_mode else None
                ok     = _send_brevo_email(dest, name, subj, msg,
                                           delivery_id=delivery_id or "",
                                           landing_url=abs_lu) if dest else False
                _mkt.mark_sent(delivery_id, ok, error="" if ok else "Brevo error")
            elif req.method == "sms":
                dest   = req.test_phone if test_mode else phone
                msg    = _contact_message_sms(name, city, profession, abs_lu, sms_tpl)
                delivery_id = _mkt.create_sms_delivery(tok) if not test_mode else None
                ok     = _send_brevo_sms(dest, msg) if dest else False
                _mkt.mark_sent(delivery_id, ok, error="" if ok else "Brevo SMS error")
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


# ── Webhook Brevo (bounces / unsubscribes) ─────────────────────────────────────

@router.post("/api/v3/webhooks/brevo")
async def brevo_webhook(request: Request):
    """
    Reçoit les événements Brevo (hardBounce, softBounce, blocked, unsubscribed).
    Met à jour ProspectDeliveryDB + marque le prospect V3 si bounce hard.
    """
    try:
        events = await request.json()
        if isinstance(events, dict):
            events = [events]
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid JSON"}, status_code=400)

    from datetime import datetime
    processed = 0
    for ev in events:
        event_type  = ev.get("event", "")
        email       = ev.get("email", "")
        msg_id      = ev.get("message-id", "") or ev.get("messageId", "")

        if not email:
            continue

        # Chercher la livraison par message-id ou par email (dernière livraison)
        try:
            from marketing_module.database import (
                SessionLocal as MktSession, db_update_delivery,
            )
            from marketing_module.models import (
                ProspectDeliveryDB, DeliveryStatus, BounceType,
            )
            with MktSession() as mdb:
                delivery = None
                if msg_id:
                    delivery = (mdb.query(ProspectDeliveryDB)
                                .filter_by(provider_message_id=msg_id).first())
                if not delivery:
                    # Fallback : chercher par prospect_id (token = email lookup)
                    with SessionLocal() as db:
                        p = db.query(V3ProspectDB).filter_by(email=email).first()
                    if p:
                        delivery = (mdb.query(ProspectDeliveryDB)
                                    .filter_by(project_id="presence-ia",
                                               prospect_id=p.token)
                                    .order_by(ProspectDeliveryDB.created_at.desc())
                                    .first())

                if delivery:
                    if event_type in ("hardBounce", "blocked"):
                        db_update_delivery(mdb, delivery.id, {
                            "delivery_status": DeliveryStatus.bounced,
                            "bounce_type":     BounceType.hard,
                            "error_message":   event_type,
                        })
                    elif event_type == "softBounce":
                        db_update_delivery(mdb, delivery.id, {
                            "delivery_status": DeliveryStatus.bounced,
                            "bounce_type":     BounceType.soft,
                        })
                    elif event_type == "unsubscribed":
                        db_update_delivery(mdb, delivery.id, {
                            "reply_status": "negative",
                        })
        except Exception as e:
            log.warning("brevo_webhook delivery update: %s", e)

        # Bounce hard → marquer le prospect V3 (évite les re-envois)
        if event_type in ("hardBounce", "blocked") and email:
            try:
                with SessionLocal() as db:
                    p = db.query(V3ProspectDB).filter_by(email=email).first()
                    if p and not p.contacted:
                        p.sent_method = "bounce"
                        p.contacted   = True
                        db.commit()
            except Exception as e:
                log.warning("brevo_webhook V3 update: %s", e)

        processed += 1
        log.info("Brevo webhook: %s → %s", event_type, email)

    return JSONResponse({"ok": True, "processed": processed})


@router.post("/api/v3/webhooks/twilio/inbound")
async def twilio_inbound_sms(request: Request):
    """
    Webhook Twilio — réception SMS entrant d'un prospect.
    À configurer dans la console Twilio : Messaging → Phone Number → Webhook URL
      → POST https://presence-ia.com/api/v3/webhooks/twilio/inbound

    Twilio envoie un form body avec : From, Body, MessageSid, etc.
    """
    try:
        form = await request.form()
        from_phone = form.get("From", "").strip()
        body_text  = form.get("Body", "").strip()
        msg_sid    = form.get("MessageSid", "")

        if not from_phone:
            return JSONResponse({"ok": False, "error": "no From"})

        log.info("Twilio inbound SMS de %s : %s", from_phone, body_text[:60])

        # Normaliser le numéro pour comparaison (+33 vs 06...)
        def _normalize(n: str) -> str:
            n = n.strip().replace(" ", "").replace("-", "").replace(".", "")
            if n.startswith("0033"): n = "+" + n[2:]
            if n.startswith("33") and not n.startswith("+"): n = "+" + n
            return n

        from_normalized = _normalize(from_phone)

        # Chercher le prospect par téléphone
        with SessionLocal() as db:
            prospects = db.query(V3ProspectDB).filter(
                V3ProspectDB.phone.isnot(None)
            ).all()
            prospect = None
            for p in prospects:
                if _normalize(p.phone or "") == from_normalized:
                    prospect = p
                    break

        if not prospect:
            log.info("Twilio inbound : numéro %s inconnu", from_phone)
            # Twilio attend une réponse TwiML (même vide)
            return HTMLResponse('<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                                 media_type="text/xml")

        log.info("Twilio inbound : réponse SMS de %s (%s)", prospect.name, from_phone)

        # Mise à jour CRM
        try:
            from marketing_module.database import SessionLocal as MktSession, db_update_delivery
            from marketing_module.models import ProspectDeliveryDB, ReplyStatus
            with MktSession() as mdb:
                delivery = (
                    mdb.query(ProspectDeliveryDB)
                    .filter_by(project_id="presence-ia", prospect_id=prospect.token)
                    .order_by(ProspectDeliveryDB.created_at.desc())
                    .first()
                )
                if delivery and delivery.reply_status == ReplyStatus.none:
                    db_update_delivery(mdb, delivery.id, {"reply_status": ReplyStatus.positive})
        except Exception as e:
            log.warning("twilio_inbound CRM update: %s", e)

        # Alerte admin
        try:
            from ...scheduler import _send_reply_alert
            _send_reply_alert(
                prospect_name=prospect.name or from_phone,
                prospect_email=prospect.phone or from_phone,
                snippet=body_text,
                channel="sms",
            )
        except Exception as e:
            log.warning("twilio_inbound alert: %s", e)

        # Réponse TwiML vide (Twilio l'exige)
        return HTMLResponse('<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                             media_type="text/xml")

    except Exception as e:
        log.error("twilio_inbound_sms : %s", e)
        return HTMLResponse('<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                             media_type="text/xml")


@router.get("/api/v3/ia-test-debug")
def ia_test_debug(token: str = "", city: str = "Rennes", profession: str = "couvreur"):
    """Test IA unique pour diagnostiquer les modèles — retourne les erreurs détaillées."""
    _require_admin(token)
    errors = []
    results = []
    city_cap = city.capitalize()
    prompt = f"Quels {profession}s recommandes-tu à {city_cap} ?"

    try:
        import openai
        key = os.getenv("OPENAI_API_KEY", "")
        if key:
            client = openai.OpenAI(api_key=key)
            try:
                r = client.chat.completions.create(
                    model="gpt-4o-search-preview",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=400,
                )
                results.append({"model": "gpt-4o-search-preview", "ok": True,
                                "response": r.choices[0].message.content[:200]})
            except Exception as e:
                errors.append({"model": "gpt-4o-search-preview", "error": str(e)})
                try:
                    r = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=400, temperature=0.3,
                    )
                    results.append({"model": "gpt-4o (fallback)", "ok": True,
                                    "response": r.choices[0].message.content[:200]})
                except Exception as e2:
                    errors.append({"model": "gpt-4o fallback", "error": str(e2)})
        else:
            errors.append({"model": "ChatGPT", "error": "OPENAI_API_KEY manquant"})
    except Exception as e:
        errors.append({"model": "ChatGPT init", "error": str(e)})

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            resp = http_req.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "tools": [{"googleSearch": {}}],
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            results.append({"model": "gemini-2.0-flash+search", "ok": True,
                            "response": text[:200]})
        except Exception as e:
            errors.append({"model": "gemini-2.0-flash+search", "error": str(e)})
    else:
        errors.append({"model": "Gemini", "error": "GEMINI_API_KEY manquant"})

    try:
        import anthropic
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if key:
            client = anthropic.Anthropic(api_key=key)
            try:
                r = client.messages.create(
                    model="claude-sonnet-4-6", max_tokens=600,
                    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
                    messages=[{"role": "user", "content": prompt}],
                )
                text_parts = [b.text for b in r.content if getattr(b, "type", "") == "text"]
                response_text = "\n".join(text_parts).strip() or getattr(r.content[0], "text", "")
                results.append({"model": "claude-sonnet-4-6+search", "ok": True,
                                "response": response_text[:200]})
            except Exception as e:
                errors.append({"model": "claude-sonnet-4-6+search", "error": str(e)})
        else:
            errors.append({"model": "Claude", "error": "ANTHROPIC_API_KEY manquant"})
    except Exception as e:
        errors.append({"model": "Claude init", "error": str(e)})

    return {"prompt": prompt, "results": results, "errors": errors}


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
