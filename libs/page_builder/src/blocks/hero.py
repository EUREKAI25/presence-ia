"""Bloc Hero — image/vidéo/couleur/gradient plein écran avec CTA."""
from typing import Literal, Optional
from pydantic import BaseModel
from .base import BaseBlock, BlockStructure, BlockSeed


class HeroStructure(BlockStructure):
    bg_type: Literal["image", "video", "color", "gradient"] = "color"
    text_position: Literal["center", "left", "right"] = "center"
    overlay: bool = True
    min_height: str = "90vh"


class HeroSeed(BlockSeed):
    title: str = ""
    subtitle: str = ""
    badge: Optional[str] = None
    cta_primary_label: Optional[str] = None
    cta_primary_href: str = "#"
    cta_secondary_label: Optional[str] = None
    cta_secondary_href: str = "#"
    bg_src: Optional[str] = None
    bg_color: Optional[str] = None


class HeroBlock(BaseBlock):
    block_type: Literal["hero_block"] = "hero_block"
    structure: HeroStructure = HeroStructure()
    seed: HeroSeed = HeroSeed()
