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
    CloserDB, CommissionDB, CommissionStatus, ComplianceRuleDB, DeliveryStatus,
    MeetingDB, MeetingStatus, ProspectDeliveryDB, ReplyStatus, ReputationStatus,
    RotationStrategyDB, SendingDomainDB, SendingMailboxDB, SocialAccountDB,
    SocialPostDB, SocialPostStatus, TaskDB, WarmupStrategyDB, WarmupStatus,
)

_DB_PATH = os.getenv("MKT_DB_PATH", "marketing.db")
_engine = create_engine(f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def init_db():
    Base.metadata.create_all(bind=_engine)


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
