"""
MARKETING_MODULE — Unified Models
SQLAlchemy ORM + Pydantic schemas.
Covers: email, SMS, social, CRM (closers, meetings, commissions, tasks).
No hardcoded business data. All scoped by project_id.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                        Integer, String, Text)
from sqlalchemy.orm import DeclarativeBase, relationship


def _uid() -> str:
    return str(uuid.uuid4())

def _now() -> datetime:
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class Channel(str, Enum):
    email    = "email"
    sms      = "sms"
    whatsapp = "whatsapp"
    linkedin = "linkedin"
    instagram = "instagram"
    pinterest = "pinterest"
    tiktok    = "tiktok"
    facebook  = "facebook"
    twitter   = "twitter"

class DomainRole(str, Enum):
    sending = "sending"
    landing = "landing"
    mixed   = "mixed"

class DnsStatus(str, Enum):
    unknown = "unknown"
    valid   = "valid"
    invalid = "invalid"
    pending = "pending"

class WarmupStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed   = "completed"
    paused      = "paused"
    failed      = "failed"

class ReputationStatus(str, Enum):
    unknown     = "unknown"
    healthy     = "healthy"
    degraded    = "degraded"
    at_risk     = "at_risk"
    blacklisted = "blacklisted"

class AuthMode(str, Enum):
    plain   = "plain"
    oauth2  = "oauth2"
    api_key = "api_key"

class RotationAlgorithm(str, Enum):
    round_robin     = "round_robin"
    weighted        = "weighted"
    least_used      = "least_used"
    random          = "random"
    health_priority = "health_priority"

class CampaignStatus(str, Enum):
    draft    = "draft"
    active   = "active"
    paused   = "paused"
    stopped  = "stopped"
    archived = "archived"

class DeliveryStatus(str, Enum):
    pending  = "pending"
    sent     = "sent"
    failed   = "failed"
    bounced  = "bounced"
    deferred = "deferred"

class ReplyStatus(str, Enum):
    none     = "none"
    positive = "positive"
    negative = "negative"
    neutral  = "neutral"
    ooo      = "ooo"

class BounceType(str, Enum):
    none = "none"
    soft = "soft"
    hard = "hard"

class ComplianceScope(str, Enum):
    mailbox  = "mailbox"
    domain   = "domain"
    campaign = "campaign"
    global_  = "global"

class ComplianceAction(str, Enum):
    alert         = "alert"
    pause_mailbox = "pause_mailbox"
    pause_domain  = "pause_domain"
    stop_campaign = "stop_campaign"

class SocialPostStatus(str, Enum):
    draft      = "draft"
    scheduled  = "scheduled"
    publishing = "publishing"
    published  = "published"
    failed     = "failed"
    cancelled  = "cancelled"

class MeetingStatus(str, Enum):
    scheduled = "scheduled"
    completed = "completed"
    no_show   = "no_show"
    cancelled = "cancelled"

class CommissionStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    paid    = "paid"
    disputed = "disputed"

class TaskStatus(str, Enum):
    todo       = "todo"
    in_progress = "in_progress"
    done       = "done"
    cancelled  = "cancelled"


# ══════════════════════════════════════════════════════════════════════════════
# ORM — EMAIL INFRASTRUCTURE
# ══════════════════════════════════════════════════════════════════════════════

class SendingDomainDB(Base):
    __tablename__ = "sending_domains"
    id                 = Column(String, primary_key=True, default=_uid)
    project_id         = Column(String, nullable=False, index=True)
    name               = Column(String, nullable=False, unique=True)
    role               = Column(String, default=DomainRole.sending)
    provider           = Column(String, nullable=True)
    provider_domain_id = Column(String, nullable=True)
    spf_status         = Column(String, default=DnsStatus.unknown)
    dkim_status        = Column(String, default=DnsStatus.unknown)
    dmarc_status       = Column(String, default=DnsStatus.unknown)
    dns_checked_at     = Column(DateTime, nullable=True)
    warmup_status      = Column(String, default=WarmupStatus.not_started)
    reputation_status  = Column(String, default=ReputationStatus.unknown)
    is_active          = Column(Boolean, default=True)
    meta               = Column(JSON, default=dict)
    created_at         = Column(DateTime, default=_now)
    updated_at         = Column(DateTime, default=_now, onupdate=_now)
    mailboxes          = relationship("SendingMailboxDB", back_populates="domain", cascade="all, delete-orphan")


class SendingMailboxDB(Base):
    __tablename__ = "sending_mailboxes"
    id                = Column(String, primary_key=True, default=_uid)
    project_id        = Column(String, nullable=False, index=True)
    domain_id         = Column(String, ForeignKey("sending_domains.id"), nullable=False)
    local_part        = Column(String, nullable=False)
    email             = Column(String, nullable=False, unique=True)
    smtp_host         = Column(String, nullable=True)
    smtp_port         = Column(Integer, default=587)
    imap_host         = Column(String, nullable=True)
    imap_port         = Column(Integer, default=993)
    username          = Column(String, nullable=True)
    password_enc      = Column(String, nullable=True)
    auth_mode         = Column(String, default=AuthMode.plain)
    api_key_enc       = Column(String, nullable=True)
    daily_limit       = Column(Integer, default=50)
    hourly_limit      = Column(Integer, default=10)
    sent_today        = Column(Integer, default=0)
    sent_this_hour    = Column(Integer, default=0)
    warmup_status     = Column(String, default=WarmupStatus.not_started)
    warmup_day        = Column(Integer, default=0)
    reputation_status = Column(String, default=ReputationStatus.unknown)
    last_send_at      = Column(DateTime, nullable=True)
    is_active         = Column(Boolean, default=True)
    meta              = Column(JSON, default=dict)
    created_at        = Column(DateTime, default=_now)
    updated_at        = Column(DateTime, default=_now, onupdate=_now)
    domain            = relationship("SendingDomainDB", back_populates="mailboxes")
    deliveries        = relationship("ProspectDeliveryDB", back_populates="mailbox")


class WarmupStrategyDB(Base):
    __tablename__ = "warmup_strategies"
    id                  = Column(String, primary_key=True, default=_uid)
    project_id          = Column(String, nullable=False, index=True)
    name                = Column(String, nullable=False)
    ramp_schedule       = Column(JSON, default=list)
    max_daily_volume    = Column(Integer, default=50)
    reply_simulation    = Column(Boolean, default=False)
    auto_pause_on_issue = Column(Boolean, default=True)
    health_rules        = Column(JSON, default=dict)
    meta                = Column(JSON, default=dict)
    created_at          = Column(DateTime, default=_now)


class RotationStrategyDB(Base):
    __tablename__ = "rotation_strategies"
    id                    = Column(String, primary_key=True, default=_uid)
    project_id            = Column(String, nullable=False, index=True)
    name                  = Column(String, nullable=False)
    algorithm             = Column(String, default=RotationAlgorithm.round_robin)
    per_mailbox_daily_cap = Column(Integer, default=50)
    per_domain_daily_cap  = Column(Integer, default=200)
    cooldown_hours        = Column(Integer, default=0)
    failure_rules         = Column(JSON, default=dict)
    meta                  = Column(JSON, default=dict)
    created_at            = Column(DateTime, default=_now)
    campaigns             = relationship("CampaignDB", back_populates="rotation_strategy")


# ══════════════════════════════════════════════════════════════════════════════
# ORM — CAMPAIGNS & SEQUENCES (multi-channel)
# ══════════════════════════════════════════════════════════════════════════════

class CampaignDB(Base):
    __tablename__ = "campaigns"
    id                   = Column(String, primary_key=True, default=_uid)
    project_id           = Column(String, nullable=False, index=True)
    name                 = Column(String, nullable=False)
    channels             = Column(JSON, default=list)       # ["email", "sms"]
    target_segment       = Column(JSON, default=dict)
    landing_domain_id    = Column(String, ForeignKey("sending_domains.id"), nullable=True)
    rotation_strategy_id = Column(String, ForeignKey("rotation_strategies.id"), nullable=True)
    status               = Column(String, default=CampaignStatus.draft)
    daily_send_limit     = Column(Integer, default=100)
    track_opens          = Column(Boolean, default=True)
    track_clicks         = Column(Boolean, default=True)
    meta                 = Column(JSON, default=dict)
    created_at           = Column(DateTime, default=_now)
    updated_at           = Column(DateTime, default=_now, onupdate=_now)
    landing_domain       = relationship("SendingDomainDB", foreign_keys=[landing_domain_id])
    rotation_strategy    = relationship("RotationStrategyDB", back_populates="campaigns")
    sequences            = relationship("CampaignSequenceDB", back_populates="campaign", cascade="all, delete-orphan")
    deliveries           = relationship("ProspectDeliveryDB", back_populates="campaign")


class CampaignSequenceDB(Base):
    __tablename__ = "campaign_sequences"
    id            = Column(String, primary_key=True, default=_uid)
    project_id    = Column(String, nullable=False, index=True)
    campaign_id   = Column(String, ForeignKey("campaigns.id"), nullable=False)
    name          = Column(String, nullable=False)
    stop_on_reply = Column(Boolean, default=True)
    meta          = Column(JSON, default=dict)
    created_at    = Column(DateTime, default=_now)
    campaign      = relationship("CampaignDB", back_populates="sequences")
    steps         = relationship("CampaignSequenceStepDB", back_populates="sequence",
                                 order_by="CampaignSequenceStepDB.step_order",
                                 cascade="all, delete-orphan")


class CampaignSequenceStepDB(Base):
    __tablename__ = "campaign_sequence_steps"
    id               = Column(String, primary_key=True, default=_uid)
    sequence_id      = Column(String, ForeignKey("campaign_sequences.id"), nullable=False)
    step_order       = Column(Integer, nullable=False)
    delay_days       = Column(Integer, default=0)
    channel          = Column(String, default=Channel.email)
    subject_template = Column(Text, nullable=True)          # email only
    body_template    = Column(Text, nullable=False)
    trigger_rules    = Column(JSON, default=dict)
    meta             = Column(JSON, default=dict)
    created_at       = Column(DateTime, default=_now)
    sequence         = relationship("CampaignSequenceDB", back_populates="steps")


class ProspectDeliveryDB(Base):
    __tablename__ = "prospect_deliveries"
    id                  = Column(String, primary_key=True, default=_uid)
    project_id          = Column(String, nullable=False, index=True)
    campaign_id         = Column(String, ForeignKey("campaigns.id"), nullable=False)
    prospect_id         = Column(String, nullable=False)    # ID externe (projet consommateur)
    channel             = Column(String, default=Channel.email)
    mailbox_id          = Column(String, ForeignKey("sending_mailboxes.id"), nullable=True)
    social_account_id   = Column(String, ForeignKey("social_accounts.id"), nullable=True)
    sequence_step_id    = Column(String, ForeignKey("campaign_sequence_steps.id"), nullable=True)
    scheduled_at        = Column(DateTime, nullable=True)
    sent_at             = Column(DateTime, nullable=True)
    delivery_status     = Column(String, default=DeliveryStatus.pending)
    reply_status        = Column(String, default=ReplyStatus.none)
    bounce_type         = Column(String, default=BounceType.none)
    opened_at           = Column(DateTime, nullable=True)
    clicked_at          = Column(DateTime, nullable=True)
    provider_message_id = Column(String, nullable=True)
    error_message       = Column(Text, nullable=True)
    meta                = Column(JSON, default=dict)
    created_at          = Column(DateTime, default=_now)
    updated_at          = Column(DateTime, default=_now, onupdate=_now)
    campaign            = relationship("CampaignDB", back_populates="deliveries")
    mailbox             = relationship("SendingMailboxDB", back_populates="deliveries")
    social_account      = relationship("SocialAccountDB", back_populates="deliveries")


class ComplianceRuleDB(Base):
    __tablename__ = "compliance_rules"
    id                = Column(String, primary_key=True, default=_uid)
    project_id        = Column(String, nullable=False, index=True)
    name              = Column(String, nullable=False)
    scope             = Column(String, default=ComplianceScope.mailbox)
    rule_type         = Column(String, nullable=False)
    threshold         = Column(Float, nullable=False)
    window_hours      = Column(Integer, default=24)
    action_on_trigger = Column(String, default=ComplianceAction.alert)
    is_active         = Column(Boolean, default=True)
    meta              = Column(JSON, default=dict)
    created_at        = Column(DateTime, default=_now)


# ══════════════════════════════════════════════════════════════════════════════
# ORM — SOCIAL MEDIA
# ══════════════════════════════════════════════════════════════════════════════

class SocialAccountDB(Base):
    __tablename__ = "social_accounts"
    id              = Column(String, primary_key=True, default=_uid)
    project_id      = Column(String, nullable=False, index=True)
    platform        = Column(String, nullable=False)        # instagram, pinterest, tiktok…
    account_name    = Column(String, nullable=False)
    credentials_enc = Column(JSON, default=dict)            # {access_token, refresh_token, …}
    daily_post_limit = Column(Integer, default=5)
    posted_today    = Column(Integer, default=0)
    is_active       = Column(Boolean, default=True)
    meta            = Column(JSON, default=dict)
    created_at      = Column(DateTime, default=_now)
    updated_at      = Column(DateTime, default=_now, onupdate=_now)
    deliveries      = relationship("ProspectDeliveryDB", back_populates="social_account")
    posts           = relationship("SocialPostDB", back_populates="account")


class SocialPostDB(Base):
    __tablename__ = "social_posts"
    id           = Column(String, primary_key=True, default=_uid)
    project_id   = Column(String, nullable=False, index=True)
    campaign_id  = Column(String, ForeignKey("campaigns.id"), nullable=True)
    account_id   = Column(String, ForeignKey("social_accounts.id"), nullable=False)
    platform     = Column(String, nullable=False)
    content      = Column(Text, nullable=False)
    media_urls   = Column(JSON, default=list)
    hashtags     = Column(JSON, default=list)
    link         = Column(String, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    status       = Column(String, default=SocialPostStatus.draft)
    external_id  = Column(String, nullable=True)    # ID on the platform
    external_url = Column(String, nullable=True)    # URL of published post
    error        = Column(Text, nullable=True)
    meta         = Column(JSON, default=dict)
    created_at   = Column(DateTime, default=_now)
    updated_at   = Column(DateTime, default=_now, onupdate=_now)
    account      = relationship("SocialAccountDB", back_populates="posts")


# ══════════════════════════════════════════════════════════════════════════════
# ORM — CRM (Closers, Meetings, Commissions, Tasks)
# ══════════════════════════════════════════════════════════════════════════════

class CloserDB(Base):
    __tablename__ = "closers"
    id              = Column(String, primary_key=True, default=_uid)
    project_id      = Column(String, nullable=False, index=True)
    name            = Column(String, nullable=False)
    email           = Column(String, nullable=True)
    phone           = Column(String, nullable=True)
    commission_rate = Column(Float, default=0.18)       # 18%
    bonus_rate      = Column(Float, default=0.05)       # 5% bonus
    is_active       = Column(Boolean, default=True)
    meta            = Column(JSON, default=dict)
    created_at      = Column(DateTime, default=_now)
    updated_at      = Column(DateTime, default=_now, onupdate=_now)
    meetings        = relationship("MeetingDB", back_populates="closer")
    commissions     = relationship("CommissionDB", back_populates="closer")
    tasks           = relationship("TaskDB", back_populates="closer")


class MeetingDB(Base):
    __tablename__ = "meetings"
    id                 = Column(String, primary_key=True, default=_uid)
    project_id         = Column(String, nullable=False, index=True)
    prospect_id        = Column(String, nullable=False)     # ID externe
    closer_id          = Column(String, ForeignKey("closers.id"), nullable=True)
    campaign_id        = Column(String, ForeignKey("campaigns.id"), nullable=True)
    scheduled_at       = Column(DateTime, nullable=True)
    completed_at       = Column(DateTime, nullable=True)
    status             = Column(String, default=MeetingStatus.scheduled)
    calendly_event_id  = Column(String, nullable=True)
    calendly_event_uri = Column(String, nullable=True)
    deal_value         = Column(Float, nullable=True)       # montant deal si conclu
    notes              = Column(Text, nullable=True)
    meta               = Column(JSON, default=dict)
    created_at         = Column(DateTime, default=_now)
    updated_at         = Column(DateTime, default=_now, onupdate=_now)
    closer             = relationship("CloserDB", back_populates="meetings")
    commissions        = relationship("CommissionDB", back_populates="meeting")


class CommissionDB(Base):
    __tablename__ = "commissions"
    id          = Column(String, primary_key=True, default=_uid)
    project_id  = Column(String, nullable=False, index=True)
    closer_id   = Column(String, ForeignKey("closers.id"), nullable=False)
    meeting_id  = Column(String, ForeignKey("meetings.id"), nullable=True)
    amount      = Column(Float, nullable=False)
    rate        = Column(Float, nullable=False)
    deal_value  = Column(Float, nullable=True)
    status      = Column(String, default=CommissionStatus.pending)
    paid_at     = Column(DateTime, nullable=True)
    notes       = Column(Text, nullable=True)
    meta        = Column(JSON, default=dict)
    created_at  = Column(DateTime, default=_now)
    updated_at  = Column(DateTime, default=_now, onupdate=_now)
    closer      = relationship("CloserDB", back_populates="commissions")
    meeting     = relationship("MeetingDB", back_populates="commissions")


class TaskDB(Base):
    __tablename__ = "tasks"
    id          = Column(String, primary_key=True, default=_uid)
    project_id  = Column(String, nullable=False, index=True)
    prospect_id = Column(String, nullable=True)
    closer_id   = Column(String, ForeignKey("closers.id"), nullable=True)
    title       = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    due_at      = Column(DateTime, nullable=True)
    status      = Column(String, default=TaskStatus.todo)
    meta        = Column(JSON, default=dict)
    created_at  = Column(DateTime, default=_now)
    updated_at  = Column(DateTime, default=_now, onupdate=_now)
    closer      = relationship("CloserDB", back_populates="tasks")


# ══════════════════════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class EurkaiOutput(BaseModel):
    success: bool
    result: Any
    message: str
    error: Optional[dict] = None


# — Domains
class SendingDomainCreate(BaseModel):
    project_id: str
    name: str
    role: DomainRole = DomainRole.sending
    provider: Optional[str] = None
    meta: dict = {}

class SendingDomainOut(BaseModel):
    id: str; project_id: str; name: str; role: str; provider: Optional[str]
    spf_status: str; dkim_status: str; dmarc_status: str
    warmup_status: str; reputation_status: str; is_active: bool; created_at: datetime
    class Config: from_attributes = True


# — Mailboxes
class SendingMailboxCreate(BaseModel):
    project_id: str
    domain_id: str
    local_part: str
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    auth_mode: AuthMode = AuthMode.plain
    api_key: Optional[str] = None
    daily_limit: int = 50
    hourly_limit: int = 10
    meta: dict = {}

class SendingMailboxOut(BaseModel):
    id: str; project_id: str; domain_id: str; email: str; local_part: str
    daily_limit: int; hourly_limit: int; sent_today: int
    warmup_status: str; warmup_day: int; reputation_status: str
    is_active: bool; last_send_at: Optional[datetime]; created_at: datetime
    class Config: from_attributes = True


# — Strategies
class WarmupStrategyCreate(BaseModel):
    project_id: str
    name: str
    ramp_schedule: list = []
    max_daily_volume: int = 50
    reply_simulation: bool = False
    auto_pause_on_issue: bool = True
    health_rules: dict = {}
    meta: dict = {}

class RotationStrategyCreate(BaseModel):
    project_id: str
    name: str
    algorithm: RotationAlgorithm = RotationAlgorithm.round_robin
    per_mailbox_daily_cap: int = 50
    per_domain_daily_cap: int = 200
    cooldown_hours: int = 0
    failure_rules: dict = {}
    meta: dict = {}


# — Campaigns
class CampaignCreate(BaseModel):
    project_id: str
    name: str
    channels: list[str] = ["email"]
    target_segment: dict = {}
    landing_domain_id: Optional[str] = None
    rotation_strategy_id: Optional[str] = None
    daily_send_limit: int = 100
    track_opens: bool = True
    track_clicks: bool = True
    meta: dict = {}

class CampaignOut(BaseModel):
    id: str; project_id: str; name: str; channels: list
    status: str; daily_send_limit: int; created_at: datetime
    class Config: from_attributes = True


# — Sequences
class SequenceCreate(BaseModel):
    project_id: str
    campaign_id: str
    name: str
    stop_on_reply: bool = True
    meta: dict = {}

class SequenceStepCreate(BaseModel):
    sequence_id: str
    step_order: int
    delay_days: int = 0
    channel: Channel = Channel.email
    subject_template: Optional[str] = None
    body_template: str
    trigger_rules: dict = {}
    meta: dict = {}


# — Deliveries
class ScheduleSendInput(BaseModel):
    project_id: str
    campaign_id: str
    prospect_ids: list[str]
    sequence_step_id: str
    scheduled_at: Optional[datetime] = None

class DeliveryResultInput(BaseModel):
    delivery_id: str
    status: DeliveryStatus
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None

class BounceInput(BaseModel):
    delivery_id: str
    bounce_type: BounceType
    error_message: Optional[str] = None

class ReplyInput(BaseModel):
    delivery_id: str
    reply_status: ReplyStatus


# — Compliance
class ComplianceRuleCreate(BaseModel):
    project_id: str
    name: str
    scope: ComplianceScope = ComplianceScope.mailbox
    rule_type: str
    threshold: float
    window_hours: int = 24
    action_on_trigger: ComplianceAction = ComplianceAction.alert
    meta: dict = {}


# — Social
class SocialAccountCreate(BaseModel):
    project_id: str
    platform: str
    account_name: str
    credentials: dict = {}
    daily_post_limit: int = 5
    meta: dict = {}

class SocialPostCreate(BaseModel):
    project_id: str
    account_id: str
    campaign_id: Optional[str] = None
    content: str
    media_urls: list[str] = []
    hashtags: list[str] = []
    link: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    meta: dict = {}


# — CRM
class CloserCreate(BaseModel):
    project_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    commission_rate: float = 0.18
    bonus_rate: float = 0.05
    meta: dict = {}

class CloserOut(BaseModel):
    id: str; project_id: str; name: str; email: Optional[str]
    commission_rate: float; bonus_rate: float; is_active: bool; created_at: datetime
    class Config: from_attributes = True

class MeetingCreate(BaseModel):
    project_id: str
    prospect_id: str
    closer_id: Optional[str] = None
    campaign_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    deal_value: Optional[float] = None
    calendly_event_id: Optional[str] = None
    calendly_event_uri: Optional[str] = None
    notes: Optional[str] = None
    meta: dict = {}

class MeetingOut(BaseModel):
    id: str; project_id: str; prospect_id: str
    closer_id: Optional[str]; campaign_id: Optional[str]
    scheduled_at: Optional[datetime]; status: str
    deal_value: Optional[float]; created_at: datetime
    class Config: from_attributes = True

class CommissionCreate(BaseModel):
    project_id: str
    closer_id: str
    meeting_id: Optional[str] = None
    deal_value: float
    rate: Optional[float] = None    # si None → utilise commission_rate du closer
    notes: Optional[str] = None
    meta: dict = {}

class TaskCreate(BaseModel):
    project_id: str
    title: str
    prospect_id: Optional[str] = None
    closer_id: Optional[str] = None
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    meta: dict = {}


# — Calendly webhook
class CalendlyWebhookPayload(BaseModel):
    event: str                      # "invitee.created" | "invitee.canceled"
    payload: dict
