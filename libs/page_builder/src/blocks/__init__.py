"""
Blocs v0.2 — exports publics + BlockUnion discriminé.
"""
from typing import Annotated, Union
from pydantic import Field

from .base import BaseBlock, BlockStructure, BlockSeed
from .hero import HeroBlock, HeroStructure, HeroSeed
from .navbar import NavBarBlock, NavBarStructure, NavBarSeed, NavLink
from .stat import StatBlock, StatStructure, StatSeed, StatItem
from .steps import StepsBlock, StepsStructure, StepsSeed, StepItem
from .faq import FAQBlock, FAQStructure, FAQSeed, FAQItem
from .pricing import PricingBlock, PricingStructure, PricingSeed, PricingCardSeed
from .cta import CTABlock, CTAStructure, CTASeed
from .image import ImageBlock, ImageStructure, ImageSeed
from .testimonial import TestimonialBlock, TestimonialStructure, TestimonialSeed, TestimonialItemSeed
from .content import ContentBlock, ContentStructure, ContentSeed, ContentItem
from .footer import FooterBlock, FooterStructure, FooterSeed, FooterColumn

# Union discriminée par block_type — utilisable dans Pydantic avec discriminator
BlockUnion = Annotated[
    Union[
        HeroBlock,
        NavBarBlock,
        StatBlock,
        StepsBlock,
        FAQBlock,
        PricingBlock,
        CTABlock,
        ImageBlock,
        TestimonialBlock,
        ContentBlock,
        FooterBlock,
    ],
    Field(discriminator="block_type"),
]

__all__ = [
    # Base
    "BaseBlock", "BlockStructure", "BlockSeed",
    # Hero
    "HeroBlock", "HeroStructure", "HeroSeed",
    # NavBar
    "NavBarBlock", "NavBarStructure", "NavBarSeed", "NavLink",
    # Stat
    "StatBlock", "StatStructure", "StatSeed", "StatItem",
    # Steps
    "StepsBlock", "StepsStructure", "StepsSeed", "StepItem",
    # FAQ
    "FAQBlock", "FAQStructure", "FAQSeed", "FAQItem",
    # Pricing
    "PricingBlock", "PricingStructure", "PricingSeed", "PricingCardSeed",
    # CTA
    "CTABlock", "CTAStructure", "CTASeed",
    # Image
    "ImageBlock", "ImageStructure", "ImageSeed",
    # Testimonial
    "TestimonialBlock", "TestimonialStructure", "TestimonialSeed", "TestimonialItemSeed",
    # Content
    "ContentBlock", "ContentStructure", "ContentSeed", "ContentItem",
    # Footer
    "FooterBlock", "FooterStructure", "FooterSeed", "FooterColumn",
    # Union
    "BlockUnion",
]
