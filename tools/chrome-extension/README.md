# PRESENCE_IA — Chrome Extension

Capture un screenshot de l'onglet courant (ex: une réponse ChatGPT/Gemini/Claude)
et l'uploade automatiquement vers l'API `/api/evidence/upload`.

## Installation (mode développeur)

1. Ouvrir Chrome → `chrome://extensions/`
2. Activer **Mode développeur** (en haut à droite)
3. Cliquer **Charger l'extension non empaquetée**
4. Sélectionner ce dossier `tools/chrome-extension/`
5. L'icône PRESENCE_IA apparaît dans la barre Chrome

## Configuration

Éditer `config.json` avant d'installer :

```json
{
  "server_url": "https://presence-ia.com",   // URL du serveur API
  "default_profession": "couvreur",           // Profession par défaut dans le popup
  "default_city": "Rennes",                   // Ville par défaut
  "admin_token": "votre-admin-token"         // Valeur de ADMIN_TOKEN dans .env
}
```

> ⚠️ Ne pas committer `config.json` avec un vrai token en production.

## Utilisation

1. Ouvrir ChatGPT/Gemini/Claude avec la requête du prospect
2. Cliquer sur l'icône PRESENCE_IA dans Chrome
3. Sélectionner le **fournisseur IA** (openai / anthropic / gemini)
4. Vérifier **profession** et **ville**
5. Cliquer **Capture & Upload**
6. L'URL est affichée → bouton "Copier l'URL" disponible

## Ce que ça fait

- Capture le screenshot de l'onglet visible (`chrome.tabs.captureVisibleTab`)
- Rename automatique : `YYYY-MM-DD_HHMM_provider_rand.png`
- Stocké sur le serveur : `dist/evidence/{profession}/{city}/`
- Accessible depuis la landing page du prospect (section "Preuves des tests")

## Ajouter des icônes

Placer dans ce dossier :
- `icon16.png` (16×16)
- `icon48.png` (48×48)
- `icon128.png` (128×128)

Sans icônes, Chrome utilisera son icône par défaut — l'extension fonctionne quand même.
