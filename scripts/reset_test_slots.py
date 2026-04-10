"""
reset_test_slots.py — Jeu de données test pour Chantier B (N = f(slots Calendly))

Injecte dans marketing.db :
  - 2 closers actifs (test_closer_1 / test_closer_2)
  - 10 slots proches  J+2→J+4  (20 min chacun)
  - 5  slots moyens   J+5→J+7
  - 2  slots lointains J+9→J+11
  - 3  meetings (30% des slots proches) → status booked sur les slots correspondants

Usage :
  python scripts/reset_test_slots.py
  python scripts/reset_test_slots.py --dry-run   # affiche sans insérer

IMPORTANT : nettoie d'abord les données de test précédentes (tag "[TEST]" dans le nom).
Ne touche PAS aux closers/slots/meetings réels.
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, timedelta

# ── chemin vers le module marketing ──────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "libs"))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from marketing_module.database import SessionLocal
from marketing_module.models import (
    CloserDB, SlotDB, MeetingDB,
    SlotStatus, MeetingStatus,
)

PROJECT_ID = "presence-ia"
TEST_TAG   = "[TEST]"   # marqueur pour identifier et nettoyer les données test


def _uid() -> str:
    return str(uuid.uuid4())


def reset_test_slots(dry_run: bool = False) -> dict:
    """
    Remet à zéro les données de test et injecte un nouveau jeu.
    Retourne un résumé {closers, slots_proches, slots_moyens, slots_lointains, meetings}.
    """
    now   = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    today = now.replace(hour=0)

    # ── Définition des slots ──────────────────────────────────────────────────
    # Créneaux à 9h, 10h, 11h, 14h, 15h — 20 min chacun

    def _slot_times(day_offset: int, hour: int):
        start = today + timedelta(days=day_offset, hours=hour)
        end   = start + timedelta(minutes=20)
        return start, end

    # Proches : J+2 → J+4 (10 slots)
    proches_raw = [
        _slot_times(2, 9),
        _slot_times(2, 10),
        _slot_times(2, 14),
        _slot_times(3, 9),
        _slot_times(3, 11),
        _slot_times(3, 14),
        _slot_times(3, 15),
        _slot_times(4, 9),
        _slot_times(4, 10),
        _slot_times(4, 15),
    ]

    # Moyens : J+5 → J+7 (5 slots)
    moyens_raw = [
        _slot_times(5, 9),
        _slot_times(5, 14),
        _slot_times(6, 10),
        _slot_times(7, 9),
        _slot_times(7, 14),
    ]

    # Lointains : J+9 → J+11 (2 slots)
    lointains_raw = [
        _slot_times(9, 10),
        _slot_times(11, 14),
    ]

    print("\n" + "═" * 60)
    print("  RESET TEST SLOTS — Chantier B")
    print(f"  Mode : {'DRY RUN (aucune écriture)' if dry_run else 'RÉEL (écriture en DB)'}")
    print("═" * 60)
    print(f"\n  Référence temporelle : {today.strftime('%Y-%m-%d')}")
    print(f"  Slots proches   : {len(proches_raw)}  (J+2 → J+4)")
    print(f"  Slots moyens    : {len(moyens_raw)}   (J+5 → J+7)")
    print(f"  Slots lointains : {len(lointains_raw)}   (J+9 → J+11)")
    print(f"  Meetings prévus : 3  (slots proches index 0, 2, 5)")

    if dry_run:
        print("\n  [DRY RUN] Aucune modification en base.")
        print("═" * 60 + "\n")
        return {"dry_run": True}

    db = SessionLocal()
    try:
        # ── 1. Nettoyage des données test précédentes ────────────────────────
        old_closers = db.query(CloserDB).filter(
            CloserDB.project_id == PROJECT_ID,
            CloserDB.name.like(f"%{TEST_TAG}%"),
        ).all()
        old_closer_ids = [c.id for c in old_closers]

        if old_closer_ids:
            deleted_slots = db.query(SlotDB).filter(
                SlotDB.project_id == PROJECT_ID,
                SlotDB.closer_id.in_(old_closer_ids),
            ).delete(synchronize_session=False)
            deleted_meetings = db.query(MeetingDB).filter(
                MeetingDB.project_id == PROJECT_ID,
                MeetingDB.closer_id.in_(old_closer_ids),
            ).delete(synchronize_session=False)
            for c in old_closers:
                db.delete(c)
            print(f"\n  Nettoyage : {len(old_closers)} closers, {deleted_slots} slots,"
                  f" {deleted_meetings} meetings supprimés")
        else:
            # Nettoyage par tag dans les notes aussi (slots sans closer test)
            deleted_slots = db.query(SlotDB).filter(
                SlotDB.project_id == PROJECT_ID,
                SlotDB.notes.like(f"%{TEST_TAG}%"),
            ).delete(synchronize_session=False)
            if deleted_slots:
                print(f"\n  Nettoyage : {deleted_slots} slots orphelins supprimés")

        db.flush()

        # ── 2. Création des 2 closers test ───────────────────────────────────
        closer1 = CloserDB(
            id         = _uid(),
            project_id = PROJECT_ID,
            name       = f"Thomas Dupont {TEST_TAG}",
            first_name = "Thomas",
            last_name  = "Dupont",
            email      = "thomas.dupont.test@presence-ia.com",
            is_active  = True,
            commission_rate = 0.18,
        )
        closer2 = CloserDB(
            id         = _uid(),
            project_id = PROJECT_ID,
            name       = f"Camille Martin {TEST_TAG}",
            first_name = "Camille",
            last_name  = "Martin",
            email      = "camille.martin.test@presence-ia.com",
            is_active  = True,
            commission_rate = 0.18,
        )
        db.add(closer1)
        db.add(closer2)
        db.flush()

        closers = [closer1, closer2]
        print(f"\n  Closers créés : {closer1.name} / {closer2.name}")

        # ── 3. Création des slots ─────────────────────────────────────────────
        # Index des slots proches qui recevront un meeting : 0, 2, 5
        booked_indices = {0, 2, 5}

        proche_slots = []
        for i, (start, end) in enumerate(proches_raw):
            closer = closers[i % 2]
            status = SlotStatus.booked if i in booked_indices else SlotStatus.available
            s = SlotDB(
                id         = _uid(),
                project_id = PROJECT_ID,
                starts_at  = start,
                ends_at    = end,
                closer_id  = closer.id,
                status     = status,
                notes      = f"{TEST_TAG} proche slot {i+1}",
            )
            db.add(s)
            proche_slots.append(s)

        moyen_slots = []
        for i, (start, end) in enumerate(moyens_raw):
            closer = closers[i % 2]
            s = SlotDB(
                id         = _uid(),
                project_id = PROJECT_ID,
                starts_at  = start,
                ends_at    = end,
                closer_id  = closer.id,
                status     = SlotStatus.available,
                notes      = f"{TEST_TAG} moyen slot {i+1}",
            )
            db.add(s)
            moyen_slots.append(s)

        lointain_slots = []
        for i, (start, end) in enumerate(lointains_raw):
            closer = closers[i % 2]
            s = SlotDB(
                id         = _uid(),
                project_id = PROJECT_ID,
                starts_at  = start,
                ends_at    = end,
                closer_id  = closer.id,
                status     = SlotStatus.available,
                notes      = f"{TEST_TAG} lointain slot {i+1}",
            )
            db.add(s)
            lointain_slots.append(s)

        db.flush()

        # ── 4. Création des 3 meetings (slots booked_indices) ────────────────
        meetings_created = []
        for idx in sorted(booked_indices):
            slot = proche_slots[idx]
            m = MeetingDB(
                id           = _uid(),
                project_id   = PROJECT_ID,
                prospect_id  = f"test-prospect-{idx+1:03d}",
                closer_id    = slot.closer_id,
                scheduled_at = slot.starts_at,
                status       = MeetingStatus.scheduled,
                notes        = f"{TEST_TAG} meeting pour slot proche {idx+1}",
            )
            db.add(m)
            db.flush()
            # Lier le slot au meeting
            slot.meeting_id = m.id
            meetings_created.append(m)

        db.commit()

        # ── 5. Résumé ────────────────────────────────────────────────────────
        total_proche   = len(proche_slots)
        booked_proche  = len(booked_indices)
        taux_couverture = booked_proche / total_proche * 100

        print(f"\n  ── Résumé injection ──")
        print(f"  Closers actifs   : 2")
        print(f"  Slots proches    : {total_proche}  ({booked_proche} booked / {total_proche - booked_proche} available)")
        print(f"  Slots moyens     : {len(moyen_slots)}")
        print(f"  Slots lointains  : {len(lointain_slots)}")
        print(f"  Meetings créés   : {len(meetings_created)}")
        print(f"  Taux couverture  : {taux_couverture:.0f}%")

        if taux_couverture < 70:
            statut = "RUN — générer des leads"
        elif taux_couverture >= 85:
            statut = "STOP — saturé"
        else:
            statut = "TOP_UP ou IDLE (selon file)"

        print(f"  Statut attendu   : {statut}")
        print(f"\n  ✓ Base injectée. Vérifier dans le dashboard admin → Pilotage slots.")
        print("═" * 60 + "\n")

        return {
            "closers":          2,
            "slots_proches":    total_proche,
            "slots_booked":     booked_proche,
            "slots_moyens":     len(moyen_slots),
            "slots_lointains":  len(lointain_slots),
            "meetings":         len(meetings_created),
            "taux_couverture":  round(taux_couverture, 1),
            "statut_attendu":   statut,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Injecte un jeu de données test dans marketing.db")
    parser.add_argument("--dry-run", action="store_true", help="Affiche sans modifier la base")
    args = parser.parse_args()

    reset_test_slots(dry_run=args.dry_run)
