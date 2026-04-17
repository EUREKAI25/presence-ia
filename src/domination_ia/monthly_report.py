"""
Rapport mensuel HTML — synthèse du delta mois-sur-mois.
"""

from datetime import date


def generate_monthly_report(
    delta: dict,
    company_name: str,
    city: str,
    business_type: str,
) -> str:
    """
    Génère un rapport HTML mensuel à partir du delta de la boucle mensuelle.
    Returns: HTML string
    """
    run_date    = delta.get("run_date", date.today().isoformat())
    score_now   = delta.get("score_current", 0)
    score_prev  = delta.get("score_previous")
    score_delta = delta.get("score_delta")
    trend       = delta.get("trend", "stable")
    changes     = delta.get("changes_summary", [])
    history     = delta.get("history", [])

    trend_color = {"up": "#10b981", "down": "#ef4444", "stable": "#f59e0b", "first_run": "#6366f1"}.get(trend, "#6b7280")
    trend_label = {"up": "↑ Progression", "down": "↓ Recul", "stable": "→ Stable", "first_run": "★ Premier audit"}.get(trend, "")

    delta_html = ""
    if score_delta is not None:
        sign = "+" if score_delta > 0 else ""
        delta_html = f'<span style="color:{trend_color};font-size:1.1rem;font-weight:700">{sign}{score_delta}</span>'

    history_rows = ""
    for run in reversed(history[-6:]):
        r_date  = run.get("date", "")
        r_score = run.get("score", 0)
        bar_w   = int(r_score / 10 * 100)
        history_rows += f"""
        <tr>
          <td style="padding:8px 12px;color:#94a3b8">{r_date}</td>
          <td style="padding:8px 12px">
            <div style="display:flex;align-items:center;gap:8px">
              <div style="width:120px;background:#1e293b;border-radius:4px;height:8px">
                <div style="width:{bar_w}%;background:#6366f1;height:8px;border-radius:4px"></div>
              </div>
              <span style="color:#e2e8f0;font-weight:600">{r_score}/10</span>
            </div>
          </td>
        </tr>"""

    changes_html = "\n".join(
        f'<li style="margin-bottom:6px;color:#cbd5e1">{c}</li>' for c in changes
    )

    new_comps  = delta.get("new_competitors", [])
    lost_comps = delta.get("lost_competitors", [])
    gained_q   = delta.get("queries_gained", [])
    lost_q     = delta.get("queries_lost", [])

    def badge_list(items, color):
        if not items:
            return '<span style="color:#475569;font-style:italic">Aucun</span>'
        return " ".join(
            f'<span style="background:{color}22;color:{color};padding:2px 8px;border-radius:12px;font-size:0.85rem">{i}</span>'
            for i in items
        )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Rapport mensuel — {company_name} — {run_date}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f172a; color: #e2e8f0; padding: 32px; min-height: 100vh; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 20px; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
  h2 {{ font-size: 1.1rem; color: #94a3b8; margin-bottom: 16px; font-weight: 500; }}
  h3 {{ font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.1em; color: #64748b; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  ul {{ list-style: none; padding: 0; }}
  @media print {{ body {{ background: white; color: black; }} .card {{ background: #f8fafc; }} }}
</style>
</head>
<body>

<div style="max-width:800px;margin:0 auto">

  <!-- Header -->
  <div class="card" style="background:linear-gradient(135deg,#1e1b4b,#312e81);border:1px solid #4338ca22">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px">
      <div>
        <h1>📊 Rapport mensuel — {company_name}</h1>
        <h2>{business_type} à {city} · {run_date}</h2>
      </div>
      <div style="background:#0f172a;border-radius:12px;padding:16px 24px;text-align:center">
        <div style="font-size:2.5rem;font-weight:800;color:#e2e8f0">{score_now}<span style="font-size:1rem;color:#64748b">/10</span></div>
        <div style="font-size:0.85rem;color:#94a3b8;margin-top:4px">Score IA actuel</div>
        <div style="margin-top:8px">{delta_html}</div>
        <div style="color:{trend_color};font-size:0.85rem;font-weight:600;margin-top:4px">{trend_label}</div>
      </div>
    </div>
  </div>

  <!-- Résumé des changements -->
  <div class="card">
    <h3>Ce qui a changé ce mois</h3>
    <ul>{changes_html}</ul>
  </div>

  <!-- Historique 6 mois -->
  <div class="card">
    <h3>Historique score (6 derniers mois)</h3>
    <table>{history_rows}</table>
  </div>

  <!-- Concurrents -->
  <div class="card">
    <h3>Concurrents</h3>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <div style="color:#94a3b8;font-size:0.85rem;margin-bottom:8px">Nouveaux concurrents détectés</div>
        {badge_list(new_comps, "#ef4444")}
      </div>
      <div>
        <div style="color:#94a3b8;font-size:0.85rem;margin-bottom:8px">Concurrents disparus</div>
        {badge_list(lost_comps, "#10b981")}
      </div>
    </div>
  </div>

  <!-- Requêtes -->
  <div class="card">
    <h3>Visibilité par requête</h3>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <div style="color:#94a3b8;font-size:0.85rem;margin-bottom:8px">Requêtes gagnées ✅</div>
        {badge_list(gained_q[:5], "#10b981")}
      </div>
      <div>
        <div style="color:#94a3b8;font-size:0.85rem;margin-bottom:8px">Requêtes perdues ⚠️</div>
        {badge_list(lost_q[:5], "#ef4444")}
      </div>
    </div>
  </div>

  <!-- Pied de page -->
  <div style="text-align:center;color:#334155;font-size:0.8rem;padding:16px 0">
    Rapport généré automatiquement par Présence IA · {run_date}
  </div>

</div>
</body>
</html>"""
