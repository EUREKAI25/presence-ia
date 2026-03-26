"""
Scheduler APScheduler — tâches périodiques PRESENCE_IA.

Jobs actifs :
- run_due_targets   : toutes les heures — prospection automatique Google Places
"""
import logging
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

    # Job 7 : enrichissement Google Places automatique — vérification toutes les heures
    _scheduler.add_job(
        _job_auto_enrich,
        trigger=IntervalTrigger(hours=1),
        id="auto_enrich",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Job 8 : fourniture leads — vérification toutes les heures
    _scheduler.add_job(
        _job_provision_leads,
        trigger=IntervalTrigger(hours=1),
        id="provision_leads",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Job 9 : refresh tests IA — lun/jeu/dim à 9h30, 15h, 18h30 UTC
    for _hour, _minute in [(9, 30), (15, 0), (18, 30)]:
        _scheduler.add_job(
            _job_refresh_ia,
            trigger=CronTrigger(day_of_week="mon,thu,sun", hour=_hour, minute=_minute, timezone="UTC"),
            id=f"refresh_ia_{_hour:02d}{_minute:02d}",
            replace_existing=True,
            misfire_grace_time=1800,
        )

    _scheduler.start()
    log.info("Scheduler démarré — %d job(s)", len(_scheduler.get_jobs()))


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


def _job_refresh_ia():
    """Relance les tests IA (ChatGPT + Gemini + Claude) pour toutes les paires
    ville/métier actives — lun/jeu/dim à 9h30, 15h, 18h30 UTC."""
    try:
        import time as _time, json as _json
        from .database import SessionLocal
        from .api.routes.v3 import _run_ia_test, V3ProspectDB
        with SessionLocal() as db:
            pairs = db.query(V3ProspectDB.city, V3ProspectDB.profession).distinct().all()
        log.info("refresh_ia : %d paires à tester", len(pairs))
        for city, profession in pairs:
            try:
                ia_data = _run_ia_test(profession, city)
                if not ia_data or not ia_data.get("results"):
                    continue
                ia_results_json = _json.dumps(ia_data["results"], ensure_ascii=False)
                with SessionLocal() as db:
                    for p in db.query(V3ProspectDB).filter_by(city=city, profession=profession).all():
                        p.ia_prompt    = ia_data.get("prompt")
                        p.ia_response  = ia_data.get("response")
                        p.ia_model     = ia_data.get("model")
                        p.ia_tested_at = ia_data.get("tested_at")
                        p.ia_results   = ia_results_json
                    db.commit()
                log.info("refresh_ia OK: %s / %s", profession, city)
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
    """Wrapper DB → appelle run_due_targets() depuis prospection_admin."""
    try:
        from .database import SessionLocal
        from .api.routes.prospection_admin import run_due_targets
        db = SessionLocal()
        try:
            run_due_targets(db)
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

        # Réponse 1 — bot répond au sender (ton formel)
        _WARMING_REPLIES = [
            "Bonjour,\n\nMerci pour votre message, je l'ai bien reçu.\n\nJe vous recontacte dès que possible.\n\nCordialement",
            "Bonjour,\n\nBien reçu, merci.\n\nJe reviendrai vers vous prochainement.\n\nBonne journée",
            "Bonjour,\n\nMerci de votre retour. Je prends note et vous réponds dans les meilleurs délais.\n\nCordialement",
            "Bonjour,\n\nMessage bien reçu. Je vous confirme que je traiterai votre demande très prochainement.\n\nBien à vous",
            "Bonjour,\n\nMerci pour ces informations. Je reviens vers vous rapidement.\n\nCordialement",
            "Bonjour,\n\nBien noté, merci de votre message. Je vous tiens informé.\n\nBonne journée",
            "Bonjour,\n\nReçu 5/5. Je transfère votre message aux bonnes personnes.\n\nCordialement",
            "Bonjour,\n\nMerci, c'est noté. On se recontacte très prochainement.\n\nBien à vous",
        ]

        # Réponse 2 — sender relance (ton plus court, ~40% des cas)
        _WARMING_FOLLOWUPS = [
            "Merci pour votre réponse rapide.\n\nJe reste disponible si vous avez des questions.\n\nBonne journée",
            "Parfait, merci.\n\nN'hésitez pas à me contacter si besoin.\n\nCordialement",
            "Très bien, j'attends de vos nouvelles.\n\nBonne continuation",
            "Merci ! À bientôt.",
            "Super, on fait comme ça.\n\nBonne journée à vous",
            "D'accord, merci pour le retour.\n\nCordialement",
            "OK, noté. Merci !",
            "Bien reçu, à très vite.",
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
                                # Le sender qui répond est au hasard parmi les senders warming
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
                if str(now.weekday()) not in configured_days:
                    return
                if now.hour != cfg.hour_utc:
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

    except Exception as e:
        log.error("_job_auto_enrich: %s", e)


def _job_provision_leads(force: bool = False):
    """
    Fourniture automatique de X leads en file ContactDB.
    Vérifie toutes les heures si la config (jour + heure UTC) correspond.
    Si force=True : ignore active/jour/heure (pour test manuel).
    Ordre : segments SireneSegmentDB par score DESC, suspects non encore provisionnés.
    """
    try:
        from datetime import datetime, timedelta
        from .database import SessionLocal
        from .models import LeadProvisioningConfigDB, SireneSuspectDB, SireneSegmentDB, ContactDB

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
                configured_days = [d.strip() for d in (cfg.days or "").split(",") if d.strip()]
                if str(now.weekday()) not in configured_days:
                    return
                if now.hour != cfg.hour_utc:
                    return
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
                    .limit(remaining)
                    .all()
                )

                for s in suspects:
                    contact = ContactDB(
                        company_name=s.raison_sociale,
                        city=s.ville,
                        profession=s.profession_id,
                        status="SUSPECT",
                        notes=f"SIRENE auto — dept:{s.departement or ''} NAF:{s.code_naf or ''}",
                    )
                    db.add(contact)
                    s.provisioned_at = now
                    provisioned += 1
                    remaining -= 1

            cfg.last_run = now
            cfg.last_count = provisioned
            db.commit()
            log.info("provision_leads : %d lead(s) ajoutés en ContactDB", provisioned)

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
