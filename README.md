# Market Analysis Agent

Agent d'analyse de marché e-commerce piloté par un prompt libre.
L'agent extrait le produit et le marché, choisit ses outils, et produit un rapport stratégique.

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyse le marché canadien pour les Nike Air Max 90. Je veux savoir si c'\''est rentable de les revendre en ligne."}'
```

---

## Architecture

```
POST /analyze { "prompt": "..." }
        │
        ▼
┌─────────────────────────────────────────────────┐
│              LangGraph — Boucle ReAct            │
│                                                  │
│  node_orchestrator  ← Gemini                     │
│    │  extrait product/market depuis le prompt    │
│    │  décide quel tool appeler                   │
│    │  évalue après chaque appel                  │
│    │                                             │
│    ├──► node_scraper   (SerpApi Shopping)        │
│    │         └──► node_orchestrator              │
│    │                                             │
│    ├──► node_sentiment (SerpApi Reviews)         │
│    │         └──► node_orchestrator              │
│    │                                             │
│    ├──► node_trends    (SerpApi Trends)          │
│    │         └──► node_orchestrator              │
│    │                                             │
│    └──► node_report    (Gemini)  ──► END         │
└─────────────────────────────────────────────────┘
        │
        ▼
    JSON Report
```

**Pattern ReAct (Reason + Act) :**
À chaque tour, `node_orchestrator` raisonne sur les données disponibles
et décide quoi faire ensuite. Il boucle jusqu'à ce que les données soient
suffisantes pour répondre à la demande, puis route vers `node_report`.
Maximum `MAX_TURNS` tours (défaut : 6, configurable dans `.env`).

**Fallback automatique :** si une API est indisponible, le mock
correspondant prend le relais — la requête ne fail jamais.

**Pourquoi LangGraph ?**
LangGraph modélise l'agent comme un graphe orienté avec support natif des cycles.
Trois raisons concrètes :

1. **Support des cycles** — `add_edge(tool_node, "node_orchestrator")` crée la boucle ReAct. Sans ça, il faudrait gérer l'état manuellement entre les itérations.
2. **État partagé entre les tours** — `AgentState` accumule les données. L'orchestrateur voit ce qui a déjà été collecté et prend sa décision en connaissance de cause.
3. **Routing conditionnel lisible** — `conditional_edges("node_orchestrator", route_next)` exprime clairement que c'est l'orchestrateur qui pilote le flux.

---

## Fichiers

```
market-agent/
├── app/
│   ├── config.py        # Variables d'environnement (os.getenv + .env)
│   ├── tools.py         # Collecte données : SerpApi + mocks
│   ├── fallbacks.py     # Fonctions de fallback rule-based
│   ├── nodes.py         # Les 5 nodes LangGraph (logique métier)
│   ├── agent.py         # Câblage du graphe + run_analysis()
│   └── main.py          # API FastAPI (routes + SSE streaming)
├── test/
│   ├── test_tools.py    # Tests des outils de collecte
│   ├── test_nodes.py    # Tests des nodes individuellement
│   ├── test_pipeline.py # Tests du pipeline complet
│   └── test_api.py      # Tests des routes HTTP
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

**Séparation des responsabilités :**

| Fichier | Responsabilité |
|---|---|
| `config.py` | Lire l'environnement |
| `tools.py` | Appeler les APIs externes |
| `fallbacks.py` | Logique rule-based quand les APIs ne fonctionnent pas (Gemini et SerpAPI) |
| `nodes.py` | Logique de chaque node LangGraph |
| `agent.py` | Câblage du graphe LangGraph |
| `main.py` | Exposer l'API REST + SSE streaming |

---

## Installation

### Étape 1 — Cloner et configurer

```bash
git clone https://github.com/your-username/market-agent.git
cd market-agent
cp .env.example .env
# Remplir les clés API dans .env
```

### Étape 2 — Lancer avec Docker

S'assurer que Docker Desktop est lancé. Si non installé, télécharger sur [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop).

```bash
docker compose up --build
```

Il y a 2 manières de tester le pipeline:
1- Option 1:
Aller directement sur `http://localhost:8000` pour voir l'interface utilisateur.
2- Option 2:
Aller sur `http://localhost:8000/docs` pour tester en version backend.

### Étape 3 — Utiliser l'API

```bash
# Vérifier que le service tourne
curl http://localhost:8000/health

# Lancer une analyse avec un prompt libre
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyse le marché canadien pour les Nike Air Max 90. Je veux savoir si c'\''est rentable de les revendre en ligne."}'

# Autres exemples
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"prompt": "I want to sell iPhone 15 cases in the USA. Is the market competitive?"}'

# Dashboard HTML (SSE streaming)
open http://localhost:8000

# Documentation interactive Swagger
open http://localhost:8000/docs
```

### Sans Docker (développement local)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Tests

```bash
# Tous les tests (pas de clé API requise — fonctionne en mode mock)
python -m pytest test/ -v
```

# Par module
python -m pytest test/test_tools.py -v
python -m pytest test/test_nodes.py -v
python -m pytest test/test_pipeline.py -v
python -m pytest test/test_api.py -v
```

| Fichier | Tests | Critère couvert |
|---|---|---|
| `test_tools.py` | `test_scraper_returns_prices`<br>`test_sentiment_returns_reviews`<br>`test_trends_returns_insights` | **Fonctionnement des outils individuels** — chaque outil retourne des données non vides avec la bonne structure |
| `test_nodes.py` | `test_orchestrator_routes_to_valid_node`<br>`test_data_nodes_collect_data` | **Orchestration de l'agent** — l'orchestrateur choisit un node valide et les nodes collectent des données |
| `test_nodes.py` | `test_report_node_generates_complete_report` | **Validation des outputs** — le rapport contient les blocs requis (`executive_summary`, `market_score`, `recommendations`) |
| `test_pipeline.py` | `test_pipeline_extracts_product_and_market`<br>`test_pipeline_used_at_least_one_tool`<br>`test_pipeline_insights_are_complete` | **Orchestration end-to-end** — le graphe complet extrait le contexte, utilise au moins un outil, et produit un rapport |
| `test_api.py` | `test_health_endpoint`<br>`test_analyze_returns_report` | **Validation des outputs HTTP** — l'API retourne 200 avec un rapport valide |
| `test_api.py` | `test_invalid_prompt_rejected` | **Gestion des cas d'erreur** — prompt trop court ou manquant retourne 422 |

---

## Clés API

| Service | Utilisation | Gratuit ? | Lien |
|---|---|---|---|
| Google Gemini | Orchestration + rapport | ✅ Oui | Voir le fichier envoyé par courriel pour avoir accès à la clé |
| SerpApi | Prix + avis + tendances Google | ✅ 250 req/mois | Voir le fichier envoyé par courriel pour avoir accès à la clé |

Sans clés, tout fonctionne en mode mock avec des données simulées
qui ont la même structure que les vraies APIs.

---

## Exemple de rapport généré

```json
{
  "prompt": "Analyse le marché canadien pour les Nike Air Max 90...",
  "product": "Nike Air Max 90",
  "market": "Canada",
  "generated_at": "2026-03-16T10:00:00+00:00",
  "report_source": "gemini",
  "tools_used": ["scraper", "trends"],
  "turns": 2,
  "reasoning_log": [
    { "turn": 1, "action": "node_scraper",  "reason": "Besoin des prix actuels pour évaluer la rentabilité" },
    { "turn": 2, "action": "node_trends",   "reason": "Besoin des tendances pour évaluer le timing" },
    { "turn": 3, "action": "node_report",   "reason": "Données suffisantes pour répondre à la demande" }
  ],
  "insights": {
    "intent": "market_opportunity",
    "executive_summary": "Le marché canadien des Nike Air Max 90 est compétitif mais rentable...",
    "market_score": 7,
    "market_score_explanation": "Demande stable, marges correctes sur les éditions rares.",
    "pricing": { "min": 134.99, "max": 174.99, "average": 162.0, "recommendation": 157.14 },
    "trends": { "momentum": "rising", "popularity_score": 7, "peak_season": "Q4" },
    "opportunities": ["Éditions limitées à forte marge", "Marché revendeurs actif"],
    "risks": ["Concurrence Amazon/Foot Locker sur les prix", "Stock limité"],
    "recommendations": ["Cibler les coloris rares", "Lancer en septembre avant la peak season"]
  }
}
```

---

## Question 4 — Architecture de données

**PostgreSQL + Redis**

```sql
-- Requêtes et leur statut
CREATE TABLE analysis_requests (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt       TEXT NOT NULL,
    product      TEXT,
    market       TEXT,
    status       TEXT DEFAULT 'pending',
    turns        INTEGER,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    duration_ms  INTEGER
);

-- Rapports générés
CREATE TABLE analysis_reports (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id    UUID REFERENCES analysis_requests(id),
    report        JSONB NOT NULL,
    reasoning_log JSONB,
    tools_used    TEXT[],
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Cache des appels API
CREATE TABLE data_cache (
    cache_key  TEXT PRIMARY KEY,   -- hash(product + market + tool)
    payload    JSONB NOT NULL,
    expires_at TIMESTAMPTZ
);

-- Versions des prompts système (pour A/B testing)
CREATE TABLE prompt_configs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT UNIQUE NOT NULL,
    prompt     TEXT NOT NULL,
    version    INTEGER DEFAULT 1,
    is_active  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Pourquoi PostgreSQL ?**
`report JSONB` stocke le rapport complet sans figer le schéma — les champs `insights` varient selon l'intention détectée par Gemini. SQL reste disponible pour les agrégats (`AVG(turns)`, `COUNT(*)` par produit).

**Pourquoi Redis pour le cache ?**
SerpApi est limité à 100 req/mois en gratuit. Une clé `hash(product:market:tool)` avec TTL évite les appels redondants — même produit analysé 50 fois = 1 seul appel SerpApi.

```python
# Exemple d'implémentation dans tools.py
key = hashlib.md5(f"{product}:{market}:scraper".encode()).hexdigest()
if cached := redis.get(key):
    return json.loads(cached)
result = _serpapi_scraper(...)
redis.setex(key, ttl=3600, value=json.dumps(result))
```

---

## Question 5 — Monitoring et observabilité

**Tracing : Langfuse** (open-source, spécialisé LLM)

Chaque invocation du graphe devient une trace avec un span par node et par tour.
Le `reasoning_log` déjà présent dans chaque rapport est le point d'entrée naturel.

**Métriques clés (Prometheus + Grafana) :**

| Métrique | Type | Seuil d'alerte |
|---|---|---|
| `analysis_duration_seconds` (p95) | Histogram | > 30s |
| `orchestrator_turns_avg` | Gauge | > 2.5 tours |
| `tool_errors_total` par outil | Counter | hausse soudaine |
| `llm_tokens_used_total` | Counter | > budget/jour |
| `mock_fallback_total` | Counter | hausse = API externe en panne |

`orchestrator_turns_avg` est la métrique la plus utile : un nombre de tours élevé
signale que l'orchestrateur a du mal à décider, ce qui indique un prompt à améliorer.

**Qualité des outputs — LLM as Judge :**
Un second appel Gemini note chaque rapport sur complétude, cohérence et pertinence.
Le score est stocké dans `analysis_reports` et affiché dans Grafana.

---

## Question 6 — Scaling et optimisation

**Pour 100+ analyses simultanées**, l'API devient asynchrone :

```
POST /analyze  → retourne { job_id } immédiatement
GET  /jobs/{id} → poll pour le résultat
```

Un pool de workers Celery consomme une queue Redis.
Chaque worker fait tourner un graphe LangGraph indépendant.

**Parallélisation des outils :**
Actuellement les nodes tournent en séquence (orchestrateur → scraper → orchestrateur → ...).
En production, les 3 outils pourraient tourner en parallèle via `Send()` de LangGraph,
puis l'orchestrateur évalue les résultats combinés en un seul tour.

**Optimisation des coûts LLM :**
- `MAX_TURNS` borné (défaut 6) garantit un coût maximum par analyse
- Prompt caching Gemini pour les prompts système répétitifs
- Redis cache évite les appels SerpApi redondants

---

## Question 7 — Amélioration continue et A/B testing

**LLM as Judge :**
```python
JUDGE_PROMPT = """
Evaluate this market analysis report. Score 1-5 on:
- completeness  : does it answer the user's original question?
- coherence     : is the recommended price consistent with collected data?
- actionability : are the recommendations specific and actionable?

User's prompt: {prompt}
Report: {report}

Return ONLY JSON: {{ "completeness": N, "coherence": N, "actionability": N }}
"""
```

**A/B testing des prompts :**
Le prompt de `node_orchestrator` est versionné dans `prompt_configs`.
On assigne aléatoirement une variante à chaque requête et compare
les scores Judge + le nombre moyen de tours sur 100 analyses.
Moins de tours + meilleur score = meilleure variante.

**Feedback utilisateur :**
```
POST /feedback  { job_id, rating: 1|-1, comment: "..." }
```
Un taux de ratings négatifs > 15% sur 7 jours déclenche une révision des prompts.

**Évolution des capacités :**
- Court terme : cache des analyses précédentes par produit — l'agent enrichit les données existantes plutôt que de repartir de zéro
- Moyen terme : l'orchestrateur pose des questions de clarification avant de lancer les outils
- Long terme : fine-tuning sur les rapports bien notés pour réduire les coûts Gemini
