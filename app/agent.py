"""
agent.py
--------
Assemble le graphe LangGraph avec une boucle de reflexion (ReAct).

Flux :
    START
      |
      v
  node_orchestrator  <- Gemini extrait product/market, choisit le 1er tool
      |
      | route_next() : lit state["next_action"]
      |
      +---> node_scraper    -> retour a node_orchestrator
      +---> node_sentiment  -> retour a node_orchestrator
      +---> node_trends     -> retour a node_orchestrator
      +---> node_report     -> END

L'orchestrateur tourne en boucle jusqu'à decider "node_report".
Max 6 tours (= max 2 tours par 3 tools) pour eviter une boucle infinie.

La cle du cycle : chaque tool pointe VERS node_orchestrator,
pas vers node_report. C'est node_orchestrator qui decide
quand terminer.
"""

import logging
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from app.nodes import (
    node_orchestrator,
    node_scraper,
    node_sentiment,
    node_trends,
    node_report,
)

log = logging.getLogger(__name__)


# -------------------------------------------------
# ETAT PARTAGE
# -------------------------------------------------

class AgentState(TypedDict):
    """
    Dict partage entre tous les nodes LangGraph.

    Nouveaux champs vs version precedente :
      prompt        : texte libre de l'utilisateur
      next_action   : decision de l'orchestrateur a chaque tour
      turn          : compteur de tours (protection boucle infinie)
      last_reasoning     : derniere justification de l'orchestrateur
      reasoning_log : historique de toutes les decisions
    """
    prompt: str
    product: str
    market: str
    next_action: str
    turn: int
    last_reasoning: str
    reasoning_log: list
    scraper_data: dict
    sentiment_data: dict
    trends_data: dict
    report: dict
    errors: list
    exhausted_tools: list  # outils qui ne peuvent plus retourner de nouvelles données


# -------------------------------------------------
# ROUTING
# -------------------------------------------------

def route_next(state: AgentState) -> str:
    """
    Lit state["next_action"] et retourne le nom du node suivant.

    Appele par conditional_edges apres node_orchestrator
    ET apres chaque node de collecte.

    "node_report" est la seule sortie qui ne reboucle pas
    vers node_orchestrator.
    """
    action = state.get("next_action", "node_report")
    log.info(f"[route_next] → {action}")

    # mapping = {
    #     "scraper":   "node_scraper",
    #     "sentiment": "node_sentiment",
    #     "trends":    "node_trends",
    #     "report":    "node_report",
    # }
    # return mapping.get(action, "node_report")
    
    # Validation simple : on accepte seulement les 4 actions possibles, sinon on termine
    if action not in ["node_scraper", "node_sentiment", "node_trends", "node_report"]:
        log.warning(f"next_action '{action}' est invalide, on retourne 'node_report' par défaut.")

    action = action if action in ["node_scraper", "node_sentiment", "node_trends", "node_report"] else "node_report"
    return action


def log_reasoning(state: AgentState) -> dict:
    """
    Node leger qui enregistre la decision de l'orchestrateur
    dans reasoning_log avant de router vers le tool.
    Permet de tracer toutes les decisions dans le rapport final.
    """
    log_entry = {
        "turn":   state.get("turn", 0),
        "action": state.get("next_action", ""),
        "reason": state.get("last_reasoning", ""),
    }
    current_log = state.get("reasoning_log", [])
    return {"reasoning_log": current_log + [log_entry]}


# -------------------------------------------------
# CONSTRUCTION DU GRAPHE
# -------------------------------------------------

def build_graph():
    """
    Construit le graphe avec cycle :

        START
            |
      node_orchestrator
            |
      (conditional) route_next <--------
            |                           |
      +-----+------+-------+            |
      |     |      |       |            |
    scraper sent  trends report         |
      |     |      |       |            |
      +-----+------+       END          |
            |                           |
      log_reasoning     --------------- |
    """
    graph = StateGraph(AgentState)

    # Enregistrement des nodes
    graph.add_node("node_orchestrator", node_orchestrator)
    graph.add_node("log_reasoning", log_reasoning)
    graph.add_node("node_scraper", node_scraper)
    graph.add_node("node_sentiment", node_sentiment)
    graph.add_node("node_trends", node_trends)
    graph.add_node("node_report", node_report)

    # Entree : toujours par l'orchestrateur
    graph.add_edge(START, "node_orchestrator")

    # Apres l'orchestrateur : routing selon next_action
    graph.add_conditional_edges(
        "node_orchestrator",
        route_next,
    )

    # Apres chaque tool : on log la decision puis on reboucle vers node_orchestrator pour la prochaine decision
    for tool_node in ["node_scraper", "node_sentiment", "node_trends"]:
        graph.add_edge(tool_node, "log_reasoning")

    graph.add_edge("log_reasoning", "node_orchestrator")

    # Sortie : node_report vers END
    graph.add_edge("node_report", END)

    return graph.compile()

_graph = build_graph()


# -------------------------------------------------
# POINT D'ENTREE PUBLIC
# -------------------------------------------------

def run_analysis(prompt: str) -> dict:
    """
    Lance le pipeline complet a partir d'un prompt libre.

    Exemple :
        report = run_analysis(
            "Analyse le marche canadien pour les Nike Air Max 90. "
            "Je veux savoir si c'est rentable de les revendre en ligne."
        )
    """
    log.info(f"run_analysis: prompt='{prompt[:80]}...'")

    initial_state: AgentState = {
        "prompt":         prompt,
        "product":        "",
        "market":         "",
        "next_action":    "",
        "turn":           0,
        "last_reasoning": "",
        "reasoning_log":  [],
        "scraper_data":   {},
        "sentiment_data": {},
        "trends_data":    {},
        "report":           {},
        "errors":           [],
        "exhausted_tools":  [],
    }

    final_state = _graph.invoke(initial_state)
    return final_state["report"]
