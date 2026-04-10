"""
test_slot_coverage.py — Simulation de la logique N = f(slots closers)
Usage : python scripts/test_slot_coverage.py
"""

TAUX_CONVERSION  = 0.02   # 2% bootstrap
SEUIL_MIN        = 0.70   # 70% → générer des leads
SEUIL_MAX        = 0.85   # 85% → stopper


def simuler(label: str, proche_total: int, proche_reserves: int, leads_en_file: int):
    """Simule la logique de pilotage pour un état donné."""

    taux = proche_reserves / proche_total if proche_total > 0 else 0.0
    proche_disponibles = max(0, proche_total - proche_reserves)
    leads_necessaires  = int(proche_disponibles / TAUX_CONVERSION)
    leads_manquants    = max(0, leads_necessaires - leads_en_file)

    if taux >= SEUIL_MAX:
        statut   = "STOP — saturé"
        decision = "Ne rien faire"
    elif taux < SEUIL_MIN:
        statut   = "RUN — générer des leads"
        decision = f"Lancer outbound · cap = {leads_manquants} leads"
    else:
        # Zone intermédiaire 70–85%
        if leads_en_file >= leads_necessaires:
            statut   = "IDLE — file suffisante"
            decision = f"File OK ({leads_en_file} >= {leads_necessaires})"
        else:
            cap_topup = max(1, leads_manquants // 2)   # appoint léger : 50% du manque
            statut   = "TOP_UP — appoint léger"
            decision = f"Lancer outbound · cap = {cap_topup} leads (50% du manque)"

    print(f"\n{'─'*52}")
    print(f"  {label}")
    print(f"{'─'*52}")
    print(f"  Slots proches    : {proche_reserves}/{proche_total} remplis")
    print(f"  Taux couverture  : {taux*100:.0f}%  (min={SEUIL_MIN*100:.0f}% / max={SEUIL_MAX*100:.0f}%)")
    print(f"  Leads nécessaires: {leads_necessaires}  (={proche_disponibles} dispo / {TAUX_CONVERSION*100:.0f}%)")
    print(f"  Leads en file    : {leads_en_file}")
    print(f"  Leads manquants  : {leads_manquants}")
    print(f"  Statut           : {statut}")
    print(f"  Décision         : {decision}")


if __name__ == "__main__":
    print("\n" + "═"*52)
    print("  SIMULATION — Pilotage N = f(slots closers)")
    print("  Taux conversion bootstrap : 2%")
    print("═"*52)

    # Cas 1 : slots proches vides (20%)
    simuler(
        label          = "CAS 1 — Slots proches vides (20%)",
        proche_total   = 10,
        proche_reserves= 2,
        leads_en_file  = 50,
    )

    # Cas 2 : slots proches corrects (75%)
    simuler(
        label          = "CAS 2 — Slots proches corrects (75%)",
        proche_total   = 8,
        proche_reserves= 6,
        leads_en_file  = 50,
    )

    # Cas 3 : slots proches saturés (90%)
    simuler(
        label          = "CAS 3 — Slots proches saturés (90%)",
        proche_total   = 10,
        proche_reserves= 9,
        leads_en_file  = 200,
    )

    # Cas bonus : file insuffisante malgré couverture faible
    simuler(
        label          = "CAS 4 — File vide, slots libres",
        proche_total   = 10,
        proche_reserves= 1,
        leads_en_file  = 0,
    )

    print("\n" + "═"*52 + "\n")
