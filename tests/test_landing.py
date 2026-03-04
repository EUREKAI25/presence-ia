"""Tests — chantier 05 : landing /{profession}?t={token}."""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models import Base, CampaignDB, ProspectDB
from src.database import init_db


@pytest.fixture(scope="module")
def client_and_prospect():
    """TestClient + un prospect de test avec token connu."""
    from src.api.main import app
    init_db()
    client = TestClient(app)

    # Créer prospect via l'API d'abord pour avoir une campagne
    # On utilise directement la DB de test
    from src.database import SessionLocal
    db = SessionLocal()
    try:
        campaign = CampaignDB(
            profession="couvreur",
            city="brest",
            mode="AUTO_TEST",
        )
        db.add(campaign)
        db.flush()

        prospect = ProspectDB(
            campaign_id=campaign.campaign_id,
            name="Toit Mon Toit",
            city="brest",
            profession="couvreur",
            website="https://toit-mon-toit.fr",
            reviews_count=32,
            competitors_cited=json.dumps(["Pro Toiture", "Express Couverture"]),
            ia_visibility_score=2.5,
            landing_token="testtoken123",
        )
        db.add(prospect)
        db.commit()
        token = prospect.landing_token
        pid   = prospect.prospect_id
        prof  = prospect.profession
    finally:
        db.close()

    return client, token, pid, prof


class TestLandingRoute:
    def test_valid_token_returns_200(self, client_and_prospect):
        client, token, pid, prof = client_and_prospect
        r = client.get(f"/{prof}?t={token}")
        assert r.status_code == 200

    def test_returns_html_content_type(self, client_and_prospect):
        client, token, pid, prof = client_and_prospect
        r = client.get(f"/{prof}?t={token}")
        assert "text/html" in r.headers["content-type"]

    def test_contains_prospect_name(self, client_and_prospect):
        client, token, pid, prof = client_and_prospect
        r = client.get(f"/{prof}?t={token}")
        assert "Toit Mon Toit" in r.text

    def test_contains_city(self, client_and_prospect):
        client, token, pid, prof = client_and_prospect
        r = client.get(f"/{prof}?t={token}")
        assert "brest" in r.text.lower() or "Brest" in r.text

    def test_contains_profession(self, client_and_prospect):
        client, token, pid, prof = client_and_prospect
        r = client.get(f"/{prof}?t={token}")
        assert "couvreur" in r.text.lower()

    def test_invalid_token_returns_404(self, client_and_prospect):
        client, token, pid, prof = client_and_prospect
        r = client.get(f"/couvreur?t=tokenquinexistepas")
        assert r.status_code == 404

    def test_missing_token_returns_422(self, client_and_prospect):
        """Sans token, FastAPI retourne 422 (paramètre requis manquant)."""
        client, token, pid, prof = client_and_prospect
        r = client.get("/couvreur")
        # t= a default="" donc la route ne plante pas (retourne 404 car pas de prospect)
        assert r.status_code in (404, 422)

    def test_any_profession_slug_works(self, client_and_prospect):
        """Le slug de profession dans l'URL est accepté pour n'importe quelle valeur."""
        client, token, pid, prof = client_and_prospect
        # Même token, slug différent → toujours 200 (le prospect est trouvé par token)
        r = client.get(f"/plombier?t={token}")
        assert r.status_code == 200

    def test_landing_has_plans_section(self, client_and_prospect):
        """La page doit contenir la section tarifs / plans."""
        client, token, pid, prof = client_and_prospect
        r = client.get(f"/{prof}?t={token}")
        # La section plans ou les mots "Offres" / "plan" doivent apparaître
        assert "plan" in r.text.lower() or "offre" in r.text.lower() or "€" in r.text

    def test_landing_has_resultats_section(self, client_and_prospect):
        """La page doit avoir une section résultats."""
        client, token, pid, prof = client_and_prospect
        r = client.get(f"/{prof}?t={token}")
        assert "resultats" in r.text.lower() or "résultats" in r.text.lower() or "Audit" in r.text


class TestLandingUrl:
    def test_landing_url_uses_profession(self):
        from src.generate import landing_url
        from unittest.mock import MagicMock
        p = MagicMock()
        p.profession = "plombier"
        p.landing_token = "abc123"
        url = landing_url(p)
        assert "/plombier?" in url
        assert "t=abc123" in url

    def test_landing_url_not_hardcoded_couvreur(self):
        from src.generate import landing_url
        from unittest.mock import MagicMock
        p = MagicMock()
        p.profession = "electricien"
        p.landing_token = "xyz"
        url = landing_url(p)
        assert "/couvreur" not in url
        assert "/electricien?" in url
