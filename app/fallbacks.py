# -------------------------------------------------
# NODE ORCHESTRATEUR
# -------------------------------------------------

def _fallback_extract_from_prompt(prompt: str) -> str:
    """
    Extraction basique du nom de produit depuis le prompt.
    Utilise uniquement en fallback sans Gemini.
    Cherche les mots capitalises ou les noms de marques connus.
    """
    import re
    # Cherche des sequences de mots capitalises (ex: "Nike Air Max 90")
    matches = re.findall(r"(?:[A-Z][a-z]+(?:\s+[A-Z0-9][a-z0-9]*)+)", prompt)
    if matches:
        return max(matches, key=len)
    # Fallback : prend les 3 premiers mots significatifs
    words = [w for w in prompt.split() if len(w) > 3]
    return " ".join(words[:3]) if words else "unknown product"


def _fallback_extract_market_from_prompt(prompt: str) -> str:
    """
    Extraction basique du marche/pays depuis le prompt.
    Utilise uniquement en fallback sans Gemini.
    """
    prompt_lower = prompt.lower()
    markets = {
        "canada":        "Canada",
        "canadian":      "Canada",
        "usa":           "USA",
        "united states": "USA",
        "american":      "USA",
        "france":        "France",
        "french":        "France",
        "uk":            "UK",
        "britain":       "UK",
    }
    for keyword, market in markets.items():
        if keyword in prompt_lower:
            return market
    return "Canada"  # defaut



# -------------------------------------------------
# NODE REPORT
# -------------------------------------------------

def _fallback_rule_based_insights(state: dict) -> dict:
    prices = [
        p["price"]
        for p in state.get("scraper_data", {}).get("data", [])
        if isinstance(p.get("price"), (int, float))
    ]
    avg = round(sum(prices) / len(prices), 2) if prices else 0.0
    n_posts = len(state.get("sentiment_data", {}).get("data", []))

    return {
        "executive_summary": (
            f"Analyse pour {state.get('product')} sur le marché {state.get('market')}. "
            f"Prix moyen : {avg}$. Données issues de {n_posts} avis clients."
        ),
        "pricing": {
            "min":         min(prices, default=0.0),
            "max":         max(prices, default=0.0),
            "average":     avg,
            "recommended": round(avg * 0.97, 2),
            "rationale":   "Légèrement en dessous de la moyenne du marché pour un positionnement compétitif.",
        },
        "sentiment": {
            "score":     0.5,
            "label":     "neutral",
            "positives": ["Données collectées avec succès"],
            "negatives": ["LLM indisponible — analyse rule-based"],
        },
        "trends": {
            "momentum":        "stable",
            "peak_season":     "inconnu",
            "price_evolution": "stable",
        },
        "opportunities":   ["Fourchette de prix identifiée"],
        "risks":           ["Analyse LLM indisponible"],
        "recommendations": [f"Envisager un prix autour de {round(avg * 0.97, 2)}$"],
        "market_score":    5,
    }



# -------------------------------------------------
# TOOL SENTIMENT
# -------------------------------------------------

def _fallback_mock_scraper(product: str, market: str) -> dict:
    currency = "CAD" if "canada" in market.lower() else "USD"
    all_items = [
        {"source": "Amazon",        "price": 159.99, "title": f"{product} — Amazon {currency}"},
        {"source": "Walmart",       "price": 149.99, "title": f"{product} — Walmart {currency}"},
        {"source": "Best Buy",      "price": 174.99, "title": f"{product} — Best Buy {currency}"},
        {"source": "eBay",          "price": 134.99, "title": f"{product} (used) — eBay {currency}"},
        {"source": "Target",        "price": 162.49, "title": f"{product} — Target {currency}"},
        {"source": "Costco",        "price": 144.99, "title": f"{product} (bundle) — Costco {currency}"},
        {"source": "Newegg",        "price": 156.00, "title": f"{product} — Newegg {currency}"},
        {"source": "B&H Photo",     "price": 168.95, "title": f"{product} — B&H Photo {currency}"},
        {"source": "Apple Store",   "price": 179.00, "title": f"{product} — Apple Store {currency}"},
        {"source": "Samsung",       "price": 171.50, "title": f"{product} — Samsung Direct {currency}"},
        {"source": "Rakuten",       "price": 152.75, "title": f"{product} — Rakuten {currency}"},
        {"source": "AliExpress",    "price": 118.00, "title": f"{product} (import) — AliExpress {currency}"},
        {"source": "Staples",       "price": 164.99, "title": f"{product} — Staples {currency}"},
        {"source": "The Source",    "price": 169.99, "title": f"{product} — The Source {currency}"},
        {"source": "Canadian Tire", "price": 157.99, "title": f"{product} — Canadian Tire {currency}"},
        {"source": "Sport Chek",    "price": 172.00, "title": f"{product} — Sport Chek {currency}"},
        {"source": "Shopify Store", "price": 145.00, "title": f"{product} — Boutique indépendante {currency}"},
        {"source": "Facebook Mkt.", "price": 125.00, "title": f"{product} (occasion) — Facebook Marketplace {currency}"},
        {"source": "Kijiji",        "price": 110.00, "title": f"{product} (used) — Kijiji {currency}"},
        {"source": "Costco.ca",     "price": 141.99, "title": f"{product} (online) — Costco.ca {currency}"},
    ]
    return {"source": "mock", "data": all_items}



# -------------------------------------------------
# TOOL SENTIMENT
# -------------------------------------------------

def _fallback_mock_sentiment(product: str) -> dict:
    all_reviews = [
        f"Je viens d'acheter {product}. Honnêtement, le meilleur achat de l'année. Super confortable et bien fini.",
        f"Avis sur {product} après 6 mois d'utilisation : la qualité est toujours excellente, aucun problème constaté.",
        f"Est-ce que {product} vaut le prix ? Je trouve que c'est un peu trop cher pour ce que c'est.",
        f"Mon {product} a cassé après 3 mois. Le service client était inutile et le remboursement refusé.",
        f"Je n'arrive pas à croire à quel point {product} est bien conçu. Je reçois des compliments à chaque utilisation.",
        f"{product} vs le concurrent principal : {product} gagne clairement sur la qualité de fabrication.",
        f"La qualité du {product} est inconsistante selon les lots. J'ai dû en retourner un avant d'en avoir un bon.",
        f"J'ai eu {product} en solde à -30%. Totalement rentable à ce prix, je le recommande vivement.",
        f"Livraison rapide, emballage soigné. Le {product} est conforme à la description. Très satisfait.",
        f"Déçu par {product}. Les photos en ligne sont trompeuses, le produit réel est moins bien.",
        f"Troisième achat de {product} pour notre famille. On ne change pas une formule gagnante !",
        f"Le {product} chauffe beaucoup après 30 minutes d'utilisation. À surveiller sur le long terme.",
        f"Rapport qualité/prix imbattable. Le {product} fait le travail sans prétention.",
        f"Attention : le {product} n'est pas compatible avec tous les accessoires annoncés. Vérifiez avant d'acheter.",
        f"J'utilise {product} tous les jours depuis 1 an, aucun signe d'usure. Excellent investissement.",
        f"Le service après-vente de {product} est top. Remplacement express sans poser de questions.",
        f"{product} reçu en cadeau. Je ne l'aurais pas acheté moi-même à ce prix, mais il est vraiment bien.",
        f"Interface du {product} un peu complexe au début, mais on s'y fait vite. Fonctionnalités complètes.",
        f"Retour produit : le {product} ne convient pas à mon usage. Trop encombrant au quotidien.",
        f"Le {product} est exactement ce que je cherchais. Simple, efficace, durable. Note parfaite.",
    ]
    return {"source": "mock", "data": all_reviews}


# -------------------------------------------------
# TOOL TRENDS
# -------------------------------------------------

def _fallback_mock_trends(product: str, market: str) -> dict:
    region = "Canada" if "canada" in market.lower() else "États-Unis"
    all_insights = [
        f"L'intérêt de recherche pour {product} est EN HAUSSE de +12% sur les 30 derniers jours au {region}.",
        f"La demande pour {product} est historiquement au pic en Q4 (oct-déc), avec un creux notable en janvier.",
        f"Le prix moyen de {product} est resté stable sur les 3 derniers mois, variation < 2%.",
        f"Recherches associées en hausse : '{product} avis', '{product} vs concurrent', '{product} promo'.",
        f"Les produits concurrents voient leur intérêt de recherche baisser de -8% vs {product}.",
        f"Le volume de recherche pour {product} a doublé par rapport à la même période l'an dernier.",
        f"Les recherches mobile représentent 68% du trafic pour {product} au {region}.",
        f"Pic saisonnier anticipé pour {product} : Black Friday et période des Fêtes sont les moments clés.",
        f"La tendance des prix pour {product} est légèrement à la BAISSE sur les 6 derniers mois (-4%).",
        f"Le marché de l'occasion pour {product} est très actif : +25% de listings sur les plateformes secondaires.",
        f"Les régions urbaines (Montréal, Toronto, Vancouver) concentrent 72% des recherches pour {product}.",
        f"Les avis négatifs pour {product} ont diminué de 15% depuis la dernière mise à jour du produit.",
        f"Comparaison internationale : {product} performe mieux au {region} qu'en Europe (+18% d'intérêt).",
        f"Les alertes de prix pour {product} ont augmenté de 34% : les consommateurs attendent une promo.",
        f"Le taux de retour pour {product} est estimé à 6%, inférieur à la moyenne de la catégorie (9%).",
        f"Les recherches '{product} bundle' et '{product} kit' sont en hausse de +40% ce trimestre.",
        f"Momentum du marché : HAUSSE — la catégorie produit de {product} est en croissance structurelle.",
        f"Les ventes de {product} en ligne représentent désormais 61% du total, vs 39% en boutique physique.",
        f"Intérêt pour '{product} reconditionné' en hausse de +55% : segment à surveiller.",
        f"Score de popularité estimé à 7.8/10 pour {product} sur le marché {region} actuel.",
    ]
    return {"source": "mock", "data": all_insights}

