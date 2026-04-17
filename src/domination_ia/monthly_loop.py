"""
Boucle mensuelle — CRITIQUE.
Relance l'audit IA, compare avec le mois précédent, détecte progression/régressions.
"""

import json
import os
from datetime import date, datetime
from pathlib import Path


_STATE_DIR = Path("dist/domination_ia")


def get_state_path(company_slug: str) -> Path:
    return _STATE_DIR / company_slug / "state.json"


def load_state(company_slug: str) -> dict:
    path = get_state_path(company_slug)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {"runs": []}


def save_state(company_slug: str, state: dict) -> None:
    path = get_state_path(company_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def run_monthly_update(
    company_name: str,
    city: str,
    business_type: str,
    website: str,
    company_slug: str,
    skip_ia: bool = False,
    existing_ia_results: list | None = None,
) -> dict:
    """
    Relance l'audit complet et compare avec le run précédent.

    Returns:
        {
            "run_date":         str,
            "score_current":    float,
            "score_previous":   float | None,
            "score_delta":      float | None,
            "trend":            str,  # up/stable/down/first_run
            "competitors_current":  [str],
            "competitors_previous": [str],
            "new_competitors":      [str],
            "lost_competitors":     [str],
            "queries_gained":       [str],
            "queries_lost":         [str],
            "changes_summary":      [str],
            "ia_results":           list,
            "score_data":           dict,
        }
    """
    from ..methode_ia.ia_runner import run_ia_queries
    try:
        from ..ia_reports.parser import parse_ia_results
        from ..ia_reports.scoring import compute_score, extract_competitors
    except ImportError:
        from src.ia_reports.parser import parse_ia_results
        from src.ia_reports.scoring import compute_score, extract_competitors

    # Audit IA
    if skip_ia:
        ia_results = existing_ia_results or []
    else:
        ia_results = run_ia_queries(company_name, city, business_type, website)

    queries      = parse_ia_results(ia_results, company_name)
    score_data   = compute_score(queries)
    competitors  = extract_competitors(queries, company_name)

    run_date   = date.today().isoformat()
    score_now  = score_data.get("score", 0.0)
    comp_names = [c.get("name", "") for c in competitors if c.get("name")]

    # Charger l'historique
    state = load_state(company_slug)
    runs  = state.get("runs", [])

    # Comparaison avec le run précédent
    previous       = runs[-1] if runs else None
    score_prev     = previous["score"] if previous else None
    comp_prev      = previous.get("competitors", []) if previous else []
    queries_prev   = set(previous.get("cited_queries", [])) if previous else set()

    cited_now    = set(
        q.get("query", "") for q in queries
        if any(q.get(m) and company_name.lower() in q.get(m, "").lower()
               for m in ("chatgpt", "gemini", "claude"))
    )

    new_comps    = [c for c in comp_names if c not in comp_prev]
    lost_comps   = [c for c in comp_prev  if c not in comp_names]
    gained_q     = list(cited_now - queries_prev)
    lost_q       = list(queries_prev - cited_now)

    if score_prev is None:
        trend = "first_run"
    elif score_now > score_prev + 0.5:
        trend = "up"
    elif score_now < score_prev - 0.5:
        trend = "down"
    else:
        trend = "stable"

    score_delta = round(score_now - score_prev, 2) if score_prev is not None else None

    changes = _build_changes_summary(
        trend, score_now, score_prev, score_delta,
        new_comps, lost_comps, gained_q, lost_q, company_name, city
    )

    # Sauvegarder le nouveau run
    runs.append({
        "date":          run_date,
        "score":         score_now,
        "competitors":   comp_names,
        "cited_queries": list(cited_now),
    })
    state["runs"] = runs[-12:]  # garder 12 mois max
    save_state(company_slug, state)

    return {
        "run_date":              run_date,
        "score_current":         score_now,
        "score_previous":        score_prev,
        "score_delta":           score_delta,
        "trend":                 trend,
        "competitors_current":   comp_names,
        "competitors_previous":  comp_prev,
        "new_competitors":       new_comps,
        "lost_competitors":      lost_comps,
        "queries_gained":        gained_q,
        "queries_lost":          lost_q,
        "changes_summary":       changes,
        "ia_results":            ia_results,
        "score_data":            score_data,
        "history":               runs,
    }


def _build_changes_summary(
    trend, score_now, score_prev, delta,
    new_comps, lost_comps, gained_q, lost_q,
    company_name, city,
) -> list[str]:
    lines = []

    if trend == "first_run":
        lines.append(f"Premier audit — score de départ : {score_now}/10")
        return lines

    sign = "+" if delta and delta > 0 else ""
    lines.append(f"Score : {score_prev} → {score_now}/10 ({sign}{delta})")

    if trend == "up":
        lines.append(f"✅ Progression confirmée — +{delta} point(s) ce mois")
    elif trend == "down":
        lines.append(f"⚠️ Recul détecté — {delta} point(s) à récupérer")
    else:
        lines.append("→ Score stable — position maintenue")

    if new_comps:
        lines.append(f"🆕 Nouveaux concurrents détectés : {', '.join(new_comps)}")
    if lost_comps:
        lines.append(f"📉 Concurrents disparus : {', '.join(lost_comps)} (opportunité)")
    if gained_q:
        lines.append(f"✅ Nouvelles requêtes où vous apparaissez : {len(gained_q)}")
    if lost_q:
        lines.append(f"⚠️ Requêtes perdues ce mois : {len(lost_q)} — vérifier le contenu concerné")

    return lines
