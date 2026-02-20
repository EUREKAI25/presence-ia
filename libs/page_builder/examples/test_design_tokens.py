"""
Test du système de design tokens.
Génère 3 pages identiques avec des couleurs différentes pour démontrer la dérivation automatique.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import (
    Page, Section, Column, DesignTokens,
    HeroModule, PricingModule, PricingPlan, CTAModule,
    render_page
)


def create_test_page(tokens: DesignTokens, suffix: str) -> str:
    """Crée une page de test avec les tokens donnés."""
    page = Page(
        title=f"Test Design {suffix}",
        design_tokens=tokens,
        sections=[
            Section(
                order=0,
                columns=[
                    Column(span=12, module=HeroModule(
                        badge="🎨 Test Design System",
                        title="Même structure, couleurs différentes",
                        subtitle="Cette page utilise le design system dérivé automatiquement",
                        cta_primary={"label": "Bouton primaire", "href": "#"},
                        cta_secondary={"label": "Bouton secondaire", "href": "#"}
                    ))
                ]
            ),
            Section(
                order=1,
                columns=[
                    Column(span=12, module=PricingModule(
                        title="Tarifs (mêmes données, design dérivé)",
                        plans=[
                            PricingPlan(
                                name="Plan A",
                                price="49€",
                                features=["Feature 1", "Feature 2"],
                                is_featured=True
                            )
                        ]
                    ))
                ]
            )
        ]
    )
    return render_page(page)


def main():
    output_dir = Path(__file__).parent

    # Test 1 : Violet (défaut)
    tokens_violet = DesignTokens(
        primary_color="#667eea",
        secondary_color="#764ba2",
        font_size_base=16
    )
    html_violet = create_test_page(tokens_violet, "Violet")
    (output_dir / "test_violet.html").write_text(html_violet, encoding="utf-8")
    print("✅ test_violet.html généré")

    # Test 2 : Rouge/Orange
    tokens_red = DesignTokens(
        primary_color="#e94560",
        secondary_color="#ff7043",
        font_size_base=16
    )
    html_red = create_test_page(tokens_red, "Rouge")
    (output_dir / "test_red.html").write_text(html_red, encoding="utf-8")
    print("✅ test_red.html généré")

    # Test 3 : Bleu/Cyan
    tokens_blue = DesignTokens(
        primary_color="#3b82f6",
        secondary_color="#06b6d4",
        font_size_base=18  # Plus gros aussi
    )
    html_blue = create_test_page(tokens_blue, "Bleu")
    (output_dir / "test_blue.html").write_text(html_blue, encoding="utf-8")
    print("✅ test_blue.html généré (font-size: 18px)")

    print("\n🎨 Ouvrir les 3 fichiers pour comparer :")
    print(f"   open {output_dir}/test_violet.html")
    print(f"   open {output_dir}/test_red.html")
    print(f"   open {output_dir}/test_blue.html")


if __name__ == "__main__":
    main()
