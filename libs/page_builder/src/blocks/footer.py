"""Bloc Footer — pied de page multi-colonnes."""
from typing import List, Literal, Optional
from pydantic import BaseModel
from .base import BaseBlock, BlockStructure, BlockSeed
from .navbar import NavLink


class FooterColumn(BaseModel):
    title: Optional[str] = None
    links: List[NavLink] = []


class FooterStructure(BlockStructure):
    columns: int = 3
    show_social: bool = False


class FooterSeed(BlockSeed):
    copyright: str = ""
    columns: List[FooterColumn] = []
    social_links: List[NavLink] = []


class FooterBlock(BaseBlock):
    block_type: Literal["footer_block"] = "footer_block"
    structure: FooterStructure = FooterStructure()
    seed: FooterSeed = FooterSeed()
