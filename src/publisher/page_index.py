"""
Index des pages publiées — stockage, enregistrement et interrogation.

Table : published_pages
Colonnes clés :
  id, prospect_token, page_type, profession, city,
  target_keywords (JSON), visibility, published_url,
  wp_page_id, title, slug, internal_links_json, published_at, updated_at

Fonctions exportées :
  ensure_table(engine)
  register_published_page(db, prospect, publish_result) → id
  list_generated_pages_for_prospect(db, prospect_id)    → list[dict]
  find_related_pages(db, profession, city, ...)         → list[dict]
  update_internal_links(db, page_id, links)
"""

import json
import logging
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

# ── Import Base ────────────────────────────────────────────────────────────────

try:
    from ..models import Base as _Base
except ImportError:
    from src.models import Base as _Base


# ── Modèle DB ─────────────────────────────────────────────────────────────────

class PublishedPageDB(_Base):
    """Page générée et publiée pour un prospect V3."""
    __tablename__ = "published_pages"

    id                  = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    prospect_token      = sa.Column(sa.String,  nullable=False, index=True)
    page_type           = sa.Column(sa.String,  default="service_local")   # service_local | faq | guide | audit_public | autre
    profession          = sa.Column(sa.String,  nullable=False, index=True)
    city                = sa.Column(sa.String,  nullable=False, index=True)
    target_keywords     = sa.Column(sa.Text,    default="[]")              # JSON list[str]
    visibility          = sa.Column(sa.String,  default="discreet")        # discreet | integrated
    published_url       = sa.Column(sa.String,  nullable=True)
    wp_page_id          = sa.Column(sa.Integer, nullable=True)
    title               = sa.Column(sa.String,  default="")
    slug                = sa.Column(sa.String,  default="")
    internal_links_json = sa.Column(sa.Text,    nullable=True)             # JSON list[{title,url,anchor,reason}]
    published_at        = sa.Column(sa.String,  default="")                # ISO date
    updated_at          = sa.Column(sa.String,  default="")


# ── Helpers ───────────────────────────────────────────────────────────────────

def ensure_table(engine) -> None:
    """Crée la table published_pages si elle n'existe pas encore."""
    PublishedPageDB.__table__.create(engine, checkfirst=True)
    log.debug("[page_index] table published_pages OK")


def _row_to_dict(r: PublishedPageDB) -> dict:
    return {
        "id":                  r.id,
        "prospect_token":      r.prospect_token,
        "page_type":           r.page_type,
        "profession":          r.profession,
        "city":                r.city,
        "target_keywords":     json.loads(r.target_keywords or "[]"),
        "visibility":          r.visibility,
        "published_url":       r.published_url,
        "wp_page_id":          r.wp_page_id,
        "title":               r.title,
        "slug":                r.slug,
        "internal_links":      json.loads(r.internal_links_json or "[]"),
        "published_at":        r.published_at,
        "updated_at":          r.updated_at,
    }


# ── CRUD ──────────────────────────────────────────────────────────────────────

def register_published_page(db: Session, prospect, publish_result: dict) -> int:
    """
    Enregistre une page publiée dans l'index.

    Args:
        db             : session SQLAlchemy
        prospect       : instance V3ProspectDB
        publish_result : dict retourné par publish_content()

    Returns:
        id de la ligne insérée (int)
    """
    profession = (getattr(prospect, "profession", "") or "").lower().strip()
    city       = (getattr(prospect, "city", "") or "").lower().strip()
    keywords   = json.dumps([profession, city, f"{profession} {city}"])

    # Évite les doublons : même token + même URL (ou même slug si pas d'URL)
    existing_url  = publish_result.get("url")
    existing_slug = publish_result.get("slug", "")
    if existing_url:
        dup = db.query(PublishedPageDB).filter(
            PublishedPageDB.prospect_token == prospect.token,
            PublishedPageDB.published_url  == existing_url,
        ).first()
    else:
        dup = db.query(PublishedPageDB).filter(
            PublishedPageDB.prospect_token == prospect.token,
            PublishedPageDB.slug           == existing_slug,
        ).first()

    today = date.today().isoformat()

    if dup:
        # Mise à jour
        dup.visibility     = publish_result.get("visibility", "discreet")
        dup.published_url  = publish_result.get("url") or dup.published_url
        dup.wp_page_id     = publish_result.get("page_id") or dup.wp_page_id
        dup.title          = publish_result.get("title", dup.title)
        dup.updated_at     = today
        db.commit()
        log.info("[page_index] page mise à jour (id=%s) pour %s", dup.id, prospect.token)
        return dup.id

    row = PublishedPageDB(
        prospect_token  = prospect.token,
        page_type       = publish_result.get("publish_target", "service_local"),
        profession      = profession,
        city            = city,
        target_keywords = keywords,
        visibility      = publish_result.get("visibility", "discreet"),
        published_url   = publish_result.get("url"),
        wp_page_id      = publish_result.get("page_id"),
        title           = publish_result.get("title", ""),
        slug            = existing_slug,
        published_at    = publish_result.get("publish_date", today),
        updated_at      = today,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log.info("[page_index] page enregistrée (id=%s) pour %s — %s", row.id, prospect.token, row.published_url or row.slug)
    return row.id


def list_generated_pages_for_prospect(db: Session, prospect_id: str) -> list[dict]:
    """Retourne toutes les pages publiées d'un prospect, ordre anti-chronologique."""
    rows = (
        db.query(PublishedPageDB)
        .filter(PublishedPageDB.prospect_token == prospect_id)
        .order_by(PublishedPageDB.published_at.desc())
        .all()
    )
    return [_row_to_dict(r) for r in rows]


def find_related_pages(
    db: Session,
    profession: str,
    city: str,
    exclude_prospect: str = "",
    exclude_url: str = "",
    limit: int = 5,
) -> list[dict]:
    """
    Trouve les pages publiées sémantiquement proches.

    Priorité de tri :
      1. Même profession + même ville  (+15)
      2. Même profession seule         (+10)
      3. Même ville seule              (+5)

    Exclut :
      - les pages sans URL publiée
      - le prospect source (exclude_prospect)
      - la page source elle-même (exclude_url)
      - les pages visibility non discreet/integrated
    """
    q = (
        db.query(PublishedPageDB)
        .filter(
            PublishedPageDB.published_url != None,    # noqa: E711
            PublishedPageDB.published_url != "",
            PublishedPageDB.visibility.in_(["discreet", "integrated"]),
        )
    )
    if exclude_prospect:
        q = q.filter(PublishedPageDB.prospect_token != exclude_prospect)
    if exclude_url:
        q = q.filter(PublishedPageDB.published_url != exclude_url)

    rows = q.all()

    prof_norm = profession.lower().strip()
    city_norm = city.lower().strip()

    def _score(r: PublishedPageDB) -> int:
        s = 0
        if r.profession == prof_norm:
            s += 10
        if r.city == city_norm:
            s += 5
        return s

    ranked = sorted(rows, key=_score, reverse=True)
    return [_row_to_dict(r) for r in ranked[:limit]]


def update_internal_links(db: Session, page_id: int, links: list[dict]) -> None:
    """Enregistre les suggestions de liens internes dans la DB pour une page."""
    row = db.query(PublishedPageDB).filter(PublishedPageDB.id == page_id).first()
    if row:
        row.internal_links_json = json.dumps(links, ensure_ascii=False)
        row.updated_at = date.today().isoformat()
        db.commit()
        log.debug("[page_index] internal_links mis à jour pour page %s (%d liens)", page_id, len(links))
