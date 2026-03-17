"""
test_tools.py — Vérifie que chaque outil retourne des données utilisables.
"""

import os

os.environ.pop("SERPAPI_KEY", None)

from app.tools import fetch_scraper, fetch_sentiment, fetch_trends


def test_scraper_returns_prices():
    data = fetch_scraper("iPhone 15", "Canada")["data"]
    assert len(data) > 0
    assert all("price" in item and "title" in item for item in data)


def test_sentiment_returns_reviews():
    data = fetch_sentiment("Nike Air Max")["data"]
    assert len(data) > 0
    assert all(isinstance(text, str) for text in data)


def test_trends_returns_insights():
    data = fetch_trends("Samsung Galaxy S24", "Canada")["data"]
    assert len(data) > 0
    assert all(isinstance(text, str) for text in data)
