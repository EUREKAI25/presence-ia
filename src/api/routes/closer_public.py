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
    return HTMLResponse("""<!DOCTYPE html><html lang="fr"><head>
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
      -webkit-text-fill-color:transparent">15% de commission</span><br>sur chaque deal que vous signez
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
        <div style="font-size:1.6rem;font-weight:800;color:#a78bfa">15%</div>
        <div style="color:#6b7280;font-size:11px;margin-top:4px">de commission</div>
      </div>
      <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:16px 24px;text-align:center">
        <div style="font-size:1.6rem;font-weight:800;color:#2ecc71">jusqu'à 1 350€</div>
        <div style="color:#6b7280;font-size:11px;margin-top:4px">par deal signé</div>
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

</body></html>""")


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
    {"rank": 1, "name": "Kévin R.",    "signed": 4, "commission": 2100.0, "bonus": False, "rate": 15},
    {"rank": 2, "name": "Marie Martin","signed": 2, "commission": 1050.0, "bonus": False, "rate": 15},
    {"rank": 3, "name": "David L.",    "signed": 1, "commission": 525.0,  "bonus": False, "rate": 15},
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
    commission_rate = 0.15
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
        f'<td style="padding:10px 16px">{_meeting_badge(m["status"])}</td>'
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
</div>"""

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
    {_meeting_badge(meeting["status"])}
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
        "commission_info": "15% du deal · jusqu'à 1 350€ par deal signé (offre Domination IA Locale).",
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
        f'<td style="padding:10px 16px">{_meeting_badge(m["status"])}</td>'
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

    # ── Onglets ───────────────────────────────────────────────────────────────
    TABS = [("rdv", "Mes RDV"), ("commissions", "Commissions"),
            ("offre", "L'offre"), ("script", "Script"), ("objections", "Objections")]

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


def _meeting_badge(status: str) -> str:
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
  <div>{_meeting_badge(meeting.status)}</div>
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
# Page créneaux du closer
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/closer/{token}/slots", response_class=HTMLResponse)
def closer_slots(token: str, request: Request):
    """Page de sélection des créneaux disponibles pour un closer."""
    closer = _get_closer_by_token(token)
    if not closer:
        return HTMLResponse("<p style='font-family:sans-serif;padding:40px;color:#666'>Lien invalide.</p>",
                            status_code=404)

    import datetime as _dt
    now  = _dt.datetime.utcnow()
    week = now + _dt.timedelta(days=14)

    slots  = []
    lb     = []
    my_rank = "—"
    try:
        from marketing_module.database import (SessionLocal as MktSession,
                                               db_list_slots, db_monthly_leaderboard)
        from marketing_module.models import SlotStatus, MeetingDB
        from ...database import SessionLocal
        from ...models import V3ProspectDB

        with MktSession() as mdb:
            slots = db_list_slots(mdb, PROJECT_ID, from_dt=now, to_dt=week)
            lb    = db_monthly_leaderboard(mdb, PROJECT_ID)

            # Enrichir les slots avec les infos prospect
            slot_data = []
            for s in slots:
                prospect_info = ""
                if s.meeting_id:
                    mtg = mdb.query(MeetingDB).filter_by(id=s.meeting_id).first()
                    if mtg:
                        with SessionLocal() as db:
                            p = db.query(V3ProspectDB).filter_by(token=mtg.prospect_id).first()
                        if p:
                            prospect_info = f"{p.name} · {p.city} · {p.profession}"
                slot_data.append({
                    "id":            s.id,
                    "starts_at":     s.starts_at,
                    "ends_at":       s.ends_at,
                    "status":        s.status,
                    "closer_id":     s.closer_id,
                    "prospect_info": prospect_info,
                })
    except Exception:
        slot_data = []

    for r in lb:
        if r["closer_id"] == closer.id:
            my_rank = str(r["rank"])
            break

    # Grouper par jour
    days: dict = {}
    for s in slot_data:
        day = s["starts_at"].strftime("%A %d/%m")
        days.setdefault(day, []).append(s)

    STATUS_INFO = {
        "available": ("#2ecc71", "Disponible", False),
        "booked":    ("#8b5cf6", "Prospect inscrit — à prendre", True),
        "claimed":   ("#6366f1", "Pris par moi", False),
        "completed": ("#9ca3af", "Terminé", False),
        "cancelled": ("#374151", "Annulé", False),
    }

    days_html = ""
    for day, day_slots in days.items():
        slots_html = ""
        for s in day_slots:
            # Si claimed par quelqu'un d'autre
            if s["status"] == "claimed" and s["closer_id"] != closer.id:
                color, label, can_claim = "#374151", "Pris", False
            else:
                color, label, can_claim = STATUS_INFO.get(s["status"], ("#555", s["status"], False))
                if s["status"] == "claimed" and s["closer_id"] == closer.id:
                    color, label = "#6366f1", "Pris par moi"

            starts_fmt = s["starts_at"].strftime("%H:%M")
            ends_fmt   = s["ends_at"].strftime("%H:%M")

            prospect_div = (
                f'<div style="color:#9ca3af;font-size:11px;margin-top:2px">{s["prospect_info"]}</div>'
            ) if s["prospect_info"] else ""

            claim_btn = (
                f'<button onclick="claimSlot(\'{s["id"]}\')" '
                f'style="margin-top:8px;padding:5px 12px;background:#8b5cf6;border:none;'
                f'border-radius:4px;color:#fff;font-size:11px;font-weight:600;cursor:pointer">'
                f'Prendre ce créneau</button>'
            ) if can_claim else ""

            slots_html += (
                f'<div id="slot-{s["id"]}" style="background:#1a1a2e;border:1px solid {color}40;'
                f'border-radius:8px;padding:12px 16px;margin-bottom:8px">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
                f'  <div>'
                f'    <span style="color:#fff;font-weight:600;font-size:13px">{starts_fmt} – {ends_fmt}</span>'
                f'    {prospect_div}'
                f'    {claim_btn}'
                f'  </div>'
                f'  <span style="background:{color}20;color:{color};font-size:10px;font-weight:600;'
                f'  padding:2px 7px;border-radius:10px;flex-shrink:0">{label}</span>'
                f'</div></div>'
            )
        days_html += (
            f'<div style="margin-bottom:24px">'
            f'<h3 style="color:#9ca3af;font-size:11px;font-weight:600;text-transform:uppercase;'
            f'letter-spacing:.08em;margin-bottom:12px">{day}</h3>'
            f'{slots_html or "<p style=\'color:#555;font-size:12px\'>Aucun créneau ce jour</p>"}'
            f'</div>'
        )

    if not days_html:
        days_html = '<p style="color:#555;font-size:13px;padding:20px 0">Aucun créneau disponible pour les 14 prochains jours.</p>'

    # Leaderboard sidebar
    lb_rows = ""
    for r in lb:
        is_me = r["closer_id"] == closer.id
        bonus_badge = ('<span style="background:#2ecc7120;color:#2ecc71;font-size:9px;'
                       'font-weight:600;padding:1px 5px;border-radius:8px;margin-left:4px">+5%</span>'
                       ) if r["bonus"] else ""
        rank_icon = "🥇" if r["rank"] == 1 else ("🥈" if r["rank"] == 2 else "#" + str(r["rank"]))
        lb_rows += (
            f'<tr style="background:{"#6366f115" if is_me else "transparent"};border-bottom:1px solid #1a1a2e">'
            f'<td style="padding:8px 12px;font-size:12px;color:#9ca3af">'
            f'{rank_icon}</td>'
            f'<td style="padding:8px 12px;font-size:12px;color:#fff;font-weight:{"700" if is_me else "400"}">'
            f'{r["name"]}{" (moi)" if is_me else ""}{bonus_badge}</td>'
            f'<td style="padding:8px 12px;font-size:12px;color:#2ecc71;text-align:right">{r["signed"]}</td>'
            f'</tr>'
        )
    if not lb_rows:
        lb_rows = '<tr><td colspan="3" style="padding:16px;text-align:center;color:#555">Aucune donnée</td></tr>'

    name = closer.name

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Créneaux — {name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
table{{width:100%;border-collapse:collapse}}
#toast{{position:fixed;bottom:24px;right:24px;background:#2ecc71;color:#0f0f1a;
  padding:10px 20px;border-radius:6px;font-size:13px;font-weight:600;
  opacity:0;transition:opacity .3s;pointer-events:none}}
</style></head><body>
<div style="background:#1a1a2e;border-bottom:1px solid #2a2a4e;padding:14px 24px;
            display:flex;align-items:center;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:10px">
    <img src="/assets/logo.svg" alt="Présence IA" style="height:24px">
    <span style="color:#9ca3af;font-size:11px">Portail Closer</span>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <span style="color:#fff;font-size:13px;font-weight:600">{name}</span>
    <a href="/closer/{token}?tab=classement" style="color:#527FB3;font-size:12px;text-decoration:none">← Mon portail</a>
  </div>
</div>

<div style="max-width:900px;margin:0 auto;padding:28px 20px">

<!-- Légende -->
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px">
  <div style="display:flex;align-items:center;gap:6px"><span style="width:10px;height:10px;background:#2ecc71;border-radius:50%;display:inline-block"></span><span style="color:#9ca3af;font-size:11px">Disponible</span></div>
  <div style="display:flex;align-items:center;gap:6px"><span style="width:10px;height:10px;background:#8b5cf6;border-radius:50%;display:inline-block"></span><span style="color:#9ca3af;font-size:11px">Prospect inscrit</span></div>
  <div style="display:flex;align-items:center;gap:6px"><span style="width:10px;height:10px;background:#6366f1;border-radius:50%;display:inline-block"></span><span style="color:#9ca3af;font-size:11px">Pris par moi</span></div>
  <div style="display:flex;align-items:center;gap:6px"><span style="width:10px;height:10px;background:#374151;border-radius:50%;display:inline-block"></span><span style="color:#9ca3af;font-size:11px">Pris par un autre</span></div>
</div>

<div style="display:grid;grid-template-columns:1fr minmax(240px,320px);gap:28px">
<div>
  <h2 style="color:#fff;font-size:15px;font-weight:700;margin-bottom:16px">Créneaux — 14 prochains jours</h2>
  {days_html}
</div>
<div>
  <h2 style="color:#fff;font-size:15px;font-weight:700;margin-bottom:16px">Classement du mois</h2>
  {'<div style="background:#6366f120;border:1px solid #6366f140;border-radius:6px;padding:8px 12px;margin-bottom:12px;font-size:12px;color:#a5b4fc">Votre rang : #' + my_rank + '</div>' if my_rank != "—" else ""}
  <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden;margin-bottom:12px">
  <table style="border-collapse:collapse">
  <tbody>{lb_rows}</tbody>
  </table></div>
  <p style="color:#555;font-size:11px;line-height:1.5">Les 2 premiers reçoivent +5% de commission ce mois.</p>
</div>
</div>

</div>
<div id="toast"></div>
<script>
function toast(m, err){{
  const t=document.getElementById('toast');
  t.textContent=m;t.style.background=err?'#e94560':'#2ecc71';
  t.style.opacity=1;setTimeout(()=>t.style.opacity=0,2500);
}}
async function claimSlot(slotId){{
  const btn=event.target;
  btn.textContent='En cours…';btn.disabled=true;
  const r=await fetch('/closer/{token}/slots/'+slotId+'/claim',{{method:'POST'}});
  const d=await r.json();
  if(d.ok){{
    toast('Créneau réservé ✓');
    // Mettre à jour le slot visuellement
    const el=document.getElementById('slot-'+slotId);
    if(el){{
      el.style.borderColor='#6366f140';
      el.querySelector('span[style*="border-radius:10px"]').textContent='Pris par moi';
      btn.remove();
    }}
  }} else {{
    btn.textContent='Prendre ce créneau';btn.disabled=false;
    toast(d.error||'Erreur',true);
  }}
}}
</script>
</body></html>""")


@router.post("/closer/{token}/slots/{slot_id}/claim")
async def closer_claim_slot(token: str, slot_id: str):
    """Un closer revendique un créneau."""
    closer = _get_closer_by_token(token)
    if not closer:
        from fastapi import HTTPException
        raise HTTPException(404, "Lien invalide")

    try:
        from marketing_module.database import SessionLocal as MktSession, db_claim_slot
        with MktSession() as mdb:
            ok, message = db_claim_slot(mdb, slot_id, closer.id)
        return JSONResponse({"ok": ok, "message": message, "error": None if ok else message})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
