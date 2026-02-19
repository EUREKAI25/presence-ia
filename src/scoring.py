"""
Module SCORE
Règle EMAIL_OK : mentions=0 sur ≥2/3 modèles ET ≥4/5 requêtes (concurrent stable optionnel)
Score /10 : +4 invisible +2 concurrents +1 ads +1 reviews +1 website
"""
import json, logging
from collections import Counter
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from .database import db_get_prospect, db_list_prospects, db_list_runs, jl
from .models import ProspectDB, ProspectStatus

log = logging.getLogger(__name__)
MIN_COMP_RUNS   = 2   # concurrent vu dans ≥N runs
MODELS_NEEDED   = 2   # sur ≥2/3 modèles
QUERIES_NEEDED  = 4   # sur ≥4/5 requêtes


def _email_ok(runs) -> Tuple[bool, str]:
    if not runs: return False, "Aucun run"

    by_model: Dict[str, list] = {}
    for r in runs: by_model.setdefault(r.model, []).append(r)

    by_query: Dict[int, List[bool]] = {i: [] for i in range(5)}
    for r in runs:
        for qi, m in enumerate(jl(r.mention_per_query)):
            if qi < 5: by_query[qi].append(bool(m))

    invis_models  = [m for m, rs in by_model.items() if all(not r.mentioned_target for r in rs)]
    invis_queries = [qi for qi, ms in by_query.items() if ms and all(not m for m in ms)]

    cc: Counter = Counter()
    for r in runs:
        for c in jl(r.competitors_entities):
            if isinstance(c, str): cc[c.lower()] += 1
    stable = [n for n, cnt in cc.items() if cnt >= MIN_COMP_RUNS]

    ok = len(invis_models) >= MODELS_NEEDED and len(invis_queries) >= QUERIES_NEEDED
    j  = (f"Modèles invisibles {len(invis_models)}/3 {'✓' if len(invis_models)>=MODELS_NEEDED else '✗'} | "
          f"Requêtes invisibles {len(invis_queries)}/5 {'✓' if len(invis_queries)>=QUERIES_NEEDED else '✗'} | "
          f"Concurrents stables {len(stable)}")
    return ok, j


def _score(p: ProspectDB, runs, ok: bool) -> Tuple[float, str, List[str]]:
    s = 0.0; parts = []
    if ok:       s += 4; parts.append("+4 Invisibilité robuste")

    cc: Counter = Counter()
    for r in runs:
        for c in jl(r.competitors_entities):
            if isinstance(c, str): cc[c.lower()] += 1
    stable = [n for n, cnt in cc.most_common(5) if cnt >= MIN_COMP_RUNS]
    if stable:   s += 2; parts.append(f"+2 Concurrents: {', '.join(stable[:2])}")
    if p.google_ads_active:                                  s += 1; parts.append("+1 Google Ads actif")
    if p.reviews_count and p.reviews_count >= 20:            s += 1; parts.append(f"+1 {p.reviews_count} avis")
    if p.website:                                            s += 1; parts.append("+1 Site web présent")

    j = f"Score {s}/10 — EMAIL_OK: {'OUI' if ok else 'NON'}\n" + "\n".join(parts)
    return s, j, stable


def run_scoring(db: Session, campaign_id: str, prospect_ids: Optional[List[str]] = None) -> Dict:
    if prospect_ids:
        prospects = [p for pid in prospect_ids if (p := db_get_prospect(db, pid))]
    else:
        # Re-scorer aussi les SCORED (pour mise à jour éligibilité après enrichissement email)
        tested  = db_list_prospects(db, campaign_id, status=ProspectStatus.TESTED.value)
        rescored = db_list_prospects(db, campaign_id, status=ProspectStatus.SCORED.value)
        prospects = tested + rescored

    res = {"total": len(prospects), "scored": 0, "eligible": 0}
    for p in prospects:
        runs = db_list_runs(db, p.prospect_id)
        if not runs: continue
        ok, ej  = _email_ok(runs)
        sc, sj, stable = _score(p, runs, ok)

        p.eligibility_flag    = ok
        p.ia_visibility_score = sc
        p.score_justification = f"{ej}\n\n{sj}"
        p.competitors_cited   = json.dumps(stable[:5], ensure_ascii=False)
        p.status              = ProspectStatus.SCORED.value
        db.commit()
        res["scored"] += 1
        if ok: res["eligible"] += 1
    return res
