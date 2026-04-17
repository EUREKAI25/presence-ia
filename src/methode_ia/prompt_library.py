"""
Bibliothèque de prompts — prêts à l'emploi pour le client.
Variables remplies avec les données de l'entreprise.
"""


def generate_prompt_library(
    company_name: str,
    city: str,
    business_type: str,
    website: str = "",
) -> dict:
    """
    Génère 4 prompts directement copiables par le client.

    Returns:
        {
            "page_service":  str,
            "faq":           str,
            "rewrite":       str,
            "optimize":      str,
        }
    """
    return {
        "page_service":  _prompt_page_service(company_name, city, business_type),
        "faq":           _prompt_faq(company_name, city, business_type),
        "rewrite":       _prompt_rewrite(company_name, city, business_type, website),
        "optimize":      _prompt_optimize(company_name, city, business_type, website),
    }


def _prompt_page_service(company_name: str, city: str, business_type: str) -> str:
    return f"""Crée une page de contenu complète pour mon site web.

Contexte :
- Entreprise : {company_name}
- Métier : {business_type}
- Ville principale : {city}

Objectif : que cette page soit citée par ChatGPT, Gemini et Claude quand quelqu'un demande "{business_type} à {city}".

Structure à respecter EXACTEMENT :

# {business_type.capitalize()} à {city} — {company_name}

[Introduction de 3 phrases : qui nous sommes, notre expertise, notre zone d'intervention à {city}]

## Nos prestations à {city}
[Liste de 5-7 services avec une description de 2 phrases chacun]

## Pourquoi choisir {company_name} ?
[3-4 arguments différenciants concrets : années d'expérience, garanties, délais, certifications]

## Zone d'intervention
[{city} et liste de 8-10 communes voisines]

## Questions fréquentes — {business_type} à {city}
[5 questions-réponses sur le service, les tarifs, les délais, les garanties]

## Contact
{company_name} — {business_type} à {city}
[Téléphone] | [Email] | [Adresse]

Contraintes :
- Mentionner "{company_name}" et "{city}" dans les 2 premières phrases
- Pas de jargon technique — ton professionnel et accessible
- 700-900 mots au total
- Format markdown avec titres H1, H2"""


def _prompt_faq(company_name: str, city: str, business_type: str) -> str:
    return f"""Génère une FAQ complète pour mon activité de {business_type} à {city}.

Contexte :
- Entreprise : {company_name}
- Métier : {business_type}
- Ville : {city}

Objectif : que cette FAQ réponde exactement aux questions que les gens posent à ChatGPT, Gemini et Claude sur {business_type} à {city}.

Génère 10 questions-réponses en respectant ce format pour chaque entrée :

**Q : [question]**
R : [Réponse de 3-5 phrases. Mentionner {company_name} naturellement dans la réponse. Inclure la ville {city}.]

Questions à couvrir obligatoirement :
1. Quel est le tarif d'un {business_type} à {city} ?
2. Quel est le délai d'intervention ?
3. Quelle zone couvrez-vous autour de {city} ?
4. Êtes-vous disponible en urgence ?
5. Quelles garanties offrez-vous ?
6. Comment se passe un premier rendez-vous ?
7. Avez-vous des avis clients ?
8. Pourquoi choisir {company_name} plutôt qu'un concurrent ?
9. [Question spécifique au métier de {business_type} — à choisir]
10. [Question spécifique au métier de {business_type} — à choisir]

Ton : direct, rassurant, sans jargon technique."""


def _prompt_rewrite(company_name: str, city: str, business_type: str, website: str) -> str:
    website_line = f"- Site web actuel : {website}" if website else "- Site web : [VOTRE URL]"
    return f"""Réécris le contenu suivant pour qu'il soit optimisé pour les assistants IA (ChatGPT, Gemini, Claude).

Mon contexte :
- Entreprise : {company_name}
- Métier : {business_type} à {city}
{website_line}
- Objectif : être cité quand quelqu'un demande "{business_type} à {city}" à un assistant IA

Contenu actuel à réécrire :
[COLLE ICI TON TEXTE EXISTANT]

Instructions de réécriture :
1. Mentionner "{company_name}" dès la première phrase
2. Inclure "{business_type} à {city}" dans le premier paragraphe
3. Ajouter des informations concrètes : zone d'intervention, expérience, garanties
4. Structurer en paragraphes courts (3-4 phrases maximum)
5. Ajouter une mini-FAQ de 5 Q/R à la fin
6. Terminer par les coordonnées complètes sur une ligne

Longueur finale : similaire à l'original, mais version optimisée IA.
Ton : professionnel, direct, sans jargon."""


def _prompt_optimize(company_name: str, city: str, business_type: str, website: str) -> str:
    website_line = f"URL à analyser : {website}" if website else "URL à analyser : [VOTRE PAGE]"
    return f"""Analyse cette page et propose des améliorations concrètes pour qu'elle soit mieux recommandée par les assistants IA.

{website_line}

Contexte :
- Entreprise : {company_name}
- Métier : {business_type} à {city}
- Problème : peu ou pas cité par ChatGPT/Gemini/Claude

Pour chaque amélioration, donne-moi :
1. Ce qui doit être modifié (section, titre, paragraphe...)
2. Pourquoi ça améliore la visibilité dans les IA
3. Le texte exact de remplacement ou d'ajout

Règles d'analyse :
- Vérifier que "{company_name}" apparaît dès le début
- Vérifier que "{business_type} à {city}" est dans le titre H1
- Identifier les zones de texte trop courtes ou trop génériques
- Repérer l'absence de FAQ, de données de contact, de zone d'intervention
- Signaler les données structurées manquantes (JSON-LD)

Donne-moi les 5 modifications les plus impactantes en priorité."""
