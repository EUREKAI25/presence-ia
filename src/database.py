"""SQLite — init + session + CRUD helpers"""
import json, os
from pathlib import Path
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, CampaignDB, ProspectDB, TestRunDB, ProspectStatus, JobDB, JobStatus

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH      = os.getenv("DB_PATH", str(DATA_DIR / "presence_ia.db"))
ENGINE       = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


def init_db():
    Base.metadata.create_all(bind=ENGINE)


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

def new_session() -> Session:
    """Session indépendante pour les tâches en arrière-plan."""
    return SessionLocal()
