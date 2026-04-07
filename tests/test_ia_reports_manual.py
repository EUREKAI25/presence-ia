#!/usr/bin/env python3
"""
Test manuel du moteur ia_reports.

Exécuter depuis la racine du projet :
  python tests/test_ia_reports_manual.py
  python tests/test_ia_reports_manual.py --token <token_prospect>
  python tests/test_ia_reports_manual.py --list
  python tests/test_ia_reports_manual.py --fixture    # utilise données de test intégrées

Sans argument : utilise le premier prospect avec ia_results en DB.
"""

import argparse
import json
import sys
from pathlib import Path

# ── Path setup (exécution standalone depuis la racine) ───────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.database import new_session, init_db


def _print_banner(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def _print_result(label: str, value, ok: bool = True):
    icon = "✓" if ok else "✗"
    print(f"  {icon} {label}: {value}")


# ── Fixture locale (sans DB) ──────────────────────────────────────────────────

def run_fixture_test():
    """Test complet avec données synthétiques — ne nécessite pas de DB."""
    _print_banner("TEST FIXTURE — Données synthétiques")

    from src.ia_reports.parser import parse_ia_results
    from src.ia_reports.scoring import compute_score, extract_competitors, build_checklist
    from src.ia_reports.generator import render_audit_html, render_monthly_html, select_cms_guide, save_html, OUTPUT_AUDITS, OUTPUT_REPORTS

    company = "Dupont Plomberie"
    profession = "plombier"
    city = "Lyon"

    # Données ia_results format A (V3 principal)
    ia_results_raw = json.dumps([
        {"model": "ChatGPT", "prompt": "plombier urgence Lyon",
         "response": "Je recommande Dupont Plomberie à Lyon, disponible 24h/24.", "tested_at": "2026-04-07T10:00:00"},
        {"model": "Gemini",  "prompt": "plombier urgence Lyon",
         "response": "Piron Plomberie est bien noté dans votre secteur.", "tested_at": "2026-04-07T10:01:00"},
        {"model": "Claude",  "prompt": "plombier urgence Lyon",
         "response": "Dupont Plomberie est souvent mentionné pour les urgences lyonnaises.", "tested_at": "2026-04-07T10:02:00"},
        {"model": "ChatGPT", "prompt": "meilleur plombier Lyon 3e",
         "response": "Lyon Dépannage Express et Piron Plomberie sont très appréciés.", "tested_at": "2026-04-07T10:03:00"},
        {"model": "Gemini",  "prompt": "meilleur plombier Lyon 3e",
         "response": "Dupont Plomberie reçoit de bonnes évaluations sur Google.", "tested_at": "2026-04-07T10:04:00"},
        {"model": "Claude",  "prompt": "meilleur plombier Lyon 3e",
         "response": "Je n'ai pas d'informations récentes sur ce secteur précis.", "tested_at": "2026-04-07T10:05:00"},
        {"model": "ChatGPT", "prompt": "plombier chauffagiste Lyon tarif",
         "response": "Dupont Plomberie et Thermique Sud sont compétitifs.", "tested_at": "2026-04-07T10:06:00"},
        {"model": "Gemini",  "prompt": "plombier chauffagiste Lyon tarif",
         "response": "Les tarifs varient selon la prestation.", "tested_at": "2026-04-07T10:07:00"},
        {"model": "Claude",  "prompt": "plombier chauffagiste Lyon tarif",
         "response": "Dupont Plomberie affiche des tarifs clairs sur son site.", "tested_at": "2026-04-07T10:08:00"},
    ])

    print("\n1. PARSING")
    queries = parse_ia_results(ia_results_raw, company)
    print(f"   {len(queries)} requêtes parsées")
    for q in queries:
        print(f"   - {q['query_display'][:50]} | GPT:{q['chatgpt']} Gem:{q['gemini']} Cla:{q['claude']}")

    print("\n2. SCORE")
    score_data = compute_score(queries)
    for k, v in score_data.items():
        print(f"   {k}: {v}")

    print("\n3. CONCURRENTS")
    competitors = extract_competitors(queries, company)
    for c in competitors:
        print(f"   - {c['name']} (cité {c['count']} fois)")

    print("\n4. CHECKLIST")
    checklist = build_checklist(score_data["score"], profession, city)
    print(f"   Niveau : {checklist['level']} — {checklist['title']}")
    for item in checklist["items"]:
        print(f"   · {item['title']}")

    print("\n5. GUIDE CMS")
    guide = select_cms_guide(cms="wordpress")
    print(f"   Guide : {guide.name} (existe: {guide.exists()})")

    print("\n6. AUDIT HTML")
    html = render_audit_html(
        name=company, profession=profession, city=city, cms="WordPress",
        score_data=score_data, queries=queries, competitors=competitors, checklist=checklist,
        next_step="Nos équipes démarrent cette semaine."
    )
    path = save_html(html, OUTPUT_AUDITS, "fixture_audit.html")
    print(f"   Fichier : {path}")
    _print_result("Taille HTML", f"{len(html):,} chars")

    print("\n7. RAPPORT MENSUEL (simulation M1)")
    previous = {
        "score": 2.0,
        "date": "7 mars 2026",
        "queries": [
            {"query": "plombier urgence Lyon", "query_display": "plombier urgence Lyon",
             "chatgpt": False, "gemini": False, "claude": False},
        ]
    }
    html_monthly = render_monthly_html(
        name=company, profession=profession, city=city,
        current={"score_data": score_data, "queries": queries},
        previous=previous,
        num_test=2,
        periode="avril 2026",
        actions_done=[
            {"date": "15 mars", "title": "GBP mis à jour", "desc": "Photos + description", "status": "done"},
            {"date": "22 mars", "title": "FAQ publiée", "desc": "8 questions", "status": "done"},
        ],
        next_actions=[
            {"title": "Annuaires locaux", "desc": "Pages Jaunes, Yelp, annuaire BTP"},
            {"title": "Campagne avis Google", "desc": "SMS aux 30 derniers clients"},
        ],
        reviews_count=8,
        annuaires_count=2,
    )
    path_monthly = save_html(html_monthly, OUTPUT_REPORTS, "fixture_report_m1.html")
    print(f"   Fichier : {path_monthly}")
    _print_result("Taille HTML", f"{len(html_monthly):,} chars")

    _print_banner("RÉSULTAT FIXTURE")
    print(f"  Score : {score_data['score']}/10")
    print(f"  Citations : {score_data['total_citations']}/{score_data['total_possible']}")
    print(f"  Audit : {path}")
    print(f"  Rapport : {path_monthly}")
    print(f"\n  Ouvrir : open {path}")
    print(f"  Ouvrir : open {path_monthly}\n")

    return True


# ── Test avec DB ──────────────────────────────────────────────────────────────

def list_prospects_with_results(db) -> list:
    """Liste les prospects V3 qui ont des ia_results."""
    try:
        from src.models import V3ProspectDB
    except ImportError:
        from models import V3ProspectDB
    return (
        db.query(V3ProspectDB)
        .filter(V3ProspectDB.ia_results.isnot(None))
        .filter(V3ProspectDB.ia_results != "")
        .all()
    )


def run_db_test(token: str | None = None):
    """Test avec un prospect réel depuis la DB."""
    _print_banner("TEST DB — Prospect réel")

    init_db()
    db = new_session()

    try:
        prospects = list_prospects_with_results(db)
        if not prospects:
            print("  Aucun prospect avec ia_results en DB.")
            print("  Utilisez --fixture pour un test sans DB.\n")
            return False

        if token:
            p = next((x for x in prospects if x.token == token), None)
            if not p:
                print(f"  Token {token!r} non trouvé dans les prospects avec ia_results.")
                print(f"  Prospects disponibles : {[x.token for x in prospects[:5]]}")
                return False
        else:
            p = prospects[0]
            print(f"  Prospect sélectionné : {p.name} ({p.token})")

        print(f"  Nom       : {p.name}")
        print(f"  Profession: {p.profession}")
        print(f"  Ville     : {p.city}")
        print(f"  CMS       : {getattr(p, 'cms', 'non renseigné')}")

        from src.ia_reports.service import (
            create_initial_audit_for_prospect,
            create_monthly_report_for_prospect,
        )
        from src.ia_reports.storage import count_snapshots

        # Audit
        print("\n  → Génération de l'audit initial...")
        audit = create_initial_audit_for_prospect(p.token, db)
        _print_result("Score", f"{audit['summary']['score']}/10")
        _print_result("Citations", f"{audit['summary']['total_citations']}/{audit['summary']['total_possible']}")
        _print_result("Concurrents", len(audit["summary"]["competitors"]))
        _print_result("Checklist", audit["summary"]["checklist_level"])
        _print_result("Fichier audit", audit["audit_path"])
        _print_result("Guide CMS", Path(audit["cms_guide_path"]).name)

        # Rapport mensuel (si ≥ 2 snapshots maintenant)
        snap_count = count_snapshots(db, p.token)
        if snap_count >= 2:
            print("\n  → Génération du rapport mensuel...")
            report = create_monthly_report_for_prospect(p.token, db)
            _print_result("Score mensuel", f"{report['summary']['score']}/10")
            _print_result("Delta", f"{report['summary']['delta']:+.1f} pts")
            _print_result("Fichier rapport", report["report_path"])
        else:
            print("\n  (Un seul snapshot — relancer pour générer le rapport mensuel)")

        _print_banner("RÉSULTAT DB")
        print(f"  Ouvrir audit : open {audit['audit_path']}\n")

    finally:
        db.close()

    return True


def run_list():
    """Liste tous les prospects avec ia_results."""
    _print_banner("PROSPECTS AVEC IA_RESULTS")
    init_db()
    db = new_session()
    try:
        prospects = list_prospects_with_results(db)
        if not prospects:
            print("  Aucun prospect avec ia_results.")
        for p in prospects:
            print(f"  {p.token:30s} | {p.name:35s} | {p.profession:20s} | {p.city}")
    finally:
        db.close()


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test manuel du moteur ia_reports — génère audit et rapport mensuel."
    )
    parser.add_argument("--token",   help="Token du prospect à tester")
    parser.add_argument("--list",    action="store_true", help="Lister les prospects avec ia_results")
    parser.add_argument("--fixture", action="store_true", help="Tester avec données synthétiques (sans DB)")
    args = parser.parse_args()

    if args.list:
        run_list()
    elif args.fixture:
        ok = run_fixture_test()
        sys.exit(0 if ok else 1)
    else:
        ok = run_db_test(token=args.token)
        sys.exit(0 if ok else 1)
