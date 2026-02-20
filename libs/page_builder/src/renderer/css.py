"""
Générateur CSS v0.2 — CSS variables (via ThemeGenerator) + SCSS compilé (libsass).

Pipeline :
  ThemeGenerator().generate_variables(page.theme)  →  :root { --color-primary: ...; ... }
  get_compiled_scss()                               →  reset + grid + blocs (compilé une fois)
  generate_page_css(page)                           →  variables + SCSS
"""
from pathlib import Path
from ..core.schemas import Page

_SCSS_CACHE: dict = {}


def get_compiled_scss() -> str:
    """Compile main.scss une seule fois, met en cache (libsass requis)."""
    if "main" not in _SCSS_CACHE:
        import sass
        main_scss = Path(__file__).parent.parent / "scss" / "main.scss"
        _SCSS_CACHE["main"] = sass.compile(
            filename=str(main_scss),
            output_style="compressed",
        )
    return _SCSS_CACHE["main"]


def generate_css_variables(theme: dict) -> str:
    """
    Génère le bloc :root { ... } à partir d'un ThemePreset dict.

    Utilise ThemeGenerator (theme_generator) si disponible,
    sinon génère un :root minimal depuis le color_system.
    """
    try:
        from theme_generator.generator import ThemeGenerator
        return ThemeGenerator().generate_variables(theme)
    except ImportError:
        return _fallback_variables(theme)


def generate_page_css(page: Page) -> str:
    """
    CSS complet d'une page :
    1. :root { CSS variables } — depuis page.theme via ThemeGenerator
    2. SCSS compilé (reset + grid + blocs)
    """
    css_vars = generate_css_variables(page.theme)
    return css_vars + "\n\n" + get_compiled_scss()


def invalidate_scss_cache():
    """Force la recompilation SCSS (dev only)."""
    _SCSS_CACHE.clear()


# ── Fallback minimal si theme_generator non installé ─────────────────────────

def _fallback_variables(theme: dict) -> str:
    """
    Génère un :root basique depuis le color_system du ThemePreset dict.
    Utilisé si le package theme_generator n'est pas installé.
    """
    cs      = theme.get("color_system", {})
    primary = cs.get("primary",   {})
    sec     = cs.get("secondary", {})

    p_base  = primary.get("base",  "rgb(102, 126, 234)")
    p_light = primary.get("light", "rgb(118, 142, 250)")
    p_dark  = primary.get("dark",  "rgb(85, 104, 211)")
    s_base  = sec.get("base",  "rgb(118, 75, 162)")
    s_light = sec.get("light", "rgb(134, 91, 178)")
    s_dark  = sec.get("dark",  "rgb(102, 59, 146)")

    import re
    m   = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", p_base)
    rgb = f"{m.group(1)}, {m.group(2)}, {m.group(3)}" if m else "102, 126, 234"

    mood    = theme.get("mood", "neutral")
    is_dark = mood == "dark"
    color_text      = "rgb(240, 240, 245)" if is_dark else "rgb(45, 55, 72)"
    color_text_light = "rgb(160, 160, 180)" if is_dark else "rgb(113, 128, 150)"
    color_bg        = "rgb(18, 18, 28)"    if is_dark else "rgb(255, 255, 255)"
    color_bg_subtle = "rgb(28, 28, 42)"    if is_dark else "rgb(247, 250, 252)"
    color_border    = "rgb(50, 50, 70)"    if is_dark else "rgb(226, 232, 240)"

    fh = theme.get("font_family_headings", "Inter")
    fb = theme.get("font_family_body", "Inter")

    return f""":root {{
  --color-primary:       {p_base};
  --color-primary-light: {p_light};
  --color-primary-dark:  {p_dark};
  --color-primary-rgb:   {rgb};
  --color-secondary:       {s_base};
  --color-secondary-light: {s_light};
  --color-secondary-dark:  {s_dark};
  --color-text:       {color_text};
  --color-text-light: {color_text_light};
  --color-bg:         {color_bg};
  --color-bg-gray:    {color_bg_subtle};
  --color-border:     {color_border};
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-lg: 0 12px 28px rgba(0,0,0,0.12);
  --shadow-xl: 0 24px 48px rgba(0,0,0,0.18);
  --border-radius-sm: 6px;
  --border-radius-md: 12px;
  --border-radius-lg: 20px;
  --border-radius-xl: 32px;
  --border-width: 1px;
  --font-family-headings: '{fh}', sans-serif;
  --font-family-body:     '{fb}', sans-serif;
  --font-size-xs:  12px; --font-size-sm: 14px; --font-size-md: 16px;
  --font-size-lg:  18px; --font-size-xl: 20px; --font-size-2xl: 24px;
  --font-size-3xl: 30px; --font-size-4xl: 36px;
  --font-weight-normal: 400; --font-weight-medium: 500; --font-weight-bold: 700;
  --line-height-tight: 1.25; --line-height-base: 1.6; --line-height-relaxed: 1.75;
  --spacing-xs: 4px; --spacing-sm: 8px; --spacing-md: 16px; --spacing-lg: 24px;
  --spacing-xl: 32px; --spacing-2xl: 48px; --spacing-3xl: 64px;
  --transition-speed: 200ms;
  --transition-easing: cubic-bezier(0.4, 0, 0.2, 1);
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 200ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1);
  --hover-lift: -3px;
  --hover-scale: 1.01;
}}"""
