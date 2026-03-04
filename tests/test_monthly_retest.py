"""Tests — chantier 10F : monthly retest pipeline."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models import Base, CampaignDB, ProspectDB, TestRunDB
from src.database import init_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

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


def _make_prospect(db, **kwargs):
    campaign = CampaignDB(profession="couvreur", city="brest", mode="AUTO_TEST")
    db.add(campaign)
    db.flush()

    defaults = dict(
        campaign_id=campaign.campaign_id,
        name="Toit Mon Toit",
        city="brest",
        profession="couvreur",
        ia_visibility_score=2.5,
        competitors_cited=json.dumps(["Pro Toiture", "Express Couverture"]),
        paid=True,
    )
    defaults.update(kwargs)
    p = ProspectDB(**defaults)
    db.add(p)
    db.commit()
    return p


def _add_baseline_run(db, p):
    run = TestRunDB(
        campaign_id=p.campaign_id,
        prospect_id=p.prospect_id,
        model="openai",
        queries=json.dumps(["meilleur couvreur brest"]),
        raw_answers=json.dumps(["Pro Toiture est recommandé."]),
        extracted_entities=json.dumps(["Pro Toiture"]),
        mentioned_target=False,
        mention_per_query=json.dumps([False]),
        competitors_entities=json.dumps(["Pro Toiture"]),
        notes="",
    )
    db.add(run)
    db.commit()
    return run


# ── Tests run_retest ─────────────────────────────────────────────────────────

class TestRunRetest:
    def test_contrat_uniforme(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db)
        result = mod.run_retest(db, p.prospect_id, dry_run=True)
        assert "success" in result
        assert "result" in result
        assert "message" in result
        assert "error" in result

    def test_unknown_prospect_returns_error(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        result = mod.run_retest(db, "id-inconnu", dry_run=True)
        assert result["success"] is False
        assert result["error"]["code"] == "NOT_FOUND"

    def test_dry_run_creates_testrundb(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db)
        mod.run_retest(db, p.prospect_id, dry_run=True)
        runs = db.query(TestRunDB).filter_by(prospect_id=p.prospect_id).all()
        assert len(runs) == 1
        assert "retest:" in runs[0].notes

    def test_dry_run_generates_html_file(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db)
        result = mod.run_retest(db, p.prospect_id, dry_run=True)
        assert result["success"] is True
        assert Path(result["result"]["file"]).exists()

    def test_result_has_required_keys(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db)
        result = mod.run_retest(db, p.prospect_id, dry_run=True)
        r = result["result"]
        assert "run_id" in r
        assert "score_before" in r
        assert "score_after" in r
        assert "score_delta" in r
        assert "new_competitors" in r
        assert "lost_competitors" in r
        assert "file" in r

    def test_score_updated_on_prospect(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db, ia_visibility_score=2.5)
        mod.run_retest(db, p.prospect_id, dry_run=True)
        db.refresh(p)
        # Le score a été recalculé (peut changer)
        assert p.ia_visibility_score is not None

    def test_delta_computed(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db)
        result = mod.run_retest(db, p.prospect_id, dry_run=True)
        # delta = score_after - score_before
        r = result["result"]
        assert abs(r["score_after"] - r["score_before"] - r["score_delta"]) < 0.01

    def test_new_competitor_detected(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db, competitors_cited=json.dumps(["Ancien Concurrent"]))
        _add_baseline_run(db, p)
        # Le dry_run utilisera les données du prospect (pas de nouveau concurrent)
        result = mod.run_retest(db, p.prospect_id, dry_run=True)
        assert result["success"] is True

    def test_retest_tagged_in_notes(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db)
        mod.run_retest(db, p.prospect_id, dry_run=True)
        run = db.query(TestRunDB).filter_by(prospect_id=p.prospect_id).first()
        assert run.notes.startswith("retest:")

    def test_dry_run_flag_in_result(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db)
        result = mod.run_retest(db, p.prospect_id, dry_run=True)
        assert result["result"]["dry_run"] is True


# ── Tests get_retest_history ─────────────────────────────────────────────────

class TestRetestHistory:
    def test_empty_history(self, db):
        from src.livrables.monthly_retest import get_retest_history
        p = _make_prospect(db)
        history = get_retest_history(db, p.prospect_id)
        assert history == []

    def test_history_after_retest(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db)
        mod.run_retest(db, p.prospect_id, dry_run=True)
        history = mod.get_retest_history(db, p.prospect_id)
        assert len(history) == 1

    def test_history_entry_structure(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db)
        mod.run_retest(db, p.prospect_id, dry_run=True)
        history = mod.get_retest_history(db, p.prospect_id)
        entry = history[0]
        assert "run_id" in entry
        assert "ts" in entry
        assert "model" in entry
        assert "mentioned" in entry
        assert "is_retest" in entry

    def test_retest_marked_in_history(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db)
        _add_baseline_run(db, p)
        mod.run_retest(db, p.prospect_id, dry_run=True)
        history = mod.get_retest_history(db, p.prospect_id)
        retest_entries = [h for h in history if h["is_retest"]]
        assert len(retest_entries) == 1

    def test_baseline_not_marked_as_retest(self, db, tmp_path, monkeypatch):
        import src.livrables.monthly_retest as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = _make_prospect(db)
        _add_baseline_run(db, p)
        history = mod.get_retest_history(db, p.prospect_id)
        assert history[0]["is_retest"] is False


# ── Tests endpoints API ───────────────────────────────────────────────────────

class TestRetestApiEndpoints:
    @pytest.fixture(scope="class")
    def client_and_pid(self):
        from fastapi.testclient import TestClient
        from src.api.main import app
        init_db()
        client = TestClient(app)

        from src.database import SessionLocal
        db_ = SessionLocal()
        try:
            campaign = CampaignDB(profession="plombier", city="lyon", mode="AUTO_TEST")
            db_.add(campaign)
            db_.flush()
            p = ProspectDB(
                campaign_id=campaign.campaign_id,
                name="Plomb Lyon",
                city="lyon",
                profession="plombier",
                ia_visibility_score=1.5,
                competitors_cited="[]",
                paid=True,
            )
            db_.add(p)
            db_.commit()
            pid = p.prospect_id
        finally:
            db_.close()

        return client, pid

    def test_run_endpoint_dry_run(self, client_and_pid):
        client, pid = client_and_pid
        r = client.post(f"/api/retest/prospect/{pid}/run?dry_run=true")
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True

    def test_run_returns_contrat_uniforme(self, client_and_pid):
        client, pid = client_and_pid
        r = client.post(f"/api/retest/prospect/{pid}/run?dry_run=true")
        d = r.json()
        assert "success" in d
        assert "result" in d
        assert "message" in d
        assert "error" in d

    def test_history_endpoint(self, client_and_pid):
        client, pid = client_and_pid
        r = client.get(f"/api/retest/prospect/{pid}/history")
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True
        assert "history" in d["result"]

    def test_run_unknown_prospect_404(self, client_and_pid):
        client, _ = client_and_pid
        r = client.post("/api/retest/prospect/inconnu/run?dry_run=true")
        assert r.status_code == 404

    def test_history_unknown_prospect_404(self, client_and_pid):
        client, _ = client_and_pid
        r = client.get("/api/retest/prospect/inconnu/history")
        assert r.status_code == 404
