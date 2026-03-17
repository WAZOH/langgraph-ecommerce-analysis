"""
tools.py
--------
Les 3 outils de collecte de donnees :
  1. fetch_scraper()   — SerpApi Google Shopping  (mock si cle manquante)
  2. fetch_sentiment() — SerpApi Google Shopping Reviews (mock si cle manquante)
  3. fetch_trends()    — SerpApi Google Trends     (mock si cle manquante)

Chaque fonction retourne un dict avec exactement la meme structure,
que les donnees viennent de la vraie API ou du mock :
  {
      "source": "serpapi" | "mock",
      "data":   <liste de strings ou de dicts>
  }
"""

import logging
from functools import lru_cache

from app.config import cfg
from app.fallbacks import (
    _fallback_mock_scraper, _fallback_mock_sentiment, _fallback_mock_trends,
)

log = logging.getLogger(__name__)


# -------------------------------------------------
# SHARED  (SerpApi Google Shopping — cached)
# -------------------------------------------------

# Décorateur Least Recently used = Efface les résultats les plus anciens du cache. 
# Garde en mémoire les résultats des 32 dernières combinaisons d'arguments différentes.
# L'idée est de réutiliser les résultats de Google Shopping entre scraper et reviews, qui font tous les deux appel à la même API 
# et peuvent être lancés dans n'importe quel ordre selon la décision de l'orchestrateur.
@lru_cache(maxsize=32)
def _fetch_shopping_raw(product: str, market: str) -> tuple:
    """
    Appel Google Shopping partage entre scraper et reviews.
    Mis en cache par (product, market) pour eviter les appels API dupliques
    dans le meme pipeline run.
    Retourne un tuple de dicts (immuable, safe pour le cache).
    """
    from serpapi import GoogleSearch

    results = GoogleSearch({
        "engine":   "google_shopping",
        "q":        product,
        "location": market,
        "hl":       "en",
        "api_key":  cfg.serpapi_key,
        "num":      cfg.max_serp_results,
    }).get_dict()

    shopping = results.get("shopping_results", [])
    log.info(f"[google_shopping] {len(shopping)} résultats pour '{product}' / '{market}' (cache miss)")
    return tuple(shopping)


# -------------------------------------------------
# SCRAPER  (SerpApi Google Shopping)
# -------------------------------------------------

def fetch_scraper(product: str, market: str) -> dict:
    """
    Cherche les prix du produit sur Google Shopping via SerpApi.
    Retourne une liste de dicts : [{"source": ..., "price": ..., "title": ...}]
    Fallback mock si la cle SerpApi est absente ou si une erreur survient.
    """
    if cfg.has_serpapi():
        try:
            return _serpapi_scraper(product, market)
        except Exception as e:
            log.warning(f"SerpApi scraper failed ({e}), using mock.")

    return _fallback_mock_scraper(product, market)


def _serpapi_scraper(product: str, market: str) -> dict:
    shopping_results = list(_fetch_shopping_raw(product, market))

    items = []
    for r in shopping_results:
        raw = r.get("price", "").replace("$", "").replace(",", "").strip()
        try:
            items.append({
                "source": r.get("source", "Unknown"),
                "price":  float(raw.split()[0]),
                "title":  r.get("title", ""),
            })
        except (ValueError, IndexError):
            continue

    if not items:
        return _fallback_mock_scraper(product, market)

    return {"source": "serpapi", "data": items}



# -------------------------------------------------
# SENTIMENT  (SerpApi Google Shopping Reviews)
# -------------------------------------------------

def fetch_sentiment(product: str, market: str = "") -> dict:
    """
    Recupere les avis Google Shopping pour le produit via SerpApi.
    Retourne une liste de strings (titres + extraits de reviews).
    market est optionnel — permet de reutiliser le cache Google Shopping
    partage avec fetch_scraper si le meme market est passe.
    Fallback mock si la cle SerpApi est absente ou si une erreur survient.
    """
    if cfg.has_serpapi():
        try:
            return _serpapi_reviews(product, market)
        except Exception as e:
            log.warning(f"SerpApi reviews fetch failed ({e}), using mock.")

    return _fallback_mock_sentiment(product)


def _serpapi_reviews(product: str, market: str) -> dict:
    from serpapi import GoogleSearch

    # Étape 1 : réutilise le cache Google Shopping (zéro appel API si scraper déjà exécuté)
    shopping_results = list(_fetch_shopping_raw(product, market))

    top_results = sorted(
        shopping_results,
        key=lambda r: r.get("reviews", 0),
        reverse=True,
    )[:cfg.max_serp_results]

    page_tokens = [
        r["immersive_product_page_token"]
        for r in top_results
        if r.get("immersive_product_page_token")
    ]

    log.info(f"[Serpapi] {len(page_tokens)} page_token(s) trouvés pour '{product}'")

    if not page_tokens:
        log.warning(f"[Serpapi] Aucun page_token trouvé pour '{product}' — Fallback aux données mock.")
        return _fallback_mock_sentiment(product)

    # Étape 2 : récupérer les avis pour chaque page_token
    # Note : google_immersive_product ne supporte pas la pagination des reviews (~7 max par produit).
    # On compense en scannant jusqu'à 10 produits différents.
    all_reviews = []
    seen = set()
    for token in page_tokens[:10]:
        if len(all_reviews) >= cfg.max_serp_results:
            break
        result = GoogleSearch({
            "engine":     "google_immersive_product",
            "page_token": token,
            "api_key":    cfg.serpapi_key,
        }).get_dict()

        for r in result.get("product_results", {}).get("user_reviews", []):
            text = r.get("title", "")
            if r.get("text"):
                text += " — " + r["text"][:200]
            if text and text not in seen:
                seen.add(text)
                all_reviews.append(text)

    log.info(f"[Serpapi] {len(all_reviews)} reviews uniques collectées sur {min(len(page_tokens), 10)} produits scannés.")

    if not all_reviews:
        log.warning(f"[Serpapi] Aucun user_reviews trouvé — Fallback aux données mock.")
        return _fallback_mock_sentiment(product)

    return {"source": "serpapi", "data": all_reviews}


# -------------------------------------------------
# TRENDS  (SerpApi Google Trends)
# -------------------------------------------------

def fetch_trends(product: str, market: str) -> dict:
    """
    Analyse les tendances de prix et de popularite via SerpApi Google Trends.
    Retourne une liste de strings decrivant les tendances observees.
    Fallback mock si la cle SerpApi est absente.
    """
    if cfg.has_serpapi():
        try:
            return _serpapi_trends(product, market)
        except Exception as e:
            log.warning(f"SerpApi trends failed ({e}), using mock.")

    return _fallback_mock_trends(product, market)


def _serpapi_trends(product: str, market: str) -> dict:
    from serpapi import GoogleSearch

    country = "CA" if "canada" in market.lower() else "US"

    results = GoogleSearch({
        "engine":   "google_trends",
        "q":        product,
        "geo":      country,
        "api_key":  cfg.serpapi_key,
        "data_type": "TIMESERIES",
    }).get_dict()

    insights = []

    # Interets dans le temps
    timeline = results.get("interest_over_time", {}).get("timeline_data", [])
    if timeline:
        values = [
            point["values"][0]["extracted_value"]
            for point in timeline
            if point.get("values")
        ]
        if values:
            recent   = sum(values[-4:]) / 4   # moyenne des 4 dernieres periodes
            previous = sum(values[-8:-4]) / 4  # 4 periodes precedentes
            if recent > previous * 1.1:
                insights.append(f"L'intérêt de recherche est EN HAUSSE (+{round((recent/previous - 1)*100)}% vs période précédente).")
            elif recent < previous * 0.9:
                insights.append(f"L'intérêt de recherche est EN BAISSE ({round((recent/previous - 1)*100)}% vs période précédente).")
            else:
                insights.append("L'intérêt de recherche est STABLE sur les dernières semaines.")

            peak = max(range(len(values)), key=lambda i: values[i])
            insights.append(f"Pic d'intérêt de recherche observé à la période {peak} (0=la plus ancienne).")

    # Requetes associees (popularite relative)
    related = results.get("related_queries", {}).get("rising", [])
    if related:
        top = [q["query"] for q in related[:3]]
        insights.append(f"Recherches associées en hausse : {', '.join(top)}.")

    if not insights:
        return _fallback_mock_trends(product, market)

    return {"source": "serpapi", "data": insights}
