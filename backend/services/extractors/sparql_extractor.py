"""
SPARQL extractor for markdown files and notebooks.
Extracts SPARQL queries that can be indexed.
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base_extractor import BaseExtractor

class SPARQLExtractor(BaseExtractor):
    """
    Extractor for SPARQL queries from markdown files and notebooks.
    Produces query JSONs ready for indexing.
    """
    
    def _get_file_suffix(self) -> str:
        return ".md"
    
    async def extract_from_file(
        self, 
        file_path: Path, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract SPARQL queries from a file.
        
        Args:
            file_path: Path to file (.md, .markdown, .ipynb)
            params: Extraction parameters:
                - include_comments: Whether to include comment context (default: True)
                - validate_syntax: Whether to validate SPARQL syntax (default: False)
                - min_query_length: Minimum query length to include (default: 20)
                - query_types: List of query types to include (SELECT, CONSTRUCT, ASK, DESCRIBE)
        
        Returns:
            List of extracted SPARQL query objects
        """
        self.logger.info(f"Extracting SPARQL queries from: {file_path}")
        
        # Get parameters
        include_comments = params.get('include_comments', True)
        validate_syntax = params.get('validate_syntax', False)
        min_query_length = params.get('min_query_length', 20)
        query_types = params.get('query_types', ['SELECT', 'CONSTRUCT', 'ASK', 'DESCRIBE'])
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        extracted_data = []
        
        # Determine file type and extract accordingly
        if file_path.suffix.lower() == '.ipynb':
            queries = self._extract_from_notebook(content, params)
        else:
            queries = self._extract_from_markdown(content, params)
        
        # Process and validate queries
        for idx, query_info in enumerate(queries):
            query_text = query_info['query']
            
            # Skip short queries
            if len(query_text) < min_query_length:
                continue
            
            # Check query type
            query_type = self._detect_query_type(query_text)
            if query_type not in query_types:
                continue
            
            # Validate syntax if requested
            if validate_syntax and not self._validate_sparql_syntax(query_text):
                self.logger.warning(f"Invalid SPARQL syntax in query {idx}")
                continue
            
            # Extract query components
            components = self._analyze_query_components(query_text)
            
            query_data = {
                'content_type': 'sparql_query',
                'source_file': str(file_path),
                'query': query_text,
                'query_type': query_type,
                'query_id': f"query_{idx}",
                'extraction_type': 'sparql_query'
            }
            
            # Add context if available
            if include_comments and query_info.get('context'):
                query_data['context'] = query_info['context']
            
            # Add query components
            query_data.update(components)
            
            # Add metadata from notebook cells if available
            if query_info.get('cell_metadata'):
                query_data['cell_metadata'] = query_info['cell_metadata']
            
            extracted_data.append(query_data)
        
        self.logger.info(f"Extracted {len(extracted_data)} SPARQL queries")
        return self._clean_extracted_data(extracted_data)
    
    def _extract_from_markdown(self, content: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract SPARQL queries from markdown content."""
        queries = []
        
        # Pattern to match code blocks with SPARQL
        sparql_block_pattern = r'```(?:sparql|sql|rql)?\s*(.*?)```'
        
        # Find all code blocks
        blocks = re.finditer(sparql_block_pattern, content, re.DOTALL | re.IGNORECASE)
        
        for block in blocks:
            block_content = block.group(1).strip()
            
            # Check if it looks like SPARQL
            if self._looks_like_sparql(block_content):
                # Get surrounding context
                context = self._get_markdown_context(content, block.start(), block.end())
                
                queries.append({
                    'query': block_content,
                    'context': context
                })
        
        # Also look for inline SPARQL patterns (without code blocks)
        inline_patterns = [
            r'SELECT\s+.*?WHERE\s*\{.*?\}',
            r'CONSTRUCT\s*\{.*?\}\s*WHERE\s*\{.*?\}',
            r'ASK\s+WHERE\s*\{.*?\}',
            r'DESCRIBE\s+.*?WHERE\s*\{.*?\}'
        ]
        
        for pattern in inline_patterns:
            matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                query_text = match.group(0).strip()
                
                # Avoid duplicates from code blocks
                if not any(query_text in q['query'] for q in queries):
                    context = self._get_markdown_context(content, match.start(), match.end())
                    
                    queries.append({
                        'query': query_text,
                        'context': context
                    })
        
        return queries
    
    def _extract_from_notebook(self, content: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract SPARQL queries from Jupyter notebook content."""
        queries = []
        
        try:
            notebook = json.loads(content)
            cells = notebook.get('cells', [])
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON in notebook file")
            return []
        
        for cell_idx, cell in enumerate(cells):
            cell_type = cell.get('cell_type', '')
            cell_source = cell.get('source', [])
            
            # Convert source to string
            if isinstance(cell_source, list):
                cell_content = ''.join(cell_source)
            else:
                cell_content = str(cell_source)
            
            # Look for SPARQL in code cells
            if cell_type == 'code':
                sparql_queries = self._extract_sparql_from_code_cell(cell_content)
                
                for query in sparql_queries:
                    queries.append({
                        'query': query,
                        'context': f"Code cell {cell_idx}",
                        'cell_metadata': {
                            'cell_index': cell_idx,
                            'cell_type': cell_type,
                            'execution_count': cell.get('execution_count')
                        }
                    })
            
            # Look for SPARQL in markdown cells
            elif cell_type == 'markdown':
                md_queries = self._extract_from_markdown(cell_content, params)
                
                for query_info in md_queries:
                    query_info['context'] = f"Markdown cell {cell_idx}: {query_info.get('context', '')}"
                    query_info['cell_metadata'] = {
                        'cell_index': cell_idx,
                        'cell_type': cell_type
                    }
                    queries.append(query_info)
        
        return queries
    
    def _extract_sparql_from_code_cell(self, cell_content: str) -> List[str]:
        """Extract SPARQL queries from a code cell."""
        queries = []
        
        # Look for string assignments or variables containing SPARQL
        string_patterns = [
            r'["\']([^"\']*(?:SELECT|CONSTRUCT|ASK|DESCRIBE)[^"\']*)["\']',
            r'query\s*=\s*["\']([^"\']*)["\']',
            r'sparql\s*=\s*["\']([^"\']*)["\']'
        ]
        
        for pattern in string_patterns:
            matches = re.finditer(pattern, cell_content, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                potential_query = match.group(1)
                if self._looks_like_sparql(potential_query):
                    queries.append(potential_query)
        
        # Look for triple-quoted strings
        triple_quote_pattern = r'"""(.*?)"""'
        matches = re.finditer(triple_quote_pattern, cell_content, re.DOTALL)
        
        for match in matches:
            potential_query = match.group(1).strip()
            if self._looks_like_sparql(potential_query):
                queries.append(potential_query)
        
        # Look for raw queries (not in strings)
        if self._looks_like_sparql(cell_content):
            queries.append(cell_content)
        
        return queries
    
    def _looks_like_sparql(self, text: str) -> bool:
        """Check if text looks like a SPARQL query."""
        text_upper = text.upper()
        
        # Must contain a SPARQL keyword
        sparql_keywords = ['SELECT', 'CONSTRUCT', 'ASK', 'DESCRIBE']
        has_keyword = any(keyword in text_upper for keyword in sparql_keywords)
        
        if not has_keyword:
            return False
        
        # Should contain WHERE or have CONSTRUCT structure
        has_where = 'WHERE' in text_upper
        has_construct = 'CONSTRUCT' in text_upper and '{' in text
        
        # Should contain RDF patterns (curly braces)
        has_patterns = '{' in text and '}' in text
        
        return (has_where or has_construct) and has_patterns
    
    def _detect_query_type(self, query: str) -> str:
        """Detect the type of SPARQL query."""
        query_upper = query.upper()
        
        if query_upper.strip().startswith('SELECT'):
            return 'SELECT'
        elif query_upper.strip().startswith('CONSTRUCT'):
            return 'CONSTRUCT'
        elif query_upper.strip().startswith('ASK'):
            return 'ASK'
        elif query_upper.strip().startswith('DESCRIBE'):
            return 'DESCRIBE'
        
        return 'UNKNOWN'
    
    def _validate_sparql_syntax(self, query: str) -> bool:
        """Validate SPARQL syntax (basic validation)."""
        try:
            # Try to import and use a SPARQL parser if available
            try:
                from rdflib.plugins.sparql import prepareQuery
                prepareQuery(query)
                return True
            except ImportError:
                # Fallback to basic syntax checking
                return self._basic_sparql_validation(query)
        except:
            return False
    
    def _basic_sparql_validation(self, query: str) -> bool:
        """Basic SPARQL syntax validation without external dependencies."""
        query_upper = query.upper()
        
        # Check for basic structure
        if 'SELECT' in query_upper:
            return 'WHERE' in query_upper and '{' in query and '}' in query
        elif 'CONSTRUCT' in query_upper:
            return '{' in query and '}' in query and query.count('{') >= 2
        elif 'ASK' in query_upper:
            return 'WHERE' in query_upper and '{' in query and '}' in query
        elif 'DESCRIBE' in query_upper:
            return True  # DESCRIBE can be simple
        
        return False
    
    def _analyze_query_components(self, query: str) -> Dict[str, Any]:
        """Analyze SPARQL query components."""
        components = {}
        
        # Extract prefixes
        prefixes = re.findall(r'PREFIX\s+(\w+):\s*<([^>]+)>', query, re.IGNORECASE)
        if prefixes:
            components['prefixes'] = {prefix: uri for prefix, uri in prefixes}
        
        # Extract variables (for SELECT queries)
        if query.upper().strip().startswith('SELECT'):
            variables = re.findall(r'\?(\w+)', query)
            components['variables'] = list(set(variables))
        
        # Extract graph patterns
        graph_patterns = self._extract_graph_patterns(query)
        if graph_patterns:
            components['graph_patterns'] = graph_patterns
        
        # Count triples approximately
        triple_count = query.count('.') + query.count(';')
        components['estimated_triple_count'] = triple_count
        
        return components
    
    def _extract_graph_patterns(self, query: str) -> List[str]:
        """Extract graph patterns from SPARQL query."""
        patterns = []
        
        # Find WHERE clause
        where_match = re.search(r'WHERE\s*\{(.*)\}', query, re.DOTALL | re.IGNORECASE)
        if where_match:
            where_content = where_match.group(1)
            
            # Split on . or ; to get individual patterns
            pattern_splits = re.split(r'[.;]', where_content)
            
            for pattern in pattern_splits:
                pattern = pattern.strip()
                if pattern and '?' in pattern:  # Has variables
                    patterns.append(pattern)
        
        return patterns[:10]  # Limit to first 10 patterns
    
    def _get_markdown_context(self, content: str, start_pos: int, end_pos: int) -> str:
        """Get surrounding context for a match in markdown."""
        lines = content[:start_pos].split('\n')
        
        # Look for preceding headings
        context_parts = []
        
        for line in reversed(lines[-10:]):  # Look at last 10 lines
            line = line.strip()
            if line.startswith('#'):
                context_parts.append(line)
                break
            elif line and not line.startswith('```'):
                context_parts.append(line)
        
        context_parts.reverse()
        return ' | '.join(context_parts) if context_parts else ""
    
    async def extract_from_url(
        self, 
        url: str, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract SPARQL queries from a URL.
        """
        self.logger.info(f"Extracting SPARQL from URL: {url}")
        
        # Download and delegate to file extraction
        import aiohttp
        import tempfile
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Determine file type from URL
                    file_extension = '.md'
                    if url.endswith('.ipynb'):
                        file_extension = '.ipynb'
                    elif url.endswith('.markdown'):
                        file_extension = '.markdown'
                    
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension, mode='w', encoding='utf-8') as temp_file:
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
                    raise Exception(f"Failed to download from {url}: {response.status}")
    
    def get_extraction_preview(self, file_path: Path) -> Dict[str, Any]:
        """
        Get a preview of what would be extracted without full processing.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Quick scan for SPARQL-like content
            sparql_keywords = ['SELECT', 'CONSTRUCT', 'ASK', 'DESCRIBE']
            keyword_counts = {}
            
            for keyword in sparql_keywords:
                keyword_counts[keyword] = len(re.findall(keyword, content, re.IGNORECASE))
            
            # Look for code blocks
            code_blocks = len(re.findall(r'```', content))
            
            # Estimate queries
            total_keywords = sum(keyword_counts.values())
            estimated_queries = max(1, total_keywords)
            
            # Check if it's a notebook
            is_notebook = file_path.suffix.lower() == '.ipynb'
            if is_notebook:
                try:
                    notebook = json.loads(content)
                    cells = notebook.get('cells', [])
                    code_cells = len([c for c in cells if c.get('cell_type') == 'code'])
                    markdown_cells = len([c for c in cells if c.get('cell_type') == 'markdown'])
                except:
                    code_cells = 0
                    markdown_cells = 0
            else:
                code_cells = 0
                markdown_cells = 0
            
            return {
                "file_type": "notebook" if is_notebook else "markdown",
                "keyword_counts": keyword_counts,
                "code_blocks": code_blocks // 2,  # Divide by 2 since ``` comes in pairs
                "estimated_queries": estimated_queries,
                "total_characters": len(content),
                "notebook_cells": {
                    "code_cells": code_cells,
                    "markdown_cells": markdown_cells
                } if is_notebook else None,
                "extraction_feasible": total_keywords > 0
            }
        
        except Exception as e:
            return {"error": str(e)} 