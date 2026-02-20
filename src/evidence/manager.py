"""
Evidence Manager — gestion des preuves par (profession, city).
Couche logique indépendante de la route HTTP.

Fonctions exposées :
  register_evidence(db, profession, city, model, ts, file_url, meta) -> evidence_id
  list_evidence(db, profession, city, limit) -> list
  pick_latest_evidence(db, profession, city, k) -> list
  refresh_index(db, evidence_root) -> dict
"""
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..database import db_get_or_create_evidence, db_get_evidence, jl, jd
from ..models import CityEvidenceDB

log = logging.getLogger(__name__)

VALID_MODELS = {"openai", "anthropic", "gemini"}


def register_evidence(
    db: Session,
    profession: str,
    city: str,
    model: str,
    ts: Optional[str],
    file_url: str,
    meta: Optional[dict] = None,
) -> str:
    """
    Enregistre une preuve (URL vers screenshot ou fichier) pour (profession, city).
    Ne fait pas d'upload — s'attend à une URL déjà accessible.

    Args:
        db:         Session SQLAlchemy
        profession: Profession (ex: "couvreur")
        city:       Ville (ex: "rennes")
        model:      Modèle IA source ("openai" | "anthropic" | "gemini" | autre)
        ts:         Timestamp ISO (défaut: maintenant)
        file_url:   URL de la preuve (fichier déjà uploadé ou distant)
        meta:       Métadonnées supplémentaires (dict optionnel)

    Returns:
        evidence_id (str) — identifiant unique de la preuve enregistrée
    """
    profession = profession.strip().lower()
    city = city.strip().lower()
    ts = ts or datetime.utcnow().isoformat()
    evidence_id = str(uuid.uuid4())

    entry = {
        "evidence_id": evidence_id,
        "ts": ts,
        "provider": model,
        "url": file_url,
        "processed_url": None,
        "filename": Path(file_url).name if file_url else "",
        "processed_fn": None,
        **(meta or {}),
    }

    ev = db_get_or_create_evidence(db, profession, city)
    images = jl(ev.images)
    images.insert(0, entry)
    ev.images = jd(images)
    db.commit()

    log.info("Evidence enregistrée : %s/%s — %s", profession, city, evidence_id)
    return evidence_id


def list_evidence(
    db: Session,
    profession: str,
    city: str,
    limit: int = 20,
) -> list:
    """
    Retourne la liste des preuves pour (profession, city), triées par date décroissante.

    Args:
        db: Session SQLAlchemy
        profession: Profession
        city: Ville
        limit: Nombre max d'entrées (défaut 20)

    Returns:
        Liste de dicts [{evidence_id, ts, provider, url, ...}]
    """
    ev = db_get_evidence(db, profession, city)
    if not ev:
        return []
    images = jl(ev.images)
    images.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return images[:limit]


def pick_latest_evidence(
    db: Session,
    profession: str,
    city: str,
    k: int = 3,
) -> list:
    """
    Retourne les k preuves les plus récentes pour (profession, city).
    Priorise les entrées avec processed_url (WEBP 16:9 traité).

    Args:
        db: Session SQLAlchemy
        profession: Profession
        city: Ville
        k: Nombre d'éléments à retourner (défaut 3)

    Returns:
        Liste des k preuves les plus récentes
    """
    all_items = list_evidence(db, profession, city, limit=k * 3)
    # Prioriser les processed
    with_processed = [i for i in all_items if i.get("processed_url")]
    without = [i for i in all_items if not i.get("processed_url")]
    combined = with_processed + without
    return combined[:k]


def refresh_index(db: Session, evidence_root: Optional[Path] = None) -> dict:
    """
    Scanne le répertoire evidence sur le disque et synchronise la DB.
    Utile après un déploiement ou un ajout de fichiers manuels.

    Parcourt : evidence_root/{profession}/{city}/*.{png,jpg,webp}
    Enregistre les fichiers non encore présents dans la DB.

    Args:
        db: Session SQLAlchemy
        evidence_root: Chemin racine (défaut: dist/evidence/ relatif au projet)

    Returns:
        {"scanned": int, "new": int, "skipped": int, "errors": int}
    """
    if evidence_root is None:
        # Chemin par défaut : dist/evidence/ à la racine du projet PRESENCE_IA
        evidence_root = (
            Path(__file__).parent.parent.parent / "dist" / "evidence"
        )

    base_url = os.getenv("BASE_URL", "http://localhost:8001")
    stats = {"scanned": 0, "new": 0, "skipped": 0, "errors": 0}

    if not evidence_root.exists():
        log.warning("evidence_root n'existe pas : %s", evidence_root)
        return stats

    # Structure : evidence_root/{profession}/{city}/{fichier}
    for profession_dir in evidence_root.iterdir():
        if not profession_dir.is_dir():
            continue
        profession = profession_dir.name.lower()

        for city_dir in profession_dir.iterdir():
            if not city_dir.is_dir():
                continue
            city = city_dir.name.lower()

            ev = db_get_or_create_evidence(db, profession, city)
            existing_filenames = {
                img.get("filename", "") for img in jl(ev.images)
            }

            new_entries = []
            for f in sorted(city_dir.iterdir()):
                stats["scanned"] += 1
                if f.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                    stats["skipped"] += 1
                    continue
                if f.name in existing_filenames:
                    stats["skipped"] += 1
                    continue

                # Détecter le provider depuis le nom de fichier (convention: ..._{provider}_...)
                provider = "unknown"
                for p in VALID_MODELS:
                    if p in f.name.lower():
                        provider = p
                        break

                url = f"{base_url}/dist/evidence/{profession}/{city}/{f.name}"
                entry = {
                    "evidence_id": str(uuid.uuid4()),
                    "ts": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(),
                    "provider": provider,
                    "url": url,
                    "processed_url": url if f.suffix.lower() == ".webp" else None,
                    "filename": f.name,
                    "processed_fn": f.name if f.suffix.lower() == ".webp" else None,
                    "source": "refresh_index",
                }
                new_entries.append(entry)
                stats["new"] += 1

            if new_entries:
                images = jl(ev.images)
                images = new_entries + images
                ev.images = jd(images)
                try:
                    db.commit()
                    log.info(
                        "refresh_index: %d nouvelle(s) preuve(s) pour %s/%s",
                        len(new_entries), profession, city,
                    )
                except Exception as e:
                    db.rollback()
                    log.error("refresh_index DB error: %s", e)
                    stats["errors"] += len(new_entries)
                    stats["new"] -= len(new_entries)

    return stats
