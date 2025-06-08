"""
PDF extractor for research papers.
Extracts scientific methods that can be indexed.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add libraries to path
libs_path = Path(__file__).parent.parent.parent / "libraries"
sys.path.insert(0, str(libs_path))

from .base_extractor import BaseExtractor

class PDFExtractor(BaseExtractor):
    """
    Extractor for PDF research papers.
    Produces method JSONs ready for indexing.
    """
    
    def _get_file_suffix(self) -> str:
        return ".pdf"
    
    async def extract_from_file(
        self, 
        file_path: Path, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract research methods from a PDF paper.
        
        Args:
            file_path: Path to .pdf file
            params: Extraction parameters:
                - llm_engine: LLM to use for extraction (default: "openai")
                - max_chars: Max characters to process (default: 12000)
                - min_confidence: Minimum confidence for method sections (default: 0.3)
                - force_reprocess: Whether to reprocess if already exists (default: False)
        
        Returns:
            List of extracted method objects
        """
        self.logger.info(f"Extracting methods from PDF: {file_path}")
        
        # Import the PDF extraction functions
        try:
            from literature_library.extract_pdf_methods import (
                extract_pdf_text_with_structure,
                filter_methods_sections,
                extract_structured_methods,
                validate_and_enhance_methods
            )
        except ImportError as e:
            raise ImportError(f"PDF extraction dependencies not available: {e}")
        
        # Get parameters
        llm_engine = params.get('llm_engine', 'openai')
        max_chars = params.get('max_chars', 12000)
        min_confidence = params.get('min_confidence', 0.3)
        
        extracted_data = []
        
        try:
            # Extract text with structure from PDF
            self.logger.info("Extracting PDF text structure...")
            sections = extract_pdf_text_with_structure(file_path)
            
            if not sections:
                raise ValueError("Could not extract text from PDF")
            
            # Filter to method sections
            self.logger.info("Filtering for methods sections...")
            method_sections = filter_methods_sections(sections, min_confidence=min_confidence)
            
            if not method_sections:
                self.logger.warning("No method sections found in PDF")
                return []
            
            self.logger.info(f"Found {len(method_sections)} potential method sections")
            
            # Extract structured methods using LLM
            self.logger.info(f"Extracting structured methods using {llm_engine}...")
            methods_data = extract_structured_methods(
                method_sections, 
                engine=llm_engine,
                max_chars=max_chars
            )
            
            if not methods_data:
                self.logger.warning("LLM extraction returned no results")
                return []
            
            # Validate and enhance the extracted methods
            self.logger.info("Validating and enhancing extracted methods...")
            enhanced_methods = validate_and_enhance_methods(methods_data)
            
            # Convert to list format and add metadata
            if 'methods' in enhanced_methods:
                for method in enhanced_methods['methods']:
                    method.update({
                        'content_type': 'complete_method',
                        'source_file': str(file_path),
                        'extraction_type': 'method',
                        'paper_title': enhanced_methods.get('paper_title', 'Unknown'),
                        'llm_engine': llm_engine,
                        'extraction_confidence': min_confidence
                    })
                    extracted_data.append(method)
            
            self.logger.info(f"Successfully extracted {len(extracted_data)} methods")
            
        except Exception as e:
            self.logger.error(f"Failed to extract methods from PDF: {e}")
            raise
        
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
        Extract from a PDF URL.
        """
        self.logger.info(f"Extracting PDF from URL: {url}")
        
        # Download and delegate to file extraction
        import aiohttp
        import tempfile
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Validate it's a PDF
                    if not content.startswith(b'%PDF'):
                        raise ValueError("Downloaded content is not a valid PDF")
                    
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
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
                    raise Exception(f"Failed to download PDF from {url}: {response.status}")
    
    def get_extraction_preview(self, file_path: Path) -> Dict[str, Any]:
        """
        Get a preview of what would be extracted without full processing.
        """
        try:
            from literature_library.extract_pdf_methods import (
                extract_pdf_text_with_structure,
                filter_methods_sections
            )
            
            # Extract structure
            sections = extract_pdf_text_with_structure(file_path)
            
            if not sections:
                return {"error": "Could not extract text from PDF"}
            
            # Filter for methods
            method_sections = filter_methods_sections(sections, min_confidence=0.3)
            
            # Get basic stats
            total_chars = sum(len(section.get('content', '')) for section in sections)
            method_chars = sum(len(section.get('content', '')) for section in method_sections)
            
            section_headings = [section.get('heading', 'Unknown') for section in sections]
            method_headings = [
                {
                    'heading': section.get('heading', 'Unknown'),
                    'confidence': section.get('confidence', 0.0),
                    'page': section.get('page', 0)
                } 
                for section in method_sections
            ]
            
            return {
                "total_sections": len(sections),
                "method_sections": len(method_sections),
                "total_characters": total_chars,
                "method_characters": method_chars,
                "all_headings": section_headings[:10],  # First 10
                "method_headings": method_headings,
                "estimated_methods": max(1, len(method_sections)),
                "extraction_feasible": method_chars > 0 and method_chars < 50000
            }
        
        except Exception as e:
            return {"error": str(e)} 