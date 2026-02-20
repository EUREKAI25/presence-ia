"""
Générateur de Design System EURKAI.
Dérive 60+ CSS variables à partir de 4 valeurs de base (2 couleurs + font-size + line-height).
"""
from .schemas import DesignTokens
from typing import Dict


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convertit #RRGGBB en (R, G, B)."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def lighten(hex_color: str, percent: int = 20) -> str:
    """Éclaircit une couleur de X%."""
    r, g, b = hex_to_rgb(hex_color)
    factor = 1 + (percent / 100)
    r = min(255, int(r * factor))
    g = min(255, int(g * factor))
    b = min(255, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def darken(hex_color: str, percent: int = 20) -> str:
    """Assombrit une couleur de X%."""
    r, g, b = hex_to_rgb(hex_color)
    factor = 1 - (percent / 100)
    r = max(0, int(r * factor))
    g = max(0, int(g * factor))
    b = max(0, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def generate_css_variables(tokens: DesignTokens) -> str:
    """
    Génère les CSS variables dérivées à partir des tokens.

    Returns:
        CSS :root {} avec toutes les variables dérivées
    """
    primary = tokens.primary_color
    secondary = tokens.secondary_color
    base_font = tokens.font_size_base
    base_line = tokens.line_height_base
    spacing = tokens.spacing_unit

    # Dérivation couleurs
    primary_light = lighten(primary, 15)
    primary_dark = darken(primary, 15)
    secondary_light = lighten(secondary, 15)
    secondary_dark = darken(secondary, 15)

    # Dérivation espacements (multiples de spacing_unit)
    spacing_vars = {
        "xs": spacing // 2,
        "sm": spacing,
        "md": spacing * 2,
        "lg": spacing * 3,
        "xl": spacing * 4,
        "2xl": spacing * 6,
        "3xl": spacing * 8,
    }

    # Dérivation typographie (multiples de font_size_base)
    font_vars = {
        "xs": round(base_font * 0.75),
        "sm": round(base_font * 0.875),
        "md": base_font,
        "lg": round(base_font * 1.125),
        "xl": round(base_font * 1.25),
        "2xl": round(base_font * 1.5),
        "3xl": round(base_font * 1.875),
        "4xl": round(base_font * 2.25),
    }

    css = f"""
:root {{
  /* === Couleurs === */
  --color-primary: {primary};
  --color-primary-light: {primary_light};
  --color-primary-dark: {primary_dark};
  --color-secondary: {secondary};
  --color-secondary-light: {secondary_light};
  --color-secondary-dark: {secondary_dark};

  /* Couleurs sémantiques */
  --color-text: #2d3748;
  --color-text-light: #718096;
  --color-bg: #ffffff;
  --color-bg-gray: #f7fafc;
  --color-border: #e2e8f0;

  /* === Espacements === */
  --spacing-xs: {spacing_vars['xs']}px;
  --spacing-sm: {spacing_vars['sm']}px;
  --spacing-md: {spacing_vars['md']}px;
  --spacing-lg: {spacing_vars['lg']}px;
  --spacing-xl: {spacing_vars['xl']}px;
  --spacing-2xl: {spacing_vars['2xl']}px;
  --spacing-3xl: {spacing_vars['3xl']}px;

  /* === Typographie === */
  --font-size-xs: {font_vars['xs']}px;
  --font-size-sm: {font_vars['sm']}px;
  --font-size-md: {font_vars['md']}px;
  --font-size-lg: {font_vars['lg']}px;
  --font-size-xl: {font_vars['xl']}px;
  --font-size-2xl: {font_vars['2xl']}px;
  --font-size-3xl: {font_vars['3xl']}px;
  --font-size-4xl: {font_vars['4xl']}px;

  --line-height-base: {base_line};
  --line-height-tight: 1.25;
  --line-height-relaxed: 1.75;

  --font-family-base: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;

  /* === Autres === */
  --border-radius-sm: 4px;
  --border-radius-md: 8px;
  --border-radius-lg: 12px;
  --border-radius-xl: 16px;

  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);

  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 200ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1);

  /* Breakpoints (utilisés dans media queries) */
  --breakpoint-mobile: 640px;
  --breakpoint-tablet: 768px;
  --breakpoint-desktop: 1024px;
  --breakpoint-wide: 1280px;
}}
""".strip()

    return css


def generate_utility_classes() -> str:
    """
    Génère les classes utilitaires (grid, boutons, etc.).

    Returns:
        CSS avec classes réutilisables
    """
    css = """
/* === Reset & Base === */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-family-base);
  font-size: var(--font-size-md);
  line-height: var(--line-height-base);
  color: var(--color-text);
  background: var(--color-bg);
}

/* === Grid System (12 colonnes) === */
.grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: var(--spacing-md);
}

.col-span-1 { grid-column: span 1; }
.col-span-2 { grid-column: span 2; }
.col-span-3 { grid-column: span 3; }
.col-span-4 { grid-column: span 4; }
.col-span-5 { grid-column: span 5; }
.col-span-6 { grid-column: span 6; }
.col-span-7 { grid-column: span 7; }
.col-span-8 { grid-column: span 8; }
.col-span-9 { grid-column: span 9; }
.col-span-10 { grid-column: span 10; }
.col-span-11 { grid-column: span 11; }
.col-span-12 { grid-column: span 12; }

/* Responsive : mobile 1 colonne */
@media (max-width: 768px) {
  .grid {
    grid-template-columns: 1fr !important;
  }
  .col-span-1, .col-span-2, .col-span-3, .col-span-4,
  .col-span-5, .col-span-6, .col-span-7, .col-span-8,
  .col-span-9, .col-span-10, .col-span-11, .col-span-12 {
    grid-column: span 1;
  }
}

/* === Container === */
.container {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--spacing-md);
}

/* === Sections === */
.section {
  padding: var(--spacing-3xl) 0;
}

/* === Boutons === */
.btn {
  display: inline-block;
  padding: var(--spacing-sm) var(--spacing-lg);
  font-size: var(--font-size-md);
  font-weight: 600;
  text-decoration: none;
  border-radius: var(--border-radius-md);
  transition: all var(--transition-base);
  cursor: pointer;
  border: none;
}

.btn-primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark));
  color: white;
  box-shadow: var(--shadow-md);
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.btn-secondary {
  background: var(--color-bg-gray);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}

.btn-secondary:hover {
  background: var(--color-bg);
  border-color: var(--color-primary);
}

/* === Typographie === */
h1, h2, h3, h4, h5, h6 {
  font-weight: 700;
  line-height: var(--line-height-tight);
  color: var(--color-text);
}

h1 { font-size: var(--font-size-4xl); margin-bottom: var(--spacing-md); }
h2 { font-size: var(--font-size-3xl); margin-bottom: var(--spacing-md); }
h3 { font-size: var(--font-size-2xl); margin-bottom: var(--spacing-sm); }

p { margin-bottom: var(--spacing-md); }

/* === Utilitaires === */
.text-center { text-align: center; }
.text-gradient {
  background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
""".strip()

    return css
