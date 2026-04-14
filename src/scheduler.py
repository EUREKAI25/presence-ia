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

    # Job 3 : polling Calendly — toutes les 10 min
    _scheduler.add_job(
        _job_calendly_poll,
        trigger=IntervalTrigger(minutes=10),
        id="calendly_poll",
        replace_existing=True,
        misfire_grace_time=120,
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

    # Job 9 : refresh IA désactivé — les tests IA sont lancés à la génération de leads (generate_v3)

    # Job 10 : monitoring clés API — toutes les 6h
    _scheduler.add_job(
        _job_check_api_keys,
        trigger=IntervalTrigger(hours=6),
        id="check_api_keys",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Job 11 : outbound v3_prospects — tous les jours à 9h UTC
    _scheduler.add_job(
        _job_outbound,
        trigger=CronTrigger(hour=9, minute=0, timezone="UTC"),
        id="outbound",
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
    """Relance les tests IA (ChatGPT + Gemini + Claude) pour :
    - la paire active (active_pair_state.json) — dès activation, avant tout envoi
    - toutes les paires en prospection (sent_at dans les 30 derniers jours)
    lun/jeu/dim à 9h30, 15h, 18h30 UTC. 3 appels API par paire.
    Alimente ia_cited_companies.
    """
    try:
        import time as _time, json as _json
        from datetime import timedelta
        from .database import SessionLocal
        from .api.routes.v3 import _run_ia_test, V3ProspectDB
        from .active_pair import get_active_pair

        active_pairs = set()

        # 1. Paire active (peut n'avoir aucun envoi encore)
        active = get_active_pair()
        if active:
            active_pairs.add((active["city"], active["profession"]))

        # 2. Paires en prospection (au moins 1 envoi dans les 30j)
        cutoff = datetime.utcnow() - timedelta(days=30)
        with SessionLocal() as db:
            rows = (
                db.query(V3ProspectDB.city, V3ProspectDB.profession)
                .filter(V3ProspectDB.sent_at >= cutoff)
                .distinct()
                .all()
            )
        for r in rows:
            active_pairs.add((r.city, r.profession))

        if not active_pairs:
            log.info("refresh_ia : aucune paire active ou en prospection — skip")
            return

        log.info("refresh_ia : %d paire(s) à tester", len(active_pairs))
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


def _job_calendly_poll():
    """
    Polling Calendly (plan gratuit — pas de webhooks).
    Toutes les 10 min : cherche les nouveaux RDV depuis le dernier poll,
    les enregistre dans MeetingDB, marque la séquence email comme stoppée.
    """
    try:
        import os, requests as _req
        from datetime import datetime, timezone, timedelta
        from .database import SessionLocal
        from .models import V3ProspectDB

        token = os.getenv("CALENDLY_TOKEN", "")
        if not token:
            return

        org = "https://api.calendly.com/organizations/77e3ded7-540e-45ff-ab45-f40e8eb39e7c"
        headers = {"Authorization": f"Bearer {token}"}

        # Fenêtre : depuis 15 min en arrière (chevauchement léger pour ne rien rater)
        since = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        resp = _req.get(
            "https://api.calendly.com/scheduled_events",
            params={"organization": org, "status": "active",
                    "min_start_time": since, "count": 100},
            headers=headers, timeout=10,
        )
        if resp.status_code != 200:
            log.warning("Calendly poll HTTP %s", resp.status_code)
            return

        events = resp.json().get("collection", [])
        if not events:
            return

        log.info("Calendly poll : %d event(s) récents", len(events))

        try:
            from marketing_module.database import SessionLocal as MktSession
            from marketing_module.models import MeetingDB, MeetingStatus, ReplyStatus
            from marketing_module.database import (db_create_meeting, db_update_delivery,
                                                    db_sync_slot_from_meeting)
        except Exception as e:
            log.warning("marketing_module non dispo pour Calendly poll: %s", e)
            return

        with SessionLocal() as db, MktSession() as mdb:
            for ev in events:
                event_uuid = ev.get("uri", "").split("/")[-1]
                calendly_event_id = event_uuid

                # Éviter les doublons
                existing = mdb.query(MeetingDB).filter_by(
                    calendly_event_id=calendly_event_id
                ).first()
                if existing:
                    # Synchroniser quand même le slot si le meeting existe déjà
                    db_sync_slot_from_meeting(mdb, "presence-ia", existing)
                    continue

                # Récupérer l'email de l'invité
                inv_resp = _req.get(
                    f"https://api.calendly.com/scheduled_events/{event_uuid}/invitees",
                    params={"count": 1}, headers=headers, timeout=10,
                )
                if inv_resp.status_code != 200:
                    continue
                invitees = inv_resp.json().get("collection", [])
                if not invitees:
                    continue
                invitee_email = invitees[0].get("email", "")
                if not invitee_email:
                    continue

                # Chercher le prospect V3 par email
                prospect = db.query(V3ProspectDB).filter_by(email=invitee_email).first()
                prospect_id = prospect.token if prospect else invitee_email

                # Parser la date de RDV
                try:
                    scheduled_at = datetime.fromisoformat(
                        ev["start_time"].replace("Z", "+00:00")
                    )
                except Exception:
                    scheduled_at = None

                # Créer le meeting dans CRM
                new_meeting = db_create_meeting(mdb, {
                    "project_id":        "presence-ia",
                    "prospect_id":       prospect_id,
                    "campaign_id":       None,
                    "scheduled_at":      scheduled_at,
                    "status":            MeetingStatus.scheduled,
                    "calendly_event_id": calendly_event_id,
                    "calendly_event_uri": ev.get("uri", ""),
                    "notes":             invitees[0].get("name", ""),
                })

                # Créer un slot 'booked' dans l'agenda des closers
                if new_meeting:
                    db_sync_slot_from_meeting(mdb, "presence-ia", new_meeting)

                # Tracker le booking sur le prospect V3
                if prospect and not prospect.email_booked_at:
                    prospect.email_booked_at = datetime.utcnow()
                    db.commit()

                # Stopper la séquence email : marquer la dernière livraison comme "replied"
                from marketing_module.models import ProspectDeliveryDB
                last_delivery = (
                    mdb.query(ProspectDeliveryDB)
                    .filter_by(project_id="presence-ia", prospect_id=prospect_id)
                    .order_by(ProspectDeliveryDB.created_at.desc())
                    .first()
                )
                if last_delivery:
                    db_update_delivery(mdb, last_delivery.id, {
                        "reply_status": ReplyStatus.positive
                    })

                log.info("Calendly RDV enregistré — %s (%s)", invitee_email, event_uuid[:8])

    except Exception as e:
        log.error("_job_calendly_poll : %s", e)


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


def _outbound_send_prospect(p, dry_run: bool = False,
                            brevo_key: str = None, sent_idx: int = 0) -> dict:
    """
    Pipeline outbound complet pour UN V3ProspectDB.
    Utilisé par _job_outbound (boucle) ET par les boutons test admin.

    Étapes :
      1. ia_results absent → lance _run_ia_test et stocke en DB
      2. Image ville absente → fetch Unsplash (fallback 3 niveaux) et stocke
      3. Formate le message (_OUTBOUND_BODY / _OUTBOUND_SMS)
      4. Envoie via Brevo — sauf si dry_run=True
      5. Marque sent_at/email_status — SAUF si p.is_test (profil réutilisable)

    Retourne dict : ok, ia_ok, ia_total, has_image, img_source, terme, channel, body, error
    """
    import os, json, requests as _req, random
    from datetime import datetime
    from .api.routes.v3 import _run_ia_test, _resolve_termes
    from .city_images import fetch_city_header_image
    from .models import RefCityDB, V3ProspectDB
    from .database import SessionLocal

    if brevo_key is None:
        brevo_key = os.getenv("BREVO_API_KEY", "")

    # ── 1. Enrichissement IA si absent ───────────────────────────────────────
    ia_results_list = []
    if p.ia_results:
        try:
            ia_results_list = json.loads(p.ia_results)
        except Exception:
            pass

    if not ia_results_list:
        log.info("[OUTBOUND] ia_results absent pour %s/%s — lancement requêtes IA",
                 p.profession, p.city)
        ia_data = _run_ia_test(p.profession, p.city)
        ia_results_json = json.dumps(ia_data.get("results", []), ensure_ascii=False) \
                          if ia_data.get("results") else None
        if ia_results_json:
            with SessionLocal() as _db:
                _p2 = _db.query(V3ProspectDB).filter_by(token=p.token).first()
                if _p2:
                    _p2.ia_results = ia_results_json
                    _db.commit()
            try:
                ia_results_list = json.loads(ia_results_json)
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
                "https://api.brevo.com/v3/transactionalSms/send",
                headers={"api-key": brevo_key, "Content-Type": "application/json"},
                json={"sender": "PresenceIA", "recipient": phone_e164, "content": body},
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


def _get_calendly_available_slots(token: str, org: str, start, end) -> list:
    """
    Interroge Calendly pour les créneaux disponibles sur la période [start, end].
    Retourne une liste de dicts {start, end} ou [] si API non disponible.
    """
    import requests as _req
    headers = {"Authorization": f"Bearer {token}"}
    start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str   = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Récupérer les event types actifs
    r = _req.get("https://api.calendly.com/event_types",
                 params={"organization": org, "active": "true", "count": 10},
                 headers=headers, timeout=10)
    if r.status_code != 200:
        return []

    available = []
    for et in r.json().get("collection", []):
        et_uri = et.get("uri", "")
        if not et_uri:
            continue
        r2 = _req.get("https://api.calendly.com/event_type_available_times",
                      params={"event_type": et_uri,
                              "start_time": start_str, "end_time": end_str},
                      headers=headers, timeout=10)
        if r2.status_code == 200:
            for t in r2.json().get("collection", []):
                if t.get("status") == "available":
                    available.append({"start": t["start_time"], "end": t["end_time"]})
    return available


def compute_outbound_need() -> dict:
    """
    Calcule le besoin en leads en fonction des créneaux Calendly.

    Retourne :
      proche         : {total, reserves, disponibles}
      taux_couverture: float (%)
      leads_en_file  : int
      leads_necessaires: int
      cap_recommande : int (envois max pour ce run)
      statut         : "idle" | "running" | "saturated"
      bootstrap      : bool
    """
    import os
    from datetime import datetime, timezone, timedelta
    from .database import SessionLocal
    from .models import V3ProspectDB

    now = datetime.now(timezone.utc)

    # ── Fenêtres ──────────────────────────────────────────────────────────────
    def _range(d_start, d_end):
        return (now + timedelta(days=d_start),
                now + timedelta(days=d_end, hours=23, minutes=59, seconds=59))

    proche_start,   proche_end   = _range(2, 4)
    moyen_start,    moyen_end    = _range(5, 7)
    lointain_start, lointain_end = _range(8, 14)

    token = os.getenv("CALENDLY_TOKEN", "")
    org   = "https://api.calendly.com/organizations/77e3ded7-540e-45ff-ab45-f40e8eb39e7c"
    slots_per_day = int(os.getenv("CLOSER_SLOTS_PER_DAY", "2"))

    # ── Créneaux disponibles (Calendly API) ───────────────────────────────────
    def _count_in_range(slots, start, end):
        n = 0
        for s in slots:
            try:
                t = datetime.fromisoformat(s["start"].replace("Z", "+00:00"))
                if start <= t <= end:
                    n += 1
            except Exception:
                pass
        return n

    all_available = []
    if token:
        try:
            all_available = _get_calendly_available_slots(
                token, org, proche_start, lointain_end)
        except Exception as e:
            log.warning("compute_outbound_need: Calendly API indisponible — %s", e)

    if all_available:
        proche_dispo_cal   = _count_in_range(all_available, proche_start, proche_end)
        moyen_dispo_cal    = _count_in_range(all_available, moyen_start, moyen_end)
        lointain_dispo_cal = _count_in_range(all_available, lointain_start, lointain_end)
    else:
        # Fallback : capacité configurée (jours × slots/jour)
        proche_dispo_cal   = 3 * slots_per_day
        moyen_dispo_cal    = 3 * slots_per_day
        lointain_dispo_cal = 7 * slots_per_day

    # ── Créneaux réservés (meetings DB) ───────────────────────────────────────
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import MeetingDB, MeetingStatus

        with MktSession() as mdb:
            def _booked(start, end):
                return mdb.query(MeetingDB).filter(
                    MeetingDB.project_id == "presence-ia",
                    MeetingDB.status == MeetingStatus.scheduled,
                    MeetingDB.scheduled_at >= start,
                    MeetingDB.scheduled_at <= end,
                ).count()

            proche_reserves   = _booked(proche_start, proche_end)
            moyen_reserves    = _booked(moyen_start, moyen_end)
            lointain_reserves = _booked(lointain_start, lointain_end)
    except Exception as e:
        log.warning("compute_outbound_need: marketing_module indisponible — %s", e)
        proche_reserves = moyen_reserves = lointain_reserves = 0

    # ── Totaux slots proches (dispo + réservés = total proposé aux prospects) ─
    proche_total      = proche_dispo_cal + proche_reserves
    proche_disponibles = max(0, proche_dispo_cal)

    taux = (proche_reserves / proche_total) if proche_total > 0 else 0.0

    # ── Leads en file + mode bootstrap ────────────────────────────────────────
    with SessionLocal() as db:
        leads_en_file = db.query(V3ProspectDB).filter(
            V3ProspectDB.ia_results.isnot(None),
            V3ProspectDB.sent_at.is_(None),
            V3ProspectDB.email.isnot(None),
        ).count()
        sent_total = db.query(V3ProspectDB).filter(
            V3ProspectDB.sent_at.isnot(None)
        ).count()

    bootstrap        = sent_total < 30
    taux_conversion  = 0.02   # 2% fixe (mode bootstrap)
    leads_necessaires = int(proche_disponibles / taux_conversion) if proche_disponibles > 0 else 0
    leads_manquants   = max(0, leads_necessaires - leads_en_file)

    # ── Statut (4 niveaux) ────────────────────────────────────────────────────
    # STOP     : couverture > 85%
    # RUN      : couverture < 70% → génération agressive
    # TOP_UP   : couverture 70–85% ET file insuffisante → appoint léger (50% du manque)
    # IDLE     : couverture 70–85% ET file suffisante
    if taux >= 0.85:
        statut        = "saturated"
        cap_recommande = 0
    elif taux < 0.70:
        statut        = "running"
        cap_recommande = leads_manquants
    else:
        # Zone intermédiaire 70–85%
        if leads_en_file >= leads_necessaires:
            statut        = "idle"
            cap_recommande = 0
        else:
            statut        = "top_up"
            cap_recommande = max(1, leads_manquants // 2)

    return {
        "proche":            {"total": proche_total, "reserves": proche_reserves,
                              "disponibles": proche_disponibles},
        "moyen":             {"total": moyen_dispo_cal + moyen_reserves,
                              "reserves": moyen_reserves,
                              "disponibles": max(0, moyen_dispo_cal)},
        "lointain":          {"total": lointain_dispo_cal + lointain_reserves,
                              "reserves": lointain_reserves,
                              "disponibles": max(0, lointain_dispo_cal)},
        "taux_couverture":   round(taux * 100, 1),
        "leads_en_file":     leads_en_file,
        "leads_necessaires": leads_necessaires,
        "leads_manquants":   leads_manquants,
        "cap_recommande":    cap_recommande,
        "statut":            statut,
        "bootstrap":         bootstrap,
        "taux_conversion":   taux_conversion,
        "source_slots":      "calendly" if all_available else "config",
    }


def _job_outbound(force: bool = False):
    """
    Outbound v3_prospects — tous les jours à 9h UTC.
    Sélectionne les prospects avec ia_results IS NOT NULL et sent_at IS NULL.
    Score : skip si l'entreprise est déjà citée par l'IA, envoyer sinon.

    Variables d'env :
      OUTBOUND_CAP          — nombre max d'envois par run (défaut : 10)
      OUTBOUND_DRY_RUN      — si "true" : aucun envoi, aucune écriture DB, logs only
      CLOSER_SLOTS_PER_DAY  — capacité fallback si Calendly API indisponible (défaut : 2)
    """
    import os, random, requests as _req
    from datetime import datetime
    from .database import SessionLocal
    from .models import V3ProspectDB, ScoringConfigDB

    dry_run = os.getenv("OUTBOUND_DRY_RUN", "true").lower() == "true"  # SÉCURITÉ : défaut=true, activation explicite requise
    cap     = int(os.getenv("OUTBOUND_CAP", "10"))
    if dry_run:
        cap = min(cap, 20)   # sécurité : cap 20 max en dry_run

    brevo_key = os.getenv("BREVO_API_KEY", "")
    if not brevo_key and not dry_run:
        log.warning("[OUTBOUND] BREVO_API_KEY absent — job annulé")
        return

    mode_label = "DRY_RUN" if dry_run else "LIVE"

    # ── Pilotage par slots Calendly ───────────────────────────────────────────
    _need_for_log = None   # conservé pour le journal
    if not force:
        try:
            need = compute_outbound_need()
            _need_for_log = need
            statut = need["statut"]
            log.info(
                "[OUTBOUND] slots proches %d/%d (%.0f%%) · leads_file=%d · besoin=%d · statut=%s",
                need["proche"]["reserves"], need["proche"]["total"],
                need["taux_couverture"],
                need["leads_en_file"], need["leads_necessaires"], statut,
            )
            # ── Journal pilotage (toujours, même si skip) ───────────────────
            try:
                _paire_st = __import__("src.active_pair", fromlist=["get_active_pair"]).get_active_pair()
                from .models import PipelineHistoryLogDB
                with SessionLocal() as _hdb:
                    _hdb.add(PipelineHistoryLogDB(
                        mode              = "BOOTSTRAP" if need.get("bootstrap") else "AUTO",
                        paire_city        = (_paire_st or {}).get("city"),
                        paire_profession  = (_paire_st or {}).get("profession"),
                        taux_couverture   = need.get("taux_couverture"),
                        slots_proches_total    = need.get("proche", {}).get("total"),
                        slots_proches_remplis  = need.get("proche", {}).get("reserves"),
                        slots_moyens_total     = need.get("moyen",  {}).get("total"),
                        slots_moyens_remplis   = need.get("moyen",  {}).get("reserves"),
                        slots_lointains_total  = need.get("lointain", {}).get("total"),
                        slots_lointains_remplis= need.get("lointain", {}).get("reserves"),
                        leads_en_file     = need.get("leads_en_file"),
                        leads_necessaires = need.get("leads_necessaires"),
                        statut            = statut,
                        cap_genere        = cap if statut not in ("saturated", "idle") else 0,
                        source_slots      = need.get("source_slots"),
                    ))
                    _hdb.commit()
            except Exception as _je:
                log.debug("[OUTBOUND] pipeline_history_log: %s", _je)
            # ───────────────────────────────────────────────────────────────
            if statut == "saturated":
                log.info("[OUTBOUND] Saturé (%.0f%% > 85%%) — skip", need["taux_couverture"])
                return
            if statut == "idle":
                log.info("[OUTBOUND] Idle — leads en file suffisants (%d >= %d) — skip",
                         need["leads_en_file"], need["leads_necessaires"])
                return
            # Ajuster le cap au besoin réel (running = cap plein, top_up = 50% du manque)
            if need["cap_recommande"] > 0:
                cap = min(cap, need["cap_recommande"])
                mode_cap = "top_up" if statut == "top_up" else "run"
                log.info("[OUTBOUND] Cap ajusté à %d (%s)", cap, mode_cap)
        except Exception as e:
            log.warning("[OUTBOUND] Calcul slot coverage échoué — mode normal: %s", e)

    # ── Chantier C : vérifier/avancer la paire active ────────────────────────
    from .active_pair import check_saturation as _check_saturation
    with SessionLocal() as _db_pair:
        _active = _check_saturation(_db_pair)
    if not _active:
        log.warning("[OUTBOUND] aucune paire active disponible — job annulé")
        return
    log.info("[OUTBOUND] paire active — %s / %s (score=%.1f)",
             _active["profession"], _active["city"], _active.get("score", 0))

    # ── Image obligatoire pour la paire active ───────────────────────────────
    try:
        from .city_images import fetch_city_header_image
        from .models import RefCityDB as _RefCityDB
        with SessionLocal() as _db_img:
            _ref_img = _db_img.query(_RefCityDB).filter_by(
                city_name=(_active["city"] or "").upper()
            ).first()
            _has_img = bool(_ref_img and _ref_img.header_image_url)
        if not _has_img:
            log.info("[OUTBOUND] Image absente pour %s — fetch Unsplash (fallback)…",
                     _active["city"])
            _img_url = fetch_city_header_image(_active["city"])
            if not _img_url:
                log.warning("[OUTBOUND] Aucune image pour %s — job annulé (landing sans visuel)",
                            _active["city"])
                return
            log.info("[OUTBOUND] Image récupérée pour %s : %s", _active["city"], _img_url[:60])
    except Exception as _ie:
        log.warning("[OUTBOUND] Vérification image échouée : %s — on continue", _ie)

    # ── Lire le flag refs_only depuis ScoringConfigDB ─────────────────────────
    refs_only = True  # fallback
    try:
        with SessionLocal() as _db_cfg:
            _cfg_refs = _db_cfg.query(ScoringConfigDB).filter_by(id="default").first()
            if _cfg_refs and hasattr(_cfg_refs, "outbound_refs_only"):
                refs_only = bool(_cfg_refs.outbound_refs_only)
    except Exception:
        pass

    # ── Sélection email + SMS ─────────────────────────────────────────────────
    _base_filter = [
        V3ProspectDB.city       == _active["city"],
        V3ProspectDB.profession == _active["profession"],
        V3ProspectDB.ia_results.isnot(None),
        V3ProspectDB.sent_at.is_(None),
    ]
    # Exclure les profils test (gérés manuellement)
    _base_filter.append(V3ProspectDB.is_test.isnot(True))
    # Si refs_only : uniquement les prospects avec city_reference renseignée
    if refs_only:
        _base_filter.append(V3ProspectDB.city_reference.isnot(None))

    with SessionLocal() as db:
        # Email : priorité
        has_email = (
            db.query(V3ProspectDB)
            .filter(
                *_base_filter,
                V3ProspectDB.email.isnot(None),
                (V3ProspectDB.email_status.is_(None) |
                 V3ProspectDB.email_status.notin_(["bounced", "unsubscribed"])),
            )
            .limit(cap * 20)
            .all()
        )
        # SMS : uniquement si pas d'email
        has_sms = (
            db.query(V3ProspectDB)
            .filter(
                *_base_filter,
                V3ProspectDB.phone.isnot(None),
                V3ProspectDB.email.is_(None),
            )
            .limit(cap * 20)
            .all()
        )

    valid_email   = [p for p in has_email if _outbound_is_valid_email(p.email)]
    invalid_email = [p for p in has_email if not _outbound_is_valid_email(p.email)]
    valid_sms     = [p for p in has_sms if _outbound_normalize_phone(p.phone)]
    invalid_sms   = [p for p in has_sms if not _outbound_normalize_phone(p.phone)]

    # Fusionner : email d'abord, SMS ensuite
    candidates = valid_email + valid_sms

    log.info("[OUTBOUND] sélection — email_valide=%d  sms_valide=%d  email_invalide=%d  sms_invalide=%d",
             len(valid_email), len(valid_sms), len(invalid_email), len(invalid_sms))

    if dry_run and invalid_email:
        for p in invalid_email:
            log.info("[OUTBOUND][DRY_RUN] EMAIL_INVALIDE — %-40s  %s", p.name[:40], p.email)
    if dry_run and invalid_sms:
        for p in invalid_sms:
            log.info("[OUTBOUND][DRY_RUN] SMS_INVALIDE — %-40s  %s", p.name[:40], p.phone)

    # ── Scoring comparatif (dry_run uniquement) ────────────────────────────────
    if dry_run:
        cited_count     = sum(1 for p in candidates if _outbound_is_cited(p.name, p.ia_results or "[]"))
        not_cited_count = len(candidates) - cited_count
        log.info("[OUTBOUND][DRY_RUN] scoring comparatif sur %d candidats :", len(candidates))
        log.info("[OUTBOUND][DRY_RUN]   avec scoring  — would_send=%d  would_skip=%d",
                 not_cited_count, cited_count)
        log.info("[OUTBOUND][DRY_RUN]   sans scoring  — would_send=%d", len(candidates))

    # ── Boucle principale ─────────────────────────────────────────────────────
    selected    = 0
    skipped     = 0
    would_send  = 0
    sent        = 0
    errors      = 0

    for prospect in candidates:
        if (sent if not dry_run else would_send) >= cap:
            break

        selected += 1

        # Scoring — skip si déjà cité par les IA
        if _outbound_is_cited(prospect.name, prospect.ia_results or "[]"):
            skipped += 1
            log.info("[OUTBOUND] SKIP cité — %-40s  %-20s  %s",
                     prospect.name[:40], prospect.city or "", prospect.email)
            continue

        result = _outbound_send_prospect(
            prospect, dry_run=dry_run,
            brevo_key=brevo_key,
            sent_idx=sent + would_send,
        )

        if dry_run:
            would_send += 1
            log.info("[OUTBOUND][DRY_RUN] ══ %s #%d\n  To: %s <%s>\n  Body: %s",
                     result.get("channel","?").upper(), would_send,
                     prospect.name, prospect.email or prospect.phone,
                     (result.get("body","")[:80]))
        elif result.get("ok"):
            sent += 1
            log.info("[OUTBOUND] %s envoyé — %s (%s / %s)",
                     result.get("channel","?").upper(), prospect.name,
                     prospect.profession, prospect.city)
        else:
            errors += 1
            log.warning("[OUTBOUND] erreur — %s : %s", prospect.name, result.get("error"))

    if dry_run:
        log.info("[OUTBOUND][DRY_RUN] terminé — sélectionnés=%d  skipped(cités)=%d  would_send=%d  (0 envoi réel, 0 écriture DB)",
                 selected, skipped, would_send)
    else:
        log.info("[OUTBOUND] terminé — sélectionnés=%d  skipped=%d  envoyés=%d  erreurs=%d",
                 selected, skipped, sent, errors)
