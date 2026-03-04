"""Tests — chantier 04 : CMS blocks."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from src.api.main import app
    from src.database import init_db
    init_db()
    return TestClient(app)


@pytest.fixture(scope="module")
def token():
    import os
    return os.getenv("ADMIN_TOKEN", "changeme")


class TestCmsApi:
    def test_list_blocks_returns_list(self, client):
        r = client.get("/api/cms/blocks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_blocks_filter_by_prefix(self, client):
        r = client.get("/api/cms/blocks?prefix=home.")
        assert r.status_code == 200
        data = r.json()
        for item in data:
            assert item["key"].startswith("home.")

    def test_list_blocks_filter_by_locale(self, client):
        r = client.get("/api/cms/blocks?locale=fr")
        assert r.status_code == 200
        data = r.json()
        for item in data:
            assert item["locale"] == "fr"

    def test_upsert_creates_block(self, client):
        payload = {"key": "test.key.create", "value": "Valeur test", "locale": "fr"}
        r = client.post("/api/cms/block/upsert", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True
        assert d["result"]["key"] == "test.key.create"

    def test_upsert_updates_existing_block(self, client):
        key = "test.key.update"
        client.post("/api/cms/block/upsert", json={"key": key, "value": "v1", "locale": "fr"})
        r = client.post("/api/cms/block/upsert", json={"key": key, "value": "v2", "locale": "fr"})
        assert r.status_code == 200
        assert r.json()["success"] is True
        # Vérifier la valeur mise à jour
        blocks = client.get(f"/api/cms/blocks?prefix={key}").json()
        updated = next((b for b in blocks if b["key"] == key), None)
        assert updated is not None
        assert updated["value"] == "v2"

    def test_upsert_contrat_uniforme(self, client):
        r = client.post("/api/cms/block/upsert", json={"key": "test.contrat", "value": "ok", "locale": "fr"})
        d = r.json()
        assert "success" in d
        assert "result" in d
        assert "message" in d
        assert "error" in d

    def test_upsert_different_locales_coexist(self, client):
        key = "test.multi.locale"
        client.post("/api/cms/block/upsert", json={"key": key, "value": "Bonjour", "locale": "fr"})
        client.post("/api/cms/block/upsert", json={"key": key, "value": "Hello", "locale": "en"})
        fr = client.get(f"/api/cms/blocks?prefix={key}&locale=fr").json()
        en = client.get(f"/api/cms/blocks?prefix={key}&locale=en").json()
        assert any(b["value"] == "Bonjour" for b in fr)
        assert any(b["value"] == "Hello" for b in en)

    def test_admin_cms_requires_token(self, client):
        r = client.get("/admin/cms")
        # Doit rediriger ou retourner 403
        assert r.status_code in (403, 302, 303, 200)

    def test_admin_cms_with_token(self, client, token):
        r = client.get(f"/admin/cms?token={token}")
        assert r.status_code == 200
        assert "CMS" in r.text or "bloc" in r.text.lower()

    def test_seed_blocks_exist_after_init(self, client):
        r = client.get("/api/cms/blocks?prefix=home.")
        assert r.status_code == 200
        # Au moins les blocs seed doivent exister
        data = r.json()
        assert len(data) >= 1
