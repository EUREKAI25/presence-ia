"""
Pipeline Méthode Présence IA — orchestrateur principal.

Entrée  : company_name, city, website (optionnel), business_type
Sortie  : livrable complet (HTML + JSON) + chemin fichier

Étapes :
  1. Génération des requêtes IA
  2. Exécution multi-modèles (ChatGPT, Gemini, Claude)
  3. Parse + scoring des résultats
  4. Extraction des concurrents
  5. Génération du diagnostic
  6. Plan d'action structuré
  7. Bibliothèque de prompts
  8. Structures de contenus
  9. Checklist d'implémentation
  10. Assemblage du livrable HTML + JSON
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
    max_queries: int = 7,
    skip_ia: bool = False,
    existing_ia_results: Optional[list] = None,
) -> dict:
    """
    Exécute le pipeline complet Méthode Présence IA.

    Args:
        company_name        : nom de l'entreprise
        city                : ville principale
        business_type       : type d'activité / métier
        website             : URL du site web (optionnel)
        max_queries         : nombre de requêtes IA (défaut 7)
        skip_ia             : True pour sauter les appels IA (utile en test)
        existing_ia_results : réutiliser des résultats IA déjà en DB (Format A)

    Returns:
        {
            "ok":                bool,
            "error":             str | None,
            "company_name":      str,
            "city":              str,
            "business_type":     str,
            "website":           str,
            "generated_at":      str,
            "score":             float,
            "score_data":        dict,
            "queries":           list,
            "competitors":       list,
            "diagnostic":        dict,
            "action_plan":       list,
            "prompt_library":    dict,
            "content_structures": dict,
            "checklist":         dict,
            "deliverable_html":  str,
            "deliverable_json":  dict,
            "deliverable_path":  str,
        }
    """
    started_at = datetime.now()
    website = website or ""

    try:
        from ..ia_reports.parser import parse_ia_results
        from ..ia_reports.scoring import compute_score, extract_competitors, build_checklist
    except ImportError:
        from src.ia_reports.parser import parse_ia_results
        from src.ia_reports.scoring import compute_score, extract_competitors, build_checklist

    try:
        from .ia_runner import run_ia_queries
        from .diagnostic import generate_diagnostic
        from .action_plan import generate_action_plan
        from .prompt_library import generate_prompt_library
        from .content_structures import generate_content_structures
        from .deliverable import assemble_deliverable
    except ImportError:
        from src.methode_ia.ia_runner import run_ia_queries
        from src.methode_ia.diagnostic import generate_diagnostic
        from src.methode_ia.action_plan import generate_action_plan
        from src.methode_ia.prompt_library import generate_prompt_library
        from src.methode_ia.content_structures import generate_content_structures
        from src.methode_ia.deliverable import assemble_deliverable

    # ── 1-2. Requêtes IA ─────────────────────────────────────────────────
    if existing_ia_results:
        log.info("[pipeline] Réutilisation de %d résultats IA existants", len(existing_ia_results))
        ia_results = existing_ia_results
    elif skip_ia:
        log.info("[pipeline] Mode skip_ia — résultats vides")
        ia_results = []
    else:
        log.info("[pipeline] Démarrage requêtes IA pour %s / %s / %s", company_name, city, business_type)
        try:
            ia_results = run_ia_queries(
                company_name=company_name,
                city=city,
                business_type=business_type,
                website=website,
                max_queries=max_queries,
            )
        except Exception as e:
            log.error("[pipeline] Erreur IA : %s", e)
            return {"ok": False, "error": f"Erreur lors des requêtes IA : {e}"}

    # ── 3. Parse ──────────────────────────────────────────────────────────
    queries = parse_ia_results(ia_results, company_name)
    log.info("[pipeline] %d requêtes parsées", len(queries))

    # ── 4. Score ──────────────────────────────────────────────────────────
    score_data = compute_score(queries)
    log.info("[pipeline] Score = %.1f (%d/%d)", score_data["score"],
             score_data["total_citations"], score_data["total_possible"])

    # ── 5. Concurrents ────────────────────────────────────────────────────
    competitors = extract_competitors(queries, company_name, top_n=5)
    log.info("[pipeline] %d concurrents extraits", len(competitors))

    # ── 6. Diagnostic ─────────────────────────────────────────────────────
    diagnostic = generate_diagnostic(
        company_name=company_name,
        city=city,
        business_type=business_type,
        score_data=score_data,
        queries=queries,
        competitors=competitors,
    )

    # ── 7. Plan d'action ──────────────────────────────────────────────────
    action_plan = generate_action_plan(
        score_level=diagnostic["score_level"],
        business_type=business_type,
        city=city,
    )

    # ── 8. Prompts ────────────────────────────────────────────────────────
    prompt_lib = generate_prompt_library(
        company_name=company_name,
        city=city,
        business_type=business_type,
        website=website,
    )

    # ── 9. Structures ─────────────────────────────────────────────────────
    content_structs = generate_content_structures(
        company_name=company_name,
        city=city,
        business_type=business_type,
    )

    # ── 10. Checklist ─────────────────────────────────────────────────────
    checklist = build_checklist(score_data["score"], business_type, city)

    # ── 11. Livrable ──────────────────────────────────────────────────────
    generated_at = started_at.strftime("%d/%m/%Y à %Hh%M")
    deliverable = assemble_deliverable(
        company_name=company_name,
        city=city,
        business_type=business_type,
        website=website,
        score_data=score_data,
        queries=queries,
        competitors=competitors,
        diagnostic=diagnostic,
        action_plan=action_plan,
        prompt_library=prompt_lib,
        content_structures=content_structs,
        checklist=checklist,
        generated_at=generated_at,
    )

    elapsed = (datetime.now() - started_at).total_seconds()
    log.info("[pipeline] Terminé en %.1fs — score=%.1f — fichier: %s",
             elapsed, score_data["score"], deliverable["path"])

    return {
        "ok":                  True,
        "error":               None,
        "company_name":        company_name,
        "city":                city,
        "business_type":       business_type,
        "website":             website,
        "generated_at":        generated_at,
        "score":               score_data["score"],
        "score_data":          score_data,
        "queries":             queries,
        "competitors":         competitors,
        "diagnostic":          diagnostic,
        "action_plan":         action_plan,
        "prompt_library":      prompt_lib,
        "content_structures":  content_structs,
        "checklist":           checklist,
        "deliverable_html":    deliverable["html"],
        "deliverable_json":    deliverable["json"],
        "deliverable_path":    deliverable["path"],
        "elapsed_seconds":     round(elapsed, 1),
    }
