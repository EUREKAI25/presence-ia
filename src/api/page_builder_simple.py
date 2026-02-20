"""
Page Builder Simple — Version MVP pour PRESENCE_IA
Génère HTML avec design system EURKAI sans modules complexes
"""
import json

def build_page_simple(db, page_type: str, design_preset: str = "default") -> str:
    """Version simplifiée qui génère HTML avec design system dérivé."""

    from ..database import get_block, db_get_page_layout
    from offers_module.database import db_list_offers

    # Design tokens selon preset
    presets = {
        "default": {
            "primary": "#e94560",
            "secondary": "#ff7043",
            "primary_light": "#fef5f7",
            "text": "#1a1a2e",
            "bg": "#fafafa"
        },
        "thalasso": {
            "primary": "#4895b2",
            "secondary": "#8abaa9",
            "primary_light": "#e3f2f7",
            "text": "#1e293b",
            "bg": "#f0f9ff"
        },
        "myhealthprac": {
            "primary": "#b0906f",
            "secondary": "#a28260",
            "primary_light": "#f8f6f3",
            "text": "#1a1a2e",
            "bg": "#faf8f5"
        }
    }

    colors = presets.get(design_preset, presets["default"])

    # Récupérer blocs
    B = lambda sk, fk, **kw: get_block(db, page_type, sk, fk, **kw)
    offers = db_list_offers(db)
    num_offers = len(offers)

    # Construire HTML
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PRESENCE_IA — Référencement IA</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --color-primary: {colors['primary']};
            --color-secondary: {colors['secondary']};
            --color-primary-light: {colors['primary_light']};
            --color-text: {colors['text']};
            --color-bg: {colors['bg']};
            --spacing-unit: 8px;
            --radius-md: 8px;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: var(--color-text);
            background: var(--color-bg);
            line-height: 1.6;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 0 calc(var(--spacing-unit) * 3);
        }}

        /* HEADER */
        header {{
            padding: calc(var(--spacing-unit) * 3) 0;
            border-bottom: 1px solid rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            z-index: 100;
        }}

        nav {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 900px;
            margin: 0 auto;
            padding: 0 calc(var(--spacing-unit) * 3);
        }}

        .logo {{
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--color-text);
        }}

        .logo span {{
            color: var(--color-primary);
        }}

        /* HERO */
        .hero {{
            padding: calc(var(--spacing-unit) * 12) 0 calc(var(--spacing-unit) * 10);
            text-align: center;
            background: linear-gradient(180deg, #fff 0%, var(--color-primary-light) 100%);
        }}

        .hero h1 {{
            font-size: clamp(2rem, 5vw, 3.2rem);
            margin-bottom: calc(var(--spacing-unit) * 3);
            line-height: 1.1;
        }}

        .hero p {{
            font-size: 1.15rem;
            color: #6b7280;
            margin-bottom: calc(var(--spacing-unit) * 5);
            max-width: 600px;
            margin-left: auto;
            margin-right: auto;
        }}

        .hero-btns {{
            display: flex;
            gap: calc(var(--spacing-unit) * 2);
            justify-content: center;
            flex-wrap: wrap;
        }}

        .btn-primary {{
            background: var(--color-primary);
            color: white;
            padding: calc(var(--spacing-unit) * 2) calc(var(--spacing-unit) * 5);
            border-radius: var(--radius-md);
            font-weight: 600;
            border: none;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}

        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.2);
        }}

        .btn-secondary {{
            background: white;
            color: var(--color-text);
            padding: calc(var(--spacing-unit) * 2) calc(var(--spacing-unit) * 5);
            border-radius: var(--radius-md);
            font-weight: 600;
            border: 2px solid #e5e7eb;
            cursor: pointer;
            transition: all 0.3s ease;
        }}

        .btn-secondary:hover {{
            border-color: var(--color-primary);
            color: var(--color-primary);
        }}

        /* SECTIONS */
        section {{
            padding: calc(var(--spacing-unit) * 10) 0;
        }}

        h2 {{
            font-size: clamp(1.75rem, 4vw, 2.5rem);
            margin-bottom: calc(var(--spacing-unit) * 2);
        }}

        /* PRICING */
        .pricing {{
            background: linear-gradient(180deg, #fff 0%, var(--color-primary-light) 100%);
        }}

        /* Grille intelligente adaptative */
        .plans {{
            display: grid;
            gap: calc(var(--spacing-unit) * 3);
            margin-top: calc(var(--spacing-unit) * 6);
        }}

        /* 2 offres : 2 colonnes sur desktop, centrées */
        .plans-2 {{
            grid-template-columns: repeat(2, 1fr);
            max-width: 640px;
            margin-left: auto;
            margin-right: auto;
        }}

        /* 3 offres : 3 colonnes sur desktop */
        .plans-3 {{
            grid-template-columns: repeat(3, 1fr);
        }}

        /* 4+ offres : 4 colonnes sur très large écran */
        .plans-4, .plans-5, .plans-6 {{
            grid-template-columns: repeat(3, 1fr);
        }}

        @media (min-width: 1200px) {{
            .plans-4, .plans-5, .plans-6 {{
                grid-template-columns: repeat(4, 1fr);
            }}
        }}

        /* Tablet : max 2 colonnes */
        @media (max-width: 900px) {{
            .plans-2, .plans-3, .plans-4, .plans-5, .plans-6 {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        /* Mobile : 1 colonne */
        @media (max-width: 768px) {{
            .plans, .plans-2, .plans-3, .plans-4, .plans-5, .plans-6 {{
                grid-template-columns: 1fr;
            }}
        }}

        .plan {{
            background: white;
            border-radius: calc(var(--radius-md) * 1.5);
            padding: calc(var(--spacing-unit) * 4);
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
        }}

        .plan:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        }}

        .plan h3 {{
            font-size: 1.5rem;
            margin-bottom: calc(var(--spacing-unit) * 1);
        }}

        .price {{
            font-size: clamp(2rem, 6vw, 3rem);
            font-weight: 700;
            color: var(--color-primary);
            margin: calc(var(--spacing-unit) * 2) 0;
            line-height: 1.1;
        }}

        .plan ul {{
            list-style: none;
            margin: calc(var(--spacing-unit) * 3) 0;
        }}

        .plan li {{
            padding: calc(var(--spacing-unit) * 1) 0;
            border-bottom: 1px solid #f3f4f6;
        }}

        .plan li::before {{
            content: "✓ ";
            color: var(--color-primary);
            font-weight: 700;
        }}

        @media (max-width: 768px) {{
            .hero h1 {{ font-size: 2rem; }}
            .plans {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <header>
        <nav>
            <div class="logo">PRESENCE<span>_IA</span></div>
            <button class="btn-primary" style="padding: 10px 22px; font-size: 0.9rem;">Démarrer</button>
        </nav>
    </header>

    <section class="hero">
        <div class="container">
            <h1>{B("hero", "title")}</h1>
            <p>{B("hero", "subtitle")}</p>
            <div class="hero-btns">
                <button class="btn-primary">{B("hero", "cta_primary")}</button>
                <button class="btn-secondary">{B("hero", "cta_secondary")}</button>
            </div>
        </div>
    </section>

    <section class="pricing">
        <div class="container">
            <h2 style="text-align: center;">Tarifs transparents</h2>
            <p style="text-align: center; color: #6b7280; margin-bottom: 48px;">Choisissez l'offre qui vous correspond</p>

            <div class="plans plans-{num_offers}">"""

    # Ajouter les plans
    for offer in offers:
        features = json.loads(offer.features or "[]") if isinstance(offer.features, str) else (offer.features or [])
        price_display = f"{int(offer.price)}€" if offer.price == int(offer.price) else f"{offer.price}€"

        html += f"""
                <div class="plan">
                    <h3>{offer.name}</h3>
                    <div class="price">{price_display}</div>
                    <ul>"""

        for feature in features:
            html += f"<li>{feature}</li>"

        html += f"""
                    </ul>
                    <button class="btn-primary" style="width: 100%;" onclick="startCheckout('{offer.id}')">Commander</button>
                </div>"""

    html += """
            </div>
        </div>
    </section>

    <script>
        function startCheckout(offerId) {
            window.location.href = '/checkout?offer_id=' + offerId;
        }
    </script>
</body>
</html>"""

    return html
