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
        # Convert file_path to Path object if it's a string
        if isinstance(file_path, str):
            file_path = Path(file_path)
        
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
            
            # Check query type (use the already detected type from markdown extraction if available)
            query_type = query_info.get('query_type', self._detect_query_type(query_text))
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
                'sparql_query': query_text,  # Also add as sparql_query for compatibility with working system
                'query_type': query_type,
                'query_id': f"query_{idx}",
                'extraction_type': 'sparql_query'
            }
            
            # Add structured data if available (from improved markdown extraction)
            if query_info.get('title'):
                query_data['title'] = query_info['title']
            if query_info.get('description'):
                query_data['description'] = query_info['description']
            if query_info.get('concepts'):
                query_data['concepts'] = query_info['concepts']
            if query_info.get('search_text'):
                query_data['text'] = query_info['search_text']  # For Qdrant indexing
            
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
        """Extract SPARQL queries from markdown content using the same pattern as the working loader."""
        queries = []
        
        # Use the same pattern as the working SparqlQueryParser
        # Pattern to match query blocks: ### QUERY_NAME followed by Description and SPARQL code
        structured_pattern = r'###\s+([A-Z_]+)\s+Description:\s+(.*?)```sparql\s+(.*?)```'
        matches = re.finditer(structured_pattern, content, re.DOTALL)
        
        for match in matches:
            title = match.group(1).strip()
            description = match.group(2).strip()
            sparql_query = match.group(3).strip()
            
            # Create search text combining title, description and query
            search_text = f"{title} {description} {sparql_query}"
            
            # Extract query type
            query_type = "SELECT"
            if re.search(r'\bCONSTRUCT\b', sparql_query, re.IGNORECASE):
                query_type = "CONSTRUCT"
            elif re.search(r'\bASK\b', sparql_query, re.IGNORECASE):
                query_type = "ASK"
            elif re.search(r'\bDESCRIBE\b', sparql_query, re.IGNORECASE):
                query_type = "DESCRIBE"
            
            # Extract key concepts from query
            concepts = []
            # Common LiPD/paleoclimate concepts
            concept_patterns = [
                r'\b(temperature|precipitation|chronology|age|depth)\b',
                r'\b(proxy|archive|paleoenvironment|climate)\b',
                r'\b(dataset|publication|author|location)\b',
                r'\b(measurement|value|variable|unit)\b'
            ]
            
            for pattern in concept_patterns:
                concept_matches = re.findall(pattern, search_text, re.IGNORECASE)
                concepts.extend([m.lower() for m in concept_matches])
            
            concepts = list(set(concepts))  # Remove duplicates
            
            queries.append({
                'query': sparql_query,
                'context': f"Title: {title}",
                'title': title,
                'description': description,
                'query_type': query_type,
                'concepts': concepts,
                'search_text': search_text
            })
        
        # Fallback: if no structured queries found, try generic code blocks
        if not queries:
            sparql_block_pattern = r'```(?:sparql|sql|rql)?\s*(.*?)```'
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
        
        return queries
    
    def _extract_from_notebook(self, content: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract SPARQL queries from Jupyter notebook content with enhanced context analysis."""
        queries = []
        
        try:
            notebook = json.loads(content)
            cells = notebook.get('cells', [])
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON in notebook file")
            return []
        
        # Pre-process cells to build context map
        cell_contexts = self._build_notebook_context_map(cells)
        
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
                sparql_queries = self._extract_sparql_from_code_cell(cell_content, cell_idx)
                
                for query_info in sparql_queries:
                    # Enhance with notebook context
                    enhanced_context = self._get_enhanced_notebook_context(
                        cell_idx, cells, cell_contexts, query_info.get('variable_name')
                    )
                    
                    query_data = {
                        'query': query_info['query'],
                        'context': enhanced_context['context'],
                        'title': enhanced_context['title'],
                        'description': enhanced_context['description'],
                        'query_type': self._detect_query_type(query_info['query']),
                        'concepts': self._extract_notebook_concepts(enhanced_context, query_info['query']),
                        'search_text': f"{enhanced_context['title']} {enhanced_context['description']} {query_info['query']}",
                        'cell_metadata': {
                            'cell_index': cell_idx,
                            'cell_type': cell_type,
                            'execution_count': cell.get('execution_count'),
                            'variable_name': query_info.get('variable_name'),
                            'extraction_method': query_info.get('method'),
                            'surrounding_cells': enhanced_context['surrounding_cells']
                        }
                    }
                    queries.append(query_data)
            
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
    
    def _extract_sparql_from_code_cell(self, cell_content: str, cell_idx: int) -> List[Dict[str, Any]]:
        """Extract SPARQL queries from a code cell with metadata."""
        queries = []
        
        # Method 1: Look for variable assignments with SPARQL
        variable_patterns = [
            r'(\w*query\w*)\s*=\s*["\']([^"\']*?(?:SELECT|CONSTRUCT|ASK|DESCRIBE)[^"\']*?)["\']',
            r'(\w*sparql\w*)\s*=\s*["\']([^"\']*?)["\']',
            r'(\w+)\s*=\s*["\']([^"\']*?(?:PREFIX|SELECT|CONSTRUCT|ASK|DESCRIBE)[^"\']*?)["\']'
        ]
        
        for pattern in variable_patterns:
            matches = re.finditer(pattern, cell_content, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                variable_name = match.group(1)
                potential_query = match.group(2)
                if self._looks_like_sparql(potential_query):
                    queries.append({
                        'query': potential_query.strip(),
                        'variable_name': variable_name,
                        'method': 'variable_assignment',
                        'cell_index': cell_idx
                    })
        
        # Method 2: Look for triple-quoted strings (multiline)
        triple_quote_patterns = [
            r'(\w*)\s*=\s*"""(.*?)"""',  # variable = """..."""
            r'"""(.*?)"""'  # standalone """..."""
        ]
        
        for pattern in triple_quote_patterns:
            matches = re.finditer(pattern, cell_content, re.DOTALL)
            
            for match in matches:
                if len(match.groups()) == 2:
                    # Variable assignment
                    variable_name = match.group(1) or 'anonymous'
                    potential_query = match.group(2).strip()
                else:
                    # Standalone
                    variable_name = 'anonymous'
                    potential_query = match.group(1).strip()
                
                if self._looks_like_sparql(potential_query):
                    queries.append({
                        'query': potential_query,
                        'variable_name': variable_name,
                        'method': 'triple_quoted_string',
                        'cell_index': cell_idx
                    })
        
        # Method 3: Look for single-quoted multiline strings
        single_quote_multiline = r"(\w*)\s*=\s*'([^']*(?:PREFIX|SELECT|CONSTRUCT|ASK|DESCRIBE)[^']*?)'"
        matches = re.finditer(single_quote_multiline, cell_content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            variable_name = match.group(1) or 'anonymous'
            potential_query = match.group(2).strip()
            if self._looks_like_sparql(potential_query):
                queries.append({
                    'query': potential_query,
                    'variable_name': variable_name,
                    'method': 'single_quoted_multiline',
                    'cell_index': cell_idx
                })
        
        # Method 4: Look for f-strings or formatted strings
        f_string_pattern = r'f["\']([^"\']*(?:PREFIX|SELECT|CONSTRUCT|ASK|DESCRIBE)[^"\']*?)["\']'
        matches = re.finditer(f_string_pattern, cell_content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            potential_query = match.group(1).strip()
            if self._looks_like_sparql(potential_query):
                queries.append({
                    'query': potential_query,
                    'variable_name': 'f_string',
                    'method': 'f_string',
                    'cell_index': cell_idx
                })
        
        # Method 5: Look for raw cell content that might be pure SPARQL
        if self._looks_like_sparql(cell_content.strip()) and not queries:
            queries.append({
                'query': cell_content.strip(),
                'variable_name': 'raw_cell',
                'method': 'raw_cell_content',
                'cell_index': cell_idx
            })
        
        # Remove duplicate queries (same query content from same cell)
        unique_queries = []
        seen_queries = set()
        
        for query_info in queries:
            # Create a key to identify duplicates
            query_key = (query_info['cell_index'], query_info['query'].strip())
            
            if query_key not in seen_queries:
                seen_queries.add(query_key)
                unique_queries.append(query_info)
        
        return unique_queries
    
    def _build_notebook_context_map(self, cells: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """Build a map of notebook cells with their content and types for context analysis."""
        context_map = {}
        
        for idx, cell in enumerate(cells):
            cell_type = cell.get('cell_type', '')
            cell_source = cell.get('source', [])
            
            # Convert source to string
            if isinstance(cell_source, list):
                cell_content = ''.join(cell_source)
            else:
                cell_content = str(cell_source)
            
            context_map[idx] = {
                'type': cell_type,
                'content': cell_content,
                'is_heading': self._is_heading_cell(cell_content, cell_type),
                'heading_level': self._get_heading_level(cell_content, cell_type),
                'has_sparql_keywords': any(keyword in cell_content.upper() for keyword in ['SPARQL', 'QUERY', 'PREFIX', 'SELECT'])
            }
        
        return context_map
    
    def _is_heading_cell(self, content: str, cell_type: str) -> bool:
        """Check if a cell is a heading."""
        if cell_type == 'markdown':
            stripped = content.strip()
            return stripped.startswith('#') or any(keyword.lower() in stripped.lower() 
                                                 for keyword in ['query', 'sparql', 'complex', 'custom'])
        return False
    
    def _get_heading_level(self, content: str, cell_type: str) -> int:
        """Get the heading level (1-6) for markdown cells."""
        if cell_type == 'markdown':
            stripped = content.strip()
            if stripped.startswith('#'):
                level = 0
                for char in stripped:
                    if char == '#':
                        level += 1
                    else:
                        break
                return min(level, 6)
        return 0
    
    def _get_enhanced_notebook_context(
        self, 
        cell_idx: int, 
        cells: List[Dict[str, Any]], 
        cell_contexts: Dict[int, Dict[str, Any]],
        variable_name: str = None
    ) -> Dict[str, Any]:
        """Get enhanced context for a SPARQL query found in a notebook cell."""
        
        # Look for the most recent heading
        title = ""
        description = ""
        context_parts = []
        surrounding_cells = []
        
        # Look backwards for headings and relevant context
        for i in range(cell_idx - 1, max(-1, cell_idx - 10), -1):
            if i in cell_contexts:
                cell_info = cell_contexts[i]
                
                # Track surrounding cells
                if cell_info['type'] == 'markdown':
                    surrounding_cells.append({
                        'index': i,
                        'type': cell_info['type'],
                        'content': cell_info['content'][:200] + "..." if len(cell_info['content']) > 200 else cell_info['content']
                    })
                
                # Look for the most recent heading
                if cell_info['is_heading'] and not title:
                    title = self._extract_title_from_markdown(cell_info['content'])
                    
                # Collect description from nearby markdown cells
                elif cell_info['type'] == 'markdown' and len(description) < 500:
                    cell_desc = self._extract_description_from_markdown(cell_info['content'])
                    if cell_desc:
                        description = cell_desc + " " + description
        
        # Look forward for additional context
        for i in range(cell_idx + 1, min(len(cells), cell_idx + 5)):
            if i in cell_contexts:
                cell_info = cell_contexts[i]
                if cell_info['type'] == 'markdown':
                    surrounding_cells.append({
                        'index': i,
                        'type': cell_info['type'],
                        'content': cell_info['content'][:200] + "..." if len(cell_info['content']) > 200 else cell_info['content']
                    })
        
        # Fallback title
        if not title:
            if variable_name and variable_name != 'anonymous':
                title = f"SPARQL Query: {variable_name}"
            else:
                title = f"SPARQL Query in Cell {cell_idx}"
        
        # Fallback description
        if not description:
            description = f"SPARQL query extracted from notebook cell {cell_idx}"
        
        # Create context string
        context_parts = [f"Notebook cell {cell_idx}"]
        if variable_name and variable_name != 'anonymous':
            context_parts.append(f"Variable: {variable_name}")
        if title:
            context_parts.append(f"Section: {title}")
        
        return {
            'title': title.strip(),
            'description': description.strip(),
            'context': " | ".join(context_parts),
            'surrounding_cells': surrounding_cells
        }
    
    def _extract_title_from_markdown(self, content: str) -> str:
        """Extract title from markdown content."""
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                # Remove # characters and clean up
                title = re.sub(r'^#+\s*', '', line).strip()
                return title
        return ""
    
    def _extract_description_from_markdown(self, content: str) -> str:
        """Extract description from markdown content."""
        # Remove markdown formatting and get clean text
        lines = content.strip().split('\n')
        description_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip empty lines and headers
            if not line or line.startswith('#'):
                continue
            # Remove markdown formatting
            clean_line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)  # Bold
            clean_line = re.sub(r'\*([^*]+)\*', r'\1', clean_line)  # Italic
            clean_line = re.sub(r'`([^`]+)`', r'\1', clean_line)  # Code
            clean_line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean_line)  # Links
            
            if clean_line:
                description_lines.append(clean_line)
                
            # Limit description length
            if len(' '.join(description_lines)) > 300:
                break
        
        return ' '.join(description_lines)
    
    def _extract_notebook_concepts(self, context: Dict[str, Any], query: str) -> List[str]:
        """Extract concepts from notebook context and SPARQL query."""
        concepts = []
        
        # Combine all text for concept extraction
        all_text = f"{context['title']} {context['description']} {query}"
        
        # Common SPARQL/RDF concepts
        sparql_patterns = [
            r'\b(prefix|select|construct|ask|describe|where|filter|optional|union|graph)\b',
            r'\b(dataset|variable|measurement|location|archive|proxy)\b',
            r'\b(temperature|precipitation|age|depth|chronology|climate)\b',
            r'\b(paleoclimate|paleoenvironment|timeseries|compilation)\b',
            r'\b(rdf|ontology|linkedearth|lipd|sparql)\b'
        ]
        
        for pattern in sparql_patterns:
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            concepts.extend([m.lower() for m in matches])
        
        # Remove duplicates and common words
        concepts = list(set(concepts))
        concepts = [c for c in concepts if len(c) > 2 and c not in ['the', 'and', 'for', 'with']]
        
        return concepts[:10]  # Limit to top 10 concepts
    
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
        
        # Handle queries that may start with PREFIX declarations
        # Look for the main query type keywords anywhere in the query, but prioritize ones that appear first
        if 'SELECT' in query_upper:
            return 'SELECT'
        elif 'CONSTRUCT' in query_upper:
            return 'CONSTRUCT'
        elif 'ASK' in query_upper:
            return 'ASK'
        elif 'DESCRIBE' in query_upper:
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
            # Convert file_path to Path object if it's a string
            if isinstance(file_path, str):
                file_path = Path(file_path)
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