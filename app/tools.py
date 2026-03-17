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
def _fetch_shopping_raw(product: str, market: str, market_code: str = "CA") -> tuple:
    """
    Appel Google Shopping partage entre scraper et reviews (sentiment).
    Mis en cache par (product, market, market_code) pour eviter les appels API dupliques
    dans le meme pipeline run.
    Retourne un tuple de dicts (immuable, safe pour le cache).
    """
    from serpapi import GoogleSearch

    results = GoogleSearch({
        "engine":   "google_shopping",
        "q":        product,
        "gl":       market_code.lower(),
        # "hl":       "en",
        "api_key":  cfg.serpapi_key,
        "num":      cfg.max_serp_results,
    }).get_dict()

    shopping = results.get("shopping_results", [])
    log.info(f"[google_shopping] {len(shopping)} résultats pour '{product}' / '{market}' ({market_code}) (cache miss)")
    # log.info(f"Shopping = {shopping}")

    return tuple(shopping)


# -------------------------------------------------
# SCRAPER  (SerpApi Google Shopping)
# -------------------------------------------------

def fetch_scraper(product: str, market: str, market_code: str = "CA") -> dict:
    """
    Cherche les prix du produit sur Google Shopping via SerpApi.
    Retourne une liste de dicts : [{"source": ..., "price": ..., "title": ...}]
    Fallback mock si la cle SerpApi est absente ou si une erreur survient.
    """
    if cfg.has_serpapi():
        try:
            return _serpapi_scraper(product, market, market_code)
        except Exception as e:
            log.warning(f"SerpApi a échoué avec erreur ({e}), on utilise les données mock.")

    return _fallback_mock_scraper(product, market)


def _serpapi_scraper(product: str, market: str, market_code: str = "CA") -> dict:
    shopping_results = list(_fetch_shopping_raw(product, market, market_code))

    items = []
    for r in shopping_results:
        price = r.get("extracted_price")
        if price is None:
            try:
                raw = "".join(c for c in r.get("price", "") if c.isdigit() or c == ".")
                price = float(raw)
            except (ValueError, IndexError):
                continue
        items.append({
            "source": r.get("source", "Unknown"),
            "price":  float(price),
            "title":  r.get("title", ""),
        })

    if not items:
        return _fallback_mock_scraper(product, market)

    return {"source": "serpapi", "data": items}



# -------------------------------------------------
# SENTIMENT  (SerpApi Google Shopping Reviews)
# -------------------------------------------------

def fetch_sentiment(product: str, market: str = "", market_code: str = "CA") -> dict:
    """
    Récupère les avis Google Shopping pour le produit via SerpApi.
    Retourne une liste de strings (titres + extraits de reviews).

    Fallback mock si la cle SerpApi est absente ou si une erreur survient.

    NOTE: L'API Serpapi  retourne au maximum ~7 reviews par produit — c'est une
    limite de la plateforme, pas une erreur. 7 reviews est suffisant pour
    l'analyse de sentiment. Ne pas rappeler cet outil si des reviews ont
    deja ete collectees.
    """
    if cfg.has_serpapi():
        try:
            return _serpapi_reviews(product, market, market_code)
        except Exception as e:
            log.warning(f"SerpApi reviews fetch failed ({e}), using mock.")

    return _fallback_mock_sentiment(product)


def _serpapi_reviews(product: str, market: str, market_code: str = "CA") -> dict:
    from serpapi import GoogleSearch

    # Étape 1 : réutilise le cache Google Shopping (zéro appel API si scraper déjà exécuté)
    shopping_results = list(_fetch_shopping_raw(product, market, market_code))

    top_results = sorted(
        shopping_results,
        key=lambda r: r.get("reviews", 0),
        reverse=True,
    )[:cfg.max_serp_results]

    # log.info(f"[Serpapi] {top_results}")

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

    return {
        "source": "serpapi",
        "data": all_reviews
    }


# -------------------------------------------------
# TRENDS  (SerpApi Google Trends)
# -------------------------------------------------

def fetch_trends(product: str, market: str, country_code: str = "CA") -> dict:
    """
    Analyse les tendances de prix et de popularite via SerpApi Google Trends.
    Retourne une liste de strings decrivant les tendances observees.
    Fallback mock si la cle SerpApi est absente.
    country_code : code ISO 3166-1 alpha-2 fourni par l'orchestrateur (ex: "CA", "US", "FR").
    """
    if cfg.has_serpapi():
        try:
            return _serpapi_trends(product, market, country_code)
        except Exception as e:
            log.warning(f"SerpApi trends failed ({e}), using mock.")

    return _fallback_mock_trends(product, market)


def _serpapi_trends(product: str, market: str, country_code: str = "CA") -> dict:
    from serpapi import GoogleSearch

    country = country_code.upper()

    results = GoogleSearch({
        "engine":   "google_trends",
        "q":        product,
        "geo":      country,
        "api_key":  cfg.serpapi_key,
        # "data_type": "TIMESERIES",
    }).get_dict()

    insights = []

    # log.info(f"[Serpapi Trends] Résultats bruts : {results}")

    # Interets dans le temps
    timeline = results.get("interest_over_time", {}).get("timeline_data", [])
    if timeline:
        dates = [point.get("date", "") for point in timeline if point.get("values")]
        values = [
            point["values"][0]["extracted_value"]
            for point in timeline
            if point.get("values")
        ]
        if values:
            non_zero = [v for v in values if v > 0]
            recent   = sum(values[-4:]) / 4
            previous = sum(values[-8:-4]) / 4

            # Tendance générale
            if previous == 0:
                if recent > 0:
                    insights.append("L'intérêt de recherche est EN HAUSSE (données précédentes nulles).")
                else:
                    insights.append("L'intérêt de recherche est STABLE (faible) sur les dernières semaines.")
            elif recent > previous * 1.1:
                insights.append(f"L'intérêt de recherche est EN HAUSSE (+{round((recent/previous - 1)*100)}% vs période précédente).")
            elif recent < previous * 0.9:
                insights.append(f"L'intérêt de recherche est EN BAISSE ({round((recent/previous - 1)*100)}% vs période précédente).")
            else:
                insights.append("L'intérêt de recherche est STABLE sur les dernières semaines.")

            # Pic avec date réelle
            peak_idx = max(range(len(values)), key=lambda i: values[i])
            peak_val = values[peak_idx]
            if peak_val > 0:
                peak_date = dates[peak_idx] if peak_idx < len(dates) else f"période {peak_idx}"
                insights.append(f"Pic d'intérêt maximum ({peak_val}/100) observé la semaine du {peak_date}.")

            # Nouveau produit : peu de données historiques
            zero_ratio = values.count(0) / len(values)
            if zero_ratio > 0.7 and non_zero:
                insights.append(f"Produit récent ou niche : {round(zero_ratio*100)}% des semaines ont un intérêt nul — les données sont concentrées sur {len(non_zero)} semaine(s).")

            # Reprise récente après silence
            if all(v == 0 for v in values[-8:-4]) and recent > 0:
                insights.append(f"Regain d'intérêt récent après une période de silence (4 semaines précédentes à 0).")

            # Post-pic déclin
            if peak_idx < len(values) - 4 and peak_val > 0:
                post_peak_avg = sum(values[peak_idx+1:]) / max(len(values[peak_idx+1:]), 1)
                if post_peak_avg < peak_val * 0.3:
                    insights.append(f"Déclin post-lancement : l'intérêt a fortement chuté depuis le pic ({peak_val}/100 → moy. {round(post_peak_avg)}/100).")

    # Requetes associees — rising en priorité, top en fallback
    related_queries = results.get("related_queries", {})
    related = related_queries.get("rising") or related_queries.get("top", [])
    if related:
        top = [q["query"] for q in related[:3]]
        label = "en hausse" if results.get("related_queries", {}).get("rising") else "populaires"
        insights.append(f"Recherches associées {label} : {', '.join(top)}.")

    if not insights:
        return _fallback_mock_trends(product, market)

    return {"source": "serpapi", "data": insights}
