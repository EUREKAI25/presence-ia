"""Admin — /admin/sequences : gérer les séquences email/SMS."""
import json, os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from ...database import get_db
from ._nav import admin_nav, admin_token

router = APIRouter(tags=["Admin Sequences"])

MKT_BASE = "http://127.0.0.1:8001/mkt"
PROJECT_ID = os.getenv("MKT_PROJECT_ID", "presence_ia")


def _check(request: Request):
    t = (request.headers.get("X-Admin-Token")
         or request.query_params.get("token")
         or request.cookies.get("admin_token", ""))
    if t != admin_token():
        raise HTTPException(403, "Acces refuse")


def _mkt_get(path: str):
    import requests as _req
    r = _req.get(f"{MKT_BASE}{path}", timeout=10)
    if r.ok:
        return r.json().get("result", [])
    return []


def _mkt_post(path: str, data: dict):
    import requests as _req
    r = _req.post(f"{MKT_BASE}{path}", json=data, timeout=10)
    return r.ok, r.json() if r.ok else {}


def _mkt_patch(path: str, data: dict):
    import requests as _req
    r = _req.patch(f"{MKT_BASE}{path}", json=data, timeout=10)
    return r.ok


def _mkt_delete(path: str):
    import requests as _req
    r = _req.delete(f"{MKT_BASE}{path}", timeout=10)
    return r.ok


CHANNEL_COLOR = {"email": "#3b82f6", "sms": "#10b981"}
CHANNEL_LABEL = {"email": "Email", "sms": "SMS"}


def _step_card(step: dict, seq_id: str, token: str) -> str:
    ch = step.get("channel", "email")
    badge = (f'<span style="background:{CHANNEL_COLOR.get(ch,"#888")};color:#fff;'
             f'padding:1px 7px;border-radius:3px;font-size:11px">{CHANNEL_LABEL.get(ch, ch)}</span>')
    subject = step.get("subject") or step.get("subject_template") or ""
    body = (step.get("body_text") or step.get("body_template") or "")[:80]
    delay = step.get("delay_days", 0)
    step_id = step.get("id", "")
    order = step.get("step_number") or step.get("step_order") or 1
    return f"""
<div id="step-{step_id}" style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:6px;
     padding:12px 16px;margin-bottom:8px;display:flex;align-items:flex-start;gap:12px">
  <div style="display:flex;flex-direction:column;gap:4px;min-width:90px">
    {badge}
    <span style="font-size:11px;color:#6b7280">J+{delay}</span>
    <span style="font-size:10px;color:#9ca3af">ordre {order}</span>
  </div>
  <div style="flex:1;min-width:0">
    <div style="font-size:13px;font-weight:600;color:#1a1a2e;margin-bottom:2px">{subject or "(pas d objet)"}</div>
    <div style="font-size:12px;color:#6b7280;white-space:pre-wrap">{body}...</div>
  </div>
  <div style="display:flex;gap:6px;flex-shrink:0">
    <button onclick="editStep('{seq_id}','{step_id}',{json.dumps(step)})"
      style="background:#fff;border:1px solid #d1d5db;padding:4px 10px;border-radius:4px;
             font-size:12px;cursor:pointer">Modifier</button>
    <button onclick="deleteStep('{seq_id}','{step_id}')"
      style="background:#fff;border:1px solid #fca5a5;color:#dc2626;padding:4px 8px;
             border-radius:4px;font-size:12px;cursor:pointer">X</button>
  </div>
</div>"""


def _sequence_block(seq: dict, token: str) -> str:
    seq_id = seq.get("id", "")
    name = seq.get("name", "")
    active = seq.get("is_active", True)
    steps = seq.get("steps", [])
    email_steps = [s for s in steps if s.get("channel", "email") == "email"]
    sms_steps = [s for s in steps if s.get("channel", "sms") == "sms"]

    def _col(title, color, ch_steps, ch):
        cards = "".join(_step_card(s, seq_id, token) for s in ch_steps)
        return f"""
<div style="flex:1;min-width:280px">
  <div style="font-size:12px;font-weight:700;color:{color};margin-bottom:8px;
              text-transform:uppercase;letter-spacing:.05em">{title} ({len(ch_steps)})</div>
  {cards if cards else '<div style="font-size:12px;color:#9ca3af;font-style:italic">Aucune etape</div>'}
  <button onclick="addStep('{seq_id}','{ch}')"
    style="margin-top:8px;background:{color};color:#fff;border:none;padding:6px 14px;
           border-radius:5px;font-size:12px;cursor:pointer">+ Ajouter email</button>
</div>"""

    badge_active = (
        f'<span style="background:#d1fae5;color:#065f46;padding:2px 8px;border-radius:3px;font-size:11px">Actif</span>'
        if active else
        f'<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:3px;font-size:11px">Inactif</span>'
    )
    toggle_label = "Desactiver" if active else "Activer"

    return f"""
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:20px">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
    <strong style="font-size:15px">{name}</strong>
    {badge_active}
    <div style="margin-left:auto;display:flex;gap:8px">
      <button onclick="toggleSeq('{seq_id}', {str(not active).lower()})"
        style="background:#fff;border:1px solid #d1d5db;padding:5px 12px;border-radius:4px;font-size:12px;cursor:pointer">
        {toggle_label}</button>
      <button onclick="deleteSeq('{seq_id}')"
        style="background:#fff;border:1px solid #fca5a5;color:#dc2626;padding:5px 10px;
               border-radius:4px;font-size:12px;cursor:pointer">Supprimer</button>
    </div>
  </div>
  <div style="display:flex;gap:20px;flex-wrap:wrap">
    {_col("Emails", "#3b82f6", email_steps, "email")}
    {_col("SMS", "#10b981", sms_steps, "sms")}
  </div>
</div>"""


@router.get("/admin/sequences", response_class=HTMLResponse)
def admin_sequences(request: Request, db: Session = Depends(get_db)):
    _check(request)
    token = request.query_params.get("token", admin_token())

    sequences_raw = _mkt_get(f"/sequences?project_id={PROJECT_ID}")
    if not isinstance(sequences_raw, list):
        sequences_raw = []

    # Charger les steps pour chaque séquence
    sequences = []
    for s in sequences_raw:
        detail = _mkt_get(f"/sequences/{s['id']}")
        if isinstance(detail, dict):
            sequences.append(detail)
        else:
            sequences.append(s)

    blocks = "".join(_sequence_block(s, token) for s in sequences)
    if not blocks:
        blocks = '<p style="color:#9ca3af;font-style:italic">Aucune séquence. Créez-en une ci-dessous.</p>'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Sequences — PRESENCE_IA</title>
<style>
  *{{box-sizing:border-box}}
  body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;margin:0;color:#1a1a2e}}
  .modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:100;align-items:center;justify-content:center}}
  .modal.open{{display:flex}}
  .modal-box{{background:#fff;border-radius:10px;padding:28px;width:540px;max-width:95vw;max-height:90vh;overflow-y:auto}}
  label{{font-size:13px;font-weight:600;display:block;margin-bottom:4px}}
  input,select,textarea{{width:100%;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;margin-bottom:14px}}
  textarea{{font-family:monospace;resize:vertical}}
  .btn-primary{{background:#e94560;color:#fff;border:none;padding:9px 20px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600}}
  .btn-cancel{{background:#fff;border:1px solid #d1d5db;padding:9px 16px;border-radius:6px;cursor:pointer;font-size:13px}}
</style>
</head><body>
{admin_nav(token, "sequences")}

<div style="max-width:1000px;margin:32px auto;padding:0 20px">
  <div style="display:flex;align-items:center;gap:16px;margin-bottom:24px">
    <h1 style="font-size:18px;margin:0">Sequences email &amp; SMS</h1>
    <button onclick="document.getElementById('modal-new').classList.add('open')"
      style="background:#e94560;color:#fff;border:none;padding:8px 18px;border-radius:6px;
             font-size:13px;cursor:pointer;font-weight:600">+ Nouvelle sequence</button>
  </div>
  <div id="sequences-list">{blocks}</div>
</div>

<!-- Modal nouvelle séquence -->
<div class="modal" id="modal-new">
  <div class="modal-box">
    <h2 style="margin:0 0 20px;font-size:16px">Nouvelle sequence</h2>
    <label>Nom</label>
    <input id="new-name" placeholder="Ex: Sequence prospection Brest">
    <div style="display:flex;gap:10px;justify-content:flex-end">
      <button class="btn-cancel" onclick="document.getElementById('modal-new').classList.remove('open')">Annuler</button>
      <button class="btn-primary" onclick="createSeq()">Creer</button>
    </div>
  </div>
</div>

<!-- Modal ajouter/modifier étape -->
<div class="modal" id="modal-step">
  <div class="modal-box">
    <h2 style="margin:0 0 20px;font-size:16px" id="modal-step-title">Ajouter une etape</h2>
    <input type="hidden" id="step-seq-id">
    <input type="hidden" id="step-id">
    <label>Canal</label>
    <select id="step-channel" onchange="toggleSubject()">
      <option value="email">Email</option>
      <option value="sms">SMS</option>
    </select>
    <label>Delai (jours apres l etape precedente)</label>
    <input type="number" id="step-delay" value="0" min="0">
    <label>Ordre</label>
    <input type="number" id="step-order" value="1" min="1">
    <div id="subject-row">
      <label>Objet</label>
      <input id="step-subject" placeholder="Ex: Votre visibilite sur les IA">
    </div>
    <label>Corps (texte)</label>
    <textarea id="step-body" rows="7" placeholder="Bonjour {{first_name}},&#10;..."></textarea>
    <div style="font-size:11px;color:#9ca3af;margin-top:-10px;margin-bottom:14px">
      Placeholders : {{first_name}} {{company_name}} {{city}} {{profession}} {{calendly_link}} {{sender_name}}
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end">
      <button class="btn-cancel" onclick="document.getElementById('modal-step').classList.remove('open')">Annuler</button>
      <button class="btn-primary" onclick="saveStep()">Enregistrer</button>
    </div>
  </div>
</div>

<script>
const TOKEN = "{token}";
const MKT = "/mkt";
const PROJECT = "{PROJECT_ID}";

function toggleSubject() {{
  const ch = document.getElementById('step-channel').value;
  document.getElementById('subject-row').style.display = ch === 'email' ? 'block' : 'none';
}}

function addStep(seqId, channel) {{
  document.getElementById('modal-step-title').textContent = 'Ajouter une etape';
  document.getElementById('step-seq-id').value = seqId;
  document.getElementById('step-id').value = '';
  document.getElementById('step-channel').value = channel;
  document.getElementById('step-delay').value = 0;
  document.getElementById('step-order').value = 1;
  document.getElementById('step-subject').value = '';
  document.getElementById('step-body').value = '';
  toggleSubject();
  document.getElementById('modal-step').classList.add('open');
}}

function editStep(seqId, stepId, step) {{
  document.getElementById('modal-step-title').textContent = 'Modifier l etape';
  document.getElementById('step-seq-id').value = seqId;
  document.getElementById('step-id').value = stepId;
  document.getElementById('step-channel').value = step.channel || 'email';
  document.getElementById('step-delay').value = step.delay_days || 0;
  document.getElementById('step-order').value = step.step_number || step.step_order || 1;
  document.getElementById('step-subject').value = step.subject || step.subject_template || '';
  document.getElementById('step-body').value = step.body_text || step.body_template || '';
  toggleSubject();
  document.getElementById('modal-step').classList.add('open');
}}

async function saveStep() {{
  const seqId = document.getElementById('step-seq-id').value;
  const stepId = document.getElementById('step-id').value;
  const data = {{
    channel: document.getElementById('step-channel').value,
    delay_days: parseInt(document.getElementById('step-delay').value) || 0,
    step_number: parseInt(document.getElementById('step-order').value) || 1,
    subject: document.getElementById('step-subject').value,
    body_text: document.getElementById('step-body').value,
  }};
  let r;
  if (stepId) {{
    r = await fetch(MKT + '/sequences/' + seqId + '/steps/' + stepId, {{
      method: 'PATCH', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(data)
    }});
  }} else {{
    r = await fetch(MKT + '/sequences/' + seqId + '/steps', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{...data, sequence_id: seqId}})
    }});
  }}
  if (r.ok) {{ location.reload(); }}
  else {{ alert('Erreur : ' + await r.text()); }}
}}

async function deleteStep(seqId, stepId) {{
  if (!confirm('Supprimer cette etape ?')) return;
  const r = await fetch(MKT + '/sequences/' + seqId + '/steps/' + stepId, {{method:'DELETE'}});
  if (r.ok) {{ location.reload(); }}
}}

async function deleteSeq(seqId) {{
  if (!confirm('Supprimer toute la sequence et ses etapes ?')) return;
  const r = await fetch(MKT + '/sequences/' + seqId, {{method:'DELETE'}});
  if (r.ok) {{ location.reload(); }}
}}

async function toggleSeq(seqId, newActive) {{
  const r = await fetch(MKT + '/sequences/' + seqId, {{
    method: 'PATCH', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{is_active: newActive}})
  }});
  if (r.ok) {{ location.reload(); }}
}}

async function createSeq() {{
  const name = document.getElementById('new-name').value.trim();
  if (!name) return;
  const r = await fetch(MKT + '/sequences', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{name, project_id: PROJECT, campaign_id: 'default'}})
  }});
  if (r.ok) {{ location.reload(); }}
  else {{ alert('Erreur : ' + await r.text()); }}
}}
</script>
</body></html>""")
