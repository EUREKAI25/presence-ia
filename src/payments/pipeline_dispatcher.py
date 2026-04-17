"""
Dispatcher de pipelines — lancé après paiement Stripe confirmé.
Mappe offre → pipeline et exécute de manière asynchrone.
"""

import logging
import os
from datetime import datetime

log = logging.getLogger(__name__)

# ── Mapping offre → type de pipeline ─────────────────────────────────────────

def resolve_pipeline_type(offer_name: str) -> str:
    """Détermine le pipeline à lancer depuis le nom de l'offre."""
    name = (offer_name or "").lower()
    if "domination" in name:
        return "domination"
    if "implantation" in name:
        return "implantation"
    return "methode"


# ── Dispatcher principal (appelé en BackgroundTask) ───────────────────────────

def run_pipeline_job(job_id: str, db_url: str) -> None:
    """
    Charge le job depuis la DB, lance le bon pipeline, met à jour le statut.
    Doit être appelé dans un thread séparé (BackgroundTasks).
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from ..models import PipelineJobDB

    engine  = create_engine(db_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    db      = Session()

    try:
        job = db.query(PipelineJobDB).filter(PipelineJobDB.id == job_id).first()
        if not job:
            log.error("PipelineJob %s introuvable", job_id)
            return

        job.status = "running"
        db.commit()

        result = _dispatch(job)

        job.status           = "done"
        job.score            = result.get("score_data", {}).get("score")
        job.deliverable_path = _get_deliverable_path(result, job.pipeline_type)
        job.completed_at     = datetime.utcnow()
        db.commit()

        _send_confirmation_email(job, result)
        log.info("PipelineJob %s done — %s — score=%s", job_id, job.pipeline_type, job.score)

    except Exception as exc:
        log.exception("PipelineJob %s erreur", job_id)
        try:
            job.status       = "error"
            job.error        = str(exc)[:500]
            job.completed_at = datetime.utcnow()
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _dispatch(job) -> dict:
    """Lance le pipeline selon pipeline_type et retourne le résultat complet."""
    params = dict(
        company_name  = job.company_name,
        city          = job.city,
        business_type = job.business_type,
        website       = job.website or "",
    )

    if job.pipeline_type == "domination":
        from ..domination_ia.pipeline import run_pipeline
        return run_pipeline(**params)

    if job.pipeline_type == "implantation":
        from ..implantation_ia.pipeline import run_pipeline
        return run_pipeline(**params)

    # methode (défaut)
    from ..methode_ia.pipeline import run_pipeline
    return run_pipeline(**params)


def _get_deliverable_path(result: dict, pipeline_type: str) -> str | None:
    if pipeline_type == "domination":
        return result.get("domination_deliverable_path")
    if pipeline_type == "implantation":
        return result.get("deliverable_path") or result.get("implantation_deliverable_path")
    return result.get("deliverable_path")


def _send_confirmation_email(job, result: dict) -> None:
    """Envoie un email 'livrable prêt' au client. Silencieux si Brevo absent."""
    if not job.email:
        return
    try:
        from ..api.routes.v3 import _send_brevo_email

        base_url = os.getenv("BASE_URL", "https://presence-ia.com")
        pipeline_labels = {
            "methode":      "Méthode Présence IA",
            "implantation": "Implantation IA",
            "domination":   "Domination IA",
        }
        label = pipeline_labels.get(job.pipeline_type, job.offer_name or "Présence IA")
        score = job.score

        subject = f"✅ Votre livrable {label} est prêt"
        body = (
            f"Bonjour,\n\n"
            f"Votre livrable **{label}** vient d'être généré.\n\n"
            f"Score de visibilité IA actuel : {round(score, 1) if score else '—'}/10\n\n"
            f"Votre rapport personnalisé est disponible dans votre espace client.\n"
            f"Si vous avez des questions, répondez directement à cet email.\n\n"
            f"L'équipe Présence IA"
        )
        _send_brevo_email(
            to_email=job.email,
            to_name=job.company_name,
            subject=subject,
            body=body,
        )
        log.info("Email livrable envoyé à %s", job.email)
    except Exception as e:
        log.warning("Email livrable non envoyé : %s", e)


def send_payment_received_email(
    email: str,
    company_name: str,
    offer_name: str,
    pipeline_type: str,
) -> None:
    """Envoie email 'paiement reçu, analyse en cours' immédiatement après paiement."""
    if not email:
        return
    try:
        from ..api.routes.v3 import _send_brevo_email

        delays = {
            "methode":      "3 à 5 minutes",
            "implantation": "5 à 8 minutes",
            "domination":   "8 à 12 minutes",
        }
        delay = delays.get(pipeline_type, "quelques minutes")

        subject = f"⚡ Paiement reçu — {offer_name} — Analyse en cours"
        body = (
            f"Bonjour {company_name},\n\n"
            f"Nous avons bien reçu votre paiement pour l'offre **{offer_name}**.\n\n"
            f"Votre analyse IA personnalisée est en cours de génération.\n"
            f"Délai estimé : {delay}.\n\n"
            f"Vous recevrez automatiquement votre livrable complet dès que l'analyse sera terminée.\n\n"
            f"L'équipe Présence IA"
        )
        _send_brevo_email(
            to_email=email,
            to_name=company_name,
            subject=subject,
            body=body,
        )
        log.info("Email paiement reçu envoyé à %s", email)
    except Exception as e:
        log.warning("Email paiement reçu non envoyé : %s", e)
