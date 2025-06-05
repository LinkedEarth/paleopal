# Ontology Library

A semantic search library for paleoclimate ontology entities. This library indexes and provides intelligent retrieval of ontology terms, definitions, and relationships from the LinkedEarth ontology.

## Features

- **Semantic Search**: Find relevant ontology entities using natural language descriptions
- **Category Filtering**: Filter by entity categories (archive, proxy, variable, interpretation, units)
- **Synonym Matching**: Search by synonyms and alternative terminology
- **Entity Relationships**: Discover related concepts and terms
- **Multiple Entity Types**: Support for archive types, paleo variables, proxies, interpretation variables, units, and seasonality
- **CLI Interface**: Command-line tools for searching and exploring the ontology

## Installation

The library requires the following dependencies:
```bash
pip install faiss-cpu sentence-transformers
```

## Quick Start

### 1. Build the Index

First, build the search index from the ontology data:

```bash
cd backend/libraries/ontology_library
python index_ontology.py
```

### 2. Search for Entities

```python
from libraries.ontology_library.retrieve import retrieve_ontology_entities

# Find entities related to coral temperature measurements
entities = retrieve_ontology_entities("coral temperature proxy")
for e in entities:
    print(f"{e['name']}: {e['description']}")
```

### 3. Get Specific Entities

```python
from libraries.ontology_library.retrieve import get_ontology_entity

# Get detailed information about coral
coral = get_ontology_entity('Coral')
print(f"Description: {coral['description']}")
print(f"Synonyms: {coral['synonyms']}")
```

## Entity Types and Categories

The ontology contains several types of entities organized into categories:

### Archive Types (category: 'archive')
Data sources and sample types:
- **Coral**: Marine organisms used for paleoclimate reconstruction
- **Wood**: Tree rings and dendrochronology samples  
- **Lake sediment**: Sedimentary deposits from lakes
- **Glacier ice**: Ice cores from glaciers
- **Speleothem**: Cave deposits

### Paleo Variables (category: 'variable')
Measurable paleoclimate quantities:
- **temperature**: Temperature measurements and reconstructions
- **precipitation**: Rainfall and moisture variables
- **d18O**: Oxygen isotope ratios
- **Mg_Ca**: Magnesium to calcium ratios

### Paleo Proxies (category: 'proxy')
Measurement types and analytical methods:
- **Mg/Ca**: Elemental ratio measurements
- **d18O**: Isotopic measurements
- **organic matter**: Organic geochemistry

### Interpretation Variables (category: 'interpretation')
What the proxy data represents:
- **temperature**: Temperature interpretations
- **precipitation**: Precipitation interpretations
- **seasonality**: Seasonal timing information

### Units (category: 'unit')
Measurement units:
- **degC**: Degrees Celsius
- **mm**: Millimeters
- **permil**: Per mil (‰)

### Seasonality (category: 'interpretation', type: 'InterpretationSeasonality')
Temporal aspects:
- **Annual**: Year-round averages
- **Summer**: Summer season
- **DJF**: December-January-February

## API Reference

### Main Functions

#### `retrieve_ontology_entities(query, *, top_k=5, category=None, entity_type=None, namespace=None, min_score=0.3)`
Search for ontology entities using semantic similarity.

**Parameters:**
- `query` (str): Natural language description
- `top_k` (int): Maximum number of results
- `category` (str, optional): Filter by category ('archive', 'proxy', 'variable', 'interpretation', 'unit')
- `entity_type` (str, optional): Filter by specific entity type
- `namespace` (str, optional): Filter by namespace
- `min_score` (float): Minimum similarity score threshold

**Returns:** List of matching entities with metadata

#### `get_ontology_entity(entity_name, *, exact_match=True)`
Get a specific entity by name.

**Parameters:**
- `entity_name` (str): Name of the entity to find
- `exact_match` (bool): Whether to require exact name match

**Returns:** Entity metadata or None if not found

#### `find_entities_by_synonym(synonym, *, top_k=10)`
Find entities that have the given synonym.

**Returns:** List of entities with the matching synonym

### Convenience Functions

#### `find_archive_types(description="")` 
Find archive types (data sources).

#### `find_paleo_variables(description="")`
Find paleoclimate variables.

#### `find_paleo_proxies(description="")`
Find proxy measurement types.

#### `find_interpretation_variables(description="")`
Find interpretation variables.

#### `find_units(description="")`
Find measurement units.

#### `find_related_entities(entity_name, *, top_k=5)`
Find entities semantically related to a given entity.

## Command Line Interface

### Search Entities
```bash
python search_ontology.py "coral temperature"
```

### List All Entities
```bash
python search_ontology.py --list
```

### Filter by Category
```bash
python search_ontology.py "temperature" --category interpretation
```

### Get Specific Entity
```bash
python search_ontology.py --get Coral
```

### Find by Synonym
```bash
python search_ontology.py --synonym "ice cores"
```

### List Categories/Types
```bash
python search_ontology.py --categories
python search_ontology.py --entity-types
python search_ontology.py --namespaces
```

## Examples

### Example 1: Coral Temperature Reconstruction

```python
from libraries.ontology_library.retrieve import *

# Find coral archive information
coral_archives = find_archive_types("coral")
coral = coral_archives[0]
print(f"Archive: {coral['name']}")
print(f"Description: {coral['description']}")

# Find temperature variables
temp_vars = find_paleo_variables("temperature")
print(f"Temperature variable: {temp_vars[0]['name']}")

# Find relevant proxies
coral_proxies = find_paleo_proxies("coral")
for proxy in coral_proxies:
    print(f"Proxy: {proxy['name']}")

# Find temperature interpretation
temp_interp = find_interpretation_variables("temperature")
print(f"Interpretation: {temp_interp[0]['name']}")
```

### Example 2: Exploring Synonyms

```python
# Find all entities that use "SST" as a synonym
sst_entities = find_entities_by_synonym("SST")
for entity in sst_entities:
    print(f"{entity['name']} uses 'SST' to mean: {entity['matched_synonym']}")

# Search for isotope-related terms
isotope_entities = retrieve_ontology_entities("isotope analysis")
for entity in isotope_entities:
    print(f"{entity['name']}: {entity['description']}")
```

### Example 3: Category Exploration

```python
# List all archive types
archives = find_archive_types()
print("Available archive types:")
for archive in archives:
    print(f"- {archive['name']}: {archive['description']}")

# Find units for temperature
temp_units = find_units("temperature")
for unit in temp_units:
    print(f"Temperature unit: {unit['name']}")
```

## Development

### Building the Index

The index is built from the JSON data file containing ontology entities:

```bash
python index_ontology.py --data-file ontology/indexing_data.json
```

### Running the Demo

```bash
python demo.py
```

### Testing Search

```bash
# Search for entities
python search_ontology.py "coral temperature"

# List entities by category
python search_ontology.py --list --category archive

# Get entity details
python search_ontology.py --get "Coral"
```

## Data Structure

The ontology entities are stored with the following structure:

```json
{
    "id": "unique-uuid",
    "uri": "http://linked.earth/ontology/archive#Coral", 
    "name": "Coral",
    "description": "an identifiable organism that belongs to the kingdom Animalia, phylum Cnindaria.",
    "synonyms": ["coral"],
    "entity_type": "ArchiveType",
    "category": "archive",
    "namespace": "archive",
    "search_text": "Combined text for semantic search"
}
```

## File Structure

```
ontology_library/
├── __init__.py
├── README.md
├── index_ontology.py     # Build search index from JSON data
├── search_ontology.py    # Core search functionality  
├── retrieve.py          # High-level API
├── demo.py             # Usage demonstrations
├── ontology/           # Source ontology data
│   ├── indexing_data.json
│   └── ontology.ttl
└── ontology_index/     # Generated search index (after running index_ontology.py)
    ├── ontology_entities.faiss
    └── ontology_entities_meta.jsonl
```

## Integration with Paleoclimate Analysis

This library is designed to work with paleoclimate data analysis workflows:

1. **Data Discovery**: Find appropriate archive types for your research
2. **Variable Selection**: Identify relevant paleoclimate variables
3. **Proxy Understanding**: Learn about measurement techniques and proxies
4. **Interpretation Guidance**: Understand what proxy measurements represent
5. **Standardization**: Use consistent terminology and units
6. **Relationship Mapping**: Discover connections between different concepts

The semantic search capabilities make it easy to explore the ontology using natural language, while the structured categorization provides systematic access to different types of paleoclimate knowledge. 