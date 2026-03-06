"""test_send.py — execute_send_batch with a mock provider."""
import os
os.environ["MKT_DB_PATH"] = ":memory:"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marketing_module.models import (
    Base, CampaignStatus, Channel, ReputationStatus, WarmupStatus,
)
from marketing_module.database import (
    db_create_campaign, db_create_domain, db_create_mailbox,
    db_create_rotation, db_create_sequence, db_create_sequence_step,
    db_list_deliveries,
)
from marketing_module.module import execute_send_batch


class MockEmailProvider:
    def send(self, mailbox, delivery_id, prospect_id, sequence_step_id):
        return {"success": True, "message_id": f"mock-{delivery_id}"}


class FailingEmailProvider:
    def send(self, mailbox, delivery_id, prospect_id, sequence_step_id):
        return {"success": False, "error": "Provider error"}


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _setup(db):
    rotation = db_create_rotation(db, {
        "project_id": "test", "name": "Rotation",
        "algorithm": "round_robin", "per_mailbox_daily_cap": 50,
    })
    campaign = db_create_campaign(db, {
        "project_id": "test", "name": "Campaign",
        "channels": [Channel.email], "status": CampaignStatus.active,
        "rotation_strategy_id": rotation.id,
        "stop_on_reply": True, "stop_on_meeting": True,
    })
    domain = db_create_domain(db, {
        "project_id": "test", "domain": "test.com",
        "role": "sending", "dns_status": "verified",
    })
    mailbox = db_create_mailbox(db, {
        "project_id": "test", "domain_id": domain.id,
        "email": "send@test.com", "display_name": "Test",
        "daily_limit": 50, "hourly_limit": 10,
        "warmup_status": WarmupStatus.completed,
        "reputation_status": ReputationStatus.healthy,
        "is_active": True,
    })
    sequence = db_create_sequence(db, {
        "project_id": "test", "campaign_id": campaign.id,
        "name": "Sequence", "is_active": True,
    })
    step = db_create_sequence_step(db, {
        "sequence_id": sequence.id, "step_number": 1,
        "channel": "email", "delay_days": 0,
        "subject": "Hello", "body_html": "<p>Hi</p>",
    })
    return campaign, step


def test_batch_send_success(db):
    campaign, step = _setup(db)
    result = execute_send_batch(
        db=db,
        project_id="test",
        campaign_id=campaign.id,
        prospect_ids=["p1@test.com", "p2@test.com", "p3@test.com"],
        sequence_step_id=step.id,
        channel_provider=MockEmailProvider(),
        channel=Channel.email,
    )
    assert result.success is True
    assert result.result["sent"] == 3
    assert result.result["skipped"] == 0
    assert result.result["failed"] == 0


def test_batch_send_dry_run(db):
    campaign, step = _setup(db)
    result = execute_send_batch(
        db=db,
        project_id="test",
        campaign_id=campaign.id,
        prospect_ids=["p1@test.com"],
        sequence_step_id=step.id,
        channel_provider=MockEmailProvider(),
        channel=Channel.email,
        dry_run=True,
    )
    assert result.success is True
    assert result.result["sent"] == 1
    assert result.result["deliveries"][0]["dry_run"] is True


def test_batch_send_dedup(db):
    campaign, step = _setup(db)
    # Send once
    execute_send_batch(
        db=db,
        project_id="test",
        campaign_id=campaign.id,
        prospect_ids=["p1@test.com"],
        sequence_step_id=step.id,
        channel_provider=MockEmailProvider(),
        channel=Channel.email,
    )
    # Send again — should be skipped
    result = execute_send_batch(
        db=db,
        project_id="test",
        campaign_id=campaign.id,
        prospect_ids=["p1@test.com"],
        sequence_step_id=step.id,
        channel_provider=MockEmailProvider(),
        channel=Channel.email,
    )
    assert result.result["skipped"] == 1
    assert result.result["sent"] == 0


def test_batch_send_provider_failure(db):
    campaign, step = _setup(db)
    result = execute_send_batch(
        db=db,
        project_id="test",
        campaign_id=campaign.id,
        prospect_ids=["p1@test.com"],
        sequence_step_id=step.id,
        channel_provider=FailingEmailProvider(),
        channel=Channel.email,
    )
    assert result.result["failed"] == 1
    assert result.result["sent"] == 0


def test_inactive_campaign_rejected(db):
    rotation = db_create_rotation(db, {
        "project_id": "test2", "name": "R",
        "algorithm": "round_robin", "per_mailbox_daily_cap": 50,
    })
    campaign = db_create_campaign(db, {
        "project_id": "test2", "name": "Paused",
        "channels": [Channel.email], "status": CampaignStatus.paused,
    })
    result = execute_send_batch(
        db=db,
        project_id="test2",
        campaign_id=campaign.id,
        prospect_ids=["p@test.com"],
        sequence_step_id="step-x",
        channel_provider=MockEmailProvider(),
        channel=Channel.email,
    )
    assert result.success is False
    assert "paused" in result.message
