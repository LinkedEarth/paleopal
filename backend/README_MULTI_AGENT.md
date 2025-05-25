# Multi-Agent System for PaleoPal

## Overview

This document describes the multi-agent system architecture implemented for PaleoPal, designed to support multiple specialized agents for paleoclimate data analysis and research workflows.

## Architecture

### Core Components

1. **Base Agent Interface** (`agents/base_agent.py`)
   - Abstract base class for all agents
   - Standard request/response formats
   - Capability registration system
   - Conversation state management

2. **Agent Registry** (`services/agent_registry.py`)
   - Central registry for all agents
   - Request routing and validation
   - Capability discovery
   - Agent status monitoring

3. **Multi-Agent Router** (`routers/agents.py`)
   - FastAPI endpoints for agent interactions
   - RESTful API for agent discovery and execution
   - Integration with existing backend

### Standard Formats

#### AgentRequest
```python
{
    "agent_type": "sparql",
    "capability": "generate_query", 
    "conversation_id": "optional-uuid",
    "user_input": "Find temperature data from Antarctica",
    "context": {},
    "notebook_context": {},
    "metadata": {"llm_provider": "google"}
}
```

#### AgentResponse
```python
{
    "status": "success|needs_clarification|error|processing",
    "result": {...},
    "message": "Human-readable description",
    "conversation_id": "uuid",
    "clarification_questions": [...],
    "context_updates": {},
    "generated_code": "...",
    "execution_info": {
        "language": "sparql",
        "endpoint": "triplestore",
        "result_count": 42
    },
    "metadata": {}
}
```

## Available Agents

### SPARQL Agent (`agents/sparql_agent_v2.py`)

**Agent Type:** `sparql`

**Capabilities:**
- `generate_query`: Generate SPARQL queries from natural language

**Features:**
- Conversation state persistence
- Clarification question handling  
- Integration with existing SPARQL generation pipeline
- Support for multiple LLM providers
- **Query generation only** - execution happens in notebook with live data

### Data Analysis Agent (`agents/data_analysis_agent.py`)

**Agent Type:** `data_analysis`

**Capabilities:**
- `load_lipd_datasets`: Load LiPD datasets using PyLiPD from SPARQL-discovered names/URLs
- `execute_sparql_query`: Generate code to execute SPARQL queries via PyLiPD with GraphDB endpoint
- `create_pyleoclim_series`: Create Pyleoclim Series from SPARQL-extracted data arrays
- `analyze_timeseries`: Perform various timeseries analyses using Pyleoclim
- `create_visualizations`: Create plots and visualizations using Pyleoclim
- `multi_dataset_workflow`: Orchestrate complex workflows involving multiple datasets

**Features:**
- Seamless integration with SPARQL agent
- Code generation for [Pyleoclim](https://github.com/LinkedEarth/Pyleoclim_util) and [PyLiPD](https://github.com/LinkedEarth/pylipd)
- Support for multiple data loading strategies
- Ready-to-execute Python code generation
- Multi-dataset analysis workflows
- **Live SPARQL execution** via PyLiPD GraphDB integration

**New SPARQL Execution Capabilities:**
- `generate_code_to_load_remote_datasets`: Execute dataset discovery SPARQL queries and load remote datasets via PyLiPD
- `generate_code_to_load_timeseries`: Execute timeseries SPARQL queries and create Pyleoclim timeseries from results
- `generate_code_to_run_sparql`: Execute generic SPARQL queries and return dataframe results

## API Endpoints

### Agent Discovery

- `GET /agents/` - List all available agents
- `GET /agents/capabilities` - Get all capabilities across agents
- `GET /agents/status` - Get agent status information
- `GET /agents/{agent_type}` - Get specific agent information
- `GET /agents/{agent_type}/capabilities` - Get agent capabilities with schemas

### Agent Execution

- `POST /agents/request` - Main entry point for agent requests
- `POST /agents/{agent_type}/{capability}` - Direct capability execution
- `GET /agents/find/capability/{capability_name}` - Find agents with specific capability

### Example Usage

#### List Available Agents
```bash
curl http://localhost:8000/agents/
```

#### Execute SPARQL Query
```bash
curl -X POST http://localhost:8000/agents/request \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "sparql",
    "capability": "execute_query",
    "user_input": "PREFIX le: <http://linked.earth/ontology#> SELECT ?dataset ?name WHERE { ?dataset a le:Dataset . ?dataset le:hasName ?name . } LIMIT 5"
  }'
```

#### Generate SPARQL from Natural Language
```bash
curl -X POST http://localhost:8000/agents/sparql/generate_query \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "Find temperature data from Antarctica",
    "metadata": {"llm_provider": "google"}
  }'
```

#### Load LiPD Datasets from SPARQL Discovery
```bash
curl -X POST http://localhost:8000/agents/data_analysis/load_lipd_datasets \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "Load discovered coral datasets",
    "context": {"dataset_names": ["coral1.lpd", "coral2.lpd"]}
  }'
```

#### Create Pyleoclim Series from SPARQL Data
```bash
curl -X POST http://localhost:8000/agents/data_analysis/create_pyleoclim_series \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "Create timeseries from extracted data",
    "context": {
      "sparql_data": {
        "values": [1.2, 1.5, 0.8, 2.1],
        "ages": [1000, 1100, 1200, 1300],
        "metadata": {
          "value_name": "Temperature",
          "value_unit": "°C",
          "time_unit": "years BP"
        }
      }
    }
  }'
```

#### Execute SPARQL Queries via Data Analysis Agent
```bash
curl -X POST http://localhost:8000/agents/data_analysis/execute_sparql_query \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "PREFIX le: <http://linked.earth/ontology#> SELECT ?dataset ?name WHERE { ?dataset a le:Dataset . ?dataset le:hasName ?name . } LIMIT 5",
    "context": {}
  }'
```

#### Load Remote Datasets via SPARQL Discovery
```bash
curl -X POST http://localhost:8000/agents/data_analysis/generate_code_to_load_remote_datasets \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "PREFIX le: <http://linked.earth/ontology#> SELECT ?dataset WHERE { ?dataset a le:Dataset . ?dataset le:archiveType \"coral\" . }",
    "context": {"endpoint_url": "http://localhost:7200/repositories/paleoclimate"}
  }'
```

#### Load Timeseries Data via SPARQL
```bash
curl -X POST http://localhost:8000/agents/data_analysis/generate_code_to_load_timeseries \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "PREFIX le: <http://linked.earth/ontology#> SELECT ?age ?temperature WHERE { ?ts le:hasAge ?age . ?ts le:hasValue ?temperature . }",
    "context": {"endpoint_url": "http://localhost:7200/repositories/paleoclimate"}
  }'
```

#### Execute Generic SPARQL Query
```bash
curl -X POST http://localhost:8000/agents/data_analysis/generate_code_to_run_sparql \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "PREFIX le: <http://linked.earth/ontology#> SELECT ?dataset ?location WHERE { ?dataset le:hasLocation ?location . }",
    "context": {}
  }'
```

#### Multi-Agent Workflow Example
```