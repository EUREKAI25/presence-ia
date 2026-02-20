"""
Exemple simple : Landing page avec hero + pricing + CTA.
Génère un fichier HTML de démo.
"""
import sys
from pathlib import Path

# Ajout du src au path pour import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import (
    Page, Section, Column, DesignTokens,
    HeroModule, PricingModule, PricingPlan, CTAModule,
    render_page
)


def main():
    # Design personnalisé
    tokens = DesignTokens(
        primary_color="#667eea",
        secondary_color="#764ba2",
        font_size_base=16,
        line_height_base=1.6,
        spacing_unit=8
    )

    # Construction de la page
    page = Page(
        title="Mon SaaS Génial",
        description="Automatisez votre business avec notre solution IA",
        design_tokens=tokens,
        sections=[
            # Section Hero (pleine largeur)
            Section(
                order=0,
                columns=[
                    Column(span=12, module=HeroModule(
                        badge="✨ Nouveau — Propulsé par l'IA",
                        title="Automatisez votre business en 5 minutes",
                        subtitle="Notre plateforme IA transforme vos processus manuels en workflows automatisés. Plus de 10 000 entreprises nous font confiance.",
                        cta_primary={"label": "Démarrer gratuitement", "href": "#pricing"},
                        cta_secondary={"label": "Voir la démo", "href": "#demo"}
                    ))
                ]
            ),

            # Section Pricing (3 colonnes)
            Section(
                order=1,
                bg_color="#f7fafc",
                columns=[
                    Column(span=12, module=PricingModule(
                        title="Tarifs transparents",
                        subtitle="Choisissez le plan adapté à vos besoins",
                        plans=[
                            PricingPlan(
                                name="Starter",
                                price="29€ / mois",
                                features=[
                                    "5 projets automatisés",
                                    "100 exécutions / mois",
                                    "Support email",
                                    "Intégrations de base"
                                ],
                                cta_label="Commencer",
                                cta_href="#signup"
                            ),
                            PricingPlan(
                                name="Pro",
                                price="99€ / mois",
                                features=[
                                    "Projets illimités",
                                    "1000 exécutions / mois",
                                    "Support prioritaire",
                                    "Toutes les intégrations",
                                    "Analytics avancées"
                                ],
                                is_featured=True,
                                cta_label="Commencer",
                                cta_href="#signup"
                            ),
                            PricingPlan(
                                name="Enterprise",
                                price="Sur mesure",
                                features=[
                                    "Volume personnalisé",
                                    "SLA garanti",
                                    "Support dédié",
                                    "Déploiement on-premise",
                                    "Formation équipe"
                                ],
                                cta_label="Nous contacter",
                                cta_href="#contact"
                            )
                        ]
                    ))
                ]
            ),

            # Section CTA finale
            Section(
                order=2,
                columns=[
                    Column(span=12, module=CTAModule(
                        title="Prêt à automatiser votre business ?",
                        subtitle="Rejoignez 10 000+ entreprises qui gagnent du temps chaque jour",
                        button_label="Démarrer gratuitement",
                        button_href="#signup"
                    ))
                ]
            )
        ]
    )

    # Génération HTML
    html = render_page(page)

    # Sauvegarde
    output_path = Path(__file__).parent / "demo_landing.html"
    output_path.write_text(html, encoding="utf-8")

    print(f"✅ Page générée : {output_path}")
    print(f"   Ouvrir avec : open {output_path}")


if __name__ == "__main__":
    main()
