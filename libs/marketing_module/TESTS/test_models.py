"""test_models.py — ORM creation + basic CRUD in SQLite in-memory."""
import os
os.environ["MKT_DB_PATH"] = ":memory:"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marketing_module.models import Base, Channel, CampaignStatus, WarmupStatus
from marketing_module.database import (
    db_create_domain, db_create_mailbox, db_create_campaign,
    db_get_campaign, db_list_mailboxes,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_domain(db):
    obj = db_create_domain(db, {
        "project_id": "test", "domain": "test.com",
        "role": "sending", "dns_status": "pending",
    })
    assert obj.id
    assert obj.domain == "test.com"


def test_create_mailbox(db):
    domain = db_create_domain(db, {
        "project_id": "test", "domain": "test.com",
        "role": "sending", "dns_status": "pending",
    })
    mb = db_create_mailbox(db, {
        "project_id": "test", "domain_id": domain.id,
        "email": "hello@test.com", "display_name": "Test",
        "daily_limit": 50, "hourly_limit": 10,
        "warmup_status": WarmupStatus.not_started,
    })
    assert mb.email == "hello@test.com"
    rows = db_list_mailboxes(db, "test")
    assert len(rows) == 1


def test_create_campaign(db):
    obj = db_create_campaign(db, {
        "project_id": "test", "name": "Test Campaign",
        "channels": [Channel.email], "status": CampaignStatus.draft,
        "stop_on_reply": True, "stop_on_meeting": True,
    })
    assert obj.id
    fetched = db_get_campaign(db, obj.id)
    assert fetched.name == "Test Campaign"
    assert fetched.status == CampaignStatus.draft


def test_campaign_status_update(db):
    obj = db_create_campaign(db, {
        "project_id": "test", "name": "Campaign 2",
        "channels": [Channel.email], "status": CampaignStatus.draft,
    })
    from marketing_module.database import db_update_campaign
    updated = db_update_campaign(db, obj.id, {"status": CampaignStatus.active})
    assert updated.status == CampaignStatus.active
