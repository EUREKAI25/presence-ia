"""
Génération de page service locale optimisée IA.

Structure produite :
  H1  "{Profession} à {Ville} — {Nom entreprise}"
  Intro   problème client + solution
  Services liste des prestations
  Confiance  avis, garanties, expérience
  FAQ  section intégrée avec Q/R

Output : HTML complet prêt à copier-coller dans n'importe quel CMS.
"""


def _esc(s: str) -> str:
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ── Éléments de contenu selon la profession ──────────────────────────────────

# Catalogue de prestations et accroche par secteur
# Chaque entrée : (mots_clés, prestations, probleme_client, phrase_confiance)
_SECTOR_DATA = {
    "plombier": (
        ["plombier", "plomberie", "dépannage", "fuite"],
        ["Dépannage fuite d'eau", "Débouchage canalisations", "Installation sanitaires",
         "Remplacement chauffe-eau", "Réparation robinetterie", "Urgence plomberie 24h"],
        "Une fuite, une canalisation bouchée, un chauffe-eau en panne… Ces problèmes ne préviennent pas. Vous avez besoin d'un professionnel fiable, disponible rapidement et transparent sur ses tarifs.",
        "interventions garanties · devis gratuit · disponible 6j/7",
    ),
    "électricien": (
        ["électricien", "électricité", "élec"],
        ["Mise aux normes tableau électrique", "Installation prises et interrupteurs",
         "Dépannage panne électrique", "Pose éclairage LED", "Installation VMC",
         "Certificat de conformité"],
        "Une panne électrique ou une installation non conforme peut être dangereuse. Faites appel à un électricien qualifié pour sécuriser votre logement.",
        "travaux certifiés · devis gratuit · artisan qualifié",
    ),
    "chauffagiste": (
        ["chauffagiste", "chauffage", "chaudière", "pompe à chaleur"],
        ["Entretien chaudière", "Installation pompe à chaleur", "Dépannage chauffage",
         "Remplacement chaudière", "Installation climatisation", "Conseil économies d'énergie"],
        "Un chauffage en panne en hiver, une chaudière qui fait du bruit… Votre confort thermique mérite un professionnel réactif et expérimenté.",
        "contrat entretien disponible · devis gratuit · intervention rapide",
    ),
    "serrurier": (
        ["serrurier", "serrure", "porte", "blindage"],
        ["Ouverture porte claquée", "Remplacement serrure", "Installation serrure multipoints",
         "Blindage porte", "Dépannage urgence", "Changement cylindre"],
        "Porte claquée, serrure forcée, clés perdues… Ces situations stressantes nécessitent une intervention rapide d'un serrurier de confiance.",
        "tarif annoncé avant intervention · devis gratuit · disponible 24h/24",
    ),
    "peintre": (
        ["peintre", "peinture", "ravalement", "décoration"],
        ["Peinture intérieure", "Peinture extérieure et ravalement", "Pose papier peint",
         "Enduit de lissage", "Isolation thermique par l'extérieur", "Conseils couleurs"],
        "Donner un nouveau souffle à votre intérieur ou protéger votre façade demande un peintre sérieux, propre et respectueux de votre logement.",
        "finitions soignées · devis gratuit · matériaux de qualité",
    ),
    "menuisier": (
        ["menuisier", "menuiserie", "fenêtre", "porte"],
        ["Pose fenêtres double vitrage", "Installation portes d'entrée", "Fabrication sur mesure",
         "Rénovation volets", "Pose parquet", "Dressing et rangements"],
        "Rénover ses fenêtres, sécuriser son entrée ou créer des rangements sur mesure : un menuisier qualifié fait toute la différence.",
        "fabrication française · devis gratuit · pose incluse",
    ),
}

_DEFAULT_SECTOR = (
    [],
    ["Diagnostic", "Intervention sur site", "Conseil personnalisé",
     "Devis gratuit", "Suivi après intervention"],
    "Vous cherchez un professionnel fiable et réactif dans votre secteur ? Notre équipe est à votre service.",
    "professionnel qualifié · devis gratuit · travail garanti",
)


def _get_sector(profession: str) -> tuple:
    """Retourne les données sectorielles selon la profession."""
    prof_low = profession.lower()
    for key, data in _SECTOR_DATA.items():
        keywords, services, intro, trust = data
        if key in prof_low or any(k in prof_low for k in keywords):
            return services, intro, trust
    return _DEFAULT_SECTOR[1], _DEFAULT_SECTOR[2], _DEFAULT_SECTOR[3]


# ── Génération HTML ───────────────────────────────────────────────────────────

def _faq_html(faq_items: list[dict]) -> str:
    """Génère la section FAQ en HTML avec balises <details> / <summary>."""
    if not faq_items:
        return ""
    items_html = "\n".join(
        f'<details style="border-bottom:1px solid #e5e7eb;padding:12px 0">'
        f'<summary style="cursor:pointer;font-weight:600;color:#1e3a5f;list-style:none;padding-right:24px">'
        f'{_esc(item["question"])}</summary>'
        f'<p style="margin:10px 0 0;color:#374151;line-height:1.7">{_esc(item["answer"])}</p>'
        f'</details>'
        for item in faq_items
    )
    return f"""
<section style="margin-top:48px">
  <h2 style="font-size:22px;font-weight:700;color:#1a1a2e;margin-bottom:24px">Questions fréquentes</h2>
  <div style="border-top:1px solid #e5e7eb">
    {items_html}
  </div>
</section>"""


def generate_service_page(
    prospect,
    faq_items: list[dict] | None = None,
    competitors: list[dict] | None = None,
    internal_links: list[dict] | None = None,
) -> str:
    """
    Génère une page service HTML complète optimisée pour la visibilité IA.

    La page est autonome (CSS inline), prête à être copiée dans n'importe quel CMS.

    Args:
        prospect       : instance V3ProspectDB
        faq_items      : liste [{question, answer}] retournée par faq_generator
        competitors    : liste [{name, count}] retournée par scoring
        internal_links : liste [{title, url, anchor, reason}] pour le bloc "À lire aussi"
                         (optionnel — injecté avant </body> si non vide)

    Returns:
        str : HTML complet de la page service
    """
    name       = getattr(prospect, "name", "")
    profession = getattr(prospect, "profession", "professionnel")
    ville      = getattr(prospect, "city", "votre ville").capitalize()
    phone      = getattr(prospect, "phone", "") or ""
    website    = getattr(prospect, "website", "") or getattr(prospect, "url", "") or ""
    rating     = getattr(prospect, "rating", None)

    services, intro_text, trust_badges = _get_sector(profession)

    # Étoiles Google si disponibles
    rating_html = ""
    if rating:
        stars = "★" * int(float(rating)) + "☆" * (5 - int(float(rating)))
        rating_html = f'<span style="color:#f59e0b;font-size:18px">{stars}</span> <span style="color:#6b7280;font-size:14px">{rating}/5 sur Google</span>'

    # Services en grille
    services_html = "".join(
        f'<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px;font-size:15px;color:#1a1a2e">'
        f'<span style="color:#e94560;margin-right:8px">→</span>{_esc(s)}</div>'
        for s in services
    )

    # Badges confiance
    badges_html = " · ".join(
        f'<span style="background:#eff6ff;color:#1e40af;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600">{b.strip()}</span>'
        for b in trust_badges.split("·")
    )

    # Section contact
    contact_parts = []
    if phone:
        contact_parts.append(f'📞 <a href="tel:{phone}" style="color:#e94560;text-decoration:none;font-weight:700">{_esc(phone)}</a>')
    if website:
        contact_parts.append(f'🌐 <a href="{_esc(website)}" style="color:#1e3a5f;text-decoration:none">{_esc(website)}</a>')
    contact_html = " &nbsp;·&nbsp; ".join(contact_parts) if contact_parts else ""

    faq_section = _faq_html(faq_items or [])

    # Bloc "À lire aussi" (maillage interne discret)
    from .link_injector import build_link_block
    link_block = build_link_block(internal_links or [])

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(profession.capitalize())} à {_esc(ville)} — {_esc(name)}</title>
<meta name="description" content="{_esc(name)}, votre {_esc(profession)} à {_esc(ville)}. Devis gratuit, intervention rapide, travail garanti.">
</head>
<body style="font-family:system-ui,sans-serif;color:#1a1a2e;line-height:1.6;margin:0;padding:0">

<!-- HERO -->
<header style="background:linear-gradient(135deg,#1e3a5f 0%,#e94560 100%);color:#fff;padding:60px 24px;text-align:center">
  <h1 style="font-size:32px;font-weight:800;margin:0 0 12px">{_esc(profession.capitalize())} à {_esc(ville)} — {_esc(name)}</h1>
  <p style="font-size:18px;opacity:.9;margin:0 0 20px">{_esc(intro_text[:100])}…</p>
  {f'<a href="tel:{phone}" style="background:#fff;color:#e94560;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:16px;display:inline-block">📞 Appeler maintenant</a>' if phone else ''}
</header>

<main style="max-width:800px;margin:0 auto;padding:40px 24px">

  <!-- INTRO -->
  <section style="margin-bottom:40px">
    <h2 style="font-size:22px;font-weight:700;color:#1a1a2e;margin-bottom:16px">Votre {_esc(profession)} de confiance à {_esc(ville)}</h2>
    <p style="font-size:16px;color:#374151">{_esc(intro_text)}</p>
    {f'<p style="margin-top:16px">{rating_html}</p>' if rating_html else ''}
  </section>

  <!-- SERVICES -->
  <section style="margin-bottom:40px">
    <h2 style="font-size:22px;font-weight:700;color:#1a1a2e;margin-bottom:20px">Nos prestations à {_esc(ville)}</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px">
      {services_html}
    </div>
  </section>

  <!-- CONFIANCE -->
  <section style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:24px;margin-bottom:40px;text-align:center">
    <h2 style="font-size:18px;font-weight:700;color:#1a1a2e;margin:0 0 16px">Pourquoi choisir {_esc(name)} ?</h2>
    <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center">
      {badges_html}
    </div>
    {f'<p style="margin-top:16px;font-size:15px">{contact_html}</p>' if contact_html else ''}
  </section>

  <!-- FAQ -->
  {faq_section}

</main>

<!-- FOOTER -->
<footer style="text-align:center;padding:32px 24px;background:#f3f4f6;color:#6b7280;font-size:13px;margin-top:48px">
  {_esc(name)} · {_esc(profession.capitalize())} à {_esc(ville)}
  {f" · {_esc(phone)}" if phone else ""}
</footer>

{link_block}
</body>
</html>"""
