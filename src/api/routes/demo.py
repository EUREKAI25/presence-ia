"""
Route /admin/demo/{campaign_id} — chantier 08
Écran de démo du flux complet : campagne, prospects, evidence, citations, landing, outreach.
"""
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...database import (
    get_db, db_get_campaign, db_list_prospects,
    db_get_evidence, db_list_runs, jl,
)
from ...generate import landing_url

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "secret")
router = APIRouter(tags=["Demo"])


def _check_admin(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(403, "Accès refusé")


def _nav(token: str) -> str:
    t = f"?token={token}"
    return (
        f'<nav style="background:#1a0a4e;padding:12px 24px;display:flex;gap:20px;align-items:center">'
        f'<span style="color:#fff;font-weight:800;font-size:16px">⚡ PRESENCE_IA</span>'
        f'<a href="/admin{t}" style="color:#aaa;font-size:13px;text-decoration:none">Dashboard</a>'
        f'<a href="/admin/contacts{t}" style="color:#aaa;font-size:13px;text-decoration:none">Contacts</a>'
        f'</nav>'
    )


def _prospect_rows(prospects, db, token: str) -> str:
    rows = ""
    for p in prospects:
        comps = jl(p.competitors_cited)
        comp_str = ", ".join(comps[:3]) or "—"
        score = p.ia_visibility_score or 0
        lurl = landing_url(p)
        runs = db_list_runs(db, p.prospect_id)
        runs_sorted = sorted(runs, key=lambda r: r.ts, reverse=True)
        last_run = runs_sorted[0] if runs_sorted else None
        mentions = jl(last_run.mention_per_query) if last_run else []
        mention_str = " ".join(["✅" if m else "❌" for m in mentions]) or "—"
        rows += (
            f"<tr>"
            f'<td style="padding:10px;font-weight:600">{p.name}</td>'
            f'<td style="padding:10px;color:#6b7280">{p.city}</td>'
            f'<td style="padding:10px">'
            f'<span style="font-size:20px;font-weight:900;color:#e94560">{score:.1f}</span>'
            f'<span style="font-size:11px;color:#6b7280">/10</span>'
            f'</td>'
            f'<td style="padding:10px;font-size:12px;color:#374151">{comp_str}</td>'
            f'<td style="padding:10px;font-size:12px">{mention_str}</td>'
            f'<td style="padding:10px">'
            f'<a href="{lurl}" target="_blank" style="background:#1a0a4e;color:#fff;padding:5px 10px;border-radius:4px;font-size:11px;text-decoration:none;margin-right:6px">Landing</a>'
            f'<button onclick="genOutreach(\'{p.prospect_id}\')" style="background:#e94560;color:#fff;padding:5px 10px;border-radius:4px;font-size:11px;border:none;cursor:pointer">Outreach</button>'
            f'</td>'
            f"</tr>"
        )
    return rows or '<tr><td colspan="6" style="padding:16px;color:#6b7280;text-align:center">Aucun prospect</td></tr>'


@router.get("/admin/demo/{campaign_id}", response_class=HTMLResponse)
def admin_demo(campaign_id: str, token: str = "", db: Session = Depends(get_db)):
    _check_admin(token)

    campaign = db_get_campaign(db, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campagne introuvable")

    prospects = db_list_prospects(db, campaign_id)
    nb_scored = sum(1 for p in prospects if p.ia_visibility_score is not None)

    # Evidence screenshots
    evidence = db_get_evidence(db, campaign.profession, campaign.city)
    ev_html = ""
    if evidence:
        imgs = jl(evidence.images)
        urls = [img.get("processed_url") or img.get("url") for img in imgs[:3] if img]
        urls = [u for u in urls if u]
        if urls:
            ev_html = '<div style="display:flex;gap:12px;flex-wrap:wrap">' + "".join(
                f'<img src="{u}" style="height:110px;border-radius:6px;object-fit:cover">' for u in urls
            ) + "</div>"
    if not ev_html:
        ev_html = '<p style="color:#6b7280;font-size:13px">Aucune preuve disponible pour ce métier × ville.</p>'

    prospect_rows = _prospect_rows(prospects, db, token)
    nav = _nav(token)
    prof_cap = campaign.profession.capitalize()
    city_cap = campaign.city.capitalize()

    return f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Démo — {prof_cap} × {city_cap}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e}}
.body{{max-width:1100px;margin:0 auto;padding:32px 24px}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.card h2{{color:#e94560;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:16px}}
table{{border-collapse:collapse;width:100%}}
th{{background:#f3f4f6;color:#6b7280;font-size:11px;padding:10px;text-align:left;font-weight:600;text-transform:uppercase}}
td{{border-bottom:1px solid #f3f4f6}}
.stat{{display:inline-block;text-align:center;padding:12px 20px}}
.stat-val{{font-size:28px;font-weight:900;color:#1a0a4e}}
.stat-lbl{{font-size:11px;color:#6b7280;text-transform:uppercase;margin-top:2px}}
#outreach-modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:100;align-items:center;justify-content:center}}
#outreach-modal.open{{display:flex}}
.modal-box{{background:#fff;border-radius:10px;padding:32px;max-width:600px;width:90%;max-height:80vh;overflow-y:auto}}
</style>
</head>
<body>
{nav}
<div class="body">

<div class="card">
  <h2>Campagne — {prof_cap} × {city_cap}</h2>
  <div>
    <div class="stat"><div class="stat-val">{prof_cap}</div><div class="stat-lbl">Métier</div></div>
    <div class="stat"><div class="stat-val">{city_cap}</div><div class="stat-lbl">Ville</div></div>
    <div class="stat"><div class="stat-val">{len(prospects)}</div><div class="stat-lbl">Prospects</div></div>
    <div class="stat"><div class="stat-val">{nb_scored}</div><div class="stat-lbl">Scorés</div></div>
    <div class="stat"><div class="stat-val">{campaign.mode}</div><div class="stat-lbl">Mode</div></div>
  </div>
</div>

<div class="card">
  <h2>Preuves IA — {city_cap}</h2>
  {ev_html}
</div>

<div class="card">
  <h2>Prospects ({len(prospects)})</h2>
  <table>
    <tr>
      <th>Entreprise</th><th>Ville</th><th>Score IA</th>
      <th>Concurrents</th><th>Citations</th><th>Actions</th>
    </tr>
    {prospect_rows}
  </table>
</div>

</div>

<div id="outreach-modal">
  <div class="modal-box">
    <h3 style="margin-bottom:16px;color:#1a0a4e;font-size:16px">Message Outreach généré</h3>
    <div id="outreach-content" style="font-size:13px;line-height:1.6;white-space:pre-wrap;color:#374151;background:#f9fafb;padding:16px;border-radius:6px"></div>
    <button onclick="document.getElementById('outreach-modal').classList.remove('open')"
      style="margin-top:16px;background:#6b7280;color:#fff;border:none;padding:8px 20px;border-radius:5px;cursor:pointer;font-size:13px">
      Fermer
    </button>
  </div>
</div>

<script>
async function genOutreach(pid) {{
  const r = await fetch(`/api/generate/prospect/${{pid}}/outreach-messages`, {{method:'POST'}});
  const d = await r.json();
  const box = document.getElementById('outreach-content');
  if (d.success && d.result) {{
    const msgs = d.result.messages || d.result;
    box.textContent = typeof msgs === 'string' ? msgs : JSON.stringify(msgs, null, 2);
  }} else {{
    box.textContent = 'Erreur : ' + JSON.stringify(d.error || d, null, 2);
  }}
  document.getElementById('outreach-modal').classList.add('open');
}}
</script>
</body></html>"""
