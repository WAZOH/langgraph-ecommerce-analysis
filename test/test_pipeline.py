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
    assert report["product"] != "" and report["market"] != ""


def test_pipeline_used_at_least_one_tool(report):
    assert len(report["tools_used"]) > 0


def test_pipeline_insights_are_complete(report):
    # Les blocs obligatoirs du rapport doivent toujours être présents "executive_summary", "market_score", "recommendations"
    for key in ("executive_summary", "market_score", "recommendations"):
        assert key in report["insights"]
