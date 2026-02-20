"""
API publique du Page Builder EURKAI.
"""
from .core.schemas import (
    Page, Section, Column, DesignTokens,
    HeroModule, PricingModule, PricingPlan,
    TextModule, CTAModule, ProofModule,
    TestimonialsModule, TestimonialItem, Element
)
from .renderer.html import render_page as _render_page


class PageBuilder:
    """
    Builder de page modulaire EURKAI.

    Usage:
        >>> builder = PageBuilder()
        >>> page = builder.create_page(
        ...     title="Mon SaaS",
        ...     sections=[...]
        ... )
        >>> html = builder.render(page)
    """

    def __init__(self, design_tokens: DesignTokens | None = None):
        """
        Initialise le builder avec des tokens de design optionnels.

        Args:
            design_tokens: Tokens de design personnalisés
        """
        self.design_tokens = design_tokens or DesignTokens()

    def create_page(
        self,
        title: str,
        sections: list[Section],
        description: str | None = None,
        design_tokens: DesignTokens | None = None
    ) -> Page:
        """
        Crée une page.

        Args:
            title: Titre de la page
            sections: Liste de sections
            description: Description meta (SEO)
            design_tokens: Tokens de design (override instance)

        Returns:
            Page validée
        """
        return Page(
            title=title,
            description=description,
            design_tokens=design_tokens or self.design_tokens,
            sections=sections
        )

    def render(self, page: Page) -> str:
        """
        Rend une page en HTML complet.

        Args:
            page: Page à rendre

        Returns:
            HTML complet
        """
        return _render_page(page)


# Fonction raccourcie pour usage direct
def render_page(page: Page) -> str:
    """
    Rend une page en HTML complet (fonction raccourcie).

    Args:
        page: Page à rendre

    Returns:
        HTML complet
    """
    return _render_page(page)
