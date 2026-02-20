# Changelog

## [0.1.0] - 2026-02-20

### Ajouté
- ✅ Architecture core complète (schemas, design_system, renderer, builder)
- ✅ Modules essentiels : Hero, Pricing, Testimonials, Proof, Text, CTA
- ✅ Design system avec dérivation automatique (60+ variables CSS depuis 4 inputs)
- ✅ Grid CSS 12 colonnes responsive (mobile, tablet, desktop)
- ✅ Support multicolonnes par section
- ✅ Exemples fonctionnels (simple_landing.py, test_design_tokens.py)
- ✅ Tests unitaires (test_schemas.py)
- ✅ Documentation complète (README.md)
- ✅ Package pip installable (pyproject.toml)

### Architecture
- Structure récursive : Page → Section → Column → Module → Element
- Zero build step (CSS variables, pas de compilation SCSS)
- Pydantic v2 strict pour validation
- Compatible FastAPI (HTMLResponse)

### Design System
**Entrées** : 2 couleurs + font-size + line-height

**Sorties automatiques** :
- Couleurs dérivées (light, dark, sémantiques)
- Espacements (xs → 3xl, multiples de spacing_unit)
- Typographie (xs → 4xl, multiples de font_size_base)
- Shadows, radius, transitions

### Modules
- **HeroModule** : Badge + titre + sous-titre + 2 CTAs
- **PricingModule** : Grid de plans tarifaires
- **TestimonialsModule** : Témoignages clients
- **ProofModule** : Stats + chiffres clés
- **TextModule** : Bloc texte libre
- **CTAModule** : Call-to-action simple

### Temps développement
- Phase 1 (Core) : ~2h
- Phase 2 (Modules) : ~1.5h
- Tests + doc : ~1h
- **Total** : ~4.5h (estimé : 4h)
