"""
test_tools.py — Vérifie que chaque outil retourne des données utilisables.
"""

import os

os.environ.pop("SERPAPI_KEY", None)

from app.tools import fetch_scraper, fetch_sentiment, fetch_trends


def test_scraper_returns_prices():
    # Vérifie que fetch_scraper retourne une liste non vide de résultats.
    # Chaque item doit avoir un champ "price" (float) et "title" (nom du produit).
    # Sans clé SerpApi → utilise le mock, donc toujours des données disponibles.
    data = fetch_scraper("iPhone 15", "Canada")["data"]
    assert len(data) > 0
    assert all("price" in item and "title" in item for item in data)


def test_sentiment_returns_reviews():
    # Vérifie que fetch_sentiment retourne une liste non vide de reviews.
    # Chaque review doit être une string (titre + extrait de l'avis client).
    # Sans clé SerpApi → utilise le mock.
    data = fetch_sentiment("Nike Air Max")["data"]
    assert len(data) > 0
    assert all(isinstance(text, str) for text in data)


def test_trends_returns_insights():
    # Vérifie que fetch_trends retourne une liste non vide de phrases d'analyse.
    # Chaque insight doit être une string décrivant une tendance observée.
    # Sans clé SerpApi → utilise le mock.
    data = fetch_trends("Samsung Galaxy S24", "Canada")["data"]
    assert len(data) > 0
    assert all(isinstance(text, str) for text in data)
