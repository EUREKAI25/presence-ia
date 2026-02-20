"""
Style Presets — sets de règles visuelles cohérentes.

Un style preset est indépendant de la palette de couleurs.
On peut prendre la palette d'un site minimaliste et lui appliquer le style "elevated",
ou prendre une palette colorée et l'appliquer en "flat".

Les éléments d'un preset fonctionnent ensemble :
  - rounded  → boutons, cards, inputs tous arrondis + ombres douces
  - flat     → tout carré + aucune ombre + bordures à la place
  - elevated → arrondi prononcé + ombres fortes + depth
  - minimal  → arrondi discret + ombres quasi inexistantes + espacement généreux
  - bold     → ombres "dures" (offset coloré) + transitions rapides + contraste fort
  - dark     → ombres lumineuses (glow) + fond sombre
"""
from typing import Dict, Literal

StylePresetName = Literal["rounded", "flat", "elevated", "minimal", "bold", "dark"]

# Chaque preset = dict de règles qui se traduisent en CSS variables
STYLE_PRESETS: Dict[str, dict] = {

    "rounded": {
        "radius":        {"sm": "6px",  "md": "12px", "lg": "20px", "xl": "32px"},
        "shadow":        {
            "sm": "0 1px 3px rgba(0,0,0,0.06)",
            "md": "0 4px 12px rgba(0,0,0,0.08)",
            "lg": "0 12px 28px rgba(0,0,0,0.12)",
            "xl": "0 24px 48px rgba(0,0,0,0.18)",
        },
        "btn_variant":        "filled",
        "animation":          "subtle",
        "transition_speed":   "200ms",
        "transition_easing":  "cubic-bezier(0.4, 0, 0.2, 1)",
        "hover_lift":         "-3px",
        "hover_scale":        "1.01",
        "border_width":       "1px",
    },

    "flat": {
        "radius":        {"sm": "0",   "md": "0",   "lg": "0",   "xl": "0"},
        "shadow":        {"sm": "none","md": "none","lg": "none","xl": "none"},
        "btn_variant":        "outline",
        "animation":          "none",
        "transition_speed":   "0ms",
        "transition_easing":  "linear",
        "hover_lift":         "0",
        "hover_scale":        "1",
        "border_width":       "2px",
    },

    "elevated": {
        "radius":        {"sm": "8px",  "md": "16px", "lg": "24px", "xl": "40px"},
        "shadow":        {
            "sm": "0 2px 8px rgba(0,0,0,0.08)",
            "md": "0 8px 24px rgba(0,0,0,0.12)",
            "lg": "0 16px 48px rgba(0,0,0,0.16)",
            "xl": "0 32px 64px rgba(0,0,0,0.22)",
        },
        "btn_variant":        "filled",
        "animation":          "moderate",
        "transition_speed":   "250ms",
        "transition_easing":  "cubic-bezier(0.34, 1.56, 0.64, 1)",  # spring
        "hover_lift":         "-5px",
        "hover_scale":        "1.02",
        "border_width":       "0",
    },

    "minimal": {
        "radius":        {"sm": "2px", "md": "4px", "lg": "8px", "xl": "12px"},
        "shadow":        {
            "sm": "none",
            "md": "0 1px 4px rgba(0,0,0,0.04)",
            "lg": "0 2px 8px rgba(0,0,0,0.06)",
            "xl": "0 4px 16px rgba(0,0,0,0.08)",
        },
        "btn_variant":        "ghost",
        "animation":          "none",
        "transition_speed":   "150ms",
        "transition_easing":  "ease",
        "hover_lift":         "0",
        "hover_scale":        "1",
        "border_width":       "1px",
    },

    "bold": {
        "radius":        {"sm": "4px", "md": "8px", "lg": "12px", "xl": "20px"},
        # Ombres "dures" décalées — style néo-brutaliste
        "shadow":        {
            "sm": "2px 2px 0 var(--color-text)",
            "md": "4px 4px 0 var(--color-text)",
            "lg": "6px 6px 0 var(--color-text)",
            "xl": "8px 8px 0 var(--color-text)",
        },
        "btn_variant":        "filled",
        "animation":          "rich",
        "transition_speed":   "120ms",
        "transition_easing":  "cubic-bezier(0.4, 0, 0.2, 1)",
        "hover_lift":         "-2px",
        "hover_scale":        "1.03",
        "border_width":       "2px",
    },

    "dark": {
        "radius":        {"sm": "6px",  "md": "10px", "lg": "16px", "xl": "24px"},
        # Ombres lumineuses (glow) — couleur primaire
        "shadow":        {
            "sm": "0 0 8px rgba(var(--color-primary-rgb), 0.2)",
            "md": "0 0 20px rgba(var(--color-primary-rgb), 0.25)",
            "lg": "0 0 40px rgba(var(--color-primary-rgb), 0.30)",
            "xl": "0 0 60px rgba(var(--color-primary-rgb), 0.35)",
        },
        "btn_variant":        "filled",
        "animation":          "subtle",
        "transition_speed":   "200ms",
        "transition_easing":  "cubic-bezier(0.4, 0, 0.2, 1)",
        "hover_lift":         "-2px",
        "hover_scale":        "1.01",
        "border_width":       "1px",
    },
}


def get_style_preset(name: str) -> dict:
    """Retourne le preset par nom, fallback sur 'rounded'."""
    return STYLE_PRESETS.get(name, STYLE_PRESETS["rounded"])
