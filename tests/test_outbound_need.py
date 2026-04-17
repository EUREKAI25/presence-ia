"""
Tests — compute_outbound_need() : pilotage outbound par RDV réels.

Scénarios :
  T01  Agenda vide       → statut=running, caps maximaux
  T02  Agenda à 20%      → statut=running (seuil exact)
  T03  Agenda à 30%      → statut=top_up
  T04  Agenda à 70%      → statut=idle
  T05  Agenda saturé 90% → statut=saturated, caps=0
  T06  Bootstrap (<30 envois totaux) + saturé → override running
  T07  LAUNCH_MODE=true  → volumes × 1.5 (plafonné par max)
  T08  urgence_lundi : lundi < 50% cible → cap_sms > 0 même en idle
  T09  urgence_lundi OFF : lundi plein → cap_sms=0 en idle
  T10  is_test=True      → bookings exclus du comptage
  T11  TARGET_RDV_WEEK=5 → seuils déplacés
  T12  OUTBOUND_MAX_EMAIL=7 → plafond respecté en running
"""
import sys, os, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "libs"))

import pytest
from datetime import datetime, timedelta, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models import Base, V3ProspectDB, V3BookingDB
from marketing_module.models import Base as MktBase, SlotDB, CloserDB, SlotStatus

from src.scheduler import compute_outbound_need


# ── Helpers DB ────────────────────────────────────────────────────────────────

def _make_main_engine():
    e = create_engine("sqlite:///:memory:",
                      connect_args={"check_same_thread": False},
                      poolclass=StaticPool)
    Base.metadata.create_all(e)
    return sessionmaker(bind=e, autocommit=False, autoflush=False)


def _make_mkt_engine():
    e = create_engine("sqlite:///:memory:",
                      connect_args={"check_same_thread": False},
                      poolclass=StaticPool)
    MktBase.metadata.create_all(e)
    return sessionmaker(bind=e, autocommit=False, autoflush=False)


def _future(days: int) -> str:
    return (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")


def _next_monday_iso() -> str:
    today = date.today()
    skip  = (7 - today.weekday()) % 7 or 7
    d     = today + timedelta(days=skip)
    return d.strftime("%Y-%m-%dT09:00:00")


def _make_prospect(Session, is_test=False, sent=False) -> str:
    token = str(uuid.uuid4())
    with Session() as db:
        db.add(V3ProspectDB(
            token=token, name="Société Test", city="Nantes",
            profession="couvreur", landing_url="/l/" + token,
            email=f"{token[:8]}@test.fr", ia_results='[]',
            is_test=is_test,
            sent_at=datetime.utcnow() if sent else None,
            city_reference="NANTES",
        ))
        db.commit()
    return token


def _make_booking(Session, prospect_token: str, start_iso: str) -> None:
    with Session() as db:
        db.add(V3BookingDB(
            prospect_token=prospect_token,
            name="Client", email="c@test.fr",
            start_iso=start_iso,
            end_iso=start_iso[:13] + ":20:00",
        ))
        db.commit()


def _make_closer(MktSession) -> None:
    with MktSession() as mdb:
        mdb.add(CloserDB(
            project_id="presence-ia", name="Closer Test", is_active=True,
        ))
        mdb.commit()


def _make_slots(MktSession, count: int) -> None:
    with MktSession() as mdb:
        for i in range(count):
            dt = datetime.utcnow() + timedelta(days=3, hours=i)
            mdb.add(SlotDB(
                project_id="presence-ia", status=SlotStatus.available,
                starts_at=dt, ends_at=dt + timedelta(minutes=20),
            ))
        mdb.commit()


# ── Fixture principale ────────────────────────────────────────────────────────

@pytest.fixture
def dbs(monkeypatch):
    Main = _make_main_engine()
    Mkt  = _make_mkt_engine()
    monkeypatch.setattr("src.database.SessionLocal", Main)
    monkeypatch.setattr("marketing_module.database.SessionLocal", Mkt)
    # Env vars par défaut (sûrs, cohérents)
    for k, v in [
        ("TARGET_RDV_MONDAY",   "3"),
        ("TARGET_RDV_WEEK",     "10"),
        ("OUTBOUND_BASE_EMAIL", "5"),
        ("OUTBOUND_BASE_SMS",   "3"),
        ("OUTBOUND_MAX_EMAIL",  "20"),
        ("OUTBOUND_MAX_SMS",    "10"),
        ("LAUNCH_MODE",         "false"),
    ]:
        monkeypatch.setenv(k, v)
    return Main, Mkt


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestStatutTiers:
    """Vérification des seuils fill_need → statut."""

    def test_T01_agenda_vide_running(self, dbs):
        """0 RDV pris, target=10 → fill_need=1.0 → running, caps maximaux."""
        Main, Mkt = dbs
        _make_prospect(Main)  # lead en file, pas envoyé
        # Simuler 50 envois passés pour sortir du bootstrap
        for _ in range(50):
            _make_prospect(Main, sent=True)
        result = compute_outbound_need()
        assert result["statut"] == "running"
        assert result["fill_need"] == 1.0
        assert result["rdv_taken_week"] == 0
        assert result["cap_email"] == 20   # OUTBOUND_MAX_EMAIL
        assert result["cap_sms"]   >  0

    def test_T02_seuil_running_exact(self, dbs, monkeypatch):
        """2 RDV sur target=10 → fill_need=0.80 → toujours running (seuil inclus)."""
        Main, Mkt = dbs
        for _ in range(50): _make_prospect(Main, sent=True)
        for _ in range(2):
            tok = _make_prospect(Main)
            _make_booking(Main, tok, _future(5))
        result = compute_outbound_need()
        assert result["statut"] == "running"
        assert abs(result["fill_need"] - 0.80) < 0.01

    def test_T03_top_up(self, dbs):
        """3 RDV sur target=10 → fill_need=0.70 → top_up."""
        Main, Mkt = dbs
        for _ in range(50): _make_prospect(Main, sent=True)
        for _ in range(3):
            tok = _make_prospect(Main)
            _make_booking(Main, tok, _future(5))
        result = compute_outbound_need()
        assert result["statut"] == "top_up"
        assert result["cap_email"] == 10   # base_email * 2
        assert result["rdv_taken_week"] == 3

    def test_T04_idle(self, dbs):
        """7 RDV sur target=10 → fill_need=0.30 → idle."""
        Main, Mkt = dbs
        for _ in range(50): _make_prospect(Main, sent=True)
        for _ in range(7):
            tok = _make_prospect(Main)
            _make_booking(Main, tok, _future(5))
        result = compute_outbound_need()
        assert result["statut"] == "idle"
        assert result["cap_email"] == 5    # base_email
        assert result["rdv_taken_week"] == 7

    def test_T05_saturated(self, dbs):
        """9 RDV sur target=10 → fill_need=0.10 → saturated, caps=0."""
        Main, Mkt = dbs
        for _ in range(50): _make_prospect(Main, sent=True)
        for _ in range(9):
            tok = _make_prospect(Main)
            _make_booking(Main, tok, _future(5))
        result = compute_outbound_need()
        assert result["statut"] == "saturated"
        assert result["cap_email"] == 0
        assert result["cap_sms"]   == 0
        assert result["cap_recommande"] == 0


class TestBootstrap:
    def test_T06_bootstrap_override_saturated(self, dbs):
        """< 30 envois totaux + agenda saturé → override running, au moins base_email."""
        Main, Mkt = dbs
        # 5 envois seulement (bootstrap) + 9 RDV pris (→ saturated normalement)
        for _ in range(5): _make_prospect(Main, sent=True)
        for _ in range(9):
            tok = _make_prospect(Main)
            _make_booking(Main, tok, _future(5))
        result = compute_outbound_need()
        assert result["bootstrap"] is True
        assert result["statut"] == "running"
        assert result["cap_email"] >= 5   # au moins base_email


class TestLaunchMode:
    def test_T07_launch_mode_multiplie_volumes(self, dbs, monkeypatch):
        """LAUNCH_MODE=true → volumes × 1.5, plafonné par max_email/max_sms."""
        Main, Mkt = dbs
        monkeypatch.setenv("LAUNCH_MODE", "true")
        for _ in range(50): _make_prospect(Main, sent=True)
        # top_up scenario : 3 RDV
        for _ in range(3):
            tok = _make_prospect(Main)
            _make_booking(Main, tok, _future(5))
        result = compute_outbound_need()
        assert result["launch_mode"] is True
        assert result["statut"] == "top_up"
        # top_up normal : cap_email = base_email*2 = 10
        # launch_mode   : cap_email = min(int(10*1.5), 20) = 15
        assert result["cap_email"] == 15


class TestUrgenceLundi:
    def test_T08_urgence_lundi_active(self, dbs):
        """Lundi à 0 RDV (< 50% cible=3) → urgence_lundi=True → cap_sms > 0 en idle."""
        Main, Mkt = dbs
        for _ in range(50): _make_prospect(Main, sent=True)
        # 7 RDV → idle, mais lundi vide
        for _ in range(7):
            tok = _make_prospect(Main)
            _make_booking(Main, tok, _future(5))  # pas sur le lundi prochain
        result = compute_outbound_need()
        assert result["statut"] == "idle"
        assert result["urgence_lundi"] is True
        assert result["cap_sms"] == 3   # base_sms

    def test_T09_urgence_lundi_inactive(self, dbs):
        """Lundi plein (3/3 cible) → urgence_lundi=False → cap_sms=0 en idle."""
        Main, Mkt = dbs
        for _ in range(50): _make_prospect(Main, sent=True)
        # 7 RDV total → idle
        for _ in range(7):
            tok = _make_prospect(Main)
            _make_booking(Main, tok, _future(5))
        # + 3 RDV lundi prochain (atteint la cible)
        for _ in range(3):
            tok = _make_prospect(Main)
            _make_booking(Main, tok, _next_monday_iso())
        result = compute_outbound_need()
        assert result["urgence_lundi"] is False
        assert result["cap_sms"] == 0


class TestIsTestExclusion:
    def test_T10_bookings_is_test_exclus(self, dbs):
        """Bookings de prospects is_test=True ne comptent PAS dans rdv_taken_week."""
        Main, Mkt = dbs
        for _ in range(50): _make_prospect(Main, sent=True)
        # 3 vrais RDV
        for _ in range(3):
            tok = _make_prospect(Main, is_test=False)
            _make_booking(Main, tok, _future(5))
        # 5 RDV de test — ne doivent pas compter
        for _ in range(5):
            tok = _make_prospect(Main, is_test=True)
            _make_booking(Main, tok, _future(5))
        result = compute_outbound_need()
        assert result["rdv_taken_week"] == 3, (
            f"rdv_taken_week={result['rdv_taken_week']} — les bookings is_test ne doivent pas compter"
        )


class TestConfig:
    def test_T11_target_rdv_week_custom(self, dbs, monkeypatch):
        """TARGET_RDV_WEEK=5 : 3 RDV sur 5 → fill_need=0.40 → top_up (seuil exact)."""
        Main, Mkt = dbs
        monkeypatch.setenv("TARGET_RDV_WEEK", "5")
        for _ in range(50): _make_prospect(Main, sent=True)
        for _ in range(3):
            tok = _make_prospect(Main)
            _make_booking(Main, tok, _future(5))
        result = compute_outbound_need()
        assert result["rdv_taken_week"] == 3
        assert abs(result["fill_need"] - 0.40) < 0.01
        assert result["statut"] == "top_up"

    def test_T12_max_email_plafonne(self, dbs, monkeypatch):
        """OUTBOUND_MAX_EMAIL=7 → cap_email ≤ 7 même en running."""
        Main, Mkt = dbs
        monkeypatch.setenv("OUTBOUND_MAX_EMAIL", "7")
        for _ in range(50): _make_prospect(Main, sent=True)
        result = compute_outbound_need()
        assert result["statut"] == "running"
        assert result["cap_email"] == 7


class TestSlots:
    def test_slots_open_lu_depuis_slotdb(self, dbs):
        """slots_open reflète les créneaux disponibles dans SlotDB."""
        Main, Mkt = dbs
        _make_slots(Mkt, 12)
        result = compute_outbound_need()
        assert result["slots_open"] == 12

    def test_deux_closers(self, dbs):
        """active_closers=2 quand 2 closers actifs dans SlotDB."""
        Main, Mkt = dbs
        for _ in range(2): _make_closer(Mkt)
        result = compute_outbound_need()
        assert result["active_closers"] == 2
