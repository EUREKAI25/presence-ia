"""
Tests — pipeline complet Présence IA : simulation comportements prospects.

Périmètre :
  P01  Sélection prospects : email valide avant email invalide, is_test exclu
  P02  Exclusion email bounced + email cité dans IA
  P03  Validité email : formats valides / invalides
  P04  Normalisation téléphone E.164

  S01  Prospect ignore : sent_at posé, aucun tracking
  S02  Prospect ouvre : email_opened_at set
  S03  Prospect clique : email_clicked_at set
  S04  Prospect réserve RDV → booking dans v3_bookings
  S05  Prospect réserve rapidement (J+1) → statut urgent (<48h)
  S06  Prospect réserve tard (J+5) → statut accessible

  R01  Booking créé avec données complètes et cohérentes
  R02  Double booking interdit : même token → deux bookings séparés (pas fusion)
  R03  Booking supprimé n'apparaît plus dans l'agenda

  A01  /closer/agenda : RDV visibles, max 4/jour
  A02  Statut urgent si < 48h
  A03  Statut accessible si > 48h
  A04  Prospect sans booking : invisible dans l'agenda

  O01  Outbound running (agenda vide) → caps maximaux
  O02  Outbound top_up (30%) → cap intermédiaire
  O03  Outbound idle (70%) → cap minimal
  O04  Outbound saturated (90%) → caps = 0, skip
  O05  Bootstrap (<30 envois) + saturé → override running

  F01  Pipeline complet : prospect → outbound → comportement → RDV → agenda
  F02  _job_outbound dry_run : sélectionne, log, ne marque pas sent_at
  F03  Bug fix cap : _job_outbound utilise cap_email/cap_sms (NameError absent)
"""
import sys, os, uuid, json, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "libs"))

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, MagicMock

from src.models import Base, V3ProspectDB, V3BookingDB
from marketing_module.models import Base as MktBase, CloserDB, SlotDB, SlotStatus


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


_IA_RESULTS = json.dumps([
    {"model": "ChatGPT", "prompt": "plombier Lyon",
     "response": "Dupont Plomberie est très bien noté à Lyon.", "tested_at": "2026-04-07T10:00:00"},
    {"model": "Gemini",  "prompt": "plombier urgence Lyon",
     "response": "Piron Plomberie et Leroux sont cités.", "tested_at": "2026-04-07T10:01:00"},
    {"model": "Claude",  "prompt": "meilleur plombier Lyon",
     "response": "Dupont Plomberie est souvent mentionné.", "tested_at": "2026-04-07T10:02:00"},
])

_IA_RESULTS_NOT_CITED = json.dumps([
    {"model": "ChatGPT", "prompt": "plombier Lyon",
     "response": "Piron Plomberie et Leroux sont les meilleurs.", "tested_at": "2026-04-07T10:00:00"},
])


def _prospect(Main, name="Dupont Plomberie", email=True, phone=False, is_test=False,
              ia_results=_IA_RESULTS, email_status=None, city_reference="LYON",
              sent_at=None) -> str:
    tok = str(uuid.uuid4())
    with Main() as db:
        db.add(V3ProspectDB(
            token=tok, name=name, city="Lyon", profession="plombier",
            landing_url=f"/l/{tok}",
            email=f"{tok[:8]}@test.fr" if email else None,
            phone="+33612345678" if phone else None,
            ia_results=ia_results, is_test=is_test,
            email_status=email_status,
            city_reference=city_reference,
            sent_at=sent_at,
        ))
        db.commit()
    return tok


def _booking(Main, tok: str, hours_from_now: float) -> str:
    dt  = datetime.utcnow() + timedelta(hours=hours_from_now)
    bid = str(uuid.uuid4())
    with Main() as db:
        db.add(V3BookingDB(
            id=bid, prospect_token=tok,
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
    for k, v in [
        ("TARGET_RDV_MONDAY",   "3"),
        ("TARGET_RDV_WEEK",     "10"),
        ("OUTBOUND_BASE_EMAIL", "5"),
        ("OUTBOUND_BASE_SMS",   "3"),
        ("OUTBOUND_MAX_EMAIL",  "20"),
        ("OUTBOUND_MAX_SMS",    "10"),
        ("LAUNCH_MODE",         "false"),
        ("OUTBOUND_DRY_RUN",    "true"),
    ]:
        monkeypatch.setenv(k, v)
    return Main, Mkt


# ── P : Sélection et filtrage prospects ───────────────────────────────────────

class TestSelection:

    def test_P01_is_test_exclu_de_la_selection(self, dbs):
        """Prospect is_test=True absent du filtre outbound de base."""
        Main, _ = dbs
        _prospect(Main, is_test=True)
        with Main() as db:
            count = db.query(V3ProspectDB).filter(
                V3ProspectDB.is_test.isnot(True),
                V3ProspectDB.sent_at.is_(None),
                V3ProspectDB.email.isnot(None),
            ).count()
        assert count == 0

    def test_P01b_reel_visible_dans_selection(self, dbs):
        """Prospect is_test=False inclus dans la sélection outbound."""
        Main, _ = dbs
        _prospect(Main, is_test=False)
        with Main() as db:
            count = db.query(V3ProspectDB).filter(
                V3ProspectDB.is_test.isnot(True),
                V3ProspectDB.sent_at.is_(None),
                V3ProspectDB.email.isnot(None),
            ).count()
        assert count == 1

    def test_P02_bounced_exclu(self, dbs):
        """email_status=bounced exclu de la sélection email."""
        Main, _ = dbs
        _prospect(Main, email_status="bounced")
        from sqlalchemy import or_
        with Main() as db:
            count = db.query(V3ProspectDB).filter(
                V3ProspectDB.email.isnot(None),
                V3ProspectDB.sent_at.is_(None),
                or_(
                    V3ProspectDB.email_status.is_(None),
                    V3ProspectDB.email_status.notin_(["bounced", "unsubscribed"]),
                ),
            ).count()
        assert count == 0, "bounced ne doit pas passer le filtre email"

    def test_P02b_unsubscribed_exclu(self, dbs):
        """email_status=unsubscribed exclu."""
        Main, _ = dbs
        _prospect(Main, email_status="unsubscribed")
        from sqlalchemy import or_
        with Main() as db:
            count = db.query(V3ProspectDB).filter(
                V3ProspectDB.email.isnot(None),
                or_(
                    V3ProspectDB.email_status.is_(None),
                    V3ProspectDB.email_status.notin_(["bounced", "unsubscribed"]),
                ),
            ).count()
        assert count == 0

    def test_P03_email_valide(self):
        """_outbound_is_valid_email : formats valides vs invalides."""
        from src.scheduler import _outbound_is_valid_email
        valides = [
            "dupont@free.fr", "contact@maison-martin.com",
            "jean.pierre.durand+pro@gmail.com",
        ]
        invalides = [
            "", "pas-un-email", "@nodomain", "double@@at.fr",
            "noreply@domain.fr", "test@domain.fr", "info@domain.jpg",
        ]
        for e in valides:
            assert _outbound_is_valid_email(e), f"Faux négatif : {e!r}"
        for e in invalides:
            assert not _outbound_is_valid_email(e), f"Faux positif : {e!r}"

    def test_P04_normalisation_telephone(self):
        """_outbound_normalize_phone : formats E.164."""
        from src.scheduler import _outbound_normalize_phone
        assert _outbound_normalize_phone("+33612345678")  == "+33612345678"
        assert _outbound_normalize_phone("0612345678")    == "+33612345678"
        assert _outbound_normalize_phone("06 12 34 56 78") == "+33612345678"
        assert _outbound_normalize_phone("pas-un-tel")    is None

    def test_P05_cited_exclu(self):
        """_outbound_is_cited : entreprise citée → True (skip)."""
        from src.scheduler import _outbound_is_cited
        ia_cite = json.dumps([
            {"model": "ChatGPT", "prompt": "plombier",
             "response": "Dupont Plomberie est très bien noté."}
        ])
        ia_non_cite = json.dumps([
            {"model": "ChatGPT", "prompt": "plombier",
             "response": "Leroux est très bien noté."}
        ])
        assert _outbound_is_cited("Dupont Plomberie", ia_cite) is True
        assert _outbound_is_cited("Dupont Plomberie", ia_non_cite) is False


# ── S : Comportements prospects simulés ───────────────────────────────────────

class TestComportements:

    def test_S01_ignore_aucun_tracking(self, dbs):
        """Prospect ignore : sent_at posé, pas de tracking email."""
        Main, _ = dbs
        tok = _prospect(Main, sent_at=datetime.utcnow())
        with Main() as db:
            p = db.query(V3ProspectDB).filter_by(token=tok).first()
        assert p.sent_at is not None
        assert p.email_opened_at is None
        assert p.email_clicked_at is None

    def test_S02_ouvre_email(self, dbs):
        """Prospect ouvre email : email_opened_at set."""
        Main, _ = dbs
        tok = _prospect(Main, sent_at=datetime.utcnow())
        now = datetime.utcnow()
        with Main() as db:
            p = db.query(V3ProspectDB).filter_by(token=tok).first()
            p.email_opened_at = now
            db.commit()
        with Main() as db:
            p2 = db.query(V3ProspectDB).filter_by(token=tok).first()
        assert p2.email_opened_at is not None
        assert p2.email_clicked_at is None

    def test_S03_clique_email(self, dbs):
        """Prospect clique : email_clicked_at set."""
        Main, _ = dbs
        tok = _prospect(Main, sent_at=datetime.utcnow())
        now = datetime.utcnow()
        with Main() as db:
            p = db.query(V3ProspectDB).filter_by(token=tok).first()
            p.email_opened_at  = now
            p.email_clicked_at = now
            db.commit()
        with Main() as db:
            p2 = db.query(V3ProspectDB).filter_by(token=tok).first()
        assert p2.email_clicked_at is not None

    def test_S04_reserve_rdv(self, dbs):
        """Prospect réserve : booking créé dans v3_bookings."""
        Main, _ = dbs
        tok = _prospect(Main)
        bid = _booking(Main, tok, hours_from_now=72)
        with Main() as db:
            b = db.query(V3BookingDB).filter_by(id=bid).first()
        assert b is not None
        assert b.prospect_token == tok

    def test_S05_reserve_rapidement_urgent(self, dbs):
        """Réservation J+1 (<48h) → statut urgent dans l'agenda."""
        Main, _ = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        tok = _prospect(Main)
        _booking(Main, tok, hours_from_now=24)
        slots = _build_real_slots("")
        assert slots[0]["status"] == "accessible_urgent"

    def test_S06_reserve_tard_accessible(self, dbs):
        """Réservation J+5 (>48h) → statut accessible."""
        Main, _ = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        tok = _prospect(Main)
        _booking(Main, tok, hours_from_now=120)
        slots = _build_real_slots("")
        assert slots[0]["status"] == "accessible"


# ── R : Cohérence des bookings ────────────────────────────────────────────────

class TestBookings:

    def test_R01_booking_données_complètes(self, dbs):
        """Booking contient tous les champs obligatoires non nuls."""
        Main, _ = dbs
        tok = _prospect(Main)
        bid = _booking(Main, tok, hours_from_now=48)
        with Main() as db:
            b = db.query(V3BookingDB).filter_by(id=bid).first()
        assert b.prospect_token
        assert b.start_iso
        assert b.end_iso
        assert b.name
        assert b.email
        # start < end
        assert b.start_iso < b.end_iso

    def test_R02_double_booking_deux_entrees(self, dbs):
        """Deux bookings sur le même token → deux lignes distinctes en DB."""
        Main, _ = dbs
        tok = _prospect(Main)
        bid1 = _booking(Main, tok, hours_from_now=72)
        bid2 = _booking(Main, tok, hours_from_now=120)
        assert bid1 != bid2
        with Main() as db:
            count = db.query(V3BookingDB).filter_by(prospect_token=tok).count()
        assert count == 2

    def test_R03_booking_supprimé_invisible_agenda(self, dbs):
        """Booking supprimé → absent de _build_real_slots."""
        Main, _ = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        tok = _prospect(Main)
        bid = _booking(Main, tok, hours_from_now=72)
        with Main() as db:
            db.query(V3BookingDB).filter_by(id=bid).delete()
            db.commit()
        slots = _build_real_slots("")
        assert len(slots) == 0


# ── A : Agenda closer ─────────────────────────────────────────────────────────

class TestAgenda:

    def test_A01_rdv_visible_agenda(self, dbs):
        """Booking → slot visible dans _build_real_slots."""
        Main, _ = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        tok = _prospect(Main)
        _booking(Main, tok, hours_from_now=72)
        slots = _build_real_slots("")
        assert len(slots) == 1
        assert slots[0]["prospect"]["email"] == f"{tok[:8]}@test.fr"

    def test_A02_agenda_vide_sans_booking(self, dbs):
        """Prospect sans booking → agenda vide."""
        Main, _ = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        _prospect(Main)
        slots = _build_real_slots("")
        assert slots == []

    def test_A03_lot_mixte_seul_booked_visible(self, dbs):
        """5 prospects (ignore/ouvre/clique/réserve/test) → 1 seul slot agenda."""
        Main, _ = dbs
        from src.api.routes.agenda_closer import _build_real_slots
        now = datetime.utcnow()
        toks = {}
        with Main() as db:
            for key, extra in [
                ("ignore",  {}),
                ("opened",  {"email_opened_at": now}),
                ("clicked", {"email_clicked_at": now}),
                ("booked",  {}),
                ("test",    {"is_test": True}),
            ]:
                tok = str(uuid.uuid4())
                toks[key] = tok
                db.add(V3ProspectDB(
                    token=tok, name=f"Société {key}", city="Lyon",
                    profession="plombier", landing_url=f"/l/{tok}",
                    email=f"{tok[:8]}@test.fr", ia_results="[]",
                    city_reference="LYON",
                    is_test=extra.pop("is_test", False),
                    sent_at=now if key != "test" else None,
                    **extra,
                ))
            db.commit()
        _booking(Main, toks["booked"], hours_from_now=72)
        slots = _build_real_slots("")
        assert len(slots) == 1
        assert slots[0]["prospect"]["email"].startswith(toks["booked"][:8])

    def test_A04_max_4_slots_par_jour(self, monkeypatch):
        """_filter_slots : jamais plus de 4 créneaux par jour."""
        from datetime import date
        from collections import Counter
        from src.api.routes.v3 import _filter_slots

        monkeypatch.setenv("MAX_VISIBLE_SLOTS_PER_DAY", "4")
        monkeypatch.setenv("DAYS_VISIBLE_AHEAD",        "14")
        monkeypatch.setenv("LAUNCH_MODE",               "false")

        slots = []
        for delta in range(2, 8):
            target = date.today() + timedelta(days=delta)
            for h in range(9, 19):
                start = datetime(target.year, target.month, target.day, h, 0)
                slots.append({
                    "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end":   (start + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                })

        result = _filter_slots(slots, date.today(), "seed-test")
        per_day = Counter(s["_dt"].date() for s in result)
        for d, n in per_day.items():
            assert n <= 4, f"Jour {d} : {n} créneaux > 4"


# ── O : Pilotage outbound ─────────────────────────────────────────────────────

class TestPilotageOutbound:

    def _fill(self, dbs, n_rdv: int, n_sent: int = 50):
        """Crée n_sent prospects envoyés + n_rdv bookings futurs."""
        Main, _ = dbs
        for _ in range(n_sent):
            _prospect(Main, sent_at=datetime.utcnow(), email=True)
        for _ in range(n_rdv):
            tok = _prospect(Main)
            _booking(Main, tok, hours_from_now=72)

    def test_O01_running_agenda_vide(self, dbs):
        """0 RDV → running, cap_email=20."""
        self._fill(dbs, n_rdv=0)
        from src.scheduler import compute_outbound_need
        r = compute_outbound_need()
        assert r["statut"] == "running"
        assert r["cap_email"] == 20
        assert r["fill_need"] == 1.0

    def test_O02_top_up_30pct(self, dbs):
        """3 RDV / 10 cible → fill=0.70 → top_up."""
        self._fill(dbs, n_rdv=3)
        from src.scheduler import compute_outbound_need
        r = compute_outbound_need()
        assert r["statut"] == "top_up"
        assert abs(r["fill_need"] - 0.70) < 0.02
        assert r["cap_email"] == 10   # base*2

    def test_O03_idle_70pct(self, dbs):
        """7 RDV / 10 → fill=0.30 → idle, cap_email=5 (base)."""
        self._fill(dbs, n_rdv=7)
        from src.scheduler import compute_outbound_need
        r = compute_outbound_need()
        assert r["statut"] == "idle"
        assert r["cap_email"] == 5

    def test_O04_saturated_skip(self, dbs):
        """9 RDV / 10 → saturated, caps=0."""
        self._fill(dbs, n_rdv=9)
        from src.scheduler import compute_outbound_need
        r = compute_outbound_need()
        assert r["statut"] == "saturated"
        assert r["cap_email"] == 0
        assert r["cap_sms"]   == 0

    def test_O05_bootstrap_override(self, dbs):
        """< 30 envois + saturé → bootstrap override → running."""
        Main, _ = dbs
        for _ in range(5):
            _prospect(Main, sent_at=datetime.utcnow())
        for _ in range(9):
            tok = _prospect(Main)
            _booking(Main, tok, hours_from_now=72)
        from src.scheduler import compute_outbound_need
        r = compute_outbound_need()
        assert r["bootstrap"] is True
        assert r["statut"] == "running"
        assert r["cap_email"] >= 5


# ── F : Flux complet ──────────────────────────────────────────────────────────

class TestFluxComplet:

    def test_F01_pipeline_prospect_to_agenda(self, dbs):
        """Flux complet : prospect créé → comportement → booking → visible agenda."""
        Main, _ = dbs
        from src.api.routes.agenda_closer import _build_real_slots

        # 1. Prospect envoyé
        tok = _prospect(Main, sent_at=datetime.utcnow())
        # 2. Ouvre l'email
        with Main() as db:
            p = db.query(V3ProspectDB).filter_by(token=tok).first()
            p.email_opened_at = datetime.utcnow()
            db.commit()
        # 3. Clique
        with Main() as db:
            p = db.query(V3ProspectDB).filter_by(token=tok).first()
            p.email_clicked_at = datetime.utcnow()
            db.commit()
        # 4. Réserve RDV
        bid = _booking(Main, tok, hours_from_now=72)
        # 5. Agenda contient ce RDV
        slots = _build_real_slots("")
        assert len(slots) == 1
        slot = slots[0]
        assert slot["prospect"]["email"] == f"{tok[:8]}@test.fr"
        assert slot["status"] == "accessible"
        # 6. Données cohérentes
        assert slot["date"]       # date non vide
        assert slot["time_start"] # heure de début

    def test_F02_job_outbound_dry_run_ne_marque_pas_sent_at(self, dbs, monkeypatch):
        """_job_outbound dry_run : prospects sélectionnés, aucun sent_at modifié."""
        Main, Mkt = dbs
        monkeypatch.setenv("OUTBOUND_DRY_RUN", "true")

        # Créer 5 prospects éligibles + 50 envoyés (hors bootstrap)
        for _ in range(50):
            _prospect(Main, name="Envoyé", sent_at=datetime.utcnow())
        toks = [_prospect(Main, name=f"Prospect {i}") for i in range(5)]

        # Mock les dépendances externes (imports locaux dans _job_outbound)
        fake_pair = {"city": "Lyon", "profession": "plombier", "score": 80.0}

        with patch("src.active_pair.check_saturation", return_value=fake_pair), \
             patch("src.city_images.fetch_city_header_image", return_value="https://img/x.jpg"), \
             patch("src.api.routes.v3._run_ia_test", return_value=None):
            from src.scheduler import _job_outbound
            _job_outbound(force=True)  # force=True bypasse compute_outbound_need

        # Aucun sent_at modifié
        with Main() as db:
            sent = db.query(V3ProspectDB).filter(
                V3ProspectDB.sent_at.isnot(None),
                V3ProspectDB.name.like("Prospect%"),
            ).count()
        assert sent == 0, "dry_run=True : aucun prospect ne doit avoir sent_at modifié"

    def test_F03_bug_cap_absent_corrige(self, dbs, monkeypatch):
        """_job_outbound ne lève pas NameError (fix bug 'cap' → 'cap_email'/'cap_sms')."""
        Main, _ = dbs
        monkeypatch.setenv("OUTBOUND_DRY_RUN", "true")
        for _ in range(50):
            _prospect(Main, name="Envoyé", sent_at=datetime.utcnow())
        _prospect(Main, name="Cible")

        fake_pair = {"city": "Lyon", "profession": "plombier", "score": 80.0}
        with patch("src.active_pair.check_saturation", return_value=fake_pair), \
             patch("src.city_images.fetch_city_header_image", return_value="https://img/x.jpg"), \
             patch("src.api.routes.v3._run_ia_test", return_value=None):
            from src.scheduler import _job_outbound
            try:
                _job_outbound(force=True)
            except NameError as e:
                pytest.fail(f"NameError détecté (bug cap non corrigé) : {e}")

    def test_F04_coherence_compte_rdv_is_test(self, dbs):
        """Bookings is_test exclus de rdv_taken_week — chiffre pilotage correct."""
        Main, _ = dbs
        for _ in range(50): _prospect(Main, sent_at=datetime.utcnow())
        # 3 vrais RDV
        for _ in range(3):
            tok = _prospect(Main, is_test=False)
            _booking(Main, tok, hours_from_now=72)
        # 5 RDV test (ne doivent pas compter)
        for _ in range(5):
            tok = _prospect(Main, is_test=True)
            _booking(Main, tok, hours_from_now=72)

        from src.scheduler import compute_outbound_need
        r = compute_outbound_need()
        assert r["rdv_taken_week"] == 3, (
            f"rdv_taken_week={r['rdv_taken_week']} — les bookings is_test ne doivent pas compter"
        )
