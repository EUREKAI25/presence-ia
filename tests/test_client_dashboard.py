"""Tests — chantier 10G : client dashboard."""
import json
import pytest
from fastapi.testclient import TestClient

from src.models import Base, CampaignDB, ProspectDB, TestRunDB
from src.database import init_db


@pytest.fixture(scope="module")
def client_and_data():
    from src.api.main import app
    init_db()
    client = TestClient(app)

    from src.database import SessionLocal
    db = SessionLocal()
    try:
        campaign = CampaignDB(profession="plombier", city="nantes", mode="AUTO_TEST")
        db.add(campaign)
        db.flush()

        prospect = ProspectDB(
            campaign_id=campaign.campaign_id,
            name="Plomb Nantes",
            city="nantes",
            profession="plombier",
            ia_visibility_score=6.0,
            competitors_cited=json.dumps(["Aqua Pro", "Nantes Plomberie"]),
            landing_token="dashtoken789",
            paid=True,
        )
        db.add(prospect)
        db.flush()

        run = TestRunDB(
            campaign_id=campaign.campaign_id,
            prospect_id=prospect.prospect_id,
            model="openai",
            queries=json.dumps(["meilleur plombier nantes", "plombier recommandé nantes"]),
            raw_answers=json.dumps(["Aqua Pro est recommandé.", "Nantes Plomberie est cité."]),
            extracted_entities=json.dumps(["Aqua Pro", "Nantes Plomberie"]),
            mentioned_target=True,
            mention_per_query=json.dumps([True, False]),
            competitors_entities=json.dumps(["Aqua Pro", "Nantes Plomberie"]),
            notes="",
        )
        db.add(run)
        db.commit()
        pid = prospect.prospect_id
        token = prospect.landing_token
    finally:
        db.close()

    return client, pid, token


class TestClientDashboard:
    def test_valid_token_returns_200(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert r.status_code == 200

    def test_returns_html(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "text/html" in r.headers["content-type"]

    def test_invalid_token_returns_404(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t=tokeninconnu")
        assert r.status_code == 404

    def test_wrong_prospect_returns_404(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/inconnu?t={token}")
        assert r.status_code == 404

    def test_empty_token_returns_404(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}")
        assert r.status_code == 404

    def test_contains_prospect_name(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "Plomb Nantes" in r.text

    def test_contains_city(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "nantes" in r.text.lower()

    def test_contains_profession(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "plombier" in r.text.lower()

    def test_contains_score(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "6.0" in r.text or "6,0" in r.text

    def test_contains_history_section(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "historique" in r.text.lower() or "Historique" in r.text

    def test_contains_last_run_detail(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "meilleur plombier nantes" in r.text.lower() or "requête" in r.text.lower() or "Dernier test" in r.text

    def test_contains_competitors_section(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "Aqua Pro" in r.text or "concurrent" in r.text.lower()

    def test_contains_checklist_section(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "checklist" in r.text.lower() or "Checklist" in r.text

    def test_checklist_has_items(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "JSON-LD" in r.text or "Google Business" in r.text

    def test_contains_livrables_section(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "livrable" in r.text.lower() or "Livrable" in r.text

    def test_contains_next_retest(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        assert "re-test" in r.text.lower() or "retest" in r.text.lower() or "prochain" in r.text.lower()

    def test_mentions_cited_queries(self, client_and_data):
        client, pid, token = client_and_data
        r = client.get(f"/client/{pid}?t={token}")
        # At least one query result should be shown
        assert "✅" in r.text or "❌" in r.text or "Cité" in r.text
