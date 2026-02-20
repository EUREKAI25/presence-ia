"""
Renderer HTML v0.2 — génère le HTML complet d'une Page.
Dispatch : blocs v0.2 (block_type) en priorité, puis modules v0.1 (module_type).
"""
from typing import Any
from ..core.schemas import Page, Section, Column, BaseModule
from ..core.schemas import HeroModule, PricingModule, TextModule, CTAModule, ProofModule, TestimonialsModule
from ..blocks.hero        import HeroBlock
from ..blocks.navbar      import NavBarBlock
from ..blocks.stat        import StatBlock
from ..blocks.steps       import StepsBlock
from ..blocks.faq         import FAQBlock
from ..blocks.pricing     import PricingBlock
from ..blocks.cta         import CTABlock
from ..blocks.image       import ImageBlock
from ..blocks.testimonial import TestimonialBlock
from ..blocks.content     import ContentBlock
from ..blocks.footer      import FooterBlock
from .css import generate_page_css


# ── Point d'entrée public ───────────────────────────────────────────────────

def render_page(page: Page, extra_head: str = "", extra_body_end: str = "") -> str:
    """Génère le HTML complet d'une page."""
    css = generate_page_css(page)

    # NavBar éventuelle rendue hors du flux des sections
    navbar_html = ""
    sections_html_parts = []
    for section in sorted(page.sections, key=lambda s: s.order):
        if not section.enabled:
            continue
        # Détecter si la section contient uniquement une NavBar
        if (len(section.columns) == 1
                and isinstance(section.columns[0].module, NavBarBlock)):
            navbar_html = render_navbar_block(section.columns[0].module)
        else:
            sections_html_parts.append(render_section(section))

    sections_html = "\n".join(sections_html_parts)

    font_url = page.theme.get("font_google_url", "")
    font_link = f'<link rel="preconnect" href="https://fonts.googleapis.com">\n  <link rel="stylesheet" href="{font_url}">' if font_url else ""

    return f"""<!DOCTYPE html>
<html lang="{getattr(page, 'lang', 'fr')}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page.title}</title>
  {f'<meta name="description" content="{page.description}">' if page.description else ''}
  {font_link}
  <style>{css}</style>
  {extra_head}
</head>
<body>
{navbar_html}
{sections_html}
{extra_body_end}
</body>
</html>"""


# ── Section ─────────────────────────────────────────────────────────────────

def render_section(section: Section) -> str:
    section_id  = f' id="{section.id}"' if section.id else ""
    bg_style    = f' style="background:{section.bg_color};"' if section.bg_color else ""

    # 1 colonne span 12 → pas de grid
    if len(section.columns) == 1 and section.columns[0].span == 12:
        inner = render_module(section.columns[0].module)
        return f'<section{section_id} class="section"{bg_style}>\n  <div class="container">\n{inner}\n  </div>\n</section>'

    cols_html = "\n".join(
        f'  <div class="col-span-{col.span}">\n{render_module(col.module)}\n  </div>'
        for col in section.columns
    )
    return f"""<section{section_id} class="section"{bg_style}>
  <div class="container">
    <div class="grid">
{cols_html}
    </div>
  </div>
</section>"""


# ── Dispatch module/bloc ─────────────────────────────────────────────────────

def render_module(module: Any) -> str:
    """Dispatch vers le renderer approprié (v0.2 d'abord, puis v0.1)."""
    # v0.2 — blocs typés
    if isinstance(module, HeroBlock):        return render_hero_block(module)
    if isinstance(module, NavBarBlock):      return render_navbar_block(module)
    if isinstance(module, StatBlock):        return render_stat_block(module)
    if isinstance(module, StepsBlock):       return render_steps_block(module)
    if isinstance(module, FAQBlock):         return render_faq_block(module)
    if isinstance(module, PricingBlock):     return render_pricing_block(module)
    if isinstance(module, CTABlock):         return render_cta_block(module)
    if isinstance(module, ImageBlock):       return render_image_block(module)
    if isinstance(module, TestimonialBlock): return render_testimonial_block(module)
    if isinstance(module, ContentBlock):     return render_content_block(module)
    if isinstance(module, FooterBlock):      return render_footer_block(module)

    # v0.1 — modules legacy
    if isinstance(module, HeroModule):          return render_hero(module)
    if isinstance(module, PricingModule):       return render_pricing(module)
    if isinstance(module, TextModule):          return render_text(module)
    if isinstance(module, CTAModule):           return render_cta(module)
    if isinstance(module, ProofModule):         return render_proof(module)
    if isinstance(module, TestimonialsModule):  return render_testimonials(module)

    return f"<!-- Bloc non implémenté : {getattr(module, 'block_type', getattr(module, 'module_type', '?'))} -->"


# ── Renderers blocs v0.2 ────────────────────────────────────────────────────

def render_hero_block(b: HeroBlock) -> str:
    s, d = b.structure, b.seed

    # Classes BEM
    classes = ["hero", f"hero--bg-{s.bg_type}", f"hero--text-{s.text_position}"]
    if s.overlay and s.bg_type in ("image", "video"):
        classes.append("hero--overlay")
    if b.css_class:
        classes.append(b.css_class)

    # Style inline : min-height + background-image si image
    # (inline évite les conflits CSS parent — cf. leçons apprises)
    inline_styles = [f"min-height:{s.min_height}"]
    if s.bg_type == "image" and d.bg_src:
        inline_styles.append(f"background-image:url('{d.bg_src}')")
    elif s.bg_type == "color" and d.bg_color:
        inline_styles.append(f"background:{d.bg_color}")

    style_attr = f' style="{";".join(inline_styles)}"' if inline_styles else ""
    id_attr    = f' id="{b.id}"' if b.id else ""

    badge_html = f'<span class="hero__badge">{d.badge}</span>\n    ' if d.badge else ""

    cta_group = ""
    if d.cta_primary_label or d.cta_secondary_label:
        primary   = f'<a href="{d.cta_primary_href}" class="btn btn-primary">{d.cta_primary_label}</a>' if d.cta_primary_label else ""
        secondary = f'<a href="{d.cta_secondary_href}" class="btn btn-secondary">{d.cta_secondary_label}</a>' if d.cta_secondary_label else ""
        cta_group = f'\n    <div class="hero__cta-group">{primary}{secondary}</div>'

    return f"""<div class="{" ".join(classes)}"{style_attr}{id_attr}>
  <div class="hero__content">
    {badge_html}<h1 class="hero__title">{d.title}</h1>
    <p class="hero__subtitle">{d.subtitle}</p>{cta_group}
  </div>
</div>"""


def render_navbar_block(b: NavBarBlock) -> str:
    s, d = b.structure, b.seed

    classes = ["navbar", f"navbar--{s.position}", f"navbar--{s.style}"]
    if b.css_class:
        classes.append(b.css_class)

    if d.logo_img:
        logo_inner = f'<img src="{d.logo_img}" alt="{d.logo_text}">'
    else:
        logo_inner = d.logo_text

    links_html = "".join(
        f'<li><a href="{lnk.href}" class="navbar__link"'
        f'{f" target=\"{lnk.target}\"" if lnk.target else ""}>{lnk.label}</a></li>'
        for lnk in d.links
    )

    return f"""<nav class="{" ".join(classes)}">
  <div class="navbar__inner">
    <a href="{d.logo_href}" class="navbar__logo">{logo_inner}</a>
    <ul class="navbar__links">{links_html}</ul>
  </div>
</nav>"""


def render_stat_block(b: StatBlock) -> str:
    s, d = b.structure, b.seed

    classes = ["stat", f"stat--{s.layout}"]
    if b.css_class:
        classes.append(b.css_class)

    items_html = ""
    for item in d.stats:
        source_html = ""
        if s.show_sources and item.source_url:
            source_html = f'<div class="stat__source"><a href="{item.source_url}" target="_blank" rel="noopener">source</a></div>'
        items_html += f"""<div class="stat__item">
  <div class="stat__value">{item.value}</div>
  <div class="stat__label">{item.label}</div>
  {source_html}
</div>"""

    return f"""<div class="{" ".join(classes)}">
  <div class="stat__container">
    <div class="stat__grid">{items_html}</div>
  </div>
</div>"""


def render_steps_block(b: StepsBlock) -> str:
    s, d = b.structure, b.seed

    classes = ["steps", f"steps--{s.variant}", f"steps--{s.direction}"]
    if b.css_class:
        classes.append(b.css_class)

    header = ""
    if d.title:
        sub = f'<p class="steps__subtitle">{d.subtitle}</p>' if d.subtitle else ""
        header = f'<div class="steps__header"><h2 class="steps__title">{d.title}</h2>{sub}</div>'

    items_html = ""
    for i, step in enumerate(d.steps, 1):
        num_html = ""
        if s.numbering == "numeric":
            num_html = f'<div class="steps__number">{i}</div>'
        elif s.numbering == "icon" and step.icon:
            num_html = f'<div class="steps__number">{step.icon}</div>'

        title_html = f'<div class="steps__item-title">{step.title}</div>' if step.title else ""
        items_html += f"""<div class="steps__item">
  {num_html}
  {title_html}
  <div class="steps__item-desc">{step.description}</div>
</div>"""

    return f"""<div class="{" ".join(classes)}">
  <div class="container">
    {header}
    <div class="steps__list">{items_html}</div>
  </div>
</div>"""


def render_faq_block(b: FAQBlock) -> str:
    s, d = b.structure, b.seed

    classes = ["faq", f"faq--{s.style}"]
    if b.css_class:
        classes.append(b.css_class)

    header = f'<div class="faq__header"><h2 class="faq__title">{d.title}</h2></div>' if d.title else ""

    items_html = ""
    for i, item in enumerate(d.items):
        if s.style == "accordion":
            # Toggle JS inline minimal — pas de dépendance externe
            items_html += f"""<div class="faq__item">
  <button class="faq__question" aria-expanded="false"
    onclick="var a=this.nextElementSibling;var open=this.getAttribute('aria-expanded')==='true';this.setAttribute('aria-expanded',!open);a.hidden=open;"
  >{item.question}<span class="faq__icon" aria-hidden="true">▾</span></button>
  <div class="faq__answer" hidden>{item.answer}</div>
</div>"""
        else:  # list
            items_html += f"""<div class="faq__item">
  <div class="faq__question">{item.question}</div>
  <div class="faq__answer">{item.answer}</div>
</div>"""

    return f"""<div class="{" ".join(classes)}">
  <div class="container" style="max-width:{s.max_width}">
    {header}
    <div class="faq__list">{items_html}</div>
  </div>
</div>"""


def render_pricing_block(b: PricingBlock) -> str:
    s, d = b.structure, b.seed

    # Layout auto : calculé selon nombre de cartes
    if s.layout == "auto":
        n = len(d.cards)
        grid_mod = "1col" if n == 1 else "2col" if n == 2 else "3col"
    else:
        grid_mod = s.layout

    header = ""
    if d.title:
        sub = f'<p class="pricing__subtitle">{d.subtitle}</p>' if d.subtitle else ""
        header = f'<div class="pricing__header"><h2 class="pricing__title">{d.title}</h2>{sub}</div>'

    cards_html = ""
    for card in d.cards:
        featured_cls = " pricing__card--featured" if card.is_featured else ""
        style_cls    = f" pricing__card--{s.card_style}"
        badge        = '<span class="pricing__badge-featured">Recommandé</span>' if card.is_featured else ""
        period_html  = f'<div class="pricing__period">{card.period}</div>' if card.period else ""
        feats        = "".join(f"<li>{f}</li>" for f in card.features)

        if card.cta_js:
            cta = f'<button class="pricing__cta" onclick="{card.cta_js}">{card.cta_label}</button>'
        else:
            cta = f'<a href="{card.cta_href}" class="pricing__cta">{card.cta_label}</a>'

        cards_html += f"""<div class="pricing__card{featured_cls}{style_cls}">
  {badge}
  <div class="pricing__name">{card.name}</div>
  <div class="pricing__price">{card.price}</div>
  {period_html}
  <ul class="pricing__features">{feats}</ul>
  {cta}
</div>"""

    return f"""<div class="pricing">
  <div class="container">
    {header}
    <div class="pricing__grid pricing__grid--{grid_mod}">{cards_html}</div>
  </div>
</div>"""


def render_cta_block(b: CTABlock) -> str:
    s, d = b.structure, b.seed

    classes = ["cta-block", f"cta-block--{s.bg_type}", f"cta-block--text-{s.text_align}"]
    if b.css_class:
        classes.append(b.css_class)

    inline = ""
    if s.bg_type == "color" and d.bg_color:
        inline = f' style="background:{d.bg_color};"'
    elif s.bg_type == "gradient" and d.bg_gradient:
        inline = f' style="background:{d.bg_gradient};"'

    subtitle = f'<p class="cta-block__subtitle">{d.subtitle}</p>' if d.subtitle else ""

    return f"""<div class="{" ".join(classes)}"{inline}>
  <div class="cta-block__inner">
    <h2 class="cta-block__title">{d.title}</h2>
    {subtitle}
    <a href="{d.btn_href}" class="cta-block__btn">{d.btn_label}</a>
  </div>
</div>"""


def render_image_block(b: ImageBlock) -> str:
    s, d = b.structure, b.seed

    classes = ["image-block", f"image-block--{s.size}"]
    if s.caption_position != "none":
        classes.append(f"image-block--caption-{s.caption_position}")
    if b.css_class:
        classes.append(b.css_class)

    aspect = f' style="aspect-ratio:{s.aspect_ratio};"' if s.aspect_ratio else ""
    caption = ""
    if d.caption:
        caption = f'<figcaption class="image-block__caption">{d.caption}</figcaption>'

    return f"""<figure class="{" ".join(classes)}">
  <div class="image-block__wrapper"{aspect}>
    <img src="{d.src}" alt="{d.alt}">
    {caption if s.caption_position == "overlay" else ""}
  </div>
  {caption if s.caption_position == "below" else ""}
</figure>"""


def render_testimonial_block(b: TestimonialBlock) -> str:
    s, d = b.structure, b.seed

    classes = ["testimonials"]
    if b.css_class:
        classes.append(b.css_class)

    header = f'<div class="testimonials__header"><h2 class="testimonials__title">{d.title}</h2></div>' if d.title else ""

    items_html = ""
    for item in d.items:
        avatar = f'<img src="{item.avatar}" alt="{item.name}" class="testimonials__avatar">' if item.avatar else ""
        role   = f'<div class="testimonials__role">{item.role}</div>' if item.role else ""
        items_html += f"""<div class="testimonials__card">
  {avatar}
  <div class="testimonials__content">{item.content}</div>
  <div class="testimonials__author">{item.name}</div>
  {role}
</div>"""

    return f"""<div class="{" ".join(classes)}">
  <div class="container">
    {header}
    <div class="testimonials__grid">{items_html}</div>
  </div>
</div>"""


def render_content_block(b: ContentBlock) -> str:
    s, d = b.structure, b.seed

    classes = ["content-block", f"content-block--{s.variant}"]
    if b.css_class:
        classes.append(b.css_class)

    parts = []
    for key, item in d.items.items():
        if item.type == "text":
            parts.append(f'<p class="content-block__text">{item.value}</p>')
        elif item.type == "html":
            parts.append(item.value)
        elif item.type == "image":
            parts.append(f'<img src="{item.value}" alt="{item.alt or ""}" class="content-block__image">')
        elif item.type == "link":
            parts.append(f'<a href="{item.value}">{item.alt or item.value}</a>')

    return f'<div class="{" ".join(classes)}">{"".join(parts)}</div>'


def render_footer_block(b: FooterBlock) -> str:
    s, d = b.structure, b.seed

    classes = ["footer"]
    if b.css_class:
        classes.append(b.css_class)

    cols_html = ""
    for col in d.columns:
        title_html = f'<h4 class="footer__col-title">{col.title}</h4>' if col.title else ""
        links_html = "".join(
            f'<a href="{lnk.href}" class="footer__link">{lnk.label}</a>'
            for lnk in col.links
        )
        cols_html += f'<div><{title_html}<div class="footer__links">{links_html}</div></div>'

    social_html = ""
    if s.show_social and d.social_links:
        slinks = "".join(
            f'<a href="{lnk.href}">{lnk.label}</a>'
            for lnk in d.social_links
        )
        social_html = f'<div class="footer__social">{slinks}</div>'

    return f"""<footer class="{" ".join(classes)}">
  <div class="footer__inner">
    <div class="footer__grid">{cols_html}</div>
    <div class="footer__bottom">
      <p class="footer__copyright">{d.copyright}</p>
      {social_html}
    </div>
  </div>
</footer>"""


# ── Renderers modules v0.1 (compat) ─────────────────────────────────────────

def render_hero(module: HeroModule) -> str:
    badge = f'<div class="hero-badge">{module.badge}</div>' if module.badge else ''
    cta_p = f'<a href="{module.cta_primary["href"]}" class="btn btn-primary">{module.cta_primary["label"]}</a>' if module.cta_primary else ''
    cta_s = f'<a href="{module.cta_secondary["href"]}" class="btn btn-secondary">{module.cta_secondary["label"]}</a>' if module.cta_secondary else ''
    ctas  = f'<div class="hero-btns">{cta_p}{cta_s}</div>' if (cta_p or cta_s) else ''
    return f'<div class="hero">{badge}<h1>{module.title}</h1><p>{module.subtitle}</p>{ctas}</div>'


def render_pricing(module: PricingModule) -> str:
    header = f'<div class="pricing-header"><h2>{module.title}</h2>{f"<p>{module.subtitle}</p>" if module.subtitle else ""}</div>'
    cards  = "".join(
        f'<div class="pricing-card{"  featured" if p.is_featured else ""}">'
        f'<div class="pricing-name">{p.name}</div>'
        f'<div class="pricing-price">{p.price}</div>'
        f'<ul class="pricing-features">{"".join(f"<li>{f}</li>" for f in p.features)}</ul>'
        f'<a href="{p.cta_href}" class="btn btn-primary" style="width:100%">{p.cta_label}</a>'
        f'</div>'
        for p in module.plans
    )
    return f'<div class="pricing">{header}<div class="pricing-grid">{cards}</div></div>'


def render_text(module: TextModule) -> str:
    elems = "".join(f"<p>{e.content}</p>" for e in module.elements if e.type == "text")
    return f'<div class="text-module">{elems}</div>'


def render_cta(module: CTAModule) -> str:
    bg    = f' style="background:{module.background_color};"' if module.background_color else ''
    sub   = f'<p>{module.subtitle}</p>' if module.subtitle else ''
    return f'<div class="cta"{bg}><h2>{module.title}</h2>{sub}<a href="{module.button_href}" class="btn btn-primary">{module.button_label}</a></div>'


def render_proof(module: ProofModule) -> str:
    stats = "".join(
        f'<div class="proof-stat"><div class="proof-value">{s["value"]}</div><div class="proof-label">{s["label"]}</div></div>'
        for s in module.stats
    )
    return f'<div class="proof"><div class="proof-header"><h2>{module.title}</h2></div><div class="proof-stats">{stats}</div></div>'


def render_testimonials(module: TestimonialsModule) -> str:
    items = "".join(
        f'<div class="testimonial-card">'
        f'<div class="testimonial-content">&ldquo;{i.content}&rdquo;</div>'
        f'<div class="testimonial-author">{i.name}</div>'
        f'{f"<div class=\"testimonial-role\">{i.role}</div>" if i.role else ""}'
        f'</div>'
        for i in module.items
    )
    return f'<div class="testimonials"><div class="testimonials-header"><h2>{module.title}</h2></div><div class="testimonials-grid">{items}</div></div>'
