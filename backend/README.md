# Simplified SPARQL Agent API

This API provides a streamlined interface to the simplified SPARQL agent for the JupyterLab PaleoPal project. The simplified agent follows a more straightforward process for generating SPARQL queries than the full agent.

## Features

- **Simplified Query Generation**: Generates SPARQL queries from natural language using a 3-step process (retrieve context, generate query, refine if needed)
- **Error Resilience**: Includes robust error handling and automatic fallback to different LLM providers
- **Metadata Return**: Returns additional information like excluded conditions and assumptions made during query generation
- **Direct Query Execution**: Allows direct execution of SPARQL queries against the GraphDB endpoint

## Getting Started

### Prerequisites

- Python 3.8+
- GraphDB running with the LinkedEarth ontology loaded
- Required Python packages (see `requirements.txt`)
- API keys for LLM providers set in environment variables or `.env` file

### Starting the API

Run the API using Uvicorn:

```bash
cd /path/to/jupyterlab_paleopal
python -m uvicorn backend.app_simplified_api:app --reload
```

The API will be available at http://localhost:8000.

### Testing the API

A test script is provided to verify that the API is working correctly:

```bash
cd /path/to/jupyterlab_paleopal
python backend/test_simplified_api.py
```

## API Endpoints

### Generate a SPARQL Query

```
POST /generate
```

**Request Body:**

```json
{
  "query": "Find coral datasets with temperature measurements",
  "llm_provider": "openai"  // Optional, defaults to DEFAULT_LLM_PROVIDER in config
}
```

**Response:**

```json
{
  "sparql_query": "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> ...",
  "message": "I've generated a SPARQL query for your request: ...",
  "result_count": 15,
  "results": [...],  // Query results if available
  "excluded_conditions": ["Condition X couldn't be included because..."],
  "assumptions": ["Assumed Y because..."],
  "refinement_count": 0
}
```

### Execute a SPARQL Query

```
POST /execute
```

**Request Body:**

```json
{
  "query": "PREFIX le: <http://linked.earth/ontology#> SELECT ..."
}
```

**Response:**

```json
{
  "results": [...],  // Formatted query results
  "query": "PREFIX le: <http://linked.earth/ontology#> SELECT ..."
}
```

### Test Connection

```
GET /test-connection
```

**Response:**

```json
{
  "status": "connected",
  "endpoint": "http://localhost:7200/repositories/LiPDVerse-dynamic"
}
```

### Initialize Database

```
POST /initialize-db
```

**Response:**

```json
{
  "message": "Database initialization started in the background"
}
```

## LLM Provider Fallback

The simplified agent includes automatic fallback between different LLM providers:

1. The agent will try to use the specified provider first (or DEFAULT_LLM_PROVIDER from config)
2. If that fails, it will try OpenAI
3. If OpenAI fails, it will try Google
4. If all providers fail, it will use a fallback query

## Customization

You can customize the API by modifying these files:

- `backend/config.py`: Change default providers, API endpoints, etc.
- `backend/agent/simple_sparql_agent.py`: Modify the agent's behavior
- `backend/app_simplified_api.py`: Adjust API endpoints and behavior

## Differences from Full Agent

The simplified agent differs from the full agent in several ways:

1. **Simpler Workflow**: Uses a more streamlined process with fewer steps
2. **No Conversation History**: Each query is treated independently
3. **Built-in Results**: Returns query results directly in the response
4. **Enhanced Error Handling**: More robust fallback mechanisms
5. **Improved Entity Matching**: Uses a hybrid approach with LLM-assisted entity term extraction 