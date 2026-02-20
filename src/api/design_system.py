"""
Design System EURKAI — CSS Variables Generator
Génère CSS avec tokens dérivés automatiquement selon preset
"""

def get_design_tokens(preset: str = "default") -> dict:
    """Retourne les tokens de design selon le preset choisi."""
    presets = {
        "default": {
            "primary": "#e94560",
            "secondary": "#ff7043",
            "primary_light": "#fef5f7",
            "primary_lighter": "#fff5f7",
            "text": "#1a1a2e",
            "text_light": "#6b7280",
            "bg": "#fafafa",
            "border": "#e5e7eb",
            "white": "#fff"
        },
        "thalasso": {
            "primary": "#4895b2",
            "secondary": "#8abaa9",
            "primary_light": "#e3f2f7",
            "primary_lighter": "#f0f9ff",
            "text": "#1e293b",
            "text_light": "#64748b",
            "bg": "#f8fafc",
            "border": "#cbd5e1",
            "white": "#fff"
        },
        "myhealthprac": {
            "primary": "#b0906f",
            "secondary": "#a28260",
            "primary_light": "#f8f6f3",
            "primary_lighter": "#faf8f5",
            "text": "#1a1a2e",
            "text_light": "#6b7280",
            "bg": "#faf8f5",
            "border": "#e5e7eb",
            "white": "#fff"
        }
    }
    return presets.get(preset, presets["default"])


def generate_css_with_tokens(preset: str = "default") -> str:
    """Génère le CSS complet avec variables dérivées du preset."""
    tokens = get_design_tokens(preset)

    return f"""
:root {{
    --color-primary: {tokens['primary']};
    --color-secondary: {tokens['secondary']};
    --color-primary-light: {tokens['primary_light']};
    --color-primary-lighter: {tokens['primary_lighter']};
    --color-text: {tokens['text']};
    --color-text-light: {tokens['text_light']};
    --color-bg: {tokens['bg']};
    --color-border: {tokens['border']};
    --color-white: {tokens['white']};
    --spacing-unit: 8px;
    --radius-sm: 6px;
    --radius-md: 8px;
    --radius-lg: 10px;
    --radius-xl: 12px;
    --font-size-sm: 0.85rem;
    --font-size-md: 0.9rem;
    --font-size-base: 1rem;
    --font-size-lg: 1.05rem;
    --font-size-xl: 1.15rem;
}}

* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}

body {{
    font-family: 'Segoe UI', sans-serif;
    background: var(--color-bg);
    color: var(--color-text);
    line-height: 1.6;
}}

a {{
    color: var(--color-primary);
    text-decoration: none;
}}

nav {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: calc(var(--spacing-unit) * 2.5) calc(var(--spacing-unit) * 5);
    border-bottom: 1px solid var(--color-border);
    position: sticky;
    top: 0;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    z-index: 100;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}}

.logo {{
    font-size: 1.3rem;
    font-weight: bold;
    color: var(--color-text);
}}

.logo span {{
    color: var(--color-primary);
}}

.nav-cta {{
    background: var(--color-primary);
    color: var(--color-white);
    padding: calc(var(--spacing-unit) * 1.25) calc(var(--spacing-unit) * 2.75);
    border-radius: var(--radius-sm);
    font-weight: bold;
    font-size: var(--font-size-md);
}}

.hero {{
    text-align: center;
    padding: calc(var(--spacing-unit) * 12.5) calc(var(--spacing-unit) * 2.5) calc(var(--spacing-unit) * 10);
    max-width: 800px;
    margin: 0 auto;
    background: linear-gradient(180deg, var(--color-white) 0%, var(--color-primary-lighter) 100%);
}}

.hero-badge {{
    display: inline-block;
    background: var(--color-white);
    border: 1px solid var(--color-primary);
    color: var(--color-primary);
    padding: calc(var(--spacing-unit) * 0.75) calc(var(--spacing-unit) * 2);
    border-radius: 20px;
    font-size: var(--font-size-sm);
    margin-bottom: calc(var(--spacing-unit) * 3);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}}

.hero h1 {{
    font-size: clamp(2rem, 5vw, 3.2rem);
    color: var(--color-text);
    margin-bottom: calc(var(--spacing-unit) * 2.5);
    line-height: 1.2;
}}

.hero h1 span {{
    color: var(--color-primary);
}}

.hero p {{
    font-size: var(--font-size-xl);
    color: var(--color-text-light);
    max-width: 580px;
    margin: 0 auto calc(var(--spacing-unit) * 4.5);
}}

.hero-btns {{
    display: flex;
    gap: calc(var(--spacing-unit) * 2);
    justify-content: center;
    flex-wrap: wrap;
}}

.btn-primary {{
    background: linear-gradient(90deg, var(--color-primary), var(--color-secondary));
    color: var(--color-white);
    padding: calc(var(--spacing-unit) * 2) calc(var(--spacing-unit) * 4.5);
    border-radius: var(--radius-md);
    font-weight: bold;
    font-size: var(--font-size-lg);
    border: none;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    transition: all 0.3s ease;
}}

.btn-secondary {{
    background: var(--color-white);
    color: var(--color-text);
    padding: calc(var(--spacing-unit) * 2) calc(var(--spacing-unit) * 4.5);
    border-radius: var(--radius-md);
    font-weight: bold;
    font-size: var(--font-size-lg);
    border: 1px solid var(--color-border);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    transition: all 0.3s ease;
}}

.btn-primary:hover {{
    opacity: 0.9;
    transform: translateY(-2px);
}}

.btn-secondary:hover {{
    border-color: var(--color-primary);
    color: var(--color-primary);
}}

.proof {{
    background: linear-gradient(180deg, var(--color-primary-light) 0%, var(--color-white) 100%);
    padding: calc(var(--spacing-unit) * 3.5) calc(var(--spacing-unit) * 2.5);
    text-align: center;
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
}}

.proof > * {{
    max-width: 900px;
    margin-left: auto;
    margin-right: auto;
}}

.proof p {{
    color: var(--color-text-light);
    font-size: var(--font-size-md);
    margin-bottom: calc(var(--spacing-unit) * 1.5);
}}

.proof-stats {{
    display: flex;
    gap: calc(var(--spacing-unit) * 6);
    justify-content: center;
    flex-wrap: wrap;
}}

.stat {{
    text-align: center;
}}

.stat strong {{
    display: block;
    font-size: 1.8rem;
    font-weight: bold;
    color: var(--color-primary);
}}

.stat span {{
    font-size: var(--font-size-sm);
    color: var(--color-text-light);
}}

section {{
    padding: calc(var(--spacing-unit) * 10) calc(var(--spacing-unit) * 2.5);
    max-width: 900px;
    margin: 0 auto;
}}

h2 {{
    font-size: clamp(1.5rem, 3vw, 2.2rem);
    color: var(--color-text);
    margin-bottom: calc(var(--spacing-unit) * 2);
    max-width: 800px;
}}

.sub {{
    color: var(--color-text-light);
    font-size: var(--font-size-lg);
    margin-bottom: calc(var(--spacing-unit) * 6);
    max-width: 700px;
}}

.chat-demo {{
    background: var(--color-white);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: calc(var(--spacing-unit) * 3.5);
    margin: 0 auto calc(var(--spacing-unit) * 7.5);
    max-width: 600px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}}

.chat-q {{
    color: var(--color-text-light);
    font-size: var(--font-size-md);
    margin-bottom: calc(var(--spacing-unit) * 1.5);
}}

.chat-q strong {{
    color: var(--color-text);
}}

.chat-r {{
    background: var(--color-bg);
    border-left: 3px solid var(--color-primary);
    border-radius: var(--radius-sm);
    padding: calc(var(--spacing-unit) * 2);
    font-size: var(--font-size-md);
    color: var(--color-text);
}}

.chat-r .bad {{
    color: var(--color-primary);
    font-weight: bold;
}}

.chat-r .good {{
    color: #2ecc71;
    font-weight: bold;
}}

.steps {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: calc(var(--spacing-unit) * 3);
    margin-top: calc(var(--spacing-unit) * 6);
}}

.step {{
    background: var(--color-white);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: calc(var(--spacing-unit) * 3.5);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    transition: transform 0.2s;
}}

.step:hover {{
    transform: translateY(-4px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}}

.step-num {{
    font-size: 2rem;
    font-weight: bold;
    color: var(--color-primary);
    margin-bottom: calc(var(--spacing-unit) * 1.5);
}}

.step h3 {{
    color: var(--color-text);
    margin-bottom: calc(var(--spacing-unit) * 1);
    font-size: var(--font-size-base);
}}

.step p {{
    color: var(--color-text-light);
    font-size: var(--font-size-md);
}}

.pricing {{
    background: linear-gradient(180deg, var(--color-white) 0%, var(--color-bg) 100%);
    padding: calc(var(--spacing-unit) * 10) calc(var(--spacing-unit) * 2.5);
    border-top: 1px solid var(--color-border);
}}

.pricing-inner {{
    max-width: 960px;
    margin: 0 auto;
    text-align: center;
}}

.plans {{
    display: grid;
    gap: calc(var(--spacing-unit) * 3);
    margin-top: calc(var(--spacing-unit) * 6);
    text-align: left;
}}

/* Grille intelligente selon nombre d'offres */
.plans-2 {{
    grid-template-columns: repeat(2, 1fr);
    max-width: 640px;
    margin-left: auto;
    margin-right: auto;
}}

.plans-3 {{
    grid-template-columns: repeat(3, 1fr);
}}

.plans-4, .plans-5, .plans-6 {{
    grid-template-columns: repeat(3, 1fr);
}}

@media (min-width: 1200px) {{
    .plans-4, .plans-5, .plans-6 {{
        grid-template-columns: repeat(4, 1fr);
    }}
}}

@media (max-width: 900px) {{
    .plans-2, .plans-3, .plans-4, .plans-5, .plans-6 {{
        grid-template-columns: repeat(2, 1fr);
    }}
}}

@media (max-width: 768px) {{
    .plans, .plans-2, .plans-3, .plans-4, .plans-5, .plans-6 {{
        grid-template-columns: 1fr;
    }}
}}

.plan {{
    background: var(--color-white);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: calc(var(--spacing-unit) * 4);
    position: relative;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    transition: transform 0.2s;
}}

.plan:hover {{
    transform: translateY(-4px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}}

.plan.best {{
    border-color: var(--color-primary);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}}

.plan.best::before {{
    content: "Recommandé";
    position: absolute;
    top: -12px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--color-primary);
    color: var(--color-white);
    padding: 4px 16px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: bold;
    white-space: nowrap;
}}

.plan h3 {{
    color: var(--color-text);
    margin-bottom: calc(var(--spacing-unit) * 1);
}}

.price {{
    font-size: clamp(2rem, 6vw, 2.4rem);
    font-weight: bold;
    color: var(--color-primary);
    margin: calc(var(--spacing-unit) * 1.5) 0;
    line-height: 1.1;
}}

.price span {{
    font-size: var(--font-size-base);
    color: var(--color-text-light);
}}

.plan ul {{
    list-style: none;
    margin: calc(var(--spacing-unit) * 2.5) 0 calc(var(--spacing-unit) * 3);
}}

.plan ul li {{
    padding: calc(var(--spacing-unit) * 0.875) 0;
    color: var(--color-text);
    border-bottom: 1px solid var(--color-border);
    font-size: var(--font-size-md);
}}

.plan ul li::before {{
    content: "✓ ";
    color: #2ecc71;
}}

.btn-plan {{
    display: block;
    background: linear-gradient(90deg, var(--color-primary), var(--color-secondary));
    color: var(--color-white);
    padding: calc(var(--spacing-unit) * 1.75);
    border-radius: var(--radius-sm);
    font-weight: bold;
    text-align: center;
    border: none;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    transition: all 0.3s ease;
}}

.btn-plan.ghost {{
    background: var(--color-white);
    border: 1px solid var(--color-primary);
    color: var(--color-primary);
}}

.btn-plan:hover {{
    opacity: 0.9;
    transform: translateY(-2px);
}}

.faq {{
    max-width: 720px;
    margin: 0 auto;
}}

.faq-item {{
    border-bottom: 1px solid var(--color-border);
    padding: calc(var(--spacing-unit) * 2.5) 0;
}}

.faq-item h3 {{
    color: var(--color-text);
    font-size: var(--font-size-base);
    margin-bottom: calc(var(--spacing-unit) * 1);
}}

.faq-item p {{
    color: var(--color-text-light);
    font-size: var(--font-size-md);
}}

.section-problem {{
    background: linear-gradient(135deg, var(--color-primary-lighter) 0%, var(--color-white) 100%);
    padding: calc(var(--spacing-unit) * 10) calc(var(--spacing-unit) * 2.5);
    margin: calc(var(--spacing-unit) * 7.5) 0;
}}

.section-howto {{
    background: var(--color-white);
    padding: calc(var(--spacing-unit) * 10) calc(var(--spacing-unit) * 2.5);
}}

.section-evidence {{
    background: linear-gradient(180deg, var(--color-bg) 0%, var(--color-white) 100%);
    padding: calc(var(--spacing-unit) * 10) calc(var(--spacing-unit) * 2.5);
    margin: calc(var(--spacing-unit) * 7.5) 0;
}}

.cta-final {{
    background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));
    padding: calc(var(--spacing-unit) * 10) calc(var(--spacing-unit) * 2.5);
    text-align: center;
}}

.cta-final h2 {{
    font-size: clamp(1.5rem, 3vw, 2rem);
    color: var(--color-white);
    margin-bottom: calc(var(--spacing-unit) * 2);
}}

.cta-final p {{
    color: var(--color-white);
    margin-bottom: calc(var(--spacing-unit) * 4);
    opacity: 0.9;
}}

footer {{
    background: var(--color-bg);
    padding: calc(var(--spacing-unit) * 4) calc(var(--spacing-unit) * 2.5);
    text-align: center;
    color: var(--color-text-light);
    font-size: var(--font-size-sm);
    border-top: 1px solid var(--color-border);
}}

footer a {{
    color: var(--color-primary);
}}
"""
