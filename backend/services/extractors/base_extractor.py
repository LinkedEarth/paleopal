"""
Base extractor class for document processing.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class BaseExtractor(ABC):
    """
    Abstract base class for document extractors.
    """
    
    def __init__(self):
        self.logger = logger
    
    @abstractmethod
    async def extract_from_file(
        self, 
        file_path: Path, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract structured data from a file.
        
        Args:
            file_path: Path to the file to extract from
            params: Extraction parameters
            
        Returns:
            List of extracted data objects
        """
        pass
    
    async def extract_from_url(
        self, 
        url: str, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract structured data from a URL.
        Default implementation downloads the file and uses extract_from_file.
        
        Args:
            url: URL to extract from
            params: Extraction parameters
            
        Returns:
            List of extracted data objects
        """
        # Download file and delegate to extract_from_file
        import aiohttp
        import tempfile
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=self._get_file_suffix()) as temp_file:
                        temp_file.write(content)
                        temp_path = Path(temp_file.name)
                    
                    try:
                        return await self.extract_from_file(temp_path, params)
                    finally:
                        temp_path.unlink()
                else:
                    raise Exception(f"Failed to download from {url}: {response.status}")
    
    def _get_file_suffix(self) -> str:
        """Get appropriate file suffix for temporary files."""
        return ".tmp"
    
    def _validate_params(self, params: Dict[str, Any], required: List[str] = None) -> None:
        """
        Validate that required parameters are present.
        
        Args:
            params: Parameters to validate
            required: List of required parameter names
        """
        if required:
            missing = [param for param in required if param not in params]
            if missing:
                raise ValueError(f"Missing required parameters: {missing}")
    
    def _clean_extracted_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean and standardize extracted data.
        
        Args:
            data: Raw extracted data
            
        Returns:
            Cleaned data
        """
        cleaned = []
        for item in data:
            if item and isinstance(item, dict):
                # Remove None values and empty strings
                cleaned_item = {k: v for k, v in item.items() if v is not None and v != ""}
                if cleaned_item:
                    cleaned.append(cleaned_item)
        return cleaned 