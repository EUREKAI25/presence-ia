"""
Schémas Pydantic pour le Page Builder EURKAI.
Structure récursive : Page → Section → Column → Module → Element

v0.1 : HeroModule, PricingModule, TextModule, CTAModule, ProofModule, TestimonialsModule
v0.2 : SectionLayout + BlockUnion (nouveaux blocs) — compat v0.1 conservée
"""
from typing import List, Optional, Dict, Any, Literal, Union, Annotated
from pydantic import BaseModel, Field


class DesignTokens(BaseModel):
    """Tokens simplifiés v0.1 — conservé pour compat backward uniquement."""
    primary_color: str = Field(default="#667eea")
    secondary_color: str = Field(default="#764ba2")
    font_size_base: int = Field(default=16)
    line_height_base: float = Field(default=1.6)
    spacing_unit: int = Field(default=8)


class Element(BaseModel):
    """Élément atomique (texte, image, bouton, etc.)."""
    type: Literal["text", "button", "image", "badge", "link"] = "text"
    content: str = ""
    href: Optional[str] = None
    css_class: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class BaseModule(BaseModel):
    """Module de base (classe abstraite)."""
    module_type: str = Field(..., description="Type de module (hero, pricing, text, etc.)")
    css_class: Optional[str] = None
    custom_css: Optional[str] = None


class HeroModule(BaseModule):
    """Module Hero (badge + titre + sous-titre + 2 CTAs)."""
    module_type: Literal["hero"] = "hero"
    badge: Optional[str] = None
    title: str = Field(..., description="Titre principal")
    subtitle: str = Field(default="", description="Sous-titre")
    cta_primary: Optional[Dict[str, str]] = None  # {"label": "...", "href": "..."}
    cta_secondary: Optional[Dict[str, str]] = None


class PricingPlan(BaseModel):
    """Plan de tarification."""
    name: str
    price: str
    features: List[str] = Field(default_factory=list)
    cta_label: str = "Commencer"
    cta_href: str = "#"
    is_featured: bool = False


class PricingModule(BaseModule):
    """Module Pricing (grid de plans)."""
    module_type: Literal["pricing"] = "pricing"
    title: str = "Tarifs"
    subtitle: Optional[str] = None
    plans: List[PricingPlan] = Field(default_factory=list)


class TextModule(BaseModule):
    """Module texte libre (liste d'éléments)."""
    module_type: Literal["text"] = "text"
    elements: List[Element] = Field(default_factory=list)


class CTAModule(BaseModule):
    """Module call-to-action simple."""
    module_type: Literal["cta"] = "cta"
    title: str = Field(..., description="Titre du CTA")
    subtitle: Optional[str] = None
    button_label: str = "Commencer"
    button_href: str = "#"
    background_color: Optional[str] = None


class ProofModule(BaseModule):
    """Module preuves/stats."""
    module_type: Literal["proof"] = "proof"
    title: str = "Nos résultats"
    stats: List[Dict[str, str]] = Field(default_factory=list)  # [{"value": "95%", "label": "..."}]


class TestimonialItem(BaseModel):
    """Témoignage client."""
    name: str
    role: Optional[str] = None
    content: str
    avatar: Optional[str] = None


class TestimonialsModule(BaseModule):
    """Module témoignages."""
    module_type: Literal["testimonials"] = "testimonials"
    title: str = "Témoignages"
    items: List[TestimonialItem] = Field(default_factory=list)


# Type Union pour les modules v0.1 (résolu après définition de toutes les classes)
ModuleType = Union[
    HeroModule,
    PricingModule,
    TextModule,
    CTAModule,
    ProofModule,
    TestimonialsModule
]

# ── v0.2 : SectionLayout ────────────────────────────────────────────────────

SectionLayoutType = Literal["full", "two_col", "three_col", "asym_8_4", "hero_bleed"]


class SectionLayout(BaseModel):
    """Configuration du layout d'une section."""
    type: SectionLayoutType = "full"
    gap: Optional[str] = None
    align: Literal["start", "center", "end", "stretch"] = "stretch"


# ── Column — accepte v0.1 ModuleType ET v0.2 BlockUnion ─────────────────────

def _make_column_module_type():
    """Construit le type Union column_module combinant v0.1 et v0.2."""
    from ..blocks import BlockUnion
    return Union[ModuleType, BlockUnion]


class Column(BaseModel):
    """Colonne (1-12 span sur grid 12 colonnes)."""
    span: int = Field(default=12, ge=1, le=12, description="Largeur colonne (1-12)")
    module: Any = Field(..., description="Module v0.1 ou bloc v0.2")

    @classmethod
    def validate_module(cls, v):
        return v


class Section(BaseModel):
    """Section (conteneur de colonnes)."""
    id: Optional[str] = None
    bg_color: Optional[str] = None
    padding: Optional[str] = None
    enabled: bool = True
    order: int = 0
    layout: SectionLayout = Field(default_factory=SectionLayout)
    columns: List[Column] = Field(default_factory=list)


class Page(BaseModel):
    """Page complète."""
    title: str
    description: Optional[str] = None
    lang: str = "fr"
    theme: Dict = Field(
        default_factory=dict,
        description="ThemePreset dict (issu de theme_composer) — palette + style preset",
    )
    sections: List[Section] = Field(default_factory=list)

    class Config:
        validate_assignment = True
