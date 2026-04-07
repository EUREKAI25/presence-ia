"""
publisher — Publication des contenus générés sur le site du client.

  publish_content(prospect, page_html, schema_snippet, credentials) → dict
  publish_for_prospect(prospect_id, db, credentials) → dict

  refresh_internal_links_for_prospect(prospect_id, db) → dict
  refresh_internal_links_for_all(db) → dict

CMS supportés :
  Automatique : WordPress (REST API + Application Password)
  Manuel      : Wix, Shopify, Squarespace, Webflow, inconnu
"""
from .service import publish_content, publish_for_prospect
from .mesh_service import refresh_internal_links_for_prospect, refresh_internal_links_for_all

__all__ = [
    "publish_content",
    "publish_for_prospect",
    "refresh_internal_links_for_prospect",
    "refresh_internal_links_for_all",
]
