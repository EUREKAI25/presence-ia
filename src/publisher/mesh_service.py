"""
Service de maillage interne — rafraîchissement des liens pour un prospect ou tous.

Fonctions exportées :
  refresh_internal_links_for_prospect(prospect_id, db, credentials=None) → dict
  refresh_internal_links_for_all(db, credentials_map=None) → dict

Logique V1 :
  1. Charge les pages publiées du prospect depuis published_pages
  2. Trouve les pages proches (même profession / même ville)
  3. Construit les suggestions (max 3 liens par page)
  4. Enregistre internal_links_json en DB
  5. Retourne le patch HTML à injecter manuellement (ou via WP update_page V2)

V2 (TODO) :
  - update_page() WordPress avec GET du contenu existant + injection du bloc
"""

import logging

log = logging.getLogger(__name__)


# ── Refresh pour un prospect ──────────────────────────────────────────────────

def refresh_internal_links_for_prospect(
    prospect_id: str,
    db,
    credentials: dict | None = None,
) -> dict:
    """
    Recalcule les liens internes pour toutes les pages publiées d'un prospect.

    Args:
        prospect_id : token V3ProspectDB
        db          : session SQLAlchemy
        credentials : {"username": ..., "app_password": ...} — WP uniquement (V2)

    Returns:
        {
          "prospect_id":   str,
          "name":          str,
          "pages_updated": int,
          "links_created": int,
          "pages": [
            {
              "id":          int,
              "title":       str,
              "url":         str | None,
              "links_count": int,
              "links":       [{title, url, anchor, reason}],
              "method":      "db_saved" | "no_related",
              "patch_html":  str | None,   # HTML du bloc à injecter manuellement
            }
          ],
          "errors": list[str],
        }
    """
    try:
        from .page_index import (
            list_generated_pages_for_prospect,
            find_related_pages,
            update_internal_links,
        )
        from .link_builder import build_internal_link_suggestions
        from ..content_engine.link_injector import build_link_block
    except ImportError:
        from src.publisher.page_index import (
            list_generated_pages_for_prospect,
            find_related_pages,
            update_internal_links,
        )
        from src.publisher.link_builder import build_internal_link_suggestions
        from src.content_engine.link_injector import build_link_block

    try:
        from ..models import V3ProspectDB
    except ImportError:
        from src.models import V3ProspectDB

    p = db.query(V3ProspectDB).filter(V3ProspectDB.token == prospect_id).first()
    if not p:
        raise ValueError(f"Prospect introuvable : {prospect_id!r}")

    pages   = list_generated_pages_for_prospect(db, prospect_id)
    results = []
    errors  = []
    total_links = 0

    for page in pages:
        try:
            related = find_related_pages(
                db,
                profession       = page["profession"],
                city             = page["city"],
                exclude_prospect = prospect_id,   # exclut toutes les pages du même prospect
                exclude_url      = page.get("published_url", ""),
                limit            = 5,
            )
            links = build_internal_link_suggestions(page, related, max_links=3)

            # Enregistre en DB
            update_internal_links(db, page["id"], links)
            total_links += len(links)

            patch_html = build_link_block(links) if links else None
            method = "db_saved" if links else "no_related"

            # TODO V2 WordPress auto-update :
            #   1. GET /wp-json/wp/v2/pages/{wp_page_id} → récupérer le contenu existant
            #   2. inject_internal_links(existing_html, links) → html enrichi
            #   3. update_page(site_url, username, app_password, wp_page_id, enriched_html)
            # Requiert credentials + wp_page_id + website sur le prospect.
            # Non implémenté en V1 — patch manuel retourné ci-dessous.

            results.append({
                "id":          page["id"],
                "title":       page["title"],
                "url":         page.get("published_url"),
                "links_count": len(links),
                "links":       links,
                "method":      method,
                "patch_html":  patch_html,
            })

        except Exception as e:
            errors.append(f"Page {page.get('id', '?')} ({page.get('title', '')}): {e}")
            log.error("[mesh] Erreur page %s : %s", page.get("id"), e)

    return {
        "prospect_id":   prospect_id,
        "name":          getattr(p, "name", prospect_id),
        "pages_updated": len(results),
        "links_created": total_links,
        "pages":         results,
        "errors":        errors,
    }


# ── Refresh pour tous les prospects ──────────────────────────────────────────

def refresh_internal_links_for_all(
    db,
    credentials_map: dict | None = None,
) -> dict:
    """
    Rafraîchit le maillage interne pour tous les prospects ayant des pages publiées.

    Args:
        db               : session SQLAlchemy
        credentials_map  : {"prospect_token": {"username": ..., "app_password": ...}}

    Returns:
        {"total": int, "ok": int, "errors": int, "results": list}
    """
    try:
        from .page_index import PublishedPageDB
    except ImportError:
        from src.publisher.page_index import PublishedPageDB

    tokens_rows = db.query(PublishedPageDB.prospect_token).distinct().all()
    tokens = [r[0] for r in tokens_rows]

    ok_count  = 0
    err_count = 0
    results   = []

    for token in tokens:
        creds = (credentials_map or {}).get(token)
        try:
            r = refresh_internal_links_for_prospect(token, db, credentials=creds)
            results.append({"token": token, "ok": True,  "result": r})
            ok_count += 1
        except Exception as e:
            results.append({"token": token, "ok": False, "error": str(e)})
            err_count += 1
            log.error("[mesh] refresh_all — token %s : %s", token, e)

    return {
        "total":   len(tokens),
        "ok":      ok_count,
        "errors":  err_count,
        "results": results,
    }
