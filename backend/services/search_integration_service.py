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
        
    async def search_notebook_workflows(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Search for relevant workflows from the notebook library.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of workflow matches with metadata
        """
        try:
            # Import and call the Qdrant-backed search function directly
            from libraries.notebook_library.search_workflows import search_workflows as _search_workflows

            results = _search_workflows(query, limit=top_k)
            return results if isinstance(results, list) else []

        except ImportError as e:
            logger.error(f"Failed to import notebook_library.search_workflows: {e}")
            return []
        except Exception as e:
            logger.error(f"Error searching workflows: {e}")
            return []
    
    async def search_literature_methods(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant methods from the literature library.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of method matches with metadata
        """
        try:
            # Import and call the Qdrant-backed search function directly
            from libraries.literature_library.search_methods import search_methods as _search_methods

            results = _search_methods(query, limit=top_k)
            return results if isinstance(results, list) else []

        except ImportError as e:
            logger.error(f"Failed to import literature_library.search_methods: {e}")
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
            # Import and call the Qdrant-backed search function directly
            from libraries.notebook_library.search_snippets import search_snippets as _search_snippets

            raw_results = _search_snippets(query, limit=top_k)

            # Enhance results with additional metadata for code generation
            enhanced_results = []
            for result in raw_results:
                enhanced_result = result.copy()
                enhanced_result["snippet_type"] = "code"
                enhanced_result["similarity_score"] = result.get("score", result.get("similarity_score", 0.0))

                # Extract useful context
                if "code" in result:
                    enhanced_result["code_preview"] = result["code"][:200] + "..." if len(result["code"]) > 200 else result["code"]

                enhanced_results.append(enhanced_result)

            return enhanced_results

        except ImportError as e:
            logger.error(f"Failed to import notebook_library.search_snippets: {e}")
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
            # Import and call the Qdrant-backed search function directly
            from libraries.readthedocs_library.search_docs import search_docs as _search_docs

            raw_results = _search_docs(query, limit=top_k)

            # Enhance results with additional metadata
            enhanced_results = []
            for result in raw_results:
                enhanced_result = result.copy()
                enhanced_result["doc_type"] = result.get("doc_type", "documentation")
                enhanced_result["similarity_score"] = result.get("score", result.get("similarity_score", 0.0))

                # Add content preview
                if "content" in result:
                    enhanced_result["content_preview"] = result["content"][:300] + "..." if len(result["content"]) > 300 else result["content"]

                enhanced_results.append(enhanced_result)

            return enhanced_results

        except ImportError as e:
            logger.error(f"Failed to import readthedocs_library.search_docs: {e}")
            return []
        except Exception as e:
            logger.warning(f"Documentation search failed: {e}")
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
            # Import and call the Qdrant-backed search function directly
            from libraries.readthedocs_library.search_code import search_code as _search_code

            raw_results = _search_code(query, limit=top_k)

            # Enhance results with additional metadata
            enhanced_results = []
            for result in raw_results:
                enhanced_result = result.copy()
                enhanced_result["example_type"] = "code_example"
                enhanced_result["similarity_score"] = result.get("score", result.get("similarity_score", 0.0))

                # Add code preview
                if "code" in result:
                    enhanced_result["code_preview"] = result["code"][:200] + "..." if len(result["code"]) > 200 else result["code"]

                enhanced_results.append(enhanced_result)

            return enhanced_results

        except ImportError as e:
            logger.error(f"Failed to import readthedocs_library.search_code: {e}")
            return []
        except Exception as e:
            logger.warning(f"Code example search failed: {e}")
            return []
    
    async def search_sparql_queries(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Search for relevant SPARQL queries from the SPARQL library.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of SPARQL query matches with metadata
        """
        try:
            # Check if SPARQL index exists
            sparql_lib_path = self.base_dir / "libraries" / "sparql_library"
            if not sparql_lib_path.exists():
                logger.warning("SPARQL library not found. Skipping SPARQL search.")
                return []
            
            # Import and call the search function directly
            try:
                # Add sparql_library to path temporarily
                import sys
                sparql_lib_str = str(sparql_lib_path)
                if sparql_lib_str not in sys.path:
                    sys.path.insert(0, sparql_lib_str)
                
                from retrieve import retrieve_sparql_queries
                results = retrieve_sparql_queries(query, top_k=top_k)
                
                # Enhance results with additional metadata
                enhanced_results = []
                for result in results:
                    enhanced_result = result.copy()
                    enhanced_result["result_type"] = "sparql_query"
                    enhanced_result["similarity_score"] = result.get("score", result.get("similarity", 0.0))
                    
                    # Standardize field names
                    if "description" not in enhanced_result and "name" in result:
                        enhanced_result["description"] = result["name"]
                    if "sparql" not in enhanced_result and "query" in result:
                        enhanced_result["sparql"] = result["query"]
                    
                    enhanced_results.append(enhanced_result)
                
                return enhanced_results
            except ImportError as e:
                logger.error(f"Failed to import SPARQL search functions: {e}")
                return []
            except Exception as e:
                logger.warning(f"SPARQL search failed: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching SPARQL queries: {e}")
            return []

    async def search_ontology_entities(self, query: str, top_k: int = 5, use_term_extraction: bool = True) -> List[Dict[str, Any]]:
        """
        Search for relevant ontology entities from the ontology library.
        
        Args:
            query: Search query
            top_k: Number of results to return
            use_term_extraction: Whether to use LLM-based term extraction for better results
            
        Returns:
            List of ontology entity matches with metadata
        """
        try:
            # Check if ontology library exists
            ontology_lib_path = self.base_dir / "libraries" / "ontology_library"
            if not ontology_lib_path.exists():
                logger.warning("Ontology library not found. Skipping ontology search.")
                return []
            
            # Use LLM-based term extraction for paleoclimate queries if enabled
            search_terms = [query]  # Default to using the original query
            
            if use_term_extraction:
                try:
                    # Import here to avoid circular imports
                    from services.service_manager import service_manager
                    from config import DEFAULT_LLM_PROVIDER
                    
                    # Get LLM for term extraction
                    llm = service_manager.get_llm_provider(DEFAULT_LLM_PROVIDER)
                    
                    # Extract paleoclimate terms using LLM (similar to extract_paleo_terms)
                    search_terms = self._extract_paleo_terms_for_search(llm, query)
                except Exception as e:
                    logger.warning(f"Term extraction failed, using original query: {e}")
                    search_terms = [query]
            
            # Import and call the search function directly
            try:
                # Add ontology_library to path temporarily
                import sys
                ontology_lib_str = str(ontology_lib_path)
                if ontology_lib_str not in sys.path:
                    sys.path.insert(0, ontology_lib_str)
                
                from search_ontology import search_entities
                
                # Search for entities using each extracted term
                all_matches = []
                for term in search_terms:
                    term_results = search_entities(term, limit=top_k)
                    all_matches.extend(term_results)
                
                # Remove duplicates based on entity URI/ID
                seen_uris = set()
                unique_matches = []
                for result in all_matches:
                    entity_id = result.get("entity_id", result.get("uri", ""))
                    if entity_id and entity_id not in seen_uris:
                        seen_uris.add(entity_id)
                        
                        # Enhance results with additional metadata
                        enhanced_result = result.copy()
                        enhanced_result["result_type"] = "ontology_entity"
                        enhanced_result["similarity_score"] = result.get("score", result.get("similarity", 0.0))
                        
                        # Ensure required fields exist
                        if "uri" not in enhanced_result and "entity_id" in result:
                            enhanced_result["uri"] = result["entity_id"]
                        if "label" not in enhanced_result and "name" in result:
                            enhanced_result["label"] = result["name"]
                        if "type" not in enhanced_result:
                            enhanced_result["type"] = "Unknown"
                        
                        unique_matches.append(enhanced_result)
                
                # Sort by similarity score and limit results
                unique_matches.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
                return unique_matches[:top_k]
                
            except ImportError as e:
                logger.error(f"Failed to import ontology search functions: {e}")
                return []
            except Exception as e:
                logger.warning(f"Ontology search failed: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching ontology entities: {e}")
            return []
    
    def _extract_paleo_terms_for_search(self, llm, user_query: str) -> List[str]:
        """
        Extract relevant paleoclimate terms from a user query using an LLM.
        Similar to the extract_paleo_terms function in SPARQL handlers.
        
        Args:
            llm: LLM model to use
            user_query: Raw user query
            
        Returns:
            List of extracted paleoclimate terms
        """
        try:
            # Import here to avoid circular imports
            from langchain.schema import HumanMessage, SystemMessage
            import json
            import re
            
            # Construct a prompt that asks the LLM to extract relevant terms
            prompt = f"""Analyze this paleoclimate query and extract key domain terms that may match ontology entities:

Query: "{user_query}"

Extract specialized terms like:
- Archive types (coral, ice core, speleothem, etc.)
- Variables (d18O, temperature, precipitation, etc.)  
- Units (permil, degrees Celsius, etc.)
- Proxy types (radiocarbon, alkenone, etc.)
- Geographic locations (Pacific Ocean, Atlantic, etc.)

Return ONLY a JSON array of the extracted terms:
["term1", "term2", "term3"]
"""

            # Generate the extraction using LangChain message types
            messages = [
                SystemMessage(content="You are a paleoclimate data expert. Extract only the relevant terms without explanation."),
                HumanMessage(content=prompt)
            ]
            
            # Execute LLM directly with the prompt
            response = llm._call(messages).strip()

            # Extract JSON from the response
            json_pattern = re.compile(r'\[\s*".*"\s*\]', re.DOTALL)
            match = json_pattern.search(response)

            terms = []
            if match:
                try:
                    terms = json.loads(match.group(0))
                except Exception as e:
                    logger.warning(f"Error parsing LLM output as JSON: {str(e)}")
                    # Fallback: try to find JSON with more relaxed pattern
                    match = re.search(r'(\[.*\])', response, re.DOTALL)
                    if match:
                        try:
                            terms = json.loads(match.group(1))
                        except Exception as e:
                            logger.warning(f"Error parsing with relaxed pattern: {str(e)}")

            logger.info(f"Extracted paleo terms: {terms}")
            return terms if terms else [user_query]
            
        except Exception as e:
            logger.error(f"Error extracting paleo terms: {e}")
            # Return the user query as a single term as fallback
            return [user_query]
    
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
        workflows = await self.search_notebook_workflows(user_query, top_k=3)
        
        # Search methods with lower weight (for loose guidance)
        methods = await self.search_literature_methods(user_query, top_k=5)
        
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
        snippets = await self.search_snippets(user_query, top_k=2)
        
        # Search documentation (important for API usage)
        # documentation = await self.search_documentation(user_query, top_k=1)
        
        # Search code examples (important for patterns)
        code_examples = await self.search_code_examples(user_query, top_k=5)
        
        return {
            "snippets": snippets,
            # "documentation": documentation,
            "code_examples": code_examples,
            "previous_code": previous_code,
            "query": user_query
        }
    
    async def get_context_for_sparql_generation(self, user_query: str) -> Dict[str, Any]:
        """
        Get comprehensive context for SPARQL query generation by searching
        similar SPARQL queries and ontology entities.
        
        Args:
            user_query: The user's request for SPARQL query generation
            
        Returns:
            Dictionary containing SPARQL generation context
        """
        # Search similar SPARQL queries (high weight)
        similar_queries = await self.search_sparql_queries(user_query, top_k=3)
        
        # Search ontology entities (important for entity matching)
        entities = await self.search_ontology_entities(user_query, top_k=5)
        
        return {
            "similar_queries": similar_queries,
            "entities": entities,
            "query": user_query
        }
    
    def format_workflow_context_for_llm(self, context: Dict[str, Any]) -> str:
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
                sections.append(f"**Steps**: {workflow.get('num_steps', workflow.get('step_count', 'Unknown'))}")
                sections.append(f"**Type**: {workflow.get('workflow_type', 'general')}")
                sections.append(f"**Complexity**: {workflow.get('complexity', 'simple')}")
                
                # Get workflow steps from either workflow_steps or steps field
                workflow_steps = workflow.get("workflow_steps", workflow.get("steps", []))
                if workflow_steps:
                    sections.append("**Step Breakdown**:")
                    for step in workflow_steps:
                        # Handle different step formats - some have step_number, description, etc.
                        step_desc = step.get("description", step.get("step_description", ""))
                        step_num = step.get("step_number", "")
                        step_type = step.get("step_type", "")
                        if step_num:
                            sections.append(f"- Step {step_num}: {step_desc}")
                        elif step_type:
                            sections.append(f"- [{step_type}] {step_desc}")
                        else:
                            sections.append(f"- {step_desc}")
                
                if workflow.get("description"):
                    sections.append(f"**Description**: {workflow['description']}")
                    
                sections.append("")  # Add spacing
        
        # Add method context (lower weight) - now using complete methods
        if context.get("methods"):
            sections.append("## RELEVANT SCIENTIFIC METHODS (Lower Priority - Use as Loose Guidance):\n")
            for i, method in enumerate(context["methods"], 1):
                sections.append(f"### Method {i}: {method.get('method_name', 'Unknown')}")
                sections.append(f"**From Paper**: {method.get('paper_title', 'Unknown')}")
                sections.append(f"**Similarity**: {method.get('similarity_score', 0):.3f}")
                sections.append(f"**Steps**: {method.get('num_steps', 'Unknown')}")
                
                # Get method description
                if method.get("description"):
                    sections.append(f"**Summary**: {method['description']}")
                elif method.get("method_description"):
                    sections.append(f"**Summary**: {method['method_description']}")
                
                # Get step categories from the complete method
                if method.get("step_categories"):
                    sections.append(f"**Categories**: {', '.join(method['step_categories'])}")
                elif method.get("category"):
                    sections.append(f"**Category**: {method['category']}")
                
                # Show step breakdown from method structure
                method_structure = method.get("method_structure", {})
                steps = method_structure.get("steps", method.get("steps", []))
                if steps:
                    sections.append("**Method Steps**:")
                    for step in steps[:5]:  # Show first 5 steps
                        step_num = step.get("step_number", "")
                        step_cat = step.get("category", "")
                        step_summary = step.get("searchable_summary", step.get("summary", ""))
                        step_desc = step.get("description", "")
                        
                        if step_num and step_cat:
                            sections.append(f"- Step {step_num} [{step_cat}]: {step_summary or step_desc}")
                        elif step_cat:
                            sections.append(f"- [{step_cat}] {step_summary or step_desc}")
                        else:
                            sections.append(f"- {step_summary or step_desc}")
                    
                    if len(steps) > 5:
                        sections.append(f"... and {len(steps) - 5} more steps")
                    
                sections.append("")  # Add spacing
        
        return "\n".join(sections)
    
    def format_code_context_for_llm(self, context: Dict[str, Any]) -> str:
        """
        Format the code generation context into a text prompt for the LLM.
        
        Args:
            context: Context from get_context_for_code_generation or generate_code_node
            
        Returns:
            Formatted text for LLM consumption
        """
        sections = []
        
        # Add refinement context first if this is a refinement request (highest priority)
        if context.get("refinement_context"):
            refinement_ctx = context["refinement_context"]
            sections.append("## REFINEMENT CONTEXT (Highest Priority - Build Upon This):\n")
            
            previous_agent_type = refinement_ctx.get("previous_agent_type", "unknown")
            
            if refinement_ctx.get("previous_query"):
                # Handle different agent types appropriately
                if previous_agent_type == "sparql":
                    sections.append("### Previous SPARQL Query:")
                    sections.append("```sparql")
                    sections.append(refinement_ctx["previous_query"])
                    sections.append("```")
                elif previous_agent_type == "code":
                    sections.append("### Previous Generated Code:")
                    sections.append("```python")
                    sections.append(refinement_ctx["previous_query"])
                    sections.append("```")
                else:
                    sections.append("### Previous Query/Code:")
                    sections.append("```")
                    sections.append(refinement_ctx["previous_query"])
                    sections.append("```")
                sections.append("")
            
            if refinement_ctx.get("previous_results"):
                prev_results = refinement_ctx["previous_results"]
                sections.append("### Previous Results:")
                sections.append(f"**Result count**: {len(prev_results)}")
                
                # Show a sample of previous results for context
                if prev_results and len(prev_results) > 0:
                    sections.append("**Sample results** (use these in your code):")
                    import json
                    try:
                        # Show first few results as examples
                        sample_results = prev_results[:3] if len(prev_results) > 3 else prev_results
                        for i, result in enumerate(sample_results, 1):
                            sections.append(f"Result {i}: {json.dumps(result, indent=2)}")
                        if len(prev_results) > 3:
                            sections.append(f"... and {len(prev_results) - 3} more results")
                    except Exception as e:
                        sections.append(f"Previous results available but could not display: {str(e)}")
                sections.append("")
            
            if refinement_ctx.get("refinement_request"):
                sections.append("### User's Refinement Request:")
                sections.append(refinement_ctx["refinement_request"])
                sections.append("")
        
        # Add previous code context (highest priority for regular requests)
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

    def format_sparql_context_for_llm(self, context: Dict[str, Any]) -> str:
        """
        Format the SPARQL generation context into a text prompt for the LLM.
        
        Args:
            context: Context from get_context_for_sparql_generation or generate_query_node
            
        Returns:
            Formatted text for LLM consumption
        """
        sections = []
        
        # Add refinement context first if this is a refinement request (highest priority)
        if context.get("refinement_context"):
            refinement_ctx = context["refinement_context"]
            sections.append("## REFINEMENT CONTEXT (Highest Priority - Use This for Context):\n")
            
            if refinement_ctx.get("previous_query"):
                sections.append("### Previous SPARQL Query:")
                sections.append("```sparql")
                sections.append(refinement_ctx["previous_query"])
                sections.append("```")
                sections.append("")
            
            if refinement_ctx.get("previous_results"):
                prev_results = refinement_ctx["previous_results"]
                sections.append("### Previous Query Results:")
                sections.append(f"**Result count**: {len(prev_results)}")
                
                # Show a sample of previous results for context
                if prev_results and len(prev_results) > 0:
                    sections.append("**Sample results** (for context):")
                    import json
                    try:
                        # Show first few results as examples
                        sample_results = prev_results[:3] if len(prev_results) > 3 else prev_results
                        for i, result in enumerate(sample_results, 1):
                            sections.append(f"Result {i}: {json.dumps(result, indent=2)}")
                        if len(prev_results) > 3:
                            sections.append(f"... and {len(prev_results) - 3} more results")
                    except Exception as e:
                        sections.append(f"Previous results available but could not display: {str(e)}")
                sections.append("")
            
            if refinement_ctx.get("refinement_request"):
                sections.append("### User's Refinement Request:")
                sections.append(refinement_ctx["refinement_request"])
                sections.append("")
        
        # Add similar SPARQL queries (high weight)
        if context.get("similar_queries"):
            sections.append("## RELEVANT SPARQL QUERIES (High Priority - Use These Queries):\n")
            for i, query in enumerate(context["similar_queries"], 1):
                sections.append(f"### Query {i}: {query.get('description', 'Unknown')}")
                sections.append(f"**Similarity**: {query.get('similarity_score', 0):.3f}")
                
                if query.get("sparql"):
                    sections.append("**Query**:")
                    sections.append("```sparql")
                    sections.append(query["sparql"])
                    sections.append("```")
                
                sections.append("")  # Add spacing
        
        # Add ontology entities (important for entity matching)
        if context.get("entities"):
            sections.append("## RELEVANT ONTOLOGY ENTITIES (Important - Use These Entities):\n")
            for i, entity in enumerate(context["entities"], 1):
                sections.append(f"### Entity {i}: {entity.get('label', 'Unknown')}")
                sections.append(f"**Similarity**: {entity.get('similarity_score', 0):.3f}")
                
                if entity.get("uri"):
                    sections.append("**URI**:")
                    sections.append(entity["uri"])
                
                if entity.get("type"):
                    sections.append("**Type**:")
                    sections.append(entity["type"])
                
                sections.append("")  # Add spacing
        
        return "\n".join(sections)


# Global instance
search_service = SearchIntegrationService() 