"""Tests — chantier 06 : contacts tracking CRUD."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models import Base, ContactDB
from src.database import (
    db_create_contact, db_get_contact, db_list_contacts,
    db_update_contact, db_delete_contact,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_contact(**kwargs) -> ContactDB:
    defaults = dict(
        company_name="Toit Mon Toit",
        email="contact@toit.fr",
        phone="02 98 00 00 00",
        city="Brest",
        profession="couvreur",
        status="SUSPECT",
    )
    defaults.update(kwargs)
    return ContactDB(**defaults)


class TestContactCRUD:
    def test_create_and_get(self, db):
        c = db_create_contact(db, _make_contact())
        assert c.id is not None
        fetched = db_get_contact(db, c.id)
        assert fetched.company_name == "Toit Mon Toit"

    def test_list_contacts(self, db):
        db_create_contact(db, _make_contact(company_name="A"))
        db_create_contact(db, _make_contact(company_name="B"))
        contacts = db_list_contacts(db)
        assert len(contacts) >= 2

    def test_list_ordered_by_date_desc(self, db):
        db_create_contact(db, _make_contact(company_name="Premier"))
        db_create_contact(db, _make_contact(company_name="Dernier"))
        contacts = db_list_contacts(db)
        # Le plus récent en premier
        assert contacts[0].company_name == "Dernier"

    def test_update_message_sent(self, db):
        c = db_create_contact(db, _make_contact())
        assert c.message_sent is False
        db_update_contact(db, c, message_sent=True)
        updated = db_get_contact(db, c.id)
        assert updated.message_sent is True

    def test_update_message_read(self, db):
        c = db_create_contact(db, _make_contact())
        db_update_contact(db, c, message_read=True)
        assert db_get_contact(db, c.id).message_read is True

    def test_update_paid_and_status(self, db):
        c = db_create_contact(db, _make_contact())
        db_update_contact(db, c, paid=True, status="CLIENT")
        updated = db_get_contact(db, c.id)
        assert updated.paid is True
        assert updated.status == "CLIENT"

    def test_update_status_to_prospect(self, db):
        c = db_create_contact(db, _make_contact(status="SUSPECT"))
        db_update_contact(db, c, status="PROSPECT")
        assert db_get_contact(db, c.id).status == "PROSPECT"

    def test_delete_contact(self, db):
        c = db_create_contact(db, _make_contact())
        cid = c.id
        db_delete_contact(db, c)
        assert db_get_contact(db, cid) is None

    def test_get_nonexistent_returns_none(self, db):
        assert db_get_contact(db, "id-qui-nexiste-pas") is None

    def test_contact_has_required_fields(self, db):
        c = db_create_contact(db, _make_contact(
            offer_selected="KIT",
            acquisition_cost=97.0,
            notes="À relancer lundi",
        ))
        assert c.offer_selected == "KIT"
        assert c.acquisition_cost == 97.0
        assert "relancer" in c.notes

    def test_date_added_auto(self, db):
        c = db_create_contact(db, _make_contact())
        assert c.date_added is not None

    def test_create_minimal_contact(self, db):
        """company_name seul suffit."""
        c = db_create_contact(db, ContactDB(company_name="Minimal"))
        assert c.id is not None
        assert c.email is None
        assert c.status == "SUSPECT"


class TestContactApiEndpoints:
    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.main import app
        from src.database import init_db
        init_db()
        return TestClient(app)

    def test_create_via_api(self, client):
        r = client.post(
            "/admin/contacts/create?token=changeme",
            json={"company_name": "Couverture API", "status": "SUSPECT"},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert "id" in d

    def test_create_requires_company_name(self, client):
        r = client.post(
            "/admin/contacts/create?token=changeme",
            json={"email": "test@test.fr"},
        )
        assert r.status_code == 400

    def test_create_requires_token(self, client):
        r = client.post(
            "/admin/contacts/create",
            json={"company_name": "Test"},
        )
        assert r.status_code == 403

    def test_mark_sent_via_api(self, client):
        # Créer d'abord un contact
        r = client.post(
            "/admin/contacts/create?token=changeme",
            json={"company_name": "Mark Sent Test"},
        )
        cid = r.json()["id"]
        r2 = client.post(f"/admin/contacts/{cid}/sent?token=changeme")
        assert r2.status_code == 200
        assert r2.json()["ok"] is True

    def test_mark_read_via_api(self, client):
        r = client.post(
            "/admin/contacts/create?token=changeme",
            json={"company_name": "Mark Read Test"},
        )
        cid = r.json()["id"]
        r2 = client.post(f"/admin/contacts/{cid}/read?token=changeme")
        assert r2.status_code == 200

    def test_mark_paid_via_api(self, client):
        r = client.post(
            "/admin/contacts/create?token=changeme",
            json={"company_name": "Mark Paid Test"},
        )
        cid = r.json()["id"]
        r2 = client.post(f"/admin/contacts/{cid}/paid?token=changeme")
        assert r2.status_code == 200

    def test_set_status_valid(self, client):
        r = client.post(
            "/admin/contacts/create?token=changeme",
            json={"company_name": "Status Test"},
        )
        cid = r.json()["id"]
        r2 = client.post(
            f"/admin/contacts/{cid}/set-status?token=changeme",
            json={"status": "PROSPECT"},
        )
        assert r2.status_code == 200

    def test_set_status_invalid_rejected(self, client):
        r = client.post(
            "/admin/contacts/create?token=changeme",
            json={"company_name": "Bad Status Test"},
        )
        cid = r.json()["id"]
        r2 = client.post(
            f"/admin/contacts/{cid}/set-status?token=changeme",
            json={"status": "INVALIDE"},
        )
        assert r2.status_code == 400

    def test_delete_via_api(self, client):
        r = client.post(
            "/admin/contacts/create?token=changeme",
            json={"company_name": "Delete Test"},
        )
        cid = r.json()["id"]
        r2 = client.post(f"/admin/contacts/{cid}/delete?token=changeme")
        assert r2.status_code == 200
        assert r2.json()["ok"] is True

    def test_mark_sent_404_on_unknown(self, client):
        r = client.post("/admin/contacts/id-inconnu/sent?token=changeme")
        assert r.status_code == 404
