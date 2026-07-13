# Notebook Library

Hierarchical indexing of Jupyter notebooks under `my_notebooks/` into **Qdrant**:

| Collection | Role |
|---|---|
| `notebook_summaries` | Parent docs (notebook + project summaries) |
| `notebook_snippets` | Child docs (code + comments + section markdown; **no outputs**) |
| `notebook_workflows` | LLM/heuristic workflows (notebook- and project-level) |

Parent-child retrieval: search summaries to select notebooks/projects, then expand to linked children.

---

## Prerequisites

```bash
cd backend/libraries
# Activate your paleopal env
# Qdrant must be running (default localhost:6333)
export QDRANT_HOST=localhost
export QDRANT_PORT=6333

# Optional embedding overrides
# export EMBED_MODEL=all-MiniLM-L6-v2
# export MODEL_CACHE_DIR=/path/to/backend/models_cache
```

For `--llm` indexing / agent `--generate` tests, set the matching API key (`OPENAI_API_KEY`, `XAI_API_KEY`, …).

---

## 1. Preview extraction (no Qdrant writes)

Inspect what would be indexed before writing vectors.

```bash
cd backend/libraries

# Built-in samples: tutorial | paleobook-single | paleobook-project | mixed
python notebook_library/preview_extraction.py --sample mixed --out /tmp/nb_preview.json

# Specific paths
python notebook_library/preview_extraction.py notebook_library/my_notebooks/pyleoclim_tutorials

# With LLM summaries + workflows (needs API key)
python notebook_library/preview_extraction.py --sample paleobook-project --llm openai --out /tmp/nb_llm.json
```

**Flags**

| Flag | Meaning |
|---|---|
| `--sample …` | Use a built-in notebook set |
| `--llm openai\|grok` | LLM summary + workflow extraction |
| `--out PATH` | Write full JSON report |
| `--max-sections N` | Truncate section preview size (default 8) |
| `--quiet` | JSON only |

---

## 2. Index notebooks → Qdrant

```bash
cd backend/libraries

# Heuristic-only (fast)
python notebook_library/index_notebooks.py --keep-invalid --force-recreate \
  notebook_library/my_notebooks

# With LLM enrichment (slow first time; uses disk cache afterward)
python notebook_library/index_notebooks.py --keep-invalid --force-recreate --llm openai \
  notebook_library/my_notebooks
```

**Flags**

| Flag | Meaning |
|---|---|
| `--force-recreate` | Drop/recreate collections |
| `--keep-invalid` | Keep snippets with unresolved names |
| `--llm openai\|grok` | Summaries + workflows via LLM |
| `--llm-cache-dir PATH` | Cache directory (default: `notebook_library/.llm_cache`) |
| `--no-llm-cache` | Always call the API |
| `--bootstrap-llm-cache` | Seed cache from existing Qdrant LLM payloads, then exit |
| `--out PREFIX` | Optional collection name prefix |
| `--no-hoist-imports` / `--no-synth-imports` | Compat no-ops |

**What indexing does**

- Skips `_build/`, `.virtual_documents`, checkpoints, etc.
- Expands CFR-style projects (`data_assembly` / `data_assimilation` / `validation`) into combined project parents
- Joins `_metadata/notebooks.json` provenance when paths match
- Prints `LLM cache: hits=… misses=… writes=…` at the end

Full library rebuild (includes notebooks):

```bash
bash index_everything.sh
```

---

## 3. LLM cache

Default path: **`notebook_library/.llm_cache/`** (gitignored).

```bash
# After a successful --llm index: seed cache from Qdrant (no API calls)
python notebook_library/index_notebooks.py --bootstrap-llm-cache --llm openai

# Custom location
export NOTEBOOK_LLM_CACHE_DIR=/path/to/cache
# or: --llm-cache-dir /path/to/cache
```

Cache keys include provider + model + notebook content hash. Changing model/prompts → new misses until refilled.

---

## 4. Search / retrieve

```bash
cd backend/libraries

# Child snippets (include parent_summary in payload)
python notebook_library/search_snippets.py "load LiPD from URL" --type snippets -k 5

# Parent summaries
python notebook_library/search_snippets.py "data assimilation GMST" --type summaries -k 5

# Parent → child expand
python notebook_library/search_snippets.py "PAGES2k proxy database" --type parent-child -k 3

# Workflows
python notebook_library/search_snippets.py "validate reconstruction" --type workflows -k 5
# or:
python notebook_library/search_workflows.py "validate reconstruction" -k 5
```

High-level API wrapper:

```bash
python notebook_library/retrieve.py "spectral analysis pyleoclim" --type parent-child -k 3
```

**Types:** `snippets` | `summaries` | `workflows` | `parent-child` | `steps` (legacy alias → snippets)

Use **`-k` or `--k`** for result count.

---

## 5. Agent context tests

These print **retrieved payloads**, the **formatted context string** sent to the LLM, and optionally the **agent response**.

Run from **`backend/`** (not `libraries/`):

```bash
cd backend

# --- Code agent ---
python -m agents.code.test_code_agent_context \
  "Load a LiPD dataset from a URL using PyLiPD" -k 3 \
  --out /tmp/code_agent_context.json

python -m agents.code.test_code_agent_context \
  "Load a LiPD dataset from a URL using PyLiPD" -k 2 --generate \
  --out /tmp/code_agent_generate.json

# --- Workflow agent ---
python -m agents.workflow.test_workflow_agent_context \
  "Assemble PAGES2k proxies, run data assimilation, validate GMST" -k 3 \
  --out /tmp/workflow_agent_context.json

python -m agents.workflow.test_workflow_agent_context \
  "Assemble PAGES2k proxies, run DA, validate GMST" --generate \
  --out /tmp/workflow_agent_generate.json

# --- SPARQL agent ---
python -m agents.sparql.test_sparql_agent_context \
  "Find coral d18O records from the tropical Pacific" -k 3 \
  --no-term-extraction \
  --out /tmp/sparql_agent_context.json

python -m agents.sparql.test_sparql_agent_context \
  "Find coral d18O records from the tropical Pacific" --generate \
  --out /tmp/sparql_agent_generate.json
```

**Shared flags**

| Flag | Meaning |
|---|---|
| `-k` / `--k` | Retrieval depth |
| `--generate` | Call the agent’s generate node |
| `--provider` | LLM provider (default `openai`) |
| `--model` | Optional model override |
| `--out PATH` | JSON report |
| `--quiet` | JSON only |

SPARQL-only: `--no-term-extraction` skips LLM ontology term extraction (faster context-only runs).  
Code-only: `--two-step` enables the production 2-step symbol-planning path.

Tests prefer `backend/models_cache/all-MiniLM-L6-v2` when present (offline embeddings).

---

## Architecture (short)

```
Notebook / Project summary  ──search──►  select parents
         │
         └── children (snippets) + workflows  ──expand──►  LLM context
```

- **Code agent** → parent-child snippets (+ RTD docs/examples)  
- **Workflow agent** → notebook summaries + workflows  
- **SPARQL agent** → similar SPARQL queries + ontology entities  

Cell **outputs are never indexed**.

---

## Related docs

- Broader library indexing (SPARQL, ontology, RTD, literature): [`../README.md`](../README.md)
- Notebook corpus sync: `scripts/update_notebooks.py` + `notebook_manifest.yml`
