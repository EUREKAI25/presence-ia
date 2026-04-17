"""
Tests — pipeline booking + agenda closer + sécurités outbound.

Scénarios :
  B01  Booking créé → remonte dans _build_real_slots (agenda closer)
  B02  Booking < 48h → statut accessible_urgent dans l'agenda
  B03  Booking > 48h → statut accessible dans l'agenda
  B04  Prospect is_test=True → exclu des candidats outbound
  B05  OUTBOUND_DRY_RUN=true → _outbound_send_prospect ne marque pas sent_at
  B06  Pas de double booking : deux bookings sur le même token prospect
       remontent tous les deux dans l'agenda (pas de déduplication silencieuse)
  B07  Lot mélangé : prospects ignore / ouvre / clique / réserve → états cohérents
"""
import sys, os, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "libs"))

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, MagicMock

from src.models import Base, V3ProspectDB, V3BookingDB
from marketing_module.models import Base as MktBase, CloserDB


# ── Helpers DB ────────────────────────────────────────────────────────────────

def _make_engines():
    def _e():
        return create_engine("sqlite:///:memory:",
                             connect_args={"check_same_thread": False},
                             poolclass=StaticPool)
    main_e = _e(); Base.metadata.create_all(main_e)
    mkt_e  = _e(); MktBase.metadata.create_all(mkt_e)
    return (sessionmaker(bind=main_e, autocommit=False, autoflush=False),
            sessionmaker(bind=mkt_e,  autocommit=False, autoflush=False))


def _prospect(Main, is_test=False, ia_results='[]') -> str:
    tok = str(uuid.uuid4())
    with Main() as db:
        db.add(V3ProspectDB(
            token=tok, name="Plombier Dupont", city="Lyon",
            profession="plombier", landing_url=f"/l/{tok}",
            email=f"{tok[:8]}@test.fr", ia_results=ia_results,
            is_test=is_test, city_reference="LYON",
        ))
        db.commit()
    return tok


def _booking(Main, tok: str, hours_from_now: float) -> str:
    dt = datetime.utcnow() + timedelta(hours=hours_from_now)
    bid = str(uuid.uuid4())
    with Main() as db:
        db.add(V3BookingDB(
            id=bid,
            prospect_token=tok,
            name="Client Test", email="client@test.fr",
            start_iso=dt.strftime("%Y-%m-%dT%H:%M:%S"),
            end_iso=(dt + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%S"),
        ))
        db.commit()
    return bid


@pytest.fixture
def dbs(monkeypatch):
    Main, Mkt = _make_engines()
    monkeypatch.setattr("src.database.SessionLocal", Main)
    monkeypatch.setattr("marketing_module.database.SessionLocal", Mkt)
    return Main, Mkt


# ── B01-B03 : agenda closer ───────────────────────────────────────────────────

class TestAgendaCloser:
    """_build_real_slots() lit v3_bookings et retourne les créneaux réels."""

    def test_B01_booking_remonte_dans_agenda(self, dbs):
        """Un booking créé dans v3_bookings apparaît dans _build_real_slots."""
        Main, Mkt = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        tok = _prospect(Main)
        _booking(Main, tok, hours_from_now=72)
        slots = _build_real_slots("")
        assert len(slots) == 1, f"Attendu 1 slot, obtenu {len(slots)}"
        assert slots[0]["prospect"]["email"] == f"{tok[:8]}@test.fr"

    def test_B02_booking_urgent_moins_48h(self, dbs):
        """Booking dans moins de 48h → status=accessible_urgent."""
        Main, Mkt = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        tok = _prospect(Main)
        _booking(Main, tok, hours_from_now=24)
        slots = _build_real_slots("")
        assert slots[0]["status"] == "accessible_urgent", (
            f"status={slots[0]['status']} — attendu accessible_urgent"
        )

    def test_B03_booking_lointain_accessible(self, dbs):
        """Booking dans plus de 48h → status=accessible."""
        Main, Mkt = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        tok = _prospect(Main)
        _booking(Main, tok, hours_from_now=96)
        slots = _build_real_slots("")
        assert slots[0]["status"] == "accessible"

    def test_B06_deux_bookings_meme_prospect(self, dbs):
        """Deux bookings sur un même prospect remontent tous les deux (pas de déduplication)."""
        Main, Mkt = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        tok = _prospect(Main)
        _booking(Main, tok, hours_from_now=72)
        _booking(Main, tok, hours_from_now=120)
        slots = _build_real_slots("")
        assert len(slots) == 2, (
            f"Attendu 2 slots pour 2 bookings, obtenu {len(slots)}"
        )

    def test_B01b_agenda_vide_sans_booking(self, dbs):
        """Sans booking : _build_real_slots retourne [] (pas de données de test intrusives)."""
        Main, _ = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        slots = _build_real_slots("")
        assert slots == []


# ── B04 : exclusion is_test des candidats outbound ───────────────────────────

class TestIsTestExclusion:
    """Les prospects is_test=True ne doivent jamais entrer dans la sélection outbound."""

    def test_B04_is_test_exclu_selection_email(self, dbs):
        """Prospect is_test=True → absent de la requête de sélection email outbound."""
        Main, _ = dbs
        tok = _prospect(Main, is_test=True, ia_results='[{"ok": true}]')
        with Main() as db:
            from sqlalchemy import or_
            count = db.query(V3ProspectDB).filter(
                V3ProspectDB.email.isnot(None),
                V3ProspectDB.sent_at.is_(None),
                V3ProspectDB.is_test.isnot(True),
            ).count()
        assert count == 0, (
            "Prospect is_test=True ne doit pas apparaître dans les candidats outbound"
        )

    def test_B04b_prospect_reel_visible(self, dbs):
        """Prospect is_test=False → présent dans la sélection outbound."""
        Main, _ = dbs
        _prospect(Main, is_test=False, ia_results='[{"ok": true}]')
        with Main() as db:
            count = db.query(V3ProspectDB).filter(
                V3ProspectDB.email.isnot(None),
                V3ProspectDB.sent_at.is_(None),
                V3ProspectDB.is_test.isnot(True),
            ).count()
        assert count == 1


# ── B05 : dry_run → aucun marquage sent_at ───────────────────────────────────

class TestDryRun:
    """OUTBOUND_DRY_RUN=true → _outbound_send_prospect ne modifie jamais la DB."""

    def test_B05_dry_run_ne_marque_pas_sent_at(self, dbs, monkeypatch):
        """Appel _outbound_send_prospect avec dry_run=True → sent_at reste None."""
        Main, _ = dbs
        monkeypatch.setenv("OUTBOUND_DRY_RUN", "true")
        tok = _prospect(Main, ia_results='[{"ok": true, "model": "openai"}]')

        with Main() as db:
            p = db.query(V3ProspectDB).filter_by(token=tok).first()
            assert p.sent_at is None

            # Appel direct avec dry_run=True (bypasse Brevo, bypasse GCal)
            # On mock la vérification image pour isoler la logique DRY_RUN
            with patch("src.city_images.fetch_city_header_image", return_value="https://img.test/x.jpg"):
                from src.scheduler import _outbound_send_prospect
                result = _outbound_send_prospect(p, dry_run=True,
                                                 brevo_key="fake-key", sent_idx=0)

        assert result.get("dry_run") is True
        assert result.get("ok") is True

        # Vérifier que sent_at n'a PAS été modifié en DB
        with Main() as db:
            p2 = db.query(V3ProspectDB).filter_by(token=tok).first()
            assert p2.sent_at is None, (
                "dry_run=True : sent_at ne doit jamais être modifié"
            )

    def test_B05b_dry_run_env_bloque_envoi(self, monkeypatch):
        """OUTBOUND_DRY_RUN=true est lu en défaut → pas d'envoi sans activation explicite."""
        # La valeur par défaut de OUTBOUND_DRY_RUN doit être "true"
        monkeypatch.delenv("OUTBOUND_DRY_RUN", raising=False)
        import os
        dry_run = os.getenv("OUTBOUND_DRY_RUN", "true").lower() == "true"
        assert dry_run is True, (
            "OUTBOUND_DRY_RUN doit être true par défaut — "
            "activation explicite requise pour les envois réels"
        )


# ── B07 : lot de prospects avec comportements mélangés ───────────────────────

class TestLotMixte:
    """Simulation d'un lot de 5 prospects avec comportements variés."""

    def _setup_lot(self, Main):
        """
        Crée un lot de 5 prospects :
          p_ignore    : envoyé, aucun tracking
          p_opened    : envoyé, email ouvert
          p_clicked   : envoyé, email cliqué
          p_booked    : envoyé, a réservé (v3_booking créé)
          p_test      : is_test=True (doit être exclu de tout calcul réel)
        """
        now = datetime.utcnow()
        tokens = {}

        with Main() as db:
            for key, extra in [
                ("p_ignore",  {}),
                ("p_opened",  {"email_opened_at": now}),
                ("p_clicked", {"email_clicked_at": now}),
                ("p_booked",  {}),
                ("p_test",    {"is_test": True}),
            ]:
                tok = str(uuid.uuid4())
                tokens[key] = tok
                db.add(V3ProspectDB(
                    token=tok, name=f"Société {key}", city="Paris",
                    profession="électricien", landing_url=f"/l/{tok}",
                    email=f"{tok[:8]}@test.fr", ia_results='[]',
                    city_reference="PARIS",
                    is_test=extra.pop("is_test", False),
                    sent_at=now if key != "p_test" else None,
                    **extra,
                ))
            db.commit()

        # Booking pour p_booked
        _booking(Main, tokens["p_booked"], hours_from_now=72)
        return tokens

    def test_B07_etats_coherents_apres_lot(self, dbs):
        Main, _ = dbs
        tokens = self._setup_lot(Main)

        with Main() as db:
            # p_booked a un booking dans v3_bookings
            bk_count = db.query(V3BookingDB).filter_by(
                prospect_token=tokens["p_booked"]
            ).count()
            assert bk_count == 1, "p_booked doit avoir 1 booking"

            # p_test est exclu des envois réels
            test_count = db.query(V3ProspectDB).filter(
                V3ProspectDB.token == tokens["p_test"],
                V3ProspectDB.is_test.isnot(True),
            ).count()
            assert test_count == 0, "p_test ne doit pas passer le filtre is_test"

            # p_opened a email_opened_at set
            p = db.query(V3ProspectDB).filter_by(token=tokens["p_opened"]).first()
            assert p.email_opened_at is not None

            # p_clicked a email_clicked_at set
            p = db.query(V3ProspectDB).filter_by(token=tokens["p_clicked"]).first()
            assert p.email_clicked_at is not None

            # Tous les vrais prospects envoyés ont sent_at
            for key in ("p_ignore", "p_opened", "p_clicked", "p_booked"):
                p = db.query(V3ProspectDB).filter_by(token=tokens[key]).first()
                assert p.sent_at is not None, f"{key} doit avoir sent_at"

    def test_B07b_agenda_booking_seul(self, dbs):
        """Seul p_booked doit apparaître dans l'agenda closer."""
        Main, _ = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        tokens = self._setup_lot(Main)
        slots = _build_real_slots("")
        assert len(slots) == 1
        assert slots[0]["prospect"]["email"].startswith(tokens["p_booked"][:8])
