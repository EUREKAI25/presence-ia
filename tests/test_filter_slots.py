"""
Tests — _filter_slots() : visibilité créneaux côté prospect.

Scénarios :
  F01  J+0 → toujours 0 créneau (jamais le jour même)
  F02  J+1 → max 1 créneau en mode normal
  F03  J+1 → max 2 créneaux en LAUNCH_MODE=true
  F04  Max 4 créneaux par jour (MAX_VISIBLE_SLOTS_PER_DAY=4)
  F05  Horizon 14 jours strict — rien au-delà
  F06  Déterminisme : même seed + même jour = même résultat
  F07  Tokens différents → sélections différentes (variabilité)
  F08  Slots dans le passé ignorés
  F09  Slots week-end présents mais filtrés si SlotDB ne les pousse pas
  F10  MAX_VISIBLE_SLOTS_PER_DAY=2 → cap à 2 même en J+3
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "libs"))

import pytest
from datetime import date, datetime, timedelta
from collections import Counter

from src.api.routes.v3 import _filter_slots


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slots_for_day(days_offset: int, count: int = 10) -> list:
    """Génère `count` créneaux pour le jour J+days_offset."""
    target = date.today() + timedelta(days=days_offset)
    slots  = []
    for h in range(9, 9 + count):
        start = datetime(target.year, target.month, target.day, h, 0)
        end   = start + timedelta(minutes=20)
        slots.append({
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end":   end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return slots


def _run(slots, monkeypatch, seed="token-test", **env):
    """Lance _filter_slots avec les env vars spécifiées (défauts sûrs)."""
    defaults = {
        "MAX_VISIBLE_SLOTS_PER_DAY": "4",
        "DAYS_VISIBLE_AHEAD":        "14",
        "LAUNCH_MODE":               "false",
    }
    defaults.update(env)
    for k, v in defaults.items():
        monkeypatch.setenv(k, v)
    return _filter_slots(slots, date.today(), seed)


def _slots_per_day(result: list) -> Counter:
    """Compte les créneaux par date dans le résultat."""
    return Counter(s["_dt"].date() for s in result)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestJourMeme:
    def test_F01_jour_zero_toujours_vide(self, monkeypatch):
        """J+0 : jamais de créneau affiché, peu importe le mode."""
        today_slots = _slots_for_day(0, count=10)
        result = _run(today_slots, monkeypatch)
        assert result == [], "J+0 doit toujours retourner 0 créneau"


class TestProximite:
    def test_F02_j1_max1_mode_normal(self, monkeypatch):
        """J+1 : au plus 1 créneau en mode normal."""
        slots = _slots_for_day(1, count=10)
        for _ in range(30):  # répétition pour couvrir la variabilité rng
            result = _run(slots, monkeypatch, seed=f"seed-{_}",
                          LAUNCH_MODE="false")
            count_j1 = sum(1 for s in result if s["_delta"] == 1)
            assert count_j1 <= 1, (
                f"J+1 mode normal : {count_j1} créneaux affichés > 1"
            )

    def test_F03_j1_max2_launch_mode(self, monkeypatch):
        """J+1 : au plus 2 créneaux en LAUNCH_MODE=true."""
        slots = _slots_for_day(1, count=10)
        for _ in range(30):
            result = _run(slots, monkeypatch, seed=f"seed-{_}",
                          LAUNCH_MODE="true")
            count_j1 = sum(1 for s in result if s["_delta"] == 1)
            assert count_j1 <= 2, (
                f"J+1 launch_mode : {count_j1} créneaux affichés > 2"
            )


class TestCapParJour:
    def test_F04_max_4_par_jour(self, monkeypatch):
        """Aucun jour ne dépasse MAX_VISIBLE_SLOTS_PER_DAY=4."""
        # 10 créneaux par jour sur J+2 à J+7
        slots = []
        for delta in range(2, 8):
            slots.extend(_slots_for_day(delta, count=10))
        for seed in ["aaa", "bbb", "ccc", "ddd", "eee"]:
            result = _run(slots, monkeypatch, seed=seed,
                          MAX_VISIBLE_SLOTS_PER_DAY="4")
            for d, n in _slots_per_day(result).items():
                assert n <= 4, f"Jour {d} : {n} créneaux > 4"

    def test_F04b_cap_respecte_valeur_custom(self, monkeypatch):
        """MAX_VISIBLE_SLOTS_PER_DAY=2 → jamais plus de 2/jour."""
        slots = []
        for delta in range(2, 6):
            slots.extend(_slots_for_day(delta, count=10))
        result = _run(slots, monkeypatch, seed="cap2test",
                      MAX_VISIBLE_SLOTS_PER_DAY="2")
        for d, n in _slots_per_day(result).items():
            assert n <= 2, f"Jour {d} : {n} créneaux > 2 avec cap=2"


class TestHorizon:
    def test_F05_rien_au_dela_14j(self, monkeypatch):
        """Aucun créneau affiché au-delà de DAYS_VISIBLE_AHEAD=14."""
        slots = []
        for delta in [10, 13, 14, 15, 20]:
            slots.extend(_slots_for_day(delta, count=5))
        result = _run(slots, monkeypatch, DAYS_VISIBLE_AHEAD="14")
        for s in result:
            assert s["_delta"] <= 14, (
                f"Créneau à J+{s['_delta']} affiché hors horizon 14j"
            )

    def test_F05b_horizon_custom_7j(self, monkeypatch):
        """DAYS_VISIBLE_AHEAD=7 → rien au-delà de J+7."""
        slots = []
        for delta in range(2, 12):
            slots.extend(_slots_for_day(delta, count=5))
        result = _run(slots, monkeypatch, DAYS_VISIBLE_AHEAD="7")
        for s in result:
            assert s["_delta"] <= 7


class TestDeterminisme:
    def test_F06_meme_seed_meme_resultat(self, monkeypatch):
        """Même seed + même jour = résultat identique (déterminisme)."""
        slots = []
        for delta in range(2, 8):
            slots.extend(_slots_for_day(delta, count=10))
        r1 = _run(slots, monkeypatch, seed="prospect-abc")
        r2 = _run(slots, monkeypatch, seed="prospect-abc")
        ids1 = [s["start"] for s in r1]
        ids2 = [s["start"] for s in r2]
        assert ids1 == ids2, "Même seed → doit produire exactement le même résultat"

    def test_F07_seeds_differentes_variabilite(self, monkeypatch):
        """Seeds différentes → sélections différentes (variabilité réelle)."""
        slots = []
        for delta in range(2, 8):
            slots.extend(_slots_for_day(delta, count=10))
        results = set()
        for seed in [f"p-{i}" for i in range(20)]:
            r = _run(slots, monkeypatch, seed=seed)
            results.add(tuple(s["start"] for s in r))
        # Avec 20 tokens différents, au moins 3 sélections distinctes
        assert len(results) >= 3, (
            "Seeds différentes devraient produire des sélections variées"
        )


class TestPassé:
    def test_F08_slots_passes_ignores(self, monkeypatch):
        """Créneaux passés (delta < 0) toujours ignorés."""
        past_slots = []
        for delta in [-5, -3, -1]:
            target = date.today() + timedelta(days=delta)
            past_slots.append({
                "start": datetime(target.year, target.month, target.day, 10, 0)
                         .strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end":   datetime(target.year, target.month, target.day, 10, 20)
                         .strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
        result = _run(past_slots, monkeypatch)
        assert result == [], "Les créneaux passés ne doivent jamais être affichés"
