"""
test_pipeline.py — Vérifie que le pipeline complet produit un rapport valide.
"""

import os
import pytest

os.environ.pop("SERPAPI_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

from app.agent import run_analysis

PROMPT = "Analyse le marche canadien pour les Nike Air Max 90. Je veux savoir si c'est rentable de les revendre en ligne."
SAMPLE_PRODUCT = "Nike Air Max 90"
SAMPLE_MARKET  = "Canada"

@pytest.fixture(scope="module")
def report():
    """Lance le pipeline une seule fois pour tous les tests du module."""
    return run_analysis(PROMPT)


def test_pipeline_extracts_product_and_market(report):
    # Vérifie que l'orchestrateur a bien extrait le produit et le marché depuis le prompt.
    # Les deux champs ne doivent pas être vides après le pipeline.
    assert report["product"] != "" and report["market"] != ""


def test_pipeline_used_at_least_one_tool(report):
    # Vérifie que le pipeline a appelé au moins un outil de collecte (scraper, sentiment ou trends).
    # Un rapport généré sans aucun outil serait basé sur rien.
    assert len(report["tools_used"]) > 0


def test_pipeline_insights_are_complete(report):
    # Vérifie que les 3 blocs obligatoires sont toujours présents dans les insights,
    # peu importe l'intention détectée ou les outils utilisés.
    for key in ("executive_summary", "market_score", "recommendations"):
        assert key in report["insights"]
