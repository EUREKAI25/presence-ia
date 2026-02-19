"""
Module SCAN — Création campagne + import prospects
POST /api/prospect-scan
"""
import csv, io, uuid
from typing import List

from sqlalchemy.orm import Session

from .database import db_create_campaign, db_create_prospect, db_get_campaign, jd
from .models import CampaignCreate, CampaignDB, ProspectDB, ProspectInput, ProspectScanInput, ProspectStatus


# ── Requêtes imposées par profession ──────────────────────────────────

_QUERIES: dict = {
    "couvreur": [
        "Quel est le meilleur couvreur à {city} ?",
        "J'ai une fuite de toiture à {city}, tu peux me recommander un couvreur ?",
        "Qui sont les couvreurs les mieux notés à {city} ?",
        "Quelles entreprises de couverture ou de toiture sont connues à {city} ?",
        "Donne-moi des noms de couvreurs ou d'entreprises de toiture à {city}",
    ],
    "plombier": [
        "Quel est le meilleur plombier à {city} ?",
        "J'ai une fuite d'eau à {city}, tu peux me recommander un plombier ?",
        "Qui sont les plombiers les mieux notés à {city} ?",
        "Quelles entreprises de plomberie sont connues à {city} ?",
        "Donne-moi des noms de plombiers ou d'entreprises de plomberie à {city}",
    ],
    "restaurant": [
        "Quel est le meilleur restaurant à {city} ?",
        "Tu me conseilles quel restaurant à {city} ?",
        "Quels sont les restaurants les mieux notés à {city} ?",
        "Quels restaurants sont incontournables à {city} ?",
        "Donne-moi des noms de restaurants à {city}",
    ],
    "default": [
        "Quel est le meilleur {profession} à {city} ?",
        "Tu peux me recommander un bon {profession} à {city} ?",
        "Qui sont les meilleurs {profession}s à {city} ?",
        "Quelles entreprises de {profession} sont connues à {city} ?",
        "Donne-moi des noms de {profession}s ou d'entreprises à {city}",
    ],
}


def get_queries(profession: str, city: str) -> List[str]:
    templates = _QUERIES.get(profession.lower().strip(), _QUERIES["default"])
    return [t.format(profession=profession, city=city) for t in templates]


# ── Campagne ──────────────────────────────────────────────────────────

def create_campaign(db: Session, data: CampaignCreate) -> CampaignDB:
    obj = CampaignDB(
        campaign_id=str(uuid.uuid4()),
        profession=data.profession,
        city=data.city,
        max_prospects=data.max_prospects,
        mode=data.mode.value,
    )
    return db_create_campaign(db, obj)


# ── Scan / import ─────────────────────────────────────────────────────

def scan_prospects(db: Session, data: ProspectScanInput) -> List[ProspectDB]:
    if data.campaign_id:
        campaign = db_get_campaign(db, data.campaign_id)
        if not campaign:
            raise ValueError(f"Campagne {data.campaign_id} introuvable")
    else:
        campaign = create_campaign(db, CampaignCreate(
            profession=data.profession,
            city=data.city,
            max_prospects=data.max_prospects,
        ))

    inputs: List[ProspectInput] = (data.manual_prospects or [])[:data.max_prospects]
    if not inputs:
        # Placeholder — forcer l'import d'une vraie liste
        inputs = [ProspectInput(name=f"[PLACEHOLDER] {i+1} — {data.profession} {data.city}")
                  for i in range(min(3, data.max_prospects))]

    created = []
    for inp in inputs:
        p = ProspectDB(
            prospect_id=str(uuid.uuid4()),
            campaign_id=campaign.campaign_id,
            name=inp.name,
            city=inp.city or data.city,
            profession=inp.profession or data.profession,
            website=inp.website,
            phone=inp.phone,
            reviews_count=inp.reviews_count,
            google_ads_active=inp.google_ads_active,
            status=ProspectStatus.SCHEDULED.value,
        )
        created.append(db_create_prospect(db, p))

    return created


def load_csv(content: str, city: str, profession: str) -> List[ProspectInput]:
    reader = csv.DictReader(io.StringIO(content))
    out = []
    for row in reader:
        name = row.get("name", "").strip()
        if not name:
            continue
        out.append(ProspectInput(
            name=name,
            city=row.get("city", city).strip() or city,
            profession=row.get("profession", profession).strip() or profession,
            website=row.get("website", "").strip() or None,
            phone=row.get("phone", "").strip() or None,
            reviews_count=int(row["reviews_count"]) if row.get("reviews_count", "").strip().isdigit() else None,
            google_ads_active=row.get("google_ads_active", "").strip().lower() in ("true", "1", "oui"),
        ))
    return out
