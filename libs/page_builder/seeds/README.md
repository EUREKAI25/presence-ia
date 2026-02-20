# Seeds — page_builder v0.2

Les seeds sont des fichiers JSON décrivant une page complète au format `ManifestPage`.

## Utilisation

```python
import json
from page_builder import ManifestPage, parse_manifest, render_page

with open("seeds/demo_landing.json") as f:
    manifest = ManifestPage(**json.load(f))

# Injecter des valeurs contextuelles
manifest.placeholder_context = {"project_name": "Mon SaaS", "price": "49€"}

html = render_page(parse_manifest(manifest))
```

## Fichiers disponibles

| Fichier | Description |
|---|---|
| `demo_landing.json` | Landing page générique complète (navbar → hero → stats → steps → pricing → faq → cta → footer) |

## Créer un seed pour un nouveau projet

1. Copier `demo_landing.json`
2. Adapter `design_tokens` (couleurs de votre marque)
3. Remplacer les clés `@namespace.key` par vos propres clés i18n **ou** par du texte direct
4. Ajouter vos `placeholder_context` (variables `{city}`, `{price}`, etc.)
5. Désactiver les sections inutiles avec `"enabled": false`
6. Ajouter les cards pricing réelles

## Format des clés i18n

- `"@navbar.demo.logo"` → résolu depuis `i18n/fr.json` → `navbar.demo.logo`
- `"Texte direct"` → retourné tel quel (pas de résolution)
- `"{city}"` → remplacé par `placeholder_context["city"]`

## Ajouter une langue

1. Créer `i18n/de.json` (structure identique à `fr.json`)
2. Définir `"lang": "de"` dans le manifest
