"""
PRESENCE_IA — Paramétrage du module page_builder.

Ce fichier est le point d'entrée entre la DB PRESENCE_IA et le module EURKAI
page_builder. Il ne contient aucune logique de rendu HTML : il construit
un ManifestPage depuis la DB, puis délègue entièrement à page_builder.

Flux :
  DB (ThemeConfigDB + ContentBlockDB + PageLayoutDB + CityHeaderDB)
    → build_manifest_from_db()
    → ManifestPage
    → parse_manifest()
    → Page
    → render_page()
    → HTML

Architecture "paramétrage" :
  - page_builder fournit les seeds génériques (structure + blocs)
  - PRESENCE_IA fournit le contenu (DB) et le thème (DB)
  - Les seeds du projet sont construits dynamiquement, pas stockés en fichier
"""
import json
from typing import Optional
from sqlalchemy.orm import Session

from page_builder import ManifestPage, parse_manifest, render_page
from page_builder.manifest.schema import ManifestSection, ManifestColumn, ManifestBlockConfig

from ...database import get_block, db_get_header, db_get_theme, db_get_page_layout


# ── Structure des pages PRESENCE_IA ──────────────────────────────────────────
# Définit quels blocs constituent chaque section pour chaque page_type.
# C'est le "manifest de paramétrage" apporté par le projet.

_LANDING_SECTIONS = [
    {
        "key": "hero",
        "block_type": "hero_block",
        "structure": {
            "bg_type": "image",
            "text_position": "center",
            "overlay": True,
            "min_height": "90vh",
        },
    },
    {
        "key": "proof_stat",
        "block_type": "stat_block",
        "structure": {"layout": "horizontal", "show_sources": False},
    },
    {
        "key": "proof_visual",
        "block_type": "steps_block",
        "structure": {"direction": "horizontal", "numbering": "numeric", "variant": "cards"},
    },
    {
        "key": "pricing",
        "block_type": "pricing_block",
        "structure": {"layout": "auto", "card_style": "elevated"},
    },
    {
        "key": "faq",
        "block_type": "faq_block",
        "structure": {"style": "accordion", "max_width": "800px"},
    },
    {
        "key": "cta_final",
        "block_type": "cta_block",
        "structure": {"bg_type": "gradient", "text_align": "center"},
    },
    {
        "key": "footer",
        "block_type": "footer_block",
        "structure": {"columns": 2, "show_social": False},
    },
]

_HOME_SECTIONS = [
    {
        "key": "hero",
        "block_type": "hero_block",
        "structure": {
            "bg_type": "gradient",
            "text_position": "center",
            "overlay": False,
            "min_height": "85vh",
        },
    },
    {
        "key": "proof_stat",
        "block_type": "stat_block",
        "structure": {"layout": "horizontal", "show_sources": False},
    },
    {
        "key": "proof_visual",
        "block_type": "steps_block",
        "structure": {"direction": "horizontal", "numbering": "numeric", "variant": "cards"},
    },
    {
        "key": "faq",
        "block_type": "faq_block",
        "structure": {"style": "accordion", "max_width": "800px"},
    },
    {
        "key": "cta_final",
        "block_type": "cta_block",
        "structure": {"bg_type": "gradient", "text_align": "center"},
    },
    {
        "key": "footer",
        "block_type": "footer_block",
        "structure": {"columns": 2, "show_social": False},
    },
]

# Valeurs par défaut des placeholders PRESENCE_IA
_PLACEHOLDER_DEFAULTS = {
    "city":        "votre ville",
    "profession":  "professionnel de santé",
    "price":       "97€",
    "n_queries":   "15",
    "n_models":    "3",
    "models":      "ChatGPT, Gemini et Claude",
}


# ── Seeds par section — construits depuis ContentBlockDB ──────────────────────

def _seed_hero(db: Session, page_type: str, city: Optional[str], profession: Optional[str],
               header_url: Optional[str]) -> dict:
    B = lambda fk, d="": get_block(db, page_type, "hero", fk, profession, city) or d
    return {
        "title":              B("title",    "Votre visibilité IA en 48h"),
        "subtitle":           B("subtitle", "Audit complet sur ChatGPT, Gemini et Claude. Plan d'action concret."),
        "badge":              B("badge")    or None,
        "cta_primary_label":  B("cta_label", "Tester ma visibilité — {price}"),
        "cta_primary_href":   B("cta_href", "#contact"),
        "cta_secondary_label": B("cta_secondary_label") or None,
        "cta_secondary_href": B("cta_secondary_href", "#how"),
        "bg_src":             header_url,
    }


def _seed_proof_stat(db: Session, page_type: str, city: Optional[str], profession: Optional[str]) -> dict:
    B = lambda fk, d="": get_block(db, page_type, "proof_stat", fk, profession, city) or d
    stats = []
    for i in range(1, 6):
        val   = B(f"stat_{i}_value")
        label = B(f"stat_{i}_label")
        if val and label:
            stats.append({"value": val, "label": label})
    return {"stats": stats or [
        {"value": "87%", "label": "des professionnels testés sont invisibles sur les IA"},
        {"value": "3 IA", "label": "testées simultanément\nChatGPT · Gemini · Claude"},
        {"value": "48h",  "label": "délai de livraison\nrapport + plan d'action"},
    ]}


def _seed_proof_visual(db: Session, page_type: str, city: Optional[str], profession: Optional[str]) -> dict:
    B = lambda fk, d="": get_block(db, page_type, "proof_visual", fk, profession, city) or d
    steps = []
    for i in range(1, 7):
        title = B(f"step_{i}_title")
        desc  = B(f"step_{i}_desc")
        if not desc:
            break
        steps.append({"title": title or None, "description": desc})
    return {
        "title":    B("title",    "Comment fonctionne l'audit"),
        "subtitle": B("subtitle", "Un test automatisé, rigoureux, répété sur les 3 grandes IA du marché."),
        "steps":    steps or [
            {"description": "Nous simulons les requêtes de vos futurs clients sur ChatGPT, Gemini et Claude."},
            {"description": "Nous analysons si votre entreprise est citée, et comment."},
            {"description": "Vous recevez un rapport détaillé avec votre score de visibilité IA."},
            {"description": "Vous obtenez un plan d'action concret pour améliorer votre référencement."},
        ],
    }


def _seed_faq(db: Session, page_type: str, city: Optional[str], profession: Optional[str]) -> dict:
    B = lambda fk, d="": get_block(db, page_type, "faq", fk, profession, city) or d
    items = []
    for i in range(1, 11):
        q = B(f"q{i}")
        a = B(f"a{i}")
        if not q:
            break
        items.append({"question": q, "answer": a})
    return {
        "title": B("title", "Questions fréquentes"),
        "items": items or [
            {"question": "Pourquoi suis-je invisible sur les IA ?",
             "answer": "Les IA recommandent les entreprises qu'elles connaissent. Si votre présence en ligne est faible, elles citent vos concurrents."},
            {"question": "Pour quel type d'entreprise ?",
             "answer": "Tout professionnel en contact avec des particuliers : artisans, prestataires de services, professions libérales."},
            {"question": "Quel délai pour recevoir mon rapport ?",
             "answer": "48 heures après votre commande, vous recevez votre rapport complet par email."},
            {"question": "Comment améliorer ma visibilité IA ?",
             "answer": "Nous vous fournissons un plan d'action concret avec les actions prioritaires à mener."},
        ],
    }


def _seed_cta(db: Session, page_type: str, city: Optional[str], profession: Optional[str]) -> dict:
    B = lambda fk, d="": get_block(db, page_type, "cta_final", fk, profession, city) or d
    return {
        "title":     B("title",     "Votre audit en 48h — {price}"),
        "subtitle":  B("subtitle",  "Rejoignez les professionnels qui savent où ils en sont sur les IA."),
        "btn_label": B("btn_label", "Commander mon audit"),
        "btn_href":  B("btn_href",  "#contact"),
    }


def _seed_pricing(db: Session) -> dict:
    """Construit le seed pricing depuis offers_module."""
    try:
        from offers_module.database import list_offers
        from offers_module import get_db as offers_get_db
        with offers_get_db() as offers_db:
            offers = list_offers(offers_db)
        cards = []
        for i, offer in enumerate(offers):
            cards.append({
                "name":        offer.name,
                "price":       f"{offer.price:.0f}€" if hasattr(offer, "price") else "Sur devis",
                "period":      None,
                "features":    json.loads(offer.features) if isinstance(offer.features, str) else (offer.features or []),
                "is_featured": i == 1,
                "cta_label":   "Commander",
                "cta_href":    "#",
            })
        if cards:
            return {"title": "Nos offres", "subtitle": "", "cards": cards}
    except Exception:
        pass
    # Fallback — offre unique
    return {
        "title": "Audit de visibilité IA",
        "subtitle": "Rapport complet + plan d'action",
        "cards": [{
            "name": "Audit Complet",
            "price": "{price}",
            "features": [
                "15 requêtes testées sur 3 IA",
                "ChatGPT · Gemini · Claude",
                "Rapport détaillé en 48h",
                "Plan d'action concret",
                "Support email inclus",
            ],
            "is_featured": True,
            "cta_label": "Commander mon audit",
            "cta_href": "#contact",
        }],
    }


def _seed_footer(db: Session, page_type: str) -> dict:
    return {
        "copyright": "© 2026 PRESENCE_IA — Tous droits réservés",
        "columns": [
            {"title": "Service", "links": [
                {"label": "Comment ça marche", "href": "#how"},
                {"label": "Tarifs", "href": "#pricing"},
                {"label": "FAQ", "href": "#faq"},
            ]},
            {"title": "Légal", "links": [
                {"label": "CGV", "href": "/cgv"},
                {"label": "Mentions légales", "href": "/mentions"},
            ]},
        ],
        "social_links": [],
    }


# ── Fonction principale ───────────────────────────────────────────────────────

def build_manifest_from_db(
    db: Session,
    page_type: str = "landing",
    city: Optional[str] = None,
    profession: Optional[str] = None,
) -> ManifestPage:
    """
    Construit un ManifestPage complet depuis la DB PRESENCE_IA.

    1. ThemePreset depuis ThemeConfigDB
    2. Structure des sections depuis PageLayoutDB (ordre + enabled)
    3. Seeds des blocs depuis ContentBlockDB (textes éditables admin)
    4. Hero bg_src depuis CityHeaderDB (si landing + city)
    5. Pricing depuis offers_module
    """
    # 1. Thème
    theme = db_get_theme(db)

    # 2. Structure des sections (layout)
    section_defs = _LANDING_SECTIONS if page_type == "landing" else _HOME_SECTIONS
    layout_row = db_get_page_layout(db, page_type)
    if layout_row:
        try:
            layout_cfg = {s["key"]: s for s in json.loads(layout_row.sections_config)}
        except Exception:
            layout_cfg = {}
    else:
        layout_cfg = {}

    # 3. Hero bg_src (landing uniquement) — toujours chercher un header disponible
    header_url = None
    if page_type == "landing":
        from ...models import CityHeaderDB
        hdr = db_get_header(db, city) if city else None
        if not hdr:
            hdr = db.query(CityHeaderDB).first()
        header_url = hdr.url if hdr else None

    # 4. Seeds des blocs
    seed_builders = {
        "hero":        lambda: _seed_hero(db, page_type, city, profession, header_url),
        "proof_stat":  lambda: _seed_proof_stat(db, page_type, city, profession),
        "proof_visual": lambda: _seed_proof_visual(db, page_type, city, profession),
        "pricing":     lambda: _seed_pricing(db),
        "faq":         lambda: _seed_faq(db, page_type, city, profession),
        "cta_final":   lambda: _seed_cta(db, page_type, city, profession),
        "footer":      lambda: _seed_footer(db, page_type),
    }

    # 5. Construire les sections ManifestSection (avec order/enabled depuis layout_cfg)
    manifest_sections = []
    for i, sec_def in enumerate(section_defs):
        key = sec_def["key"]
        cfg = layout_cfg.get(key, {})
        enabled = cfg.get("enabled", True)
        order   = cfg.get("order", i)

        seed = seed_builders.get(key, lambda: {})()

        manifest_sections.append(ManifestSection(
            key=key,
            enabled=enabled,
            order=order,
            columns=[ManifestColumn(
                span=12,
                block=ManifestBlockConfig(
                    block_type=sec_def["block_type"],
                    structure=sec_def["structure"],
                    seed=seed,
                ),
            )],
        ))

    # 6. Placeholder context
    price = _PLACEHOLDER_DEFAULTS["price"]  # "97€" par défaut
    placeholder_context = {
        **_PLACEHOLDER_DEFAULTS,
        "city":       city or _PLACEHOLDER_DEFAULTS["city"],
        "profession": profession or _PLACEHOLDER_DEFAULTS["profession"],
        "price":      price,
    }

    return ManifestPage(
        page_type=page_type,
        lang="fr",
        title=f"Audit IA — {city or 'votre ville'}" if page_type == "landing" else "Audit de visibilité IA",
        theme=theme,
        sections=manifest_sections,
        placeholder_context=placeholder_context,
    )


# ── Fonctions de rendu ────────────────────────────────────────────────────────

def render_landing(db: Session, city: Optional[str] = None, profession: Optional[str] = None,
                   extra_body_end: str = "") -> str:
    manifest = build_manifest_from_db(db, page_type="landing", city=city, profession=profession)
    page = parse_manifest(manifest)
    return render_page(page, extra_body_end=extra_body_end)


def render_home(db: Session, extra_body_end: str = "") -> str:
    manifest = build_manifest_from_db(db, page_type="home")
    page = parse_manifest(manifest)
    return render_page(page, extra_body_end=extra_body_end)
