"""
Logique de suggestion de liens internes.

Fonction principale :
  build_internal_link_suggestions(page, related_pages, max_links=3) → list[dict]

Chaque lien retourné :
  { title, url, anchor, reason }

Règles V1 :
  - max 3 liens par page
  - jamais de lien vers la page elle-même
  - prioriser même profession + même ville
  - ancres naturelles et variées (pas de spam)
  - uniquement vers pages publiées (URL non vide)
"""

# ── Ancres ────────────────────────────────────────────────────────────────────

_ANCHORS_BY_TYPE: dict[str, str] = {
    "service_local": "{profession} à {ville}",
    "faq":           "FAQ {profession} {ville}",
    "guide":         "Guide {profession}",
    "audit_public":  "Audit IA {profession}",
    "autre":         "{profession} — {ville}",
}


def _build_anchor(profession: str, city: str, page_type: str) -> str:
    """Construit une ancre naturelle à partir du type de page et de la localisation."""
    template = _ANCHORS_BY_TYPE.get(page_type, "{profession} à {ville}")
    return template.format(
        profession = profession.capitalize() if profession else "professionnel",
        ville      = city.capitalize() if city else "votre ville",
    )


def _build_reason(source: dict, target: dict) -> str:
    """Phrase courte expliquant pourquoi ce lien est pertinent."""
    same_prof = source.get("profession", "") == target.get("profession", "")
    same_city = source.get("city", "") == target.get("city", "")

    if same_prof and same_city:
        return f"Même métier et même ville"
    if same_prof:
        target_city = (target.get("city") or "").capitalize()
        return f"Même métier, autre ville ({target_city})"
    if same_city:
        target_prof = (target.get("profession") or "").capitalize()
        return f"Même ville, autre métier ({target_prof})"
    return "Contenu complémentaire"


# ── Suggestions ───────────────────────────────────────────────────────────────

def build_internal_link_suggestions(
    page: dict,
    related_pages: list[dict],
    max_links: int = 3,
) -> list[dict]:
    """
    Construit la liste des liens internes à injecter dans une page.

    Args:
        page          : dict décrivant la page source
                        (profession, city, published_url, page_type, title, slug)
        related_pages : résultat de find_related_pages() — trié par pertinence
        max_links     : maximum de liens (3 par défaut, jamais dépassé)

    Returns:
        list[{title, url, anchor, reason}]
        Liste vide si aucune page liée disponible.
    """
    own_url = (page.get("published_url") or "").rstrip("/").lower()
    seen    = {own_url} if own_url else set()

    suggestions: list[dict] = []

    for rp in related_pages:
        if len(suggestions) >= max_links:
            break

        url = (rp.get("published_url") or "").rstrip("/")
        if not url or url.lower() in seen:
            continue
        seen.add(url.lower())

        anchor = _build_anchor(
            rp.get("profession", ""),
            rp.get("city", ""),
            rp.get("page_type", "service_local"),
        )
        reason = _build_reason(page, rp)

        suggestions.append({
            "title":  rp.get("title") or anchor,
            "url":    url,
            "anchor": anchor,
            "reason": reason,
        })

    return suggestions
