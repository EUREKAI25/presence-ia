"""
Pipeline Implantation IA — orchestrateur complet (offre 3500€).

Réutilise entièrement le pipeline Méthode 500€.
Ajoute : analyse concurrents TOP 3, analyse écarts, stratégie, contenus, livrable premium.

Étapes :
  1.  Pipeline 500 (audit + diagnostic + plan d'action + prompts + structures + checklist)
  2.  Analyse TOP 3 concurrents via IA web search
  3.  Analyse des écarts client vs concurrents
  4.  Stratégie d'implantation (3 phases)
  5.  Génération des contenus (FAQ + page service + blocs IA)
  6.  Assemblage livrable premium HTML + JSON
"""
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)


def run_pipeline(
    company_name: str,
    city: str,
    business_type: str,
    website: Optional[str] = None,
    existing_ia_results: Optional[list] = None,
    skip_ia: bool = False,
    skip_competitors: bool = False,
    max_queries: int = 7,
) -> dict:
    """
    Exécute le pipeline complet Implantation IA.

    Args:
        company_name        : nom de l'entreprise
        city                : ville principale
        business_type       : type d'activité / métier
        website             : URL du site (optionnel)
        existing_ia_results : résultats IA déjà en DB (Format A), skip les appels IA
        skip_ia             : True pour sauter les appels IA (tests)
        skip_competitors    : True pour sauter l'analyse concurrents (tests)
        max_queries         : nb requêtes IA (défaut 7)

    Returns:
        {
            "ok":                  bool,
            "error":               str | None,
            # Données pipeline 500
            "score":               float,
            "score_data":          dict,
            "queries":             list,
            "competitors_raw":     list,    # [{name, count}, ...]
            "diagnostic":          dict,
            "action_plan":         list,
            "prompt_library":      dict,
            "content_structures":  dict,
            "checklist":           dict,
            # Données 3500
            "competitor_analyses": list,    # analyse détaillée TOP 3
            "competitor_summaries":list,    # résumé structuré pour livrable
            "gaps":                list,    # [{gap, impact, priority}]
            "strategy":            dict,    # {phases, pages_to_create, ...}
            "generated_contents":  dict,    # {faq, service_page, ia_blocks, paths}
            # Livrable
            "deliverable_html":    str,
            "deliverable_json":    dict,
            "deliverable_path":    str,
            "elapsed_seconds":     float,
        }
    """
    started_at = datetime.now()
    website    = website or ""

    # ── 1. Pipeline 500 ──────────────────────────────────────────────────────
    log.info("[implantation] Étape 1 : pipeline Méthode 500")
    try:
        from ..methode_ia.pipeline import run_pipeline as run_methode
    except ImportError:
        from src.methode_ia.pipeline import run_pipeline as run_methode

    base = run_methode(
        company_name=company_name,
        city=city,
        business_type=business_type,
        website=website,
        existing_ia_results=existing_ia_results,
        skip_ia=skip_ia,
        max_queries=max_queries,
    )

    if not base["ok"]:
        return {"ok": False, "error": f"Pipeline 500 échoué : {base.get('error')}"}

    score_data       = base["score_data"]
    queries          = base["queries"]
    competitors_raw  = base["competitors"]     # [{name, count}]
    diagnostic       = base["diagnostic"]
    action_plan      = base["action_plan"]

    # ── 2. Analyse TOP 3 concurrents ─────────────────────────────────────────
    log.info("[implantation] Étape 2 : analyse TOP 3 concurrents")
    try:
        from .competitor_analyzer import analyze_top_competitors
    except ImportError:
        from src.implantation_ia.competitor_analyzer import analyze_top_competitors

    competitor_analyses = []
    if not skip_competitors and competitors_raw:
        try:
            competitor_analyses = analyze_top_competitors(
                competitors_raw, city, business_type, top_n=3
            )
        except Exception as e:
            log.warning("[implantation] Analyse concurrents échouée : %s", e)
    elif skip_competitors:
        log.info("[implantation] Mode skip_competitors — analyse ignorée")

    # ── 3. Résumé concurrents ────────────────────────────────────────────────
    try:
        from .gap_analyzer import build_competitor_summary, generate_gap_analysis
    except ImportError:
        from src.implantation_ia.gap_analyzer import build_competitor_summary, generate_gap_analysis

    competitor_summaries = build_competitor_summary(competitor_analyses)

    # ── 4. Analyse des écarts ────────────────────────────────────────────────
    log.info("[implantation] Étape 3 : analyse des écarts")
    gaps = generate_gap_analysis(score_data, competitor_analyses, business_type, city)
    log.info("[implantation] %d écarts identifiés", len(gaps))

    # ── 5. Stratégie ─────────────────────────────────────────────────────────
    log.info("[implantation] Étape 4 : stratégie d'implantation")
    try:
        from .strategy import build_strategy
    except ImportError:
        from src.implantation_ia.strategy import build_strategy

    strategy = build_strategy(gaps, competitor_summaries, business_type, city)

    # ── 6. Génération des contenus ───────────────────────────────────────────
    log.info("[implantation] Étape 5 : génération des contenus")
    try:
        from .content_generator import generate_all_contents
    except ImportError:
        from src.implantation_ia.content_generator import generate_all_contents

    generated_contents = generate_all_contents(
        company_name=company_name,
        city=city,
        business_type=business_type,
        website=website,
        queries=queries,
    )

    # ── 7. Livrable ──────────────────────────────────────────────────────────
    log.info("[implantation] Étape 6 : assemblage livrable")
    try:
        from .deliverable import assemble_deliverable
    except ImportError:
        from src.implantation_ia.deliverable import assemble_deliverable

    generated_at = started_at.strftime("%d/%m/%Y à %Hh%M")
    deliverable  = assemble_deliverable(
        company_name=company_name,
        city=city,
        business_type=business_type,
        website=website,
        score_data=score_data,
        queries=queries,
        diagnostic=diagnostic,
        action_plan=action_plan,
        competitor_summaries=competitor_summaries,
        gaps=gaps,
        strategy=strategy,
        generated_contents=generated_contents,
        generated_at=generated_at,
    )

    elapsed = (datetime.now() - started_at).total_seconds()
    log.info("[implantation] Terminé en %.1fs — score=%.1f — %d concurrents — %d écarts — fichier: %s",
             elapsed, score_data["score"], len(competitor_summaries), len(gaps), deliverable["path"])

    return {
        "ok":                  True,
        "error":               None,
        "company_name":        company_name,
        "city":                city,
        "business_type":       business_type,
        "website":             website,
        "generated_at":        generated_at,
        # Pipeline 500
        "score":               score_data["score"],
        "score_data":          score_data,
        "queries":             queries,
        "competitors_raw":     competitors_raw,
        "diagnostic":          diagnostic,
        "action_plan":         action_plan,
        "prompt_library":      base["prompt_library"],
        "content_structures":  base["content_structures"],
        "checklist":           base["checklist"],
        # 3500
        "competitor_analyses": competitor_analyses,
        "competitor_summaries":competitor_summaries,
        "gaps":                gaps,
        "strategy":            strategy,
        "generated_contents":  generated_contents,
        # Livrable
        "deliverable_html":    deliverable["html"],
        "deliverable_json":    deliverable["json"],
        "deliverable_path":    deliverable["path"],
        "elapsed_seconds":     round(elapsed, 1),
    }
