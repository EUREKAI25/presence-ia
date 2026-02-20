# EURKAI Page Builder

Module standalone de construction de pages modulaires pour l'écosystème EURKAI.

## Principe

Vous définissez **2 couleurs + font-size + line-height** → tout le reste (design system, responsive, modules) se dérive automatiquement.

## Installation

```bash
# Depuis GitHub
pip install git+https://github.com/EURKAI25/page-builder.git

# En local (dev)
pip install -e /chemin/vers/page_builder
```

## Usage

### Exemple simple

```python
from page_builder import (
    Page, Section, Column, DesignTokens,
    HeroModule, PricingModule, PricingPlan,
    render_page
)

# Design personnalisé
tokens = DesignTokens(
    primary_color="#e94560",
    secondary_color="#ff7043",
    font_size_base=16,
    line_height_base=1.6
)

# Construction page
page = Page(
    title="Mon SaaS",
    description="Landing page automatisée",
    design_tokens=tokens,
    sections=[
        # Hero
        Section(
            order=0,
            columns=[
                Column(span=12, module=HeroModule(
                    badge="Nouveau 🚀",
                    title="Automatisez votre business",
                    subtitle="Solution complète pour PME",
                    cta_primary={"label": "Démarrer", "href": "#pricing"},
                    cta_secondary={"label": "En savoir plus", "href": "#features"}
                ))
            ]
        ),
        # Pricing (3 colonnes)
        Section(
            order=1,
            columns=[
                Column(span=4, module=PricingModule(
                    title="Tarifs",
                    plans=[
                        PricingPlan(
                            name="Starter",
                            price="29€/mois",
                            features=["5 projets", "Support email"],
                            cta_href="#signup"
                        ),
                        PricingPlan(
                            name="Pro",
                            price="99€/mois",
                            features=["Projets illimités", "Support prioritaire"],
                            is_featured=True,
                            cta_href="#signup"
                        ),
                        PricingPlan(
                            name="Enterprise",
                            price="Sur mesure",
                            features=["SLA", "Support dédié"],
                            cta_href="#contact"
                        )
                    ]
                ))
            ]
        )
    ]
)

# Génération HTML
html = render_page(page)
print(html)
```

### Avec FastAPI

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from page_builder import render_page

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home():
    page = Page(...)  # Voir exemple ci-dessus
    return HTMLResponse(render_page(page))
```

## Modules disponibles

- **HeroModule** : Badge + titre + sous-titre + 2 CTAs
- **PricingModule** : Grid de plans tarifaires
- **TestimonialsModule** : Témoignages clients
- **ProofModule** : Stats + chiffres clés
- **TextModule** : Bloc texte libre
- **CTAModule** : Call-to-action simple

## Architecture

```
Page → Section → Column → Module → Element
```

- **Page** : Contient design tokens + sections
- **Section** : Ligne avec 1-N colonnes (grid 12 colonnes)
- **Column** : Span 1-12, contient 1 module
- **Module** : Hero, Pricing, Text, etc.
- **Element** : Texte, bouton, image, etc.

## Design System

**Entrées utilisateur** :
- `primary_color` (ex: #667eea)
- `secondary_color` (ex: #764ba2)
- `font_size_base` (ex: 16px)
- `line_height_base` (ex: 1.6)

**Dérivations automatiques** (60+ variables CSS) :
- Couleurs intermédiaires (light, dark, alpha)
- Espacements (xs, sm, md, lg, xl → multiples de 8px)
- Typographie (xs, sm, md, lg, xl → multiples de font_size_base)
- Shadows, radius, transitions

## Responsive

Grid CSS 12 colonnes avec breakpoints automatiques :
- **Desktop** : Grid 12 colonnes
- **Tablet** : Grid adaptative
- **Mobile** : 1 colonne (empilement automatique)

Exemple : 3 cartes pricing côte à côte desktop → empilées mobile.

## Développement

```bash
# Installation dev
cd page_builder
pip install -e ".[dev]"

# Tests
pytest tests/

# Exemple
python examples/simple_landing.py
```

## Licence

MIT
