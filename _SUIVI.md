# PRESENCE_IA — Suivi

**Statut** : 🟢 actif — Pipeline complet opérationnel
**Créé** : 2026-02-12
**Dernière MAJ** : 2026-04-07

---

## 🔌 SESSION 2026-04-07 — Maillage interne discret (ajout)

### Réalisé

#### 7. Module de maillage interne

**Objectif** : relier intelligemment les pages générées sans exposer dans la navigation.

| Fichier | Rôle |
|---|---|
| `src/publisher/page_index.py` | `PublishedPageDB` (table `published_pages`) + `register_published_page()` + `list_generated_pages_for_prospect()` + `find_related_pages()` + `update_internal_links()` |
| `src/publisher/link_builder.py` | `build_internal_link_suggestions(page, related, max=3)` — ancres naturelles, 5 types de page, règle "jamais vers soi-même" |
| `src/content_engine/link_injector.py` | `build_link_block(links)` + `inject_internal_links(html, links)` — bloc "À lire aussi" sobrement injecté avant `</body>` |
| `src/publisher/mesh_service.py` | `refresh_internal_links_for_prospect(id, db)` + `refresh_internal_links_for_all(db)` — calcul + sauvegarde DB + patch HTML |

**Modifications :**
- `publisher/service.py` : appel `register_published_page()` après chaque publication (WP ou manuelle)
- `publisher/__init__.py` : exports `refresh_internal_links_for_prospect`, `refresh_internal_links_for_all`
- `content_engine/page_generator.py` : param `internal_links` optionnel → bloc injecté dans la page
- `api/routes/livrables.py` : `POST /api/ia-reports/{token}/mesh`
- `api/routes/crm_admin.py` : bouton `🔗 Maillage interne` + JS `iaMesh()` avec affichage liens + patch HTML dépliable

**Logique de priorité (find_related_pages) :**
- +10 : même profession · +5 : même ville · filtre : URL non vide, visibility discreet/integrated
- jamais de lien vers le même prospect (exclut par token) ni vers la même URL

**Résultats fixture :**
```
Plombier Lyon → 3 liens :
  → Plombier à Villeurbanne (même métier, autre ville)
  → Chauffagiste à Lyon (même ville, autre métier)
  → FAQ Plombier Lyon (même métier et même ville)
Page avec links : 6 152 chars · bloc "À lire aussi" ✓
```

**TODO V2 :** WordPress auto-update via GET /wp-json/wp/v2/pages/{id} + injection + PUT (commenté dans mesh_service.py)

---

## 🔌 SESSION 2026-04-07 — Pipeline complet branché + publisher

### Réalisé

#### 1. Endpoints API ia_reports (branchement)

| Endpoint | Action |
|---|---|
| `POST /api/ia-reports/{token}/audit` | Audit initial → fichier + snapshot DB |
| `POST /api/ia-reports/{token}/monthly` | Rapport mensuel + delta auto depuis snapshot |
| `POST /api/ia-reports/{token}/bundle` | Audit + monthly + contenus en un appel |
| `POST /api/ia-reports/{token}/content` | FAQ + page service + JSON-LD |
| `POST /api/ia-reports/{token}/publish` | Publication page sur le site du client |

#### 2. Boutons fiche CRM (`/admin/crm/prospect/{token}`)

Section "Rapports IA" avec 6 actions inline (résultat sans rechargement) :
- 📊 Générer audit · 📅 Rapport mensuel · 📦 Bundle complet
- ✍ Générer contenus · 🚀 Publier sur le site · 👁 Voir audit HTML
- Champs WP credentials (identifiant + Application Password) révélés au clic sur Publier
- Instructions publication manuelle dépliables dans le résultat

#### 3. Module `src/content_engine/`

| Fichier | Rôle |
|---|---|
| `faq_generator.py` | Requêtes IA → questions naturelles + réponses courtes. 5 questions essentielles systématiques. |
| `page_generator.py` | Page `{profession} à {ville}` HTML complète (intro, services, confiance, FAQ). CSS inline, copier-coller CMS. |
| `schema_generator.py` | JSON-LD `LocalBusiness` (mapping @type par secteur) + `FAQPage`. Snippet prêt + instructions WP/Wix/Shopify. |
| `service.py` | `generate_content_bundle(token, db)` → charge depuis snapshot ou ia_results, sauvegarde dans `deliverables/generated/content/{slug}/` |

**Résultats fixture validés :**
```
8 questions FAQ · Plumber @type auto · page 8 423 chars · snippet JSON-LD 2 540 chars
```

#### 4. Module `src/publisher/`

| Fichier | Rôle |
|---|---|
| `wordpress.py` | `publish_page()` — POST `/wp-json/wp/v2/pages` + Application Password. `update_page()` pour re-pub. |
| `fallback_manual.py` | Instructions pas-à-pas par CMS (WP / Wix / Shopify / Squarespace / Webflow / inconnu). |
| `service.py` | `publish_content()` — détecte CMS, publie auto WP ou fallback manuel. `publish_for_prospect()` charge depuis disque ou génère à la volée. |

**Logique :**
- WordPress + credentials → API REST, URL publique retournée
- WordPress sans credentials → instructions manuelles WP
- Wix / Shopify / Squarespace / Webflow → instructions spécifiques
- CMS inconnu → instructions génériques (FTP ou copier-coller)

#### 5. Fix arrondi delta

`round(..., 1)` sur `delta_val` dans `generator.py` et `service.py` — élimine les `+3.5999...` en affichage.

#### 6. Contrôle de visibilité des pages publiées

Problème : risque d'exposition non voulue dans la navigation du site client.

**Solution implémentée :**
- `visibility = "discreet"` (défaut) — page publiée, accessible par URL directe, absente des menus
- `visibility = "integrated"` — TODO V2 (nécessite plugin WP REST API Menus)
- Renommage `public_nav` → `integrated` dans tous les fichiers publisher
- `publish_date` ajouté dans tous les retours (ISO format)
- `menu_note` explicite dans chaque retour (ex: "Page publiée sans intégration au menu")
- Instructions manuelles : "⚠️ NE PAS ajouter au menu" dans chaque CMS (WP, Wix, Shopify, Squarespace, Webflow)
- TODO V2 dans `wordpress.py` : `POST /wp-json/wp/v2/menus/{menu_id}/items` (plugin requis)

**Badges CRM :**
- 🟢 `Page publiée (discrète)` — fond vert sombre
- 🔵 `Page publiée (intégrée)` — fond bleu sombre
- Affichage de `menu_note` (ℹ) et `publish_date` dans le résultat inline

### État actuel du pipeline

```
Prospect V3 (ia_results)
  → ia_reports : audit HTML + snapshot DB
  → ia_reports : rapport mensuel + delta
  → content_engine : FAQ + page service + JSON-LD
  → publisher : publication WP auto OU package manuel CMS
  → fiche CRM : boutons inline pour déclencher chaque étape
```

### Prochaines actions

| Priorité | Action |
|---|---|
| 🔴 | Déployer sur VPS (git push + restart) |
| 🔴 | Tester sur un prospect réel avec ia_results |
| 🟠 | Activer outbound LIVE (`OUTBOUND_DRY_RUN=false`) |
| 🟡 | Configurer webhook Brevo |
| 🟡 | Ajouter Stripe Price IDs (en attente SIRET) |

---

## 🔌 SESSION 2026-04-06 — Job outbound + DRY_RUN diagnostic

### Réalisé

| Fichier / Composant | Action | Statut |
|---|---|---|
| `src/scheduler.py` | `_job_outbound()` créé — sélection/scoring/envoi v3_prospects | ✅ |
| `src/scheduler.py` | Job 11 enregistré dans scheduler (cron 9h UTC) | ✅ |
| `src/scheduler.py` | Mode `OUTBOUND_DRY_RUN=true` ajouté — logs détaillés, 0 envoi, 0 écriture DB | ✅ |
| VPS `.env` | `OUTBOUND_DRY_RUN=true` + `OUTBOUND_CAP=20` configurés | ✅ |
| VPS | Déployé + service redémarré — 13 jobs actifs | ✅ |
| GitHub | Pushé sur main | ✅ |

### Résultats DRY_RUN (exécuté 2026-04-06 21h26)

```
Batch analysé           : 200 prospects (ia_results + non envoyés)
  → avec email          : 109
  → sans email          :  91

Scoring comparatif :
  avec scoring   → would_send =  29  /  would_skip = 80  (73% skippés car déjà cités IA)
  sans scoring   → would_send = 109

Run cap=20 :
  sélectionnés   = 58
  skippés (cités)= 38
  would_send     = 20  ✅  (0 envoi réel, 0 écriture DB)
```

### Problèmes identifiés

| Problème | Exemple | Impact |
|---|---|---|
| Faux emails (noms de fichiers scrapés) | `cropped-favicon@2x-32x32.jpg`, `icon_close@2x.png` | Envoi rejeté par Brevo ou bounce |
| Placeholder email | `name@company.com` | Idem |
| Adresse technique Sentry | `...@sentry-next.wixpress.com` | Pas un vrai destinataire |

### Logique job_outbound (état final)

- Sélection : `ia_results IS NOT NULL` + `sent_at IS NULL` + `email IS NOT NULL`
- Scoring : matching mots-clés nom entreprise vs réponses IA → cité = skip
- Envoi via Brevo API, rotation 25 senders warmés
- Update `sent_at` + `sent_method = 'brevo'` après envoi réussi
- Cap : `OUTBOUND_CAP` env (actuel : 20) — remettre à 10 pour prod
- Prochain run LIVE : dès que `OUTBOUND_DRY_RUN` repassé à `false`

### État VPS au 2026-04-06

| Élément | Valeur |
|---|---|
| v3_prospects total | 2 833 |
| v3_prospects testés IA | 1 752 |
| v3_prospects avec email | 1 147 (dont ~X% faux emails à filtrer) |
| Envoyés à ce jour | 1 |
| city_headers | 14 villes |
| Enrichissement Gemini | actif (100/run, toutes heures) |
| Warming | actif — J18 — cap 8/sender — plateau J22 (11 avril) |

### Filtre email — ajouté (2026-04-06 21h32)

`_outbound_is_valid_email()` — règles :
- Regex email standard
- Exclusion extensions image/fichier (`.jpg`, `.png`, `.webp`, `.svg`...)
- Exclusion mots-clés techniques (`sentry`, `wixpress`, `noreply`, `cropped-`, `favicon`...)

**Résultats DRY_RUN avec filtre :**
```
Batch 200 :  sans_email=91  email_invalide=9  email_valide=100
Scoring  :   would_send=27 / would_skip=73 (sur 100 valides)
Run cap20:   sélectionnés=66  skipped=46  would_send=20  ✅
```
Les 9 emails invalides détectés et exclus : noms de fichiers image, adresses Sentry/Wixpress.

### Tracking email outbound — ajouté (2026-04-06 21h39)

| Fichier | Action |
|---|---|
| `src/models.py` | `V3ProspectDB` : +`email_status` / `email_sent_at` / `email_opened_at` / `email_bounced_at` |
| `src/database.py` | Migration `init_db()` : 4 colonnes via ALTER TABLE (idempotent) |
| `src/scheduler.py` | `job_outbound` : `email_status='sent'` + `email_sent_at=now()` à l'envoi |
| `src/api/routes/brevo_webhook.py` | `POST /webhooks/brevo` — traite delivered/open/click/bounce/spam |
| `src/api/main.py` | Route webhook enregistrée |

**Statuts tracking :** `pending → sent → delivered → opened → bounced`

**Config Brevo à faire** (côté dashboard Brevo) :
- Paramètres → Webhooks → Ajouter URL : `https://presence-ia.com/webhooks/brevo`
- Événements à cocher : Delivered, Opened, Clicked, Bounced, Spam, Unsubscribed

### Page outbound-stats — ajoutée (2026-04-06 21h46)

- `GET /admin/outbound-stats` : KPIs sent / delivered / opened / bounced + taux
- Breakdown 7 derniers jours
- Distribution statuts
- Lien "Outbound" dans sidebar nav section MARKETING

### Message final v1 + simulation cap=5 (2026-04-07)

| Fichier | Action |
|---|---|
| `src/scheduler.py` | `_OUTBOUND_SUBJECTS` → `"Votre nom n'est pas sorti"` |
| `src/scheduler.py` | `_OUTBOUND_BODY` → 4 lignes, ton direct, `{profession}/{ville}` |
| `src/scheduler.py` | DRY_RUN : affiche To / From / Subject / Body rendu complet |
| `src/scheduler.py` | Fix requête SQL : `email NOT NULL` filtré en amont |

**Résultats simulation :**
```
total avec email : 100   invalides : 9   valides : 91
scoring          : would_send=24  would_skip=67
run cap=5        : sélectionnés=7  skipped=2  would_send=5 ✅
0 envoi réel — 0 écriture DB
```

### Moteur ia_reports — modules propres (2026-04-07)

Architecture séparée en 5 modules dans `src/ia_reports/` :

| Module | Rôle |
|---|---|
| `parser.py` | Parse ia_results — tolère formats A (V3) et B (legacy), JSON string ou list |
| `scoring.py` | Score /10, extraction concurrents, checklist dynamique (3 niveaux) |
| `generator.py` | HTML audit + monthly, sélection guide CMS, sauvegarde fichier |
| `storage.py` | Snapshots DB — save/load/count, migration idempotente |
| `service.py` | API haut niveau : `create_initial_audit_for_prospect()`, `create_monthly_report_for_prospect()`, `create_full_deliverable_bundle()` |

**Outputs générés dans :** `deliverables/generated/audits/` et `deliverables/generated/reports/`

**Script de test :**
```bash
python tests/test_ia_reports_manual.py --fixture    # test sans DB (données synthétiques)
python tests/test_ia_reports_manual.py              # test avec 1er prospect DB
python tests/test_ia_reports_manual.py --token <t>  # test par token
python tests/test_ia_reports_manual.py --list       # liste prospects disponibles
```

**Résultats fixture (2026-04-07) :**
```
3 requêtes / 9 tests — Score 5.6/10 — 5/9 citations
Audit    : deliverables/generated/audits/fixture_audit.html (6 954 chars) ✅
Rapport  : deliverables/generated/reports/fixture_report_m1.html (9 139 chars) ✅
```

### Pipeline complet prospect → audit → rapport mensuel (2026-04-07)

| Composant | Fichier | Rôle |
|---|---|---|
| `IaSnapshotDB` | `src/models.py` | Table persistance (score, matrix, competitors, HTML) |
| Migration | `src/database.py` | `ia_snapshots` créée via `Base.metadata.create_all` |
| `_build_dynamic_checklist(score)` | `report_generator.py` | Fondations / Contenu / Optimisation selon score |
| `_save_snapshot(db, ...)` | `report_generator.py` | Sauvegarde après chaque rapport |
| `_load_last_snapshot(db, token)` | `report_generator.py` | Charge le snapshot précédent pour le delta |
| `generate_audit_report(prospect, db)` | `report_generator.py` | Checklist dynamique + snapshot auto |
| `generate_monthly_report(prospect, db)` | `report_generator.py` | Charge snapshot précédent auto depuis DB |
| `run_monthly(db)` | `report_generator.py` | Boucle sur tous les clients avec audit |
| Routes pipeline | `livrables.py` | GET/POST audit, monthly, snapshot, history + POST run-monthly |

**Résultats tests** (DB SQLite mémoire) :
```
[1] Audit: score=5 / snapshot sauvegardé OK
[2] _load_last_snapshot: score=5 OK
[3] Monthly: 2 snapshots, delta calculé OK
[4] run_monthly: 'Dupont Plomberie' score=5 OK — 3 snapshots en DB
```

### Génération automatique rapports (2026-04-07)

| Fichier | Contenu |
|---|---|
| `src/livrables/report_generator.py` | `generate_audit_report()` + `generate_monthly_report()` + `build_snapshot()` |
| `src/api/routes/livrables.py` | Routes `/api/reports/v3/{token}/audit` (GET) + `/monthly` (GET/POST) + `/snapshot` (GET) |

**Logique principale :**
- `_is_cited(name, response)` : majorité stricte des mots significatifs — évite faux positifs sur mots génériques
- `_build_query_matrix()` : groupe les 9 résultats IA par prompt → 3 colonnes ChatGPT/Gemini/Claude
- `_score()` : `(citations / total_tests) × 10`
- `_extract_competitors()` : regex markdown links + listes → Counter → dédoublonnage
- `build_snapshot()` : exporte le JSON à passer en `previous_data` au rapport suivant
- Tous les placeholders `{{VAR}}` remplacés — testé sur 9 ia_results simulés ✓

### Livrables clients — structure créée (2026-04-07)

| Fichier | Contenu | Offres |
|---|---|---|
| `deliverables/audit/audit_template.html` | Rapport d'audit IA — variables `{{NOM_ENTREPRISE}}`, score, 5 requêtes × 3 modèles, concurrents, checklist 8 points | 97€ / 500€ / 3500€ / 9000€ |
| `deliverables/reports/report_template.html` | Rapport de suivi mensuel — évolution score, re-test, actions réalisées, prochaines étapes | 3500€ / 9000€ |
| `deliverables/guides/` | Symlinks → RESOURCES/GUIDE_WORDPRESS/WIX/SHOPIFY/PREMIUM | 500€ / 3500€ / 9000€ |
| `deliverables/README.md` | Mapping offre → livrables + variables template | — |

### Reste à faire

- [ ] Configurer webhook Brevo : `https://presence-ia.com/webhooks/brevo` (Delivered/Opened/Bounced/Spam)
- [ ] **Lancer LIVE** : `OUTBOUND_DRY_RUN=false` + `OUTBOUND_CAP=10` sur VPS
- [ ] Fix IMAP timeout warming (bot-free + bot-paid)
- [ ] Stripe Price IDs (dès réception SIRET)
- [ ] Augmenter `OUTBOUND_CAP` progressivement après premiers retours

---

## 🔌 SESSION 2026-03-28 (suite) — IA callers + Préfectures + Upload images

### Réalisé

| Fichier / Composant | Action | Statut |
|---|---|---|
| `src/ia_test.py` | ChatGPT : modèle `chatgpt-4o-latest` → `gpt-4o` (Responses API) | ✅ |
| `src/ia_test.py` | Gemini : `google.generativeai` → `google.genai` (nouveau package installé) + modèle `gemini-2.0-flash` | ✅ |
| `src/ia_test.py` | Gemini : fallback modèle `gemini-2.5-flash-preview-04-17` → `gemini-2.0-flash` | ✅ |
| VPS | `google-genai` installé dans `.venv` | ✅ |
| `src/api/routes/admin.py` | Alerte "sans image" filtrée aux **préfectures** uniquement (102 villes) + badges cliquables pour upload direct | ✅ |
| `src/api/routes/admin.py` | Table PAR MÉTIER × VILLE filtrée aux préfectures uniquement | ✅ |
| `src/database.py` | Limit breakdown SQL : 20 → 200 (pour avoir assez de préfectures après filtrage) | ✅ |

### IA callers — état final

| Modèle | Statut | Notes |
|---|---|---|
| ChatGPT (`gpt-4o`) | ✅ | Responses API + web_search_preview + instructions système |
| Claude (`claude-3-5-sonnet`) | ✅ | Multi-turn web_search_20250305 (tour 1 → tool_use → tour 2) |
| Gemini (`gemini-2.0-flash`) | ✅ | `google.genai` + Google Search grounding |

- Prochaine exécution `_job_refresh_ia` : **dimanche 30 mars à 9h30 UTC** (11h30 Paris)

### Admin — préfectures

- Alerte accueil : liste filtrée aux 102 préfectures uniquement (plus les 640 petites villes)
- Clic sur une préfecture → sélecteur de fichier → upload → badge supprimé si succès
- Table PAR MÉTIER × VILLE : idem, filtrée préfectures (Puget-sur-Argens, Boulogne-Billancourt, etc. supprimés)

### Playwright — décision finale

- **Abandonné définitivement** : Cloudflare bloque systématiquement (headless, headed, Chrome natif, profil réel)
- **Architecture retenue** : API uniquement (ChatGPT Responses API + Claude SDK + Gemini genai)
- `~/presence-ia-runner/scrape.py` et `launchd plist` → inutiles, peuvent être supprimés

---

## 🔌 SESSION 2026-03-28 — Enrichissement Gemini + Playwright + Alertes admin

### Réalisé

| Fichier / Composant | Action | Statut |
|---|---|---|
| `src/gemini_places.py` | Nouveau module — enrichissement entreprise via Gemini + Search Grounding (remplace Google Places API expirée) | ✅ |
| `src/api/routes/leads_runner.py` | `_phase2_enrich` migré de Google Places → `fetch_company_info` (Gemini) | ✅ |
| `src/scheduler.py` | `_job_auto_enrich` : conditions heure/jour assouplies (hour_utc=-1 = toutes heures) | ✅ |
| `data/presence_ia.db` | `enrichment_config` : `active=1`, `suspects_per_run=100`, `days=0-6`, `hour_utc=-1` | ✅ |
| `src/api/routes/admin.py` | Alerte accueil : villes sans image filtrées aux leads qualifiés dispos uniquement, liste dépliable avec badge par ville | ✅ |
| `src/api/routes/contacts.py` | Suppression warning "620 villes sans image" (déplacé sur accueil) | ✅ |
| `src/api/routes/scan_admin.py` | Endpoints `/api/ia-pairs` + `/api/ia-results` créés (925 paires actives) | ✅ |

### Enrichissement Gemini — résultats

- Test sur SMAC / Issy-les-Moulineaux → `{'website': 'https://www.smac-sa.com', 'phone': '01 55 95 48 00'}` ✅
- Pipeline : 100 suspects/run × toutes les heures = ~2 400/jour

---

## 🔌 SESSION 2026-03-26 (suite 7) — Objections structurées

### Réalisé

| Fichier | Action | Statut |
|---|---|---|
| `data/closer_content.json` | 10 objections restructurées (logique + exemple + variante) | ✅ |
| VPS | Déployé + service redémarré (active) | ✅ |

### Objections couvertes

| # | Objection | Logique |
|---|---|---|
| 1 | C'est trop cher | Faire parler de la valeur client, pas défendre le prix |
| 2 | Je dois réfléchir | Isoler le vrai frein, ne pas remplir le vide |
| 3 | J'ai déjà une agence | Canal différent — complémentarité, pas concurrence |
| 4 | Pas le temps | Retourner : manque de temps = raison de déléguer |
| 5 | Pas convaincu | Faire tester ChatGPT en direct |
| 6 | Envoyer des infos | Identifier le frein + verrouiller la relance avant de raccrocher |
| 7 | Préfère attendre | Rendre l'attente coûteuse + exclusivité zone |
| 8 | Ne connaît pas l'IA | Recadrer : rien à comprendre techniquement |
| 9 | Si ça ne marche pas | Transformer en garantie concrète 6 mois |
| 10 | Zone encore disponible ? | Factuel, pas de pression artificielle |

---

## 🔌 SESSION 2026-03-26 (suite 6) — Arguments de vente + Trame de vente

### Réalisé

| Fichier | Action | Statut |
|---|---|---|
| `data/closer_content.json` | Ajout `arguments_vente` (3 offres × arguments/limites/upgrade) | ✅ |
| `data/closer_content.json` | Ajout `trame_vente` (6 étapes — intention + exemples + points clés) | ✅ |
| `src/api/routes/closer_public.py` | 2 nouveaux onglets dans fiche RDV : Arguments + Trame de vente | ✅ |
| VPS | Déployé + service redémarré (active) | ✅ |

### Livrables

**Arguments de vente** → onglet "Arguments" dans la fiche RDV closer
- OFFRE 500 : 4 arguments + pour qui + 4 limites (à dire clairement) + pitch upgrade 3500€
- OFFRE 3500 : 5 arguments + pour qui + 4 limites + pitch upgrade 9000€
- OFFRE 9000 : 5 arguments + différenciation + notion de domination

**Trame de vente** → onglet "Trame de vente" dans la fiche RDV
- 6 étapes : Ouverture / Compréhension / Diagnostic / Valeur / Offres / Closing
- Chaque étape : intention + exemples de phrases + points clés
- Cadre (pas un script rigid) — adaptatble au style de chaque closer

### Fiche RDV — onglets ressources (état final)

| Onglet | Contenu |
|---|---|
| Les offres | Accordéon 3 offres (texte + bouton lien paiement) |
| Arguments | Arguments / limites / upgrade par offre |
| Trame de vente | 6 étapes + exemples |
| Objections | 9 réponses aux objections |
| Commissions | Taux + montants par offre |

---

## 🔌 SESSION 2026-03-26 (suite 5) — Portail Closer + Offres refondues

### Réalisé

| Fichier | Action | Statut |
|---|---|---|
| `src/api/routes/closer_public.py` | Fiche RDV entièrement refondue | ✅ |
| `src/api/routes/closer_public.py` | 3 nouveaux endpoints (notes, complete, payment-link) | ✅ |
| `src/api/routes/closer_public.py` | Panel commissions : header mois + versé/à verser | ✅ |
| `data/closer_content.json` | Offres refondues + script + objections réécrits | ✅ |
| `data/marketing.db` | Closer test Thomas Leroy créé + 2 meetings assignés | ✅ |
| VPS | Déployé + service redémarré (active) | ✅ |

### Portail closer `/closer/{token}`

- **Panel Commissions** : en-tête "Ventes & Commissions — Mars 2026" + 4 KPIs (ventes ce mois / commission ce mois / taux / cumulé) + bloc Versé / À verser / En attente
- Stats mois filtrées sur `scheduled_at.month == now.month`
- Commissions versées depuis table `commissions` (status=paid vs pending)

### Fiche RDV `/closer/{token}/meeting/{id}`

**Bloc Score IA** :
- Score /10 (barre colorée rouge/orange/vert)
- "Cité X fois sur N requêtes IA"
- Panier moyen estimé par secteur (dict hardcodé : pisciniste 15-35k€, couvreur 8-15k€, etc.)
- Liste des concurrents cités par les IA (extraits du ia_results JSON)

**En-tête prospect** :
- Bouton 📞 tel: si téléphone disponible
- Bouton 🔗 Landing (lien vers landing page)
- Bouton "Clôturer ce RDV" → modal

**Modal clôture** :
- Select résultat : Signé / No-show / Annulé / À relancer
- Si Signé → select offre (500/3500/9000) + montant auto
- Si À relancer → champ date de relance
- Notes de clôture
- Submit → PATCH `meeting.status` + `deal_value` + notes en DB

**Notes auto-save** : textarea avec debounce 1s, PATCH `/notes` sans rechargement

**Onglets ressources** :
- "Les offres" → accordéon vertical, ouvert sur Exécution Complète (3 500€), prix en grand, bouton "Envoyer lien →"
- "Script & conseils" → guide déroulé + script fusionnés (aide-mémoire supprimé)
- "Objections" → 9 réponses dont objection exclusivité zone
- "Commissions" → taux + montants par offre

**3 nouveaux endpoints** :
- `PATCH /closer/{token}/meeting/{id}/notes` → auto-save notes
- `POST /closer/{token}/meeting/{id}/complete` → clôturer RDV
- `POST /closer/{token}/meeting/{id}/payment-link` → stub Stripe (à câbler quand Price IDs configurés)

### Offres refondues (`closer_content.json`)

| Offre | Ancien nom | Nouveau nom | Prix |
|---|---|---|---|
| 1 | Kit Autonome | Audit Complet | 500 € |
| 2 | Tout Inclus | Exécution Complète | 3 500 € |
| 3 | Domination IA Locale | Domination IA Locale + exclusivité territoriale | 9 000 € |

- Perplexity supprimé (remplacé par "les IA")
- "Cibles principales couvreurs/piscinistes..." supprimé
- Exclusivité territoriale ~100 km ajoutée sur offre 9000€
- Script de vente : guide déroulé intégré (plus d'aide-mémoire séparé)
- Objections : 9 réponses dont exclusivité zone

### Données test

- Closer test : Thomas Leroy, token `65d42e7629ec906b70d8063f88b6dcdd`, commission 15%
- 2 RDV assignés : 27/03 11h00 + 15h20 (prospect [TEST] Nathalie / Pisciniste / Paris)

### Reste à faire

- [ ] Configurer Stripe Price IDs (3 offres) → activer bouton "Envoyer lien"
- [ ] Job auto-scoring TESTED → SCORED
- [ ] Rapport hebdo automatique (offre 3500€)
- [ ] Boucle mensuelle auto (offre 9000€)
- [ ] `mots_cles_sirene` pour toutes les professions (actuellement seulement pisciniste)

---

## 🔌 SESSION 2026-03-26 (suite 4) — Refonte page Prospection

### Réalisé

| Fichier | Action | Statut |
|---|---|---|
| `src/api/routes/prospection_admin.py` | Refonte complète de `prospection_page()` | ✅ |
| VPS | Déployé + service redémarré (active) | ✅ |

### Nouvelle UX `/admin/prospection`

**En haut (visible)** :
- Formulaire rapide : Métier + Ville + Problématique (opt) + Mission (opt)
- Touche Entrée ou bouton "Ajouter au panier"
- `<datalist>` avec les métiers existants pour autocomplétion
- Panier JS (en mémoire) : liste des paires avec tags colorés, suppression unitaire
- Bouton "Lancer tout" : pour chaque paire → crée le métier (upsert) → crée le ciblage → lance le run

**En accordéons `<details>` fermés** :
- Ciblages existants (avec boutons Lancer / Activer / Supprimer)
- Métiers configurés (édition inline + ajout manuel)
- Requêtes IA (édition inline + ajout)
- Import CSV

---

## 🔌 SESSION 2026-03-26 (suite 3) — Monitoring clés API

### Réalisé

| Fichier | Action | Statut |
|---|---|---|
| `src/scheduler.py` | Job 10 ajouté — `_job_check_api_keys()` toutes les 6h | ✅ |
| `src/api/routes/admin.py` | Alerte "Clés API invalides" ajoutée dans `_build_alerts()` | ✅ |
| VPS | 2 fichiers déployés + service redémarré | ✅ |

### Comportement

- Toutes les 6h : test HTTP sur OpenAI / Gemini / Anthropic
- Si 401 ou 403 → email Brevo envoyé à `ADMIN_ALERT_EMAIL` avec liens de renouvellement
- Dashboard : badge rouge "Clés API invalides : X, Y" si détecté à l'ouverture

### Contexte

- Déclencheur : OpenAI (401) + Gemini (403) redétectés invalides pendant les tests pipeline
- Clés remises à jour manuellement depuis secrets.env → VPS : toutes les 3 valides (200)

---

## 🔌 SESSION 2026-03-26 (suite 2) — Tests pipeline complet

### Réalisé

| Test | Résultat |
|---|---|
| 19 steps testés automatiquement via script Python | 19/19 OK |
| Health, SIRENE, enrichissement, contacts, campagnes, SMS, tracking, RDV, closers, finances, dashboard | tous verts |

### Incohérences détectées

| Sévérité | Problème | Action |
|---|---|---|
| 🔴 | OpenAI 401 + Gemini 403 — clés expirées | Clés remplacées + monitoring ajouté |
| 🟡 | Stats marketing hub affiche "?" | marketing.db retourne 0 — normal si pipeline pas encore actif |
| 🟡 | CA closers hub affiche "?" | 0 deal signé en base — normal |

---

## 🔌 SESSION 2026-03-26 (suite) — Refonte interface admin

### Réalisé

| Fichier | Action | Statut |
|---|---|---|
| `src/api/routes/_nav.py` | Navigation refaite en 4 sections : LEADS / MARKETING / CLOSERS / FINANCES | ✅ |
| `src/api/routes/admin.py` | Bloc **Alertes** ajouté en tête du dashboard (leads non contactés, villes sans visuel, RDV non traités, pipeline bloqué) | ✅ |
| `src/api/routes/admin_hub.py` | Nouveau fichier — 4 pages hub sectorielles | ✅ |
| `src/api/main.py` | `admin_hub_router` enregistré | ✅ |
| VPS | 4 fichiers déployés + service redémarré | ✅ |

### Nouvelles pages

| Route | Contenu |
|---|---|
| `/admin/leads-hub` | KPIs funnel complet, taux de conversion par étape, liens rapides |
| `/admin/marketing` | Stats email/SMS (8 KPIs), ouverture/clic/RDV/ventes, détail complet |
| `/admin/closers-hub` | CA total, marge 82%, commissions, ventilation par offre, top closers |
| `/admin/finances` | CA par offre, IA cost tracking, form coûts (récurrent/ponctuel/type), résultat net estimé |

### Structure navigation

```
LEADS      → leads-hub, contacts, prospection, suspects, scheduler
MARKETING  → marketing, campaigns
CLOSERS    → closers-hub, crm, crm/closers
FINANCES   → finances, analytics
```

### À faire

- [ ] Configurer les Stripe Price IDs (payment bloqué sur les 3 offres)
- [ ] Câbler le scheduler rapport hebdo (Tout Inclus 3500€)
- [ ] Câbler la boucle mensuelle automatique (Domination 9000€)
- [ ] Vérifier rendu landing après refresh IA (29 paires ChatGPT + Gemini + Claude)
- [ ] `wp_jsonld_code.png` — capture manquante dans guide WP

---

## 🔌 SESSION 2026-03-26 — Landing page + Warming email + Scheduler IA

### Réalisé

| Fichier / Composant | Action | Statut |
|---|---|---|
| `src/api/routes/v3.py` | Fix `city_image_url` — évite double URL quand `header.url` déjà absolu | ✅ |
| `data/presence_ia.db` (VPS) | Fix URLs relatives city_headers → absolues pour 10 villes (Paris, Colmar, Bordeaux, Avignon, Toulon, Versailles, Cayenne, Bar-le-Duc, Bourg-en-Bresse, Mont-de-Marsan) | ✅ |
| `src/scheduler.py` | Ajout job `refresh_ia` — lun/jeu/dim à 9h30, 15h, 18h30 UTC | ✅ |
| `src/scheduler.py` | Warming : jitter ±45min (3h15–4h45 au lieu de 4h pile) | ✅ |
| `src/scheduler.py` | Warming : 20 sujets + 12 corps (vs 7+5 avant) | ✅ |
| `src/scheduler.py` | Warming : double aller-retour — bot répond (passe 1) + sender relance à 40% (passe 2) | ✅ |
| `src/scheduler.py` | Warming : emojis dans les réponses + délai humain avant réponse (2–18 min) et relance (5–35 min) | ✅ |
| Clés API VPS | OPENAI_API_KEY + GEMINI_API_KEY + ANTHROPIC_API_KEY mises à jour | ✅ |
| `/api/v3/refresh-ia` | Refresh manuel déclenché — 29 paires ville/métier en cours (ChatGPT + Gemini + Claude) | ✅ |

### Problèmes identifiés et résolus

- **Background landing absent** : `header.url` passé de relatif → absolu en DB, mais le code préfixait encore `base_url` → URL double cassée → fix dans v3.py
- **Clés API invalides sur VPS** : ChatGPT (401) + Gemini (403) + Anthropic (401) → toutes remplacées
- **Résultats IA = Claude × 3** : conséquence des clés invalides, le refresh corrige progressivement
- **Job refresh_ia manquant** : documenté dans les commentaires v3.py mais jamais ajouté au scheduler → ajouté
- **Warming trop régulier** : 4h pile détectable par les providers → jitter + délais humains

### À faire

- [ ] Vérifier après le refresh (29 paires, ~22 min) que ChatGPT + Gemini + Claude apparaissent bien sur la landing
- [ ] Captures Wix + Shopify pour le guide PREMIUM (`GUIDE_VISIBILITE_IA_PREMIUM.html`)
- [ ] Configurer les Stripe Price IDs (payment bloqué sur les 3 offres)
- [ ] Câbler le scheduler rapport hebdo (Tout Inclus 3500€)
- [ ] Câbler la boucle mensuelle automatique (Domination 9000€)
- [ ] `wp_jsonld_code.png` — capture Insert Headers and Footers avec JSON-LD (manquante dans guide WP)

---

## 🔌 SESSION 2026-03-22 (suite 15) — ZIP livrable Kit Autonome

### Réalisé

| Fichier | Contenu | Statut |
|---|---|---|
| `RESOURCES/KIT_AUTONOME_GUIDES_CMS.zip` | 3 guides (WP + Wix + Shopify), 36 Ko | ✅ créé |

### Contenu du ZIP

- `GUIDE_WORDPRESS_VISIBILITE_IA.html` — 25 items checklist, 11 sections
- `GUIDE_WIX_VISIBILITE_IA.html` — 27 items checklist, spécificités Wix
- `GUIDE_SHOPIFY_VISIBILITE_IA.html` — 30 items checklist, spécificités Shopify

### À faire

- [ ] Déployer le ZIP sur le VPS (accessible en téléchargement depuis /resources/)
- [ ] Configurer les Stripe Price IDs (payment bloqué sur les 3 offres)
- [ ] Câbler le scheduler rapport hebdo (Tout Inclus 3500€)
- [ ] Câbler la boucle mensuelle automatique (Domination 9000€)

---

## 🔌 SESSION 2026-03-22 (suite 14) — Guide Shopify Kit Autonome

### Réalisé

| Fichier | Statut |
|---|---|
| `RESOURCES/GUIDE_SHOPIFY_VISIBILITE_IA.html` | ✅ créé |

### Spécificités Shopify couvertes

- Mode mot de passe (point bloquant n°1)
- Domaine .myshopify.com → personnalisé obligatoire
- Thème dupliqué avant modification code
- Boutique en ligne → Préférences (SEO global)
- Section "Référencement" par produit/collection/page
- Blog FAQ avec questions en H2
- JSON-LD dans theme.liquid avant `</head>`
- Google Search Console via Préférences
- Collections : descriptions souvent vides par défaut

### Sidebar checklist : 30 items, progression sauvegardée (localStorage)

---

## 🔌 SESSION 2026-03-22 (suite 13) — Guide Wix Kit Autonome

### Réalisé

| Fichier | Statut |
|---|---|
| `RESOURCES/GUIDE_WIX_VISIBILITE_IA.html` | ✅ créé |

### Spécificités Wix couvertes

- Domaine personnalisé obligatoire (point bloquant expliqué)
- Wix Editor vs Wix Studio
- Widget Accordéon + Wix App Market FAQ
- Paramètres SEO page par page (3 points → Paramètres SEO)
- SEO Wiz + connexion Google Search Console
- Custom Code (Head) pour JSON-LD
- Historique du site pour sauvegarde
- Piège "Heading 2 utilisé comme H1 visuel"

### Sidebar checklist : 27 items, progression sauvegardée (localStorage)

### À faire

- [ ] Créer le guide Shopify (dernière plateforme manquante)
- [ ] Packager les 3 guides dans le ZIP livrable Kit Autonome

---

## 🔌 SESSION 2026-03-22 (suite 12) — Guide WordPress Kit Autonome

### Réalisé

| Fichier | Contenu | Statut |
|---|---|---|
| `RESOURCES/GUIDE_WORDPRESS_VISIBILITE_IA.html` | Guide complet 11 sections, HTML premium | ✅ |

### Contenu du guide

| Section | Détail |
|---|---|
| Introduction | Objectif + résultat attendu |
| Pré-requis | Admin WP, plugins (Yoast/Rank Math, Insert Headers) |
| Page d'accueil | H1 + premier paragraphe optimisés, captures définies |
| Pages services | Structure 7 blocs, texte copiable, captures |
| Page FAQ | 8 Q/R copiables, formulation orientée IA |
| JSON-LD | Code complet copiable avec tous les champs clés |
| Balises H1/H2 | Règles + comparatif avant/après |
| Page À propos | Structure factuellement riche |
| Exemples avant/après | 5 comparatifs (accueil, service, FAQ, méta) |
| Erreurs à éviter | 10 erreurs fréquentes |
| Checklist finale | 30 items à cocher avec captures requises |

### Compte-rendu : ce bloc _SUIVI.md

### À faire

- [ ] Créer le même guide pour Wix
- [ ] Créer le même guide pour Shopify
- [ ] Intégrer les guides dans le livrable Kit Autonome (ZIP ou page dédiée)

---

## 🔌 SESSION 2026-03-22 (suite 11) — Pipeline offres → modules EURKAI

### Réalisé

| Livrable | Statut |
|---|---|
| Inventaire des modules réels (13 endpoints) | ✅ |
| Pipeline 500€ — 6 étapes, exécution once | ✅ |
| Pipeline 3 500€ — phase initiale + suivi mensuel | ✅ |
| Pipeline 9 000€ — phase 1 + boucle mensuelle ×12 + logique amélioration | ✅ |
| Tableau modules × offres | ✅ |
| Gaps identifiés (5) avec effort + solution | ✅ |

### Gaps prioritaires

| Gap | Offre | Priorité |
|---|---|---|
| Rapport hebdo automatique | 3 500€ | Moyen |
| Guides CMS statiques dans /RESOURCES/ | 500€ | Faible |
| Boucle mensuelle automatique (jobs.py) | 9 000€ | Moyen |
| Export rapport mensuel HTML/PDF | 9 000€ | Moyen |
| Citations locales | 3 500€ + 9 000€ | Manuel |

### Compte-rendu : `PIPELINE_OFFRES_2026-03-22.md`

---

## 🔌 SESSION 2026-03-22 (suite 10) — Catalogue offres structuré

### Réalisé

| Livrable | Statut |
|---|---|
| 3 fiches offres (cible / problème / résultat / contenu / non inclus / effort / argumentaire) | ✅ |
| Tableau comparatif 10 critères | ✅ |
| Argumentaire closer simplifié (qualifier → orienter → fermer) | ✅ |
| 3 résumés checkout | ✅ |
| 3 versions home ultra-synthétiques | ✅ |

### Compte-rendu : `CATALOGUE_OFFRES_2026-03-22.md`

### À faire

- [ ] Injecter les résumés checkout dans `/admin/offers` → champ `Résumé checkout`
- [ ] Injecter les versions home dans la section pricing de la landing
- [ ] Vérifier cohérence avec les meta déjà en DB

---

## 🔌 SESSION 2026-03-22 (suite 9) — Recrutement closer t13/t14/t15

### Réalisé

| Tâche | Contenu | Statut |
|---|---|---|
| t13 — Post Facebook | Prêt à copier-coller | ✅ |
| t14 — Réponse commentaire | "Reçu 👌 Je t'envoie le lien en MP." | ✅ |
| t15 — Message MP | Prêt à copier-coller avec lien `/closer/recruit` | ✅ |

### Compte-rendu : `RECRUTEMENT_CLOSER_2026-03-22.md` (existant)

### À faire

- [ ] Publier le post Facebook
- [ ] Répondre aux commentaires "CLOSER" avec la réponse courte
- [ ] Envoyer le MP à chaque commentateur

---

## 🔌 SESSION 2026-03-22 (suite 8) — Meta offres finalisées

### Réalisé

| Offre | Champs corrigés | Statut |
|---|---|---|
| Kit Autonome 500€ | `description_closer`, `description_checkout`, `result_promised` | ✅ |
| Tout Inclus 3 500€ | `description_closer` (timeline + "de A à Z") | ✅ |
| Domination IA Locale 9 000€ | `result_promised` (reformulé outcome-first) | ✅ |

### Cohérence montée en gamme

| | 500€ | 3 500€ | 9 000€ |
|---|---|---|---|
| Positionnement | Autonomie + outils | Délégation totale | Domination + durée |
| Effort client | Appliquer soi-même | Zéro | Zéro |
| Timeline résultats | Dès application | Mois 2-3 | Mois 1-2 + 12 mois |
| Upgrade | → Tout Inclus | → Domination | Reconduction |

### Compte-rendu : `META_OFFRES_2026-03-22.md`

### À faire

- [ ] Configurer les Stripe Price IDs (sans eux : paiement impossible)
- [ ] Vérifier rendu portail closer + landing page (descriptions visibles)

---

## 🔌 SESSION 2026-03-22 (suite 7) — Source de vérité unique offres

### Réalisé

| Fichier | Description | Statut |
|---|---|---|
| `OFFERS_MODULE/offers_module/models.py` | Ajout colonne `meta TEXT DEFAULT "{}"` dans `OfferDB` | ✅ |
| `OFFERS_MODULE/offers_module/schemas.py` | Ajout `meta: Optional[str]` dans OfferCreate / OfferUpdate / OfferOut | ✅ |
| DB VPS `data/presence_ia.db` | `ALTER TABLE offers ADD COLUMN meta TEXT` + seed 3 offres (500/3500/9000€) avec meta complète | ✅ |
| `src/api/routes/offers.py` | Admin — affichage/édition de tous les champs meta (closer, checkout, cible, EURKAI, etc.) | ✅ |
| `src/api/routes/closer_public.py` | Onglet "L'offre" branché sur OfferDB (3 cartes dynamiques avec meta.description_closer) | ✅ |
| `src/api/routes/generate.py` | Landing page — ajout `description_checkout` sous les features de chaque plan | ✅ |
| Déploiement VPS | 5 fichiers copiés + service redémarré — tests OK (3 offres visibles dans portail demo) | ✅ |

### Structure meta OfferDB

```json
{
  "description_closer": "Pitch vendeur pour l'onglet 'L'offre' du portail closer",
  "description_checkout": "Résumé affiché sur la landing page au-dessus du bouton 'Choisir ce plan'",
  "target": "Pour qui",
  "result_promised": "Résultat visé",
  "duration_months": 3,
  "execution_frequency": "once|monthly|quarterly",
  "execution_qty": 1,
  "not_included": ["liste", "de", "ce", "qui", "n'est", "pas", "inclus"],
  "upgrade_pitch": "Argumentaire pour monter de gamme",
  "eurkai_modules": [{"module": "AI_INQUIRY_MODULE", ...}]
}
```

### Compte-rendu : `SOURCE_VERITE_OFFRES_2026-03-22.md`

### À faire

- [ ] Remplir les champs meta dans `/admin/offers` (description_closer + description_checkout pour chaque offre)
- [ ] Configurer les Stripe Price IDs
- [ ] Vérifier rendu landing page avec descriptions checkout

---

## 🔌 SESSION 2026-03-22 (suite 6) — Recrutement closer t24

### Réalisé

| Fichier | Description | Statut |
|---|---|---|
| `src/api/routes/closer_public.py` | Fix contenu : `~89€` → `90–1620€ par deal signé` (valeur démo remplacée par fourchette réelle) | ✅ |

### Contenu produit

- Message Facebook prêt à poster (mot-clé "CLOSER" → MP)
- Message MP avec lien `/closer/recruit` + consigne audio/vidéo
- Pages `/closer/` et `/closer/recruit` vérifiées et opérationnelles

### Compte-rendu : `RECRUTEMENT_CLOSER_2026-03-22.md`

### À faire

- [ ] Poster le message Facebook
- [ ] Gérer les commentaires → envoyer le MP
- [ ] Suivre les candidatures dans `/admin/crm/closers`

---

## 🔌 SESSION 2026-03-22 (suite 5) — Tests closer t16 + t17

### Réalisé

| Fichier | Description | Statut |
|---|---|---|
| `src/api/routes/closer_public.py` | Fix bug : suppression `date_of_birth` du dict data (champ absent du modèle ORM) | ✅ |
| DB VPS `data/marketing.db` | Création tables `closer_applications` + `closers` (jamais initialisées sur cette DB) | ✅ |
| DB VPS `closers` | Table recrée avec schéma complet (colonne `token` manquante — désynchronisation) | ✅ |

### Résultats tests

| Tâche | Résultat |
|---|---|
| t16 — Candidature complète | ✅ soumise + visible en admin (id `ae685ce9`) |
| t17 — Portail closer | ✅ accessible + onglets L'offre / Script / Objections + contenu `closer_content.json` chargé |

### Compte-rendu : `CLOSER_TESTS_2026-03-22.md`

---

## 🔌 SESSION 2026-03-22 (suite 4) — Socle commercial closers

### Réalisé

| Fichier | Description | Statut |
|---|---|---|
| `data/closer_content.json` | Créé — script 7 étapes, 8 objections, offres brief, commission, guide RDV | ✅ |
| `RESOURCES/FICHE_PRODUIT_PRESENCE_IA.html` | Amélioré — section Positionnement + bloc détails par offre (pour qui, pas inclus, résultat, délai, argumentaire) | ✅ |

### Contenu produit

- **Positionnement** : ce que c'est / à qui / problème / résultat / ce que ce n'est pas
- **Script** : 7 étapes orales (ouverture → closing → suite)
- **Objections** : 8 traitées (trop cher / réfléchir / agence / IA / temps / garanties / infos / attendre)
- **Fiches offres** : 3 offres avec pour qui / pas inclus / résultat / délai / argumentaire closer

### Commissions rappel

| Offre | Prix | Commission |
|---|---|---|
| Kit Autonome | 500 € | ~90 € |
| Tout Inclus | 3 500 € | ~630 € |
| Domination IA Locale | 9 000 € | ~1 620 € |

Bonus +5 % pour les 2 meilleurs closers du mois.

### Source principale

`data/closer_content.json` → portail closer (`/closer/{token}`) — onglets Script, Objections, L'offre.
Compte-rendu : `CLOSER_SOCLE_2026-03-22.md`

### À faire

- [ ] Configurer Stripe Price IDs sur `/admin/offers` → activer le paiement
- [ ] Recruter 1 closer minimum (0 en base — bloquant commercial)
- [ ] Mettre à jour `ANTHROPIC_API_KEY` sur VPS

---

## 🔌 SESSION 2026-03-22 (suite 3) — mots_cles_sirene toutes professions

### Réalisé

| Fichier | Description | Statut |
|---|---|---|
| DB VPS `professions` | `mots_cles_sirene` ajoutés pour les 11 professions actives sans mots-clés | ✅ |

### Détail

- **11/11 professions** mises à jour — plus aucune profession active sans mots-clés
- Workaround : clé `ANTHROPIC_API_KEY` sur le VPS révoquée (401) → mots-clés générés en local selon les mêmes règles que le prompt `sirene_keywords.py`, poussés directement via `sqlite3` Python sur SSH
- Compte-rendu : `KEYWORDS_SIRENE_2026-03-22.md`

### À faire

- [ ] Mettre à jour `ANTHROPIC_API_KEY` sur le VPS (clé actuelle révoquée — bloque l'endpoint `/admin/sirene/generate-keywords`)
- [ ] Relancer enrichissement → vérifier filtrage mots-clés OK + 0 doublon créé
- [ ] Lancer campagne sur les 72 prospects uniques — **pas encore, décision à prendre**
- [ ] Surveiller réponses IMAP (8 entreprises contactées ce jour)
- [ ] Vérifier warming au prochain run (~18h UTC) : logs `warming: X emails envoyés`

---

## 🔌 SESSION 2026-03-22 (suite 2) — Campagne test + fix doublons v3_prospects

### Réalisé

| Fichier | Description | Statut |
|---|---|---|
| `src/api/routes/leads_runner.py` | Fix bug critique : vérification email existant avant insert dans `V3ProspectDB` | ✅ |
| DB VPS `v3_prospects` | Dédoublonnage : 574 → 73 entrées (501 supprimées), 0 doublon restant | ✅ |

### Campagne test email — 2026-03-22 14h26

- 20 emails envoyés via Brevo (0 erreur technique)
- Bug découvert : seulement **8 adresses uniques** touchées — doublons en base
- `contact@belles-piscines.com` a reçu **7 fois** le même email
- Bug corrigé → plus aucun doublon possible à l'enrichissement

### Preview SMS — 2026-03-22

- Template `__global__` utilisé correctement
- Message : `Les IA citent vos concurrents, pas vous. Voyez pourquoi en 20 min : {landing_url}` — 120 chars
- Résultat : ✅ OK

### État DB après corrections

- `v3_prospects` : **73 entrées uniques**, 72 non contactées, prêtes pour campagne
- Doublons : **0**
- Fix anti-doublon déployé sur VPS

### À faire

- [ ] Relancer enrichissement → vérifier 0 doublon créé
- [ ] Surveiller réponses IMAP (8 entreprises contactées ce jour)

---

## 🔌 SESSION 2026-03-22 (suite) — Templates, tests envoi, fix warming

### Réalisé

| Fichier | Description | Statut |
|---|---|---|
| DB VPS `v3_landing_texts` | Templates `__global__` corrigés : `{Calendly}` invalide → `{landing_url}` + accents restaurés | ✅ |
| `src/api/routes/contacts.py` | Fix `preview-sms` et `send-sms` test : chargent maintenant le template `__global__` depuis la DB | ✅ |
| `src/scheduler.py` | Fix bug critique `_warming_day_cap()` : `datetime.utcnow()` → `_dt.datetime.utcnow()` | ✅ |

### Test envoi email — 2026-03-22

- 4 emails envoyés via Brevo depuis `contact@presence-ia.online`
- **3/4 reçus** : contact@presence-ia.com ✓ · contact@nathaliebrigitte.com ✓ · nathaliecbrigitte@gmail.com ✓
- **nathalie.brigitte@gmail.com** : non reçu — probablement filtré spam/promotions Gmail (domaine en warmup)
- **À surveiller** : retesters nathalie.brigitte@gmail.com dans ~1 semaine quand le warming aura progressé

### Bug warming (critique, corrigé)

- Le job `_job_warming` s'exécutait toutes les 4h depuis le 20/03 mais crashait immédiatement
- Erreur : `name 'datetime' is not defined` dans `_warming_day_cap()`
- **Zéro email de warming envoyé depuis le démarrage**
- Fix : `datetime.utcnow()` → `_dt.datetime.utcnow()` (le module était importé comme `_dt`)
- Déployé et redémarré — prochain run dans ~4h

### État pipeline au 2026-03-22

| Job | Statut |
|---|---|
| SIRENE scan (Lun/Mer/Ven 2h UTC) | ✅ actif |
| Enrichissement Google Places (toutes les heures) | ✅ actif — 20 suspects/run — 1er batch : 12 contacts créés |
| Provisioning leads (7h UTC Lun-Ven) | ✅ actif — 20 leads/run |
| Email warming (toutes les 4h) | ✅ **fixé** — était cassé depuis le 20/03 |

### À surveiller

- [ ] **nathalie.brigitte@gmail.com** : rétester dans ~1 semaine (délivrabilité Gmail)
- [ ] Confirmer que le warming envoie bien des emails au prochain run (~18h UTC)
- [ ] Générer `mots_cles_sirene` pour les 11 professions sans mots-clés (enrichissement ne les traite pas encore)

---

## 🔌 SESSION 2026-03-20/22 — Enrichissement auto + test multi-emails + fix villes

### Réalisé

| Fichier | Description | Statut |
|---|---|---|
| `src/models.py` | Nouveau modèle `EnrichmentConfigDB` (active, suspects_per_run, hour_utc, days, last_run, last_count) | ✅ |
| `src/scheduler.py` | Job `_job_auto_enrich()` — enrichissement Google Places automatique, toutes les heures, respecte config admin | ✅ |
| `src/api/routes/professions_admin.py` | `POST /api/admin/enrich/config` + `POST /api/admin/enrich/run-now` | ✅ |
| `src/api/routes/professions_admin.py` | Panneau UI "Enrichissement automatique" (toggle actif, suspects/run, heure UTC, jours, "Lancer maintenant") | ✅ |
| `src/api/routes/contacts.py` | Test email : 4 adresses pré-cochées (nathalie.brigitte, nathaliecbrigitte, contact@nathaliebrigitte, contact@presence-ia) multi-select | ✅ |
| `src/api/routes/contacts.py` | Bouton "Prévisualiser SMS" (dry run — affiche le message sans envoyer, avec nb caractères) | ✅ |
| `src/api/routes/contacts.py` | Endpoint `POST /admin/contacts/test/preview-sms` | ✅ |
| `src/api/routes/headers.py` | Fix matching ville : cherche `aspach michelbach` ET `aspach-michelbach` (or_ SQLAlchemy) | ✅ |
| DB VPS | Codes postaux manquants ajoutés : Aspach-Michelbach (68700), Bénesse-Maremne (40230), Puget-sur-Argens (83480) | ✅ |

### Chaîne d'automatisation complète (après activation depuis Admin)

```
Lun/Mer/Ven 2h UTC  → _job_auto_qualify    : récupération suspects SIRENE (671K en DB)
             3h UTC  → _job_auto_enrich     : enrichissement Google Places (tel/email) — NOUVEAU
             7h UTC  → _job_provision_leads : push contactables → ContactDB
```

### État DB au 2026-03-22
- Suspects : **671 140** (tous `enrichi_at=NULL` — à enrichir)
- Contacts : **15** (3 provisionnés auto)
- Segments : **1 718/1 719 done** (SIRENE quasi-complet)
- Enrichissement config : **active=False** (à activer depuis Admin/Leads)
- Provisioning config : **active=False** (à activer après 1er batch enrichissement)

### À faire avant activation
- [ ] Admin/Leads → activer "Enrichissement Google Places" (régler quantité + heure)
- [ ] Tester avec "Lancer maintenant" → vérifier 1er batch (contacts avec tel/email)
- [ ] Activer "Fourniture leads" après validation enrichissement
- [ ] Tester envoi email depuis page Contacts (4 adresses test) + prévisualisation SMS
- [ ] `mots_cles_sirene` : générer à la volée par profession au moment de l'enrichissement

### Décisions
- `mots_cles_sirene` générés à la demande (par profession, au moment de l'enrichissement) — pas en masse
- SMS : pas de 2e numéro → dry run "Prévisualiser" pour valider le contenu

---

## 🔌 SESSION 2026-03-17 — Pipeline leads unifié + page Contacts

### Réalisé

| Fichier | Description | Statut |
|---|---|---|
| `src/models.py` | Champ `mots_cles_sirene TEXT` sur `ProfessionDB` | ✅ |
| `src/database.py` | Migration AUTO `mots_cles_sirene` au démarrage | ✅ |
| `src/sirene.py` | `_get_name_keywords_for_segment()` utilise `mots_cles_sirene` (filtre étymologique, non aqua/natation) | ✅ |
| `src/sirene_keywords.py` | **NOUVEAU** — génération LLM (Anthropic) des mots-clés SIRENE par profession | ✅ |
| `src/api/routes/professions_admin.py` | Bouton "🔑 Mots-clés SIRENE", colonne ✓/⚠, `data-has-kw`, endpoint `POST /admin/sirene/generate-keywords` | ✅ |
| `src/api/routes/leads_runner.py` | **NOUVEAU** — pipeline unifié qualification+enrichissement, boucle par lots, `enrichi_at` pour ne jamais retraiter | ✅ |
| `src/api/routes/contacts.py` | **RÉÉCRIT** — page ContactDB, widget leads inline, checkboxes sélection groupée, mode test email/SMS, boutons ✉/💬 par ligne | ✅ |
| `src/api/routes/_nav.py` | Sidebar simplifiée (suppression enrich, naf-audit, segments, v3 contacts) | ✅ |
| `src/api/main.py` | Mount router `leads_runner` | ✅ |

### Bugs corrigés
- `generateKeywords` JS dans mauvais bloc script → corrigé
- `toast` non défini sur page professions → remplacé par `alert()`
- 422 sur `/admin/leads/run` : `Request` non typé FastAPI → corrigé
- Téléphone tronqué : regex `[^\s|]+` → lecture directe `c.phone`
- Pipeline stoppé après 1 lead : retraitait les mêmes suspects en boucle → fix `enrichi_at IS NULL`
- Compteur `traités > suspects` (quadratique) → `enrichi_at` marqué AVANT appel API
- Apostrophe dans `confirm()` JS → guillemets doubles
- 550 doublons contacts supprimés (pipeline bugué avait tout retraité)

### État base au 2026-03-17
- Suspects : **6 637** (tous `enrichi_at = NULL` — remis à zéro pour relance propre)
- Contacts : **11 prospects piscinistes** (collectés malgré le bug)
- Segments : **~1 719 total, ~99 done**
- `mots_cles_sirene` généré pour : pisciniste ✅ (autres à faire)

### Prochaine étape
- [ ] Relancer pipeline pisciniste (20 leads) pour valider la logique `enrichi_at`
- [ ] Générer `mots_cles_sirene` pour les autres professions
- [ ] Tester envoi email/SMS depuis page Contacts (mode test + groupé)
- [ ] Vérifier template email/SMS global (`__global__`) est bien configuré

### Mode test contacts
- Email : `nathalie.brigitte@gmail.com` (pré-rempli par défaut)
- Tel : `0660474292` (pré-rempli par défaut)
- Métier : lu depuis le select du widget leads

---

## 🔌 SESSION 2026-03-16 — SIRENE pipeline, Audit NAF, filtre suspects

### Réalisé

| Fichier | Description | Statut |
|---|---|---|
| `src/api/routes/enrich_admin.py` | **NOUVEAU** — `/admin/enrich` : enrichissement suspects → prospects V3 via Google Places + scraping (qty = nb contactables voulus, pas suspects traités) | ✅ |
| `src/api/routes/naf_audit.py` | **NOUVEAU** — `/admin/naf-audit` : audit codes NAF en direct sur SIRENE, détection conflits (55 NAF partagés), purge suspects ambigus par NAF ou en masse | ✅ |
| `src/api/routes/professions_admin.py` | Liste suspects cliquable, page `/admin/suspects` paginée, modal qualification redesignée (tableau par profession : suspects + segments done/total), checkbox masquer NAF litigieux | ✅ |
| `src/database.py` | `db_suspects_list()` paginée avec filtres | ✅ |
| `src/sirene.py` | `_get_name_keywords_for_segment()` : si NAF ambigu (partagé 2+ professions), filtre résultats SIRENE par raison sociale sur `termes_recherche` | ✅ |
| `src/api/routes/_nav.py` | Ajout "Enrichir suspects" + "Audit NAF" dans sidebar | ✅ |

### Corrections données VPS (SQL direct)
- `pisciniste` : NAF 4329A → **4329B**, suspects erronés supprimés + resegmentés (OTIS/KONE exclus par filtre nom)
- `dentiste-implantologie` + `orthodontiste-prive` : 8621Z → **8623Z**
- `chirurgien-esthetique` : 8621Z → **8622B**
- **Purge globale 2026-03-16 21h** : 133 769 suspects supprimés, 419 segments remis en `pending` (base vide, qualif à relancer)

### État base au 2026-03-16
- Suspects : **0** (purgé, relance nécessaire)
- Segments : **419 pending**
- Professions actives : 1 (pisciniste coché) + autres à activer selon besoin

### Prochaine étape
- [ ] Relancer qualification (pisciniste d'abord pour valider filtre nom)
- [ ] Automatisation `mots_cles_sirene` via LLM pour chaque profession (termes apparaissant dans raison sociale SIRENE, différents de termes_recherche Google)
- [ ] Tester pipeline complet suspects → enrichissement → prospects V3

---

## 🔌 SESSION 2026-03-13 — CRM, CLOSER, GTM, REPLY TRACKING

### Réalisé

| Fichier | Description | Statut |
|---|---|---|
| `libs/marketing_module/models.py` | ContactDB, CloserApplicationDB, ProspectJourneyDB, MeetingDB enrichi (rescheduled_from_id, outcome, commission_rate/amount), ProspectDeliveryDB (landing_visited_at, calendly_clicked_at), CloserDB enrichi (token, contact_id, dob), enums JourneyStage + ApplicationStage | ✅ |
| `libs/marketing_module/database.py` | _migrate_existing_tables() ALTER TABLE idempotent + CRUD Contact, Journey, Application | ✅ |
| `src/api/routes/crm_admin.py` | **NOUVEAU** — /admin/crm vue Table + Kanban drag&drop 6 colonnes, /admin/crm/closers, /admin/crm/application/{id} validation 1 clic | ✅ |
| `src/api/routes/closer_public.py` | **NOUVEAU** — /closer/ présentation, /closer/recruit formulaire (vidéo+audio+message), /closer/{token} portail closer, /closer/{token}/meeting/{id} fiche RDV | ✅ |
| `src/api/routes/_nav.py` | Section CRM ajoutée dans sidebar admin | ✅ |
| `src/api/main.py` | Routers crm_admin + closer_public + mount closer-audio static | ✅ |
| `src/api/routes/_gtm.py` | **NOUVEAU** — helper gtm_head(), gtm_body(), gtm_push() — activé via GTM_ID env var | ✅ |
| `src/api/routes/v3_mkt_bridge.py` | record_landing_visit(), record_calendly_click() | ✅ |
| `src/api/routes/v3.py` | GTM dans landing /l/{token}, /l/track/calendly/{token} redirect trackée, tous les liens Calendly instrumentés, webhook Twilio inbound SMS | ✅ |
| `src/api/routes/page_builder_route.py` | GTM dans render_home | ✅ |
| `src/scheduler.py` | _job_imap_reply_poll() toutes les 5 min + _send_reply_alert() via Brevo | ✅ |

### Variables d'env à configurer sur le VPS

```bash
# GTM
GTM_ID=GTM-XXXXXXX

# IMAP reply tracking (contact@presence-ia.com ou autre boîte)
IMAP_HOST=imap.gmail.com          # ou imap.ionos.de, mail.ionos.fr etc.
IMAP_PORT=993
IMAP_USER=contact@presence-ia.com
IMAP_PASSWORD=xxxx
IMAP_FOLDER=INBOX

# Alerte réponse (email admin à alerter)
ADMIN_ALERT_EMAIL=ton@email.com

# Twilio inbound SMS
# Configurer dans console Twilio : Messaging → Phone Number → Webhook
# POST https://presence-ia.com/api/v3/webhooks/twilio/inbound
```

### URLs nouvelles en prod

| URL | Description |
|-----|-------------|
| `/admin/crm` | CRM pipeline (table + kanban) |
| `/admin/crm/closers` | Gestion closers + candidatures |
| `/closer/` | Page présentation programme closer |
| `/closer/recruit` | Formulaire candidature |
| `/closer/{token}` | Portail closer |
| `/l/track/calendly/{token}` | Tracking clic Calendly |
| `POST /api/v3/webhooks/twilio/inbound` | Webhook SMS entrant |

### Commits déployés
- `f4caaac` — CRM Kanban + Closer + marketing_module enrichi
- `0a10f17` — GTM + tracking landing_visited_at + calendly_clicked_at
- *(reply tracking — en cours)*

### À faire / en attente

- [ ] Configurer `IMAP_*` + `ADMIN_ALERT_EMAIL` sur VPS
- [ ] Configurer webhook Twilio inbound dans console Twilio
- [ ] Créer container GTM-XXXXXXX + ajouter GTM_ID sur VPS
- [ ] Configurer GTM : triggers landing_visit, calendly_click, cta_click
- [ ] Remplir contenu `/closer/` (script de vente, objections)
- [ ] Long terme : Brevo Inbound Parsing (MX record replies.presence-ia.fr → temps réel)

---

## 🔌 SESSION 2026-03-12 — RESTAURATION LANDING PAGE + FIX ADMIN

### Réalisé
| Fichier | Description | Statut |
|---|---|---|
| `src/api/main.py` | Routeur admin/login déplacé AVANT generate (catch-all `/{profession}`) — fix `/admin` returning 404 | ✅ |
| `src/api/routes/admin.py` | `_check_token` redirige vers `/admin/login` (302) au lieu de 403 | ✅ |
| `src/api/routes/v3.py` | Logo SVG ajouté dans la nav (`/assets/logo.svg`, height:54px) | ✅ |
| `src/api/routes/generate.py` | **Restauration état référence** : overlay hero `.78/.85`, "Aucun concurrent cité", marques IA texte seul (sans icônes SVG), suppression `_AI_LOGOS` dict | ✅ |

### Commits déployés
- `484a61f` — fix admin router ordering + redirect
- `b3a6f40` — revert v3 landing
- `59cb265` — v3 logo SVG nav
- `79f8be3` — fix generate: marques texte seul, suppression SVG logos IA

### Référence utilisée
`/Users/nathalie/Dropbox/____BIG_BOFF___/_INPUTS/TOIT'URIEN — Audit Visibilite IA (1).html`
(sauvegardé depuis `https://presence-ia.com/couvreur?t=6b84ba4b258f4eaabdf7b3e4`)

---

## 🔌 SESSION 2026-03-11 — ENRICHISSEMENT PROSPECTS (url, nom, cms, tel, mobile, email)

### Réalisé
| Fichier | Description | Statut |
|---|---|---|
| `src/cms_detector.py` | Nouveau — détecte CMS depuis HTML/headers (wp, wix, squarespace, webflow, shopify, jimdo, prestashop, joomla, drupal, typo3) | ✅ |
| `src/enrich.py` | Ajout `enrich_website()` (email + mobile en 1 requête) + `_classify_phone()` | ✅ |
| `src/google_places.py` | `_classify_phone()` intégrée, `international_phone_number` dans Details, nouvelle `search_prospects_enriched()` | ✅ |
| `src/models.py` | Colonnes `mobile TEXT` + `cms TEXT` ajoutées à ProspectDB | ✅ |
| `src/database.py` | Migration auto `prospects.mobile` + `prospects.cms` | ✅ |
| `src/api/routes/campaign.py` | Route `/prospect-scan/auto` utilise `search_prospects_enriched`, retourne 6 champs | ✅ |

### Réponse retournée par `/api/prospect-scan/auto`
```json
{
  "id": "...", "name": "Dupont Toiture", "website": "https://dupont-toiture.fr",
  "tel": "02 99 12 34 56", "mobile": "06 12 34 56 78",
  "email": "contact@dupont-toiture.fr", "cms": "wordpress"
}
```

### Prochaines étapes
- [ ] Déployer sur VPS + tester avec vraie campagne
- [ ] Résoudre blocage Cloudflare pour tests IA (solution extension Chrome)

---

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
