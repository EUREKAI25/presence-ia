"""
Tests du module scoring
Signatures réelles :
  _email_ok(runs)         → (bool, str)
  _score(p, runs, ok)     → (float, str, list)
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────

def make_prospect(website=None, google_ads=False, reviews_count=0):
    p = MagicMock()
    p.prospect_id         = "test-001"
    p.name                = "Couvreur Test"
    p.city                = "Lyon"
    p.profession          = "couvreur"
    p.website             = website
    p.google_ads_active   = google_ads
    p.reviews_count       = reviews_count
    p.eligibility_flag    = False
    p.ia_visibility_score = None
    p.competitors_cited   = json.dumps([])
    return p


def make_run(model, mentioned, mention_per_query, competitors):
    r = MagicMock()
    r.model                = model
    r.mentioned_target     = mentioned
    r.mention_per_query    = json.dumps(mention_per_query)
    r.competitors_entities = json.dumps(competitors)
    return r


# ── _email_ok ─────────────────────────────────────────────────────────────

class TestEmailOK:
    def _ok(self, runs):
        from src.scoring import _email_ok
        result, _ = _email_ok(runs)
        return result

    def test_invisible_3_modeles_4_requetes(self):
        """
        Invisible sur 3/3 modèles, 4/5 requêtes (qi=4 visible sur anthropic),
        concurrent stable (vu 3 fois) → EMAIL_OK.
        Note : by_query vérifie ALL runs pour chaque requête.
        """
        runs = [
            make_run("openai",    False, [False, False, False, False, False], ["concurrent alpha"]),
            make_run("anthropic", False, [False, False, False, False, True],  ["concurrent alpha"]),
            make_run("gemini",    False, [False, False, False, False, False], ["concurrent alpha"]),
        ]
        assert self._ok(runs) is True

    def test_visible_partout_non_eligible(self):
        runs = [
            make_run("openai",    True, [True]*5, []),
            make_run("anthropic", True, [True]*5, []),
        ]
        assert self._ok(runs) is False

    def test_invisible_sans_concurrent_stable_eligible(self):
        """Invisible sur 2 modèles, sans concurrent stable → éligible (règle v2 : concurrent non requis)."""
        runs = [
            make_run("openai",    False, [False]*5, ["alpha sa"]),
            make_run("anthropic", False, [False]*5, ["beta sarl"]),
        ]
        assert self._ok(runs) is True

    def test_aucun_run_non_eligible(self):
        assert self._ok([]) is False

    def test_un_seul_modele_insuffisant(self):
        """Un seul modèle < 2/3 → pas OK même invisible."""
        runs = [make_run("openai", False, [False]*5, ["concurrent alpha", "concurrent alpha"])]
        assert self._ok(runs) is False

    def test_trop_visible_sur_requetes(self):
        """Cité sur 3/5 requêtes → pas assez invisible."""
        runs = [
            make_run("openai",    False, [False,False,True,True,True], ["concurrent alpha"]),
            make_run("anthropic", False, [False,False,True,True,True], ["concurrent alpha"]),
        ]
        assert self._ok(runs) is False

    def test_retourne_justification(self):
        from src.scoring import _email_ok
        runs = [make_run("openai", False, [False]*5, ["concurrent alpha", "concurrent alpha"])]
        _, justif = _email_ok(runs)
        assert isinstance(justif, str) and len(justif) > 0


# ── _score ────────────────────────────────────────────────────────────────

class TestScore:
    def _score(self, runs, ok, website=None, google_ads=False, reviews_count=0):
        from src.scoring import _score
        p = make_prospect(website=website, google_ads=google_ads, reviews_count=reviews_count)
        score, _, _ = _score(p, runs, ok)
        return score

    def test_score_max(self):
        """ok=True + concurrents stables + ads + reviews + website → ≥ 8"""
        runs = [
            make_run("openai",    False, [False]*5, ["concurrent alpha"]),
            make_run("anthropic", False, [False]*5, ["concurrent alpha"]),
        ]
        s = self._score(runs, ok=True,
                        website="https://example.com",
                        google_ads=True,
                        reviews_count=25)
        assert s >= 8

    def test_score_faible_si_visible(self):
        """ok=False + pas de concurrents → score faible"""
        runs = [
            make_run("openai",    True, [True]*5, []),
            make_run("anthropic", True, [True]*5, []),
        ]
        s = self._score(runs, ok=False)
        assert s <= 4

    def test_score_dans_bornes(self):
        """Score toujours dans [0, 10]"""
        runs = [make_run("openai", False, [False]*5, ["concurrent alpha", "concurrent alpha"])]
        s = self._score(runs, ok=True)
        assert 0 <= s <= 10

    def test_score_retourne_concurrents_stables(self):
        from src.scoring import _score
        runs = [
            make_run("openai",    False, [False]*5, ["martin toiture"]),
            make_run("anthropic", False, [False]*5, ["martin toiture"]),
        ]
        p = make_prospect()
        _, _, stable = _score(p, runs, True)
        assert isinstance(stable, list) and len(stable) >= 1
