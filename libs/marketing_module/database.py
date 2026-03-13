"""
MARKETING_MODULE — Database layer
SQLite + SQLAlchemy. Path configurable via MKT_DB_PATH env var.
All queries scoped by project_id.
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    Base, BounceType, CampaignDB, CampaignSequenceDB, CampaignSequenceStepDB,
    CloserApplicationDB, CloserDB, CommissionDB, CommissionStatus, ComplianceRuleDB,
    ContactDB, DeliveryStatus, MeetingDB, MeetingStatus, ProspectDeliveryDB,
    ProspectJourneyDB, ReplyStatus, ReputationStatus, RotationStrategyDB,
    SendingDomainDB, SendingMailboxDB, SlotDB, SlotStatus, SocialAccountDB, SocialPostDB,
    SocialPostStatus, TaskDB, WarmupStrategyDB, WarmupStatus,
)

_DB_PATH = os.getenv("MKT_DB_PATH", "marketing.db")
_engine = create_engine(f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def init_db():
    Base.metadata.create_all(bind=_engine)
    _migrate_existing_tables()
    db = SessionLocal()
    try:
        _seed_default_sequence(db)
    finally:
        db.close()


def _migrate_existing_tables():
    """Ajoute les colonnes manquantes sur les tables existantes (SQLite ALTER TABLE)."""
    migrations = [
        ("closers",             "contact_id",           "TEXT"),
        ("closers",             "token",                "TEXT"),
        ("closers",             "first_name",           "TEXT"),
        ("closers",             "last_name",            "TEXT"),
        ("closers",             "date_of_birth",        "TEXT"),
        ("meetings",            "rescheduled_from_id",  "TEXT"),
        ("meetings",            "outcome",              "TEXT"),
        ("meetings",            "commission_rate",      "REAL"),
        ("meetings",            "commission_amount",    "REAL"),
        ("prospect_deliveries", "landing_visited_at",   "DATETIME"),
        ("prospect_deliveries", "calendly_clicked_at",  "DATETIME"),
        ("slots",               "calendar_event_id",    "TEXT"),
        ("slots",               "notes",                "TEXT"),
    ]
    with _engine.connect() as conn:
        for table, col, col_type in migrations:
            try:
                conn.execute(__import__("sqlalchemy").text(
                    f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                ))
                conn.commit()
            except Exception:
                pass  # colonne déjà existante


_PROJECT_ID = os.getenv("MKT_PROJECT_ID", "presence_ia")

_DEFAULT_SEQUENCE_STEPS = [
    {"step_order": 1, "delay_days": 0,  "channel": "email",
     "subject_template": "Les IA recommandent vos concurrents a {city}",
     "body_template": (
         "Bonjour,\n\nNous avons verifie ce que voient vos prospects lorsqu'ils demandent a leur IA :\n\n"
         "\"Quel {profession} recommandez-vous a {city} ?\"\n\nCertaines entreprises sont recommandees.\n\n"
         "Vous pouvez voir ce que l'IA affiche ici :\n{landing_url}\n\nBonne journee,\nPresence IA")},
    {"step_order": 2, "delay_days": 1,  "channel": "sms",
     "subject_template": None,
     "body_template": (
         "Bonjour, nous avons analyse ce que les IA affichent pour un {profession} a {city}. "
         "Voici la page : {landing_url} - Presence IA")},
    {"step_order": 3, "delay_days": 3,  "channel": "email",
     "subject_template": "Voici ce que voient vos prospects sur les IA",
     "body_template": (
         "Bonjour,\n\nQuand quelqu'un cherche un {profession} a {city} sur ChatGPT ou Gemini,\n"
         "certaines entreprises sont proposees en priorite.\n\n"
         "Votre entreprise n'apparait pas actuellement dans ces reponses.\n\n"
         "Voici la page personnalisee :\n{landing_url}\n\n"
         "Nous pouvons vous expliquer cela en 20 minutes si vous le souhaitez.")},
    {"step_order": 4, "delay_days": 5,  "channel": "sms",
     "subject_template": None,
     "body_template": (
         "Bonjour, petit rappel : la page montrant les resultats des IA pour {city} "
         "est toujours disponible. {landing_url} - Presence IA")},
    {"step_order": 5, "delay_days": 7,  "channel": "email",
     "subject_template": "Votre analyse est toujours disponible",
     "body_template": (
         "Bonjour,\n\nNous avions prepare une page montrant ce que les IA affichent\n"
         "lorsqu'un prospect cherche un {profession} a {city}.\n\n"
         "La page est toujours accessible ici :\n{landing_url}\n\n"
         "Si vous voulez comprendre pourquoi certaines entreprises sont citees\n"
         "et comment y apparaitre, vous pouvez reserver un creneau.")},
    {"step_order": 6, "delay_days": 14, "channel": "email",
     "subject_template": "Dernier message concernant votre visibilite IA",
     "body_template": (
         "Bonjour,\n\nLes recommandations faites par les IA deviennent\n"
         "un nouveau canal d'acquisition pour les entreprises locales.\n\n"
         "Nous avons analyse ce qui apparait actuellement pour {city}.\n\n"
         "Voici la page :\n{landing_url}\n\n"
         "Si le sujet vous interesse, vous pouvez reserver un audit gratuit\n"
         "pour voir comment ameliorer votre visibilite.")},
]


def _seed_default_sequence(db: Session):
    """Cree la sequence de prospection par defaut si elle n'existe pas."""
    existing = db.query(CampaignSequenceDB).filter_by(
        project_id=_PROJECT_ID, name="Prospection couvreurs"
    ).first()
    if existing:
        return

    # Campagne par defaut (SQLite n'enforce pas les FK sans PRAGMA)
    campaign = db.query(CampaignDB).filter_by(
        project_id=_PROJECT_ID, name="Prospection par defaut"
    ).first()
    if not campaign:
        campaign = CampaignDB(
            project_id=_PROJECT_ID,
            name="Prospection par defaut",
            channels=["email", "sms"],
            status="active",
        )
        db.add(campaign)
        db.flush()

    seq = CampaignSequenceDB(
        project_id=_PROJECT_ID,
        campaign_id=campaign.id,
        name="Prospection couvreurs",
        stop_on_reply=True,
    )
    db.add(seq)
    db.flush()

    for step_data in _DEFAULT_SEQUENCE_STEPS:
        db.add(CampaignSequenceStepDB(sequence_id=seq.id, **step_data))

    db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── SendingDomain ──────────────────────────────────────────────────────────────

def db_create_domain(db: Session, data: dict) -> SendingDomainDB:
    obj = SendingDomainDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_domains(db: Session, project_id: str, active_only: bool = False) -> list[SendingDomainDB]:
    q = db.query(SendingDomainDB).filter_by(project_id=project_id)
    if active_only:
        q = q.filter_by(is_active=True)
    return q.all()

def db_get_domain(db: Session, domain_id: str) -> Optional[SendingDomainDB]:
    return db.query(SendingDomainDB).filter_by(id=domain_id).first()

def db_get_domain_by_name(db: Session, name: str) -> Optional[SendingDomainDB]:
    return db.query(SendingDomainDB).filter_by(name=name).first()

def db_update_domain(db: Session, domain_id: str, updates: dict) -> Optional[SendingDomainDB]:
    obj = db_get_domain(db, domain_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj


# ── SendingMailbox ─────────────────────────────────────────────────────────────

def db_create_mailbox(db: Session, data: dict) -> SendingMailboxDB:
    obj = SendingMailboxDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_mailboxes(db: Session, project_id: str, domain_id: Optional[str] = None,
                      active_only: bool = False) -> list[SendingMailboxDB]:
    q = db.query(SendingMailboxDB).filter_by(project_id=project_id)
    if domain_id:
        q = q.filter_by(domain_id=domain_id)
    if active_only:
        q = q.filter_by(is_active=True)
    return q.all()

def db_get_mailbox(db: Session, mailbox_id: str) -> Optional[SendingMailboxDB]:
    return db.query(SendingMailboxDB).filter_by(id=mailbox_id).first()

def db_update_mailbox(db: Session, mailbox_id: str, updates: dict) -> Optional[SendingMailboxDB]:
    obj = db_get_mailbox(db, mailbox_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj

def db_increment_sent(db: Session, mailbox_id: str):
    obj = db_get_mailbox(db, mailbox_id)
    if obj:
        obj.sent_today     = (obj.sent_today or 0) + 1
        obj.sent_this_hour = (obj.sent_this_hour or 0) + 1
        obj.last_send_at   = datetime.utcnow()
        db.commit()

def db_reset_daily_counters(db: Session, project_id: Optional[str] = None):
    q = db.query(SendingMailboxDB)
    if project_id:
        q = q.filter_by(project_id=project_id)
    q.update({"sent_today": 0, "sent_this_hour": 0})
    db.commit()


# ── WarmupStrategy ─────────────────────────────────────────────────────────────

def db_create_warmup(db: Session, data: dict) -> WarmupStrategyDB:
    obj = WarmupStrategyDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_warmups(db: Session, project_id: str) -> list[WarmupStrategyDB]:
    return db.query(WarmupStrategyDB).filter_by(project_id=project_id).all()

def db_get_warmup(db: Session, warmup_id: str) -> Optional[WarmupStrategyDB]:
    return db.query(WarmupStrategyDB).filter_by(id=warmup_id).first()

def db_update_warmup(db: Session, warmup_id: str, updates: dict) -> Optional[WarmupStrategyDB]:
    obj = db_get_warmup(db, warmup_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


# ── RotationStrategy ───────────────────────────────────────────────────────────

def db_create_rotation(db: Session, data: dict) -> RotationStrategyDB:
    obj = RotationStrategyDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_rotations(db: Session, project_id: str) -> list[RotationStrategyDB]:
    return db.query(RotationStrategyDB).filter_by(project_id=project_id).all()

def db_get_rotation(db: Session, rotation_id: str) -> Optional[RotationStrategyDB]:
    return db.query(RotationStrategyDB).filter_by(id=rotation_id).first()

def db_update_rotation(db: Session, rotation_id: str, updates: dict) -> Optional[RotationStrategyDB]:
    obj = db_get_rotation(db, rotation_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


# ── Campaign ───────────────────────────────────────────────────────────────────

def db_create_campaign(db: Session, data: dict) -> CampaignDB:
    obj = CampaignDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_campaigns(db: Session, project_id: str, status: Optional[str] = None) -> list[CampaignDB]:
    q = db.query(CampaignDB).filter_by(project_id=project_id)
    if status:
        q = q.filter_by(status=status)
    return q.all()

def db_get_campaign(db: Session, campaign_id: str) -> Optional[CampaignDB]:
    return db.query(CampaignDB).filter_by(id=campaign_id).first()

def db_update_campaign(db: Session, campaign_id: str, updates: dict) -> Optional[CampaignDB]:
    obj = db_get_campaign(db, campaign_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj


# ── Sequence & Steps ───────────────────────────────────────────────────────────

def db_create_sequence(db: Session, data: dict) -> CampaignSequenceDB:
    obj = CampaignSequenceDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_sequences(db: Session, project_id: str,
                      campaign_id: Optional[str] = None) -> list[CampaignSequenceDB]:
    q = db.query(CampaignSequenceDB).filter_by(project_id=project_id)
    if campaign_id:
        q = q.filter_by(campaign_id=campaign_id)
    return q.all()

def db_get_sequence(db: Session, sequence_id: str) -> Optional[CampaignSequenceDB]:
    return db.query(CampaignSequenceDB).filter_by(id=sequence_id).first()

def db_update_sequence(db: Session, sequence_id: str, updates: dict) -> Optional[CampaignSequenceDB]:
    obj = db_get_sequence(db, sequence_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

# Aliases pour la compatibilité avec les routes
def db_create_sequence_step(db: Session, data: dict) -> CampaignSequenceStepDB:
    obj = CampaignSequenceStepDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

db_create_step = db_create_sequence_step  # alias

def db_list_sequence_steps(db: Session, sequence_id: str) -> list[CampaignSequenceStepDB]:
    return (db.query(CampaignSequenceStepDB)
            .filter_by(sequence_id=sequence_id)
            .order_by(CampaignSequenceStepDB.step_number)
            .all())

db_list_steps = db_list_sequence_steps  # alias

def db_get_sequence_step(db: Session, step_id: str) -> Optional[CampaignSequenceStepDB]:
    return db.query(CampaignSequenceStepDB).filter_by(id=step_id).first()

db_get_step = db_get_sequence_step  # alias

def db_update_sequence_step(db: Session, step_id: str, updates: dict) -> Optional[CampaignSequenceStepDB]:
    obj = db_get_sequence_step(db, step_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

def db_delete_sequence_step(db: Session, step_id: str) -> bool:
    obj = db_get_sequence_step(db, step_id)
    if not obj: return False
    db.delete(obj); db.commit()
    return True

def db_delete_sequence(db: Session, sequence_id: str) -> bool:
    obj = db_get_sequence(db, sequence_id)
    if not obj: return False
    db.delete(obj); db.commit()
    return True


# ── ProspectDelivery ───────────────────────────────────────────────────────────

def db_create_delivery(db: Session, data: dict) -> ProspectDeliveryDB:
    obj = ProspectDeliveryDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_get_delivery(db: Session, delivery_id: str) -> Optional[ProspectDeliveryDB]:
    return db.query(ProspectDeliveryDB).filter_by(id=delivery_id).first()

def db_list_deliveries(db: Session, campaign_id: str,
                       prospect_id: Optional[str] = None) -> list[ProspectDeliveryDB]:
    q = db.query(ProspectDeliveryDB).filter_by(campaign_id=campaign_id)
    if prospect_id:
        q = q.filter_by(prospect_id=prospect_id)
    return q.all()

def db_update_delivery(db: Session, delivery_id: str, updates: dict) -> Optional[ProspectDeliveryDB]:
    obj = db_get_delivery(db, delivery_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj

def db_prospect_already_contacted(db: Session, campaign_id: str, prospect_id: str,
                                   sequence_step_id: str) -> bool:
    return db.query(ProspectDeliveryDB).filter_by(
        campaign_id=campaign_id,
        prospect_id=prospect_id,
        sequence_step_id=sequence_step_id,
    ).first() is not None

def db_prospect_replied(db: Session, campaign_id: str, prospect_id: str) -> bool:
    return db.query(ProspectDeliveryDB).filter(
        ProspectDeliveryDB.campaign_id == campaign_id,
        ProspectDeliveryDB.prospect_id == prospect_id,
        ProspectDeliveryDB.reply_status != ReplyStatus.none,
    ).first() is not None


# ── ComplianceRule ─────────────────────────────────────────────────────────────

def db_create_rule(db: Session, data: dict) -> ComplianceRuleDB:
    obj = ComplianceRuleDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_rules(db: Session, project_id: str, scope: Optional[str] = None) -> list[ComplianceRuleDB]:
    q = db.query(ComplianceRuleDB).filter_by(project_id=project_id, is_active=True)
    if scope:
        q = q.filter_by(scope=scope)
    return q.all()

def db_get_rule(db: Session, rule_id: str) -> Optional[ComplianceRuleDB]:
    return db.query(ComplianceRuleDB).filter_by(id=rule_id).first()

def db_update_rule(db: Session, rule_id: str, updates: dict) -> Optional[ComplianceRuleDB]:
    obj = db_get_rule(db, rule_id)
    if not obj:
        return None
    for k, v in updates.items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


# ── SocialAccount ──────────────────────────────────────────────────────────────

def db_create_social_account(db: Session, data: dict) -> SocialAccountDB:
    obj = SocialAccountDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_social_accounts(db: Session, project_id: str,
                             platform: Optional[str] = None) -> list[SocialAccountDB]:
    q = db.query(SocialAccountDB).filter_by(project_id=project_id, is_active=True)
    if platform:
        q = q.filter_by(platform=platform)
    return q.all()

def db_get_social_account(db: Session, account_id: str) -> Optional[SocialAccountDB]:
    return db.query(SocialAccountDB).filter_by(id=account_id).first()

def db_update_social_account(db: Session, account_id: str, updates: dict) -> Optional[SocialAccountDB]:
    obj = db_get_social_account(db, account_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj


# ── SocialPost ─────────────────────────────────────────────────────────────────

def db_create_social_post(db: Session, data: dict) -> SocialPostDB:
    obj = SocialPostDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_social_posts(db: Session, project_id: str,
                          account_id: Optional[str] = None,
                          status: Optional[str] = None) -> list[SocialPostDB]:
    q = db.query(SocialPostDB).filter_by(project_id=project_id)
    if account_id:
        q = q.filter_by(account_id=account_id)
    if status:
        q = q.filter_by(status=status)
    return q.all()

def db_get_social_post(db: Session, post_id: str) -> Optional[SocialPostDB]:
    return db.query(SocialPostDB).filter_by(id=post_id).first()

def db_update_social_post(db: Session, post_id: str, updates: dict) -> Optional[SocialPostDB]:
    obj = db_get_social_post(db, post_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj


# ── Closer ─────────────────────────────────────────────────────────────────────

def db_create_closer(db: Session, data: dict) -> CloserDB:
    obj = CloserDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_closers(db: Session, project_id: str, active_only: bool = True) -> list[CloserDB]:
    q = db.query(CloserDB).filter_by(project_id=project_id)
    if active_only:
        q = q.filter_by(is_active=True)
    return q.all()

def db_get_closer(db: Session, closer_id: str) -> Optional[CloserDB]:
    return db.query(CloserDB).filter_by(id=closer_id).first()

def db_update_closer(db: Session, closer_id: str, updates: dict) -> Optional[CloserDB]:
    obj = db_get_closer(db, closer_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj


# ── Meeting ────────────────────────────────────────────────────────────────────

def db_create_meeting(db: Session, data: dict) -> MeetingDB:
    obj = MeetingDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_meetings(db: Session, project_id: str,
                     closer_id: Optional[str] = None,
                     status: Optional[str] = None) -> list[MeetingDB]:
    q = db.query(MeetingDB).filter_by(project_id=project_id)
    if closer_id:
        q = q.filter_by(closer_id=closer_id)
    if status:
        q = q.filter_by(status=status)
    return q.all()

def db_get_meeting(db: Session, meeting_id: str) -> Optional[MeetingDB]:
    return db.query(MeetingDB).filter_by(id=meeting_id).first()

def db_update_meeting(db: Session, meeting_id: str, updates: dict) -> Optional[MeetingDB]:
    obj = db_get_meeting(db, meeting_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj


# ── Commission ─────────────────────────────────────────────────────────────────

def db_create_commission(db: Session, data: dict) -> CommissionDB:
    obj = CommissionDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_commissions(db: Session, project_id: str,
                         closer_id: Optional[str] = None,
                         status: Optional[str] = None) -> list[CommissionDB]:
    q = db.query(CommissionDB).filter_by(project_id=project_id)
    if closer_id:
        q = q.filter_by(closer_id=closer_id)
    if status:
        q = q.filter_by(status=status)
    return q.all()

def db_get_commission(db: Session, commission_id: str) -> Optional[CommissionDB]:
    return db.query(CommissionDB).filter_by(id=commission_id).first()

def db_update_commission(db: Session, commission_id: str, updates: dict) -> Optional[CommissionDB]:
    obj = db_get_commission(db, commission_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj


# ── Task ───────────────────────────────────────────────────────────────────────

def db_create_task(db: Session, data: dict) -> TaskDB:
    obj = TaskDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_list_tasks(db: Session, project_id: str,
                  closer_id: Optional[str] = None,
                  prospect_id: Optional[str] = None) -> list[TaskDB]:
    q = db.query(TaskDB).filter_by(project_id=project_id)
    if closer_id:
        q = q.filter_by(closer_id=closer_id)
    if prospect_id:
        q = q.filter_by(prospect_id=prospect_id)
    return q.all()

def db_get_task(db: Session, task_id: str) -> Optional[TaskDB]:
    return db.query(TaskDB).filter_by(id=task_id).first()

def db_update_task(db: Session, task_id: str, updates: dict) -> Optional[TaskDB]:
    obj = db_get_task(db, task_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj


# ── Stats ──────────────────────────────────────────────────────────────────────

def db_campaign_stats(db: Session, campaign_id: str) -> dict:
    rows = db.query(ProspectDeliveryDB).filter_by(campaign_id=campaign_id).all()
    total   = len(rows)
    sent    = sum(1 for r in rows if r.delivery_status == DeliveryStatus.sent)
    bounced = sum(1 for r in rows if r.bounce_type != BounceType.none)
    opened  = sum(1 for r in rows if r.opened_at)
    clicked = sum(1 for r in rows if r.clicked_at)
    replied = sum(1 for r in rows if r.reply_status != ReplyStatus.none)
    return {
        "total": total, "sent": sent, "bounced": bounced,
        "opened": opened, "clicked": clicked, "replied": replied,
        "bounce_rate": round(bounced / sent, 4) if sent else 0,
        "open_rate":   round(opened  / sent, 4) if sent else 0,
        "reply_rate":  round(replied / sent, 4) if sent else 0,
    }

def db_mailbox_stats(db: Session, mailbox_id: str, window_hours: int = 24) -> dict:
    since = datetime.utcnow() - timedelta(hours=window_hours)
    rows  = db.query(ProspectDeliveryDB).filter(
        ProspectDeliveryDB.mailbox_id == mailbox_id,
        ProspectDeliveryDB.sent_at >= since,
    ).all()
    total   = len(rows)
    bounced = sum(1 for r in rows if r.bounce_type != BounceType.none)
    failed  = sum(1 for r in rows if r.delivery_status == DeliveryStatus.failed)
    return {
        "sent": total, "bounced": bounced, "failed": failed,
        "bounce_rate":  round(bounced / total, 4) if total else 0,
        "failure_rate": round(failed  / total, 4) if total else 0,
    }

# ── Contact ────────────────────────────────────────────────────────────────────

def db_create_contact(db: Session, data: dict) -> ContactDB:
    obj = ContactDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_get_contact(db: Session, contact_id: str) -> Optional[ContactDB]:
    return db.query(ContactDB).filter_by(id=contact_id).first()

def db_get_contact_by_email(db: Session, project_id: str, email: str) -> Optional[ContactDB]:
    return db.query(ContactDB).filter_by(project_id=project_id, email=email).first()

def db_list_contacts(db: Session, project_id: str) -> list[ContactDB]:
    return db.query(ContactDB).filter_by(project_id=project_id).order_by(ContactDB.created_at.desc()).all()

def db_update_contact(db: Session, contact_id: str, updates: dict) -> Optional[ContactDB]:
    obj = db_get_contact(db, contact_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj


# ── ProspectJourney ────────────────────────────────────────────────────────────

def db_get_journey(db: Session, project_id: str, prospect_id: str) -> Optional[ProspectJourneyDB]:
    return db.query(ProspectJourneyDB).filter_by(
        project_id=project_id, prospect_id=prospect_id
    ).first()

def db_upsert_journey(db: Session, project_id: str, prospect_id: str, updates: dict) -> ProspectJourneyDB:
    obj = db_get_journey(db, project_id, prospect_id)
    if not obj:
        obj = ProspectJourneyDB(project_id=project_id, prospect_id=prospect_id)
        db.add(obj)
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj

def db_list_journeys(db: Session, project_id: str, stage: Optional[str] = None) -> list[ProspectJourneyDB]:
    q = db.query(ProspectJourneyDB).filter_by(project_id=project_id)
    if stage:
        q = q.filter_by(stage=stage)
    return q.order_by(ProspectJourneyDB.updated_at.desc()).all()


# ── CloserApplication ──────────────────────────────────────────────────────────

def db_create_application(db: Session, data: dict) -> CloserApplicationDB:
    obj = CloserApplicationDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_get_application(db: Session, app_id: str) -> Optional[CloserApplicationDB]:
    return db.query(CloserApplicationDB).filter_by(id=app_id).first()

def db_get_application_by_token(db: Session, token: str) -> Optional[CloserApplicationDB]:
    return db.query(CloserApplicationDB).filter_by(token=token).first()

def db_list_applications(db: Session, project_id: str,
                          stage: Optional[str] = None) -> list[CloserApplicationDB]:
    q = db.query(CloserApplicationDB).filter_by(project_id=project_id)
    if stage:
        q = q.filter_by(stage=stage)
    return q.order_by(CloserApplicationDB.created_at.desc()).all()

def db_update_application(db: Session, app_id: str, updates: dict) -> Optional[CloserApplicationDB]:
    obj = db_get_application(db, app_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj


# ── Stats ──────────────────────────────────────────────────────────────────────

# ── Slot ───────────────────────────────────────────────────────────────────────

def db_create_slot(db: Session, data: dict) -> SlotDB:
    obj = SlotDB(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def db_get_slot(db: Session, slot_id: str) -> Optional[SlotDB]:
    return db.query(SlotDB).filter_by(id=slot_id).first()

def db_list_slots(db: Session, project_id: str,
                  from_dt: Optional[datetime] = None,
                  to_dt: Optional[datetime] = None,
                  status: Optional[str] = None) -> list[SlotDB]:
    q = db.query(SlotDB).filter_by(project_id=project_id)
    if from_dt:
        q = q.filter(SlotDB.starts_at >= from_dt)
    if to_dt:
        q = q.filter(SlotDB.starts_at <= to_dt)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(SlotDB.starts_at.asc()).all()

def db_update_slot(db: Session, slot_id: str, updates: dict) -> Optional[SlotDB]:
    obj = db_get_slot(db, slot_id)
    if not obj: return None
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj

def db_claim_slot(db: Session, slot_id: str, closer_id: str) -> tuple[bool, str]:
    """
    Tente de revendiquer un créneau pour un closer.
    Règles :
      - Le créneau doit être 'booked' (prospect inscrit, pas encore pris)
      - Le closer ne doit pas avoir un autre créneau à ±25 min (anti-consécutif)
    Retourne (success, message).
    """
    slot = db_get_slot(db, slot_id)
    if not slot:
        return False, "Créneau introuvable."
    if slot.status != SlotStatus.booked:
        return False, "Ce créneau n'est plus disponible."

    # Anti-consécutif : vérifie les créneaux déjà pris par ce closer
    from datetime import timedelta
    window = timedelta(minutes=25)
    conflict = db.query(SlotDB).filter(
        SlotDB.project_id == slot.project_id,
        SlotDB.closer_id  == closer_id,
        SlotDB.status     == SlotStatus.claimed,
        SlotDB.starts_at  >= slot.starts_at - window,
        SlotDB.starts_at  <= slot.starts_at + window,
    ).first()
    if conflict:
        return False, "Vous avez déjà un créneau dans cette plage horaire (règle anti-consécutif)."

    slot.closer_id  = closer_id
    slot.status     = SlotStatus.claimed
    slot.updated_at = datetime.utcnow()
    db.commit(); db.refresh(slot)
    return True, "Créneau réservé avec succès."

def db_delete_slot(db: Session, slot_id: str) -> bool:
    obj = db_get_slot(db, slot_id)
    if not obj: return False
    db.delete(obj); db.commit()
    return True

def db_sync_slot_from_meeting(db: Session, project_id: str, meeting: MeetingDB):
    """
    Crée ou met à jour un slot 'booked' quand un prospect réserve via Calendly.
    Si un slot existe déjà avec calendar_event_id, on le met à jour.
    """
    if not meeting.scheduled_at:
        return
    existing = None
    if meeting.calendly_event_id:
        existing = db.query(SlotDB).filter_by(
            project_id=project_id,
            calendar_event_id=meeting.calendly_event_id,
        ).first()
    if existing:
        existing.status     = SlotStatus.booked
        existing.meeting_id = meeting.id
        existing.updated_at = datetime.utcnow()
        db.commit()
    else:
        db_create_slot(db, {
            "project_id":        project_id,
            "starts_at":         meeting.scheduled_at,
            "ends_at":           meeting.scheduled_at + timedelta(minutes=20),
            "meeting_id":        meeting.id,
            "status":            SlotStatus.booked,
            "calendar_event_id": meeting.calendly_event_id,
        })


# ── Leaderboard ────────────────────────────────────────────────────────────────

def db_monthly_leaderboard(db: Session, project_id: str) -> list[dict]:
    """
    Classement mensuel des closers par deals signés ce mois-ci.
    Retourne une liste triée, avec le rang et le bonus éventuel.
    """
    from datetime import date
    today = date.today()
    month_start = datetime(today.year, today.month, 1)

    closers = db.query(CloserDB).filter_by(project_id=project_id, is_active=True).all()
    rows = []
    for c in closers:
        meetings = db.query(MeetingDB).filter(
            MeetingDB.project_id == project_id,
            MeetingDB.closer_id  == c.id,
            MeetingDB.status     == MeetingStatus.completed,
            MeetingDB.completed_at >= month_start,
        ).all()
        total_signed = len(meetings)
        total_revenue = sum(m.deal_value or 0 for m in meetings)
        total_commission = sum(
            (m.deal_value or 0) * (m.commission_rate or c.commission_rate)
            for m in meetings
        )
        rows.append({
            "closer_id":      c.id,
            "name":           c.name,
            "signed":         total_signed,
            "revenue":        total_revenue,
            "commission":     total_commission,
            "base_rate":      c.commission_rate,
        })

    rows.sort(key=lambda x: x["signed"], reverse=True)
    for i, row in enumerate(rows):
        row["rank"]  = i + 1
        row["bonus"] = i < 2 and row["signed"] > 0  # top 2 avec au moins 1 deal
        row["effective_rate"] = row["base_rate"] + (0.05 if row["bonus"] else 0)
    return rows


def db_closer_stats(db: Session, project_id: str, closer_id: str) -> dict:
    meetings    = db.list_meetings(project_id=project_id, closer_id=closer_id) if False else \
                  db.query(MeetingDB).filter_by(project_id=project_id, closer_id=closer_id).all()
    commissions = db.query(CommissionDB).filter_by(project_id=project_id, closer_id=closer_id).all()
    total_m     = len(meetings)
    completed   = sum(1 for m in meetings if m.status == MeetingStatus.completed)
    no_show     = sum(1 for m in meetings if m.status == MeetingStatus.no_show)
    total_earned = sum(c.amount for c in commissions if c.status in (CommissionStatus.approved, CommissionStatus.paid))
    total_paid   = sum(c.amount for c in commissions if c.status == CommissionStatus.paid)
    return {
        "meetings_total": total_m,
        "meetings_completed": completed,
        "meetings_no_show": no_show,
        "conversion_rate": round(completed / total_m, 4) if total_m else 0,
        "commissions_earned": total_earned,
        "commissions_paid": total_paid,
    }
