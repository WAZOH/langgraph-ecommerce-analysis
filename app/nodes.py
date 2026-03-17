"""
nodes.py
--------
Les nodes du graphe LangGraph :

  node_orchestrator  — cerveau de l'agent : extrait le contexte, decide
                       quels tools appeler, evalue apres chaque appel,
                       boucle jusqu'a satisfaction ou max_turns atteint
  node_scraper       — collecte les prix (SerpApi Shopping)
  node_sentiment     — collecte les avis Google Shopping Reviews (SerpApi)
  node_trends        — analyse tendances prix/popularite (SerpApi Trends)
  node_report        — compile le rapport final (Gemini)

Pattern ReAct dans node_orchestrator :
  Reason : Gemini analyse ce qu'il a et decide quoi faire
  Act    : appelle un tool
  Repeat : jusqu'a "sufficient" = true ou max_turns atteint
"""

import json
import logging
from datetime import datetime, timezone

import google.generativeai as genai

from app.config import cfg
from app.tools import fetch_scraper, fetch_sentiment, fetch_trends
from app.fallbacks import (
    _fallback_extract_from_prompt, _fallback_extract_market_from_prompt,
    _fallback_market_code, _fallback_rule_based_insights,
)

log = logging.getLogger(__name__)

MAX_TURNS = cfg.max_turns  # protection contre boucle infinie, configurable via .env

# -------------------------------------------------
# NODE ORCHESTRATEUR
# -------------------------------------------------

def node_orchestrator(state: dict) -> dict:
    """
    Cerveau de l'agent. Appele a chaque tour de boucle.

    Tour 1 (state["turn"] == 0) :
      - Extrait le produit et le marche depuis le prompt utilisateur
      - Decide quel premier tool appeler

    Tours suivants :
      - Evalue les donnees deja collectees (A parir de State)
      - Decide si c'est suffisant pour generer le rapport
      - Sinon, choisit le prochain tool a appeler

    Input  : state["prompt"], state["turn"], state["scraper_data"], ...
    Output : {
        "product":          str, # extrait du prompt (tour 1 seulement, lorsque turn==0)
        "market":           str, # extrait du prompt (tour 1 seulement, lorsque turn==0)
        "market_code":      str, # code ISO 3166-1 alpha-2 du pays, ex: "US", "CA", "FR" (tour 1 seulement, lorsque turn==0)
        "next_action":      str, # "node_scraper" | "node_sentiment" | "node_trends" | "node_report"
        "turn":             int, # +1 à chaque tour
        "last_reasoning":   str, # Explicitation de la decision prise à ce tour (courte phrase)
    }

    Fallback : si Gemini est indisponible, on utilise les données mock.
    """
    turn = state.get("turn", 0)
    log.info(f"[node_orchestrator] Tour {turn}/{MAX_TURNS}")

    if cfg.has_gemini():
        try:
            decision = _gemini_orchestrate(state)
            log.info(f"[node_orchestrator] Decision : {decision['next_action']} — {decision['last_reasoning']}")
            market = decision.get("market", state.get("market", ""))
            return {
                "product":          decision.get("product", state.get("product", "")),
                "market":           market,
                "market_code":        decision.get("market_code", state.get("market_code", _fallback_market_code(market))),
                "next_action":      decision["next_action"],
                "last_reasoning":   decision["last_reasoning"],
                "turn":             turn + 1,
            }
        except Exception as e:
            log.warning(f"[node_orchestrator] Gemini failed ({e}), fallback.")
            state["errors"].append(f"orchestrator_turn{turn}: {e}")

    # Fallback : plan sequentiel par defaut
    # Au tour 0, on extrait quand meme product/market du prompt
    product = state.get("product") or _fallback_extract_from_prompt(state.get("prompt", ""))
    market  = state.get("market")  or _fallback_extract_market_from_prompt(state.get("prompt", ""))
    market_code = state.get("market_code") or _fallback_market_code(market)
    fallback_plan = ["scraper", "sentiment", "trends", "report"]
    next_action = fallback_plan[min(turn, len(fallback_plan) - 1)]
    return {
        "product":        product,
        "market":         market,
        "market_code":      market_code,
        "next_action":    next_action,
        "last_reasoning": f"Fallback plan — step {turn + 1}",
        "turn":           turn + 1,
    }


def _gemini_orchestrate(state: dict) -> dict:
    """
    Prompt Gemini pour prendre la prochaine decision.

    Tour 1 : extrait product/market ET choisit le premier tool.
    Tours suivants : evalue les donnees et choisit la prochaine action.
    """
    genai.configure(api_key=cfg.gemini_api_key)
    model = genai.GenerativeModel(cfg.gemini_model)

    turn = state.get("turn", 0)
    collected = _summarize_collected(state)

    if turn == 0:
        # Premier tour : extraire le contexte + choisir le premier tool
        prompt = f"""
            You are an AI market analysis agent. A user sent this request:

            "{state['prompt']}"

            Your tasks:
            1. Extract the product name and market/country from the prompt.
            2. Understand what type of analysis the user wants.
            3. Decide which tool to call FIRST.

            Available tools:
            - "node_scraper"   : fetches current prices (always start here)
            - "node_sentiment" : fetches Google Shopping customer reviews
            - "node_trends"    : analyzes price and popularity trends over time

            IMPORTANT: Write ALL text fields (last_reasoning, etc.) in French.

            Respond with ONLY a valid JSON object:
            {{
                "product":        "<extracted product name>",
                "market":         "<English country/region name for SerpApi location, e.g. Canada, United States, France — NOT a description>",
                "market_code":      "<ISO 3166-1 alpha-2 country code, e.g. CA, US, FR, GB>",
                "next_action":    "<node_scraper|node_sentiment|node_trends>",
                "last_reasoning": "<une phrase en français : pourquoi cet outil en premier>"
            }}
        """
    else:
        # Tours suivants : evaluer et decider
        prompt = f"""
            You are an AI market analysis agent. Here is the user's original request:

            "{state['prompt']}"

            Data collected so far (turn {turn}/{MAX_TURNS}):
            {collected}

            Decide what to do next. You can:
            - Call another tool if important data is missing:
                "node_scraper"   : current prices
                "node_sentiment" : Google Shopping customer reviews
                "node_trends"    : price and popularity trends
            - Go to "node_report" if you have enough data to answer the user's question.

            Rules:
            - If turn >= {MAX_TURNS}, you MUST choose "node_report".
            - "node_sentiment" returns at most ~7 reviews — this is a platform limit, not an error. 7 reviews is sufficient for sentiment analysis; do NOT call it again.
            - "node_trends" returns at most ~5 insights — this is a platform limit, not an error. 5 insights is sufficient for trend analysis; do NOT call it again.

            IMPORTANT: Write ALL text fields (last_reasoning, etc.) in French.

            Respond with ONLY a valid JSON object:
            {{
            "next_action":    "<node_scraper|node_sentiment|node_trends|node_report>",
            "last_reasoning": "<une phrase en français : pourquoi cette action>"
            }}
        """

    response = model.generate_content(prompt)
    text = (
        response.text.strip()
        .removeprefix("```json").removeprefix("```")
        .removesuffix("```").strip()
    )
    return json.loads(text)



def _summarize_collected(state: dict) -> str:
    """
    Construit un resume textuel des donnees deja collectees pour l'orchestrateur.
    Utilisé par l'orchestrateur pour evaluer si c'est suffisant.
    """
    parts = []

    exhausted = state.get("exhausted_tools", [])
    if state.get("scraper_data", {}).get("data"):
        prices = [p["price"] for p in state["scraper_data"]["data"]]
        note = " (EXHAUSTED — do NOT call again, no more data available)" if "scraper" in exhausted else ""
        parts.append(f"- PRICES: {len(prices)} results, avg ${sum(prices)/len(prices):.2f}, "
                     f"range ${min(prices):.2f}–${max(prices):.2f}{note}")
    else:
        parts.append("- PRICES: not collected yet")

    exhausted = state.get("exhausted_tools", [])
    if state.get("sentiment_data", {}).get("data"):
        n = len(state["sentiment_data"]["data"])
        note = " (EXHAUSTED — do NOT call the same tool again, no more data available)" if "sentiment" in exhausted else ""
        parts.append(f"- REVIEWS SENTIMENT: {n} posts collected{note}")
    else:
        parts.append("- REVIEWS SENTIMENT: not collected yet")

    if state.get("trends_data", {}).get("data"):
        n = len(state["trends_data"]["data"])
        note = " (EXHAUSTED — do NOT call again, no more data available)" if "trends" in exhausted else ""
        parts.append(f"- TRENDS: {n} insights collected{note}")
    else:
        parts.append("- TRENDS: not collected yet")

    return "\n".join(parts)



# -------------------------------------------------
# HELPER
# -------------------------------------------------

def _check_exhausted(state: dict, tool_name: str, data_key: str) -> dict | None:
    """
    Si des données existent déjà pour cet outil, le marqué comme épuisé
    et retourne le dict de mise à jour. Sinon retourne None.
    """
    if not state.get(data_key, {}).get("data"):
        return None
    log.info(f"[{tool_name}] Données déjà collectées — outil marqué comme épuisé.")
    exhausted = list(state.get("exhausted_tools", []))
    if tool_name not in exhausted:
        exhausted.append(tool_name)
    return {"exhausted_tools": exhausted}


# -------------------------------------------------
# NODE SCRAPER
# -------------------------------------------------

def node_scraper(state: dict) -> dict:
    """
    Collecte les prix actuels via SerpApi Google Shopping.
    Si des données existent déjà, re-fetch avec un num plus grand et fusionne
    en dédoublonnant par (source, price).

    Input  : state["product"], state["market"]
    Output : {"scraper_data": {"source": ..., "data": [...]}}
    """
    if result := _check_exhausted(state, "scraper", "scraper_data"):
        return result

    log.info(f"[node_scraper] Produit: {state['product']} / Marche: {state['market']} / Market code: {state.get('market_code', 'CA')}")
    result = fetch_scraper(state["product"], state["market"], state.get("market_code", "CA"))
    result["data"] = result["data"][:cfg.max_serp_results]
    log.info(f"[node_scraper] {len(result['data'])} résultats collectés. Source: {result['source']}")
    return {"scraper_data": result}


# -------------------------------------------------
# NODE SENTIMENT
# -------------------------------------------------

def node_sentiment(state: dict) -> dict:
    """
    Collecte les avis Google Shopping Reviews via SerpApi.
    Si des données existent déjà, re-fetch et fusionne en dédoublonnant par texte exact.

    Input  : state["product"]
    Output : {"sentiment_data": {"source": ..., "data": [...]}}
    """
    if result := _check_exhausted(state, "sentiment", "sentiment_data"):
        return result

    log.info(f"[node_sentiment] {state['product']} / {state['market']}")
    result = fetch_sentiment(state["product"], state["market"], state.get("market_code", "CA"))
    result["data"] = result["data"][:cfg.max_serp_results]
    log.info(f"[node_sentiment] {len(result['data'])} reviews collectées. Source: {result['source']}")
    return {"sentiment_data": result}


# -------------------------------------------------
# NODE TRENDS
# -------------------------------------------------

def node_trends(state: dict) -> dict:
    """
    Analyse les tendances de prix et popularite via SerpApi Trends.
    Si des données existent déjà, re-fetch et fusionne en dédoublonnant par texte exact.

    Input  : state["product"], state["market"]
    Output : {"trends_data": {"source": ..., "data": [...]}}
    """
    if result := _check_exhausted(state, "trends", "trends_data"):
        return result

    log.info(f"[node_trends] {state['product']} / {state['market']} ({state.get('market_code', 'CA')})")
    result = fetch_trends(state["product"], state["market"], state.get("market_code", "CA"))
    log.info(f"[node_trends] {len(result['data'])} insights collectés. Source: {result['source']}")
    return {"trends_data": result}


# -------------------------------------------------
# NODE REPORT
# -------------------------------------------------

def node_report(state: dict) -> dict:
    """
    Compile toutes les donnees en un rapport strategique.
    Le rapport est adapte au prompt original de l'utilisateur.

    Si Gemini est disponible : analyse profonde + recommandations.
    Sinon : fallback rule-based sur les stats brutes.

    Input  : state["prompt"], state["scraper_data"], ...
    Output : {"report": {...}}
    """
    log.info("[node_report] Generation du rapport...")

    if cfg.has_gemini():
        try:
            insights = _gemini_insights(state)
            source = "gemini"
        except Exception as e:
            log.warning(f"Gemini a échoué avec erreur: ({e}), fallback avec rule-based.")
            state["errors"].append(f"node_report: {e}")
            insights = _fallback_rule_based_insights(state)
            source = "rule_based"
    else:
        insights = _fallback_rule_based_insights(state)
        source = "rule_based"

    report = _assemble_report(state, insights, source)
    log.info(f"[node_report] Rapport genere (source: {source})")
    return {"report": report}



def _gemini_insights(state: dict) -> dict:
    genai.configure(api_key=cfg.gemini_api_key)
    model = genai.GenerativeModel(cfg.gemini_model)
    response = model.generate_content(_build_dynamic_report_prompt(state))
    text = (
        response.text.strip()
        .removeprefix("```json").removeprefix("```")
        .removesuffix("```").strip()
    )
    return json.loads(text)


def _build_dynamic_report_prompt(state: dict) -> str:
    """
    Construit un prompt de rapport adapte dynamiquement a l'intention de l'utilisateur.

    Contrairement a _build_report_prompt qui impose une structure JSON fixe,
    cette fonction laisse Gemini determiner quelles sections sont pertinentes
    selon ce que l'utilisateur a reellement demande.

    Intentions detectees :
      - buy_decision       : l'utilisateur veut savoir s'il doit acheter
      - pricing_strategy   : l'utilisateur cherche a fixer/optimiser un prix
      - market_opportunity : l'utilisateur evalue une opportunite de marche
      - sentiment_analysis : l'utilisateur veut connaitre l'opinion de la communaute
      - competitive_analysis : l'utilisateur analyse la concurrence
      - general_analysis   : demande generique
    """
    sections = []

    if state.get("scraper_data", {}).get("data"):
        lines = "\n".join(
            f"  - {p['source']}: ${p['price']}"
            for p in state["scraper_data"]["data"]
        )
        sections.append(f"CURRENT PRICES:\n{lines}")

    if state.get("sentiment_data", {}).get("data"):
        lines = "\n".join(
            f"  - {post[:250]}" # On affiche juste les 250 premiers caractères de chaque review
            for post in state["sentiment_data"]["data"][:10] # On limite à 10 reviews pour le prompt
        )
        sections.append(f"REVIEWS SENTIMENT ({len(state['sentiment_data']['data'])} posts):\n{lines}")

    if state.get("trends_data", {}).get("data"):
        lines = "\n".join(f"  - {i}" for i in state["trends_data"]["data"])
        sections.append(f"MARKET TRENDS:\n{lines}")

    data_block = "\n\n".join(sections) if sections else "No data collected."

    return f"""
        You are a senior e-commerce market analyst.

        The user's original request was:
        "{state.get('prompt', '')}"

        Product : {state.get('product', 'unknown')}
        Market  : {state.get('market', 'unknown')}

        Data collected:
        {data_block}

        Step 1 — Identify the user's primary intent among:
          "buy_decision"         (should I buy / is it worth it?)
          "pricing_strategy"     (how should I price it / is the price fair?)
          "market_opportunity"   (is there a business opportunity here?)
          "sentiment_analysis"   (what do people think / community opinions?)
          "competitive_analysis" (who are the competitors / market share?)
          "general_analysis"     (general market overview)

        Step 2 — Generate a strategic report tailored to that intent.

        Rules for sections:
          ALWAYS include:
            "intent"                  : the identified intent string
            "executive_summary"       : 2-3 sentences directly answering the user's question
            "market_score"            : integer 1-10
            "market_score_explanation": why this score

          Include "pricing" when intent is buy_decision or pricing_strategy:
            {{"min": float, "max": float, "average": float,
              "recommendation": float, "recommendation_reason": string}}

          Include "sentiment" when intent is buy_decision or sentiment_analysis:
            {{"NPS": int 0-10, "label": "negative|neutral|positive",
              "positives": [string, ...], "negatives": [string, ...]}}

          Include "competitive_analysis" when intent is market_opportunity or competitive_analysis:
            {{"key_players": [string, ...], "market_share": {{player: float%, ...}}}}

          Include "trends" when intent is market_opportunity or pricing_strategy:
            {{"popularity_score": int 0-10, "popularity_explanation": string,
              "momentum": "rising|stable|declining",
              "peak_season": string, "price_evolution": "rising|stable|falling"}}

          Include "opportunities" and "risks" when intent is market_opportunity or general_analysis:
            [string, ...]

          ALWAYS include "recommendations": 2-4 actionable items tailored to the user's intent.

        IMPORTANT: Write ALL text fields (executive_summary, market_score_explanation,
        recommendation_reason, popularity_explanation, peak_season, opportunities, risks,
        recommendations, positives, negatives, etc.) in French.

        Respond with ONLY a valid JSON object. No markdown, no backticks.
    """


def _assemble_report(state: dict, insights: dict, source: str) -> dict:
    # Reconstruit le journal des decisions de l'orchestrateur
    tools_used = []
    if state.get("scraper_data",   {}).get("data"): tools_used.append("scraper")
    if state.get("sentiment_data", {}).get("data"): tools_used.append("sentiment")
    if state.get("trends_data",    {}).get("data"): tools_used.append("trends")

    return {
        "prompt":        state.get("prompt", ""),
        "product":       state.get("product", ""),
        "market":        state.get("market", ""),
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "report_source": source,
        "tools_used":    tools_used,
        "turns":         state.get("turn", 0),
        "reasoning_log": state.get("reasoning_log", []),
        "data_sources": {
            "scraper":   state.get("scraper_data",   {}).get("source", "None"),
            "sentiment": state.get("sentiment_data", {}).get("source", "None"),
            "trends":    state.get("trends_data",    {}).get("source", "None"),
        },
        "data_raw": {
            "prices":       state.get("scraper_data",   {}).get("data", []),
            "reviews": state.get("sentiment_data", {}).get("data", [])[:5],
            "trends":       state.get("trends_data",    {}).get("data", []),
        },
        "insights": insights,
        "errors":   state["errors"],
    }
