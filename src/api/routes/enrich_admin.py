"""
Admin — Enrichissement suspects SIRENE → prospects V3
GET  /admin/enrich         → formulaire (profession + dept + quantité)
POST /admin/enrich/run     → démarre l'enrichissement en arrière-plan
GET  /admin/enrich/status  → polling état
"""
import json, logging, os, secrets, threading
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...database import SessionLocal, db_suspects_list
from ._nav import admin_nav, admin_token

log    = logging.getLogger(__name__)
router = APIRouter()

# ── État global de l'enrichissement en cours ──────────────────────────────────
_STATE: dict = {"running": False, "total": 0, "done": 0, "enriched": 0,
                "skipped": 0, "errors": 0, "results": [], "profession_id": "",
                "dept": "", "finished_at": None}
_LOCK = threading.Lock()


def _require_admin(token: str):
    if token != admin_token():
        from fastapi import HTTPException
        raise HTTPException(403, "Non autorisé")


# ── Page principale ────────────────────────────────────────────────────────────

@router.get("/admin/enrich", response_class=HTMLResponse)
def enrich_page(token: str = "", profession_id: str = "", dept: str = ""):
    _require_admin(token)

    with SessionLocal() as db:
        from ...models import ProfessionDB, SireneSuspectDB
        from sqlalchemy import func

        # Professions qui ont des suspects
        rows = (db.query(ProfessionDB.id, ProfessionDB.label,
                         func.count(SireneSuspectDB.id).label("nb"))
                .join(SireneSuspectDB, SireneSuspectDB.profession_id == ProfessionDB.id)
                .group_by(ProfessionDB.id)
                .order_by(func.count(SireneSuspectDB.id).desc())
                .all())

        # Depts disponibles pour la profession sélectionnée
        depts = []
        if profession_id:
            dept_rows = (db.query(SireneSuspectDB.departement,
                                  func.count(SireneSuspectDB.id))
                         .filter_by(profession_id=profession_id)
                         .group_by(SireneSuspectDB.departement)
                         .order_by(SireneSuspectDB.departement)
                         .all())
            depts = [(d, n) for d, n in dept_rows if d]

    prof_opts = "".join(
        f'<option value="{r.id}" {"selected" if r.id == profession_id else ""}>'
        f'{r.label} ({r.nb:,})</option>'
        for r in rows
    )
    dept_opts = '<option value="">Tous départements</option>' + "".join(
        f'<option value="{d}" {"selected" if d == dept else ""}>{d} ({n:,})</option>'
        for d, n in depts
    )

    state_json = json.dumps(_STATE)
    nav = admin_nav(token, "enrich")
    return HTMLResponse(f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><title>Enrichissement suspects</title>
{nav}
<style>
body{{font-family:system-ui,sans-serif;background:#f9fafb;color:#111;margin:0}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin:16px 24px}}
label{{font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:4px}}
select,input[type=number],input[type=text]{{border:1px solid #d1d5db;border-radius:6px;padding:8px 10px;font-size:13px;width:100%;box-sizing:border-box}}
.btn{{background:#e94560;color:#fff;border:none;border-radius:6px;padding:9px 20px;font-size:13px;font-weight:600;cursor:pointer}}
.btn:hover{{background:#c73652}}
.btn-green{{background:#16a34a}}.btn-green:hover{{background:#15803d}}
.btn-blue{{background:#2563eb}}.btn-blue:hover{{background:#1d4ed8}}
.btn:disabled{{background:#9ca3af;cursor:not-allowed}}
.progress-bar{{height:8px;background:#e5e7eb;border-radius:4px;overflow:hidden;margin:10px 0}}
.progress-fill{{height:100%;background:#e94560;border-radius:4px;transition:width .4s}}
.result-row{{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #f3f4f6;font-size:12px}}
.tag-ok{{background:#d1fae5;color:#065f46;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700}}
.tag-skip{{background:#f3f4f6;color:#9ca3af;padding:2px 6px;border-radius:4px;font-size:10px}}
.tag-email{{background:#dbeafe;color:#1e40af;padding:2px 6px;border-radius:4px;font-size:10px}}
</style></head><body>
<div style="padding:20px 24px 0">
  <h2 style="font-size:18px;font-weight:700;margin:0 0 4px">Enrichir des suspects</h2>
  <p style="color:#6b7280;font-size:13px;margin:0 0 16px">Google Places + scraping email → prospects prêts pour campagne</p>

  <div class="card">
    <div style="display:grid;grid-template-columns:2fr 1fr 1fr auto;gap:12px;align-items:end">
      <div>
        <label>Métier</label>
        <select id="sel-prof" onchange="loadDepts()">{prof_opts}</select>
      </div>
      <div>
        <label>Département</label>
        <select id="sel-dept">{dept_opts}</select>
      </div>
      <div>
        <label>Quantité souhaitée</label>
        <input type="number" id="inp-qty" value="50" min="1" max="500">
      </div>
      <div>
        <button class="btn" id="btn-run" onclick="startEnrich()">▶ Enrichir</button>
      </div>
    </div>
  </div>

  <!-- Progression -->
  <div class="card" id="progress-card" style="display:none">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h3 style="margin:0;font-size:14px;font-weight:700" id="prog-title">⏳ Enrichissement en cours...</h3>
      <div style="display:flex;gap:8px">
        <span id="prog-counts" style="font-size:13px;color:#6b7280"></span>
        <a id="btn-crm" href="#" style="display:none" class="btn btn-green btn-sm" style="padding:5px 12px;font-size:12px">→ Voir dans Contacts</a>
      </div>
    </div>
    <div class="progress-bar"><div class="progress-fill" id="prog-fill" style="width:0%"></div></div>
    <div style="display:flex;gap:16px;margin:10px 0;font-size:12px">
      <span>✓ <strong id="cnt-enriched">0</strong> enrichis</span>
      <span style="color:#16a34a">✉ <strong id="cnt-email">0</strong> emails</span>
      <span style="color:#9ca3af">⊘ <strong id="cnt-skip">0</strong> ignorés</span>
    </div>
    <div id="results-list" style="max-height:380px;overflow-y:auto"></div>
  </div>
</div>

<script>
const TOKEN = '{token}';

async function loadDepts() {{
  const profId = document.getElementById('sel-prof').value;
  if (!profId) return;
  location.href = '/admin/enrich?token='+TOKEN+'&profession_id='+profId;
}}

async function startEnrich() {{
  const profId = document.getElementById('sel-prof').value;
  const dept   = document.getElementById('sel-dept').value;
  const qty    = parseInt(document.getElementById('inp-qty').value) || 50;
  if (!profId) {{ alert('Choisissez un métier'); return; }}

  document.getElementById('btn-run').disabled = true;
  document.getElementById('progress-card').style.display = 'block';
  document.getElementById('prog-title').textContent = '⏳ Enrichissement en cours...';
  document.getElementById('btn-crm').style.display = 'none';

  await fetch('/admin/enrich/run?token='+TOKEN, {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{profession_id: profId, dept: dept, qty: qty}})
  }});

  _poll();
}}

let _pollTimer = null;
function _poll() {{
  clearTimeout(_pollTimer);
  fetch('/admin/enrich/status?token='+TOKEN)
    .then(r => r.json())
    .then(d => {{
      const pct = d.total > 0 ? Math.round(d.done / d.total * 100) : 0;
      document.getElementById('prog-fill').style.width = pct + '%';
      document.getElementById('prog-counts').textContent = d.done + ' / ' + d.total;
      document.getElementById('cnt-enriched').textContent = d.enriched;
      document.getElementById('cnt-skip').textContent = d.skipped;
      const emailCnt = d.results.filter(r => r.email).length;
      document.getElementById('cnt-email').textContent = emailCnt;

      // Résultats récents
      const list = document.getElementById('results-list');
      list.innerHTML = d.results.slice(-30).reverse().map(r => `
        <div class="result-row">
          <span style="flex:1;font-weight:500">${{r.name}}</span>
          <span style="color:#9ca3af">${{r.city}}</span>
          ${{r.enriched
            ? `<span class="tag-ok">Google ✓</span>${{r.email ? '<span class="tag-email">✉ '+r.email+'</span>' : ''}}`
            : '<span class="tag-skip">pas de site</span>'}}
        </div>`).join('');

      if (d.running) {{
        _pollTimer = setTimeout(_poll, 2000);
      }} else {{
        document.getElementById('btn-run').disabled = false;
        if (d.enriched > 0) {{
          document.getElementById('prog-title').textContent = '✓ Terminé — ' + d.enriched + ' prospects créés';
          const btn = document.getElementById('btn-crm');
          btn.href = '/admin/v3?token='+TOKEN;
          btn.style.display = 'inline-block';
        }} else {{
          document.getElementById('prog-title').textContent = '⚠ Aucun prospect trouvé sur Google Places';
        }}
      }}
    }})
    .catch(() => {{ if (_STATE_running) _pollTimer = setTimeout(_poll, 3000); }});
}}

// Reprendre polling si enrichissement déjà en cours
const _initState = {state_json};
if (_initState.running) {{ document.getElementById('progress-card').style.display='block'; _poll(); }}
</script>
</body></html>""")


# ── Enrichissement en arrière-plan ────────────────────────────────────────────

@router.post("/admin/enrich/run")
async def enrich_run(request: Request, token: str = ""):
    _require_admin(token)
    data = await request.json()
    profession_id = data.get("profession_id", "")
    dept          = data.get("dept", "") or None
    qty           = int(data.get("qty", 50))

    if not profession_id:
        return JSONResponse({"error": "profession_id requis"}, status_code=400)

    if _STATE["running"]:
        return JSONResponse({"error": "Enrichissement déjà en cours"}, status_code=409)

    threading.Thread(
        target=_run_enrich, args=(profession_id, dept, qty), daemon=True
    ).start()
    return JSONResponse({"ok": True})


def _run_enrich(profession_id: str, dept: Optional[str], qty: int):
    from ...google_places import fetch_text_search, fetch_place_details
    from ...enrich import enrich_website
    from ...models import V3ProspectDB, ProfessionDB

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")

    with _LOCK:
        _STATE.update({"running": True, "total": 0, "done": 0, "enriched": 0,
                       "skipped": 0, "errors": 0, "results": [],
                       "profession_id": profession_id, "dept": dept or "",
                       "finished_at": None})

    try:
        with SessionLocal() as db:
            # Récupérer label + label_pluriel de la profession
            prof = db.query(ProfessionDB).filter_by(id=profession_id).first()
            prof_label    = prof.label    if prof else profession_id
            prof_plural   = prof.label_pluriel if prof and prof.label_pluriel else prof_label

            # Prendre les suspects (priorité : sans enrichissement)
            total, suspects = db_suspects_list(
                db, profession_id=profession_id, dept=dept, page=1, per_page=min(qty * 3, 500)
            )

        _STATE["total"] = min(len(suspects), qty)

        processed = 0
        for s in suspects:
            if processed >= qty:
                break

            ville = s.ville or ""
            query = f"{s.raison_sociale} {ville}".strip()

            result_entry = {"name": s.raison_sociale, "city": ville,
                            "siret": s.id, "enriched": False, "email": None}

            try:
                # Google Places : chercher par nom + ville
                places = fetch_text_search(query, "", api_key, max_results=1) if api_key else []

                if not places:
                    result_entry["enriched"] = False
                    with _LOCK:
                        _STATE["skipped"] += 1
                else:
                    place = places[0]
                    place_id = place.get("place_id", "")
                    details  = fetch_place_details(place_id, api_key) if place_id and api_key else {}

                    website = details.get("website") or ""
                    phone   = details.get("formatted_phone_number") or s.code_postal and None or None
                    rating  = details.get("rating")
                    reviews = details.get("user_ratings_total")

                    if not website:
                        result_entry["enriched"] = False
                        with _LOCK:
                            _STATE["skipped"] += 1
                    else:
                        # Scraping email
                        enriched = enrich_website(website, timeout=5)
                        email  = enriched.get("email")
                        mobile = enriched.get("mobile")

                        result_entry.update({"enriched": True, "email": email,
                                             "website": website, "phone": phone})

                        # Créer V3ProspectDB
                        tok = secrets.token_hex(16)
                        landing_url = f"/v3/{tok}"
                        v3 = V3ProspectDB(
                            token=tok,
                            name=s.raison_sociale,
                            city=ville,
                            profession=prof_label,
                            phone=phone or mobile,
                            website=website,
                            email=email,
                            rating=rating,
                            reviews_count=reviews,
                            landing_url=landing_url,
                            scrape_status="done",
                        )
                        with SessionLocal() as db2:
                            db2.add(v3)
                            db2.commit()

                        with _LOCK:
                            _STATE["enriched"] += 1

            except Exception as e:
                log.warning(f"Enrich {s.raison_sociale}: {e}")
                with _LOCK:
                    _STATE["errors"] += 1

            processed += 1
            with _LOCK:
                _STATE["done"] = processed
                _STATE["results"].append(result_entry)
                if len(_STATE["results"]) > 200:
                    _STATE["results"] = _STATE["results"][-200:]

    except Exception as e:
        log.error(f"Enrichissement fatal: {e}")
    finally:
        with _LOCK:
            _STATE["running"]     = False
            _STATE["finished_at"] = datetime.utcnow().isoformat()


@router.get("/admin/enrich/status")
def enrich_status(token: str = ""):
    _require_admin(token)
    with _LOCK:
        return JSONResponse(dict(_STATE))
