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
    """Page de présentation du programme closer (contenu à remplir)."""
    return HTMLResponse("""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Programme Closer — Présence IA</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0;min-height:100vh}
.hero{text-align:center;padding:80px 20px 60px;max-width:800px;margin:0 auto}
h1{font-size:clamp(2rem,5vw,3rem);color:#fff;margin-bottom:16px;line-height:1.2}
.sub{color:#9ca3af;font-size:1.1rem;margin-bottom:40px;line-height:1.6}
.btn{display:inline-block;background:#6366f1;color:#fff;padding:14px 40px;
     border-radius:8px;text-decoration:none;font-weight:700;font-size:1rem}
.section{max-width:900px;margin:0 auto;padding:60px 20px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px;margin-top:32px}
.card{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:24px}
.card h3{color:#fff;margin-bottom:8px}
.card p{color:#9ca3af;font-size:0.9rem;line-height:1.5}
.badge{display:inline-block;background:#6366f120;color:#6366f1;padding:4px 12px;
       border-radius:20px;font-size:0.85rem;font-weight:600;margin-bottom:20px}
</style>
</head><body>

<div class="hero">
  <span class="badge">Opportunité — Closer Présence IA</span>
  <h1>Devenez Closer<br>Présence IA</h1>
  <p class="sub">
    Rejoignez notre équipe de commerciaux indépendants et accompagnez<br>
    les artisans et PME locales dans leur visibilité sur les IA.
  </p>
  <a href="/closer/recruit" class="btn">Postuler maintenant →</a>
</div>

<div class="section">
  <h2 style="color:#fff;text-align:center;margin-bottom:8px">Ce que vous ferez</h2>
  <p style="color:#9ca3af;text-align:center;margin-bottom:32px">
    Les rendez-vous sont déjà pris. Votre rôle : convaincre et closer.
  </p>
  <div class="cards">
    <div class="card">
      <h3>RDV qualifiés fournis</h3>
      <p>Nous gérons la prospection et la prise de RDV. Vous arrivez avec un prospect chaud prêt à signer.</p>
    </div>
    <div class="card">
      <h3>Commission attractive</h3>
      <p>18% sur chaque deal + 5% de bonus sur les deals dépassant l'objectif mensuel.</p>
    </div>
    <div class="card">
      <h3>Scripts &amp; objections</h3>
      <p>Formation complète fournie : script de vente, réponses aux objections, accès aux outils.</p>
    </div>
    <div class="card">
      <h3>100% télétravail</h3>
      <p>Les calls se font en visio. Travaillez depuis n'importe où, aux heures qui vous conviennent.</p>
    </div>
  </div>
</div>

<div style="text-align:center;padding:60px 20px">
  <a href="/closer/recruit" class="btn">Je postule →</a>
</div>

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
<div class="wrap">
  <a href="/closer" style="color:#527FB3;font-size:12px;text-decoration:none">← Programme closer</a>
  <h1 style="margin-top:16px">Candidature Closer</h1>
  <p class="sub">Remplissez ce formulaire. Nous vous répondrons sous 48h.</p>

  <form id="form" method="post" action="/closer/recruit" enctype="multipart/form-data">

    <div class="section-title">Vos informations</div>

    <div class="row">
      <div class="field">
        <label>Prénom *</label>
        <input type="text" name="first_name" required placeholder="Marie">
      </div>
      <div class="field">
        <label>Nom *</label>
        <input type="text" name="last_name" required placeholder="Dupont">
      </div>
    </div>

    <div class="field">
      <label>Email *</label>
      <input type="email" name="email" required placeholder="vous@exemple.com">
    </div>

    <div class="field">
      <label>Téléphone</label>
      <input type="tel" name="phone" placeholder="+33 6 12 34 56 78">
    </div>

    <div class="row">
      <div class="field">
        <label>Ville</label>
        <input type="text" name="city" placeholder="Paris">
      </div>
      <div class="field">
        <label>Pays</label>
        <input type="text" name="country" value="FR" placeholder="FR">
      </div>
    </div>

    <div class="field">
      <label>LinkedIn (optionnel)</label>
      <input type="url" name="linkedin_url" placeholder="https://linkedin.com/in/...">
    </div>

    <div class="section-title">Votre présentation</div>

    <div class="field">
      <label>Message de présentation *</label>
      <textarea name="message" required placeholder="Présentez-vous, votre expérience en vente/closing, pourquoi ce programme vous intéresse..."></textarea>
    </div>

    <div class="field">
      <label>Lien vidéo de présentation (YouTube, Loom, Drive…)</label>
      <input type="url" name="video_url" placeholder="https://loom.com/share/...">
      <p class="hint">2-3 minutes max. Présentez-vous et expliquez votre motivation.</p>
    </div>

    <div class="field">
      <label>Message audio (optionnel)</label>
      <input type="file" name="audio_file" accept="audio/*" style="padding:8px">
      <p class="hint">Fichier audio .mp3 ou .m4a — 5 Mo max</p>
    </div>

    <button type="submit" class="btn">Envoyer ma candidature →</button>
  </form>
</div>

<script>
document.getElementById('form').addEventListener('submit', async function(e) {
  e.preventDefault();
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

        data = {
            "project_id":   PROJECT_ID,
            "first_name":   form.get("first_name", "").strip() or None,
            "last_name":    form.get("last_name", "").strip() or None,
            "email":        form.get("email", "").strip() or None,
            "phone":        form.get("phone", "").strip() or None,
            "city":         form.get("city", "").strip() or None,
            "country":      form.get("country", "FR").strip() or "FR",
            "linkedin_url": form.get("linkedin_url", "").strip() or None,
            "message":      form.get("message", "").strip() or None,
            "video_url":    form.get("video_url", "").strip() or None,
            "audio_url":    audio_url,
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


@router.get("/closer/{token}", response_class=HTMLResponse)
def closer_portal(token: str, request: Request):
    """Portail closer — liste de ses RDV + stats."""
    preview = request.query_params.get("preview")

    closer = _get_closer_by_token(token)
    if not closer and not preview:
        return HTMLResponse("<p style='font-family:sans-serif;padding:40px;color:#666'>Lien invalide.</p>",
                            status_code=404)

    name = getattr(closer, "name", "Closer") if closer else "Aperçu"

    meetings = []
    stats = {"total": 0, "completed": 0, "no_show": 0, "scheduled": 0, "earned": 0.0}
    try:
        from marketing_module.database import SessionLocal as MktSession
        from marketing_module.models import MeetingDB, MeetingStatus
        from ...database import SessionLocal
        from ...models import V3ProspectDB

        with MktSession() as mdb:
            q = mdb.query(MeetingDB).filter_by(project_id=PROJECT_ID)
            if closer:
                q = q.filter_by(closer_id=closer.id)
            mtgs = q.order_by(MeetingDB.scheduled_at.desc()).limit(50).all()

            with SessionLocal() as db:
                for m in mtgs:
                    prospect = db.query(V3ProspectDB).filter_by(token=m.prospect_id).first()
                    meetings.append({
                        "id": m.id,
                        "name": prospect.name if prospect else m.prospect_id[:12],
                        "city": prospect.city if prospect else "—",
                        "profession": prospect.profession if prospect else "—",
                        "scheduled_at": m.scheduled_at.strftime("%d/%m/%y %H:%M") if m.scheduled_at else "—",
                        "status": m.status,
                        "deal_value": m.deal_value,
                        "notes": m.notes or "",
                    })
                    stats["total"] += 1
                    if m.status == MeetingStatus.completed:
                        stats["completed"] += 1
                        if m.deal_value:
                            rate = getattr(closer, "commission_rate", 0.18) if closer else 0.18
                            stats["earned"] += m.deal_value * rate
                    elif m.status == MeetingStatus.no_show:
                        stats["no_show"] += 1
                    elif m.status == MeetingStatus.scheduled:
                        stats["scheduled"] += 1
    except Exception:
        pass

    conv_rate = f"{stats['completed']/stats['total']*100:.0f}%" if stats["total"] else "—"

    mtg_rows = "".join(
        f'<tr style="border-bottom:1px solid #1a1a2e;cursor:pointer" '
        f'onclick="window.location=\'/closer/{token}/meeting/{m["id"]}\'">'
        f'<td style="padding:12px 16px;color:#fff;font-size:13px">'
        f'{m["name"]}<div style="color:#6b7280;font-size:11px">{m["city"]} · {m["profession"]}</div></td>'
        f'<td style="padding:12px 16px;color:#9ca3af;font-size:12px">{m["scheduled_at"]}</td>'
        f'<td style="padding:12px 16px">{_meeting_badge(m["status"])}</td>'
        f'<td style="padding:12px 16px;color:{"#2ecc71" if m["deal_value"] else "#555"};font-size:12px">'
        f'{"{}€".format(int(m["deal_value"])) if m["deal_value"] else "—"}</td>'
        f'</tr>'
        for m in meetings
    ) or '<tr><td colspan="4" style="padding:40px;text-align:center;color:#555">Aucun RDV pour le moment</td></tr>'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} — Portail Closer</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
table{{width:100%;border-collapse:collapse}}
th{{padding:10px 16px;text-align:left;color:#9ca3af;font-size:10px;font-weight:600;
   letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #2a2a4e}}
tr:hover{{background:#111127}}
</style></head><body>

<div style="background:#1a1a2e;border-bottom:1px solid #2a2a4e;padding:16px 24px;
            display:flex;align-items:center;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:12px">
    <img src="/assets/logo.svg" alt="Présence IA" style="height:28px">
    <span style="color:#9ca3af;font-size:12px">Portail Closer</span>
  </div>
  <span style="color:#fff;font-weight:600">{name}</span>
</div>

<div style="max-width:900px;margin:0 auto;padding:32px 20px">

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:32px">
  {"".join(
    f'<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;text-align:center">'
    f'<div style="font-size:1.8rem;font-weight:700;color:{c}">{v}</div>'
    f'<div style="color:#9ca3af;font-size:11px;margin-top:4px">{l}</div></div>'
    for v, l, c in [
        (stats["scheduled"],  "RDV à venir",    "#6366f1"),
        (stats["completed"],  "Signés",          "#2ecc71"),
        (stats["no_show"],    "No-show",         "#e94560"),
        (conv_rate,           "Taux conversion", "#e9a020"),
        (f'{stats["earned"]:.0f}€', "Commissions", "#527FB3"),
    ]
  )}
</div>

<h2 style="color:#fff;font-size:16px;margin-bottom:16px">Mes rendez-vous</h2>
<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;overflow:hidden">
<table><thead><tr>
  <th>Prospect</th><th>Date</th><th>Statut</th><th>Deal</th>
</tr></thead>
<tbody>{mtg_rows}</tbody></table></div>

</div></body></html>""")


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

    def _fmt(dt):
        return dt.strftime("%d/%m/%y %H:%M") if dt else "—"

    name  = prospect.name if prospect else "—"
    city  = prospect.city if prospect else "—"
    prof  = prospect.profession if prospect else "—"
    email = prospect.email if prospect else "—"

    # Historique livraisons (timeline comportementale)
    timeline = ""
    try:
        for d in deliveries:
            items = []
            if d.sent_at:    items.append(f'<li style="color:#6366f1">Envoyé {_fmt(d.sent_at)}</li>')
            if d.opened_at:  items.append(f'<li style="color:#f59e0b">Ouvert {_fmt(d.opened_at)}</li>')
            if d.clicked_at: items.append(f'<li style="color:#2ecc71">Clic landing {_fmt(d.clicked_at)}</li>')
            timeline += "".join(items)
    except Exception:
        pass

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Fiche RDV — {name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
</style></head><body>

<div style="background:#1a1a2e;border-bottom:1px solid #2a2a4e;padding:16px 24px">
  <img src="/assets/logo.svg" alt="Présence IA" style="height:24px">
</div>

<div style="max-width:700px;margin:0 auto;padding:32px 20px">
<a href="/closer/{closer_token}" style="color:#527FB3;font-size:12px;text-decoration:none">← Mes RDV</a>

<h1 style="color:#fff;font-size:22px;margin:16px 0 4px">{name}</h1>
<p style="color:#9ca3af">{city} · {prof}</p>
<p style="color:#555;font-size:12px;margin-top:4px">{email}</p>

<div style="margin:24px 0;padding:16px;background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;
            display:grid;grid-template-columns:repeat(3,1fr);gap:16px;text-align:center">
  <div>
    <div style="color:#f59e0b;font-size:1.1rem;font-weight:700">{_fmt(meeting.scheduled_at)}</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Date RDV</div>
  </div>
  <div>
    <div>{_meeting_badge(meeting.status)}</div>
    <div style="color:#9ca3af;font-size:11px;margin-top:8px">Statut</div>
  </div>
  <div>
    <div style="color:#2ecc71;font-size:1.1rem;font-weight:700">
      {"{}€".format(int(meeting.deal_value)) if meeting.deal_value else "—"}
    </div>
    <div style="color:#9ca3af;font-size:11px;margin-top:4px">Deal</div>
  </div>
</div>

{'<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px;margin-bottom:20px"><p style="color:#9ca3af;font-size:10px;text-transform:uppercase;margin-bottom:8px">Notes</p><p style="color:#ccc;line-height:1.5">' + (meeting.notes or "Aucune note") + '</p></div>'}

<div style="background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:16px">
<p style="color:#9ca3af;font-size:10px;text-transform:uppercase;margin-bottom:12px">Historique du prospect</p>
<ul style="list-style:none;display:flex;flex-direction:column;gap:4px;font-size:12px">
{timeline or '<li style="color:#555">Aucun historique disponible</li>'}
</ul>
</div>

</div></body></html>""")
