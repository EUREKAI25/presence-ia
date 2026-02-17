"""
Data models — Campaign, ProspectRecord, TestRun
SQLAlchemy (SQLite) + Pydantic v2 + Enums + transitions statuts
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ── ENUMS ──────────────────────────────────────────────────────────────

class ProspectStatus(str, Enum):
    SCANNED       = "SCANNED"
    SCHEDULED     = "SCHEDULED"
    TESTING       = "TESTING"
    TESTED        = "TESTED"
    SCORED        = "SCORED"
    READY_ASSETS  = "READY_ASSETS"
    READY_TO_SEND = "READY_TO_SEND"
    SENT_MANUAL   = "SENT_MANUAL"


_TRANSITIONS: Dict[str, List[str]] = {
    "SCANNED":       ["SCHEDULED"],
    "SCHEDULED":     ["TESTING"],
    "TESTING":       ["TESTED"],
    "TESTED":        ["SCORED"],
    "SCORED":        ["READY_ASSETS"],
    "READY_ASSETS":  ["READY_TO_SEND"],
    "READY_TO_SEND": ["SENT_MANUAL"],
    "SENT_MANUAL":   [],
}


def can_transition(current: str, target: str) -> bool:
    return target in _TRANSITIONS.get(current, [])


class CampaignMode(str, Enum):
    DRY_RUN    = "DRY_RUN"
    AUTO_TEST  = "AUTO_TEST"
    SEND_READY = "SEND_READY"


# ── ORM ────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class CampaignDB(Base):
    __tablename__ = "campaigns"
    campaign_id:   Mapped[str]      = mapped_column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profession:    Mapped[str]      = mapped_column(sa.String, nullable=False)
    city:          Mapped[str]      = mapped_column(sa.String, nullable=False)
    created_at:    Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.utcnow)
    mode:          Mapped[str]      = mapped_column(sa.String, default="AUTO_TEST")
    status:        Mapped[str]      = mapped_column(sa.String, default="active")
    max_prospects: Mapped[int]      = mapped_column(sa.Integer, default=30)

    prospects: Mapped[List["ProspectDB"]] = relationship("ProspectDB", back_populates="campaign", cascade="all, delete-orphan")
    runs:      Mapped[List["TestRunDB"]]  = relationship("TestRunDB",  back_populates="campaign", cascade="all, delete-orphan")


class ProspectDB(Base):
    __tablename__ = "prospects"
    prospect_id:         Mapped[str]            = mapped_column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id:         Mapped[str]            = mapped_column(sa.String, sa.ForeignKey("campaigns.campaign_id"), nullable=False)
    name:                Mapped[str]            = mapped_column(sa.String, nullable=False)
    city:                Mapped[str]            = mapped_column(sa.String, nullable=False)
    profession:          Mapped[str]            = mapped_column(sa.String, nullable=False)
    website:             Mapped[Optional[str]]  = mapped_column(sa.String, nullable=True)
    phone:               Mapped[Optional[str]]  = mapped_column(sa.String, nullable=True)
    reviews_count:       Mapped[Optional[int]]  = mapped_column(sa.Integer, nullable=True)
    google_ads_active:   Mapped[Optional[bool]] = mapped_column(sa.Boolean, nullable=True)
    competitors_cited:   Mapped[str]            = mapped_column(sa.Text, default="[]")
    ia_visibility_score: Mapped[Optional[float]]= mapped_column(sa.Float, nullable=True)
    eligibility_flag:    Mapped[bool]           = mapped_column(sa.Boolean, default=False)
    landing_token:       Mapped[str]            = mapped_column(sa.String, default=lambda: uuid.uuid4().hex[:24])
    video_url:           Mapped[Optional[str]]  = mapped_column(sa.String, nullable=True)
    screenshot_url:      Mapped[Optional[str]]  = mapped_column(sa.String, nullable=True)
    status:              Mapped[str]            = mapped_column(sa.String, default="SCANNED")
    score_justification: Mapped[Optional[str]]  = mapped_column(sa.Text, nullable=True)
    created_at:          Mapped[datetime]       = mapped_column(sa.DateTime, default=datetime.utcnow)

    campaign: Mapped["CampaignDB"]      = relationship("CampaignDB", back_populates="prospects")
    runs:     Mapped[List["TestRunDB"]] = relationship("TestRunDB",  back_populates="prospect", cascade="all, delete-orphan")


class TestRunDB(Base):
    __tablename__ = "test_runs"
    run_id:               Mapped[str]           = mapped_column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id:          Mapped[str]           = mapped_column(sa.String, sa.ForeignKey("campaigns.campaign_id"), nullable=False)
    prospect_id:          Mapped[str]           = mapped_column(sa.String, sa.ForeignKey("prospects.prospect_id"), nullable=False)
    ts:                   Mapped[datetime]      = mapped_column(sa.DateTime, default=datetime.utcnow)
    model:                Mapped[str]           = mapped_column(sa.String, nullable=False)
    queries:              Mapped[str]           = mapped_column(sa.Text, default="[]")
    raw_answers:          Mapped[str]           = mapped_column(sa.Text, default="[]")
    extracted_entities:   Mapped[str]           = mapped_column(sa.Text, default="[]")
    mentioned_target:     Mapped[bool]          = mapped_column(sa.Boolean, default=False)
    mention_per_query:    Mapped[str]           = mapped_column(sa.Text, default="[]")
    competitors_entities: Mapped[str]           = mapped_column(sa.Text, default="[]")
    notes:                Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    campaign: Mapped["CampaignDB"] = relationship("CampaignDB", back_populates="runs")
    prospect: Mapped["ProspectDB"] = relationship("ProspectDB",  back_populates="runs")


# ── PYDANTIC SCHEMAS ────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    profession:    str
    city:          str
    max_prospects: int          = 30
    mode:          CampaignMode = CampaignMode.AUTO_TEST


class ProspectInput(BaseModel):
    name:              str
    city:              Optional[str]  = None
    profession:        Optional[str]  = None
    website:           Optional[str]  = None
    phone:             Optional[str]  = None
    reviews_count:     Optional[int]  = None
    google_ads_active: Optional[bool] = None


class ProspectScanInput(BaseModel):
    city:             str
    profession:       str
    max_prospects:    int                       = 30
    campaign_id:      Optional[str]             = None
    manual_prospects: Optional[List[ProspectInput]] = None


class IATestRunInput(BaseModel):
    campaign_id:  str
    prospect_ids: Optional[List[str]] = None
    dry_run:      bool                = False


class ScoringRunInput(BaseModel):
    campaign_id:  str
    prospect_ids: Optional[List[str]] = None


class GenerateInput(BaseModel):
    campaign_id:  str
    prospect_ids: Optional[List[str]] = None


class AssetsInput(BaseModel):
    video_url:      str
    screenshot_url: str


class PipelineRunInput(BaseModel):
    """Runner unique : SCAN → TEST → SCORE → GENERATE → QUEUE"""
    city:             str
    profession:       str
    max_prospects:    int                          = 30
    manual_prospects: Optional[List[ProspectInput]] = None
    dry_run:          bool                         = False
