"""
Schéma du manifest JSON — format standardisé pour décrire une page complète.
ManifestPage → parse_manifest() → Page → render_page() → HTML

Le champ `theme` accepte un ThemePreset dict (produit par theme_composer) :
  - color_system   : palette extraite par scraping (primaire, secondaire…)
  - style_preset_name : "rounded"|"flat"|"elevated"|"minimal"|"bold"|"dark"
  - font_family_headings / font_family_body
  - bg_prominence  : "none"|"subtle"|"strong"|"dominant"
  - animation_style : "none"|"subtle"|"moderate"|"rich"
  - mood           : "minimal"|"playful"|"corporate"|"bold"|"elegant"|"dark"
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ManifestBlockConfig(BaseModel):
    """Configuration d'un bloc dans le manifest."""
    block_type: str
    structure: Dict[str, Any] = Field(default_factory=dict)
    seed: Dict[str, Any] = Field(default_factory=dict)
    css_class: Optional[str] = None
    id: Optional[str] = None


class ManifestColumn(BaseModel):
    span: int = 12
    block: ManifestBlockConfig


class ManifestSection(BaseModel):
    key: str
    enabled: bool = True
    order: int = 0
    bg_color: Optional[str] = None
    layout_type: Optional[str] = None
    columns: List[ManifestColumn] = Field(default_factory=list)


class ManifestPage(BaseModel):
    """
    Format manifest JSON complet pour une page.

    Exemple minimal :
    {
      "page_type": "landing",
      "lang": "fr",
      "title": "Audit IA - {city}",
      "theme": {
        "color_system": {
          "primary":   {"base": "rgb(102,126,234)", "light": "rgb(118,142,250)", "dark": "rgb(85,104,211)"},
          "secondary": {"base": "rgb(118,75,162)",  "light": "rgb(134,91,178)",  "dark": "rgb(102,59,146)"}
        },
        "font_family_headings": "Inter",
        "font_family_body": "Inter",
        "style_preset_name": "rounded",
        "animation_style": "subtle",
        "bg_prominence": "none"
      },
      "sections": [...],
      "placeholder_context": {"city": "Rennes", "price": "97€"}
    }
    """
    page_type: str = "landing"
    lang: str = "fr"
    title: str = ""
    description: Optional[str] = None
    theme: Dict[str, Any] = Field(
        default_factory=dict,
        description="ThemePreset dict (palette + style preset — voir theme_composer)",
    )
    sections: List[ManifestSection] = Field(default_factory=list)
    placeholder_context: Dict[str, str] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)
