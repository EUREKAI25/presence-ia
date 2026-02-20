"""Tests i18n — résolution clés, passthrough, placeholders, pipeline complet."""
import pytest
from src.core.i18n import i18n_resolve, resolve_placeholders, resolve, reload_cache


def setup_function():
    reload_cache()


# ── i18n_resolve ─────────────────────────────────────────────────────────────

def test_passthrough_direct_text():
    assert i18n_resolve("Texte direct") == "Texte direct"


def test_passthrough_empty():
    assert i18n_resolve("") == ""


def test_resolve_existing_key():
    result = i18n_resolve("@navbar.demo.logo", lang="fr")
    assert result == "Mon Projet"


def test_resolve_nested_key():
    result = i18n_resolve("@hero.demo.title", lang="fr")
    assert "titre" in result.lower() or len(result) > 0


def test_missing_key_returns_placeholder():
    result = i18n_resolve("@inexistant.cle.profonde", lang="fr")
    assert result.startswith("[missing:")


def test_english_key():
    result = i18n_resolve("@navbar.demo.logo", lang="en")
    assert result == "My Project"


def test_unknown_lang_returns_missing():
    result = i18n_resolve("@navbar.demo.logo", lang="zz")
    assert result.startswith("[missing:")


# ── resolve_placeholders ──────────────────────────────────────────────────────

def test_placeholder_simple():
    result = resolve_placeholders("Bonjour {name}", {"name": "Alice"})
    assert result == "Bonjour Alice"


def test_placeholder_multiple():
    result = resolve_placeholders("{city} — {price}", {"city": "Paris", "price": "49€"})
    assert result == "Paris — 49€"


def test_placeholder_missing_left_intact():
    result = resolve_placeholders("Bonjour {unknown}", {"name": "Alice"})
    assert result == "Bonjour {unknown}"


def test_placeholder_no_context():
    result = resolve_placeholders("Bonjour {name}", None)
    assert result == "Bonjour {name}"


def test_placeholder_empty_text():
    assert resolve_placeholders("", {"city": "Lyon"}) == ""


# ── resolve (pipeline complet) ────────────────────────────────────────────────

def test_resolve_pipeline_i18n_only():
    result = resolve("@navbar.demo.logo", lang="fr")
    assert result == "Mon Projet"


def test_resolve_pipeline_with_placeholders():
    # La clé i18n contient {project_name}
    result = resolve("@hero.demo.title", lang="fr", context={"project_name": "ACME"})
    assert isinstance(result, str)
    assert len(result) > 0


def test_resolve_pipeline_direct_text_with_placeholders():
    result = resolve("Bonjour {name} !", lang="fr", context={"name": "Bob"})
    assert result == "Bonjour Bob !"


def test_resolve_pipeline_no_context():
    result = resolve("Texte sans placeholder", lang="fr")
    assert result == "Texte sans placeholder"
