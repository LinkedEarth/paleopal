"""
Document Extraction API endpoints.
Provides REST API for extracting structured data from various document types.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.document_extraction_service import extraction_service, DocumentType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extract", tags=["document_extraction"])

# Request/Response models
class ExtractionParamsModel(BaseModel):
    """Model for extraction parameters."""
    workflow_title: Optional[str] = Field(None, description="Specific workflow to extract (notebooks)")
    hoist_imports: Optional[bool] = Field(True, description="Move imports to top")
    synth_imports: Optional[bool] = Field(True, description="Synthesize missing imports")
    extract_snippets: Optional[bool] = Field(True, description="Extract code snippets")
    extract_workflows: Optional[bool] = Field(True, description="Extract complete workflows")
    llm_engine: Optional[str] = Field("openai", description="LLM engine for extraction")
    max_chars: Optional[int] = Field(12000, description="Max characters to process")
    min_confidence: Optional[float] = Field(0.3, description="Minimum confidence threshold")
    base_url: Optional[str] = Field(None, description="Base URL for ReadTheDocs extraction")
    target_classes: Optional[List[str]] = Field(None, description="Target classes for ontology extraction")
    max_pages: Optional[int] = Field(50, description="Max pages to crawl")
    include_patterns: Optional[List[str]] = Field(None, description="URL patterns to include")
    exclude_patterns: Optional[List[str]] = Field(None, description="URL patterns to exclude")

class URLExtractionRequest(BaseModel):
    """Model for URL-based extraction requests."""
    url: str = Field(..., description="URL to extract from")
    document_type: Optional[str] = Field(None, description="Document type override")
    params: Optional[ExtractionParamsModel] = Field(None, description="Extraction parameters")

class ExtractionResponse(BaseModel):
    """Model for extraction responses."""
    success: bool
    request_id: str
    document_type: str
    extracted_count: int
    extracted_data: List[Dict[str, Any]]
    source_info: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

@router.get("/types")
async def get_supported_types():
    """Get list of supported document types and their capabilities."""
    supported_types = extraction_service.get_supported_types()
    
    # Get detailed info for each type
    type_info = {}
    for doc_type_str in supported_types:
        try:
            doc_type = DocumentType(doc_type_str)
            type_info[doc_type_str] = extraction_service.get_extraction_info(doc_type)
        except ValueError:
            continue
    
    return {
        "supported_types": supported_types,
        "type_details": type_info
    }

@router.post("/notebook", response_model=ExtractionResponse)
async def extract_notebook(
    file: UploadFile = File(...),
    params: Optional[str] = Form(None)
):
    """
    Extract workflows and snippets from a Jupyter notebook.
    """
    if not file.filename.endswith('.ipynb'):
        raise HTTPException(status_code=400, detail="File must be a Jupyter notebook (.ipynb)")
    
    try:
        # Parse parameters if provided
        extraction_params = {}
        if params:
            import json
            extraction_params = json.loads(params)
        
        # Read file content
        content = await file.read()
        
        # Extract data
        result = await extraction_service.extract_from_file(
            content, 
            file.filename,
            DocumentType.NOTEBOOK,
            extraction_params
        )
        
        return ExtractionResponse(
            success=result.success,
            request_id=result.request_id,
            document_type=result.document_type.value,
            extracted_count=len(result.extracted_data),
            extracted_data=result.extracted_data,
            source_info=result.source_info,
            error_message=result.error_message
        )
    
    except Exception as e:
        logger.error(f"Notebook extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pdf", response_model=ExtractionResponse)
async def extract_pdf(
    file: UploadFile = File(...),
    params: Optional[str] = Form(None)
):
    """
    Extract research methods from a PDF paper.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF (.pdf)")
    
    try:
        # Parse parameters if provided
        extraction_params = {}
        if params:
            import json
            extraction_params = json.loads(params)
        
        # Read file content
        content = await file.read()
        
        # Extract data
        result = await extraction_service.extract_from_file(
            content, 
            file.filename,
            DocumentType.PDF,
            extraction_params
        )
        
        return ExtractionResponse(
            success=result.success,
            request_id=result.request_id,
            document_type=result.document_type.value,
            extracted_count=len(result.extracted_data),
            extracted_data=result.extracted_data,
            source_info=result.source_info,
            error_message=result.error_message
        )
    
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/url", response_model=ExtractionResponse)
async def extract_from_url(request: URLExtractionRequest):
    """
    Extract data from a URL (supports various document types).
    """
    try:
        # Convert document type string to enum if provided
        doc_type = None
        if request.document_type:
            try:
                doc_type = DocumentType(request.document_type)
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported document type: {request.document_type}"
                )
        
        # Convert params model to dict
        extraction_params = {}
        if request.params:
            extraction_params = request.params.dict(exclude_none=True)
        
        # Extract data
        result = await extraction_service.extract_from_url(
            request.url,
            doc_type,
            extraction_params
        )
        
        return ExtractionResponse(
            success=result.success,
            request_id=result.request_id,
            document_type=result.document_type.value,
            extracted_count=len(result.extracted_data),
            extracted_data=result.extracted_data,
            source_info=result.source_info,
            error_message=result.error_message
        )
    
    except Exception as e:
        logger.error(f"URL extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/preview/notebook")
async def preview_notebook_extraction(file: UploadFile = File(...)):
    """
    Preview what would be extracted from a notebook without full processing.
    """
    if not file.filename.endswith('.ipynb'):
        raise HTTPException(status_code=400, detail="File must be a Jupyter notebook (.ipynb)")
    
    try:
        # Save temp file
        import tempfile
        content = await file.read()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ipynb") as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)
        
        try:
            # Get preview from extractor
            from services.extractors.notebook_extractor import NotebookExtractor
            extractor = NotebookExtractor()
            preview = extractor.get_extraction_preview(temp_path)
            
            return {
                "success": True,
                "filename": file.filename,
                "preview": preview
            }
        finally:
            temp_path.unlink()
    
    except Exception as e:
        logger.error(f"Notebook preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/preview/pdf")
async def preview_pdf_extraction(file: UploadFile = File(...)):
    """
    Preview what would be extracted from a PDF without full processing.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF (.pdf)")
    
    try:
        # Save temp file
        import tempfile
        content = await file.read()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)
        
        try:
            # Get preview from extractor
            from services.extractors.pdf_extractor import PDFExtractor
            extractor = PDFExtractor()
            preview = extractor.get_extraction_preview(temp_path)
            
            return {
                "success": True,
                "filename": file.filename,
                "preview": preview
            }
        finally:
            temp_path.unlink()
    
    except Exception as e:
        logger.error(f"PDF preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Check health of extraction service."""
    try:
        supported_types = extraction_service.get_supported_types()
        
        return {
            "status": "healthy",
            "supported_extractors": len(supported_types),
            "available_types": supported_types
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Service unhealthy: {e}") 