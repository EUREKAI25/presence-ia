"""Routes /closing_pack, /closing_pack/exemple/* et /recap."""
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

CLOSER_TOKEN = os.getenv("CLOSER_TOKEN", "closer-secret")
_ROOT = Path(__file__).parent.parent.parent.parent / "RESOURCES"
_FICHE_PATH = _ROOT / "FICHE_PRODUIT_PRESENCE_IA.html"
_EXEMPLES_DIR = _ROOT / "exemples"
_RECRUTEMENT_PATH = _ROOT / "recrutement_closers.html"

router = APIRouter(tags=["Closing Pack"])

VALID_SLUG = re.compile(r'^[a-z0-9_-]+$')


@router.get("/closing_pack", response_class=HTMLResponse)
def closing_pack(t: str = ""):
    if not t or t != CLOSER_TOKEN:
        raise HTTPException(403, "Accès refusé")
    if not _FICHE_PATH.exists():
        raise HTTPException(404, "Fiche produit introuvable")
    return _FICHE_PATH.read_text(encoding="utf-8")


@router.get("/closing_pack/exemple/{slug}", response_class=HTMLResponse)
def closing_pack_exemple(slug: str, t: str = ""):
    if not t or t != CLOSER_TOKEN:
        raise HTTPException(403, "Accès refusé")
    if not VALID_SLUG.match(slug):
        raise HTTPException(400, "Slug invalide")
    filepath = _EXEMPLES_DIR / f"{slug}.html"
    if not filepath.exists():
        raise HTTPException(404, f"Exemple '{slug}' introuvable")
    return filepath.read_text(encoding="utf-8")


@router.get("/recap", response_class=HTMLResponse)
def recap_coach():
    """Page de récap publique pour partage avec coach / partenaires."""
    filepath = _EXEMPLES_DIR / "recap_coach.html"
    if not filepath.exists():
        raise HTTPException(404, "Récap introuvable")
    return filepath.read_text(encoding="utf-8")


@router.get("/confirmation", response_class=HTMLResponse)
def confirmation():
    return HTMLResponse("""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rendez-vous confirmé — Présence IA</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,'Segoe UI',sans-serif;background:#f8fafc;color:#1e293b;
      min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
    .card{background:#fff;border-radius:16px;border:1px solid #e2e8f0;
      box-shadow:0 4px 32px rgba(0,0,0,.06);max-width:560px;width:100%;padding:48px 48px 52px;
      text-align:center}
    .icon{width:56px;height:56px;background:#f0fdf4;border-radius:50%;
      display:flex;align-items:center;justify-content:center;margin:0 auto 28px;
      font-size:26px}
    h1{font-size:1.75rem;font-weight:800;color:#0f172a;letter-spacing:-.03em;margin-bottom:16px}
    .lead{font-size:1rem;color:#475569;line-height:1.7;margin-bottom:32px}
    .list{text-align:left;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;
      padding:20px 24px;margin-bottom:32px}
    .list li{display:flex;align-items:flex-start;gap:10px;font-size:.95rem;color:#334155;
      padding:7px 0;border-bottom:1px solid #e2e8f0;line-height:1.5}
    .list li:last-child{border-bottom:none}
    .list li::before{content:"•";color:#2563eb;font-weight:700;flex-shrink:0;margin-top:1px}
    .duration{display:inline-flex;align-items:center;gap:8px;background:#eff6ff;
      color:#1d4ed8;font-size:.85rem;font-weight:600;padding:8px 18px;
      border-radius:30px;margin-bottom:28px}
    .note{font-size:.88rem;color:#64748b;line-height:1.65;
      border-top:1px solid #f1f5f9;padding-top:24px}
    .brand{margin-top:40px;font-size:.78rem;color:#94a3b8;letter-spacing:.04em}
    .brand span{color:#2563eb;font-weight:700}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✓</div>
    <h1>Votre audit IA est prêt</h1>
    <p class="lead">Nous avons analysé la visibilité de votre entreprise<br>dans les réponses des IA.</p>
    <ul class="list">
      <li>Quels concurrents sont recommandés à votre place</li>
      <li>Pourquoi ils apparaissent et pas vous</li>
      <li>Comment corriger cela</li>
    </ul>
    <div class="duration">⏱ Durée de l'appel : 20 minutes</div>
    <p class="note">Nous vous montrerons votre audit en direct pendant l'appel.<br>
    Merci de préparer vos questions si vous souhaitez analyser un point précis.</p>
    <p class="brand">Présence <span>IA</span></p>
  </div>
</body>
</html>""")


@router.get("/recrutement", response_class=HTMLResponse)
def recrutement():
    """Page de recrutement closers (publique)."""
    if not _RECRUTEMENT_PATH.exists():
        raise HTTPException(404, "Page introuvable")
    return _RECRUTEMENT_PATH.read_text(encoding="utf-8")


@router.get("/exemple/{slug}", response_class=HTMLResponse)
def exemple_public(slug: str):
    """Exemples de livrables publics (pas de token requis — contenu démo uniquement)."""
    if not VALID_SLUG.match(slug):
        raise HTTPException(400, "Slug invalide")
    filepath = _EXEMPLES_DIR / f"{slug}.html"
    if not filepath.exists():
        raise HTTPException(404, f"Exemple '{slug}' introuvable")
    return filepath.read_text(encoding="utf-8")
