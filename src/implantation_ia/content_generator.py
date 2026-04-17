"""
Générateur de contenus — crée les contenus prêts à intégrer pour le client.
Réutilise la logique de content_engine (faq_generator + page_generator).
Standalone : pas de DB nécessaire.
"""
import json
import logging
from types import SimpleNamespace
from pathlib import Path

log = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "dist" / "implantation_ia"


def _mock_prospect(company_name: str, city: str, business_type: str, website: str = "", phone: str = ""):
    """Crée un objet prospect factice compatible avec content_engine."""
    return SimpleNamespace(
        name=company_name,
        profession=business_type,
        city=city.capitalize(),
        phone=phone,
        website=website,
        url=website,
        token=f"implantation_{company_name[:10].lower().replace(' ', '_')}",
        rating=None,
        cms=None,
    )


def generate_faq_content(
    company_name: str,
    city: str,
    business_type: str,
    queries: list[dict] = None,
    max_items: int = 10,
) -> list[dict]:
    """
    Génère la FAQ complète (10 Q/R) prête à intégrer.
    Réutilise content_engine.faq_generator.
    """
    try:
        from ..content_engine.faq_generator import generate_faq
    except ImportError:
        from src.content_engine.faq_generator import generate_faq

    prospect = _mock_prospect(company_name, city, business_type)
    return generate_faq(prospect, queries or [], max_items=max_items)


def generate_service_page_content(
    company_name: str,
    city: str,
    business_type: str,
    website: str = "",
    faq_items: list[dict] = None,
) -> str:
    """
    Génère la page service HTML complète.
    Réutilise content_engine.page_generator.
    """
    try:
        from ..content_engine.page_generator import generate_service_page
    except ImportError:
        from src.content_engine.page_generator import generate_service_page

    prospect = _mock_prospect(company_name, city, business_type, website)
    return generate_service_page(prospect, faq_items=faq_items or [])


def generate_ia_blocks(
    company_name: str,
    city: str,
    business_type: str,
    website: str = "",
) -> dict:
    """
    Génère les blocs optimisés IA : title, meta, intro, GBP description, JSON-LD.
    """
    bt    = business_type
    city_ = city.capitalize()
    cn    = company_name

    return {
        "title_tag": f"{bt.capitalize()} à {city_} — {cn} | Devis gratuit",
        "meta_description": (
            f"{cn}, votre {bt} à {city_} de confiance. "
            f"Intervention rapide, devis gratuit, travail garanti. "
            f"Contactez-nous dès maintenant."
        ),
        "homepage_intro": (
            f"{cn} est votre {bt} à {city_} et dans les communes voisines. "
            f"Nous intervenons rapidement sur tous types d'interventions {bt}, "
            f"avec transparence sur les tarifs et garantie sur toutes nos prestations. "
            f"Contactez-nous pour un devis gratuit sous 24h."
        ),
        "gbp_description": (
            f"{cn} — {bt.capitalize()} professionnel à {city_}. "
            f"Spécialisés dans [vos spécialités], nous intervenons à {city_} "
            f"et dans un rayon de XX km. Devis gratuit, réponse sous 24h."
        ),
        "jsonld_localbusiness": json.dumps({
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": cn,
            "description": f"{bt.capitalize()} à {city_} — {cn}",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": city_,
                "addressCountry": "FR",
            },
            "telephone": "[VOTRE NUMÉRO]",
            "url": website or f"[URL DE {cn.upper()}]",
            "areaServed": {
                "@type": "City",
                "name": city_,
            },
            "openingHoursSpecification": [
                {
                    "@type": "OpeningHoursSpecification",
                    "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                    "opens": "08:00",
                    "closes": "18:00",
                }
            ],
            "priceRange": "€€",
        }, ensure_ascii=False, indent=2),
        "faq_jsonld_template": json.dumps({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f"Quel est le tarif d'un {bt} à {city_} ?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": f"Chez {cn}, nos tarifs varient selon la prestation. Contactez-nous pour un devis gratuit.",
                    },
                },
                {
                    "@type": "Question",
                    "name": f"Dans quelle zone intervenez-vous autour de {city_} ?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": f"{cn} intervient à {city_} et dans les communes voisines. Contactez-nous pour vérifier votre zone.",
                    },
                },
            ],
        }, ensure_ascii=False, indent=2),
    }


def generate_all_contents(
    company_name: str,
    city: str,
    business_type: str,
    website: str = "",
    queries: list[dict] = None,
) -> dict:
    """
    Génère tous les contenus : FAQ, page service, blocs IA.

    Returns:
        {
            "faq":          list[dict],
            "service_page": str,    # HTML complet
            "ia_blocks":    dict,
            "paths":        dict,   # chemins fichiers sauvegardés
            "errors":       list[str],
        }
    """
    errors = []

    # FAQ
    faq = []
    try:
        faq = generate_faq_content(company_name, city, business_type, queries)
        log.info("[content] FAQ : %d questions", len(faq))
    except Exception as e:
        log.error("[content] FAQ échouée : %s", e)
        errors.append(f"faq: {e}")

    # Page service
    service_page = ""
    try:
        service_page = generate_service_page_content(company_name, city, business_type, website, faq)
        log.info("[content] Page service : %d chars", len(service_page))
    except Exception as e:
        log.error("[content] Page service échouée : %s", e)
        errors.append(f"service_page: {e}")

    # Blocs IA
    ia_blocks = {}
    try:
        ia_blocks = generate_ia_blocks(company_name, city, business_type, website)
        log.info("[content] %d blocs IA générés", len(ia_blocks))
    except Exception as e:
        log.error("[content] Blocs IA échoués : %s", e)
        errors.append(f"ia_blocks: {e}")

    # Sauvegarde
    import re, unicodedata
    def _slug(s: str) -> str:
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:30]

    slug    = _slug(company_name)
    out_dir = _OUTPUT_DIR / slug / "content"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths   = {}

    if faq:
        try:
            p = out_dir / "faq.json"
            p.write_text(json.dumps(faq, ensure_ascii=False, indent=2), encoding="utf-8")
            paths["faq_json"] = str(p)
        except Exception as e:
            errors.append(f"save_faq: {e}")

    if service_page:
        try:
            p = out_dir / "page_service.html"
            p.write_text(service_page, encoding="utf-8")
            paths["service_page"] = str(p)
        except Exception as e:
            errors.append(f"save_page: {e}")

    if ia_blocks:
        try:
            p = out_dir / "ia_blocks.json"
            p.write_text(json.dumps(ia_blocks, ensure_ascii=False, indent=2), encoding="utf-8")
            paths["ia_blocks"] = str(p)
        except Exception as e:
            errors.append(f"save_blocks: {e}")

    return {
        "faq":          faq,
        "service_page": service_page,
        "ia_blocks":    ia_blocks,
        "paths":        paths,
        "errors":       errors,
    }
