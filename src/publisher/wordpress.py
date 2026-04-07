"""
Publication via l'API REST WordPress.

Utilise l'authentification par Application Password (recommandé depuis WP 5.6).
Le client génère son Application Password dans :
  Tableau de bord → Utilisateurs → Votre profil → Application Passwords

Docs API : https://developer.wordpress.org/rest-api/reference/pages/
"""

import logging
import re
from datetime import date

import requests

log = logging.getLogger(__name__)

_TIMEOUT = 20  # secondes


def _base_url(site_url: str) -> str:
    """Normalise l'URL de base (retire slash final, force https si absent)."""
    url = site_url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url


def _api(site_url: str) -> str:
    return _base_url(site_url) + "/wp-json/wp/v2"


def _html_to_wp_blocks(html: str) -> str:
    """
    Convertit le HTML brut en contenu compatible Gutenberg.
    WordPress accepte du HTML brut via le bloc <!-- wp:html -->.
    C'est la méthode la plus simple et la plus fiable.
    """
    return f'<!-- wp:html -->\n{html}\n<!-- /wp:html -->'


def check_credentials(site_url: str, username: str, app_password: str) -> dict:
    """
    Vérifie que les credentials WordPress sont valides.

    Returns:
        {"ok": bool, "user": str | None, "error": str | None}
    """
    try:
        r = requests.get(
            f"{_api(site_url)}/users/me",
            auth=(username, app_password),
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            return {"ok": True, "user": data.get("name", username), "error": None}
        return {
            "ok": False,
            "user": None,
            "error": f"HTTP {r.status_code} — {r.text[:200]}",
        }
    except requests.RequestException as e:
        return {"ok": False, "user": None, "error": str(e)}


def publish_page(
    site_url: str,
    username: str,
    app_password: str,
    title: str,
    html_content: str,
    slug: str = "",
    status: str = "publish",
    parent_id: int = 0,
    visibility: str = "discreet",
) -> dict:
    """
    Crée une page WordPress via REST API.

    NAVIGATION : cette fonction ne touche JAMAIS aux menus WordPress.
    Les menus sont gérés séparément dans Apparence → Menus.
    Une page publiée n'apparaît pas automatiquement dans la navigation
    sauf si le thème utilise un "menu automatique" (rare sur les thèmes modernes).

    visibility = "discreet"    → page publiée, accessible par URL directe, absente des menus
    visibility = "integrated"  → page publiée + instruction manuelle d'ajout au menu

    Args:
        site_url     : URL du site (ex: https://mon-site.fr)
        username     : identifiant WordPress
        app_password : Application Password généré dans WP (espaces OK)
        title        : titre de la page
        html_content : contenu HTML complet
        slug         : slug URL (auto depuis le titre si vide)
        status       : "publish" | "draft" | "pending"
        parent_id    : ID page parente (0 = page racine)
        visibility   : "discreet" (défaut) | "integrated"

    Returns:
        {
          "ok":           bool,
          "page_id":      int | None,
          "url":          str | None,   # URL publique de la page
          "edit_url":     str | None,   # URL back-office
          "wp_status":    str,          # statut WP ("publish", "draft"…)
          "visibility":   str,          # "discreet" | "integrated"
          "menu_note":    str,          # note explicite sur la navigation
          "slug":         str,
          "error":        str | None,
        }
    """
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower())
        slug = slug.strip("-")[:60]

    payload = {
        "title":   title,
        "content": _html_to_wp_blocks(html_content),
        "slug":    slug,
        "status":  status,
        # WordPress n'expose pas de champ "menu" dans l'API pages.
        # La page ne sera JAMAIS ajoutée automatiquement à un menu.
    }
    if parent_id:
        payload["parent"] = parent_id

    publish_date = date.today().isoformat()

    menu_note = (
        "Page publiée sans intégration au menu. Accessible par URL directe uniquement."
        if visibility == "discreet"
        else
        "Page publiée. Pour l'ajouter au menu : Apparence → Menus → cocher la page → Enregistrer."
    )

    # Intégration au menu (non implémentée en V1 — requiert l'API WP Menus)
    if visibility == "integrated":
        # TODO V2 : POST /wp-json/wp/v2/menus/{menu_id}/items avec {"object_id": page_id}
        # Non implémenté — WP Menus API nécessite le plugin WP REST API Menus
        log.info("publish_page: visibility=integrated — ajout au menu non automatique (V1)")

    try:
        r = requests.post(
            f"{_api(site_url)}/pages",
            auth=(username, app_password),
            json=payload,
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        log.error("publish_page: erreur réseau sur %s — %s", site_url, e)
        return {"ok": False, "page_id": None, "url": None, "edit_url": None, "status": "", "error": str(e)}

    if r.status_code in (200, 201):
        data      = r.json()
        page_id   = data.get("id")
        page_url  = data.get("link", "")
        edit_url  = f"{_base_url(site_url)}/wp-admin/post.php?post={page_id}&action=edit"
        wp_status = data.get("status", status)
        log.info("publish_page: ✓ page #%s créée sur %s — %s [%s]", page_id, site_url, page_url, visibility)
        return {
            "ok":           True,
            "page_id":      page_id,
            "url":          page_url,
            "edit_url":     edit_url,
            "wp_status":    wp_status,
            "visibility":   visibility,
            "menu_note":    menu_note,
            "slug":         slug,
            "title":        title,
            "publish_date": publish_date,
            "error":        None,
        }

    # Erreur WP — parse le message
    try:
        err_data = r.json()
        err_msg  = err_data.get("message", r.text[:300])
        err_code = err_data.get("code", f"HTTP_{r.status_code}")
    except Exception:
        err_msg  = r.text[:300]
        err_code = f"HTTP_{r.status_code}"

    log.error("publish_page: ✗ %s — %s : %s", site_url, err_code, err_msg)
    return {
        "ok":           False,
        "page_id":      None,
        "url":          None,
        "edit_url":     None,
        "wp_status":    "",
        "visibility":   visibility,
        "menu_note":    menu_note,
        "slug":         slug,
        "title":        title,
        "publish_date": publish_date,
        "error":        f"{err_code}: {err_msg}",
    }


def update_page(
    site_url: str,
    username: str,
    app_password: str,
    page_id: int,
    html_content: str,
    title: str = "",
    status: str = "publish",
) -> dict:
    """
    Met à jour une page WordPress existante par son ID.
    Utile pour les re-publications après mise à jour du contenu.
    """
    payload: dict = {
        "content": _html_to_wp_blocks(html_content),
        "status":  status,
    }
    if title:
        payload["title"] = title

    try:
        r = requests.post(
            f"{_api(site_url)}/pages/{page_id}",
            auth=(username, app_password),
            json=payload,
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        return {"ok": False, "page_id": page_id, "url": None, "edit_url": None, "status": "", "error": str(e)}

    if r.status_code in (200, 201):
        data     = r.json()
        page_url = data.get("link", "")
        edit_url = f"{_base_url(site_url)}/wp-admin/post.php?post={page_id}&action=edit"
        log.info("update_page: ✓ page #%s mise à jour sur %s", page_id, site_url)
        return {"ok": True, "page_id": page_id, "url": page_url, "edit_url": edit_url, "status": data.get("status", status), "error": None}

    try:
        err = r.json().get("message", r.text[:200])
    except Exception:
        err = r.text[:200]
    return {"ok": False, "page_id": page_id, "url": None, "edit_url": None, "status": "", "error": err}
