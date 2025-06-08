"""
Notebook extractor for Jupyter notebooks.
Extracts workflows and code snippets that can be indexed.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List
import json

# Add libraries to path
libs_path = Path(__file__).parent.parent.parent / "libraries"
sys.path.insert(0, str(libs_path))

from .base_extractor import BaseExtractor

class NotebookExtractor(BaseExtractor):
    """
    Extractor for Jupyter notebooks.
    Produces workflow and snippet JSONs ready for indexing.
    """
    
    def _get_file_suffix(self) -> str:
        return ".ipynb"
    
    async def extract_from_file(
        self, 
        file_path: Path, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract workflows and snippets from a Jupyter notebook.
        
        Args:
            file_path: Path to .ipynb file
            params: Extraction parameters:
                - workflow_title: Optional specific workflow to extract
                - hoist_imports: Whether to move imports to top (default: True)
                - synth_imports: Whether to synthesize missing imports (default: True)
                - extract_snippets: Whether to extract code snippets (default: True)
                - extract_workflows: Whether to extract complete workflows (default: True)
        
        Returns:
            List of extracted workflow/snippet objects
        """
        self.logger.info(f"Extracting from notebook: {file_path}")
        
        # Import the notebook indexing functions
        try:
            from notebook_library.index_notebooks import (
                extract_snippets,
                extract_complete_workflows,
                cluster_notebook_cells
            )
        except ImportError as e:
            raise ImportError(f"Notebook extraction dependencies not available: {e}")
        
        # Get parameters
        workflow_title = params.get('workflow_title')
        hoist_imports = params.get('hoist_imports', True)
        synth_imports = params.get('synth_imports', True)
        extract_snippets_flag = params.get('extract_snippets', True)
        extract_workflows_flag = params.get('extract_workflows', True)
        
        extracted_data = []
        
        # Extract snippets if requested
        if extract_snippets_flag:
            try:
                snippets = extract_snippets(
                    file_path, 
                    hoist_imports=hoist_imports, 
                    synth_imports=synth_imports
                )
                
                # Add metadata to snippets
                for snippet in snippets:
                    snippet.update({
                        'content_type': 'code_snippet',
                        'source_file': str(file_path),
                        'extraction_type': 'snippet'
                    })
                
                extracted_data.extend(snippets)
                self.logger.info(f"Extracted {len(snippets)} code snippets")
                
            except Exception as e:
                self.logger.error(f"Failed to extract snippets: {e}")
        
        # Extract complete workflows if requested
        if extract_workflows_flag:
            try:
                # First get snippets for workflow extraction
                snippets_for_workflows = extract_snippets(
                    file_path, 
                    hoist_imports=hoist_imports, 
                    synth_imports=synth_imports
                )
                
                # Extract complete workflows
                workflows = extract_complete_workflows(file_path, snippets_for_workflows)
                
                # Filter by workflow title if specified
                if workflow_title:
                    workflows = [w for w in workflows if w.get('title', '').lower() == workflow_title.lower()]
                
                # Add metadata to workflows
                for workflow in workflows:
                    workflow.update({
                        'content_type': 'complete_workflow',
                        'source_file': str(file_path),
                        'extraction_type': 'workflow'
                    })
                
                extracted_data.extend(workflows)
                self.logger.info(f"Extracted {len(workflows)} complete workflows")
                
            except Exception as e:
                self.logger.error(f"Failed to extract workflows: {e}")
        
        # Clean and return data
        cleaned_data = self._clean_extracted_data(extracted_data)
        
        self.logger.info(f"Total extracted items: {len(cleaned_data)}")
        return cleaned_data
    
    async def extract_from_url(
        self, 
        url: str, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract from a notebook URL (e.g., GitHub raw link).
        """
        self.logger.info(f"Extracting notebook from URL: {url}")
        
        # Download and delegate to file extraction
        import aiohttp
        import tempfile
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Validate it's a valid notebook
                    try:
                        notebook_data = json.loads(content.decode('utf-8'))
                        if 'cells' not in notebook_data:
                            raise ValueError("Invalid notebook format: missing 'cells'")
                    except json.JSONDecodeError:
                        raise ValueError("Invalid JSON format for notebook")
                    
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".ipynb") as temp_file:
                        temp_file.write(content)
                        temp_path = Path(temp_file.name)
                    
                    try:
                        # Add URL to params for metadata
                        params_with_url = params.copy()
                        params_with_url['source_url'] = url
                        
                        result = await self.extract_from_file(temp_path, params_with_url)
                        
                        # Update source info for URL extraction
                        for item in result:
                            item['source_url'] = url
                            item['source_file'] = url  # Override file path with URL
                        
                        return result
                    finally:
                        temp_path.unlink()
                else:
                    raise Exception(f"Failed to download notebook from {url}: {response.status}")
    
    def get_extraction_preview(self, file_path: Path) -> Dict[str, Any]:
        """
        Get a preview of what would be extracted without full processing.
        """
        try:
            import nbformat
            
            nb = nbformat.read(file_path, as_version=4)
            
            # Count cells by type
            code_cells = sum(1 for cell in nb.cells if cell.cell_type == "code")
            markdown_cells = sum(1 for cell in nb.cells if cell.cell_type == "markdown")
            
            # Look for workflow headers
            potential_workflows = []
            for cell in nb.cells:
                if cell.cell_type == "markdown":
                    lines = cell.source.split('\n')
                    for line in lines:
                        if line.strip().startswith('#'):
                            potential_workflows.append(line.strip())
            
            return {
                "total_cells": len(nb.cells),
                "code_cells": code_cells,
                "markdown_cells": markdown_cells,
                "potential_workflows": potential_workflows[:10],  # First 10
                "estimated_snippets": max(1, code_cells // 3),  # Rough estimate
                "estimated_workflows": max(1, len(potential_workflows) // 2)
            }
        
        except Exception as e:
            return {"error": str(e)} 