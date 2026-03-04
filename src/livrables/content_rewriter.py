"""
CONTENT_REWRITER (10C)
Scrape le site du prospect et réécrit les contenus pour l'optimisation LLM.
V1 : requests + BeautifulSoup, réécriture template-based (sans LLM call).

Offre : Tout Inclus (3500€)
Endpoint : POST /api/generate/prospect/{id}/content-rewrite
"""
import json
import logging
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from ..models import ProspectDB

log = logging.getLogger(__name__)

DIST_DIR = Path(__file__).parent.parent.parent / "dist"
TIMEOUT = 10
_UA = "Mozilla/5.0 (compatible; PRESENCE_IA-audit/1.0)"

# Mots-clés pour détecter les sous-pages utiles
_SUBPAGE_KW = {
    "about":    ["about", "qui-sommes", "a-propos", "presentation", "equipe"],
    "services": ["services", "prestations", "travaux", "solutions", "offres"],
}


# ── Scraping ─────────────────────────────────────────────────────────────────

def scrape_page(url: str) -> dict:
    """
    Scrape une URL et retourne title, h1, h2s, paragraphs.
    Retourne {"url": url, "error": str} en cas d'échec.
    """
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": _UA})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Nettoyer les blocs parasites
        for tag in soup(["nav", "footer", "header", "script", "style", "aside"]):
            tag.decompose()

        title = soup.title.get_text(strip=True) if soup.title else ""
        h1_tag = soup.find("h1")
        h1 = h1_tag.get_text(strip=True) if h1_tag else ""
        h2s = [h.get_text(strip=True) for h in soup.find_all("h2")][:5]
        paragraphs = [
            p.get_text(strip=True)
            for p in soup.find_all("p")
            if len(p.get_text(strip=True)) > 40
        ][:8]

        return {"url": url, "title": title, "h1": h1, "h2s": h2s, "paragraphs": paragraphs}
    except Exception as e:
        log.warning("Scraping échoué (%s) : %s", url, e)
        return {"url": url, "error": str(e)}


def _find_subpages(website: str, home_html: str) -> dict:
    """
    Depuis le HTML de la page d'accueil, détecte les URLs about et services.
    Retourne {"about": url|None, "services": url|None}.
    """
    base = website.rstrip("/")
    soup = BeautifulSoup(home_html, "html.parser")
    found = {}

    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text(strip=True).lower()
        for page_type, kws in _SUBPAGE_KW.items():
            if page_type not in found:
                if any(kw in href or kw in text for kw in kws):
                    if href.startswith("http"):
                        found[page_type] = href
                    elif href.startswith("/"):
                        found[page_type] = base + href
    return found


# ── Réécriture ───────────────────────────────────────────────────────────────

def _rewrite_page(scraped: dict, p: ProspectDB) -> dict:
    """
    Génère le contenu réécrit pour une page scrapée.
    Stratégie LLM-first : entités nommées, sémantique locale, signal d'autorité.
    """
    city     = p.city.capitalize()
    prof     = p.profession
    name     = p.name
    reviews  = p.reviews_count or 0

    signal = f"{name} est un {prof} établi à {city}"
    if reviews >= 10:
        signal += f", reconnu par {reviews} avis clients"
    signal += "."

    return {
        "original": {
            "title":      scraped.get("title", ""),
            "h1":         scraped.get("h1", ""),
            "h2s":        scraped.get("h2s", []),
            "paragraphs": scraped.get("paragraphs", []),
        },
        "rewritten": {
            "title": f"{prof.capitalize()} à {city} | {name}",
            "h1":    f"{name} — {prof.capitalize()} à {city}",
            "h2s": [
                f"Vos travaux de {prof} à {city}",
                f"Pourquoi choisir {name} ?",
                f"Avis clients — {name}, {prof} à {city}",
                f"Zone d'intervention : {city} et alentours",
            ],
            "intro": (
                f"{name} est votre {prof} de confiance à {city}. "
                f"Spécialisé dans les travaux de {prof} à {city} et ses environs, "
                f"notre équipe met son expertise à votre service pour tous vos projets. "
                f"{signal}"
            ),
            "signal_autorite": signal,
        },
    }


# ── Rapport HTML ─────────────────────────────────────────────────────────────

def _html_report(pages: dict, p: ProspectDB, failed: list) -> str:
    city = p.city.capitalize()

    def _diff_block(label: str, page_data: dict) -> str:
        orig = page_data["original"]
        rew  = page_data["rewritten"]
        h2s_orig = "<br>".join(orig["h2s"]) or "<em style='color:#888'>Aucun H2</em>"
        h2s_rew  = "<br>".join(f"• {h}" for h in rew["h2s"])
        paras = "".join(
            f'<p style="font-size:12px;color:#555;margin:4px 0">{p_}</p>'
            for p_ in orig["paragraphs"][:3]
        ) or "<em style='color:#888;font-size:12px'>Aucun paragraphe extrait</em>"
        return f"""
<div style="border:1px solid #e5e7eb;border-radius:10px;padding:24px;margin-bottom:24px">
  <h3 style="color:#e94560;font-size:15px;margin-bottom:20px">{label}</h3>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
    <div>
      <div style="background:#fef2f2;border-radius:6px;padding:16px">
        <div style="font-size:11px;color:#888;margin-bottom:10px;text-transform:uppercase;font-weight:bold">Avant</div>
        <div style="font-size:11px;color:#666;margin-bottom:4px">Title</div>
        <div style="font-size:13px;color:#1a1a2e;margin-bottom:12px">{orig["title"] or "—"}</div>
        <div style="font-size:11px;color:#666;margin-bottom:4px">H1</div>
        <div style="font-size:13px;color:#1a1a2e;margin-bottom:12px">{orig["h1"] or "—"}</div>
        <div style="font-size:11px;color:#666;margin-bottom:4px">H2</div>
        <div style="font-size:13px;color:#1a1a2e;margin-bottom:12px">{h2s_orig}</div>
        <div style="font-size:11px;color:#666;margin-bottom:4px">Contenu</div>
        {paras}
      </div>
    </div>
    <div>
      <div style="background:#f0fdf4;border-radius:6px;padding:16px">
        <div style="font-size:11px;color:#888;margin-bottom:10px;text-transform:uppercase;font-weight:bold">Après (optimisé LLM)</div>
        <div style="font-size:11px;color:#666;margin-bottom:4px">Title</div>
        <div style="font-size:13px;font-weight:bold;color:#15803d;margin-bottom:12px">{rew["title"]}</div>
        <div style="font-size:11px;color:#666;margin-bottom:4px">H1</div>
        <div style="font-size:13px;font-weight:bold;color:#15803d;margin-bottom:12px">{rew["h1"]}</div>
        <div style="font-size:11px;color:#666;margin-bottom:4px">H2</div>
        <div style="font-size:13px;color:#15803d;margin-bottom:12px">{h2s_rew}</div>
        <div style="font-size:11px;color:#666;margin-bottom:4px">Intro optimisée</div>
        <div style="font-size:12px;color:#15803d;margin:4px 0;line-height:1.5">{rew["intro"]}</div>
        <div style="margin-top:12px;padding:10px;background:#dcfce7;border-radius:4px;font-size:11px;color:#15803d">
          <strong>Signal d'autorité :</strong> {rew["signal_autorite"]}
        </div>
      </div>
    </div>
  </div>
</div>"""

    pages_html = ""
    for label, data in pages.items():
        pages_html += _diff_block(label, data)

    failed_html = ""
    if failed:
        failed_html = f"""<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:6px;padding:12px;margin-bottom:20px">
  <strong style="color:#dc2626">Pages non scrapées :</strong>
  <ul style="margin:6px 0 0 16px;font-size:12px;color:#dc2626">
    {"".join(f'<li>{f}</li>' for f in failed)}
  </ul>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Content Rewrite — {p.name}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',sans-serif;background:#f9fafb;color:#1a1a2e}}</style>
</head><body>
<div style="max-width:1100px;margin:0 auto;padding:32px">
  <h1 style="color:#1a1a2e;font-size:22px;margin-bottom:6px">
    Optimisation de contenu LLM — {p.name}
  </h1>
  <p style="color:#6b7280;font-size:13px;margin-bottom:28px">
    {p.profession.capitalize()} à {city} — {p.website or "site non renseigné"}
  </p>

  <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;margin-bottom:28px">
    <strong style="color:#1d4ed8;font-size:13px">Comment utiliser ce rapport :</strong>
    <ol style="margin:8px 0 0 16px;font-size:12px;color:#1d4ed8;line-height:1.8">
      <li>Remplacez le <strong>title</strong> de chaque page dans votre CMS</li>
      <li>Remplacez le <strong>H1</strong> par la version optimisée</li>
      <li>Ajoutez les <strong>H2</strong> proposés dans les sections de la page</li>
      <li>Insérez le <strong>paragraphe d'intro</strong> en haut du contenu principal</li>
      <li>Ajoutez le <strong>signal d'autorité</strong> dans la section "À propos" ou pied de page</li>
    </ol>
  </div>

  {failed_html}
  {pages_html}
</div>
</body></html>"""


# ── Entrée principale ─────────────────────────────────────────────────────────

def generate_content_rewrite(p: ProspectDB) -> dict:
    """
    Scrape le site du prospect et génère un rapport avant/après.

    Returns:
        {
          "pages_scraped": int,
          "pages_failed": list,
          "rewrites": dict,  # {label: {original, rewritten}}
          "file": str,       # chemin HTML
        }
    """
    website = (p.website or "").rstrip("/")
    if not website:
        return {
            "success": False,
            "pages_scraped": 0,
            "pages_failed": ["Site web non renseigné"],
            "rewrites": {},
            "file": None,
        }

    pages_to_scrape = {"Accueil": website}
    failed = []

    # Scrape accueil pour détecter les sous-pages
    try:
        resp = requests.get(website, timeout=TIMEOUT, headers={"User-Agent": _UA})
        resp.raise_for_status()
        home_html = resp.text
        subpages = _find_subpages(website, home_html)
        if subpages.get("about"):
            pages_to_scrape["À propos"] = subpages["about"]
        if subpages.get("services"):
            pages_to_scrape["Services"] = subpages["services"]
    except Exception as e:
        log.warning("Accueil inaccessible (%s) : %s", website, e)
        failed.append(f"Accueil ({website}) : {e}")
        # On continue avec un scrape générique
        home_html = ""

    rewrites = {}
    for label, url in pages_to_scrape.items():
        scraped = scrape_page(url)
        if "error" in scraped:
            failed.append(f"{label} ({url}) : {scraped['error']}")
        else:
            rewrites[label] = _rewrite_page(scraped, p)

    # Si aucune page scrapée avec succès, on génère quand même depuis les données prospect
    if not rewrites:
        rewrites["Accueil (données prospect)"] = _rewrite_page(
            {"url": website, "title": "", "h1": "", "h2s": [], "paragraphs": []},
            p,
        )

    # Sauvegarde
    out_dir = DIST_DIR / p.prospect_id / "livrables"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "content_rewrite.html"
    html_path.write_text(_html_report(rewrites, p, failed), encoding="utf-8")

    return {
        "pages_scraped": len(rewrites),
        "pages_failed": failed,
        "rewrites": rewrites,
        "file": str(html_path),
    }
