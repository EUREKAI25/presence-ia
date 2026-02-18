"""
Tests Send Queue : enrich.py + upload routes + send-email
"""
import sys, os, io, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


# ── Fixture client ─────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path):
    os.environ["DB_PATH"]     = str(tmp_path / "test.db")
    os.environ["ADMIN_TOKEN"] = "test-token"
    os.environ["UPLOADS_DIR"] = str(tmp_path / "uploads")
    os.environ["BREVO_API_KEY"] = "brevo-test-key"
    from src.api.main import app
    from src.database import init_db
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def prospect_id(client):
    """Crée une campagne + un prospect éligible scoré."""
    # Créer campagne
    cr = client.post("/api/campaign/create",
                     json={"city": "Rennes", "profession": "couvreur"})
    cid = cr.json()["campaign_id"]

    # Créer prospect via scan manuel
    r = client.post("/api/prospect-scan", json={
        "city": "Rennes", "profession": "couvreur",
        "campaign_id": cid,
        "manual_prospects": [{
            "name": "Toiture Test SA",
            "website": "https://toiture-test.fr",
            "phone": "0299000001",
            "reviews_count": 42,
        }]
    })
    pid = r.json()["prospects"][0]["id"]

    # Forcer statut SCORED + éligible en DB
    from src.database import SessionLocal
    from src.models import ProspectDB
    db = SessionLocal()
    p = db.query(ProspectDB).filter_by(prospect_id=pid).first()
    p.status = "SCORED"
    p.eligibility_flag = True
    p.ia_visibility_score = 7.5
    p.competitors_cited = '["Martin Toiture", "Dupont Couverture"]'
    db.commit()
    db.close()
    return pid


# ── Tests enrich.py ────────────────────────────────────────────────────────

class TestEnrichEmail:

    def _resp(self, text: str, status=200):
        r = MagicMock()
        r.status_code = status
        r.text = text
        return r

    def test_trouve_email_simple(self):
        from src.enrich import extract_email_from_website
        html = '<a href="mailto:contact@toiture-bretonne.fr">Contactez-nous</a>'
        with patch("requests.get", return_value=self._resp(html)):
            assert extract_email_from_website("https://toiture-bretonne.fr") == "contact@toiture-bretonne.fr"

    def test_ignore_domaines_parasites(self):
        from src.enrich import extract_email_from_website
        html = 'src="https://cdn.example.com/js" data-email="test@google.com extra@sentry.io"'
        with patch("requests.get", return_value=self._resp(html)):
            # Aucun email valide (tous dans _IGNORE_DOMAINS)
            assert extract_email_from_website("https://toiture.fr") is None

    def test_retourne_none_si_aucun_email(self):
        from src.enrich import extract_email_from_website
        with patch("requests.get", return_value=self._resp("<html><body>Pas d'email ici</body></html>")):
            assert extract_email_from_website("https://toiture.fr") is None

    def test_retourne_none_si_exception(self):
        from src.enrich import extract_email_from_website
        with patch("requests.get", side_effect=Exception("timeout")):
            assert extract_email_from_website("https://toiture.fr") is None

    def test_retourne_none_si_url_vide(self):
        from src.enrich import extract_email_from_website
        assert extract_email_from_website("") is None
        assert extract_email_from_website(None) is None

    def test_premier_email_valide(self):
        from src.enrich import extract_email_from_website
        html = 'info@wordpress.org bonne@toiture.fr autre@toiture.fr'
        with patch("requests.get", return_value=self._resp(html)):
            # info@wordpress est ignoré (noreply prefix n'est pas dans IGNORE_PREFIXES mais
            # wordpress.org est dans IGNORE_DOMAINS) → retourne bonne@toiture.fr
            result = extract_email_from_website("https://toiture.fr")
            assert result == "bonne@toiture.fr"


# ── Tests endpoint enrich-email ────────────────────────────────────────────

class TestEnrichEmailEndpoint:

    def test_trouve_email(self, client, prospect_id):
        html = '<a href="mailto:toiture-test@gmail.com">Email</a>'
        mock_resp = MagicMock(); mock_resp.text = html
        with patch("src.enrich.http.get", return_value=mock_resp):
            r = client.post(f"/admin/prospect/{prospect_id}/enrich-email?token=test-token")
        assert r.status_code == 200
        assert r.json()["found"] is True
        assert r.json()["email"] == "toiture-test@gmail.com"

    def test_not_found(self, client, prospect_id):
        mock_resp = MagicMock(); mock_resp.text = "<html>Pas d'email</html>"
        with patch("src.enrich.http.get", return_value=mock_resp):
            r = client.post(f"/admin/prospect/{prospect_id}/enrich-email?token=test-token")
        assert r.status_code == 200
        assert r.json()["found"] is False

    def test_403_sans_token(self, client, prospect_id):
        r = client.post(f"/admin/prospect/{prospect_id}/enrich-email")
        assert r.status_code == 403


# ── Tests upload ────────────────────────────────────────────────────────────

class TestUpload:

    def test_upload_proof_image(self, client, prospect_id, tmp_path):
        content = b"fake-image-content"
        r = client.post(
            f"/admin/prospect/{prospect_id}/upload-proof-image?token=test-token",
            files={"file": ("proof.jpg", io.BytesIO(content), "image/jpeg")},
        )
        assert r.status_code == 200
        assert "url" in r.json()
        assert "proof.jpg" in r.json()["url"]

    def test_upload_city_image(self, client, prospect_id):
        r = client.post(
            f"/admin/prospect/{prospect_id}/upload-city-image?token=test-token",
            files={"file": ("city.jpg", io.BytesIO(b"city-img"), "image/jpeg")},
        )
        assert r.status_code == 200
        assert "city.jpg" in r.json()["url"]

    def test_upload_video_url(self, client, prospect_id):
        r = client.post(
            f"/admin/prospect/{prospect_id}/upload-video?token=test-token",
            data={"video_url": "https://youtube.com/watch?v=test"},
        )
        assert r.status_code == 200
        assert r.json()["url"] == "https://youtube.com/watch?v=test"

    def test_upload_video_sans_fichier_ni_url(self, client, prospect_id):
        r = client.post(
            f"/admin/prospect/{prospect_id}/upload-video?token=test-token",
        )
        assert r.status_code == 400

    def test_upload_prospect_inconnu_404(self, client):
        r = client.post(
            "/admin/prospect/inexistant/upload-proof-image?token=test-token",
            files={"file": ("p.jpg", io.BytesIO(b"x"), "image/jpeg")},
        )
        assert r.status_code == 404


# ── Tests send-email ────────────────────────────────────────────────────────

class TestSendEmail:

    def _set_email(self, prospect_id: str, email: str):
        from src.database import SessionLocal
        from src.models import ProspectDB
        db = SessionLocal()
        p = db.query(ProspectDB).filter_by(prospect_id=prospect_id).first()
        p.email = email
        db.commit(); db.close()

    def test_400_si_pas_email(self, client, prospect_id):
        r = client.post(f"/admin/prospect/{prospect_id}/send-email?token=test-token")
        assert r.status_code == 400
        assert "email" in r.json()["detail"].lower()

    def test_envoie_via_brevo(self, client, prospect_id):
        self._set_email(prospect_id, "artisan@toiture-test.fr")
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"messageId": "abc123"}
        with patch("src.api.routes.upload.http.post", return_value=mock_resp):
            r = client.post(f"/admin/prospect/{prospect_id}/send-email?token=test-token")
        assert r.status_code == 200
        d = r.json()
        assert d["sent"] is True
        assert d["email"] == "artisan@toiture-test.fr"
        assert d["message_id"] == "abc123"

    def test_502_si_brevo_echoue(self, client, prospect_id):
        self._set_email(prospect_id, "artisan@toiture-test.fr")
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"message":"Bad request"}'
        with patch("src.api.routes.upload.http.post", return_value=mock_resp):
            r = client.post(f"/admin/prospect/{prospect_id}/send-email?token=test-token")
        assert r.status_code == 502


# ── Test page send-queue ────────────────────────────────────────────────────

class TestSendQueuePage:

    def test_retourne_200(self, client, prospect_id):
        r = client.get("/admin/send-queue?token=test-token")
        assert r.status_code == 200
        assert "Send Queue" in r.text

    def test_affiche_prospect(self, client, prospect_id):
        r = client.get("/admin/send-queue?token=test-token")
        assert "Toiture Test SA" in r.text

    def test_403_sans_token(self, client):
        r = client.get("/admin/send-queue")
        assert r.status_code == 403
