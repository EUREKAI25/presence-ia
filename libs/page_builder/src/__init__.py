"""
EURKAI Page Builder v0.2 — Module standalone de construction de pages modulaires.

Usage v0.1 (compat):
    >>> from page_builder import Page, Section, Column, HeroModule, render_page

Usage v0.2 (manifest):
    >>> from page_builder import ManifestPage, parse_manifest, render_page
    >>> import json
    >>> with open("seeds/demo.json") as f:
    ...     manifest = ManifestPage(**json.load(f))
    >>> html = render_page(parse_manifest(manifest))

Usage v0.2 (blocs directs):
    >>> from page_builder import HeroBlock, HeroStructure, HeroSeed, Page, Section, Column, render_page
"""

# ── v0.1 compat ─────────────────────────────────────────────────────────────
from .core.schemas import (
    DesignTokens,
    Element,
    BaseModule,
    HeroModule,
    PricingModule,
    PricingPlan,
    TextModule,
    CTAModule,
    ProofModule,
    TestimonialItem,
    TestimonialsModule,
    Column,
    Section,
    Page,
)
from .builder import PageBuilder
from .renderer.html import render_page

# ── v0.2 — blocs ────────────────────────────────────────────────────────────
from .blocks import (
    BaseBlock, BlockStructure, BlockSeed,
    HeroBlock, HeroStructure, HeroSeed,
    NavBarBlock, NavBarStructure, NavBarSeed, NavLink,
    StatBlock, StatStructure, StatSeed, StatItem,
    StepsBlock, StepsStructure, StepsSeed, StepItem,
    FAQBlock, FAQStructure, FAQSeed, FAQItem,
    PricingBlock, PricingStructure, PricingSeed, PricingCardSeed,
    CTABlock, CTAStructure, CTASeed,
    ImageBlock, ImageStructure, ImageSeed,
    TestimonialBlock, TestimonialStructure, TestimonialSeed, TestimonialItemSeed,
    ContentBlock, ContentStructure, ContentSeed, ContentItem,
    FooterBlock, FooterStructure, FooterSeed, FooterColumn,
    BlockUnion,
)

# ── v0.2 — manifest ──────────────────────────────────────────────────────────
from .manifest import ManifestPage, parse_manifest

# ── v0.2 — i18n ──────────────────────────────────────────────────────────────
from .core.i18n import resolve as i18n_resolve, resolve_placeholders

__version__ = "0.2.0"

__all__ = [
    # v0.1
    "DesignTokens", "Element", "BaseModule",
    "HeroModule", "PricingModule", "PricingPlan", "TextModule",
    "CTAModule", "ProofModule", "TestimonialItem", "TestimonialsModule",
    "Column", "Section", "Page",
    "PageBuilder", "render_page",
    # v0.2 blocs
    "BaseBlock", "BlockStructure", "BlockSeed",
    "HeroBlock", "HeroStructure", "HeroSeed",
    "NavBarBlock", "NavBarStructure", "NavBarSeed", "NavLink",
    "StatBlock", "StatStructure", "StatSeed", "StatItem",
    "StepsBlock", "StepsStructure", "StepsSeed", "StepItem",
    "FAQBlock", "FAQStructure", "FAQSeed", "FAQItem",
    "PricingBlock", "PricingStructure", "PricingSeed", "PricingCardSeed",
    "CTABlock", "CTAStructure", "CTASeed",
    "ImageBlock", "ImageStructure", "ImageSeed",
    "TestimonialBlock", "TestimonialStructure", "TestimonialSeed", "TestimonialItemSeed",
    "ContentBlock", "ContentStructure", "ContentSeed", "ContentItem",
    "FooterBlock", "FooterStructure", "FooterSeed", "FooterColumn",
    "BlockUnion",
    # v0.2 manifest
    "ManifestPage", "parse_manifest",
    # v0.2 i18n
    "i18n_resolve", "resolve_placeholders",
]
