"""
Theme Composer — transforme les tokens bruts en ThemePreset cohérent.
Utilise les règles d'harmonie + analyse LLM (Claude).

ThemePreset = palette (scrapée) + style_preset (choisi) + métadonnées
La palette et le style sont indépendants : on peut prendre la palette
d'un site minimaliste et lui appliquer le style "elevated".
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from anthropic import Anthropic
import json
import os

from .harmony_rules import HarmonyRules
from .font_matcher import FontMatcher
from .style_presets import STYLE_PRESETS, get_style_preset, StylePresetName


class ThemePreset(BaseModel):
    """
    Seed propriétaire capturant l'esprit d'un design.

    Deux composantes indépendantes :
    - color_system + typography  → extraits du scraping (ou définis manuellement)
    - style_preset               → choisi librement (rounded, flat, elevated…)
    """

    # ── Métadonnées ──────────────────────────────────────────────────────────
    name: str = "Untitled Theme"
    source_url: Optional[str] = None
    mood: str = "neutral"            # minimal | playful | corporate | bold | elegant | dark
    use_cases: List[str] = Field(default_factory=lambda: ["landing"])
    # use_cases multiples : ["landing", "saas"] — guide les contraintes de rendu
    # (ex: pas de video background si "checkout" dans use_cases)

    # ── Palette — issue du scraping ou définie manuellement ──────────────────
    color_system: Dict = Field(default_factory=dict)
    # {"primary": {"base": "rgb(...)", "light": "...", "dark": "..."}, "secondary": {...}, ...}

    font_family_headings: str = "Inter"
    font_family_body: str = "Inter"
    font_google_url: str = ""
    font_weights: Dict[str, int] = Field(default_factory=lambda: {
        "normal": 400, "medium": 500, "bold": 700
    })

    # ── Style preset — choisi indépendamment de la palette ───────────────────
    style_preset_name: StylePresetName = "rounded"
    # Le preset complet est résolu dynamiquement depuis STYLE_PRESETS
    # Peut être surchargé propriété par propriété via style_overrides
    style_overrides: Dict = Field(default_factory=dict)
    # ex: {"radius": {"md": "20px"}} pour surcharger uniquement le radius md

    # ── Background ───────────────────────────────────────────────────────────
    bg_prominence: str = "none"      # none | subtle | strong | dominant
    # none     → couleurs plates, pas d'image de fond
    # subtle   → dégradé léger en fond
    # strong   → image de fond sur sections clés
    # dominant → le background EST le design principal (hero immersif)

    bg_default_src: Optional[str] = None
    # URL de l'image/vidéo de fond par défaut (injectée si bg_prominence != "none")

    # ── Animation ────────────────────────────────────────────────────────────
    animation_style: str = "subtle"  # none | subtle | moderate | rich
    # Dérivé automatiquement du style_preset si non précisé

    # ── Descriptions (générées par LLM) ──────────────────────────────────────
    harmony_description: str = ""
    key_characteristics: List[str] = Field(default_factory=list)

    def get_style(self) -> dict:
        """Retourne le style preset résolu avec overrides appliqués."""
        base = get_style_preset(self.style_preset_name).copy()
        if self.style_overrides:
            _deep_merge(base, self.style_overrides)
        return base

    def allows_video_bg(self) -> bool:
        """True si video background est cohérent avec les use_cases."""
        blocking = {"checkout", "form", "tunnel"}
        return not any(uc in blocking for uc in self.use_cases)


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge récursif de override dans base (in-place)."""
    for key, val in override.items():
        if isinstance(val, dict) and key in base and isinstance(base[key], dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
    return base


class ThemeComposer:
    """Compositeur de thèmes à partir de tokens bruts."""

    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.anthropic_api_key) if self.anthropic_api_key else None
        self.harmony = HarmonyRules()
        self.font_matcher = FontMatcher()

    def compose(
        self,
        raw_data: Dict,
        screenshot_base64: Optional[str] = None,
        style_preset_name: StylePresetName = "rounded",
    ) -> ThemePreset:
        """
        Compose un ThemePreset à partir de données brutes.

        Args:
            raw_data:            Données du scraper (couleurs, fonts, composants…)
            screenshot_base64:   Screenshot pour analyse LLM (optionnel)
            style_preset_name:   Style à appliquer (indépendant de la palette)

        Returns:
            ThemePreset complet : palette scrapée + style choisi
        """
        # 1. Palette — couleurs
        color_system = self.harmony.detect_color_relationships(
            raw_data.get("colors", []) + raw_data.get("backgrounds", [])
        )

        # 2. Typographie
        detected_fonts = raw_data.get("fonts", [])
        font_headings = self.font_matcher.match_font(detected_fonts[0]) if detected_fonts else "Inter"
        font_body = self.font_matcher.match_font(detected_fonts[1] if len(detected_fonts) > 1 else detected_fonts[0]) if detected_fonts else "Inter"
        font_google_url = self.font_matcher.get_font_url(font_headings)

        # 3. Analyse LLM (mood, use_cases, bg_prominence, animation)
        semantic = {}
        if self.client and screenshot_base64:
            semantic = self._analyze_with_llm(
                screenshot_base64=screenshot_base64,
                color_system=color_system,
                components=raw_data.get("component_styles", {}),
            )

        # 4. Dériver animation_style du style_preset si LLM ne l'a pas détecté
        preset_rules = get_style_preset(style_preset_name)
        animation_style = semantic.get("animation_style", preset_rules.get("animation", "subtle"))

        return ThemePreset(
            name=semantic.get("name", "Untitled Theme"),
            source_url=raw_data.get("url"),
            mood=semantic.get("mood", "neutral"),
            use_cases=semantic.get("use_cases", ["landing"]),
            color_system=color_system,
            font_family_headings=font_headings,
            font_family_body=font_body,
            font_google_url=font_google_url,
            style_preset_name=style_preset_name,
            bg_prominence=semantic.get("bg_prominence", "none"),
            animation_style=animation_style,
            harmony_description=semantic.get("harmony_description", ""),
            key_characteristics=semantic.get("key_characteristics", []),
        )

    def _analyze_with_llm(
        self,
        screenshot_base64: str,
        color_system: Dict,
        components: Dict,
    ) -> Dict:
        """
        Analyse sémantique via Claude.
        Détecte : mood, use_cases, bg_prominence, animation_style.
        """
        if not self.client:
            return {}

        primary = color_system.get("primary", {}).get("base", "N/A")

        prompt = f"""Analyse ce site web. Retourne UNIQUEMENT un JSON valide :
{{
  "name": "nom suggestif du thème",
  "mood": "minimal|playful|corporate|bold|elegant|dark",
  "use_cases": ["landing"|"saas"|"ecommerce"|"blog"|"portfolio"|"checkout"],
  "bg_prominence": "none|subtle|strong|dominant",
  "animation_style": "none|subtle|moderate|rich",
  "harmony_description": "2-3 phrases sur l'harmonie visuelle",
  "key_characteristics": ["carac 1", "carac 2", "carac 3"]
}}

Couleur primaire détectée : {primary}

Critères bg_prominence :
- none      → fonds blancs/gris unis, le contenu prime
- subtle    → léger dégradé ou texture de fond
- strong    → images ou patterns utilisés en fond de sections
- dominant  → background est l'élément visuel principal (hero immersif)

Critères animation_style :
- none     → site statique, transitions inexistantes
- subtle   → micro-interactions discrètes
- moderate → animations d'entrée, hovers prononcés
- rich     → parallaxe, keyframes, interactions complexes
"""
        try:
            msg = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=800,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": screenshot_base64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            text = msg.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except Exception as e:
            print(f"⚠️  LLM analysis error: {e}")
            return {}

    def save_preset(self, preset: ThemePreset, output_path: str):
        """Sauvegarde le preset en JSON."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(preset.model_dump(), f, indent=2, ensure_ascii=False)
