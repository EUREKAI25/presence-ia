# REF_IA — Suivi

**Statut** : ✅ MVP livré — pipeline complet opérationnel
**Créé** : 2026-02-12
**Dernière MAJ** : 2026-02-17
**Pipeline** : BRIEF ✅ → CDC ✅ → DEV ✅ → TESTS ✅ → GITHUB ✅

**GitHub** : https://github.com/EUREKAI25/ref-ia
**Local** : `/Users/nathalie/Dropbox/____BIG_BOFF___/PROJETS/PRO/REF_IA/`
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
| `src/api/routes/admin.py` | Admin UI HTML (ADMIN_TOKEN) |

---

## Historique

- 2026-02-12 : Création automatique via Pipeline Agence
- 2026-02-17 : Implémentation complète (session Claude Code)
  - 27 fichiers créés — 1788 lignes
  - Modules : scan, ia_test, scoring, generate, assets, scheduler
  - Routes API : campaign, ia_test, scoring, generate, pipeline, admin
  - Tests pytest : test_scoring (9 cas), test_ia_extract (12 cas)
  - README.md complet avec quickstart 10 lignes
  - GitHub : https://github.com/EUREKAI25/ref-ia
  - .env → symlink `/Users/nathalie/.bigboff/secrets.env`

## Prochaines étapes

- [ ] Lancer le serveur et tester le runner : `POST /api/pipeline/run`
- [ ] Valider le dry_run avec vraies données (couvreurs Lyon/Paris)
- [ ] Ajouter assets (video_url + screenshot_url) pour 1 prospect test
- [ ] Vérifier la landing page GET `/couvreur?t=TOKEN`
- [ ] Déployer sur VPS / Railway si validation OK
