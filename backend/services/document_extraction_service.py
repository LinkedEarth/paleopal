"""
Document Extraction Service

Main service that coordinates extraction of structured data from various document types
for indexing into the paleoclimate libraries. Supports:
- Jupyter notebooks → workflow/snippet JSONs
- PDF papers → method JSONs  
- ReadTheDocs HTML → doc/code JSONs
- Ontology TTL files → entity JSONs
- SPARQL markdown/notebooks → query JSONs
"""

import os
import tempfile
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import mimetypes

logger = logging.getLogger(__name__)

class DocumentType(Enum):
    """Supported document types for extraction."""
    NOTEBOOK = "notebook"
    PDF = "pdf"
    READTHEDOCS = "readthedocs"
    ONTOLOGY = "ontology"
    SPARQL = "sparql"
    UNKNOWN = "unknown"

@dataclass
class ExtractionRequest:
    """Request for document extraction."""
    document_type: DocumentType
    source_type: str  # "file" or "url"
    content: Union[bytes, str]  # File content or URL
    filename: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    extraction_params: Optional[Dict[str, Any]] = None

@dataclass
class ExtractionResult:
    """Result of document extraction."""
    request_id: str
    document_type: DocumentType
    success: bool
    extracted_data: List[Dict[str, Any]]
    error_message: Optional[str] = None
    source_info: Optional[Dict[str, Any]] = None
    extraction_stats: Optional[Dict[str, Any]] = None

class DocumentExtractionService:
    """
    Main service for extracting structured data from various document types.
    """
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "paleopal_extractions"
        self.temp_dir.mkdir(exist_ok=True)
        self._extractors = {}
        self._load_extractors()
    
    def _load_extractors(self):
        """Load all available extractors."""
        try:
            from .extractors.notebook_extractor import NotebookExtractor
            self._extractors[DocumentType.NOTEBOOK] = NotebookExtractor()
        except ImportError as e:
            logger.warning(f"Notebook extractor not available: {e}")
        
        try:
            from .extractors.pdf_extractor import PDFExtractor
            self._extractors[DocumentType.PDF] = PDFExtractor()
        except ImportError as e:
            logger.warning(f"PDF extractor not available: {e}")
        
        try:
            from .extractors.readthedocs_extractor import ReadTheDocsExtractor
            self._extractors[DocumentType.READTHEDOCS] = ReadTheDocsExtractor()
        except ImportError as e:
            logger.warning(f"ReadTheDocs extractor not available: {e}")
        
        try:
            from .extractors.ontology_extractor import OntologyExtractor
            self._extractors[DocumentType.ONTOLOGY] = OntologyExtractor()
        except ImportError as e:
            logger.warning(f"Ontology extractor not available: {e}")
        
        try:
            from .extractors.sparql_extractor import SPARQLExtractor
            self._extractors[DocumentType.SPARQL] = SPARQLExtractor()
        except ImportError as e:
            logger.warning(f"SPARQL extractor not available: {e}")
    
    def detect_document_type(self, filename: str, content: Union[bytes, str] = None) -> DocumentType:
        """
        Detect document type from filename and optionally content.
        """
        if not filename:
            return DocumentType.UNKNOWN
        
        filename_lower = filename.lower()
        
        # Check file extensions
        if filename_lower.endswith('.ipynb'):
            return DocumentType.NOTEBOOK
        elif filename_lower.endswith('.pdf'):
            return DocumentType.PDF
        elif filename_lower.endswith(('.ttl', '.rdf', '.owl', '.n3')):
            return DocumentType.ONTOLOGY
        elif filename_lower.endswith(('.md', '.markdown')):
            # Could be SPARQL or other, need content analysis
            if content and isinstance(content, str):
                if 'SELECT' in content.upper() or 'CONSTRUCT' in content.upper():
                    return DocumentType.SPARQL
            return DocumentType.SPARQL  # Default for markdown
        elif filename_lower.endswith(('.html', '.htm')):
            return DocumentType.READTHEDOCS
        
        # Check MIME types
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            if mime_type == 'application/pdf':
                return DocumentType.PDF
            elif mime_type in ['text/html', 'application/xhtml+xml']:
                return DocumentType.READTHEDOCS
        
        return DocumentType.UNKNOWN
    
    async def extract_from_file(
        self, 
        file_content: bytes, 
        filename: str,
        document_type: Optional[DocumentType] = None,
        extraction_params: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        Extract structured data from uploaded file.
        """
        request_id = str(uuid.uuid4())
        
        # Auto-detect document type if not provided
        if document_type is None:
            document_type = self.detect_document_type(filename, file_content)
        
        if document_type == DocumentType.UNKNOWN:
            return ExtractionResult(
                request_id=request_id,
                document_type=document_type,
                success=False,
                extracted_data=[],
                error_message=f"Unsupported document type for file: {filename}"
            )
        
        # Check if extractor is available
        if document_type not in self._extractors:
            return ExtractionResult(
                request_id=request_id,
                document_type=document_type,
                success=False,
                extracted_data=[],
                error_message=f"Extractor not available for document type: {document_type.value}"
            )
        
        # Save file temporarily
        temp_file = self.temp_dir / f"{request_id}_{filename}"
        try:
            with open(temp_file, 'wb') as f:
                f.write(file_content)
            
            # Extract data
            extractor = self._extractors[document_type]
            extracted_data = await extractor.extract_from_file(
                temp_file, 
                extraction_params or {}
            )
            
            return ExtractionResult(
                request_id=request_id,
                document_type=document_type,
                success=True,
                extracted_data=extracted_data,
                source_info={
                    "filename": filename,
                    "file_size": len(file_content),
                    "source_type": "file"
                }
            )
        
        except Exception as e:
            logger.error(f"Extraction failed for {filename}: {e}")
            return ExtractionResult(
                request_id=request_id,
                document_type=document_type,
                success=False,
                extracted_data=[],
                error_message=str(e)
            )
        finally:
            # Cleanup temp file
            if temp_file.exists():
                temp_file.unlink()
    
    async def extract_from_url(
        self, 
        url: str,
        document_type: Optional[DocumentType] = None,
        extraction_params: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        Extract structured data from URL.
        """
        request_id = str(uuid.uuid4())
        
        # Auto-detect document type if not provided
        if document_type is None:
            # Try to guess from URL
            if any(domain in url for domain in ['readthedocs.io', 'readthedocs.org']):
                document_type = DocumentType.READTHEDOCS
            elif url.endswith('.pdf'):
                document_type = DocumentType.PDF
            elif url.endswith('.ipynb'):
                document_type = DocumentType.NOTEBOOK
            elif url.endswith(('.ttl', '.rdf', '.owl')):
                document_type = DocumentType.ONTOLOGY
            else:
                document_type = DocumentType.READTHEDOCS  # Default for URLs
        
        # Check if extractor is available
        if document_type not in self._extractors:
            return ExtractionResult(
                request_id=request_id,
                document_type=document_type,
                success=False,
                extracted_data=[],
                error_message=f"Extractor not available for document type: {document_type.value}"
            )
        
        try:
            # Extract data
            extractor = self._extractors[document_type]
            extracted_data = await extractor.extract_from_url(
                url, 
                extraction_params or {}
            )
            
            return ExtractionResult(
                request_id=request_id,
                document_type=document_type,
                success=True,
                extracted_data=extracted_data,
                source_info={
                    "url": url,
                    "source_type": "url"
                }
            )
        
        except Exception as e:
            logger.error(f"URL extraction failed for {url}: {e}")
            return ExtractionResult(
                request_id=request_id,
                document_type=document_type,
                success=False,
                extracted_data=[],
                error_message=str(e)
            )
    
    def get_supported_types(self) -> List[str]:
        """Get list of supported document types."""
        return [doc_type.value for doc_type in self._extractors.keys()]
    
    def get_extraction_info(self, document_type: DocumentType) -> Dict[str, Any]:
        """Get information about what can be extracted from a document type."""
        info_map = {
            DocumentType.NOTEBOOK: {
                "description": "Extract workflows and code snippets from Jupyter notebooks",
                "output_types": ["complete_workflow", "workflow_step", "code_snippet"],
                "required_params": [],
                "optional_params": ["workflow_title", "hoist_imports", "synth_imports"]
            },
            DocumentType.PDF: {
                "description": "Extract research methods from PDF papers",
                "output_types": ["complete_method", "method_step"],
                "required_params": [],
                "optional_params": ["llm_engine", "max_chars", "min_confidence"]
            },
            DocumentType.READTHEDOCS: {
                "description": "Extract documentation and code examples from ReadTheDocs sites",
                "output_types": ["documentation", "code_example", "api_reference"],
                "required_params": ["base_url"],
                "optional_params": ["max_pages", "include_patterns", "exclude_patterns"]
            },
            DocumentType.ONTOLOGY: {
                "description": "Extract entities and relationships from ontology files",
                "output_types": ["ontology_entity", "relationship"],
                "required_params": ["target_classes"],
                "optional_params": ["include_properties", "max_depth"]
            },
            DocumentType.SPARQL: {
                "description": "Extract SPARQL queries from markdown or notebooks",
                "output_types": ["sparql_query"],
                "required_params": [],
                "optional_params": ["include_comments", "validate_syntax"]
            }
        }
        
        return info_map.get(document_type, {
            "description": "Unknown document type",
            "output_types": [],
            "required_params": [],
            "optional_params": []
        })

# Global document extraction service instance
extraction_service = DocumentExtractionService() 