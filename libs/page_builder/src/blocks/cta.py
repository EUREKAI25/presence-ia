"""Bloc CTA — call-to-action avec gradient/couleur/image."""
from typing import Literal, Optional
from .base import BaseBlock, BlockStructure, BlockSeed


class CTAStructure(BlockStructure):
    bg_type: Literal["gradient", "color", "image"] = "gradient"
    text_align: Literal["center", "left"] = "center"


class CTASeed(BlockSeed):
    title: str = ""
    subtitle: Optional[str] = None
    btn_label: str = "Commencer"
    btn_href: str = "#"
    bg_color: Optional[str] = None
    bg_gradient: Optional[str] = None


class CTABlock(BaseBlock):
    block_type: Literal["cta_block"] = "cta_block"
    structure: CTAStructure = CTAStructure()
    seed: CTASeed = CTASeed()
