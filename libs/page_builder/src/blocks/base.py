"""
Blocs de base pour page_builder v0.2.
Structure/Seed séparés + BaseBlock discriminé.
"""
from typing import Optional
from pydantic import BaseModel


class BlockStructure(BaseModel):
    """Structure visuelle d'un bloc (layout, variants, options d'affichage)."""
    pass


class BlockSeed(BaseModel):
    """Contenu d'un bloc (textes, URLs, données). Clés en @namespace.key → i18n."""
    pass


class BaseBlock(BaseModel):
    """Bloc de base (classe parente de tous les blocs v0.2)."""
    block_type: str
    css_class: Optional[str] = None
    id: Optional[str] = None
