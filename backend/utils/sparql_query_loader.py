import os
import re
from pathlib import Path
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SparqlQueryParser:
    """Parser for SPARQL queries and their descriptions from Markdown files."""
    
    def __init__(self, corpus_path: str):
        """
        Initialize the query parser.
        
        Args:
            corpus_path: Path to the directory containing query markdown files
        """
        self.corpus_path = Path(corpus_path)
        if not self.corpus_path.exists():
            raise FileNotFoundError(f"Query corpus path not found: {corpus_path}")
        
    def _extract_queries_from_file(self, file_path: Path) -> List[Dict[str, str]]:
        """
        Extract SPARQL queries and their descriptions from a markdown file.
        
        Args:
            file_path: Path to the markdown file
            
        Returns:
            List of dictionaries with query name, description, and SPARQL code
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match query blocks: ### QUERY_NAME followed by Description and SPARQL code
        pattern = r'###\s+([A-Z_]+)\s+Description:\s+(.*?)```sparql\s+(.*?)```'
        matches = re.findall(pattern, content, re.DOTALL)
        
        queries = []
        for match in matches:
            query_name = match[0].strip()
            description = match[1].strip()
            sparql_code = match[2].strip()
            
            queries.append({
                'name': query_name,
                'description': description,
                'sparql': sparql_code,
                'file': file_path.name
            })
        
        return queries
    
    def load_queries(self) -> List[Dict[str, str]]:
        """
        Load all SPARQL queries from the corpus.
        
        Returns:
            List of all queries with their metadata
        """
        all_queries = []
        
        md_files = list(self.corpus_path.glob('*.md'))
        if not md_files:
            logger.warning(f"No markdown files found in {self.corpus_path}")
            return []
        
        for file_path in md_files:
            try:
                file_queries = self._extract_queries_from_file(file_path)
                all_queries.extend(file_queries)
                logger.info(f"Loaded {len(file_queries)} queries from {file_path.name}")
            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
        
        return all_queries
    
    def get_query_by_name(self, query_name: str) -> Optional[Dict[str, str]]:
        """
        Get a specific query by its name.
        
        Args:
            query_name: The name of the query to retrieve
            
        Returns:
            Query dictionary if found, None otherwise
        """
        queries = self.load_queries()
        for query in queries:
            if query['name'] == query_name:
                return query
        return None 