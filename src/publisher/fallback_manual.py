"""
Fallback publication manuelle — pour les CMS sans API (Wix, Squarespace, Shopify, inconnu).

Génère un package livrable complet avec :
- Le contenu HTML prêt à copier
- Des instructions pas-à-pas adaptées au CMS détecté
- Le JSON-LD à coller dans le <head>

Retourne un dict avec tout le nécessaire pour que le client publie lui-même en 10 minutes.
"""

from pathlib import Path

# ── Instructions par CMS ──────────────────────────────────────────────────────

_INSTRUCTIONS: dict[str, str] = {
    "wordpress": """📋 INSTRUCTIONS DE PUBLICATION — WORDPRESS

1. Connectez-vous à votre tableau de bord WordPress
2. Pages → Ajouter → coller le titre : "{title}"
3. Cliquez sur les 3 points (⋮) → Éditeur de code
4. Collez le contenu HTML fourni (fichier page_service.html)
5. Cliquez sur "Publier"

⚠️ NE PAS ajouter cette page à votre menu principal.
   La page sera accessible par URL directe sans perturber votre navigation.
   Si vous souhaitez l'ajouter plus tard : Apparence → Menus → cocher la page.

Pour le JSON-LD (important pour les IA) :
→ Extensions → Ajouter → installez "Insert Headers and Footers"
→ Réglages → Insert Headers and Footers → Section Header
→ Collez le code du fichier schema_snippet.html
→ Sauvegarder
""",

    "wix": """📋 INSTRUCTIONS DE PUBLICATION — WIX

1. Connectez-vous à votre espace Wix (manage.wix.com)
2. Éditeur → Pages → + Ajouter une page → Page vierge
3. Nommez la page : "{title}"
4. Ajoutez un bloc HTML : + → Embed → HTML personnalisé
5. Collez le contenu HTML fourni dans le bloc
6. Dans les paramètres de la page → Masquer dans le menu (décochez "Afficher dans le menu")
7. Publiez la page (bouton "Publier" en haut à droite)

⚠️ NE PAS ajouter cette page au menu principal.
   Elle restera accessible par URL directe uniquement.

Pour le JSON-LD (données structurées) :
→ Paramètres du site → SEO avancé → Balises personnalisées → Ajouter une balise
→ Collez le code du fichier schema_snippet.html
""",

    "shopify": """📋 INSTRUCTIONS DE PUBLICATION — SHOPIFY

1. Connectez-vous à votre admin Shopify
2. Boutique en ligne → Pages → Créer une page
3. Titre : "{title}"
4. Dans l'éditeur, cliquez sur l'icône "<>" (source HTML)
5. Collez le contenu HTML fourni
6. Sauvegarder et publier

⚠️ NE PAS ajouter cette page à votre menu de navigation.
   Boutique en ligne → Navigation → vérifier que la page n'est pas listée.
   Elle est accessible uniquement par URL directe.

Pour le JSON-LD :
→ Thèmes → Modifier le code → layout/theme.liquid
→ Collez le code schema_snippet.html juste avant </head>
""",

    "squarespace": """📋 INSTRUCTIONS DE PUBLICATION — SQUARESPACE

1. Connectez-vous à votre espace Squarespace
2. Pages → + Ajouter une page → Page vierge
3. Double-cliquez sur la zone de contenu → Modifier
4. Cliquez sur + → Code → Collez le contenu HTML
5. Nommez la page "{title}" dans les paramètres de page
6. Dans les paramètres de la page → cocher "Non lié" (Not Linked)
7. Publiez

⚠️ NE PAS glisser cette page dans la navigation principale.
   La laisser dans la section "Pages non liées".

Pour le JSON-LD :
→ Paramètres du site → SEO → Injection de code → En-tête
→ Collez le code schema_snippet.html
""",

    "webflow": """📋 INSTRUCTIONS DE PUBLICATION — WEBFLOW

1. Ouvrez votre projet Webflow Designer
2. Pages → + Ajouter une page → Page statique
3. Nommez "{title}"
4. Ajoutez un bloc HTML Embed → Collez le contenu
5. Dans les paramètres de la page → décocher "Inclure dans le plan du site"
6. Publiez sur votre domaine

⚠️ NE PAS ajouter cette page à votre navbar.
   Elle sera accessible par URL directe sans apparaître dans la navigation.

Pour le JSON-LD :
→ Paramètres de page → Code personnalisé → En-tête
→ Collez le code schema_snippet.html
""",

    "unknown": """📋 INSTRUCTIONS DE PUBLICATION — CMS NON DÉTECTÉ

Votre page est prête à publier. Choisissez la méthode adaptée à votre site :

Option A — Via votre admin CMS :
1. Créez une nouvelle page intitulée "{title}"
2. Passez en mode édition HTML / source code
3. Collez le contenu HTML fourni
4. Publiez sans l'ajouter au menu principal

Option B — Via FTP (site statique) :
1. Renommez le fichier page_service.html en index.html
2. Déposez-le dans un dossier /services/{slug}/ sur votre serveur
3. La page sera accessible à l'URL : https://votre-site.fr/services/{slug}/

⚠️ Dans tous les cas : NE PAS ajouter cette page au menu de navigation.
   Elle doit rester accessible par URL directe uniquement.

Pour le JSON-LD (important pour les IA) :
→ Ajoutez le code schema_snippet.html dans le <head> de votre page d'accueil
→ Et dans le <head> de votre nouvelle page service
""",
}


def _get_instructions(cms: str, title: str, slug: str) -> str:
    """Retourne les instructions adaptées au CMS."""
    cms_low = (cms or "").lower().strip()
    template = _INSTRUCTIONS.get(cms_low, _INSTRUCTIONS["unknown"])
    return template.format(title=title, slug=slug)


# ── Point d'entrée ────────────────────────────────────────────────────────────

def generate_manual_package(
    prospect,
    page_html: str,
    schema_snippet: str = "",
    title: str = "",
    visibility: str = "discreet",
    publish_target: str = "service_page",
) -> dict:
    """
    Génère un package de publication manuelle pour les CMS sans API.

    Args:
        prospect       : instance V3ProspectDB
        page_html      : HTML de la page service (depuis page_generator)
        schema_snippet : balises <script> JSON-LD (depuis schema_generator)
        title          : titre de la page (auto si vide)
        visibility     : "discreet" (URL directe, hors menu) | "integrated" (dans le menu)
        publish_target : "service_page" | "faq_page" | "local_page"

    Returns:
        {
          "ok":            bool,
          "method":        str,   # "manual"
          "cms":           str,
          "title":         str,
          "slug":          str,
          "visibility":    str,   # "discreet" | "integrated"
          "publish_target": str,
          "menu_note":     str,   # consigne explicite sur la navigation
          "instructions":  str,
          "page_html":     str,
          "schema_html":   str,
          "url":           None,
          "error":         None,
        }
    """
    import re, unicodedata

    name       = getattr(prospect, "name", "")
    profession = getattr(prospect, "profession", "professionnel")
    ville      = getattr(prospect, "city", "").capitalize()
    cms        = getattr(prospect, "cms", "") or "unknown"

    if not title:
        title = f"{profession.capitalize()} à {ville} — {name}"

    slug = unicodedata.normalize("NFD", title.lower())
    slug = "".join(c for c in slug if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")[:60]

    instructions = _get_instructions(cms, title, slug)

    menu_note = (
        "Page publiée mais non intégrée à la navigation. "
        "Accessible uniquement par URL directe."
        if visibility == "discreet"
        else
        "Page publiée. À ajouter manuellement au menu si souhaité."
    )

    return {
        "ok":             True,
        "method":         "manual",
        "cms":            cms,
        "title":          title,
        "slug":           slug,
        "visibility":     visibility,
        "publish_target": publish_target,
        "menu_note":      menu_note,
        "instructions":   instructions,
        "page_html":      page_html,
        "schema_html":    schema_snippet,
        "url":            None,
        "error":          None,
    }
