"""
Manifest parser — ManifestPage → Page (objet Pydantic v0.1/v0.2).
Résout i18n + placeholders sur chaque champ seed string.
"""
from typing import Any

from ..core.schemas import Page, Section, Column, SectionLayout
from ..core.i18n import resolve as i18n_resolve
from .schema import ManifestPage, ManifestSection, ManifestColumn, ManifestBlockConfig

# ── Registry des blocs v0.2 ─────────────────────────────────────────────────
from ..blocks import (
    HeroBlock, NavBarBlock, StatBlock, StepsBlock, FAQBlock,
    PricingBlock, CTABlock, ImageBlock, TestimonialBlock,
    ContentBlock, FooterBlock,
)

_BLOCK_REGISTRY: dict = {
    "hero_block":        HeroBlock,
    "navbar_block":      NavBarBlock,
    "stat_block":        StatBlock,
    "steps_block":       StepsBlock,
    "faq_block":         FAQBlock,
    "pricing_block":     PricingBlock,
    "cta_block":         CTABlock,
    "image_block":       ImageBlock,
    "testimonial_block": TestimonialBlock,
    "content_block":     ContentBlock,
    "footer_block":      FooterBlock,
}


def _resolve_strings(obj: Any, lang: str, ctx: dict) -> Any:
    """Parcourt récursivement un dict/list/str et résout i18n + placeholders."""
    if isinstance(obj, str):
        return i18n_resolve(obj, lang=lang, context=ctx)
    if isinstance(obj, dict):
        return {k: _resolve_strings(v, lang, ctx) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_strings(v, lang, ctx) for v in obj]
    return obj


def _parse_block(cfg: ManifestBlockConfig, lang: str, ctx: dict) -> Any:
    """Instancie un bloc v0.2 depuis sa config manifest (structure + seed résolus)."""
    block_cls = _BLOCK_REGISTRY.get(cfg.block_type)
    if block_cls is None:
        raise ValueError(f"Bloc inconnu : {cfg.block_type!r}. Registry : {list(_BLOCK_REGISTRY)}")

    resolved_seed      = _resolve_strings(cfg.seed, lang, ctx)
    resolved_structure = _resolve_strings(cfg.structure, lang, ctx)

    # Instancier avec structure et seed résolus
    structure_cls = block_cls.model_fields["structure"].default.__class__
    seed_cls      = block_cls.model_fields["seed"].default.__class__

    return block_cls(
        block_type=cfg.block_type,
        css_class=cfg.css_class,
        id=cfg.id,
        structure=structure_cls(**resolved_structure),
        seed=seed_cls(**resolved_seed),
    )


def _parse_column(col: ManifestColumn, lang: str, ctx: dict) -> Column:
    block = _parse_block(col.block, lang, ctx)
    return Column(span=col.span, module=block)


def _parse_section(sec: ManifestSection, lang: str, ctx: dict) -> Section:
    columns = [_parse_column(c, lang, ctx) for c in sec.columns]
    layout  = SectionLayout(type=sec.layout_type or "full")
    return Section(
        id=sec.key,
        bg_color=sec.bg_color,
        enabled=sec.enabled,
        order=sec.order,
        layout=layout,
        columns=columns,
    )


def parse_manifest(manifest: ManifestPage) -> Page:
    """
    Convertit un ManifestPage en Page prête à rendre.

    1. Résout i18n + placeholders sur tous les seeds
    2. Instancie chaque bloc depuis le registry
    3. Construit Column → Section → Page
    """
    lang = manifest.lang
    ctx  = manifest.placeholder_context

    # Résoudre le titre de la page lui-même
    title = i18n_resolve(manifest.title, lang=lang, context=ctx)
    desc  = i18n_resolve(manifest.description or "", lang=lang, context=ctx) or None

    sections = [
        _parse_section(sec, lang, ctx)
        for sec in sorted(manifest.sections, key=lambda s: s.order)
        if sec.enabled
    ]

    return Page(
        title=title,
        description=desc,
        lang=lang,
        theme=manifest.theme,
        sections=sections,
    )
