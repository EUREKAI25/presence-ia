"""
Font Matcher - Match fonts détectées avec Google Fonts.
"""
import requests
from typing import List, Optional
from difflib import get_close_matches
import os


class FontMatcher:
    """Matcher de fonts avec Google Fonts."""

    # Fallbacks par catégorie (si pas de match exact)
    FALLBACK_FONTS = {
        'sans-serif': 'Inter',
        'serif': 'Merriweather',
        'monospace': 'Fira Code',
        'display': 'Poppins',
        'handwriting': 'Dancing Script'
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le matcher.

        Args:
            api_key: Clé API Google Fonts (optionnel)
        """
        self.api_key = api_key or os.getenv('GOOGLE_FONTS_API_KEY')
        self._google_fonts_cache = None

    def get_google_fonts(self) -> List[str]:
        """Récupère la liste des fonts Google Fonts."""
        if self._google_fonts_cache:
            return self._google_fonts_cache

        if not self.api_key:
            # Fallback : liste hardcodée des fonts populaires
            self._google_fonts_cache = [
                'Inter', 'Roboto', 'Open Sans', 'Lato', 'Montserrat',
                'Poppins', 'Raleway', 'Nunito', 'Playfair Display',
                'Merriweather', 'Fira Code', 'Source Code Pro',
                'Work Sans', 'DM Sans', 'Plus Jakarta Sans'
            ]
            return self._google_fonts_cache

        try:
            response = requests.get(
                "https://www.googleapis.com/webfonts/v1/webfonts",
                params={"key": self.api_key, "sort": "popularity"},
                timeout=5
            )
            if response.status_code == 200:
                fonts = response.json()['items']
                self._google_fonts_cache = [f['family'] for f in fonts[:500]]  # Top 500
                return self._google_fonts_cache
        except:
            pass

        # Fallback en cas d'erreur
        return self.FALLBACK_FONTS.values()

    def match_font(self, detected_font: str) -> str:
        """
        Trouve l'équivalent Google Fonts.

        Args:
            detected_font: Font détectée (ex: "Helvetica Neue, Arial, sans-serif")

        Returns:
            Nom de la Google Font équivalente
        """
        # Nettoyer le nom
        clean_name = detected_font.split(',')[0].strip().strip('"').strip("'")

        # Cas spéciaux système
        system_fonts_map = {
            '-apple-system': 'Inter',
            'BlinkMacSystemFont': 'Inter',
            'Segoe UI': 'Inter',
            'Helvetica Neue': 'Inter',
            'Helvetica': 'Inter',
            'Arial': 'Roboto',
            'sans-serif': 'Inter',
            'Times New Roman': 'Merriweather',
            'Times': 'Merriweather',
            'Georgia': 'Merriweather',
            'serif': 'Merriweather',
            'Courier New': 'Fira Code',
            'Courier': 'Fira Code',
            'monospace': 'Fira Code'
        }

        if clean_name in system_fonts_map:
            return system_fonts_map[clean_name]

        # Matching exact
        google_fonts = self.get_google_fonts()
        if clean_name in google_fonts:
            return clean_name

        # Matching approximatif
        matches = get_close_matches(clean_name, google_fonts, n=1, cutoff=0.6)
        if matches:
            return matches[0]

        # Fallback par catégorie
        return self._fallback_by_category(clean_name)

    def _fallback_by_category(self, font_name: str) -> str:
        """Fallback intelligent selon la catégorie."""
        lower = font_name.lower()

        # Sans-serif
        if any(x in lower for x in ['helvetica', 'arial', 'sans', 'roboto']):
            return 'Inter'

        # Serif
        if any(x in lower for x in ['times', 'georgia', 'serif', 'garamond']):
            return 'Merriweather'

        # Monospace
        if any(x in lower for x in ['mono', 'courier', 'consolas', 'code']):
            return 'Fira Code'

        # Display/Titles
        if any(x in lower for x in ['display', 'title', 'heading']):
            return 'Poppins'

        # Default
        return 'Inter'

    def get_font_url(self, font_name: str, weights: List[int] = [400, 500, 700]) -> str:
        """
        Génère l'URL Google Fonts pour importer la font.

        Args:
            font_name: Nom de la font
            weights: Poids à inclure (ex: [400, 500, 700])

        Returns:
            URL Google Fonts
        """
        font_escaped = font_name.replace(' ', '+')
        weights_str = ';'.join(f'wght@{w}' for w in weights)
        return f"https://fonts.googleapis.com/css2?family={font_escaped}:{weights_str}&display=swap"
