"""
Tests POST /api/prospect-scan/auto + module google_places
Toutes les requêtes HTTP Google sont mockées.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path):
    os.environ["DB_PATH"] = str(tmp_path / "test.db")
    os.environ["GOOGLE_MAPS_API_KEY"] = "fake-key"
    from src.api.main import app
    from src.database import init_db
    init_db()
    with TestClient(app) as c:
        yield c


def _mock_text_search(places: list):
    """Retourne un mock requests.get pour TextSearch."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"status": "OK", "results": places}
    return resp


def _mock_details(website=None, phone=None, ratings=None):
    """Retourne un mock requests.get pour Place Details."""
    result = {"name": "test"}
    if website:  result["website"] = website
    if phone:    result["formatted_phone_number"] = phone
    if ratings is not None: result["user_ratings_total"] = ratings
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"status": "OK", "result": result}
    return resp


# ── Tests unitaires google_places ─────────────────────────────────────────

class TestSearchProspects:

    def _places(self, names_websites):
        """Génère des places + details mockés."""
        places = [{"place_id": f"pid{i}", "name": n, "user_ratings_total": 10 + i}
                  for i, (n, _) in enumerate(names_websites)]
        details_resps = [_mock_details(website=w, phone="0600000001", ratings=10 + i)
                         for i, (_, w) in enumerate(names_websites)]
        return places, details_resps

    def test_filtre_sans_website(self):
        """Les places sans website sont exclues."""
        from src.google_places import search_prospects
        places = [{"place_id": "p1", "name": "Sans Site", "user_ratings_total": 5}]
        detail_resp = _mock_details(website=None)  # pas de site

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_text_search(places),
                detail_resp,
            ]
            prospects, reasons = search_prospects("couvreur", "Rennes", "fake-key", max_results=5)

        assert prospects == []
        assert any("pas de site web" in r for r in reasons)

    def test_inclut_avec_website(self):
        """Place avec website incluse dans les résultats."""
        from src.google_places import search_prospects
        places = [{"place_id": "p1", "name": "Couverture Rennaise", "user_ratings_total": 42}]
        detail_resp = _mock_details(website="https://www.couverture-rennaise.fr",
                                    phone="0299000001", ratings=42)

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [_mock_text_search(places), detail_resp]
            prospects, reasons = search_prospects("couvreur", "Rennes", "fake-key", max_results=5)

        assert len(prospects) == 1
        assert prospects[0]["name"] == "Couverture Rennaise"
        assert prospects[0]["website"] == "https://www.couverture-rennaise.fr"
        assert prospects[0]["phone"] == "0299000001"
        assert prospects[0]["reviews_count"] == 42

    def test_dedupe_par_domaine(self):
        """Deux places avec le même domaine → seule la première est gardée."""
        from src.google_places import search_prospects
        places = [
            {"place_id": "p1", "name": "Martin Toiture",  "user_ratings_total": 10},
            {"place_id": "p2", "name": "Martin Toiture 2", "user_ratings_total": 5},
        ]
        same_url = "https://martin-toiture.fr/contact"
        d1 = _mock_details(website=same_url, ratings=10)
        d2 = _mock_details(website="https://www.martin-toiture.fr", ratings=5)  # même domaine

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [_mock_text_search(places), d1, d2]
            prospects, reasons = search_prospects("couvreur", "Rennes", "fake-key", max_results=5)

        assert len(prospects) == 1
        assert any("doublon" in r for r in reasons)

    def test_max_results_respecte(self):
        """On ne dépasse pas max_results."""
        from src.google_places import search_prospects
        places = [{"place_id": f"p{i}", "name": f"Artisan {i}", "user_ratings_total": i}
                  for i in range(10)]
        details = [_mock_details(website=f"https://artisan{i}.fr", ratings=i)
                   for i in range(10)]

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [_mock_text_search(places)] + details
            prospects, _ = search_prospects("couvreur", "Rennes", "fake-key", max_results=3)

        assert len(prospects) == 3

    def test_zero_results(self):
        """ZERO_RESULTS Google → liste vide sans erreur."""
        from src.google_places import search_prospects
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"status": "ZERO_RESULTS", "results": []}

        with patch("requests.get", return_value=resp):
            prospects, reasons = search_prospects("couvreur", "Rennes", "fake-key")

        assert prospects == []

    def test_api_error_leve_exception(self):
        """Statut REQUEST_DENIED → ValueError levée."""
        from src.google_places import search_prospects
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"status": "REQUEST_DENIED", "error_message": "Invalid key"}

        with patch("requests.get", return_value=resp):
            with pytest.raises(ValueError, match="REQUEST_DENIED"):
                search_prospects("couvreur", "Rennes", "bad-key")

    def test_details_error_saute_place(self):
        """Erreur sur Place Details → place sautée, pas d'exception globale."""
        from src.google_places import search_prospects
        places = [
            {"place_id": "p1", "name": "Artisan OK",  "user_ratings_total": 5},
            {"place_id": "p2", "name": "Artisan ERR", "user_ratings_total": 3},
        ]
        ok_detail  = _mock_details(website="https://artisan-ok.fr", ratings=5)
        err_detail = MagicMock()
        err_detail.raise_for_status.side_effect = Exception("timeout")

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [_mock_text_search(places), ok_detail, err_detail]
            prospects, reasons = search_prospects("couvreur", "Rennes", "fake-key", max_results=5)

        assert len(prospects) == 1
        assert any("erreur détails" in r for r in reasons)


# ── Tests endpoint POST /api/prospect-scan/auto ────────────────────────────

class TestAutoScanEndpoint:

    def _places_setup(self, mock_get, items):
        """
        items: list of (name, website)  — les places retournées par Google
        Configure mock_get.side_effect : 1 TextSearch + N Details
        """
        places = [{"place_id": f"pid{i}", "name": n, "user_ratings_total": 20}
                  for i, (n, _) in enumerate(items)]
        details = [_mock_details(website=w, phone="0600000001", ratings=20)
                   for (_, w) in items]
        mock_get.side_effect = [_mock_text_search(places)] + details

    def test_retourne_200_et_created(self, client):
        with patch("requests.get") as mock_get:
            self._places_setup(mock_get, [
                ("Couverture Rennaise", "https://couverture-rennaise.fr"),
                ("Martin Toiture",      "https://martin-toiture.fr"),
            ])
            r = client.post("/api/prospect-scan/auto",
                            json={"city": "Rennes", "profession": "couvreur"})
        assert r.status_code == 200
        data = r.json()
        assert data["created"] == 2
        assert data["source"] == "google_places"
        assert "campaign_id" in data

    def test_prospects_ont_website(self, client):
        with patch("requests.get") as mock_get:
            self._places_setup(mock_get, [
                ("Couverture Rennaise", "https://couverture-rennaise.fr"),
            ])
            r = client.post("/api/prospect-scan/auto",
                            json={"city": "Rennes", "profession": "couvreur"})
        p = r.json()["prospects"][0]
        assert p["website"] == "https://couverture-rennaise.fr"

    def test_sans_cle_retourne_400(self, client):
        backup = os.environ.pop("GOOGLE_MAPS_API_KEY", None)
        r = client.post("/api/prospect-scan/auto",
                        json={"city": "Rennes", "profession": "couvreur"})
        assert r.status_code == 400
        assert "GOOGLE_MAPS_API_KEY" in r.json()["detail"]
        if backup: os.environ["GOOGLE_MAPS_API_KEY"] = backup

    def test_skipped_et_reasons(self, client):
        """Places sans site → comptés dans skipped + reasons."""
        places = [
            {"place_id": "p1", "name": "Avec Site",    "user_ratings_total": 10},
            {"place_id": "p2", "name": "Sans Site",    "user_ratings_total": 5},
        ]
        d1 = _mock_details(website="https://avec-site.fr", ratings=10)
        d2 = _mock_details(website=None)

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [_mock_text_search(places), d1, d2]
            r = client.post("/api/prospect-scan/auto",
                            json={"city": "Rennes", "profession": "couvreur"})

        data = r.json()
        assert data["created"] == 1
        assert data["skipped"] == 1
        assert len(data["reasons"]) == 1

    def test_campaign_id_existant(self, client):
        """Si campaign_id fourni et valide, on y rattache les prospects."""
        # Créer une campagne d'abord
        cr = client.post("/api/campaign/create",
                         json={"city": "Rennes", "profession": "couvreur"})
        cid = cr.json()["campaign_id"]

        with patch("requests.get") as mock_get:
            self._places_setup(mock_get, [
                ("Couverture Rennaise", "https://couverture-rennaise.fr"),
            ])
            r = client.post("/api/prospect-scan/auto",
                            json={"city": "Rennes", "profession": "couvreur",
                                  "campaign_id": cid})

        assert r.json()["campaign_id"] == cid

    def test_campaign_id_invalide_404(self, client):
        with patch("requests.get") as mock_get:
            self._places_setup(mock_get, [
                ("Couverture Rennaise", "https://couverture-rennaise.fr"),
            ])
            r = client.post("/api/prospect-scan/auto",
                            json={"city": "Rennes", "profession": "couvreur",
                                  "campaign_id": "inexistant-id"})
        assert r.status_code == 404

    def test_dedupe_endpoint(self, client):
        """Deux places même domaine → 1 seul créé en DB."""
        places = [
            {"place_id": "p1", "name": "Martin A", "user_ratings_total": 10},
            {"place_id": "p2", "name": "Martin B", "user_ratings_total": 5},
        ]
        d1 = _mock_details(website="https://martin-toiture.fr",     ratings=10)
        d2 = _mock_details(website="https://www.martin-toiture.fr", ratings=5)

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [_mock_text_search(places), d1, d2]
            r = client.post("/api/prospect-scan/auto",
                            json={"city": "Rennes", "profession": "couvreur"})

        data = r.json()
        assert data["created"] == 1
        assert data["skipped"] == 1

    def test_google_api_error_502(self, client):
        """Erreur Google API → 502."""
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"status": "REQUEST_DENIED", "error_message": "Invalid key"}
        with patch("requests.get", return_value=resp):
            r = client.post("/api/prospect-scan/auto",
                            json={"city": "Rennes", "profession": "couvreur"})
        assert r.status_code == 502
