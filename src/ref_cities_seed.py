"""
ref_cities_seed.py — Villes de référence françaises (préfectures + sous-préfectures).
Utilisé au démarrage pour peupler ref_cities et backfiller city_reference sur V3ProspectDB.
"""
from __future__ import annotations

# (city_name_uppercase, city_type)
REF_CITIES: list[tuple[str, str]] = [
    # Préfectures
    ("PARIS", "prefecture"), ("MARSEILLE", "prefecture"), ("LYON", "prefecture"),
    ("TOULOUSE", "prefecture"), ("NICE", "prefecture"), ("NANTES", "prefecture"),
    ("STRASBOURG", "prefecture"), ("MONTPELLIER", "prefecture"), ("BORDEAUX", "prefecture"),
    ("LILLE", "prefecture"), ("RENNES", "prefecture"), ("REIMS", "prefecture"),
    ("SAINT-ETIENNE", "prefecture"), ("TOULON", "prefecture"), ("GRENOBLE", "prefecture"),
    ("DIJON", "prefecture"), ("ANGERS", "prefecture"), ("NIMES", "prefecture"),
    ("VILLEURBANNE", "prefecture"), ("CLERMONT-FERRAND", "prefecture"),
    ("LE MANS", "prefecture"), ("AMIENS", "prefecture"), ("LIMOGES", "prefecture"),
    ("TOURS", "prefecture"), ("METZ", "prefecture"), ("BESANCON", "prefecture"),
    ("PERPIGNAN", "prefecture"), ("BREST", "prefecture"), ("ROUEN", "prefecture"),
    ("ARGENTEUIL", "prefecture"), ("ORLEANS", "prefecture"), ("NANCY", "prefecture"),
    ("POITIERS", "prefecture"), ("PAU", "prefecture"), ("MULHOUSE", "prefecture"),
    ("CAEN", "prefecture"), ("AVIGNON", "prefecture"), ("VERSAILLES", "prefecture"),
    ("NANTERRE", "prefecture"), ("CRETEIL", "prefecture"), ("BOBIGNY", "prefecture"),
    ("EVRY", "prefecture"), ("CERGY", "prefecture"), ("MELUN", "prefecture"),
    ("ANNECY", "prefecture"), ("CHAMBERY", "prefecture"), ("AUXERRE", "prefecture"),
    ("TROYES", "prefecture"), ("CHALONS-EN-CHAMPAGNE", "prefecture"),
    ("COLMAR", "prefecture"), ("BELFORT", "prefecture"), ("MACON", "prefecture"),
    ("EPINAL", "prefecture"), ("CHAUMONT", "prefecture"), ("BAR-LE-DUC", "prefecture"),
    ("VESOUL", "prefecture"), ("NEVERS", "prefecture"), ("MOULINS", "prefecture"),
    ("BOURGES", "prefecture"), ("CHATEAUROUX", "prefecture"), ("TULLE", "prefecture"),
    ("AURILLAC", "prefecture"), ("PERIGUEUX", "prefecture"), ("AGEN", "prefecture"),
    ("CAHORS", "prefecture"), ("MONTAUBAN", "prefecture"), ("ALBI", "prefecture"),
    ("AUCH", "prefecture"), ("TARBES", "prefecture"), ("FOIX", "prefecture"),
    ("CARCASSONNE", "prefecture"), ("RODEZ", "prefecture"), ("MENDE", "prefecture"),
    ("VALENCE", "prefecture"), ("PRIVAS", "prefecture"), ("GAP", "prefecture"),
    ("DIGNE-LES-BAINS", "prefecture"), ("NICE", "prefecture"),
    ("LA ROCHELLE", "prefecture"), ("ANGOULEME", "prefecture"),
    ("LAVAL", "prefecture"), ("ALENCON", "prefecture"), ("SAINT-LO", "prefecture"),
    ("VANNES", "prefecture"), ("QUIMPER", "prefecture"), ("SAINT-BRIEUC", "prefecture"),
    ("RENNES", "prefecture"), ("LAON", "prefecture"), ("BEAUVAIS", "prefecture"),
    ("EVREUX", "prefecture"), ("CHARTRES", "prefecture"), ("ARRAS", "prefecture"),
    ("LONS-LE-SAUNIER", "prefecture"), ("BOURG-EN-BRESSE", "prefecture"),
    ("GUERET", "prefecture"), ("LA ROCHE-SUR-YON", "prefecture"),
    ("NIORT", "prefecture"), ("LIMOGES", "prefecture"), ("LE PUY-EN-VELAY", "prefecture"),
    ("BLOIS", "prefecture"), ("MONT-DE-MARSAN", "prefecture"), ("AJACCIO", "prefecture"),
    ("BASTIA", "prefecture"),
    # Sous-préfectures importantes
    ("DUNKERQUE", "sous_prefecture"), ("CALAIS", "sous_prefecture"),
    ("BOULOGNE-SUR-MER", "sous_prefecture"), ("VALENCIENNES", "sous_prefecture"),
    ("DOUAI", "sous_prefecture"), ("MAUBEUGE", "sous_prefecture"),
    ("LE HAVRE", "sous_prefecture"), ("DIEPPE", "sous_prefecture"),
    ("LORIENT", "sous_prefecture"), ("SAINT-NAZAIRE", "sous_prefecture"),
    ("BAYONNE", "sous_prefecture"), ("BIARRITZ", "sous_prefecture"),
    ("SAINT-GAUDENS", "sous_prefecture"), ("CASTRES", "sous_prefecture"),
    ("ALBI", "sous_prefecture"), ("BEZIERS", "sous_prefecture"),
    ("SETE", "sous_prefecture"), ("NARBONNE", "sous_prefecture"),
    ("PERPIGNAN", "sous_prefecture"), ("FREJUS", "sous_prefecture"),
    ("ANTIBES", "sous_prefecture"), ("CANNES", "sous_prefecture"),
    ("GRASSE", "sous_prefecture"), ("MENTON", "sous_prefecture"),
    ("AIX-EN-PROVENCE", "sous_prefecture"), ("ARLES", "sous_prefecture"),
    ("AUBAGNE", "sous_prefecture"), ("DRAGUIGNAN", "sous_prefecture"),
    ("BRIGNOLES", "sous_prefecture"), ("HYERES", "sous_prefecture"),
    ("CARPENTRAS", "sous_prefecture"), ("ORANGE", "sous_prefecture"),
    ("GAP", "sous_prefecture"), ("DIGNE-LES-BAINS", "sous_prefecture"),
    ("MENTON", "sous_prefecture"), ("SAINT-MARTIN-D'HERES", "sous_prefecture"),
    ("VIENNE", "sous_prefecture"), ("VOIRON", "sous_prefecture"),
    ("BOURGOIN-JALLIEU", "sous_prefecture"), ("THONON-LES-BAINS", "sous_prefecture"),
    ("ANNEMASSE", "sous_prefecture"), ("ALBERTVILLE", "sous_prefecture"),
    ("SAINT-JEAN-DE-MAURIENNE", "sous_prefecture"), ("AIX-LES-BAINS", "sous_prefecture"),
    ("BRON", "sous_prefecture"), ("VILLEFRANCHE-SUR-SAONE", "sous_prefecture"),
    ("MACON", "sous_prefecture"), ("BOURG-EN-BRESSE", "sous_prefecture"),
    ("ROANNE", "sous_prefecture"), ("MONTBRISON", "sous_prefecture"),
    ("THIERS", "sous_prefecture"), ("RIOM", "sous_prefecture"),
    ("ISSOIRE", "sous_prefecture"), ("VICHY", "sous_prefecture"),
    ("CUSSET", "sous_prefecture"), ("MONTLUCON", "sous_prefecture"),
    ("MOULINS", "sous_prefecture"),
]


def seed_ref_cities(db) -> int:
    """Insère les villes de référence manquantes. Retourne le nombre insérées."""
    from .models import RefCityDB
    existing = {r.city_name for r in db.query(RefCityDB.city_name).all()}
    inserted = 0
    for city_name, city_type in REF_CITIES:
        if city_name not in existing:
            db.add(RefCityDB(city_name=city_name, city_type=city_type))
            inserted += 1
    if inserted:
        db.commit()
    return inserted


def backfill_city_reference(db) -> int:
    """
    Pour chaque prospect dont city (UPPERCASE) est dans ref_cities :
    → city_reference = city
    Sinon laisse NULL.
    Retourne le nombre de prospects mis à jour.
    """
    from .models import RefCityDB, V3ProspectDB

    ref_names = {r.city_name for r in db.query(RefCityDB.city_name).all()}

    updated = 0
    prospects = db.query(V3ProspectDB).filter(V3ProspectDB.city_reference.is_(None)).all()
    for p in prospects:
        city_upper = (p.city or "").strip().upper()
        if city_upper in ref_names:
            p.city_reference = p.city
            updated += 1
    if updated:
        db.commit()
    return updated
