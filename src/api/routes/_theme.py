"""
_theme.py — Système de design Présence IA

Palette extraite du logo (Adobe Illustrator) :
  Bleu acier    #527fb3   → primary, liens, actions
  Ardoise       #394455   → sidebar, titres, texte fort
  Or chaud      #996d2e   → accent secondaire, badges
  Or vif        #ffbd5c   → highlights admin (logo ADMIN)
  Gris chaud    #616466   → texte muted, décoratif

Trois thèmes :
  ADMIN   → fond clair #f0f4f9, sidebar ardoise, accents bleu+or
  CLOSER  → fond sombre #0d1421, dark premium navy
  PUBLIC  → blanc, minimaliste, accents bleu acier
"""

# ─────────────────────────────────────────────────────────────────────────────
# TOKENS DE DESIGN
# ─────────────────────────────────────────────────────────────────────────────

# Couleurs logo
C_BLUE       = "#527fb3"   # bleu acier principal
C_BLUE_DARK  = "#3d6494"   # bleu foncé (hover, pressed)
C_BLUE_LIGHT = "#e8f0fb"   # bleu très clair (bg hover, pills)
C_SLATE      = "#394455"   # ardoise foncée (sidebar, headings)
C_SLATE_MID  = "#5a6880"   # ardoise moyenne (text secondary)
C_GOLD       = "#996d2e"   # or chaud (badges, accents)
C_GOLD_LIGHT = "#fdf3e3"   # or très clair (bg badge)
C_GOLD_VIVID = "#ffbd5c"   # or vif (highlights, ADMIN)
C_GRAY_WARM  = "#616466"   # gris chaud (muted)

# Couleurs sémantiques
C_SUCCESS = "#16a34a"
C_SUCCESS_BG = "#dcfce7"
C_WARNING = "#d97706"
C_WARNING_BG = "#fef3c7"
C_DANGER  = "#dc2626"
C_DANGER_BG = "#fee2e2"
C_INFO    = "#0284c7"
C_INFO_BG = "#e0f2fe"

# Ombres raffinées (teintées logo)
SH_XS  = "0 1px 2px rgba(57,68,85,.06)"
SH_SM  = "0 1px 4px rgba(82,127,179,.08),0 1px 2px rgba(57,68,85,.05)"
SH_MD  = "0 4px 12px rgba(82,127,179,.1),0 2px 4px rgba(57,68,85,.07)"
SH_LG  = "0 8px 24px rgba(82,127,179,.15),0 2px 8px rgba(57,68,85,.08)"
SH_XL  = "0 20px 40px rgba(82,127,179,.18),0 4px 16px rgba(57,68,85,.1)"
SH_GOLD = "0 4px 16px rgba(153,109,46,.2),0 1px 4px rgba(57,68,85,.1)"

# Ombres dark (thème closer)
SH_DARK_SM = "0 2px 8px rgba(0,0,0,.3),0 1px 3px rgba(0,0,0,.2)"
SH_DARK_MD = "0 8px 24px rgba(0,0,0,.35),0 2px 8px rgba(0,0,0,.25)"
SH_DARK_LG = "0 16px 48px rgba(0,0,0,.4),0 4px 16px rgba(0,0,0,.3)"


# ─────────────────────────────────────────────────────────────────────────────
# THÈME ADMIN — fond clair, sidebar ardoise
# ─────────────────────────────────────────────────────────────────────────────

ADMIN_CSS = f"""
:root {{
  --c-bg:          #f0f4f9;
  --c-surface:     #ffffff;
  --c-border:      #dce4ef;
  --c-border-soft: #eaeff7;
  --c-text:        #1e2a3a;
  --c-text-2:      {C_SLATE_MID};
  --c-text-3:      #8a9ab0;
  --c-primary:     {C_BLUE};
  --c-primary-dk:  {C_BLUE_DARK};
  --c-primary-lt:  {C_BLUE_LIGHT};
  --c-gold:        {C_GOLD};
  --c-gold-lt:     {C_GOLD_LIGHT};
  --c-gold-vv:     {C_GOLD_VIVID};
  --c-success:     {C_SUCCESS};
  --c-success-bg:  {C_SUCCESS_BG};
  --c-warning:     {C_WARNING};
  --c-warning-bg:  {C_WARNING_BG};
  --c-danger:      {C_DANGER};
  --c-danger-bg:   {C_DANGER_BG};
  --sh-xs: {SH_XS};
  --sh-sm: {SH_SM};
  --sh-md: {SH_MD};
  --sh-lg: {SH_LG};
  --sh-xl: {SH_XL};
}}
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
  background: var(--c-bg);
  color: var(--c-text);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}}
a {{ color: var(--c-primary); text-decoration: none; }}
a:hover {{ color: var(--c-primary-dk); }}

/* Cards */
.card {{
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 20px 24px;
  box-shadow: var(--sh-sm);
}}
.card-flat {{
  background: var(--c-surface);
  border: 1px solid var(--c-border-soft);
  border-radius: 8px;
  padding: 16px 20px;
}}
.card-elevated {{
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--sh-md);
}}

/* Titres de page */
.page-title {{
  font-size: 20px;
  font-weight: 700;
  color: var(--c-text);
  margin: 0 0 4px;
  letter-spacing: -.01em;
}}
.page-sub {{
  font-size: 13px;
  color: var(--c-text-2);
  margin: 0 0 24px;
}}

/* Boutons */
.btn {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all .15s ease;
  text-decoration: none;
  white-space: nowrap;
}}
.btn-primary {{
  background: var(--c-primary);
  color: #fff;
  box-shadow: var(--sh-sm);
}}
.btn-primary:hover {{
  background: var(--c-primary-dk);
  box-shadow: var(--sh-md);
  color: #fff;
}}
.btn-gold {{
  background: var(--c-gold);
  color: #fff;
  box-shadow: {SH_GOLD};
}}
.btn-gold:hover {{
  background: #7d5824;
  color: #fff;
}}
.btn-ghost {{
  background: transparent;
  color: var(--c-primary);
  border: 1px solid var(--c-border);
}}
.btn-ghost:hover {{
  background: var(--c-primary-lt);
  border-color: var(--c-primary);
}}
.btn-danger {{
  background: var(--c-danger);
  color: #fff;
}}
.btn-sm {{
  padding: 5px 10px;
  font-size: 12px;
  border-radius: 5px;
}}

/* Badges */
.badge {{
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .02em;
}}
.badge-blue   {{ background: var(--c-primary-lt); color: var(--c-primary-dk); }}
.badge-gold   {{ background: var(--c-gold-lt); color: var(--c-gold); }}
.badge-vivid  {{ background: var(--c-gold-vv); color: #4a2d00; }}
.badge-green  {{ background: var(--c-success-bg); color: var(--c-success); }}
.badge-warn   {{ background: var(--c-warning-bg); color: var(--c-warning); }}
.badge-red    {{ background: var(--c-danger-bg); color: var(--c-danger); }}
.badge-gray   {{ background: #f1f5f9; color: var(--c-text-2); }}

/* Tableaux */
table.pres-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}
table.pres-table th {{
  padding: 10px 12px;
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-2);
  text-transform: uppercase;
  letter-spacing: .05em;
  border-bottom: 1px solid var(--c-border);
  background: #f8fafc;
}}
table.pres-table td {{
  padding: 10px 12px;
  border-bottom: 1px solid var(--c-border-soft);
  vertical-align: middle;
}}
table.pres-table tr:last-child td {{ border-bottom: none; }}
table.pres-table tr:hover td {{ background: #fafcff; }}

/* Formulaires */
input[type=text], input[type=email], input[type=url],
input[type=number], input[type=password], textarea, select {{
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  font-size: 13px;
  color: var(--c-text);
  background: var(--c-surface);
  transition: border-color .15s;
  font-family: inherit;
}}
input:focus, textarea:focus, select:focus {{
  outline: none;
  border-color: var(--c-primary);
  box-shadow: 0 0 0 3px rgba(82,127,179,.12);
}}

/* KPI cards */
.kpi-card {{
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: var(--sh-sm);
}}
.kpi-label {{
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-3);
  text-transform: uppercase;
  letter-spacing: .05em;
  margin-bottom: 4px;
}}
.kpi-value {{
  font-size: 26px;
  font-weight: 700;
  color: var(--c-text);
  letter-spacing: -.02em;
  line-height: 1.1;
}}
.kpi-sub {{
  font-size: 12px;
  color: var(--c-text-3);
  margin-top: 2px;
}}

/* Alertes inline */
.alert {{
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 12px;
}}
.alert-info    {{ background: {C_INFO_BG}; color: #0c4a6e; border-left: 3px solid {C_INFO}; }}
.alert-success {{ background: var(--c-success-bg); color: #14532d; border-left: 3px solid var(--c-success); }}
.alert-warn    {{ background: var(--c-warning-bg); color: #78350f; border-left: 3px solid var(--c-warning); }}
.alert-danger  {{ background: var(--c-danger-bg); color: #7f1d1d; border-left: 3px solid var(--c-danger); }}

/* Séparateurs */
.divider {{
  border: none;
  border-top: 1px solid var(--c-border-soft);
  margin: 20px 0;
}}

/* Details/accordéons admin */
details.pres-details {{
  border: 1px solid var(--c-border);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 8px;
}}
details.pres-details summary {{
  list-style: none;
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  background: var(--c-surface);
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
}}
details.pres-details summary::-webkit-details-marker {{ display: none; }}
details.pres-details[open] summary {{ border-bottom: 1px solid var(--c-border-soft); }}
details.pres-details > div {{ padding: 16px; }}
"""


# ─────────────────────────────────────────────────────────────────────────────
# THÈME CLOSER — dark premium navy
# ─────────────────────────────────────────────────────────────────────────────

CLOSER_CSS = f"""
:root {{
  --c-bg:       #0d1421;
  --c-surface:  #162033;
  --c-raised:   #1c2b43;
  --c-border:   #2a3d5a;
  --c-border-2: #1e3050;
  --c-text:     #e2e8f5;
  --c-text-2:   #7d94b0;
  --c-text-3:   #4a627e;
  --c-primary:  {C_BLUE};
  --c-primary-lt: rgba(82,127,179,.15);
  --c-gold:     {C_GOLD_VIVID};
  --c-gold-dk:  {C_GOLD};
  --c-success:  #34d399;
  --c-warning:  {C_GOLD_VIVID};
  --c-danger:   #f87171;
  --sh-sm: {SH_DARK_SM};
  --sh-md: {SH_DARK_MD};
  --sh-lg: {SH_DARK_LG};
}}
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
  background: var(--c-bg);
  color: var(--c-text);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}}
a {{ color: var(--c-primary); text-decoration: none; }}
a:hover {{ color: #7aa8d4; }}

.card {{
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: var(--sh-sm);
}}
.card-elevated {{
  background: var(--c-raised);
  border: 1px solid var(--c-border);
  border-radius: 14px;
  padding: 24px;
  box-shadow: var(--sh-md);
}}

/* Header collant */
.closer-header {{
  position: sticky;
  top: 0;
  z-index: 200;
  background: rgba(13,20,33,.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--c-border);
  padding: 0 24px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 2px 16px rgba(0,0,0,.4);
}}
.closer-header-logo {{
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}}
.closer-header-logo img {{
  height: 28px;
  width: auto;
}}
.closer-header-nav {{
  display: flex;
  align-items: center;
  gap: 6px;
}}

.btn {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all .15s ease;
  text-decoration: none;
  white-space: nowrap;
}}
.btn-primary {{
  background: var(--c-primary);
  color: #fff;
  box-shadow: var(--sh-sm);
}}
.btn-primary:hover {{
  background: {C_BLUE_DARK};
  box-shadow: var(--sh-md);
  color: #fff;
}}
.btn-gold {{
  background: var(--c-gold);
  color: #1a0e00;
  font-weight: 700;
  box-shadow: 0 4px 16px rgba(255,189,92,.25);
}}
.btn-gold:hover {{
  background: #ffc96e;
  box-shadow: 0 6px 20px rgba(255,189,92,.35);
}}
.btn-ghost {{
  background: var(--c-primary-lt);
  color: var(--c-primary);
  border: 1px solid var(--c-border);
}}
.btn-ghost:hover {{
  background: rgba(82,127,179,.25);
}}
.btn-sm {{ padding: 5px 10px; font-size: 12px; border-radius: 5px; }}

.badge {{
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
}}
.badge-gold   {{ background: rgba(255,189,92,.15); color: var(--c-gold); border: 1px solid rgba(255,189,92,.3); }}
.badge-blue   {{ background: var(--c-primary-lt); color: #7aa8d4; border: 1px solid rgba(82,127,179,.3); }}
.badge-green  {{ background: rgba(52,211,153,.12); color: var(--c-success); border: 1px solid rgba(52,211,153,.25); }}
.badge-red    {{ background: rgba(248,113,113,.12); color: var(--c-danger); border: 1px solid rgba(248,113,113,.25); }}
.badge-gray   {{ background: rgba(255,255,255,.06); color: var(--c-text-2); border: 1px solid var(--c-border); }}

input[type=text], input[type=email], input[type=url],
input[type=number], input[type=password], textarea, select {{
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  font-size: 14px;
  color: var(--c-text);
  background: rgba(255,255,255,.04);
  transition: border-color .15s, box-shadow .15s;
  font-family: inherit;
}}
input:focus, textarea:focus, select:focus {{
  outline: none;
  border-color: var(--c-primary);
  box-shadow: 0 0 0 3px rgba(82,127,179,.2);
  background: rgba(82,127,179,.05);
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# THÈME PUBLIC / LANDING — blanc, minimaliste
# ─────────────────────────────────────────────────────────────────────────────

PUBLIC_CSS = f"""
:root {{
  --c-bg:       #ffffff;
  --c-surface:  #ffffff;
  --c-bg-soft:  #f8fafc;
  --c-border:   #e2e8f0;
  --c-text:     #1e2a3a;
  --c-text-2:   {C_SLATE_MID};
  --c-text-3:   #94a3b8;
  --c-primary:  {C_BLUE};
  --c-primary-dk: {C_BLUE_DARK};
  --c-primary-lt: {C_BLUE_LIGHT};
  --c-gold:     {C_GOLD};
  --c-gold-lt:  {C_GOLD_LIGHT};
  --sh-sm: {SH_SM};
  --sh-md: {SH_MD};
  --sh-lg: {SH_LG};
}}
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
  background: var(--c-bg);
  color: var(--c-text);
  font-size: 15px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}}
a {{ color: var(--c-primary); text-decoration: none; }}
a:hover {{ color: var(--c-primary-dk); text-decoration: underline; }}
"""


# ─────────────────────────────────────────────────────────────────────────────
# FONCTIONS HELPER — HTML <head> + headers de page
# ─────────────────────────────────────────────────────────────────────────────

def admin_page_head(title: str, extra_css: str = "") -> str:
    """
    Retourne le bloc <head> complet pour une page admin.
    Injecter en début de page, AVANT admin_nav().
    """
    return (
        f'<!DOCTYPE html>\n'
        f'<html lang="fr"><head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>{title} — Présence IA Admin</title>\n'
        f'<style>{ADMIN_CSS}{extra_css}</style>\n'
        f'</head><body>\n'
    )


def closer_page_head(title: str, extra_css: str = "") -> str:
    """Retourne le bloc <head> pour les pages closer (thème dark)."""
    return (
        f'<!DOCTYPE html>\n'
        f'<html lang="fr"><head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>{title} — Présence IA</title>\n'
        f'<style>{CLOSER_CSS}{extra_css}</style>\n'
        f'</head><body>\n'
    )


def public_page_head(title: str, extra_css: str = "") -> str:
    """Retourne le bloc <head> pour les pages publiques / landing."""
    return (
        f'<!DOCTYPE html>\n'
        f'<html lang="fr"><head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>{title}</title>\n'
        f'<style>{PUBLIC_CSS}{extra_css}</style>\n'
        f'</head><body>\n'
    )


def closer_header_html(
    token: str = "",
    back_url: str = "",
    back_label: str = "← Portail",
    title: str = "",
    right_html: str = "",
) -> str:
    """
    Header collant pour les pages closer.
    logo-white.svg sur fond dark transparent + backdrop-blur.
    """
    left = (
        f'<a href="{back_url}" class="btn btn-ghost btn-sm">{back_label}</a>'
        if back_url else
        '<a href="/" class="closer-header-logo">'
        '<img src="/assets/logo-white.svg" alt="Présence IA"></a>'
    )
    center = (
        f'<span style="font-size:14px;font-weight:600;color:var(--c-text)">{title}</span>'
        if title else ""
    )
    return (
        f'<header class="closer-header">'
        f'<div style="display:flex;align-items:center;gap:12px">{left}</div>'
        f'<div>{center}</div>'
        f'<div class="closer-header-nav">{right_html}</div>'
        f'</header>'
    )


def rdv_modal_css() -> str:
    """CSS de la modale agenda (partagé closer + admin RDV)."""
    return """
.modal-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(13,20,33,.7);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 900;
  align-items: center;
  justify-content: center;
}
.modal-overlay.open { display: flex; }
.modal-box {
  background: #1c2b43;
  border: 1px solid #2a3d5a;
  border-radius: 16px;
  padding: 28px 32px;
  width: min(520px, 92vw);
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 24px 64px rgba(0,0,0,.5), 0 4px 20px rgba(0,0,0,.3);
  position: relative;
}
.modal-title {
  font-size: 16px;
  font-weight: 700;
  color: #e2e8f5;
  margin: 0 0 20px;
}
.modal-close {
  position: absolute;
  top: 16px; right: 16px;
  background: rgba(255,255,255,.06);
  border: 1px solid #2a3d5a;
  border-radius: 6px;
  width: 30px; height: 30px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  color: #7d94b0;
  font-size: 16px;
  transition: background .15s;
}
.modal-close:hover { background: rgba(255,255,255,.1); color: #e2e8f5; }
"""
