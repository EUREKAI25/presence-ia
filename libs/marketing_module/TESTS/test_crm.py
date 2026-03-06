"""test_crm.py — CRM: closer assignment, meeting creation, commission calculation."""
import os
os.environ["MKT_DB_PATH"] = ":memory:"

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marketing_module.models import Base, CommissionStatus, MeetingStatus
from marketing_module.database import (
    db_create_closer, db_create_campaign,
    db_get_meeting, db_list_commissions,
)
from marketing_module.crm.module import (
    assign_closer, complete_meeting, handle_calendly_webhook,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_assign_closer_no_closers(db):
    result = assign_closer(db, "test")
    assert result is None


def test_assign_closer_picks_least_loaded(db):
    c1 = db_create_closer(db, {
        "project_id": "test", "name": "Alice", "email": "alice@test.com",
        "commission_rate": 0.15, "is_active": True,
    })
    c2 = db_create_closer(db, {
        "project_id": "test", "name": "Bob", "email": "bob@test.com",
        "commission_rate": 0.15, "is_active": True,
    })
    picked = assign_closer(db, "test")
    assert picked in [c1.id, c2.id]


def test_calendly_webhook_creates_meeting(db):
    closer = db_create_closer(db, {
        "project_id": "test", "name": "Alice", "email": "alice@test.com",
        "commission_rate": 0.18, "is_active": True,
    })
    payload = {
        "event": "invitee.created",
        "payload": {
            "email": "prospect@example.com",
            "name": "Jean Dupont",
            "uri": "https://calendly.com/invitees/abc123",
            "event": "https://calendly.com/events/evt001",
            "scheduled_event": {"start_time": "2026-03-10T14:00:00Z"},
        },
    }
    result = handle_calendly_webhook(db, "test", payload)
    assert result.success is True
    assert result.result["meeting_id"]
    assert result.result["closer_id"] == closer.id


def test_complete_meeting_creates_commission(db):
    closer = db_create_closer(db, {
        "project_id": "test", "name": "Alice", "email": "alice@test.com",
        "commission_rate": 0.20, "is_active": True,
    })
    from marketing_module.database import db_create_meeting
    meeting = db_create_meeting(db, {
        "project_id": "test",
        "prospect_id": "prospect@example.com",
        "closer_id": closer.id,
        "status": MeetingStatus.scheduled,
        "scheduled_at": datetime.utcnow(),
    })
    result = complete_meeting(db, meeting.id, deal_value=2000.0)
    assert result.success is True
    assert result.result["commission"] is not None
    assert result.result["commission"]["amount"] == 400.0  # 2000 * 0.20

    commissions = db_list_commissions(db, "test", closer_id=closer.id)
    assert len(commissions) == 1
    assert commissions[0].status == CommissionStatus.pending


def test_calendly_cancellation(db):
    from marketing_module.database import db_create_meeting
    meeting = db_create_meeting(db, {
        "project_id": "test",
        "prospect_id": "prospect@example.com",
        "status": MeetingStatus.scheduled,
        "calendly_event_uri": "https://calendly.com/events/evt_cancel",
    })
    payload = {
        "event": "invitee.canceled",
        "payload": {
            "event": "https://calendly.com/events/evt_cancel",
            "uri": "https://calendly.com/invitees/x",
        },
    }
    result = handle_calendly_webhook(db, "test", payload)
    assert result.success is True
    updated = db_get_meeting(db, meeting.id)
    assert updated.status == MeetingStatus.cancelled
