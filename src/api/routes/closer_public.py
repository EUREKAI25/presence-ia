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
<header style="position:sticky;top:0;z-index:100;background:#0f0f1aee;
  backdrop-filter:blur(12px);border-bottom:1px solid #1a1a2e;padding:0 24px">
  <div style="max-width:1000px;margin:0 auto;height:64px;display:flex;align-items:center;justify-content:space-between">
    <img src="/assets/logo.svg" alt="Présence IA" style="height:32px">
    <a href="/closer/recruit" class="btn-primary" style="padding:10px 28px;font-size:.9rem">Postuler →</a>
  </div>
</header>

<!-- HERO -->
<section style="padding:80px 20px 60px;text-align:center;position:relative;overflow:hidden">
  <div style="position:absolute;inset:0;background:radial-gradient(ellipse 60% 50% at 50% 0%,#6366f118,transparent);pointer-events:none"></div>
  <div style="max-width:760px;margin:0 auto;position:relative">
    <span style="display:inline-block;background:#6366f115;border:1px solid #6366f130;
      color:#a5b4fc;font-size:.8rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
      padding:6px 16px;border-radius:20px;margin-bottom:24px">Opportunité de revenus · 100% télétravail</span>
    <h1 style="font-size:clamp(2.2rem,5vw,3.4rem);color:#fff;line-height:1.15;margin-bottom:20px;
      font-weight:800;letter-spacing:-.02em">
      Gagnez <span style="background:linear-gradient(135deg,#6366f1,#a78bfa);-webkit-background-clip:text;
      -webkit-text-fill-color:transparent">18% de commission</span><br>sur chaque deal que vous signez
    </h1>
    <p style="color:#9ca3af;font-size:1.1rem;line-height:1.7;margin-bottom:40px;max-width:580px;margin-left:auto;margin-right:auto">
      Les rendez-vous sont déjà pris et qualifiés.<br>
      Votre seul job : closer. On s'occupe de tout le reste.
    </p>
    <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
      <a href="/closer/recruit" class="btn-primary">Je postule maintenant →</a>
      <a href="#comment" class="btn-sec">Comment ça marche</a>
    </div>
    <!-- Chiffres -->
    <div style="display:flex;gap:24px;justify-content:center;flex-wrap:wrap;margin-top:52px">
      <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:16px 28px;text-align:center">
        <div style="font-size:1.8rem;font-weight:800;color:#a78bfa">18%</div>
        <div style="color:#6b7280;font-size:11px;margin-top:4px">de commission</div>
      </div>
      <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:16px 28px;text-align:center">
        <div style="font-size:1.8rem;font-weight:800;color:#2ecc71">~89€</div>
        <div style="color:#6b7280;font-size:11px;margin-top:4px">par deal signé</div>
      </div>
      <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:16px 28px;text-align:center">
        <div style="font-size:1.8rem;font-weight:800;color:#f59e0b">100%</div>
        <div style="color:#6b7280;font-size:11px;margin-top:4px">à distance</div>
      </div>
      <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:16px 28px;text-align:center">
        <div style="font-size:1.8rem;font-weight:800;color:#527FB3">0</div>
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
      <h3 style="color:#fff;font-size:1rem;font-weight:700;margin-bottom:8px">On vous envoie un RDV</h3>
      <p style="color:#6b7280;font-size:.9rem;line-height:1.6">
        Nous gérons la prospection, les emails, les relances. Vous recevez un RDV avec un prospect qui a déjà montré son intérêt.
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
        18% du deal viré le 10 du mois suivant. Pas de plafond. Plus vous signez, plus vous gagnez.
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
      <div><div style="color:#fff;font-weight:600;font-size:.95rem;margin-bottom:4px">RDV qualifiés</div>
      <div style="color:#555;font-size:.85rem">Prospects chauds, déjà sensibilisés</div></div>
    </div>
    <div style="background:#0d0d1a;border:1px solid #1a1a2e;border-radius:10px;padding:20px;display:flex;gap:12px;align-items:flex-start">
      <span style="font-size:1.3rem">📊</span>
      <div><div style="color:#fff;font-weight:600;font-size:.95rem;margin-bottom:4px">Portail de suivi</div>
      <div style="color:#555;font-size:.85rem">Vos RDV, stats et commissions en temps réel</div></div>
    </div>
  </div>
</section>

<!-- CTA FINAL -->
<section style="padding:0 20px 80px">
  <div style="max-width:620px;margin:0 auto;background:linear-gradient(135deg,#1a1a2e,#16162a);
    border:1px solid #2a2a4e;border-radius:20px;padding:48px 40px;text-align:center">
    <h2 style="color:#fff;font-size:1.6rem;font-weight:700;margin-bottom:12px">Prêt à nous rejoindre ?</h2>
    <p style="color:#9ca3af;margin-bottom:32px;line-height:1.6">
      Candidature en 2 minutes. Réponse sous 48h.
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
.section-title{color:#fff;font-size:14px;font-weight:600;margin:28px 0 16px;
               padding-bottom:8px;border-bottom:1px solid #2a2a4e}
.hint{color:#555;font-size:11px;margin-top:4px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
</style>
</head><body>
<header style="background:#0f0f1a;border-bottom:1px solid #1a1a2e;padding:0 24px;margin-bottom:0">
  <div style="max-width:680px;margin:0 auto;height:60px;display:flex;align-items:center;justify-content:space-between">
    <img src="/assets/logo.svg" alt="Présence IA" style="height:28px">
    <a href="/closer" style="color:#9ca3af;font-size:12px">← Programme closer</a>
  </div>
</header>
<div class="wrap" style="padding-top:36px">
  <h1>Candidature Closer</h1>
  <p class="sub">Remplissez ce formulaire. Nous vous répondrons sous 48h.</p>

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

    <div class="row">
      <div class="field">
        <label>Date de naissance *</label>
        <input type="date" name="date_of_birth" required>
      </div>
      <div class="field">
        <label>Ville</label>
        <input type="text" name="city" placeholder="Ville">
      </div>
    </div>

    <div class="row">
      <div class="field">
        <label>Pays</label>
        <input type="text" name="country" placeholder="FR">
      </div>
    </div>

    <div class="section-title">Votre présentation</div>

    <div class="field">
      <label>Message de présentation *</label>
      <textarea name="message" required placeholder="Présentez-vous, votre expérience en vente/closing, pourquoi ce programme vous intéresse..."></textarea>
    </div>

    <div class="field" id="field-video">
      <label>Lien vidéo de présentation (YouTube, Loom, Drive…) <span id="media-req" style="color:#e94560">*</span></label>
      <input type="url" name="video_url" id="video_url" placeholder="https://loom.com/share/...">
      <p class="hint">2-3 minutes max. Présentez-vous et expliquez votre motivation.</p>
    </div>

    <div class="field">
      <label>Message audio <span style="color:#555;font-weight:400;text-transform:none;letter-spacing:0">(ou à la place de la vidéo)</span></label>
      <input type="file" name="audio_file" id="audio_file" accept="audio/*" style="padding:8px">
      <p class="hint">Fichier .mp3 ou .m4a — 5 Mo max</p>
    </div>

    <p id="media-error" style="color:#e94560;font-size:12px;margin-bottom:12px;display:none">
      Merci de fournir au moins une vidéo ou un message audio.
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
    {"rank": 1, "name": "Kévin R.",    "signed": 4, "commission": 357.84, "bonus": True,  "rate": 23},
    {"rank": 2, "name": "Marie Martin","signed": 3, "commission": 268.38, "bonus": True,  "rate": 23},
    {"rank": 3, "name": "David L.",    "signed": 1, "commission": 89.46,  "bonus": False, "rate": 18},
]


@router.get("/closer/demo/slots", response_class=HTMLResponse)
def closer_demo_slots(request: Request):
    """Page de sélection de créneaux — aperçu démo."""
    leaderboard_rows = ""
    for r in _DEMO_LEADERBOARD:
        is_me = r["name"] == "Marie Martin"
        bonus_badge = ('<span style="background:#2ecc7120;color:#2ecc71;font-size:9px;'
                       'font-weight:600;padding:1px 5px;border-radius:8px;margin-left:4px">+5% bonus</span>'
                       ) if r["bonus"] else ""
        leaderboard_rows += (
            f'<tr style="background:{"#6366f115" if is_me else "transparent"};'
            f'border-bottom:1px solid #1a1a2e">'
            f'<td style="padding:10px 14px;color:{"#a5b4fc" if r["bonus"] else "#9ca3af"};'
            f'font-size:13px;font-weight:{"700" if is_me else "400"}">'
            f'{"🥇" if r["rank"]==1 else "🥈" if r["rank"]==2 else f"#{r[\"rank\"]}"}</td>'
            f'<td style="padding:10px 14px;color:#fff;font-size:13px;font-weight:{"700" if is_me else "400"}">'
            f'{r["name"]}{" (moi)" if is_me else ""}{bonus_badge}</td>'
            f'<td style="padding:10px 14px;color:#2ecc71;font-size:13px;text-align:right">{r["signed"]} deals</td>'
            f'<td style="padding:10px 14px;color:#9ca3af;font-size:12px;text-align:right">'
            f'{r["commission"]:.0f}€ — {r["rate"]}%</td>'
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
          letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Ce mois</th>
      <th style="padding:8px 14px;text-align:right;color:#555;font-size:10px;font-weight:600;
          letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Commissions</th>
    </tr></thead>
    <tbody>{leaderboard_rows}</tbody>
    </table></div>
    <p style="color:#555;font-size:11px;line-height:1.5">
      Les 2 premiers closers du mois reçoivent un bonus de +5% sur toutes leurs commissions du mois.
    </p>
  </div>
</div>

</div>
<script>
function claimSlot(id){{
  alert('Démo uniquement — sur la vraie page, ce créneau serait réservé à votre nom.\\n\\nRègle anti-consécutif : impossible de prendre deux créneaux d\\'affilée.');
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
        "earned": 497 * commission_rate, "pending": 0.0,
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
        bonus_badge = ('<span style="background:#2ecc7120;color:#2ecc71;font-size:9px;'
                       'font-weight:600;padding:1px 5px;border-radius:8px;margin-left:4px">+5%</span>'
                       ) if r["bonus"] else ""
        leaderboard_rows_demo += (
            f'<tr style="background:{"#6366f115" if is_me else "transparent"};border-bottom:1px solid #1a1a2e">'
            f'<td style="padding:10px 14px;color:{"#a5b4fc" if r["bonus"] else "#9ca3af"};font-size:13px">'
            f'{"🥇" if r["rank"]==1 else "🥈" if r["rank"]==2 else f"#{r[\"rank\"]}"}</td>'
            f'<td style="padding:10px 14px;color:#fff;font-size:13px;font-weight:{"700" if is_me else "400"}">'
            f'{r["name"]}{" (moi)" if is_me else ""}{bonus_badge}</td>'
            f'<td style="padding:10px 14px;color:#2ecc71;font-size:13px;text-align:right">{r["signed"]}</td>'
            f'<td style="padding:10px 14px;color:#9ca3af;font-size:12px;text-align:right">'
            f'{r["commission"]:.0f}€ — {r["rate"]}%</td>'
            f'</tr>'
        )

    panel_leaderboard_demo = f"""
<div style="margin-bottom:16px">
  <a href="/closer/demo/slots" style="display:inline-block;background:#8b5cf6;color:#fff;
    text-decoration:none;padding:10px 20px;border-radius:6px;font-size:13px;font-weight:600">
    Choisir mes créneaux →</a>
</div>
<h3 style="color:#fff;font-size:14px;margin-bottom:16px">Classement ce mois-ci</h3>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden;margin-bottom:16px">
<table style="width:100%;border-collapse:collapse">
<thead><tr>
  <th style="padding:8px 14px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;border-bottom:1px solid #2a2a4e"></th>
  <th style="padding:8px 14px;text-align:left;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Closer</th>
  <th style="padding:8px 14px;text-align:right;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Deals</th>
  <th style="padding:8px 14px;text-align:right;color:#555;font-size:10px;font-weight:600;letter-spacing:.08em;border-bottom:1px solid #2a2a4e">Commissions</th>
</tr></thead>
<tbody>{leaderboard_rows_demo}</tbody>
</table></div>
<p style="color:#555;font-size:12px;line-height:1.5">
  Les 2 premiers closers du mois reçoivent +5% de commission sur tous leurs deals du mois en cours.
</p>"""

    TABS = [("rdv","Mes RDV"),("commissions","Commissions"),("offre","L'offre"),("script","Script"),("objections","Objections"),("classement","Classement")]

    def _tab_btn(slug, label, active="rdv"):
        a = slug == active
        return (f'<button onclick="switchTab(\'{slug}\')" id="tab-{slug}" '
                f'style="padding:8px 16px;border:none;border-radius:6px;cursor:pointer;font-size:12px;'
                f'font-weight:{"700" if a else "400"};background:{"#6366f1" if a else "#1a1a2e"};'
                f'color:{"#fff" if a else "#9ca3af"};border:1px solid {"#6366f1" if a else "#2a2a4e"}">{label}</button>')

    tabs_html = f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px">{"".join(_tab_btn(s,l) for s,l in TABS)}</div>'

    panels = {"rdv": panel_rdv, "commissions": panel_commissions,
              "offre": panel_offre, "script": panel_script, "objections": panel_objections,
              "classement": panel_leaderboard_demo}
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
            "date_of_birth": date_of_birth,
        }

        from marketing_module.database import SessionLocal as MktSession, db_create_application
        with MktSession() as mdb:
            app = db_create_application(mdb, data)

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
        "commission_info": "18% par deal signé.",
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
            leaderboard_rows_real += (
                f'<tr style="background:{"#6366f115" if is_me else "transparent"};border-bottom:1px solid #1a1a2e">'
                f'<td style="padding:10px 14px;color:{"#a5b4fc" if r["bonus"] else "#9ca3af"};font-size:13px">'
                f'{"🥇" if r["rank"]==1 else "🥈" if r["rank"]==2 else f"#{r[\"rank\"]}"}</td>'
                f'<td style="padding:10px 14px;color:#fff;font-size:13px;font-weight:{"700" if is_me else "400"}">'
                f'{r["name"]}{" (moi)" if is_me else ""}{bonus_badge}</td>'
                f'<td style="padding:10px 14px;color:#2ecc71;font-size:13px;text-align:right">{r["signed"]}</td>'
                f'<td style="padding:10px 14px;color:#9ca3af;font-size:12px;text-align:right">'
                f'{r["commission"]:.0f}€ — {r["effective_rate"]*100:.0f}%</td>'
                f'</tr>'
            )
    except Exception:
        leaderboard_rows_real = '<tr><td colspan="4" style="padding:20px;text-align:center;color:#555">Données non disponibles</td></tr>'

    panel_leaderboard = f"""
<div style="margin-bottom:16px">
  <a href="/closer/{token}/slots" style="display:inline-block;background:#8b5cf6;color:#fff;
    text-decoration:none;padding:10px 20px;border-radius:6px;font-size:13px;font-weight:600">
    Choisir mes créneaux →</a>
  {'<span style="margin-left:12px;color:#a5b4fc;font-size:12px">Votre rang : #' + my_rank + '</span>' if my_rank != "—" else ""}
</div>
<h3 style="color:#fff;font-size:14px;margin-bottom:16px">Classement ce mois-ci</h3>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden;margin-bottom:16px">
<table style="width:100%;border-collapse:collapse">
<thead><tr>
  <th style="padding:8px 14px;text-align:left;color:#555;font-size:10px;border-bottom:1px solid #2a2a4e"></th>
  <th style="padding:8px 14px;text-align:left;color:#555;font-size:10px;border-bottom:1px solid #2a2a4e">Closer</th>
  <th style="padding:8px 14px;text-align:right;color:#555;font-size:10px;border-bottom:1px solid #2a2a4e">Deals</th>
  <th style="padding:8px 14px;text-align:right;color:#555;font-size:10px;border-bottom:1px solid #2a2a4e">Commissions</th>
</tr></thead>
<tbody>{"".join(leaderboard_rows_real) if leaderboard_rows_real else '<tr><td colspan="4" style="padding:20px;text-align:center;color:#555">Aucun classement ce mois</td></tr>'}</tbody>
</table></div>
<p style="color:#555;font-size:12px;line-height:1.5">
  Les 2 premiers closers du mois reçoivent +5% de commission sur tous leurs deals du mois en cours.
</p>"""

    # ── Onglets ───────────────────────────────────────────────────────────────
    TABS = [("rdv", "Mes RDV"), ("commissions", "Commissions"),
            ("offre", "L'offre"), ("script", "Script"), ("objections", "Objections"),
            ("classement", "Classement")]

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

    panel_commissions = f"""
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px">
  <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#2ecc71">{stats["earned"]:.0f}€</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Gagné (tous temps)</div>
  </div>
  <div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:2rem;font-weight:700;color:#6366f1">{stats["pending"]:.0f}€</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">En attente (RDV à venir)</div>
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
        "classement":  panel_leaderboard,
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
  classement: `{panels_js["classement"]}`,
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
    meeting = None
    prospect = None

    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import MeetingDB, ProspectDeliveryDB
        from ...database import SessionLocal
        from ...models import V3ProspectDB

        with MktSession() as mdb:
            meeting = mdb.query(MeetingDB).filter_by(id=meeting_id).first()
            deliveries = []
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
    phone = prospect.phone if prospect else ""

    # Timeline comportementale
    timeline = ""
    try:
        for d in deliveries:
            items = []
            if d.sent_at:    items.append(f'<li>📧 Envoyé {_fmt(d.sent_at)}</li>')
            if d.opened_at:  items.append(f'<li style="color:#f59e0b">👁 Ouvert {_fmt(d.opened_at)}</li>')
            if d.clicked_at: items.append(f'<li style="color:#2ecc71">🖱 Clic landing {_fmt(d.clicked_at)}</li>')
            lv = getattr(d, "landing_visited_at", None)
            if lv:           items.append(f'<li style="color:#2ecc71">🌐 Landing visitée {_fmt(lv)}</li>')
            cc = getattr(d, "calendly_clicked_at", None)
            if cc:           items.append(f'<li style="color:#6366f1">📅 Calendly cliqué {_fmt(cc)}</li>')
            timeline += "".join(items)
    except Exception:
        pass

    # Guide RDV
    rdv_guide_lines = "".join(
        f'<div style="padding:6px 0;border-bottom:1px solid #1a1a2e;color:{"#6366f1" if ln.startswith(("AVANT","PENDANT","FIN","1.","2.","3.","4.","5.","6.","7.","8.","9.")) else "#ccc"};font-size:12px;line-height:1.5">{ln}</div>'
        if ln.strip() else '<div style="height:6px"></div>'
        for ln in content.get("rdv_guide", "").split("\n")
    )

    phone_btn = (
        f'<a href="tel:{phone}" style="display:inline-block;margin-top:6px;padding:6px 14px;'
        f'background:#6366f120;border:1px solid #6366f140;border-radius:4px;'
        f'color:#6366f1;font-size:12px;text-decoration:none">📞 Appeler {phone}</a>'
    ) if phone else ""

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fiche RDV — {name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
.card{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;margin-bottom:16px}}
.sec{{color:#9ca3af;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px}}
</style></head><body>

<div style="background:#1a1a2e;border-bottom:1px solid #2a2a4e;padding:14px 24px;
            display:flex;align-items:center;justify-content:space-between">
  <img src="/assets/logo.svg" alt="Présence IA" style="height:24px">
  <a href="/closer/{closer_token}" style="color:#527FB3;font-size:12px;text-decoration:none">← Mes RDV</a>
</div>

<div style="max-width:780px;margin:0 auto;padding:28px 20px">

<!-- En-tête prospect -->
<div style="margin-bottom:20px">
  <h1 style="color:#fff;font-size:20px;margin-bottom:4px">{name}</h1>
  <p style="color:#9ca3af;font-size:13px">{city} · {prof}</p>
  <p style="color:#555;font-size:12px;margin-top:2px">{email}</p>
  {phone_btn}
</div>

<!-- Bloc RDV -->
<div class="card" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:16px;text-align:center">
  <div>
    <div style="color:#f59e0b;font-size:1.2rem;font-weight:700">{_fmt(meeting.scheduled_at)}</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Date RDV</div>
  </div>
  <div>
    {_meeting_badge(meeting.status)}
    <div style="color:#9ca3af;font-size:11px;margin-top:6px">Statut</div>
  </div>
  <div>
    <div style="color:#2ecc71;font-size:1.2rem;font-weight:700">
      {"{}€".format(int(meeting.deal_value)) if meeting.deal_value else "—"}
    </div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Deal</div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">

<!-- Historique prospect -->
<div class="card">
  <p class="sec">Comportement du prospect</p>
  <ul style="list-style:none;display:flex;flex-direction:column;gap:3px;font-size:12px">
    {timeline or '<li style="color:#555">Aucun historique</li>'}
  </ul>
</div>

<!-- Notes -->
<div class="card">
  <p class="sec">Notes</p>
  <p style="color:#ccc;font-size:13px;line-height:1.5">{meeting.notes or "Aucune note"}</p>
  {f'<p style="color:#9ca3af;font-size:12px;margin-top:8px">{meeting.outcome}</p>' if getattr(meeting,"outcome","") else ""}
</div>

</div>

<!-- Guide RDV -->
<div class="card">
  <p class="sec">Fiche RDV — Aide-mémoire</p>
  <div>{rdv_guide_lines or '<p style="color:#555;font-size:12px">Guide non configuré — rendez-vous dans l\'admin → Contenu portail</p>'}</div>
</div>

</div></body></html>""")


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
        lb_rows += (
            f'<tr style="background:{"#6366f115" if is_me else "transparent"};border-bottom:1px solid #1a1a2e">'
            f'<td style="padding:8px 12px;font-size:12px;color:#9ca3af">'
            f'{"🥇" if r["rank"]==1 else "🥈" if r["rank"]==2 else f"#{r[\"rank\"]}"}</td>'
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
<p style="color:#555;font-size:11px;margin-bottom:24px">
  ⚠️ Vous ne pouvez pas prendre deux créneaux consécutifs (règle anti-consécutif : 25 min minimum entre vos créneaux).
</p>

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
