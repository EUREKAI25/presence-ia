"""
Génération automatique de mots_cles_sirene via LLM.

Pour chaque profession, demande au LLM les mots-clés de même racine étymologique
qui apparaissent dans les raisons sociales SIRENE. Ces mots servent à filtrer
les résultats SIRENE quand un NAF est partagé entre plusieurs professions.

Exemples :
  Pisciniste  → ["piscine", "piscines", "piscinier", "pisciniste"]
  Plombier    → ["plomberie", "plombier", "plombiers"]
  Fleuriste   → ["fleurs", "fleuriste", "floral", "florist"]
"""
import json, logging, os, re
import urllib.request

log = logging.getLogger(__name__)

_PROMPT = """Tu es un expert de la base SIRENE (registre des entreprises françaises).

Pour la profession : {label}

Ta tâche : trouver les mots-clés qui apparaissent dans les raisons sociales SIRENE
de cette profession — UNIQUEMENT les termes de la même racine étymologique.

Règles strictes :
- Même racine uniquement : "piscine" → ["piscine", "piscines", "piscinier", "pisciniste"]
- Mots courts (1 mot, max 15 caractères)
- PAS d'associations sémantiques (pas "aqua", "spa", "natation" pour pisciniste)
- PAS de localités, verbes, adjectifs génériques
- Couvre les variantes morphologiques du même mot (singulier/pluriel, suffixes métier)

Exemples :
- Pisciniste → ["piscine", "piscines", "piscinier", "pisciniste"]
- Plombier → ["plomberie", "plombier", "plombiers"]
- Fleuriste → ["fleurs", "fleuriste", "floral", "florist"]

Profession : {label}
Codes NAF : {codes_naf}

Réponds UNIQUEMENT avec un tableau JSON valide, sans explication."""


def _call_llm(label: str, codes_naf: list) -> list[str]:
    """Appelle Claude (Anthropic) pour générer les mots-clés SIRENE."""
    prompt = _PROMPT.format(label=label, codes_naf=", ".join(codes_naf))

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY non définie")

    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    payload = json.dumps({
        "model": model,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())

    text = data["content"][0]["text"].strip()

    # Extraire le JSON même si le LLM ajoute du texte autour
    m = re.search(r"\[.*?\]", text, re.DOTALL)
    if not m:
        raise ValueError(f"Réponse LLM non parseable : {text!r}")

    keywords = json.loads(m.group())
    # Nettoyage : minuscules, max 15 chars, pas vide
    return [k.lower().strip() for k in keywords if k and len(k.strip()) <= 15]


def generate_sirene_keywords(db, profession_id: str = None, force: bool = False) -> dict:
    """
    Génère mots_cles_sirene pour les professions qui n'en ont pas encore.
    Si profession_id fourni : traite uniquement cette profession.
    Si force=True : régénère même si déjà renseigné.
    Retourne {profession_id: keywords_list}.
    """
    from .models import ProfessionDB

    query = db.query(ProfessionDB)
    if profession_id:
        query = query.filter_by(id=profession_id)
    if not force:
        query = query.filter(ProfessionDB.mots_cles_sirene.is_(None))

    profs = query.all()
    results = {}

    for prof in profs:
        try:
            codes_naf = json.loads(prof.codes_naf or "[]")
            keywords = _call_llm(prof.label, codes_naf)
            if not keywords:
                log.warning("[KEYWORDS] %s → liste vide, ignoré", prof.id)
                continue
            prof.mots_cles_sirene = json.dumps(keywords, ensure_ascii=False)
            db.commit()
            results[prof.id] = keywords
            log.info("[KEYWORDS] %s → %s", prof.id, keywords)
        except Exception as e:
            log.error("[KEYWORDS] %s ERREUR: %s", prof.id, e)
            results[prof.id] = {"error": str(e)}

    return results
