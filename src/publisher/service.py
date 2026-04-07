"""
Service publisher — point d'entrée principal.

  publish_content(prospect, page_html, schema_snippet, credentials) → dict

Logique :
  1. Détecte le CMS (champ cms + URL du site)
  2. Si WordPress + credentials fournis → publication automatique REST API
  3. Sinon → package manuel (instructions + contenu prêt à coller)
"""

import logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

# CMS supportés en publication automatique
_AUTO_PUBLISH_CMS = {"wordpress"}


def _detect_cms(prospect) -> str:
    """
    Retourne le CMS normalisé depuis le champ cms ou l'URL du site.
    Valeurs possibles : wordpress | wix | shopify | squarespace | webflow | unknown
    """
    cms = (getattr(prospect, "cms", "") or "").lower().strip()
    if cms and cms != "unknown":
        return cms

    # Détection via URL si cms non renseigné
    website = (
        getattr(prospect, "website", "")
        or getattr(prospect, "url", "")
        or ""
    ).lower()

    if "wix.com" in website or "wixsite.com" in website:
        return "wix"
    if "shopify.com" in website or "myshopify.com" in website:
        return "shopify"
    if "squarespace.com" in website:
        return "squarespace"
    if "webflow.io" in website or "webflow.com" in website:
        return "webflow"

    return "unknown"


def publish_content(
    prospect,
    page_html: str,
    schema_snippet: str = "",
    credentials: dict | None = None,
    title: str = "",
    visibility: str = "discreet",
    publish_target: str = "service_page",
    db=None,
) -> dict:
    """
    Publie la page service sur le site du client.

    Args:
        prospect        : instance V3ProspectDB
        page_html       : HTML généré par content_engine.page_generator
        schema_snippet  : balises JSON-LD générées par schema_generator
        credentials     : {"username": ..., "app_password": ...} — WP uniquement
        title           : titre de la page (auto si vide)
        visibility      : "discreet" (défaut — URL directe, hors menu)
                          "integrated" — page visible + instruction d'ajout au menu
        publish_target  : "service_page" | "faq_page" | "local_page"

    Returns:
        {
          "ok":            bool,
          "method":        str,   # "wordpress_api" | "manual"
          "cms":           str,
          "url":           str | None,
          "edit_url":      str | None,
          "page_id":       int | None,
          "wp_status":     str,          # statut WP brut
          "status":        str,          # "published" | "draft" | "manual_required"
          "visibility":    str,          # "discreet" | "integrated"
          "publish_target": str,
          "menu_note":     str,          # consigne explicite navigation
          "slug":          str,
          "title":         str,
          "instructions":  str,
          "page_html":     str,
          "schema_html":   str,
          "error":         str | None,
        }
    """
    cms = _detect_cms(prospect)
    log.info("[publisher] CMS=%s visibility=%s pour %s", cms, visibility, getattr(prospect, "name", "?"))

    def _register(result: dict) -> None:
        """Enregistre la page publiée dans l'index — silencieux si erreur."""
        if db is None:
            return
        try:
            from .page_index import register_published_page, ensure_table
            from ..database import engine as _engine
            ensure_table(_engine)
            register_published_page(db, prospect, result)
        except Exception as _e:
            log.warning("[publisher] index non mis à jour : %s", _e)

    # ── Titre et slug ─────────────────────────────────────────────────────────
    if not title:
        name       = getattr(prospect, "name", "")
        profession = getattr(prospect, "profession", "professionnel")
        ville      = getattr(prospect, "city", "").capitalize()
        title = f"{profession.capitalize()} à {ville} — {name}"

    # ── Publication WordPress automatique ─────────────────────────────────────
    if cms == "wordpress" and credentials:
        username     = credentials.get("username", "")
        app_password = credentials.get("app_password", "")
        site_url     = (
            getattr(prospect, "website", "")
            or getattr(prospect, "url", "")
            or ""
        )

        if username and app_password and site_url:
            from .wordpress import publish_page

            result = publish_page(
                site_url     = site_url,
                username     = username,
                app_password = app_password,
                title        = title,
                html_content = page_html,
                status       = "publish",
                visibility   = visibility,
            )

            if result["ok"]:
                publish_result = {
                    "ok":             True,
                    "method":         "wordpress_api",
                    "cms":            "wordpress",
                    "url":            result["url"],
                    "edit_url":       result["edit_url"],
                    "page_id":        result["page_id"],
                    "wp_status":      result["wp_status"],
                    "status":         "published",
                    "visibility":     visibility,
                    "publish_target": publish_target,
                    "menu_note":      result["menu_note"],
                    "slug":           result["slug"],
                    "title":          result.get("title", title),
                    "publish_date":   result.get("publish_date", date.today().isoformat()),
                    "instructions":   (
                        "Pour ajouter au menu : Apparence → Menus → cocher la page."
                        if visibility == "integrated" else ""
                    ),
                    "page_html":      page_html,
                    "schema_html":    schema_snippet,
                    "error":          None,
                }
                _register(publish_result)
                return publish_result
            else:
                log.warning("[publisher] WP API échouée : %s", result["error"])
                fallback = _manual_fallback(prospect, page_html, schema_snippet, title, visibility, publish_target)
                fallback["error"] = f"WP API: {result['error']}"
                _register(fallback)
                return fallback

    # ── Fallback manuel ───────────────────────────────────────────────────────
    fallback = _manual_fallback(prospect, page_html, schema_snippet, title, visibility, publish_target)
    _register(fallback)
    return fallback


def _manual_fallback(
    prospect,
    page_html: str,
    schema_snippet: str,
    title: str,
    visibility: str = "discreet",
    publish_target: str = "service_page",
) -> dict:
    """Génère le package de publication manuelle."""
    from .fallback_manual import generate_manual_package
    pkg = generate_manual_package(
        prospect       = prospect,
        page_html      = page_html,
        schema_snippet = schema_snippet,
        title          = title,
        visibility     = visibility,
        publish_target = publish_target,
    )
    return {
        "ok":             True,
        "method":         "manual",
        "cms":            pkg["cms"],
        "url":            None,
        "edit_url":       None,
        "page_id":        None,
        "wp_status":      "",
        "status":         "manual_required",
        "visibility":     pkg["visibility"],
        "publish_target": pkg["publish_target"],
        "menu_note":      pkg["menu_note"],
        "slug":           pkg["slug"],
        "title":          pkg["title"],
        "publish_date":   date.today().isoformat(),
        "instructions":   pkg["instructions"],
        "page_html":      page_html,
        "schema_html":    schema_snippet,
        "error":          None,
    }


# ── Fonction de haut niveau avec chargement DB ────────────────────────────────

def publish_for_prospect(
    prospect_id: str,
    db,
    credentials: dict | None = None,
) -> dict:
    """
    Publie la page service d'un prospect depuis les contenus déjà générés en DB/disque.

    Charge les contenus depuis le dernier bundle généré.
    Si aucun contenu n'existe, génère d'abord via content_engine.

    Args:
        prospect_id : token du prospect V3
        db          : session SQLAlchemy
        credentials : {"username": ..., "app_password": ...} pour WP

    Returns:
        dict retourné par publish_content()
    """
    # Charge le prospect
    try:
        from ..models import V3ProspectDB
    except ImportError:
        from src.models import V3ProspectDB

    p = db.query(V3ProspectDB).filter(V3ProspectDB.token == prospect_id).first()
    if not p:
        raise ValueError(f"Prospect introuvable : {prospect_id!r}")

    # Charge les contenus générés (depuis disque si disponibles)
    page_html      = ""
    schema_snippet = ""

    import re, unicodedata
    slug = unicodedata.normalize("NFD", p.token.lower())
    slug = "".join(c for c in slug if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")[:40]

    _ROOT    = Path(__file__).parent.parent.parent
    out_dir  = _ROOT / "deliverables" / "generated" / "content" / slug

    if (out_dir / "page_service.html").exists():
        page_html = (out_dir / "page_service.html").read_text(encoding="utf-8")
        log.info("[publisher] Page chargée depuis disque : %s", out_dir / "page_service.html")

    if (out_dir / "schema_snippet.html").exists():
        schema_snippet = (out_dir / "schema_snippet.html").read_text(encoding="utf-8")

    # Si pas de contenu sur disque, générer à la volée
    if not page_html:
        log.info("[publisher] Aucun contenu sur disque — génération à la volée pour %s", p.name)
        try:
            from ..content_engine.service import generate_content_bundle
        except ImportError:
            from src.content_engine.service import generate_content_bundle

        bundle = generate_content_bundle(prospect_id, db)
        page_html      = bundle.get("page_html", "")
        schema_snippet = bundle.get("schema", {}).get("html_snippet", "") if bundle.get("schema") else ""

    if not page_html:
        raise ValueError(f"Impossible de charger ou générer la page pour {p.name}")

    return publish_content(p, page_html, schema_snippet, credentials, db=db)
