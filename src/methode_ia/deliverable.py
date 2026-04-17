"""
Assembleur du livrable client — Méthode Présence IA.
Génère le document HTML final prêt à envoyer au client.
"""
import html
import json
from datetime import datetime
from pathlib import Path

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "dist" / "methode_ia"


def _esc(s: str) -> str:
    return html.escape(str(s or ""))


def _score_color(score: float) -> str:
    if score < 3:
        return "#e53e3e"
    if score < 6:
        return "#dd6b20"
    if score < 8:
        return "#d69e2e"
    return "#38a169"


def _score_label_fr(score: float) -> str:
    if score < 1:
        return "Absent"
    if score < 3:
        return "Très faible"
    if score < 5:
        return "Faible"
    if score < 7:
        return "Moyen"
    if score < 9:
        return "Bon"
    return "Excellent"


def _priority_badge(p: str) -> str:
    colors = {"high": ("#e53e3e", "Priorité haute"), "medium": ("#dd6b20", "Priorité moyenne"), "low": ("#718096", "Priorité basse")}
    color, label = colors.get(p, ("#718096", p))
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700">{label}</span>'


def _difficulty_badge(d: str) -> str:
    colors = {"easy": ("#38a169", "Facile"), "medium": ("#d69e2e", "Moyen"), "hard": ("#e53e3e", "Difficile")}
    color, label = colors.get(d, ("#718096", d))
    return f'<span style="color:{color};font-size:11px;font-weight:600">● {label}</span>'


def _queries_table(queries: list[dict]) -> str:
    if not queries:
        return "<p style='color:#718096'>Aucune requête testée.</p>"

    rows = ""
    model_labels = {"chatgpt": "ChatGPT", "gemini": "Gemini", "claude": "Claude"}
    models_present = [m for m in ["chatgpt", "gemini", "claude"]
                      if any(row.get(m) is not None for row in queries)]

    headers = "".join(f"<th>{model_labels[m]}</th>" for m in models_present)

    for row in queries:
        q = _esc(row.get("query_display") or row.get("query", ""))
        cells = ""
        for m in models_present:
            val = row.get(m)
            if val is None:
                cells += "<td style='color:#cbd5e0'>—</td>"
            elif val:
                cells += "<td style='color:#38a169;font-size:18px'>✓</td>"
            else:
                cells += "<td style='color:#e53e3e;font-size:18px'>✗</td>"
        rows += f"<tr><td style='text-align:left;padding:8px 12px'>{q}</td>{cells}</tr>"

    return f"""<table style="width:100%;border-collapse:collapse;font-size:14px">
  <thead>
    <tr style="background:#f7fafc">
      <th style="text-align:left;padding:8px 12px;color:#4a5568">Requête testée</th>
      {headers}
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""


def _competitors_section(competitors: list[dict]) -> str:
    if not competitors:
        return "<p style='color:#718096;font-style:italic'>Aucun concurrent identifié dans les réponses IA sur votre zone.</p>"
    items = "".join(
        f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>"
        f"<span style='font-size:20px'>🏢</span>"
        f"<span style='font-weight:600'>{_esc(c['name'])}</span>"
        f"<span style='color:#718096;font-size:13px'>cité {c['count']} fois</span></div>"
        for c in competitors[:5]
    )
    return items


def _action_plan_rows(plan: list[dict]) -> str:
    if not plan:
        return ""
    rows = ""
    for i, item in enumerate(plan, 1):
        rows += f"""<tr style="border-bottom:1px solid #e2e8f0">
  <td style="padding:12px;color:#718096;font-size:13px">{i}</td>
  <td style="padding:12px">
    <div style="font-weight:600;margin-bottom:4px">{_esc(item['action'])}</div>
    <div style="color:#718096;font-size:13px">{_esc(item['impact'])}</div>
  </td>
  <td style="padding:12px;white-space:nowrap">{_priority_badge(item['priority'])}</td>
  <td style="padding:12px;white-space:nowrap">{_difficulty_badge(item['difficulty'])}</td>
</tr>"""
    return rows


def _prompt_block(label: str, prompt_text: str) -> str:
    safe = _esc(prompt_text)
    return f"""<div style="margin-bottom:32px">
  <h3 style="font-size:16px;font-weight:700;color:#2d3748;margin-bottom:12px">{label}</h3>
  <div style="position:relative">
    <pre style="background:#1a202c;color:#e2e8f0;padding:20px;border-radius:8px;
                font-size:12px;line-height:1.6;overflow-x:auto;white-space:pre-wrap">{safe}</pre>
    <div style="font-size:11px;color:#718096;margin-top:6px">
      → Copiez ce prompt et collez-le directement dans ChatGPT, Claude ou Gemini
    </div>
  </div>
</div>"""


def _structure_block(label: str, content: str) -> str:
    safe = _esc(content)
    return f"""<div style="margin-bottom:32px">
  <h3 style="font-size:16px;font-weight:700;color:#2d3748;margin-bottom:12px">{label}</h3>
  <pre style="background:#f7fafc;border:1px solid #e2e8f0;color:#2d3748;padding:20px;
              border-radius:8px;font-size:12px;line-height:1.6;overflow-x:auto;white-space:pre-wrap">{safe}</pre>
</div>"""


def _checklist_html(checklist: dict, business_type: str, city: str) -> str:
    items = checklist.get("items", [])
    rows = ""
    for item in items:
        t = _esc(item["title"].replace("{profession}", business_type).replace("{ville}", city))
        d = _esc(item["desc"].replace("{profession}", business_type).replace("{ville}", city))
        rows += f"""<li style="margin-bottom:16px;display:flex;gap:12px;align-items:flex-start">
  <span style="flex-shrink:0;width:22px;height:22px;border:2px solid #667eea;
               border-radius:4px;display:inline-block;margin-top:1px"></span>
  <div>
    <div style="font-weight:600;color:#2d3748">{t}</div>
    <div style="color:#718096;font-size:13px;margin-top:2px">{d}</div>
  </div>
</li>"""
    return f"<ul style='list-style:none;padding:0'>{rows}</ul>"


def assemble_deliverable(
    company_name: str,
    city: str,
    business_type: str,
    website: str,
    score_data: dict,
    queries: list[dict],
    competitors: list[dict],
    diagnostic: dict,
    action_plan: list[dict],
    prompt_library: dict,
    content_structures: dict,
    checklist: dict,
    generated_at: str = "",
) -> dict:
    """
    Assemble le livrable complet.

    Returns:
        {
            "html":     str,    # HTML complet du livrable
            "json":     dict,   # données structurées
            "path":     str,    # chemin du fichier HTML sauvegardé
        }
    """
    if not generated_at:
        generated_at = datetime.now().strftime("%d/%m/%Y à %Hh%M")

    score = score_data.get("score", 0.0)
    score_color = _score_color(score)
    score_label = _score_label_fr(score)
    pct = min(100, int(score * 10))

    deliverable_json = {
        "company_name":      company_name,
        "city":              city,
        "business_type":     business_type,
        "website":           website,
        "generated_at":      generated_at,
        "score":             score_data,
        "queries":           queries,
        "competitors":       competitors,
        "diagnostic":        diagnostic,
        "action_plan":       action_plan,
        "prompt_library":    prompt_library,
        "content_structures": content_structures,
        "checklist":         checklist,
    }

    html_doc = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Méthode Présence IA — {_esc(company_name)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          color: #2d3748; background: #fff; font-size: 15px; line-height: 1.6; }}
  .page {{ max-width: 860px; margin: 0 auto; padding: 40px 24px 80px; }}
  .section {{ margin-bottom: 48px; }}
  .section-title {{ font-size: 20px; font-weight: 800; color: #1a202c;
                    border-left: 4px solid #667eea; padding-left: 14px; margin-bottom: 20px; }}
  .card {{ background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px; }}
  .card + .card {{ margin-top: 16px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #edf2f7; padding: 10px 12px; text-align: center;
        font-size: 13px; font-weight: 700; color: #4a5568; }}
  td {{ padding: 10px 12px; text-align: center; border-bottom: 1px solid #edf2f7; }}
  @media print {{
    body {{ font-size: 13px; }}
    .page {{ padding: 20px; }}
    pre {{ font-size: 11px !important; }}
    .no-print {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="page">

<!-- HEADER -->
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;
            border-radius:16px;padding:36px 40px;margin-bottom:48px">
  <div style="font-size:13px;opacity:0.8;margin-bottom:4px">MÉTHODE PRÉSENCE IA</div>
  <h1 style="font-size:28px;font-weight:800;margin-bottom:6px">{_esc(company_name)}</h1>
  <div style="font-size:16px;opacity:0.9">{_esc(business_type.capitalize())} à {_esc(city)}</div>
  {f'<div style="font-size:13px;opacity:0.7;margin-top:4px">{_esc(website)}</div>' if website else ''}
  <div style="margin-top:24px;font-size:12px;opacity:0.7">Généré le {_esc(generated_at)}</div>
</div>

<!-- 1. SCORE DE VISIBILITÉ -->
<div class="section">
  <div class="section-title">1. Votre visibilité dans les assistants IA</div>
  <div class="card" style="display:flex;gap:32px;align-items:center;flex-wrap:wrap">
    <div style="text-align:center;flex-shrink:0">
      <div style="width:120px;height:120px;border-radius:50%;
                  background:conic-gradient({score_color} {pct}%, #e2e8f0 0);
                  display:flex;align-items:center;justify-content:center;
                  box-shadow:0 0 0 8px #fff inset;margin:0 auto">
        <div style="text-align:center">
          <div style="font-size:28px;font-weight:800;color:{score_color}">{score}</div>
          <div style="font-size:11px;color:#718096">/10</div>
        </div>
      </div>
      <div style="margin-top:10px;font-weight:700;color:{score_color};font-size:15px">{score_label}</div>
    </div>
    <div style="flex:1;min-width:200px">
      <p style="color:#4a5568;margin-bottom:12px">{_esc(diagnostic.get('summary', ''))}</p>
      <div style="font-size:13px;color:#718096;background:#edf2f7;padding:10px 14px;border-radius:8px">
        {_esc(diagnostic.get('model_analysis', ''))}
      </div>
    </div>
  </div>
</div>

<!-- 2. RÉSULTATS REQUÊTES -->
<div class="section">
  <div class="section-title">2. Détail des requêtes testées</div>
  <div class="card" style="padding:0;overflow:hidden">
    {_queries_table(queries)}
  </div>
  <div style="margin-top:8px;font-size:13px;color:#718096">
    ✓ = votre entreprise est citée &nbsp;|&nbsp; ✗ = non citée &nbsp;|&nbsp; — = modèle non testé
  </div>
</div>

<!-- 3. CONCURRENTS CITÉS -->
<div class="section">
  <div class="section-title">3. Concurrents visibles sur votre zone</div>
  <div class="card">
    {_competitors_section(competitors)}
    <p style="margin-top:12px;font-size:13px;color:#718096">{_esc(diagnostic.get('competitor_context', ''))}</p>
  </div>
</div>

<!-- 4. DIAGNOSTIC -->
<div class="section">
  <div class="section-title">4. Diagnostic — pourquoi cette situation ?</div>
  {"".join(
    f'<div class="card" style="margin-bottom:12px">'
    f'<div style="font-weight:700;color:#1a202c;margin-bottom:6px">🔍 {_esc(p["category"])}</div>'
    f'<p style="color:#4a5568;font-size:14px">{_esc(p["detail"])}</p></div>'
    for p in diagnostic.get("problems", [])
  )}
</div>

<!-- 5. PLAN D'ACTION -->
<div class="section">
  <div class="section-title">5. Plan d'action — {len(action_plan)} actions à mener</div>
  <div class="card" style="padding:0;overflow:hidden">
    <table>
      <thead>
        <tr style="background:#f7fafc">
          <th style="width:40px">#</th>
          <th style="text-align:left">Action</th>
          <th style="width:140px">Priorité</th>
          <th style="width:100px">Difficulté</th>
        </tr>
      </thead>
      <tbody>
        {_action_plan_rows(action_plan)}
      </tbody>
    </table>
  </div>
</div>

<!-- 6. PROMPTS À UTILISER -->
<div class="section">
  <div class="section-title">6. Prompts à utiliser — copiez et collez</div>
  <div class="card">
    <p style="color:#4a5568;font-size:14px;margin-bottom:24px">
      Ces prompts sont prêts à être copiés dans ChatGPT, Claude ou Gemini.
      Ils sont déjà remplis avec vos informations (entreprise, ville, métier).
    </p>
    {_prompt_block("📄 Créer une page service locale", prompt_library.get("page_service", ""))}
    {_prompt_block("❓ Créer une FAQ métier + ville", prompt_library.get("faq", ""))}
    {_prompt_block("✏️ Réécrire une page existante", prompt_library.get("rewrite", ""))}
    {_prompt_block("🔍 Analyser et optimiser une page", prompt_library.get("optimize", ""))}
  </div>
</div>

<!-- 7. STRUCTURES DE CONTENUS -->
<div class="section">
  <div class="section-title">7. Structures de contenus à utiliser</div>
  <div class="card">
    <p style="color:#4a5568;font-size:14px;margin-bottom:24px">
      Utilisez ces structures comme guide pour créer ou améliorer vos pages.
      Chaque élément a un rôle précis pour votre visibilité IA.
    </p>
    {_structure_block("📋 Structure — Page service locale", content_structures.get("service_page", ""))}
    {_structure_block("❓ Structure — FAQ optimisée IA", content_structures.get("faq_optimized", ""))}
    {_structure_block("📌 Blocs \"citables\" par les IA", content_structures.get("citable_content", ""))}
  </div>
</div>

<!-- 8. CHECKLIST -->
<div class="section">
  <div class="section-title">8. Checklist d'implémentation — étapes dans l'ordre</div>
  <div class="card">
    <p style="color:#4a5568;font-size:14px;margin-bottom:20px">
      <strong>{checklist.get('title', 'Plan d\'action')}</strong> —
      Suivez ces étapes dans l'ordre pour progresser le plus rapidement possible.
    </p>
    {_checklist_html(checklist, business_type, city)}
  </div>
</div>

<!-- FOOTER -->
<div style="margin-top:64px;padding-top:24px;border-top:1px solid #e2e8f0;
            text-align:center;color:#a0aec0;font-size:12px">
  Méthode Présence IA — {_esc(company_name)} — Généré le {_esc(generated_at)}<br>
  <span style="font-size:11px">Ce document est confidentiel et destiné uniquement à {_esc(company_name)}.</span>
</div>

</div>
</body>
</html>"""

    # Sauvegarde fichier
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    import re, unicodedata

    def _slug(s: str) -> str:
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:30]

    fname = f"methode_ia_{_slug(company_name)}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    out_path = _OUTPUT_DIR / fname
    out_path.write_text(html_doc, encoding="utf-8")

    return {
        "html": html_doc,
        "json": deliverable_json,
        "path": str(out_path),
    }
