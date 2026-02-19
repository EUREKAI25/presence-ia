"""
Scheduler APScheduler — tâches périodiques PRESENCE_IA.

Jobs actifs :
- run_due_targets   : toutes les heures — prospection automatique Google Places
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

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
