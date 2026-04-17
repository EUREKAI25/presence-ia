"""
Scheduler APScheduler — tâches périodiques PRESENCE_IA.

Jobs actifs :
- run_due_targets   : toutes les heures — prospection automatique Google Places
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler():
    """Démarre le scheduler et enregistre les jobs. Idempotent."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone="UTC")

    # Job 1 : prospection automatique (toutes les heures)
    _scheduler.add_job(
        _job_run_due_targets,
        trigger=IntervalTrigger(hours=1),
        id="run_due_targets",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Job 2 : retests mensuels (le 1er de chaque mois à 6h UTC)
    _scheduler.add_job(
        _job_monthly_retest,
        trigger=CronTrigger(day=1, hour=6, timezone="UTC"),
        id="monthly_retest",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Job 4 : polling IMAP réponses — toutes les 5 min
    _scheduler.add_job(
        _job_imap_reply_poll,
        trigger=IntervalTrigger(minutes=5),
        id="imap_reply_poll",
        replace_existing=True,
        misfire_grace_time=60,
    )

    # Job 5 : warming email — ~4h avec jitter ±45min (base 3h15 + jitter 5400s → entre 3h15 et 4h45)
    _scheduler.add_job(
        _job_warming,
        trigger=IntervalTrigger(hours=3, minutes=15, jitter=5400),
        id="email_warming",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Job 6 : qualification SIRENE automatique — Lun/Mer/Ven à 2h UTC
    _scheduler.add_job(
        _job_auto_qualify,
        trigger=CronTrigger(day_of_week="mon,wed,fri", hour=2, timezone="UTC"),
        id="auto_qualify",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Job 7 : enrichissement Google Places automatique — DÉSACTIVÉ (coût Gemini search)
    # _scheduler.add_job(
    #     _job_auto_enrich,
    #     trigger=IntervalTrigger(hours=1),
    #     id="auto_enrich",
    #     replace_existing=True,
    #     misfire_grace_time=300,
    # )

    # Job 8 : fourniture leads — vérification toutes les heures
    _scheduler.add_job(
        _job_provision_leads,
        trigger=IntervalTrigger(hours=1),
        id="provision_leads",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Job 9 : refresh IA — lun/jeu/dim à 7h30 UTC (AVANT outbound — paire active UNIQUEMENT)
    _scheduler.add_job(
        _job_refresh_ia,
        trigger=CronTrigger(day_of_week="mon,thu,sun", hour=7, minute=30, timezone="UTC"),
        id="refresh_ia",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Job 10 : monitoring clés API — toutes les 6h
    _scheduler.add_job(
        _job_check_api_keys,
        trigger=IntervalTrigger(hours=6),
        id="check_api_keys",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Job 11 : outbound — pile à chaque heure UTC, filtre interne sur LAUNCH_RUN_HOURS / WEEKDAY_RUN_HOURS
    _scheduler.add_job(
        _job_outbound,
        trigger=CronTrigger(minute=0),
        id="outbound",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Job 11b : relance J+1 — toutes les heures, 15 min après l'outbound
    _scheduler.add_job(
        _job_followup,
        trigger=CronTrigger(minute=15),
        id="followup",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Job 12 : sync Brevo — chaque nuit à 3h UTC (sécurité en complément du webhook)
    _scheduler.add_job(
        _job_sync_brevo,
        trigger=CronTrigger(hour=3, minute=0, timezone="UTC"),
        id="sync_brevo",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    log.info("Scheduler démarré — %d job(s)", len(_scheduler.get_jobs()))


def get_jobs_status() -> list[dict]:
    """Retourne le statut des jobs principaux (next_run depuis APScheduler)."""
    JOB_LABELS = {
        "run_due_targets": ("Prospection Google Places", "toutes les heures"),
        "auto_enrich":     ("Enrichissement SIRENE→Places", "toutes les heures"),
        "provision_leads": ("Provisioning leads", "toutes les heures"),
        "outbound":        ("Envoi emails outbound", "tous les jours à 9h UTC"),
        "refresh_ia":      ("Refresh IA (paires actives)", "Lun/Jeu/Dim 9h30 UTC"),
        "auto_qualify":    ("Qualification SIRENE", "Lun/Mer/Ven 2h UTC"),
        "email_warming":   ("Email warming", "~toutes les 4h"),
        "check_api_keys":  ("Vérif. clés API", "toutes les 6h"),
    }
    if not _scheduler or not _scheduler.running:
        return [{"id": k, "label": v[0], "freq": v[1], "next_run": None, "running": False}
                for k, v in JOB_LABELS.items()]
    result = []
    for job_id, (label, freq) in JOB_LABELS.items():
        job = _scheduler.get_job(job_id)
        result.append({
            "id": job_id,
            "label": label,
            "freq": freq,
            "next_run": job.next_run_time if job else None,
            "running": True,
        })
    return result


def _job_check_api_keys():
    """Vérifie que les clés OpenAI, Gemini et Anthropic sont valides.
    Envoie une alerte email via Brevo si l'une d'elles retourne 401/403.
    """
    import os
    import requests as _req

    CHECKS = [
        ("OpenAI",    "OPENAI_API_KEY",    "https://api.openai.com/v1/models",
         lambda k: {"Authorization": f"Bearer {k}"}),
        ("Gemini",    "GEMINI_API_KEY",    None,  None),   # URL construite dynamiquement
        ("Anthropic", "ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/models",
         lambda k: {"x-api-key": k, "anthropic-version": "2023-06-01"}),
    ]

    failed = []
    for name, env_var, url, headers_fn in CHECKS:
        key = os.getenv(env_var, "")
        if not key:
            failed.append((name, "clé absente dans .env"))
            continue
        try:
            if name == "Gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
                headers = {}
            else:
                headers = headers_fn(key)
            r = _req.get(url, headers=headers, timeout=8)
            if r.status_code in (401, 403):
                failed.append((name, f"HTTP {r.status_code} — clé invalide ou expirée"))
            else:
                log.debug("check_api_keys: %s OK (%d)", name, r.status_code)
        except Exception as e:
            failed.append((name, f"erreur réseau : {e}"))

    if not failed:
        log.info("check_api_keys: toutes les clés sont valides")
        return

    # ── Envoi alerte Brevo ────────────────────────────────────────────────────
    brevo_key   = os.getenv("BREVO_API_KEY", "")
    admin_email = os.getenv("ADMIN_ALERT_EMAIL") or os.getenv("ADMIN_EMAIL", "contact@presence-ia.com")
    admin_token = os.getenv("ADMIN_TOKEN", "changeme")

    names_str = ", ".join(n for n, _ in failed)
    log.warning("check_api_keys: clés invalides — %s", names_str)

    rows_html = "".join(
        f'<tr><td style="padding:8px 12px;font-weight:600;color:#dc2626">{n}</td>'
        f'<td style="padding:8px 12px;color:#555">{msg}</td></tr>'
        for n, msg in failed
    )
    links_html = (
        '<ul style="margin:12px 0;padding-left:20px;line-height:2">'
        '<li><a href="https://platform.openai.com/api-keys">Renouveler clé OpenAI</a></li>'
        '<li><a href="https://aistudio.google.com/app/apikey">Renouveler clé Gemini</a></li>'
        '<li><a href="https://console.anthropic.com/account/keys">Renouveler clé Anthropic</a></li>'
        '</ul>'
    )
    body = f"""
    <div style="font-family:sans-serif;max-width:600px">
      <h2 style="color:#dc2626">🔴 Clés API invalides — PRESENCE IA</h2>
      <p>Les clés suivantes ne fonctionnent plus et bloquent le refresh IA de la landing :</p>
      <table style="border-collapse:collapse;width:100%;margin:12px 0">
        <thead><tr style="background:#fef2f2">
          <th style="text-align:left;padding:8px 12px;font-size:12px;color:#9ca3af">SERVICE</th>
          <th style="text-align:left;padding:8px 12px;font-size:12px;color:#9ca3af">PROBLÈME</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p>Renouvelle les clés ici :</p>
      {links_html}
      <p style="margin-top:20px">
        <a href="https://presence-ia.com/admin?token={admin_token}"
           style="background:#e94560;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none">
          Ouvrir l'admin →
        </a>
      </p>
    </div>
    """

    if not brevo_key:
        log.warning("check_api_keys: BREVO_API_KEY absent — alerte email non envoyée")
        return

    try:
        _req.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": brevo_key, "Content-Type": "application/json"},
            json={
                "sender":      {"name": "Présence IA — Monitoring", "email": "contact@presence-ia.com"},
                "to":          [{"email": admin_email}],
                "subject":     f"🔴 Clés API invalides : {names_str}",
                "htmlContent": body,
            },
            timeout=8,
        )
        log.info("check_api_keys: alerte envoyée à %s", admin_email)
    except Exception as e:
        log.warning("check_api_keys: échec envoi alerte — %s", e)


def _job_sync_brevo():
    """Synchronise les événements Brevo (email + SMS) vers v3_prospects — nuit à 3h UTC."""
    try:
        from .api.services.brevo_sync import sync_brevo_events
        result = sync_brevo_events(days=2)  # 2 jours suffisent en cron quotidien
        log.info("sync_brevo: %s", result)
    except Exception as e:
        log.error("sync_brevo: erreur — %s", e)


def stop_scheduler():
    """Arrête proprement le scheduler (appelé au shutdown)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler arrêté")


def scheduler_status() -> list[dict]:
    """Retourne l'état des jobs pour la page /admin/scheduler."""
    if not _scheduler:
        return [{"id": "—", "next_run": "non démarré", "trigger": "—"}]
    jobs = []
    for j in _scheduler.get_jobs():
        next_run = str(j.next_run_time) if j.next_run_time else "—"
        jobs.append({"id": j.id, "next_run": next_run, "trigger": str(j.trigger)})
    return jobs or [{"id": "—", "next_run": "aucun job", "trigger": "—"}]


# ── Implémentation des jobs ────────────────────────────────────────────────

def _job_monthly_retest():
    """Lance les retests mensuels pour tous les prospects sous contrat (paid=True)."""
    try:
        from .database import SessionLocal
        from .models import ProspectDB
        from .livrables.monthly_retest import run_retest
        db = SessionLocal()
        try:
            prospects = db.query(ProspectDB).filter_by(paid=True).all()
            log.info("monthly_retest : %d prospect(s) à retester", len(prospects))
            for p in prospects:
                try:
                    result = run_retest(db, p.prospect_id)
                    if result["success"]:
                        log.info("Retest OK — %s", p.name)
                    else:
                        log.warning("Retest KO — %s : %s", p.name, result.get("error"))
                except Exception as e:
                    log.error("Retest erreur — %s : %s", p.name, e)
        finally:
            db.close()
    except Exception as e:
        log.error("_job_monthly_retest : %s", e)


_LEGAL_SFX = None  # initialisé ci-dessous pour éviter la recompilation


def _norm_cited(s: str) -> str:
    import re, unicodedata
    global _LEGAL_SFX
    if _LEGAL_SFX is None:
        _LEGAL_SFX = re.compile(
            r'\b(sarl|sas|sasu|sa|sci|snc|eurl|scp|scop|scic|gie|ei|auto[- ]entrepreneur|'
            r'and co|et (cie|fils|freres?|associes?)|groupe|holding)\b'
        )
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = _LEGAL_SFX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _extract_cited_names(ia_results: list) -> dict:
    """Extrait les noms d'entreprises cités dans les réponses IA.
    Retourne {name_raw: [model1, model2, ...]}
    """
    import re

    cited = {}  # name_raw → set(models)
    for entry in (ia_results or []):
        model    = entry.get("model", "?")
        response = entry.get("response", "")
        # Markdown links : [Nom](url)
        for m in re.finditer(r'\[([^\]]{3,60})\]\(http', response):
            raw = m.group(1).strip()
            if raw and not raw.startswith("http"):
                cited.setdefault(raw, set()).add(model)
        # Lignes débutant par - ou * ou chiffre. (listes)
        for m in re.finditer(r'^[-*\d\.]+\s+\*{0,2}([A-ZÀÂÉÈÊËÏÎÔÙÛÜ][^:\n*]{2,60})\*{0,2}', response, re.MULTILINE):
            raw = m.group(1).strip().rstrip(".,:")
            if len(raw) > 3:
                cited.setdefault(raw, set()).add(model)
    return {k: list(v) for k, v in cited.items()}


def _upsert_cited_companies(db, profession: str, city: str, cited: dict):
    """Upsert des entreprises citées dans ia_cited_companies."""
    import json
    from .models import IaCitedCompanyDB

    prof_norm = profession.lower().strip()
    city_norm = city.lower().strip()
    for name_raw, models in cited.items():
        name_norm = _norm_cited(name_raw)
        if not name_norm:
            continue
        pk = f"{prof_norm}|{city_norm}|{name_norm}"
        existing = db.get(IaCitedCompanyDB, pk)
        if existing:
            existing_models = set(json.loads(existing.models))
            existing.models   = json.dumps(sorted(existing_models | set(models)), ensure_ascii=False)
            existing.last_seen = datetime.utcnow()
        else:
            db.add(IaCitedCompanyDB(
                id         = pk,
                profession = prof_norm,
                city       = city_norm,
                name_raw   = name_raw,
                name_norm  = name_norm,
                models     = json.dumps(sorted(models), ensure_ascii=False),
                first_seen = datetime.utcnow(),
                last_seen  = datetime.utcnow(),
            ))
    db.commit()


def _job_refresh_ia():
    """Relance les tests IA (ChatGPT + Gemini + Claude) pour la paire active UNIQUEMENT.
    lun/jeu/dim à 7h30 UTC. 1 run (9 requêtes max) par exécution.
    Alimente ia_cited_companies + ia_results sur tous les prospects de la paire.
    """
    try:
        import time as _time, json as _json
        from .database import SessionLocal
        from .api.routes.v3 import _run_ia_test, V3ProspectDB
        from .active_pair import get_active_pair

        # PAIRE ACTIVE UNIQUEMENT — jamais toutes les paires
        active = get_active_pair()
        if not active:
            log.info("refresh_ia : aucune paire active — skip")
            return

        # RÈGLE ABSOLUE : uniquement les paires issues de get_active_pair()
        # Jamais de requête DB sur v3_prospects pour construire cette liste
        active_pairs = [(active["city"], active["profession"])]
        log.info("refresh_ia : paire active = %s / %s", active["city"], active["profession"])
        for city, profession in active_pairs:
            try:
                ia_data = _run_ia_test(profession, city)
                if not ia_data or not ia_data.get("results"):
                    continue
                ia_results_json = _json.dumps(ia_data["results"], ensure_ascii=False)
                cited = _extract_cited_names(ia_data["results"])
                with SessionLocal() as db:
                    for p in db.query(V3ProspectDB).filter_by(city=city, profession=profession).all():
                        p.ia_prompt    = ia_data.get("prompt")
                        p.ia_response  = ia_data.get("response")
                        p.ia_model     = ia_data.get("model")
                        p.ia_tested_at = ia_data.get("tested_at")
                        p.ia_results   = ia_results_json
                    db.commit()
                    _upsert_cited_companies(db, profession, city, cited)
                log.info("refresh_ia OK: %s / %s — %d cités extraits", profession, city, len(cited))
            except Exception as e:
                log.error("refresh_ia %s/%s: %s", profession, city, e)
            _time.sleep(3)
    except Exception as e:
        log.error("_job_refresh_ia: %s", e)



def _send_reply_alert(prospect_name: str, prospect_email: str, snippet: str, channel: str = "email"):
    """
    Envoie une alerte email à l'admin quand un prospect répond.
    Utilise directement l'API Brevo (pas de dépendance circulaire).
    Requiert : BREVO_API_KEY, ADMIN_EMAIL (ou ADMIN_ALERT_EMAIL) dans l'env.
    """
    try:
        import os, requests as _req
        key = os.getenv("BREVO_API_KEY", "")
        admin_email = os.getenv("ADMIN_ALERT_EMAIL") or os.getenv("ADMIN_EMAIL", "contact@presence-ia.com")
        if not key:
            log.warning("BREVO_API_KEY absent — alerte non envoyée pour %s", prospect_name)
            return

        channel_label = "email" if channel == "email" else "SMS"
        subject = f"🔔 Réponse {channel_label} — {prospect_name}"
        body = (
            f"<strong>{prospect_name}</strong> ({prospect_email}) a répondu à votre {channel_label}.<br><br>"
            f"<blockquote style='border-left:3px solid #6366f1;padding:8px 16px;color:#555'>"
            f"{snippet[:500]}"
            f"</blockquote><br>"
            f"<a href='https://presence-ia.com/admin/crm?token={os.getenv('ADMIN_TOKEN','changeme')}' "
            f"style='background:#6366f1;color:#fff;padding:8px 16px;border-radius:4px;text-decoration:none'>"
            f"Voir dans le CRM →</a>"
        )

        _req.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": key, "Content-Type": "application/json"},
            json={
                "sender":  {"name": "Présence IA", "email": "contact@presence-ia.com"},
                "to":      [{"email": admin_email}],
                "subject": subject,
                "htmlContent": body,
            },
            timeout=8,
        )
        log.info("Alerte réponse envoyée à %s pour %s", admin_email, prospect_name)
    except Exception as e:
        log.warning("_send_reply_alert : %s", e)


def _job_imap_reply_poll():
    """
    Polling IMAP toutes les 5 min — détecte les réponses des prospects.

    Variables d'env requises :
      IMAP_HOST     ex: imap.gmail.com
      IMAP_PORT     ex: 993
      IMAP_USER     ex: contact@presence-ia.com
      IMAP_PASSWORD mot de passe ou app password
      IMAP_FOLDER   dossier à surveiller (défaut: INBOX)

    Logique :
      1. Cherche les emails UNSEEN dans INBOX
      2. Pour chaque email, extrait l'adresse "From"
      3. Cherche le prospect dans V3ProspectDB par email
      4. Si trouvé : marque reply_status=positive dans ProspectDeliveryDB
      5. Envoie alerte email à l'admin
      6. Marque l'email comme SEEN pour ne pas le retraiter
    """
    import os, imaplib, email as _email
    from email.header import decode_header

    host  = os.getenv("IMAP_HOST", "")
    port  = int(os.getenv("IMAP_PORT", "993"))
    user  = os.getenv("IMAP_USER", "")
    pwd   = os.getenv("IMAP_PASSWORD", "")
    folder = os.getenv("IMAP_FOLDER", "INBOX")

    if not (host and user and pwd):
        return  # non configuré → silencieux

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, pwd)
        conn.select(folder)

        # Chercher emails non lus
        _, data = conn.search(None, "UNSEEN")
        if not data or not data[0]:
            conn.logout()
            return

        uids = data[0].split()
        if not uids:
            conn.logout()
            return

        log.info("IMAP poll : %d email(s) non lus", len(uids))

        from .database import SessionLocal
        from .models import V3ProspectDB

        try:
            from marketing_module.database import SessionLocal as MktSession, db_update_delivery
            from marketing_module.models import ProspectDeliveryDB, ReplyStatus
            _mkt_available = True
        except Exception:
            _mkt_available = False

        for uid in uids:
            try:
                _, msg_data = conn.fetch(uid, "(RFC822)")
                raw = msg_data[0][1]
                msg = _email.message_from_bytes(raw)

                # Extraire l'adresse From
                from_raw = msg.get("From", "")
                # Décoder si encodé
                parts = decode_header(from_raw)
                from_decoded = ""
                for part, enc in parts:
                    if isinstance(part, bytes):
                        from_decoded += part.decode(enc or "utf-8", errors="replace")
                    else:
                        from_decoded += part
                # Extraire email entre < >
                import re
                m = re.search(r"<([^>]+)>", from_decoded)
                from_email = m.group(1).lower() if m else from_decoded.strip().lower()

                if not from_email or "@" not in from_email:
                    # Marquer comme lu quand même pour éviter boucle
                    conn.store(uid, "+FLAGS", "\\Seen")
                    continue

                # Chercher prospect par email
                with SessionLocal() as db:
                    prospect = db.query(V3ProspectDB).filter(
                        V3ProspectDB.email == from_email
                    ).first()

                if not prospect:
                    # Pas un prospect connu — laisser non lu, ne pas alerter
                    log.debug("IMAP : email de %s — pas un prospect connu", from_email)
                    continue

                # Extraire snippet du corps
                snippet = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                snippet = part.get_payload(decode=True).decode("utf-8", errors="replace")[:300]
                            except Exception:
                                pass
                            break
                else:
                    try:
                        snippet = msg.get_payload(decode=True).decode("utf-8", errors="replace")[:300]
                    except Exception:
                        pass

                log.info("IMAP : réponse détectée de %s (%s)", prospect.name, from_email)

                # Mise à jour CRM
                if _mkt_available:
                    try:
                        with MktSession() as mdb:
                            delivery = (
                                mdb.query(ProspectDeliveryDB)
                                .filter_by(project_id="presence-ia", prospect_id=prospect.token)
                                .order_by(ProspectDeliveryDB.created_at.desc())
                                .first()
                            )
                            if delivery and delivery.reply_status == ReplyStatus.none:
                                db_update_delivery(mdb, delivery.id, {
                                    "reply_status": ReplyStatus.positive
                                })
                    except Exception as e:
                        log.warning("IMAP CRM update : %s", e)

                # Alerte admin
                _send_reply_alert(
                    prospect_name=prospect.name or from_email,
                    prospect_email=from_email,
                    snippet=snippet,
                    channel="email",
                )

                # Marquer comme lu pour ne pas retraiter
                conn.store(uid, "+FLAGS", "\\Seen")

            except Exception as e:
                log.error("IMAP traitement email uid=%s : %s", uid, e)

        conn.logout()

    except imaplib.IMAP4.error as e:
        log.error("IMAP connexion : %s", e)
    except Exception as e:
        log.error("_job_imap_reply_poll : %s", e)


def _job_run_due_targets():
    """
    Chantier C — Exécute la prospection pour la paire active uniquement.
    Sélectionne automatiquement la meilleure paire si aucune n'est définie.
    Vérifie la saturation après chaque exécution.
    """
    try:
        from datetime import datetime, timedelta
        from .database import SessionLocal
        from .active_pair import get_active_pair, select_next_pair, check_saturation
        from .models import ProspectionTargetDB
        from .api.routes.prospection_admin import _run_prospection, _FREQ_DAYS

        db = SessionLocal()
        try:
            # Obtenir ou sélectionner la paire active
            state = get_active_pair() or select_next_pair(db)
            if not state:
                log.info("_job_run_due_targets: aucune paire disponible")
                return

            city, profession = state["city"], state["profession"]
            t = db.query(ProspectionTargetDB).filter_by(
                city=city, profession=profession, active=True,
            ).first()
            if not t:
                log.warning("_job_run_due_targets: paire active %s/%s introuvable",
                            profession, city)
                return

            # Vérifier fréquence
            delta_days = _FREQ_DAYS.get(t.frequency, 7)
            if t.last_run and (datetime.utcnow() - t.last_run) < timedelta(days=delta_days):
                log.info("_job_run_due_targets: %s/%s — pas encore dû", profession, city)
                return

            res = _run_prospection(db, t)
            log.info("_job_run_due_targets: %s/%s — %d prospects importés",
                     profession, city, res["imported"])

            # Vérifier saturation après prospection
            check_saturation(db)
        finally:
            db.close()
    except Exception as e:
        log.error("_job_run_due_targets : %s", e)


_WARMING_SENDERS = [
    "contact@presence-ia.online", "hello@presence-ia.online", "bonjour@presence-ia.online",
    "info@presence-ia.online", "equipe@presence-ia.online",
    "contact@presence-ia.info", "hello@presence-ia.info", "bonjour@presence-ia.info",
    "info@presence-ia.info", "equipe@presence-ia.info",
    "contact@presence-ia.cloud", "hello@presence-ia.cloud", "bonjour@presence-ia.cloud",
    "info@presence-ia.cloud", "equipe@presence-ia.cloud",
    "contact@presence-ia.site", "hello@presence-ia.site", "bonjour@presence-ia.site",
    "info@presence-ia.site", "equipe@presence-ia.site",
    "contact@presence-ia.website", "hello@presence-ia.website", "bonjour@presence-ia.website",
    "info@presence-ia.website", "equipe@presence-ia.website",
]

_WARMING_RECEIVERS = [
    "bot-free@presence-ia.com",
    "bot-paid@presence-ia.com",
]

_WARMING_SUBJECTS = [
    "Bonjour, une question rapide",
    "Retour sur notre échange",
    "Quelques informations utiles",
    "Suite à notre conversation",
    "Point rapide",
    "Question concernant votre activité",
    "Votre présence en ligne",
    "Un point rapide",
    "Suivi de notre discussion",
    "Pour info",
    "À votre attention",
    "Juste un mot",
    "Pensé à vous",
    "Rapide question",
    "En passant",
    "Petite mise à jour",
    "Votre dossier",
    "Nouvelles informations",
    "Pour faire suite",
    "Confirmation rapide",
]

_WARMING_BODIES = [
    "Bonjour,\n\nJ'espère que vous allez bien. Je voulais vous contacter concernant votre visibilité en ligne.\n\nN'hésitez pas à me répondre si vous souhaitez en savoir plus.\n\nCordialement",
    "Bonjour,\n\nFaisant suite à notre échange précédent, je me permets de vous recontacter.\n\nJe reste disponible pour toute question.\n\nBonne journée",
    "Bonjour,\n\nJe vous fais parvenir quelques informations qui pourraient vous intéresser concernant votre activité.\n\nÀ votre disposition,\nCordialement",
    "Bonjour,\n\nUne question rapide : avez-vous eu l'occasion de consulter les informations que je vous ai transmises ?\n\nJe reste à votre disposition.\n\nCordialement",
    "Bonjour,\n\nJe me permets de revenir vers vous pour faire un point rapide sur nos échanges.\n\nBien à vous",
    "Bonjour,\n\nJe souhaitais simplement prendre de vos nouvelles et voir si vous aviez des questions.\n\nBonne journée à vous",
    "Bonjour,\n\nTout d'abord merci pour notre échange. Je voulais vous confirmer que j'ai bien pris note de votre situation.\n\nCordialement",
    "Bonjour,\n\nJe reviens vers vous comme promis. N'hésitez pas si vous avez besoin d'un complément d'information.\n\nBien cordialement",
    "Bonjour,\n\nJ'espère que cette semaine se passe bien pour vous. Juste un mot pour rester en contact.\n\nBonne continuation",
    "Bonjour,\n\nPetite prise de contact pour faire suite à notre dernière discussion. Je reste joignable.\n\nBien à vous",
    "Bonjour,\n\nJe me permets de vous envoyer ce message pour vous tenir informé de l'avancement de votre dossier.\n\nCordialement",
    "Bonjour,\n\nAvez-vous eu le temps de réfléchir à notre proposition ? Je suis disponible pour en discuter.\n\nBien cordialement",
]

# Jour de démarrage warming pour calculer le ramp-up
import datetime as _dt
_WARMING_START = _dt.date(2026, 3, 20)


_WARMING_FOLDER = "Warming"


def _imap_ensure_folder(conn, folder: str) -> bool:
    """Crée le dossier IMAP s'il n'existe pas encore."""
    try:
        ok, _ = conn.select(folder)
        conn.select("INBOX")
        return ok == "OK"
    except Exception:
        pass
    try:
        conn.create(folder)
        conn.select("INBOX")
        return True
    except Exception as e:
        log.debug("imap create folder %s: %s", folder, e)
        return False


def _imap_move(conn, uids: list, dest: str):
    """Copie les UIDs vers dest puis les supprime de l'inbox."""
    if not uids:
        return
    uid_str = ",".join(u.decode() if isinstance(u, bytes) else str(u) for u in uids)
    try:
        conn.copy(uid_str, dest)
        conn.store(uid_str, "+FLAGS", "\\Deleted")
        conn.expunge()
    except Exception as e:
        log.debug("imap_move → %s: %s", dest, e)


def _warming_day_cap() -> int:
    """Nombre d'emails par session selon le jour de warming (ramp-up progressif)."""
    day = (_dt.datetime.utcnow().date() - _WARMING_START).days + 1
    if day <= 3:   return 2
    if day <= 7:   return 4
    if day <= 14:  return 6
    if day <= 21:  return 8
    return 10  # plateau


def _job_warming():
    """
    Warming email — toutes les 4h.
    Envoie des emails depuis les 25 adresses Brevo vers les boîtes IMAP réelles,
    puis marque les emails reçus comme lus.
    Ramp-up progressif sur 21 jours.
    """
    import os, random, imaplib, smtplib, ssl
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from datetime import datetime

    try:
        brevo_key = os.getenv("BREVO_API_KEY", "")
        if not brevo_key:
            log.warning("warming: BREVO_API_KEY absent")
            return

        cap = _warming_day_cap()
        log.info("warming: session démarrée — cap=%d emails/sender", cap)

        # Sélectionner un sous-ensemble aléatoire de senders pour cette session
        senders = random.sample(_WARMING_SENDERS, min(cap * 2, len(_WARMING_SENDERS)))
        sent_total = 0

        for sender in senders:
            receiver = random.choice(_WARMING_RECEIVERS)
            subject = random.choice(_WARMING_SUBJECTS)
            body = random.choice(_WARMING_BODIES)

            # Nom d'affichage depuis l'adresse
            display = sender.split("@")[0].capitalize().replace("-", " ")
            domain = sender.split("@")[1]

            try:
                import requests as _req
                resp = _req.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": brevo_key, "Content-Type": "application/json"},
                    json={
                        "sender":      {"name": display, "email": sender},
                        "to":          [{"email": receiver}],
                        "subject":     subject,
                        "textContent": body,
                        "headers":     {"X-Warming": "1"},
                    },
                    timeout=10,
                )
                if resp.status_code in (200, 201, 202):
                    sent_total += 1
                    log.debug("warming: %s → %s ✓", sender, receiver)
                else:
                    log.warning("warming: %s → %s HTTP %s", sender, receiver, resp.status_code)
            except Exception as e:
                log.warning("warming send %s: %s", sender, e)

        log.info("warming: %d emails envoyés", sent_total)

        # Marquer les emails reçus comme lus dans les 2 boîtes IMAP
        imap_host = os.getenv("WARMING_IMAP_HOST", "imap.ionos.fr")
        imap_port = int(os.getenv("WARMING_IMAP_PORT", "993"))
        mailboxes = [
            (os.getenv("WARMING_MAILBOX_1", ""), os.getenv("WARMING_MAILBOX_1_PWD", "")),
            (os.getenv("WARMING_MAILBOX_2", ""), os.getenv("WARMING_MAILBOX_2_PWD", "")),
        ]

        # Réponse 1 — bot répond au sender (ton formel, parfois emoji)
        _WARMING_REPLIES = [
            "Bonjour,\n\nMerci pour votre message, je l'ai bien reçu.\n\nJe vous recontacte dès que possible.\n\nCordialement",
            "Bonjour,\n\nBien reçu, merci. 👍\n\nJe reviendrai vers vous prochainement.\n\nBonne journée",
            "Bonjour,\n\nMerci de votre retour. Je prends note et vous réponds dans les meilleurs délais.\n\nCordialement",
            "Bonjour,\n\nMessage bien reçu ! Je vous confirme que je traiterai votre demande très prochainement.\n\nBien à vous",
            "Bonjour,\n\nMerci pour ces informations. Je reviens vers vous rapidement. 🙂\n\nCordialement",
            "Bonjour,\n\nBien noté, merci de votre message. Je vous tiens informé.\n\nBonne journée ☀️",
            "Bonjour,\n\nReçu 5/5. Je transfère votre message aux bonnes personnes.\n\nCordialement",
            "Bonjour,\n\nMerci, c'est noté ! On se recontacte très prochainement.\n\nBien à vous 👋",
            "Bonjour,\n\nMerci pour votre message. Je m'en occupe dès que possible.\n\nBonne journée",
            "Bonjour,\n\nBien reçu ! Je vous réponds dans les meilleurs délais. ✅\n\nCordialement",
        ]

        # Réponse 2 — sender relance (ton plus court, ~40% des cas)
        _WARMING_FOLLOWUPS = [
            "Merci pour votre réponse rapide.\n\nJe reste disponible si vous avez des questions.\n\nBonne journée",
            "Parfait, merci ! 👍\n\nN'hésitez pas à me contacter si besoin.\n\nCordialement",
            "Très bien, j'attends de vos nouvelles.\n\nBonne continuation 🙂",
            "Merci ! À bientôt.",
            "Super, on fait comme ça.\n\nBonne journée à vous ☀️",
            "D'accord, merci pour le retour.\n\nCordialement",
            "OK, noté. Merci ! 👋",
            "Bien reçu, à très vite.",
            "Parfait ! Bonne journée.",
            "Merci pour ce retour rapide. 🙏\n\nÀ bientôt",
        ]

        import re as _re
        import email as _email_lib
        import requests as _req2

        def _extract_reply_addr(from_field: str) -> str:
            m = _re.search(r"<([^>]+)>", from_field)
            return m.group(1) if m else from_field.strip()

        def _send_warming_via_brevo(sender_email: str, to_email: str, subject: str,
                                    body: str, extra_headers: dict) -> bool:
            display = sender_email.split("@")[0].capitalize().replace("-", " ")
            try:
                r = _req2.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": brevo_key, "Content-Type": "application/json"},
                    json={
                        "sender":      {"name": display, "email": sender_email},
                        "to":          [{"email": to_email}],
                        "subject":     subject,
                        "textContent": body,
                        "headers":     extra_headers,
                    },
                    timeout=8,
                )
                return r.status_code in (200, 201, 202)
            except Exception:
                return False

        replied_total = 0
        followup_total = 0

        for email_addr, pwd in mailboxes:
            if not email_addr or not pwd:
                continue
            try:
                conn = imaplib.IMAP4_SSL(imap_host, imap_port)
                conn.login(email_addr, pwd)
                conn.select("INBOX")
                _imap_ensure_folder(conn, _WARMING_FOLDER)

                # ── Passe 1 : bot répond aux emails X-Warming (envois initiaux) ──
                _, data = conn.search(None, '(UNSEEN HEADER X-Warming 1)')
                if data and data[0]:
                    uids = data[0].split()
                    for uid in uids:
                        try:
                            _, msg_data = conn.fetch(uid, "(RFC822)")
                            msg = _email_lib.message_from_bytes(msg_data[0][1])
                            reply_to = _extract_reply_addr(msg.get("From", ""))
                            orig_subj = msg.get("Subject", "message")
                            subject   = orig_subj if orig_subj.startswith("Re:") else f"Re: {orig_subj}"
                            if reply_to and "@" in reply_to:
                                # Délai humain : entre 2 et 18 min avant de répondre
                                import time as _time
                                _time.sleep(random.randint(120, 1080))
                                ok = _send_warming_via_brevo(
                                    email_addr, reply_to, subject,
                                    random.choice(_WARMING_REPLIES),
                                    {"X-Warming-Reply": "1"},
                                )
                                if ok:
                                    replied_total += 1
                        except Exception as e:
                            log.debug("warming reply uid=%s: %s", uid, e)
                    conn.store(",".join(u.decode() for u in uids), "+FLAGS", "\\Seen")
                    _imap_move(conn, uids, _WARMING_FOLDER)

                # ── Passe 2 : sender relance (40% des échanges, 2e aller-retour) ──
                _, data2 = conn.search(None, '(UNSEEN HEADER X-Warming-Reply 1)')
                if data2 and data2[0]:
                    uids2 = data2[0].split()
                    for uid in uids2:
                        try:
                            _, msg_data = conn.fetch(uid, "(RFC822)")
                            msg = _email_lib.message_from_bytes(msg_data[0][1])
                            reply_to = _extract_reply_addr(msg.get("From", ""))
                            orig_subj = msg.get("Subject", "Re: message")
                            subject   = orig_subj if orig_subj.startswith("Re:") else f"Re: {orig_subj}"
                            # 40% de chance de relancer (3e message de la chaîne)
                            if reply_to and "@" in reply_to and random.random() < 0.40:
                                # Délai humain : entre 5 et 35 min avant la relance
                                import time as _time
                                _time.sleep(random.randint(300, 2100))
                                sender_followup = random.choice(_WARMING_SENDERS)
                                ok = _send_warming_via_brevo(
                                    sender_followup, reply_to, subject,
                                    random.choice(_WARMING_FOLLOWUPS),
                                    {"X-Warming-Followup": "1"},
                                )
                                if ok:
                                    followup_total += 1
                        except Exception as e:
                            log.debug("warming followup uid=%s: %s", uid, e)
                    conn.store(",".join(u.decode() for u in uids2), "+FLAGS", "\\Seen")
                    _imap_move(conn, uids2, _WARMING_FOLDER)

                # ── Passe 3 : archiver les X-Warming-Followup reçus ──
                _, data3 = conn.search(None, '(HEADER X-Warming-Followup 1)')
                if data3 and data3[0]:
                    uids3 = data3[0].split()
                    conn.store(",".join(u.decode() for u in uids3), "+FLAGS", "\\Seen")
                    _imap_move(conn, uids3, _WARMING_FOLDER)

                conn.logout()
                log.info("warming IMAP %s — réponses: %d, relances: %d",
                         email_addr, replied_total, followup_total)
            except Exception as e:
                log.warning("warming IMAP %s: %s", email_addr, e)

        if replied_total or followup_total:
            log.info("warming: %d réponses + %d relances envoyées", replied_total, followup_total)

    except Exception as e:
        log.error("_job_warming: %s", e)


def _job_auto_qualify():
    """Qualification SIRENE automatique — Lun/Mer/Ven à 2h UTC."""
    try:
        import threading
        t = threading.Thread(target=run_sirene_qualify, daemon=True)
        t.start()
        log.info("_job_auto_qualify : thread SIRENE démarré")
    except Exception as e:
        log.error("_job_auto_qualify : %s", e)


def _job_auto_enrich(force: bool = False):
    """
    Enrichissement automatique (Google Places) : traite N suspects non encore enrichis,
    par ordre décroissant de score segment, pour toutes les professions actives.
    Si force=True : ignore active/jour/heure.
    """
    try:
        from datetime import datetime
        from .database import SessionLocal
        from .models import EnrichmentConfigDB, ProfessionDB, SireneSuspectDB, SireneSegmentDB

        db = SessionLocal()
        try:
            cfg = db.get(EnrichmentConfigDB, "default")
            if not cfg:
                cfg = EnrichmentConfigDB(id="default")
                db.add(cfg)
                db.commit()
                db.refresh(cfg)

            if not force:
                if not cfg.active:
                    return
                now = datetime.utcnow()
                configured_days = [d.strip() for d in (cfg.days or "").split(",") if d.strip()]
                if configured_days and str(now.weekday()) not in configured_days:
                    return
                if cfg.hour_utc is not None and cfg.hour_utc >= 0 and now.hour != cfg.hour_utc:
                    return
                if cfg.last_run and (now - cfg.last_run).total_seconds() < 3600:
                    return

            now = datetime.utcnow()
            remaining = cfg.suspects_per_run
            log.info("auto_enrich: démarrage — %d suspects à enrichir", remaining)

            # Professions actives, ordonnées par score moyen de leurs segments DESC
            active_profs = db.query(ProfessionDB).filter_by(actif=True).all()
            prof_ids = [p.id for p in active_profs]

        finally:
            db.close()

        if not prof_ids:
            log.info("auto_enrich: aucune profession active")
            return

        # Enrichir via le pipeline existant (phase 2 uniquement)
        import os, json
        from .api.routes.leads_runner import _phase2_enrich, _STATE, _LOCK

        # Si un pipeline manuel tourne déjà, on ne démarre pas
        with _LOCK:
            if _STATE.get("running"):
                log.info("auto_enrich: pipeline manuel en cours, skip")
                return
            _STATE.update({
                "running": True, "phase": "auto_enrich", "stop_requested": False,
                "profession_id": "auto", "qty": remaining,
                "suspects": 0, "segments_done": 0, "segments_total": 0,
                "processed": 0, "enriched": 0, "contacts": 0,
                "results": [], "finished_at": None, "error": None,
            })

        total_enriched = 0
        try:
            db2 = SessionLocal()
            try:
                # Segments par score DESC pour prioriser les meilleures professions/depts
                segs = (
                    db2.query(SireneSegmentDB)
                    .filter(
                        SireneSegmentDB.profession_id.in_(prof_ids),
                        SireneSegmentDB.status == "done",
                    )
                    .order_by(SireneSegmentDB.score.desc())
                    .all()
                )
                ordered_prof_ids = list(dict.fromkeys(s.profession_id for s in segs))
            finally:
                db2.close()

            for prof_id in ordered_prof_ids:
                if remaining <= 0:
                    break
                with _LOCK:
                    _STATE["profession_id"] = prof_id
                    _STATE["qty"] = remaining
                _phase2_enrich(prof_id, remaining, None)
                with _LOCK:
                    done = _STATE["contacts"]
                if done > total_enriched:
                    remaining -= (done - total_enriched)
                    total_enriched = done

        finally:
            with _LOCK:
                _STATE["running"]     = False
                _STATE["phase"]       = "done"
                _STATE["finished_at"] = now.isoformat()

        # MAJ config
        db3 = SessionLocal()
        try:
            cfg3 = db3.get(EnrichmentConfigDB, "default")
            if cfg3:
                cfg3.last_run   = now
                cfg3.last_count = total_enriched
                db3.commit()
        finally:
            db3.close()

        log.info("auto_enrich: terminé — %d contact(s) créés", total_enriched)

        # ── Tracking coûts ────────────────────────────────────────────────
        try:
            from .cost_tracker import tracker as _tracker
            from .models import JobCostLogDB
            counts = _tracker.get_and_reset()
            cost = round(counts["google"] * 0.017, 4)
            db4 = SessionLocal()
            try:
                db4.add(JobCostLogDB(
                    job_id="auto_enrich",
                    started_at=now,
                    ended_at=datetime.utcnow(),
                    paire="auto",
                    nb_appels_google=counts["google"],
                    nb_appels_gemini=counts["gemini"],
                    nb_leads_generes=total_enriched,
                    cost_estimated=cost,
                ))
                db4.commit()
            finally:
                db4.close()
            log.info("auto_enrich: coûts — google=%d gemini=%d coût=%.4f$",
                     counts["google"], counts["gemini"], cost)
        except Exception as ce:
            log.warning("auto_enrich: tracking coûts échoué — %s", ce)

    except Exception as e:
        log.error("_job_auto_enrich: %s", e)


def _job_provision_leads(force: bool = False):
    """
    Fourniture automatique de X leads en file V3ProspectDB.
    Vérifie toutes les heures si la config (jour + heure UTC) correspond.
    Si force=True : ignore active/jour/heure (pour test manuel).
    Ordre : segments SireneSegmentDB par score DESC, suspects non encore provisionnés.
    """
    try:
        from datetime import datetime, timedelta
        from .database import SessionLocal
        from .models import LeadProvisioningConfigDB, SireneSuspectDB, SireneSegmentDB, IaCitedCompanyDB, V3ProspectDB
        import unicodedata, re as _re

        _LEGAL_SUFFIXES = _re.compile(
            r'\b(sarl|sas|sasu|sa|sci|snc|eurl|scp|scop|scic|gie|ei|ei|auto[- ]entrepreneur|'
            r'and co|et (cie|fils|freres?|associes?)|groupe|holding)\b'
        )
        def _norm_name(s):
            s = s.lower().strip()
            s = unicodedata.normalize("NFD", s)
            s = "".join(c for c in s if unicodedata.category(c) != "Mn")
            s = _re.sub(r"[^a-z0-9 ]", " ", s)
            s = _LEGAL_SUFFIXES.sub(" ", s)
            return _re.sub(r"\s+", " ", s).strip()

        def _is_cited(name: str, cited_norms: set) -> bool:
            """True si le nom matche un cité — exact ou sous-chaîne (min 5 chars)."""
            n = _norm_name(name)
            if not n or len(n) < 5:
                return False
            if n in cited_norms:
                return True
            # sous-chaîne : le nom IA est contenu dans le nom SIRENE ou l'inverse
            for cited in cited_norms:
                if len(cited) >= 5 and (cited in n or n in cited):
                    return True
            return False

        db = SessionLocal()
        try:
            cfg = db.get(LeadProvisioningConfigDB, "default")
            if not cfg:
                cfg = LeadProvisioningConfigDB(id="default")
                db.add(cfg)
                db.commit()
                db.refresh(cfg)

            if not force:
                if not cfg.active:
                    return
                now = datetime.utcnow()
                # Si days configurés, respecter la contrainte jour
                configured_days = [d.strip() for d in (cfg.days or "").split(",") if d.strip()]
                if configured_days and str(now.weekday()) not in configured_days:
                    return
                # Si hour_utc configuré (≥0), respecter l'heure exacte
                if cfg.hour_utc is not None and cfg.hour_utc >= 0 and now.hour != cfg.hour_utc:
                    return
                # Anti-rebond : pas deux fois dans la même heure
                if cfg.last_run and (now - cfg.last_run).total_seconds() < 3600:
                    return

            now = datetime.utcnow()

            log.info("provision_leads : démarrage (%d leads demandés)", cfg.leads_per_run)

            # Segments ordonnés par score DESC
            segments = (
                db.query(SireneSegmentDB)
                .filter(SireneSegmentDB.status == "done")
                .order_by(SireneSegmentDB.score.desc())
                .all()
            )

            remaining = cfg.leads_per_run
            provisioned = 0

            for seg in segments:
                if remaining <= 0:
                    break

                # Noms cités par IA pour ce métier (tous départements — on filtre sur nom)
                cited_norms = set(
                    row.name_norm for row in
                    db.query(IaCitedCompanyDB.name_norm)
                    .filter(IaCitedCompanyDB.profession == seg.profession_id.lower().strip())
                    .all()
                )

                suspects = (
                    db.query(SireneSuspectDB)
                    .filter(
                        SireneSuspectDB.profession_id == seg.profession_id,
                        SireneSuspectDB.departement == seg.departement,
                        SireneSuspectDB.provisioned_at.is_(None),
                        SireneSuspectDB.actif == True,
                    )
                    .order_by(
                        SireneSuspectDB.contactable.desc(),   # contactables en premier
                        SireneSuspectDB.created_at.asc(),     # FIFO
                    )
                    .limit(remaining * 3)  # marge pour les exclusions
                    .all()
                )

                for s in suspects:
                    if remaining <= 0:
                        break
                    # Exclure les entreprises déjà citées par les IA
                    if cited_norms and _is_cited(s.raison_sociale, cited_norms):
                        log.debug("provision_leads : exclu (cité IA) — %s", s.raison_sociale)
                        continue
                    # Éviter les doublons v3_prospects sur même nom+ville+métier
                    existing_v3 = db.query(V3ProspectDB).filter_by(
                        name=s.raison_sociale, city=s.ville, profession=seg.profession_id
                    ).first()
                    if existing_v3:
                        s.provisioned_at = now  # marquer quand même pour ne pas retraiter
                        continue
                    import secrets as _sec
                    _tok = _sec.token_hex(16)
                    v3 = V3ProspectDB(
                        token=_tok,
                        name=s.raison_sociale,
                        city=s.ville,
                        profession=seg.profession_id,
                        phone=getattr(s, "telephone", None) or getattr(s, "phone", None),
                        email=getattr(s, "email", None),
                        website=getattr(s, "site_web", None) or getattr(s, "website", None),
                        landing_url=f"/ia-reports/{_tok}",
                        contacted=False,
                        notes=f"SIRENE auto — dept:{s.departement or ''} NAF:{s.code_naf or ''}",
                    )
                    db.add(v3)
                    s.provisioned_at = now
                    provisioned += 1
                    remaining -= 1

            cfg.last_run = now
            cfg.last_count = provisioned
            db.commit()
            log.info("provision_leads : %d lead(s) ajoutés en V3ProspectDB", provisioned)

        finally:
            db.close()

    except Exception as e:
        log.error("_job_provision_leads : %s", e)


_SIRENE_STATE: dict = {"running": False, "done": True, "pending": 0, "done_segs": 0, "total_segs": 0, "suspects": 0}

def _sirene_qualify_state() -> dict:
    return dict(_SIRENE_STATE)

def run_sirene_qualify(profession_ids: list = None, max_per_naf: int = 200):
    """Qualification SIRENE par segments — lancé à la demande depuis l'admin.
    Si profession_ids est fourni, seuls ces métiers sont traités.
    """
    global _SIRENE_STATE
    _SIRENE_STATE = {"running": True, "done": False, "pending": 0, "done_segs": 0, "total_segs": 0, "suspects": 0}
    try:
        from .database import SessionLocal
        from .sirene import generate_segments, run_next_segment, segments_stats
        label = f"{len(profession_ids)} professions" if profession_ids else "toutes professions actives"
        log.info(f"[SIRENE] Démarrage qualification — {label}")
        db = SessionLocal()
        try:
            generated = generate_segments(db, profession_ids=profession_ids)
            log.info(f"[SIRENE] {generated} nouveaux segments générés")
            total_inserted = 0
            while True:
                result = run_next_segment(db, profession_ids=profession_ids)
                if result is None:
                    break
                if "error" not in result:
                    total_inserted += result.get("nb_inserted", 0)
                # MAJ état en temps réel
                stats = segments_stats(db)
                _SIRENE_STATE.update({
                    "pending":    stats.get("pending", 0),
                    "done_segs":  stats.get("done", 0),
                    "total_segs": stats.get("total_segments", 0),
                    "suspects":   stats.get("total_suspects", 0),
                })
            log.info(f"[SIRENE] Qualification terminée — {total_inserted} nouveaux suspects")
        finally:
            db.close()
    except Exception as e:
        log.error("[SIRENE] Erreur qualification : %s", e)
    finally:
        _SIRENE_STATE["running"] = False
        _SIRENE_STATE["done"]    = True


# ── OUTBOUND ─────────────────────────────────────────────────────────────────

_OUTBOUND_SUBJECTS = [
    "Vous n'êtes pas recommandé par les IA",
]

_OUTBOUND_BODY = """\
Bonjour,

On a cherché « {terme} {ville} » sur ChatGPT. Votre entreprise n'apparaît pas.

Aujourd'hui, beaucoup de gens passent par là avant d'appeler.

Vous avez déjà regardé ce que ça donne de votre côté ?

Si vous voulez voir concrètement ce que ça donne : {landing_url}

— Nathalie
Présence IA
"""

_OUTBOUND_SMS = "Bonjour, on a cherché « {terme} {ville} » sur ChatGPT. Votre entreprise n'apparaît pas. Vous avez regardé ce que ça donne ?"

_OUTBOUND_SENDERS = [
    ("sophie@presence-ia.online",  "Sophie — Présence IA"),
    ("marie@presence-ia.info",     "Marie — Présence IA"),
    ("lea@presence-ia.cloud",      "Léa — Présence IA"),
    ("emma@presence-ia.site",      "Emma — Présence IA"),
    ("julie@presence-ia.website",  "Julie — Présence IA"),
]

_FOLLOWUP_SUBJECT = "Je me permets de vous relancer"

_FOLLOWUP_BODY = """\
Bonjour,

Je me permets de revenir vers vous suite à mon précédent message.

Aujourd'hui, de plus en plus de personnes demandent directement à leur IA quel est le meilleur {metier} à {ville}.

Nous avons analysé votre position, et votre entreprise n'apparaît pas dans les réponses générées.

Concrètement, cela signifie que vos concurrents sont recommandés à votre place en ce moment-même, automatiquement.

Je peux vous montrer précisément ce que nous avons constaté et comment corriger cela pour votre activité de {metier} à {ville}.

Vous pouvez accéder directement à l'agenda ici :
{lien_agenda}

À très bientôt,
Nathalie
Présence IA
"""

_FOLLOWUP_SENDER = ("contact@presence-ia.online", "Nathalie — Présence IA")


def _outbound_send_prospect(p, dry_run: bool = False,
                            brevo_key: str = None, sent_idx: int = 0) -> dict:
    """
    Pipeline outbound complet pour UN V3ProspectDB.
    Utilisé par _job_outbound (boucle) ET par les boutons test admin.

    Étapes :
      1. Lit ia_results (garantis au niveau paire par _job_outbound avant la boucle)
      2. Image ville absente → fetch Unsplash (fallback 3 niveaux) et stocke
      3. Formate le message (_OUTBOUND_BODY / _OUTBOUND_SMS)
      4. Envoie via Brevo — sauf si dry_run=True
      5. Marque sent_at/email_status — SAUF si p.is_test (profil réutilisable)

    Retourne dict : ok, ia_ok, ia_total, has_image, img_source, terme, channel, body, error
    """
    import os, json, requests as _req, random
    from datetime import datetime
    from .api.routes.v3 import _resolve_termes
    from .city_images import fetch_city_header_image
    from .models import RefCityDB, V3ProspectDB
    from .database import SessionLocal

    if brevo_key is None:
        brevo_key = os.getenv("BREVO_API_KEY", "")

    # ── 1. Lecture ia_results (garantis au niveau paire avant la boucle d'envoi) ─
    ia_results_list = []
    if p.ia_results:
        try:
            ia_results_list = json.loads(p.ia_results)
        except Exception:
            pass

    ia_ok    = len([r for r in ia_results_list if r.get("ok")])
    ia_total = len(ia_results_list)

    # ── 2. Image ville obligatoire ────────────────────────────────────────────
    with SessionLocal() as _db:
        _ref = _db.query(RefCityDB).filter_by(city_name=(p.city or "").upper()).first()
        has_image  = bool(_ref and _ref.header_image_url)
        img_source = "cache" if has_image else None

    if not has_image:
        log.info("[OUTBOUND] Image absente pour %s — fetch Unsplash…", p.city)
        img_url   = fetch_city_header_image(p.city)
        has_image = bool(img_url)
        img_source = "unsplash" if has_image else None

    if not has_image and not dry_run:
        return {"ok": False, "ia_ok": ia_ok, "ia_total": ia_total,
                "has_image": False, "img_source": None,
                "error": f"Aucune image pour {p.city} — envoi bloqué"}

    # ── 3. Terme + formatage ──────────────────────────────────────────────────
    city_display = (p.city_reference or p.city or "").title()
    termes = _resolve_termes(p.profession)
    terme  = termes[0] if termes else (p.profession or "professionnel").lower()

    channel = "email" if p.email else "sms"
    subject = random.choice(_OUTBOUND_SUBJECTS)
    _base_url    = os.getenv("BASE_URL", "https://presence-ia.com").rstrip("/")
    _landing_rel = getattr(p, "landing_url", None) or ""
    landing_url  = (_base_url + _landing_rel) if _landing_rel else _base_url
    body    = (_OUTBOUND_BODY if channel == "email" else _OUTBOUND_SMS).format(
        terme=terme, ville=city_display, landing_url=landing_url
    )
    idx = sent_idx % len(_OUTBOUND_SENDERS)
    sender, sender_name = _OUTBOUND_SENDERS[idx]

    base = {"ia_ok": ia_ok, "ia_total": ia_total, "has_image": has_image,
            "img_source": img_source, "terme": terme, "channel": channel, "body": body}

    if dry_run:
        log.info("[OUTBOUND][DRY_RUN] %s — %s/%s — ia=%d/%d — img=%s",
                 channel.upper(), p.profession, p.city, ia_ok, ia_total, has_image)
        return {**base, "ok": True, "dry_run": True, "error": None}

    # ── 4. Envoi Brevo ────────────────────────────────────────────────────────
    if not brevo_key:
        return {**base, "ok": False, "error": "BREVO_API_KEY manquant"}

    try:
        if channel == "email" and p.email:
            resp = _req.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": brevo_key, "Content-Type": "application/json"},
                json={
                    "sender":      {"name": sender_name, "email": sender},
                    "to":          [{"email": p.email, "name": p.name}],
                    "subject":     subject,
                    "textContent": body,
                },
                timeout=15,
            )
        elif channel == "sms" and p.phone:
            phone_e164 = _outbound_normalize_phone(p.phone)
            if not phone_e164:
                return {**base, "ok": False, "error": f"Numéro invalide : {p.phone}"}
            resp = _req.post(
                "https://api.brevo.com/v3/transactionalSMS/sms",
                headers={"api-key": brevo_key, "Content-Type": "application/json"},
                json={"sender": "PresenceIA", "recipient": phone_e164,
                      "content": body, "type": "transactional"},
                timeout=15,
            )
        else:
            return {**base, "ok": False, "error": "Ni email ni téléphone"}

        ok = resp.status_code in (200, 201, 202)

        # ── 5. Marquer envoyé (sauf profils test — réutilisables) ────────────
        if ok and not getattr(p, "is_test", False):
            with SessionLocal() as _db:
                _p2 = _db.query(V3ProspectDB).filter_by(token=p.token).first()
                if _p2:
                    _p2.sent_at     = datetime.utcnow()
                    _p2.sent_method = channel
                    if channel == "email":
                        _p2.email_status  = "sent"
                        _p2.email_sent_at = datetime.utcnow()
                    _db.commit()

        return {**base, "ok": ok, "error": None if ok else f"Brevo HTTP {resp.status_code}"}
    except Exception as exc:
        return {**base, "ok": False, "error": str(exc)}


def _outbound_normalize_phone(phone: str) -> str | None:
    """Normalise un numéro français en format international +33..."""
    import re
    if not phone:
        return None
    digits = re.sub(r"[\s.\-()]", "", phone.strip())
    if digits.startswith("+33") and len(digits) == 12:
        return digits
    if digits.startswith("0033") and len(digits) == 13:
        return "+" + digits[2:]
    if digits.startswith("0") and len(digits) == 10 and digits[1] in "67":
        return "+33" + digits[1:]
    return None  # non mobile ou format inconnu


_EMAIL_RE = None  # compilé une fois à la première utilisation

_EMAIL_BAD_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif", ".ico", ".bmp", ".pdf")
_EMAIL_BAD_KEYWORDS   = ("sentry", "wixpress", "example", "test@", "noreply", "no-reply",
                          "donotreply", "do-not-reply", "mailer-daemon", "postmaster",
                          "bounce", "cropped-", "favicon", "logo-", "icon_")
_EMAIL_VALID_TLDS     = {
    "fr", "com", "net", "org", "io", "co", "eu", "biz", "info", "pro",
    "fr", "be", "ch", "ca", "de", "es", "it", "nl", "uk", "us", "me",
    "agency", "studio", "digital", "media", "shop", "store", "tech",
    "email", "mail", "online", "site", "web", "app", "dev",
}


def _outbound_is_valid_email(email: str) -> bool:
    """Retourne True si l'email est vraisemblablement valide pour un envoi outbound."""
    global _EMAIL_RE
    import re

    if not email or not isinstance(email, str):
        return False

    email = email.strip().lower()

    # Regex RFC-5322 simplifiée : local@domain.tld
    if _EMAIL_RE is None:
        _EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
    if not _EMAIL_RE.match(email):
        return False

    # Extensions image/fichier dans l'adresse
    if any(email.endswith(ext) or f"{ext}." in email for ext in _EMAIL_BAD_EXTENSIONS):
        return False

    # Mots-clés techniques / bots
    if any(kw in email for kw in _EMAIL_BAD_KEYWORDS):
        return False

    # TLD doit être connu (facultatif mais protège des inventions)
    tld = email.rsplit(".", 1)[-1]
    if len(tld) < 2 or len(tld) > 10:
        return False

    return True


def _outbound_is_cited(name: str, ia_results_json: str) -> bool:
    """Retourne True si l'entreprise semble citée dans les réponses IA.
    Méthode : recherche de mots-clés significatifs du nom dans le texte des réponses.
    """
    import json, re

    # Mots génériques à ignorer pour le matching
    IGNORE = {"sarl", "sas", "sasu", "eurl", "sa", "snc", "sci", "ei",
               "et", "de", "du", "la", "le", "les", "des", "au", "aux",
               "en", "par", "sur", "pour", "avec", "chez"}

    try:
        results = json.loads(ia_results_json) if isinstance(ia_results_json, str) else ia_results_json
    except Exception:
        return False

    # Texte combiné de toutes les réponses IA
    combined = " ".join(
        r.get("response", "") for r in results if isinstance(r, dict)
    ).lower()

    # Nettoyer le nom : enlever contenu entre parenthèses, ponctuation
    clean_name = re.sub(r"\(.*?\)", "", name)
    clean_name = re.sub(r"[^a-zA-ZÀ-ÿ0-9 ]", " ", clean_name)
    keywords = [w.lower() for w in clean_name.split() if len(w) > 3 and w.lower() not in IGNORE]

    if not keywords:
        return False

    # Cité si au moins 1 mot-clé significatif trouvé dans les réponses
    return any(kw in combined for kw in keywords)




def compute_outbound_need() -> dict:
    """
    Calcule le besoin outbound depuis v3_bookings (RDV réels) et SlotDB (capacité).

    Sources :
      v3_bookings      → RDV déjà pris (source de vérité)
      SlotDB.available → créneaux encore ouverts

    Env vars configurables :
      TARGET_RDV_MONDAY   int   3   RDV lundi prochain cible
      TARGET_RDV_WEEK     int   10  RDV cible sur 14 jours
      OUTBOUND_BASE_EMAIL int   5   emails de base par run
      OUTBOUND_BASE_SMS   int   3   SMS de base par run
      OUTBOUND_MAX_EMAIL  int   20  plafond email par run
      OUTBOUND_MAX_SMS    int   10  plafond SMS par run
      LAUNCH_MODE         bool  false  volumes x1.5 + J+1/J+2 ouverts côté prospect

    Retourne (parmi d'autres champs rétrocompat) :
      cap_email, cap_sms   → volumes à envoyer ce run
      statut               → "running" | "top_up" | "idle" | "saturated" | "pre_launch"
      fill_need            → 1.0 = vide, 0.0 = plein
      rdv_taken_week       → RDV réels pris sur 14j
      rdv_taken_monday     → RDV réels pris lundi prochain
      urgence_lundi        → bool (lundi < 50% de la cible)
    """
    import os
    from datetime import datetime, timezone, timedelta, date
    from .database import SessionLocal
    from .models import V3ProspectDB, V3BookingDB

    # ── Verrou de lancement ───────────────────────────────────────────────────
    LAUNCH_DATE = date(2026, 4, 16)
    today_local = datetime.now().date()
    if today_local < LAUNCH_DATE:
        log.info("compute_outbound_need: avant LAUNCH_DATE (%s) — pipeline en pause", LAUNCH_DATE)
        with SessionLocal() as db:
            leads_en_file = db.query(V3ProspectDB).filter(
                V3ProspectDB.ia_results.isnot(None),
                V3ProspectDB.sent_at.is_(None),
                V3ProspectDB.email.isnot(None),
                V3ProspectDB.is_test.is_(False),
            ).count()
        _z = {"total": 0, "reserves": 0, "disponibles": 0}
        return {
            "proche": _z, "moyen": _z, "lointain": _z,
            "taux_couverture": 0.0, "leads_en_file": leads_en_file,
            "leads_necessaires": 0, "leads_manquants": 0,
            "cap_recommande": 0, "cap_email": 0, "cap_sms": 0,
            "statut": "pre_launch", "bootstrap": True,
            "taux_conversion": 0.02, "source_slots": "db", "active_closers": 1,
            "rdv_taken_week": 0, "rdv_taken_monday": 0, "slots_open": 0,
            "fill_need": 1.0, "urgence_lundi": False, "launch_mode": False,
        }

    # ── Config env ────────────────────────────────────────────────────────────
    target_rdv_monday = int(os.getenv("TARGET_RDV_MONDAY",   "3"))
    target_rdv_week   = int(os.getenv("TARGET_RDV_WEEK",     "10"))
    base_email        = int(os.getenv("OUTBOUND_BASE_EMAIL", "5"))
    base_sms          = int(os.getenv("OUTBOUND_BASE_SMS",   "3"))
    max_email         = int(os.getenv("OUTBOUND_MAX_EMAIL",  "20"))
    max_sms           = int(os.getenv("OUTBOUND_MAX_SMS",    "10"))
    launch_mode       = os.getenv("LAUNCH_MODE", "false").lower() == "true"

    now     = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%S")
    end_iso = (now + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%S")

    # Prochain lundi (1→7 jours, jamais 0)
    days_to_monday    = (7 - today_local.weekday()) % 7 or 7
    next_monday       = today_local + timedelta(days=days_to_monday)
    monday_start_iso  = next_monday.strftime("%Y-%m-%dT00:00:00")
    monday_end_iso    = next_monday.strftime("%Y-%m-%dT23:59:59")

    # ── Lecture v3_bookings — RDV réels ───────────────────────────────────────
    rdv_taken_week   = 0
    rdv_taken_monday = 0
    leads_en_file    = 0
    sent_total       = 0

    with SessionLocal() as db:
        rdv_taken_week = (
            db.query(V3BookingDB)
            .join(V3ProspectDB, V3ProspectDB.token == V3BookingDB.prospect_token, isouter=True)
            .filter(
                V3BookingDB.start_iso >= now_iso,
                V3BookingDB.start_iso <= end_iso,
                V3ProspectDB.is_test.isnot(True),
            )
            .count()
        )
        rdv_taken_monday = (
            db.query(V3BookingDB)
            .join(V3ProspectDB, V3ProspectDB.token == V3BookingDB.prospect_token, isouter=True)
            .filter(
                V3BookingDB.start_iso >= monday_start_iso,
                V3BookingDB.start_iso <= monday_end_iso,
                V3ProspectDB.is_test.isnot(True),
            )
            .count()
        )
        leads_en_file = db.query(V3ProspectDB).filter(
            V3ProspectDB.ia_results.isnot(None),
            V3ProspectDB.sent_at.is_(None),
            V3ProspectDB.email.isnot(None),
            V3ProspectDB.is_test.is_(False),
        ).count()
        sent_total = db.query(V3ProspectDB).filter(
            V3ProspectDB.sent_at.isnot(None)
        ).count()

    # ── Lecture SlotDB — capacité disponible ──────────────────────────────────
    active_closers = 1
    slots_open     = 0
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import SlotDB, SlotStatus, CloserDB
        with MktSession() as mdb:
            active_closers = mdb.query(CloserDB).filter(
                CloserDB.project_id == "presence-ia",
                CloserDB.is_active  == True,
            ).count() or 1
            slots_open = mdb.query(SlotDB).filter(
                SlotDB.project_id == "presence-ia",
                SlotDB.status     == SlotStatus.available,
                SlotDB.starts_at  >= now,
                SlotDB.starts_at  <= now + timedelta(days=14),
            ).count()
    except Exception as e:
        log.warning("compute_outbound_need: marketing_module indisponible — %s", e)

    # ── Calcul du besoin ──────────────────────────────────────────────────────
    #  fill_need : 1.0 = agenda vide, 0.0 = agenda plein
    fill_rate_week   = min(1.0, rdv_taken_week   / target_rdv_week)   if target_rdv_week   > 0 else 1.0
    fill_rate_monday = min(1.0, rdv_taken_monday / target_rdv_monday) if target_rdv_monday > 0 else 1.0
    fill_need        = round(1.0 - fill_rate_week, 3)
    urgence_lundi    = fill_rate_monday < 0.5
    bootstrap        = sent_total < 30

    # ── Tiers d'envoi ─────────────────────────────────────────────────────────
    #  fill_need >= 0.80  → "running"   (< 20 % de la cible)
    #  fill_need >= 0.40  → "top_up"    (20-60 % de la cible)
    #  fill_need >= 0.15  → "idle"      (60-85 % de la cible)
    #  fill_need <  0.15  → "saturated" (> 85 % de la cible)
    if fill_need >= 0.80:
        statut = "running"
        e_vol  = max_email
        s_vol  = max_sms   if urgence_lundi else base_sms
    elif fill_need >= 0.40:
        statut = "top_up"
        e_vol  = base_email * 2
        s_vol  = base_sms  if urgence_lundi else 0
    elif fill_need >= 0.15:
        statut = "idle"
        e_vol  = base_email
        s_vol  = base_sms  if urgence_lundi else 0
    else:
        statut = "saturated"
        e_vol  = 0
        s_vol  = 0

    # Bootstrap override : toujours au moins base_email si < 30 envois
    if bootstrap and statut == "saturated":
        statut = "running"
        e_vol  = base_email
        s_vol  = base_sms

    # Launch mode : volumes × 1.5
    if launch_mode and statut != "saturated":
        e_vol = min(int(e_vol * 1.5), max_email)
        s_vol = min(int(s_vol * 1.5), max_sms)

    cap_email      = max(0, min(e_vol, max_email))
    cap_sms        = max(0, min(s_vol, max_sms))
    cap_recommande = cap_email + cap_sms

    # Champ rétrocompat dashboard (exprimé en taux de remplissage RDV / cible)
    taux_couverture = round(fill_rate_week * 100, 1)

    return {
        # Rétrocompat dashboard
        "proche":   {"total": slots_open + rdv_taken_week,
                     "reserves": rdv_taken_week, "disponibles": slots_open},
        "moyen":    {"total": 0, "reserves": 0, "disponibles": 0},
        "lointain": {"total": 0, "reserves": 0, "disponibles": 0},
        "taux_couverture":   taux_couverture,
        "leads_en_file":     leads_en_file,
        "leads_necessaires": target_rdv_week,
        "leads_manquants":   max(0, target_rdv_week - rdv_taken_week),
        "cap_recommande":    cap_recommande,
        "taux_conversion":   0.02,
        "source_slots":      "db",
        "active_closers":    active_closers,
        "bootstrap":         bootstrap,
        "statut":            statut,
        # Nouveaux champs
        "cap_email":         cap_email,
        "cap_sms":           cap_sms,
        "rdv_taken_week":    rdv_taken_week,
        "rdv_taken_monday":  rdv_taken_monday,
        "slots_open":        slots_open,
        "fill_need":         fill_need,
        "urgence_lundi":     urgence_lundi,
        "launch_mode":       launch_mode,
    }


def _job_followup():
    """
    Relance J+1 — envoie le mail de suivi 24h après J0.

    Règles de blocage (skip) :
      - email_status = bounced (inclut unsubscribe)
      - email_status = replied
      - email_booked_at IS NOT NULL  ou  booking dans v3_bookings
      - email_clicked_at IS NOT NULL (a visité la landing — signal fiable)
      - profession ou city vide
      - followup_sent_at déjà renseigné (anti-doublon)
    """
    import os
    import requests as _req
    import random as _random
    from datetime import datetime, timedelta
    from .database import SessionLocal
    from .models import V3ProspectDB, V3BookingDB

    dry_run   = os.getenv("OUTBOUND_DRY_RUN", "true").lower() == "true"
    brevo_key = os.getenv("BREVO_API_KEY", "")
    if not brevo_key and not dry_run:
        log.warning("[FOLLOWUP] BREVO_API_KEY absent — job annulé")
        return

    cutoff = datetime.utcnow() - timedelta(hours=24)

    with SessionLocal() as db:
        candidates = db.query(V3ProspectDB).filter(
            V3ProspectDB.email_sent_at.isnot(None),
            V3ProspectDB.email_sent_at <= cutoff,
            V3ProspectDB.followup_sent_at.is_(None),
            V3ProspectDB.sent_method == "email",
            V3ProspectDB.email.isnot(None),
            V3ProspectDB.is_test == False,  # noqa: E712
        ).all()

        if not candidates:
            log.info("[FOLLOWUP] Aucun prospect éligible")
            return

        log.info("[FOLLOWUP] %d prospects à traiter", len(candidates))

        # Index bookings par prospect_token pour éviter N requêtes
        booked_tokens = {
            r.prospect_token
            for r in db.query(V3BookingDB.prospect_token).all()
        }

        sent = skipped = 0
        skip_reasons: dict = {}

        for p in candidates:
            # ── Règles de blocage ─────────────────────────────────────────────
            reason = None
            if p.email_status == "bounced":
                reason = "bounced_or_unsubscribed"
            elif p.email_status == "replied":
                reason = "replied"
            elif p.email_booked_at or p.token in booked_tokens:
                reason = "rdv_booked"
            elif p.email_clicked_at:
                reason = "landing_visited"
            elif not (p.profession or "").strip():
                reason = "no_metier"
            elif not (p.city or "").strip():
                reason = "no_ville"

            if reason:
                p.followup_sent_at   = datetime.utcnow()
                p.followup_status    = "skipped"
                p.followup_skip_reason = reason
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                skipped += 1
                continue

            # ── Formatage ─────────────────────────────────────────────────────
            from .api.routes.v3 import _resolve_termes
            termes   = _resolve_termes(p.profession)
            metier   = termes[0] if termes else (p.profession or "").lower()
            ville    = (p.city_reference or p.city or "").title()
            base_url = os.getenv("BASE_URL", "https://presence-ia.com").rstrip("/")
            landing  = base_url + (p.landing_url or "")
            body     = _FOLLOWUP_BODY.format(metier=metier.lower(), ville=ville, lien_agenda=landing)

            if dry_run:
                log.info("[FOLLOWUP][DRY_RUN] %s — %s/%s", p.email, p.profession, p.city)
                p.followup_sent_at    = datetime.utcnow()
                p.followup_status     = "dry_run"
                p.followup_skip_reason = None
                sent += 1
                continue

            # ── Envoi Brevo ───────────────────────────────────────────────────
            try:
                sender_email, sender_name = _FOLLOWUP_SENDER
                resp = _req.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": brevo_key, "Content-Type": "application/json"},
                    json={
                        "sender":      {"name": sender_name, "email": sender_email},
                        "to":          [{"email": p.email, "name": p.name}],
                        "subject":     _FOLLOWUP_SUBJECT,
                        "textContent": body,
                    },
                    timeout=15,
                )
                ok = resp.status_code in (200, 201, 202)
            except Exception as exc:
                log.error("[FOLLOWUP] erreur Brevo pour %s : %s", p.email, exc)
                ok = False

            p.followup_sent_at    = datetime.utcnow()
            p.followup_status     = "sent" if ok else "error"
            p.followup_skip_reason = None if ok else "brevo_error"
            if ok:
                sent += 1
                log.info("[FOLLOWUP] ✓ %s — %s/%s", p.email, p.profession, p.city)
            else:
                skipped += 1

        db.commit()

    log.info("[FOLLOWUP] %s — envoyés=%d  ignorés=%d  raisons=%s",
             "DRY_RUN" if dry_run else "LIVE", sent, skipped, skip_reasons)


def _job_outbound(force: bool = False):
    """
    Outbound v3_prospects — mode autonome multi-paires.

    Variables d'env (pilotage) :
      OUTBOUND_DRY_RUN          bool    true          logs only, 0 envoi, 0 DB
      LAUNCH_MODE               bool    false         volumes x1.5 côté compute_outbound_need
      LAUNCH_AUTORUNS_ENABLED   bool    true          runs pilotés par horaires configurés
      LAUNCH_END_DATE           date    2026-04-21    fin du mode launch (YYYY-MM-DD)
      LAUNCH_RUN_HOURS          str     7,10,13,16,19 heures UTC pendant la période launch
      WEEKDAY_RUN_HOURS         str     9             heures UTC semaine normale (lun-ven)
      WEEKEND_RUN_HOURS         str     9,14          heures UTC weekend normal (sam-dim)
      MAX_PAIRS_PER_RUN         int     5             paires max traitées par run
      TARGET_RDV_MONDAY         int     3             RDV lundi cible
      TARGET_RDV_WEEK           int     10            RDV 14j cible
      OUTBOUND_BASE_EMAIL       int     40            emails de base / run
      OUTBOUND_BASE_SMS         int     10            SMS de base / run
      OUTBOUND_MAX_EMAIL        int     200           plafond email / run
      OUTBOUND_MAX_SMS          int     40            plafond SMS / run
    """
    import os, requests as _req
    from datetime import datetime, timezone, date as _date_cls
    from .database import SessionLocal
    from .models import V3ProspectDB, ScoringConfigDB

    dry_run   = os.getenv("OUTBOUND_DRY_RUN", "true").lower() == "true"
    brevo_key = os.getenv("BREVO_API_KEY", "")
    if not brevo_key and not dry_run:
        log.warning("[OUTBOUND] BREVO_API_KEY absent — job annulé")
        return

    mode_label = "DRY_RUN" if dry_run else "LIVE"

    # ── Vérification fenêtre horaire (bypassée si force=True) ────────────────
    if not force and os.getenv("LAUNCH_AUTORUNS_ENABLED", "true").lower() == "true":
        now_utc = datetime.now(timezone.utc)
        try:
            launch_end = _date_cls.fromisoformat(os.getenv("LAUNCH_END_DATE", "2026-04-21"))
        except ValueError:
            launch_end = _date_cls(2026, 4, 21)
        today_d   = now_utc.date()
        is_launch = today_d <= launch_end
        is_weekend = today_d.weekday() >= 5
        if is_launch:
            raw_hours = os.getenv("LAUNCH_RUN_HOURS",   "7,10,13,16,19")
        elif is_weekend:
            raw_hours = os.getenv("WEEKEND_RUN_HOURS",  "9,14")
        else:
            raw_hours = os.getenv("WEEKDAY_RUN_HOURS",  "9")
        allowed = [int(h.strip()) for h in raw_hours.split(",") if h.strip().isdigit()]
        if now_utc.hour not in allowed:
            log.debug("[OUTBOUND] skip — %dh UTC hors plage %s (launch=%s)",
                      now_utc.hour, allowed, is_launch)
            return
        log.info("[OUTBOUND][%s] run autorisé — %dh UTC · plage=%s · launch=%s",
                 mode_label, now_utc.hour, allowed, is_launch)

    # ── Pilotage par RDV réels (compute_outbound_need) ────────────────────────
    cap_email = int(os.getenv("OUTBOUND_MAX_EMAIL", "200"))
    cap_sms   = int(os.getenv("OUTBOUND_MAX_SMS",   "40"))

    if not force:
        try:
            need   = compute_outbound_need()
            statut = need["statut"]
            log.info(
                "[OUTBOUND][%s] statut=%s · rdv=%d/%d · fill=%.0f%% · "
                "lundi=%d/%d · urgence=%s · slots=%d · cap_e=%d · cap_s=%d · launch=%s",
                mode_label, statut,
                need["rdv_taken_week"], need["leads_necessaires"],
                (1.0 - need["fill_need"]) * 100,
                need["rdv_taken_monday"], int(os.getenv("TARGET_RDV_MONDAY", "3")),
                need["urgence_lundi"], need["slots_open"],
                need["cap_email"], need["cap_sms"], need["launch_mode"],
            )
            try:
                _paire_st = __import__("src.active_pair", fromlist=["get_active_pair"]).get_active_pair()
                from .models import PipelineHistoryLogDB
                with SessionLocal() as _hdb:
                    _hdb.add(PipelineHistoryLogDB(
                        mode              = "BOOTSTRAP" if need.get("bootstrap") else "AUTO",
                        paire_city        = (_paire_st or {}).get("city"),
                        paire_profession  = (_paire_st or {}).get("profession"),
                        taux_couverture   = need.get("taux_couverture"),
                        slots_proches_total    = need["proche"]["total"],
                        slots_proches_remplis  = need["proche"]["reserves"],
                        slots_moyens_total     = need["moyen"]["total"],
                        slots_moyens_remplis   = need["moyen"]["reserves"],
                        slots_lointains_total  = need["lointain"]["total"],
                        slots_lointains_remplis= need["lointain"]["reserves"],
                        leads_en_file     = need.get("leads_en_file"),
                        leads_necessaires = need.get("leads_necessaires"),
                        statut            = statut,
                        cap_genere        = need["cap_recommande"],
                        source_slots      = need.get("source_slots"),
                    ))
                    _hdb.commit()
            except Exception as _je:
                log.debug("[OUTBOUND] pipeline_history_log: %s", _je)
            if statut == "pre_launch":
                log.info("[OUTBOUND] Pre-launch — skip"); return
            if statut == "saturated":
                log.info("[OUTBOUND] Saturé (%.0f%% cible) — skip",
                         (1.0 - need["fill_need"]) * 100); return
            if statut == "idle" and need["cap_email"] == 0 and need["cap_sms"] == 0:
                log.info("[OUTBOUND] Idle caps=0 — skip"); return
            cap_email = need["cap_email"]
            cap_sms   = need["cap_sms"]
        except Exception as e:
            log.warning("[OUTBOUND] compute_outbound_need échoué — fallback caps: %s", e)

    # ── refs_only — lu une seule fois ─────────────────────────────────────────
    refs_only = True
    try:
        with SessionLocal() as _db_cfg:
            _cfg = _db_cfg.query(ScoringConfigDB).filter_by(id="default").first()
            if _cfg and hasattr(_cfg, "outbound_refs_only"):
                refs_only = bool(_cfg.outbound_refs_only)
    except Exception:
        pass

    # ── Boucle multi-paires ───────────────────────────────────────────────────
    from .active_pair import (check_saturation as _check_sat,
                              clear_active_pair as _clear_pair,
                              select_next_pair  as _next_pair)

    max_pairs   = int(os.getenv("MAX_PAIRS_PER_RUN", "5"))
    total_email = 0
    total_sms   = 0
    pairs_log   = []
    stop_reason = "cap_atteint"
    visited     = set()  # anti-boucle sur la même paire dans ce run

    for _idx in range(max_pairs):
        rem_e = cap_email - total_email
        rem_s = cap_sms   - total_sms
        if rem_e <= 0 and rem_s <= 0:
            stop_reason = "cap_atteint"; break

        with SessionLocal() as _db_p:
            _active = _check_sat(_db_p, visited)
        if not _active:
            stop_reason = "aucune_paire_disponible"; break

        pk = (_active["profession"], _active["city"])
        if pk in visited:
            stop_reason = "paires_epuisees_ce_run"
            log.info("[OUTBOUND] paire %s/%s déjà traitée ce run → arrêt", *pk); break
        visited.add(pk)

        log.info("[OUTBOUND][%s] paire %d/%d — %s / %s (score=%.1f) rem_e=%d rem_s=%d",
                 mode_label, _idx+1, max_pairs,
                 _active["profession"], _active["city"], _active.get("score", 0),
                 rem_e, rem_s)

        # Test IA si nécessaire pour cette paire
        try:
            from .api.routes.v3 import _run_ia_test
            import json as _json_ia
            with SessionLocal() as _db_ia:
                _has_ia = _db_ia.query(V3ProspectDB).filter(
                    V3ProspectDB.city == _active["city"],
                    V3ProspectDB.profession == _active["profession"],
                    V3ProspectDB.ia_results.isnot(None),
                ).first() is not None
            if not _has_ia:
                log.info("[OUTBOUND] %s/%s — test IA initial…",
                         _active["profession"], _active["city"])
                _ia_data = _run_ia_test(_active["profession"], _active["city"])
                if _ia_data and _ia_data.get("results"):
                    _ia_json  = _json_ia.dumps(_ia_data["results"], ensure_ascii=False)
                    _ia_cited = _extract_cited_names(_ia_data["results"])
                    with SessionLocal() as _db_ia2:
                        for _p in _db_ia2.query(V3ProspectDB).filter_by(
                            city=_active["city"], profession=_active["profession"]
                        ).all():
                            _p.ia_results   = _ia_json
                            _p.ia_tested_at = _ia_data.get("tested_at")
                        _db_ia2.commit()
                        _upsert_cited_companies(_db_ia2, _active["profession"],
                                                _active["city"], _ia_cited)
        except Exception as _e_ia:
            log.error("[OUTBOUND] erreur test IA paire %d: %s", _idx+1, _e_ia)

        # Image ville
        try:
            from .city_images import fetch_city_header_image
            from .models import RefCityDB as _RefCityDB
            with SessionLocal() as _db_img:
                _ref = _db_img.query(_RefCityDB).filter_by(
                    city_name=(_active["city"] or "").upper()
                ).first()
                _has_img = bool(_ref and _ref.header_image_url)
            if not _has_img:
                _img_url = fetch_city_header_image(_active["city"])
                if not _img_url:
                    log.warning("[OUTBOUND] %s — pas d'image → paire suivante", _active["city"])
                    _clear_pair("no_image")
                    with SessionLocal() as _db_nx: _next_pair(_db_nx, visited)
                    continue
        except Exception as _ie:
            log.warning("[OUTBOUND] image check échoué : %s — on continue", _ie)

        # Sélection prospects pour cette paire
        _bf = [
            V3ProspectDB.city       == _active["city"],
            V3ProspectDB.profession == _active["profession"],
            V3ProspectDB.ia_results.isnot(None),
            V3ProspectDB.sent_at.is_(None),
            V3ProspectDB.is_test.isnot(True),
        ]
        if refs_only:
            _bf.append(V3ProspectDB.city_reference.isnot(None))

        with SessionLocal() as db:
            has_email = (
                db.query(V3ProspectDB)
                .filter(
                    *_bf,
                    V3ProspectDB.email.isnot(None),
                    (V3ProspectDB.email_status.is_(None) |
                     V3ProspectDB.email_status.notin_(["bounced", "unsubscribed"])),
                )
                .limit(max(rem_e, 1) * 20)
                .all()
            )
            email_tokens = {p.token for p in has_email}
            has_sms = (
                db.query(V3ProspectDB)
                .filter(
                    *_bf,
                    V3ProspectDB.phone.isnot(None),
                    ~V3ProspectDB.token.in_(email_tokens) if email_tokens else True,
                )
                .limit(max(rem_s, 1) * 20)
                .all()
            )

        valid_email = [p for p in has_email if _outbound_is_valid_email(p.email)]
        valid_sms   = [p for p in has_sms   if _outbound_normalize_phone(p.phone)]

        if not valid_email and not valid_sms:
            log.info("[OUTBOUND] %s/%s — 0 prospects prêts → paire suivante",
                     _active["profession"], _active["city"])
            _clear_pair("saturation")
            with SessionLocal() as _db_nx: _next_pair(_db_nx, visited)
            continue

        log.info("[OUTBOUND] %s/%s — email_dispo=%d sms_dispo=%d",
                 _active["profession"], _active["city"],
                 len(valid_email), len(valid_sms))

        # Envois email
        pair_e = pair_e_skip = 0
        for prospect in valid_email:
            if pair_e >= rem_e: break
            if _outbound_is_cited(prospect.name, prospect.ia_results or "[]"):
                pair_e_skip += 1; continue
            result = _outbound_send_prospect(
                prospect, dry_run=dry_run, brevo_key=brevo_key,
                sent_idx=total_email + pair_e,
            )
            if dry_run:
                pair_e += 1
                log.info("[OUTBOUND][DRY_RUN] EMAIL #%d — %s <%s>  Body: %s",
                         total_email+pair_e, prospect.name, prospect.email,
                         result.get("body", "")[:80])
            elif result.get("ok"):
                pair_e += 1
                log.info("[OUTBOUND] EMAIL — %s (%s / %s)",
                         prospect.name, prospect.profession, prospect.city)
            else:
                log.warning("[OUTBOUND] EMAIL erreur — %s : %s",
                            prospect.name, result.get("error"))

        # Envois SMS
        pair_s = pair_s_skip = 0
        for prospect in valid_sms:
            if pair_s >= rem_s: break
            if _outbound_is_cited(prospect.name, prospect.ia_results or "[]"):
                pair_s_skip += 1; continue
            result = _outbound_send_prospect(
                prospect, dry_run=dry_run, brevo_key=brevo_key,
                sent_idx=total_email + pair_e + total_sms + pair_s,
            )
            if dry_run:
                pair_s += 1
                log.info("[OUTBOUND][DRY_RUN] SMS #%d — %s", total_sms+pair_s, prospect.name)
            elif result.get("ok"):
                pair_s += 1
                log.info("[OUTBOUND] SMS — %s (%s / %s)",
                         prospect.name, prospect.profession, prospect.city)
            else:
                log.warning("[OUTBOUND] SMS erreur — %s : %s",
                            prospect.name, result.get("error"))

        total_email += pair_e
        total_sms   += pair_s
        skip_total   = pair_e_skip + pair_s_skip
        pairs_log.append(
            f"{_active['profession']}/{_active['city']} e={pair_e} s={pair_s}"
            + (f" skip={skip_total}" if skip_total else "")
        )

        # Cap atteint → arrêt
        if total_email >= cap_email and total_sms >= cap_sms:
            stop_reason = "cap_atteint"; break

        # Paire partiellement épuisée → basculer pour compléter le cap
        if pair_e < rem_e or pair_s < rem_s:
            log.info("[OUTBOUND] %s/%s épuisée (e=%d/%d s=%d/%d) → paire suivante",
                     _active["profession"], _active["city"],
                     pair_e, rem_e, pair_s, rem_s)
            _clear_pair("saturation")
            with SessionLocal() as _db_nx: _next_pair(_db_nx, visited)
        else:
            stop_reason = "cap_atteint"; break
    else:
        stop_reason = "max_paires_atteint"

    # ── Résumé ────────────────────────────────────────────────────────────────
    summary = " | ".join(pairs_log) if pairs_log else "—"
    if dry_run:
        log.info("[OUTBOUND][DRY_RUN] terminé — email=%d/%d sms=%d/%d · %s",
                 total_email, cap_email, total_sms, cap_sms, summary)
    else:
        log.info("[OUTBOUND] terminé — email=%d/%d sms=%d/%d · arrêt=%s · %s",
                 total_email, cap_email, total_sms, cap_sms, stop_reason, summary)
