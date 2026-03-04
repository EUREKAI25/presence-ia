"""
MONTHLY_RETEST (10F)
Pipeline de re-test mensuel automatisé pour les prospects sous contrat.
Compare le run courant avec le run de référence (baseline) et génère un rapport.

Endpoints :
  POST /api/retest/prospect/{pid}/run
  GET  /api/retest/prospect/{pid}/history
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..database import db_get_prospect, db_list_runs, jl
from ..models import ProspectDB, TestRunDB

log = logging.getLogger(__name__)

DIST_DIR = Path(__file__).parent.parent.parent / "dist"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_from_runs(runs: list) -> float:
    """Calcule un score de visibilité moyen à partir d'une liste de runs."""
    if not runs:
        return 0.0
    mentions = [r.mentioned_target for r in runs]
    per_query = [jl(r.mention_per_query) for r in runs]
    if not mentions:
        return 0.0
    mention_rate = sum(1 for m in mentions if m) / len(mentions)
    return round(mention_rate * 10, 1)


def _get_baseline(runs: list) -> Optional[TestRunDB]:
    """Retourne le run de référence (le plus ancien non-retest)."""
    non_retest = [r for r in runs if not (r.notes or "").startswith("retest:")]
    return non_retest[-1] if non_retest else (runs[-1] if runs else None)


def _get_last_retest(runs: list) -> Optional[TestRunDB]:
    """Retourne le dernier run de retest."""
    retests = [r for r in runs if (r.notes or "").startswith("retest:")]
    return retests[0] if retests else None  # sorted desc par ts


def get_retest_history(db: Session, prospect_id: str) -> list:
    """
    Retourne l'historique des retests pour un prospect.
    Chaque entrée contient : run_id, ts, score_approx, models, note.
    """
    runs = db_list_runs(db, prospect_id)
    history = []
    for r in sorted(runs, key=lambda x: x.ts, reverse=True):
        history.append({
            "run_id":    r.run_id,
            "ts":        r.ts.isoformat(),
            "model":     r.model,
            "mentioned": r.mentioned_target,
            "is_retest": (r.notes or "").startswith("retest:"),
            "note":      r.notes or "",
        })
    return history


# ── Génération rapport progression ───────────────────────────────────────────

def _progression_html(p: ProspectDB, current_runs: list, baseline_run: Optional[TestRunDB],
                      delta_score: float, new_comps: list, lost_comps: list) -> str:
    city = p.city.capitalize()
    score_now   = p.ia_visibility_score or 0
    score_base  = max(0.0, score_now - delta_score)
    trend_icon  = "📈" if delta_score > 0 else ("📉" if delta_score < 0 else "➡️")
    trend_label = f"+{delta_score:.1f}" if delta_score > 0 else f"{delta_score:.1f}"

    comp_rows = ""
    for c in new_comps:
        comp_rows += f'<tr><td>{c}</td><td style="color:#dc2626">Nouveau concurrent détecté</td></tr>'
    for c in lost_comps:
        comp_rows += f'<tr><td>{c}</td><td style="color:#16a34a">Plus cité (favorable)</td></tr>'
    if not comp_rows:
        comp_rows = '<tr><td colspan="2" style="color:#6b7280;text-align:center">Aucun changement de concurrent</td></tr>'

    base_date = baseline_run.ts.strftime("%d/%m/%Y") if baseline_run else "—"
    now_date  = datetime.utcnow().strftime("%d/%m/%Y")

    return f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rapport de progression — {p.name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e}}
.header{{background:linear-gradient(135deg,#1a0a4e,#0e2560);color:#fff;padding:32px 40px}}
.header h1{{font-size:22px;font-weight:800;margin-bottom:6px}}
.header p{{color:rgba(255,255,255,.7);font-size:13px}}
.body{{max-width:860px;margin:0 auto;padding:32px 24px}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.card h2{{color:#e94560;font-size:14px;margin-bottom:20px;text-transform:uppercase;letter-spacing:.5px}}
.score-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;text-align:center}}
.score-val{{font-size:48px;font-weight:900;letter-spacing:-2px}}
.score-lbl{{font-size:11px;color:#6b7280;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}}
.delta{{font-size:22px;font-weight:700;padding:8px 20px;border-radius:6px}}
.delta-pos{{background:#dcfce7;color:#16a34a}}
.delta-neg{{background:#fef2f2;color:#dc2626}}
.delta-neu{{background:#f3f4f6;color:#6b7280}}
table{{border-collapse:collapse;width:100%}}
th{{background:#f3f4f6;color:#6b7280;font-size:11px;padding:10px;text-align:left;font-weight:600}}
td{{padding:10px;border-bottom:1px solid #e5e7eb;font-size:13px}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600}}
.badge-active{{background:#dcfce7;color:#16a34a}}
</style>
</head>
<body>
<div class="header">
  <h1>Rapport de progression mensuel — {p.name}</h1>
  <p>{p.profession.capitalize()} à {city} &nbsp;·&nbsp; Rapport du {now_date} &nbsp;·&nbsp; Baseline : {base_date}</p>
</div>

<div class="body">

  <div class="card">
    <h2>Score de visibilité IA</h2>
    <div class="score-grid">
      <div>
        <div class="score-val" style="color:#6b7280">{score_base:.1f}</div>
        <div class="score-lbl">Score initial</div>
      </div>
      <div>
        <div style="font-size:36px;padding-top:8px">{trend_icon}</div>
        <div>
          <span class="delta {'delta-pos' if delta_score > 0 else ('delta-neg' if delta_score < 0 else 'delta-neu')}">
            {trend_label}
          </span>
        </div>
      </div>
      <div>
        <div class="score-val" style="color:#e94560">{score_now:.1f}</div>
        <div class="score-lbl">Score actuel</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Évolution des concurrents</h2>
    <table>
      <tr><th>Concurrent</th><th>Changement</th></tr>
      {comp_rows}
    </table>
  </div>

  <div class="card">
    <h2>Contrat actif</h2>
    <p style="font-size:13px;color:#374151">
      <span class="badge badge-active">Contrat actif</span>
      &nbsp; Le prochain retest sera effectué automatiquement dans 30 jours.
    </p>
    <p style="font-size:12px;color:#6b7280;margin-top:12px">
      {len(current_runs)} run(s) effectué(s) lors de ce cycle · Modèles : {", ".join({r.model for r in current_runs}) or "—"}
    </p>
  </div>

</div>
</body></html>"""


# ── Entrée principale ─────────────────────────────────────────────────────────

def run_retest(db: Session, prospect_id: str, dry_run: bool = False) -> dict:
    """
    Lance un cycle de re-test pour un prospect.

    En mode dry_run=True : simule le run sans appeler AI_INQUIRY_MODULE.
    En mode normal : tente d'appeler AI_INQUIRY_MODULE ; fallback dry_run si absent.

    Returns EURKAI contrat uniforme :
      {success, result: {run_id, score_delta, new_competitors, lost_competitors, file}, message, error}
    """
    p = db_get_prospect(db, prospect_id)
    if not p:
        return {"success": False, "result": None, "message": "",
                "error": {"code": "NOT_FOUND", "detail": f"Prospect {prospect_id} introuvable"}}

    all_runs = db_list_runs(db, prospect_id)
    all_runs_sorted = sorted(all_runs, key=lambda r: r.ts, reverse=True)
    baseline = _get_baseline(all_runs_sorted)

    # Baseline competitors
    baseline_comps = set()
    if baseline:
        try:
            baseline_comps = set(json.loads(baseline.competitors_entities or "[]"))
        except Exception:
            pass

    # Tenter un vrai run IA si pas dry_run
    new_run_id = None
    ai_result  = None

    if not dry_run:
        try:
            import AI_INQUIRY_MODULE as aim  # type: ignore
            queries = jl(baseline.queries) if baseline else [
                f"meilleur {p.profession} {p.city}",
                f"{p.profession} recommandé {p.city}",
                f"trouver {p.profession} {p.city}",
            ]
            ai_result = aim.run(
                profession=p.profession,
                city=p.city,
                prospect_name=p.name,
                queries=queries,
            )
        except (ImportError, Exception) as e:
            log.info("AI_INQUIRY_MODULE non disponible (%s) — mode dry_run", e)
            dry_run = True

    if dry_run or ai_result is None:
        # Simuler un résultat basé sur le score actuel
        mentioned = (p.ia_visibility_score or 0) >= 3.0
        ai_result = {
            "success": True,
            "result": {
                "mentioned_target": mentioned,
                "mention_per_query": [mentioned] * 3,
                "competitors": json.loads(p.competitors_cited or "[]")[:3],
                "queries": [
                    f"meilleur {p.profession} {p.city}",
                    f"{p.profession} recommandé {p.city}",
                    f"trouver {p.profession} {p.city}",
                ],
                "answers": ["[dry_run]"],
            },
            "message": "dry_run",
            "error": None,
        }

    if not ai_result.get("success"):
        return {"success": False, "result": None, "message": "",
                "error": {"code": "AI_ERROR", "detail": str(ai_result.get("error"))}}

    res = ai_result["result"]
    now = datetime.utcnow()

    # Créer le TestRunDB de retest
    retest_run = TestRunDB(
        campaign_id=p.campaign_id,
        prospect_id=prospect_id,
        ts=now,
        model="retest",
        queries=json.dumps(res.get("queries", [])),
        raw_answers=json.dumps(res.get("answers", [])),
        extracted_entities=json.dumps(res.get("competitors", [])),
        mentioned_target=res.get("mentioned_target", False),
        mention_per_query=json.dumps(res.get("mention_per_query", [])),
        competitors_entities=json.dumps(res.get("competitors", [])),
        notes=f"retest:{now.strftime('%Y-%m')}" + (" dry_run" if dry_run else ""),
    )
    db.add(retest_run)
    db.commit()
    db.refresh(retest_run)
    new_run_id = retest_run.run_id

    # Calcul delta
    current_comps = set(res.get("competitors", []))
    new_comps  = sorted(current_comps - baseline_comps)
    lost_comps = sorted(baseline_comps - current_comps)

    old_score = p.ia_visibility_score or 0
    new_score = round((sum(1 for m in res.get("mention_per_query", []) if m)
                       / max(len(res.get("mention_per_query", [1])), 1)) * 10, 1)
    delta = round(new_score - old_score, 1)

    # Mettre à jour le score du prospect
    p.ia_visibility_score = new_score
    db.commit()

    # Générer le rapport HTML
    out_dir = DIST_DIR / prospect_id / "livrables"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"retest_{now.strftime('%Y%m')}.html"
    report_path.write_text(
        _progression_html(p, [retest_run], baseline, delta, new_comps, lost_comps),
        encoding="utf-8",
    )

    return {
        "success": True,
        "result": {
            "run_id":          new_run_id,
            "score_before":    old_score,
            "score_after":     new_score,
            "score_delta":     delta,
            "new_competitors": new_comps,
            "lost_competitors": lost_comps,
            "dry_run":         dry_run,
            "file":            str(report_path),
        },
        "message": f"Retest effectué pour {p.name} — delta score : {'+' if delta >= 0 else ''}{delta}",
        "error": None,
    }
