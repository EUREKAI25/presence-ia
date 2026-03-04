"""Tests — chantier 08 : admin demo route."""
import json
import pytest
from fastapi.testclient import TestClient

from src.models import Base, CampaignDB, ProspectDB
from src.database import init_db


@pytest.fixture(scope="module")
def client_and_data():
    from src.api.main import app
    init_db()
    client = TestClient(app)

    from src.database import SessionLocal
    db = SessionLocal()
    try:
        campaign = CampaignDB(profession="couvreur", city="brest", mode="AUTO_TEST")
        db.add(campaign)
        db.flush()

        prospect = ProspectDB(
            campaign_id=campaign.campaign_id,
            name="Toit Breton",
            city="brest",
            profession="couvreur",
            ia_visibility_score=4.5,
            competitors_cited=json.dumps(["Pro Toiture", "Brest Couverture"]),
            landing_token="demotoken456",
            paid=True,
        )
        db.add(prospect)
        db.commit()
        cid = campaign.campaign_id
        pid = prospect.prospect_id
    finally:
        db.close()

    return client, cid, pid


class TestAdminDemoRoute:
    def test_valid_token_returns_200(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert r.status_code == 200

    def test_returns_html(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert "text/html" in r.headers["content-type"]

    def test_invalid_token_returns_403(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=mauvais")
        assert r.status_code == 403

    def test_unknown_campaign_returns_404(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get("/admin/demo/inexistant?token=secret")
        assert r.status_code == 404

    def test_contains_profession(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert "couvreur" in r.text.lower()

    def test_contains_city(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert "brest" in r.text.lower()

    def test_contains_prospect_name(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert "Toit Breton" in r.text

    def test_contains_score(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert "4.5" in r.text

    def test_contains_competitors(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert "Pro Toiture" in r.text or "Brest Couverture" in r.text

    def test_contains_landing_link(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert "Landing" in r.text or "demotoken456" in r.text or "couvreur" in r.text

    def test_contains_outreach_button(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert "Outreach" in r.text or "outreach" in r.text.lower()

    def test_contains_evidence_section(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert "Preuves" in r.text or "preuves" in r.text.lower()

    def test_contains_preuves_section(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert "preuve" in r.text.lower() or "Aucune preuve" in r.text

    def test_contains_campaign_stats(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}?token=secret")
        assert "Campagne" in r.text
        assert "Prospects" in r.text

    def test_empty_token_returns_403(self, client_and_data):
        client, cid, pid = client_and_data
        r = client.get(f"/admin/demo/{cid}")
        assert r.status_code == 403
