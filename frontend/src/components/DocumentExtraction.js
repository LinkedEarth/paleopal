import React, { useState, useRef } from 'react';
import axios from 'axios';
import API_CONFIG from '../config/api';
import { THEME } from '../styles/colorTheme';

// Configure axios defaults
axios.defaults.baseURL = process.env.REACT_APP_API_URL || 
                         (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000');

const DocumentExtraction = ({ targetLibrary, libraryDetails, onIndexComplete }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedUrl, setSelectedUrl] = useState('');
  const [extractionMode, setExtractionMode] = useState('file'); // 'file' or 'url'
  const [documentType, setDocumentType] = useState('auto');
  const [extractionParams, setExtractionParams] = useState({});
  const [supportedTypes, setSupportedTypes] = useState({});
  const [preview, setPreview] = useState(null);
  const [extractionResult, setExtractionResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [showItemModal, setShowItemModal] = useState(false);
  const [selectedItems, setSelectedItems] = useState(new Set());
  const fileInputRef = useRef(null);

  // Load supported types on component mount
  React.useEffect(() => {
    fetchSupportedTypes();
  }, []);

  const fetchSupportedTypes = async () => {
    try {
      const response = await axios.get(`${API_CONFIG.ENDPOINTS.EXTRACT}/types`);
      setSupportedTypes(response.data.type_details || {});
    } catch (error) {
      console.error('Failed to fetch supported types:', error);
    }
  };

  // Get supported document types based on library type
  const getSupportedDocumentTypes = () => {
    if (!libraryDetails?.library?.type) {
      // Default types if no library is specified
      return [
        { value: 'auto', label: 'Auto-detect' },
        { value: 'notebook', label: 'Jupyter Notebook' },
        { value: 'pdf', label: 'PDF Paper' },
        { value: 'readthedocs', label: 'ReadTheDocs Site' },
        { value: 'ontology', label: 'Ontology (TTL/RDF/OWL)' },
        { value: 'sparql', label: 'SPARQL Queries (Markdown/Notebook)' }
      ];
    }

    const libraryType = libraryDetails.library.type;
    
    // Define document types relevant to each library type
    const typeMapping = {
      'query_library': [
        { value: 'auto', label: 'Auto-detect' },
        { value: 'sparql', label: 'SPARQL Queries (Markdown/Notebook)' },
        { value: 'notebook', label: 'Jupyter Notebook (Enhanced SPARQL)' }
      ],
      'reference_library': [
        { value: 'auto', label: 'Auto-detect' },
        { value: 'ontology', label: 'Ontology (TTL/RDF/OWL)' },
        { value: 'pdf', label: 'Reference Papers' }
      ],
      'methods_library': [
        { value: 'auto', label: 'Auto-detect' },
        { value: 'pdf', label: 'Research Papers' },
        { value: 'notebook', label: 'Jupyter Notebooks (Methods)' }
      ],
      'documentation_library': [
        { value: 'auto', label: 'Auto-detect' },
        { value: 'readthedocs', label: 'ReadTheDocs Site' },
        { value: 'notebook', label: 'Tutorial Notebooks' },
        { value: 'pdf', label: 'Documentation PDFs' }
      ]
    };

    return typeMapping[libraryType] || [
      { value: 'auto', label: 'Auto-detect' },
      { value: 'notebook', label: 'Jupyter Notebook' },
      { value: 'pdf', label: 'PDF Paper' },
      { value: 'readthedocs', label: 'ReadTheDocs Site' },
      { value: 'ontology', label: 'Ontology (TTL/RDF/OWL)' },
      { value: 'sparql', label: 'SPARQL Queries (Markdown/Notebook)' }
    ];
  };

  // Get description for library-specific document types
  const getLibrarySpecificDescription = () => {
    if (!libraryDetails?.library?.type) return null;

    const descriptions = {
      'query_library': 'Extract SPARQL queries from markdown files and Jupyter notebooks with enhanced context analysis, including cell-level metadata, variable names, and surrounding documentation',
      'reference_library': 'Extract ontology entities and research references for the reference library',
      'methods_library': 'Extract research methods and analytical procedures for the methods library',
      'documentation_library': 'Extract documentation, tutorials, and API references for the documentation library'
    };

    return descriptions[libraryDetails.library.type];
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setError(null);
      setPreview(null);
      setExtractionResult(null);
      
      // Auto-detect document type
      const extension = file.name.toLowerCase().split('.').pop();
      if (extension === 'ipynb') {
        setDocumentType('notebook');
      } else if (extension === 'pdf') {
        setDocumentType('pdf');
      } else if (['ttl', 'rdf', 'owl', 'n3'].includes(extension)) {
        setDocumentType('ontology');
      } else if (['md', 'markdown'].includes(extension)) {
        setDocumentType('sparql');
      } else if (['html', 'htm'].includes(extension)) {
        setDocumentType('readthedocs');
      } else {
        setDocumentType('auto');
      }
    }
  };

  const handlePreview = async () => {
    if (!selectedFile && !selectedUrl) return;

    setLoading(true);
    setError(null);

    try {
      if (extractionMode === 'file' && selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);

        let endpoint = `${API_CONFIG.ENDPOINTS.EXTRACT}/preview/notebook`;
        if (documentType === 'pdf' || selectedFile.name.toLowerCase().endsWith('.pdf')) {
          endpoint = `${API_CONFIG.ENDPOINTS.EXTRACT}/preview/pdf`;
        } else if (documentType === 'sparql' || selectedFile.name.toLowerCase().match(/\.(md|markdown)$/)) {
          endpoint = `${API_CONFIG.ENDPOINTS.EXTRACT}/preview/notebook`; // SPARQL doesn't have preview yet, use notebook
        }

        const response = await axios.post(endpoint, formData);
        setPreview(response.data.preview);
      } else {
        setPreview({ message: 'URL preview not yet implemented' });
      }
    } catch (error) {
      setError(error.response?.data?.detail || error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleExtraction = async () => {
    if (!selectedFile && !selectedUrl) return;

    setLoading(true);
    setError(null);

    try {
      let response;

      if (extractionMode === 'file' && selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('params', JSON.stringify(extractionParams));

        // Determine the correct endpoint based on document type and library
        let endpoint = `${API_CONFIG.ENDPOINTS.EXTRACT}/notebook`;
        
        // Route to appropriate extractor
        if (documentType === 'pdf' || selectedFile.name.toLowerCase().endsWith('.pdf')) {
          endpoint = `${API_CONFIG.ENDPOINTS.EXTRACT}/pdf`;
        } else if (documentType === 'sparql' || selectedFile.name.toLowerCase().match(/\.(md|markdown)$/)) {
          endpoint = `${API_CONFIG.ENDPOINTS.EXTRACT}/sparql`;
        } else if (documentType === 'notebook' || selectedFile.name.toLowerCase().endsWith('.ipynb')) {
          // Check if we should use SPARQL extraction for notebooks in query libraries
          const isQueryLibrary = libraryDetails?.library?.type === 'query_library';
          const isAutoDetectInQueryLib = documentType === 'auto' && isQueryLibrary;
          const isSparqlRequested = documentType === 'sparql';
          
          if (isQueryLibrary || isAutoDetectInQueryLib || isSparqlRequested) {
            // Use enhanced SPARQL extractor for notebooks in query libraries
            endpoint = `${API_CONFIG.ENDPOINTS.EXTRACT}/sparql`;
          } else {
            // Use regular notebook extractor for other libraries
            endpoint = `${API_CONFIG.ENDPOINTS.EXTRACT}/notebook`;
          }
        }

        response = await axios.post(endpoint, formData);
      } else if (extractionMode === 'url' && selectedUrl) {
        response = await axios.post(`${API_CONFIG.ENDPOINTS.EXTRACT}/url`, {
            url: selectedUrl,
            document_type: documentType === 'auto' ? null : documentType,
            params: extractionParams
        });
      }

      setExtractionResult(response.data);
    } catch (error) {
      setError(error.response?.data?.detail || error.message);
    } finally {
      setLoading(false);
    }
  };

  const updateExtractionParam = (key, value) => {
    setExtractionParams(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const toggleItemSelection = (index) => {
    const newSelection = new Set(selectedItems);
    if (newSelection.has(index)) {
      newSelection.delete(index);
    } else {
      newSelection.add(index);
    }
    setSelectedItems(newSelection);
  };

  const selectAllItems = () => {
    if (!extractionResult?.extracted_data) return;
    const allIndices = new Set(extractionResult.extracted_data.map((_, idx) => idx));
    setSelectedItems(allIndices);
  };

  const deselectAllItems = () => {
    setSelectedItems(new Set());
  };

  const viewItemDetails = (item, index) => {
    setSelectedItem({ ...item, index });
    setShowItemModal(true);
  };

  const handleIndexing = async () => {
    if (!extractionResult?.extracted_data || !targetLibrary) {
      alert('No extracted data available or target library not specified');
      return;
    }

    // Get selected items for indexing
    const itemsToIndex = selectedItems.size > 0 
      ? extractionResult.extracted_data.filter((_, idx) => selectedItems.has(idx))
      : extractionResult.extracted_data;

    if (itemsToIndex.length === 0) {
      alert('No items selected for indexing');
      return;
    }

    setLoading(true);
    try {
      // Index selected documents into the target library
      const response = await axios.post(`${API_CONFIG.ENDPOINTS.LIBRARIES}/${targetLibrary}/documents/bulk`, {
        documents: itemsToIndex.map(item => ({
            text: item.content || item.description || item.query || item.name || '',
            metadata: {
              title: item.title || item.name,
              content_type: item.content_type,
              extraction_type: item.extraction_type,
              source_file: extractionResult.source_file || 'Document Extraction',
              extracted_at: new Date().toISOString(),
              ...item // Include all other fields as metadata
            }
          }))
      });
      
      // Call the success callback if provided
      if (onIndexComplete) {
        onIndexComplete(response.data);
      }
      
      // Clear the extraction result to show success
      setExtractionResult(null);
      setSelectedItems(new Set());
      
    } catch (error) {
      console.error('Indexing error:', error);
      alert(`Failed to index documents: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const renderParameterControls = () => {
    const typeInfo = supportedTypes[documentType];
    if (!typeInfo) return null;

    return (
      <div className="space-y-4">
        <h4 className={`font-medium ${THEME.text.primary}`}>Extraction Parameters</h4>
        
        {/* Required parameters */}
        {typeInfo.required_params && typeInfo.required_params.map(param => (
          <div key={param} className="space-y-2">
            <label className={`block text-sm font-medium ${THEME.text.secondary}`}>
              {param.replace(/_/g, ' ')} <span className={THEME.status.error.text}>*</span>
            </label>
            {param === 'target_classes' ? (
              <textarea
                className={`w-full px-3 py-2 border rounded-md text-sm ${THEME.borders.default} ${THEME.containers.card} ${THEME.text.primary}`}
                placeholder="Enter class URIs, one per line"
                value={(extractionParams[param] || []).join('\n')}
                onChange={(e) => updateExtractionParam(param, e.target.value.split('\n').filter(l => l.trim()))}
                rows={3}
              />
            ) : (
              <input
                type="text"
                className={`w-full px-3 py-2 border rounded-md text-sm ${THEME.borders.default} ${THEME.containers.card} ${THEME.text.primary}`}
                value={extractionParams[param] || ''}
                onChange={(e) => updateExtractionParam(param, e.target.value)}
                placeholder={`Enter ${param.replace(/_/g, ' ')}`}
              />
            )}
          </div>
        ))}

        {/* Optional parameters */}
        {typeInfo.optional_params && typeInfo.optional_params.map(param => (
          <div key={param} className="space-y-2">
            <label className={`block text-sm font-medium ${THEME.text.secondary}`}>
              {param.replace(/_/g, ' ')}
            </label>
            {param.includes('_count') || param.includes('max_') || param.includes('min_') ? (
              <input
                type="number"
                className={`w-full px-3 py-2 border rounded-md text-sm ${THEME.borders.default} ${THEME.containers.card} ${THEME.text.primary}`}
                value={extractionParams[param] || ''}
                onChange={(e) => updateExtractionParam(param, parseInt(e.target.value) || '')}
                placeholder={getParameterPlaceholder(param)}
              />
            ) : param.includes('include_') || param.includes('hoist_') || param.includes('synth_') || param.includes('extract_') ? (
              <select
                className={`w-full px-3 py-2 border rounded-md text-sm ${THEME.borders.default} ${THEME.containers.card} ${THEME.text.primary}`}
                value={extractionParams[param] || ''}
                onChange={(e) => updateExtractionParam(param, e.target.value === 'true')}
              >
                <option value="">Default</option>
                <option value="true">True</option>
                <option value="false">False</option>
              </select>
            ) : param.includes('patterns') ? (
              <textarea
                className={`w-full px-3 py-2 border rounded-md text-sm ${THEME.borders.default} ${THEME.containers.card} ${THEME.text.primary}`}
                placeholder="Enter patterns, one per line"
                value={(extractionParams[param] || []).join('\n')}
                onChange={(e) => updateExtractionParam(param, e.target.value.split('\n').filter(l => l.trim()))}
                rows={2}
              />
            ) : (
              <input
                type="text"
                className={`w-full px-3 py-2 border rounded-md text-sm ${THEME.borders.default} ${THEME.containers.card} ${THEME.text.primary}`}
                value={extractionParams[param] || ''}
                onChange={(e) => updateExtractionParam(param, e.target.value)}
                placeholder={getParameterPlaceholder(param)}
              />
            )}
          </div>
        ))}
      </div>
    );
  };

  const getParameterPlaceholder = (param) => {
    const placeholders = {
      'llm_engine': 'openai',
      'max_chars': '12000',
      'min_confidence': '0.3',
      'max_pages': '50',
      'depth_limit': '3',
      'workflow_title': 'Specific workflow name',
      'base_url': 'https://docs.example.com'
    };
    return placeholders[param] || `Enter ${param.replace(/_/g, ' ')}`;
  };

  const renderPreview = () => {
    if (!preview) return null;

    return (
      <div className={`p-4 rounded-lg ${THEME.containers.secondary}`}>
        <h4 className={`font-medium ${THEME.text.primary} mb-3`}>Extraction Preview</h4>
        
        {preview.error ? (
          <div className={`${THEME.status.error.text} text-sm`}>{preview.error}</div>
        ) : (
          <div className="space-y-2 text-sm">
            {Object.entries(preview).map(([key, value]) => (
              <div key={key} className="flex justify-between">
                <span className={`font-medium ${THEME.text.secondary}`}>{key.replace(/_/g, ' ')}:</span>
                <span className={THEME.text.primary}>
                  {Array.isArray(value) ? value.length : typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderItemDetailsModal = () => {
    if (!selectedItem || !showItemModal) return null;

    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className={`rounded-lg border max-w-4xl w-full max-h-[90vh] flex flex-col ${THEME.containers.card} ${THEME.borders.default}`}>
          <div className={`p-6 border-b flex-shrink-0 ${THEME.borders.default}`}>
            <div className="flex items-center justify-between">
              <h3 className={`text-lg font-semibold ${THEME.text.primary}`}>
                Extracted Item Details #{selectedItem.index + 1}
              </h3>
              <button
                onClick={() => setShowItemModal(false)}
                className={`${THEME.text.muted} hover:${THEME.text.secondary} text-xl`}
              >
                ×
              </button>
            </div>
          </div>
          
          <div className="p-6 overflow-y-auto flex-1 min-h-0">
            <div className="space-y-6">
              {/* Basic Information */}
              <div>
                <h4 className={`font-medium ${THEME.text.primary} mb-3`}>Basic Information</h4>
                <div className={`p-4 rounded-lg space-y-2 ${THEME.containers.secondary}`}>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <span className={`text-sm font-medium ${THEME.text.secondary}`}>Content Type:</span>
                      <span className={`ml-2 text-sm ${THEME.text.primary}`}>{selectedItem.content_type || 'Unknown'}</span>
                    </div>
                    <div>
                      <span className={`text-sm font-medium ${THEME.text.secondary}`}>Extraction Type:</span>
                      <span className={`ml-2 text-sm ${THEME.text.primary}`}>{selectedItem.extraction_type || 'Unknown'}</span>
                    </div>
                  </div>
                  
                  {selectedItem.title && (
                    <div>
                      <span className={`text-sm font-medium ${THEME.text.secondary}`}>Title:</span>
                      <div className={`mt-1 text-sm ${THEME.text.primary}`}>{selectedItem.title}</div>
                    </div>
                  )}
                  
                  {selectedItem.name && (
                    <div>
                      <span className={`text-sm font-medium ${THEME.text.secondary}`}>Name:</span>
                      <div className={`mt-1 text-sm ${THEME.text.primary}`}>{selectedItem.name}</div>
                    </div>
                  )}
                  
                  {selectedItem.uri && (
                    <div>
                      <span className={`text-sm font-medium ${THEME.text.secondary}`}>URI:</span>
                      <div className={`mt-1 text-sm font-mono ${THEME.text.primary} break-all`}>{selectedItem.uri}</div>
                    </div>
                  )}
                </div>
              </div>

              {/* Notebook-specific metadata */}
              {(selectedItem.cell_index !== undefined || selectedItem.variable_name || selectedItem.extraction_method) && (
                <div>
                  <h4 className={`font-medium ${THEME.text.primary} mb-3`}>Notebook Context</h4>
                  <div className={`p-4 rounded-lg space-y-2 border ${THEME.agents.sparql.background} ${THEME.agents.sparql.border}`}>
                    {selectedItem.cell_index !== undefined && (
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <span className={`text-sm font-medium ${THEME.text.secondary}`}>Cell Index:</span>
                          <span className={`ml-2 text-sm ${THEME.text.primary}`}>{selectedItem.cell_index}</span>
                        </div>
                        {selectedItem.execution_count && (
                          <div>
                            <span className={`text-sm font-medium ${THEME.text.secondary}`}>Execution Count:</span>
                            <span className={`ml-2 text-sm ${THEME.text.primary}`}>{selectedItem.execution_count}</span>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {selectedItem.variable_name && (
                      <div>
                        <span className={`text-sm font-medium ${THEME.text.secondary}`}>Variable Name:</span>
                        <div className="mt-1">
                          <span className={`text-sm px-2 py-1 rounded font-mono ${THEME.agents.code.background} ${THEME.agents.code.text}`}>
                            {selectedItem.variable_name}
                          </span>
                        </div>
                      </div>
                    )}
                    
                    {selectedItem.extraction_method && (
                      <div>
                        <span className={`text-sm font-medium ${THEME.text.secondary}`}>Extraction Method:</span>
                        <div className="mt-1">
                          <span className={`text-sm px-2 py-1 rounded ${THEME.status.warning.background} ${THEME.status.warning.text}`}>
                            {selectedItem.extraction_method.replace(/_/g, ' ')}
                          </span>
                        </div>
                      </div>
                    )}

                    {selectedItem.context && (
                      <div>
                        <span className={`text-sm font-medium ${THEME.text.secondary}`}>Context:</span>
                        <div className={`mt-1 text-sm ${THEME.text.primary}`}>{selectedItem.context}</div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Concepts */}
              {selectedItem.concepts && Array.isArray(selectedItem.concepts) && selectedItem.concepts.length > 0 && (
                <div>
                  <h4 className={`font-medium ${THEME.text.primary} mb-3`}>Extracted Concepts</h4>
                  <div className={`p-4 rounded-lg ${THEME.status.success.background}`}>
                    <div className="flex flex-wrap gap-2">
                      {selectedItem.concepts.map((concept, i) => (
                        <span key={i} className={`text-sm px-2 py-1 rounded ${THEME.status.success.text} ${THEME.containers.secondary}`}>
                          {concept}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Surrounding Cells Context */}
              {selectedItem.surrounding_cells && Array.isArray(selectedItem.surrounding_cells) && selectedItem.surrounding_cells.length > 0 && (
                <div>
                  <h4 className={`font-medium ${THEME.text.primary} mb-3`}>Surrounding Notebook Cells</h4>
                  <div className={`p-4 rounded-lg space-y-3 ${THEME.status.info.background}`}>
                    {selectedItem.surrounding_cells.map((cell, i) => (
                      <div key={i} className={`p-3 rounded border ${THEME.containers.card} ${THEME.borders.default} ${THEME.text.primary}`}>
                        <div className="flex items-center mb-2">
                          <span className={`text-xs px-2 py-1 rounded mr-2 ${THEME.status.info.background} ${THEME.status.info.text}`}>
                            Cell {cell.index}
                          </span>
                          <span className={`text-xs px-2 py-1 rounded ${THEME.containers.secondary} ${THEME.text.primary}`}>
                            {cell.type}
                          </span>
                        </div>
                        <div className={`text-sm ${THEME.text.secondary} whitespace-pre-wrap max-h-20 overflow-y-auto`}>
                          {cell.content}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Content */}
              {(selectedItem.content || selectedItem.description || selectedItem.query) && (
                <div>
                  <h4 className={`font-medium ${THEME.text.primary} mb-3`}>Content</h4>
                  <div className={`p-4 rounded-lg ${THEME.containers.secondary}`}>
                    {selectedItem.content && (
                      <div className="mb-4">
                        <span className={`text-sm font-medium ${THEME.text.secondary}`}>Main Content:</span>
                        <div className={`mt-1 text-sm ${THEME.text.primary} whitespace-pre-wrap max-h-40 overflow-y-auto border rounded p-2 ${THEME.containers.card} ${THEME.borders.default}`}>
                          {selectedItem.content}
                        </div>
                      </div>
                    )}
                    
                    {selectedItem.description && (
                      <div className="mb-4">
                        <span className={`text-sm font-medium ${THEME.text.secondary}`}>Description:</span>
                        <div className={`mt-1 text-sm ${THEME.text.primary} whitespace-pre-wrap max-h-40 overflow-y-auto border rounded p-2 ${THEME.containers.card} ${THEME.borders.default}`}>
                          {selectedItem.description}
                        </div>
                      </div>
                    )}
                    
                    {selectedItem.query && (
                      <div>
                        <span className={`text-sm font-medium ${THEME.text.secondary}`}>SPARQL Query:</span>
                        <div className={`mt-1 text-sm font-mono ${THEME.text.primary} whitespace-pre-wrap max-h-60 overflow-y-auto border rounded p-3 ${THEME.containers.card} ${THEME.borders.default}`}>
                          {selectedItem.query}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Method Structure (for method extraction) */}
              {selectedItem.method_structure && (
                <div>
                  <h4 className={`font-medium ${THEME.text.primary} mb-3`}>Method Structure</h4>
                  <div className={`p-4 rounded-lg ${THEME.containers.secondary}`}>
                    <div className={`text-sm ${THEME.text.primary}`}>
                      <pre className={`whitespace-pre-wrap overflow-x-auto text-xs p-3 rounded border ${THEME.containers.card} ${THEME.borders.default} ${THEME.text.primary}`}>
                        {JSON.stringify(selectedItem.method_structure, null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              )}

              {/* Code (for code extraction) */}
              {selectedItem.code && (
                <div>
                  <h4 className={`font-medium ${THEME.text.primary} mb-3`}>Code</h4>
                  <div className={`p-4 rounded-lg ${THEME.containers.secondary}`}>
                    <div className={`text-sm font-mono ${THEME.text.primary} whitespace-pre-wrap max-h-60 overflow-y-auto border rounded p-3 ${THEME.containers.card} ${THEME.borders.default}`}>
                      {selectedItem.code}
                    </div>
                  </div>
                </div>
              )}

              {/* Additional Metadata */}
              <div>
                <h4 className={`font-medium ${THEME.text.primary} mb-3`}>Additional Metadata</h4>
                <div className={`p-4 rounded-lg ${THEME.containers.secondary}`}>
                  <div className="space-y-2">
                    {Object.entries(selectedItem).map(([key, value]) => {
                      // Skip already displayed fields
                      if ([
                        'content_type', 'extraction_type', 'title', 'name', 'uri', 'content', 
                        'description', 'query', 'method_structure', 'code', 'index',
                        'cell_index', 'variable_name', 'extraction_method', 'context', 
                        'concepts', 'surrounding_cells', 'execution_count'
                      ].includes(key)) {
                        return null;
                      }
                      
                      // Skip empty values
                      if (!value || (Array.isArray(value) && value.length === 0)) {
                        return null;
                      }
                      
                      return (
                        <div key={key} className="flex flex-wrap">
                          <span className={`text-sm font-medium ${THEME.text.secondary} min-w-[120px]`}>{key.replace(/_/g, ' ')}:</span>
                          <span className={`text-sm ${THEME.text.primary} flex-1`}>
                            {Array.isArray(value) ? value.join(', ') : 
                             typeof value === 'object' ? JSON.stringify(value) : 
                             String(value)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Indexing Preview */}
              <div>
                <h4 className={`font-medium ${THEME.text.primary} mb-3`}>Indexing Preview</h4>
                <div className={`p-3 rounded border ${THEME.containers.card} ${THEME.borders.default} ${THEME.text.primary} max-h-32 overflow-y-auto`}>
                  {selectedItem.content || selectedItem.description || selectedItem.query || selectedItem.name || 'No searchable text available'}
                </div>
                <div className={`mt-3 text-xs ${THEME.text.secondary}`}>
                  This text will be used for semantic search within the library.
                </div>
              </div>
            </div>
          </div>
          
          <div className={`p-6 border-t flex-shrink-0 ${THEME.borders.default} ${THEME.containers.secondary}`}>
            <div className="flex justify-between items-center">
              <div className={`text-sm ${THEME.text.secondary}`}>
                Item {selectedItem.index + 1} of {extractionResult?.extracted_data?.length || 0}
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={() => setShowItemModal(false)}
                  className={`px-4 py-2 rounded-md transition-colors ${THEME.buttons.secondary}`}
                >
                  Close
                </button>
                <button
                  onClick={() => {
                    toggleItemSelection(selectedItem.index);
                    setShowItemModal(false);
                  }}
                  className={`px-4 py-2 rounded-md transition-colors ${
                    selectedItems.has(selectedItem.index)
                      ? `${THEME.status.error.text} ${THEME.status.error.background}`
                      : `${THEME.status.success.text} ${THEME.status.success.background}`
                  }`}
                >
                  {selectedItems.has(selectedItem.index) ? 'Remove from Selection' : 'Add to Selection'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderExtractionResult = () => {
    if (!extractionResult) return null;

    return (
      <div className={`border rounded-lg p-6 ${THEME.containers.card} ${THEME.borders.default}`}>
        <div className="flex items-center justify-between mb-4">
          <h4 className={`font-medium ${THEME.text.primary}`}>Extraction Results</h4>
          <div className="flex items-center space-x-2">
            <span className={`px-2 py-1 text-xs rounded-full ${
              extractionResult.success ? `${THEME.status.success.background} ${THEME.status.success.text}` : `${THEME.status.error.background} ${THEME.status.error.text}`
            }`}>
              {extractionResult.success ? 'Success' : 'Failed'}
            </span>
            <span className={`text-sm ${THEME.text.muted}`}>
              {extractionResult.extracted_count} items
            </span>
          </div>
        </div>

        {extractionResult.error_message && (
          <div className={`p-3 rounded-md mb-4 ${THEME.status.error.background}`}>
            <div className={`${THEME.status.error.text} text-sm`}>{extractionResult.error_message}</div>
          </div>
        )}

        {extractionResult.success && extractionResult.extracted_data && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className={`font-medium ${THEME.text.secondary}`}>Document Type:</span>
                <span className={`ml-2 ${THEME.text.primary}`}>{extractionResult.document_type}</span>
              </div>
              <div>
                <span className={`font-medium ${THEME.text.secondary}`}>Request ID:</span>
                <span className={`ml-2 font-mono ${THEME.text.primary}`}>{extractionResult.request_id}</span>
              </div>
            </div>

            {/* Selection Controls */}
            <div className={`border-t pt-4 ${THEME.borders.default}`}>
              <div className="flex items-center justify-between mb-3">
                <h5 className={`font-medium ${THEME.text.primary}`}>Select Items for Indexing</h5>
                <div className="flex space-x-2">
                  <button
                    onClick={selectAllItems}
                    className={`text-xs px-2 py-1 rounded transition-colors ${THEME.status.info.text} ${THEME.status.info.background}`}
                  >
                    Select All
                  </button>
                  <button
                    onClick={deselectAllItems}
                    className={`text-xs px-2 py-1 rounded transition-colors ${THEME.buttons.secondary}`}
                  >
                    Deselect All
                  </button>
                </div>
              </div>
              
              <div className={`text-sm ${THEME.text.secondary} mb-3`}>
                Selected: {selectedItems.size} of {extractionResult.extracted_data.length} items
              </div>
            </div>

            <div className={`border-t pt-4 ${THEME.borders.default}`}>
              <h5 className={`font-medium ${THEME.text.primary} mb-3`}>Extracted Data</h5>
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {extractionResult.extracted_data.map((item, idx) => (
                  <div key={idx} className={`border rounded p-3 transition-colors ${
                    selectedItems.has(idx) ? `${THEME.status.success.background} ${THEME.status.success.border}` : `${THEME.containers.secondary} ${THEME.borders.default}`
                  }`}>
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center space-x-2 flex-wrap gap-1">
                        <input
                          type="checkbox"
                          checked={selectedItems.has(idx)}
                          onChange={() => toggleItemSelection(idx)}
                          className={`rounded ${THEME.borders.default} ${THEME.containers.card} text-blue-600 focus:ring-blue-500 focus:ring-2`}
                        />
                        <span className={`text-xs px-2 py-1 rounded ${THEME.status.info.background} ${THEME.status.info.text}`}>
                          {item.content_type}
                        </span>
                        {item.extraction_type && (
                          <span className={`text-xs px-2 py-1 rounded ${THEME.containers.secondary} ${THEME.text.primary}`}>
                            {item.extraction_type}
                          </span>
                        )}
                        {/* Enhanced notebook metadata badges */}
                        {item.cell_index !== undefined && (
                          <span className={`text-xs px-2 py-1 rounded ${THEME.agents.sparql.background} ${THEME.agents.sparql.text}`}>
                            Cell {item.cell_index}
                          </span>
                        )}
                        {item.variable_name && item.variable_name !== 'anonymous' && (
                          <span className={`text-xs px-2 py-1 rounded ${THEME.agents.code.background} ${THEME.agents.code.text}`}>
                            {item.variable_name}
                          </span>
                        )}
                        {item.extraction_method && (
                          <span className={`text-xs px-2 py-1 rounded ${THEME.status.warning.background} ${THEME.status.warning.text}`}>
                            {item.extraction_method.replace(/_/g, ' ')}
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => viewItemDetails(item, idx)}
                        className={`text-xs px-2 py-1 rounded transition-colors ${THEME.buttons.primary}`}
                      >
                        View Details
                      </button>
                    </div>
                    
                    <div className="text-sm space-y-1">
                      {item.title && (
                        <div><span className={`font-medium ${THEME.text.primary}`}>Title:</span> {item.title}</div>
                      )}
                      {item.name && (
                        <div><span className={`font-medium ${THEME.text.primary}`}>Name:</span> {item.name}</div>
                      )}
                      {item.description && (
                        <div><span className={`font-medium ${THEME.text.primary}`}>Description:</span> {item.description.substring(0, 200)}...</div>
                      )}
                      {item.query && (
                        <div>
                          <span className={`font-medium ${THEME.text.primary}`}>Query:</span> 
                          <code className={`px-1 rounded ml-1 ${THEME.containers.secondary}`}>
                            {item.query.substring(0, 100)}...
                          </code>
                        </div>
                      )}
                      {item.uri && (
                        <div><span className={`font-medium ${THEME.text.primary}`}>URI:</span> <code className={`px-1 rounded ${THEME.containers.secondary}`}>{item.uri}</code></div>
                      )}
                      {/* Enhanced notebook context */}
                      {item.context && (
                        <div><span className={`font-medium ${THEME.text.primary}`}>Context:</span> {item.context}</div>
                      )}
                      {/* Display concepts if available */}
                      {item.concepts && Array.isArray(item.concepts) && item.concepts.length > 0 && (
                        <div className="flex items-center flex-wrap gap-1 mt-2">
                          <span className={`font-medium text-xs ${THEME.text.primary}`}>Concepts:</span>
                          {item.concepts.slice(0, 5).map((concept, i) => (
                            <span key={i} className={`text-xs px-1 py-0.5 rounded ${THEME.status.success.background} ${THEME.status.success.text}`}>
                              {concept}
                            </span>
                          ))}
                          {item.concepts.length > 5 && (
                            <span className={`text-xs ${THEME.text.muted}`}>+{item.concepts.length - 5} more</span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className={`border-t pt-4 ${THEME.borders.default}`}>
              <button
                className={`w-full py-2 px-4 rounded-md transition-colors disabled:opacity-50 ${THEME.status.success.text} ${THEME.status.success.background}`}
                onClick={handleIndexing}
                disabled={loading || !targetLibrary || selectedItems.size === 0}
              >
                {loading ? 'Indexing...' : 
                 selectedItems.size > 0 
                   ? `Index ${selectedItems.size} Selected Item${selectedItems.size === 1 ? '' : 's'} into ${libraryDetails?.library.name || 'Library'}`
                   : 'Select Items to Index'
                }
              </button>
              {!targetLibrary && (
                <p className={`text-xs ${THEME.text.muted} mt-2 text-center`}>
                  No target library specified
                </p>
              )}
              {targetLibrary && selectedItems.size === 0 && (
                <p className={`text-xs ${THEME.text.muted} mt-2 text-center`}>
                  Select items above to enable indexing
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  const supportedDocumentTypes = getSupportedDocumentTypes();
  const libraryDescription = getLibrarySpecificDescription();

  return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Input Section */}
        <div className="lg:col-span-1 space-y-6">
          {/* Mode Selection */}
          <div className={`p-4 rounded-lg border ${THEME.containers.card} ${THEME.borders.default}`}>
            <h3 className={`font-semibold ${THEME.text.primary} mb-3`}>Input Source</h3>
            <div className="space-y-3">
              <div className="flex space-x-4">
                <label className={`flex items-center ${THEME.text.primary}`}>
                  <input
                    type="radio"
                    value="file"
                    checked={extractionMode === 'file'}
                    onChange={(e) => setExtractionMode(e.target.value)}
                    className="mr-2"
                  />
                  Upload File
                </label>
                <label className={`flex items-center ${THEME.text.primary}`}>
                  <input
                    type="radio"
                    value="url"
                    checked={extractionMode === 'url'}
                    onChange={(e) => setExtractionMode(e.target.value)}
                    className="mr-2"
                  />
                  From URL
                </label>
              </div>

              {extractionMode === 'file' ? (
                <div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    onChange={handleFileSelect}
                    accept=".ipynb,.pdf,.ttl,.rdf,.owl,.n3,.md,.markdown,.html,.htm"
                    className={`w-full ${THEME.text.primary} file:${THEME.buttons.primary.replace('hover:', '')} file:rounded-md file:px-3 file:py-2 file:border-0 file:cursor-pointer`}
                  />
                  {selectedFile && (
                    <div className={`mt-2 text-sm ${THEME.text.secondary}`}>
                      Selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <input
                    type="url"
                    value={selectedUrl}
                    onChange={(e) => setSelectedUrl(e.target.value)}
                    placeholder="https://example.com/document.pdf"
                    className={`w-full px-3 py-2 border rounded-md ${THEME.borders.default} ${THEME.containers.card} ${THEME.text.primary}`}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Document Type Selection */}
          <div className={`p-4 rounded-lg border ${THEME.containers.card} ${THEME.borders.default}`}>
            <h3 className={`font-semibold ${THEME.text.primary} mb-3`}>Document Type</h3>
            <select
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              className={`w-full px-3 py-2 border rounded-md ${THEME.borders.default} ${THEME.containers.card} ${THEME.text.primary}`}
            >
            {supportedDocumentTypes.map(type => (
              <option key={type.value} value={type.value}>{type.label}</option>
            ))}
            </select>
            
            {supportedTypes[documentType] && (
              <div className={`mt-2 text-xs ${THEME.text.secondary}`}>
                {supportedTypes[documentType].description}
              </div>
            )}

          {libraryDescription && (
            <div className={`mt-2 text-xs p-2 rounded border ${THEME.status.info.text} ${THEME.status.info.background} ${THEME.status.info.border}`}>
              {libraryDescription}
            </div>
          )}

          {/* Enhanced Notebook SPARQL Extraction Info */}
          {((documentType === 'sparql' && selectedFile?.name.endsWith('.ipynb')) || 
            (documentType === 'notebook' && libraryDetails?.library?.type === 'query_library') ||
            (documentType === 'auto' && selectedFile?.name.endsWith('.ipynb') && libraryDetails?.library?.type === 'query_library')) && (
            <div className={`mt-3 text-xs p-3 rounded border ${THEME.agents.sparql.background} ${THEME.agents.sparql.text} ${THEME.agents.sparql.border}`}>
              <div className="font-medium mb-1">Enhanced Notebook SPARQL Extraction</div>
              <ul className="list-disc list-inside space-y-1 text-xs">
                <li>Extracts SPARQL queries from code cells (variables, strings, f-strings)</li>
                <li>Analyzes surrounding markdown cells for context and descriptions</li>
                <li>Captures cell metadata (index, variable names, execution count)</li>
                <li>Extracts concepts and provides rich indexing metadata</li>
                <li>Deduplicates queries and identifies extraction methods</li>
              </ul>
            </div>
          )}
          </div>

          {/* Parameters */}
          {documentType !== 'auto' && (
            <div className={`p-4 rounded-lg border ${THEME.containers.card} ${THEME.borders.default}`}>
              {renderParameterControls()}
            </div>
          )}

          {/* Action Buttons */}
          <div className="space-y-2">
            <button
              onClick={handlePreview}
              disabled={loading || (!selectedFile && !selectedUrl)}
              className={`w-full py-2 px-4 rounded-md disabled:opacity-50 transition-colors ${THEME.buttons.primary}`}
            >
              {loading ? 'Loading...' : 'Preview Extraction'}
            </button>
            
            <button
              onClick={handleExtraction}
              disabled={loading || (!selectedFile && !selectedUrl)}
              className={`w-full py-2 px-4 rounded-md disabled:opacity-50 transition-colors ${THEME.status.success.text} ${THEME.status.success.background}`}
            >
              {loading ? 'Extracting...' : 'Extract Data'}
            </button>
          </div>

          {/* Target Library Info */}
          {targetLibrary && libraryDetails && (
            <div className={`p-4 rounded-lg border ${THEME.status.success.background} ${THEME.status.success.border}`}>
              <h3 className={`font-semibold ${THEME.status.success.text} mb-3`}>Target Library</h3>
              <div className="space-y-2 text-sm">
                <div>
                  <span className={`font-medium ${THEME.status.success.text}`}>Name:</span> {libraryDetails.library.name}
                </div>
                <div>
                  <span className={`font-medium ${THEME.status.success.text}`}>Type:</span> {libraryDetails.library.type?.replace(/_/g, ' ') || 'unknown'}
                </div>
                <div>
                  <span className={`font-medium ${THEME.status.success.text}`}>Collections:</span> {libraryDetails.collections?.length || 0}
                </div>
                <div>
                  <span className={`font-medium ${THEME.status.success.text}`}>Documents:</span> {(libraryDetails.library.total_documents || 0).toLocaleString()}
                </div>
              </div>
              <p className={`text-xs ${THEME.status.success.text} mt-2`}>
                ✓ Extracted documents will be indexed into this library
              </p>
            </div>
          )}
        </div>

        {/* Results Section */}
        <div className="lg:col-span-2 space-y-6">
          {error && (
            <div className={`border p-4 rounded-lg ${THEME.status.error.background} ${THEME.status.error.border}`}>
              <div className={`${THEME.status.error.text} font-medium`}>Error</div>
              <div className={`${THEME.status.error.text} text-sm mt-1`}>{error}</div>
            </div>
          )}

          {preview && (
            <div className={`border rounded-lg p-6 ${THEME.containers.card} ${THEME.borders.default}`}>
              <h3 className={`font-semibold ${THEME.text.primary} mb-4`}>Preview</h3>
              {renderPreview()}
            </div>
          )}

          {extractionResult && renderExtractionResult()}

        {/* Library-Specific Documentation */}
        {libraryDetails && (
          <div className={`p-4 rounded-lg border ${THEME.status.info.background} ${THEME.status.info.border}`}>
            <h3 className={`font-semibold ${THEME.status.info.text} mb-2`}>
              Supported Document Types for {libraryDetails.library.name}
            </h3>
            <div className={`space-y-2 text-sm ${THEME.status.info.text}`}>
              {supportedDocumentTypes.map(type => {
                if (type.value === 'auto') return null;
                
                const descriptions = {
                  'notebook': libraryDetails.library.type === 'query_library' 
                    ? 'Extracts SPARQL queries and code snippets from notebooks'
                    : libraryDetails.library.type === 'methods_library'
                    ? 'Extracts analytical workflows and method steps'
                    : libraryDetails.library.type === 'documentation_library'
                    ? 'Extracts tutorial content and code examples'
                    : 'Extracts workflows and code snippets',
                  'pdf': libraryDetails.library.type === 'methods_library'
                    ? 'Extracts research methods and analytical procedures'
                    : libraryDetails.library.type === 'reference_library'
                    ? 'Extracts research references and metadata'
                    : libraryDetails.library.type === 'documentation_library'
                    ? 'Extracts documentation content and references'
                    : 'Extracts research methods using LLM',
                  'readthedocs': libraryDetails.library.type === 'documentation_library'
                    ? 'Crawls documentation, API references, and tutorials'
                    : 'Crawls documentation and API references',
                  'ontology': libraryDetails.library.type === 'reference_library'
                    ? 'Extracts entities, relationships, and definitions'
                    : 'Extracts entities and relationships',
                  'sparql': libraryDetails.library.type === 'query_library'
                    ? 'Extracts SPARQL queries and query patterns'
                    : 'Extracts SPARQL queries and code blocks'
                };

                return (
                  <div key={type.value}>
                    <strong>{type.label}:</strong> {descriptions[type.value] || type.label}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Item Details Modal */}
      {renderItemDetailsModal()}
    </div>
  );
};

export default DocumentExtraction; 
