# Code Embeddings System for Paleoclimate Analysis

The Code Embeddings System enables semantic search and AI-powered code generation for paleoclimate data analysis by parsing Jupyter notebooks and creating vector embeddings of code examples.

## Overview

This system provides:
- **Semantic Search**: Find relevant code examples based on natural language queries
- **AI Code Generation**: Generate analysis code by adapting existing examples
- **Notebook Parsing**: Automatically extract code patterns from Jupyter notebooks
- **Multi-Library Support**: Covers Pyleoclim, PyLiPD, and general data analysis

## Architecture

```
User Query → Semantic Search → Relevant Examples → LLM Adaptation → Generated Code
```

1. **Code Embeddings Service** (`services/code_embeddings.py`)
   - Parses Jupyter notebooks (`.ipynb` files)
   - Creates vector embeddings using sentence-transformers
   - Stores in ChromaDB for fast semantic search

2. **Data Analysis Agent** (`agents/data_analysis_agent.py`)
   - Uses semantic search to find relevant examples
   - Adapts examples using LLM for specific user requests
   - Generates ready-to-run Python code for notebooks

## Setup and Usage

### 1. Initialize the System

```bash
# Initialize with sample examples
python scripts/initialize_code_embeddings.py
```

### 2. Add Your Notebooks

#### Option A: Manual Copy
Place your `.ipynb` files in `backend/data/notebooks/`

#### Option B: Add from External Directory
```bash
# Add single notebook
python scripts/add_notebooks.py /path/to/notebook.ipynb

# Add all notebooks from directory
python scripts/add_notebooks.py /path/to/notebooks/ --recursive

# Copy notebooks to local directory
python scripts/add_notebooks.py /path/to/notebooks/ --copy --recursive
```

### 3. Use in Multi-Agent System

```python
from agents.base_agent import AgentRequest
from services.agent_registry import agent_registry

# Generate analysis code
request = AgentRequest(
    agent_type="data_analysis",
    capability="generate_analysis_code", 
    user_input="Create a power spectral density plot for temperature data",
    context={
        "analysis_type": "spectral",
        "output_format": "notebook"
    }
)

response = await agent_registry.route_request(request)
print(response.generated_code)
```

## Notebook Format

### Structured Examples (Recommended)

Use cell tags to mark examples:

```markdown
## Power Spectral Analysis
**Description**: Compute power spectral density using various methods
**Categories**: spectral, analysis, psd
**Libraries**: pyleoclim
```
*Add tag: `example-metadata`*

```python
import pyleoclim as pyleo

# Compute power spectral density
psd = ts.spectral()
psd.plot(title='Power Spectral Density')
```
*Add tag: `example-code`*

### Auto-Detection

The system can also auto-detect patterns in untagged code cells:

- Detects libraries: `pyleoclim`, `pylipd`, `pandas`, `numpy`, `matplotlib`
- Identifies categories: `spectral`, `correlation`, `visualization`, `filtering`
- Generates metadata automatically

## Supported Analysis Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `spectral` | Frequency domain analysis | PSD, wavelets, spectrograms |
| `correlation` | Timeseries relationships | Cross-correlation, coherence |
| `visualization` | Plotting and dashboards | Time series plots, heatmaps |
| `filtering` | Data preprocessing | Low-pass, high-pass, bandpass |
| `statistics` | Statistical analysis | Significance testing, trends |
| `sparql` | Data integration | SPARQL queries, LiPD loading |
| `ensemble` | Multi-model analysis | Ensemble statistics, stacking |
| `basic` | Fundamental operations | Series creation, data loading |

## API Reference

### CodeEmbeddingsService

```python
from services.code_embeddings import code_embeddings_service

# Initialize
code_embeddings_service.initialize()

# Search examples
examples = code_embeddings_service.search_examples("spectral analysis", limit=5)

# Add notebook
code_embeddings_service.add_notebook("/path/to/notebook.ipynb")

# Load from directory
code_embeddings_service.load_notebooks_from_directory("/path/to/notebooks")

# Get statistics
stats = code_embeddings_service.get_collection_stats()
```

### Generated Code Structure

The system generates executable Python code with:

```python
# Generated Analysis Code for Spectral Analysis
# Generated using Code Embeddings Agent
# Analysis request: Create power spectral density plot

import pyleoclim as pyleo
import numpy as np

# Create or load your timeseries data
# ts = pyleo.Series(...)

# Compute power spectral density  
psd = ts.spectral()

# Create visualization
psd.plot(
    title='Power Spectral Density',
    xlabel='Frequency (1/year)',
    ylabel='Power'
)
```

## Example Workflows

### 1. Spectral Analysis Discovery

```python
# User request: "Find periodic cycles in my temperature data"

# System finds relevant examples:
# - Power spectral density computation
# - Wavelet analysis
# - Significance testing

# Generates adapted code:
# - Loads user's data
# - Applies appropriate spectral methods
# - Creates publication-ready plots
```

### 2. Multi-Proxy Comparison

```python
# User request: "Compare multiple proxy records and find correlations"

# System finds examples for:
# - Data standardization
# - Correlation analysis
# - Multi-panel visualization

# Generates workflow:
# - Loads multiple datasets
# - Standardizes to common time grid
# - Computes correlation matrix
# - Creates comparison plots
```

### 3. SPARQL Integration

```python
# User request: "Load coral datasets from GraphDB and analyze trends"

# System combines:
# - SPARQL query patterns
# - PyLiPD data loading
# - Trend analysis methods

# Generates complete workflow:
# - SPARQL query for coral data
# - Data loading and processing
# - Trend detection and visualization
```

## Data Sources for Examples

The system is designed to work with notebooks from:

- **PyleoTutorials**: Progressive analysis tutorials
- **paleoBooks**: Research-grade Jupyter notebooks  
- **Official Documentation**: Pyleoclim and PyLiPD examples
- **Community Contributions**: User-submitted analysis patterns
- **Research Workflows**: Published analysis notebooks

## Configuration

### Environment Variables

```bash
# ChromaDB storage location
CHROMA_DB_PATH="./data/chroma_db"

# Notebooks directory
NOTEBOOKS_DIR="./data/notebooks"

# Embedding model
EMBEDDING_MODEL="all-MiniLM-L6-v2"
```

### Custom Models

```python
from services.code_embeddings import CodeEmbeddingsService

# Use custom embedding model
service = CodeEmbeddingsService(embedding_provider="sentence-transformers")
service.embedding_function = SentenceTransformerEmbeddingFunction(
    model_name="all-mpnet-base-v2"  # Larger, more accurate model
)
```

## Performance and Scaling

- **Search Speed**: ~10ms for semantic search queries
- **Storage**: ~1KB per code example
- **Memory**: ~500MB for embedding model
- **Scalability**: Tested with 1000+ code examples

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   pip install sentence-transformers chromadb
   ```

2. **Collection Not Found**
   ```bash
   python scripts/initialize_code_embeddings.py
   ```

3. **No Examples Found**
   - Check notebook format and tags
   - Verify notebooks contain sufficient code content
   - Review auto-detection patterns

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Run with verbose output
code_embeddings_service.initialize()
```

## Contributing

### Adding New Categories

1. Update auto-detection patterns in `_auto_detect_example()`
2. Add category descriptions to README
3. Submit example notebooks demonstrating the category

### Improving Search

1. Test queries and relevance
2. Adjust search parameters
3. Contribute better example notebooks
4. Suggest new metadata fields

## Future Enhancements

- **Multi-language Support**: R, Julia, MATLAB notebooks
- **Advanced Patterns**: Workflow graphs, parameter tuning
- **Interactive Examples**: Widget-based tutorials
- **Version Control**: Track example evolution and updates
- **Quality Metrics**: Automated example validation 