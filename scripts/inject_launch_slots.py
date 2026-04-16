"""
inject_launch_slots.py — Génère les créneaux de lancement (20/4+)

Logique :
  - Lundi 20/4  : active_closers × 3 slots (lancement doux)
  - Mardi 21/4  : active_closers × 4 slots (montée en charge)
  - Mer→Ven 22-24/4 : active_closers × 2 slots/jour
  - Semaine 2 (27/4+) : active_closers × 2 slots/jour
  - Créneaux : 9h, 10h, 11h, 14h, 15h, 16h (20 min, lun–ven uniquement)

Dynamique : lit active_closers depuis closers WHERE is_active=1 (hors [TEST]).
Si 0 closers réels, utilise les closers [TEST] comme fallback.

Usage :
  python scripts/inject_launch_slots.py
  python scripts/inject_launch_slots.py --dry-run
  python scripts/inject_launch_slots.py --clean   # supprime les slots de lancement existants
"""

import argparse
import os
import sys
import uuid
from datetime import date, datetime, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "libs"))
sys.path.insert(0, os.path.join(_ROOT, "src"))

_env_file = os.path.join(_ROOT, ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from marketing_module.database import SessionLocal
from marketing_module.models import CloserDB, SlotDB, SlotStatus

PROJECT_ID   = "presence-ia"
LAUNCH_DATE  = date(2026, 4, 20)
LAUNCH_TAG   = "[LAUNCH]"

# Heures disponibles (on pioche dedans selon la capacité du jour)
_HOURS = [9, 10, 11, 14, 15, 16]

# Slots par closer selon le jour (lun=0 … ven=4)
_SLOTS_PER_CLOSER = {
    0: 3,  # lundi   20/4
    1: 4,  # mardi   21/4
    2: 2,  # mercredi
    3: 2,  # jeudi
    4: 2,  # vendredi
}


def _uid():
    return str(uuid.uuid4())


def _slots_for_date(d: date, n: int):
    """Retourne n créneaux de 20 min pour la journée d (heures de _HOURS)."""
    hours = _HOURS[:n]
    result = []
    for h in hours:
        start = datetime(d.year, d.month, d.day, h, 0)
        end   = start + timedelta(minutes=20)
        result.append((start, end))
    return result


def inject_launch_slots(dry_run: bool = False, clean: bool = False):
    db = SessionLocal()
    try:
        # ── Récupérer les closers ─────────────────────────────────────────────
        closers = db.query(CloserDB).filter(
            CloserDB.project_id == PROJECT_ID,
            CloserDB.is_active  == True,
        ).all()
        real_closers = [c for c in closers if "[TEST]" not in (c.name or "")]
        label = f"{len(real_closers)} réels + {len(closers) - len(real_closers)} test"

        n_closers = len(closers)
        print(f"\n{'═'*60}")
        print(f"  INJECT LAUNCH SLOTS")
        print(f"  Mode : {'DRY RUN' if dry_run else 'RÉEL'}")
        print(f"  Closers actifs ({label}) : {n_closers}")
        print(f"  Lancement : {LAUNCH_DATE}")
        print(f"{'═'*60}")

        if n_closers == 0:
            print("  ❌ Aucun closer disponible — abandon.")
            return

        # ── Nettoyage slots LAUNCH existants ─────────────────────────────────
        if clean or not dry_run:
            deleted = db.query(SlotDB).filter(
                SlotDB.project_id == PROJECT_ID,
                SlotDB.notes.like(f"%{LAUNCH_TAG}%"),
                SlotDB.status == SlotStatus.available,
            ).delete(synchronize_session=False)
            if deleted:
                print(f"\n  Nettoyage : {deleted} slots LAUNCH supprimés")
            db.flush()

        # ── Génération des créneaux (20/4 → 4 semaines) ──────────────────────
        total_slots = 0
        d = LAUNCH_DATE
        end_date = LAUNCH_DATE + timedelta(weeks=4)

        print(f"\n  Créneaux générés :")
        while d < end_date:
            if d.weekday() >= 5:   # sam/dim → skip
                d += timedelta(days=1)
                continue

            n_per_closer = _SLOTS_PER_CLOSER.get(d.weekday(), 2)
            total_day    = n_closers * n_per_closer
            times        = _slots_for_date(d, n_per_closer)

            print(f"    {d.strftime('%a %d/%m')} : {n_closers} closers × {n_per_closer} = {total_day} slots")

            if not dry_run:
                for closer in closers:
                    for (start, end) in times:
                        s = SlotDB(
                            id         = _uid(),
                            project_id = PROJECT_ID,
                            starts_at  = start,
                            ends_at    = end,
                            closer_id  = closer.id,
                            status     = SlotStatus.available,
                            notes      = f"{LAUNCH_TAG} {d.isoformat()}",
                        )
                        db.add(s)
            total_slots += total_day
            d += timedelta(days=1)

        if not dry_run:
            db.commit()

        print(f"\n  Total : {total_slots} slots sur 4 semaines")
        print(f"  {'[DRY RUN — aucune écriture]' if dry_run else '✓ Injectés en base'}")
        print(f"{'═'*60}\n")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clean",   action="store_true", help="Supprimer les slots LAUNCH existants")
    args = parser.parse_args()
    inject_launch_slots(dry_run=args.dry_run, clean=args.clean)
