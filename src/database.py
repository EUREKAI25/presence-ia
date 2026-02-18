"""SQLite — init + session + CRUD helpers"""
import json, os
from pathlib import Path
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, CampaignDB, ProspectDB, TestRunDB, ProspectStatus, JobDB, JobStatus, CityEvidenceDB, ContactDB, PricingConfigDB

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH      = os.getenv("DB_PATH", str(DATA_DIR / "presence_ia.db"))
ENGINE       = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


_PRICING_DEFAULTS = [
    {
        "key": "FLASH", "title": "Audit Flash", "price_text": "97€ une fois", "price_eur": 97.0,
        "bullets": '["Test sur 3 IA × 5 requêtes","Score visibilité /10","Concurrents identifiés","Rapport PDF + vidéo 90s","Checklist 8 points"]',
        "stripe_price_id": None, "highlighted": False, "active": True, "sort_order": 1,
    },
    {
        "key": "KIT", "title": "Kit Visibilité IA", "price_text": "500€ + 90€/mois × 6", "price_eur": 500.0,
        "bullets": '["Audit complet inclus","Kit contenu optimisé IA","Suivi mensuel 6 mois","Re-tests trimestriels","Dashboard résultats","Support prioritaire"]',
        "stripe_price_id": None, "highlighted": True, "active": True, "sort_order": 2,
    },
    {
        "key": "DONE_FOR_YOU", "title": "Tout inclus", "price_text": "3 500€ forfait", "price_eur": 3500.0,
        "bullets": '["Audit + Kit inclus","Rédaction contenus","Citations locales","Optimisation fiches","Garantie résultats 6 mois"]',
        "stripe_price_id": None, "highlighted": False, "active": True, "sort_order": 3,
    },
]


def init_db():
    Base.metadata.create_all(bind=ENGINE)
    # Migration colonnes ajoutées après création initiale
    from sqlalchemy import text
    with ENGINE.connect() as conn:
        for col in [
            "email TEXT", "proof_image_url TEXT", "city_image_url TEXT",
            "paid INTEGER DEFAULT 0", "stripe_session_id TEXT",
        ]:
            try:
                conn.execute(text(f"ALTER TABLE prospects ADD COLUMN {col}"))
            except Exception:
                pass
        conn.commit()
    # Seed pricing defaults (only if table is empty)
    with SessionLocal() as db:
        if db.query(PricingConfigDB).count() == 0:
            for p in _PRICING_DEFAULTS:
                db.add(PricingConfigDB(**p))
            db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── JSON helpers ──
def jl(s: str) -> list:
    try: return json.loads(s or "[]")
    except: return []

def jd(o) -> str:
    return json.dumps(o, ensure_ascii=False)


# ── Campaign ──
def db_create_campaign(db: Session, obj: CampaignDB) -> CampaignDB:
    db.add(obj); db.commit(); db.refresh(obj); return obj

def db_get_campaign(db: Session, cid: str) -> Optional[CampaignDB]:
    return db.query(CampaignDB).filter_by(campaign_id=cid).first()

def db_list_campaigns(db: Session) -> List[CampaignDB]:
    return db.query(CampaignDB).order_by(CampaignDB.created_at.desc()).all()


# ── Prospect ──
def db_create_prospect(db: Session, obj: ProspectDB) -> ProspectDB:
    db.add(obj); db.commit(); db.refresh(obj); return obj

def db_get_prospect(db: Session, pid: str) -> Optional[ProspectDB]:
    return db.query(ProspectDB).filter_by(prospect_id=pid).first()

def db_get_by_token(db: Session, token: str) -> Optional[ProspectDB]:
    return db.query(ProspectDB).filter_by(landing_token=token).first()

def db_list_prospects(db: Session, cid: str, status: Optional[str] = None) -> List[ProspectDB]:
    q = db.query(ProspectDB).filter_by(campaign_id=cid)
    if status: q = q.filter_by(status=status)
    return q.order_by(ProspectDB.ia_visibility_score.desc().nullslast()).all()


# ── TestRun ──
def db_create_run(db: Session, obj: TestRunDB) -> TestRunDB:
    db.add(obj); db.commit(); db.refresh(obj); return obj

def db_list_runs(db: Session, pid: str) -> List[TestRunDB]:
    return db.query(TestRunDB).filter_by(prospect_id=pid).order_by(TestRunDB.ts).all()


# ── Jobs ──
def db_create_job(db: Session, obj: JobDB) -> JobDB:
    db.add(obj); db.commit(); db.refresh(obj); return obj

def db_get_job(db: Session, job_id: str) -> Optional[JobDB]:
    return db.query(JobDB).filter_by(job_id=job_id).first()

def db_update_job(db: Session, job: JobDB, **kwargs) -> JobDB:
    for k, v in kwargs.items():
        setattr(job, k, v)
    db.commit(); db.refresh(job); return job

# ── CityEvidence ──
def db_get_or_create_evidence(db: Session, profession: str, city: str) -> CityEvidenceDB:
    ev = db.query(CityEvidenceDB).filter_by(profession=profession, city=city).first()
    if not ev:
        ev = CityEvidenceDB(profession=profession, city=city)
        db.add(ev); db.commit(); db.refresh(ev)
    return ev

def db_get_evidence(db: Session, profession: str, city: str) -> Optional[CityEvidenceDB]:
    return db.query(CityEvidenceDB).filter_by(profession=profession, city=city).first()


def new_session() -> Session:
    """Session indépendante pour les tâches en arrière-plan."""
    return SessionLocal()


# ── Contacts ──
def db_list_contacts(db: Session) -> list:
    return db.query(ContactDB).order_by(ContactDB.date_added.desc()).all()

def db_get_contact(db: Session, cid: str) -> Optional[ContactDB]:
    return db.query(ContactDB).filter_by(id=cid).first()

def db_create_contact(db: Session, obj: ContactDB) -> ContactDB:
    db.add(obj); db.commit(); db.refresh(obj); return obj

def db_update_contact(db: Session, contact: ContactDB, **kwargs) -> ContactDB:
    for k, v in kwargs.items():
        setattr(contact, k, v)
    db.commit(); db.refresh(contact); return contact

def db_delete_contact(db: Session, contact: ContactDB):
    db.delete(contact); db.commit()


# ── Pricing ──
def db_list_pricing(db: Session) -> list:
    return db.query(PricingConfigDB).filter_by(active=True).order_by(PricingConfigDB.sort_order).all()

def db_get_pricing(db: Session, key: str) -> Optional[PricingConfigDB]:
    return db.query(PricingConfigDB).filter_by(key=key).first()

def db_update_pricing(db: Session, pricing: PricingConfigDB, **kwargs) -> PricingConfigDB:
    for k, v in kwargs.items():
        setattr(pricing, k, v)
    db.commit(); db.refresh(pricing); return pricing
