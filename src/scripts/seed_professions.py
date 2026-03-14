"""
Script one-time : génère ~200 professions via Claude API et insère dans ProfessionDB.

Usage (depuis /opt/presence-ia) :
    python -m src.scripts.seed_professions

Options :
    --dry-run   : affiche le JSON sans insérer en DB
    --force     : réinsère même les professions déjà en DB (met à jour)
"""
import json, os, sys

# Ajouter le répertoire racine au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

PROMPT = """Tu es un expert en marketing local français et en prospection commerciale.

Génère une liste de 200 professions/métiers de professionnels indépendants français qui ont besoin \
de visibilité locale en ligne pour trouver des clients.

Critères d'inclusion :
- Le professionnel est indépendant ou gérant d'une TPE/PME (PAS une franchise nationale)
- Quand un particulier ou une entreprise a besoin de ce service, il le cherche en ligne ou demande à une IA
- Le professionnel doit acquérir activement des clients (pas uniquement par réseau fermé ou réputation établie)
- Inclure les niches : une niche avec fort score de dépendance à la visibilité est très pertinente

Critères d'exclusion :
- Franchises nationales (opticien en chaîne, pharmacie, fast-food...)
- Professions réglementées sans concurrence locale réelle (notaire, pharmacien...)
- Métiers dont l'acquisition se fait uniquement via flux piéton ou plateformes nationales (restaurant standard, boulangerie de quartier...)
- Professions uniquement par réseau/recommandation fermé (avocat d'affaires, banquier privé...)

Pour chaque profession, retourne un objet JSON avec EXACTEMENT ces champs :
- "id": slug kebab-case unique (ex: "plombier", "chirurgien-esthetique")
- "label": nom FR singulier (ex: "Plombier")
- "label_pluriel": nom FR pluriel (ex: "Plombiers")
- "categorie": exactement une de ces valeurs: "Bâtiment", "Santé", "Beauté", "Auto", "Services", "Immobilier", "Juridique", "High-tech", "Événementiel", "Animal", "Autre"
- "codes_naf": liste des codes NAF principaux (liste de strings, ex: ["4322A", "4322B"]) — liste vide si incertain
- "termes_recherche": 2-4 termes pour chercher ces pros sur Google / SIRENE (ex: ["plombier", "plomberie", "chauffagiste"])
- "score_visibilite": entier 1-10 (10 = on Google immédiatement dès qu'on en a besoin, ex: plombier urgence)
- "score_conseil_ia": entier 1-10 (10 = on fait des recherches approfondies, on compare, on demande à ChatGPT avant de choisir, ex: chirurgien esthétique)
- "valeur_client": estimation en € entier de la valeur d'un nouveau client (commande typique ou valeur annuelle)
- "notes_ia": 1 phrase max expliquant les scores de visibilité et conseil_ia

Retourne UNIQUEMENT un tableau JSON valide de 200 objets, sans texte avant ni après, sans markdown.
"""


BATCHES = [
    ("Bâtiment",      "Concentre-toi sur : Bâtiment (artisans du bâtiment, travaux, rénovation). 50 professions."),
    ("Santé/Beauté",  "Concentre-toi sur : Santé, Beauté, Animal, Bien-être. 50 professions. PAS de Bâtiment."),
    ("Services/Auto", "Concentre-toi sur : Auto, Services aux particuliers, Événementiel, Autre. 50 professions. PAS de Bâtiment, Santé, Beauté."),
    ("Pro/Immo",      "Concentre-toi sur : Immobilier, Juridique, High-tech, Services B2B locaux. 50 professions. PAS de catégories précédentes."),
]


def _insert_profession(db, p: dict, force: bool) -> str:
    """Insère ou met à jour une profession. Retourne 'inserted'/'updated'/'skipped'."""
    from src.database import db_get_profession, db_upsert_profession
    pid = p.get("id", "").strip()
    if not pid:
        return "skipped"
    existing = db_get_profession(db, pid)
    if existing and not force:
        return "skipped"
    data = {
        "id":               pid,
        "label":            p.get("label", pid),
        "label_pluriel":    p.get("label_pluriel", p.get("label", pid) + "s"),
        "categorie":        p.get("categorie", "Autre"),
        "codes_naf":        json.dumps(p.get("codes_naf", []), ensure_ascii=False),
        "termes_recherche": json.dumps(p.get("termes_recherche", [pid]), ensure_ascii=False),
        "score_visibilite": p.get("score_visibilite"),
        "score_conseil_ia": p.get("score_conseil_ia"),
        "valeur_client":    p.get("valeur_client"),
        "notes_ia":         p.get("notes_ia"),
        "actif":            True,
    }
    db_upsert_profession(db, data)
    return "updated" if existing else "inserted"


def _call_and_insert(client, db, batch_label: str, instructions: str, force: bool, seen: set) -> int:
    """Appelle Claude, parse le JSON, insère chaque profession immédiatement."""
    prompt = PROMPT.replace("200 professions", "50 professions") + f"\n\nINSTRUCTIONS SPÉCIFIQUES : {instructions}"
    print(f"⏳ [{batch_label}] Appel API...", flush=True)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    print(f"✓ [{batch_label}] Réponse reçue ({len(text)} chars) — parsing JSON...", flush=True)

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    professions = json.loads(text)
    print(f"✓ [{batch_label}] {len(professions)} professions parsées — insertion en DB...", flush=True)

    inserted = 0
    for p in professions:
        pid = p.get("id", "").strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        status = _insert_profession(db, p, force)
        if status in ("inserted", "updated"):
            inserted += 1
            print(f"  + {p.get('label','?')} ({p.get('categorie','?')}) score={p.get('score_visibilite','?')}", flush=True)

    print(f"✅ [{batch_label}] {inserted} insérées en DB", flush=True)
    return inserted


def main():
    dry_run = "--dry-run" in sys.argv
    force   = "--force"   in sys.argv

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY manquante")
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("❌ anthropic non installé : pip install anthropic")
        sys.exit(1)

    if dry_run:
        print("Mode dry-run — pas d'insertion DB")

    client = anthropic.Anthropic(api_key=api_key)

    from src.database import SessionLocal
    db = SessionLocal()
    seen = set()
    total = 0

    try:
        for label, instructions in BATCHES:
            try:
                n = _call_and_insert(client, db, label, instructions, force, seen)
                total += n
                print(f"📊 Total en DB : {total}", flush=True)
            except Exception as e:
                print(f"⚠️ Lot {label} échoué : {e}", flush=True)
    finally:
        db.close()

    print(f"\n🎉 Terminé — {total} professions insérées au total", flush=True)

    if dry_run:
        print(json.dumps(professions[:3], ensure_ascii=False, indent=2))
        print(f"... (dry-run, {len(professions)} total)")
        return

    from src.database import SessionLocal
    from src.database import db_upsert_profession

    with SessionLocal() as db:
        inserted = updated = skipped = 0
        for p in professions:
            pid = p.get("id", "").strip()
            if not pid:
                skipped += 1
                continue

            from src.database import db_get_profession
            existing = db_get_profession(db, pid)

            if existing and not force:
                skipped += 1
                continue

            data = {
                "id":               pid,
                "label":            p.get("label", pid),
                "label_pluriel":    p.get("label_pluriel", p.get("label", pid) + "s"),
                "categorie":        p.get("categorie", "Autre"),
                "codes_naf":        json.dumps(p.get("codes_naf", []), ensure_ascii=False),
                "termes_recherche": json.dumps(p.get("termes_recherche", [pid]), ensure_ascii=False),
                "score_visibilite": p.get("score_visibilite"),
                "score_conseil_ia": p.get("score_conseil_ia"),
                "valeur_client":    p.get("valeur_client"),
                "notes_ia":         p.get("notes_ia"),
                "actif":            True,
            }
            db_upsert_profession(db, data)
            if existing:
                updated += 1
            else:
                inserted += 1

        print(f"✅ DB : {inserted} insérées, {updated} mises à jour, {skipped} ignorées")


if __name__ == "__main__":
    main()
