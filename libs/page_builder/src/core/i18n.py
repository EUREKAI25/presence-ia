"""
i18n — résolution des clés de traduction.

Clés format "@namespace.key" → texte localisé
Textes directs → retournés tels quels
Placeholders {city}, {price}, etc. → résolus via context dict
"""
import json
import re
from pathlib import Path
from typing import Optional

_I18N_CACHE: dict = {}
_I18N_DIR = Path(__file__).parent.parent.parent / "i18n"


def _load_lang(lang: str) -> dict:
    """Charge le fichier i18n/{lang}.json (lazy, mis en cache)."""
    if lang not in _I18N_CACHE:
        path = _I18N_DIR / f"{lang}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                _I18N_CACHE[lang] = json.load(f)
        else:
            _I18N_CACHE[lang] = {}
    return _I18N_CACHE[lang]


def i18n_resolve(value: str, lang: str = "fr") -> str:
    """
    Résout une clé i18n.
    "@hero.landing.title" → texte localisé
    "texte direct" → retourné tel quel
    """
    if not value or not value.startswith("@"):
        return value

    key = value[1:]  # retire le @
    catalog = _load_lang(lang)

    # Navigation dans le dict imbriqué : "hero.landing.title" → catalog["hero"]["landing"]["title"]
    parts = key.split(".")
    node = catalog
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return f"[missing:{key}]"

    return str(node) if not isinstance(node, dict) else f"[missing:{key}]"


def resolve_placeholders(text: str, context: Optional[dict] = None) -> str:
    """
    Remplace les placeholders {city}, {price}, etc. par les valeurs du contexte.
    Les placeholders sans correspondance sont laissés intacts.
    """
    if not context or not text:
        return text

    def replacer(match):
        placeholder = match.group(1)
        return str(context.get(placeholder, match.group(0)))

    return re.sub(r"\{(\w+)\}", replacer, text)


def resolve(value: str, lang: str = "fr", context: Optional[dict] = None) -> str:
    """
    Pipeline complet : i18n → placeholders.
    Usage : resolve("@hero.landing.title", lang="fr", context={"city": "Rennes"})
    """
    text = i18n_resolve(value, lang)
    return resolve_placeholders(text, context)


def reload_cache():
    """Force le rechargement du cache i18n (utile en dev)."""
    _I18N_CACHE.clear()
