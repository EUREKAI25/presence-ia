"""Admin — Prospection automatique (Google Places + pipeline IA)."""
import csv, io, json, os, uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ...database import (get_db, db_create_campaign, db_create_prospect, jd,
                          db_get_header,
                          db_list_metier_configs, db_get_metier_config,
                          db_upsert_metier_config, db_delete_metier_config,
                          db_list_ia_query_templates, db_upsert_ia_query_template,
                          db_delete_ia_query_template)
from ...models import (CampaignDB, ProspectDB, ProspectStatus, ProspectionTargetDB,
                       SireneSuspectDB, SireneSegmentDB)
from ._nav import admin_nav

router = APIRouter(tags=["Admin Prospection"])

_FREQ_LABELS = {
    "daily":    "Quotidien",
    "2x_week":  "2× / semaine",
    "weekly":   "1× / semaine",
    "2x_month": "2× / mois",
    "monthly":  "Mensuel",
}
_FREQ_DAYS = {
    "daily": 1, "2x_week": 3, "weekly": 7, "2x_month": 15, "monthly": 30,
}


def _check_token(request: Request) -> str:
    t = request.query_params.get("token") or request.cookies.get("admin_token", "")
    if t != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403, "Token invalide")
    return t


def _next_run(target: ProspectionTargetDB) -> str:
    if not target.active:
        return "—"
    if not target.last_run:
        return "Dès maintenant"
    delta = _FREQ_DAYS.get(target.frequency, 7)
    next_dt = target.last_run + timedelta(days=delta)
    now = datetime.utcnow()
    if next_dt <= now:
        return "Dès maintenant"
    diff = (next_dt - now).days
    return "Aujourd'hui" if diff == 0 else f"Dans {diff}j"


def _btn(color: str) -> str:
    return (f"background:transparent;border:1px solid {color};color:{color};"
            f"padding:4px 10px;border-radius:5px;font-size:11px;cursor:pointer;margin-left:4px")


# ── Page principale ────────────────────────────────────────────────────────────

@router.get("/admin/prospection", response_class=HTMLResponse)
def prospection_page(request: Request, db: Session = Depends(get_db)):
    token   = _check_token(request)
    targets = db.query(ProspectionTargetDB).order_by(ProspectionTargetDB.created_at.desc()).all()
    metiers = db_list_metier_configs(db)
    queries = db_list_ia_query_templates(db)

    # ── Stats leads par paire — pipeline V3 (v3_prospects) ──
    pair_rows = db.execute(text("""
        SELECT profession, city,
               COUNT(*)                                                            AS total,
               0                                                                   AS en_cours,
               0                                                                   AS pipeline,
               SUM(CASE WHEN contacted=0 AND email IS NOT NULL THEN 1 ELSE 0 END) AS prets,
               SUM(CASE WHEN contacted=1 THEN 1 ELSE 0 END)                       AS envoyes
        FROM v3_prospects
        GROUP BY profession, city
        ORDER BY total DESC
    """)).fetchall()

    # ── Stats suspects SIRENE globales ──
    s_total     = db.query(func.count(SireneSuspectDB.id)).scalar() or 0
    s_enrichis  = db.query(func.count(SireneSuspectDB.id)).filter(SireneSuspectDB.enrichi_at.isnot(None)).scalar() or 0
    s_provision = db.query(func.count(SireneSuspectDB.id)).filter(SireneSuspectDB.provisioned_at.isnot(None)).scalar() or 0
    seg_done    = db.query(func.count(SireneSegmentDB.id)).filter(SireneSegmentDB.status == "done").scalar() or 0
    seg_total   = db.query(func.count(SireneSegmentDB.id)).scalar() or 0

    # ── Tableau ciblages (pour accordéon) ──
    freq_sel_tpl = "".join(f'<option value="{k}" {{sel_{k}}}>{v}</option>' for k, v in _FREQ_LABELS.items())
    rows = ""
    for t in targets:
        last   = t.last_run.strftime("%d/%m %Hh%M") if t.last_run else "Jamais"
        next_r = _next_run(t)
        dot    = "🟢" if t.active else "⚫"
        freq_sel = freq_sel_tpl
        for k in _FREQ_LABELS:
            freq_sel = freq_sel.replace(f"{{sel_{k}}}", "selected" if t.frequency == k else "")
        inl = "background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;border-radius:4px;padding:4px 6px;font-size:12px;width:100%"
        rows += f"""<tr data-id="{t.id}">
  <td style="color:#fff;font-weight:600">{t.name}</td>
  <td style="color:#ccc">{t.city}</td>
  <td style="color:#ccc">{t.profession}</td>
  <td><select data-tid="{t.id}" data-field="frequency" style="{inl}" onchange="saveTarget(this)">{freq_sel}</select></td>
  <td><input type="number" data-tid="{t.id}" data-field="max_prospects" value="{t.max_prospects}" min="1" max="200" style="{inl};width:70px" onblur="saveTarget(this)" onkeydown="if(event.key==='Enter')this.blur()"></td>
  <td style="color:#9ca3af">{last} {f"({t.last_count} trouvés)" if t.last_count else ""}</td>
  <td style="color:#9ca3af">{next_r}</td>
  <td>{dot}</td>
  <td style="white-space:nowrap">
    <button onclick="runNow('{t.id}',this)" style="{_btn('#2ecc71')}">▶ Lancer</button>
    <button onclick="toggle('{t.id}',{str(t.active).lower()},this)" style="{_btn('#e9a020')}">{"Désactiver" if t.active else "Activer"}</button>
    <button onclick="del_('{t.id}',this)" style="{_btn('#e94560')}">✕</button>
  </td>
</tr>"""

    # ── Tableau métiers (pour accordéon) ──
    metier_rows = ""
    for m in metiers:
        cities_for_metier = [t.city for t in targets if t.profession.lower() == m.metier.lower()]
        city_tags = "".join(
            f'<span style="background:#1a2a3e;color:#60a5fa;padding:2px 8px;border-radius:4px;'
            f'font-size:11px;margin:2px;display:inline-block">{c}</span>'
            for c in cities_for_metier
        ) or '<span style="color:#555;font-size:11px">aucune ville</span>'
        metier_rows += f"""<tr data-metier="{m.metier}">
  <td style="color:#fff;font-weight:600">{m.metier}</td>
  <td><input type="text" value="{m.problematique}" data-field="problematique" data-metier="{m.metier}"
       style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;border-radius:5px;
              padding:5px 8px;font-size:12px;width:100%" onblur="saveMetier(this)"></td>
  <td><input type="text" value="{m.mission}" data-field="mission" data-metier="{m.metier}"
       style="background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;border-radius:5px;
              padding:5px 8px;font-size:12px;width:100%" onblur="saveMetier(this)"></td>
  <td>{city_tags}</td>
  <td><button onclick="delMetier('{m.metier}',this)" style="{_btn('#e94560')}">✕</button></td>
</tr>"""

    # ── Liste requêtes IA (pour accordéon) ──
    query_items = ""
    for q in queries:
        checked = "checked" if q.active else ""
        query_items += f"""<div class="q-row" data-id="{q.id}" style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
  <span style="color:#555;font-size:12px;min-width:20px">{q.order}</span>
  <input type="checkbox" {checked} onchange="toggleQuery('{q.id}',this.checked)"
         style="width:auto;accent-color:#e94560;cursor:pointer">
  <input type="text" value="{q.template}" data-id="{q.id}"
         style="flex:1;background:#0f0f1a;border:1px solid #2a2a4e;color:#e8e8f0;
                border-radius:5px;padding:7px 10px;font-size:12px;font-family:monospace"
         onblur="saveQuery(this)">
  <button onclick="delQuery('{q.id}',this)" style="{_btn('#e94560')}">✕</button>
</div>"""

    freq_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in _FREQ_LABELS.items())
    target_opts = "".join(f'<option value="{t.id}">{t.name} ({t.profession} / {t.city})</option>' for t in targets)

    # ── Tableau paires leads ──
    def _bar(val, total, color="#e94560"):
        pct = round(val / total * 100) if total else 0
        return (f'<div style="display:flex;align-items:center;gap:6px">'
                f'<div style="flex:1;background:#1a1a2e;border-radius:3px;height:6px">'
                f'<div style="width:{pct}%;background:{color};height:6px;border-radius:3px"></div>'
                f'</div><span style="color:#9ca3af;font-size:11px;min-width:24px">{val}</span></div>')

    pairs_html = ""
    total_leads = total_prets = total_envoyes = 0
    for r in pair_rows:
        total_leads   += r.total   or 0
        total_prets   += r.prets   or 0
        total_envoyes += r.envoyes or 0
        if (r.prets or 0) > 0:
            dot = '<span style="color:#2ecc71;font-size:13px">●</span>'
        elif (r.pipeline or 0) > 0 or (r.en_cours or 0) > 0:
            dot = '<span style="color:#e9a020;font-size:13px">●</span>'
        else:
            dot = '<span style="color:#374151;font-size:13px">●</span>'
        pairs_html += f"""<tr>
  <td style="padding:8px 6px">{dot}</td>
  <td style="color:#fff;font-weight:600">{r.profession}</td>
  <td style="color:#9ca3af">{r.city}</td>
  <td style="min-width:80px">{_bar(r.en_cours or 0, r.total or 1, "#e9a020")}</td>
  <td style="min-width:80px">{_bar(r.pipeline or 0, r.total or 1, "#a78bfa")}</td>
  <td style="min-width:80px">{_bar(r.prets or 0, r.total or 1, "#2ecc71")}</td>
  <td style="color:#60a5fa;font-weight:700;text-align:right">{r.envoyes or 0}</td>
  <td style="color:#555;font-size:11px;text-align:right">{r.total or 0} total</td>
</tr>"""
    if not pairs_html:
        pairs_html = '<tr><td colspan="8" style="color:#555;text-align:center;padding:20px">Aucune campagne — lancez une première prospection</td></tr>'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prospection — PRESENCE_IA</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e8e8f0}}
.wrap{{max-width:1100px;margin:0 auto;padding:28px 20px}}
h1{{color:#fff;font-size:20px;margin-bottom:6px}}
.sub{{color:#6b7280;font-size:13px;margin-bottom:28px}}
.card{{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:10px;padding:24px;margin-bottom:16px}}
.card h2{{color:#e94560;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:18px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:.8px;
    padding:8px 12px;border-bottom:1px solid #2a2a4e;text-align:left}}
td{{padding:8px 12px;border-bottom:1px solid #1a1a2e;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:rgba(255,255,255,.02)}}
label.f{{display:block;color:#9ca3af;font-size:12px;margin-bottom:5px;margin-top:14px}}
label.f:first-of-type{{margin-top:0}}
input[type=text],input[type=number],select,textarea{{
  width:100%;background:#0f0f1a;border:1px solid #2a2a4e;
  color:#e8e8f0;border-radius:6px;padding:9px 12px;font-size:13px;font-family:inherit}}
input:focus,select:focus,textarea:focus{{outline:none;border-color:#e94560}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.grid4{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:14px}}
.btn-main{{background:linear-gradient(90deg,#e8355a,#ff7043);color:#fff;border:none;
  padding:11px 28px;border-radius:7px;font-size:13px;font-weight:700;cursor:pointer}}
.btn-main:hover{{opacity:.9}}
.btn-add{{background:#1a2a3e;color:#60a5fa;border:1px solid #2a3a5e;
  padding:9px 20px;border-radius:6px;font-size:13px;cursor:pointer}}
.btn-add:hover{{background:#1e3a5e}}
.btn-sm{{background:#1a2a3e;color:#60a5fa;border:1px solid #2a3a5e;
  padding:6px 14px;border-radius:5px;font-size:12px;cursor:pointer}}
.btn-sm:hover{{background:#1e3a5e}}
.log{{background:#0a0a15;border:1px solid #1a1a2e;border-radius:8px;padding:14px;
  font-family:monospace;font-size:12px;color:#6b7280;min-height:60px;
  max-height:300px;overflow-y:auto;white-space:pre-wrap;margin-top:16px;display:none}}
.log.on{{display:block}}
.hint{{background:#0f0f1a;border:1px solid #2a2a4e;border-radius:6px;
  padding:10px 14px;font-size:11px;color:#6b7280;font-family:monospace;line-height:1.8}}
.placeholder{{color:#e94560}}
.ok{{color:#2ecc71}}.err{{color:#e94560}}.warn{{color:#e9a020}}

/* Panier */
#basket-list{{list-style:none;margin:0;padding:0}}
#basket-list li{{display:flex;align-items:center;gap:8px;padding:7px 10px;
  background:#0f0f1a;border:1px solid #2a2a4e;border-radius:6px;margin-bottom:6px;font-size:13px}}
#basket-list li .tag-metier{{background:#1a2a3e;color:#60a5fa;padding:2px 8px;border-radius:4px;font-size:11px}}
#basket-list li .tag-ville{{background:#1a3a2e;color:#34d399;padding:2px 8px;border-radius:4px;font-size:11px}}
#basket-list li .tag-opt{{color:#9ca3af;font-size:11px}}
#basket-list li button{{margin-left:auto;background:transparent;border:none;color:#6b7280;
  cursor:pointer;font-size:14px;line-height:1}}
#basket-list li button:hover{{color:#e94560}}
#basket-empty{{color:#555;font-size:13px;padding:10px 0}}

/* KPI boxes */
.kpi-box{{background:#0f0f1a;border:1px solid #2a2a4e;border-radius:8px;padding:12px 18px;min-width:100px;text-align:center}}
.kpi-val{{font-size:24px;font-weight:700;color:#e8e8f0;line-height:1.1}}
.kpi-lbl{{font-size:11px;color:#6b7280;margin-top:3px;text-transform:uppercase;letter-spacing:.5px}}

/* Accordéon */
details{{background:#141424;border:1px solid #2a2a4e;border-radius:8px;margin-bottom:10px}}
details summary{{padding:14px 18px;cursor:pointer;color:#9ca3af;font-size:12px;
  text-transform:uppercase;letter-spacing:1px;list-style:none;
  display:flex;align-items:center;gap:8px;user-select:none}}
details summary::-webkit-details-marker{{display:none}}
details summary::before{{content:'▶';font-size:10px;transition:transform .15s;display:inline-block}}
details[open] summary::before{{transform:rotate(90deg)}}
details summary:hover{{color:#e8e8f0}}
.details-body{{padding:18px}}
</style>
</head><body>
{admin_nav(token, "prospection")}
<div class="wrap">
<h1>🎯 Prospection automatique</h1>
<p class="sub">Ajoutez des paires métier + ville, puis lancez. Google Places → pipeline IA → suspects qualifiés.</p>

<!-- ── LEADS PAR PAIRE ────────────────────────────────────────────── -->
<div class="card">
  <h2>Leads par paire métier × ville</h2>
  <div style="display:flex;gap:20px;margin-bottom:16px;flex-wrap:wrap">
    <div class="kpi-box"><div class="kpi-val">{total_leads}</div><div class="kpi-lbl">Leads total</div></div>
    <div class="kpi-box"><div class="kpi-val" style="color:#2ecc71">{total_prets}</div><div class="kpi-lbl">Prêts à envoyer</div></div>
    <div class="kpi-box"><div class="kpi-val" style="color:#60a5fa">{total_envoyes}</div><div class="kpi-lbl">Envoyés</div></div>
    <div class="kpi-box"><div class="kpi-val" style="color:#9ca3af">{s_total:,}</div><div class="kpi-lbl">Suspects SIRENE</div></div>
    <div class="kpi-box"><div class="kpi-val" style="color:#a78bfa">{s_enrichis:,}</div><div class="kpi-lbl">Enrichis Google</div></div>
    <div class="kpi-box"><div class="kpi-val" style="color:#f59e0b">{s_provision:,}</div><div class="kpi-lbl">Provisionnés</div></div>
  </div>
  <table>
    <thead><tr>
      <th style="width:20px"></th>
      <th>Métier</th><th>Ville</th>
      <th>En cours <span style="color:#e9a020;font-size:10px">●</span></th>
      <th>Pipeline <span style="color:#a78bfa;font-size:10px">●</span></th>
      <th>Prêts <span style="color:#2ecc71;font-size:10px">●</span></th>
      <th style="text-align:right">Envoyés</th>
      <th style="text-align:right">Total</th>
    </tr></thead>
    <tbody>{pairs_html}</tbody>
  </table>
  <p style="color:#6b7280;font-size:11px;margin-top:10px">
    <span style="color:#e9a020">●</span> SCHEDULED/TESTING &nbsp;
    <span style="color:#a78bfa">●</span> TESTED/SCORED/READY_ASSETS &nbsp;
    <span style="color:#2ecc71">●</span> READY_TO_SEND
  </p>
</div>

<!-- ── PIPELINE SIRENE ────────────────────────────────────────────── -->
<div class="card">
  <h2>Pipeline SIRENE — qualification automatique</h2>
  <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:12px">
    <div id="sirene-status" style="color:#9ca3af;font-size:13px">Chargement…</div>
    <button class="btn-sm" onclick="launchSirene(this)">▶ Lancer maintenant</button>
    <span style="color:#555;font-size:11px">Job auto : Lun / Mer / Ven à 2h UTC — {seg_done}/{seg_total} segments traités</span>
  </div>
  <div id="sirene-bar" style="display:none;margin-bottom:12px">
    <div style="background:#1a1a2e;border-radius:4px;height:8px;overflow:hidden">
      <div id="sirene-bar-fill" style="background:#e94560;height:8px;width:0%;transition:width .5s"></div>
    </div>
    <div id="sirene-bar-txt" style="color:#9ca3af;font-size:11px;margin-top:4px"></div>
  </div>
  <div class="log" id="log-sirene"></div>
</div>

<!-- ── FORMULAIRE RAPIDE ─────────────────────────────────────────── -->
<div class="card">
  <h2>Nouvelle prospection</h2>
  <div class="grid4">
    <div>
      <label class="f">Métier *</label>
      <input type="text" id="f_metier" placeholder="ex: pisciniste" list="metier-suggestions">
      <datalist id="metier-suggestions">
        {"".join(f'<option value="{m.metier}">' for m in metiers)}
      </datalist>
    </div>
    <div>
      <label class="f">Ville *</label>
      <input type="text" id="f_ville" placeholder="ex: Nice">
    </div>
    <div>
      <label class="f">Problématique <span style="color:#555">(opt.)</span></label>
      <input type="text" id="f_probl" placeholder="ex: entretien de piscine">
    </div>
    <div>
      <label class="f">Mission <span style="color:#555">(opt.)</span></label>
      <input type="text" id="f_mission" placeholder="ex: installer une piscine">
    </div>
  </div>
  <div class="grid2" style="margin-top:14px">
    <div>
      <label class="f">Fréquence automatique</label>
      <select id="f_freq">
        {"".join(f'<option value="{k}" {"selected" if k=="weekly" else ""}>{v}</option>' for k,v in _FREQ_LABELS.items())}
      </select>
    </div>
    <div>
      <label class="f">Nb de leads max par run</label>
      <input type="number" id="f_max" value="20" min="1" max="200">
    </div>
  </div>
  <div style="margin-top:14px;display:flex;gap:10px;align-items:center">
    <button class="btn-add" onclick="addToBasket()">+ Ajouter au panier</button>
    <span style="color:#6b7280;font-size:12px">ou appuyez sur Entrée dans un champ</span>
  </div>
</div>

<!-- ── PANIER ────────────────────────────────────────────────────── -->
<div class="card" id="basket-card" style="display:none">
  <h2>Panier <span id="basket-count" style="color:#60a5fa;font-weight:normal"></span></h2>
  <ul id="basket-list"></ul>
  <div id="basket-empty" style="display:none">Panier vide</div>
  <div style="margin-top:16px;display:flex;gap:10px;align-items:center">
    <button class="btn-main" onclick="launchAll()">▶ Lancer tout</button>
    <button class="btn-sm" onclick="clearBasket()">Vider le panier</button>
  </div>
  <div class="log" id="log-launch"></div>
</div>

<!-- ── ACCORDÉONS ────────────────────────────────────────────────── -->

<details open>
  <summary>Ciblages actifs ({len(targets)})</summary>
  <div class="details-body">
    <p style="color:#6b7280;font-size:12px;margin-bottom:14px">
      Modifiez la fréquence ou le nb de leads directement dans le tableau — sauvegarde auto.
    </p>
    <table>
      <thead><tr>
        {"".join(f'<th>{h}</th>' for h in ["Nom","Ville","Métier","Fréquence","Leads max","Dernier run","Prochain","","Actions"])}
      </tr></thead>
      <tbody>
        {rows or '<tr><td colspan="9" style="color:#555;text-align:center;padding:24px">Aucun ciblage — utilisez le formulaire ci-dessus</td></tr>'}
      </tbody>
    </table>
    <div class="log" id="log-run"></div>
  </div>
</details>

<details>
  <summary>Métiers configurés ({len(metiers)})</summary>
  <div class="details-body">
    <p style="color:#6b7280;font-size:12px;margin-bottom:16px">
      Définissent les placeholders <code style="color:#e94560">{{problematique}}</code>
      et <code style="color:#e94560">{{mission}}</code> utilisés dans les requêtes IA.
      Sauvegarde auto à la sortie du champ.
    </p>
    <table>
      <thead><tr>
        <th>Métier</th><th>Problématique</th><th>Mission</th><th>Villes actives</th><th></th>
      </tr></thead>
      <tbody id="metier-tbody">
        {metier_rows or '<tr><td colspan="5" style="color:#555;text-align:center;padding:20px">Aucun métier</td></tr>'}
      </tbody>
    </table>
    <p style="color:#9ca3af;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:20px 0 10px;padding-bottom:6px;border-bottom:1px solid #2a2a4e">Ajouter un métier manuellement</p>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px">
      <div><label class="f">Métier</label><input type="text" id="m_metier" placeholder="ex: couvreur"></div>
      <div><label class="f">Problématique</label><input type="text" id="m_probl" placeholder="ex: fuite de toiture"></div>
      <div><label class="f">Mission</label><input type="text" id="m_mission" placeholder="ex: refaire ma toiture"></div>
    </div>
    <button class="btn-add" style="margin-top:14px" onclick="addMetier()">+ Ajouter ce métier</button>
    <div class="log" id="log-metier"></div>
  </div>
</details>

<details>
  <summary>Requêtes IA ({len(queries)} requête{"s" if len(queries) != 1 else ""})</summary>
  <div class="details-body">
    <div class="hint" style="margin-bottom:16px">
      Placeholders : <span class="placeholder">{{metier}}</span> &nbsp;
      <span class="placeholder">{{ville}}</span> &nbsp;
      <span class="placeholder">{{problematique}}</span> &nbsp;
      <span class="placeholder">{{mission}}</span>
    </div>
    <div id="queries-list">{query_items or '<p style="color:#555;font-size:13px">Aucune requête</p>'}</div>
    <div style="display:flex;gap:10px;margin-top:16px;align-items:flex-end">
      <div style="flex:1">
        <label class="f">Nouvelle requête</label>
        <input type="text" id="new_query" placeholder="ex: Quel {{metier}} pour {{mission}} à {{ville}} ?">
      </div>
      <button class="btn-sm" style="margin-bottom:1px" onclick="addQuery()">+ Ajouter</button>
    </div>
    <div class="log" id="log-queries"></div>
  </div>
</details>

<details>
  <summary>Import CSV</summary>
  <div class="details-body">
    <div class="grid2">
      <div>
        <label class="f">Ciblage cible</label>
        <select id="csv_target">
          <option value="">— Sélectionner —</option>
          {target_opts}
        </select>
      </div>
      <div>
        <label class="f">Fichier CSV</label>
        <input type="file" id="csv_file" accept=".csv">
      </div>
    </div>
    <div class="hint" style="margin-top:12px">
      Colonnes : <span style="color:#e94560">name</span> (obligatoire) —
      city, profession, website, phone, reviews_count (optionnels)
    </div>
    <button class="btn-add" style="margin-top:14px" onclick="importCSV()">Importer →</button>
    <div class="log" id="log-csv"></div>
  </div>
</details>

</div><!-- /wrap -->

<script>
const T = '{token}';
let basket = [];

function logTo(id, msg, cls='') {{
  const el = document.getElementById(id);
  el.classList.add('on');
  const pfx = cls==='ok' ? '✅ ' : cls==='err' ? '❌ ' : cls==='warn' ? '⚠️ ' : '▸ ';
  el.textContent += pfx + msg + '\\n';
  el.scrollTop = el.scrollHeight;
}}

// ── SIRENE ──

async function fetchSireneStatus() {{
  try {{
    const r = await fetch(`/admin/professions/qualify-status?token=${{T}}`);
    if (!r.ok) return;
    const d = await r.json();
    const el = document.getElementById('sirene-status');
    const bar = document.getElementById('sirene-bar');
    const fill = document.getElementById('sirene-bar-fill');
    const txt = document.getElementById('sirene-bar-txt');
    if (d.running) {{
      el.innerHTML = '<span style="color:#e9a020">⟳ En cours…</span>';
      bar.style.display = 'block';
      const pct = d.total_segs > 0 ? Math.round(d.done_segs / d.total_segs * 100) : 0;
      fill.style.width = pct + '%';
      txt.textContent = `Segments : ${{d.done_segs || 0}} / ${{d.total_segs || 0}} — ${{d.suspects || 0}} suspects trouvés`;
      setTimeout(fetchSireneStatus, 3000);
    }} else {{
      el.innerHTML = `<span style="color:#2ecc71">✓ Inactif</span> — ${{d.total ? d.total.toLocaleString() : '?'}} suspects en base`;
      bar.style.display = 'none';
    }}
  }} catch(e) {{}}
}}

async function launchSirene(btn) {{
  btn.disabled = true; btn.textContent = '⟳ Lancement…';
  logTo('log-sirene', 'Lancement qualification SIRENE…');
  const r = await fetch(`/admin/professions/qualify?token=${{T}}`, {{method:'POST'}});
  const d = await r.json();
  if (r.ok) {{
    logTo('log-sirene', d.message || 'Démarré en arrière-plan', 'ok');
    setTimeout(fetchSireneStatus, 1000);
  }} else {{
    logTo('log-sirene', d.detail || 'Erreur', 'err');
  }}
  btn.disabled = false; btn.textContent = '▶ Lancer maintenant';
}}

fetchSireneStatus();

// ── Panier ──

function renderBasket() {{
  const card = document.getElementById('basket-card');
  const list = document.getElementById('basket-list');
  const cnt  = document.getElementById('basket-count');
  const empty = document.getElementById('basket-empty');
  if (basket.length === 0) {{ card.style.display = 'none'; return; }}
  card.style.display = 'block';
  cnt.textContent = `(${{basket.length}} paire${{basket.length>1?'s':''}})`;
  const freqLabels = {{{", ".join(f'"{k}":"{v}"' for k,v in _FREQ_LABELS.items())}}};
  list.innerHTML = basket.map((b, i) => `
    <li>
      <span class="tag-metier">${{b.metier}}</span>
      <span class="tag-ville">${{b.ville}}</span>
      <span class="tag-opt">${{freqLabels[b.freq]||b.freq}} · ${{b.max}} leads max</span>
      ${{b.probl ? `<span class="tag-opt">probl: ${{b.probl}}</span>` : ''}}
      ${{b.mission ? `<span class="tag-opt">mission: ${{b.mission}}</span>` : ''}}
      <button onclick="removeFromBasket(${{i}})" title="Retirer">✕</button>
    </li>
  `).join('');
  empty.style.display = basket.length ? 'none' : 'block';
}}

function addToBasket() {{
  const metier  = document.getElementById('f_metier').value.trim();
  const ville   = document.getElementById('f_ville').value.trim();
  const probl   = document.getElementById('f_probl').value.trim();
  const mission = document.getElementById('f_mission').value.trim();
  const freq    = document.getElementById('f_freq').value;
  const max     = parseInt(document.getElementById('f_max').value) || 20;
  if (!metier || !ville) {{ alert('Métier et ville sont obligatoires.'); return; }}
  basket.push({{ metier, ville, probl, mission, freq, max }});
  renderBasket();
  // Vider les champs métier/ville, garder probl/mission pour paires suivantes
  document.getElementById('f_metier').value = '';
  document.getElementById('f_ville').value  = '';
  document.getElementById('f_metier').focus();
}}

function removeFromBasket(i) {{
  basket.splice(i, 1);
  renderBasket();
}}

function clearBasket() {{
  basket = [];
  renderBasket();
}}

// Entrée dans un champ → ajouter au panier
['f_metier','f_ville','f_probl','f_mission'].forEach(id => {{
  document.getElementById(id).addEventListener('keydown', e => {{
    if (e.key === 'Enter') {{ e.preventDefault(); addToBasket(); }}
  }});
}});

// ── Lancer tout ──

async function launchAll() {{
  if (!basket.length) {{ alert('Panier vide.'); return; }}
  const log = 'log-launch';
  logTo(log, `Lancement de ${{basket.length}} paire(s)...`);

  for (const item of basket) {{
    logTo(log, `\\n→ ${{item.metier}} / ${{item.ville}}`);

    // 1. Créer le métier si besoin (upsert — pas d'erreur si déjà présent)
    const rm = await fetch('/api/admin/prospection/metiers', {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{
        token: T, metier: item.metier,
        problematique: item.probl || '',
        mission: item.mission || ''
      }})
    }});
    if (!rm.ok) {{ logTo(log, `Erreur métier: ${{(await rm.json()).detail}}`, 'err'); continue; }}
    logTo(log, `  Métier "${{item.metier}}" — OK`, 'ok');

    // 2. Créer le ciblage
    const name = `${{item.metier}}-${{item.ville}}`.toLowerCase().replace(/\\s+/g,'-');
    const rt = await fetch('/api/admin/prospection/targets', {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{
        token: T, name, city: item.ville,
        profession: item.metier, frequency: item.freq, max_prospects: item.max
      }})
    }});
    const dt = await rt.json();
    if (!rt.ok) {{
      // Peut déjà exister — chercher l'id dans la liste existante
      const existing = document.querySelector(`tr[data-id]`);
      logTo(log, `  Ciblage: ${{dt.detail||'déjà existant, on lance quand même'}}`, 'warn');
      // Tenter de relancer via le nom
      const allRows = document.querySelectorAll('#log-run')?.closest?.('details')?.querySelectorAll?.('tr[data-id]') || [];
      // fallback : on skip le run si on n'a pas l'id
      logTo(log, `  (Relancez manuellement depuis l'accordéon Ciblages existants)`, 'warn');
      continue;
    }}
    const tid = dt.id;
    logTo(log, `  Ciblage "${{name}}" créé (id: ${{tid.slice(0,8)}}…)`, 'ok');

    // 3. Lancer
    const rr = await fetch(`/api/admin/prospection/targets/${{tid}}/run?token=${{T}}`, {{method:'POST'}});
    const dr = await rr.json();
    if (rr.ok) {{
      logTo(log, `  ${{dr.imported}} prospects importés`, 'ok');
      if (dr.reasons?.length) logTo(log, `  Exclus: ${{dr.reasons.join(' | ')}}`, 'warn');
    }} else {{
      logTo(log, `  Erreur run: ${{dr.detail}}`, 'err');
    }}
  }}

  logTo(log, '\\nTerminé. Rechargement...', 'ok');
  setTimeout(() => location.reload(), 1500);
}}

// ── Ciblages — édition inline freq/max ──

async function saveTarget(el) {{
  const tid   = el.dataset.tid;
  const field = el.dataset.field;
  const val   = field === 'max_prospects' ? parseInt(el.value) : el.value;
  const r = await fetch(`/api/admin/prospection/targets/${{tid}}`, {{
    method:'PATCH', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, [field]: val }})
  }});
  el.style.borderColor = r.ok ? '#2ecc71' : '#e94560';
  setTimeout(()=>{{ el.style.borderColor=''; }}, 1500);
}}

// ── Métiers ──

async function addMetier() {{
  const metier = document.getElementById('m_metier').value.trim();
  const probl  = document.getElementById('m_probl').value.trim();
  const miss   = document.getElementById('m_mission').value.trim();
  if (!metier) {{ alert('Le métier est obligatoire.'); return; }}
  const r = await fetch('/api/admin/prospection/metiers', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, metier, problematique:probl, mission:miss }})
  }});
  if (r.ok) {{ logTo('log-metier','Métier sauvegardé','ok'); setTimeout(()=>location.reload(),600); }}
  else {{ const d=await r.json(); logTo('log-metier', d.detail||'Erreur','err'); }}
}}

async function saveMetier(input) {{
  const metier = input.dataset.metier;
  const row    = input.closest('tr');
  const probl  = row.querySelector('[data-field=problematique]').value;
  const miss   = row.querySelector('[data-field=mission]').value;
  const r = await fetch('/api/admin/prospection/metiers', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, metier, problematique:probl, mission:miss }})
  }});
  input.style.borderColor = r.ok ? '#2ecc71' : '#e94560';
  setTimeout(()=>{{ input.style.borderColor=''; }}, 1500);
}}

async function delMetier(metier, btn) {{
  if (!confirm(`Supprimer le métier "${{metier}}" ?`)) return;
  const r = await fetch(`/api/admin/prospection/metiers/${{encodeURIComponent(metier)}}?token=${{T}}`, {{method:'DELETE'}});
  if (r.ok) btn.closest('tr').remove();
  else alert('Erreur');
}}

// ── Requêtes IA ──

async function addQuery() {{
  const tpl = document.getElementById('new_query').value.trim();
  if (!tpl) {{ alert('Requête vide'); return; }}
  const order = document.querySelectorAll('.q-row').length;
  const r = await fetch('/api/admin/prospection/queries', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, template:tpl, active:true, order }})
  }});
  if (r.ok) {{ logTo('log-queries','Requête ajoutée','ok'); setTimeout(()=>location.reload(),500); }}
  else {{ const d=await r.json(); logTo('log-queries',d.detail||'Erreur','err'); }}
}}

async function saveQuery(input) {{
  const tid = input.dataset.id;
  const row = input.closest('.q-row');
  const active = row.querySelector('input[type=checkbox]').checked;
  const order  = parseInt(row.querySelector('span').textContent) || 0;
  const r = await fetch(`/api/admin/prospection/queries/${{tid}}`, {{
    method:'PUT', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, template:input.value, active, order }})
  }});
  input.style.borderColor = r.ok ? '#2ecc71' : '#e94560';
  setTimeout(()=>{{ input.style.borderColor=''; }}, 1500);
}}

async function toggleQuery(tid, active) {{
  const row   = document.querySelector(`.q-row[data-id="${{tid}}"]`);
  const input = row.querySelector('input[type=text]');
  const order = parseInt(row.querySelector('span').textContent) || 0;
  await fetch(`/api/admin/prospection/queries/${{tid}}`, {{
    method:'PUT', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ token:T, template:input.value, active, order }})
  }});
}}

async function delQuery(tid, btn) {{
  if (!confirm('Supprimer cette requête ?')) return;
  const r = await fetch(`/api/admin/prospection/queries/${{tid}}?token=${{T}}`, {{method:'DELETE'}});
  if (r.ok) btn.closest('.q-row').remove();
  else alert('Erreur');
}}

// ── Ciblages existants ──

async function toggle(id, active, btn) {{
  const r = await fetch(`/api/admin/prospection/targets/${{id}}/toggle?token=${{T}}`, {{method:'POST'}});
  if (r.ok) location.reload();
  else alert('Erreur');
}}

async function del_(id, btn) {{
  if (!confirm('Supprimer ce ciblage ?')) return;
  const r = await fetch(`/api/admin/prospection/targets/${{id}}?token=${{T}}`, {{method:'DELETE'}});
  if (r.ok) btn.closest('tr').remove();
  else alert('Erreur');
}}

async function runNow(id, btn) {{
  btn.disabled = true; btn.textContent = '…';
  logTo('log-run', `Lancement du ciblage ${{id}}...`);
  const r = await fetch(`/api/admin/prospection/targets/${{id}}/run?token=${{T}}`, {{method:'POST'}});
  const d = await r.json();
  btn.disabled = false; btn.textContent = '▶ Lancer';
  if (r.ok) {{
    logTo('log-run', `${{d.imported}} prospects importés.`, 'ok');
    if (d.reasons?.length) logTo('log-run', 'Exclus: ' + d.reasons.join(' | '), 'warn');
  }} else {{
    logTo('log-run', d.detail || 'Erreur', 'err');
  }}
}}

// ── Import CSV ──

async function importCSV() {{
  const tid  = document.getElementById('csv_target').value;
  const file = document.getElementById('csv_file').files[0];
  if (!tid)  {{ alert('Sélectionnez un ciblage.'); return; }}
  if (!file) {{ alert('Sélectionnez un fichier CSV.'); return; }}
  const text = await file.text();
  logTo('log-csv', `Import ${{file.name}}...`);
  const r = await fetch(`/api/admin/prospection/targets/${{tid}}/import-csv?token=${{T}}`, {{
    method:'POST', headers:{{'Content-Type':'text/plain'}}, body: text
  }});
  const d = await r.json();
  if (r.ok) logTo('log-csv', `${{d.imported}} importés, ${{d.skipped}} ignorés.`, 'ok');
  else logTo('log-csv', d.detail||'Erreur', 'err');
}}
</script>
</body></html>""")


# ── API — Métiers ──────────────────────────────────────────────────────────────

@router.post("/api/admin/prospection/metiers")
async def upsert_metier(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    if data.get("token") != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403)
    metier = (data.get("metier") or "").strip().lower()
    if not metier:
        raise HTTPException(400, "Métier obligatoire")
    row = db_upsert_metier_config(
        db, metier,
        data.get("problematique", ""),
        data.get("mission", ""),
    )
    return {"metier": row.metier, "problematique": row.problematique, "mission": row.mission}


@router.delete("/api/admin/prospection/metiers/{metier}")
def delete_metier(metier: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    if not db_delete_metier_config(db, metier):
        raise HTTPException(404)
    return {"deleted": True}


# ── API — Requêtes IA ──────────────────────────────────────────────────────────

@router.post("/api/admin/prospection/queries")
async def add_query(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    if data.get("token") != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403)
    tid = str(uuid.uuid4())
    row = db_upsert_ia_query_template(
        db, tid,
        data.get("template", "").strip(),
        data.get("active", True),
        data.get("order", 0),
    )
    return {"id": row.id, "template": row.template}


@router.put("/api/admin/prospection/queries/{tid}")
async def update_query(tid: str, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    if data.get("token") != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403)
    row = db_upsert_ia_query_template(
        db, tid,
        data.get("template", "").strip(),
        data.get("active", True),
        data.get("order", 0),
    )
    return {"id": row.id, "template": row.template}


@router.delete("/api/admin/prospection/queries/{tid}")
def delete_query(tid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    if not db_delete_ia_query_template(db, tid):
        raise HTTPException(404)
    return {"deleted": True}


# ── API — Ciblages ─────────────────────────────────────────────────────────────

@router.post("/api/admin/prospection/targets")
async def create_target(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    if data.get("token") != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403)
    t = ProspectionTargetDB(
        id=str(uuid.uuid4()),
        name=data["name"],
        city=data["city"],
        profession=data["profession"],
        frequency=data.get("frequency", "weekly"),
        max_prospects=int(data.get("max_prospects", 20)),
        active=True,
        created_at=datetime.utcnow(),
    )
    db.add(t); db.commit(); db.refresh(t)
    return {"id": t.id, "name": t.name}


@router.patch("/api/admin/prospection/targets/{tid}")
async def patch_target(tid: str, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    if data.get("token") != os.getenv("ADMIN_TOKEN", "changeme"):
        raise HTTPException(403)
    t = db.query(ProspectionTargetDB).filter_by(id=tid).first()
    if not t:
        raise HTTPException(404)
    if "frequency" in data:
        t.frequency = data["frequency"]
    if "max_prospects" in data:
        t.max_prospects = int(data["max_prospects"])
    db.commit()
    return {"id": t.id, "frequency": t.frequency, "max_prospects": t.max_prospects}


@router.post("/api/admin/prospection/targets/{tid}/toggle")
def toggle_target(tid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    t = db.query(ProspectionTargetDB).filter_by(id=tid).first()
    if not t: raise HTTPException(404)
    t.active = not t.active; db.commit()
    return {"active": t.active}


@router.delete("/api/admin/prospection/targets/{tid}")
def delete_target(tid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    t = db.query(ProspectionTargetDB).filter_by(id=tid).first()
    if not t: raise HTTPException(404)
    db.delete(t); db.commit()
    return {"deleted": True}


@router.post("/api/admin/prospection/targets/{tid}/run")
def run_target(tid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    t = db.query(ProspectionTargetDB).filter_by(id=tid).first()
    if not t: raise HTTPException(404)
    return _run_prospection(db, t)


@router.post("/api/admin/prospection/targets/{tid}/import-csv")
async def import_csv(tid: str, request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    target = db.query(ProspectionTargetDB).filter_by(id=tid).first()
    if not target: raise HTTPException(404)
    body = await request.body()
    text = body.decode("utf-8", errors="replace")
    sep = ";" if text.count(";") > text.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=sep)
    campaign = _get_or_create_campaign(db, target)
    imported, skipped = 0, 0
    for row in reader:
        name = (row.get("name") or row.get("nom") or "").strip()
        if not name:
            skipped += 1; continue
        p = ProspectDB(
            prospect_id=str(uuid.uuid4()),
            campaign_id=campaign.campaign_id,
            name=name,
            city=(row.get("city") or row.get("ville") or target.city).strip(),
            profession=(row.get("profession") or row.get("metier") or target.profession).strip(),
            website=(row.get("website") or row.get("site") or "").strip() or None,
            phone=(row.get("phone") or row.get("telephone") or "").strip() or None,
            reviews_count=int(row["reviews_count"]) if (row.get("reviews_count") or "").strip().isdigit() else None,
            status=ProspectStatus.SCHEDULED.value,
        )
        db.add(p); imported += 1
    db.commit()
    return {"imported": imported, "skipped": skipped}


# ── Helpers internes ───────────────────────────────────────────────────────────

def _get_or_create_campaign(db: Session, target: ProspectionTargetDB) -> CampaignDB:
    existing = db.query(CampaignDB).filter_by(profession=target.profession, city=target.city).first()
    if existing:
        return existing
    c = CampaignDB(
        campaign_id=str(uuid.uuid4()),
        profession=target.profession,
        city=target.city,
        max_prospects=target.max_prospects,
        mode="auto",
    )
    db.add(c); db.commit(); db.refresh(c)
    return c


def _run_prospection(db: Session, target: ProspectionTargetDB) -> dict:
    """Lance Google Places → enrichissement → import prospects."""

    # Vérification image de ville AVANT de lancer (évite de faire tourner Places pour rien)
    city_header = db_get_header(db, target.city.lower())
    if not city_header:
        raise HTTPException(
            400,
            f"⚠️ Image de fond manquante pour la ville « {target.city} ».\n"
            f"Ajoutez-la dans Admin → Headers avant de lancer ce ciblage."
        )

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "GOOGLE_MAPS_API_KEY non configurée dans le .env")

    from ...google_places import search_prospects_enriched
    prospects_data, reasons = search_prospects_enriched(
        target.profession, target.city, api_key, max_results=target.max_prospects
    )

    campaign = _get_or_create_campaign(db, target)
    existing_names = {
        p.name.lower()
        for p in db.query(ProspectDB).filter_by(campaign_id=campaign.campaign_id).all()
    }

    new_prospects = []
    for pd in prospects_data:
        if pd["name"].lower() in existing_names:
            continue
        p = ProspectDB(
            prospect_id=str(uuid.uuid4()),
            campaign_id=campaign.campaign_id,
            name=pd["name"],
            city=target.city,
            profession=target.profession,
            website=pd.get("website"),
            phone=pd.get("tel"),
            mobile=pd.get("mobile"),
            email=pd.get("email"),
            cms=pd.get("cms"),
            reviews_count=pd.get("reviews_count"),
            status=ProspectStatus.SCHEDULED.value,
        )
        db.add(p)
        new_prospects.append(p)
        existing_names.add(pd["name"].lower())

    db.commit()
    target.last_run   = datetime.utcnow()
    target.last_count = len(new_prospects)
    db.commit()

    return {
        "target_id": target.id,
        "imported":  len(new_prospects),
        "reasons":   reasons[:5],
    }


# ── Scheduler (appelé toutes les heures par APScheduler) ──────────────────────

def run_due_targets(db: Session):
    import logging
    log = logging.getLogger(__name__)
    targets = db.query(ProspectionTargetDB).filter_by(active=True).all()
    for t in targets:
        delta_days = _FREQ_DAYS.get(t.frequency, 7)
        if t.last_run and (datetime.utcnow() - t.last_run) < timedelta(days=delta_days):
            continue
        try:
            res = _run_prospection(db, t)
            log.info("Prospection auto '%s' : %d prospects importés", t.name, res["imported"])
        except Exception as e:
            log.error("Prospection auto '%s' erreur : %s", t.name, e)
