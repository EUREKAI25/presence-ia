"""
test_active_pair.py — Tests logiques Chantier C (sélection paire autonome)

Base SQLite en mémoire, état dans fichier temp.
Aucun pipeline réel, aucune écriture en production.

Usage :
  python scripts/test_active_pair.py
"""
import os, sys, uuid, tempfile
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# ── Couleurs terminal ─────────────────────────────────────────────────────────
G  = "\033[92m"   # vert
R  = "\033[91m"   # rouge
Y  = "\033[93m"   # jaune
B  = "\033[94m"   # bleu
DIM = "\033[2m"
RST = "\033[0m"
BOLD = "\033[1m"

def ok(msg):  print(f"  {G}✓{RST} {msg}")
def fail(msg):print(f"  {R}✗{RST} {msg}"); sys.exit(1)
def info(msg):print(f"  {DIM}{msg}{RST}")
def hdr(msg): print(f"\n{BOLD}{B}── {msg} {RST}")
def sep():    print(f"  {DIM}{'─'*54}{RST}")


# ── DB en mémoire ─────────────────────────────────────────────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# StaticPool : une seule connexion partagée → toutes les sessions voient la même DB en mémoire
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

from src.models import Base, ProspectionTargetDB, ProfessionDB, ScoringConfigDB, V3ProspectDB
Base.metadata.create_all(engine)


# ── Monkeypatch _STATE_FILE → fichier temp ────────────────────────────────────
import src.active_pair as _ap
_tmp_state = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
_tmp_state.close()
Path(_tmp_state.name).unlink()          # doit ne pas exister au départ
_ap._STATE_FILE = Path(_tmp_state.name)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _uid():
    return str(uuid.uuid4())

def _make_db() -> Session:
    """Retourne une session fraîche après avoir vidé les tables de test."""
    db = Session(engine)
    for tbl in (V3ProspectDB, ProspectionTargetDB, ProfessionDB, ScoringConfigDB):
        db.query(tbl).delete()
    db.commit()
    return db

def _profession(db, slug, label, score_v, score_c, score_i, valeur):
    p = ProfessionDB(
        id=slug, label=label, label_pluriel=label+"s",
        categorie="Test",
        score_visibilite=score_v, score_conseil_ia=score_c,
        score_concurrence=score_i, valeur_client=valeur,
        actif=True,
    )
    db.add(p); db.commit()
    return p

def _target(db, city, profession, active=True):
    t = ProspectionTargetDB(
        id=_uid(), name=f"{city}-{profession}",
        city=city, profession=profession, active=active,
    )
    db.add(t); db.commit()
    return t

def _prospects(db, city, profession, n, sent=False, bounced=False):
    """Crée n prospects pour la paire. sent=True → déjà envoyés."""
    for i in range(n):
        p = V3ProspectDB(
            token=_uid(),
            name=f"Société {city} {i}",
            city=city, profession=profession,
            landing_url=f"https://test/{i}",
            email=f"contact{i}@test-{city}.fr" if not bounced else None,
            sent_at=__import__("datetime").datetime.utcnow() if sent else None,
            email_status="bounced" if bounced else None,
        )
        db.add(p)
    db.commit()

def _scoring_cfg(db):
    c = ScoringConfigDB(
        id="default",
        w_visibilite=0.40, w_conseil_ia=0.30,
        w_concurrence=0.15, w_valeur=0.15,
    )
    db.add(c); db.commit()
    return c

def _score_label(score):
    return f"score={score:.1f}"

def _show_pair(label, city, profession, score, note=""):
    s = f"  {DIM}{label:8}{RST} {BOLD}{city} × {profession}{RST}  {Y}{_score_label(score)}{RST}"
    if note: s += f"  {DIM}({note}){RST}"
    print(s)

def _show_state(state):
    if state:
        info(f"→ Paire active : {state['city']} × {state['profession']}  "
             f"score={state['score']}  override={state.get('override', False)}")
    else:
        info("→ Aucune paire active")


# ═════════════════════════════════════════════════════════════════════════════
# SETUP COMMUN
# ═════════════════════════════════════════════════════════════════════════════

print(f"\n{BOLD}TEST CHANTIER C — Sélection autonome paire ville × métier{RST}")
print(f"{DIM}Base : SQLite :memory: · État : fichier temp · Aucun pipeline réel{RST}")

# Scores profession (score_visibilite=v, score_conseil_ia=c, score_concurrence=n, valeur)
# Score global ≈ v×0.4 + c×0.3 + n×0.15 + min(valeur/1000,10)×0.15
# Paire A : plombier Paris    → 9×0.4 + 9×0.3 + 7×0.15 + 8×0.15 = 3.6+2.7+1.05+1.2 = 8.55 → ~8.6
# Paire B : electricien Lyon  → 7×0.4 + 6×0.3 + 6×0.15 + 5×0.15 = 2.8+1.8+0.9+0.75 = 6.25 → ~6.3
# Paire C : menuisier Nantes  → 5×0.4 + 4×0.3 + 4×0.15 + 3×0.15 = 2.0+1.2+0.6+0.45 = 4.25 → ~4.3
# Paire D : peintre Paris     → 8×0.4 + 8×0.3 + 6×0.15 + 7×0.15 = 3.2+2.4+0.9+1.05 = 7.55 → ~7.6 (saturée)

PAIRS = [
    dict(city="Paris",   profession="plombier",    sv=9, sc=9, si=7, val=8000,  n_dispo=10, n_sent=0, label="A"),
    dict(city="Lyon",    profession="electricien", sv=7, sc=6, si=6, val=5000,  n_dispo=5,  n_sent=0, label="B"),
    dict(city="Nantes",  profession="menuisier",   sv=5, sc=4, si=4, val=3000,  n_dispo=3,  n_sent=0, label="C"),
    dict(city="Paris",   profession="peintre",     sv=8, sc=8, si=6, val=7000,  n_dispo=0,  n_sent=4, label="D (saturée)"),
]

print(f"\n{BOLD}Paires de test :{RST}")
for p in PAIRS:
    from src.database import db_score_global
    score_approx = (p["sv"]*0.40 + p["sc"]*0.30 + p["si"]*0.15 + min(p["val"]/1000,10)*0.15)
    _show_pair(
        p["label"],
        p["city"], p["profession"],
        score_approx,
        "saturée — 0 dispo" if p["n_dispo"] == 0 else f"{p['n_dispo']} prospects dispo",
    )

sep()


# ═════════════════════════════════════════════════════════════════════════════
# TEST 1 — Sélection de la meilleure paire disponible
# ═════════════════════════════════════════════════════════════════════════════
hdr("TEST 1 — Meilleure paire disponible choisie en premier")

db = _make_db()
_scoring_cfg(db)
for p in PAIRS:
    _profession(db, p["profession"], p["profession"].capitalize(),
                p["sv"], p["sc"], p["si"], p["val"])
    _target(db, p["city"], p["profession"])
    if p["n_dispo"] > 0:
        _prospects(db, p["city"], p["profession"], p["n_dispo"])
    if p["n_sent"] > 0:
        _prospects(db, p["city"], p["profession"], p["n_sent"], sent=True)

_ap.clear_active_pair("reset")

state = _ap.select_next_pair(db)
_show_state(state)

assert state is not None, "Aucune paire sélectionnée"
assert state["city"] == "Paris" and state["profession"] == "plombier", \
    f"Attendu Paris×plombier (score ~8.6), obtenu {state['city']}×{state['profession']}"

ok(f"Paire sélectionnée : {state['city']} × {state['profession']}  "
   f"(score={state['score']} — le plus élevé parmi les paires disponibles)")
info("Paire D (peintre Paris, score ~7.6) ignorée car 0 prospects dispo")

db.close()


# ═════════════════════════════════════════════════════════════════════════════
# TEST 2 — Une seule paire active à la fois
# ═════════════════════════════════════════════════════════════════════════════
hdr("TEST 2 — Une seule paire active à la fois")

db = _make_db()
_scoring_cfg(db)
for p in PAIRS:
    _profession(db, p["profession"], p["profession"].capitalize(),
                p["sv"], p["sc"], p["si"], p["val"])
    _target(db, p["city"], p["profession"])
    if p["n_dispo"] > 0:
        _prospects(db, p["city"], p["profession"], p["n_dispo"])

_ap.clear_active_pair("reset")

state1 = _ap.select_next_pair(db)
info(f"Premier appel select_next_pair → {state1['city']} × {state1['profession']}")

state2 = _ap.select_next_pair(db)     # deuxième appel sans clear
info(f"Deuxième appel select_next_pair → {state2['city']} × {state2['profession']}")

assert state1["city"] == state2["city"] and state1["profession"] == state2["profession"], \
    f"select_next_pair a changé de paire sans saturation : {state1} → {state2}"

current = _ap.get_active_pair()
assert current is not None, "Aucune paire active après sélection"
assert current["city"] == state1["city"] and current["profession"] == state1["profession"]

ok(f"Une seule paire active : {current['city']} × {current['profession']}")
ok("select_next_pair idempotent — ne change pas la paire si elle reste disponible")

db.close()


# ═════════════════════════════════════════════════════════════════════════════
# TEST 3 — Paire saturée ignorée
# ═════════════════════════════════════════════════════════════════════════════
hdr("TEST 3 — Paire saturée ignorée lors de la sélection")

db = _make_db()
_scoring_cfg(db)

# Seulement paire D (saturée, score élevé) et paire B (dispo, score moyen)
for p in [p for p in PAIRS if p["label"] in ("D (saturée)", "B")]:
    _profession(db, p["profession"], p["profession"].capitalize(),
                p["sv"], p["sc"], p["si"], p["val"])
    _target(db, p["city"], p["profession"])
    if p["n_dispo"] > 0:
        _prospects(db, p["city"], p["profession"], p["n_dispo"])
    if p["n_sent"] > 0:
        _prospects(db, p["city"], p["profession"], p["n_sent"], sent=True)

_ap.clear_active_pair("reset")

state = _ap.select_next_pair(db)
_show_state(state)

assert state is not None
assert not (state["city"] == "Paris" and state["profession"] == "peintre"), \
    "Paire D (saturée) ne devrait pas être sélectionnée"
assert state["city"] == "Lyon" and state["profession"] == "electricien", \
    f"Attendu Lyon×electricien, obtenu {state['city']}×{state['profession']}"

ok(f"Paire D (peintre Paris, score ~7.6) ignorée malgré son score élevé")
ok(f"Paire B sélectionnée à la place : {state['city']} × {state['profession']} (score={state['score']})")

db.close()


# ═════════════════════════════════════════════════════════════════════════════
# TEST 4 — Passage automatique à la suivante après saturation
# ═════════════════════════════════════════════════════════════════════════════
hdr("TEST 4 — Bascule automatique quand la paire active est saturée")

db = _make_db()
_scoring_cfg(db)

for p in [p for p in PAIRS if p["label"] in ("A", "B")]:
    _profession(db, p["profession"], p["profession"].capitalize(),
                p["sv"], p["sc"], p["si"], p["val"])
    _target(db, p["city"], p["profession"])
    _prospects(db, p["city"], p["profession"], p["n_dispo"])

# Forcer la paire A comme active
_ap.set_active_pair("Paris", "plombier", score=8.6, target_id="test-a")
info("Paire active initiale : Paris × plombier")

state = _ap.get_active_pair()
avail = _ap._available_count(db, state["city"], state["profession"])
info(f"Prospects dispo pour Paris×plombier : {avail}")

ok(f"Paire A active — {avail} prospects dispo, pas encore saturée")

# Simuler saturation : envoyer tous les prospects de la paire A
db.query(V3ProspectDB).filter(
    V3ProspectDB.city == "Paris",
    V3ProspectDB.profession == "plombier",
).update({"sent_at": __import__("datetime").datetime.utcnow()})
db.commit()

avail_after = _ap._available_count(db, "Paris", "plombier")
info(f"Après envoi de tous les prospects : {avail_after} dispo (saturée)")

# check_saturation doit détecter la saturation et passer à B
new_state = _ap.check_saturation(db)
_show_state(new_state)

assert new_state is not None, "Aucune paire sélectionnée après saturation"
assert not (new_state["city"] == "Paris" and new_state["profession"] == "plombier"), \
    "La paire saturée ne devrait plus être active"
assert new_state["city"] == "Lyon" and new_state["profession"] == "electricien", \
    f"Attendu Lyon×electricien, obtenu {new_state['city']}×{new_state['profession']}"

ok(f"Paire A saturée → passage automatique à paire B : "
   f"{new_state['city']} × {new_state['profession']} (score={new_state['score']})")

db.close()


# ═════════════════════════════════════════════════════════════════════════════
# TEST 5 — Override manuel
# ═════════════════════════════════════════════════════════════════════════════
hdr("TEST 5 — Override admin : forcer une paire spécifique")

db = _make_db()
_scoring_cfg(db)

for p in PAIRS:
    _profession(db, p["profession"], p["profession"].capitalize(),
                p["sv"], p["sc"], p["si"], p["val"])
    _target(db, p["city"], p["profession"])
    if p["n_dispo"] > 0:
        _prospects(db, p["city"], p["profession"], p["n_dispo"])

# Sélection automatique → Paire A
_ap.clear_active_pair("reset")
auto = _ap.select_next_pair(db)
info(f"Sélection auto → {auto['city']} × {auto['profession']}  (override={auto.get('override', False)})")
assert auto["city"] == "Paris" and auto["profession"] == "plombier"
assert not auto.get("override"), "La sélection auto ne devrait pas être un override"

# Override → forcer paire C (score faible)
forced = _ap.set_active_pair("Nantes", "menuisier", score=4.3,
                              target_id="test-c", override=True)
info(f"Après override    → {forced['city']} × {forced['profession']}  (override={forced.get('override')})")

assert forced["city"] == "Nantes" and forced["profession"] == "menuisier"
assert forced.get("override") is True, "Le flag override devrait être True"

current = _ap.get_active_pair()
assert current["city"] == "Nantes" and current["profession"] == "menuisier"

ok(f"Paire A (meilleure score) remplacée par override admin : "
   f"{forced['city']} × {forced['profession']}")
ok("Flag override=True préservé dans l'état")

# Réinitialiser : reprendre la sélection auto
_ap.clear_active_pair("reset_test")
reset = _ap.select_next_pair(db)
info(f"Après réinitialisation → {reset['city']} × {reset['profession']}  "
     f"(override={reset.get('override', False)})")
assert reset["city"] == "Paris" and reset["profession"] == "plombier"
assert not reset.get("override")

ok("Après réinitialisation, sélection auto reprend la meilleure paire")

db.close()


# ═════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ
# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'═'*58}")
print(f"{BOLD}{G}  5/5 tests passés{RST}")
print(f"{'═'*58}")
print(f"""
  {BOLD}Comportement validé :{RST}
  1. Meilleure paire disponible sélectionnée en premier {G}✓{RST}
  2. Une seule paire active à la fois                   {G}✓{RST}
  3. Paire saturée ignorée (même si score élevé)        {G}✓{RST}
  4. Bascule automatique après saturation               {G}✓{RST}
  5. Override admin + réinitialisation                  {G}✓{RST}
""")

# Nettoyage fichier temp
_ap.clear_active_pair("cleanup")
