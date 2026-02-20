"""
Exemple d'intégration FastAPI.
Lancer avec : uvicorn fastapi_example:app --reload
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from src import (
    Page, Section, Column, DesignTokens,
    HeroModule, PricingModule, PricingPlan,
    render_page
)

app = FastAPI(title="Page Builder FastAPI Example")


@app.get("/", response_class=HTMLResponse)
def home():
    """Page d'accueil."""
    page = Page(
        title="FastAPI + Page Builder",
        description="Exemple d'intégration",
        design_tokens=DesignTokens(
            primary_color="#667eea",
            secondary_color="#764ba2"
        ),
        sections=[
            Section(
                order=0,
                columns=[
                    Column(span=12, module=HeroModule(
                        badge="FastAPI + Page Builder",
                        title="Créez des pages en quelques lignes",
                        subtitle="Module standalone EURKAI pour générer des landing pages modulaires",
                        cta_primary={"label": "Démarrer", "href": "#pricing"},
                        cta_secondary={"label": "Documentation", "href": "/docs"}
                    ))
                ]
            ),
            Section(
                order=1,
                bg_color="#f7fafc",
                columns=[
                    Column(span=12, module=PricingModule(
                        title="Simple et puissant",
                        plans=[
                            PricingPlan(
                                name="Open Source",
                                price="Gratuit",
                                features=[
                                    "Modules illimités",
                                    "Design system auto",
                                    "Responsive natif",
                                    "Code Python simple"
                                ],
                                is_featured=True,
                                cta_label="Voir sur GitHub",
                                cta_href="https://github.com/EURKAI25/page-builder"
                            )
                        ]
                    ))
                ]
            )
        ]
    )
    return HTMLResponse(render_page(page))


if __name__ == "__main__":
    import uvicorn
    print("🚀 Serveur FastAPI démarré")
    print("   → http://127.0.0.1:8000")
    print("   → http://127.0.0.1:8000/docs (Swagger)")
    uvicorn.run(app, host="127.0.0.1", port=8000)
