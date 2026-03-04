"""Tests — route /closing_pack (fiche produit closers)."""
import os
import pytest
from fastapi.testclient import TestClient

from src.database import init_db

os.environ.setdefault("CLOSER_TOKEN", "closer-secret")


@pytest.fixture(scope="module")
def client():
    from src.api.main import app
    init_db()
    return TestClient(app)


class TestClosingPack:
    def test_valid_token_returns_200(self, client):
        r = client.get("/closing_pack?t=closer-secret")
        assert r.status_code == 200

    def test_returns_html(self, client):
        r = client.get("/closing_pack?t=closer-secret")
        assert "text/html" in r.headers["content-type"]

    def test_contains_fiche_content(self, client):
        r = client.get("/closing_pack?t=closer-secret")
        assert "Présence IA" in r.text or "PRESENCE IA" in r.text or "Tout Inclus" in r.text

    def test_invalid_token_returns_403(self, client):
        r = client.get("/closing_pack?t=mauvais-token")
        assert r.status_code == 403

    def test_empty_token_returns_403(self, client):
        r = client.get("/closing_pack")
        assert r.status_code == 403

    def test_wrong_token_returns_403(self, client):
        r = client.get("/closing_pack?t=admin-token")
        assert r.status_code == 403
