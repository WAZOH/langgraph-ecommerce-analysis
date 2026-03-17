"""
config.py
---------
Lit les variables d'environnement depuis le fichier .env (ou l'environnement
système). Pas de librairie externe — juste os.getenv.

Utilisation :
    from app.config import cfg
    print(cfg.gemini_api_key)
"""

import os
from dotenv import load_dotenv  # python-dotenv charge le fichier .env

# Charge le fichier .env s'il existe (en développement local).
# En production Docker, les variables sont injectées directement.
load_dotenv()


class Config:
    # --- LLM ---
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    # Modèle Gemini à utiliser (configurable via .env)
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-robotics-er-1.5-preview")

    # --- SerpApi ---
    # Clé API SerpApi pour Google Shopping + résultats organiques
    serpapi_key: str = os.getenv("SERPAPI_KEY", "")

    # --- Comportement ---
    # Nombre max de résultats SerpApi à récupérer. Par défaut 20
    max_serp_results: int = int(os.getenv("MAX_SERP_RESULTS", "20"))

    # Nombre max de tours pour l'analyse. Par défaut 6
    max_turns: int = int(os.getenv("MAX_TURNS", "6"))

    # Longueur maximale et minimale du prompt
    max_prompt_length: int = int(os.getenv("MAX_PROMPT_LENGTH", "1000"))
    min_prompt_length: int = int(os.getenv("MIN_PROMPT_LENGTH", "10"))

    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    def has_serpapi(self) -> bool:
        return bool(self.serpapi_key)


# Instance globale importable partout
cfg = Config()
