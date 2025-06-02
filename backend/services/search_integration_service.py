"""
Search Integration Service

This service provides integration with notebook_library and literature_library
to search for relevant workflows and methods that can inform workflow planning.
Enhanced with code snippet and documentation search for code generation context.
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add the library directories to Python path for imports
base_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(base_dir / "libraries" / "notebook_library"))
sys.path.insert(0, str(base_dir / "libraries" / "literature_library"))
sys.path.insert(0, str(base_dir / "libraries" / "readthedocs_library"))

logger = logging.getLogger(__name__)

class SearchIntegrationService:
    """Service to search notebook workflows and literature methods."""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent  # Go up to workspace root
        self.notebook_library_dir = self.base_dir / "libraries" / "notebook_library"
        self.literature_library_dir = self.base_dir / "libraries" / "literature_library"
        self.readthedocs_library_dir = self.base_dir / "libraries" / "readthedocs_library"
        
    async def search_workflows(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Search for relevant workflows from the notebook library.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of workflow matches with metadata
        """
        try:
            # Check if workflow index exists
            index_dir = self.notebook_library_dir / "notebook_index"
            if not index_dir.exists():
                logger.warning("Workflow index not found. Skipping workflow search.")
                return []
            
            # Import and call the search function directly
            try:
                from libraries.notebook_library.search_workflows import search_workflows
                results = search_workflows(query, top_k=top_k, index_dir=index_dir)
                return results if isinstance(results, list) else []
            except ImportError as e:
                logger.error(f"Failed to import search_workflows: {e}")
                return []
            except FileNotFoundError as e:
                logger.warning(f"Workflow index not found: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching workflows: {e}")
            return []
    
    async def search_methods(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant methods from the literature library.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of method matches with metadata
        """
        try:
            # Check if methods index exists
            index_dir = self.literature_library_dir / "methods_index"
            if not index_dir.exists():
                logger.warning("Methods index not found. Skipping methods search.")
                return []
            
            # Import and call the search function directly
            try:
                from libraries.literature_library.index_methods import search_methods_index
                results = search_methods_index(
                    query=query,
                    index_dir=index_dir,
                    top_k=top_k
                )
                return results if isinstance(results, list) else []
            except ImportError as e:
                logger.error(f"Failed to import index_methods: {e}")
                return []
            except RuntimeError as e:
                logger.warning(f"Methods index not available: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching methods: {e}")
            return []
    
    async def search_snippets(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant code snippets from the notebook library.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of code snippet matches with metadata
        """
        try:
            # Check if snippet index exists
            index_dir = self.notebook_library_dir / "notebook_index"
            if not index_dir.exists():
                logger.warning("Notebook/snippet index not found. Skipping snippet search.")
                return []
            
            # Import and call the search function directly
            try:
                from libraries.notebook_library.search_snippets import search
                results = search(query, index_dir=index_dir, top_k=top_k)
                
                # Enhance results with additional metadata for code generation
                enhanced_results = []
                for result in results:
                    enhanced_result = result.copy()
                    enhanced_result["snippet_type"] = "code"
                    enhanced_result["similarity_score"] = result.get("score", 0.0)
                    
                    # Extract useful context
                    if "code" in result:
                        enhanced_result["code_preview"] = result["code"][:200] + "..." if len(result["code"]) > 200 else result["code"]
                    
                    enhanced_results.append(enhanced_result)
                
                return enhanced_results
            except ImportError as e:
                logger.error(f"Failed to import search_snippets: {e}")
                return []
            except FileNotFoundError as e:
                logger.warning(f"Snippet index not found: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching snippets: {e}")
            return []
    
    async def search_documentation(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant documentation from the readthedocs library.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of documentation matches with metadata
        """
        try:
            # Check if docs index exists
            index_dir = self.readthedocs_library_dir / "rtd_index"
            if not index_dir.exists():
                logger.warning("ReadTheDocs index not found. Skipping documentation search.")
                return []
            
            # Import and call the search function directly
            try:
                from libraries.readthedocs_library.search_docs import search
                results = search(query, top_k=top_k, index_dir=index_dir)
                
                # Enhance results with additional metadata
                enhanced_results = []
                for result in results:
                    enhanced_result = result.copy()
                    enhanced_result["doc_type"] = "documentation"
                    enhanced_result["similarity_score"] = result.get("score", 0.0)
                    
                    # Add content preview
                    if "content" in result:
                        enhanced_result["content_preview"] = result["content"][:300] + "..." if len(result["content"]) > 300 else result["content"]
                    
                    enhanced_results.append(enhanced_result)
                
                return enhanced_results
            except ImportError as e:
                logger.error(f"Failed to import search_docs: {e}")
                return []
            except Exception as e:
                logger.warning(f"Documentation search failed: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching documentation: {e}")
            return []
    
    async def search_code_examples(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Search for relevant code examples from the readthedocs library.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of code example matches with metadata
        """
        try:
            # Check if code index exists
            index_dir = self.readthedocs_library_dir / "rtd_code_index"
            if not index_dir.exists():
                logger.warning("ReadTheDocs code index not found. Skipping code example search.")
                return []
            
            # Import and call the search function directly
            try:
                from libraries.readthedocs_library.search_code import search_code
                results = search_code(query, top_k=top_k, index_dir=index_dir)
                
                # Enhance results with additional metadata
                enhanced_results = []
                for result in results:
                    enhanced_result = result.copy()
                    enhanced_result["example_type"] = "code_example"
                    enhanced_result["similarity_score"] = result.get("score", 0.0)
                    
                    # Add code preview
                    if "code" in result:
                        enhanced_result["code_preview"] = result["code"][:200] + "..." if len(result["code"]) > 200 else result["code"]
                    
                    enhanced_results.append(enhanced_result)
                
                return enhanced_results
            except ImportError as e:
                logger.error(f"Failed to import search_code: {e}")
                return []
            except Exception as e:
                logger.warning(f"Code example search failed: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching code examples: {e}")
            return []
    
    async def get_context_for_planning(self, user_query: str) -> Dict[str, Any]:
        """
        Get comprehensive context for workflow planning by searching both
        notebooks and literature.
        
        Args:
            user_query: The user's request
            
        Returns:
            Dictionary containing workflow and method context
        """
        # Search workflows with higher weight
        workflows = await self.search_workflows(user_query, top_k=3)
        
        # Search methods with lower weight (for loose guidance)
        methods = await self.search_methods(user_query, top_k=5)
        
        return {
            "workflows": workflows,
            "methods": methods,
            "query": user_query
        }
    
    async def get_context_for_code_generation(self, user_query: str, previous_code: str = "") -> Dict[str, Any]:
        """
        Get comprehensive context for code generation by searching snippets,
        documentation, and code examples.
        
        Args:
            user_query: The user's request for code generation
            previous_code: Code from previous cells in the notebook
            
        Returns:
            Dictionary containing code generation context
        """
        # Search code snippets (high weight)
        snippets = await self.search_snippets(user_query, top_k=5)
        
        # Search documentation (important for API usage)
        documentation = await self.search_documentation(user_query, top_k=5)
        
        # Search code examples (important for patterns)
        code_examples = await self.search_code_examples(user_query, top_k=3)
        
        return {
            "snippets": snippets,
            "documentation": documentation,
            "code_examples": code_examples,
            "previous_code": previous_code,
            "query": user_query
        }
    
    def format_context_for_llm(self, context: Dict[str, Any]) -> str:
        """
        Format the search context into a text prompt for the LLM.
        
        Args:
            context: Context from get_context_for_planning
            
        Returns:
            Formatted text for LLM consumption
        """
        sections = []
        
        # Add workflow context (high weight)
        if context.get("workflows"):
            sections.append("## RELEVANT WORKFLOW EXAMPLES (High Priority - Follow These Patterns):\n")
            for i, workflow in enumerate(context["workflows"], 1):
                sections.append(f"### Workflow {i}: {workflow.get('title', 'Unknown')}")
                sections.append(f"**Similarity**: {workflow.get('similarity_score', 0):.3f}")
                sections.append(f"**Steps**: {workflow.get('step_count', 'Unknown')}")
                
                if workflow.get("workflow_steps"):
                    sections.append("**Step Breakdown**:")
                    for step in workflow["workflow_steps"]:
                        sections.append(f"- {step.get('step_description', step)}")
                
                if workflow.get("description"):
                    sections.append(f"**Description**: {workflow['description']}")
                    
                sections.append("")  # Add spacing
        
        # Add method context (lower weight)
        if context.get("methods"):
            sections.append("## RELEVANT SCIENTIFIC METHODS (Lower Priority - Use as Loose Guidance):\n")
            for i, method in enumerate(context["methods"], 1):
                sections.append(f"### Method {i}: {method.get('method_name', 'Unknown')}")
                sections.append(f"**From Paper**: {method.get('paper_title', 'Unknown')}")
                sections.append(f"**Similarity**: {method.get('similarity_score', 0):.3f}")
                
                if method.get("searchable_summary"):
                    sections.append(f"**Summary**: {method['searchable_summary']}")
                    
                if method.get("category"):
                    sections.append(f"**Category**: {method['category']}")
                    
                sections.append("")  # Add spacing
        
        return "\n".join(sections)
    
    def format_code_context_for_llm(self, context: Dict[str, Any]) -> str:
        """
        Format the code generation context into a text prompt for the LLM.
        
        Args:
            context: Context from get_context_for_code_generation
            
        Returns:
            Formatted text for LLM consumption
        """
        sections = []
        
        # Add previous code context (highest priority)
        if context.get("previous_code"):
            sections.append("## PREVIOUS CODE (Highest Priority - Use Variables and Build Upon This):\n")
            sections.append("```python")
            sections.append(context["previous_code"])
            sections.append("```\n")
        
        # Add snippet context (high weight)
        if context.get("snippets"):
            sections.append("## RELEVANT CODE SNIPPETS (High Priority - Adapt These Patterns):\n")
            for i, snippet in enumerate(context["snippets"], 1):
                sections.append(f"### Snippet {i}: {snippet.get('notebook', 'Unknown')}")
                sections.append(f"**Similarity**: {snippet.get('similarity_score', 0):.3f}")
                
                if snippet.get("code"):
                    sections.append("**Code**:")
                    sections.append("```python")
                    sections.append(snippet["code"])
                    sections.append("```")
                
                if snippet.get("imports"):
                    sections.append(f"**Imports**: {', '.join(snippet['imports'])}")
                    
                sections.append("")  # Add spacing
        
        # Add documentation context (important for correct API usage)
        if context.get("documentation"):
            sections.append("## RELEVANT DOCUMENTATION (Important - Follow API Patterns):\n")
            for i, doc in enumerate(context["documentation"], 1):
                sections.append(f"### Documentation {i}: {doc.get('source', 'Unknown')}")
                sections.append(f"**Similarity**: {doc.get('similarity_score', 0):.3f}")
                
                if doc.get("content"):
                    sections.append("**Content**:")
                    sections.append(doc["content"])
                    
                sections.append("")  # Add spacing
        
        # Add code examples (important for patterns)
        if context.get("code_examples"):
            sections.append("## RELEVANT CODE EXAMPLES (Important - Follow These Usage Patterns):\n")
            for i, example in enumerate(context["code_examples"], 1):
                sections.append(f"### Example {i}: {example.get('symbol', 'Unknown')}")
                sections.append(f"**Similarity**: {example.get('similarity_score', 0):.3f}")
                
                if example.get("code"):
                    sections.append("**Code**:")
                    sections.append("```python")
                    sections.append(example["code"])
                    sections.append("```")
                    
                sections.append("")  # Add spacing
        
        return "\n".join(sections)


# Global instance
search_service = SearchIntegrationService() 