"""
Tests du module scoring — EMAIL_OK + score /10
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock
import json
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────

def make_prospect(runs):
    """Crée un prospect mock avec des runs simulés."""
    p = MagicMock()
    p.prospect_id = "test-001"
    p.name = "Couvreur Test"
    p.city = "Lyon"
    p.profession = "couvreur"
    p.website = None
    p.google_ads = False
    p.google_reviews_count = 3
    p.runs = runs
    p.eligibility_flag = False
    p.ia_visibility_score = None
    p.competitors_cited = json.dumps([])
    return p


def make_run(model, mentioned, mention_per_query, competitors):
    r = MagicMock()
    r.model = model
    r.mentioned_target = mentioned
    r.mention_per_query = json.dumps(mention_per_query)
    r.competitors_entities = json.dumps(competitors)
    return r


# ── EMAIL_OK ──────────────────────────────────────────────────────────────

class TestEmailOK:
    def _run_email_ok(self, runs):
        from src.scoring import _email_ok
        p = make_prospect(runs)
        return _email_ok(p)

    def test_invisible_2_models_4_queries(self):
        """Invisible sur 2/3 modèles, 4/5 requêtes → EMAIL_OK"""
        runs = [
            make_run("gpt-4o-mini", False, [False]*5, ["ConcurrentA"]),
            make_run("claude-haiku", False, [False, False, False, False, True], ["ConcurrentB"]),
            make_run("gemini", True, [True]*5, []),
        ]
        assert self._run_email_ok(runs) is True

    def test_visible_partout_non_eligible(self):
        """Toujours cité → pas EMAIL_OK"""
        runs = [
            make_run("gpt-4o-mini", True, [True]*5, []),
            make_run("claude-haiku", True, [True]*5, []),
        ]
        assert self._run_email_ok(runs) is False

    def test_pas_de_concurrent_non_eligible(self):
        """Invisible mais aucun concurrent → pas EMAIL_OK"""
        runs = [
            make_run("gpt-4o-mini", False, [False]*5, []),
            make_run("claude-haiku", False, [False]*5, []),
        ]
        assert self._run_email_ok(runs) is False

    def test_aucun_run_non_eligible(self):
        """Aucun run → pas EMAIL_OK"""
        assert self._run_email_ok([]) is False

    def test_un_seul_modele_non_eligible(self):
        """Un seul modèle (< 2/3) → pas EMAIL_OK même si invisible"""
        runs = [
            make_run("gpt-4o-mini", False, [False]*5, ["ConcurrentA"]),
        ]
        assert self._run_email_ok(runs) is False

    def test_visible_sur_trop_de_requetes(self):
        """Cité sur 3/5 requêtes → pas assez invisible → EMAIL_OK False"""
        runs = [
            make_run("gpt-4o-mini", False, [False, False, True, True, True], ["ConcurrentA"]),
            make_run("claude-haiku", False, [False, False, True, True, True], ["ConcurrentB"]),
        ]
        assert self._run_email_ok(runs) is False


# ── Score /10 ─────────────────────────────────────────────────────────────

class TestScore:
    def _run_score(self, runs, website=None, google_ads=False, google_reviews_count=0):
        from src.scoring import _score
        p = make_prospect(runs)
        p.website = website
        p.google_ads = google_ads
        p.google_reviews_count = google_reviews_count
        return _score(p)

    def test_score_max_invisible(self):
        """Invisible + concurrents + ads + reviews + website = 10"""
        runs = [
            make_run("gpt-4o-mini", False, [False]*5, ["ConcurrentA", "ConcurrentB"]),
            make_run("claude-haiku", False, [False]*5, ["ConcurrentC"]),
        ]
        score = self._run_score(runs, website="https://example.com",
                                google_ads=True, google_reviews_count=10)
        assert score >= 8  # au moins 8/10

    def test_score_zero_visible(self):
        """Toujours cité → score faible"""
        runs = [
            make_run("gpt-4o-mini", True, [True]*5, []),
            make_run("claude-haiku", True, [True]*5, []),
        ]
        score = self._run_score(runs)
        assert score <= 4

    def test_score_entre_bornes(self):
        """Score toujours dans [0, 10]"""
        runs = [
            make_run("gpt-4o-mini", False, [False, True, False, False, True], ["X"]),
        ]
        score = self._run_score(runs)
        assert 0 <= score <= 10
