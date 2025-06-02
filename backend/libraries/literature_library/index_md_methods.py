from __future__ import annotations

"""literature_library.index_md_methods

Scan a folder of markdown files (e.g. paleoclimatology/papers-text.md/*.md) and index the method section (using LLM extraction if LLM_ENGINE is set) and summarize it into bullet points. Reuses the same FAISS index (methods.faiss) and metadata (methods_meta.jsonl) as index_methods.py.
"""

import json
import logging
import os
import pathlib
import re
from functools import lru_cache
from typing import List, Dict, Any

import faiss  # type: ignore
import numpy as np

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError as e:  # pragma: no cover
    raise ImportError("sentence-transformers is required: pip install sentence-transformers") from e

try:
    from transformers import pipeline  # type: ignore
except ImportError as e:  # pragma: no cover
    raise ImportError("transformers is required (pip install transformers) for HF summarizer") from e

LOG = logging.getLogger("lit-index-md")
logging.basicConfig(level=logging.INFO)

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

# ----------------------------------------------------
# LLM-based extraction (reused from index_methods.py)
# ----------------------------------------------------

def _call_openai(prompt: str, model: str = "gpt-4o", max_tokens: int = 512) -> str:
    """Call OpenAI chat completion API compatible with both <1.0 and >=1.0 SDKs."""
    try:
        import openai  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise ImportError("openai package is required for --llm openai") from e

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    messages = [
        {"role": "system", "content": "You are an expert scientific methods extractor. Return ONLY a numbered list of concise procedural steps."},
        {"role": "user", "content": prompt},
    ]

    # Detect SDK version
    if hasattr(openai, "OpenAI"):  # >=1.0.0
        client = openai.OpenAI()
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,
        )
        return resp.choices[0].message.content.strip()  # type: ignore
    else:  # 0.x series
        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,
        )
        try:
            return resp.choices[0].message["content"].strip()  # type: ignore
        except Exception:
            # Some 0.x versions expose .choices[0].message.content
            return resp.choices[0].message.content.strip()  # type: ignore


def _call_ollama(prompt: str, model: str = "deepseek-r1") -> str:
    import requests, uuid, json as _json

    req = {"model": model, "prompt": prompt, "stream": False}
    try:
        resp = requests.post("http://localhost:11434/api/generate", json=req, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except Exception as e:
        raise RuntimeError(f"Ollama request failed: {e}")


def _summarise_with_llm(raw_text: str, engine: str, max_steps: int = 12) -> List[str]:
    """LLM-based extraction (engine = 'openai' or 'ollama'). Returns list of steps or empty list."""
    if engine == "none":
        return []

    # Split into manageable chunks (~3500 chars) and summarise each, then combine.
    chunks: List[str] = []
    current = []
    char_limit = 3500
    for sentence in re.split(r"(?<=[.!?])\s+", raw_text):
        current.append(sentence)
        if sum(len(s) for s in current) > char_limit:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))

    partial_summaries: List[str] = []
    for ch in chunks:
        prompt = (
            "Extract the procedural steps described in the following scientific methods/procedure text. "
            "Return ONLY a numbered list of concise steps.\n\n" + ch[:3800]
        )
        try:
            if engine == "openai":
                resp = _call_openai(prompt)
            elif engine == "ollama":
                resp = _call_ollama(prompt)
            else:
                return []
            partial_summaries.append(resp)
        except Exception as e:
            LOG.warning("LLM summarisation failed on chunk: %s", e)
            continue

    if not partial_summaries:
        return []

    combined_prompt = (
        "Merge and deduplicate the following numbered step lists into a single numbered list of up to "
        f"{max_steps} key steps. Make each step imperative, concise, and self-contained."\
    )
    combined_prompt += "\n\n" + "\n".join(partial_summaries)

    try:
        if engine == "openai":
            final_resp = _call_openai(combined_prompt)
        elif engine == "ollama":
            final_resp = _call_ollama(combined_prompt)
        else:
            return []
    except Exception as e:
        LOG.warning("LLM merge summarisation failed: %s", e)
        return []

    # Parse numbered lines
    steps: List[str] = []
    for line in final_resp.splitlines():
        m = re.match(r"^\s*\d+\.\s+(.*\S)", line)
        if m:
            steps.append(m.group(1).strip())
        elif line.strip() and not steps:
            steps.append(line.strip())
    return steps[:max_steps]


# ----------------------------------------------------
# HF summarizer (reused from index_methods.py)
# ----------------------------------------------------

SUMM_MODEL = os.getenv("METHODS_SUMM_MODEL", "facebook/bart-large-cnn")

@lru_cache(maxsize=1)
def _get_summarizer():
    """Return a transformers summarization pipeline or None if fails."""
    try:
        return pipeline("summarization", model=SUMM_MODEL, device=-1)
    except Exception as e:
        LOG.warning("Failed to load summarization model %s: %s. Falling back to heuristic summariser.", SUMM_MODEL, e)
        return None


def _summarise_with_hf(text: str, max_steps: int = 10) -> List[str]:
    """Use HF summarization pipeline to convert text to steps list."""
    summariser = _get_summarizer()
    if summariser is None:
        return []

    # Truncate to model limit (~1024 tokens ~ 4000 chars). We'll use 3500 chars per chunk.
    chunks: List[str] = []
    current = []
    char_limit = 3500
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        current.append(sentence)
        if sum(len(s) for s in current) > char_limit:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))

    summary_parts: List[str] = []
    for ch in chunks:
        try:
            res = summariser(  # type: ignore
                ch,
                max_length=256,
                min_length=30,
                do_sample=False,
                truncation=True,
            )
            summary_parts.append(res[0]["summary_text"].strip())
        except Exception as e:
            LOG.debug("Summariser failed on chunk: %s", e)
            continue

    if not summary_parts:
        return []

    combined = " ".join(summary_parts)

    # Split combined summary into numbered steps if present
    step_lines: List[str] = []
    for line in combined.splitlines():
        line = line.strip()
        m = re.match(r"^(?:\d+\.|-\s|•\s)?\s*(.+)$", line)
        if m and m.group(1):
            step_lines.append(m.group(1).strip())
    if not step_lines:
        step_lines = [combined]

    return step_lines[:max_steps]


# ----------------------------------------------------
# Summarise (bullet, LLM, HF, heuristic) (reused from index_methods.py)
# ----------------------------------------------------

_BULLET_RE = re.compile(r"^\s*(?:[-\u2022]|\d+\.)\s+(.*\S)")

def summarise_to_steps(raw_text: str, max_steps: int = 12, llm_engine: str = "none") -> List[str]:
    """Return a list of procedural steps using bullets, LLM, HF summariser, or heuristics."""
    # 1. If LLM engine is specified, use it directly and skip slower local routines
    if llm_engine != "none":
        llm_steps = _summarise_with_llm(raw_text, engine=llm_engine, max_steps=max_steps)
        if llm_steps:
            return llm_steps

    # 2. Lightweight bullet-list detection (fast)
    lines = raw_text.splitlines()
    bullet_steps: List[str] = []
    for ln in lines:
        m = _BULLET_RE.match(ln)
        if m:
            bullet_steps.append(m.group(1).strip())
    if len(bullet_steps) >= 3:
        return bullet_steps[:max_steps]

    # 3. Optional HF summariser (can be slow) – only if LLM not used
    adv = _summarise_with_hf(raw_text, max_steps=max_steps) if llm_engine == "none" else []
    if adv:
        return adv

    # 4. Final heuristic sentence extraction
    sentences = re.split(r"(?<=[.!?])\s+", raw_text)
    steps: List[str] = []
    for s in sentences:
        s_clean = s.strip()
        if len(s_clean.split()) < 6:
            continue
        steps.append(s_clean)
        if len(steps) >= max_steps:
            break
    return steps


# ----------------------------------------------------
# Indexing (reused from index_methods.py)
# ----------------------------------------------------

def _load_model() -> SentenceTransformer:  # type: ignore
    if not hasattr(_load_model, "_m"):
        _load_model._m = SentenceTransformer(EMBED_MODEL_NAME)  # type: ignore
    return _load_model._m  # type: ignore


def _load_pdf_metadata(md_path: pathlib.Path) -> Dict[str, Any]:
    """If <md>.json exists, return its contents, else {}."""
    meta_path = md_path.with_suffix(".json")
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text())
        except Exception:
            return {}
    return {}


def build_index(md_paths: List[pathlib.Path], out_dir: pathlib.Path, llm_engine: str = "none") -> pathlib.Path:
    """Scan markdown files, extract method text (using LLM extraction if llm_engine is set), summarize into bullet points, and append to the FAISS index (methods.faiss) and metadata (methods_meta.jsonl) in out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "methods_meta.jsonl"
    index_path = out_dir / "methods.faiss"

    # Load existing index (if any) and metadata
    if index_path.exists() and meta_path.exists():
        index = faiss.read_index(str(index_path))
        metadata: List[Dict[str, Any]] = []
        with meta_path.open() as f:
            for line in f:
                metadata.append(json.loads(line))
    else:
        index = faiss.IndexFlatIP(EMBED_MODEL_NAME)  # (dummy, will be recreated)
        metadata = []

    model = _load_model()

    new_records: List[Dict[str, Any]] = []
    new_texts: List[str] = []

    for p in md_paths:
        LOG.info("Reading %s", p.name)
        try:
            raw = p.read_text()
        except Exception as e:
            LOG.warning("Failed to read %s: %s", p, e)
            continue

        # (Optionally) use LLM to extract method text (or use full text)
        if llm_engine != "none":
            prompt = "Extract the experimental / methods / procedure section from the following scientific paper (in markdown). Return ONLY the extracted text (no bullet points).\n\n" + raw[: 3800]
            try:
                if llm_engine == "openai":
                    raw = _call_openai(prompt)
                elif llm_engine == "ollama":
                    raw = _call_ollama(prompt)
            except Exception as e:
                LOG.warning("LLM extraction failed on %s: %s", p, e)
                # (fallback to full text)

        # Summarise (bullet, LLM, HF, heuristic) into steps
        steps = summarise_to_steps(raw, llm_engine=llm_engine)

        meta_extra = _load_pdf_metadata(p)

        rec = {
            "file": str(p),
            "title": meta_extra.get("title") or p.stem,
            "raw": raw,
            "section_type": "md",
            "steps": steps,
            "doi": meta_extra.get("doi"),
            "authors": meta_extra.get("authors"),
            "year": meta_extra.get("published_date"),
            "source": meta_extra.get("source"),
        }
        new_records.append(rec)
        new_texts.append(raw)

    if not new_records:
        raise RuntimeError("No new records extracted from markdown files")

    # Recompute embeddings (for new texts) and append to index
    embs = model.encode(new_texts, show_progress_bar=True, batch_size=32, normalize_embeddings=True)
    index = faiss.IndexFlatIP(embs.shape[1])
    index.add(embs.astype(np.float32))

    # Append new metadata (and re-write index)
    faiss.write_index(index, str(index_path))
    with meta_path.open("a") as f:
        for rec in new_records:
            f.write(json.dumps(rec) + "\n")

    LOG.info("Indexed %d new md records (total: %d) → %s", len(new_records), len(metadata) + len(new_records), out_dir)
    return out_dir


if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="Index markdown (md) files (extract method text, summarize into bullet points, and append to FAISS index).")
    parser.add_argument("paths", nargs="+", help="Markdown file(s) or folder(s) (recursively scanned for *.md)")
    parser.add_argument("--out", default="literature_index", help="Output index directory (reuses methods.faiss & methods_meta.jsonl)")
    parser.add_argument("--llm", choices=["openai", "ollama", "none"], default=os.getenv("LLM_ENGINE", "none"), help="LLM engine (openai, ollama, or none) (default: LLM_ENGINE env var or none)")
    args = parser.parse_args()

    md_paths: List[pathlib.Path] = []
    for p in args.paths:
        path = pathlib.Path(p)
        if path.is_dir():
            md_paths.extend(list(path.rglob("*.md")))
        elif path.suffix.lower() == ".md":
            md_paths.append(path)

    if not md_paths:
        sys.exit("No markdown (*.md) files found.")

    build_index(md_paths, pathlib.Path(args.out), llm_engine=args.llm) 