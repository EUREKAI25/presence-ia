"""
Tests du module ia_test — normalisation, extraction, mention fuzzy
Inclut les cas réels de bruit observés en production (2026-02-18).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────

def _entities(text):
    from src.ia_test import extract_entities
    return extract_entities(text)

def _competitors(text, name="Test SARL", website=None):
    from src.ia_test import extract_entities, competitors_from
    return competitors_from(extract_entities(text), name, website)


# ── Normalize ─────────────────────────────────────────────────────────────

class TestNormalize:
    def test_lowercase(self):
        from src.ia_test import norm
        assert norm("DUPONT") == "dupont"

    def test_strip_accents(self):
        from src.ia_test import norm
        r = norm("Plomberie Étoile")
        assert "toile" in r

    def test_strip_legal(self):
        from src.ia_test import norm
        r = norm("Couvreur SARL Dupont")
        assert "sarl" not in r

    def test_empty(self):
        from src.ia_test import norm
        assert norm("") == ""


# ── Domain ────────────────────────────────────────────────────────────────

class TestExtractDomain:
    def test_basic_url(self):
        from src.ia_test import domain
        assert domain("https://www.dupont.fr") == "dupont.fr"

    def test_no_www(self):
        from src.ia_test import domain
        assert domain("https://couvreur-paris.com/contact") == "couvreur-paris.com"

    def test_empty(self):
        from src.ia_test import domain
        assert domain("") == ""

    def test_not_url(self):
        from src.ia_test import domain
        # Texte sans protocole http:// → retourne ""
        assert domain("Couvreur Paris") == ""

    def test_url_avec_query_string(self):
        from src.ia_test import domain
        assert domain("https://martin-toiture.fr/contact?ref=IA") == "martin-toiture.fr"


# ── IsMentioned ───────────────────────────────────────────────────────────

class TestIsMentioned:
    # Signature : is_mentioned(text, name, website=None)
    def test_exact_match(self):
        from src.ia_test import is_mentioned
        assert is_mentioned("Je recommande Dupont Toiture", "Dupont Toiture") is True

    def test_fuzzy_match(self):
        from src.ia_test import is_mentioned
        # Le texte IA cite "Toitures" (pluriel), le nom du prospect est "Toiture" (singulier)
        assert is_mentioned("Dupont Toitures est excellent", "Dupont Toiture") is True

    def test_no_match(self):
        from src.ia_test import is_mentioned
        assert is_mentioned("Je recommande Martin Couverture", "Dupont Toiture") is False

    def test_website_match(self):
        from src.ia_test import is_mentioned
        text = "Visitez https://www.dupont.fr pour plus d'infos"
        assert is_mentioned(text, "Dupont Plomberie",
                            website="https://www.dupont.fr") is True


# ── Extraction — cas réels de bruit production ────────────────────────────

class TestExtractEntitiesNoBruitProduction:
    """
    Cas réels observés le 2026-02-18 : les IA répondaient de façon générique
    sans citer de vrais artisans. L'extracteur renvoyait du bruit pur.
    Tous ces cas DOIVENT retourner [].
    """

    def test_bordeaux_seul_est_bruit(self):
        """Ville seule = stopword = rejeté."""
        assert _entities("Je vous conseille de chercher à Bordeaux.") == []

    def test_voici_est_bruit(self):
        """Verbe de transition courant dans les réponses IA."""
        assert _entities("Voici mes recommandations pour votre recherche.") == []

    def test_google_maps_est_bruit(self):
        """Plateforme générique."""
        assert _entities("Consultez Google Maps pour trouver un plombier.") == []

    def test_recommandations_est_bruit(self):
        assert _entities("Recommandations : cherchez sur les annuaires locaux.") == []

    def test_demandez_est_bruit(self):
        assert _entities("Demandez à votre entourage ou consultez les avis.") == []

    def test_avis_seul_est_bruit(self):
        assert _entities("Avis clients disponibles en ligne.") == []

    def test_content_listmodels_gemini_est_bruit(self):
        """Réponse d'erreur Gemini observée en prod."""
        assert _entities("Content Call ListModels") == []

    def test_trouver_ressources_est_bruit(self):
        """Réponse Anthropic générique observée en prod."""
        result = _entities("Trouver Ressources locales disponibles sur internet.")
        assert result == []

    def test_reponse_ia_generique_complete(self):
        """Texte complet typique d'une IA qui refuse de nommer des artisans."""
        text = (
            "Je vous recommande de consulter Google Maps, Pages Jaunes ou "
            "Yelp pour trouver un plombier à Bordeaux. Voici quelques conseils : "
            "demandez des devis, vérifiez les avis clients, et contactez plusieurs "
            "professionnels. Recommandations : privilégiez les artisans certifiés RGE."
        )
        result = _competitors(text)
        assert result == []


# ── Extraction — vrais concurrents doivent passer ────────────────────────

class TestExtractEntitiesVraisConcurrents:
    """
    Des noms d'entreprises réels multi-tokens doivent être détectés.
    """

    def test_deux_concurrents_reels(self):
        text = "Je recommande Martin Couverture et Dupont Toiture pour vos travaux."
        entities = _entities(text)
        values = [e["value"] for e in entities]
        assert any("Martin Couverture" in v or "Dupont Toiture" in v for v in values)

    def test_concurrent_avec_suffixe_legal(self):
        """SARL n'empêche pas la détection si le nom est valide."""
        text = "L'entreprise Couverture Bretonne SARL intervient rapidement."
        entities = _entities(text)
        assert len(entities) >= 1

    def test_url_concurrent(self):
        """URL d'un concurrent doit être capturée."""
        text = "Vous pouvez consulter https://www.martin-toiture.fr pour comparer."
        entities = _entities(text)
        assert any(e["type"] == "url" for e in entities)

    def test_single_word_rejecte(self):
        """Un nom d'une seule majuscule ne doit pas passer."""
        result = _entities("Contactez Dupont pour plus d'informations.")
        # "Dupont" seul = 1 token = rejeté
        company_values = [e["value"] for e in result if e["type"] == "company"]
        assert not any(v.strip() == "Dupont" for v in company_values)

    def test_token_trop_court_rejete(self):
        """Tokens de moins de 3 chars rejetés."""
        result = _entities("Le Sa Bo est une entreprise locale.")
        assert result == []

    def test_empty_text(self):
        assert _entities("") == []

    def test_competitors_from_exclut_le_prospect(self):
        """Le prospect lui-même ne doit pas apparaître dans les concurrents."""
        text = "Dupont Toiture est souvent cité, tout comme Martin Couverture."
        result = _competitors(text, name="Dupont Toiture")
        assert not any("Dupont" in c for c in result)
