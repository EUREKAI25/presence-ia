"""Bloc Pricing — grille de plans tarifaires."""
from typing import List, Literal, Optional
from pydantic import BaseModel
from .base import BaseBlock, BlockStructure, BlockSeed


class PricingCardSeed(BaseModel):
    name: str
    price: str
    period: Optional[str] = None
    features: List[str] = []
    is_featured: bool = False
    cta_label: str = "Commencer"
    cta_href: str = "#"
    cta_js: Optional[str] = None


class PricingStructure(BlockStructure):
    layout: Literal["auto", "1col", "2col", "3col"] = "auto"
    card_style: Literal["bordered", "elevated", "flat"] = "bordered"


class PricingSeed(BlockSeed):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    cards: List[PricingCardSeed] = []


class PricingBlock(BaseBlock):
    block_type: Literal["pricing_block"] = "pricing_block"
    structure: PricingStructure = PricingStructure()
    seed: PricingSeed = PricingSeed()
