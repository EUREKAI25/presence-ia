"""
V3 ↔ marketing_module bridge — tracking opens/clicks/bounces/Calendly.

Fonctionne en mode dégradé si marketing_module non disponible ou marketing.db vide.
Utilise le projet "presence-ia" (défini dans presence_ia_seed.json).
"""
import logging
from typing import Optional

log = logging.getLogger("v3.mkt")

PROJECT_ID = "presence-ia"
_cache: dict = {}   # campaign_id, step_id


def _mkt_db():
    try:
        from marketing_module.database import SessionLocal
        return SessionLocal()
    except Exception as e:
        log.debug("marketing_module DB non disponible: %s", e)
        return None


def _load_ids() -> tuple[str, str]:
    """Lit campaign_id + step_1_id depuis marketing.db (mis en cache)."""
    if "campaign_id" in _cache:
        return _cache["campaign_id"], _cache["step_id"]
    db = _mkt_db()
    if not db:
        return "", ""
    try:
        from marketing_module.models import (
            CampaignDB, CampaignSequenceDB, CampaignSequenceStepDB,
        )
        c = db.query(CampaignDB).filter_by(project_id=PROJECT_ID).first()
        if not c:
            log.info("marketing.db: aucune campagne pour '%s' — seed non chargé ?", PROJECT_ID)
            return "", ""
        seq = db.query(CampaignSequenceDB).filter_by(campaign_id=c.id).first()
        sid = ""
        if seq:
            step = (
                db.query(CampaignSequenceStepDB)
                .filter_by(sequence_id=seq.id)
                .order_by(CampaignSequenceStepDB.step_order)
                .first()
            )
            sid = step.id if step else ""
        _cache.update({"campaign_id": c.id, "step_id": sid})
        log.info("marketing.db chargé — campaign=%s step=%s", c.id[:8], sid[:8] if sid else "—")
        return c.id, sid
    except Exception as e:
        log.warning("_load_ids erreur: %s", e)
        return "", ""
    finally:
        db.close()


def create_delivery(prospect_token: str) -> Optional[str]:
    """
    Crée un ProspectDeliveryDB avant l'envoi.
    Retourne delivery_id (str UUID) ou None si indisponible.
    """
    campaign_id, step_id = _load_ids()
    if not campaign_id:
        return None
    db = _mkt_db()
    if not db:
        return None
    try:
        from marketing_module.database import db_create_delivery
        from marketing_module.models import Channel, DeliveryStatus
        from datetime import datetime
        d = db_create_delivery(db, {
            "project_id":       PROJECT_ID,
            "campaign_id":      campaign_id,
            "prospect_id":      prospect_token,
            "channel":          Channel.email,
            "sequence_step_id": step_id or None,
            "delivery_status":  DeliveryStatus.pending,
            "scheduled_at":     datetime.utcnow(),
        })
        return d.id
    except Exception as e:
        log.warning("create_delivery: %s", e)
        return None
    finally:
        db.close()


def create_sms_delivery(prospect_token: str) -> Optional[str]:
    """Idem pour SMS."""
    campaign_id, step_id = _load_ids()
    if not campaign_id:
        return None
    db = _mkt_db()
    if not db:
        return None
    try:
        from marketing_module.database import db_create_delivery
        from marketing_module.models import Channel, DeliveryStatus
        from datetime import datetime
        d = db_create_delivery(db, {
            "project_id":       PROJECT_ID,
            "campaign_id":      campaign_id,
            "prospect_id":      prospect_token,
            "channel":          Channel.sms,
            "sequence_step_id": step_id or None,
            "delivery_status":  DeliveryStatus.pending,
            "scheduled_at":     datetime.utcnow(),
        })
        return d.id
    except Exception as e:
        log.warning("create_sms_delivery: %s", e)
        return None
    finally:
        db.close()


def mark_sent(delivery_id: Optional[str], ok: bool, error: str = ""):
    """Met à jour le statut de livraison après envoi."""
    if not delivery_id:
        return
    db = _mkt_db()
    if not db:
        return
    try:
        from marketing_module.database import db_update_delivery
        from marketing_module.models import DeliveryStatus
        from datetime import datetime
        if ok:
            db_update_delivery(db, delivery_id, {
                "delivery_status": DeliveryStatus.sent,
                "sent_at":         datetime.utcnow(),
            })
        else:
            db_update_delivery(db, delivery_id, {
                "delivery_status": DeliveryStatus.failed,
                "error_message":   error or "Send failed",
            })
    except Exception as e:
        log.warning("mark_sent: %s", e)
    finally:
        db.close()


def record_open(delivery_id: str):
    """Enregistre une ouverture (appelé par le pixel de tracking)."""
    db = _mkt_db()
    if not db:
        return
    try:
        from marketing_module.database import db_update_delivery
        from datetime import datetime
        db_update_delivery(db, delivery_id, {"opened_at": datetime.utcnow()})
    except Exception as e:
        log.warning("record_open: %s", e)
    finally:
        db.close()


def record_click(delivery_id: str):
    """Enregistre un clic (appelé par le lien de tracking)."""
    db = _mkt_db()
    if not db:
        return
    try:
        from marketing_module.database import db_update_delivery
        from datetime import datetime
        db_update_delivery(db, delivery_id, {"clicked_at": datetime.utcnow()})
    except Exception as e:
        log.warning("record_click: %s", e)
    finally:
        db.close()


def _resolve_prospect_id(v3_token: str) -> str:
    """
    Les deliveries sont créées avec prospect_id = V3ProspectDB.token.
    Retourne directement le token (c'est l'identifiant unique).
    """
    return v3_token


def record_landing_visit(prospect_token: str):
    """Enregistre la visite de la landing personnalisée."""
    db = _mkt_db()
    if not db:
        return
    try:
        from marketing_module.database import db_update_delivery
        from marketing_module.models import ProspectDeliveryDB
        from datetime import datetime
        contact_id = _resolve_prospect_id(prospect_token)
        delivery = (
            db.query(ProspectDeliveryDB)
            .filter_by(project_id=PROJECT_ID, prospect_id=contact_id)
            .order_by(ProspectDeliveryDB.created_at.desc())
            .first()
        )
        if delivery and not delivery.landing_visited_at:
            db_update_delivery(db, delivery.id, {"landing_visited_at": datetime.utcnow()})
            log.info("record_landing_visit: token=%s contact=%s delivery=%s", prospect_token[:8], contact_id[:8], delivery.id[:8])
    except Exception as e:
        log.warning("record_landing_visit: %s", e)
    finally:
        db.close()


def record_calendly_click(prospect_token: str):
    """Enregistre un clic sur le bouton Calendly."""
    db = _mkt_db()
    if not db:
        return
    try:
        from marketing_module.database import db_update_delivery
        from marketing_module.models import ProspectDeliveryDB
        from datetime import datetime
        contact_id = _resolve_prospect_id(prospect_token)
        delivery = (
            db.query(ProspectDeliveryDB)
            .filter_by(project_id=PROJECT_ID, prospect_id=contact_id)
            .order_by(ProspectDeliveryDB.created_at.desc())
            .first()
        )
        if delivery and not delivery.calendly_clicked_at:
            db_update_delivery(db, delivery.id, {"calendly_clicked_at": datetime.utcnow()})
            log.info("record_calendly_click: token=%s contact=%s delivery=%s", prospect_token[:8], contact_id[:8], delivery.id[:8])
    except Exception as e:
        log.warning("record_calendly_click: %s", e)
    finally:
        db.close()


def invalidate_cache():
    """Force le rechargement des IDs (utile après seed_loader)."""
    _cache.clear()
