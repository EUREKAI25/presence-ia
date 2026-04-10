"""
Pages publiques Closer — recrutement + portail closer.

Routes :
  GET  /closer/              → page de présentation du programme
  GET  /closer/recruit       → formulaire de candidature
  POST /closer/recruit       → soumission candidature
  GET  /closer/{token}       → portail closer (ses RDV, stats)
  GET  /closer/{token}/meeting/{meeting_id} → fiche RDV détaillée
"""
import os
import uuid
import json
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter(tags=["Closer Public"])

PROJECT_ID = "presence-ia"


def _mkt():
    """Context manager marketing_module session."""
    from marketing_module.database import SessionLocal
    return SessionLocal()


# ─────────────────────────────────────────────────────────────────────────────
# Page de présentation du programme Closer
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/closer/", response_class=HTMLResponse)
@router.get("/closer", response_class=HTMLResponse)
def closer_presentation():
    """Page de présentation du programme closer."""
    from src.api.routes.crm_admin import _load_closer_content as _lcc
    _cfg = _lcc()
    _bonus_enabled = _cfg.get("bonus_enabled", False)
    _bonus_rate    = float(_cfg.get("bonus_rate", 0.04))
    _max_standard  = 2000
    _max_with_bonus = int(9000 * (0.18 + _bonus_rate))  # ex: 1980
    _display_max   = f"{_max_with_bonus:,}€".replace(",", " ") if _bonus_enabled else "2 000€"
    _display_sub   = f"par deal signé · dont {int(_bonus_rate*100)}% bonus top closer" if _bonus_enabled else "par deal signé"
    _html = """<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Devenez Closer — Présence IA</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0;min-height:100vh}
a{text-decoration:none}
.btn-primary{display:inline-block;background:linear-gradient(135deg,#6366f1,#8b5cf6);
  color:#fff;padding:15px 44px;border-radius:50px;font-weight:700;font-size:1rem;
  box-shadow:0 4px 24px #6366f140;transition:transform .15s,box-shadow .15s}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 32px #6366f160}
.btn-sec{display:inline-block;background:transparent;color:#9ca3af;padding:14px 32px;
  border-radius:50px;font-weight:600;font-size:.95rem;border:1px solid #2a2a4e;transition:border-color .15s,color .15s}
.btn-sec:hover{border-color:#6366f1;color:#fff}
</style>
</head><body>

<!-- HEADER -->
<header style="position:sticky;top:0;z-index:100;background:#fff;
  border-bottom:1px solid #e5e7eb;padding:0 24px">
  <div style="max-width:1000px;margin:0 auto;height:68px;display:flex;align-items:center;justify-content:space-between">
    <img src="/assets/logo.svg" alt="Présence IA" style="height:44px">
    <a href="/closer/recruit" class="btn-primary" style="padding:10px 28px;font-size:.9rem">Postuler →</a>
  </div>
</header>

<!-- HERO -->
<section style="padding:80px 20px 60px;text-align:center;position:relative;overflow:hidden">
  <div style="position:absolute;inset:0;background:radial-gradient(ellipse 60% 50% at 50% 0%,#6366f118,transparent);pointer-events:none"></div>
  <div style="max-width:760px;margin:0 auto;position:relative">
    <span style="display:inline-block;background:#6366f115;border:1px solid #6366f130;
      color:#a5b4fc;font-size:.8rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
      padding:6px 16px;border-radius:20px;margin-bottom:24px">Programme closer · 100% télétravail · Zéro prospection</span>
    <h1 style="font-size:clamp(2.2rem,5vw,3.4rem);color:#fff;line-height:1.15;margin-bottom:20px;
      font-weight:800;letter-spacing:-.02em">
      Gagnez <span style="background:linear-gradient(135deg,#6366f1,#a78bfa);-webkit-background-clip:text;
      -webkit-text-fill-color:transparent">18% de commission</span><br>sur chaque deal que vous signez
    </h1>
    <p style="color:#9ca3af;font-size:1.1rem;line-height:1.7;margin-bottom:40px;max-width:580px;margin-left:auto;margin-right:auto">
      Les prospects ont réservé leur créneau. Vous choisissez ceux que vous voulez prendre.<br>
      Zéro prospection. Votre seul job : closer.
    </p>
    <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
      <a href="/closer/recruit" class="btn-primary">Je postule maintenant →</a>
      <a href="#comment" class="btn-sec">Comment ça marche</a>
    </div>
    <!-- Chiffres -->
    <div style="display:flex;gap:16px;justify-content:center;flex-wrap:wrap;margin-top:52px">
      <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:16px 24px;text-align:center">
        <div style="font-size:1.6rem;font-weight:800;color:#a78bfa">18%</div>
        <div style="color:#6b7280;font-size:11px;margin-top:4px">de commission</div>
      </div>
      <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:16px 24px;text-align:center">
        <div style="font-size:1.6rem;font-weight:800;color:#2ecc71">jusqu'à {_display_max}</div>
        <div style="color:#6b7280;font-size:11px;margin-top:4px">{_display_sub}</div>
      </div>
      <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:16px 24px;text-align:center">
        <div style="font-size:1.6rem;font-weight:800;color:#f59e0b">100%</div>
        <div style="color:#6b7280;font-size:11px;margin-top:4px">à distance</div>
      </div>
      <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:16px 24px;text-align:center">
        <div style="font-size:1.6rem;font-weight:800;color:#527FB3">0</div>
        <div style="color:#6b7280;font-size:11px;margin-top:4px">prospection de votre côté</div>
      </div>
    </div>
  </div>
</section>

<!-- PRÉSENTATION ACTIVITÉ -->
<section style="padding:0 20px 64px">
  <div style="max-width:680px;margin:0 auto">
    <p style="color:#ccc;font-size:1rem;line-height:1.85;margin-bottom:20px">
      Présence IA aide les entreprises locales à apparaître dans les réponses des IA comme ChatGPT, Claude ou Gemini — là où leurs prospects prennent désormais leurs décisions.
    </p>
    <p style="color:#9ca3af;font-size:.95rem;line-height:1.85;margin-bottom:20px">
      Ces entreprises investissent pour être présentes sur Google. Pourtant, elles ne sont pas visibles là où les décisions se prennent vraiment. Résultat&nbsp;: des concurrents qui ne dépensent parfois rien en publicité passent devant elles dans les recommandations des IA. Le manque à gagner est énorme.
    </p>
    <p style="color:#9ca3af;font-size:.95rem;line-height:1.85;margin-bottom:20px">
      Nous générons des rendez-vous avec des prospects qui ont déjà pris conscience de ce décalage et veulent le corriger. L'offre est claire, les outils sont solides, avec trois options simples pour adapter la solution sans friction.
    </p>
    <p style="color:#9ca3af;font-size:.95rem;line-height:1.85;margin-bottom:20px">
      Ici, vous n'avez pas à convaincre de l'existence du problème&nbsp;: il est déjà visible. Vous apportez une réponse claire, directe et activable.
    </p>
    <p style="color:#ccc;font-size:1rem;line-height:1.85">
      Nous recherchons des closers capables de transformer cette évidence en décision — rapidement, proprement, sans forcer.
    </p>
  </div>
</section>

<!-- COMMENT ÇA MARCHE -->
<section id="comment" style="padding:72px 20px;max-width:900px;margin:0 auto">
  <h2 style="color:#fff;font-size:1.8rem;font-weight:700;text-align:center;margin-bottom:8px">Comment ça marche</h2>
  <p style="color:#9ca3af;text-align:center;margin-bottom:48px">3 étapes, pas de surprise</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px">
    <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:14px;padding:28px;position:relative">
      <div style="width:36px;height:36px;background:#6366f120;border:1px solid #6366f140;border-radius:50%;
        display:flex;align-items:center;justify-content:center;color:#a5b4fc;font-weight:700;margin-bottom:16px">1</div>
      <h3 style="color:#fff;font-size:1rem;font-weight:700;margin-bottom:8px">Vous choisissez vos créneaux</h3>
      <p style="color:#6b7280;font-size:.9rem;line-height:1.6">
        Des prospects qualifiés ont réservé un créneau. Vous accédez à la liste et choisissez librement ceux que vous voulez prendre. Aucune obligation de volume.
      </p>
    </div>
    <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:14px;padding:28px">
      <div style="width:36px;height:36px;background:#6366f120;border:1px solid #6366f140;border-radius:50%;
        display:flex;align-items:center;justify-content:center;color:#a5b4fc;font-weight:700;margin-bottom:16px">2</div>
      <h3 style="color:#fff;font-size:1rem;font-weight:700;margin-bottom:8px">Vous closez</h3>
      <p style="color:#6b7280;font-size:.9rem;line-height:1.6">
        Vous avez le script, les réponses aux objections, la fiche prospect. Vous faites le call et signez le deal.
      </p>
    </div>
    <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:14px;padding:28px">
      <div style="width:36px;height:36px;background:#6366f120;border:1px solid #6366f140;border-radius:50%;
        display:flex;align-items:center;justify-content:center;color:#a5b4fc;font-weight:700;margin-bottom:16px">3</div>
      <h3 style="color:#fff;font-size:1rem;font-weight:700;margin-bottom:8px">Vous êtes payé</h3>
      <p style="color:#6b7280;font-size:.9rem;line-height:1.6">
        Votre commission est calculée automatiquement sur chaque deal signé. Paiement immédiat sur demande selon le montant cumulé. Pas de plafond.
      </p>
    </div>
  </div>
</section>

<!-- CE QU'ON FOURNIT -->
<section style="padding:0 20px 72px;max-width:900px;margin:0 auto">
  <h2 style="color:#fff;font-size:1.8rem;font-weight:700;text-align:center;margin-bottom:48px">Ce qu'on vous fournit</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px">
    <div style="background:#0d0d1a;border:1px solid #1a1a2e;border-radius:10px;padding:20px;display:flex;gap:12px;align-items:flex-start">
      <span style="font-size:1.3rem">📋</span>
      <div><div style="color:#fff;font-weight:600;font-size:.95rem;margin-bottom:4px">Script de vente</div>
      <div style="color:#555;font-size:.85rem">Mot pour mot, testé et validé</div></div>
    </div>
    <div style="background:#0d0d1a;border:1px solid #1a1a2e;border-radius:10px;padding:20px;display:flex;gap:12px;align-items:flex-start">
      <span style="font-size:1.3rem">💬</span>
      <div><div style="color:#fff;font-weight:600;font-size:.95rem;margin-bottom:4px">Réponses aux objections</div>
      <div style="color:#555;font-size:.85rem">Pour chaque blocage courant</div></div>
    </div>
    <div style="background:#0d0d1a;border:1px solid #1a1a2e;border-radius:10px;padding:20px;display:flex;gap:12px;align-items:flex-start">
      <span style="font-size:1.3rem">📅</span>
      <div><div style="color:#fff;font-weight:600;font-size:.95rem;margin-bottom:4px">Créneaux à choisir</div>
      <div style="color:#555;font-size:.85rem">Prospects chauds, avec contexte complet</div></div>
    </div>
    <div style="background:#0d0d1a;border:1px solid #1a1a2e;border-radius:10px;padding:20px;display:flex;gap:12px;align-items:flex-start">
      <span style="font-size:1.3rem">📊</span>
      <div><div style="color:#fff;font-weight:600;font-size:.95rem;margin-bottom:4px">Portail de suivi</div>
      <div style="color:#555;font-size:.85rem">Vos créneaux, stats et commissions en temps réel</div></div>
    </div>
  </div>
</section>

<!-- CTA FINAL -->
<section style="padding:0 20px 80px">
  <div style="max-width:620px;margin:0 auto;background:linear-gradient(135deg,#1a1a2e,#16162a);
    border:1px solid #2a2a4e;border-radius:20px;padding:48px 40px;text-align:center">
    <h2 style="color:#fff;font-size:1.6rem;font-weight:700;margin-bottom:12px">Prêt à nous rejoindre ?</h2>
    <p style="color:#9ca3af;margin-bottom:32px;line-height:1.6">
      Candidature rapide. Pas de SIRET ni de statut requis à cette étape.<br>Réponse sous 48h.
    </p>
    <a href="/closer/recruit" class="btn-primary">Envoyer ma candidature →</a>
  </div>
</section>

</body></html>"""
    _html = _html.replace("{_display_max}", _display_max).replace("{_display_sub}", _display_sub)
    return HTMLResponse(_html)


# ─────────────────────────────────────────────────────────────────────────────
# Formulaire de candidature
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/closer/recruit", response_class=HTMLResponse)
def closer_recruit_form():
    return HTMLResponse("""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Postuler — Closer Présence IA</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}
.wrap{max-width:640px;margin:0 auto;padding:48px 20px}
h1{color:#fff;font-size:1.8rem;margin-bottom:8px}
.sub{color:#9ca3af;margin-bottom:32px}
.field{margin-bottom:20px}
label{display:block;color:#9ca3af;font-size:12px;font-weight:600;
      letter-spacing:.08em;text-transform:uppercase;margin-bottom:6px}
input,textarea,select{width:100%;background:#1a1a2e;border:1px solid #2a2a4e;
  border-radius:6px;padding:10px 12px;color:#e8e8f0;font-size:14px;outline:none}
input:focus,textarea:focus{border-color:#6366f1}
textarea{resize:vertical;min-height:120px}
.btn{width:100%;background:#6366f1;color:#fff;border:none;border-radius:8px;
     padding:14px;font-size:1rem;font-weight:700;cursor:pointer;margin-top:8px}
.btn:hover{background:#5254cc}
.section-title{color:#fff;font-size:14px;font-weight:600;margin:40px 0 18px;padding-top:20px;border-top:1px solid #2a2a4e;
               padding-bottom:8px;border-bottom:1px solid #2a2a4e}
.hint{color:#555;font-size:11px;margin-top:4px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
</style>
</head><body>
<header style="position:sticky;top:0;z-index:100;background:#fff;border-bottom:1px solid #e5e7eb;padding:0 24px">
  <div style="max-width:680px;margin:0 auto;height:68px;display:flex;align-items:center;justify-content:space-between">
    <img src="/assets/logo.svg" alt="Présence IA" style="height:44px">
    <a href="/closer" style="color:#6b7280;font-size:13px;font-weight:500">← Programme closer</a>
  </div>
</header>
<div class="wrap" style="padding-top:48px;padding-bottom:60px">
  <h1 style="margin-bottom:8px">Candidature Closer</h1>
  <p class="sub" style="margin-bottom:36px">Réponse et démarrage sous 48h.</p>

  <form id="form" method="post" action="/closer/recruit" enctype="multipart/form-data">

    <div class="section-title">Vos informations</div>

    <div class="row">
      <div class="field">
        <label>Prénom *</label>
        <input type="text" name="first_name" required placeholder="Prénom">
      </div>
      <div class="field">
        <label>Nom *</label>
        <input type="text" name="last_name" required placeholder="Nom">
      </div>
    </div>

    <div class="field">
      <label>Email *</label>
      <input type="email" name="email" required placeholder="votre@email.com">
    </div>

    <div class="field">
      <label>Téléphone</label>
      <input type="tel" name="phone" placeholder="Numéro de téléphone">
    </div>

    <div class="field">
      <label>Ville</label>
      <input type="text" name="city" placeholder="Ville">
    </div>

    <div class="row">
      <div class="field">
        <label>Pays</label>
        <input type="text" name="country" placeholder="FR">
      </div>
    </div>

    <div class="section-title">Votre présentation</div>

    <div class="field">
      <span id="media-req" style="display:none"></span>
      <p style="color:#d1d5db;font-size:.95rem;font-weight:400;line-height:1.7;margin-bottom:20px">Merci de vous présenter à travers un message vidéo ou audio de 2 à 3 minutes maximum en abordant les points suivants&nbsp;:</p><ul style="color:#d1d5db;font-size:.95rem;font-weight:400;line-height:1.8;margin:0 0 20px 24px;list-style:disc"><li>Votre expérience en closing (contexte, type d&rsquo;offres, résultats si possible)</li><li>Votre niveau de connaissance en webmarketing (SEO, IA, acquisition&hellip;)</li><li>Vos disponibilités (date de démarrage et nombre d&rsquo;heures par semaine)</li><li>Votre motivation pour rejoindre ce projet</li></ul>

      <!-- Option A : upload fichier -->
      <div style="background:#0d0d1a;border:1px solid #2a2a4e;border-radius:8px;padding:14px 16px;margin-bottom:10px">
        <div style="color:#9ca3af;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px">Uploader un fichier</div>
        <input type="file" name="audio_file" id="audio_file" accept="audio/*,video/*" style="padding:6px;width:100%">
        <p class="hint" style="margin-top:6px">Audio ou vidéo — .mp3, .m4a, .mp4, .mov — 50 Mo max</p>
      </div>

      <!-- Séparateur -->
      <div style="display:flex;align-items:center;gap:10px;margin:6px 0 10px">
        <div style="flex:1;height:1px;background:#2a2a4e"></div>
        <span style="color:#555;font-size:12px">ou</span>
        <div style="flex:1;height:1px;background:#2a2a4e"></div>
      </div>

      <!-- Option B : lien URL -->
      <div style="background:#0d0d1a;border:1px solid #2a2a4e;border-radius:8px;padding:14px 16px">
        <div style="color:#9ca3af;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px">Coller un lien</div>
        <input type="url" name="video_url" id="video_url" placeholder="YouTube, Loom, Drive, Dropbox…" style="width:100%">
        <p class="hint" style="margin-top:6px">Lien public ou partageable</p>
      </div>
    </div>

    <p id="media-error" style="color:#e94560;font-size:12px;margin-bottom:12px;display:none">
      Merci de fournir au moins un fichier ou un lien de présentation.
    </p>

    <button type="submit" class="btn">Envoyer ma candidature →</button>
  </form>
</div>

<script>
const form = document.getElementById('form');
const videoInput = document.getElementById('video_url');
const audioInput = document.getElementById('audio_file');

function updateMediaReq() {
  const hasVideo = videoInput.value.trim().length > 0;
  const hasAudio = audioInput.files && audioInput.files.length > 0;
  const req = document.getElementById('media-req');
  if (req) req.style.display = (hasVideo || hasAudio) ? 'none' : 'inline';
}
videoInput.addEventListener('input', updateMediaReq);
audioInput.addEventListener('change', updateMediaReq);

form.addEventListener('submit', async function(e) {
  e.preventDefault();
  const hasVideo = videoInput.value.trim().length > 0;
  const hasAudio = audioInput.files && audioInput.files.length > 0;
  const errEl = document.getElementById('media-error');
  if (!hasVideo && !hasAudio) {
    errEl.style.display = 'block';
    return;
  }
  errEl.style.display = 'none';

  const btn = this.querySelector('.btn');
  btn.textContent = 'Envoi en cours...';
  btn.disabled = true;

  const fd = new FormData(this);
  const r = await fetch('/closer/recruit', {method:'POST', body: fd});
  const data = await r.json();

  if (data.ok) {
    document.querySelector('.wrap').innerHTML = `
      <div style="text-align:center;padding:60px 0">
        <div style="font-size:3rem;margin-bottom:16px">✓</div>
        <h2 style="color:#fff;margin-bottom:12px">Candidature envoyée !</h2>
        <p style="color:#9ca3af">Nous vous répondrons sous 48h à l'adresse que vous avez fournie.</p>
        <a href="/closer" style="display:inline-block;margin-top:24px;color:#527FB3">← Retour</a>
      </div>`;
  } else {
    btn.textContent = 'Envoyer ma candidature →';
    btn.disabled = false;
    alert('Erreur : ' + (data.error || 'Veuillez réessayer'));
  }
});
</script>
</body></html>""")


# ─────────────────────────────────────────────────────────────────────────────
# Pages démo (aperçu admin sans données réelles)
# ─────────────────────────────────────────────────────────────────────────────

_DEMO_MEETINGS = [
    {
        "id":           "demo-1",
        "name":         "Jean-Marc Fabre",
        "city":         "Lyon",
        "profession":   "Plombier",
        "phone":        "06 12 34 56 78",
        "scheduled_str": "Demain 14h00",
        "status":       "scheduled",
        "deal_value":   None,
        "notes":        "A vu la landing 2 fois, a cliqué sur Calendly. Très intéressé par la visibilité IA.",
        "outcome":      "",
        "timeline":     [
            ("📧", "Envoyé", "08/03 09:14", "#6b7280"),
            ("👁", "Ouvert", "08/03 11:32", "#f59e0b"),
            ("🌐", "Landing visitée", "08/03 11:34", "#2ecc71"),
            ("📅", "Calendly cliqué", "08/03 11:37", "#6366f1"),
        ],
    },
    {
        "id":           "demo-2",
        "name":         "Sophie Renard",
        "city":         "Bordeaux",
        "profession":   "Coiffeuse",
        "phone":        "07 98 76 54 32",
        "scheduled_str": "15/03 10h30",
        "status":       "scheduled",
        "deal_value":   None,
        "notes":        "Déjà contactée par un concurrent. Sensible au prix.",
        "outcome":      "",
        "timeline":     [
            ("📧", "Envoyé", "07/03 14:20", "#6b7280"),
            ("👁", "Ouvert", "09/03 08:55", "#f59e0b"),
        ],
    },
    {
        "id":           "demo-3",
        "name":         "Marc Delorme",
        "city":         "Nantes",
        "profession":   "Électricien",
        "phone":        "06 55 44 33 22",
        "scheduled_str": "05/03 16h00",
        "status":       "completed",
        "deal_value":   497,
        "notes":        "Très motivé, a signé rapidement.",
        "outcome":      "Signé sans objection majeure. Client très chaud.",
        "timeline":     [
            ("📧", "Envoyé", "01/03 10:00", "#6b7280"),
            ("👁", "Ouvert", "01/03 12:15", "#f59e0b"),
            ("🌐", "Landing visitée", "01/03 12:18", "#2ecc71"),
            ("📅", "Calendly cliqué", "02/03 09:30", "#6366f1"),
        ],
    },
    {
        "id":           "demo-4",
        "name":         "Patricia Morin",
        "city":         "Toulouse",
        "profession":   "Esthéticienne",
        "phone":        "",
        "scheduled_str": "02/03 11h00",
        "status":       "no_show",
        "deal_value":   None,
        "notes":        "N'a pas décroché. SMS envoyé.",
        "outcome":      "",
        "timeline":     [
            ("📧", "Envoyé", "28/02 09:00", "#6b7280"),
            ("👁", "Ouvert", "28/02 18:40", "#f59e0b"),
        ],
    },
]


_DEMO_SLOTS = [
    {"id": "slot-1", "starts": "2026-03-14 09:00", "ends": "2026-03-14 09:20", "status": "booked",
     "prospect": "Jean-Marc Fabre", "city": "Lyon", "profession": "Plombier"},
    {"id": "slot-2", "starts": "2026-03-14 09:20", "ends": "2026-03-14 09:40", "status": "claimed_other",
     "closer": "Kévin R."},
    {"id": "slot-3", "starts": "2026-03-14 10:00", "ends": "2026-03-14 10:20", "status": "booked",
     "prospect": "Sophie Renard", "city": "Bordeaux", "profession": "Coiffeuse"},
    {"id": "slot-4", "starts": "2026-03-14 10:20", "ends": "2026-03-14 10:40", "status": "available"},
    {"id": "slot-5", "starts": "2026-03-14 11:00", "ends": "2026-03-14 11:20", "status": "claimed_me",
     "prospect": "Henri Dumont", "city": "Paris", "profession": "Électricien"},
    {"id": "slot-6", "starts": "2026-03-14 14:00", "ends": "2026-03-14 14:20", "status": "booked",
     "prospect": "Martine Colas", "city": "Nice", "profession": "Esthéticienne"},
    {"id": "slot-7", "starts": "2026-03-14 14:20", "ends": "2026-03-14 14:40", "status": "available"},
    {"id": "slot-8", "starts": "2026-03-15 09:00", "ends": "2026-03-15 09:20", "status": "booked",
     "prospect": "Pierre Lemaire", "city": "Marseille", "profession": "Carreleur"},
    {"id": "slot-9", "starts": "2026-03-15 10:00", "ends": "2026-03-15 10:20", "status": "available"},
]

_DEMO_LEADERBOARD = [
    {"rank": 1, "name": "Kévin R.",    "signed": 4, "commission": 2520.0, "bonus": False, "rate": 18},
    {"rank": 2, "name": "Marie Martin","signed": 2, "commission": 1260.0, "bonus": False, "rate": 18},
    {"rank": 3, "name": "David L.",    "signed": 1, "commission": 630.0,  "bonus": False, "rate": 18},
]


@router.get("/closer/demo/slots", response_class=HTMLResponse)
def closer_demo_slots(request: Request):
    """Page de sélection de créneaux — aperçu démo."""
    leaderboard_rows = ""
    for r in _DEMO_LEADERBOARD:
        is_me = r["name"] == "Marie Martin"
        rank_icon = "🥇" if r["rank"] == 1 else ("🥈" if r["rank"] == 2 else "#" + str(r["rank"]))
        leaderboard_rows += (
            f'<tr style="background:{"#6366f115" if is_me else "transparent"};'
            f'border-bottom:1px solid #1a1a2e">'
            f'<td style="padding:10px 14px;color:#9ca3af;'
            f'font-size:13px;font-weight:{"700" if is_me else "400"}">'
            f'{rank_icon}</td>'
            f'<td style="padding:10px 14px;color:#fff;font-size:13px;font-weight:{"700" if is_me else "400"}">'
            f'{r["name"]}{" (moi)" if is_me else ""}</td>'
            f'<td style="padding:10px 14px;color:#2ecc71;font-size:13px;text-align:right">{r["signed"]} deals</td>'
            f'</tr>'
        )

    # Grouper créneaux par jour
    from datetime import datetime as _dt
    days: dict = {}
    for s in _DEMO_SLOTS:
        day = _dt.strptime(s["starts"], "%Y-%m-%d %H:%M").strftime("%A %d/%m")
        days.setdefault(day, []).append(s)

    STATUS_INFO = {
        "available":    ("#2ecc71", "Disponible", False),
        "booked":       ("#8b5cf6", "Prospect inscrit", True),
        "claimed_me":   ("#6366f1", "Pris par moi", False),
        "claimed_other":("#374151", "Pris par un autre", False),
    }

    days_html = ""
    for day, slots in days.items():
        slots_html = ""
        for s in slots:
            color, label, can_claim = STATUS_INFO.get(s["status"], ("#555", s["status"], False))
            starts_fmt = s["starts"].split(" ")[1]
            ends_fmt   = s["ends"].split(" ")[1]
            prospect_info = ""
            if s.get("prospect"):
                prospect_info = (
                    f'<div style="color:#9ca3af;font-size:11px;margin-top:2px">'
                    f'{s["prospect"]} · {s.get("city","")} · {s.get("profession","")}</div>'
                )
            elif s.get("closer"):
                prospect_info = f'<div style="color:#555;font-size:11px;margin-top:2px">Closer : {s["closer"]}</div>'

            claim_btn = (
                f'<button onclick="claimSlot(\'{s["id"]}\')" '
                f'style="margin-top:8px;padding:5px 12px;background:#8b5cf6;border:none;'
                f'border-radius:4px;color:#fff;font-size:11px;font-weight:600;cursor:pointer">Prendre ce créneau</button>'
            ) if can_claim else ""

            slots_html += (
                f'<div style="background:#1a1a2e;border:1px solid {color}40;border-radius:8px;'
                f'padding:12px 16px;margin-bottom:8px">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
                f'  <div>'
                f'    <span style="color:#fff;font-weight:600;font-size:13px">{starts_fmt} – {ends_fmt}</span>'
                f'    {prospect_info}'
                f'    {claim_btn}'
                f'  </div>'
                f'  <span style="background:{color}20;color:{color};font-size:10px;font-weight:600;'
                f'  padding:2px 7px;border-radius:10px;flex-shrink:0">{label}</span>'
                f'</div>'
                f'</div>'
            )
        days_html += (
            f'<div style="margin-bottom:24px">'
            f'<h3 style="color:#9ca3af;font-size:11px;font-weight:600;text-transform:uppercase;'
            f'letter-spacing:.08em;margin-bottom:12px">{day}</h3>'
            f'{slots_html}</div>'
        )

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Créneaux disponibles — Aperçu</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}</style>
</head><body>
<div style="background:#1a1a2e;border-bottom:1px solid #2a2a4e;padding:14px 24px;
            display:flex;align-items:center;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:10px">
    <img src="/assets/logo.svg" alt="Présence IA" style="height:24px">
    <span style="color:#9ca3af;font-size:11px">Portail Closer</span>
  </div>
  <a href="/closer/demo" style="color:#527FB3;font-size:12px;text-decoration:none">← Mon portail</a>
</div>
<div style="max-width:820px;margin:0 auto;padding:28px 20px">

<div style="background:#6366f115;border:1px solid #6366f130;border-radius:6px;
  padding:10px 14px;margin-bottom:20px;font-size:12px;color:#a5b4fc">
  ⚠️ Aperçu admin — données fictives.
</div>

<!-- Légende -->
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px">
  <div style="display:flex;align-items:center;gap:6px">
    <span style="width:10px;height:10px;background:#2ecc71;border-radius:50%;display:inline-block"></span>
    <span style="color:#9ca3af;font-size:11px">Disponible</span>
  </div>
  <div style="display:flex;align-items:center;gap:6px">
    <span style="width:10px;height:10px;background:#8b5cf6;border-radius:50%;display:inline-block"></span>
    <span style="color:#9ca3af;font-size:11px">Prospect inscrit</span>
  </div>
  <div style="display:flex;align-items:center;gap:6px">
    <span style="width:10px;height:10px;background:#6366f1;border-radius:50%;display:inline-block"></span>
    <span style="color:#9ca3af;font-size:11px">Pris par moi</span>
  </div>
  <div style="display:flex;align-items:center;gap:6px">
    <span style="width:10px;height:10px;background:#374151;border-radius:50%;display:inline-block"></span>
    <span style="color:#9ca3af;font-size:11px">Pris par un autre</span>
  </div>
</div>

<!-- Créneaux -->
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:24px">
  <div>
    <h2 style="color:#fff;font-size:15px;font-weight:700;margin-bottom:16px">Créneaux disponibles</h2>
    {days_html}
  </div>
  <div>
    <h2 style="color:#fff;font-size:15px;font-weight:700;margin-bottom:16px">Classement du mois</h2>
    <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden;margin-bottom:12px">
    <table style="width:100%;border-collapse:collapse">
    <thead><tr>
      <th style="padding:8px 14px;text-align:left;color:#555;font-size:10px;font-weight:600;
          letter-spacing:.08em;border-bottom:1px solid #2a2a4e"></th>
      <th style="padding:8px 14px;text-align:left;color:#555;font-size:10px;font-weight:600;
          letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Closer</th>
      <th style="padding:8px 14px;text-align:right;color:#555;font-size:10px;font-weight:600;
          letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Deals ce mois</th>
    </tr></thead>
    <tbody>{leaderboard_rows}</tbody>
    </table></div>
    <p style="color:#555;font-size:11px;line-height:1.5">
      Commission versée le 10 du mois suivant la signature.
    </p>
  </div>
</div>

</div>
<script>
function claimSlot(id){{
  alert('Démo uniquement — sur la vraie page, ce créneau serait réservé à votre nom.');
}}
</script>
</body></html>""")


@router.get("/closer/demo", response_class=HTMLResponse)
def closer_portal_demo(request: Request):
    """Portail closer — aperçu avec données de démonstration."""
    content  = _load_portal_content()
    commission_rate = 0.18
    name = "Marie Martin"

    stats = {
        "scheduled": 2, "completed": 1, "no_show": 1,
        "earned": 3500 * commission_rate, "pending": 0.0,
    }
    conv_rate = "33%"

    stats_html = "".join(
        f'<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;'
        f'padding:14px 16px;text-align:center">'
        f'<div style="font-size:1.6rem;font-weight:700;color:{c}">{v}</div>'
        f'<div style="color:#9ca3af;font-size:11px;margin-top:3px">{l}</div>'
        f'</div>'
        for v, l, c in [
            (stats["scheduled"],          "RDV à venir",      "#6366f1"),
            (stats["completed"],          "Signés",           "#2ecc71"),
            (stats["no_show"],            "No-show",          "#e94560"),
            (conv_rate,                   "Taux conversion",  "#e9a020"),
            (f'{stats["earned"]:.0f}€',   "Gagné",            "#527FB3"),
            (f'{stats["pending"]:.0f}€',  "En attente",       "#9ca3af"),
        ]
    )

    upcoming = [m for m in _DEMO_MEETINGS if m["status"] == "scheduled"]
    past     = [m for m in _DEMO_MEETINGS if m["status"] != "scheduled"]

    def _upcoming_card(m):
        phone_btn = (
            f'<a href="tel:{m["phone"]}" style="display:inline-block;margin-top:8px;'
            f'padding:5px 12px;background:#6366f120;border:1px solid #6366f140;'
            f'border-radius:4px;color:#6366f1;font-size:11px;text-decoration:none">📞 Appeler</a>'
        ) if m["phone"] else ""
        return (
            f'<div style="background:#1a1a2e;border:1px solid #6366f140;border-radius:10px;padding:16px;margin-bottom:12px">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
            f'  <div>'
            f'    <div style="color:#fff;font-size:14px;font-weight:600">{m["name"]}</div>'
            f'    <div style="color:#6b7280;font-size:11px;margin-top:2px">{m["city"]} · {m["profession"]}</div>'
            f'    {phone_btn}'
            f'  </div>'
            f'  <div style="text-align:right">'
            f'    <div style="color:#6366f1;font-size:13px;font-weight:600">{m["scheduled_str"]}</div>'
            f'    <a href="/closer/demo/meeting/{m["id"]}" '
            f'    style="display:inline-block;margin-top:6px;color:#527FB3;font-size:11px;text-decoration:none">'
            f'    Fiche RDV →</a>'
            f'  </div>'
            f'</div>'
            f'</div>'
        )

    upcoming_html = "".join(_upcoming_card(m) for m in upcoming)

    past_rows = "".join(
        f'<tr style="border-bottom:1px solid #1a1a2e;cursor:pointer" '
        f'onclick="window.location=\'/closer/demo/meeting/{m["id"]}\'">'
        f'<td style="padding:10px 16px;color:#fff;font-size:12px">'
        f'{m["name"]}<div style="color:#6b7280;font-size:10px">{m["city"]}</div></td>'
        f'<td style="padding:10px 16px;color:#9ca3af;font-size:11px">{m["scheduled_str"]}</td>'
        f'<td style="padding:10px 16px">{_meeting_badge(m["status"], m.get("scheduled_at"))}</td>'
        f'<td style="padding:10px 16px;color:{"#2ecc71" if m["deal_value"] else "#555"};font-size:12px">'
        f'{"{}€".format(int(m["deal_value"])) if m["deal_value"] else "—"}</td>'
        f'<td style="padding:10px 16px;color:{"#2ecc71" if m["deal_value"] else "#555"};font-size:11px">'
        f'{"{}€".format(int(m["deal_value"]*commission_rate)) if m["deal_value"] else "—"}</td>'
        f'</tr>'
        for m in past
    )

    comm_info_html = "".join(
        f'<p style="margin-bottom:8px">{ln}</p>'
        for ln in content.get("commission_info", "").split("\n") if ln.strip()
    )

    def _pre(text):
        return "<br>".join(
            f'<span style="color:{"#6366f1" if ln.startswith(tuple("123456789")) else "#ccc"}">{ln}</span>'
            if ln.strip() else '<span style="display:block;height:8px"></span>'
            for ln in (text or "").split("\n")
        )

    panel_rdv = f"""
<div style="background:#6366f115;border:1px solid #6366f130;border-radius:6px;padding:10px 14px;margin-bottom:20px;font-size:12px;color:#a5b4fc">
  ⚠️ Aperçu admin — données fictives. La vraie page s'affiche sur <code>/closer/{{token}}</code>
</div>
<h3 style="color:#fff;font-size:14px;margin-bottom:16px">RDV à venir ({len(upcoming)})</h3>
{upcoming_html}
<h3 style="color:#9ca3af;font-size:12px;letter-spacing:.06em;text-transform:uppercase;margin:24px 0 12px">Historique</h3>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden">
<table style="width:100%;border-collapse:collapse">
<thead><tr>
  <th style="padding:8px 16px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #2a2a4e">Prospect</th>
  <th style="padding:8px 16px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #2a2a4e">Date</th>
  <th style="padding:8px 16px;border-bottom:1px solid #2a2a4e;color:#555;font-size:10px">Statut</th>
  <th style="padding:8px 16px;border-bottom:1px solid #2a2a4e;color:#555;font-size:10px">Deal</th>
  <th style="padding:8px 16px;border-bottom:1px solid #2a2a4e;color:#555;font-size:10px">Commission</th>
</tr></thead>
<tbody>{past_rows}</tbody></table></div>"""

    _bonus_on   = content.get("bonus_enabled", False)
    _bonus_rate = float(content.get("bonus_rate", 0.04))
    _bonus_block = (
        f'<div style="background:#6366f110;border:1px solid #6366f140;border-radius:8px;padding:14px 16px;margin-top:12px">'
        f'<p style="color:#a5b4fc;font-size:11px;font-weight:700;margin-bottom:4px">BONUS MENSUEL ACTIF</p>'
        f'<p style="color:#ccc;font-size:12px;line-height:1.6">'
        f'Le top closer du mois reçoit +{int(_bonus_rate*100)}% rétroactif sur tous ses deals.<br>'
        f'Taux effectif : <strong style="color:#a5b4fc">{int((0.18+_bonus_rate)*100)}%</strong> · '
        f'Max sur Domination : <strong style="color:#2ecc71">{int(9000*(0.18+_bonus_rate))}€</strong>'
        f'</p></div>'
    ) if _bonus_on else ""

    panel_commissions = f"""
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px">
  <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#2ecc71">{stats["earned"]:.0f}€</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Gagné (tous temps)</div>
  </div>
  <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#6366f1">{stats["pending"]:.0f}€</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">En attente</div>
  </div>
  <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#e9a020">{commission_rate*100:.0f}%</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Taux de commission</div>
  </div>
</div>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px">
<p style="color:#9ca3af;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Détail</p>
<div style="color:#ccc;font-size:13px;line-height:1.8">{comm_info_html}</div>
</div>
{_bonus_block}"""

    def _resource_block(title, text, color="#6366f1"):
        return (
            f'<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px">'
            f'<p style="color:{color};font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">{title}</p>'
            f'<div style="color:#ccc;font-size:13px;line-height:1.8">{_pre(text)}</div>'
            f'</div>'
        )

    panel_offre      = _resource_block(content.get("offer_title","L'offre") + f' — {content.get("offer_price","")}', content.get("offer_pitch",""), "#2ecc71")
    panel_script     = _resource_block("Script de vente", content.get("pitch_script",""), "#6366f1")
    panel_objections = _resource_block("Réponses aux objections", content.get("objections",""), "#e9a020")

    # Leaderboard démo
    leaderboard_rows_demo = ""
    for r in _DEMO_LEADERBOARD:
        is_me = r["name"] == "Marie Martin"
    # panel_rdv avec bouton Agenda
    panel_rdv = (
        f'<div style="margin-bottom:20px">'
        f'<a href="/closer/demo/slots" style="display:inline-block;background:#8b5cf6;'
        f'color:#fff;text-decoration:none;padding:9px 18px;border-radius:6px;font-size:12px;font-weight:600">'
        f'📅 Agenda — voir les créneaux disponibles →</a>'
        f'</div>'
    ) + panel_rdv

    TABS = [("rdv","Mes RDV"),("commissions","Commissions"),("offre","L'offre"),("script","Script"),("objections","Objections")]

    def _tab_btn(slug, label, active="rdv"):
        a = slug == active
        return (f'<button onclick="switchTab(\'{slug}\')" id="tab-{slug}" '
                f'style="padding:8px 16px;border:none;border-radius:6px;cursor:pointer;font-size:12px;'
                f'font-weight:{"700" if a else "400"};background:{"#6366f1" if a else "#1a1a2e"};'
                f'color:{"#fff" if a else "#9ca3af"};border:1px solid {"#6366f1" if a else "#2a2a4e"}">{label}</button>')

    tabs_html = f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px">{"".join(_tab_btn(s,l) for s,l in TABS)}</div>'

    panels = {"rdv": panel_rdv, "commissions": panel_commissions,
              "offre": panel_offre, "script": panel_script, "objections": panel_objections}
    panels_js = {k: v.replace("`","\\`").replace("${","\\${") for k,v in panels.items()}

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Portail Closer — Aperçu</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}table{{width:100%;border-collapse:collapse}}tr:hover{{background:#111127}}</style>
</head><body>
<div style="background:#1a1a2e;border-bottom:1px solid #2a2a4e;padding:14px 24px;display:flex;align-items:center;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:10px">
    <img src="/assets/logo.svg" alt="Présence IA" style="height:26px">
    <span style="color:#9ca3af;font-size:11px">Portail Closer</span>
  </div>
  <span style="color:#fff;font-weight:600;font-size:14px">{name}</span>
</div>
<div style="max-width:920px;margin:0 auto;padding:28px 20px">
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:28px">{stats_html}</div>
{tabs_html}
<div id="tab-content">{panel_rdv}</div>
</div>
<script>
const _panels={{{",".join(f'"{k}":`{v}`' for k,v in panels_js.items())}}};
function switchTab(slug){{
  document.getElementById('tab-content').innerHTML=_panels[slug]||'';
  document.querySelectorAll('[id^="tab-"]').forEach(b=>{{
    const a=b.id==='tab-'+slug;
    b.style.background=a?'#6366f1':'#1a1a2e';b.style.color=a?'#fff':'#9ca3af';
    b.style.fontWeight=a?'700':'400';b.style.borderColor=a?'#6366f1':'#2a2a4e';
  }});
}}
</script>
</body></html>""")


@router.get("/closer/demo/meeting/{demo_id}", response_class=HTMLResponse)
def closer_meeting_demo(demo_id: str, request: Request):
    """Fiche RDV — aperçu avec données de démonstration."""
    content  = _load_portal_content()
    meeting  = next((m for m in _DEMO_MEETINGS if m["id"] == demo_id), _DEMO_MEETINGS[0])

    rdv_guide_lines = "".join(
        f'<div style="padding:6px 0;border-bottom:1px solid #1a1a2e;color:{"#6366f1" if ln.startswith(("AVANT","PENDANT","FIN","1.","2.","3.","4.","5.","6.","7.","8.","9.")) else "#ccc"};font-size:12px;line-height:1.5">{ln}</div>'
        if ln.strip() else '<div style="height:6px"></div>'
        for ln in content.get("rdv_guide", "").split("\n")
    )

    timeline_html = "".join(
        f'<li style="color:{color};font-size:12px">{icon} {label} — {date}</li>'
        for icon, label, date, color in meeting["timeline"]
    )

    phone_btn = (
        f'<a href="tel:{meeting["phone"]}" style="display:inline-block;margin-top:6px;padding:6px 14px;'
        f'background:#6366f120;border:1px solid #6366f140;border-radius:4px;'
        f'color:#6366f1;font-size:12px;text-decoration:none">📞 {meeting["phone"]}</a>'
    ) if meeting["phone"] else ""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fiche RDV — {meeting["name"]}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}.card{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;margin-bottom:16px}}.sec{{color:#9ca3af;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px}}</style>
</head><body>
<div style="background:#1a1a2e;border-bottom:1px solid #2a2a4e;padding:14px 24px;display:flex;align-items:center;justify-content:space-between">
  <img src="/assets/logo.svg" alt="Présence IA" style="height:24px">
  <a href="/closer/demo" style="color:#527FB3;font-size:12px;text-decoration:none">← Mes RDV</a>
</div>
<div style="max-width:780px;margin:0 auto;padding:28px 20px">

<div style="background:#6366f115;border:1px solid #6366f130;border-radius:6px;padding:10px 14px;margin-bottom:20px;font-size:12px;color:#a5b4fc">
  ⚠️ Aperçu admin — données fictives
</div>

<div style="margin-bottom:20px">
  <h1 style="color:#fff;font-size:20px;margin-bottom:4px">{meeting["name"]}</h1>
  <p style="color:#9ca3af;font-size:13px">{meeting["city"]} · {meeting["profession"]}</p>
  {phone_btn}
</div>

<div class="card" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:16px;text-align:center">
  <div>
    <div style="color:#f59e0b;font-size:1.2rem;font-weight:700">{meeting["scheduled_str"]}</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Date RDV</div>
  </div>
  <div>
    {_meeting_badge(meeting["status"], meeting.get("scheduled_at"))}
    <div style="color:#9ca3af;font-size:11px;margin-top:6px">Statut</div>
  </div>
  <div>
    <div style="color:{"#2ecc71" if meeting["deal_value"] else "#555"};font-size:1.2rem;font-weight:700">
      {"{}€".format(int(meeting["deal_value"])) if meeting["deal_value"] else "—"}
    </div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Deal</div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
<div class="card">
  <p class="sec">Comportement du prospect</p>
  <ul style="list-style:none;display:flex;flex-direction:column;gap:4px">{timeline_html}</ul>
</div>
<div class="card">
  <p class="sec">Notes</p>
  <p style="color:#ccc;font-size:13px;line-height:1.5">{meeting["notes"] or "Aucune note"}</p>
  {f'<p style="color:#9ca3af;font-size:12px;margin-top:8px">{meeting["outcome"]}</p>' if meeting["outcome"] else ""}
</div>
</div>

<div class="card">
  <p class="sec">Fiche RDV — Aide-mémoire</p>
  <div>{rdv_guide_lines or "<p style='color:#555;font-size:12px'>Guide non configuré — Admin → Contenu portail</p>"}</div>
</div>

</div></body></html>""")


@router.post("/closer/recruit")
async def closer_recruit_submit(request: Request):
    """Traite la soumission de candidature."""
    try:
        from pathlib import Path
        form = await request.form()

        # Traitement fichier audio
        audio_url = None
        audio_file = form.get("audio_file")
        if audio_file and hasattr(audio_file, "filename") and audio_file.filename:
            ext = Path(audio_file.filename).suffix or ".mp3"
            fn  = f"{uuid.uuid4().hex}{ext}"
            out_dir = Path(__file__).parent.parent.parent.parent / "dist" / "closer-audio"
            out_dir.mkdir(parents=True, exist_ok=True)
            content = await audio_file.read()
            if len(content) <= 5 * 1024 * 1024:  # 5 Mo max
                (out_dir / fn).write_bytes(content)
                audio_url = f"/dist/closer-audio/{fn}"

        video_url = form.get("video_url", "").strip() or None
        if not video_url and not audio_url:
            return JSONResponse(
                {"ok": False, "error": "Merci de fournir au moins une vidéo ou un message audio."},
                status_code=400,
            )

        # Date de naissance
        from datetime import date as _date
        dob_raw = form.get("date_of_birth", "").strip()
        date_of_birth = None
        if dob_raw:
            try:
                date_of_birth = _date.fromisoformat(dob_raw)
            except ValueError:
                pass

        data = {
            "project_id":    PROJECT_ID,
            "first_name":    form.get("first_name", "").strip() or None,
            "last_name":     form.get("last_name", "").strip() or None,
            "email":         form.get("email", "").strip() or None,
            "phone":         form.get("phone", "").strip() or None,
            "city":          form.get("city", "").strip() or None,
            "country":       form.get("country", "FR").strip() or "FR",
            "message":       form.get("message", "").strip() or None,
            "video_url":     video_url,
            "audio_url":     audio_url,
            "meta":         {"date_of_birth": str(date_of_birth) if date_of_birth else None},
        }

        from marketing_module.database import SessionLocal as MktSession, db_create_application
        from marketing_module.models import CloserApplicationDB
        with MktSession() as mdb:
            app = db_create_application(mdb, data)
            total = mdb.query(CloserApplicationDB).filter_by(project_id=PROJECT_ID).count()

        # SMS de notification
        try:
            import os as _os, requests as _req
            _brevo_key = _os.getenv("BREVO_API_KEY", "")
            if _brevo_key:
                _prenom = data.get("first_name") or ""
                _nom    = data.get("last_name") or ""
                _name   = f"{_prenom} {_nom}".strip() or "Anonyme"
                _token  = _os.getenv("ADMIN_TOKEN", "")
                _msg = (
                    f"Nouvelle candidature closer recue - {total} au total\n"
                    f"Candidat : {_name}\n"
                    f"https://presence-ia.com/admin/closers-hub?token={_token}"
                )
                _req.post(
                    "https://api.brevo.com/v3/transactionalSMS/sms",
                    headers={"api-key": _brevo_key, "Content-Type": "application/json"},
                    json={"sender": "PresenceIA", "recipient": "+393514459617",
                          "content": _msg, "type": "transactional"},
                    timeout=8,
                )
        except Exception:
            pass

        # Email de confirmation au candidat
        try:
            import os as _oc, requests as _rq
            _bkey = _oc.getenv("BREVO_API_KEY", "")
            _prenom = data.get("first_name") or ""
            _email_c = data.get("email") or ""
            _name_c = f"{_prenom} {data.get('last_name') or ''}".strip() or "Closer"
            if _bkey and _email_c:
                _rq.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": _bkey, "Content-Type": "application/json"},
                    json={
                        "sender": {"name": "Présence IA", "email": "contact@presence-ia.com"},
                        "to": [{"email": _email_c, "name": _name_c}],
                        "subject": "Candidature bien reçue — Présence IA",
                        "htmlContent": f"""<p>Bonjour {_prenom or _name_c},</p>
                        <p>Nous avons bien reçu votre candidature au programme Closer Présence IA.</p>
                        <p>Nous l'étudions avec attention et vous répondrons <strong>sous 48h</strong>.</p>
                        <p>En attendant, vous pouvez consulter la page du programme : 
                        <a href="https://presence-ia.com/closer">presence-ia.com/closer</a></p>
                        <p style="color:#999;font-size:12px">— L'équipe Présence IA</p>""",
                    },
                    timeout=8,
                )
        except Exception:
            pass
        return JSONResponse({"ok": True, "id": app.id})

    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ─────────────────────────────────────────────────────────────────────────────
# Portail closer (authentifié par token)
# ─────────────────────────────────────────────────────────────────────────────

def _get_closer_by_token(token: str):
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import CloserDB
        with MktSession() as mdb:
            return mdb.query(CloserDB).filter_by(token=token).first()
    except Exception:
        return None


def _load_portal_content() -> dict:
    """Charge le contenu éditable du portail (script, offre, objections, etc.)."""
    from pathlib import Path as _P
    import json as _j
    f = _P(__file__).parent.parent.parent.parent / "data" / "closer_content.json"
    try:
        if f.exists():
            return _j.loads(f.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {
        "offer_title": "Présence IA — Visibilité locale sur les IA",
        "offer_price": "497 €/an",
        "offer_pitch": "Aide les artisans et PME locales à apparaître sur ChatGPT et les IA.",
        "pitch_script": "Script non encore configuré — rendez-vous dans l'admin → Contenu portail.",
        "objections": "Objections non encore configurées.",
        "rdv_guide": "Guide RDV non encore configuré.",
        "commission_info": "18% du deal · jusqu'à 1 620€ par deal signé (offre Domination IA Locale).",
        "bonus_enabled": False, "bonus_rate": 0.04, "bonus_top_n": 1,
    }


@router.get("/closer/{token}", response_class=HTMLResponse)
def closer_portal(token: str, request: Request):
    """Portail closer — RDV, stats, commissions, ressources."""
    preview = request.query_params.get("preview")
    tab     = request.query_params.get("tab", "rdv")

    closer = _get_closer_by_token(token)
    if not closer and not preview:
        return HTMLResponse("<p style='font-family:sans-serif;padding:40px;color:#666'>Lien invalide.</p>",
                            status_code=404)

    name         = getattr(closer, "name", "Closer") if closer else "Aperçu"
    commission_rate = getattr(closer, "commission_rate", 0.18) if closer else 0.18
    content      = _load_portal_content()

    # ── Données RDV ──────────────────────────────────────────────────────────
    meetings_upcoming = []
    meetings_past     = []
    stats = {"total": 0, "completed": 0, "no_show": 0, "scheduled": 0,
             "earned": 0.0, "pending": 0.0}
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    stats_month = {"signed": 0, "earned": 0.0}

    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import MeetingDB, MeetingStatus
        from ...database import SessionLocal
        from ...models import V3ProspectDB

        with MktSession() as mdb:
            q = mdb.query(MeetingDB).filter_by(project_id=PROJECT_ID)
            if closer:
                q = q.filter_by(closer_id=closer.id)
            mtgs = q.order_by(MeetingDB.scheduled_at.asc()).limit(100).all()

            with SessionLocal() as db:
                for m in mtgs:
                    prospect = db.query(V3ProspectDB).filter_by(token=m.prospect_id).first()
                    entry = {
                        "id":           m.id,
                        "name":         prospect.name if prospect else "—",
                        "city":         prospect.city if prospect else "—",
                        "profession":   prospect.profession if prospect else "—",
                        "phone":        prospect.phone if prospect else "",
                        "scheduled_at": m.scheduled_at,
                        "scheduled_str": m.scheduled_at.strftime("%d/%m/%y %H:%M") if m.scheduled_at else "—",
                        "status":       m.status,
                        "deal_value":   m.deal_value,
                        "notes":        m.notes or "",
                        "outcome":      getattr(m, "outcome", "") or "",
                    }
                    stats["total"] += 1
                    if m.status == MeetingStatus.completed:
                        stats["completed"] += 1
                        if m.deal_value:
                            stats["earned"] += m.deal_value * commission_rate
                            if m.scheduled_at and m.scheduled_at.month == now.month and m.scheduled_at.year == now.year:
                                stats_month["signed"] += 1
                                stats_month["earned"] += m.deal_value * commission_rate
                    elif m.status == MeetingStatus.no_show:
                        stats["no_show"] += 1
                    elif m.status == MeetingStatus.scheduled:
                        stats["scheduled"] += 1
                        if m.deal_value:
                            stats["pending"] += m.deal_value * commission_rate
                    # Séparer à venir / passé
                    if m.status == MeetingStatus.scheduled and m.scheduled_at and m.scheduled_at.replace(tzinfo=timezone.utc) >= now:
                        meetings_upcoming.append(entry)
                    else:
                        meetings_past.append(entry)
    except Exception:
        pass

    meetings_past.sort(key=lambda x: x["scheduled_at"] or datetime.min, reverse=True)
    conv_rate = f"{stats['completed']/stats['total']*100:.0f}%" if stats["total"] else "—"

    # ── Commissions versé / à verser ─────────────────────────────────────────
    comm_verse    = 0.0
    comm_a_verser = stats["earned"]
    try:
        from marketing_module.database import SessionLocal as MktSession3
        from marketing_module.models import CommissionDB
        with MktSession3() as mdb3:
            q_c = mdb3.query(CommissionDB).filter_by(project_id=PROJECT_ID)
            if closer:
                q_c = q_c.filter_by(closer_id=closer.id)
            all_comms = q_c.all()
            if all_comms:
                comm_verse    = sum(c.amount or 0 for c in all_comms if getattr(c, "status", "") == "paid")
                comm_a_verser = sum(c.amount or 0 for c in all_comms if getattr(c, "status", "") != "paid")
    except Exception:
        pass

    # ── Stats bar ─────────────────────────────────────────────────────────────
    stats_html = "".join(
        f'<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;'
        f'padding:14px 16px;text-align:center">'
        f'<div style="font-size:1.6rem;font-weight:700;color:{c}">{v}</div>'
        f'<div style="color:#9ca3af;font-size:11px;margin-top:3px">{l}</div>'
        f'</div>'
        for v, l, c in [
            (stats["scheduled"],          "RDV à venir",      "#6366f1"),
            (stats["completed"],          "Signés",           "#2ecc71"),
            (stats["no_show"],            "No-show",          "#e94560"),
            (conv_rate,                   "Taux conversion",  "#e9a020"),
            (f'{stats["earned"]:.0f}€',   "Gagné",            "#527FB3"),
            (f'{stats["pending"]:.0f}€',  "En attente",       "#9ca3af"),
        ]
    )

    # ── RDV à venir ──────────────────────────────────────────────────────────
    def _upcoming_card(m):
        phone_btn = (
            f'<a href="tel:{m["phone"]}" style="display:inline-block;margin-top:8px;'
            f'padding:5px 12px;background:#6366f120;border:1px solid #6366f140;'
            f'border-radius:4px;color:#6366f1;font-size:11px;text-decoration:none">📞 Appeler</a>'
        ) if m["phone"] else ""
        return (
            f'<div style="background:#1a1a2e;border:1px solid #6366f140;border-radius:10px;'
            f'padding:16px;margin-bottom:12px">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
            f'  <div>'
            f'    <div style="color:#fff;font-size:14px;font-weight:600">{m["name"]}</div>'
            f'    <div style="color:#6b7280;font-size:11px;margin-top:2px">{m["city"]} · {m["profession"]}</div>'
            f'    {phone_btn}'
            f'  </div>'
            f'  <div style="text-align:right">'
            f'    <div style="color:#6366f1;font-size:13px;font-weight:600">{m["scheduled_str"]}</div>'
            f'    <a href="/closer/{token}/meeting/{m["id"]}" '
            f'    style="display:inline-block;margin-top:6px;color:#527FB3;font-size:11px;text-decoration:none">'
            f'    Fiche RDV →</a>'
            f'  </div>'
            f'</div>'
            f'</div>'
        )

    upcoming_html = (
        "".join(_upcoming_card(m) for m in meetings_upcoming)
        or '<p style="color:#555;font-size:13px;padding:20px 0">Aucun RDV à venir</p>'
    )

    # ── Historique ────────────────────────────────────────────────────────────
    past_rows = "".join(
        f'<tr style="border-bottom:1px solid #1a1a2e;cursor:pointer" '
        f'onclick="window.location=\'/closer/{token}/meeting/{m["id"]}\'">'
        f'<td style="padding:10px 16px;color:#fff;font-size:12px">'
        f'{m["name"]}<div style="color:#6b7280;font-size:10px">{m["city"]}</div></td>'
        f'<td style="padding:10px 16px;color:#9ca3af;font-size:11px">{m["scheduled_str"]}</td>'
        f'<td style="padding:10px 16px">{_meeting_badge(m["status"], m.get("scheduled_at"))}</td>'
        f'<td style="padding:10px 16px;color:{"#2ecc71" if m["deal_value"] else "#555"};font-size:12px">'
        f'{"{}€".format(int(m["deal_value"])) if m["deal_value"] else "—"}</td>'
        f'<td style="padding:10px 16px;color:{"#2ecc71" if m["deal_value"] else "#555"};font-size:11px">'
        f'{"{}€".format(int(m["deal_value"]*commission_rate)) if m["deal_value"] else "—"}</td>'
        f'</tr>'
        for m in meetings_past
    ) or '<tr><td colspan="5" style="padding:30px;text-align:center;color:#555">Aucun historique</td></tr>'

    # ── Commissions ───────────────────────────────────────────────────────────
    comm_info_html = "".join(
        f'<p style="margin-bottom:8px">{line}</p>'
        for line in content.get("commission_info", "").split("\n") if line.strip()
    )

    # ── Leaderboard réel ──────────────────────────────────────────────────────
    leaderboard_rows_real = ""
    my_rank = "—"
    try:
        from marketing_module.database import SessionLocal as MktSession2, db_monthly_leaderboard
        with MktSession2() as mdb2:
            lb = db_monthly_leaderboard(mdb2, PROJECT_ID)
        for r in lb:
            is_me = closer and r["closer_id"] == closer.id
            if is_me:
                my_rank = str(r["rank"])
            bonus_badge = ('<span style="background:#2ecc7120;color:#2ecc71;font-size:9px;'
                           'font-weight:600;padding:1px 5px;border-radius:8px;margin-left:4px">+5%</span>'
                           ) if r["bonus"] else ""
            rank_icon = "🥇" if r["rank"] == 1 else ("🥈" if r["rank"] == 2 else "#" + str(r["rank"]))
            leaderboard_rows_real += (
                f'<tr style="background:{"#6366f115" if is_me else "transparent"};border-bottom:1px solid #1a1a2e">'
                f'<td style="padding:10px 14px;color:{"#a5b4fc" if r["bonus"] else "#9ca3af"};font-size:13px">'
                f'{rank_icon}</td>'
                f'<td style="padding:10px 14px;color:#fff;font-size:13px;font-weight:{"700" if is_me else "400"}">'
                f'{r["name"]}{" (moi)" if is_me else ""}{bonus_badge}</td>'
                f'<td style="padding:10px 14px;color:#2ecc71;font-size:13px;text-align:right">{r["signed"]}</td>'
                f'</tr>'
            )
    except Exception:
        leaderboard_rows_real = '<tr><td colspan="3" style="padding:20px;text-align:center;color:#555">Données non disponibles</td></tr>'

    # ── Paiement ──────────────────────────────────────────────────────────────
    closer_iban = ""
    payment_requests_closer = []
    if closer:
        try:
            closer_meta = json.loads(closer.meta) if isinstance(closer.meta, str) else (closer.meta or {})
            closer_iban = closer_meta.get("iban", "")
        except Exception:
            pass
        try:
            import json as _pj
            _pf = Path(__file__).parent.parent.parent.parent / "data" / "payment_requests.json"
            if _pf.exists():
                _all = _pj.loads(_pf.read_text(encoding="utf-8"))
                payment_requests_closer = [r for r in _all if r.get("closer_id") == str(closer.id)]
        except Exception:
            pass

    _pr_rows = ""
    for pr in payment_requests_closer:
        _st_color = "#2ecc71" if pr.get("status") == "paid" else "#f59e0b"
        _st_label = "Versé" if pr.get("status") == "paid" else "En attente"
        _paid_note = f' · versé le {pr["paid_at"][:10]}' if pr.get("paid_at") else ""
        _pr_rows += (
            f'<tr style="border-bottom:1px solid #1a1a2e">'
            f'<td style="padding:10px 14px;color:#ccc;font-size:12px">{pr.get("requested_at","")[:10]}</td>'
            f'<td style="padding:10px 14px;color:#2ecc71;font-size:13px;font-weight:600">{pr.get("amount",0):.0f}€</td>'
            f'<td style="padding:10px 14px"><span style="background:{_st_color}20;color:{_st_color};'
            f'font-size:10px;font-weight:600;padding:2px 7px;border-radius:10px">{_st_label}</span>{_paid_note}</td>'
            f'</tr>'
        )
    if not _pr_rows:
        _pr_rows = '<tr><td colspan="3" style="padding:20px;color:#555;text-align:center;font-size:12px">Aucune demande</td></tr>'

    _iban_save_js = f"""
async function saveIban(){{
  const iban=document.getElementById('iban-input').value.trim().toUpperCase();
  if(!iban){{alert('Saisissez votre IBAN.');return;}}
  const r=await fetch('/closer/{token}/iban',{{method:'POST',
    headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{iban}})
  }});
  if(r.ok){{document.getElementById('iban-saved').style.display='inline';
    setTimeout(()=>document.getElementById('iban-saved').style.display='none',2000);}}
}}
async function requestPayment(){{
  const r=await fetch('/closer/{token}/payment-request',{{method:'POST',
    headers:{{'Content-Type':'application/json'}}
  }});
  const d=await r.json();
  if(d.ok){{alert('Demande envoyée ! Montant : '+d.amount+'€ · versement le 10 du mois.');location.reload();}}
  else{{alert(d.error||'Erreur');}}
}}
""" if closer else "function saveIban(){{}} function requestPayment(){{}}"

    _pending_amount = comm_a_verser
    _can_request = closer and _pending_amount > 0 and not any(
        r.get("status") == "pending" for r in payment_requests_closer
    )
    _request_btn_style = (
        "background:#6366f1;color:#fff;cursor:pointer"
        if _can_request else
        "background:#2a2a4e;color:#555;cursor:not-allowed"
    )
    _request_btn_title = (
        "" if _can_request else
        ("Demande déjà en cours" if any(r.get("status") == "pending" for r in payment_requests_closer)
         else "Aucun montant à verser")
    )

    panel_paiement = f"""
<div style="margin-bottom:24px">
  <h2 style="color:#fff;font-size:16px;font-weight:700;margin-bottom:4px">Paiement des commissions</h2>
  <p style="color:#6b7280;font-size:12px">Versement le 10 du mois suivant la signature du client.</p>
</div>

<!-- Solde -->
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:24px">
  <div style="background:#1a1a2e;border:1px solid #2ecc7140;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#2ecc71">{comm_verse:.0f}€</div>
    <div style="color:#9ca3af;font-size:10px;margin-top:4px">Déjà versé</div>
  </div>
  <div style="background:#1a1a2e;border:1px solid #f59e0b40;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#f59e0b">{_pending_amount:.0f}€</div>
    <div style="color:#9ca3af;font-size:10px;margin-top:4px">À verser</div>
  </div>
</div>

<!-- IBAN -->
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px;margin-bottom:20px">
  <p style="color:#9ca3af;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Votre IBAN (pour le virement)</p>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <input id="iban-input" value="{closer_iban}" placeholder="FR76 XXXX XXXX XXXX XXXX XXXX XXX"
      style="flex:1;min-width:240px;background:#0f0f1a;border:1px solid #3a3a6e;border-radius:6px;
             padding:10px 14px;color:#e8e8f0;font-size:13px;font-family:monospace;outline:none">
    <button onclick="saveIban()" style="padding:10px 20px;background:#6366f1;border:none;
      border-radius:6px;color:#fff;font-size:13px;font-weight:600;cursor:pointer">Enregistrer</button>
    <span id="iban-saved" style="color:#2ecc71;font-size:12px;display:none">IBAN enregistré ✓</span>
  </div>
  <p style="color:#555;font-size:11px;margin-top:8px">Format international. Ex : FR76 3000 6000 0112 3456 7890 189</p>
</div>

<!-- Demander paiement -->
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:20px;margin-bottom:20px">
  <p style="color:#9ca3af;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Demander un versement</p>
  <p style="color:#ccc;font-size:13px;margin-bottom:14px">
    Solde à verser : <strong style="color:#f59e0b">{_pending_amount:.0f}€</strong>
  </p>
  <button onclick="requestPayment()" {('title="'+_request_btn_title+'"') if _request_btn_title else ''}
    {"disabled" if not _can_request else ""}
    style="padding:10px 24px;border:none;border-radius:6px;font-size:13px;font-weight:600;{_request_btn_style}">
    Demander le versement
  </button>
  {('<p style="color:#f59e0b;font-size:11px;margin-top:8px">⚠ ' + _request_btn_title + '</p>') if _request_btn_title else ''}
</div>

<!-- Historique demandes -->
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden">
<p style="color:#9ca3af;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;padding:14px 16px;border-bottom:1px solid #2a2a4e;margin:0">Historique des demandes</p>
<table style="width:100%;border-collapse:collapse">
<thead><tr>
  <th style="padding:8px 14px;text-align:left;color:#555;font-size:10px;border-bottom:1px solid #1a1a2e">Date demande</th>
  <th style="padding:8px 14px;text-align:left;color:#555;font-size:10px;border-bottom:1px solid #1a1a2e">Montant</th>
  <th style="padding:8px 14px;text-align:left;color:#555;font-size:10px;border-bottom:1px solid #1a1a2e">Statut</th>
</tr></thead>
<tbody>{_pr_rows}</tbody></table></div>
<script>{_iban_save_js}</script>"""

    # ── Onglets ───────────────────────────────────────────────────────────────
    TABS = [("rdv", "Mes RDV"), ("commissions", "Commissions"),
            ("paiement", "Paiement"), ("offre", "L'offre"), ("script", "Script"), ("objections", "Objections")]

    def _tab_btn(slug, label):
        active = slug == tab
        return (
            f'<button onclick="switchTab(\'{slug}\')" id="tab-{slug}" '
            f'style="padding:8px 16px;border:none;border-radius:6px;cursor:pointer;font-size:12px;'
            f'font-weight:{"700" if active else "400"};'
            f'background:{"#6366f1" if active else "#1a1a2e"};'
            f'color:{"#fff" if active else "#9ca3af"};'
            f'border:1px solid {"#6366f1" if active else "#2a2a4e"}">'
            f'{label}</button>'
        )

    tabs_html = f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px">{"".join(_tab_btn(s,l) for s,l in TABS)}</div>'

    def _pre(text):
        """Rendu texte brut en HTML lisible."""
        return "<br>".join(
            f'<span style="color:{"#6366f1" if ln.startswith(tuple("123456789")) else "#ccc"}">{ln}</span>'
            if ln.strip() else '<span style="display:block;height:8px"></span>'
            for ln in (text or "").split("\n")
        )

    panel_rdv = f"""
<div style="margin-bottom:20px">
  <a href="/closer/{token}/slots" style="display:inline-block;background:#8b5cf6;
    color:#fff;text-decoration:none;padding:9px 18px;border-radius:6px;font-size:12px;font-weight:600">
    📅 Agenda — voir les créneaux disponibles →</a>
</div>
<h3 style="color:#fff;font-size:14px;margin-bottom:16px">RDV à venir ({len(meetings_upcoming)})</h3>
{upcoming_html}
<h3 style="color:#9ca3af;font-size:12px;letter-spacing:.06em;text-transform:uppercase;margin:24px 0 12px">Historique</h3>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden">
<table style="width:100%;border-collapse:collapse">
<thead><tr>
  <th style="padding:8px 16px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #2a2a4e">Prospect</th>
  <th style="padding:8px 16px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #2a2a4e">Date</th>
  <th style="padding:8px 16px;border-bottom:1px solid #2a2a4e;color:#555;font-size:10px">Statut</th>
  <th style="padding:8px 16px;border-bottom:1px solid #2a2a4e;color:#555;font-size:10px">Deal</th>
  <th style="padding:8px 16px;border-bottom:1px solid #2a2a4e;color:#555;font-size:10px">Commission</th>
</tr></thead>
<tbody>{past_rows}</tbody></table></div>"""

    _months_fr = ["janvier","février","mars","avril","mai","juin","juillet",
                  "août","septembre","octobre","novembre","décembre"]
    _month_label = f"{_months_fr[now.month - 1].capitalize()} {now.year}"
    panel_commissions = f"""
<div style="margin-bottom:20px;display:flex;justify-content:space-between;align-items:baseline">
  <h2 style="color:#fff;font-size:16px;font-weight:700">Ventes &amp; Commissions</h2>
  <span style="color:#6366f1;font-size:12px;font-weight:600">{_month_label}</span>
</div>

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:20px">
  <div style="background:#1a1a2e;border:1px solid #2ecc7140;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#2ecc71">{stats_month["signed"]}</div>
    <div style="color:#9ca3af;font-size:10px;margin-top:4px">Ventes ce mois</div>
  </div>
  <div style="background:#1a1a2e;border:1px solid #2ecc7140;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#2ecc71">{stats_month["earned"]:.0f}€</div>
    <div style="color:#9ca3af;font-size:10px;margin-top:4px">Commission ce mois</div>
  </div>
  <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#e9a020">{commission_rate*100:.0f}%</div>
    <div style="color:#9ca3af;font-size:10px;margin-top:4px">Taux commission</div>
  </div>
  <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#527FB3">{stats["earned"]:.0f}€</div>
    <div style="color:#9ca3af;font-size:10px;margin-top:4px">Cumulé total</div>
  </div>
</div>

<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;margin-bottom:20px">
  <p style="color:#9ca3af;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Historique versements</p>
  <div style="display:flex;gap:24px;align-items:center">
    <div>
      <div style="font-size:1.5rem;font-weight:700;color:#2ecc71">{comm_verse:.0f}€</div>
      <div style="color:#9ca3af;font-size:10px;margin-top:2px">Versé</div>
    </div>
    <div style="width:1px;height:40px;background:#2a2a4e"></div>
    <div>
      <div style="font-size:1.5rem;font-weight:700;color:#f59e0b">{comm_a_verser:.0f}€</div>
      <div style="color:#9ca3af;font-size:10px;margin-top:2px">À verser</div>
    </div>
    <div style="width:1px;height:40px;background:#2a2a4e"></div>
    <div>
      <div style="font-size:1.5rem;font-weight:700;color:#9ca3af">{stats["pending"]:.0f}€</div>
      <div style="color:#9ca3af;font-size:10px;margin-top:2px">En attente (RDV)</div>
    </div>
  </div>
</div>

<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px">
  <p style="color:#9ca3af;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Règles &amp; détail</p>
  <div style="color:#ccc;font-size:13px;line-height:1.8">{comm_info_html or '<span style="color:#555">Aucune règle définie — voir avec l\'équipe.</span>'}</div>
</div>"""

    def _resource_block(title, text, color="#6366f1"):
        return (
            f'<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;margin-bottom:16px">'
            f'<p style="color:{color};font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">{title}</p>'
            f'<div style="color:#ccc;font-size:13px;line-height:1.8">{_pre(text)}</div>'
            f'</div>'
        )

    panel_offre       = _resource_block(content.get("offer_title","L'offre") + f' — {content.get("offer_price","")}', content.get("offer_pitch",""), "#2ecc71")
    panel_script      = _resource_block("Script de vente", content.get("pitch_script",""), "#6366f1")
    panel_objections  = _resource_block("Réponses aux objections", content.get("objections",""), "#e9a020")

    panels = {
        "rdv":         panel_rdv,
        "commissions": panel_commissions,
        "paiement":    panel_paiement,
        "offre":       panel_offre,
        "script":      panel_script,
        "objections":  panel_objections,
    }
    panels_js = {k: v.replace("`", "\\`").replace("${", "\\${") for k, v in panels.items()}

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} — Portail Closer</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
table{{width:100%;border-collapse:collapse}}
tr:hover{{background:#111127}}
</style></head><body>

<div style="background:#1a1a2e;border-bottom:1px solid #2a2a4e;padding:14px 24px;
            display:flex;align-items:center;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:10px">
    <img src="/assets/logo.svg" alt="Présence IA" style="height:26px">
    <span style="color:#9ca3af;font-size:11px">Portail Closer</span>
  </div>
  <span style="color:#fff;font-weight:600;font-size:14px">{name}</span>
</div>

<div style="max-width:920px;margin:0 auto;padding:28px 20px">

<!-- Stats -->
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:28px">
{stats_html}
</div>

<!-- Tabs -->
{tabs_html}

<!-- Contenu de l'onglet actif -->
<div id="tab-content">
  {panels.get(tab, panels["rdv"])}
</div>

</div>
<script>
const _panels = {{
  rdv: `{panels_js["rdv"]}`,
  commissions: `{panels_js["commissions"]}`,
  paiement: `{panels_js["paiement"]}`,
  offre: `{panels_js["offre"]}`,
  script: `{panels_js["script"]}`,
  objections: `{panels_js["objections"]}`,
}};
function switchTab(slug) {{
  document.getElementById('tab-content').innerHTML = _panels[slug] || '';
  document.querySelectorAll('[id^="tab-"]').forEach(b => {{
    const active = b.id === 'tab-' + slug;
    b.style.background  = active ? '#6366f1' : '#1a1a2e';
    b.style.color       = active ? '#fff'    : '#9ca3af';
    b.style.fontWeight  = active ? '700'     : '400';
    b.style.borderColor = active ? '#6366f1' : '#2a2a4e';
  }});
  history.replaceState(null,'',location.pathname + '?tab=' + slug);
}}
</script>
</body></html>""")


def _meeting_badge(status: str, scheduled_at=None) -> str:
    from datetime import datetime, timezone as _tz
    # Si RDV "scheduled" mais date passée → afficher "Passé" au lieu de "À venir"
    if status == "scheduled" and scheduled_at:
        _now = datetime.now(_tz.utc)
        _sat = scheduled_at if scheduled_at.tzinfo else scheduled_at.replace(tzinfo=_tz.utc)
        if _sat < _now:
            return (f'<span style="background:#9ca3af20;color:#9ca3af;font-size:10px;font-weight:600;'
                    f'padding:2px 7px;border-radius:10px">Passé</span>')
    m = {
        "scheduled": ("#f59e0b", "À venir"),
        "completed": ("#2ecc71", "Signé"),
        "no_show":   ("#e94560", "No-show"),
        "cancelled": ("#9ca3af", "Annulé"),
    }
    color, label = m.get(status, ("#6366f1", status))
    return (f'<span style="background:{color}20;color:{color};font-size:10px;font-weight:600;'
            f'padding:2px 7px;border-radius:10px">{label}</span>')


@router.get("/closer/{closer_token}/meeting/{meeting_id}", response_class=HTMLResponse)
def closer_meeting_detail(closer_token: str, meeting_id: str, request: Request):
    """Fiche RDV détaillée pour le closer."""
    import json as _json
    import re as _re

    meeting = None
    prospect = None
    deliveries = []

    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import MeetingDB, ProspectDeliveryDB
        from ...database import SessionLocal
        from ...models import V3ProspectDB

        with MktSession() as mdb:
            meeting = mdb.query(MeetingDB).filter_by(id=meeting_id).first()
            if meeting:
                deliveries = mdb.query(ProspectDeliveryDB).filter_by(
                    project_id=PROJECT_ID, prospect_id=meeting.prospect_id
                ).order_by(ProspectDeliveryDB.created_at.desc()).limit(5).all()

        if meeting:
            with SessionLocal() as db:
                prospect = db.query(V3ProspectDB).filter_by(token=meeting.prospect_id).first()
    except Exception:
        pass

    if not meeting:
        return HTMLResponse("<p style='padding:40px;color:#666'>RDV introuvable.</p>", status_code=404)

    content = _load_portal_content()

    def _fmt(dt):
        return dt.strftime("%d/%m/%y %H:%M") if dt else "—"

    name  = prospect.name if prospect else "—"
    city  = prospect.city if prospect else "—"
    prof  = prospect.profession if prospect else "—"
    email = prospect.email if prospect else "—"
    phone = (prospect.phone or "") if prospect else ""
    land  = getattr(prospect, "landing_url", "") or ""

    # ── Score IA + concurrents ─────────────────────────────────────────────
    ia_score = 0.0
    cited_names: list = []
    total_queries = 0
    prospect_cit = 0
    try:
        raw = getattr(prospect, "ia_results", None)
        if raw:
            results = _json.loads(raw) if isinstance(raw, str) else (raw or [])
            total_queries = len(results)
            norm_name = _re.sub(r'[^a-z0-9 ]', '', (name or "").lower().replace("[test]", "").strip())
            for r in results:
                resp = r.get("response", "")
                for m in _re.finditer(r'\[([^\]]{3,60})\]\(', resp):
                    n = m.group(1).strip()
                    if n and n not in cited_names and not n.startswith("http"):
                        cited_names.append(n)
                if norm_name and len(norm_name) > 3 and norm_name in resp.lower():
                    prospect_cit += 1
            if total_queries:
                ia_score = round(prospect_cit / total_queries * 10, 1)
    except Exception:
        pass

    score_color = "#2ecc71" if ia_score >= 6 else ("#f59e0b" if ia_score >= 3 else "#e94560")
    score_pct = int(ia_score / 10 * 100)

    _PANIERS = {
        "couvreur": "8 000 – 15 000 €", "pisciniste": "15 000 – 35 000 €",
        "menuisier": "5 000 – 20 000 €", "plombier": "2 000 – 8 000 €",
        "electricien": "1 500 – 6 000 €", "macon": "10 000 – 50 000 €",
        "peintre": "2 000 – 10 000 €", "carreleur": "3 000 – 15 000 €",
        "installateur": "5 000 – 25 000 €", "renovateur": "15 000 – 80 000 €",
        "toiture": "8 000 – 20 000 €", "isolation": "5 000 – 20 000 €",
    }
    prof_norm = _re.sub(r'[^a-z]', '', (prof or "").lower()
                        .replace("é","e").replace("è","e").replace("ê","e")
                        .replace("à","a").replace("â","a").replace("ô","o"))
    panier = next((v for k, v in _PANIERS.items() if k in prof_norm), "Non renseigné")

    cited_html = "".join(
        f'<span style="background:#2a2a4e;color:#ccc;font-size:10px;padding:2px 8px;'
        f'border-radius:10px;margin:2px;display:inline-block">{n[:45]}</span>'
        for n in cited_names[:12]
    ) or '<span style="color:#555;font-size:12px">Aucune donnée IA disponible</span>'

    # ── Timeline comportementale ───────────────────────────────────────────
    timeline = ""
    try:
        for dv in deliveries:
            if dv.sent_at:    timeline += f'<li>📧 Envoyé {_fmt(dv.sent_at)}</li>'
            if dv.opened_at:  timeline += f'<li style="color:#f59e0b">👁 Ouvert {_fmt(dv.opened_at)}</li>'
            if dv.clicked_at: timeline += f'<li style="color:#2ecc71">🖱 Clic landing {_fmt(dv.clicked_at)}</li>'
            lv = getattr(dv, "landing_visited_at", None)
            if lv:            timeline += f'<li style="color:#2ecc71">🌐 Landing visitée {_fmt(lv)}</li>'
            cc = getattr(dv, "calendly_clicked_at", None)
            if cc:            timeline += f'<li style="color:#6366f1">📅 Calendly cliqué {_fmt(cc)}</li>'
    except Exception:
        pass

    phone_btn = (
        f'<a href="tel:{phone}" style="padding:6px 12px;background:#6366f120;border:1px solid #6366f140;'
        f'border-radius:4px;color:#6366f1;font-size:12px;text-decoration:none">📞 {phone}</a>'
    ) if phone else ""
    land_btn = (
        f'<a href="https://presence-ia.com{land}" target="_blank" '
        f'style="padding:6px 12px;background:#2ecc7120;border:1px solid #2ecc7140;'
        f'border-radius:4px;color:#2ecc71;font-size:12px;text-decoration:none">🔗 Landing</a>'
    ) if land else ""

    # ── Accordéon offres ──────────────────────────────────────────────────
    pitch = content.get("offer_pitch", "")
    import re as _re2
    offer_blocks = _re2.split(r'─{5,}', pitch)
    offer_texts = {str(i+1): offer_blocks[i+1].strip() if i+1 < len(offer_blocks) else "" for i in range(3)}
    offer_accordeon = ""
    for i, (num, oname, price) in enumerate([("1","Audit Complet","500 €"),
                                              ("2","Exécution Complète","3 500 €"),
                                              ("3","Domination IA Locale","9 000 €")]):
        open_attr = " open" if i == 1 else ""
        offer_accordeon += (
            f'<details{open_attr} style="margin-bottom:10px;background:#0f0f1a;border:1px solid #2a2a4e;border-radius:8px">'
            f'<summary style="padding:16px;cursor:pointer;display:flex;align-items:center;justify-content:space-between;list-style:none">'
            f'<div><span style="color:#9ca3af;font-size:10px">Offre {num}</span>'
            f'<div style="color:#fff;font-size:15px;font-weight:700;margin-top:2px">{oname}</div></div>'
            f'<div style="text-align:right">'
            f'<div style="color:#2ecc71;font-size:1.8rem;font-weight:900">{price}</div>'
            f'<button onclick="sendPaymentLink(event,\'{num}\')" style="margin-top:4px;padding:4px 10px;'
            f'background:#6366f1;color:#fff;border:none;border-radius:4px;font-size:10px;cursor:pointer">'
            f'Envoyer lien →</button></div></summary>'
            f'<div style="padding:0 16px 16px">'
            f'<pre id="ob{num}" style="white-space:pre-wrap;font-family:inherit;font-size:12px;color:#ccc;line-height:1.7"></pre>'
            f'</div></details>'
        )

    script_text = content.get("pitch_script", "")

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fiche RDV — {name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
.card{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;margin-bottom:14px}}
.sec{{color:#9ca3af;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;display:block}}
.rtab{{padding:7px 14px;border:1px solid #2a2a4e;border-radius:6px;background:#1a1a2e;color:#9ca3af;font-size:11px;cursor:pointer}}
.active-rtab{{background:#6366f1;color:#fff;border-color:#6366f1}}
details>summary::-webkit-details-marker{{display:none}}
textarea{{background:#0f0f1a;border:1px solid #2a2a4e;border-radius:6px;color:#ccc;font-size:13px;
  padding:10px;width:100%;resize:vertical;min-height:80px;font-family:inherit;line-height:1.5}}
textarea:focus{{outline:none;border-color:#6366f1}}
.modal-bg{{display:none;position:fixed;inset:0;background:#000a;z-index:100;align-items:center;justify-content:center}}
.modal-bg.open{{display:flex}}
.modal{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:24px;max-width:480px;width:90%}}
select{{background:#0f0f1a;border:1px solid #2a2a4e;border-radius:6px;color:#ccc;padding:8px 10px;width:100%;font-size:13px}}
</style></head><body>

<div style="background:#1a1a2e;border-bottom:1px solid #2a2a4e;padding:14px 24px;
            display:flex;align-items:center;justify-content:space-between">
  <img src="/assets/logo.svg" alt="Présence IA" style="height:24px">
  <a href="/closer/{closer_token}" style="color:#527FB3;font-size:12px;text-decoration:none">← Mes RDV</a>
</div>

<div style="max-width:820px;margin:0 auto;padding:24px 20px">

<!-- EN-TÊTE PROSPECT -->
<div class="card" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
  <div>
    <h1 style="color:#fff;font-size:18px;font-weight:700">{name}</h1>
    <p style="color:#9ca3af;font-size:12px;margin-top:3px">{city} · {prof}
      <span style="color:#555"> · {email}</span></p>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
    {phone_btn}
    {land_btn}
    <button onclick="document.getElementById('modal-complete').classList.add('open')"
      style="padding:7px 14px;background:#6366f1;color:#fff;border:none;border-radius:6px;
             font-size:12px;cursor:pointer;font-weight:600">
      ✓ Clôturer ce RDV</button>
  </div>
</div>

<!-- SCORE IA -->
<div class="card">
  <span class="sec">Visibilité IA actuelle</span>
  <div style="display:flex;align-items:center;gap:16px;margin-bottom:12px">
    <div style="text-align:center;min-width:56px">
      <div style="font-size:2.2rem;font-weight:900;color:{score_color}">{ia_score}</div>
      <div style="color:#555;font-size:10px">/10</div>
    </div>
    <div style="flex:1">
      <div style="background:#0f0f1a;border-radius:4px;height:8px;overflow:hidden">
        <div style="background:{score_color};width:{score_pct}%;height:100%;border-radius:4px;
                    transition:width .5s"></div>
      </div>
      <div style="color:#9ca3af;font-size:11px;margin-top:5px">
        Cité <strong>{prospect_cit}</strong> fois sur <strong>{total_queries}</strong> requêtes
        &nbsp;·&nbsp; Panier moyen estimé :
        <strong style="color:#fff">{panier}</strong>
      </div>
    </div>
  </div>
  <span class="sec" style="margin-bottom:6px">Concurrents cités par les IA</span>
  <div style="display:flex;flex-wrap:wrap;gap:4px">{cited_html}</div>
</div>

<!-- RDV + STATUT -->
<div class="card" style="display:flex;gap:24px;align-items:center;flex-wrap:wrap">
  <div>
    <div style="color:#f59e0b;font-size:1.1rem;font-weight:700">{_fmt(meeting.scheduled_at)}</div>
    <div style="color:#9ca3af;font-size:10px;margin-top:2px">Date RDV</div>
  </div>
  <div>{_meeting_badge(meeting.status, meeting.scheduled_at)}</div>
  {"<div><div style='color:#2ecc71;font-size:1.1rem;font-weight:700'>{}€</div><div style='color:#9ca3af;font-size:10px;margin-top:2px'>Deal signé</div></div>".format(int(meeting.deal_value)) if meeting.deal_value else ""}
</div>

<!-- NOTES ÉDITABLES -->
<div class="card">
  <span class="sec">Notes
    <span id="note-status" style="font-size:9px;color:#555;font-weight:400;text-transform:none;margin-left:8px"></span>
  </span>
  <textarea id="notes-area" placeholder="Points clés du prospect, objections soulevées, décision...">{meeting.notes or ""}</textarea>
</div>

<!-- COMPORTEMENT -->
<div class="card">
  <span class="sec">Comportement du prospect</span>
  <ul style="list-style:none;display:flex;flex-direction:column;gap:4px;font-size:12px">
    {timeline or '<li style="color:#555">Aucun historique disponible</li>'}
  </ul>
</div>

<!-- RESSOURCES CLOSER -->
<div style="margin-top:4px">
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
    <button onclick="showRes('offres')" id="rtab-offres" class="rtab active-rtab">Les offres</button>
    <button onclick="showRes('args')" id="rtab-args" class="rtab">Arguments</button>
    <button onclick="showRes('trame')" id="rtab-trame" class="rtab">Trame de vente</button>
    <button onclick="showRes('objections')" id="rtab-objections" class="rtab">Objections</button>
    <button onclick="showRes('commissions')" id="rtab-commissions" class="rtab">Commissions</button>
  </div>

  <div id="res-offres" class="res-panel">
    <p style="color:#9ca3af;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;
              margin-bottom:12px">Ordre de présentation : Domination → Exécution → Audit</p>
    {offer_accordeon}
  </div>
  <div id="res-args" class="res-panel card" style="display:none">
    <span class="sec">Arguments de vente par offre</span>
    <pre style="white-space:pre-wrap;font-family:inherit;font-size:12px;color:#ccc;line-height:1.7">{content.get("arguments_vente","")}</pre>
  </div>
  <div id="res-trame" class="res-panel card" style="display:none">
    <span class="sec">Trame de vente — 6 étapes</span>
    <pre style="white-space:pre-wrap;font-family:inherit;font-size:12px;color:#ccc;line-height:1.7">{content.get("trame_vente", content.get("pitch_script",""))}</pre>
  </div>
  <div id="res-objections" class="res-panel card" style="display:none">
    <span class="sec">Réponses aux objections</span>
    <pre style="white-space:pre-wrap;font-family:inherit;font-size:12px;color:#ccc;line-height:1.7">{content.get("objections","")}</pre>
  </div>
  <div id="res-commissions" class="res-panel card" style="display:none">
    <span class="sec">Conditions de rémunération</span>
    <pre style="white-space:pre-wrap;font-family:inherit;font-size:12px;color:#ccc;line-height:1.7">{content.get("commission_info","")}</pre>
  </div>
</div>

</div>

<!-- MODAL CLÔTURE RDV -->
<div class="modal-bg" id="modal-complete">
  <div class="modal">
    <h2 style="color:#fff;font-size:16px;font-weight:700;margin-bottom:20px">Clôturer ce RDV</h2>
    <div style="display:flex;flex-direction:column;gap:14px">
      <div>
        <label style="color:#9ca3af;font-size:11px;display:block;margin-bottom:6px">Résultat</label>
        <select id="cl-status" onchange="onStatusChange()">
          <option value="completed">Signé ✓</option>
          <option value="no_show">No-show</option>
          <option value="cancelled">Annulé</option>
          <option value="relance">À relancer</option>
        </select>
      </div>
      <div id="cl-offer-block">
        <label style="color:#9ca3af;font-size:11px;display:block;margin-bottom:6px">Offre signée</label>
        <select id="cl-offer">
          <option value="500">Audit Complet — 500 €</option>
          <option value="3500" selected>Exécution Complète — 3 500 €</option>
          <option value="9000">Domination IA Locale — 9 000 €</option>
        </select>
      </div>
      <div id="cl-date-block" style="display:none">
        <label style="color:#9ca3af;font-size:11px;display:block;margin-bottom:6px">Date de relance</label>
        <input type="date" id="cl-date" style="background:#0f0f1a;border:1px solid #2a2a4e;
               border-radius:6px;color:#ccc;padding:8px;width:100%;font-size:13px">
      </div>
      <div>
        <label style="color:#9ca3af;font-size:11px;display:block;margin-bottom:6px">Notes de clôture</label>
        <textarea id="cl-notes" placeholder="Résumé du call, décision, prochaine étape..."></textarea>
      </div>
      <div style="display:flex;gap:10px;justify-content:flex-end">
        <button onclick="document.getElementById('modal-complete').classList.remove('open')"
          style="padding:8px 16px;background:#1a1a2e;border:1px solid #2a2a4e;color:#9ca3af;
                 border-radius:6px;cursor:pointer;font-size:12px">Annuler</button>
        <button onclick="submitComplete()"
          style="padding:8px 16px;background:#6366f1;border:none;color:#fff;
                 border-radius:6px;cursor:pointer;font-size:12px;font-weight:600">Enregistrer</button>
      </div>
    </div>
  </div>
</div>

<script>
// ── Injecter textes offres ──
const _ot = {_json.dumps(offer_texts)};
Object.keys(_ot).forEach(k => {{
  const el = document.getElementById('ob'+k);
  if (el) el.textContent = _ot[k];
}});

// ── Onglets ressources ──
function showRes(key) {{
  document.querySelectorAll('.res-panel').forEach(p => p.style.display='none');
  document.querySelectorAll('.rtab').forEach(b => b.classList.remove('active-rtab'));
  document.getElementById('res-'+key).style.display='block';
  document.getElementById('rtab-'+key).classList.add('active-rtab');
}}

// ── Notes auto-save (debounce 1s) ──
let _nt;
document.getElementById('notes-area').addEventListener('input', function() {{
  clearTimeout(_nt);
  document.getElementById('note-status').textContent = '…';
  _nt = setTimeout(async () => {{
    const r = await fetch('/closer/{closer_token}/meeting/{meeting_id}/notes', {{
      method:'PATCH', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{notes: this.value}})
    }});
    const ns = document.getElementById('note-status');
    ns.textContent = r.ok ? 'sauvegardé ✓' : 'erreur';
    setTimeout(() => ns.textContent='', 2000);
  }}, 1000);
}});

// ── Modal clôture ──
function onStatusChange() {{
  const s = document.getElementById('cl-status').value;
  document.getElementById('cl-offer-block').style.display = s==='completed' ? 'block' : 'none';
  document.getElementById('cl-date-block').style.display  = s==='relance'   ? 'block' : 'none';
}}

async function submitComplete() {{
  const status  = document.getElementById('cl-status').value;
  const offerV  = document.getElementById('cl-offer').value;
  const notes   = document.getElementById('cl-notes').value;
  const relDate = document.getElementById('cl-date').value;
  const r = await fetch('/closer/{closer_token}/meeting/{meeting_id}/complete', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{status, deal_value:status==='completed'?parseFloat(offerV):null,
                           notes, relance_date:relDate}})
  }});
  const d = await r.json();
  if (r.ok) {{ document.getElementById('modal-complete').classList.remove('open'); location.reload(); }}
  else alert(d.error || 'Erreur');
}}

async function sendPaymentLink(e, offerNum) {{
  e.stopPropagation(); e.preventDefault();
  const r = await fetch('/closer/{closer_token}/meeting/{meeting_id}/payment-link', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{offer_num: offerNum}})
  }});
  const d = await r.json();
  alert(d.message || 'Lien envoyé !');
}}
</script>
</body></html>""")


@router.patch("/closer/{closer_token}/meeting/{meeting_id}/notes", response_class=JSONResponse)
async def closer_save_notes(closer_token: str, meeting_id: str, request: Request):
    """Auto-save des notes sur un RDV."""
    body = await request.json()
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import MeetingDB
        with MktSession() as mdb:
            m = mdb.query(MeetingDB).filter_by(id=meeting_id).first()
            if m:
                m.notes = body.get("notes", "")
                mdb.commit()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/closer/{closer_token}/meeting/{meeting_id}/complete", response_class=JSONResponse)
async def closer_complete_meeting(closer_token: str, meeting_id: str, request: Request):
    """Clôturer un RDV : statut + deal + notes."""
    from datetime import datetime
    body = await request.json()
    status   = body.get("status", "completed")
    deal_val = body.get("deal_value")
    notes    = body.get("notes", "")
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import MeetingDB, MeetingStatus
        status_map = {
            "completed": MeetingStatus.completed,
            "no_show":   MeetingStatus.no_show,
            "cancelled": MeetingStatus.cancelled,
            "relance":   MeetingStatus.scheduled,
        }
        with MktSession() as mdb:
            m = mdb.query(MeetingDB).filter_by(id=meeting_id).first()
            if not m:
                return JSONResponse({"error": "RDV introuvable"}, status_code=404)
            m.status = status_map.get(status, MeetingStatus.completed)
            if deal_val:
                m.deal_value = float(deal_val)
            if notes:
                existing = m.notes or ""
                m.notes = (existing + f"\n[Clôture] {notes}").strip()
            if status == "completed":
                m.completed_at = datetime.utcnow()
            mdb.commit()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/closer/{closer_token}/meeting/{meeting_id}/payment-link", response_class=JSONResponse)
async def closer_send_payment_link(closer_token: str, meeting_id: str, request: Request):
    """Envoyer le lien de paiement Stripe au prospect (stub — configurer Stripe Price IDs)."""
    body = await request.json()
    offer_num = str(body.get("offer_num", "2"))
    offers = {"1": ("Audit Complet", "500"), "2": ("Exécution Complète", "3500"),
              "3": ("Domination IA Locale", "9000")}
    o_name, o_price = offers.get(offer_num, ("Offre", ""))
    # TODO: créer session Stripe + envoyer email quand stripe_price_id configuré
    return JSONResponse({
        "message": f"⚠️ Stripe non configuré — Prix ID manquant pour '{o_name} ({o_price}€)'. "
                   f"Configurez dans /admin puis réessayez."
    })


# ─────────────────────────────────────────────────────────────────────────────
# Couche crédits — helpers
# ─────────────────────────────────────────────────────────────────────────────

def _credit_value(starts_at, now_naive) -> int:
    """Valeur crédits d'un slot selon son délai. Positif = urgent, négatif = futur lointain."""
    delta_h = (starts_at - now_naive).total_seconds() / 3600
    if delta_h < 24:   return  2
    if delta_h < 48:   return  1
    if delta_h < 72:   return  0
    if delta_h < 120:  return -1   # 3–5 jours
    if delta_h < 240:  return -2   # 5–10 jours
    return -3


def _calc_closer_credits(closer_id: str, mdb) -> int:
    """Solde = Σ valeurs des slots futurs *claimed* par ce closer (passés exclus)."""
    from datetime import datetime as _dt2
    from marketing_module.models import SlotDB, SlotStatus
    now = _dt2.utcnow()
    taken = mdb.query(SlotDB).filter(
        SlotDB.closer_id == str(closer_id),
        SlotDB.status == SlotStatus.claimed,
        SlotDB.starts_at > now,
    ).all()
    return sum(_credit_value(s.starts_at, now) for s in taken)


# ─────────────────────────────────────────────────────────────────────────────
# Page créneaux du closer
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/closer/{token}/slots", response_class=HTMLResponse)
def closer_slots(token: str, request: Request):
    """Planning interactif — calendrier jour/semaine/mois avec couche crédits."""
    closer = _get_closer_by_token(token)
    if not closer:
        return HTMLResponse("<p style='font-family:sans-serif;padding:40px;color:#666'>Lien invalide.</p>",
                            status_code=404)

    import datetime as _dt
    import json as _json
    now = _dt.datetime.utcnow()
    end = now + _dt.timedelta(days=30)

    slot_data   = []
    my_meetings = []
    lb          = []
    my_rank     = "—"

    try:
        from marketing_module.database import (SessionLocal as MktSession,
                                               db_list_slots, db_monthly_leaderboard)
        from marketing_module.models import SlotDB, SlotStatus, MeetingDB, CloserDB
        from ...database import SessionLocal
        from ...models import V3ProspectDB

        with MktSession() as mdb:
            credits     = _calc_closer_credits(str(closer.id), mdb)
            raw_slots   = db_list_slots(mdb, PROJECT_ID, from_dt=now, to_dt=end)
            lb          = db_monthly_leaderboard(mdb, PROJECT_ID)
            all_closers = mdb.query(CloserDB).filter_by(
                project_id=PROJECT_ID, is_active=True
            ).all()
            all_credits = {str(c.id): _calc_closer_credits(str(c.id), mdb) for c in all_closers}

            with SessionLocal() as db:
                # ── Slots ────────────────────────────────────────────────────
                for s in raw_slots:
                    p_name = p_city = p_profession = p_phone = ""
                    p_rating = p_reviews = None
                    p_competitors = []
                    score = None
                    meeting_id = None

                    if s.meeting_id:
                        mtg = mdb.query(MeetingDB).filter_by(id=s.meeting_id).first()
                        if mtg:
                            meeting_id = str(mtg.id)
                            if mtg.prospect_id:
                                p = db.query(V3ProspectDB).filter_by(
                                    token=mtg.prospect_id
                                ).first()
                                if p:
                                    p_name       = p.name or ""
                                    p_city       = p.city or ""
                                    p_profession = p.profession or ""
                                    p_phone      = p.phone or ""
                                    p_rating     = p.rating
                                    p_reviews    = p.reviews_count
                                    if p.competitors:
                                        try:
                                            p_competitors = _json.loads(p.competitors)
                                        except Exception:
                                            pass
                                    if p_rating:
                                        score = round(p_rating * 20)

                    delta_h   = (s.starts_at - now).total_seconds() / 3600
                    is_urgent = delta_h < 48
                    cv        = _credit_value(s.starts_at, now)

                    is_mine        = (s.status == SlotStatus.claimed
                                      and str(s.closer_id) == str(closer.id))
                    is_taken_other = (s.status in (SlotStatus.claimed, SlotStatus.blocked)
                                      and str(s.closer_id) != str(closer.id))
                    is_booked      = (s.status == SlotStatus.booked)

                    credit_ok = True if is_urgent else (credits + cv) >= 0
                    if is_booked and is_urgent and not credit_ok:
                        eligible = [c for c in all_closers
                                    if (all_credits.get(str(c.id), 0) + cv) < 0]
                        if len(eligible) == len(all_closers):
                            credit_ok = True

                    can_claim    = is_booked and credit_ok
                    credit_block = is_booked and not credit_ok

                    explainers = []
                    if p_competitors:
                        explainers.append(f"{len(p_competitors)} concurrent(s) visible(s) en IA")
                    if p_rating and p_rating >= 4.0:
                        explainers.append(f"Réputation Google {p_rating}/5 · {p_reviews or '?'} avis")
                    elif p_reviews and int(p_reviews) > 20:
                        explainers.append(f"Activité établie ({p_reviews} avis Google)")
                    if p_phone:
                        explainers.append("Coordonnées directes disponibles")

                    slot_data.append({
                        "id":             str(s.id),
                        "starts":         s.starts_at.isoformat(),
                        "ends":           s.ends_at.isoformat() if s.ends_at else None,
                        "is_urgent":      is_urgent,
                        "is_mine":        is_mine,
                        "is_taken_other": is_taken_other,
                        "can_claim":      can_claim,
                        "credit_block":   credit_block,
                        "meeting_id":     meeting_id,
                        "prospect": {
                            "name":       p_name,
                            "city":       p_city,
                            "profession": p_profession,
                            "phone":      p_phone,
                            "score":      score,
                            "explainers": explainers[:3],
                        },
                    })

                # ── Mes RDV ──────────────────────────────────────────────────
                my_mtgs = mdb.query(MeetingDB).filter_by(
                    project_id=PROJECT_ID, closer_id=closer.id
                ).order_by(MeetingDB.scheduled_at.desc()).limit(50).all()
                for m in my_mtgs:
                    pp = None
                    if m.prospect_id:
                        pp = db.query(V3ProspectDB).filter_by(token=m.prospect_id).first()
                    my_meetings.append({
                        "id":             str(m.id),
                        "scheduled":      m.scheduled_at.isoformat() if m.scheduled_at else None,
                        "scheduled_str":  m.scheduled_at.strftime("%d/%m %H:%M") if m.scheduled_at else "—",
                        "status":         str(m.status),
                        "is_future":      bool(m.scheduled_at and m.scheduled_at > now),
                        "deal_value":     m.deal_value,
                        "prospect_name":  pp.name  if pp else "—",
                        "prospect_city":  pp.city  if pp else "—",
                        "prospect_phone": pp.phone if pp else "",
                    })

    except Exception:
        pass

    # ── Dataset mock : injecté si aucun slot réel ou ?demo=1 ──────────────────
    _demo = request.query_params.get("demo") or not slot_data
    if _demo:
        _prospects = [
            ("Cabinet Aubert",    "Lyon",        "Expert-comptable",  "06 12 34 56 78", 86, ["BDO","Mazars"],         ["3 concurrents visibles en IA","Réputation Google 4.3/5 · 47 avis","Coordonnées directes disponibles"]),
            ("Clinique Moreau",   "Paris 15e",   "Chirurgien dentiste","06 23 45 67 89", 74, ["Dentego"],              ["1 concurrent visible en IA","Activité établie (31 avis Google)","Coordonnées directes disponibles"]),
            ("Auto École Martin", "Bordeaux",    "Auto-école",        "05 56 78 90 12", 61, [],                       ["Coordonnées directes disponibles"]),
            ("Plomberie Durand",  "Nantes",      "Plombier",          "02 40 12 34 56", 79, ["Engie Home","Dalkia"],  ["2 concurrents visibles en IA","Réputation Google 4.5/5 · 62 avis","Coordonnées directes disponibles"]),
            ("Koiffure Studio",   "Lille",       "Coiffeur",          "",               55, ["Saint Algue"],          ["1 concurrent visible en IA"]),
            ("Garage Renard",     "Strasbourg",  "Garagiste",         "03 88 56 78 90", 82, ["Midas","Speedy"],       ["2 concurrents visibles en IA","Réputation Google 4.1/5 · 88 avis","Coordonnées directes disponibles"]),
            ("Notaire Lefebvre",  "Montpellier", "Notaire",           "04 67 34 56 78", 91, [],                       ["Réputation Google 4.8/5 · 19 avis","Coordonnées directes disponibles"]),
            ("Institut Beauté",   "Nice",        "Esthéticienne",     "04 93 12 34 56", 67, ["Yves Rocher"],          ["1 concurrent visible en IA","Coordonnées directes disponibles"]),
        ]
        _base     = now.replace(hour=9, minute=0, second=0, microsecond=0)
        _mock_def = [
            # (delta_h, state, prospect_idx)
            #  Urgents < 24h — accessibles
            ( 2,   "booked_accessible_urgent",  0),
            ( 6,   "booked_accessible_urgent",  1),
            (14,   "booked_accessible_urgent",  2),
            (20,   "booked_accessible_urgent",  3),
            # Urgents 24-48h — accessibles
            (26,   "booked_accessible_urgent",  4),
            (36,   "booked_accessible_urgent",  5),
            (44,   "booked_accessible_urgent",  6),
            # Futurs accessibles 2-4 jours
            (52,   "booked_accessible",         7),
            (62,   "booked_accessible",         0),
            (74,   "booked_accessible",         1),
            (88,   "booked_accessible",         2),
            (100,  "booked_accessible",         3),
            # Futurs non accessibles (credit_block)
            (56,   "credit_block",              4),
            (70,   "credit_block",              5),
            (96,   "credit_block",              6),
            # Pris par moi
            (30,   "mine",                      7),
            (78,   "mine",                      0),
            (110,  "mine",                      1),
            # Pris par autre
            (10,   "taken_other",               2),
            (48,   "taken_other",               3),
            (64,   "taken_other",               4),
            (116,  "taken_other",               5),
            # Futurs lointains accessibles (5-7 jours)
            (122,  "booked_accessible",         6),
            (134,  "booked_accessible",         7),
            (148,  "booked_accessible",         0),
        ]
        for i, (dh, state, pi) in enumerate(_mock_def):
            _t   = _base + _dt.timedelta(hours=dh)
            _dur = _dt.timedelta(minutes=20)
            _pu  = _prospects[pi]
            _is_urgent        = dh < 48
            _is_mine          = (state == "mine")
            _is_taken_other   = (state == "taken_other")
            _can_claim        = (state in ("booked_accessible", "booked_accessible_urgent"))
            _credit_block     = (state == "credit_block")
            slot_data.append({
                "id":             f"mock-{i}",
                "starts":         _t.isoformat(),
                "ends":           (_t + _dur).isoformat(),
                "is_urgent":      _is_urgent,
                "is_mine":        _is_mine,
                "is_taken_other": _is_taken_other,
                "can_claim":      _can_claim,
                "credit_block":   _credit_block,
                "meeting_id":     None,
                "prospect": {
                    "name":       _pu[0],
                    "city":       _pu[1],
                    "profession": _pu[2],
                    "phone":      _pu[3],
                    "score":      _pu[4],
                    "explainers": _pu[6],
                },
            })
        my_meetings = [
            {"id": "mock-rdv-1", "scheduled": (_base + _dt.timedelta(hours=30)).isoformat(),
             "scheduled_str": (_base + _dt.timedelta(hours=30)).strftime("%d/%m %H:%M"),
             "status": "scheduled", "is_future": True, "deal_value": None,
             "prospect_name": "Cabinet Aubert", "prospect_city": "Lyon", "prospect_phone": "06 12 34 56 78"},
            {"id": "mock-rdv-2", "scheduled": (_base - _dt.timedelta(hours=48)).isoformat(),
             "scheduled_str": (_base - _dt.timedelta(hours=48)).strftime("%d/%m %H:%M"),
             "status": "completed", "is_future": False, "deal_value": 3500,
             "prospect_name": "Garage Renard", "prospect_city": "Strasbourg", "prospect_phone": "03 88 56 78 90"},
            {"id": "mock-rdv-3", "scheduled": (_base - _dt.timedelta(hours=24)).isoformat(),
             "scheduled_str": (_base - _dt.timedelta(hours=24)).strftime("%d/%m %H:%M"),
             "status": "no_show", "is_future": False, "deal_value": None,
             "prospect_name": "Plomberie Durand", "prospect_city": "Nantes", "prospect_phone": "02 40 12 34 56"},
        ]

    for r in lb:
        if str(r["closer_id"]) == str(closer.id):
            my_rank = str(r["rank"])
            break

    urgent_free  = [s for s in slot_data if s["is_urgent"] and s["can_claim"]]
    mode_libre   = len(urgent_free) == 0
    banner_msg   = ("Aucun rendez-vous urgent — choisissez librement."
                    if mode_libre else
                    "Créneaux urgents à assurer en priorité pour débloquer les créneaux éloignés.")
    banner_color = "#2ecc71" if mode_libre else "#f59e0b"
    banner_bg    = "#2ecc7110" if mode_libre else "#f59e0b10"
    banner_bdr   = "#2ecc7130" if mode_libre else "#f59e0b30"

    name          = closer.name
    slots_json    = _json.dumps(slot_data,   ensure_ascii=False)
    meetings_json = _json.dumps(my_meetings, ensure_ascii=False)

    # Placeholders évitent l'échappement CSS/JS dans une f-string
    _html = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Planning — __NAME__</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}
.cal-slot:hover{filter:brightness(1.2);z-index:2}
#popup-overlay{position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:100;
  display:none;align-items:center;justify-content:center;padding:20px}
#popup-overlay.open{display:flex}
#popup-box{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:14px;
  padding:24px;max-width:440px;width:100%;max-height:90vh;overflow-y:auto}
#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
  background:#2ecc71;color:#0f0f1a;padding:10px 22px;border-radius:6px;
  font-size:13px;font-weight:600;opacity:0;transition:opacity .3s;pointer-events:none;z-index:200}
.vbtn{padding:6px 14px;border:1px solid #2a2a4e;border-radius:6px;
  font-size:11px;font-weight:600;cursor:pointer;background:#1a1a2e;color:#9ca3af;transition:all .15s}
.vbtn.active{background:#6366f1;color:#fff;border-color:#6366f1}
.fchip{padding:5px 12px;border:1px solid #2a2a4e;border-radius:20px;
  font-size:11px;font-weight:600;cursor:pointer;background:#1a1a2e;color:#555;transition:all .15s}
</style>
</head>
<body>

<!-- Header -->
<div style="background:#1a1a2e;border-bottom:1px solid #2a2a4e;padding:12px 20px;
  display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:50">
  <div style="display:flex;align-items:center;gap:10px">
    <img src="/assets/logo.svg" alt="" style="height:22px">
    <span style="color:#9ca3af;font-size:11px">Planning</span>
  </div>
  <div style="display:flex;align-items:center;gap:14px">
    <span style="color:#fff;font-size:13px;font-weight:600">__NAME__</span>
    <a href="/closer/__TOKEN__" style="color:#527FB3;font-size:12px;text-decoration:none">← Portail</a>
  </div>
</div>

<!-- Banner -->
<div style="background:__BANNER_BG__;border-bottom:1px solid __BANNER_BDR__;
  padding:8px 20px;color:__BANNER_COLOR__;font-size:11px;line-height:1.6">__BANNER_MSG__</div>

<div style="max-width:1100px;margin:0 auto">

<!-- Controls -->
<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  padding:14px 20px;border-bottom:1px solid #1a1a2e">

  <div style="display:flex;gap:4px">
    <button class="vbtn" id="vbtn-day"   onclick="setView('day')">Jour</button>
    <button class="vbtn" id="vbtn-week"  onclick="setView('week')">Semaine</button>
    <button class="vbtn" id="vbtn-month" onclick="setView('mois')">Mois</button>
  </div>

  <div style="display:flex;align-items:center;gap:6px">
    <button onclick="navigate(-1)" style="padding:5px 11px;background:#1a1a2e;
      border:1px solid #2a2a4e;border-radius:4px;color:#9ca3af;cursor:pointer;font-size:14px">‹</button>
    <span id="cal-label" style="font-size:12px;color:#fff;font-weight:600;
      min-width:130px;text-align:center"></span>
    <button onclick="navigate(1)" style="padding:5px 11px;background:#1a1a2e;
      border:1px solid #2a2a4e;border-radius:4px;color:#9ca3af;cursor:pointer;font-size:14px">›</button>
    <button onclick="goToday()" style="padding:5px 10px;background:#1a1a2e;
      border:1px solid #2a2a4e;border-radius:4px;color:#527FB3;cursor:pointer;
      font-size:10px;font-weight:600">Auj.</button>
  </div>

  <div style="flex:1;min-width:8px"></div>

  <div style="display:flex;gap:6px;flex-wrap:wrap">
    <button class="fchip" id="f-urgent"     onclick="toggleF('urgent')"    >⚡ Urgents</button>
    <button class="fchip" id="f-accessible" onclick="toggleF('accessible')">● Accessibles</button>
    <button class="fchip" id="f-pris"       onclick="toggleF('pris')"      >● Pris</button>
    <button class="fchip" id="f-blocked"    onclick="toggleF('blocked')"   >● Non accessibles</button>
  </div>
</div>

<!-- Calendar -->
<div style="overflow-x:auto;padding:16px 20px 0">
  <div id="cal"></div>
</div>

<!-- Mes RDV -->
<div style="max-width:760px;margin:44px auto 0;padding:0 20px 60px">
  <h2 style="color:#fff;font-size:15px;font-weight:700;margin-bottom:16px;
    padding-bottom:10px;border-bottom:1px solid #2a2a4e">Mes RDV</h2>
  <div id="mes-rdv"></div>
</div>

</div>

<!-- Popup -->
<div id="popup-overlay" onclick="closePopup()">
  <div id="popup-box" onclick="event.stopPropagation()">
    <div id="popup-body"></div>
  </div>
</div>

<div id="toast"></div>

<script>
const SLOTS        = __SLOTS_JSON__;
const MY_MEETINGS  = __MEETINGS_JSON__;
const TOKEN        = '__TOKEN__';

// ── Constants ─────────────────────────────────────────────────────────────
const HR=60, DAY_S=8, DAY_E=21, CAL_H=(DAY_E-DAY_S)*HR;
const DAYS_FR=['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'];
const MONTHS_FR=['Janvier','Février','Mars','Avril','Mai','Juin','Juillet',
                 'Août','Septembre','Octobre','Novembre','Décembre'];
const FC={urgent:'#e94560',accessible:'#8b5cf6',pris:'#6366f1',blocked:'#6b7280'};

// ── State ─────────────────────────────────────────────────────────────────
let view='week', cur=new Date();
let F={urgent:true,accessible:true,pris:true,blocked:true};

// ── Helpers ───────────────────────────────────────────────────────────────
const addD=(d,n)=>{const r=new Date(d);r.setDate(r.getDate()+n);return r;};
function weekStart(d){const r=new Date(d);r.setDate(r.getDate()-((r.getDay()+6)%7));r.setHours(0,0,0,0);return r;}
function sameDay(a,b){return a.getFullYear()===b.getFullYear()&&a.getMonth()===b.getMonth()&&a.getDate()===b.getDate();}
function fmtT(iso){const d=new Date(iso);return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');}
function he(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

// ── Slot style ────────────────────────────────────────────────────────────
function sStyle(s){
  if(s.is_mine)                  return{bg:'#6366f130',br:'#6366f1',c:'#a5b4fc',lbl:'Réservé',dim:false};
  if(s.is_taken_other)           return{bg:'#1a1a2e',  br:'#2a2a4e',c:'#555',   lbl:'Pris',   dim:true };
  if(s.credit_block)             return{bg:'#111',     br:'#1e1e30',c:'#333',   lbl:'—',      dim:true };
  if(s.can_claim&&s.is_urgent)   return{bg:'#e94560',  br:'#e94560',c:'#fff',   lbl:'URGENT', dim:false};
  if(s.can_claim)                return{bg:'#8b5cf6',  br:'#8b5cf6',c:'#fff',   lbl:'Libre',  dim:false};
  return                               {bg:'#111',     br:'#1e1e30',c:'#333',   lbl:'—',      dim:true };
}

function visible(s){
  const mu=F.urgent    && s.is_urgent && s.can_claim;
  const ma=F.accessible&& !s.is_urgent&& s.can_claim;
  const mb=F.blocked   &&(s.credit_block||(s.is_taken_other&&!s.is_mine));
  const mp=F.pris      && s.is_mine;
  return mu||ma||mb||mp;
}

// ── Time column ───────────────────────────────────────────────────────────
function timeCol(){
  let h='<div style="position:relative;height:'+CAL_H+'px;width:38px;flex-shrink:0">';
  for(let hr=DAY_S;hr<=DAY_E;hr++){
    h+=`<div style="position:absolute;top:${(hr-DAY_S)*HR}px;right:3px;font-size:9px;
      color:#2a2a4e;transform:translateY(-50%);white-space:nowrap">${hr}h</div>`;
  }
  return h+'</div>';
}

function hLines(){
  let h='';
  for(let hr=DAY_S;hr<=DAY_E;hr++)
    h+=`<div style="position:absolute;top:${(hr-DAY_S)*HR}px;left:0;right:0;
      border-top:1px solid #1a1a2e;pointer-events:none"></div>`;
  return h;
}

function slotBlock(s,wide=false){
  const st=sStyle(s);
  const d=new Date(s.starts);
  const top=(d.getHours()-DAY_S)*HR+d.getMinutes();
  if(top<0||top>CAL_H-2) return '';
  const dim=st.dim?'opacity:0.35;':'';
  const pname=he((s.prospect.name||'').split(' ')[0]);
  const urg=s.is_urgent&&s.can_claim?'⚡':'';
  const tl=String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');
  return `<div onclick="openPopup('${he(s.id)}')" class="cal-slot"
    style="position:absolute;left:2px;right:2px;top:${top}px;height:19px;
    background:${st.bg};border:1px solid ${st.br};border-radius:3px;
    color:${st.c};font-size:9px;overflow:hidden;cursor:pointer;
    padding:1px 3px;white-space:nowrap;text-overflow:ellipsis;${dim}"
    title="${he(s.prospect.name)} · ${he(s.prospect.city)}">${urg}${wide?tl+' ':''}${pname}</div>`;
}

// ── Views ─────────────────────────────────────────────────────────────────
function renderDay(){
  const dSlots=SLOTS.filter(s=>sameDay(new Date(s.starts),cur)&&visible(s));
  document.getElementById('cal-label').textContent=
    ['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche'][((cur.getDay()+6)%7)]+
    ' '+cur.getDate()+' '+MONTHS_FR[cur.getMonth()];
  let h='<div style="display:flex;max-width:500px">'+timeCol();
  let body=`<div style="position:relative;height:${CAL_H}px;flex:1;border-left:1px solid #1a1a2e">${hLines()}`;
  if(!dSlots.length) body+=`<div style="position:absolute;top:180px;left:0;right:0;
    text-align:center;color:#2a2a4e;font-size:12px">Aucun créneau ce jour</div>`;
  dSlots.forEach(s=>{body+=slotBlock(s,true);});
  document.getElementById('cal').innerHTML=h+body+'</div></div>';
}

function renderWeek(){
  const start=weekStart(cur);
  const days=Array.from({length:7},(_,i)=>addD(start,i));
  const e=days[6];
  document.getElementById('cal-label').textContent=
    String(start.getDate()).padStart(2,'0')+'/'+(start.getMonth()+1)+
    ' – '+String(e.getDate()).padStart(2,'0')+'/'+(e.getMonth()+1);
  let h='<div style="display:flex;min-width:560px">'+timeCol();
  days.forEach(d=>{
    const today=sameDay(d,new Date());
    const ds=SLOTS.filter(s=>sameDay(new Date(s.starts),d)&&visible(s));
    h+=`<div style="flex:1;min-width:0">
      <div style="text-align:center;padding:5px 2px;font-size:10px;border-bottom:1px solid #1a1a2e;
        color:${today?'#6366f1':'#9ca3af'};font-weight:${today?700:400};
        background:${today?'#6366f108':'transparent'}">${DAYS_FR[((d.getDay()+6)%7)]} ${d.getDate()}</div>
      <div style="position:relative;height:${CAL_H}px;border-left:1px solid #1a1a2e;
        background:${today?'#6366f105':'transparent'}">${hLines()}${ds.map(s=>slotBlock(s)).join('')}</div>
    </div>`;
  });
  document.getElementById('cal').innerHTML=h+'</div>';
}

function renderMonth(){
  const y=cur.getFullYear(),m=cur.getMonth();
  document.getElementById('cal-label').textContent=MONTHS_FR[m]+' '+y;
  const gs=addD(new Date(y,m,1),-((new Date(y,m,1).getDay()+6)%7));
  let h='<div>';
  h+='<div style="display:grid;grid-template-columns:repeat(7,1fr);margin-bottom:3px">';
  DAYS_FR.forEach(dn=>{h+=`<div style="text-align:center;font-size:9px;color:#6b7280;padding:3px">${dn}</div>`;});
  h+='</div><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:1px;background:#1a1a2e;border-radius:8px;overflow:hidden">';
  for(let i=0;i<42;i++){
    const cell=addD(gs,i);
    const inM=cell.getMonth()===m;
    const isT=sameDay(cell,new Date());
    const cs=SLOTS.filter(s=>sameDay(new Date(s.starts),cell)&&visible(s));
    h+=`<div onclick="gotoDay(${cell.getFullYear()},${cell.getMonth()},${cell.getDate()})"
      style="background:#0f0f1a;min-height:66px;padding:5px;cursor:pointer">
      <div style="font-size:10px;font-weight:${isT?700:400};margin-bottom:3px;
        color:${isT?'#6366f1':(inM?'#9ca3af':'#2a2a4e')}">${cell.getDate()}</div>
      <div style="display:flex;flex-wrap:wrap;gap:2px">`;
    cs.slice(0,8).forEach(s=>{
      const st=sStyle(s);
      h+=`<div onclick="event.stopPropagation();openPopup('${he(s.id)}')"
        style="width:7px;height:7px;border-radius:50%;background:${st.br};cursor:pointer"
        title="${he(s.prospect.name)}"></div>`;
    });
    if(cs.length>8) h+=`<span style="font-size:8px;color:#555">+${cs.length-8}</span>`;
    h+='</div></div>';
  }
  document.getElementById('cal').innerHTML=h+'</div></div>';
}

function render(){
  if(view==='day')       renderDay();
  else if(view==='week') renderWeek();
  else                   renderMonth();
}

function navigate(dir){
  if(view==='day')   cur=addD(cur,dir);
  else if(view==='week') cur=addD(cur,dir*7);
  else cur=new Date(cur.getFullYear(),cur.getMonth()+dir,1);
  render();
}
function goToday(){cur=new Date();render();}
function gotoDay(y,m,d){cur=new Date(y,m,d);setView('day');}

function setView(v){
  view=v;
  ['day','week','mois'].forEach(k=>{
    const b=document.getElementById('vbtn-'+k);
    if(b) b.className='vbtn'+(k===v?' active':'');
  });
  render();
}

function toggleF(key){
  F[key]=!F[key];
  const chip=document.getElementById('f-'+key);
  if(chip){
    chip.style.background =F[key]?FC[key]+'28':'#1a1a2e';
    chip.style.color      =F[key]?FC[key]:'#555';
    chip.style.borderColor=F[key]?FC[key]+'50':'#2a2a4e';
  }
  render();
}

// ── Popup ─────────────────────────────────────────────────────────────────
function openPopup(id){
  const s=SLOTS.find(x=>x.id===id); if(!s) return;
  const st=sStyle(s);
  const sd=new Date(s.starts),ed=s.ends?new Date(s.ends):null;
  const tStr=fmtT(s.starts)+(ed?' – '+fmtT(s.ends):'')+
    ' · '+String(sd.getDate()).padStart(2,'0')+'/'+(sd.getMonth()+1)+'/'+sd.getFullYear();

  const urgBadge=s.is_urgent?`<span style="background:#e9456020;color:#e94560;font-size:9px;
    font-weight:700;padding:1px 6px;border-radius:8px;margin-left:6px">URGENT</span>`:'';

  const chip=s.is_mine?
    `<div style="background:#6366f120;color:#6366f1;font-size:10px;padding:3px 10px;
      border-radius:4px;display:inline-block;margin-bottom:10px">Réservé par moi</div>`:
    s.is_taken_other?
    `<div style="background:#37415130;color:#6b7280;font-size:10px;padding:3px 10px;
      border-radius:4px;display:inline-block;margin-bottom:10px">Déjà pris</div>`:
    s.credit_block?
    `<div style="background:#37415130;color:#555;font-size:10px;padding:3px 10px;
      border-radius:4px;display:inline-block;margin-bottom:10px">Non accessible</div>`:'';

  const scoreBar=s.prospect.score?`<div style="margin:14px 0">
    <div style="display:flex;justify-content:space-between;margin-bottom:5px">
      <span style="font-size:10px;color:#9ca3af">Score prospect</span>
      <span style="font-size:13px;font-weight:700;color:#e9a020">${s.prospect.score}/100</span>
    </div>
    <div style="height:4px;background:#111;border-radius:2px">
      <div style="height:4px;width:${s.prospect.score}%;background:linear-gradient(90deg,#f59e0b,#2ecc71);border-radius:2px"></div>
    </div></div>`:'';

  const expl=(s.prospect.explainers||[]).length?
    `<div style="margin:12px 0;background:#111;border-radius:6px;padding:10px 12px">`+
    s.prospect.explainers.map(e=>`<div style="display:flex;gap:7px;margin-bottom:5px;align-items:flex-start">
      <span style="color:#2ecc71;font-size:10px;flex-shrink:0">✓</span>
      <span style="font-size:11px;color:#ccc">${he(e)}</span></div>`).join('')+'</div>':'';

  const pSection=(!s.prospect.name&&!s.prospect.city)?
    `<div style="color:#555;font-size:12px;margin:8px 0;font-style:italic">Aucune info prospect</div>`:
    `<div style="margin-bottom:10px">
      <div style="font-size:16px;font-weight:700;color:#fff">${he(s.prospect.name)}${urgBadge}</div>
      <div style="font-size:12px;color:#9ca3af;margin-top:3px">
        ${he(s.prospect.profession)}${s.prospect.profession&&s.prospect.city?' · ':''}${he(s.prospect.city)}
      </div></div>`;

  const claimBtn=s.can_claim?`<button onclick="claimSlot('${he(s.id)}')" id="claim-btn"
    style="width:100%;padding:12px;background:${s.is_urgent?'#e94560':'#8b5cf6'};border:none;
    border-radius:8px;color:#fff;font-size:14px;font-weight:700;cursor:pointer;margin-top:14px">
    Prendre ce RDV${s.is_urgent?' — URGENT':''}</button>`:'';

  document.getElementById('popup-body').innerHTML=`
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">
      <div style="flex:1">${pSection}</div>
      <button onclick="closePopup()" style="background:none;border:none;color:#6b7280;
        font-size:22px;cursor:pointer;line-height:1;flex-shrink:0;margin-left:12px;margin-top:-4px">×</button>
    </div>
    ${chip}
    <div style="font-size:11px;color:#6366f1;font-weight:600;margin-bottom:8px">🕐 ${tStr}</div>
    ${scoreBar}${expl}${claimBtn}`;
  document.getElementById('popup-overlay').className='open';
}
function closePopup(){document.getElementById('popup-overlay').className='';}

// ── Claim ─────────────────────────────────────────────────────────────────
async function claimSlot(id){
  const btn=document.getElementById('claim-btn');
  if(btn){btn.textContent='…';btn.disabled=true;}
  const r=await fetch('/closer/'+TOKEN+'/slots/'+id+'/claim',{method:'POST'});
  const d=await r.json();
  if(d.ok){closePopup();toast('Créneau réservé ✓');setTimeout(()=>location.reload(),900);}
  else{if(btn){btn.textContent='Prendre ce RDV';btn.disabled=false;}toast(d.error||'Erreur',true);}
}

// ── Toast ─────────────────────────────────────────────────────────────────
function toast(msg,err){
  const t=document.getElementById('toast');
  t.textContent=msg;t.style.background=err?'#e94560':'#2ecc71';t.style.color=err?'#fff':'#0f0f1a';
  t.style.opacity=1;setTimeout(()=>t.style.opacity=0,2500);
}

// ── Mes RDV ───────────────────────────────────────────────────────────────
function stInfo(st){
  const m={'scheduled':['#f59e0b','À venir'],'MeetingStatus.scheduled':['#f59e0b','À venir'],
    'completed':['#2ecc71','Signé'],'MeetingStatus.completed':['#2ecc71','Signé'],
    'no_show':['#e94560','No-show'],'MeetingStatus.no_show':['#e94560','No-show'],
    'cancelled':['#9ca3af','Annulé'],'MeetingStatus.cancelled':['#9ca3af','Annulé']};
  return m[st]||['#9ca3af',st];
}

function rdvCard(m,isPast){
  const[sc,sl]=stInfo(m.status);
  const done=['completed','MeetingStatus.completed','cancelled','MeetingStatus.cancelled'].includes(m.status);
  const tel=m.prospect_phone?`<a href="tel:${he(m.prospect_phone)}"
    style="display:inline-block;margin-top:4px;padding:3px 10px;background:#6366f120;
    border:1px solid #6366f140;border-radius:4px;color:#6366f1;font-size:10px;text-decoration:none">📞 Appeler</a>`:'';
  const acts=isPast&&!done?`<div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap">
    <button onclick="updM('${he(m.id)}','completed')"
      style="padding:4px 12px;background:#2ecc7120;border:1px solid #2ecc7140;
      border-radius:4px;color:#2ecc71;font-size:10px;font-weight:600;cursor:pointer">Vente</button>
    <button onclick="updM('${he(m.id)}','relance')"
      style="padding:4px 12px;background:#f59e0b20;border:1px solid #f59e0b40;
      border-radius:4px;color:#f59e0b;font-size:10px;font-weight:600;cursor:pointer">Rappel</button>
    <button onclick="updM('${he(m.id)}','no_show')"
      style="padding:4px 12px;background:#e9456020;border:1px solid #e9456040;
      border-radius:4px;color:#e94560;font-size:10px;font-weight:600;cursor:pointer">Refus</button>
  </div>`:'';
  return`<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;
    padding:14px 16px;margin-bottom:8px">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div><div style="color:#fff;font-size:13px;font-weight:600">${he(m.prospect_name)}</div>
        <div style="color:#6b7280;font-size:11px;margin-top:2px">${he(m.prospect_city)}</div>${tel}</div>
      <div style="text-align:right;flex-shrink:0;margin-left:12px">
        <div style="color:#6366f1;font-size:12px;font-weight:600">${he(m.scheduled_str)}</div>
        <span style="background:${sc}20;color:${sc};font-size:9px;font-weight:600;
          padding:1px 7px;border-radius:8px;display:inline-block;margin-top:4px">${sl}</span>
      </div></div>${acts}</div>`;
}

async function updM(id,outcome){
  let dv=null;
  if(outcome==='completed'){const v=prompt('Montant du deal (€) :');if(v===null)return;dv=parseFloat(v)||0;}
  const body={status:outcome};if(dv!==null)body.deal_value=dv;
  const r=await fetch('/closer/'+TOKEN+'/meeting/'+id+'/complete',
    {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(r.ok){toast('RDV mis à jour ✓');setTimeout(()=>location.reload(),900);}
  else toast('Erreur',true);
}

function renderMesRdv(){
  const up=MY_MEETINGS.filter(m=>m.is_future);
  const pa=MY_MEETINGS.filter(m=>!m.is_future);
  if(!MY_MEETINGS.length){
    document.getElementById('mes-rdv').innerHTML=
      '<p style="color:#374151;font-size:12px;padding:12px 0">Aucun RDV enregistré</p>';return;
  }
  let h='';
  if(up.length){
    h+=`<p style="color:#9ca3af;font-size:10px;text-transform:uppercase;letter-spacing:.08em;
      font-weight:700;margin-bottom:10px">À venir (${up.length})</p>`;
    up.forEach(m=>{h+=rdvCard(m,false);});
  }
  if(pa.length){
    h+=`<p style="color:#9ca3af;font-size:10px;text-transform:uppercase;letter-spacing:.08em;
      font-weight:700;margin:${up.length?'20px':'0'} 0 10px">Passés</p>`;
    pa.slice(0,20).forEach(m=>{h+=rdvCard(m,true);});
  }
  document.getElementById('mes-rdv').innerHTML=h;
}

// ── Init ──────────────────────────────────────────────────────────────────
(function initFilters(){
  const on=v=>window.innerWidth<640?v==='urgent'||v==='accessible':true;
  Object.keys(F).forEach(k=>{
    F[k]=on(k);
    const chip=document.getElementById('f-'+k);
    if(chip){
      chip.style.background =F[k]?FC[k]+'28':'#1a1a2e';
      chip.style.color      =F[k]?FC[k]:'#555';
      chip.style.borderColor=F[k]?FC[k]+'50':'#2a2a4e';
    }
  });
  // Force all ON on desktop
  if(window.innerWidth>=640){
    Object.keys(F).forEach(k=>{F[k]=true;});
    ['urgent','accessible','pris','blocked'].forEach(k=>{
      const chip=document.getElementById('f-'+k);
      if(chip){chip.style.background=FC[k]+'28';chip.style.color=FC[k];chip.style.borderColor=FC[k]+'50';}
    });
  }
})();
view=window.innerWidth<640?'day':'week';
setView(view);
renderMesRdv();
</script>
</body></html>"""

    _html = (_html
        .replace("__NAME__",          name)
        .replace("__TOKEN__",         token)
        .replace("__BANNER_MSG__",    banner_msg)
        .replace("__BANNER_COLOR__",  banner_color)
        .replace("__BANNER_BG__",     banner_bg)
        .replace("__BANNER_BDR__",    banner_bdr)
        .replace("__MY_RANK__",       my_rank)
        .replace("__SLOTS_JSON__",    slots_json)
        .replace("__MEETINGS_JSON__", meetings_json)
    )
    return HTMLResponse(_html)


@router.post("/closer/{token}/slots/{slot_id}/claim")
async def closer_claim_slot(token: str, slot_id: str):
    """Un closer revendique un créneau."""
    closer = _get_closer_by_token(token)
    if not closer:
        from fastapi import HTTPException
        raise HTTPException(404, "Lien invalide")

    try:
        from marketing_module.database import SessionLocal as MktSession, db_claim_slot, db_update_meeting, db_create_meeting
        from marketing_module.models import SlotDB
        with MktSession() as mdb:
            ok, message = db_claim_slot(mdb, slot_id, closer.id)
            if ok:
                slot = mdb.query(SlotDB).filter(SlotDB.id == slot_id).first()
                if slot and slot.meeting_id:
                    db_update_meeting(mdb, slot.meeting_id, {"closer_id": str(closer.id)})
                elif slot:
                    from datetime import datetime as _dt_now
                    db_create_meeting(mdb, {
                        "project_id": str(slot.project_id) if slot.project_id else None,
                        "slot_id": str(slot.id),
                        "closer_id": str(closer.id),
                        "scheduled_at": slot.starts_at,
                        "status": "scheduled",
                        "claimed_at": _dt_now.utcnow().isoformat(),
                    })
        return JSONResponse({"ok": ok, "message": message, "error": None if ok else message})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ─────────────────────────────────────────────────────────────────────────────
# Paiement SEPA — enregistrement IBAN + demande de versement
# ─────────────────────────────────────────────────────────────────────────────

_PAYMENT_REQUESTS_FILE = Path(__file__).parent.parent.parent.parent / "data" / "payment_requests.json"


def _load_payment_requests() -> list:
    try:
        if _PAYMENT_REQUESTS_FILE.exists():
            return json.loads(_PAYMENT_REQUESTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_payment_requests(requests: list):
    _PAYMENT_REQUESTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PAYMENT_REQUESTS_FILE.write_text(
        json.dumps(requests, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@router.post("/closer/{token}/iban")
async def save_closer_iban(token: str, request: Request):
    """Enregistre l'IBAN du closer dans closer.meta."""
    closer = _get_closer_by_token(token)
    if not closer:
        from fastapi import HTTPException
        raise HTTPException(404, "Lien invalide")
    data = await request.json()
    iban = data.get("iban", "").strip().upper().replace(" ", "")
    if not iban or len(iban) < 15:
        return JSONResponse({"ok": False, "error": "IBAN invalide"}, status_code=400)
    try:
        from marketing_module.database import SessionLocal as MktSession
        with MktSession() as mdb:
            c = mdb.get(type(closer), closer.id)
            meta = {}
            try:
                meta = json.loads(c.meta) if isinstance(c.meta, str) else (c.meta or {})
            except Exception:
                pass
            meta["iban"] = iban
            c.meta = json.dumps(meta, ensure_ascii=False)
            mdb.commit()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/closer/{token}/payment-request")
async def create_payment_request(token: str):
    """Crée une demande de paiement pour le closer (solde des commissions non versées)."""
    from fastapi import HTTPException
    closer = _get_closer_by_token(token)
    if not closer:
        raise HTTPException(404, "Lien invalide")

    # Vérifier qu'il n'y a pas déjà une demande en attente
    reqs = _load_payment_requests()
    pending = [r for r in reqs if r.get("closer_id") == str(closer.id) and r.get("status") == "pending"]
    if pending:
        return JSONResponse({"ok": False, "error": "Une demande est déjà en cours"}, status_code=400)

    # Calculer le montant (commissions non payées)
    amount = 0.0
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import CommissionDB
        with MktSession() as mdb:
            comms = mdb.query(CommissionDB).filter_by(
                project_id=PROJECT_ID, closer_id=str(closer.id)
            ).all()
            amount = sum(c.amount or 0 for c in comms if getattr(c, "status", "") != "paid")
    except Exception:
        pass

    if amount <= 0:
        return JSONResponse({"ok": False, "error": "Aucun solde à verser"}, status_code=400)

    # Récupérer l'IBAN
    iban = ""
    try:
        meta = json.loads(closer.meta) if isinstance(closer.meta, str) else (closer.meta or {})
        iban = meta.get("iban", "")
    except Exception:
        pass
    if not iban:
        return JSONResponse({"ok": False, "error": "Enregistrez votre IBAN d'abord"}, status_code=400)

    from datetime import datetime as _dt
    req = {
        "id":           uuid.uuid4().hex,
        "closer_id":    str(closer.id),
        "closer_name":  closer.name or "",
        "iban":         iban,
        "amount":       round(amount, 2),
        "requested_at": _dt.utcnow().isoformat(),
        "status":       "pending",
        "paid_at":      None,
    }
    reqs.append(req)
    _save_payment_requests(reqs)
    return JSONResponse({"ok": True, "amount": round(amount, 2)})
