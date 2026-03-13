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
            from marketing_module.database import db_create_meeting, db_update_delivery
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
                db_create_meeting(mdb, {
                    "project_id":        "presence-ia",
                    "prospect_id":       prospect_id,
                    "campaign_id":       None,
                    "scheduled_at":      scheduled_at,
                    "status":            MeetingStatus.scheduled,
                    "calendly_event_id": calendly_event_id,
                    "calendly_event_uri": ev.get("uri", ""),
                    "notes":             invitees[0].get("name", ""),
                })

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
