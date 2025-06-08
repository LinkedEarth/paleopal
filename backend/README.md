# PaleoPal Backend

This directory contains the FastAPI / LangGraph **multi-agent backend** for PaleoPal.

## Key components

| Area | Path | Notes |
|------|------|-------|
| Agents | `backend/agents/` | LangGraph agents (`sparql`, `code`, `workflow_generation`, …). |
| Vector search | `backend/libraries/` | Notebook, literature, ontology & documentation indexes (all served from **Qdrant**). |
| API & routers | `backend/routers/` | HTTP endpoints exposed to the React front-end. |
| Services | `backend/services/` | Helper services (LLM provider, conversation state, search integration, …). |

## Persistence model

| Data | Storage | Table / File |
|------|---------|--------------|
| Conversation metadata | SQLite (`data/conversations.db`) | `conversations` |
| Agent state (LangGraph) | SQLite | `conversation_states` |
| Workflow plans | SQLite | `workflow_plans` |
| Vector embeddings | Qdrant (external) | multiple collections |

Legacy JSON files that used to live under `data/` (`conversations.json`, `conversation_states.json`, `workflows/workflow_plans.json`) are no longer written to and can be archived or deleted.

## Running locally

```bash
# create virtualenv and install deps
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# start Qdrant (Docker)
docker run -p 6333:6333 qdrant/qdrant

# launch API (hot-reload)
uvicorn backend.main:app --reload
```

Environment variables can be placed in `backend/.env` (see `backend/config.py` for defaults).

## Tests

```bash
pytest backend/tests
```

## Migration notes

* May 2025: switched persistence to SQLite; introduced `conversation_states` and `workflow_plans` tables.
* May 2025: all libraries migrated to Qdrant; added `qdrant-client` to requirements. 