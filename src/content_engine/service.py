"""
Service content_engine — point d'entrée principal.

  generate_content_bundle(prospect_id, db) → {faq, page_html, schema, paths}

Pipeline :
  1. Charge le prospect depuis DB
  2. Charge les queries depuis le dernier snapshot (ou depuis ia_results)
  3. Génère la FAQ
  4. Génère la page service HTML
  5. Génère les JSON-LD (LocalBusiness + FAQPage)
  6. Sauvegarde les fichiers sur disque
  7. Retourne les chemins + le contenu
"""

import json
import logging
from pathlib import Path

from .faq_generator    import generate_faq
from .page_generator   import generate_service_page
from .schema_generator import generate_schema

log = logging.getLogger(__name__)

_ROOT          = Path(__file__).parent.parent.parent
OUTPUT_CONTENT = _ROOT / "deliverables" / "generated" / "content"


def _get_prospect(db, prospect_id: str):
    """Charge V3ProspectDB par token. Lève ValueError si non trouvé."""
    try:
        from ..models import V3ProspectDB
    except ImportError:
        from src.models import V3ProspectDB
    p = db.query(V3ProspectDB).filter(V3ProspectDB.token == prospect_id).first()
    if not p:
        raise ValueError(f"Prospect introuvable : {prospect_id!r}")
    return p


def _load_queries(db, prospect) -> list[dict]:
    """
    Charge les requêtes depuis le dernier snapshot ou depuis ia_results brut.
    Priorité : snapshot DB (déjà parsé) > ia_results brut (parse à la volée).
    """
    # Tentative snapshot DB (plus rapide, déjà parsé)
    try:
        from ..ia_reports.storage import load_last_snapshot
    except ImportError:
        from src.ia_reports.storage import load_last_snapshot

    snap = load_last_snapshot(db, prospect.token)
    if snap and snap.get("queries"):
        return snap["queries"]

    # Fallback : parser les ia_results bruts
    if prospect.ia_results:
        try:
            from ..ia_reports.parser import parse_ia_results
        except ImportError:
            from src.ia_reports.parser import parse_ia_results
        return parse_ia_results(prospect.ia_results, prospect.name)

    return []


def _load_competitors(db, prospect) -> list[dict]:
    """Charge les concurrents depuis le dernier snapshot."""
    try:
        from ..ia_reports.storage import load_last_snapshot
    except ImportError:
        from src.ia_reports.storage import load_last_snapshot

    snap = load_last_snapshot(db, prospect.token)
    return snap.get("competitors", []) if snap else []


def _save(content: str, directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    log.info("Contenu écrit : %s", path)
    return path


def _slug(s: str) -> str:
    import re, unicodedata
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s[:40]


def generate_content_bundle(
    prospect_id: str,
    db,
    max_faq: int = 10,
) -> dict:
    """
    Génère FAQ + page service + JSON-LD pour un prospect V3.

    Args:
        prospect_id : token du prospect V3
        db          : session SQLAlchemy
        max_faq     : nombre max de questions FAQ

    Returns:
        {
          "prospect_id":   str,
          "name":          str,
          "faq":           list[dict],  # [{question, answer}, ...]
          "page_html":     str,         # HTML complet de la page service
          "schema":        dict,        # {local_business, faq_page, html_snippet, instructions}
          "paths": {
            "faq_json":    str,         # chemin fichier faq.json
            "page_html":   str,         # chemin fichier page.html
            "schema_json": str,         # chemin fichier schema.json
          },
          "errors":        list[str],
        }
    """
    p      = _get_prospect(db, prospect_id)
    slug   = _slug(p.token)
    errors = []

    log.info("[content] Génération pour %s (%s, %s)", p.name, p.profession, p.city)

    # 1. Queries (depuis snapshot ou ia_results)
    queries = _load_queries(db, p)
    if not queries:
        log.warning("[content] Aucune query disponible pour %s — FAQ générique", p.name)

    # 2. Concurrents
    competitors = _load_competitors(db, p)

    # 3. FAQ
    faq = []
    try:
        faq = generate_faq(p, queries, max_items=max_faq)
        log.info("[content] FAQ : %d questions générées", len(faq))
    except Exception as e:
        log.error("[content] FAQ échouée : %s", e)
        errors.append(f"faq: {e}")

    # 4. Page service HTML
    page_html = ""
    try:
        page_html = generate_service_page(p, faq_items=faq, competitors=competitors)
        log.info("[content] Page service : %d chars", len(page_html))
    except Exception as e:
        log.error("[content] Page service échouée : %s", e)
        errors.append(f"page: {e}")

    # 5. JSON-LD
    schema = {}
    try:
        schema = generate_schema(p, faq_items=faq)
        log.info("[content] JSON-LD : LocalBusiness + FAQPage générés")
    except Exception as e:
        log.error("[content] Schema échoué : %s", e)
        errors.append(f"schema: {e}")

    # 6. Sauvegarde
    out_dir = OUTPUT_CONTENT / slug
    paths   = {}

    if faq:
        try:
            p_faq = _save(
                json.dumps(faq, ensure_ascii=False, indent=2),
                out_dir, "faq.json"
            )
            paths["faq_json"] = str(p_faq)
        except Exception as e:
            errors.append(f"save_faq: {e}")

    if page_html:
        try:
            p_page = _save(page_html, out_dir, "page_service.html")
            paths["page_html"] = str(p_page)
        except Exception as e:
            errors.append(f"save_page: {e}")

    if schema:
        try:
            schema_content = json.dumps(
                {"local_business": schema["local_business"], "faq_page": schema["faq_page"]},
                ensure_ascii=False, indent=2
            )
            p_schema = _save(schema_content, out_dir, "schema.json")
            paths["schema_json"] = str(p_schema)

            # Snippet HTML séparé (prêt à copier-coller)
            p_snippet = _save(schema["html_snippet"], out_dir, "schema_snippet.html")
            paths["schema_snippet"] = str(p_snippet)
        except Exception as e:
            errors.append(f"save_schema: {e}")

    return {
        "prospect_id": prospect_id,
        "name":        p.name,
        "faq":         faq,
        "page_html":   page_html,
        "schema":      schema,
        "paths":       paths,
        "errors":      errors,
    }
