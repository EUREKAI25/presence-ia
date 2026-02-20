"""
Tests unitaires pour les schémas Pydantic.
"""
import sys
from pathlib import Path

# Ajout src au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import (
    DesignTokens, Page, Section, Column,
    HeroModule, PricingModule, PricingPlan,
    render_page
)


def test_design_tokens_defaults():
    """Test des valeurs par défaut des tokens."""
    tokens = DesignTokens()
    assert tokens.primary_color == "#667eea"
    assert tokens.secondary_color == "#764ba2"
    assert tokens.font_size_base == 16
    assert tokens.line_height_base == 1.6
    assert tokens.spacing_unit == 8


def test_design_tokens_custom():
    """Test des tokens personnalisés."""
    tokens = DesignTokens(
        primary_color="#ff0000",
        secondary_color="#00ff00",
        font_size_base=18,
        line_height_base=1.8,
        spacing_unit=10
    )
    assert tokens.primary_color == "#ff0000"
    assert tokens.font_size_base == 18


def test_hero_module():
    """Test de création d'un HeroModule."""
    hero = HeroModule(
        title="Test Title",
        subtitle="Test Subtitle",
        badge="Badge",
        cta_primary={"label": "CTA", "href": "#test"}
    )
    assert hero.module_type == "hero"
    assert hero.title == "Test Title"
    assert hero.cta_primary["label"] == "CTA"


def test_pricing_module():
    """Test de création d'un PricingModule."""
    pricing = PricingModule(
        title="Pricing",
        plans=[
            PricingPlan(
                name="Plan 1",
                price="99€",
                features=["Feature 1", "Feature 2"],
                is_featured=True
            )
        ]
    )
    assert pricing.module_type == "pricing"
    assert len(pricing.plans) == 1
    assert pricing.plans[0].is_featured is True


def test_page_creation():
    """Test de création d'une page complète."""
    page = Page(
        title="Test Page",
        description="Test description",
        sections=[
            Section(
                order=0,
                columns=[
                    Column(span=12, module=HeroModule(
                        title="Hero Title",
                        subtitle="Hero Subtitle"
                    ))
                ]
            )
        ]
    )
    assert page.title == "Test Page"
    assert len(page.sections) == 1
    assert page.sections[0].columns[0].span == 12


def test_page_rendering():
    """Test de rendu HTML d'une page."""
    page = Page(
        title="Test Render",
        sections=[
            Section(
                order=0,
                columns=[
                    Column(span=12, module=HeroModule(
                        title="Test",
                        subtitle="Subtitle"
                    ))
                ]
            )
        ]
    )
    html = render_page(page)

    # Vérifications basiques
    assert "<!DOCTYPE html>" in html
    assert "<title>Test Render</title>" in html
    assert "Test" in html
    assert "Subtitle" in html
    assert ":root {" in html  # CSS variables
    assert "var(--" in html  # Utilisation des variables


def test_multicolumn_section():
    """Test d'une section multi-colonnes."""
    section = Section(
        order=0,
        columns=[
            Column(span=4, module=HeroModule(title="Col 1")),
            Column(span=4, module=HeroModule(title="Col 2")),
            Column(span=4, module=HeroModule(title="Col 3"))
        ]
    )
    assert len(section.columns) == 3
    assert section.columns[0].span == 4
    assert section.columns[1].span == 4
    assert section.columns[2].span == 4


if __name__ == "__main__":
    # Run tests
    test_design_tokens_defaults()
    test_design_tokens_custom()
    test_hero_module()
    test_pricing_module()
    test_page_creation()
    test_page_rendering()
    test_multicolumn_section()
    print("✅ Tous les tests passent")
