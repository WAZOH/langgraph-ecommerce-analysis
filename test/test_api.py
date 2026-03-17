"""
test_api.py — Vérifie que l'API accepte les bonnes requêtes et rejette les mauvaises.
"""

import os
import pytest

os.environ.pop("SERPAPI_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

from fastapi.testclient import TestClient
from app.main import app
from app.config import cfg

client = TestClient(app)

VALID_PROMPT = "Analyse le marche canadien pour les Nike Air Max 90. Je veux savoir si je devrais ajouter ce produit à mon site e-commerce de souliers."
SAMPLE_PRODUCT = "Nike Air Max 90"
SAMPLE_MARKET  = "Canada"

def test_health_endpoint():
    r = client.get("/health")
    # L'endpoint de santé doit répondre avec un statut 200 et un message "ok"
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_analyze_returns_report():
    data = client.post("/analyze", json={"prompt": VALID_PROMPT}).json()
    assert data["success"] is True
    assert "insights" in data["report"]


def test_invalid_prompt_rejected():
    from app.main import AnalyzeRequest
    min_len = cfg.min_prompt_length
    too_short = "x" * (min_len - 1)
    assert client.post("/analyze", json={"prompt": too_short}).status_code == 422
    assert client.post("/analyze", json={}).status_code == 422
