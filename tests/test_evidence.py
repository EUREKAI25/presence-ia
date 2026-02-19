"""Tests unitaires — evidence : parsing filename, listing, _process_image."""
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── Helpers à tester (pas de dépendance réseau) ──────────────────────────────

FILENAME_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<hhmm>\d{4})_(?P<provider>openai|anthropic|gemini)_(?P<rand>[a-z0-9]{6})\.(png|webp)$"
)


def parse_filename(filename: str) -> dict | None:
    """Extrait ts (datetime) et provider depuis un nom de fichier evidence."""
    m = FILENAME_PATTERN.match(filename)
    if not m:
        return None
    ts_str = f"{m.group('date')} {m.group('hhmm')[:2]}:{m.group('hhmm')[2:]}"
    return {
        "ts": datetime.strptime(ts_str, "%Y-%m-%d %H:%M"),
        "provider": m.group("provider"),
        "rand": m.group("rand"),
    }


def latest_evidence(images: list, limit: int = 6) -> list:
    """Retourne les N images triées par ts décroissant."""
    def _key(img):
        return img.get("ts", img.get("filename", ""))
    return sorted(images, key=_key, reverse=True)[:limit]


# ── Tests parsing filename ────────────────────────────────────────────────────

class TestParseFilename:
    def test_valid_openai_png(self):
        r = parse_filename("2026-02-18_1732_openai_6wf1pq.png")
        assert r is not None
        assert r["provider"] == "openai"
        assert r["ts"] == datetime(2026, 2, 18, 17, 32)
        assert r["rand"] == "6wf1pq"

    def test_valid_anthropic_webp(self):
        r = parse_filename("2026-01-01_0900_anthropic_abc123.webp")
        assert r is not None
        assert r["provider"] == "anthropic"
        assert r["ts"].hour == 9

    def test_valid_gemini(self):
        r = parse_filename("2025-12-31_2359_gemini_zzzzzz.png")
        assert r is not None
        assert r["provider"] == "gemini"

    def test_invalid_provider(self):
        assert parse_filename("2026-02-18_1732_gpt4_6wf1pq.png") is None

    def test_invalid_format(self):
        assert parse_filename("screenshot.png") is None
        assert parse_filename("") is None
        assert parse_filename("2026-02-18_173_openai_6wf1pq.png") is None

    def test_processed_webp(self):
        """Le fichier processed a le même pattern mais extension .webp."""
        r = parse_filename("2026-02-18_1732_openai_6wf1pq.webp")
        assert r is not None
        assert r["provider"] == "openai"


# ── Tests latest_evidence ─────────────────────────────────────────────────────

class TestLatestEvidence:
    def _imgs(self, ts_list):
        return [{"ts": ts, "provider": "openai", "filename": f"f_{i}.png", "url": f"http://x/{i}.png"}
                for i, ts in enumerate(ts_list)]

    def test_sorted_descending(self):
        imgs = self._imgs(["2026-01-01T10:00", "2026-01-03T08:00", "2026-01-02T12:00"])
        result = latest_evidence(imgs, limit=3)
        assert result[0]["ts"] == "2026-01-03T08:00"
        assert result[1]["ts"] == "2026-01-02T12:00"
        assert result[2]["ts"] == "2026-01-01T10:00"

    def test_limit_respected(self):
        imgs = self._imgs([f"2026-01-0{i}T10:00" for i in range(1, 9)])
        result = latest_evidence(imgs, limit=6)
        assert len(result) == 6

    def test_empty_list(self):
        assert latest_evidence([]) == []

    def test_single_item(self):
        imgs = self._imgs(["2026-01-01T10:00"])
        assert len(latest_evidence(imgs)) == 1

    def test_uses_processed_url_when_present(self):
        imgs = [{"ts": "2026-01-01T10:00", "provider": "openai",
                 "filename": "f.png", "url": "http://x/f.png",
                 "processed_url": "http://x/f.webp"}]
        result = latest_evidence(imgs)
        assert result[0].get("processed_url") == "http://x/f.webp"


# ── Tests _process_image ──────────────────────────────────────────────────────

class TestProcessImage:
    def test_process_creates_webp(self):
        """_process_image crée un fichier WEBP 16:9 à 1600px."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow non disponible")

        # Créer une image temporaire 800x600
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "test.png"
            dest = Path(tmpdir) / "test.webp"
            img = Image.new("RGB", (800, 600), color=(100, 150, 200))
            img.save(src, "PNG")

            # Importer la fonction de traitement
            import sys
            sys.path.insert(0, ".")
            from src.api.routes.evidence import _process_image

            result = _process_image(src, dest)
            assert result is True
            assert dest.exists()

            # Vérifier dimensions 16:9
            out = Image.open(dest)
            w, h = out.size
            assert w == 1600
            assert abs(h - int(w * 9 / 16)) <= 1  # tolérance 1px arrondi

    def test_process_missing_file(self):
        """_process_image retourne False si le fichier source n'existe pas."""
        import sys
        sys.path.insert(0, ".")
        from src.api.routes.evidence import _process_image

        with tempfile.TemporaryDirectory() as tmpdir:
            src  = Path(tmpdir) / "nonexistent.png"
            dest = Path(tmpdir) / "out.webp"
            result = _process_image(src, dest)
            assert result is False


# ── Tests DB CRUD headers ─────────────────────────────────────────────────────

class TestHeaderCRUD:
    def test_upsert_and_get(self):
        import sys
        sys.path.insert(0, ".")
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from src.models import Base, CityHeaderDB
        from src.database import db_upsert_header, db_get_header, db_delete_header

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        row = db_upsert_header(db, "rennes", "rennes.webp", "http://x/rennes.webp")
        assert row.city == "rennes"
        assert row.url == "http://x/rennes.webp"

        fetched = db_get_header(db, "rennes")
        assert fetched is not None
        assert fetched.filename == "rennes.webp"

        # Upsert (mise à jour)
        db_upsert_header(db, "rennes", "rennes_v2.webp", "http://x/rennes_v2.webp")
        updated = db_get_header(db, "rennes")
        assert updated.filename == "rennes_v2.webp"

        # Delete
        ok = db_delete_header(db, "rennes")
        assert ok is True
        assert db_get_header(db, "rennes") is None

        db.close()
