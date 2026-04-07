"""
Service principal — point d'entrée haut niveau pour la génération de rapports.

Fonctions publiques :
  create_initial_audit_for_prospect(prospect_id, db, ...)
  create_monthly_report_for_prospect(prospect_id, db, ...)
  create_full_deliverable_bundle(prospect_id, db)

Chacune retourne un dict avec les chemins générés et un summary des métriques.
"""

import logging
from datetime import date
from pathlib import Path

from .parser   import parse_ia_results
from .scoring  import compute_score, extract_competitors, build_checklist
from .generator import (
    render_audit_html,
    render_monthly_html,
    select_cms_guide,
    save_html,
    OUTPUT_AUDITS,
    OUTPUT_REPORTS,
)
from .storage import (
    save_snapshot,
    load_last_snapshot,
    count_snapshots,
    ensure_table,
)

log = logging.getLogger(__name__)


# ── Helpers internes ──────────────────────────────────────────────────────────

def _get_prospect(db, prospect_id: str):
    """
    Charge un V3ProspectDB depuis la DB par token.
    Lève ValueError si non trouvé ou sans ia_results.
    """
    try:
        from ..models import V3ProspectDB
    except ImportError:
        from src.models import V3ProspectDB

    p = db.query(V3ProspectDB).filter(V3ProspectDB.token == prospect_id).first()
    if not p:
        raise ValueError(f"Prospect introuvable : {prospect_id!r}")
    if not p.ia_results:
        raise ValueError(
            f"Prospect {prospect_id!r} ({p.name}) sans ia_results — "
            "impossible de générer un rapport."
        )
    return p


def _slug(s: str) -> str:
    """Nom de fichier sûr depuis une chaîne quelconque."""
    import re, unicodedata
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s[:40]


def _filename(prefix: str, token: str) -> str:
    today = date.today().strftime("%Y%m%d")
    return f"{prefix}_{_slug(token)}_{today}.html"


# ── Audit initial ─────────────────────────────────────────────────────────────

def create_initial_audit_for_prospect(
    prospect_id: str,
    db,
    next_step: str = "",
    aliases: list[str] | None = None,
    save_to_disk: bool = True,
) -> dict:
    """
    Génère l'audit initial HTML pour un prospect V3.

    Pipeline :
      1. Charge le prospect depuis la DB
      2. Parse ia_results (robuste multi-format)
      3. Calcule le score IA
      4. Extrait les concurrents
      5. Génère la checklist adaptée au score
      6. Sélectionne le guide CMS
      7. Injecte dans audit_template.html
      8. Sauvegarde snapshot en DB
      9. Écrit le HTML sur disque

    Args:
        prospect_id  : token du prospect V3
        db           : session SQLAlchemy
        next_step    : texte de la prochaine étape (adapté à l'offre vendue)
        aliases      : noms alternatifs pour la détection de citations
        save_to_disk : True pour écrire le fichier HTML (défaut)

    Returns:
        {
          "prospect_id":    str,
          "name":           str,
          "audit_html":     str,   # HTML complet
          "audit_path":     str,   # chemin fichier (ou "" si save_to_disk=False)
          "cms_guide_path": str,   # chemin du guide CMS adapté
          "snapshot_id":    int,
          "summary": {
            "score":          float,
            "total_citations": int,
            "total_possible":  int,
            "total_queries":   int,
            "competitors":     list,
            "checklist_level": str,
          }
        }
    """
    # 1. Prospect
    p = _get_prospect(db, prospect_id)
    log.info("[audit] Génération pour %s (%s, %s)", p.name, p.profession, p.city)

    # 2. Parse
    queries = parse_ia_results(p.ia_results, p.name, aliases)
    if not queries:
        raise ValueError(
            f"ia_results de {p.name} vides ou non parsables. "
            "Le pipeline IA a-t-il bien été exécuté ?"
        )

    # 3. Score
    score_data = compute_score(queries)
    log.info("[audit] Score = %.1f (%d/%d citations)",
             score_data["score"], score_data["total_citations"], score_data["total_possible"])

    # 4. Concurrents — depuis les réponses brutes si disponibles
    competitors = extract_competitors(queries, p.name)

    # 5. Checklist
    checklist = build_checklist(score_data["score"], p.profession.lower(), p.city.capitalize())

    # 6. Guide CMS
    cms_guide = select_cms_guide(
        cms     = getattr(p, "cms", None),
        website = getattr(p, "website", None) or getattr(p, "url", None),
    )

    # 7. HTML
    html = render_audit_html(
        name        = p.name,
        profession  = p.profession,
        city        = p.city,
        cms         = getattr(p, "cms", "") or "",
        score_data  = score_data,
        queries     = queries,
        competitors = competitors,
        checklist   = checklist,
        next_step   = next_step,
    )

    # 8. Snapshot DB
    snap_id = save_snapshot(
        db, p.token, score_data, queries, competitors, html, report_type="audit"
    )

    # 9. Fichier disque
    audit_path = ""
    if save_to_disk:
        fname = _filename("audit", p.token)
        path  = save_html(html, OUTPUT_AUDITS, fname)
        audit_path = str(path)

    return {
        "prospect_id":    prospect_id,
        "name":           p.name,
        "audit_html":     html,
        "audit_path":     audit_path,
        "cms_guide_path": str(cms_guide),
        "snapshot_id":    snap_id,
        "summary": {
            "score":            score_data["score"],
            "total_citations":  score_data["total_citations"],
            "total_possible":   score_data["total_possible"],
            "total_queries":    score_data["total_queries"],
            "competitors":      competitors,
            "checklist_level":  checklist["level"],
        },
    }


# ── Rapport mensuel ───────────────────────────────────────────────────────────

def create_monthly_report_for_prospect(
    prospect_id: str,
    db,
    aliases: list[str] | None = None,
    actions_done: list[dict] | None = None,
    next_actions: list[dict] | None = None,
    periode: str = "",
    note: str = "",
    reviews_count = "—",
    annuaires_count = "—",
    next_retest: str = "à définir",
    save_to_disk: bool = True,
) -> dict:
    """
    Génère le rapport mensuel HTML pour un prospect V3.

    Nécessite qu'un audit initial ait été généré (au moins 1 snapshot en DB).
    Charge automatiquement le dernier snapshot pour le delta.

    Args:
        prospect_id     : token du prospect V3
        db              : session SQLAlchemy
        aliases         : noms alternatifs pour la détection de citations
        actions_done    : [{date, title, desc, status, icon}, ...]
        next_actions    : [{title, desc}, ...]
        periode         : ex: "mai 2026" (auto si vide)
        note            : texte libre de suivi (auto si vide)
        reviews_count   : nb avis Google ajoutés ce mois
        annuaires_count : nb annuaires référencés
        next_retest     : date prochaine re-test
        save_to_disk    : True pour écrire le fichier HTML

    Returns:
        {
          "prospect_id":   str,
          "name":          str,
          "report_html":   str,
          "report_path":   str,
          "snapshot_id":   int,
          "num_test":      int,
          "summary": {
            "score":           float,
            "prev_score":      float,
            "delta":           float,
            "total_citations": int,
            "total_possible":  int,
          }
        }
    """
    # 1. Prospect
    p = _get_prospect(db, prospect_id)
    log.info("[monthly] Génération pour %s (%s, %s)", p.name, p.profession, p.city)

    # 2. Snapshot précédent (requis)
    previous = load_last_snapshot(db, p.token)
    if previous is None:
        raise ValueError(
            f"Aucun audit initial trouvé pour {p.name} ({prospect_id}). "
            "Appelez d'abord create_initial_audit_for_prospect()."
        )

    # 3. Parse ia_results actuels
    queries = parse_ia_results(p.ia_results, p.name, aliases)
    if not queries:
        raise ValueError(f"ia_results de {p.name} vides ou non parsables.")

    # 4. Score actuel
    score_data = compute_score(queries)

    # 5. Concurrents
    competitors = extract_competitors(queries, p.name)

    # 6. Numéro du test (nb snapshots existants + 1 car on n'a pas encore sauvegardé)
    num_test = count_snapshots(db, p.token) + 1

    # 7. HTML
    html = render_monthly_html(
        name            = p.name,
        profession      = p.profession,
        city            = p.city,
        current         = {"score_data": score_data, "queries": queries},
        previous        = previous,
        num_test        = num_test,
        periode         = periode,
        actions_done    = actions_done,
        next_actions    = next_actions,
        note            = note,
        reviews_count   = reviews_count,
        annuaires_count = annuaires_count,
        next_retest     = next_retest,
    )

    # 8. Snapshot DB
    snap_id = save_snapshot(
        db, p.token, score_data, queries, competitors, html, report_type="monthly"
    )

    # 9. Fichier disque
    report_path = ""
    if save_to_disk:
        fname = _filename(f"report_m{num_test - 1}", p.token)
        path  = save_html(html, OUTPUT_REPORTS, fname)
        report_path = str(path)

    delta = round(score_data["score"] - previous["score"], 1)
    log.info("[monthly] Score = %.1f (delta %+.1f)", score_data["score"], delta)

    return {
        "prospect_id":  prospect_id,
        "name":         p.name,
        "report_html":  html,
        "report_path":  report_path,
        "snapshot_id":  snap_id,
        "num_test":     num_test,
        "summary": {
            "score":            score_data["score"],
            "prev_score":       previous["score"],
            "delta":            delta,
            "total_citations":  score_data["total_citations"],
            "total_possible":   score_data["total_possible"],
        },
    }


# ── Bundle complet ────────────────────────────────────────────────────────────

def create_full_deliverable_bundle(
    prospect_id: str,
    db,
    next_step: str = "",
    aliases: list[str] | None = None,
) -> dict:
    """
    Génère tous les livrables disponibles pour un prospect en une seule appel.

    Comportement :
    - Toujours : génère l'audit initial + sauvegarde snapshot
    - Si un audit existe déjà en DB : génère aussi le rapport mensuel
    - Sélectionne le guide CMS adapté

    Returns:
        {
          "prospect_id":    str,
          "name":           str,
          "audit_path":     str,
          "report_path":    str | None,
          "cms_guide_path": str,
          "snapshot_id":    int,
          "report_snapshot_id": int | None,
          "summary":        dict,
          "errors":         list[str],
        }
    """
    errors = []
    result = {
        "prospect_id":        prospect_id,
        "name":               "",
        "audit_path":         "",
        "report_path":        None,
        "cms_guide_path":     "",
        "snapshot_id":        None,
        "report_snapshot_id": None,
        "summary":            {},
        "errors":             errors,
    }

    # Audit initial
    try:
        audit = create_initial_audit_for_prospect(
            prospect_id, db, next_step=next_step, aliases=aliases
        )
        result["name"]           = audit["name"]
        result["audit_path"]     = audit["audit_path"]
        result["cms_guide_path"] = audit["cms_guide_path"]
        result["snapshot_id"]    = audit["snapshot_id"]
        result["summary"]        = audit["summary"]
    except Exception as e:
        log.error("[bundle] Audit échoué pour %s : %s", prospect_id, e)
        errors.append(f"audit: {e}")
        return result

    # Rapport mensuel (si un snapshot précédent existait avant l'audit)
    # On recharge pour voir si un snapshot antérieur existait
    prev_count = count_snapshots(db, prospect_id) - 1  # -1 = l'audit qu'on vient de créer
    if prev_count > 0:
        try:
            report = create_monthly_report_for_prospect(
                prospect_id, db, aliases=aliases
            )
            result["report_path"]        = report["report_path"]
            result["report_snapshot_id"] = report["snapshot_id"]
        except Exception as e:
            log.warning("[bundle] Rapport mensuel échoué pour %s : %s", prospect_id, e)
            errors.append(f"monthly: {e}")

    # Contenu IA-optimisé (FAQ + page service + JSON-LD)
    try:
        from ..content_engine.service import generate_content_bundle
        content = generate_content_bundle(prospect_id, db)
        result["content_paths"] = content["paths"]
        result["faq_count"]     = len(content["faq"])
        if content["errors"]:
            errors.extend([f"content/{e}" for e in content["errors"]])
    except Exception as e:
        log.warning("[bundle] Content engine échoué pour %s : %s", prospect_id, e)
        errors.append(f"content: {e}")

    return result
