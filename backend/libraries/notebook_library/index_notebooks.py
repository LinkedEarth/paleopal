"""notebook_library.index_notebooks

CLI / importable function to scan Jupyter notebooks, extract code (and nearby
markdown) snippets, embed them, and persist a Qdrant index.
"""
from __future__ import annotations

import json
import os
import pathlib
import uuid
import ast
import sys
from typing import List, Dict, Any, Tuple, Set, Optional
import re
import builtins

import nbformat
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES

EMBED_MODEL_NAME = os.getenv("SNIPPET_EMBED_MODEL", "all-MiniLM-L6-v2")


def _load_model() -> SentenceTransformer:  # type: ignore
    """Load (or cache) the sentence-transformer model used for embeddings."""
    if not hasattr(_load_model, "_model"):
        _load_model._model = SentenceTransformer(EMBED_MODEL_NAME)  # type: ignore
    return _load_model._model  # type: ignore


############################
# Dependency helpers
############################


def _names_defined_used(code: str) -> Tuple[Set[str], Set[str], Set[str]]:
    """Return sets (defined, used, imports) for a code cell."""
    defined: Set[str] = set()
    used: Set[str] = set()
    imports: Set[str] = set()

    # Strip Jupyter magics and shell escapes so AST can parse
    cleaned_lines = [
        l for l in code.splitlines()
        if not l.lstrip().startswith("%") and not l.lstrip().startswith("!")
    ]

    try:
        tree = ast.parse("\n".join(cleaned_lines))
    except SyntaxError:
        return defined, used, imports  # skip broken cell

    class NameCollector(ast.NodeVisitor):
        def visit_Name(self, node):  # type: ignore
            if isinstance(node.ctx, ast.Store):
                defined.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                used.add(node.id)

        def visit_FunctionDef(self, node):  # type: ignore
            defined.add(node.name)
            self.generic_visit(node)

        def visit_Import(self, node):  # type: ignore
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                defined.add(name)
                imports.add(name)

        def visit_ImportFrom(self, node):  # type: ignore
            for alias in node.names:
                name = alias.asname or alias.name
                defined.add(name)
                imports.add(name)

    NameCollector().visit(tree)
    return defined, used, imports


IMPORT_RE = re.compile(r"^\s*(?:import\s+\w|from\s+\S+\s+import)" )


############################
# Common Cell Clustering Logic
############################


def cluster_notebook_cells(
    nb_path: pathlib.Path, 
    *, 
    hoist_imports: bool = True, 
    synth_imports: bool = True,
    snippet_mode: bool = True,
    workflow_title: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Common function to cluster notebook cells into meaningful code units.
    
    Args:
        nb_path: Path to the notebook file
        hoist_imports: Whether to move all imports to the top of each cluster
        synth_imports: Whether to synthesize missing import statements
        snippet_mode: If True, clusters based on markdown headers (snippet mode).
                     If False, clusters all code cells together (workflow step mode).
        workflow_title: If provided, only extract cells from this specific workflow section
        
    Returns:
        List of clustered code units with metadata
    """
    nb = nbformat.read(nb_path, as_version=4)
    cells = nb.cells

    # Precompute defined names per code cell
    code_cells_info: List[Tuple[int, str, Set[str], Set[str], Set[str]]] = []  # (idx, code, defined, used, imports)
    for idx, cell in enumerate(cells):
        if cell.cell_type == "code":
            d, u, imps = _names_defined_used(cell.source)
            code_cells_info.append((idx, cell.source, d, u, imps))

    idx_to_info = {idx: (code, defined, used, imports) for idx, code, defined, used, imports in code_cells_info}

    clusters: List[Dict[str, Any]] = []
    current_block_code_idxs: List[int] = []
    current_heading = "Notebook start"
    
    # For workflow mode, track if we're in the target workflow
    in_target_workflow = workflow_title is None  # If no specific workflow, process all

    def flush_block():
        if not current_block_code_idxs:
            return

        # Determine dependencies
        block_defined: Set[str] = set()
        block_used: Set[str] = set()
        block_imports: Set[str] = set()

        # consider current block cells first
        for idx in current_block_code_idxs:
            code, defined, used, imports = idx_to_info[idx]
            block_defined.update(defined)
            block_used.update(used)
            block_imports.update(imports)

        unresolved = block_used - block_defined

        # remove Python builtins (initial pass)
        builtin_names = set(dir(builtins))
        unresolved -= builtin_names

        dependency_code_idxs: List[int] = []
        if unresolved:
            # First pass: look backwards only within current heading (already done by current_block_code_idxs)
            first_idx = current_block_code_idxs[0]
            for prev_idx in reversed(range(0, first_idx)):
                if prev_idx not in idx_to_info:
                    continue
                code, defined, _, imports_prev = idx_to_info[prev_idx]
                if unresolved & defined:
                    dependency_code_idxs.insert(0, prev_idx)
                    unresolved -= defined
                    block_imports.update(imports_prev)
                if not unresolved:
                    break

        # Second pass: widen search to any earlier cell that defines unresolved symbols
        if unresolved:
            first_idx = current_block_code_idxs[0]
            for prev_idx in reversed(range(0, first_idx)):
                if prev_idx in dependency_code_idxs or prev_idx not in idx_to_info:
                    continue
                code_prev, defined_prev, _, imports_prev = idx_to_info[prev_idx]
                if unresolved & defined_prev or unresolved & imports_prev:
                    dependency_code_idxs.insert(0, prev_idx)
                    unresolved -= defined_prev
                    block_imports.update(imports_prev)
                if not unresolved:
                    break

        all_code_idxs = dependency_code_idxs + current_block_code_idxs

        # recompute metadata across ALL cells (dependencies included)
        block_defined.clear()
        block_used.clear()
        block_imports.clear()
        for idx in all_code_idxs:
            code, defined, used, imports = idx_to_info[idx]
            block_defined.update(defined)
            block_used.update(used)
            block_imports.update(imports)

        unresolved = block_used - block_defined
        
        builtin_names = set(dir(builtins))
        unresolved -= builtin_names

        # Concatenate code with separators
        code_sections = [idx_to_info[i][0] for i in all_code_idxs]

        # Synthesise missing imports if requested
        synthetic_import_lines: List[str] = []
        if synth_imports and unresolved:
            for name in sorted(unresolved):
                synthetic_import_lines.append(f"import {name}")
            if synthetic_import_lines:
                block_imports.update(unresolved)
                block_defined.update(unresolved)
                unresolved.clear()

        if synthetic_import_lines:
            code_sections.insert(0, "\n".join(synthetic_import_lines))

        if hoist_imports:
            import_lines: List[str] = []
            other_lines: List[str] = []
            seen_imports = set()
            for section in code_sections:
                for line in section.splitlines():
                    if IMPORT_RE.match(line):
                        stripped = line.strip()
                        if stripped not in seen_imports:
                            seen_imports.add(stripped)
                            import_lines.append(line)
                    else:
                        other_lines.append(line)

            full_code = "\n".join(import_lines) + "\n\n" + "\n".join(other_lines)
        else:
            full_code = "\n\n# ----\n".join(code_sections)

        cluster_id = str(uuid.uuid4())
        clusters.append({
            "id": cluster_id,
            "notebook": str(nb_path),
            "cell_indices": all_code_idxs,
            "code": full_code,
            "markdown_context": current_heading.strip(),
            "defined": sorted(block_defined),
            "used": sorted(block_used),
            "imports": sorted(block_imports),
            "unresolved": sorted(unresolved),
        })

    # iterate over cells
    for idx, cell in enumerate(cells):
        if cell.cell_type == "markdown" and cell.source.lstrip().startswith("#"):
            # heading boundary
            if snippet_mode:
                # In snippet mode, each heading creates a new cluster
                flush_block()
                current_block_code_idxs = []
                current_heading = cell.source
                in_target_workflow = workflow_title is None or workflow_title in cell.source
            else:
                # In workflow mode, create clusters for sub-headings within workflows
                if workflow_title is None:
                    # Process all workflows - each heading starts a new cluster
                    flush_block()
                    current_block_code_idxs = []
                    current_heading = cell.source
                    in_target_workflow = True
                elif workflow_title in cell.source:
                    # Found target workflow - start collecting
                    flush_block()
                    current_block_code_idxs = []
                    current_heading = cell.source
                    in_target_workflow = True
                elif in_target_workflow:
                    # Check if this is a sub-heading within the target workflow
                    if cell.source.lstrip().startswith("#"):
                        # Count the number of # to determine heading level
                        stripped = cell.source.lstrip()
                        heading_level = 0
                        for char in stripped:
                            if char == '#':
                                heading_level += 1
                            else:
                                break
                        
                        # If it's a main heading (single #), this means end of current workflow
                        if heading_level == 1:
                            flush_block()
                            in_target_workflow = False
                            break
                        else:
                            # It's a sub-heading (##, ###, etc.) - create a new step
                            flush_block()
                            current_block_code_idxs = []
                            current_heading = cell.source
                            # Stay in the workflow
            continue

        if cell.cell_type == "code" and in_target_workflow:
            current_block_code_idxs.append(idx)

    # flush last block
    if in_target_workflow:
        flush_block()

    return clusters


def extract_snippets(nb_path: pathlib.Path, *, hoist_imports: bool = True, synth_imports: bool = True) -> List[Dict[str, Any]]:
    """Return list of multi-cell recipe snippets from a notebook.

    This function now uses the common clustering logic in snippet mode.
    
    Heuristic:
    * A markdown cell starting with `#` denotes the beginning of a new recipe.
    * All following code cells until the next heading (or EOF) belong to it.
    * Before finalising, we prepend earlier dependency cells so that all
      variables used in the block are defined.
    """
    return cluster_notebook_cells(
        nb_path, 
        hoist_imports=hoist_imports, 
        synth_imports=synth_imports,
        snippet_mode=True
    )


def build_index(
    notebook_paths: List[pathlib.Path],
    collection_name_prefix: str = None,
    *,
    hoist_imports: bool = True,
    keep_invalid: bool = False,
    synth_imports: bool = True,
    force_recreate: bool = False,
) -> Dict[str, str]:
    """
    Build Qdrant indexes from notebooks.
    
    Returns:
        Dictionary mapping collection types to collection names created
    """
    if collection_name_prefix is None:
        collections = {
            "snippets": COLLECTION_NAMES["notebook_snippets"],
            "workflows": COLLECTION_NAMES["notebook_workflows"]
            # Note: no longer creating separate notebook_steps collection
        }
    else:
        collections = {
            "snippets": f"{collection_name_prefix}_snippets",
            "workflows": f"{collection_name_prefix}_workflows"
        }

    all_snippets: List[Dict[str, Any]] = []
    all_workflows: List[Dict[str, Any]] = []

    def _embed_text(s: Dict[str, Any]) -> str:
        """Extract text for embedding from snippet metadata."""
        parts = [s.get("title", "")]
        if s.get("code"):
            parts.append(s["code"])
        if s.get("markdown"):
            parts.append(s["markdown"])
        return "\n".join(p for p in parts if p)

    def _complete_workflow_embed_text(w: Dict[str, Any]) -> str:
        """Extract text for embedding from complete workflow with steps."""
        parts = [w.get("title", "")]
        if w.get("description"):
            parts.append(w["description"])
        if w.get("keywords"):
            parts.extend(w["keywords"])
        
        # Add all step content for comprehensive searchability
        for step in w.get("workflow_steps", []):
            if step.get("description"):
                parts.append(step["description"])
        if step.get("code"):
            parts.append(step["code"])
        if step.get("dependencies"):
            parts.extend(step["dependencies"])
        
        return " ".join(p for p in parts if p)

    for nb_path in tqdm(notebook_paths, desc="Processing notebooks"):
        try:
            snippets = extract_snippets(
                nb_path, 
                hoist_imports=hoist_imports, 
                synth_imports=synth_imports
            )
            
            if keep_invalid:
                # Keep all snippets even if they have unresolved dependencies
                valid_snippets = snippets
            else:
                # Filter out snippets with unresolved dependencies
                valid_snippets = [s for s in snippets if not s.get("unresolved")]
            
            # Add embedding text to each snippet
            for snippet in valid_snippets:
                snippet["text"] = _embed_text(snippet)
                snippet["id"] = str(uuid.uuid4())
                snippet["notebook_path"] = str(nb_path)
                
            all_snippets.extend(valid_snippets)
            
            # Extract complete workflows with embedded steps
            complete_workflows = extract_complete_workflows(nb_path, snippets)
            for workflow in complete_workflows:
                workflow["text"] = _complete_workflow_embed_text(workflow)
                workflow["id"] = str(uuid.uuid4())
                workflow["notebook_path"] = str(nb_path)
                
            all_workflows.extend(complete_workflows)
            
        except Exception as e:
            print(f"Error processing {nb_path}: {e}")
            continue

    if not all_snippets and not all_workflows:
        raise ValueError("No valid snippets or workflows extracted from notebooks")

    # Get Qdrant manager
    qdrant_manager = get_qdrant_manager()
    
    # Create collections and index documents
    results = {}
    
    if all_snippets:
        print(f"Indexing {len(all_snippets)} snippets...")
        if qdrant_manager.create_collection(collections["snippets"], force_recreate=force_recreate):
            qdrant_manager.index_documents(
                collection_name=collections["snippets"],
                documents=all_snippets,
                text_field="text"
            )
            results["snippets"] = collections["snippets"]
    
    if all_workflows:
        print(f"Indexing {len(all_workflows)} complete workflows...")
        if qdrant_manager.create_collection(collections["workflows"], force_recreate=force_recreate):
            qdrant_manager.index_documents(
                collection_name=collections["workflows"],
                documents=all_workflows,
                text_field="text"
            )
            results["workflows"] = collections["workflows"]
    
    print(f"Notebook indexing completed. Created collections: {list(results.values())}")
    return results


def extract_complete_workflows(nb_path: pathlib.Path, snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract complete workflow documents with all steps embedded as metadata."""
    nb = nbformat.read(nb_path, as_version=4)
    cells = nb.cells
    
    workflows = []
    current_workflow = None
    seen_workflow_titles = set()  # Track duplicate workflows
    
    # First, get basic workflow structure
    for cell in cells:
        if cell.cell_type == "markdown":
            source = cell.source.strip()
            
            # Look for workflow headers (# or ##)
            if source.startswith("#"):
                # Finalize previous workflow
                if current_workflow:
                    # Use intelligent clustering for this workflow's steps
                    workflow_steps = extract_workflow_steps_for_workflow(nb_path, current_workflow["title"])
                    
                    # Skip workflows with 0 steps
                    if len(workflow_steps) == 0:
                        # print(f"Skipping workflow '{current_workflow['title']}' - no steps found")
                        current_workflow = None
                        continue
                        
                    current_workflow["workflow_steps"] = workflow_steps
                    current_workflow["num_steps"] = len(workflow_steps)
                    
                    # Aggregate metadata from steps
                    all_step_types = set()
                    all_keywords = set(current_workflow.get("keywords", []))
                    defined_names = set()
                    used_names = set()
                    all_dependencies = set()
                    
                    for step in workflow_steps:
                        all_step_types.add(step.get("step_type", "computation"))
                        all_keywords.update(step.get("keywords", []))
                        defined_names.update(step.get("defined_names", []))
                        used_names.update(step.get("used_names", []))
                        all_dependencies.update(step.get("dependencies", []))
                    
                    current_workflow.update({
                        "step_types": list(all_step_types),
                        "all_keywords": list(all_keywords),
                        "defined_names": list(defined_names),
                        "used_names": list(used_names),
                        "all_dependencies": list(all_dependencies),
                        "steps_preview": [
                            {
                                "step_number": step.get("step_number"),
                                "step_type": step.get("step_type"),
                                "description": step.get("description", "")[:200] + "..." if len(step.get("description", "")) > 200 else step.get("description", "")
                            }
                            for step in workflow_steps[:3]  # Show first 3 steps as preview
                        ]
                    })
                    
                    workflows.append(current_workflow)
                
                # Start new workflow
                title_match = re.match(r'^#+\s*(.+)', source)
                title = title_match.group(1) if title_match else "Unnamed Workflow"
                
                # Skip duplicate workflows (case-insensitive)
                title_normalized = title.lower().strip()
                if title_normalized in seen_workflow_titles:
                    # print(f"Skipping duplicate workflow '{title}'")
                    current_workflow = None
                    continue
                
                seen_workflow_titles.add(title_normalized)
                
                # Extract description from remaining markdown
                lines = source.split('\n')[1:]  # Skip title line
                description = '\n'.join(lines).strip()
                
                current_workflow = {
                    "title": title,
                    "description": description,
                    "content_type": "complete_workflow",
                    "workflow_type": classify_workflow_type(f"{title} {description}"),
                    "keywords": extract_keywords_from_text(f"{title} {description}"),
                    "complexity": "simple",
                    "has_imports": False,
                    "cell_count": 0
                }
        
        elif cell.cell_type == "code" and current_workflow:
            current_workflow["cell_count"] += 1
            
            # Check for imports
            if re.search(r'^\s*(?:import|from)\s', cell.source, re.MULTILINE):
                current_workflow["has_imports"] = True
            
            # Assess complexity based on code patterns
            if any(pattern in cell.source for pattern in ['for ', 'while ', 'def ', 'class ', 'if ']):
                current_workflow["complexity"] = "complex"
            elif current_workflow["complexity"] == "simple" and len(cell.source.split('\n')) > 5:
                current_workflow["complexity"] = "medium"
    
    # Don't forget the last workflow
    if current_workflow:
        # Use intelligent clustering for this workflow's steps
        workflow_steps = extract_workflow_steps_for_workflow(nb_path, current_workflow["title"])
        
        # Skip workflows with 0 steps
        if len(workflow_steps) == 0:
            # print(f"Skipping workflow '{current_workflow['title']}' - no steps found")
            pass
        else:
            current_workflow["workflow_steps"] = workflow_steps
            current_workflow["num_steps"] = len(workflow_steps)
            
            # Aggregate metadata from steps
            all_step_types = set()
            all_keywords = set(current_workflow.get("keywords", []))
            defined_names = set()
            used_names = set()
            all_dependencies = set()
            
            for step in workflow_steps:
                all_step_types.add(step.get("step_type", "computation"))
                all_keywords.update(step.get("keywords", []))
                defined_names.update(step.get("defined_names", []))
                used_names.update(step.get("used_names", []))
                all_dependencies.update(step.get("dependencies", []))
            
            current_workflow.update({
                "step_types": list(all_step_types),
                "all_keywords": list(all_keywords),
                "defined_names": list(defined_names),
                "used_names": list(used_names),
                "all_dependencies": list(all_dependencies),
                "steps_preview": [
                    {
                        "step_number": step.get("step_number"),
                        "step_type": step.get("step_type"),
                        "description": step.get("description", "")[:200] + "..." if len(step.get("description", "")) > 200 else step.get("description", "")
                    }
                    for step in workflow_steps[:3]  # Show first 3 steps as preview
                ]
            })
            
            workflows.append(current_workflow)
    
    return workflows


def extract_workflow_steps(snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract steps from snippets belonging to a workflow using intelligent clustering."""
    steps = []
    step_number = 1
    
    for snippet in snippets:
        code = snippet.get("code", "").strip()
        
        # Skip steps with no meaningful code content
        if not code:
            continue
            
        # Skip steps that only contain comments or whitespace
        code_lines = [line.strip() for line in code.split('\n') if line.strip()]
        meaningful_lines = [line for line in code_lines if not line.startswith('#') and not line.startswith('"""') and not line.startswith("'''")]
        
        if not meaningful_lines:
            # print(f"Skipping step with only comments/markdown: {snippet.get('markdown_context', 'Unknown')[:50]}...")
            continue
        
        # Convert snippet to step format
        step = {
            "step_number": step_number,
            "description": snippet.get("markdown_context", f"Step {step_number}"),
            "code": code,
            "step_type": classify_step_type(code),
            "defined_names": snippet.get("defined", []),
            "used_names": snippet.get("used", []),
            "dependencies": snippet.get("imports", []),
            "keywords": extract_keywords_from_text(code + " " + snippet.get("markdown_context", "")),
            "cell_indices": snippet.get("cell_indices", []),
            "unresolved_dependencies": snippet.get("unresolved", [])
        }
        steps.append(step)
        step_number += 1
    
    return steps


def extract_workflow_steps_for_workflow(nb_path: pathlib.Path, workflow_title: str) -> List[Dict[str, Any]]:
    """Extract workflow steps for a specific workflow using intelligent clustering."""
    # Use the common clustering function in workflow mode for the specific workflow
    clusters = cluster_notebook_cells(
        nb_path,
        hoist_imports=True,
        synth_imports=True,
        snippet_mode=False,  # Use workflow mode
        workflow_title=workflow_title
    )
    
    return extract_workflow_steps(clusters)


def extract_individual_steps_from_workflow(workflow: Dict[str, Any], nb_path: pathlib.Path) -> List[Dict[str, Any]]:
    """Extract individual steps directly from notebook cells for a workflow."""
    nb = nbformat.read(nb_path, as_version=4)
    cells = nb.cells
    
    steps = []
    in_workflow = False
    step_number = 1
    
    for cell in cells:
        if cell.cell_type == "markdown":
            source = cell.source.strip()
            if source.startswith("#") and workflow["title"] in source:
                in_workflow = True
                continue
            elif source.startswith("#") and in_workflow:
                # Next workflow started
                break
        
        elif cell.cell_type == "code" and in_workflow and cell.source.strip():
            step = {
                "step_number": step_number,
                "description": f"Step {step_number} from {workflow['title']}",
                "code": cell.source.strip(),
                "step_type": classify_step_type(cell.source),
                "defined_names": extract_defined_names(cell.source),
                "used_names": extract_used_names(cell.source),
                "dependencies": [],
                "keywords": extract_keywords_from_text(cell.source)
            }
            steps.append(step)
            step_number += 1
    
    return steps


def classify_workflow_type(text: str) -> str:
    """Classify the overall type of workflow based on title and description."""
    text_lower = text.lower()
    
    if any(keyword in text_lower for keyword in ['analysis', 'analyze', 'statistical']):
        return "data_analysis"
    elif any(keyword in text_lower for keyword in ['visualization', 'plot', 'chart', 'graph']):
        return "visualization"
    elif any(keyword in text_lower for keyword in ['preprocess', 'clean', 'transform']):
        return "preprocessing"
    elif any(keyword in text_lower for keyword in ['model', 'train', 'predict', 'machine learning']):
        return "modeling"
    elif any(keyword in text_lower for keyword in ['load', 'import', 'read', 'fetch']):
        return "data_loading"
    else:
        return "general"


def extract_workflows(nb_path: pathlib.Path) -> List[Dict[str, Any]]:
    """Extract workflow-level information from a notebook."""
    nb = nbformat.read(nb_path, as_version=4)
    cells = nb.cells
    
    workflows = []
    current_workflow = None
    
    for cell in cells:
        if cell.cell_type == "markdown":
            source = cell.source.strip()
            
            # Look for workflow headers (# or ##)
            if source.startswith("#"):
                # Start new workflow
                if current_workflow:
                    workflows.append(current_workflow)
                
                title_match = re.match(r'^#+\s*(.+)', source)
                title = title_match.group(1) if title_match else "Unnamed Workflow"
                
                # Extract description from remaining markdown
                lines = source.split('\n')[1:]  # Skip title line
                description = '\n'.join(lines).strip()
                
                current_workflow = {
                    "title": title,
                    "description": description,
                    "keywords": extract_keywords_from_text(f"{title} {description}"),
                    "cell_count": 0,
                    "has_imports": False,
                    "complexity": "simple"
                }
        
        elif cell.cell_type == "code" and current_workflow:
            current_workflow["cell_count"] += 1
            
            # Check for imports
            if re.search(r'^\s*(?:import|from)\s', cell.source, re.MULTILINE):
                current_workflow["has_imports"] = True
            
            # Assess complexity based on code patterns
            if any(pattern in cell.source for pattern in ['for ', 'while ', 'def ', 'class ', 'if ']):
                current_workflow["complexity"] = "complex"
            elif current_workflow["complexity"] == "simple" and len(cell.source.split('\n')) > 5:
                current_workflow["complexity"] = "medium"
    
    # Don't forget the last workflow
    if current_workflow:
        workflows.append(current_workflow)
    
    return workflows


def extract_individual_steps(snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract individual computational steps from snippets."""
    steps = []
    
    for snippet in snippets:
        code = snippet.get("code", "")
        if not code:
            continue
            
        # Split code into logical steps (by empty lines or comments)
        code_blocks = re.split(r'\n\s*\n|\n\s*#[^\n]*\n', code)
        
        for i, block in enumerate(code_blocks):
            block = block.strip()
            if not block or len(block) < 10:  # Skip very short blocks
                continue
            
            step = {
                "description": f"Step {i+1} from {snippet.get('title', 'unknown snippet')}",
                "code": block,
                "step_number": i + 1,
                "snippet_id": snippet.get("id"),
                "dependencies": snippet.get("dependencies", []),
                "defined_names": extract_defined_names(block),
                "used_names": extract_used_names(block),
                "step_type": classify_step_type(block)
            }
            steps.append(step)
    
    return steps


def extract_keywords_from_text(text: str) -> List[str]:
    """Extract keywords from text using simple heuristics."""
    # Common data science keywords
    keywords = set()
    
    keyword_patterns = [
        r'\b(pandas|numpy|matplotlib|seaborn|sklearn|scipy)\b',
        r'\b(dataframe|array|plot|chart|model|analysis)\b',
        r'\b(load|save|read|write|import|export)\b',
        r'\b(filter|sort|group|merge|join|pivot)\b',
        r'\b(visualization|statistics|machine learning|deep learning)\b'
    ]
    
    text_lower = text.lower()
    for pattern in keyword_patterns:
        matches = re.findall(pattern, text_lower)
        keywords.update(matches)
    
    return list(keywords)


def extract_defined_names(code: str) -> List[str]:
    """Extract variable names defined in code block."""
    defined = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined.add(target.id)
            elif isinstance(node, ast.FunctionDef):
                defined.add(node.name)
    except:
        pass  # Skip parsing errors
    
    return list(defined)


def extract_used_names(code: str) -> List[str]:
    """Extract variable names used in code block."""
    used = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used.add(node.id)
    except:
        pass  # Skip parsing errors
    
    return list(used)


def classify_step_type(code: str) -> str:
    """Classify the type of computational step."""
    code_lower = code.lower()
    
    if any(pattern in code_lower for pattern in ['import ', 'from ']):
        return "import"
    elif any(pattern in code_lower for pattern in ['read_csv', 'load', 'open(']):
        return "data_loading"
    elif any(pattern in code_lower for pattern in ['plot', 'show()', 'figure', 'subplot']):
        return "visualization"
    elif any(pattern in code_lower for pattern in ['def ', 'class ']):
        return "definition"
    elif any(pattern in code_lower for pattern in ['for ', 'while ']):
        return "iteration"
    elif any(pattern in code_lower for pattern in ['if ', 'else', 'elif']):
        return "conditional"
    else:
        return "computation"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build snippet library from notebooks")
    parser.add_argument("paths", nargs="+", help="Notebook paths or directories (recursively scanned)")
    parser.add_argument("--out", default="notebook", help="Output prefix for collections")
    parser.add_argument("--no-hoist-imports", action="store_true", help="Keep imports in original positions")
    parser.add_argument("--keep-invalid", action="store_true", help="Include snippets with unresolved names")
    parser.add_argument("--no-synth-imports", action="store_true", help="Do not create synthetic import lines for missing names")
    parser.add_argument("--force-recreate", action="store_true", help="Force recreate collections if they exist")
    args = parser.parse_args()

    # collect notebooks
    collected: List[pathlib.Path] = []
    for p in args.paths:
        path = pathlib.Path(p)
        if path.is_dir():
            collected.extend(path.rglob("*.ipynb"))
        elif path.suffix == ".ipynb":
            collected.append(path)

    if not collected:
        raise SystemExit("No .ipynb files found in given paths")

    build_index(
        collected, 
        args.out, 
        hoist_imports=not args.no_hoist_imports, 
        keep_invalid=args.keep_invalid, 
        synth_imports=not args.no_synth_imports,
        force_recreate=args.force_recreate
    ) 
