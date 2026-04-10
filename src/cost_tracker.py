"""
cost_tracker — Compteurs thread-safe pour les appels API Google Places et Gemini.

Usage :
    from .cost_tracker import tracker
    tracker.increment_google()   # dans google_places.py
    tracker.increment_gemini()   # dans gemini_places.py
    counts = tracker.get_and_reset()  # en fin de job
"""
import threading


class _ApiTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._google = 0
        self._gemini = 0

    def increment_google(self):
        with self._lock:
            self._google += 1

    def increment_gemini(self):
        with self._lock:
            self._gemini += 1

    def get_and_reset(self) -> dict:
        """Retourne les compteurs actuels et les remet à zéro."""
        with self._lock:
            counts = {"google": self._google, "gemini": self._gemini}
            self._google = 0
            self._gemini = 0
        return counts

    def snapshot(self) -> dict:
        """Lit les compteurs sans les réinitialiser."""
        with self._lock:
            return {"google": self._google, "gemini": self._gemini}


# Singleton partagé par tout le process
tracker = _ApiTracker()
