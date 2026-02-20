"""
Règles d'harmonie pour analyser et reproduire le design.
"""
import re
from typing import List, Dict, Tuple, Optional
from collections import Counter
import colorsys


class HarmonyRules:
    """Règles pour détecter et appliquer l'harmonie visuelle."""

    @staticmethod
    def rgb_to_hsl(rgb_str: str) -> Tuple[float, float, float]:
        """
        Convertit rgb(r,g,b) ou rgba(r,g,b,a) en (h, s, l).

        Returns:
            (hue 0-360, saturation 0-1, lightness 0-1)
        """
        # Parser rgb/rgba
        match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', rgb_str)
        if not match:
            return (0, 0, 0)

        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))

        # Normaliser 0-1
        r, g, b = r / 255.0, g / 255.0, b / 255.0

        # Convertir en HSL
        h, l, s = colorsys.rgb_to_hls(r, g, b)

        return (h * 360, s, l)  # Hue en degrés

    @staticmethod
    def hsl_to_rgb(h: float, s: float, l: float) -> str:
        """Convertit HSL en rgb(r,g,b)."""
        r, g, b = colorsys.hls_to_rgb(h / 360.0, l, s)
        return f"rgb({int(r*255)}, {int(g*255)}, {int(b*255)})"

    @staticmethod
    def lighten(rgb_str: str, percent: float) -> str:
        """Éclaircit une couleur de X%."""
        h, s, l = HarmonyRules.rgb_to_hsl(rgb_str)
        l = min(1.0, l + (percent / 100))
        return HarmonyRules.hsl_to_rgb(h, s, l)

    @staticmethod
    def darken(rgb_str: str, percent: float) -> str:
        """Assombrit une couleur de X%."""
        h, s, l = HarmonyRules.rgb_to_hsl(rgb_str)
        l = max(0.0, l - (percent / 100))
        return HarmonyRules.hsl_to_rgb(h, s, l)

    @staticmethod
    def add_alpha(rgb_str: str, alpha: float) -> str:
        """Ajoute un canal alpha."""
        match = re.match(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', rgb_str)
        if match:
            r, g, b = match.groups()
            return f"rgba({r}, {g}, {b}, {alpha})"
        return rgb_str

    def detect_color_relationships(self, colors: List[str]) -> Dict:
        """
        Détecte les relations entre couleurs (même famille).

        Returns:
            {
                "primary": {"base": "rgb(...)", "light": "rgb(...)", "dark": "rgb(...)"},
                "secondary": {...},
                "neutral": {...}
            }
        """
        if not colors:
            return {}

        # Convertir en HSL
        hsl_colors = [(c, self.rgb_to_hsl(c)) for c in colors]

        # Filtrer couleurs très sombres/claires (probablement neutrals)
        neutrals = [c for c, (h, s, l) in hsl_colors if s < 0.1 or l > 0.95 or l < 0.05]
        chromatic = [(c, hsl) for c, hsl in hsl_colors if c not in neutrals]

        if not chromatic:
            return {"neutral": {"base": colors[0] if colors else "rgb(128,128,128)"}}

        # Grouper par teinte similaire (tolérance ±30°)
        families = []
        used = set()

        for i, (color1, (h1, s1, l1)) in enumerate(chromatic):
            if color1 in used:
                continue

            family = [color1]
            used.add(color1)

            for j, (color2, (h2, s2, l2)) in enumerate(chromatic[i+1:]):
                if color2 in used:
                    continue

                # Même famille si hue proche
                if abs(h1 - h2) < 30 or abs(h1 - h2) > 330:  # Circular
                    family.append(color2)
                    used.add(color2)

            if family:
                families.append(family)

        # Trier families par nombre (la plus utilisée = primary)
        families.sort(key=len, reverse=True)

        result = {}

        # Primary (famille la plus répandue)
        if families:
            primary_family = families[0]
            result['primary'] = self._analyze_family(primary_family)

        # Secondary (2e famille)
        if len(families) > 1:
            secondary_family = families[1]
            result['secondary'] = self._analyze_family(secondary_family)

        # Neutrals
        if neutrals:
            result['neutral'] = self._analyze_family(neutrals)

        return result

    def _analyze_family(self, colors: List[str]) -> Dict:
        """Analyse une famille de couleurs et extrait base/light/dark."""
        if not colors:
            return {"base": "rgb(128,128,128)"}

        # Trier par luminosité
        hsl_list = [(c, self.rgb_to_hsl(c)) for c in colors]
        sorted_colors = sorted(hsl_list, key=lambda x: x[1][2])  # Tri par lightness

        # Médiane = base
        mid_idx = len(sorted_colors) // 2
        base = sorted_colors[mid_idx][0]

        # Plus clair = light
        light = sorted_colors[-1][0] if len(sorted_colors) > 1 else self.lighten(base, 15)

        # Plus foncé = dark
        dark = sorted_colors[0][0] if len(sorted_colors) > 2 else self.darken(base, 15)

        return {
            "base": base,
            "light": light,
            "dark": dark,
            "variants": colors
        }

    def detect_component_pattern(self, components: List[Dict], key: str = 'backgroundColor') -> Dict:
        """
        Détecte le pattern commun dans une liste de composants.

        Args:
            components: Liste de styles de composants
            key: Propriété à analyser

        Returns:
            Pattern le plus fréquent
        """
        if not components:
            return {}

        # Compter fréquences
        counter = Counter(c.get(key) for c in components if c.get(key))

        if not counter:
            return {}

        # Valeur la plus fréquente
        most_common = counter.most_common(1)[0][0]

        # Trouver un composant représentatif avec cette valeur
        representative = next(c for c in components if c.get(key) == most_common)

        return representative

    def detect_shadow_system(self, shadows: List[str]) -> Dict[str, str]:
        """
        Détecte le système de shadows (sm, md, lg, xl).

        Groupe les shadows par "intensité" (offset + blur).
        """
        if not shadows:
            return {
                "sm": "0 1px 2px rgba(0,0,0,0.05)",
                "md": "0 4px 6px rgba(0,0,0,0.1)",
                "lg": "0 10px 15px rgba(0,0,0,0.1)",
                "xl": "0 20px 25px rgba(0,0,0,0.1)"
            }

        # Parser les shadows et calculer "intensité"
        parsed = []
        for shadow in shadows:
            if shadow == 'none':
                continue
            # Simplification : extraire les valeurs numériques
            nums = re.findall(r'\d+', shadow)
            if len(nums) >= 2:
                offset = int(nums[0])
                blur = int(nums[1]) if len(nums) > 1 else 0
                intensity = offset + blur
                parsed.append((intensity, shadow))

        if not parsed:
            return {}

        # Trier par intensité
        parsed.sort(key=lambda x: x[0])

        # Diviser en 4 groupes (sm, md, lg, xl)
        n = len(parsed)
        result = {}

        if n >= 1:
            result['sm'] = parsed[0][1]
        if n >= 2:
            result['md'] = parsed[n//3][1]
        if n >= 3:
            result['lg'] = parsed[2*n//3][1]
        if n >= 4:
            result['xl'] = parsed[-1][1]

        return result

    def most_common_value(self, values: List[str]) -> str:
        """Retourne la valeur la plus fréquente."""
        if not values:
            return ""
        counter = Counter(values)
        return counter.most_common(1)[0][0]
