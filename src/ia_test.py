"""
Module TEST — Multi-IA runner
temperature ≤ 0.2 | extraction entités | matching flou normalisé
"""
import logging, os, re, unicodedata, uuid
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from .database import db_create_run, db_get_prospect, db_list_prospects, jd, jl
from .models import ProspectDB, ProspectStatus, TestRunDB
from .scan import get_queries

log = logging.getLogger(__name__)
TEMP = 0.1  # ≤ 0.2 imposé

_LEGAL = re.compile(r"\b(sarl|sas|eurl|srl|snc|sa|spa|ltd|llc|gmbh|cie|group[e]?|et fils)\b", re.I)


# ── Normalisation ─────────────────────────────────────────────────────

def _no_accent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def norm(name: str) -> str:
    if not name: return ""
    s = _LEGAL.sub(" ", name.lower())
    s = _no_accent(s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())

def domain(url: str) -> str:
    if not url or not url.startswith(("http://", "https://")):
        return ""
    u = re.sub(r"^https?://(?:www\.)?", "", url.lower()).split("/")[0].split("?")[0]
    return u if "." in u else ""


# ── Matching flou ─────────────────────────────────────────────────────

def is_mentioned(text: str, name: str, website: Optional[str] = None, thr: float = 0.82) -> bool:
    nt, nn = norm(text), norm(name)
    if not nn: return False
    if nn in nt: return True
    words = [w for w in nn.split() if len(w) > 2]
    if words and all(w in nt for w in words): return True
    tw = nt.split()
    nw = nn.split()
    for i in range(len(tw)):
        chunk = " ".join(tw[i:i+len(nw)+3])
        if SequenceMatcher(None, nn, chunk).ratio() >= thr: return True
    if website:
        d = domain(website)
        nd = norm(d)  # normalise le domaine comme le texte (enlève les points etc.)
        if nd and len(nd) > 2 and nd in nt: return True
    return False


# ── Extraction entités ────────────────────────────────────────────────

# Mots génériques jamais considérés comme concurrents
_STOPWORDS: set = {
    # Villes / géographie
    "bordeaux", "paris", "lyon", "marseille", "toulouse", "nantes", "rennes",
    "strasbourg", "lille", "nice", "montpellier", "grenoble", "tours",
    "brest", "quimper", "lorient", "vannes", "saint", "bretagne",
    "rouen", "caen", "dijon", "reims", "metz", "nancy", "amiens",
    "clermont", "ferrand", "limoges", "poitiers", "angers", "le mans",
    "france", "europe", "bretagne", "normandie", "alsace",
    # Plateformes / générique
    "google", "maps", "googlemaps", "pagesjaunes", "pages", "jaunes", "yelp",
    "tripadvisor", "leboncoin", "facebook", "instagram", "twitter", "linkedin",
    "youtube", "whatsapp",
    # Verbes / interjections en majuscule fréquents dans les réponses IA
    "voici", "voila", "demandez", "recommandations", "recommandez",
    "attention", "important", "note", "remarque", "conseil", "conseils",
    "informations", "information", "contact", "contactez", "appelez",
    "trouver", "recherchez", "consultez", "ressources", "services",
    "avis", "devis", "urgent", "disponible", "disponibles",
    # Réponses IA génériques
    "content", "context", "listmodels", "models", "response", "error",
    "call", "api", "query", "result", "results", "output",
    # Termes ultra-génériques (pas les métiers : "Couverture Bretonne" est un vrai nom)
    "artisan", "artisans", "entreprise", "entreprises",
    "societe", "societes", "professionnel", "professionnels",
}

# Suffixes légaux à supprimer avant d'évaluer (déjà dans norm(), mais utile ici aussi)
_LEGAL_SUFFIXES = re.compile(
    r"\b(sarl|sas|eurl|snc|sa|spa|ltd|llc|gmbh|cie|groupe?|et fils|and co)\b", re.I
)

# Regex 1 : noms mixtes (Toit Mon Toit, Couverture Bretonne…)
_ORG_RE = re.compile(
    r"\b(?:[A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝ]"
    r"[a-zàáâãäåæçèéêëìíîïðñòóôõöøùúûüý]{2,}"
    r"(?:[-\s][A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝ]"
    r"[a-zàáâãäåæçèéêëìíîïðñòóôõöøùúûüý]{2,}){1,4})\b"
)

# Regex 2 : noms tout-caps (TOIT'URIEN, RDT COUVERTURE, LBAT TOITURE…)
_ORG_CAPS_RE = re.compile(
    r"\b(?:[A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝ]{3,}"
    r"(?:['\s\-][A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝ]{3,}){0,4})\b"
)


def _is_valid_org(name: str) -> bool:
    """Renvoie True si le nom ressemble à une organisation réelle."""
    tokens = name.split()

    # Minimum 2 tokens
    if len(tokens) < 2:
        return False

    # Chaque token doit faire >= 3 caractères
    if any(len(t) < 3 for t in tokens):
        return False

    # Aucun token ne doit être un stopword
    norm_tokens = {_no_accent(t.lower()) for t in tokens}
    if norm_tokens & _STOPWORDS:
        return False

    # Nom entier normalisé ne doit pas être dans les stopwords
    if _no_accent(name.lower().strip()) in _STOPWORDS:
        return False

    return True


def extract_entities(text: str) -> List[Dict]:
    """
    Extraction conservatrice : URLs/domaines + noms d'organisation multi-tokens.
    Retourne une liste vide si rien de fiable n'est trouvé — c'est OK.
    """
    out = []

    # 1. URLs → domaines fiables
    for url in re.findall(r"https?://[^\s,;)\"'>]+", text):
        d = domain(url)
        if d and len(d) > 3:
            out.append({"type": "url", "value": url, "domain": d})

    # 2a. Noms d'organisation mixtes (Toit Mon Toit, Couverture Bretonne…)
    for m in _ORG_RE.finditer(text):
        candidate = m.group().strip()
        clean = _LEGAL_SUFFIXES.sub("", candidate).strip()
        if _is_valid_org(clean):
            out.append({"type": "company", "value": candidate})

    # 2b. Noms tout-caps (TOIT'URIEN, RDT COUVERTURE…) — normalisation pour validation
    for m in _ORG_CAPS_RE.finditer(text):
        candidate = m.group().strip()
        # Convertir en titre pour réutiliser _is_valid_org (qui travaille sur tokens)
        candidate_title = candidate.replace("'", " ").replace("-", " ")
        clean = _LEGAL_SUFFIXES.sub("", candidate_title).strip()
        # Exclure les mots isolés de 3 lettres (acronymes courants) sauf si 2+ tokens
        tokens = [t for t in clean.split() if t]
        if len(tokens) >= 2 and not ({_no_accent(t.lower()) for t in tokens} & _STOPWORDS):
            out.append({"type": "company", "value": candidate})

    # Dédoublonnage insensible à la casse
    seen: set = set()
    return [e for e in out if not (e["value"].lower() in seen or seen.add(e["value"].lower()))]


def competitors_from(entities: List[Dict], name: str, website: Optional[str]) -> List[str]:
    """Filtre les entités : exclut le prospect lui-même + validation finale."""
    nt, dt = norm(name), domain(website or "")
    result = []
    for e in entities:
        v = e["value"]
        # Exclure si c'est le prospect lui-même
        if nt and nt in norm(v):
            continue
        if dt and dt in v.lower():
            continue
        # Pour les URLs, utiliser le domaine comme valeur lisible
        if e["type"] == "url":
            d = e.get("domain", "")
            if d and d != dt:
                result.append(d)
        else:
            result.append(v)
    return result


# ── Adaptateurs IA (web search natif — résultats identiques aux interfaces web) ───

USE_PLAYWRIGHT = os.getenv("USE_PLAYWRIGHT", "0") == "1"  # désactivé — APIs web_search par défaut


def _resolve_openai_model() -> str:
    """Retourne le modèle OpenAI actif : env var si définie, sinon chatgpt-4o-latest (alias officiel → toujours le plus récent)."""
    return os.getenv("OPENAI_MODEL") or "gpt-4o"

def _resolve_anthropic_model() -> str:
    """Retourne le modèle Anthropic actif : env var si définie, sinon détecte le dernier claude-sonnet dispo."""
    if os.getenv("ANTHROPIC_MODEL"):
        return os.getenv("ANTHROPIC_MODEL")
    try:
        import anthropic
        models = [m.id for m in anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")).models.list().data]
        sonnet = sorted([m for m in models if "sonnet" in m], reverse=True)
        return sonnet[0] if sonnet else "claude-sonnet-4-6"
    except Exception:
        return "claude-sonnet-4-6"

def _resolve_gemini_model() -> str:
    """Retourne le modèle Gemini actif : env var si définie, sinon gemini-2.0-flash."""
    return os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"


def _openai_api(q: str) -> str:
    import openai
    model = _resolve_openai_model()
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    r = client.responses.create(
        model=model,
        tools=[{"type": "web_search_preview"}],
        instructions=(
            "Tu es un assistant qui aide à trouver des prestataires locaux en France. "
            "Quand on te demande des piscinistes, couvreurs, plombiers ou autres artisans "
            "dans une ville, tu DOIS donner une liste à puces de vrais noms d'entreprises "
            "locales avec leurs sites web si disponibles. Ne refuse jamais de citer des noms."
        ),
        input=q,
    )
    log.info("openai api: %s", model)
    return r.output_text or ""

def _anthropic_api(q: str) -> str:
    import anthropic
    model = _resolve_anthropic_model()
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Tour 1 : Claude lance la recherche web
    r1 = client.messages.create(
        model=model, max_tokens=2048,
        system=(
            "Tu es un assistant qui aide à trouver des prestataires locaux en France. "
            "Quand on te demande des piscinistes, couvreurs ou artisans dans une ville, "
            "utilise web_search pour trouver de vraies entreprises locales, puis liste-les "
            "avec leurs noms et sites web. Cite toujours des noms réels."
        ),
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": q}],
    )
    log.info("anthropic api: %s stop=%s", model, r1.stop_reason)

    # Si Claude a utilisé le tool → continuer pour obtenir la réponse finale
    if r1.stop_reason == "tool_use":
        # Construire le message de continuation avec les résultats du tool
        tool_results = []
        for block in r1.content:
            if block.type == "tool_use":
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Recherche effectuée.",
                })
        if tool_results:
            r2 = client.messages.create(
                model=model, max_tokens=2048,
                system=(
                    "Tu es un assistant qui aide à trouver des prestataires locaux en France. "
                    "Liste les entreprises trouvées avec leurs noms et sites web."
                ),
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
                messages=[
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": r1.content},
                    {"role": "user", "content": tool_results},
                ],
            )
            return "".join(b.text for b in r2.content if hasattr(b, "text")) or ""

    return "".join(b.text for b in r1.content if hasattr(b, "text")) or ""

def _gemini_api(q: str) -> str:
    from google import genai
    from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
    model_name = _resolve_gemini_model()
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    r = client.models.generate_content(
        model=model_name,
        contents=q,
        config=GenerateContentConfig(
            system_instruction=(
                "Tu es un assistant qui aide à trouver des prestataires locaux en France. "
                "Quand on te demande des piscinistes, couvreurs ou artisans dans une ville, "
                "recherche et liste de vraies entreprises locales avec leurs noms et sites web."
            ),
            tools=[Tool(google_search=GoogleSearch())],
        ),
    )
    log.info("gemini api: %s", model_name)
    return r.text or ""

def _openai(q: str) -> str:
    return _pw_query("chatgpt", q) if USE_PLAYWRIGHT else _openai_api(q)

def _anthropic(q: str) -> str:
    return _pw_query("claude", q) if USE_PLAYWRIGHT else _anthropic_api(q)

def _gemini(q: str) -> str:
    return _pw_query("gemini", q) if USE_PLAYWRIGHT else _gemini_api(q)


def _pw_query(platform: str, q: str) -> str:
    """Lance Playwright (free→paid), fallback sur API web_search si Playwright échoue."""
    from .playwright_scraper import scrape
    for tier in ("free", "paid"):
        res = scrape(platform, tier, q)
        if res["ok"] and res["text"]:
            log.info("[playwright] %s/%s → %d chars | model: %s", platform, tier, len(res["text"]), res["model"])
            return res["text"]
        if res["error"] and "Session manquante" not in res["error"]:
            log.error("[playwright] ALERTE %s/%s — %s", platform, tier, res["error"])

    # Playwright échoué → fallback API web_search (même résultat, sans Cloudflare)
    log.warning("[playwright] %s : sessions échouées → fallback API", platform)
    api_fn = {"chatgpt": _openai_api, "claude": _anthropic_api, "gemini": _gemini_api}.get(platform)
    if api_fn:
        return api_fn(q)
    return ""

_CALLERS = {
    "openai":    (_openai,    "OPENAI_API_KEY"),
    "anthropic": (_anthropic, "ANTHROPIC_API_KEY"),
    "gemini":    (_gemini,    "GEMINI_API_KEY"),
}

def active_models() -> List[str]:
    return [m for m, (_, k) in _CALLERS.items() if os.getenv(k)]


# ── Run ───────────────────────────────────────────────────────────────

def run_for_prospect(db: Session, p: ProspectDB, dry_run: bool = False) -> List[TestRunDB]:
    queries = get_queries(p.profession, p.city)
    models  = active_models() if not dry_run else list(_CALLERS)

    if not models:
        log.warning("Aucune clé API IA configurée")
        return []

    if p.status == ProspectStatus.SCHEDULED.value:
        p.status = ProspectStatus.TESTING.value; db.commit()

    runs = []
    for model in models:
        caller, _ = _CALLERS[model]
        raw, ents, mq, comps, notes = [], [], [], [], []
        mentioned = False

        for qi, q in enumerate(queries):
            ans = f"[DRY_RUN] {q}" if dry_run else _safe_call(caller, q, model, qi, notes)
            raw.append(ans)
            e = extract_entities(ans)
            ents.append([{"type": x["type"], "value": x["value"]} for x in e])
            m = is_mentioned(ans, p.name, p.website)
            mq.append(m)
            if m: mentioned = True
            comps.extend(competitors_from(e, p.name, p.website))

        seen: set = set()
        uc = [c for c in comps if not (c.lower() in seen or seen.add(c.lower()))]

        run = TestRunDB(
            run_id=str(uuid.uuid4()),
            campaign_id=p.campaign_id,
            prospect_id=p.prospect_id,
            ts=datetime.utcnow(),
            model=model,
            queries=jd(queries),
            raw_answers=jd(raw),
            extracted_entities=jd(ents),
            mentioned_target=mentioned,
            mention_per_query=jd(mq),
            competitors_entities=jd(uc[:20]),
            notes="; ".join(notes) or None,
        )
        db_create_run(db, run)
        runs.append(run)

    if p.status == ProspectStatus.TESTING.value:
        p.status = ProspectStatus.TESTED.value; db.commit()
    return runs


def _safe_call(caller, q, model, qi, notes):
    try:
        return caller(q)
    except Exception as e:
        log.error(f"[{model}] Q{qi+1}: {e}")
        notes.append(f"Q{qi+1} {model}: {e}")
        return f"[ERREUR] {e}"


def run_campaign(db: Session, campaign_id: str, prospect_ids: Optional[List[str]] = None,
                 dry_run: bool = False) -> Dict:
    if prospect_ids:
        prospects = [db_get_prospect(db, pid) for pid in prospect_ids]
        prospects = [p for p in prospects if p]
    else:
        prospects = db_list_prospects(db, campaign_id, status=ProspectStatus.SCHEDULED.value)

    res = {"total": len(prospects), "processed": 0, "runs_created": 0, "errors": []}
    for p in prospects:
        try:
            r = run_for_prospect(db, p, dry_run=dry_run)
            res["processed"] += 1; res["runs_created"] += len(r)
        except Exception as e:
            log.error(f"Prospect {p.prospect_id}: {e}")
            res["errors"].append({"prospect_id": p.prospect_id, "error": str(e)})
    return res
