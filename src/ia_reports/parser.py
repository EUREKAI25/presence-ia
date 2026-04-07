"""
Parseur robuste de ia_results.

Tolère tous les formats rencontrés dans la DB :

  Format A (V3 principal) — liste de résultats par entrée modèle×requête :
    [
      {"model": "ChatGPT", "prompt": "...", "response": "...", "tested_at": "..."},
      {"model": "Gemini",  "prompt": "...", "response": "...", "tested_at": "..."},
      ...
    ]

  Format B (legacy) — liste par requête avec résultats précompilés :
    [
      {
        "query": "...",
        "chatgpt": {"cited": false, "competitors": [...]},
        "gemini":  {"cited": true,  "competitors": [...]},
        "claude":  {"cited": false, "competitors": [...]}
      },
      ...
    ]

  + chaîne JSON de l'un des formats ci-dessus
  + None / [] → retourne []

Structure canonique retournée :
  [
    {
      "query":         str,         # prompt brut
      "query_display": str,         # nettoyé pour affichage client
      "chatgpt":       bool | None, # cité ? None = non testé
      "gemini":        bool | None,
      "claude":        bool | None,
      "tested_at":     str,
      "responses":     dict,        # {model: réponse brute} pour extraction concurrents
    },
    ...  # max 5 requêtes
  ]
"""

import json
import logging
import re
import unicodedata

log = logging.getLogger(__name__)

MODELS = ["ChatGPT", "Gemini", "Claude"]
MAX_QUERIES = 5


# ── Normalisation ─────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Normalise pour comparaison souple : minuscules, sans accents, sans suffixes légaux."""
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b(sarl|sas|eurl|sa|sasu|sci|ei|auto entrepreneur)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _clean_query(q: str) -> str:
    """Retire les artefacts de formatage des prompts ({profession}, {ville}, etc.)."""
    q = re.sub(r"\{[^}]+\}", "", q).strip()
    return q if q else q


# ── Citation ──────────────────────────────────────────────────────────────────

def is_cited(company_name: str, response: str, aliases: list[str] | None = None) -> bool:
    """
    Vérifie si le nom de l'entreprise apparaît dans une réponse IA.

    Utilise une majorité stricte : plus de la moitié des mots significatifs
    (≥ 3 chars) du nom doivent apparaître dans la réponse normalisée.
    Cela évite les faux positifs sur des mots génériques comme "plomberie".

    Args:
        company_name : nom principal de l'entreprise
        response     : texte de la réponse IA
        aliases      : noms alternatifs à tester en parallèle (ex: nom court)

    Returns:
        True si l'entreprise est citée.
    """
    if not company_name or not response:
        return False

    resp_norm = _norm(response)

    def _check(name: str) -> bool:
        name_norm = _norm(name)
        words = [w for w in name_norm.split() if len(w) >= 3]
        if not words:
            return False
        matches = sum(1 for w in words if w in resp_norm)
        return matches > len(words) // 2

    if _check(company_name):
        return True

    for alias in (aliases or []):
        if alias and _check(alias):
            return True

    return False


# ── Parseur ───────────────────────────────────────────────────────────────────

def _load_raw(ia_results_raw) -> list:
    """Décode ia_results depuis str JSON, dict, list ou None."""
    if ia_results_raw is None:
        return []
    if isinstance(ia_results_raw, str):
        try:
            data = json.loads(ia_results_raw)
        except (json.JSONDecodeError, ValueError):
            log.warning("ia_results: impossible de parser le JSON")
            return []
        return data if isinstance(data, list) else []
    if isinstance(ia_results_raw, list):
        return ia_results_raw
    if isinstance(ia_results_raw, dict):
        # Cas rare : dict racine wrappant une liste
        return ia_results_raw.get("results", ia_results_raw.get("data", []))
    return []


def _is_format_a(entries: list) -> bool:
    """Format A : entrées de type {model, prompt/query, response}."""
    if not entries:
        return False
    first = entries[0]
    return isinstance(first, dict) and (
        "model" in first or "response" in first
    )


def _is_format_b(entries: list) -> bool:
    """Format B : entrées de type {query, chatgpt: {cited}, gemini, claude}."""
    if not entries:
        return False
    first = entries[0]
    return isinstance(first, dict) and (
        "chatgpt" in first or "gemini" in first or "claude" in first
    )


def _parse_format_a(entries: list, company_name: str, aliases: list[str]) -> list[dict]:
    """
    Parse le format principal V3 : une entrée par (modèle × requête).
    Groupe par prompt, calcule les citations depuis les réponses brutes.
    """
    by_prompt: dict[str, dict] = {}

    for entry in entries:
        prompt = entry.get("prompt") or entry.get("query") or ""
        model  = entry.get("model", "")
        resp   = entry.get("response", "") or ""
        ts     = entry.get("tested_at", "")

        if not prompt:
            continue

        if prompt not in by_prompt:
            by_prompt[prompt] = {
                "query":     prompt,
                "chatgpt":   None,
                "gemini":    None,
                "claude":    None,
                "tested_at": ts,
                "responses": {},
            }

        model_key = model.lower()
        if model_key in ("chatgpt", "openai", "gpt"):
            by_prompt[prompt]["chatgpt"] = is_cited(company_name, resp, aliases)
            by_prompt[prompt]["responses"]["ChatGPT"] = resp
        elif model_key in ("gemini", "google", "bard"):
            by_prompt[prompt]["gemini"] = is_cited(company_name, resp, aliases)
            by_prompt[prompt]["responses"]["Gemini"] = resp
        elif model_key in ("claude", "anthropic"):
            by_prompt[prompt]["claude"] = is_cited(company_name, resp, aliases)
            by_prompt[prompt]["responses"]["Claude"] = resp

    rows = list(by_prompt.values())
    for row in rows:
        row["query_display"] = _clean_query(row["query"])

    return rows[:MAX_QUERIES]


def _parse_format_b(entries: list) -> list[dict]:
    """
    Parse le format legacy : une entrée par requête avec cited précompilé.
    """
    rows = []
    for entry in entries:
        query = entry.get("query") or entry.get("prompt") or ""
        if not query:
            continue

        def _cited(model_data) -> bool | None:
            if model_data is None:
                return None
            if isinstance(model_data, dict):
                v = model_data.get("cited")
                if isinstance(v, bool):
                    return v
                # Certains formats stockent "✓" / "✗"
                if v in ("✓", "yes", "true", True):
                    return True
                if v in ("✗", "no", "false", False):
                    return False
            if isinstance(model_data, bool):
                return model_data
            return None

        rows.append({
            "query":         query,
            "query_display": _clean_query(query),
            "chatgpt":       _cited(entry.get("chatgpt")),
            "gemini":        _cited(entry.get("gemini")),
            "claude":        _cited(entry.get("claude")),
            "tested_at":     entry.get("tested_at", ""),
            "responses":     {},  # Pas de réponses brutes dans ce format
        })

    return rows[:MAX_QUERIES]


def parse_ia_results(
    ia_results_raw,
    company_name: str,
    aliases: list[str] | None = None,
) -> list[dict]:
    """
    Point d'entrée principal du parseur.

    Détecte le format automatiquement et retourne une liste canonique de requêtes.
    Robuste face aux données manquantes, JSON malformé, formats inconnus.

    Args:
        ia_results_raw : JSON string, liste Python, dict, ou None
        company_name   : nom de l'entreprise auditée (pour la détection de citations)
        aliases        : noms alternatifs (nom court, nom sans forme juridique, etc.)

    Returns:
        list[dict] — structure canonique, max 5 requêtes
    """
    if not company_name:
        log.warning("parse_ia_results: company_name vide, citations non calculables")

    entries = _load_raw(ia_results_raw)
    if not entries:
        return []

    if _is_format_b(entries):
        log.debug("parse_ia_results: format B détecté (%d entrées)", len(entries))
        return _parse_format_b(entries)

    if _is_format_a(entries):
        log.debug("parse_ia_results: format A détecté (%d entrées)", len(entries))
        return _parse_format_a(entries, company_name, aliases or [])

    log.warning("parse_ia_results: format non reconnu, tentative format A par défaut")
    return _parse_format_a(entries, company_name, aliases or [])
