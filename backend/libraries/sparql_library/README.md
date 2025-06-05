# SPARQL Library

A semantic search library for SPARQL queries used in paleoclimate data analysis. This library indexes and provides intelligent retrieval of SPARQL query templates from documentation.

## Features

- **Semantic Search**: Find relevant SPARQL queries using natural language descriptions
- **Parameter Substitution**: Automatically substitute parameters in query templates
- **Category Filtering**: Filter queries by type (dataset, filter, variable, etc.)
- **Query Templates**: Access structured query information with parameter metadata
- **CLI Interface**: Command-line tools for searching and managing queries

## Installation

The library requires the following dependencies:
```bash
pip install faiss-cpu sentence-transformers
```

## Quick Start

### 1. Build the Index

First, build the search index from the SPARQL query documentation:

```bash
cd backend/libraries/sparql_library
python index_queries.py
```

### 2. Search for Queries

```python
from libraries.sparql_library.retrieve import retrieve_sparql_queries

# Find queries related to geographic filtering
queries = retrieve_sparql_queries("filter datasets by location")
for q in queries:
    print(f"{q['name']}: {q['description']}")
```

### 3. Get Specific Queries with Parameters

```python
from libraries.sparql_library.retrieve import get_sparql_query

# Get a geographic filter query with specific coordinates
query = get_sparql_query('QUERY_FILTER_GEO', {
    'latMin': '40.0',
    'latMax': '50.0',
    'lonMin': '-120.0',
    'lonMax': '-110.0'
})
print(query)
```

## API Reference

### Main Functions

#### `retrieve_sparql_queries(query, *, top_k=3, category=None, min_score=0.3)`
Search for SPARQL queries using semantic similarity.

**Parameters:**
- `query` (str): Natural language description
- `top_k` (int): Maximum number of results
- `category` (str, optional): Filter by category ('filter', 'dataset', 'variable', etc.)
- `min_score` (float): Minimum similarity score threshold

**Returns:** List of matching queries with metadata

#### `get_sparql_query(query_name, *, parameters=None)`
Get a specific query by name with optional parameter substitution.

**Parameters:**
- `query_name` (str): Exact query name (e.g., 'QUERY_DSNAME')
- `parameters` (dict, optional): Parameter values to substitute

**Returns:** SPARQL query string or None if not found

#### `list_query_categories()`
Get all available query categories.

**Returns:** List of category names

#### `get_query_template(query_name)`
Get detailed information about a query including parameters.

**Returns:** Dictionary with query metadata 