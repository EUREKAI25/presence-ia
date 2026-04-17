"""
Livrable Domination IA — HTML premium 8 sections.
"""

import json
from datetime import date
from pathlib import Path


def assemble_deliverable(
    company_name: str,
    city: str,
    business_type: str,
    website: str,
    # depuis implantation_ia
    methode_result: dict,
    competitor_analyses: list[dict],
    gaps: list[dict],
    strategy: dict,
    generated_contents: dict,
    # domination-specific
    all_competitor_analyses: list[dict],
    patterns: dict,
    domination_strategy: dict,
    content_plan: dict,
    monthly_report_html: str,
) -> dict:
    """
    Génère le livrable HTML complet Domination IA (8 sections).
    Returns: {html, json, path}
    """
    score_data = methode_result.get("score_data", {})
    score      = score_data.get("score", 0.0)
    slug       = f"{company_name.lower().replace(' ', '_')}_{city.lower().replace(' ', '_')}"
    out_date   = date.today().isoformat()

    html = _build_html(
        company_name, city, business_type, website, score, score_data,
        all_competitor_analyses, patterns, domination_strategy, content_plan,
        gaps, strategy, generated_contents, monthly_report_html, out_date,
    )

    out_dir  = Path(f"dist/domination_ia/{slug}")
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"domination_ia_{slug}_{out_date}.html"
    html_path.write_text(html, encoding="utf-8")

    payload = {
        "company_name":    company_name,
        "city":            city,
        "business_type":   business_type,
        "score":           score,
        "generated_at":    out_date,
        "total_competitors": len(all_competitor_analyses),
        "nb_gaps":         len(gaps),
        "axes":            [a.get("axis") for a in domination_strategy.get("axes", [])],
    }
    (out_dir / f"domination_ia_{slug}_{out_date}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {"html": html, "json": payload, "path": str(html_path)}


def _build_html(
    company_name, city, business_type, website, score, score_data,
    all_competitors, patterns, domination_strategy, content_plan,
    gaps, strategy, generated_contents, monthly_report_html, out_date,
) -> str:
    nb_comps   = len(all_competitors)
    nb_gaps    = len(gaps)
    nb_pages   = len(content_plan.get("local_pages", []))
    maturity   = patterns.get("market_maturity", "low")
    maturity_label = {"low": "Peu mature", "medium": "En développement", "high": "Mature"}.get(maturity, maturity)
    score_pct  = int(score / 10 * 100)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Domination IA — {company_name} — {city}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f172a; color: #e2e8f0; }}
  .section {{ padding: 40px; border-bottom: 1px solid #1e293b; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px; }}
  .badge {{ display:inline-block; padding:2px 10px; border-radius:12px; font-size:0.8rem; font-weight:600; }}
  .tag-green  {{ background:#10b98122; color:#10b981; }}
  .tag-orange {{ background:#f59e0b22; color:#f59e0b; }}
  .tag-red    {{ background:#ef444422; color:#ef4444; }}
  .tag-blue   {{ background:#6366f122; color:#6366f1; }}
  h2 {{ font-size:1.3rem; margin-bottom:4px; }}
  h3 {{ font-size:1rem; color:#94a3b8; font-weight:500; margin-bottom:20px; }}
  h4 {{ font-size:0.85rem; text-transform:uppercase; letter-spacing:0.1em; color:#64748b; margin-bottom:12px; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .grid3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
  .grid4 {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; }}
  code {{ background:#0f172a; padding:2px 6px; border-radius:4px; font-size:0.85rem; color:#a5f3fc; font-family:monospace; }}
  pre  {{ background:#0f172a; padding:16px; border-radius:8px; overflow:auto; font-size:0.82rem; color:#a5f3fc; white-space:pre-wrap; }}
  table {{ width:100%; border-collapse:collapse; }}
  td, th {{ padding:10px 12px; text-align:left; border-bottom:1px solid #1e293b; }}
  th {{ font-size:0.8rem; text-transform:uppercase; color:#64748b; font-weight:600; }}
  @media print {{
    body {{ background:white; color:black; }}
    .section {{ border-bottom:1px solid #ddd; }}
    .card {{ background:#f8fafc; }}
    pre {{ background:#f8fafc; color:#1e293b; }}
  }}
</style>
</head>
<body>

<!-- ══ HEADER ══════════════════════════════════════════════════════════ -->
<div style="background:linear-gradient(135deg,#0f172a,#1e1b4b);padding:48px 40px;border-bottom:1px solid #312e81">
  <div style="max-width:960px;margin:0 auto">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:24px">
      <div>
        <div style="color:#818cf8;font-size:0.85rem;font-weight:600;letter-spacing:0.1em;margin-bottom:8px">
          DOMINATION IA — STRATÉGIE COMPLÈTE
        </div>
        <h1 style="font-size:2rem;font-weight:800;color:#fff;margin-bottom:6px">{company_name}</h1>
        <div style="color:#94a3b8;font-size:1rem">{business_type} · {city} · Généré le {out_date}</div>
      </div>
      <div style="{_grid4_metrics_style()}">
        {_metric_box(str(round(score, 1)) + "/10", "Score IA", "#6366f1")}
        {_metric_box(str(nb_comps), "Concurrents analysés", "#8b5cf6")}
        {_metric_box(str(nb_gaps), "Écarts identifiés", "#a78bfa")}
        {_metric_box(str(nb_pages), "Pages à créer", "#c4b5fd")}
      </div>
    </div>
  </div>
</div>

<!-- ══ 1. AUDIT IA ══════════════════════════════════════════════════════ -->
<div class="section" style="max-width:960px;margin:0 auto">
  <h2>1 — Audit IA</h2>
  <h3>Visibilité actuelle sur les assistants IA</h3>
  {_audit_section(score, score_data, score_pct)}
</div>

<!-- ══ 2. ANALYSE CONCURRENTIELLE COMPLÈTE ════════════════════════════ -->
<div class="section" style="max-width:960px;margin:0 auto">
  <h2>2 — Analyse concurrentielle complète</h2>
  <h3>{nb_comps} acteurs analysés sur {business_type} à {city}</h3>
  {_competitors_section(all_competitors)}
</div>

<!-- ══ 3. PATTERNS DE DOMINATION ══════════════════════════════════════ -->
<div class="section" style="max-width:960px;margin:0 auto">
  <h2>3 — Patterns de domination</h2>
  <h3>Ce qui fait gagner sur ce marché · Maturité : {maturity_label}</h3>
  {_patterns_section(patterns)}
</div>

<!-- ══ 4. STRATÉGIE DOMINATION ════════════════════════════════════════ -->
<div class="section" style="max-width:960px;margin:0 auto">
  <h2>4 — Stratégie de domination</h2>
  <h3>{domination_strategy.get("positioning", "")[:120]}…</h3>
  {_strategy_section(domination_strategy)}
</div>

<!-- ══ 5. PLAN DE CONTENU 12 MOIS ═════════════════════════════════════ -->
<div class="section" style="max-width:960px;margin:0 auto">
  <h2>5 — Plan de contenu 12 mois</h2>
  <h3>Système de production mensuel</h3>
  {_content_plan_section(content_plan)}
</div>

<!-- ══ 6. CONTENUS GÉNÉRÉS ════════════════════════════════════════════ -->
<div class="section" style="max-width:960px;margin:0 auto">
  <h2>6 — Contenus générés</h2>
  <h3>Blocs copy-paste à intégrer immédiatement</h3>
  {_contents_section(generated_contents)}
</div>

<!-- ══ 7. ÉCARTS ET STRATÉGIE IMPLANTATION ════════════════════════════ -->
<div class="section" style="max-width:960px;margin:0 auto">
  <h2>7 — Écarts et plan d'implantation</h2>
  <h3>Ce qui manque et comment le corriger en 3 phases</h3>
  {_gaps_strategy_section(gaps, strategy)}
</div>

<!-- ══ 8. RAPPORT MENSUEL (TEMPLATE) ══════════════════════════════════ -->
<div style="max-width:960px;margin:0 auto;padding:40px">
  <h2 style="margin-bottom:8px">8 — Rapport mensuel automatisé</h2>
  <h3 style="color:#94a3b8;margin-bottom:24px">Template — mis à jour automatiquement chaque mois</h3>
  <div style="border:1px solid #312e81;border-radius:12px;overflow:hidden">
    {monthly_report_html}
  </div>
</div>

<!-- Footer -->
<div style="text-align:center;color:#334155;font-size:0.8rem;padding:32px">
  Livrable généré par Présence IA · Domination IA 9000€ · {out_date}
</div>

</body>
</html>"""


def _grid4_metrics_style():
    return "display:grid;grid-template-columns:repeat(2,1fr);gap:12px"


def _metric_box(value, label, color):
    return f"""
    <div style="background:#0f172a;border:1px solid {color}33;border-radius:10px;padding:14px 18px;text-align:center;min-width:100px">
      <div style="font-size:1.6rem;font-weight:800;color:{color}">{value}</div>
      <div style="font-size:0.75rem;color:#64748b;margin-top:4px">{label}</div>
    </div>"""


def _audit_section(score, score_data, score_pct):
    level       = score_data.get("score_level", "faible")
    total_q     = score_data.get("total_queries", 0)
    cited_q     = score_data.get("cited_queries", 0)
    by_model    = score_data.get("by_model", {})

    model_rows = ""
    for model, data in by_model.items():
        pct = data.get("pct", 0)
        bar = int(pct)
        model_rows += f"""
        <tr>
          <td style="color:#94a3b8;padding:8px 12px">{model}</td>
          <td style="padding:8px 12px">
            <div style="display:flex;align-items:center;gap:8px">
              <div style="width:160px;background:#0f172a;border-radius:4px;height:8px">
                <div style="width:{bar}%;background:#6366f1;height:8px;border-radius:4px"></div>
              </div>
              <span style="color:#e2e8f0">{pct}%</span>
            </div>
          </td>
        </tr>"""

    return f"""
    <div class="grid2">
      <div class="card">
        <h4>Score global</h4>
        <div style="display:flex;align-items:center;gap:20px">
          <div style="position:relative;width:80px;height:80px">
            <svg viewBox="0 0 36 36" width="80" height="80">
              <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                fill="none" stroke="#1e293b" stroke-width="3"/>
              <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                fill="none" stroke="#6366f1" stroke-width="3"
                stroke-dasharray="{score_pct}, 100"/>
            </svg>
            <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
                        font-size:1.1rem;font-weight:800;color:#e2e8f0">{round(score, 1)}</div>
          </div>
          <div>
            <div style="font-size:1.1rem;font-weight:700;color:#e2e8f0;margin-bottom:4px">{level.upper()}</div>
            <div style="color:#64748b;font-size:0.85rem">{cited_q}/{total_q} requêtes</div>
          </div>
        </div>
      </div>
      <div class="card">
        <h4>Par modèle IA</h4>
        <table>{model_rows}</table>
      </div>
    </div>"""


def _competitors_section(all_competitors):
    if not all_competitors:
        return '<div class="card" style="color:#64748b">Aucun concurrent analysé</div>'

    cards = ""
    for c in all_competitors:
        if c.get("error"):
            continue
        name    = c.get("name", "Inconnu")
        website = c.get("website", "")
        signals = c.get("signals", {})
        pages   = c.get("pages", {})
        strengths = c.get("strengths", [])
        rating  = signals.get("google_rating", "—")
        reviews = signals.get("review_count", "—")

        page_badges = ""
        for key, label in [("faq","FAQ"),("blog","Blog"),("pages_locales","Local"),("pages_services","Services")]:
            color = "#10b981" if pages.get(key) else "#334155"
            page_badges += f'<span class="badge" style="background:{color}22;color:{color}">{label}</span> '

        strength_items = "".join(f"<li style='color:#94a3b8;font-size:0.85rem;margin-bottom:4px'>• {s}</li>" for s in strengths[:3])

        cards += f"""
        <div class="card">
          <div style="font-weight:700;color:#e2e8f0;margin-bottom:6px">{name}</div>
          {"<div style='color:#64748b;font-size:0.8rem;margin-bottom:8px'>" + website + "</div>" if website else ""}
          <div style="margin-bottom:10px">{page_badges}</div>
          <div style="display:flex;gap:16px;margin-bottom:10px">
            <div style="font-size:0.82rem;color:#94a3b8">⭐ {rating} · {reviews} avis</div>
          </div>
          {"<ul style='padding:0'>" + strength_items + "</ul>" if strengths else ""}
        </div>"""

    return f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px">{cards}</div>'


def _patterns_section(patterns):
    winning  = patterns.get("winning_formula", "")
    opps     = patterns.get("opportunities", [])
    formats  = patterns.get("dominant_formats", [])
    signals  = patterns.get("content_signals", [])
    trust    = patterns.get("trust_signals", {})
    prev     = patterns.get("content_prevalence", {})

    opp_html = "\n".join(f'<li style="margin-bottom:8px;color:#cbd5e1">✦ {o}</li>' for o in opps)
    fmt_html = " ".join(f'<span class="badge tag-blue">{f}</span>' for f in formats)
    sig_html = "\n".join(f'<li style="margin-bottom:6px;color:#94a3b8;font-size:0.85rem">→ {s}</li>' for s in signals)

    return f"""
    <div class="card" style="margin-bottom:16px">
      <h4>Formule gagnante</h4>
      <p style="color:#cbd5e1;line-height:1.6">{winning}</p>
    </div>
    <div class="grid2" style="margin-bottom:16px">
      <div class="card">
        <h4>Opportunités</h4>
        <ul style="list-style:none">{opp_html}</ul>
      </div>
      <div class="card">
        <h4>Signaux observés</h4>
        <ul style="list-style:none">{sig_html}</ul>
        <div style="margin-top:12px;color:#94a3b8;font-size:0.82rem">
          Moyenne : ⭐ {trust.get('avg_rating', '—')} · {trust.get('avg_reviews', '—')} avis
          · Seuil : {trust.get('min_reviews_to_compete', '—')}+
        </div>
      </div>
    </div>
    <div class="card">
      <h4>Formats dominants</h4>
      <div>{fmt_html}</div>
    </div>"""


def _strategy_section(domination_strategy):
    positioning = domination_strategy.get("positioning", "")
    axes        = domination_strategy.get("axes", [])
    moat        = domination_strategy.get("moat", "")
    timeline    = domination_strategy.get("timeline", "")

    colors = {"contenu": "#6366f1", "structure": "#8b5cf6", "autorité": "#a78bfa"}

    axes_html = ""
    for ax in axes:
        color   = colors.get(ax.get("axis", ""), "#6366f1")
        actions = ax.get("actions", [])
        act_html = "\n".join(f'<li style="margin-bottom:6px;color:#cbd5e1">→ {a}</li>' for a in actions)
        axes_html += f"""
        <div class="card" style="border-top:3px solid {color}">
          <div style="color:{color};font-size:0.85rem;font-weight:700;margin-bottom:8px">{ax.get('title','')}</div>
          <div style="color:#94a3b8;font-size:0.85rem;margin-bottom:12px">{ax.get('goal','')}</div>
          <ul style="list-style:none;margin-bottom:12px">{act_html}</ul>
          <div style="background:#0f172a;padding:8px 12px;border-radius:6px;font-size:0.8rem;color:#64748b">
            KPI : {ax.get('kpi','')}
          </div>
        </div>"""

    return f"""
    <div class="card" style="margin-bottom:16px">
      <h4>Positionnement</h4>
      <p style="color:#cbd5e1;line-height:1.6">{positioning}</p>
    </div>
    <div class="grid3" style="margin-bottom:16px">{axes_html}</div>
    <div class="grid2">
      <div class="card">
        <h4>Avantage défendable (Moat)</h4>
        <p style="color:#cbd5e1;font-size:0.9rem;line-height:1.6">{moat}</p>
      </div>
      <div class="card">
        <h4>Timeline</h4>
        <p style="color:#10b981;font-size:1rem;font-weight:600">{timeline}</p>
      </div>
    </div>"""


def _content_plan_section(content_plan):
    quota      = content_plan.get("monthly_quota", {})
    calendar   = content_plan.get("calendar_12", [])
    signals    = content_plan.get("content_signals", [])
    local_pgs  = content_plan.get("local_pages", [])

    quota_items = "".join(
        f'<div style="text-align:center;padding:12px"><div style="font-size:1.4rem;font-weight:800;color:#6366f1">{v}</div>'
        f'<div style="font-size:0.75rem;color:#64748b">{k.replace("_"," ")}</div></div>'
        for k, v in quota.items() if k != "description"
    )

    cal_rows = ""
    for m in calendar:
        status_color = {"actif": "#10b981", "planifié": "#f59e0b", "anticipé": "#64748b"}.get(m.get("status"), "#64748b")
        pages_str = ", ".join(m.get("pages", [])) or "—"
        cal_rows += f"""
        <tr>
          <td style="color:#94a3b8">{m.get('month_name')}</td>
          <td><span class="badge" style="background:{status_color}22;color:{status_color}">{m.get('status')}</span></td>
          <td style="color:#cbd5e1;font-size:0.85rem">{m.get('focus','')}</td>
          <td style="color:#94a3b8;font-size:0.82rem">{pages_str[:50]}</td>
          <td style="color:#f59e0b">+{m.get('avis',0)} avis</td>
        </tr>"""

    sig_html = "\n".join(f'<li style="margin-bottom:6px;color:#94a3b8;font-size:0.85rem">→ {s}</li>' for s in signals)

    pages_high = [p for p in local_pgs if p.get("priority") == "high"]
    pg_html = " ".join(f'<span class="badge tag-blue">{p["title"]}</span>' for p in pages_high[:5])

    return f"""
    <div class="card" style="margin-bottom:16px">
      <h4>Quota mensuel</h4>
      <div style="display:flex;flex-wrap:wrap;gap:8px">{quota_items}</div>
      <div style="margin-top:12px;color:#64748b;font-size:0.85rem">{quota.get('description','')}</div>
    </div>
    <div class="card" style="margin-bottom:16px">
      <h4>Pages locales prioritaires</h4>
      <div>{pg_html}</div>
    </div>
    <div class="card" style="margin-bottom:16px">
      <h4>Calendrier 12 mois</h4>
      <table>
        <tr><th>Mois</th><th>Statut</th><th>Focus</th><th>Pages</th><th>Avis</th></tr>
        {cal_rows}
      </table>
    </div>
    <div class="card">
      <h4>Signaux contextuels</h4>
      <ul style="list-style:none">{sig_html}</ul>
    </div>"""


def _contents_section(generated_contents):
    if not generated_contents:
        return '<div class="card" style="color:#64748b">Contenus non générés (mode skip)</div>'

    blocks = []
    for key, value in generated_contents.items():
        if not value or not isinstance(value, str):
            continue
        label = key.replace("_", " ").title()
        content_escaped = value.replace("<", "&lt;").replace(">", "&gt;")
        blocks.append(f"""
        <div class="card" style="margin-bottom:12px">
          <h4>{label}</h4>
          <pre>{content_escaped[:600]}{"..." if len(value) > 600 else ""}</pre>
        </div>""")

    return "\n".join(blocks) if blocks else '<div class="card" style="color:#64748b">Aucun contenu généré</div>'


def _gaps_strategy_section(gaps, strategy):
    priority_colors = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}

    gap_rows = ""
    for g in gaps:
        prio  = g.get("priority", "medium")
        color = priority_colors.get(prio, "#94a3b8")
        gap_rows += f"""
        <tr>
          <td style="color:#e2e8f0">{g.get('gap','')}</td>
          <td style="color:#94a3b8;font-size:0.85rem">{g.get('impact','')[:60]}</td>
          <td><span class="badge" style="background:{color}22;color:{color}">{prio}</span></td>
        </tr>"""

    phases = strategy.get("phases", [])
    phase_colors = ["#ef4444", "#f59e0b", "#10b981"]
    phases_html = ""
    for i, phase in enumerate(phases):
        color = phase_colors[i] if i < len(phase_colors) else "#6366f1"
        steps = phase.get("steps", [])
        steps_html = "\n".join(f'<li style="color:#cbd5e1;margin-bottom:4px;font-size:0.85rem">→ {s}</li>' for s in steps)
        phases_html += f"""
        <div class="card" style="border-top:3px solid {color}">
          <div style="color:{color};font-weight:700;margin-bottom:6px">{phase.get('phase','')}</div>
          <div style="color:#64748b;font-size:0.82rem;margin-bottom:10px">{phase.get('duration','')}</div>
          <ul style="list-style:none">{steps_html}</ul>
        </div>"""

    return f"""
    <div class="card" style="margin-bottom:16px">
      <h4>Écarts détectés</h4>
      <table>
        <tr><th>Écart</th><th>Impact</th><th>Priorité</th></tr>
        {gap_rows}
      </table>
    </div>
    <div class="grid3">{phases_html}</div>"""
