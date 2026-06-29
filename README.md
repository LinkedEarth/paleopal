![PaleoPAL Logo](https://github.com/LinkedEarth/Logos/blob/master/PaleoPAL/PaleoPal_rectangular_light.png?raw=true)

[![DOI](https://zenodo.org/badge/990262252.svg)](https://doi.org/10.5281/zenodo.19341100)

# PaleoPAL: An AI Assistant for Paleoclimatology

## Overview

PaleoPal is an AI-powered assistant designed to accelerate paleoclimate research by combining retrieval-augmented generation (RAG), specialized AI agents, and a comprehensive vector knowledge base derived from notebooks, research papers, and ontologies.

## PaleoPAL Core Features

- **Domain-Specific Intelligence**: PaleoPAL is designed to work with paleoclimate data and research methodologies. It understands fundamental concepts in paleoclimate science such as "proxies" and can perform context-aware analysis, including time series analysis. 
- **Multi-Agent Architecture**: Specialized agents handle different aspects of research from querying datasets on the [LiPDGraph](https://linkedearth.graphdb.mint.isi.edu), to opening datasets with [PyLiPD](https://pylipd.readthedocs.io/en/latest/), and performing time series analysis with [Pyleoclim](https://pyleoclim-util.readthedocs.io/en/latest/).
- **Knowledge-Driven**: Built on knowledge extracted from code documentation and tutorials and scientific notebooks. 
- **Transparency and Collaboration**: Real-time progress visualization, clarification dialogues, and context-aware responses ensure researchers understand and control the AI's reasoning process.

## Repository Structure

```
PaleoPAL/
├── backend/                    # FastAPI backend server
│   ├── agents/                 # Specialized AI agents
│   ├── libraries/              # RAG knowledge bases
│   │   ├── notebook_library/   # Jupyter notebook workflows & snippets. This library is automatically updated from the tutorials for the Pyleoclim and PyLiPD software and the PaleoBooks gallery. 
│   │   ├── ontology_library/   # Paleoclimate ontology indexing & search
│   │   ├── readthedocs_library/# API docs, code, and symbol indexing
│   │   └── sparql_library/     # SPARQL query templates for LiPDGraph
│   ├── routers/                # API route handlers
│   ├── schemas/                # Data models
│   ├── services/               # Business logic services
│   ├── scripts/                # Utility scripts
│   └── utils/                  # Shared utilities
├── frontend/                   # React frontend application
├── vscode-extension/           # VS Code extension for PaleoPAL
├── docs/                       # Documentation & architecture diagrams
│   ├── figures/
│   ├── gallery/
│   ├── ArchitectureDiagram.mmd
│   ├── PaleoPal_High_Level_Architecture.md
│   └── PaleoPal_Technical_Architecture.md
├── docker-compose.yml          # Docker orchestration
└── start-paleopal.sh           # Local startup script
```

## Acknowledgement

The development of PaleoPAL is supported by NSF #2425885. 