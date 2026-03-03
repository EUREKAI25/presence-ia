"""Tests — chantier 10 : moteur de livrables clients."""
import json
import pytest
from unittest.mock import MagicMock


# ── Fixtures ────────────────────────────────────────────────────────────────

def make_prospect(**kwargs):
    p = MagicMock()
    p.prospect_id = kwargs.get("prospect_id", "test-pid-001")
    p.name = kwargs.get("name", "Toit Mon Toit")
    p.city = kwargs.get("city", "Brest")
    p.profession = kwargs.get("profession", "couvreur")
    p.website = kwargs.get("website", "https://toit-mon-toit.fr")
    p.phone = kwargs.get("phone", "02 98 00 00 00")
    p.reviews_count = kwargs.get("reviews_count", 32)
    p.competitors_cited = json.dumps(kwargs.get("competitors", ["Toit Pro", "Couverture Express"]))
    p.ia_visibility_score = kwargs.get("score", 2.5)
    p.score_justification = kwargs.get("justification", "Données structurées absentes, faible volume d'avis.")
    p.landing_token = kwargs.get("landing_token", "abc123")
    return p


def make_run(model="openai", queries=None, mentioned=False, competitors=None):
    r = MagicMock()
    r.model = model
    r.queries = json.dumps(queries or ["Quel est le meilleur couvreur à Brest ?"])
    r.mention_per_query = json.dumps([mentioned])
    r.competitors_entities = json.dumps(competitors or ["Toit Pro"])
    r.ts = MagicMock()
    r.ts.strftime = lambda fmt: "01/01/2026"
    return r


# ── Tests 10B — JSONLD_GENERATOR ────────────────────────────────────────────

class TestJsonldGenerator:
    def test_local_business_always_present(self, tmp_path, monkeypatch):
        import src.livrables.jsonld as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        result = mod.generate_jsonld(p)
        assert "local_business" in result["blocks"]
        lb = result["blocks"]["local_business"]
        assert lb["@type"] == "LocalBusiness"
        assert lb["name"] == "Toit Mon Toit"
        assert lb["address"]["addressLocality"] == "Brest"

    def test_aggregate_rating_when_reviews(self, tmp_path, monkeypatch):
        import src.livrables.jsonld as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(reviews_count=45)
        result = mod.generate_jsonld(p)
        lb = result["blocks"]["local_business"]
        assert "aggregateRating" in lb
        assert lb["aggregateRating"]["reviewCount"] == "45"

    def test_no_aggregate_rating_without_reviews(self, tmp_path, monkeypatch):
        import src.livrables.jsonld as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(reviews_count=0)
        result = mod.generate_jsonld(p)
        assert "aggregateRating" not in result["blocks"]["local_business"]

    def test_faq_page_when_items_provided(self, tmp_path, monkeypatch):
        import src.livrables.jsonld as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        faq_items = [{"question": "Quel couvreur à Brest ?", "answer": "Toit Mon Toit"}]
        result = mod.generate_jsonld(p, faq_items=faq_items)
        assert "faq_page" in result["blocks"]
        assert result["blocks"]["faq_page"]["@type"] == "FAQPage"

    def test_no_faq_page_without_items(self, tmp_path, monkeypatch):
        import src.livrables.jsonld as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        result = mod.generate_jsonld(p, faq_items=None)
        assert "faq_page" not in result["blocks"]

    def test_html_snippet_contains_script_tag(self, tmp_path, monkeypatch):
        import src.livrables.jsonld as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        result = mod.generate_jsonld(p)
        assert '<script type="application/ld+json">' in result["html_snippet"]

    def test_files_written(self, tmp_path, monkeypatch):
        import src.livrables.jsonld as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        mod.generate_jsonld(p)
        assert (tmp_path / p.prospect_id / "livrables" / "jsonld.json").exists()
        assert (tmp_path / p.prospect_id / "livrables" / "jsonld_snippet.html").exists()


# ── Tests 10D — EDITORIAL_CHECKLIST ─────────────────────────────────────────

class TestEditorialChecklist:
    def test_returns_10_items(self, tmp_path, monkeypatch):
        import src.livrables.checklist as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        result = mod.generate_checklist(p)
        assert result["total"] == 10

    def test_avis_item_shows_missing_count(self, tmp_path, monkeypatch):
        import src.livrables.checklist as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(reviews_count=10)
        result = mod.generate_checklist(p)
        avis_item = next(i for i in result["items"] if i["id"] == "avis")
        assert "30 avis manquants" in avis_item["label"]

    def test_avis_item_done_when_enough(self, tmp_path, monkeypatch):
        import src.livrables.checklist as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(reviews_count=50)
        result = mod.generate_checklist(p)
        avis_item = next(i for i in result["items"] if i["id"] == "avis")
        assert avis_item["done"] is True

    def test_html_file_written(self, tmp_path, monkeypatch):
        import src.livrables.checklist as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        result = mod.generate_checklist(p)
        assert (tmp_path / p.prospect_id / "livrables" / "checklist.html").exists()

    def test_html_contains_prospect_name(self, tmp_path, monkeypatch):
        import src.livrables.checklist as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(name="Couverture Bretonne")
        result = mod.generate_checklist(p)
        assert "Couverture Bretonne" in result["html"]

    def test_completion_pct_zero_by_default(self, tmp_path, monkeypatch):
        import src.livrables.checklist as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(reviews_count=5)
        result = mod.generate_checklist(p)
        assert result["completion_pct"] == 0


# ── Tests 10E — STRATEGIC_DOSSIER ───────────────────────────────────────────

class TestStrategicDossier:
    def _db_mock(self, runs=None):
        db = MagicMock()
        runs = runs or []

        import src.livrables.dossier as mod
        mod.db_list_runs = lambda _db, pid: runs
        return db

    def test_score_projection_baseline(self, tmp_path, monkeypatch):
        import src.livrables.dossier as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        mod.db_list_runs = lambda db, pid: []
        p = make_prospect(score=3.0)
        result = mod.generate_dossier(MagicMock(), p)
        assert result["summary"]["score_baseline"] == 3.0

    def test_score_projection_m6_capped_at_10(self, tmp_path, monkeypatch):
        import src.livrables.dossier as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        mod.db_list_runs = lambda db, pid: []
        p = make_prospect(score=9.0)
        result = mod.generate_dossier(MagicMock(), p)
        assert result["summary"]["score_m6"] <= 10.0

    def test_competitors_in_summary(self, tmp_path, monkeypatch):
        import src.livrables.dossier as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        mod.db_list_runs = lambda db, pid: []
        p = make_prospect(competitors=["Toit Pro", "Express Cover"])
        result = mod.generate_dossier(MagicMock(), p)
        assert "Toit Pro" in result["summary"]["competitors"]

    def test_html_file_written(self, tmp_path, monkeypatch):
        import src.livrables.dossier as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        mod.db_list_runs = lambda db, pid: []
        p = make_prospect()
        mod.generate_dossier(MagicMock(), p)
        assert (tmp_path / p.prospect_id / "livrables" / "dossier_strategique.html").exists()

    def test_html_contains_4_sections(self, tmp_path, monkeypatch):
        import src.livrables.dossier as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        mod.db_list_runs = lambda db, pid: []
        p = make_prospect()
        result = mod.generate_dossier(MagicMock(), p)
        for section in ["1. Pourquoi vous n'apparaissez pas", "2. Qui est cité", "3. Plan d'action", "4. Projections"]:
            assert section in result["html"]


# ── Tests 10A — FAQ_GENERATOR ────────────────────────────────────────────────

class TestFaqGenerator:
    def test_generates_pages_from_runs(self, tmp_path, monkeypatch):
        import src.livrables.faq as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        runs = [make_run(queries=["Quel couvreur à Brest ?", "Recommande un couvreur à Brest"])]
        mod.db_list_runs = lambda db, pid: runs
        p = make_prospect()
        result = mod.generate_faq(MagicMock(), p)
        assert result["count"] == 2

    def test_fallback_queries_when_no_runs(self, tmp_path, monkeypatch):
        import src.livrables.faq as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        mod.db_list_runs = lambda db, pid: []
        p = make_prospect()
        result = mod.generate_faq(MagicMock(), p)
        assert result["count"] == 3

    def test_jsonld_items_match_pages(self, tmp_path, monkeypatch):
        import src.livrables.faq as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        mod.db_list_runs = lambda db, pid: []
        p = make_prospect()
        result = mod.generate_faq(MagicMock(), p)
        assert len(result["jsonld_items"]) == result["count"]
        for item in result["jsonld_items"]:
            assert "question" in item
            assert "answer" in item

    def test_html_files_created(self, tmp_path, monkeypatch):
        import src.livrables.faq as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        mod.db_list_runs = lambda db, pid: []
        p = make_prospect()
        result = mod.generate_faq(MagicMock(), p)
        for f in result["files"]:
            from pathlib import Path
            assert Path(f).exists()

    def test_max_10_pages(self, tmp_path, monkeypatch):
        import src.livrables.faq as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        many_queries = [f"Question {i} couvreur Brest" for i in range(15)]
        mod.db_list_runs = lambda db, pid: [make_run(queries=many_queries)]
        p = make_prospect()
        result = mod.generate_faq(MagicMock(), p)
        assert result["count"] <= 10

    def test_dedupe_queries(self, tmp_path, monkeypatch):
        import src.livrables.faq as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        q = "Quel couvreur à Brest ?"
        runs = [
            make_run(queries=[q, q, "Autre question"]),
            make_run(queries=[q]),
        ]
        mod.db_list_runs = lambda db, pid: runs
        p = make_prospect()
        result = mod.generate_faq(MagicMock(), p)
        queries = [pg["query"] for pg in result["pages"]]
        assert len(queries) == len(set(q.lower() for q in queries))
