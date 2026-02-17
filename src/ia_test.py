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
    if not url: return ""
    u = re.sub(r"^https?://|^www\.", "", url.lower()).split("/")[0]
    p = u.split(".")
    return p[-2] if len(p) >= 2 else u


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
        if d and len(d) > 2 and d in nt: return True
    return False


# ── Extraction entités ────────────────────────────────────────────────

def extract_entities(text: str) -> List[Dict]:
    out = []
    for url in re.findall(r"https?://\S+", text):
        d = domain(url)
        if d: out.append({"type": "url", "value": url, "domain": d})
    for m in re.finditer(r"(?:[A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝ][a-zàáâãäåæçèéêëìíîïðñòóôõöøùúûüý]+\s?){1,4}", text):
        n = m.group().strip()
        if len(n) > 3:
            out.append({"type": "company", "value": n})
    seen: set = set()
    return [e for e in out if not (e["value"].lower() in seen or seen.add(e["value"].lower()))]

def competitors_from(entities: List[Dict], name: str, website: Optional[str]) -> List[str]:
    nt, dt = norm(name), domain(website or "")
    result = []
    for e in entities:
        v = e["value"]
        if nt and nt in norm(v): continue
        if dt and dt in v.lower(): continue
        result.append(v)
    return result


# ── Adaptateurs IA ────────────────────────────────────────────────────

def _openai(q: str) -> str:
    import openai
    r = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY")).chat.completions.create(
        model="gpt-4o-mini", messages=[{"role":"user","content":q}], temperature=TEMP, max_tokens=600)
    return r.choices[0].message.content or ""

def _anthropic(q: str) -> str:
    import anthropic
    r = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")).messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=600, temperature=TEMP,
        messages=[{"role":"user","content":q}])
    return r.content[0].text if r.content else ""

def _gemini(q: str) -> str:
    import google.generativeai as g
    g.configure(api_key=os.getenv("GEMINI_API_KEY"))
    r = g.GenerativeModel("gemini-1.5-flash",
        generation_config={"temperature": TEMP, "max_output_tokens": 600}).generate_content(q)
    return r.text or ""

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
