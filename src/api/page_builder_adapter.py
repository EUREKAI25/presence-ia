"""
Page Builder Adapter — PRESENCE_IA
Convertit PageLayoutDB + blocs → Page schema EURKAI → HTML
"""
import json
from pathlib import Path
import sys

# Import page_builder depuis EURKAI
page_builder_path = Path(__file__).parent.parent.parent.parent / "EURKAI" / "MODULES" / "page_builder" / "src"
sys.path.insert(0, str(page_builder_path))

from core.schemas import Page, Section, Column, DesignTokens
from modules.hero import HeroModule
from modules.text import TextModule
from modules.cta import CTAModule
from modules.pricing import PricingModule
from modules.proof import ProofModule
from renderer.html import render_page


def build_page_from_db(db, page_type: str, design_preset: str = "default") -> str:
    """
    Convertit PageLayoutDB + blocs → HTML complet avec design system EURKAI.

    Args:
        db: Session SQLAlchemy
        page_type: "home" ou "landing"
        design_preset: "default", "thalasso", "myhealthprac"

    Returns:
        HTML complet
    """
    from ...database import get_block, db_get_page_layout
    from offers_module.database import db_list_offers

    # Charger layout
    layout = db_get_page_layout(db, page_type)
    if layout:
        sections_config = json.loads(layout.sections_config)
    else:
        # Config par défaut
        sections_config = [
            {"key": "hero", "enabled": True, "order": 0},
            {"key": "proof_stat", "enabled": True, "order": 1},
            {"key": "pricing", "enabled": True, "order": 2},
            {"key": "cta", "enabled": True, "order": 3},
        ]

    # Helper pour récupérer blocs
    B = lambda sk, fk, **kw: get_block(db, page_type, sk, fk, **kw)

    # Design tokens selon preset
    design_tokens = get_design_tokens(design_preset)

    # Construire sections
    sections = []

    for config in sections_config:
        if not config.get("enabled", True):
            continue

        key = config["key"]
        order = config.get("order", 0)

        # Mapper chaque section key → Module
        module = None

        if key == "hero":
            module = HeroModule(
                badge_text="✨ Référencement IA automatisé",
                title=B("hero", "title"),
                subtitle=B("hero", "subtitle"),
                cta_primary={
                    "label": B("hero", "cta_primary"),
                    "href": "#pricing"
                },
                cta_secondary={
                    "label": B("hero", "cta_secondary"),
                    "href": "#proof"
                }
            )

        elif key == "proof_stat":
            module = ProofModule(
                title="Preuve de résultats",
                stats=[
                    {
                        "value": B("proof_stat", "stat_1_value"),
                        "label": B("proof_stat", "stat_1_label")
                    },
                    {
                        "value": B("proof_stat", "stat_2_value"),
                        "label": B("proof_stat", "stat_2_label")
                    },
                    {
                        "value": B("proof_stat", "stat_3_value"),
                        "label": B("proof_stat", "stat_3_label")
                    }
                ],
                sources=[
                    {
                        "url": B("proof_stat", "source_url_1"),
                        "label": B("proof_stat", "source_label_1")
                    } if B("proof_stat", "source_url_1") else None,
                    {
                        "url": B("proof_stat", "source_url_2"),
                        "label": B("proof_stat", "source_label_2")
                    } if B("proof_stat", "source_url_2") else None,
                ]
            )

        elif key == "pricing":
            offers = db_list_offers(db)
            plans = []
            for o in offers:
                features = json.loads(o.features or "[]") if isinstance(o.features, str) else (o.features or [])
                plans.append({
                    "name": o.name,
                    "price": f"{int(o.price)}€" if o.price == int(o.price) else f"{o.price}€",
                    "features": features,
                    "cta": {
                        "label": "Commander",
                        "href": f"javascript:startCheckout('{o.id}')"
                    },
                    "highlighted": getattr(o, 'highlighted', False)
                })

            module = PricingModule(
                title="Tarifs transparents",
                subtitle="Choisissez l'offre qui vous correspond",
                plans=plans
            )

        elif key == "cta":
            module = CTAModule(
                title=B("cta", "title"),
                subtitle=B("cta", "subtitle"),
                cta={
                    "label": B("cta", "btn_label"),
                    "href": "#pricing"
                }
            )

        elif key == "problem" or key == "proof_visual" or key == "faq":
            # Pour l'instant, TextModule simple
            module = TextModule(
                content=f"<h2>{B(key, 'title')}</h2><p>{B(key, 'subtitle')}</p>"
            )

        if module:
            sections.append(Section(
                columns=[Column(span=12, module=module)],
                order=order,
                bg_color="transparent"
            ))

    # Trier par order
    sections.sort(key=lambda s: s.order)

    # Construire Page
    page = Page(
        title=f"PRESENCE_IA — {page_type.title()}",
        description="Référencement IA automatisé pour professionnels",
        design_tokens=design_tokens,
        sections=sections
    )

    # Render
    html = render_page(page)

    # Ajouter script checkout (spécifique PRESENCE_IA)
    checkout_script = """
    <script>
        function startCheckout(offerId) {
            window.location.href = '/checkout?offer_id=' + offerId;
        }
    </script>
    """

    html = html.replace("</body>", f"{checkout_script}</body>")

    return html


def get_design_tokens(preset: str = "default") -> DesignTokens:
    """Retourne les design tokens selon le preset choisi."""

    presets = {
        "default": DesignTokens(
            primary_color="#e94560",  # Rose PRESENCE_IA actuel
            secondary_color="#ff7043",
            font_size_base=16,
            line_height_base=1.6,
            spacing_unit=8
        ),
        "thalasso": DesignTokens(
            primary_color="#4895b2",  # Bleu océan
            secondary_color="#8abaa9",  # Vert d'eau
            font_size_base=16,
            line_height_base=1.6,
            spacing_unit=8
        ),
        "myhealthprac": DesignTokens(
            primary_color="#b0906f",  # Beige doré
            secondary_color="#a28260",  # Bronze
            font_size_base=16,
            line_height_base=1.6,
            spacing_unit=8
        )
    }

    return presets.get(preset, presets["default"])
