"""Tests blocs v0.2 — instantiation + render HTML + classes BEM."""
import pytest
from src.blocks import (
    HeroBlock, HeroStructure, HeroSeed,
    NavBarBlock, NavBarSeed, NavLink,
    StatBlock, StatSeed, StatItem,
    StepsBlock, StepsSeed, StepItem,
    FAQBlock, FAQSeed, FAQItem,
    PricingBlock, PricingSeed, PricingCardSeed,
    CTABlock, CTASeed,
    ImageBlock, ImageSeed,
    TestimonialBlock, TestimonialSeed, TestimonialItemSeed,
    ContentBlock, ContentSeed, ContentItem,
    FooterBlock, FooterSeed, FooterColumn,
)
from src.renderer.html import render_module


# ── HeroBlock ────────────────────────────────────────────────────────────────

def test_hero_block_defaults():
    b = HeroBlock()
    assert b.block_type == "hero_block"
    assert b.structure.bg_type == "color"
    assert b.structure.text_position == "center"


def test_hero_block_render_basic():
    b = HeroBlock(seed=HeroSeed(title="Titre test", subtitle="Sous-titre"))
    html = render_module(b)
    assert "hero" in html
    assert "Titre test" in html
    assert "Sous-titre" in html


def test_hero_block_image_has_inline_style():
    b = HeroBlock(
        structure=HeroStructure(bg_type="image", overlay=True, min_height="90vh"),
        seed=HeroSeed(title="T", bg_src="/img/bg.jpg"),
    )
    html = render_module(b)
    assert "background-image:url('/img/bg.jpg')" in html
    assert "min-height:90vh" in html
    assert "hero--overlay" in html


def test_hero_block_cta_group():
    b = HeroBlock(seed=HeroSeed(
        title="T",
        cta_primary_label="Démarrer",
        cta_primary_href="#go",
        cta_secondary_label="Plus d'infos",
    ))
    html = render_module(b)
    assert "hero__cta-group" in html
    assert "Démarrer" in html
    assert "Plus d'infos" in html


# ── NavBarBlock ───────────────────────────────────────────────────────────────

def test_navbar_block_render():
    b = NavBarBlock(seed=NavBarSeed(
        logo_text="ACME",
        links=[NavLink(label="Accueil", href="/"), NavLink(label="Tarifs", href="#pricing")],
    ))
    html = render_module(b)
    assert "navbar" in html
    assert "ACME" in html
    assert "Accueil" in html
    assert "Tarifs" in html


def test_navbar_sticky_class():
    b = NavBarBlock()
    html = render_module(b)
    assert "navbar--sticky" in html


# ── StatBlock ─────────────────────────────────────────────────────────────────

def test_stat_block_render():
    b = StatBlock(seed=StatSeed(stats=[
        StatItem(value="95%", label="Satisfaction"),
        StatItem(value="10k", label="Clients"),
    ]))
    html = render_module(b)
    assert "95%" in html
    assert "Satisfaction" in html
    assert "stat__value" in html
    assert "stat__label" in html


# ── StepsBlock ────────────────────────────────────────────────────────────────

def test_steps_block_cards():
    b = StepsBlock(seed=StepsSeed(
        title="Comment ça marche",
        steps=[StepItem(description="Étape 1"), StepItem(description="Étape 2")],
    ))
    html = render_module(b)
    assert "steps--cards" in html
    assert "Comment ça marche" in html
    assert "Étape 1" in html


def test_steps_block_numbering():
    b = StepsBlock(seed=StepsSeed(steps=[StepItem(description="X")]))
    html = render_module(b)
    assert "steps__number" in html
    assert ">1<" in html


# ── FAQBlock ──────────────────────────────────────────────────────────────────

def test_faq_accordion_render():
    b = FAQBlock(seed=FAQSeed(
        title="FAQ",
        items=[FAQItem(question="Q1?", answer="R1"), FAQItem(question="Q2?", answer="R2")],
    ))
    html = render_module(b)
    assert "faq--accordion" in html
    assert "Q1?" in html
    assert "R1" in html
    assert "aria-expanded" in html


def test_faq_list_style():
    from src.blocks.faq import FAQStructure
    b = FAQBlock(
        structure=FAQStructure(style="list"),
        seed=FAQSeed(items=[FAQItem(question="Q?", answer="R")]),
    )
    html = render_module(b)
    assert "faq--list" in html
    assert "aria-expanded" not in html


# ── PricingBlock ──────────────────────────────────────────────────────────────

def test_pricing_auto_layout_2col():
    b = PricingBlock(seed=PricingSeed(cards=[
        PricingCardSeed(name="A", price="10€"),
        PricingCardSeed(name="B", price="20€"),
    ]))
    html = render_module(b)
    assert "pricing__grid--2col" in html


def test_pricing_auto_layout_3col():
    b = PricingBlock(seed=PricingSeed(cards=[
        PricingCardSeed(name="A", price="10€"),
        PricingCardSeed(name="B", price="20€"),
        PricingCardSeed(name="C", price="30€"),
    ]))
    html = render_module(b)
    assert "pricing__grid--3col" in html


def test_pricing_featured_class():
    b = PricingBlock(seed=PricingSeed(cards=[
        PricingCardSeed(name="Pro", price="50€", is_featured=True),
    ]))
    html = render_module(b)
    assert "pricing__card--featured" in html


def test_pricing_cta_js():
    b = PricingBlock(seed=PricingSeed(cards=[
        PricingCardSeed(name="X", price="0€", cta_js="startCheckout('abc')"),
    ]))
    html = render_module(b)
    assert "<button" in html
    assert "startCheckout" in html


# ── CTABlock ──────────────────────────────────────────────────────────────────

def test_cta_block_gradient():
    b = CTABlock(seed=CTASeed(title="Prêt ?", btn_label="Go", btn_href="#"))
    html = render_module(b)
    assert "cta-block--gradient" in html
    assert "Prêt ?" in html


# ── ImageBlock ────────────────────────────────────────────────────────────────

def test_image_block_render():
    b = ImageBlock(seed=ImageSeed(src="/img/photo.jpg", alt="Photo test"))
    html = render_module(b)
    assert "image-block" in html
    assert "/img/photo.jpg" in html
    assert 'alt="Photo test"' in html


# ── TestimonialBlock ──────────────────────────────────────────────────────────

def test_testimonial_block_render():
    b = TestimonialBlock(seed=TestimonialSeed(
        title="Témoignages",
        items=[TestimonialItemSeed(name="Alice", content="Super service !")],
    ))
    html = render_module(b)
    assert "testimonials" in html
    assert "Alice" in html
    assert "Super service" in html


# ── ContentBlock ──────────────────────────────────────────────────────────────

def test_content_block_text():
    b = ContentBlock(seed=ContentSeed(items={
        "body": ContentItem(type="text", value="Bonjour le monde"),
    }))
    html = render_module(b)
    assert "Bonjour le monde" in html


def test_content_block_html_raw():
    b = ContentBlock(seed=ContentSeed(items={
        "raw": ContentItem(type="html", value="<strong>Bold</strong>"),
    }))
    html = render_module(b)
    assert "<strong>Bold</strong>" in html


# ── FooterBlock ───────────────────────────────────────────────────────────────

def test_footer_block_render():
    b = FooterBlock(seed=FooterSeed(
        copyright="© 2026 ACME",
        columns=[FooterColumn(title="Liens", links=[NavLink(label="CGV", href="/cgv")])],
    ))
    html = render_module(b)
    assert "footer" in html
    assert "© 2026 ACME" in html
    assert "CGV" in html
