"""
EDITORIAL_CHECKLIST (10D)
Génère une checklist HTML interactive personnalisée — 10 actions classées par impact IA.
Chaque item est pré-rempli avec les données du prospect.
"""
import json
from pathlib import Path
from typing import List

from ..models import ProspectDB

DIST_DIR = Path(__file__).parent.parent.parent / "dist"


def _build_items(p: ProspectDB) -> List[dict]:
    """
    Construit les items de checklist ordonnés par impact IA estimé.
    Chaque item : {id, label, detail, impact, done}
    """
    city  = p.city.capitalize()
    prof  = p.profession.capitalize()
    name  = p.name

    avis_cible = 40
    avis_actuels = p.reviews_count or 0
    avis_manquants = max(0, avis_cible - avis_actuels)

    items = [
        {
            "id": "jsonld",
            "label": "Ajouter les données structurées JSON-LD sur votre site",
            "detail": (
                f"Coller le bloc LocalBusiness + AggregateRating dans le &lt;head&gt; "
                f"de {p.website or 'votre site'}. "
                f"C'est le signal le plus direct pour que les IA identifient {name} "
                f"comme référence locale."
            ),
            "impact": "Très élevé",
            "impact_class": "high",
            "done": False,
        },
        {
            "id": "google_business",
            "label": "Compléter Google Business Profile à 100 %",
            "detail": (
                f"Description détaillée mentionnant « {prof} à {city} », "
                f"photos récentes, horaires à jour, liste complète des services. "
                f"Un profil complet = signal fort pour les LLMs."
            ),
            "impact": "Très élevé",
            "impact_class": "high",
            "done": False,
        },
        {
            "id": "avis",
            "label": f"Atteindre {avis_cible} avis Google"
            + (f" ({avis_manquants} avis manquants)" if avis_manquants > 0 else " ✓ Objectif atteint"),
            "detail": (
                f"Demander systématiquement un avis après chaque intervention. "
                f"Les IA pondèrent fortement le volume et la récence des avis. "
                f"Répondre à tous les avis (positifs et négatifs)."
            ),
            "impact": "Élevé",
            "impact_class": "high",
            "done": avis_actuels >= avis_cible,
        },
        {
            "id": "faq",
            "label": "Publier 5 à 10 pages FAQ optimisées pour les IA",
            "detail": (
                f"Une page par requête testée lors de l'audit. "
                f"Exemple : « Quel est le meilleur {p.profession} à {city} ? » "
                f"→ créer une page qui répond et positionne {name}."
            ),
            "impact": "Élevé",
            "impact_class": "high",
            "done": False,
        },
        {
            "id": "h1",
            "label": f"Inclure « {prof} à {city} » dans le H1 de votre page d'accueil",
            "detail": (
                f"Le titre principal (H1) doit contenir explicitement votre métier "
                f"et votre ville. Exemple : « {name} — {prof} à {city} »."
            ),
            "impact": "Élevé",
            "impact_class": "high",
            "done": False,
        },
        {
            "id": "nap",
            "label": "Vérifier la cohérence NAP sur toutes les plateformes",
            "detail": (
                f"Nom, Adresse, Téléphone doivent être identiques partout : "
                f"site web, Google Business, PagesJaunes, Facebook, etc. "
                f"La moindre variation affaiblit le signal pour les IA."
            ),
            "impact": "Moyen",
            "impact_class": "medium",
            "done": False,
        },
        {
            "id": "citations",
            "label": "Créer ou mettre à jour vos citations sur 15 à 20 plateformes locales",
            "detail": (
                "PagesJaunes, Yelp, Houzz, Allovoisins, Cylex, Kompass, "
                "Annuaire du bâtiment (selon métier). "
                "Chaque citation = un signal supplémentaire d'autorité locale."
            ),
            "impact": "Moyen",
            "impact_class": "medium",
            "done": False,
        },
        {
            "id": "about",
            "label": "Réécrire votre page « À propos » avec des entités nommées explicites",
            "detail": (
                f"Mentionner explicitement : nom de l'entreprise ({name}), "
                f"ville ({city}), métier ({p.profession}), ancienneté, certifications, "
                f"zone d'intervention. Les LLMs recherchent ces entités nommées."
            ),
            "impact": "Moyen",
            "impact_class": "medium",
            "done": False,
        },
        {
            "id": "presse",
            "label": "Obtenir un article de presse locale ou une interview",
            "detail": (
                f"Un article dans un journal local ({city} Actu, journal régional) "
                f"mentionnant {name} est un signal d'autorité très fort pour les LLMs. "
                f"Même un communiqué de presse publié en ligne suffit."
            ),
            "impact": "Moyen",
            "impact_class": "medium",
            "done": False,
        },
        {
            "id": "mentions",
            "label": "Obtenir des mentions sur des forums et blogs locaux",
            "detail": (
                f"Répondre à des questions sur des forums locaux, "
                f"être cité dans des articles de blog de partenaires ou associations. "
                f"Ces mentions hors-site renforcent votre présence sémantique."
            ),
            "impact": "Faible",
            "impact_class": "low",
            "done": False,
        },
    ]
    return items


def generate_checklist(p: ProspectDB) -> dict:
    """
    Génère une checklist HTML interactive pour le prospect.

    Returns:
        {"html": str, "items": list, "file": str}
    """
    items = _build_items(p)
    done_count = sum(1 for i in items if i["done"])
    total = len(items)
    pct = int(done_count / total * 100)

    items_html = ""
    for item in items:
        checked = 'checked' if item["done"] else ''
        badge_cls = f"badge-{item['impact_class']}"
        items_html += f"""
  <div class="item{'  item--done' if item['done'] else ''}" id="item-{item['id']}">
    <label class="item-label">
      <input type="checkbox" {checked} onchange="toggle('{item['id']}', this.checked)">
      <span class="item-text">{item['label']}</span>
      <span class="badge {badge_cls}">{item['impact']}</span>
    </label>
    <p class="item-detail">{item['detail']}</p>
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Checklist Visibilité IA — {p.name}</title>
<style>
:root {{
  --acc: #e8355a; --green: #16a34a; --amber: #d97706; --blue: #2563eb;
  --txt: #111827; --muted: #6b7280; --light: #f9fafb; --border: #e5e7eb;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background: var(--light); color: var(--txt); padding: 32px 16px; }}
.wrap {{ max-width: 720px; margin: 0 auto; }}
header {{ margin-bottom: 32px; }}
header h1 {{ font-size: 22px; font-weight: 800; margin-bottom: 4px; }}
header p {{ color: var(--muted); font-size: 14px; }}
.progress-bar {{ background: var(--border); border-radius: 99px; height: 10px; margin: 20px 0 6px; overflow: hidden; }}
.progress-fill {{ background: var(--green); height: 100%; border-radius: 99px; transition: width .4s ease; }}
.progress-label {{ font-size: 13px; color: var(--muted); margin-bottom: 28px; }}
.progress-label strong {{ color: var(--green); }}
.item {{ background: #fff; border: 1.5px solid var(--border); border-radius: 12px; padding: 18px 20px; margin-bottom: 12px; transition: border-color .2s; }}
.item--done {{ border-color: var(--green); background: #f0fdf4; }}
.item-label {{ display: flex; align-items: flex-start; gap: 12px; cursor: pointer; }}
.item-label input[type=checkbox] {{ width: 18px; height: 18px; flex-shrink: 0; margin-top: 2px; accent-color: var(--green); cursor: pointer; }}
.item-text {{ flex: 1; font-size: 15px; font-weight: 600; line-height: 1.4; }}
.item--done .item-text {{ text-decoration: line-through; color: var(--muted); }}
.badge {{ flex-shrink: 0; font-size: 10px; font-weight: 700; padding: 3px 10px; border-radius: 20px; text-transform: uppercase; letter-spacing: .5px; }}
.badge-high {{ background: #fee2e2; color: #b91c1c; }}
.badge-medium {{ background: #fef3c7; color: #92400e; }}
.badge-low {{ background: var(--light); color: var(--muted); border: 1px solid var(--border); }}
.item-detail {{ font-size: 13px; color: var(--muted); line-height: 1.6; margin-top: 10px; padding-left: 30px; }}
footer {{ margin-top: 40px; text-align: center; font-size: 12px; color: var(--muted); }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Checklist Visibilité IA — {p.name}</h1>
    <p>{p.profession.capitalize()} à {p.city.capitalize()} · Score actuel : {p.ia_visibility_score or 0:.1f}/10</p>
    <div class="progress-bar"><div class="progress-fill" id="fill" style="width:{pct}%"></div></div>
    <p class="progress-label"><strong id="pct">{pct}%</strong> complété · <span id="done-count">{done_count}</span>/{total} actions</p>
  </header>
  <div id="items">{items_html}
  </div>
  <footer>© 2026 PRESENCE_IA — Checklist générée le {__import__('datetime').datetime.now().strftime('%d/%m/%Y')}</footer>
</div>
<script>
const total = {total};
function updateProgress() {{
  const all = document.querySelectorAll('#items input[type=checkbox]');
  const done = [...all].filter(c => c.checked).length;
  const pct = Math.round(done / total * 100);
  document.getElementById('fill').style.width = pct + '%';
  document.getElementById('pct').textContent = pct + '%';
  document.getElementById('done-count').textContent = done;
  localStorage.setItem('checklist_{p.prospect_id}', JSON.stringify([...all].map(c => c.checked)));
}}
function toggle(id, checked) {{
  const item = document.getElementById('item-' + id);
  if (checked) item.classList.add('item--done');
  else item.classList.remove('item--done');
  updateProgress();
}}
// Restaurer état sauvegardé
const saved = JSON.parse(localStorage.getItem('checklist_{p.prospect_id}') || 'null');
if (saved) {{
  const all = document.querySelectorAll('#items input[type=checkbox]');
  saved.forEach((v, i) => {{ if (all[i]) {{ all[i]].checked = v; if (v) all[i].closest('.item').classList.add('item--done'); }} }});
  updateProgress();
}}
</script>
</body>
</html>"""

    out_dir = DIST_DIR / p.prospect_id / "livrables"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "checklist.html"
    out_file.write_text(html, encoding="utf-8")

    return {
        "html": html,
        "items": items,
        "done_count": done_count,
        "total": total,
        "completion_pct": pct,
        "file": str(out_file),
    }
