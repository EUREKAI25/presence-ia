# PRESENCE_IA — Suivi

**Statut** : ✅ Harmonisation CSS thème clair + 98/98 tests
**Créé** : 2026-02-12
**Dernière MAJ** : 2026-02-20
**Pipeline** : BRIEF ✅ → CDC ✅ → DEV ✅ → TESTS ✅ → GITHUB ✅

**GitHub** : https://github.com/EUREKAI25/presence-ia
**Local** : `/Users/nathalie/Dropbox/____BIG_BOFF___/PROJETS/PRO/PRESENCE_IA/`
**Port** : 8001 (API FastAPI)
**Swagger** : http://localhost:8001/docs
**Admin** : http://localhost:8001/admin?token=ADMIN_TOKEN

---

## Architecture

```
SCAN → TEST (multi-IA) → SCORE (EMAIL_OK) → GENERATE → QUEUE → ASSETS → READY_TO_SEND
```

- **Modèles IA** : gpt-4o-mini / claude-haiku-4-5 / gemini-1.5-flash
- **EMAIL_OK** : invisible ≥ 2/3 modèles + ≥ 4/5 requêtes + ≥ 1 concurrent
- **Score /10** : +4 invisible +2 concurrents +1 ads +1 reviews +1 website
- **Aucun envoi auto** — fichiers CSV/JSON dans `send_queue/`
- **Landing** : GET `/couvreur?t=TOKEN` — HTML dark personnalisé
- **Scheduler** : Europe/Rome, runs mer/ven/dim 09h-13h-20h30, lun préparation

---

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `src/models.py` | ORM + Pydantic + statuts + transitions |
| `src/database.py` | SQLite + CRUD helpers |
| `src/scan.py` | Import prospects (CSV/JSON/manual) |
| `src/ia_test.py` | Multi-IA + fuzzy matching |
| `src/scoring.py` | EMAIL_OK + score /10 |
| `src/generate.py` | Audit HTML + email + script + CSV queue |
| `src/assets.py` | Gate vidéo/screenshot |
| `src/scheduler.py` | APScheduler (10 jobs) |
| `src/api/routes/pipeline.py` | **Runner unique** SCAN→QUEUE |
| `src/api/routes/admin.py` | Admin UI HTML + Send Queue |
| `src/api/routes/upload.py` | Upload proof/city/vidéo + enrich-email + send-email |
| `src/enrich.py` | Extraction email depuis homepage (regex) |

---

## Historique

- 2026-02-12 : Création automatique via Pipeline Agence
- 2026-02-17 : Implémentation complète MVP (session Claude Code)
  - 27 fichiers créés — 1788 lignes
  - Modules : scan, ia_test, scoring, generate, assets, scheduler
  - Routes API : campaign, ia_test, scoring, generate, pipeline, admin
  - Tests pytest : test_scoring (9), test_ia_extract (12)
  - GitHub + VPS déployé
- 2026-02-18 : Session 2 — Google Places + Send Queue (session Claude Code)
  - `POST /api/prospect-scan/auto` : Google Places API → 10 couvreurs Rennes testés
  - Gemini migré gemini-1.5-flash → gemini-2.0-flash (404 dépréciation)
  - Fix generate_campaign : filtre SCORED inclus (pas seulement READY_ASSETS)
  - **Send Queue** :
    - ProspectDB : +email, +proof_image_url, +city_image_url (migration auto)
    - `src/enrich.py` : extraction email regex depuis homepage
    - `src/api/routes/upload.py` : 5 endpoints upload/enrich/envoi
    - `GET /admin/send-queue` : tableau JS interactif
    - `tests/test_send_queue.py` : 20 tests — 84/84 passing
    - VPS redémarré : `/opt/presence-ia/dist/uploads` monté

- 2026-02-18 : Session 3 — Dashboard admin 5 onglets (session Claude Code)
  - ContactDB + PricingConfigDB (seed par défaut 3 offres)
  - /admin/contacts : CRUD + mark-sent/read/paid
  - /admin/offers : édition live prix/bullets/Stripe ID
  - /admin/analytics : KPIs + revenus + villes
  - /admin/evidence : preview original + WEBP + delete
  - Pillow : resize 1600px + center crop 16:9 + WEBP sur upload
  - /api/pricing : endpoint public pour landing dynamique
  - 84/84 tests OK — pushé GitHub — déployé VPS ✅ (212.227.80.241)

- 2026-02-19 : Session 4 — Migration offers_module (session Claude Code)
  - Nouveau package Python standalone `OFFERS_MODULE` v0.1.0 (16/16 tests)
  - `PricingConfigDB` supprimé de `models.py`
  - `_PRICING_DEFAULTS` + `db_list_pricing/get/update` supprimés de `database.py`
  - `src/api/routes/offers.py` supprimé (remplacé par `offers_module.router`)
  - `main.py` : `init_module()` au startup + `offers_router` monté
  - `generate.py` + `stripe_routes.py` : adaptés pour `OfferDB` (name/price/features)
  - `analytics.py` : import mort supprimé
  - 84/84 tests verts après migration

- 2026-02-20 : Session 5 — Harmonisation CSS thème clair (session Claude Code)
  - **Conversion dark → light theme** pour toutes les pages (homepage, landing, admin)
  - `src/api/main.py` : CSS homepage (body, nav, sections, boutons, footer)
  - `src/api/routes/content.py` : CSS admin contenus (formulaires, FAQ, modal sections)
  - `src/api/routes/admin.py` : CSS admin pages (dashboard, prospects, send queue, scheduler)
  - **Couleurs unifiées** : backgrounds #fff/#f9fafb, borders #e5e7eb, text #1a1a2e/#6b7280
  - **Ajout shadows** : `box-shadow: 0 1px 3px rgba(0,0,0,0.1)` pour profondeur
  - 98/98 tests verts — commit + push GitHub ✅

---

## Prochaines étapes

- [ ] Déployer sur VPS (git pull + restart)
- [ ] Configurer clés Stripe + Brevo dans secrets.env
- [ ] Créer les offres depuis `/api/admin/offers` (remplace l'ancien admin offers HTML)
- [ ] Tester workflow complet : SUSPECT → envoi → CLIENT
- [ ] Migration AI_SEO_AUDIT → offers_module (phase suivante)
