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


_SIRENE_STATE: dict = {"running": False, "done": True, "pending": 0, "done_segs": 0, "total_segs": 0, "suspects": 0}

def _sirene_qualify_state() -> dict:
    return dict(_SIRENE_STATE)

def run_sirene_qualify(max_per_naf: int = 200):
    """Qualification SIRENE par segments — lancé à la demande depuis l'admin."""
    global _SIRENE_STATE
    _SIRENE_STATE = {"running": True, "done": False, "pending": 0, "done_segs": 0, "total_segs": 0, "suspects": 0}
    try:
        from .database import SessionLocal
        from .sirene import generate_segments, run_next_segment, segments_stats
        log.info("[SIRENE] Démarrage qualification par segments...")
        db = SessionLocal()
        try:
            generated = generate_segments(db)
            log.info(f"[SIRENE] {generated} nouveaux segments générés")
            total_inserted = 0
            while True:
                result = run_next_segment(db)
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
