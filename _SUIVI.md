# PRESENCE_IA — Suivi

**Statut** : 🟢 actif — MARKETING_MODULE EURKAI complet (email + SMS + social + CRM)
**Créé** : 2026-02-12
**Dernière MAJ** : 2026-03-06 (session 2)

## 🔌 SESSION 2026-03-06 (session 2) — MARKETING_MODULE EURKAI COMPLET

### Réalisé en session 2

| Fichier | Description | Statut |
|---|---|---|
| `api/routes/domains.py` | CRUD domaines + validate via Brevo API | ✅ |
| `api/routes/mailboxes.py` | CRUD mailboxes + stats + reset-daily + test-smtp | ✅ |
| `api/routes/warmup.py` | CRUD warmup strategies + step advance | ✅ |
| `api/routes/rotation.py` | CRUD rotation strategies | ✅ |
| `api/routes/campaigns.py` | CRUD campaigns + activate/pause/stop + stats | ✅ |
| `api/routes/sequences.py` | CRUD sequences + steps | ✅ |
| `api/routes/send.py` | `POST /send/batch` — envoi multi-canal (email/SMS) | ✅ |
| `api/routes/reporting.py` | Stats campaign + mailbox + projet | ✅ |
| `api/routes/compliance.py` | CRUD rules + `POST /compliance/check` | ✅ |
| `api/routes/__init__.py` | Exports tous les routers | ✅ |
| `api/__init__.py` | Export app | ✅ |
| `api/main.py` | FastAPI app, 12 routers montés, `/health` | ✅ |
| `channels/__init__.py` + sous-packages | Structure packages channels | ✅ |
| `crm/__init__.py` | Export fonctions CRM | ✅ |
| `configs/presence_ia_seed.json` | Seed complet : 5 domaines, 25 mailboxes, warmup 21j, séquence 3 emails, SMS | ✅ |
| `configs/sublym_seed.json` | Seed Sublym : social (Instagram+Pinterest) + email | ✅ |
| `configs/seed_loader.py` | CLI seed loader (`python -m marketing_module.configs.seed_loader`) | ✅ |
| `TESTS/test_models.py` | Tests ORM + CRUD | ✅ |
| `TESTS/test_rotation.py` | Tests algorithmes rotation (round_robin, weighted, health_priority) | ✅ |
| `TESTS/test_crm.py` | Tests Calendly webhook, commission auto, annulation | ✅ |
| `TESTS/test_send.py` | Tests batch send (mock provider, dedup, dry_run, provider failure) | ✅ |
| `__init__.py` | Package root + exports publics | ✅ |
| `pyproject.toml` | Package installable pip | ✅ |
| Fix `module.py` handle_bounce | Suppression double import `db_get_delivery` | ✅ |

### MARKETING_MODULE — Structure finale complète
```
EURKAI/MODULES/MARKETING_MODULE/
├── __init__.py, models.py, database.py, module.py
├── api/
│   ├── main.py (FastAPI, 12 routers)
│   └── routes/ (12 fichiers : domains, mailboxes, warmup, rotation,
│                campaigns, sequences, send, reporting, compliance,
│                social, crm, webhooks)
├── channels/
│   ├── base.py (AbstractChannel)
│   ├── email/providers/ (base.py + brevo.py)
│   ├── sms/providers/ (twilio.py)
│   └── social/providers/ (instagram.py + pinterest.py)
├── crm/module.py (Calendly, closer assignment, commissions)
├── configs/
│   ├── presence_ia_seed.json (5 domaines, 25 mailboxes, séquence 3 emails + SMS)
│   ├── sublym_seed.json (social Instagram+Pinterest)
│   └── seed_loader.py (CLI)
├── TESTS/ (test_models, test_rotation, test_crm, test_send)
└── pyproject.toml
```

### Prochaines étapes
- [ ] Déployer MARKETING_MODULE sur VPS + lancer `seed_loader presence_ia_seed.json`
- [ ] Scorer les 17 prospects Brest (campaign_id: f61a9fed)
- [ ] Configurer Calendly webhook → `POST /mkt/webhooks/calendly?project_id=presence-ia`
- [ ] Changer CLOSER_TOKEN dans secrets.env VPS
- [ ] Scheduler APScheduler — tests IA 3x/semaine
- [ ] Ajouter credentials Brevo dans env VPS (`BREVO_API_KEY`, `BREVO_SMTP_LOGIN`, `BREVO_SMTP_PASSWORD`)

---

## 🔌 SESSION 2026-03-06 — EMAIL + LANDING + CLOSERS + OUTBOUND_EMAIL_MODULE

### Réalisé en session

| Chantier | Fichier(s) | Statut |
|---|---|---|
| Landing — accordéon IA réel (3 vraies requêtes par modèle) | `src/api/routes/generate.py` | ✅ |
| Landing — H1, insight block, ia-explain, scarcity, pre-FAQ | `generate.py` | ✅ |
| Landing — FAQ simplifiée (4 Q&A, sans jargon, sans doublons) | `generate.py` + DB | ✅ |
| Landing + home + v3 — Calendly 30min → 20min | `generate.py`, `page_builder_route.py`, `v3.py` | ✅ |
| Home — stats remplacées par phrases bénéfices | `page_builder_route.py` | ✅ |
| Fiche closers — réécriture complète 3 offres | `RESOURCES/FICHE_PRODUIT_PRESENCE_IA.html` | ✅ |
| Page recrutement closers — publique `/recrutement` | `RESOURCES/recrutement_closers.html` + `closing_pack.py` | ✅ |
| Infrastructure email — 5 domaines Brevo (presence-ia.*) | IONOS DNS + Brevo API | ✅ authentifiés |
| 25 adresses email (contact/audit/analyse/rapport/team × 5) | Brevo senders | ✅ |
| DNS SPF/DKIM/DMARC — 5 domaines | IONOS API | ✅ propagés |
| OUTBOUND_EMAIL_MODULE — module EURKAI complet | `EURKAI/MODULES/OUTBOUND_EMAIL_MODULE/` | ✅ |

### OUTBOUND_EMAIL_MODULE — Structure complète
```
EURKAI/MODULES/OUTBOUND_EMAIL_MODULE/
├── models.py, database.py, module.py   ← ORM + CRUD + engine
├── providers/base.py, brevo.py         ← interface abstraite + Brevo SMTP/API
├── api/main.py + 9 routes              ← FastAPI montable (/oem/...)
├── configs/presence_ia_seed.json       ← 25 mailboxes / 5 domaines / règles
├── configs/seed_loader.py              ← import DB via JSON
└── TESTS/ (4 fichiers)                 ← models, rotation, compliance, send
```

### Prochaines étapes
- [ ] Déployer OUTBOUND_EMAIL_MODULE sur VPS + lancer seed_loader avec BREVO_API_KEY
- [ ] Scorer les 17 prospects Brest (`POST /api/scoring/run`, campaign_id: f61a9fed)
- [ ] Créer première séquence email (sujet + body template)
- [ ] Changer CLOSER_TOKEN dans secrets.env VPS
- [ ] Scheduler APScheduler — tests IA 3x/semaine

---

## SESSION 2026-03-04 — PACK GLOBAL 9 CHANTIERS

### Chantiers (source: `CLAUDE/TODO/presence_ia_prompts_global/`)

| # | Chantier | Lieu | Statut |
|---|---|---|---|
| 00 | Conventions | — | ✅ lues |
| 01 | AI_INQUIRY_MODULE | `EURKAI/MODULES/AI_INQUIRY_MODULE/` + endpoint `/api/ai-inquiry/run` | ✅ 25/25 tests |
| 02 | competitor_analysis scenario | `src/prospecting/competitor_analysis.py` | ✅ déployé |
| 03 | evidence_manager | `src/evidence/manager.py` | ✅ déployé |
| 04 | admin CMS blocks | sqlite + routes + UI `/admin/cms` | ✅ déployé |
| 05 | landing render | `/{profession}?t=token` + offres | ✅ 12/12 tests, déployé |
| 06 | contacts tracking | mini CRM + endpoints | ✅ 22/22 tests, déployé |
| 07 | outreach sans email | POST `/api/generate/prospect/{id}/outreach-messages` | ✅ déployé |
| 08 | demo script | `src/api/routes/demo.py` | ✅ 15/15 tests, déployé |
| 10C | content rewriter | `src/livrables/content_rewriter.py` | ✅ 19/19 tests, déployé |
| 10D | editorial checklist | `src/livrables/checklist.py` | ✅ 6/6 tests (déjà présent) |
| 10E | strategic dossier | `src/livrables/dossier.py` | ✅ 5/5 tests (déjà présent) |
| 10F | monthly retest | `src/livrables/monthly_retest.py` | ✅ 20/20 tests, déployé |
| 10G | client dashboard | `src/api/routes/client_dashboard.py` | ✅ 17/17 tests, déployé |

### Chantier 01 — AI_INQUIRY_MODULE (terminé 2026-02-20 16:00)
- **Module** : `EURKAI/MODULES/AI_INQUIRY_MODULE/` (module.py + __init__.py + README.md)
- **Tests** : `TESTS/test_module.py` — 25 tests, 25 passent (dry_run, contrat uniforme, normalisation, extraction entités, présence, concurrents)
- **Adapter** : `src/api/routes/ai_inquiry.py` — `POST /api/ai-inquiry/run`
- **main.py** : route enregistrée
- **Fonctions réutilisées** : `norm()`, `is_mentioned()`, `extract_entities()`, `competitors_from()` (portées depuis ia_test.py, autonomes)

### Contrat de sortie OBLIGATOIRE (tous modules)
```json
{ "success": bool, "result": <any>, "message": str, "error": null|{"code":str,"detail":str} }
```

### Règles
- Modules dans `EURKAI/MODULES/<NOM>/` — README + tests
- PRESENCE_IA consomme via endpoints/adapters
- API-first : chaque module = 1 endpoint POST minimum
- `dry_run=true` option

---
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

- 2026-02-20 : Session 6 — Fix landing page (session Claude Code)
  - **Bug 1 fixé** : Landing lisait hero/title au lieu de hero/title_tpl → champs vides
  - **Bug 2 fixé** : Landing ne rendait que hero+pricing même si admin configurait d'autres sections
  - **Bug 3 fixé** : `db_get_header()` appelé après `_db.close()` (hors du try) → session fermée
  - **Bug 4 fixé** : Overlay ajouté sur l'image header (gradient sombre top→transparent)
  - **DB** : sections_config landing restaurée (6 sections : hero, proof_stat, proof_visual, evidence, pricing, faq)
  - **Default fallback** : si header_city pas configuré, prend le 1er header dispo en DB

- 2026-02-20 : Session 5 — Harmonisation CSS thème clair (session Claude Code)
  - **Conversion dark → light theme** pour toutes les pages (homepage, landing, admin)
  - `src/api/main.py` : CSS homepage (body, nav, sections, boutons, footer)
  - `src/api/routes/content.py` : CSS admin contenus (formulaires, FAQ, modal sections)
  - `src/api/routes/admin.py` : CSS admin pages (dashboard, prospects, send queue, scheduler)
  - **Couleurs unifiées** : backgrounds #fff/#f9fafb, borders #e5e7eb, text #1a1a2e/#6b7280
  - **Ajout shadows** : `box-shadow: 0 1px 3px rgba(0,0,0,0.1)` pour profondeur
  - 98/98 tests verts — commit + push GitHub ✅

---

---

## Session 2026-03-05 — Page closers + récap coach + exemples

### Déployé (commit bf1af1a)
- **FICHE_PRODUIT_PRESENCE_IA.html** : 15+ corrections textuelles (Plus qu'un outil, par les IA, {METIER}/{VILLE}, 27 tests, bimensuel, 6 FAQ, tableau périmètre Kit/TI, accordéons toggle)
- **Route `/closing_pack/exemple/{slug}?t=TOKEN`** : sert les 6 exemples de livrables
- **Route `/recap`** : page publique partage coach (sans auth)
- **Exemples créés** (client fictif Leroux Couverture, Rennes) :
  - `audit_fictif.html` — landing prospect simulée
  - `dossier_sommaire.html` — sommaire 30 pages
  - `faq_exemple.html` — page FAQ complète optimisée IA
  - `checklist_exemple.html` — 10 actions interactives + upsells Tout Inclus
  - `rapport_bimensuel.html` — rapport progression J-15 vs J0
  - `landing_demo.html` — vue mobile prospect
  - `recap_coach.html` — récap stratégique pour coaching

### URLs en production
- **Fiche closers** : `http://212.227.80.241:8001/closing_pack?t=closer-secret`
- **Récap coach** : `http://212.227.80.241:8001/recap` (public)
- **Exemples** : `http://212.227.80.241:8001/closing_pack/exemple/audit_fictif?t=closer-secret`

### Questions / décisions en suspens
- Fréquence re-tests : **hebdomadaire** (technique) + **rapport bimensuel** → ✅ aligné
- Requêtes : **6 par prospect** (3 primaires + 3 variantes) → à implémenter dans ia_test.py
- Accord sur terminologie : "code d'identité site" au lieu de "JSON-LD" → ✅

### À faire (priorités)

#### Urgent
- [ ] **Tester pipeline complet** avec un vrai prospect (paire ville/métier réelle)
- [ ] **Vérifier admin/prospection** : BDD connectée ? SMS fonctionnel ? Config paires ville/métier
- [ ] **CLOSER_TOKEN** : configurer une vraie valeur dans secrets.env VPS (remplacer "closer-secret")

#### Court terme
- [ ] **Guides installation Kit** : guides pas-à-pas WP/Wix/HTML avec captures + upsells (chantier dédié)
- [ ] **Rapport d'exécution Tout Inclus** : document "ce qu'on a fait" remis en fin de programme
- [ ] **Prévisionnel admin** : tableau coûts/revenus/conversion dans l'interface admin
- [ ] **6 requêtes par prospect** : passer de 3 à 6 requêtes dans ia_test.py (3 primaires + 3 variantes)
- [ ] **Closers** : recruter 2 premiers (LinkedIn, Closer Academy, groupes FB)

#### Moyen terme
- [ ] Configurer clés Stripe + Brevo dans secrets.env
- [ ] Créer les offres depuis `/api/admin/offers`
- [ ] Tester workflow complet SUSPECT → envoi → CLIENT → paiement
