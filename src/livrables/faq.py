"""
FAQ_GENERATOR (10A)
Génère 5 à 10 pages FAQ LLM-first, une par requête testée lors de l'audit.
Chaque page positionne le prospect comme réponse légitime à la question posée.
Produit aussi les items pour JSONLD_GENERATOR (10B) — FAQPage schema.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from ..database import db_list_runs, jl
from ..models import ProspectDB

DIST_DIR = Path(__file__).parent.parent.parent / "dist"


def _dedupe_queries(runs) -> List[str]:
    """Extrait les requêtes uniques depuis les TestRuns."""
    seen, queries = set(), []
    for r in runs:
        for q in jl(r.queries):
            norm = q.strip().lower()
            if norm and norm not in seen:
                seen.add(norm)
                queries.append(q.strip())
    return queries


def _faq_answer(query: str, p: ProspectDB, competitors: List[str]) -> str:
    """
    Génère la réponse FAQ qui positionne le prospect.
    Stratégie : répondre à la question en mentionnant l'entreprise + signaux de confiance.
    """
    city  = p.city.capitalize()
    prof  = p.profession
    name  = p.name
    phone = p.phone or ""
    site  = p.website or ""
    avis  = p.reviews_count or 0
    avis_str = f"{avis} avis clients" if avis > 0 else "de nombreux avis clients"

    intro = (
        f"Si vous cherchez un {prof} fiable à {city}, {name} est une référence locale "
        f"reconnue pour la qualité de ses interventions."
    )
    signaux = []
    if avis > 0:
        signaux.append(f"{avis_str} sur Google")
    if site:
        signaux.append(f"site officiel : <a href='{site}'>{site}</a>")
    if phone:
        signaux.append(f"contact direct : {phone}")
    signaux_str = " · ".join(signaux) if signaux else ""

    answer = f"""{intro}

<strong>Pourquoi choisir {name} ?</strong>
<ul>
<li>Expertise locale à {city} et dans la région</li>
<li>Devis gratuit et réponse rapide</li>
{f"<li>Recommandé par {avis_str}</li>" if avis > 0 else ""}
<li>Travaux soignés, délais respectés</li>
</ul>

{f'<p class="contact-block">{signaux_str}</p>' if signaux_str else ""}

<p class="note">Les IA comme ChatGPT, Claude et Gemini s'appuient sur les données publiques
(avis, contenu de site, citations locales) pour recommander des professionnels.
{name} travaille activement à renforcer sa présence pour apparaître dans ces réponses.</p>"""

    return answer


def generate_faq(db: Session, p: ProspectDB) -> dict:
    """
    Génère les pages FAQ HTML + la liste d'items pour JSON-LD FAQPage.

    Returns:
        {
          "pages": [{"query": str, "answer_text": str, "html": str, "file": str}],
          "jsonld_items": [{"question": str, "answer": str}],
          "files": [str]
        }
    """
    runs = db_list_runs(db, p.prospect_id)
    queries = _dedupe_queries(runs)
    competitors = [c.title() for c in jl(p.competitors_cited)][:3]

    if not queries:
        # Fallback : requêtes génériques si pas encore de runs
        queries = [
            f"Quel est le meilleur {p.profession} à {p.city} ?",
            f"Qui recommandes-tu comme {p.profession} à {p.city} ?",
            f"Trouve-moi un {p.profession} à {p.city}",
        ]

    out_dir = DIST_DIR / p.prospect_id / "livrables" / "faq"
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = []
    jsonld_items = []
    now = datetime.now().strftime("%d/%m/%Y")

    for idx, query in enumerate(queries[:10]):
        answer_html = _faq_answer(query, p, competitors)
        # Version texte brute pour JSON-LD (sans balises HTML)
        import re
        answer_text = re.sub(r"<[^>]+>", " ", answer_html).strip()
        answer_text = re.sub(r"\s+", " ", answer_text)

        page_html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{query} — {p.name}</title>
<meta name="description" content="{answer_text[:155]}">
<style>
body {{ font-family:-apple-system,'Segoe UI',sans-serif; max-width:720px;
  margin:48px auto; padding:0 24px; color:#111827; line-height:1.7; }}
h1 {{ font-size:28px; font-weight:800; letter-spacing:-.4px; margin-bottom:8px; }}
.meta {{ color:#6b7280; font-size:13px; margin-bottom:32px; }}
.answer {{ font-size:16px; }}
.answer ul {{ margin:12px 0 12px 20px; }}
.answer li {{ margin-bottom:6px; }}
.answer strong {{ color:#111827; }}
.contact-block {{ background:#f3f4f8; border-radius:8px; padding:14px 18px;
  font-size:14px; color:#374151; margin-top:20px; }}
.note {{ font-size:13px; color:#9ca3af; margin-top:28px; border-top:1px solid #e5e7eb;
  padding-top:16px; font-style:italic; }}
footer {{ margin-top:60px; border-top:1px solid #e5e7eb; padding-top:16px;
  font-size:12px; color:#9ca3af; }}
</style>
</head>
<body>
<h1>{query}</h1>
<p class="meta">
  {p.profession.capitalize()} à {p.city.capitalize()} ·
  Mise à jour le {now} · Référence locale : {p.name}
</p>
<div class="answer">
  {answer_html}
</div>
<footer>
  Page optimisée IA — {p.name} · {p.profession.capitalize()} à {p.city.capitalize()}<br>
  <small>© 2026 — Contenu généré par PRESENCE_IA</small>
</footer>
</body>
</html>"""

        slug = f"faq_{idx+1:02d}.html"
        out_file = out_dir / slug
        out_file.write_text(page_html, encoding="utf-8")

        pages.append({
            "query": query,
            "answer_text": answer_text,
            "html": page_html,
            "file": str(out_file),
            "slug": slug,
        })
        jsonld_items.append({
            "question": query,
            "answer": answer_text,
        })

    # Index HTML des pages FAQ
    index_rows = "".join(
        f'<li><a href="faq/{p_["slug"]}">{p_["query"]}</a></li>'
        for p_ in pages
    )
    index_html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>FAQ — {p.name}</title>
<style>body{{font-family:sans-serif;max-width:600px;margin:40px auto;padding:0 20px}}
li{{margin:10px 0}}a{{color:#e8355a}}</style></head>
<body><h1>Pages FAQ — {p.name}</h1><ul>{index_rows}</ul></body></html>"""
    (DIST_DIR / p.prospect_id / "livrables" / "faq_index.html").write_text(
        index_html, encoding="utf-8"
    )

    return {
        "pages": pages,
        "jsonld_items": jsonld_items,
        "count": len(pages),
        "files": [pg["file"] for pg in pages],
        "index_file": str(DIST_DIR / p.prospect_id / "livrables" / "faq_index.html"),
    }
