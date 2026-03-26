"""
test_nodes.py — Vérifie que chaque node fait son travail dans le graphe.
"""

import os
import pytest

os.environ.pop("SERPAPI_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

from app.tools import fetch_scraper, fetch_sentiment, fetch_trends
from app.nodes import node_orchestrator, node_scraper, node_sentiment, node_trends, node_report

SAMPLE_PROMPT  = "Analyse le marche canadien pour les Nike Air Max 90. Je veux savoir si c'est rentable de les revendre en ligne."
SAMPLE_PRODUCT = "Nike Air Max 90"
SAMPLE_MARKET  = "Canada"
SAMPLE_MARKET_CODE = "CA"


@pytest.fixture
def base_state() -> dict:
    return {
        "prompt":         SAMPLE_PROMPT,
        "product":        SAMPLE_PRODUCT,
        "market":         SAMPLE_MARKET,
        "market_code":    "CA",
        "next_action":    "",
        "turn":           0,
        "last_reasoning": "",
        "reasoning_log":  [],
        "scraper_data":   {},
        "sentiment_data": {},
        "trends_data":    {},
        "report":          {},
        "errors":          [],
        "exhausted_tools": [],
    }


@pytest.fixture
def populated_state(base_state) -> dict:
    base_state["scraper_data"]   = fetch_scraper(SAMPLE_PRODUCT, SAMPLE_MARKET, SAMPLE_MARKET_CODE)
    base_state["sentiment_data"] = fetch_sentiment(SAMPLE_PRODUCT, SAMPLE_MARKET, SAMPLE_MARKET_CODE)
    base_state["trends_data"]    = fetch_trends(SAMPLE_PRODUCT, SAMPLE_MARKET, SAMPLE_MARKET_CODE)
    return base_state


def test_orchestrator_routes_to_valid_node(base_state):
    # Vérifie que node_orchestrator retourne toujours une action connue du graphe.
    # Peu importe l'état, next_action ne peut pas être une valeur arbitraire —
    # sinon route_next() tomberait sur le fallback "node_report".
    result = node_orchestrator(base_state)
    assert result["next_action"] in ("node_scraper", "node_sentiment", "node_trends", "node_report")


def test_data_nodes_collect_data(base_state):
    # Vérifie que chaque node de collecte remplit bien son champ dans l'état.
    # node_scraper  → scraper_data["data"]   : liste de prix
    # node_sentiment → sentiment_data["data"] : liste de reviews
    # node_trends   → trends_data["data"]    : liste d'insights textuels
    assert len(node_scraper(base_state)["scraper_data"]["data"]) > 0
    assert len(node_sentiment(base_state)["sentiment_data"]["data"]) > 0
    assert len(node_trends(base_state)["trends_data"]["data"]) > 0


def test_report_node_generates_complete_report(populated_state):
    # Vérifie que node_report produit un rapport avec les 3 blocs toujours requis,
    # en partant d'un état déjà rempli (scraper + sentiment + trends).
    # populated_state est fourni par le fixture qui appelle les 3 outils au préalable.
    report = node_report(populated_state)["report"]
    assert report["product"] and report["market"]
    for key in ("executive_summary", "market_score", "recommendations"):
        assert key in report["insights"]
