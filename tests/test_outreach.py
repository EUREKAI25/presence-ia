"""Tests — chantier 07 : outreach sans email."""
import json
import pytest
from unittest.mock import MagicMock


def make_prospect(**kwargs):
    p = MagicMock()
    p.prospect_id    = kwargs.get("prospect_id", "test-out-001")
    p.name           = kwargs.get("name", "Toit Mon Toit")
    p.city           = kwargs.get("city", "Brest")
    p.profession     = kwargs.get("profession", "couvreur")
    p.website        = kwargs.get("website", "https://toit-mon-toit.fr")
    p.phone          = kwargs.get("phone", "02 98 00 00 00")
    p.reviews_count  = kwargs.get("reviews_count", 32)
    p.competitors_cited = json.dumps(kwargs.get("competitors", ["Toit Pro", "Express Couverture"]))
    p.ia_visibility_score = kwargs.get("score", 2.5)
    p.landing_token  = kwargs.get("landing_token", "abc123")
    return p


class TestOutreachGenerator:
    def test_returns_required_keys(self, tmp_path, monkeypatch):
        import src.livrables.outreach as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        r = mod.generate_outreach(p)
        assert "message_court" in r
        assert "message_long" in r
        assert "cta_url" in r
        assert "char_count_court" in r
        assert "files" in r

    def test_message_court_under_320_chars(self, tmp_path, monkeypatch):
        import src.livrables.outreach as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        r = mod.generate_outreach(p)
        assert r["char_count_court"] <= 320

    def test_message_court_contains_prospect_name(self, tmp_path, monkeypatch):
        import src.livrables.outreach as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(name="Couverture Bretonne")
        r = mod.generate_outreach(p)
        assert "Couverture Bretonne" in r["message_court"]

    def test_message_long_contains_city(self, tmp_path, monkeypatch):
        import src.livrables.outreach as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(city="Rennes")
        r = mod.generate_outreach(p)
        assert "Rennes" in r["message_long"]

    def test_cta_url_contains_landing_token(self, tmp_path, monkeypatch):
        import src.livrables.outreach as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(landing_token="xyz789")
        r = mod.generate_outreach(p)
        assert "xyz789" in r["cta_url"]

    def test_competitor_in_message_court(self, tmp_path, monkeypatch):
        import src.livrables.outreach as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(competitors=["Pro Couverture"])
        r = mod.generate_outreach(p)
        assert "Pro Couverture" in r["message_court"]

    def test_no_competitors_fallback(self, tmp_path, monkeypatch):
        import src.livrables.outreach as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(competitors=[])
        r = mod.generate_outreach(p)
        # Ne doit pas planter, utilise le fallback "vos concurrents"
        assert r["message_court"]
        assert "concurrents" in r["message_court"]

    def test_json_file_written(self, tmp_path, monkeypatch):
        import src.livrables.outreach as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        r = mod.generate_outreach(p)
        from pathlib import Path
        assert Path(r["files"]["json"]).exists()

    def test_json_file_valid_content(self, tmp_path, monkeypatch):
        import src.livrables.outreach as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        r = mod.generate_outreach(p)
        from pathlib import Path
        data = json.loads(Path(r["files"]["json"]).read_text())
        assert data["prospect_id"] == p.prospect_id
        assert "message_court" in data
        assert "message_long" in data

    def test_message_long_mentions_score(self, tmp_path, monkeypatch):
        import src.livrables.outreach as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(score=3.5)
        r = mod.generate_outreach(p)
        assert "3.5" in r["message_long"]
