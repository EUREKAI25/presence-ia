"""
city_images.py — Récupération et mise en cache des images header de villes de référence.
Utilise Unsplash Search (UNSPLASH_ACCESS_KEY en env) ou retourne None.
"""
from __future__ import annotations


def fetch_city_header_image(city_name: str) -> str | None:
    """
    Récupère et stocke une image header pour une ville de référence.
    Stratégie fallback en 3 essais :
      1. "{city} ville"          — photo de la ville elle-même
      2. "{city} France"         — résultats plus larges
      3. "France ville paysage"  — générique, toujours disponible
    Retourne None uniquement si Unsplash inaccessible ou clé absente.
    Une seule image par ville — mise en cache dans RefCityDB.header_image_url.
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
            f"{city_name} ville",
            f"{city_name} France",
            "France ville paysage",
        ]
        for query in queries:
            try:
                resp = _req.get(
                    "https://api.unsplash.com/search/photos",
                    params={"query": query, "orientation": "landscape",
                            "per_page": 1, "client_id": key},
                    timeout=10,
                )
                data = resp.json()
                url  = data["results"][0]["urls"]["regular"] if data.get("results") else None
                if url:
                    ref.header_image_url = url
                    db.commit()
                    return url
            except Exception:
                continue
        return None
