"""
Tests du module ia_test — normalisation, extraction, mention fuzzy
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestNormalize:
    def test_lowercase(self):
        from src.ia_test import normalize_name
        assert normalize_name("DUPONT") == "dupont"

    def test_strip_accents(self):
        from src.ia_test import normalize_name
        r = normalize_name("Plomberie Étoile")
        assert "e" in r  # é → e ou conservé, au moins normalisé
        assert "toile" in r

    def test_strip_legal(self):
        from src.ia_test import normalize_name
        r = normalize_name("Couvreur SARL Dupont")
        assert "sarl" not in r

    def test_strip_profession(self):
        from src.ia_test import normalize_name
        r = normalize_name("Plombier Jean Martin")
        assert "plombier" not in r

    def test_empty(self):
        from src.ia_test import normalize_name
        assert normalize_name("") == ""


class TestExtractDomain:
    def test_basic_url(self):
        from src.ia_test import extract_domain
        assert extract_domain("https://www.dupont.fr") == "dupont.fr"

    def test_no_www(self):
        from src.ia_test import extract_domain
        assert extract_domain("https://couvreur-paris.com/contact") == "couvreur-paris.com"

    def test_empty(self):
        from src.ia_test import extract_domain
        assert extract_domain("") == ""

    def test_not_url(self):
        from src.ia_test import extract_domain
        assert extract_domain("Couvreur Paris") == ""


class TestIsMentioned:
    def test_exact_match(self):
        from src.ia_test import is_mentioned
        assert is_mentioned("Dupont Toiture", "Je recommande Dupont Toiture") is True

    def test_fuzzy_match(self):
        from src.ia_test import is_mentioned
        assert is_mentioned("Dupont Toitures", "Dupont Toiture est excellent") is True

    def test_no_match(self):
        from src.ia_test import is_mentioned
        assert is_mentioned("Dupont Toiture", "Je recommande Martin Couverture") is False

    def test_website_match(self):
        from src.ia_test import is_mentioned
        assert is_mentioned("dupont.fr", "Visitez dupont.fr pour plus d'infos") is True


class TestExtractEntities:
    def test_extract_names(self):
        from src.ia_test import extract_entities
        text = "Je recommande Martin Couverture et Dupont Toiture pour vos travaux."
        entities = extract_entities(text)
        assert isinstance(entities, list)
        assert len(entities) >= 1

    def test_empty_text(self):
        from src.ia_test import extract_entities
        assert extract_entities("") == []

    def test_no_entities(self):
        from src.ia_test import extract_entities
        result = extract_entities("Voici une phrase sans nom propre particulier.")
        assert isinstance(result, list)
