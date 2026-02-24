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
    """Page d'accueil — HTML direct (indépendant de page_builder)."""
    B = lambda sk, fk, d="": get_block(db, "home", sk, fk) or d

    hero_title    = B("hero", "title",        "Quand vos clients demandent à ChatGPT,\nil cite vos concurrents. Pas vous.").replace("\n", "<br>")
    hero_subtitle = B("hero", "subtitle",     "Nous testons votre visibilité et réalisons votre plan d'action personnalisé.")
    hero_cta      = B("hero", "cta_primary",  "Tester ma visibilité — 97€")
    cta_title     = B("cta", "title",    "Votre audit IA en 48h — 97€")
    cta_subtitle  = B("cta", "subtitle", "Rejoignez les professionnels qui savent où ils en sont sur les IA.")
    cta_btn       = B("cta", "btn_label","Commander mon audit")

    # FAQ (jusqu'à 8 Q/R depuis ContentBlockDB, sinon défauts)
    _faq_defaults = [
        ("Pourquoi suis-je invisible sur les IA ?",
         "Les IA recommandent les entreprises qu'elles connaissent. Si votre présence en ligne est faible (pas de fiche Google, peu d'avis, site mal référencé), elles citent vos concurrents."),
        ("Pour quel type d'entreprise ?",
         "Tout professionnel en contact avec des particuliers : artisans, prestataires de services, cuisinistes, piscinistes, professions libérales..."),
        ("Combien de temps pour recevoir mon rapport ?",
         "48 heures après votre commande, vous recevez votre rapport complet par email avec votre score et le plan d'action."),
        ("Qu'est-ce que le plan d'action contient ?",
         "Une liste des actions prioritaires pour améliorer votre visibilité sur ChatGPT, Gemini et Claude : fiche Google, contenu, avis clients, présence sur les annuaires IA..."),
        ("Est-ce que ça remplace le SEO ?",
         "Non, c'est complémentaire. Le SEO optimise votre visibilité sur Google. Le référencement IA optimise votre présence dans les réponses de ChatGPT, Gemini et Claude."),
        ("Comment améliorer ma visibilité après l'audit ?",
         "Nous proposons un accompagnement mensuel pour mettre en œuvre le plan d'action et suivre l'évolution de votre score sur les IA."),
    ]
    faq_items = []
    for i in range(1, 9):
        q = B("faq", f"q{i}")
        a = B("faq", f"a{i}")
        if q and a:
            faq_items.append((q, a))
    if not faq_items:
        faq_items = _faq_defaults

    faq_html = ""
    for i, (q, a) in enumerate(faq_items):
        faq_html += (
            f'<div class="faq-item">'
            f'<button class="faq-q" aria-expanded="false" onclick="toggleFaq(this)">'
            f'{q}<span class="faq-icon">▾</span></button>'
            f'<div class="faq-a" hidden>{a}</div>'
            f'</div>'
        )

    # Steps
    _steps_defaults = [
        ("Simulation client", "Nous simulons les requêtes de vos futurs clients sur ChatGPT, Gemini et Claude."),
        ("Analyse de la réponse", "Nous vérifions si votre entreprise est citée, en quelle position, et comment."),
        ("Rapport personnalisé", "Vous recevez un rapport détaillé avec votre score de visibilité IA et celui de vos concurrents."),
        ("Plan d'action", "Vous obtenez une liste des actions concrètes pour améliorer votre référencement IA."),
    ]
    steps_html = ""
    for i, (title, desc) in enumerate(_steps_defaults, 1):
        steps_html += (
            f'<div class="step">'
            f'<div class="step__num">{i}</div>'
            f'<div class="step__title">{title}</div>'
            f'<div class="step__desc">{desc}</div>'
            f'</div>'
        )

    css = """
:root{--blue:#2563eb;--dark:#0f172a;--slate:#1e293b;--t:#1e293b;--m:#64748b;--bg:#f8fafc;--r:10px}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',sans-serif;color:var(--t);line-height:1.6;background:#fff}
a{color:inherit}
/* NAV */
.nav{display:flex;align-items:center;justify-content:space-between;padding:0 32px;height:64px;background:#fff;border-bottom:1px solid #e2e8f0;position:sticky;top:0;z-index:20}
.nav__brand{font-weight:800;font-size:1.05rem;color:var(--dark);text-decoration:none;letter-spacing:-.02em;display:flex;align-items:center;gap:8px}
.nav__brand-dot{width:8px;height:8px;background:var(--blue);border-radius:50%;display:inline-block}
.nav__cta{background:var(--blue);color:#fff;padding:10px 24px;border-radius:8px;font-weight:600;font-size:.875rem;text-decoration:none;transition:background .15s}
.nav__cta:hover{background:#1d4ed8}
/* HERO */
.hero{background:var(--dark);color:#fff;padding:100px 24px 88px;text-align:center;position:relative;overflow:hidden}
.hero::before{content:"";position:absolute;inset:0;background:radial-gradient(ellipse 80% 60% at 50% -10%,rgba(37,99,235,.35) 0%,transparent 70%);pointer-events:none}
.hero__badge{display:inline-flex;align-items:center;gap:6px;background:rgba(37,99,235,.15);border:1px solid rgba(37,99,235,.3);color:#93c5fd;font-size:.75rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:5px 14px;border-radius:100px;margin-bottom:32px}
.hero h1{font-size:clamp(2rem,5vw,3.2rem);font-weight:800;line-height:1.15;max-width:820px;margin:0 auto 24px;letter-spacing:-.03em}
.hero h1 em{font-style:normal;color:#60a5fa}
.hero p{font-size:1.1rem;max-width:540px;margin:0 auto 44px;color:#94a3b8;line-height:1.8}
.btn-hero{display:inline-flex;align-items:center;gap:10px;background:var(--blue);color:#fff;font-weight:700;padding:16px 36px;border-radius:10px;text-decoration:none;font-size:1rem;box-shadow:0 4px 24px rgba(37,99,235,.4);transition:all .15s}
.btn-hero:hover{background:#1d4ed8;transform:translateY(-1px);box-shadow:0 8px 32px rgba(37,99,235,.5)}
.btn-hero-arrow{font-size:1.1rem;transition:transform .15s}
.btn-hero:hover .btn-hero-arrow{transform:translateX(3px)}
/* STATS */
.stats-bar{background:#fff;border-bottom:1px solid #e2e8f0;padding:44px 24px}
.stats-bar__grid{display:flex;justify-content:center;gap:0;flex-wrap:wrap;max-width:860px;margin:0 auto}
.stat{text-align:center;padding:0 48px;border-right:1px solid #e2e8f0}
.stat:last-child{border-right:none}
.stat__val{font-size:2rem;font-weight:800;color:var(--dark);letter-spacing:-.04em}
.stat__lbl{font-size:.8rem;color:var(--m);margin-top:4px;line-height:1.4}
/* SECTIONS */
.section{padding:88px 24px}
.section--alt{background:var(--bg)}
.container{max-width:1040px;margin:0 auto}
.section__eyebrow{text-align:center;font-size:.75rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--blue);margin-bottom:12px}
.section__title{text-align:center;font-size:clamp(1.6rem,3vw,2.2rem);font-weight:800;margin-bottom:12px;letter-spacing:-.03em;color:var(--dark)}
.section__sub{text-align:center;color:var(--m);margin-bottom:56px;font-size:1rem;max-width:560px;margin-left:auto;margin-right:auto}
/* STEPS */
.steps-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px}
.step{background:#fff;border:1px solid #e2e8f0;border-radius:var(--r);padding:28px 24px;position:relative}
.step__num{width:36px;height:36px;background:var(--dark);color:#fff;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.85rem;margin-bottom:16px;font-variant-numeric:tabular-nums}
.step__title{font-weight:700;margin-bottom:8px;font-size:.95rem;color:var(--dark)}
.step__desc{font-size:.88rem;color:var(--m);line-height:1.65}
/* FAQ */
.faq-list{max-width:720px;margin:0 auto;border:1px solid #e2e8f0;border-radius:var(--r);overflow:hidden}
.faq-item{border-bottom:1px solid #e2e8f0}
.faq-item:last-child{border-bottom:none}
.faq-q{width:100%;text-align:left;padding:20px 24px;font-weight:600;font-size:.95rem;background:#fff;border:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:16px;color:var(--dark);transition:background .1s}
.faq-q:hover{background:#f8fafc}
.faq-icon{flex-shrink:0;color:var(--blue);transition:transform .2s;font-size:.8rem}
.faq-item.open .faq-icon{transform:rotate(180deg)}
.faq-a{display:none;padding:0 24px 20px;color:var(--m);line-height:1.75;font-size:.9rem;background:#fff}
/* CTA */
.cta-section{background:var(--dark);color:#fff;text-align:center;padding:88px 24px;position:relative;overflow:hidden}
.cta-section::before{content:"";position:absolute;inset:0;background:radial-gradient(ellipse 70% 80% at 50% 110%,rgba(37,99,235,.3) 0%,transparent 70%)}
.cta-section h2{font-size:clamp(1.8rem,3vw,2.5rem);font-weight:800;margin-bottom:16px;letter-spacing:-.03em;position:relative}
.cta-section p{font-size:1rem;color:#94a3b8;margin:0 auto 40px;max-width:480px;line-height:1.75;position:relative}
.btn-cta{display:inline-flex;align-items:center;gap:10px;background:var(--blue);color:#fff;font-weight:700;padding:18px 44px;border-radius:10px;text-decoration:none;font-size:1rem;box-shadow:0 4px 24px rgba(37,99,235,.4);position:relative;transition:all .15s}
.btn-cta:hover{background:#1d4ed8;transform:translateY(-1px)}
/* FOOTER */
footer{background:var(--slate);color:#94a3b8;padding:56px 24px 28px}
.footer__inner{max-width:1040px;margin:0 auto;display:flex;justify-content:space-between;flex-wrap:wrap;gap:40px;padding-bottom:40px}
.footer__col h4{color:#e2e8f0;font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:16px}
.footer__col a{display:block;color:#94a3b8;text-decoration:none;font-size:.85rem;margin-bottom:10px;transition:color .1s}
.footer__col a:hover{color:#fff}
.footer__logo{font-weight:800;font-size:1rem;color:#fff;margin-bottom:10px}
.footer__tagline{font-size:.82rem;color:#64748b;line-height:1.5;max-width:220px}
.footer__bottom{max-width:1040px;margin:0 auto;padding-top:24px;border-top:1px solid #334155;font-size:.78rem;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
@media(max-width:640px){.stat{padding:0 24px;border-right:none;border-bottom:1px solid #e2e8f0;padding-bottom:24px;margin-bottom:8px}.stat:last-child{border-bottom:none}.steps-grid{grid-template-columns:1fr}.footer__inner{flex-direction:column;gap:28px}}
"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Présence IA — Audit de visibilité sur ChatGPT, Gemini et Claude</title>
  <meta name="description" content="Testez si votre entreprise apparaît dans les réponses de ChatGPT, Gemini et Claude. Rapport personnalisé en 48h.">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='%232563eb'/><circle cx='16' cy='16' r='3.5' fill='white'/><circle cx='16' cy='16' r='8' stroke='white' stroke-width='1.5' fill='none' opacity='.55'/><circle cx='16' cy='16' r='13' stroke='white' stroke-width='1' fill='none' opacity='.25'/></svg>">
  <style>{css}</style>
</head>
<body>

<nav class="nav">
  <a class="nav__brand" href="/" style="display:flex;align-items:center;gap:9px;text-decoration:none"><svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><rect width="28" height="28" rx="7" fill="#2563eb"/><circle cx="14" cy="14" r="3" fill="white"/><circle cx="14" cy="14" r="7" stroke="white" stroke-width="1.5" fill="none" opacity=".55"/><circle cx="14" cy="14" r="11" stroke="white" stroke-width="1" fill="none" opacity=".25"/></svg><span>Présence&nbsp;<span style="color:#2563eb">IA</span></span></a>
  <a class="nav__cta" href="#contact">Tester ma visibilité</a>
</nav>

<div class="hero">
  <div class="hero__badge">Audit Présence IA</div>
  <h1>{hero_title}</h1>
  <p>{hero_subtitle}</p>
  <a class="btn-hero" href="#contact">{hero_cta} <span class="btn-hero-arrow">→</span></a>
</div>

<div class="stats-bar">
  <div class="stats-bar__grid">
    <div class="stat"><div class="stat__val">87%</div><div class="stat__lbl">des pros testés sont invisibles sur les IA</div></div>
    <div class="stat"><div class="stat__val">3 IA</div><div class="stat__lbl">testées : ChatGPT · Gemini · Claude</div></div>
    <div class="stat"><div class="stat__val">48h</div><div class="stat__lbl">délai de livraison rapport + plan d'action</div></div>
  </div>
</div>

<div class="section section--alt" id="how">
  <div class="container">
    <h2 class="section__title">Comment fonctionne l'audit</h2>
    <p class="section__sub">Un test automatisé, rigoureux, répété sur les 3 grandes IA du marché.</p>
    <div class="steps-grid">{steps_html}</div>
  </div>
</div>

<div class="section" id="faq">
  <div class="container">
    <p class="section__eyebrow">FAQ</p>
    <h2 class="section__title">Questions fréquentes</h2>
    <div class="faq-list">{faq_html}</div>
  </div>
</div>

<div class="cta-section" id="contact">
  <h2>{cta_title}</h2>
  <p>{cta_subtitle}</p>
  <a class="btn-cta" href="https://calendly.com/contact-presence-ia/30min">{cta_btn}</a>
</div>

<footer>
  <div class="footer__inner">
    <div class="footer__col">
      <h4>Service</h4>
      <a href="#how">Comment ça marche</a>
      <a href="#faq">FAQ</a>
      <a href="#contact">Commander</a>
    </div>
    <div class="footer__col">
      <h4>Légal</h4>
      <a href="/cgv">CGV</a>
      <a href="/mentions">Mentions légales</a>
    </div>
    <div class="footer__col">
      <h4>Contact</h4>
      <a href="mailto:contact@presence-ia.com">contact@presence-ia.com</a>
    </div>
  </div>
  <div class="footer__bottom">
    <p>© 2026 Présence IA — Tous droits réservés</p>
  </div>
</footer>

<script>
function toggleFaq(btn) {{
  const item = btn.closest('.faq-item');
  const ans  = btn.nextElementSibling;
  const open = !ans.hidden;
  ans.hidden = open;
  btn.setAttribute('aria-expanded', !open);
  item.classList.toggle('open', !open);
}}
</script>

{extra_body_end}
</body>
</html>"""
