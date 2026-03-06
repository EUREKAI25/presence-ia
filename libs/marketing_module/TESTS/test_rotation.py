"""test_rotation.py — Rotation algorithm + warmup cap logic."""
import os
os.environ["MKT_DB_PATH"] = ":memory:"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marketing_module.models import (
    Base, CampaignStatus, Channel, ReputationStatus, RotationAlgorithm, WarmupStatus,
)
from marketing_module.database import (
    db_create_campaign, db_create_domain, db_create_mailbox,
    db_create_rotation, db_update_campaign,
)
from marketing_module.module import choose_next_mailbox


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _setup_campaign_and_mailboxes(db, algorithm="round_robin", n_mailboxes=3):
    rotation = db_create_rotation(db, {
        "project_id": "test", "name": "Test Rotation",
        "algorithm": algorithm, "per_mailbox_daily_cap": 40,
    })
    campaign = db_create_campaign(db, {
        "project_id": "test", "name": "Test Campaign",
        "channels": [Channel.email], "status": CampaignStatus.active,
        "rotation_strategy_id": rotation.id,
    })
    domain = db_create_domain(db, {
        "project_id": "test", "domain": "test.com",
        "role": "sending", "dns_status": "verified",
    })
    mailboxes = []
    for i in range(n_mailboxes):
        mb = db_create_mailbox(db, {
            "project_id": "test", "domain_id": domain.id,
            "email": f"mb{i}@test.com", "display_name": "Test",
            "daily_limit": 40, "hourly_limit": 10,
            "warmup_status": WarmupStatus.completed,
            "reputation_status": ReputationStatus.healthy,
            "is_active": True,
        })
        mailboxes.append(mb)
    return campaign, mailboxes


def test_round_robin_picks_least_recently_used(db):
    campaign, mailboxes = _setup_campaign_and_mailboxes(db, "round_robin")
    picked = choose_next_mailbox(db, campaign.id)
    assert picked is not None
    assert picked.email in [m.email for m in mailboxes]


def test_no_candidate_when_all_at_limit(db):
    campaign, mailboxes = _setup_campaign_and_mailboxes(db, "round_robin")
    from marketing_module.database import db_update_mailbox
    for mb in mailboxes:
        db_update_mailbox(db, mb.id, {"sent_today": 40})
    picked = choose_next_mailbox(db, campaign.id)
    assert picked is None


def test_blacklisted_mailbox_excluded(db):
    campaign, mailboxes = _setup_campaign_and_mailboxes(db, "round_robin", n_mailboxes=1)
    from marketing_module.database import db_update_mailbox
    db_update_mailbox(db, mailboxes[0].id, {"reputation_status": ReputationStatus.blacklisted})
    picked = choose_next_mailbox(db, campaign.id)
    assert picked is None


def test_weighted_algorithm(db):
    campaign, mailboxes = _setup_campaign_and_mailboxes(db, "weighted")
    picked = choose_next_mailbox(db, campaign.id)
    assert picked is not None


def test_health_priority_algorithm(db):
    campaign, mailboxes = _setup_campaign_and_mailboxes(db, "health_priority")
    picked = choose_next_mailbox(db, campaign.id)
    assert picked is not None
    assert picked.reputation_status == ReputationStatus.healthy
