"""
Injection du bloc "À lire aussi" dans une page HTML générée.

Fonctions exportées :
  build_link_block(links) → str (HTML du bloc)
  inject_internal_links(html, links) → str (HTML enrichi)

Design :
  - Bloc discret, sobre, positionné avant </body>
  - CSS inline, aucune dépendance externe
  - Ne touche pas aux menus ni à la structure existante
  - Retourne html inchangé si links est vide
"""

import html as _html_module


def _esc(s: str) -> str:
    return _html_module.escape(str(s))


def build_link_block(links: list[dict]) -> str:
    """
    Génère le HTML du bloc "À lire aussi".

    Args:
        links : liste [{title, url, anchor, reason}]

    Returns:
        str : HTML du bloc, chaîne vide si links est vide
    """
    if not links:
        return ""

    items_html = "\n    ".join(
        f'<li style="margin:0;padding:4px 0;border-bottom:1px solid #e5e7eb;last-child:border-bottom:none">'
        f'<a href="{_esc(lk["url"])}" '
        f'style="color:#1e3a5f;text-decoration:none;font-size:14px;font-weight:500">'
        f'→ {_esc(lk["anchor"])}'
        f'</a>'
        f'</li>'
        for lk in links
    )

    return f"""
<section style="margin:2rem 0 0;padding:1.5rem 2rem;background:#f0f4f8;border-top:3px solid #1e3a5f;border-radius:0 0 8px 8px" aria-label="Pages liées">
  <p style="font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.08em;margin:0 0 0.75rem 0">À lire aussi</p>
  <ul style="margin:0;padding:0;list-style:none">
    {items_html}
  </ul>
</section>"""


def inject_internal_links(html: str, links: list[dict]) -> str:
    """
    Injecte le bloc "À lire aussi" juste avant </body>.

    Args:
        html  : HTML complet de la page
        links : liste [{title, url, anchor, reason}]

    Returns:
        HTML enrichi, ou html inchangé si links est vide
    """
    if not links:
        return html

    block = build_link_block(links)

    if "</body>" in html:
        return html.replace("</body>", block + "\n</body>", 1)

    # Fallback : append à la fin
    return html + block
