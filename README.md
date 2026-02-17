# PRESENCE_IA — Pipeline Prospection IA

> Audit de visibilité IA pour artisans locaux — pipeline B2B complet sans envoi auto.

## Quickstart (10 lignes)

```bash
# 1. Dépendances
pip install -r requirements.txt

# 2. Variables d'environnement
cp .env.example .env  # puis renseigner les clés

# 3. Lancer le serveur
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload

# 4. Runner complet (SCAN → TEST → SCORE → GENERATE → QUEUE)
curl -X POST http://localhost:8001/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"city":"Lyon","profession":"couvreur","max_prospects":5,"dry_run":true}'
```

Swagger : http://localhost:8001/docs
Admin UI : http://localhost:8001/admin?token=ADMIN_TOKEN

---

## Pipeline détaillé

```
SCAN → TEST → SCORE → GENERATE → QUEUE
```

| Étape | Endpoint | Description |
|-------|----------|-------------|
| **SCAN** | `POST /api/prospect-scan` | Crée les prospects (CSV ou JSON) |
| **TEST** | `POST /api/ia-test/run` | Lance les tests multi-IA (OpenAI/Anthropic/Gemini) |
| **SCORE** | `POST /api/scoring/run` | Calcule éligibilité EMAIL_OK + score /10 |
| **GENERATE** | `POST /api/generate/campaign` | Génère audit HTML + email + script vidéo |
| **QUEUE** | Inclus dans GENERATE | Produit CSV dans `send_queue/` |
| **ASSETS** | `POST /api/prospect/{id}/assets` | Ajoute video_url + screenshot_url |
| **READY** | `POST /api/prospect/{id}/mark-ready` | Passe à READY_TO_SEND |

**Runner tout-en-un :** `POST /api/pipeline/run` — exécute tout en une commande.

---

## Curl exemples (ordre pipeline)

```bash
# --- SCAN ---
curl -X POST http://localhost:8001/api/prospect-scan \
  -H "Content-Type: application/json" \
  -d '{"city":"Paris","profession":"plombier","max_prospects":10}'

# --- TEST ---
curl -X POST http://localhost:8001/api/ia-test/run \
  -H "Content-Type: application/json" \
  -d '{"campaign_id":"<ID>","dry_run":false}'

# --- SCORE ---
curl -X POST http://localhost:8001/api/scoring/run \
  -H "Content-Type: application/json" \
  -d '{"campaign_id":"<ID>"}'

# --- GENERATE ---
curl -X POST http://localhost:8001/api/generate/campaign \
  -H "Content-Type: application/json" \
  -d '{"campaign_id":"<ID>"}'

# --- ASSETS ---
curl -X POST http://localhost:8001/api/prospect/<PID>/assets \
  -H "Content-Type: application/json" \
  -d '{"video_url":"https://...","screenshot_url":"https://..."}'

# --- MARK READY ---
curl -X POST http://localhost:8001/api/prospect/<PID>/mark-ready
```

---

## Structure

```
src/
├── models.py          # ORM SQLAlchemy + Pydantic + statuts
├── database.py        # SQLite, CRUD helpers
├── scan.py            # Import prospects (CSV/JSON/manual)
├── ia_test.py         # Multi-IA runner (OpenAI/Anthropic/Gemini)
├── scoring.py         # EMAIL_OK + score /10
├── generate.py        # Audit HTML, email, script vidéo, CSV queue
├── assets.py          # Gate vidéo/screenshot → READY_TO_SEND
├── scheduler.py       # APScheduler (Europe/Rome, runs auto)
└── api/
    ├── main.py        # FastAPI app port 8001
    └── routes/
        ├── campaign.py   # Campagnes + scan
        ├── ia_test.py    # Tests IA
        ├── scoring.py    # Scoring
        ├── generate.py   # Génération + landing page
        ├── pipeline.py   # Runner unique SCAN→QUEUE
        └── admin.py      # Admin UI HTML (token protégé)

data/           # SQLite DB (gitignorée)
send_queue/     # CSV + email.json + video_script.txt (gitignorés)
tests/          # pytest
```

---

## Règles métier clés

- **EMAIL_OK** = invisible sur ≥ 2/3 modèles ET ≥ 4/5 requêtes ET ≥ 1 concurrent stable
- **Score /10** : +4 invisible · +2 concurrents · +1 ads · +1 reviews · +1 website
- **Aucun envoi auto** — SendQueue = fichiers CSV/JSON à traiter manuellement
- **READY_TO_SEND** bloqué sans `video_url` + `screenshot_url`
- **Landing page** : GET `/couvreur?t=<token>` — HTML dark inline personnalisé

## Variables d'environnement

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Clé OpenAI (gpt-4o-mini) |
| `ANTHROPIC_API_KEY` | Clé Anthropic (claude-haiku) |
| `GEMINI_API_KEY` | Clé Google (gemini-1.5-flash) |
| `PROSPECTING_DB_PATH` | Chemin SQLite (défaut: `./data/presence_ia.db`) |
| `ADMIN_TOKEN` | Token protection admin UI |
| `BASE_URL` | URL publique pour landing pages |
| `SENDER_SIGNATURE` | Nom expéditeur emails |
