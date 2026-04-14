"""
city_images.py — Récupération et mise en cache des images header de villes de référence.
Utilise Unsplash Search (UNSPLASH_ACCESS_KEY en env) ou retourne None.
"""
from __future__ import annotations

# Mots dans la description/alt qui indiquent une photo de ville ou paysage urbain
_GOOD_TAGS = {"city", "ville", "town", "village", "street", "rue", "church", "cathedral",
              "église", "paysage", "landscape", "architecture", "building", "aerial",
              "skyline", "place", "square", "market", "medieval", "historic", "harbour",
              "port", "river", "rivière", "pont", "bridge", "sunset", "panorama"}

# Mots qui indiquent une photo hors-sujet (événement, sport, voiture, personne seule…)
_BAD_TAGS  = {"car", "voiture", "rally", "race", "sport", "concert", "person", "portrait",
              "selfie", "food", "restaurant", "wedding", "mariage", "baby", "animal",
              "dog", "cat", "flower", "fleur"}


def _score(img: dict) -> int:
    """Score positif = probable photo de ville/paysage."""
    text = " ".join(filter(None, [
        img.get("description") or "",
        img.get("alt_description") or "",
    ])).lower()
    tags = {t.get("title", "").lower() for t in img.get("tags", [])}
    combined = text + " " + " ".join(tags)
    score = sum(1 for w in _GOOD_TAGS if w in combined)
    score -= sum(2 for w in _BAD_TAGS  if w in combined)
    score += min(img.get("likes", 0) // 20, 3)  # bonus popularité (plafonné)
    return score


def fetch_city_header_image(city_name: str) -> str | None:
    """
    Récupère et stocke une image header pour une ville de référence.
    Stratégie :
      1. "{city} ville France"     — photo de la ville elle-même
      2. "{city} paysage"          — paysage local
      3. "{city} France"           — résultats plus larges
      4. "village France paysage"  — générique, toujours disponible
    Pour chaque query on récupère les 5 premiers résultats et on prend
    celui qui a le meilleur score (favorise ville/paysage, pénalise sport/voiture).
    """
    import os
    import requests as _req
    from .database import SessionLocal
    from .models import RefCityDB

    with SessionLocal() as db:
        ref = db.query(RefCityDB).filter_by(city_name=city_name.upper()).first()
        if not ref:
            return None
        if ref.header_image_url:
            return ref.header_image_url  # déjà en cache

        key = os.getenv("UNSPLASH_ACCESS_KEY", "")
        if not key:
            return None

        queries = [
            f"{city_name} ville France",
            f"{city_name} paysage",
            f"{city_name} France",
            "village France paysage ensoleillé",
        ]
        best_url   = None
        best_score = -99
        for query in queries:
            try:
                resp = _req.get(
                    "https://api.unsplash.com/search/photos",
                    params={"query": query, "orientation": "landscape",
                            "per_page": 5, "client_id": key},
                    timeout=10,
                )
                results = resp.json().get("results", [])
                for img in results:
                    s = _score(img)
                    if s > best_score:
                        best_score = s
                        best_url   = img["urls"]["regular"]
            except Exception:
                continue
            # Si on a un candidat avec un bon score, pas besoin d'aller plus loin
            if best_url and best_score >= 2:
                break

        if best_url:
            ref.header_image_url = best_url
            db.commit()
        return best_url
