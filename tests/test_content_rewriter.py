"""Tests — chantier 10C : content rewriter (scraping + réécriture LLM)."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def make_prospect(**kwargs):
    p = MagicMock()
    p.prospect_id = kwargs.get("prospect_id", "test-cr-001")
    p.name        = kwargs.get("name", "Toit Mon Toit")
    p.city        = kwargs.get("city", "Brest")
    p.profession  = kwargs.get("profession", "couvreur")
    p.website     = kwargs.get("website", "https://toit-mon-toit.fr")
    p.reviews_count = kwargs.get("reviews_count", 32)
    return p


def _mock_response(html: str, status: int = 200):
    r = MagicMock()
    r.status_code = status
    r.text = html
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return r


_HOME_HTML = """
<html><head><title>Toit Mon Toit — Couvreur Brest</title></head>
<body>
<h1>Couvreur à Brest</h1>
<h2>Nos services</h2>
<p>Entreprise de couverture spécialisée dans la réfection de toitures en Bretagne.</p>
<p>Intervention rapide sur Brest et ses environs, devis gratuit.</p>
<a href="/a-propos">À propos</a>
<a href="/services">Nos services</a>
</body></html>
"""


class TestScrapePageUnit:
    def test_scrapes_title_h1_h2_paragraphs(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)

        with patch("src.livrables.content_rewriter.requests.get") as mock_get:
            mock_get.return_value = _mock_response(_HOME_HTML)
            result = mod.scrape_page("https://toit-mon-toit.fr")

        assert result["title"] == "Toit Mon Toit — Couvreur Brest"
        assert "Couvreur" in result["h1"]
        assert len(result["h2s"]) >= 1
        assert len(result["paragraphs"]) >= 1

    def test_returns_error_dict_on_failure(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)

        with patch("src.livrables.content_rewriter.requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            result = mod.scrape_page("https://site-inexistant.fr")

        assert "error" in result
        assert result["url"] == "https://site-inexistant.fr"

    def test_strips_nav_footer_script(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        html = """<html><head><title>T</title></head><body>
        <nav><p>Ce texte nav ne doit pas apparaître</p></nav>
        <h1>Vrai H1</h1>
        <p>Vrai paragraphe assez long pour être inclus dans les résultats.</p>
        <footer><p>Ce texte footer ne doit pas apparaître</p></footer>
        </body></html>"""
        with patch("src.livrables.content_rewriter.requests.get") as mock_get:
            mock_get.return_value = _mock_response(html)
            result = mod.scrape_page("https://test.fr")

        assert result["h1"] == "Vrai H1"
        for para in result["paragraphs"]:
            assert "nav" not in para.lower()
            assert "footer" not in para.lower()


class TestFindSubpages:
    def test_detects_about_and_services(self):
        from src.livrables.content_rewriter import _find_subpages
        found = _find_subpages("https://test.fr", _HOME_HTML)
        assert "about" in found
        assert "services" in found

    def test_absolute_href_kept(self):
        from src.livrables.content_rewriter import _find_subpages
        html = '<html><body><a href="https://test.fr/a-propos">À propos</a></body></html>'
        found = _find_subpages("https://test.fr", html)
        assert found.get("about") == "https://test.fr/a-propos"

    def test_relative_href_resolved(self):
        from src.livrables.content_rewriter import _find_subpages
        html = '<html><body><a href="/services">Services</a></body></html>'
        found = _find_subpages("https://test.fr", html)
        assert found.get("services") == "https://test.fr/services"

    def test_empty_page_returns_empty(self):
        from src.livrables.content_rewriter import _find_subpages
        found = _find_subpages("https://test.fr", "<html></html>")
        assert found == {}


class TestRewriteContent:
    def _scraped(self):
        return {
            "url": "https://test.fr",
            "title": "Couvreur Brest",
            "h1": "Couvreur à Brest",
            "h2s": ["Nos services"],
            "paragraphs": ["Texte original de présentation."],
        }

    def test_rewritten_title_contains_city_and_profession(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect()
        result = mod._rewrite_page(self._scraped(), p)
        assert "Brest" in result["rewritten"]["title"]
        assert "couvreur" in result["rewritten"]["title"].lower()

    def test_rewritten_h1_contains_name(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        result = mod._rewrite_page(self._scraped(), make_prospect(name="Couverture Bretonne"))
        assert "Couverture Bretonne" in result["rewritten"]["h1"]

    def test_rewritten_intro_mentions_all_three(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        result = mod._rewrite_page(self._scraped(), make_prospect())
        intro = result["rewritten"]["intro"]
        assert "Brest" in intro
        assert "couvreur" in intro.lower()
        assert "Toit Mon Toit" in intro

    def test_signal_autorite_mentions_reviews(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        result = mod._rewrite_page(self._scraped(), make_prospect(reviews_count=50))
        assert "50" in result["rewritten"]["signal_autorite"]

    def test_signal_autorite_no_reviews_when_zero(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        result = mod._rewrite_page(self._scraped(), make_prospect(reviews_count=0))
        # Ne doit pas mentionner "0 avis"
        assert "0 avis" not in result["rewritten"]["signal_autorite"]

    def test_original_content_preserved(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        result = mod._rewrite_page(self._scraped(), make_prospect())
        assert result["original"]["h1"] == "Couvreur à Brest"


class TestGenerateContentRewrite:
    def test_no_website_returns_error(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        p = make_prospect(website=None)
        result = mod.generate_content_rewrite(p)
        assert result["pages_scraped"] == 0
        assert result["pages_failed"]

    def test_returns_required_keys(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        with patch("src.livrables.content_rewriter.requests.get") as mock_get:
            mock_get.return_value = _mock_response(_HOME_HTML)
            result = mod.generate_content_rewrite(make_prospect())

        assert "pages_scraped" in result
        assert "pages_failed" in result
        assert "rewrites" in result
        assert "file" in result

    def test_html_file_created(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        with patch("src.livrables.content_rewriter.requests.get") as mock_get:
            mock_get.return_value = _mock_response(_HOME_HTML)
            result = mod.generate_content_rewrite(make_prospect())

        assert Path(result["file"]).exists()

    def test_html_file_contains_prospect_name(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        with patch("src.livrables.content_rewriter.requests.get") as mock_get:
            mock_get.return_value = _mock_response(_HOME_HTML)
            result = mod.generate_content_rewrite(make_prospect(name="Couverture Nord"))

        html = Path(result["file"]).read_text()
        assert "Couverture Nord" in html

    def test_scrape_failure_still_generates_file(self, tmp_path, monkeypatch):
        """Même si le scraping échoue, on génère un fichier depuis les données prospect."""
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)
        with patch("src.livrables.content_rewriter.requests.get") as mock_get:
            mock_get.side_effect = Exception("Site inaccessible")
            result = mod.generate_content_rewrite(make_prospect())

        assert result["file"] is not None
        assert Path(result["file"]).exists()
        assert result["pages_scraped"] >= 1  # fallback prospect data

    def test_multiple_pages_scraped(self, tmp_path, monkeypatch):
        import src.livrables.content_rewriter as mod
        monkeypatch.setattr(mod, "DIST_DIR", tmp_path)

        # Retourner _HOME_HTML pour toutes les requêtes
        with patch("src.livrables.content_rewriter.requests.get") as mock_get:
            mock_get.return_value = _mock_response(_HOME_HTML)
            result = mod.generate_content_rewrite(make_prospect())

        # Au moins 2 pages (accueil + services ou about)
        assert result["pages_scraped"] >= 1
