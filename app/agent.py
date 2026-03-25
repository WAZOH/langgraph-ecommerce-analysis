"""
Assemble le graphe LangGraph avec une boucle de reflexion (ReAct).

L'orchestrateur tourne en boucle jusqu'à decider "node_report".
Max 6 tours (Paramètre MAX_TURNS configuré dans .env) pour éviter une boucle infinie.

La clé du cycle : chaque tool pointe VERS node_orchestrator (à l'exception de node_report). 
C'est node_orchestrator qui décide quand terminer.
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
    Le cerveau de l'agent, partagée et mise à jour par tous les nodes du graphe.
     - node_orchestrator lit et met à jour tous les champs

    Champs importants pour le suivi de l'analyse :
      prompt        : texte libre de l'utilisateur
      next_action   : décision de l'orchestrateur à chaque tour
      turn          : compteur de tours (protection boucle infinie)
      last_reasoning: dernière justification de l'orchestrateur
      reasoning_log : historique de toutes les décisions
    """
    prompt: str
    product: str
    market: str
    market_code: str
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

    Appelé par conditional_edges apres node_orchestrator
    ET après chaque node de collecte.

    "node_report" est la seule sortie qui ne reboucle pas vers node_orchestrator.
    """
    action = state.get("next_action", "node_report")
    log.info(f"[route_next] → {action}")

    
    # Validation simple : on accepte seulement les 4 actions possibles, sinon on termine
    if action not in ["node_scraper", "node_sentiment", "node_trends", "node_report"]:
        log.warning(f"next_action '{action}' est invalide, on retourne 'node_report' par défaut.")

    action = action if action in ["node_scraper", "node_sentiment", "node_trends", "node_report"] else "node_report"
    return action


def log_reasoning(state: AgentState) -> dict:
    """
    Node léger qui enregistre la décision de l'orchestrateur
    dans reasoning_log avant de router vers le tool.
    Permet de tracer toutes les décisions dans le rapport final.
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
    Assemble le graphe LangGraph avec les nodes et edges.
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

    # Apres l'orchestrateur : toujours log la decision, puis routing selon next_action
    graph.add_edge("node_orchestrator", "log_reasoning")
    graph.add_conditional_edges(
        "log_reasoning",
        route_next,
    )

    # Apres chaque tool : reboucle directement vers node_orchestrator
    for tool_node in ["node_scraper", "node_sentiment", "node_trends"]:
        graph.add_edge(tool_node, "node_orchestrator")

    # Sortie : node_report vers END
    graph.add_edge("node_report", END)

    return graph.compile()

_graph = build_graph()


# -------------------------------------------------
# POINT D'ENTREE PUBLIC
# -------------------------------------------------

def run_analysis(prompt: str) -> dict:
    """
    Lance le pipeline complet à partir d'un prompt libre.

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
        "market_code":    "",
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
