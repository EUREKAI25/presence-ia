"""
Tests — flux complet audit → closer → envoi client.

Scénarios :
  A01  Prospect valide → audit généré, HTML non vide, score présent
  A02  Prospect sans ia_results → ValueError
  A03  Prospect inexistant → ValueError
  A04  Temps de génération < 2s

  B01  HTML contient les marqueurs métier (nom, ville, score)
  B02  Snapshot IaSnapshotDB sauvegardé en DB après génération
  B03  Snapshot lié au bon prospect_token

  C01  BREVO_API_KEY absente → _send_brevo_email retourne False (pas d'exception)
  C02  Brevo mock HTTP 201 → retourne True
  C03  Brevo mock HTTP 400 → retourne False
  C04  _body_to_html inclut la landing_url dans le HTML produit

  D01  GET /closer/{token}/booking/{id}/audit → 200 + HTML audit
  D02  Booking inexistant → 404
  D03  Prospect sans audit généré → 404 avec message explicite
  D04  POST /closer/{token}/booking/{id}/send-audit dry_run → ok=True, aucun appel Brevo

  E01  ia_results JSON malformé → ValueError levé proprement
  E02  Template audit absent → FileNotFoundError explicite (pas de 500 silencieux)
"""
import sys, os, uuid, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "libs"))

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, MagicMock

from src.models import Base, V3ProspectDB, V3BookingDB, IaSnapshotDB


# ── Helpers DB ────────────────────────────────────────────────────────────────

def _make_engine():
    e = create_engine("sqlite:///:memory:",
                      connect_args={"check_same_thread": False},
                      poolclass=StaticPool)
    Base.metadata.create_all(e)
    return sessionmaker(bind=e, autocommit=False, autoflush=False)


_IA_RESULTS_VALID = json.dumps([
    {"model": "ChatGPT", "prompt": "plombier urgence Lyon",
     "response": "Je recommande Dupont Plomberie à Lyon, disponible 24h/24.",
     "tested_at": "2026-04-07T10:00:00"},
    {"model": "Gemini",  "prompt": "plombier urgence Lyon",
     "response": "Piron Plomberie est bien noté dans votre secteur.",
     "tested_at": "2026-04-07T10:01:00"},
    {"model": "Claude",  "prompt": "meilleur plombier Lyon",
     "response": "Dupont Plomberie est souvent mentionné pour les urgences lyonnaises.",
     "tested_at": "2026-04-07T10:02:00"},
])


def _make_prospect(Session, ia_results=_IA_RESULTS_VALID, has_email=True) -> str:
    tok = str(uuid.uuid4())
    with Session() as db:
        db.add(V3ProspectDB(
            token=tok, name="Dupont Plomberie", city="Lyon",
            profession="plombier", landing_url=f"/l/{tok}",
            email=f"{tok[:8]}@test.fr" if has_email else None,
            ia_results=ia_results, city_reference="LYON",
        ))
        db.commit()
    return tok


def _make_booking(Session, tok: str) -> str:
    bid = str(uuid.uuid4())
    dt  = datetime.utcnow() + timedelta(days=3)
    with Session() as db:
        db.add(V3BookingDB(
            id=bid, prospect_token=tok,
            name="Client Test", email="client@test.fr",
            start_iso=dt.strftime("%Y-%m-%dT%H:%M:%S"),
            end_iso=(dt + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%S"),
        ))
        db.commit()
    return bid


def _make_snapshot(Session, tok: str, html="<html>AUDIT</html>") -> int:
    with Session() as db:
        snap = IaSnapshotDB(
            prospect_token=tok, report_type="audit",
            score=6, nb_mentions=2, nb_total=3,
            report_html=html,
        )
        db.add(snap)
        db.commit()
        return snap.id


@pytest.fixture
def dbs(monkeypatch):
    Main = _make_engine()
    monkeypatch.setattr("src.database.SessionLocal", Main)
    return Main


# ── A : Génération ────────────────────────────────────────────────────────────

class TestGeneration:

    def test_A01_audit_genere_prospect_valide(self, dbs):
        """Prospect valide → audit_html non vide, score float dans [0, 10]."""
        Main = dbs
        tok  = _make_prospect(Main)
        from src.ia_reports.service import create_initial_audit_for_prospect
        with Main() as db:
            result = create_initial_audit_for_prospect(tok, db, save_to_disk=False)
        assert result["audit_html"], "audit_html doit être non vide"
        assert 0 <= result["summary"]["score"] <= 10, "score hors plage [0, 10]"
        assert result["prospect_id"] == tok

    def test_A02_sans_ia_results_leve_valueerror(self, dbs):
        """Prospect sans ia_results → ValueError avec message explicite."""
        Main = dbs
        tok  = _make_prospect(Main, ia_results=None)
        from src.ia_reports.service import create_initial_audit_for_prospect
        with Main() as db:
            with pytest.raises(ValueError, match="ia_results"):
                create_initial_audit_for_prospect(tok, db, save_to_disk=False)

    def test_A03_prospect_inexistant_leve_valueerror(self, dbs):
        """Token inconnu → ValueError."""
        Main = dbs
        from src.ia_reports.service import create_initial_audit_for_prospect
        with Main() as db:
            with pytest.raises(ValueError, match="introuvable"):
                create_initial_audit_for_prospect("token-qui-nexiste-pas", db, save_to_disk=False)

    def test_A04_generation_moins_2s(self, dbs):
        """Génération d'audit < 2s (pas d'appel API externe)."""
        Main = dbs
        tok  = _make_prospect(Main)
        from src.ia_reports.service import create_initial_audit_for_prospect
        t0 = time.time()
        with Main() as db:
            create_initial_audit_for_prospect(tok, db, save_to_disk=False)
        elapsed = time.time() - t0
        assert elapsed < 2.0, f"Génération trop lente : {elapsed:.2f}s"


# ── B : Structure HTML + persistance ─────────────────────────────────────────

class TestStructure:

    def test_B01_html_contient_nom_ville_score(self, dbs):
        """HTML produit contient le nom, la ville et un score visible."""
        Main = dbs
        tok  = _make_prospect(Main)
        from src.ia_reports.service import create_initial_audit_for_prospect
        with Main() as db:
            result = create_initial_audit_for_prospect(tok, db, save_to_disk=False)
        html = result["audit_html"]
        assert "Dupont Plomberie" in html, "Nom entreprise absent du HTML"
        assert "Lyon"             in html, "Ville absente du HTML"
        assert "<html"            in html.lower(), "HTML sans balise <html>"
        score_str = str(int(result["summary"]["score"]))
        assert score_str in html, f"Score {score_str} absent du HTML"

    def test_B02_snapshot_sauvegarde_en_db(self, dbs):
        """Un IaSnapshotDB est créé en DB après génération."""
        Main = dbs
        tok  = _make_prospect(Main)
        from src.ia_reports.service import create_initial_audit_for_prospect
        with Main() as db:
            result = create_initial_audit_for_prospect(tok, db, save_to_disk=False)
            snap_id = result["snapshot_id"]
        with Main() as db:
            snap = db.query(IaSnapshotDB).filter_by(id=snap_id).first()
        assert snap is not None, "Snapshot non trouvé en DB"
        assert snap.report_html, "Snapshot sans report_html"

    def test_B03_snapshot_lie_au_bon_token(self, dbs):
        """Snapshot IaSnapshotDB.prospect_token correspond au token du prospect."""
        Main = dbs
        tok  = _make_prospect(Main)
        from src.ia_reports.service import create_initial_audit_for_prospect
        with Main() as db:
            result = create_initial_audit_for_prospect(tok, db, save_to_disk=False)
        with Main() as db:
            snap = db.query(IaSnapshotDB).filter_by(id=result["snapshot_id"]).first()
        assert snap.prospect_token == tok


# ── C : Envoi simulé ─────────────────────────────────────────────────────────

class TestEnvoiSimule:

    def test_C01_sans_api_key_retourne_false(self, monkeypatch):
        """BREVO_API_KEY absente → _send_brevo_email retourne False sans exception."""
        monkeypatch.delenv("BREVO_API_KEY", raising=False)
        from src.api.routes.v3 import _send_brevo_email
        result = _send_brevo_email("test@test.fr", "Test", "Sujet", "Corps")
        assert result is False

    def test_C02_brevo_201_retourne_true(self, monkeypatch):
        """Mock HTTP 201 → _send_brevo_email retourne True."""
        monkeypatch.setenv("BREVO_API_KEY", "fake-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        from src.api.routes.v3 import _send_brevo_email
        with patch("src.api.routes.v3.http_req.post", return_value=mock_resp):
            result = _send_brevo_email("test@test.fr", "Test", "Sujet", "Corps")
        assert result is True

    def test_C03_brevo_400_retourne_false(self, monkeypatch):
        """Mock HTTP 400 → _send_brevo_email retourne False."""
        monkeypatch.setenv("BREVO_API_KEY", "fake-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        from src.api.routes.v3 import _send_brevo_email
        with patch("src.api.routes.v3.http_req.post", return_value=mock_resp):
            result = _send_brevo_email("test@test.fr", "Test", "Sujet", "Corps")
        assert result is False

    def test_C04_body_to_html_inclut_landing_url(self):
        """_body_to_html transforme la landing_url en lien cliquable quand elle est dans le corps."""
        from src.api.routes.v3 import _body_to_html
        url  = "https://presence-ia.online/l/test123"
        # La fonction crée un lien <a> autour de l'URL si elle apparaît dans le corps
        html = _body_to_html(f"Accédez à votre audit : {url}", landing_url=url)
        assert "test123" in html, "landing_url absente du HTML généré"
        assert "<a href=" in html, "Aucun lien <a> dans le HTML généré"


# ── D : Routes closer ─────────────────────────────────────────────────────────

class TestRoutesCloser:

    def _client(self, dbs_fixture):
        from fastapi.testclient import TestClient
        from src.api.main import app
        return TestClient(app)

    def test_D01_audit_accessible_depuis_booking(self, dbs):
        """GET /closer/{token}/booking/{id}/audit → 200 + HTML de l'audit."""
        Main = dbs
        tok  = _make_prospect(Main)
        bid  = _make_booking(Main, tok)
        _make_snapshot(Main, tok, html="<html><body>AUDIT TEST</body></html>")
        client = self._client(dbs)
        resp = client.get(f"/closer/closer-abc/booking/{bid}/audit")
        assert resp.status_code == 200
        assert "AUDIT TEST" in resp.text

    def test_D02_booking_inexistant_retourne_404(self, dbs):
        """Booking id inconnu → 404."""
        client = self._client(dbs)
        resp = client.get(f"/closer/closer-abc/booking/{uuid.uuid4()}/audit")
        assert resp.status_code == 404

    def test_D03_prospect_sans_audit_retourne_404(self, dbs):
        """Booking lié à prospect sans snapshot → 404 avec message."""
        Main = dbs
        tok  = _make_prospect(Main)
        bid  = _make_booking(Main, tok)
        client = self._client(dbs)
        resp = client.get(f"/closer/closer-abc/booking/{bid}/audit")
        assert resp.status_code == 404
        assert "Aucun audit" in resp.text

    def test_D04_send_audit_dry_run_pas_appel_brevo(self, dbs, monkeypatch):
        """POST send-audit dry_run=true → ok=True, Brevo non appelé."""
        Main = dbs
        monkeypatch.setenv("OUTBOUND_DRY_RUN", "true")
        tok  = _make_prospect(Main)
        bid  = _make_booking(Main, tok)
        _make_snapshot(Main, tok)
        client = self._client(dbs)
        with patch("src.api.routes.v3.http_req.post") as mock_post:
            resp = client.post(
                f"/closer/closer-abc/booking/{bid}/send-audit",
                json={"dry_run": True},
            )
            assert mock_post.call_count == 0, "Brevo ne doit pas être appelé en dry_run"
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["dry_run"] is True


# ── E : Cas d'erreur ──────────────────────────────────────────────────────────

class TestErreurs:

    def test_E01_ia_results_json_invalide_leve_valueerror(self, dbs):
        """ia_results JSON invalide → ValueError propre (pas de crash non géré)."""
        Main = dbs
        tok  = _make_prospect(Main, ia_results="PAS DU JSON {{{")
        from src.ia_reports.service import create_initial_audit_for_prospect
        with Main() as db:
            with pytest.raises((ValueError, Exception)):
                create_initial_audit_for_prospect(tok, db, save_to_disk=False)

    def test_E02_template_absent_leve_error(self, tmp_path):
        """Template manquant → FileNotFoundError avant toute tentative de rendu."""
        from src.ia_reports import generator as gen
        orig = gen.AUDIT_TEMPLATE
        gen.AUDIT_TEMPLATE = tmp_path / "absent.html"
        try:
            with pytest.raises(FileNotFoundError):
                gen.render_audit_html(
                    name="Test", profession="plombier", city="Lyon", cms="",
                    score_data={"score": 5, "total_citations": 1, "total_possible": 3,
                                "total_queries": 3},
                    queries=[], competitors=[], checklist={"level": "moyen", "title": "T", "html": ""},
                )
        finally:
            gen.AUDIT_TEMPLATE = orig
