"""
Theme Generator — génère le CSS complet ou les variables seules à partir d'un ThemePreset.

generate(preset)           → CSS complet (variables + reset + utilities + composants)
generate_variables(preset) → uniquement le bloc :root { ... }
                             utilisé par page_builder qui gère ses propres blocs via SCSS
"""
from typing import Dict


class ThemeGenerator:
    """Générateur de CSS harmonieux à partir d'un ThemePreset."""

    def generate(self, preset: Dict) -> str:
        """CSS complet (variables + reset + utilities + composants)."""
        parts = []
        if preset.get("font_google_url"):
            parts.append(f"@import url('{preset['font_google_url']}');")
        parts.append(self.generate_variables(preset))
        parts.append(self._generate_reset())
        parts.append(self._generate_utilities())
        parts.append(self._generate_components(preset))
        return "\n\n".join(parts)

    def generate_variables(self, preset: Dict) -> str:
        """
        Génère UNIQUEMENT le bloc :root { ... }.
        Point d'entrée pour page_builder (qui gère le reste via SCSS).
        """
        # ── Résolution du style preset ────────────────────────────────────────
        style = self._resolve_style(preset)

        # ── Couleurs ──────────────────────────────────────────────────────────
        cs        = preset.get("color_system", {})
        primary   = cs.get("primary",   {})
        secondary = cs.get("secondary", {})

        p_base  = primary.get("base",  "rgb(102, 126, 234)")
        p_light = primary.get("light", "rgb(118, 142, 250)")
        p_dark  = primary.get("dark",  "rgb(85, 104, 211)")
        s_base  = secondary.get("base",  "rgb(118, 75, 162)")
        s_light = secondary.get("light", "rgb(134, 91, 178)")
        s_dark  = secondary.get("dark",  "rgb(102, 59, 146)")

        p_rgb = _rgb_str_to_components(p_base)

        # Couleurs sémantiques — adaptées si mood=dark
        is_dark = preset.get("mood") == "dark"
        color_text       = "rgb(240, 240, 245)"  if is_dark else "rgb(45, 55, 72)"
        color_text_light = "rgb(160, 160, 180)"  if is_dark else "rgb(113, 128, 150)"
        color_bg         = "rgb(18, 18, 28)"     if is_dark else "rgb(255, 255, 255)"
        color_bg_subtle  = "rgb(28, 28, 42)"     if is_dark else "rgb(247, 250, 252)"
        color_border     = "rgb(50, 50, 70)"     if is_dark else "rgb(226, 232, 240)"

        # ── Style preset → variables ──────────────────────────────────────────
        radius = style.get("radius", {})
        shadow = style.get("shadow", {})
        anim   = preset.get("animation_style", style.get("animation", "subtle"))

        radius_sm = radius.get("sm", "4px")
        radius_md = radius.get("md", "8px")
        radius_lg = radius.get("lg", "12px")
        radius_xl = radius.get("xl", "16px")

        shadow_sm = shadow.get("sm", "0 1px 2px rgba(0,0,0,0.05)")
        shadow_md = shadow.get("md", "0 4px 6px rgba(0,0,0,0.1)")
        shadow_lg = shadow.get("lg", "0 10px 15px rgba(0,0,0,0.1)")
        shadow_xl = shadow.get("xl", "0 20px 25px rgba(0,0,0,0.1)")

        border_width = style.get("border_width", "1px")
        hover_lift   = style.get("hover_lift", "-2px")
        hover_scale  = style.get("hover_scale", "1.01")

        t_speed, t_easing = _animation_tokens(anim, style)

        # ── Typographie ───────────────────────────────────────────────────────
        font_h = preset.get("font_family_headings", "Inter")
        font_b = preset.get("font_family_body", "Inter")
        fw     = preset.get("font_weights", {"normal": 400, "medium": 500, "bold": 700})

        preset_name = preset.get("style_preset_name", "rounded")

        return f""":root {{
  /* === Couleurs primaires === */
  --color-primary:       {p_base};
  --color-primary-light: {p_light};
  --color-primary-dark:  {p_dark};
  --color-primary-rgb:   {p_rgb};

  --color-secondary:       {s_base};
  --color-secondary-light: {s_light};
  --color-secondary-dark:  {s_dark};

  /* === Couleurs sémantiques === */
  --color-text:       {color_text};
  --color-text-light: {color_text_light};
  --color-bg:         {color_bg};
  --color-bg-gray:    {color_bg_subtle};
  --color-border:     {color_border};

  /* === Shadows ({preset_name} style) === */
  --shadow-sm: {shadow_sm};
  --shadow-md: {shadow_md};
  --shadow-lg: {shadow_lg};
  --shadow-xl: {shadow_xl};

  /* === Border Radius === */
  --border-radius-sm: {radius_sm};
  --border-radius-md: {radius_md};
  --border-radius-lg: {radius_lg};
  --border-radius-xl: {radius_xl};
  --border-width:     {border_width};

  /* === Typographie === */
  --font-family-headings: '{font_h}', sans-serif;
  --font-family-body:     '{font_b}', sans-serif;

  --font-size-xs:  12px;
  --font-size-sm:  14px;
  --font-size-md:  16px;
  --font-size-lg:  18px;
  --font-size-xl:  20px;
  --font-size-2xl: 24px;
  --font-size-3xl: 30px;
  --font-size-4xl: 36px;

  --font-weight-normal: {fw.get('normal', 400)};
  --font-weight-medium: {fw.get('medium', 500)};
  --font-weight-bold:   {fw.get('bold',   700)};

  --line-height-tight:   1.25;
  --line-height-base:    1.6;
  --line-height-relaxed: 1.75;

  /* === Espacement === */
  --spacing-xs:  4px;
  --spacing-sm:  8px;
  --spacing-md:  16px;
  --spacing-lg:  24px;
  --spacing-xl:  32px;
  --spacing-2xl: 48px;
  --spacing-3xl: 64px;

  /* === Animations ({anim}) === */
  --transition-speed:  {t_speed};
  --transition-easing: {t_easing};
  --transition-fast:   {_scale_speed(t_speed, 0.75)} {t_easing};
  --transition-base:   {t_speed} {t_easing};
  --transition-slow:   {_scale_speed(t_speed, 1.5)} {t_easing};
  --hover-lift:        {hover_lift};
  --hover-scale:       {hover_scale};
}}"""

    # ── Méthodes internes (CSS complet) ──────────────────────────────────────

    def _resolve_style(self, preset: Dict) -> dict:
        try:
            from theme_composer.style_presets import get_style_preset
            style = get_style_preset(preset.get("style_preset_name", "rounded")).copy()
        except ImportError:
            style = _DEFAULT_STYLE.copy()

        overrides = preset.get("style_overrides", {})
        if overrides:
            _deep_merge(style, overrides)
        return style

    def _generate_reset(self) -> str:
        return """/* === Reset & Base === */
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  font-family: var(--font-family-body);
  font-size: var(--font-size-md);
  line-height: var(--line-height-base);
  color: var(--color-text);
  background: var(--color-bg);
  -webkit-font-smoothing: antialiased;
}
h1,h2,h3,h4,h5,h6 {
  font-family: var(--font-family-headings);
  font-weight: var(--font-weight-bold);
  line-height: var(--line-height-tight);
  color: var(--color-text);
}
h1 { font-size: var(--font-size-4xl); margin-bottom: var(--spacing-md); }
h2 { font-size: var(--font-size-3xl); margin-bottom: var(--spacing-md); }
h3 { font-size: var(--font-size-2xl); margin-bottom: var(--spacing-sm); }
p  { margin-bottom: var(--spacing-md); line-height: var(--line-height-relaxed); }
a  { color: var(--color-primary); text-decoration: none; }
a:hover { color: var(--color-primary-dark); }
img { max-width: 100%; height: auto; display: block; }"""

    def _generate_utilities(self) -> str:
        cols = "\n".join(
            f".col-span-{i} {{ grid-column: span {i}; }}" for i in range(1, 13)
        )
        return f"""/* === Grid & Utilitaires === */
.grid {{
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: var(--spacing-md);
}}
{cols}
@media (max-width: 768px) {{
  .grid {{ grid-template-columns: 1fr !important; }}
  [class^="col-span-"] {{ grid-column: span 1; }}
}}
.container {{ width: 100%; max-width: 1200px; margin: 0 auto; padding: 0 var(--spacing-md); }}
.section {{ padding: var(--spacing-3xl) 0; }}
.text-center {{ text-align: center; }}
.text-gradient {{
  background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}}"""

    def _generate_components(self, preset: Dict) -> str:
        style = self._resolve_style(preset)
        btn_variant = style.get("btn_variant", "filled")
        btn_r = style.get("radius", {}).get("md", "var(--border-radius-md)")

        if btn_variant == "outline":
            btn_primary_css = "background:transparent;color:var(--color-primary);border:var(--border-width) solid var(--color-primary);"
            btn_hover_css   = "background:var(--color-primary);color:#fff;"
        elif btn_variant == "ghost":
            btn_primary_css = "background:transparent;color:var(--color-primary);border:none;"
            btn_hover_css   = "background:var(--color-bg-gray);color:var(--color-primary-dark);"
        else:
            btn_primary_css = "background:linear-gradient(135deg,var(--color-primary),var(--color-primary-dark));color:#fff;box-shadow:var(--shadow-md);"
            btn_hover_css   = "transform:translateY(var(--hover-lift));box-shadow:var(--shadow-lg);"

        return f"""/* === Boutons === */
.btn {{
  display:inline-block;padding:var(--spacing-sm) var(--spacing-lg);
  font-size:var(--font-size-md);font-weight:var(--font-weight-medium);
  font-family:var(--font-family-body);text-decoration:none;
  border-radius:{btn_r};transition:all var(--transition-base);
  cursor:pointer;border:var(--border-width) solid transparent;line-height:1.5;
}}
.btn-primary {{ {btn_primary_css} }}
.btn-primary:hover {{ {btn_hover_css} opacity:1; }}
.btn-secondary {{ background:var(--color-bg-gray);color:var(--color-text);border-color:var(--color-border); }}
.btn-secondary:hover {{ border-color:var(--color-primary);color:var(--color-primary);opacity:1; }}

/* === Inputs === */
input,textarea,select {{
  width:100%;padding:var(--spacing-sm) var(--spacing-md);
  font-size:var(--font-size-md);font-family:var(--font-family-body);
  border:var(--border-width) solid var(--color-border);
  border-radius:var(--border-radius-sm);
  background:var(--color-bg);color:var(--color-text);
  transition:border-color var(--transition-fast);
}}
input:focus,textarea:focus,select:focus {{
  outline:none;border-color:var(--color-primary);
  box-shadow:0 0 0 3px rgba(var(--color-primary-rgb),0.12);
}}

/* === Cards === */
.card {{
  background:var(--color-bg);border:var(--border-width) solid var(--color-border);
  border-radius:var(--border-radius-lg);padding:var(--spacing-lg);
  box-shadow:var(--shadow-sm);transition:all var(--transition-base);
}}
.card:hover {{ transform:translateY(var(--hover-lift));box-shadow:var(--shadow-lg); }}"""


# ── Helpers ──────────────────────────────────────────────────────────────────

_DEFAULT_STYLE = {
    "radius":       {"sm": "4px", "md": "8px", "lg": "12px", "xl": "16px"},
    "shadow":       {
        "sm": "0 1px 2px rgba(0,0,0,0.05)",
        "md": "0 4px 6px rgba(0,0,0,0.1)",
        "lg": "0 10px 15px rgba(0,0,0,0.1)",
        "xl": "0 20px 25px rgba(0,0,0,0.1)",
    },
    "btn_variant":  "filled",
    "animation":    "subtle",
    "hover_lift":   "-2px",
    "hover_scale":  "1.01",
    "border_width": "1px",
    "transition_speed":  "200ms",
    "transition_easing": "cubic-bezier(0.4, 0, 0.2, 1)",
}


def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in override.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _animation_tokens(animation_style: str, style: dict):
    default_speed  = style.get("transition_speed",  "200ms")
    default_easing = style.get("transition_easing", "cubic-bezier(0.4, 0, 0.2, 1)")
    if animation_style == "none":     return "0ms", "linear"
    if animation_style == "subtle":   return default_speed, default_easing
    if animation_style == "moderate": return "250ms", "cubic-bezier(0.34, 1.56, 0.64, 1)"
    if animation_style == "rich":     return "300ms", "cubic-bezier(0.34, 1.56, 0.64, 1)"
    return default_speed, default_easing


def _scale_speed(speed: str, factor: float) -> str:
    if speed == "0ms":
        return "0ms"
    try:
        ms = int(speed.replace("ms", ""))
        return f"{int(ms * factor)}ms"
    except ValueError:
        return speed


def _rgb_str_to_components(rgb: str) -> str:
    import re
    m = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", rgb)
    return f"{m.group(1)}, {m.group(2)}, {m.group(3)}" if m else "102, 126, 234"
