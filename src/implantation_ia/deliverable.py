"""
Assembleur du livrable Implantation IA (offre 3500€).
Livrable premium — étend le design du 500€ avec sections concurrentielles + contenus.
"""
import html
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "dist" / "implantation_ia"


def _esc(s) -> str:
    return html.escape(str(s or ""))


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:30]


def _score_color(score: float) -> str:
    if score < 3:   return "#e53e3e"
    if score < 6:   return "#dd6b20"
    if score < 8:   return "#d69e2e"
    return "#38a169"


def _score_label_fr(score: float) -> str:
    if score < 1:   return "Absent"
    if score < 3:   return "Très faible"
    if score < 5:   return "Faible"
    if score < 7:   return "Moyen"
    if score < 9:   return "Bon"
    return "Excellent"


def _priority_badge(p: str) -> str:
    m = {"high": ("#e53e3e","Priorité haute"), "medium": ("#dd6b20","Priorité moyenne"), "low": ("#718096","Priorité basse")}
    color, label = m.get(p, ("#718096", p))
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700">{label}</span>'


# ── Section 1 : Audit (repris du 500) ──────────────────────────────────────

def _audit_summary_html(score_data: dict, diagnostic: dict, score: float) -> str:
    color = _score_color(score)
    label = _score_label_fr(score)
    pct   = min(100, int(score * 10))
    return f"""
<div style="background:#f7fafc;border:1px solid #e2e8f0;border-radius:12px;padding:24px;display:flex;gap:28px;align-items:center;flex-wrap:wrap">
  <div style="text-align:center;flex-shrink:0">
    <div style="width:100px;height:100px;border-radius:50%;
                background:conic-gradient({color} {pct}%,#e2e8f0 0);
                display:flex;align-items:center;justify-content:center;
                box-shadow:0 0 0 6px #fff inset;margin:0 auto">
      <div><div style="font-size:24px;font-weight:800;color:{color}">{score}</div>
           <div style="font-size:10px;color:#718096">/10</div></div>
    </div>
    <div style="margin-top:8px;font-weight:700;color:{color};font-size:14px">{label}</div>
  </div>
  <div style="flex:1;min-width:180px">
    <p style="color:#4a5568;font-size:14px;margin-bottom:10px">{_esc(diagnostic.get('summary',''))}</p>
    <div style="font-size:12px;color:#718096;background:#edf2f7;padding:8px 12px;border-radius:6px">
      {_esc(diagnostic.get('model_analysis',''))}
    </div>
  </div>
</div>"""


def _queries_table_html(queries: list[dict]) -> str:
    if not queries:
        return "<p style='color:#718096'>Aucune requête testée.</p>"
    models_present = [m for m in ["chatgpt", "gemini", "claude"]
                      if any(row.get(m) is not None for row in queries)]
    labels = {"chatgpt": "ChatGPT", "gemini": "Gemini", "claude": "Claude"}
    headers = "".join(f"<th>{labels[m]}</th>" for m in models_present)
    rows    = ""
    for row in queries:
        q = _esc(row.get("query_display") or row.get("query", ""))
        cells = ""
        for m in models_present:
            val = row.get(m)
            if val is None:
                cells += "<td style='color:#cbd5e0'>—</td>"
            elif val:
                cells += "<td style='color:#38a169;font-size:16px'>✓</td>"
            else:
                cells += "<td style='color:#e53e3e;font-size:16px'>✗</td>"
        rows += f"<tr><td style='text-align:left;padding:8px 12px;font-size:13px'>{q}</td>{cells}</tr>"
    return f"""<table style="width:100%;border-collapse:collapse;font-size:13px">
  <thead><tr style="background:#f7fafc">
    <th style="text-align:left;padding:8px 12px;color:#4a5568">Requête</th>{headers}
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""


# ── Section 2 : Concurrents ─────────────────────────────────────────────────

def _competitor_card(comp: dict, rank: int) -> str:
    name    = _esc(comp.get("name", ""))
    website = comp.get("website", "")
    count   = comp.get("count", 0)
    rating  = comp.get("google_rating", "")
    reviews = comp.get("review_count", "")
    years   = comp.get("years_experience", "")
    strengths = comp.get("strengths", [])
    why_cited = comp.get("why_cited", "")
    error     = comp.get("error")

    pages = [
        ("FAQ",           comp.get("has_faq")),
        ("Pages locales", comp.get("has_local_pages")),
        ("Blog",          comp.get("has_blog")),
        ("Pages services",comp.get("has_services")),
    ]
    pages_html = "".join(
        f'<span style="background:{("#38a169" if v else "#e2e8f0")};color:{("#fff" if v else "#718096")};'
        f'padding:2px 8px;border-radius:10px;font-size:11px;margin-right:4px">{l}</span>'
        for l, v in pages
    )

    signals_html = ""
    if rating:
        signals_html += f'<span style="color:#d69e2e;font-weight:700">★ {rating}/5</span>'
    if reviews:
        signals_html += f' <span style="color:#718096;font-size:12px">({reviews} avis)</span>'
    if years:
        signals_html += f' <span style="color:#4a5568;font-size:12px;margin-left:8px">· {years} ans exp.</span>'

    website_link = f'<a href="{_esc(website)}" target="_blank" style="color:#667eea;font-size:12px">{_esc(website)}</a>' if website else '<span style="color:#718096;font-size:12px">Site non identifié</span>'

    strengths_html = "".join(
        f'<li style="color:#4a5568;font-size:13px;margin-bottom:4px">{_esc(s)}</li>'
        for s in strengths[:3]
    )

    error_html = f'<div style="color:#e53e3e;font-size:12px;margin-top:8px">⚠ Analyse incomplète : {_esc(error)}</div>' if error else ""

    return f"""<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin-bottom:16px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
    <div>
      <span style="background:#667eea;color:#fff;width:24px;height:24px;border-radius:50%;
                   display:inline-flex;align-items:center;justify-content:center;font-size:12px;
                   font-weight:700;margin-right:8px">#{rank}</span>
      <strong style="font-size:17px;color:#1a202c">{name}</strong>
      {f'<span style="background:#e53e3e;color:#fff;padding:1px 6px;border-radius:8px;font-size:11px;margin-left:8px">cité {count}× par les IA</span>' if count else ""}
    </div>
    {website_link}
  </div>
  <div style="margin-bottom:10px">{pages_html}</div>
  {f'<div style="margin-bottom:10px">{signals_html}</div>' if signals_html else ""}
  {f'<div style="font-size:13px;color:#2d3748;font-style:italic;margin-bottom:10px;padding:10px;background:#f7fafc;border-radius:6px">"{_esc(why_cited)}"</div>' if why_cited else ""}
  {f'<ul style="list-style:none;padding:0;margin:0">{strengths_html}</ul>' if strengths else ""}
  {error_html}
</div>"""


# ── Section 3 : Écarts ──────────────────────────────────────────────────────

def _gaps_table(gaps: list[dict]) -> str:
    if not gaps:
        return "<p style='color:#38a169'>✓ Aucun écart critique identifié.</p>"
    rows = ""
    for g in gaps:
        rows += f"""<tr style="border-bottom:1px solid #e2e8f0">
  <td style="padding:12px;font-weight:600;color:#2d3748">{_esc(g['gap'])}</td>
  <td style="padding:12px;font-size:13px;color:#718096">{_esc(g['impact'])}</td>
  <td style="padding:12px;white-space:nowrap">{_priority_badge(g['priority'])}</td>
</tr>"""
    return f"""<table style="width:100%;border-collapse:collapse">
  <thead><tr style="background:#f7fafc">
    <th style="text-align:left;padding:10px 12px;font-size:13px">Écart identifié</th>
    <th style="text-align:left;padding:10px 12px;font-size:13px">Impact</th>
    <th style="width:140px;padding:10px 12px;font-size:13px">Priorité</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""


# ── Section 4 : Stratégie ───────────────────────────────────────────────────

def _strategy_html(strategy: dict) -> str:
    phase_colors = {"immediate": "#e53e3e", "short_term": "#dd6b20", "optimization": "#38a169"}
    phases_html  = ""
    for ph in strategy.get("phases", []):
        color = phase_colors.get(ph["phase"], "#667eea")
        steps = "".join(
            f'<li style="margin-bottom:8px;color:#4a5568;font-size:14px;display:flex;gap:8px">'
            f'<span style="color:{color};flex-shrink:0;margin-top:2px">→</span>{_esc(s)}</li>'
            for s in ph["steps"]
        )
        phases_html += f"""<div style="border-left:3px solid {color};padding:16px 20px;margin-bottom:20px">
  <div style="font-weight:700;color:#1a202c;margin-bottom:10px">{_esc(ph['label'])}</div>
  <ul style="list-style:none;padding:0;margin:0">{steps}</ul>
</div>"""

    edge = _esc(strategy.get("competitive_edge", ""))
    edge_html = f"""<div style="background:#ebf8ff;border:1px solid #bee3f8;border-radius:8px;padding:16px;margin-top:16px">
  <div style="font-weight:700;color:#2b6cb0;margin-bottom:6px">💡 Votre avantage concurrentiel</div>
  <p style="color:#2c5282;font-size:14px">{edge}</p>
</div>""" if edge else ""

    return phases_html + edge_html


# ── Section 5 : Contenus ───────────────────────────────────────────────────

def _faq_preview(faq: list[dict]) -> str:
    if not faq:
        return "<p style='color:#718096'>FAQ non générée.</p>"
    items = "".join(
        f'<div style="border-bottom:1px solid #edf2f7;padding:12px 0">'
        f'<div style="font-weight:600;color:#2d3748;font-size:14px">Q : {_esc(f["question"])}</div>'
        f'<div style="color:#718096;font-size:13px;margin-top:4px">R : {_esc(f["answer"])}</div>'
        f'</div>'
        for f in faq[:5]
    )
    total = len(faq)
    return f"""{items}
<div style="margin-top:12px;font-size:12px;color:#a0aec0;text-align:center">
  {total} questions générées — FAQ complète dans les fichiers fournis
</div>"""


def _code_block(label: str, content: str, dark: bool = False) -> str:
    bg = "#1a202c" if dark else "#f7fafc"
    color = "#e2e8f0" if dark else "#2d3748"
    border = "" if dark else "border:1px solid #e2e8f0;"
    return f"""<div style="margin-bottom:20px">
  <div style="font-size:13px;font-weight:700;color:#4a5568;margin-bottom:6px">{label}</div>
  <pre style="background:{bg};color:{color};{border}padding:16px;border-radius:8px;
              font-size:12px;line-height:1.6;overflow-x:auto;white-space:pre-wrap">{_esc(content)}</pre>
</div>"""


# ── Assembleur principal ──────────────────────────────────────────────────

def assemble_deliverable(
    company_name: str,
    city: str,
    business_type: str,
    website: str,
    # Du pipeline 500
    score_data: dict,
    queries: list[dict],
    diagnostic: dict,
    action_plan: list[dict],
    # Spécifique 3500
    competitor_summaries: list[dict],
    gaps: list[dict],
    strategy: dict,
    generated_contents: dict,
    generated_at: str = "",
) -> dict:
    """
    Assemble le livrable complet Implantation IA (7 sections).

    Returns:
        {"html": str, "json": dict, "path": str}
    """
    if not generated_at:
        generated_at = datetime.now().strftime("%d/%m/%Y à %Hh%M")

    score = score_data.get("score", 0.0)
    faq   = generated_contents.get("faq", [])
    ia_b  = generated_contents.get("ia_blocks", {})

    deliverable_json = {
        "offer":              "Implantation IA — 3 500€",
        "company_name":       company_name,
        "city":               city,
        "business_type":      business_type,
        "website":            website,
        "generated_at":       generated_at,
        "score_data":         score_data,
        "queries":            queries,
        "diagnostic":         diagnostic,
        "action_plan":        action_plan,
        "competitors":        competitor_summaries,
        "gaps":               gaps,
        "strategy":           strategy,
        "contents":           {
            "faq":           faq,
            "ia_blocks":     ia_b,
            "files":         generated_contents.get("paths", {}),
        },
    }

    # Action plan rows
    ap_rows = ""
    for i, item in enumerate(action_plan, 1):
        diff_color = {"easy": "#38a169", "medium": "#d69e2e", "hard": "#e53e3e"}.get(item.get("difficulty", ""), "#718096")
        diff_label = {"easy": "Facile", "medium": "Moyen", "hard": "Difficile"}.get(item.get("difficulty", ""), "")
        ap_rows += f"""<tr style="border-bottom:1px solid #e2e8f0">
  <td style="padding:10px;color:#718096;font-size:12px">{i}</td>
  <td style="padding:10px">
    <div style="font-weight:600;font-size:14px;margin-bottom:2px">{_esc(item['action'])}</div>
    <div style="color:#718096;font-size:12px">{_esc(item['impact'])}</div>
  </td>
  <td style="padding:10px;white-space:nowrap">{_priority_badge(item['priority'])}</td>
  <td style="padding:10px;font-size:12px;color:{diff_color};font-weight:600">● {diff_label}</td>
</tr>"""

    html_doc = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Implantation IA — {_esc(company_name)}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#2d3748;background:#fff;font-size:15px;line-height:1.6}}
  .page{{max-width:900px;margin:0 auto;padding:40px 24px 80px}}
  .section{{margin-bottom:52px}}
  .section-title{{font-size:20px;font-weight:800;color:#1a202c;
                  border-left:4px solid #667eea;padding-left:14px;margin-bottom:20px}}
  .subsection{{margin-bottom:28px}}
  .subsection-title{{font-size:15px;font-weight:700;color:#4a5568;margin-bottom:12px;
                     padding-bottom:6px;border-bottom:1px solid #edf2f7}}
  table{{width:100%;border-collapse:collapse}}
  th{{background:#edf2f7;padding:10px 12px;text-align:left;font-size:13px;font-weight:700;color:#4a5568}}
  td{{padding:10px 12px;text-align:center;border-bottom:1px solid #edf2f7}}
  @media print{{body{{font-size:12px}}.page{{padding:20px}}pre{{font-size:10px!important}}}}
</style>
</head>
<body>
<div class="page">

<!-- HEADER PREMIUM -->
<div style="background:linear-gradient(135deg,#1a202c 0%,#2d3748 50%,#4a5568 100%);
            color:#fff;border-radius:16px;padding:40px;margin-bottom:52px;position:relative;overflow:hidden">
  <div style="position:absolute;top:-30px;right:-30px;width:200px;height:200px;
              background:rgba(102,126,234,.15);border-radius:50%"></div>
  <div style="font-size:12px;color:rgba(255,255,255,.6);text-transform:uppercase;
              letter-spacing:2px;margin-bottom:8px">IMPLANTATION IA — OFFRE 3 500€</div>
  <h1 style="font-size:30px;font-weight:800;margin-bottom:8px">{_esc(company_name)}</h1>
  <div style="font-size:17px;color:rgba(255,255,255,.85)">{_esc(business_type.capitalize())} à {_esc(city)}</div>
  {f'<div style="font-size:13px;color:rgba(255,255,255,.5);margin-top:6px">{_esc(website)}</div>' if website else ''}
  <div style="display:flex;gap:24px;margin-top:24px;flex-wrap:wrap">
    <div style="background:rgba(255,255,255,.1);border-radius:8px;padding:10px 18px;text-align:center">
      <div style="font-size:22px;font-weight:800;color:#667eea">{score_data.get("score",0)}</div>
      <div style="font-size:11px;opacity:.7">Score IA</div>
    </div>
    <div style="background:rgba(255,255,255,.1);border-radius:8px;padding:10px 18px;text-align:center">
      <div style="font-size:22px;font-weight:800;color:#68d391">{len(competitor_summaries)}</div>
      <div style="font-size:11px;opacity:.7">Concurrents analysés</div>
    </div>
    <div style="background:rgba(255,255,255,.1);border-radius:8px;padding:10px 18px;text-align:center">
      <div style="font-size:22px;font-weight:800;color:#fc8181">{len(gaps)}</div>
      <div style="font-size:11px;opacity:.7">Écarts identifiés</div>
    </div>
    <div style="background:rgba(255,255,255,.1);border-radius:8px;padding:10px 18px;text-align:center">
      <div style="font-size:22px;font-weight:800;color:#fbd38d">{len(faq)}</div>
      <div style="font-size:11px;opacity:.7">Q/R FAQ générées</div>
    </div>
  </div>
  <div style="font-size:12px;opacity:.5;margin-top:16px">Généré le {_esc(generated_at)}</div>
</div>

<!-- 1. AUDIT IA -->
<div class="section">
  <div class="section-title">1. Audit IA — Visibilité actuelle</div>
  {_audit_summary_html(score_data, diagnostic, score)}
  <div style="margin-top:16px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
    {_queries_table_html(queries)}
  </div>
  <div style="margin-top:8px;font-size:12px;color:#a0aec0">
    ✓ = cité &nbsp;|&nbsp; ✗ = non cité &nbsp;|&nbsp; — = non testé
  </div>
</div>

<!-- 2. TOP 3 CONCURRENTS -->
<div class="section">
  <div class="section-title">2. TOP 3 concurrents cités par les IA</div>
  {("".join(_competitor_card(c, i+1) for i, c in enumerate(competitor_summaries))) if competitor_summaries else '<p style="color:#718096">Aucun concurrent identifié dans les réponses IA.</p>'}
</div>

<!-- 3. ANALYSE DES ÉCARTS -->
<div class="section">
  <div class="section-title">3. Analyse des écarts — vous vs vos concurrents</div>
  <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
    {_gaps_table(gaps)}
  </div>
</div>

<!-- 4. STRATÉGIE D'IMPLANTATION -->
<div class="section">
  <div class="section-title">4. Stratégie d'implantation — 3 phases</div>
  {_strategy_html(strategy)}
</div>

<!-- 5. PLAN D'ACTION DÉTAILLÉ (du pipeline 500) -->
<div class="section">
  <div class="section-title">5. Plan d'action détaillé</div>
  <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
    <table>
      <thead><tr style="background:#f7fafc">
        <th style="width:40px">#</th>
        <th>Action</th>
        <th style="width:140px">Priorité</th>
        <th style="width:100px">Difficulté</th>
      </tr></thead>
      <tbody>{ap_rows}</tbody>
    </table>
  </div>
</div>

<!-- 6. CONTENUS GÉNÉRÉS -->
<div class="section">
  <div class="section-title">6. Contenus générés — prêts à intégrer</div>

  <div class="subsection">
    <div class="subsection-title">📋 Balises SEO + IA (à intégrer sur votre site)</div>
    {_code_block("Balise &lt;title&gt;", ia_b.get("title_tag", ""))}
    {_code_block("Balise &lt;meta name='description'&gt;", ia_b.get("meta_description", ""))}
    {_code_block("Paragraphe d'introduction — Page d'accueil", ia_b.get("homepage_intro", ""))}
    {_code_block("Description Google Business Profile", ia_b.get("gbp_description", ""))}
  </div>

  <div class="subsection">
    <div class="subsection-title">❓ FAQ — {len(faq)} questions/réponses</div>
    <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:20px">
      {_faq_preview(faq)}
    </div>
  </div>

  <div class="subsection">
    <div class="subsection-title">🔧 JSON-LD LocalBusiness (à placer dans &lt;head&gt;)</div>
    {_code_block("JSON-LD LocalBusiness", ia_b.get("jsonld_localbusiness", ""), dark=True)}
  </div>

  <div class="subsection">
    <div class="subsection-title">📄 Fichiers fournis</div>
    <div style="background:#f7fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px">
      {"".join(f'<div style="font-size:13px;color:#4a5568;margin-bottom:6px">📁 {_esc(k)} → <code style="background:#edf2f7;padding:2px 6px;border-radius:4px;font-size:11px">{_esc(v)}</code></div>' for k, v in generated_contents.get("paths", {}).items())}
    </div>
  </div>
</div>

<!-- 7. PROCHAINES ACTIONS -->
<div class="section">
  <div class="section-title">7. Prochaines actions — par où commencer</div>
  <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px">
    <ol style="padding-left:20px;color:#4a5568">
      {"".join(f'<li style="margin-bottom:12px;font-size:14px">{_esc(s)}</li>' for s in (strategy.get("phases",[{}])[0].get("steps", []))[:5])}
    </ol>
    <div style="margin-top:16px;padding:14px;background:#ebf8ff;border-radius:8px;font-size:13px;color:#2b6cb0">
      <strong>Re-test recommandé dans 6-8 semaines</strong> pour mesurer la progression de votre score IA.
    </div>
  </div>
</div>

<!-- FOOTER -->
<div style="margin-top:64px;padding-top:24px;border-top:1px solid #e2e8f0;
            text-align:center;color:#a0aec0;font-size:12px">
  Implantation IA — {_esc(company_name)} — Généré le {_esc(generated_at)}<br>
  <span style="font-size:11px">Document confidentiel — {_esc(company_name)}</span>
</div>

</div>
</body>
</html>"""

    # Sauvegarde
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fname    = f"implantation_ia_{_slug(company_name)}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    out_path = _OUTPUT_DIR / fname
    out_path.write_text(html_doc, encoding="utf-8")

    return {
        "html": html_doc,
        "json": deliverable_json,
        "path": str(out_path),
    }
