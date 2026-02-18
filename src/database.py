"""SQLite — init + session + CRUD helpers"""
import json, os
from pathlib import Path
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, CampaignDB, ProspectDB, TestRunDB, ProspectStatus, JobDB, JobStatus, CityEvidenceDB, ContactDB, PricingConfigDB, ContentBlockDB

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
    # Seed content blocks
    with SessionLocal() as db:
        _seed_content_blocks(db)


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


# ── ContentBlocks ──
_CONTENT_SEED = [
    # HOME — HERO
    ("home", "hero", "title",        None, None, "Quand vos clients demandent à ChatGPT,\nil cite vos concurrents. Pas vous."),
    ("home", "hero", "subtitle",     None, None, "Nous testons votre visibilité sur 3 IA et 5 requêtes. Rapport en 48h. Plan d'action concret."),
    ("home", "hero", "cta_primary",  None, None, "Tester ma visibilité — 97€"),
    ("home", "hero", "cta_secondary",None, None, "Comment ça marche"),
    # HOME — PROOF STAT
    ("home", "proof_stat", "stat_1_value", None, None, "87%"),
    ("home", "proof_stat", "stat_1_label", None, None, "des artisans testés sont invisibles sur les IA"),
    ("home", "proof_stat", "stat_2_value", None, None, "3 IA"),
    ("home", "proof_stat", "stat_2_label", None, None, "testées simultanément\nChatGPT · Gemini · Claude"),
    ("home", "proof_stat", "stat_3_value", None, None, "48h"),
    ("home", "proof_stat", "stat_3_label", None, None, "délai de livraison\nrapport + plan d'action"),
    ("home", "proof_stat", "source_url_1",   None, None, ""),
    ("home", "proof_stat", "source_label_1", None, None, ""),
    ("home", "proof_stat", "source_url_2",   None, None, ""),
    ("home", "proof_stat", "source_label_2", None, None, ""),
    # HOME — PROOF VISUAL
    ("home", "proof_visual", "title",    None, None, "Comment fonctionne l'audit"),
    ("home", "proof_visual", "subtitle", None, None, "Un test automatisé, rigoureux, répété sur les 3 grandes IA du marché."),
    ("home", "proof_visual", "step_1",   None, None, "On simule vos clients — 5 requêtes différentes posées à ChatGPT, Gemini et Claude."),
    ("home", "proof_visual", "step_2",   None, None, "On analyse les réponses — Êtes-vous cité ? Qui est cité à votre place ?"),
    ("home", "proof_visual", "step_3",   None, None, "Score de visibilité /10 — Un score clair, des données concrètes."),
    ("home", "proof_visual", "step_4",   None, None, "Plan d'action — Checklist priorisée pour corriger votre visibilité."),
    # HOME — FAQ
    ("home", "faq", "q1", None, None, "Pourquoi les IA ne me citent-elles pas ?"),
    ("home", "faq", "a1", None, None, "Les IA s'appuient sur des données publiques : avis Google, contenu de votre site, mentions dans des articles. Si ces signaux sont absents ou faibles, vous êtes invisible."),
    ("home", "faq", "q2", None, None, "Ça fonctionne pour quel type d'entreprise ?"),
    ("home", "faq", "a2", None, None, "Artisans (couvreurs, plombiers, électriciens…), restaurants, cabinets médicaux, commerces locaux. Toute entreprise dont les clients cherchent localement."),
    ("home", "faq", "q3", None, None, "Combien de temps pour voir des résultats ?"),
    ("home", "faq", "a3", None, None, "L'audit est livré en 48h. Les améliorations de visibilité IA sont généralement visibles en 4 à 12 semaines selon les actions mises en place."),
    ("home", "faq", "q4", None, None, "Est-ce que vous envoyez les emails à ma place ?"),
    ("home", "faq", "a4", None, None, "Non. Nous produisons les contenus et le plan d'action. Vous gardez le contrôle total sur ce qui est envoyé et publié."),
    # HOME — CTA
    ("home", "cta", "title",    None, None, "Votre audit en 48h — 97€"),
    ("home", "cta", "subtitle", None, None, "Entrez votre email, on vous envoie le lien de commande et on démarre le test."),
    ("home", "cta", "btn_label",None, None, "Démarrer →"),
    # LANDING — HERO (génériques)
    ("landing", "hero", "title_tpl",    None, None, "À {city}, les IA recommandent vos concurrents. Pas vous."),
    ("landing", "hero", "subtitle_tpl", None, None, "{n_queries} requêtes testées sur {n_models} IA · {models}"),
    ("landing", "hero", "cta_label",    None, None, "Recevoir mon audit complet — {price}"),
    # LANDING — PROOF VISUAL
    ("landing", "proof_visual", "mention", None, None, "Tests effectués sur 3 jours consécutifs"),
    # LANDING — PROOF STAT
    ("landing", "proof_stat", "source_url_1",   None, None, ""),
    ("landing", "proof_stat", "source_label_1", None, None, ""),
    ("landing", "proof_stat", "source_url_2",   None, None, ""),
    ("landing", "proof_stat", "source_label_2", None, None, ""),
    # LANDING — FAQ
    ("landing", "faq", "q1", None, None, "Pourquoi les IA ne me citent-elles pas ?"),
    ("landing", "faq", "a1", None, None, "Les IA s'appuient sur des données publiques : avis Google, contenu de votre site, mentions dans des articles. Si ces signaux sont absents ou faibles, vous êtes invisible."),
    ("landing", "faq", "q2", None, None, "Est-ce que le rapport inclut un plan d'action ?"),
    ("landing", "faq", "a2", None, None, "Oui. Vous recevez un rapport complet avec les requêtes testées, les concurrents identifiés, et une checklist priorisée en 8 points."),
]


def _seed_content_blocks(db: Session):
    for page_type, section_key, field_key, profession, city, value in _CONTENT_SEED:
        exists = db.query(ContentBlockDB).filter_by(
            page_type=page_type, section_key=section_key,
            field_key=field_key, profession=profession, city=city
        ).first()
        if not exists:
            db.add(ContentBlockDB(
                page_type=page_type, section_key=section_key,
                field_key=field_key, profession=profession, city=city,
                value=value
            ))
    db.commit()


def get_block(db: Session, page_type: str, section_key: str, field_key: str,
              profession: Optional[str] = None, city: Optional[str] = None,
              default: str = "") -> str:
    """Retourne la valeur du bloc avec fallback générique."""
    candidates = []
    if profession and city:
        candidates.append((profession, city))
    if profession:
        candidates.append((profession, None))
    candidates.append((None, None))
    for p, c in candidates:
        row = db.query(ContentBlockDB).filter_by(
            page_type=page_type, section_key=section_key,
            field_key=field_key, profession=p, city=c
        ).first()
        if row and row.value:
            return row.value
    return default


def set_block(db: Session, page_type: str, section_key: str, field_key: str,
              value: str, profession: Optional[str] = None, city: Optional[str] = None) -> ContentBlockDB:
    """Crée ou met à jour un bloc de contenu."""
    row = db.query(ContentBlockDB).filter_by(
        page_type=page_type, section_key=section_key,
        field_key=field_key, profession=profession, city=city
    ).first()
    if row:
        row.value = value
    else:
        row = ContentBlockDB(page_type=page_type, section_key=section_key,
                             field_key=field_key, profession=profession, city=city, value=value)
        db.add(row)
    db.commit(); db.refresh(row); return row


def db_list_content_blocks(db: Session, page_type: Optional[str] = None,
                            section_key: Optional[str] = None) -> list:
    q = db.query(ContentBlockDB)
    if page_type:  q = q.filter_by(page_type=page_type)
    if section_key: q = q.filter_by(section_key=section_key)
    return q.order_by(ContentBlockDB.page_type, ContentBlockDB.section_key, ContentBlockDB.field_key).all()
