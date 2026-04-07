"""
content_engine — Génération de contenus IA-optimisés depuis les données d'audit.

  generate_content_bundle(prospect_id, db) → {faq, page_html, schema, paths}
"""
from .service import generate_content_bundle

__all__ = ["generate_content_bundle"]
