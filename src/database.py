"""SQLite — init + session + CRUD helpers"""
import json, os
from pathlib import Path
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, CampaignDB, ProspectDB, TestRunDB, ProspectStatus, JobDB, JobStatus, CityEvidenceDB, CityHeaderDB, ContactDB, ContentBlockDB, CmsBlockDB, ThemeConfigDB, MessageTemplateDB

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH      = os.getenv("DB_PATH", str(DATA_DIR / "presence_ia.db"))
ENGINE       = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)



def init_db():
    Base.metadata.create_all(bind=ENGINE)
    # Migration colonnes ajoutées après création initiale
    from sqlalchemy import text
    with ENGINE.connect() as conn:
        for tbl, col in [
            ("prospects", "email TEXT"),
            ("prospects", "mobile TEXT"),
            ("prospects", "cms TEXT"),
            ("prospects", "proof_image_url TEXT"),
            ("prospects", "city_image_url TEXT"),
            ("prospects", "paid INTEGER DEFAULT 0"),
            ("prospects", "stripe_session_id TEXT"),
            ("v3_landing_texts", "email_subject TEXT"),
            ("v3_landing_texts", "budget_min TEXT"),
            ("v3_landing_texts", "budget_max TEXT"),
            ("v3_landing_texts", "updated_at DATETIME"),
            ("v3_landing_texts", "email_template TEXT"),
            ("v3_landing_texts", "sms_template TEXT"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col}"))
            except Exception:
                pass
        conn.commit()
    # Seed content blocks + theme
    with SessionLocal() as db:
        _seed_content_blocks(db)
        _seed_theme(db)
    # Seed CMS blocks (lazy import to avoid circular)
    try:
        from .api.routes.cms import seed_cms_blocks
        with SessionLocal() as db:
            seed_cms_blocks(db)
    except Exception:
        pass
    # Seed message templates
    with SessionLocal() as db:
        _seed_message_templates(db)


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


# ── City Headers ──────────────────────────────────────────────────────────────

def db_get_header(db: Session, city: str) -> Optional[CityHeaderDB]:
    return db.query(CityHeaderDB).filter_by(city=city.lower()).first()


def db_upsert_header(db: Session, city: str, filename: str, url: str) -> CityHeaderDB:
    row = db.query(CityHeaderDB).filter_by(city=city.lower()).first()
    if row:
        row.filename = filename
        row.url = url
    else:
        row = CityHeaderDB(city=city.lower(), filename=filename, url=url)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def db_delete_header(db: Session, city: str) -> bool:
    row = db.query(CityHeaderDB).filter_by(city=city.lower()).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def db_list_headers(db: Session) -> list:
    return db.query(CityHeaderDB).order_by(CityHeaderDB.city).all()


# ── Page Layouts ─────────────────────────────────────────────────────────────

def db_get_page_layout(db: Session, page_type: str):
    """Récupère la config des sections pour une page (home/landing)."""
    from .models import PageLayoutDB
    return db.query(PageLayoutDB).filter_by(page_type=page_type).first()


def db_upsert_page_layout(db: Session, page_type: str, sections_config: str):
    """Crée ou met à jour la config des sections."""
    from .models import PageLayoutDB
    layout = db.query(PageLayoutDB).filter_by(page_type=page_type).first()
    if layout:
        layout.sections_config = sections_config
    else:
        layout = PageLayoutDB(page_type=page_type, sections_config=sections_config)
        db.add(layout)
    db.commit()
    db.refresh(layout)
    return layout


# ── Theme Config ──────────────────────────────────────────────────────────────

# ThemePreset de base — palette myhealthprac (warm/naturelle) + style rounded
_DEFAULT_THEME_PRESET = {
    "name": "PRESENCE_IA — Warm Professional",
    "source_url": "https://www.myhealthprac.com/",
    "mood": "warm",
    "use_cases": ["landing"],
    "color_system": {
        "primary":   {"base": "rgb(176, 144, 111)", "light": "rgb(204, 188, 172)", "dark": "rgb(124, 72, 34)"},
        "secondary": {"base": "rgb(152, 108, 67)",  "light": "rgb(204, 188, 172)", "dark": "rgb(80, 36, 16)"},
    },
    "font_family_headings": "Inter",
    "font_family_body": "Inter",
    "font_google_url": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
    "font_weights": {"normal": 400, "medium": 500, "bold": 700},
    # Palette myhealthprac + style preset "rounded" choisi indépendamment
    "style_preset_name": "rounded",
    # Ombres teintées warm (override du preset rounded)
    "style_overrides": {
        "shadow": {
            "sm": "0 1px 3px rgba(124, 72, 34, 0.08)",
            "md": "0 4px 12px rgba(124, 72, 34, 0.12)",
            "lg": "0 10px 24px rgba(124, 72, 34, 0.16)",
            "xl": "0 20px 40px rgba(124, 72, 34, 0.20)",
        }
    },
    "bg_prominence": "strong",
    "animation_style": "subtle",
    "harmony_description": "Palette naturelle et chaleureuse (tons or, terre, bois) — palette myhealthprac + style rounded professionnel.",
    "key_characteristics": [
        "Palette warm/naturelle (or, terre, bois)",
        "Style rounded — arrondi professionnel",
        "Ombres chaudes teintées warm",
        "Animations subtiles",
    ],
}


def db_get_theme(db: Session) -> dict:
    """Retourne le ThemePreset actuel depuis la DB. Fallback sur le preset par défaut."""
    row = db.query(ThemeConfigDB).filter_by(id="default").first()
    if row and row.preset_json and row.preset_json != "{}":
        try:
            return json.loads(row.preset_json)
        except Exception:
            pass
    return _DEFAULT_THEME_PRESET.copy()


def db_upsert_theme(db: Session, preset_dict: dict) -> ThemeConfigDB:
    """Sauvegarde le ThemePreset en DB."""
    row = db.query(ThemeConfigDB).filter_by(id="default").first()
    payload = json.dumps(preset_dict, ensure_ascii=False)
    if row:
        row.preset_json = payload
    else:
        row = ThemeConfigDB(id="default", preset_json=payload)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _seed_theme(db: Session):
    """Insère le ThemePreset par défaut si la table est vide."""
    exists = db.query(ThemeConfigDB).filter_by(id="default").first()
    if not exists:
        db.add(ThemeConfigDB(
            id="default",
            preset_json=json.dumps(_DEFAULT_THEME_PRESET, ensure_ascii=False),
        ))
        db.commit()


# ── Message Templates ────────────────────────────────────────────────────────

_DEFAULT_TEMPLATES = [
    # ── Email J+0 — Premier contact ───────────────────────────────────────────
    {
        "slug": "email_prospection",
        "name": "Email 01 — Premier contact (J+0)",
        "channel": "email",
        "subject": "Les IA recommandent vos concurrents a {city}",
        "body": (
            "Bonjour,\n\n"
            "Nous avons verifie ce que voient vos prospects lorsqu'ils demandent a leur IA :\n\n"
            "\"Quel {profession} recommandez-vous a {city} ?\"\n\n"
            "Certaines entreprises sont recommandees.\n\n"
            "Vous pouvez voir ce que l'IA affiche ici :\n"
            "{landing_url}\n\n"
            "Bonne journee,\n"
            "Presence IA"
        ),
        "body_html": None,
        "placeholders": json.dumps(["{name}", "{city}", "{profession}", "{landing_url}"]),
    },
    # ── SMS J+1 — Apres premier email ─────────────────────────────────────────
    {
        "slug": "sms_prospection",
        "name": "SMS 01 — Apres premier email (J+1)",
        "channel": "sms",
        "subject": None,
        "body": (
            "Bonjour,\n\n"
            "Nous avons analyse ce que les IA affichent lorsqu'un prospect cherche "
            "un {profession} a {city}.\n\n"
            "Voici la page personnalisee :\n"
            "{landing_url}\n\n"
            "- Presence IA"
        ),
        "body_html": None,
        "placeholders": json.dumps(["{name}", "{city}", "{profession}", "{landing_url}"]),
    },
    # ── Email J+3 — Relance preuve ────────────────────────────────────────────
    {
        "slug": "email_sequence_j3",
        "name": "Email 02 — Relance preuve (J+3)",
        "channel": "email",
        "subject": "Voici ce que voient vos prospects sur les IA",
        "body": (
            "Bonjour,\n\n"
            "Quand quelqu'un cherche un {profession} a {city} sur ChatGPT ou Gemini,\n"
            "certaines entreprises sont proposees en priorite.\n\n"
            "Votre entreprise n'apparait pas actuellement dans ces reponses.\n\n"
            "Voici la page personnalisee :\n"
            "{landing_url}\n\n"
            "Nous pouvons vous expliquer cela en 20 minutes si vous le souhaitez."
        ),
        "body_html": None,
        "placeholders": json.dumps(["{name}", "{city}", "{profession}", "{landing_url}"]),
    },
    # ── SMS J+5 — Rappel ──────────────────────────────────────────────────────
    {
        "slug": "sms_sequence",
        "name": "SMS 02 — Rappel (J+5)",
        "channel": "sms",
        "subject": None,
        "body": (
            "Bonjour,\n\n"
            "Petit rappel : la page montrant les resultats des IA pour {city} "
            "est toujours disponible.\n\n"
            "{landing_url}\n\n"
            "- Presence IA"
        ),
        "body_html": None,
        "placeholders": json.dumps(["{name}", "{city}", "{landing_url}"]),
    },
    # ── Email J+7 — Analyse disponible ───────────────────────────────────────
    {
        "slug": "email_sequence_j7",
        "name": "Email 03 — Analyse disponible (J+7)",
        "channel": "email",
        "subject": "Votre analyse est toujours disponible",
        "body": (
            "Bonjour,\n\n"
            "Nous avions prepare une page montrant ce que les IA affichent\n"
            "lorsqu'un prospect cherche un {profession} a {city}.\n\n"
            "La page est toujours accessible ici :\n"
            "{landing_url}\n\n"
            "Si vous voulez comprendre pourquoi certaines entreprises sont citees\n"
            "et comment y apparaitre, vous pouvez reserver un creneau."
        ),
        "body_html": None,
        "placeholders": json.dumps(["{name}", "{city}", "{profession}", "{landing_url}"]),
    },
    # ── Email J+14 — Dernier contact ──────────────────────────────────────────
    {
        "slug": "email_sequence_j14",
        "name": "Email 04 — Dernier contact (J+14)",
        "channel": "email",
        "subject": "Dernier message concernant votre visibilite IA",
        "body": (
            "Bonjour,\n\n"
            "Les recommandations faites par les IA deviennent\n"
            "un nouveau canal d'acquisition pour les entreprises locales.\n\n"
            "Nous avons analyse ce qui apparait actuellement pour {city}.\n\n"
            "Voici la page :\n"
            "{landing_url}\n\n"
            "Si le sujet vous interesse, vous pouvez reserver un audit gratuit\n"
            "pour voir comment ameliorer votre visibilite."
        ),
        "body_html": None,
        "placeholders": json.dumps(["{name}", "{city}", "{profession}", "{landing_url}"]),
    },
]


def _seed_message_templates(db: Session):
    """Insere ou met a jour les templates par defaut."""
    for t in _DEFAULT_TEMPLATES:
        existing = db.query(MessageTemplateDB).filter_by(slug=t["slug"]).first()
        if existing:
            existing.name = t["name"]
            existing.subject = t.get("subject")
            existing.body = t["body"]
            existing.placeholders = t["placeholders"]
        else:
            db.add(MessageTemplateDB(**t))
    db.commit()


def db_list_templates(db: Session) -> list:
    return db.query(MessageTemplateDB).order_by(MessageTemplateDB.channel, MessageTemplateDB.slug).all()


def db_get_template(db: Session, slug: str):
    return db.query(MessageTemplateDB).filter_by(slug=slug).first()


def db_update_template(db: Session, slug: str, updates: dict):
    t = db.query(MessageTemplateDB).filter_by(slug=slug).first()
    if not t:
        return None
    for k, v in updates.items():
        if hasattr(t, k):
            setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t
