# Snippet Library Prototype

This mini-codebase lets you turn an arbitrary collection of Jupyter notebooks
into a **searchable library of code/markdown snippets**.

## Quick Start

```bash
# 1. install requirements (on a fresh venv)
pip install nbformat sentence-transformers faiss-cpu tqdm

# 2. build the index (recursive scan)
python -m snippet_library.index_notebooks path/to/notebooks --out snippet_index

# 3. query it
python -m snippet_library.search_snippets "LiPD load d18O" --index snippet_index --k 5
```

`snippet_index/` now contains:
* `snippets.faiss` – the vector index
* `snippets_meta.jsonl` – metadata for each vector (one JSON per line)

## Integrating with an LLM

```python
from snippet_library.search_snippets import search

hits = search("calculate PSD with Pyleoclim", "snippet_index", top_k=3)
for h in hits:
    print(h["code"])
```

Feed the returned code blocks into your prompt as examples.

## How it works
1. Each code cell plus its immediately preceding markdown cell (if any) is
treated as one snippet.
2. Text = `code + markdown_context` is embedded using
   [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).
3. Embeddings are stored in a FAISS inner-product index (cosine similarity).

You can swap the encoder by setting env var `SNIPPET_EMBED_MODEL` to any
Sentence-Transformers model name.

---
Feel free to adapt the extraction logic (e.g., take multi-cell blocks,
include outputs, etc.) and integrate this retrieval step in your CodeGenerationAgent. 