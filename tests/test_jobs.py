"""
Tests jobs asynchrones — POST /api/ia-test/run → 202 + GET /api/jobs/{id}
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path):
    """Client de test avec DB SQLite temporaire."""
    os.environ["DB_PATH"] = str(tmp_path / "test.db")
    os.environ["OPENAI_API_KEY"] = "sk-test"

    from src.api.main import app
    from src.database import init_db
    init_db()

    with TestClient(app) as c:
        yield c


def _create_campaign_and_prospect(client) -> tuple[str, str]:
    """Crée une campagne + 1 prospect SCHEDULED, retourne (campaign_id, prospect_id)."""
    r = client.post("/api/prospect-scan", json={
        "city": "Paris", "profession": "plombier", "max_prospects": 1,
        "manual_prospects": [{"name": "Plomberie Test", "city": "Paris"}]
    })
    assert r.status_code == 200
    data = r.json()
    return data["campaign_id"], data["prospects"][0]["id"]


# ── Tests POST /api/ia-test/run ────────────────────────────────────────────

class TestIATestAsync:
    def test_returns_202(self, client):
        cid, _ = _create_campaign_and_prospect(client)
        with patch("src.ia_test.run_campaign", return_value={"total":1,"processed":1,"runs_created":3,"errors":[]}):
            r = client.post("/api/ia-test/run", json={"campaign_id": cid, "dry_run": True})
        assert r.status_code == 202

    def test_response_has_job_id(self, client):
        cid, _ = _create_campaign_and_prospect(client)
        with patch("src.ia_test.run_campaign", return_value={"total":1,"processed":1,"runs_created":3,"errors":[]}):
            r = client.post("/api/ia-test/run", json={"campaign_id": cid, "dry_run": True})
        body = r.json()
        assert "job_id" in body
        assert body["queued"] is True
        assert "poll" in body

    def test_response_has_models(self, client):
        cid, _ = _create_campaign_and_prospect(client)
        with patch("src.ia_test.run_campaign", return_value={"total":1,"processed":1,"runs_created":3,"errors":[]}):
            r = client.post("/api/ia-test/run", json={"campaign_id": cid, "dry_run": True})
        assert isinstance(r.json()["models"], list)

    def test_campaign_not_found_404(self, client):
        r = client.post("/api/ia-test/run", json={"campaign_id": "inexistant", "dry_run": True})
        assert r.status_code == 404

    def test_no_key_no_dry_run_400(self, client):
        cid, _ = _create_campaign_and_prospect(client)
        env_backup = os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)
        r = client.post("/api/ia-test/run", json={"campaign_id": cid, "dry_run": False})
        assert r.status_code == 400
        if env_backup:
            os.environ["OPENAI_API_KEY"] = env_backup


# ── Tests GET /api/jobs/{job_id} ──────────────────────────────────────────

class TestJobStatus:
    def test_job_queued_initially(self, client):
        cid, _ = _create_campaign_and_prospect(client)
        # On bloque le worker pour observer QUEUED (pas facile sans thread, on teste via DB)
        with patch("src.api.routes.ia_test._run_job"):  # mock le worker
            r = client.post("/api/ia-test/run", json={"campaign_id": cid, "dry_run": True})
        job_id = r.json()["job_id"]
        r2 = client.get(f"/api/jobs/{job_id}")
        assert r2.status_code == 200
        assert r2.json()["job_id"] == job_id
        assert r2.json()["campaign_id"] == cid

    def test_job_not_found_404(self, client):
        r = client.get("/api/jobs/inexistant-job-id")
        assert r.status_code == 404

    def test_job_done_after_run(self, client):
        cid, _ = _create_campaign_and_prospect(client)
        mock_result = {"total": 1, "processed": 1, "runs_created": 3, "errors": []}
        with patch("src.ia_test.run_campaign", return_value=mock_result):
            r = client.post("/api/ia-test/run", json={"campaign_id": cid, "dry_run": True})
        job_id = r.json()["job_id"]
        # TestClient exécute les BackgroundTasks de façon synchrone → DONE immédiat
        r2 = client.get(f"/api/jobs/{job_id}")
        data = r2.json()
        assert data["status"] == "DONE"
        assert data["progress"]["processed"] == 1
        assert data["progress"]["runs_created"] == 3
        assert data["errors"] == []

    def test_job_progress_fields(self, client):
        cid, _ = _create_campaign_and_prospect(client)
        with patch("src.ia_test.run_campaign", return_value={"total":1,"processed":1,"runs_created":2,"errors":[]}):
            r = client.post("/api/ia-test/run", json={"campaign_id": cid, "dry_run": True})
        job_id = r.json()["job_id"]
        data = client.get(f"/api/jobs/{job_id}").json()
        assert "progress" in data
        assert "timestamps" in data
        assert data["timestamps"]["created_at"] is not None
