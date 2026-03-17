"""
main.py
-------
Point d'entree de l'API REST (FastAPI).

Routes :
  GET  /health   -> verifie que le service tourne
  POST /analyze  -> lance une analyse a partir d'un prompt libre
  GET  /         -> infos de base

Exemple de prompt :
  "Analyse le marche canadien pour les ecouteurs Sony WH-1000XM5.
   Je veux savoir si c'est le bon moment pour lancer une boutique Shopify."
"""

import json
import logging
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agent import run_analysis
from app.config import cfg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


# -------------------------------------------------
# SCHEMAS
# -------------------------------------------------

class AnalyzeRequest(BaseModel):
    """Corps de la requete POST /analyze."""
    prompt: str = Field(
        ...,
        min_length=cfg.min_prompt_length,
        max_length=cfg.max_prompt_length,
        description="Demande libre de l'utilisateur",
        examples=[
            "Analyse le marche canadien pour les ecouteurs Sony WH-1000XM5. "
            "Je veux savoir si c'est le bon moment pour lancer une boutique Shopify."
        ],
    )


class AnalyzeResponse(BaseModel):
    success:          bool
    duration_seconds: float
    report:           dict


class HealthResponse(BaseModel):
    status:      str
    has_gemini:  bool
    has_serpapi: bool


# -------------------------------------------------
# APP
# -------------------------------------------------

app = FastAPI(
    title="Market Analysis Agent",
    description=(
        "Agent d'analyse de marche e-commerce. "
        "Envoie un prompt libre, l'agent detecte le produit et le marche, "
        "choisit les outils necessaires, et produit un rapport strategique."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------
# ROUTES
# -------------------------------------------------

@app.get("/", tags=["System"])
def root():
    # index.html se retrouve dans au root du projet (et non dans /app)
    return FileResponse(BASE_DIR / "index.html")


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    return HealthResponse(
        status="ok",
        has_gemini=cfg.has_gemini(),
        has_serpapi=cfg.has_serpapi(),
    )


@app.post("/analyze/stream", tags=["Analysis"])
def analyze_stream(request: AnalyzeRequest):
    """
    Lance une analyse avec streaming SSE — chaque node LangGraph emet un event.
    Utiliser avec fetch + ReadableStream (EventSource ne supporte pas POST).
    """
    log.info(f"POST /analyze/stream — prompt='{request.prompt[:80]}...'")

    def event_generator():
        from app.agent import _graph

        initial_state = {
            "prompt":         request.prompt,
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

        try:
            yield f"data: {json.dumps({'type': 'start'})}\n\n"

            for chunk in _graph.stream(initial_state):
                for node_name, state_update in chunk.items():
                    event = {"type": "node", "node": node_name}

                    if node_name == "node_orchestrator":
                        event["product"]     = state_update.get("product", "")
                        event["market"]      = state_update.get("market", "")
                        event["market_code"] = state_update.get("market_code", "")
                        event["next_action"] = state_update.get("next_action", "")
                        event["reasoning"]   = state_update.get("last_reasoning", "")
                        event["turn"]        = state_update.get("turn", 0)
                    elif node_name == "node_scraper":
                        d = state_update.get("scraper_data", {})
                        event["count"]  = len(d.get("data", []))
                        event["source"] = d.get("source", "")
                    elif node_name == "node_sentiment":
                        d = state_update.get("sentiment_data", {})
                        event["count"]  = len(d.get("data", []))
                        event["source"] = d.get("source", "")
                    elif node_name == "node_trends":
                        d = state_update.get("trends_data", {})
                        event["count"]  = len(d.get("data", []))
                        event["source"] = d.get("source", "")
                    elif node_name == "node_report":
                        report = state_update.get("report", {})
                        yield f"data: {json.dumps({'type': 'node', 'node': 'node_report', 'source': report.get('report_source', ''), 'tools_used': report.get('tools_used', []), 'steps': len(report.get('reasoning_log', []))})}\n\n"
                        yield f"data: {json.dumps({'type': 'complete', 'report': report})}\n\n"
                        return

                    yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            log.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


@app.post("/analyze", response_model=AnalyzeResponse, tags=["Analysis"])
def analyze(request: AnalyzeRequest):
    """
    Lance une analyse de marche complete a partir d'un prompt libre.

    L'agent va :
      1. Extraire le produit et le marche depuis le prompt
      2. Decider quels outils sont necessaires selon la demande
      3. Appeler les outils un par un, evaluer apres chaque appel
      4. Generer un rapport strategique adapte a la demande
    """
    log.info(f"POST /analyze — prompt='{request.prompt[:80]}...'")
    start = time.perf_counter()

    try:
        report = run_analysis(prompt=request.prompt)
    except Exception as e:
        log.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    duration = round(time.perf_counter() - start, 2)
    log.info(f"Analysis done in {duration}s")

    return AnalyzeResponse(
        success=True,
        duration_seconds=duration,
        report=report,
    )
