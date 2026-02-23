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
    hero_subtitle = B("hero", "subtitle",     "Nous testons votre visibilité sur 3 IA et 5 requêtes. Rapport en 48h. Plan d'action concret.")
    hero_cta      = B("hero", "cta_primary",  "Tester ma visibilité — 97€")
    cta_title     = B("cta_final", "title",    "Votre audit IA en 48h — 97€")
    cta_subtitle  = B("cta_final", "subtitle", "Rejoignez les professionnels qui savent où ils en sont sur les IA.")
    cta_btn       = B("cta_final", "btn_label","Commander mon audit")

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
:root{--p:#4f46e5;--pd:#3730a3;--t:#111827;--m:#6b7280;--bg:#f9fafb;--r:12px}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;color:var(--t);line-height:1.6}
a{color:inherit}
.nav{display:flex;align-items:center;justify-content:space-between;padding:14px 24px;border-bottom:1px solid #e5e7eb;background:#fff;position:sticky;top:0;z-index:10}
.nav__brand{font-weight:800;font-size:1.1rem;color:var(--p);text-decoration:none;letter-spacing:-.02em}
.nav__cta{background:var(--p);color:#fff;padding:10px 22px;border-radius:8px;font-weight:600;font-size:.9rem;text-decoration:none}
.hero{background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);color:#fff;text-align:center;padding:96px 24px 80px}
.hero h1{font-size:clamp(1.9rem,5vw,3rem);font-weight:800;line-height:1.2;max-width:800px;margin:0 auto 24px}
.hero p{font-size:1.1rem;max-width:560px;margin:0 auto 40px;opacity:.88;line-height:1.75}
.btn-hero{display:inline-block;background:#fff;color:var(--p);font-weight:700;padding:16px 38px;border-radius:50px;text-decoration:none;font-size:1rem;box-shadow:0 4px 20px rgba(0,0,0,.15);transition:transform .15s,box-shadow .15s}
.btn-hero:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,0,0,.2)}
.stats-bar{background:#fff;border-bottom:1px solid #e5e7eb;padding:40px 24px}
.stats-bar__grid{display:flex;justify-content:center;gap:56px;flex-wrap:wrap;max-width:900px;margin:0 auto}
.stat{text-align:center}
.stat__val{font-size:2.2rem;font-weight:800;color:var(--p)}
.stat__lbl{font-size:.82rem;color:var(--m);margin-top:4px;max-width:140px}
.section{padding:80px 24px}
.section--alt{background:var(--bg)}
.container{max-width:1000px;margin:0 auto}
.section__title{text-align:center;font-size:clamp(1.5rem,3vw,2rem);font-weight:800;margin-bottom:12px}
.section__sub{text-align:center;color:var(--m);margin-bottom:52px;font-size:1.05rem}
.steps-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:24px}
.step{background:#fff;border-radius:var(--r);padding:28px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.step__num{width:40px;height:40px;background:var(--p);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.9rem;margin-bottom:16px}
.step__title{font-weight:700;margin-bottom:8px}
.step__desc{font-size:.9rem;color:var(--m);line-height:1.6}
.faq-list{max-width:760px;margin:0 auto}
.faq-item{border-bottom:1px solid #e5e7eb}
.faq-q{width:100%;text-align:left;padding:20px 0;font-weight:600;font-size:1rem;background:none;border:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:16px;color:var(--t)}
.faq-icon{flex-shrink:0;color:var(--p);transition:transform .2s;font-style:normal}
.faq-item.open .faq-icon{transform:rotate(180deg)}
.faq-a{padding:0 0 20px;color:var(--m);line-height:1.7}
.cta-section{background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);color:#fff;text-align:center;padding:80px 24px}
.cta-section h2{font-size:clamp(1.6rem,3vw,2.3rem);font-weight:800;margin-bottom:16px}
.cta-section p{font-size:1.05rem;opacity:.9;margin:0 auto 36px;max-width:520px;line-height:1.7}
.btn-cta{display:inline-block;background:#fff;color:var(--p);font-weight:700;padding:18px 46px;border-radius:50px;text-decoration:none;font-size:1.05rem;box-shadow:0 4px 20px rgba(0,0,0,.15)}
footer{background:#111827;color:#9ca3af;padding:60px 24px 32px}
.footer__inner{max-width:1000px;margin:0 auto;display:flex;justify-content:space-between;flex-wrap:wrap;gap:40px;margin-bottom:40px}
.footer__col h4{color:#fff;font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px}
.footer__col a{display:block;color:#9ca3af;text-decoration:none;font-size:.85rem;margin-bottom:10px}
.footer__col a:hover{color:#fff}
.footer__bottom{max-width:1000px;margin:0 auto;padding-top:24px;border-top:1px solid #374151;font-size:.8rem}
@media(max-width:600px){.stats-bar__grid{gap:32px}.footer__inner{flex-direction:column;gap:24px}}
"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Présence IA — Audit de visibilité sur ChatGPT, Gemini et Claude</title>
  <meta name="description" content="Testez si votre entreprise apparaît dans les réponses de ChatGPT, Gemini et Claude. Rapport personnalisé en 48h.">
  <style>{css}</style>
</head>
<body>

<nav class="nav">
  <a class="nav__brand" href="/">Présence IA</a>
  <a class="nav__cta" href="#contact">Tester ma visibilité</a>
</nav>

<div class="hero">
  <h1>{hero_title}</h1>
  <p>{hero_subtitle}</p>
  <a class="btn-hero" href="#contact">{hero_cta}</a>
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
