"""
Pipeline Domination IA (9000€).
Étape 1 : appelle le pipeline Implantation IA (3500€) — zéro duplication.
Étapes 2-7 : analyse complète + patterns + stratégie + plan contenu + rapport mensuel + livrable.
"""

import re
from pathlib import Path


def run_pipeline(
    company_name: str,
    city: str,
    business_type: str,
    website: str,
    nearby_cities: list[str] | None = None,
    max_queries: int = 7,
    skip_ia: bool = False,
    skip_competitors: bool = False,
    existing_ia_results: list | None = None,
) -> dict:
    """
    Pipeline complet Domination IA.

    Returns tous les keys du pipeline implantation + :
        all_competitor_analyses, patterns, domination_strategy,
        content_plan, monthly_delta, monthly_report_html,
        domination_deliverable_{html,json,path}
    """
    from ..implantation_ia.pipeline import run_pipeline as run_implantation
    from ..implantation_ia.competitor_analyzer import analyze_top_competitors
    from .domination_patterns import analyze_domination_patterns
    from .domination_strategy import build_domination_strategy
    from .content_plan import build_content_plan
    from .monthly_loop import run_monthly_update
    from .monthly_report import generate_monthly_report
    from .deliverable import assemble_deliverable

    slug = re.sub(r"[^a-z0-9_]", "_", f"{company_name.lower()}_{city.lower()}")

    # ── Étape 1 : pipeline 3500€ ─────────────────────────────────────────────
    implantation_result = run_implantation(
        company_name=company_name,
        city=city,
        business_type=business_type,
        website=website,
        existing_ia_results=existing_ia_results,
        skip_ia=skip_ia,
        skip_competitors=skip_competitors,
        max_queries=max_queries,
    )

    ia_results  = implantation_result.get("ia_results", [])
    score_data  = implantation_result.get("score_data", {})
    top3_comps  = implantation_result.get("competitor_analyses", [])
    gaps        = implantation_result.get("gaps", [])
    strategy    = implantation_result.get("strategy", {})
    contents    = implantation_result.get("generated_contents", {})

    # Récupère le caller IA depuis le pipeline implantation
    caller = _get_caller(implantation_result)

    # ── Étape 2 : analyse TOUS les concurrents cités ─────────────────────────
    # Les top 3 sont déjà analysés ; on analyse les suivants aussi si dispo
    methode_result   = implantation_result.get("methode_result", implantation_result)
    all_cited        = methode_result.get("competitors", [])
    cited_names      = [c.get("name", "") for c in all_cited if c.get("name")]

    if skip_competitors:
        all_competitor_analyses = top3_comps
    else:
        already_analyzed = {c.get("name", "").lower() for c in top3_comps if not c.get("error")}
        remaining = [n for n in cited_names if n.lower() not in already_analyzed]

        extra_analyses = analyze_top_competitors(
            remaining,
            city=city,
            business_type=business_type,
            top_n=len(remaining),
            caller=caller,
        )
        all_competitor_analyses = top3_comps + extra_analyses

    # ── Étape 3 : patterns de domination ─────────────────────────────────────
    patterns = analyze_domination_patterns(
        all_competitor_analyses, gaps, business_type, city
    )

    # ── Étape 4 : stratégie de domination ────────────────────────────────────
    domination_strategy = build_domination_strategy(
        patterns, score_data, gaps, business_type, city
    )

    # ── Étape 5 : plan de contenu 12 mois ────────────────────────────────────
    content_plan = build_content_plan(
        patterns, gaps, business_type, city, nearby_cities
    )

    # ── Étape 6 : boucle mensuelle ────────────────────────────────────────────
    monthly_delta = run_monthly_update(
        company_name=company_name,
        city=city,
        business_type=business_type,
        website=website,
        company_slug=slug,
        skip_ia=True,
        existing_ia_results=ia_results,
    )

    # ── Étape 7 : rapport mensuel ─────────────────────────────────────────────
    monthly_report_html = generate_monthly_report(
        monthly_delta, company_name, city, business_type
    )

    # ── Étape 8 : livrable HTML ───────────────────────────────────────────────
    domination_deliverable = assemble_deliverable(
        company_name=company_name,
        city=city,
        business_type=business_type,
        website=website,
        methode_result=methode_result,
        competitor_analyses=top3_comps,
        gaps=gaps,
        strategy=strategy,
        generated_contents=contents,
        all_competitor_analyses=all_competitor_analyses,
        patterns=patterns,
        domination_strategy=domination_strategy,
        content_plan=content_plan,
        monthly_report_html=monthly_report_html,
    )

    return {
        **implantation_result,
        "all_competitor_analyses":      all_competitor_analyses,
        "patterns":                     patterns,
        "domination_strategy":          domination_strategy,
        "content_plan":                 content_plan,
        "monthly_delta":                monthly_delta,
        "monthly_report_html":          monthly_report_html,
        "domination_deliverable_html":  domination_deliverable["html"],
        "domination_deliverable_json":  domination_deliverable["json"],
        "domination_deliverable_path":  domination_deliverable["path"],
    }


def _get_caller(implantation_result: dict):
    """Récupère le premier caller IA disponible pour les requêtes supplémentaires."""
    try:
        from ..ia_test import _openai_api
        return _openai_api
    except Exception:
        return None
