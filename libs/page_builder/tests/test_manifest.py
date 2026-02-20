"""Tests manifest — chargement seed, parse, render HTML."""
import json
import pytest
from pathlib import Path

from src.manifest.schema import ManifestPage, ManifestSection, ManifestColumn, ManifestBlockConfig
from src.manifest.parser import parse_manifest
from src.renderer.html import render_page

SEEDS_DIR = Path(__file__).parent.parent / "seeds"


# ── Chargement seed ───────────────────────────────────────────────────────────

def test_load_demo_landing_seed():
    path = SEEDS_DIR / "demo_landing.json"
    assert path.exists(), "seeds/demo_landing.json introuvable"
    with open(path) as f:
        data = json.load(f)
    manifest = ManifestPage(**data)
    assert manifest.page_type == "landing"
    assert manifest.lang == "fr"
    assert len(manifest.sections) > 0


# ── parse_manifest ────────────────────────────────────────────────────────────

def test_parse_manifest_returns_page():
    manifest = ManifestPage(
        title="Test",
        sections=[ManifestSection(
            key="hero",
            enabled=True,
            order=0,
            columns=[ManifestColumn(span=12, block=ManifestBlockConfig(
                block_type="hero_block",
                seed={"title": "Hello", "subtitle": "World"},
            ))],
        )],
    )
    page = parse_manifest(manifest)
    assert page.title == "Test"
    assert len(page.sections) == 1
    assert page.sections[0].columns[0].module.seed.title == "Hello"


def test_parse_manifest_disabled_section_excluded():
    manifest = ManifestPage(
        title="Test",
        sections=[
            ManifestSection(key="s1", enabled=True,  order=0, columns=[ManifestColumn(span=12, block=ManifestBlockConfig(block_type="hero_block", seed={"title": "Visible"}))]),
            ManifestSection(key="s2", enabled=False, order=1, columns=[ManifestColumn(span=12, block=ManifestBlockConfig(block_type="cta_block",  seed={"title": "Caché"}))]),
        ],
    )
    page = parse_manifest(manifest)
    assert len(page.sections) == 1
    assert page.sections[0].columns[0].module.seed.title == "Visible"


def test_parse_manifest_placeholder_resolved():
    manifest = ManifestPage(
        title="Page {name}",
        placeholder_context={"name": "ACME"},
        sections=[],
    )
    page = parse_manifest(manifest)
    assert page.title == "Page ACME"


def test_parse_manifest_i18n_resolved():
    manifest = ManifestPage(
        title="@navbar.demo.logo",
        lang="fr",
        sections=[],
    )
    page = parse_manifest(manifest)
    assert page.title == "Mon Projet"


def test_parse_manifest_unknown_block_raises():
    manifest = ManifestPage(
        title="Test",
        sections=[ManifestSection(
            key="x",
            enabled=True,
            order=0,
            columns=[ManifestColumn(span=12, block=ManifestBlockConfig(block_type="bloc_inexistant"))],
        )],
    )
    with pytest.raises(ValueError, match="Bloc inconnu"):
        parse_manifest(manifest)


# ── render_page depuis manifest ───────────────────────────────────────────────

def test_render_full_demo_seed():
    path = SEEDS_DIR / "demo_landing.json"
    with open(path) as f:
        data = json.load(f)
    manifest = ManifestPage(**data)
    manifest.placeholder_context = {"project_name": "ACME", "price": "49€"}

    page = parse_manifest(manifest)
    html = render_page(page)

    assert "<!DOCTYPE html>" in html
    assert "ACME" in html or "Mon Projet" in html  # i18n ou placeholder
    assert "hero" in html
    assert "--color-primary" in html


def test_render_page_has_theme_variables():
    manifest = ManifestPage(
        title="Test",
        theme={
            "color_system": {
                "primary":   {"base": "rgb(220, 38, 38)", "light": "rgb(239, 68, 68)", "dark": "rgb(185, 28, 28)"},
                "secondary": {"base": "rgb(100, 0, 0)",   "light": "rgb(120, 0, 0)",   "dark": "rgb(80, 0, 0)"},
            },
            "font_family_headings": "Inter",
            "font_family_body": "Inter",
            "style_preset_name": "rounded",
        },
        sections=[],
    )
    page = parse_manifest(manifest)
    html = render_page(page)
    # La couleur primaire doit être injectée dans le :root CSS
    assert "rgb(220, 38, 38)" in html or "220, 38, 38" in html


def test_render_page_sections_order():
    manifest = ManifestPage(
        title="Test",
        sections=[
            ManifestSection(key="b", enabled=True, order=2, columns=[ManifestColumn(span=12, block=ManifestBlockConfig(block_type="cta_block",  seed={"title": "CTA"}))]),
            ManifestSection(key="a", enabled=True, order=1, columns=[ManifestColumn(span=12, block=ManifestBlockConfig(block_type="stat_block", seed={"stats": []}))]),
        ],
    )
    page = parse_manifest(manifest)
    assert page.sections[0].id == "a"
    assert page.sections[1].id == "b"
