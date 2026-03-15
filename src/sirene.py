"""
Client SIRENE — recherche-entreprises.api.gouv.fr

Interroge l'API officielle (gratuite, sans auth) pour récupérer
les établissements actifs par code NAF + optionnellement par département.

Usage :
    from src.sirene import qualify_profession
    qualify_profession(profession, db, max_per_naf=200)
"""
import json, logging, time
from typing import Optional
import urllib.request, urllib.parse

log = logging.getLogger(__name__)

_BASE = "https://recherche-entreprises.api.gouv.fr/search"
_PER_PAGE = 25   # max autorisé par l'API
_DELAY    = 0.3  # secondes entre requêtes (politesse)


def _naf_api(code: str) -> str:
    """Normalise le code NAF pour l'API : '4322A' → '43.22A', '43.22A' → '43.22A'."""
    code = code.strip().upper()
    if len(code) == 5 and "." not in code:
        return f"{code[:2]}.{code[2:]}"
    return code


def _fetch_page(naf: str, page: int, departement: Optional[str] = None) -> dict:
    params = {
        "activite_principale": _naf_api(naf),
        "etat_administratif":  "A",   # actifs uniquement
        "per_page":            str(_PER_PAGE),
        "page":                str(page),
    }
    if departement:
        params["departement"] = departement
    url = _BASE + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "presence-ia/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log.warning(f"SIRENE fetch error naf={naf} page={page}: {e}")
        return {}


def fetch_by_naf(naf: str, max_results: int = 200,
                 departement: Optional[str] = None) -> list[dict]:
    """
    Récupère jusqu'à max_results établissements pour un code NAF donné.
    Retourne une liste de dicts normalisés.
    """
    results = []
    page = 1
    total_pages = 1

    while page <= total_pages and len(results) < max_results:
        data = _fetch_page(naf, page, departement)
        if not data or "results" not in data:
            break

        total_pages = min(data.get("total_pages", 1),
                          (max_results + _PER_PAGE - 1) // _PER_PAGE)

        for item in data.get("results", []):
            siege = item.get("siege") or {}
            siret = siege.get("siret") or item.get("siret", "")
            if not siret:
                continue
            nom = (item.get("nom_complet")
                   or item.get("nom_raison_sociale")
                   or siege.get("denomination_usuelle") or "")
            ville = (siege.get("libelle_commune") or siege.get("commune") or "").strip().upper()
            cp    = (siege.get("code_postal") or "").strip()
            dept  = (siege.get("departement") or cp[:2] if len(cp) >= 2 else "").strip()

            results.append({
                "id":            siret,
                "raison_sociale": (nom or "").strip() or siret,
                "ville":         ville or None,
                "code_postal":   cp or None,
                "departement":   dept or None,
                "code_naf":      naf,
                "actif":         True,
                "contactable":   False,
            })

        log.debug(f"SIRENE naf={naf} page={page}/{total_pages} → {len(data.get('results',[]))} items")
        page += 1
        if page <= total_pages:
            time.sleep(_DELAY)

    return results[:max_results]


def qualify_profession(profession, db, max_per_naf: int = 200) -> int:
    """
    Récupère les établissements SIRENE pour une profession et les insère en DB.
    Retourne le nombre d'établissements insérés/mis à jour.
    """
    from .database import db_sirene_upsert

    codes_naf = []
    try:
        codes_naf = json.loads(profession.codes_naf or "[]")
    except Exception:
        pass

    if not codes_naf:
        log.warning(f"Profession {profession.id} sans codes NAF — skipping SIRENE")
        return 0

    total = 0
    for naf in codes_naf:
        log.info(f"[SIRENE] {profession.label} / NAF {naf} — fetch max {max_per_naf}...")
        items = fetch_by_naf(naf, max_results=max_per_naf)
        log.info(f"[SIRENE] {profession.label} / NAF {naf} → {len(items)} établissements")
        for item in items:
            item["profession_id"] = profession.id
            db_sirene_upsert(db, item)
            total += 1

    return total


def qualify_all_active(db, max_per_naf: int = 200) -> dict:
    """
    Lance la qualification SIRENE pour toutes les professions actives.
    Retourne un résumé {profession_id: nb_insérés}.
    """
    from .database import db_list_professions
    profs = [p for p in db_list_professions(db) if p.actif]
    summary = {}
    for prof in profs:
        try:
            n = qualify_profession(prof, db, max_per_naf=max_per_naf)
            summary[prof.id] = n
            log.info(f"[SIRENE qualify] {prof.label} → {n} établissements")
        except Exception as e:
            log.error(f"[SIRENE qualify] {prof.label} ERREUR: {e}")
            summary[prof.id] = -1
    return summary
