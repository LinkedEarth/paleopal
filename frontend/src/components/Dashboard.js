import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import DocumentExtraction from './DocumentExtraction';
import API_CONFIG from '../config/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import THEME from '../styles/colorTheme';
import Icon from './Icon';

// Configure axios defaults - use same logic as API_CONFIG
axios.defaults.baseURL = process.env.REACT_APP_API_URL || 
                         (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000');

// Simple CSS for line clamping
const styles = `
  .line-clamp-3 {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  code {
    background-color: transparent !important;
  }
`;

// Helper function to detect dark mode
const isDarkMode = () => document.documentElement.classList.contains('dark');

// Expandable String Component
const ExpandableString = ({ value, maxLength = 100 }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  if (value.length <= maxLength) {
    return <span className={`text-sm ${THEME.text.primary}`}>{value}</span>;
  }
  
  return (
    <div className={`text-sm ${THEME.text.primary}`}>
      <div className={isExpanded ? '' : 'line-clamp-3'}>
        {value}
      </div>
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className={`text-xs ${THEME.status.info.text} hover:opacity-80 mt-1`}
      >
        {isExpanded ? 'Show less' : 'Show more'}
      </button>
    </div>
  );
};

// Expandable Array Component
const ExpandableArray = ({ value, keyPrefix = '' }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  if (value.length === 0) {
    return <span className={`${THEME.text.muted} italic`}>[]</span>;
  }
  
  return (
    <div>
      <span className={`text-xs ${THEME.text.secondary}`}>Array ({value.length} items)</span>
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className={`text-xs ${THEME.status.info.text} hover:opacity-80`}
      >
        {isExpanded ? ' [Hide]' : ' [Show]'}
      </button>
      {isExpanded && (
        <div className={`mt-2 space-y-1 max-h-40 overflow-y-auto border-l-2 ${THEME.borders.default} pl-3`}>
          {value.slice(0, 10).map((item, index) => (
            <div key={index} className="text-xs">
              <span className={THEME.text.muted}>[{index}]</span> <ValueRenderer value={item} keyPrefix={`${keyPrefix}_${index}`} />
            </div>
          ))}
          {value.length > 10 && (
            <div className={`text-xs ${THEME.text.muted}`}>... and {value.length - 10} more items</div>
          )}
        </div>
      )}
    </div>
  );
};

// Expandable Object Component
const ExpandableObject = ({ value, keyPrefix = '' }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const keys = Object.keys(value);
  
  if (keys.length === 0) {
    return <span className={`${THEME.text.muted} italic`}>{'{}'}</span>;
  }
  
  return (
    <div>
      <span className={`text-xs ${THEME.text.secondary}`}>Object ({keys.length} properties)</span>
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className={`text-xs ${THEME.status.info.text} hover:opacity-80`}
      >
        {isExpanded ? ' [Hide]' : ' [Show]'}
      </button>
      {isExpanded && (
        <div className={`mt-2 space-y-2 max-h-60 overflow-y-auto border-l-2 ${THEME.borders.default} pl-3`}>
          <dl className="space-y-1">
            {keys.slice(0, 10).map(subKey => (
              <div key={subKey}>
                <dt className={`text-xs font-medium ${THEME.text.secondary}`}>{subKey}</dt>
                <dd className="ml-2"><ValueRenderer value={value[subKey]} keyPrefix={`${keyPrefix}_${subKey}`} /></dd>
              </div>
            ))}
            {keys.length > 10 && (
              <div className={`text-xs ${THEME.text.muted}`}>... and {keys.length - 10} more properties</div>
            )}
          </dl>
        </div>
      )}
    </div>
  );
};

// Value Renderer Component
const ValueRenderer = ({ value, keyPrefix = '' }) => {
  if (value === null || value === undefined) {
    return <span className={`${THEME.text.muted} italic`}>null</span>;
  }
  
  if (typeof value === 'boolean') {
    return <span className={`text-xs px-2 py-1 rounded ${value ? `${THEME.status.success.background} ${THEME.status.success.text}` : `${THEME.status.error.background} ${THEME.status.error.text}`}`}>
      {value.toString()}
    </span>;
  }
  
  if (typeof value === 'string' && value.startsWith('http')) {
    return <span className={`${THEME.status.info.text} font-mono`}>{value}</span>;
  }
  
  if (typeof value === 'string' && value.length > 100) {
    return <ExpandableString value={value} />;
  }
  
  if (typeof value === 'string' || typeof value === 'number') {
    return <span className={`text-sm ${THEME.text.primary}`}>{value}</span>;
  }
  
  if (Array.isArray(value)) {
    return <ExpandableArray value={value} keyPrefix={keyPrefix} />;
  }
  
  if (typeof value === 'object') {
    return <ExpandableObject value={value} keyPrefix={keyPrefix} />;
  }
  
  return <span className={`text-sm ${THEME.text.primary}`}>{value.toString()}</span>;
};

// Metadata Viewer Component
const MetadataViewer = ({ metadata }) => {
  const [expandedSections, setExpandedSections] = useState(new Set());
  
  const toggleSection = (key) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedSections(newExpanded);
  };

  return (
    <div className={`${THEME.containers.secondary} p-3 rounded border ${THEME.borders.default} max-h-80 overflow-y-auto`}>
      <div className="space-y-3">
        {Object.entries(metadata).map(([key, value]) => (
          <div key={key} className={`border-b ${THEME.borders.default} pb-2 last:border-b-0`}>
            <dt className={`text-xs font-medium ${THEME.text.secondary} uppercase mb-1`}>{key.replace(/_/g, ' ')}</dt>
            <dd><ValueRenderer value={value} keyPrefix={key} /></dd>
          </div>
        ))}
      </div>
    </div>
  );
};

// Additional Fields Viewer Component
const AdditionalFieldsViewer = ({ document }) => {
  const [expandedFields, setExpandedFields] = useState(new Set());
  
  const toggleField = (key) => {
    const newExpanded = new Set(expandedFields);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedFields(newExpanded);
  };

  const renderFieldValue = (value, key) => {
    if (value === null || value === undefined) {
      return <span className={`${THEME.text.muted} italic`}>null</span>;
    }
    
    if (typeof value === 'object') {
      const isExpanded = expandedFields.has(key);
      return (
        <div>
          <div className="flex items-center justify-between">
            <span className={`text-xs ${THEME.text.secondary}`}>
              {Array.isArray(value) ? `Array (${value.length} items)` : `Object (${Object.keys(value).length} properties)`}
            </span>
            <button
              onClick={() => toggleField(key)}
              className={`text-xs ${THEME.status.info.text} hover:opacity-80`}
            >
              {isExpanded ? 'Hide' : 'Show'}
            </button>
          </div>
          {isExpanded && (
            <div className={`mt-2 ${THEME.containers.secondary} p-2 rounded text-xs font-mono max-h-40 overflow-y-auto`}>
              <pre className="whitespace-pre-wrap">{JSON.stringify(value, null, 2)}</pre>
            </div>
          )}
        </div>
      );
    }
    
    if (typeof value === 'string' && value.length > 200) {
      const isExpanded = expandedFields.has(key);
      return (
        <div>
          <div className={`text-sm ${THEME.text.primary}`}>
            {isExpanded ? value : `${value.substring(0, 200)}...`}
          </div>
          <button
            onClick={() => toggleField(key)}
            className={`text-xs ${THEME.status.info.text} hover:opacity-80 mt-1`}
          >
            {isExpanded ? 'Show less' : 'Show more'}
          </button>
        </div>
      );
    }
    
    return <span className={`text-sm ${THEME.text.primary}`}>{value.toString()}</span>;
  };

  const fieldsToShow = Object.entries(document).filter(([key, value]) => 
    !['text', 'content', 'id', 'description', 'code', 'signature', 'entity_id', 'uri', 'sparql', 'query'].includes(key) && 
    value !== null && value !== undefined
  );

  if (fieldsToShow.length === 0) {
    return <div className={`text-sm ${THEME.text.muted} italic`}>No additional fields to display</div>;
  }

  return (
    <div className={`${THEME.containers.secondary} p-3 rounded border ${THEME.borders.default} max-h-80 overflow-y-auto`}>
      <div className="space-y-3">
        {fieldsToShow.map(([key, value]) => (
          <div key={key} className={`border-b ${THEME.borders.default} pb-2 last:border-b-0`}>
            <dt className={`text-xs font-medium ${THEME.text.secondary} uppercase mb-1`}>{key.replace(/_/g, ' ')}</dt>
            <dd>{renderFieldValue(value, key)}</dd>
          </div>
        ))}
      </div>
    </div>
  );
};

// Metadata Editor Component for Add Document Modal
const MetadataEditor = ({ metadata, onChange }) => {
  const [metadataFields, setMetadataFields] = useState([]);
  const [showRawJSON, setShowRawJSON] = useState(false);
  const [rawJSON, setRawJSON] = useState('');

  // Initialize metadata fields from passed metadata
  useEffect(() => {
    if (metadata && typeof metadata === 'object') {
      const fields = Object.entries(metadata).map(([key, value]) => ({
        key,
        value: typeof value === 'object' ? JSON.stringify(value) : value.toString(),
        type: typeof value === 'object' ? 'json' : typeof value
      }));
      setMetadataFields(fields);
      setRawJSON(JSON.stringify(metadata, null, 2));
    } else {
      setMetadataFields([]);
      setRawJSON('{}');
    }
  }, [metadata]);

  const addField = () => {
    setMetadataFields([...metadataFields, { key: '', value: '', type: 'string' }]);
  };

  const removeField = (index) => {
    const newFields = metadataFields.filter((_, i) => i !== index);
    setMetadataFields(newFields);
    updateMetadata(newFields);
  };

  const updateField = (index, field, newValue) => {
    const newFields = [...metadataFields];
    newFields[index] = { ...newFields[index], [field]: newValue };
    setMetadataFields(newFields);
    updateMetadata(newFields);
  };

  const updateMetadata = (fields) => {
    try {
      const newMetadata = {};
      fields.forEach(({ key, value, type }) => {
        if (key.trim()) {
          if (type === 'number') {
            newMetadata[key] = parseFloat(value) || 0;
          } else if (type === 'boolean') {
            newMetadata[key] = value === 'true';
          } else if (type === 'json') {
            try {
              newMetadata[key] = JSON.parse(value);
            } catch {
              newMetadata[key] = value; // Fall back to string if JSON parse fails
            }
          } else {
            newMetadata[key] = value;
          }
        }
      });
      setRawJSON(JSON.stringify(newMetadata, null, 2));
      onChange(newMetadata);
    } catch (error) {
      console.error('Error updating metadata:', error);
    }
  };

  const handleRawJSONChange = (newJSON) => {
    setRawJSON(newJSON);
    try {
      const parsed = JSON.parse(newJSON);
      onChange(parsed);
      
      // Update fields from JSON
      const fields = Object.entries(parsed).map(([key, value]) => ({
        key,
        value: typeof value === 'object' ? JSON.stringify(value) : value.toString(),
        type: typeof value === 'object' ? 'json' : typeof value
      }));
      setMetadataFields(fields);
    } catch (error) {
      // Invalid JSON, don't update metadata object
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className={`text-sm font-medium ${THEME.text.primary}`}>Document Metadata</h4>
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={() => setShowRawJSON(!showRawJSON)}
            className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
          >
            {showRawJSON ? 'Use Form Editor' : 'Use JSON Editor'}
          </button>
        </div>
      </div>

      {showRawJSON ? (
        // Raw JSON Editor
        <div>
          <textarea
            value={rawJSON}
            onChange={(e) => handleRawJSONChange(e.target.value)}
            placeholder='{"title": "My Document", "category": "example", "author": "username"}'
            rows={8}
            className={`w-full px-3 py-2 rounded-md font-mono text-sm ${THEME.forms.textarea}`}
          />
          <p className={`text-xs ${THEME.text.muted} mt-1`}>
            Enter valid JSON metadata. Switch to Form Editor for a guided experience.
          </p>
        </div>
      ) : (
        // Form-based Editor
        <div className="space-y-3">
          {metadataFields.length > 0 && (
            <div className={`${THEME.containers.secondary} rounded-lg p-3 space-y-3 max-h-60 overflow-y-auto`}>
              {metadataFields.map((field, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <input
                    type="text"
                    placeholder="Key"
                    value={field.key}
                    onChange={(e) => updateField(index, 'key', e.target.value)}
                    className={`flex-1 px-2 py-1 text-sm rounded ${THEME.forms.input}`}
                  />
                  <select
                    value={field.type}
                    onChange={(e) => updateField(index, 'type', e.target.value)}
                    className={`px-2 py-1 text-sm rounded ${THEME.forms.select}`}
                  >
                    <option value="string">Text</option>
                    <option value="number">Number</option>
                    <option value="boolean">Boolean</option>
                    <option value="json">JSON</option>
                  </select>
                  {field.type === 'boolean' ? (
                    <select
                      value={field.value}
                      onChange={(e) => updateField(index, 'value', e.target.value)}
                      className={`flex-1 px-2 py-1 text-sm rounded ${THEME.forms.select}`}
                    >
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  ) : (
                    <input
                      type={field.type === 'number' ? 'number' : 'text'}
                      placeholder={field.type === 'json' ? '{"key": "value"}' : 'Value'}
                      value={field.value}
                      onChange={(e) => updateField(index, 'value', e.target.value)}
                      className={`flex-1 px-2 py-1 text-sm rounded ${THEME.forms.input}`}
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => removeField(index)}
                    className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 text-sm px-2 py-1"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          
          <button
            type="button"
            onClick={addField}
            className={`w-full px-3 py-2 text-sm border-2 border-dashed rounded-md transition-colors ${THEME.borders.default} ${THEME.text.secondary} hover:border-slate-400 dark:hover:border-slate-500 hover:${THEME.text.primary}`}
          >
            + Add Metadata Field
          </button>
          
          {metadataFields.length === 0 && (
            <p className={`text-xs ${THEME.text.muted} text-center py-4`}>
              No metadata fields added. Click "Add Metadata Field" to start, or use the JSON Editor.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

const Dashboard = () => {
  const [libraries, setLibraries] = useState({});
  const [systemStatus, setSystemStatus] = useState({});
  const [selectedLibrary, setSelectedLibrary] = useState(null);
  const [libraryDetails, setLibraryDetails] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [selectedCollection, setSelectedCollection] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [documentDetails, setDocumentDetails] = useState(null);
  const [showAddDocument, setShowAddDocument] = useState(false);
  const [newDocumentText, setNewDocumentText] = useState('');
  const [newDocumentMetadata, setNewDocumentMetadata] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview'); // overview, collections, documents, search
  const [mainView, setMainView] = useState('libraries'); // 'libraries' or 'extraction'
  
  // Responsive sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  // Load libraries overview
  useEffect(() => {
    fetchLibrariesOverview();
    
    // Inject styles
    const styleElement = document.createElement('style');
    styleElement.textContent = styles;
    document.head.appendChild(styleElement);
    
    return () => {
      // Cleanup: remove the style element when component unmounts
      document.head.removeChild(styleElement);
    };
  }, []);

  // Auto-close sidebar on mobile
  useEffect(() => {
    const checkIsMobile = () => {
      setIsMobile(window.innerWidth < 1024);
      if (window.innerWidth < 1024) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };
    
    checkIsMobile();
    window.addEventListener('resize', checkIsMobile);
    return () => window.removeEventListener('resize', checkIsMobile);
  }, []);

  const fetchLibrariesOverview = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_CONFIG.ENDPOINTS.LIBRARIES}/`);
      setLibraries(response.data.libraries);
      setSystemStatus(response.data.system_status);
      setError(null);
    } catch (err) {
      console.error('Error fetching libraries:', err);
      setError('Failed to load libraries');
    } finally {
      setLoading(false);
    }
  };

  const fetchLibraryDetails = async (libraryKey) => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_CONFIG.ENDPOINTS.LIBRARIES}/${libraryKey}`);
      setLibraryDetails(response.data);
      setSelectedLibrary(libraryKey);
      setActiveTab('overview');
      setError(null);
      // Reset documents when switching libraries
      setDocuments([]);
      setCurrentPage(1);
      setPagination(null);
    } catch (err) {
      console.error('Error fetching library details:', err);
      setError('Failed to load library details');
    } finally {
      setLoading(false);
    }
  };

  const fetchDocuments = async (libraryKey = selectedLibrary, collection = null, page = 1) => {
    if (!libraryKey) return;

    try {
      setDocumentsLoading(true);
      let url = `${API_CONFIG.ENDPOINTS.LIBRARIES}/${libraryKey}/documents?page=${page}&limit=20`;
      if (collection) {
        url += `&collection=${collection}`;
      }

      const response = await axios.get(url);
      setDocuments(response.data.documents);
      setPagination(response.data.pagination);
      setCurrentPage(page);
      setError(null);
    } catch (err) {
      console.error('Error fetching documents:', err);
      setError('Failed to load documents');
    } finally {
      setDocumentsLoading(false);
    }
  };

  const fetchDocumentDetails = async (libraryKey, documentId) => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_CONFIG.ENDPOINTS.LIBRARIES}/${libraryKey}/documents/${documentId}`);
      setDocumentDetails(response.data);
      setSelectedDocument(documentId);
      setError(null);
    } catch (err) {
      console.error('Error fetching document details:', err);
      setError('Failed to load document details');
    } finally {
      setLoading(false);
    }
  };

  const searchLibrary = async (libraryKey = selectedLibrary, collection = null) => {
    if (!searchQuery.trim()) return;

    try {
      setLoading(true);
      let url = `${API_CONFIG.ENDPOINTS.LIBRARIES}/${libraryKey}/search`;
      if (collection) {
        url = `${API_CONFIG.ENDPOINTS.LIBRARIES}/${libraryKey}/${collection}/search`;
      }

      const response = await axios.post(url, {
        query: searchQuery,
        limit: 20,
        filters: {}
      });

      setSearchResults(response.data);
      setActiveTab('search');
      setError(null);
    } catch (err) {
      console.error('Error searching library:', err);
      setError('Search failed');
    } finally {
      setLoading(false);
    }
  };

  const viewFileContent = async (libraryKey, filePath) => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_CONFIG.ENDPOINTS.LIBRARIES}/${libraryKey}/files/${encodeURIComponent(filePath)}`);
      setFileContent(response.data);
      setSelectedFile(filePath);
      setError(null);
    } catch (err) {
      console.error('Error fetching file content:', err);
      setError('Failed to load file content');
    } finally {
      setLoading(false);
    }
  };

  const downloadFile = (content, filename) => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (timestamp) => {
    return new Date(timestamp * 1000).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const addDocument = async () => {
    if (!selectedLibrary || !newDocumentText.trim()) return;

    try {
      setLoading(true);
      
      let metadata = {};
      if (newDocumentMetadata) {
        try {
          // If newDocumentMetadata is already an object, use it directly
          // If it's a string, try to parse it as JSON
          metadata = typeof newDocumentMetadata === 'string' 
            ? JSON.parse(newDocumentMetadata) 
            : newDocumentMetadata;
        } catch (e) {
          setError('Invalid metadata format');
          return;
        }
      }

      const response = await axios.post(`${API_CONFIG.ENDPOINTS.LIBRARIES}/${selectedLibrary}/documents`, {
        text: newDocumentText,
        metadata: metadata,
        collection: selectedCollection
      });

      setShowAddDocument(false);
      setNewDocumentText('');
      setNewDocumentMetadata('');
      setError(null);
      
      // Refresh documents list
      fetchDocuments();
      
      alert('Document added successfully!');
    } catch (err) {
      console.error('Error adding document:', err);
      setError('Failed to add document');
    } finally {
      setLoading(false);
    }
  };

  const deleteDocument = async (documentId) => {
    if (!selectedLibrary || !documentId) return;
    
    if (!window.confirm('Are you sure you want to delete this document? This action cannot be undone.')) {
      return;
    }

    try {
      setLoading(true);
      await axios.delete(`${API_CONFIG.ENDPOINTS.LIBRARIES}/${selectedLibrary}/documents/${documentId}`);
      
      // Refresh documents list
      fetchDocuments();
      
      // Close document details if it was the deleted document
      if (selectedDocument === documentId) {
        setSelectedDocument(null);
        setDocumentDetails(null);
      }
      
      setError(null);
      alert('Document deleted successfully!');
    } catch (err) {
      console.error('Error deleting document:', err);
      setError('Failed to delete document');
    } finally {
      setLoading(false);
    }
  };

  if (loading && Object.keys(libraries).length === 0) {
    return (
      <div className={`flex items-center justify-center h-screen ${THEME.containers.background}`}>
        <div className={`text-lg ${THEME.text.primary}`}>Loading dashboard...</div>
      </div>
    );
  }

  if (error && Object.keys(libraries).length === 0) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className={`${THEME.status.error.text} text-lg`}>{error}</div>
      </div>
    );
  }

  return (
    <div className={`flex h-screen ${THEME.containers.background} ${THEME.text.primary}`}>
      {/* Mobile Overlay */}
      {sidebarOpen && isMobile && (
        <div 
          className="fixed inset-0 bg-slate-900 bg-opacity-50 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed lg:relative w-64 lg:w-72 h-full ${THEME.containers.card} 
        border-r ${THEME.borders.default} flex flex-col 
        transition-transform duration-300 z-30 shadow-md
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Sidebar Header */}
        <div className={`p-4 border-b ${THEME.borders.default}`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gradient-to-br from-emerald-600 to-emerald-800 dark:from-emerald-500 dark:to-emerald-700 rounded-lg flex items-center justify-center">
                <Icon name="list" className="w-5 h-5 text-white" />
              </div>
              <span className={`font-bold ${THEME.text.primary} text-lg`}>PaleoPal</span>
            </div>
            {/* Close button for mobile */}
            {isMobile && (
              <button
                onClick={() => setSidebarOpen(false)}
                className={`lg:hidden p-1 rounded-lg ${THEME.text.secondary} ${THEME.interactive.hover}`}
              >
                <Icon name="close" className="w-5 h-5" />
              </button>
            )}
          </div>
          
          <h2 className={`font-semibold ${THEME.text.primary} mb-3`}>Libraries</h2>
          <button
            onClick={() => {
              setSelectedLibrary(null);
              setLibraryDetails(null);
              setActiveTab('overview');
              fetchLibrariesOverview();
              if (isMobile) setSidebarOpen(false);
            }}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm ${THEME.buttons.secondary} transition-colors`}
          >
            📊 System Overview
          </button>
        </div>
        
        {/* Sidebar Content */}
        <div className="flex-1 overflow-y-auto">
          {Object.entries(libraries || {}).map(([key, library]) => (
            <div key={key} className={`border-b ${THEME.borders.light}`}>
              <button
                onClick={() => {
                  fetchLibraryDetails(key);
                  if (isMobile) setSidebarOpen(false);
                }}
                className={`w-full text-left p-4 ${THEME.interactive.hover} transition-colors ${
                  selectedLibrary === key ? `${THEME.status.info.background} border-r-2 ${THEME.status.info.border}` : ''
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className={`font-medium ${selectedLibrary === key ? THEME.status.info.text : THEME.text.primary}`}>{library.name}</h3>
                  <span className={`text-xs px-2 py-1 ${THEME.containers.secondary} ${THEME.text.primary} rounded-full`}>
                    {library.total_documents || 0}
                  </span>
                </div>
                <p className={`text-sm mb-2 ${selectedLibrary === key ? THEME.status.info.text : THEME.text.secondary}`}>{library.description}</p>
                <div className="flex flex-wrap gap-1">
                  {(library.collections || []).map((collection) => (
                    <span key={collection} className={`text-xs px-2 py-1 ${THEME.status.info.background} ${THEME.status.info.text} rounded`}>
                      {collection.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </button>
            </div>
          ))}
        </div>

        {/* Sidebar Footer */}
        <div className={`p-4 border-t ${THEME.borders.default}`}>
          <Link
            to="/"
            className={`flex items-center gap-2 ${THEME.text.secondary} hover:${THEME.text.primary} transition-colors text-sm`}
            onClick={() => {
              if (isMobile) setSidebarOpen(false);
            }}
          >
            <span className="text-lg">←</span>
            <span>Back to Chat</span>
          </Link>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className={`sticky top-0 z-10 ${THEME.containers.card} shadow-sm border-b ${THEME.borders.default} px-6 py-4`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              {/* Hamburger Menu for Mobile */}
              {isMobile && (
                <button
                  onClick={() => setSidebarOpen(true)}
                  className={`lg:hidden p-2 rounded-lg ${THEME.text.secondary} ${THEME.interactive.hover}`}
                >
                  <Icon name="menu" className="w-5 h-5" />
                </button>
              )}
              
              <div className="flex items-center space-x-3">
                {!isMobile && (
                  <div className="w-8 h-8 bg-gradient-to-br from-emerald-600 to-emerald-800 dark:from-emerald-500 dark:to-emerald-700 rounded-lg flex items-center justify-center">
                    <Icon name="list" className="w-5 h-5 text-white" />
                  </div>
                )}
                <div>
                  <h1 className={`font-bold ${THEME.text.primary} ${isMobile ? 'text-lg' : 'text-2xl'}`}>
                    {isMobile ? 'Libraries' : 'Libraries Dashboard'}
                  </h1>
                  {!isMobile && (
                    <p className={`${THEME.text.secondary} mt-1`}>Browse and search indexed paleoclimate libraries</p>
                  )}
                </div>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className={`text-sm ${THEME.text.secondary} hidden sm:block`}>
                <span className="font-medium">{systemStatus.total_libraries || 0}</span> libraries •{' '}
                <span className="font-medium">{(systemStatus.total_documents || 0).toLocaleString()}</span> documents
              </div>
              <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                systemStatus.qdrant_status === 'connected' 
                  ? `${THEME.status.success.background} ${THEME.status.success.text}` 
                  : `${THEME.status.error.background} ${THEME.status.error.text}`
              }`}>
                Qdrant: {systemStatus.qdrant_status || 'unknown'}
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto">
          {!selectedLibrary ? (
            // System Overview
            <div className="p-6 overflow-y-auto">
              <div className="w-full">
                <h2 className={`text-xl font-bold ${THEME.text.primary} mb-6`}>System Overview</h2>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                  <div className={`${THEME.containers.card} p-6 rounded-lg shadow border ${THEME.borders.default}`}>
                    <h3 className={`text-lg font-semibold ${THEME.text.primary} mb-2`}>Libraries</h3>
                    <p className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">{systemStatus.total_libraries || 0}</p>
                    <p className={`text-sm ${THEME.text.secondary}`}>Active libraries</p>
                  </div>
                  <div className={`${THEME.containers.card} p-6 rounded-lg shadow border ${THEME.borders.default}`}>
                    <h3 className={`text-lg font-semibold ${THEME.text.primary} mb-2`}>Collections</h3>
                    <p className="text-3xl font-bold text-violet-600 dark:text-violet-400">{systemStatus.total_collections || 0}</p>
                    <p className={`text-sm ${THEME.text.secondary}`}>Qdrant collections</p>
                  </div>
                  <div className={`${THEME.containers.card} p-6 rounded-lg shadow border ${THEME.borders.default}`}>
                    <h3 className={`text-lg font-semibold ${THEME.text.primary} mb-2`}>Documents</h3>
                    <p className="text-3xl font-bold text-amber-600 dark:text-amber-400">{(systemStatus.total_documents || 0).toLocaleString()}</p>
                    <p className={`text-sm ${THEME.text.secondary}`}>Indexed documents</p>
                  </div>
                </div>

                <div className={`${THEME.containers.card} rounded-lg shadow overflow-hidden border ${THEME.borders.default}`}>
                  <div className={`px-6 py-4 border-b ${THEME.borders.default}`}>
                    <h3 className={`text-lg font-semibold ${THEME.text.primary}`}>Library Details</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className={`min-w-full divide-y ${THEME.borders.table}`}>
                      <thead className={`${THEME.containers.secondary}`}>
                        <tr>
                          <th className={`px-6 py-3 text-left text-xs font-medium ${THEME.text.secondary} uppercase tracking-wider`}>Library</th>
                          <th className={`px-6 py-3 text-left text-xs font-medium ${THEME.text.secondary} uppercase tracking-wider`}>Type</th>
                          <th className={`px-6 py-3 text-left text-xs font-medium ${THEME.text.secondary} uppercase tracking-wider`}>Collections</th>
                          <th className={`px-6 py-3 text-left text-xs font-medium ${THEME.text.secondary} uppercase tracking-wider`}>Documents</th>
                        </tr>
                      </thead>
                      <tbody className={`${THEME.containers.card} divide-y ${THEME.borders.table}`}>
                        {Object.entries(libraries || {}).map(([key, library]) => (
                          <tr
                            key={key}
                            onClick={() => fetchLibraryDetails(key)}
                            className={`${THEME.interactive.hover} cursor-pointer`}
                          >
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div>
                                <div className={`text-sm font-medium ${THEME.text.primary}`}>{library.name}</div>
                                <div className={`text-sm ${THEME.text.secondary}`}>{library.description}</div>
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${THEME.status.info.background} ${THEME.status.info.text}`}>
                                {library.type?.replace(/_/g, ' ') || 'unknown'}
                              </span>
                            </td>
                            <td className={`px-6 py-4 whitespace-nowrap text-sm ${THEME.text.secondary}`}>
                              {library.collections?.length || 0}
                            </td>
                            <td className={`px-6 py-4 whitespace-nowrap text-sm ${THEME.text.primary}`}>
                              {(library.total_documents || 0).toLocaleString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            // Library Details
            <div className="flex flex-col h-full">
              {/* Library Header */}
              <div className={`${THEME.containers.card} border-b ${THEME.borders.default} px-6 py-4`}>
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className={`text-xl font-bold ${THEME.text.primary}`}>{libraryDetails?.library.name}</h2>
                    <p className={`${THEME.text.secondary}`}>{libraryDetails?.library.description}</p>
                  </div>
                  <div className="flex items-center space-x-4">
                    <span className={`text-sm ${THEME.text.secondary}`}>
                      {libraryDetails?.library.total_documents || 0} documents
                    </span>
                  </div>
                </div>

                {/* Tabs */}
                <div className="flex space-x-6 mt-4">
                  {['overview', 'collections', 'documents', 'search', 'extraction'].map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                        activeTab === tab
                          ? `border-slate-500 ${THEME.text.primary}`
                          : `border-transparent ${THEME.text.secondary} hover:${THEME.text.primary} hover:border-slate-300 dark:hover:border-slate-600`
                      }`}
                    >
                      {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                  ))}
                </div>

                {/* Search Bar */}
                {activeTab === 'search' && (
                  <div className="mt-4 space-y-4">
                    <div className="flex space-x-4">
                      <div className="flex-1">
                        <input
                          type="text"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          placeholder="Search library..."
                          className={`w-full px-3 py-2 rounded-md ${THEME.forms.input}`}
                          onKeyPress={(e) => e.key === 'Enter' && searchLibrary(selectedLibrary, selectedCollection)}
                        />
                      </div>
                      <div className="w-64">
                        <select
                          value={selectedCollection || ''}
                          onChange={(e) => {
                            const collection = e.target.value || null;
                            setSelectedCollection(collection);
                            // Clear previous search results when collection changes
                            if (searchResults) {
                              setSearchResults(null);
                            }
                          }}
                          className={`w-full px-3 py-2 rounded-md ${THEME.forms.select}`}
                        >
                          <option value="">All Collections</option>
                          {(libraryDetails?.collections || []).map((collection) => (
                            <option key={collection.name} value={collection.name}>
                              {collection.name} ({(collection.documents_count || 0).toLocaleString()})
                            </option>
                          ))}
                        </select>
                      </div>
                      <button
                        onClick={() => searchLibrary(selectedLibrary, selectedCollection)}
                        disabled={!searchQuery.trim() || loading}
                        className={`px-4 py-2 rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${THEME.buttons.primary}`}
                      >
                        Search
                      </button>
                    </div>
                    {selectedCollection && (
                      <div className={`text-sm ${THEME.text.secondary}`}>
                        <span className="font-medium">Searching in:</span> {selectedCollection}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Tab Content */}
              <div className="flex-1 overflow-y-auto p-6">
                {activeTab === 'overview' && libraryDetails && (
                  <div className="w-full">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                      <div className={`${THEME.containers.card} p-6 rounded-lg shadow border ${THEME.borders.default}`}>
                        <h3 className={`text-lg font-semibold ${THEME.text.primary} mb-4`}>Library Info</h3>
                        <dl className="space-y-2">
                          <div>
                            <dt className={`text-sm font-medium ${THEME.text.secondary}`}>Type</dt>
                            <dd className={`text-sm ${THEME.text.primary}`}>{libraryDetails.library.type?.replace(/_/g, ' ') || 'unknown'}</dd>
                          </div>
                          <div>
                            <dt className={`text-sm font-medium ${THEME.text.secondary}`}>Collections</dt>
                            <dd className={`text-sm ${THEME.text.primary}`}>{libraryDetails.library.collections?.length || 0}</dd>
                          </div>
                          <div>
                            <dt className={`text-sm font-medium ${THEME.text.secondary}`}>Total Documents</dt>
                            <dd className={`text-sm ${THEME.text.primary}`}>{(libraryDetails?.library.total_documents || 0).toLocaleString()}</dd>
                          </div>
                        </dl>
                      </div>
                      <div className={`${THEME.containers.card} p-6 rounded-lg shadow border ${THEME.borders.default}`}>
                        <h3 className={`text-lg font-semibold ${THEME.text.primary} mb-4`}>Available Filters</h3>
                        <div className="space-y-2">
                          {Object.entries(libraryDetails.library.available_filters || {}).map(([key, values]) => (
                            <div key={key}>
                              <dt className={`text-sm font-medium ${THEME.text.secondary}`}>{key.replace(/_/g, ' ')}</dt>
                              <dd className={`text-sm ${THEME.text.primary}`}>
                                {Array.isArray(values) && values.length > 0 
                                  ? values.join(', ') 
                                  : 'Dynamic'
                                }
                              </dd>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className={`${THEME.containers.card} rounded-lg shadow border ${THEME.borders.default}`}>
                      <div className={`px-6 py-4 border-b ${THEME.borders.default}`}>
                        <h3 className={`text-lg font-semibold ${THEME.text.primary}`}>Collections</h3>
                      </div>
                      <div className="p-6">
                        <div className="grid gap-4">
                          {(libraryDetails?.collections || []).map((collection) => (
                            <div key={collection.name} className={`border ${THEME.borders.default} rounded-lg p-4 ${THEME.containers.secondary}`}>
                              <div className="flex items-center justify-between mb-2">
                                <h4 className={`font-medium ${THEME.text.primary}`}>{collection.name}</h4>
                                <div className="flex items-center space-x-2">
                                  <span className={`text-sm ${THEME.text.secondary}`}>
                                    {(collection.documents_count || 0).toLocaleString()} docs
                                  </span>
                                  <span className={`px-2 py-1 text-xs rounded-full ${
                                    collection.status === 'green'
                                      ? `${THEME.status.success.background} ${THEME.status.success.text}`
                                      : `${THEME.status.warning.background} ${THEME.status.warning.text}`
                                  }`}>
                                    {collection.status || 'unknown'}
                                  </span>
                                </div>
                              </div>
                              {(collection.sample_documents || []).length > 0 && (
                                <div className="mt-3">
                                  <p className={`text-sm font-medium ${THEME.text.primary} mb-2`}>Sample Documents:</p>
                                  <div className="space-y-1">
                                    {(collection.sample_documents || []).slice(0, 2).map((doc, idx) => (
                                      <div key={idx} className={`text-xs ${THEME.text.secondary} ${THEME.containers.card} p-2 rounded`}>
                                        {doc.title || doc.name || doc.content?.substring(0, 100) + '...'}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === 'collections' && libraryDetails && (
                  <div className="w-full">
                    <div className="grid gap-6">
                      {(libraryDetails.collections || []).map((collection) => (
                        <div key={collection.name} className={`${THEME.containers.card} rounded-lg shadow border ${THEME.borders.default}`}>
                          <div className={`px-6 py-4 border-b ${THEME.borders.default}`}>
                            <div className="flex items-center justify-between">
                              <h3 className={`text-lg font-semibold ${THEME.text.primary}`}>{collection.name}</h3>
                              <div className="flex items-center space-x-4">
                                <span className={`text-sm ${THEME.text.secondary}`}>
                                  {(collection.documents_count || 0).toLocaleString()} documents
                                </span>
                                <button
                                  onClick={() => {
                                    setSelectedCollection(collection.name);
                                    setActiveTab('search');
                                  }}
                                  className={`px-3 py-1 text-sm rounded transition-colors ${THEME.buttons.primary}`}
                                >
                                  Search
                                </button>
                              </div>
                            </div>
                          </div>
                          <div className="p-6">
                            {(collection.sample_documents || []).length > 0 ? (
                              <div>
                                <h4 className={`font-medium ${THEME.text.primary} mb-3`}>Sample Documents</h4>
                                <div className="space-y-3">
                                  {(collection.sample_documents || []).map((doc, idx) => (
                                    <div key={idx} className={`border ${THEME.borders.default} rounded p-3 ${THEME.containers.secondary}`}>
                                      <div className="flex items-start justify-between">
                                        <div className="flex-1 min-w-0">
                                          <p className={`text-sm font-medium ${THEME.text.primary} truncate`}>
                                            {doc.title || doc.name || 'Untitled'}
                                          </p>
                                          <p className={`text-sm ${THEME.text.secondary} mt-1`}>
                                            {doc.content || doc.description || doc.text || ''}
                                          </p>
                                          {doc.score && (
                                            <p className={`text-xs ${THEME.text.muted} mt-1`}>
                                              Similarity: {(doc.score * 100).toFixed(1)}%
                                            </p>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : (
                              <p className={`${THEME.text.secondary}`}>No sample documents available</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {activeTab === 'documents' && libraryDetails && (
                  <div className="w-full">
                    <div className="flex items-center justify-between mb-6">
                      <div>
                        <h3 className={`text-lg font-semibold ${THEME.text.primary}`}>Documents</h3>
                        <p className={`text-sm ${THEME.text.secondary}`}>
                          Browse and manage documents indexed in {libraryDetails.library.name}
                        </p>
                      </div>
                      <div className="flex items-center space-x-4">
                        <select
                          value={selectedCollection || ''}
                          onChange={(e) => {
                            const collection = e.target.value || null;
                            setSelectedCollection(collection);
                            setCurrentPage(1);
                            fetchDocuments(selectedLibrary, collection, 1);
                          }}
                          className={`px-3 py-1 border rounded text-sm ${THEME.borders.default} ${THEME.containers.card} ${THEME.text.primary}`}
                        >
                          <option value="">All Collections</option>
                          {(libraryDetails.collections || []).map((collection) => (
                            <option key={collection.name} value={collection.name}>
                              {collection.name} ({(collection.documents_count || 0).toLocaleString()})
                            </option>
                          ))}
                        </select>
                        <button
                          onClick={() => {
                            setShowAddDocument(true);
                            setNewDocumentText('');
                            setNewDocumentMetadata({});
                          }}
                          className={`px-4 py-2 rounded text-sm transition-colors ${THEME.status.success.text} ${THEME.status.success.background}`}
                        >
                          + Add Document
                        </button>
                        <button
                          onClick={() => fetchDocuments()}
                          disabled={documentsLoading}
                          className={`px-4 py-2 rounded text-sm disabled:opacity-50 transition-colors ${THEME.buttons.primary}`}
                        >
                          {documentsLoading ? 'Loading...' : 'Refresh'}
                        </button>
                      </div>
                    </div>

                    {/* Load documents when tab is activated */}
                    {activeTab === 'documents' && documents.length === 0 && !documentsLoading && (
                      <div className="text-center py-8">
                        <button
                          onClick={() => fetchDocuments()}
                          className={`px-6 py-3 rounded transition-colors ${THEME.buttons.primary}`}
                        >
                          Load Documents
                        </button>
                      </div>
                    )}

                    {/* Documents List */}
                    {documents.length > 0 && (
                      <div className={`${THEME.containers.card} rounded-lg shadow overflow-hidden border ${THEME.borders.default}`}>
                        {/* Pagination Header */}
                        {pagination && (
                          <div className={`px-6 py-3 border-b ${THEME.borders.default} ${THEME.containers.secondary}`}>
                            <div className="flex items-center justify-between">
                              <div className={`text-sm ${THEME.text.secondary}`}>
                                Showing {((currentPage - 1) * pagination.limit) + 1} to {Math.min(currentPage * pagination.limit, pagination.total)} of {pagination.total.toLocaleString()} documents
                              </div>
                              <div className="flex items-center space-x-2">
                                <button
                                  onClick={() => fetchDocuments(selectedLibrary, selectedCollection, currentPage - 1)}
                                  disabled={!pagination.has_prev || documentsLoading}
                                  className={`px-3 py-1 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${THEME.buttons.secondary}`}
                                >
                                  Previous
                                </button>
                                <span className={`text-sm ${THEME.text.secondary}`}>
                                  Page {currentPage} of {pagination.total_pages}
                                </span>
                                <button
                                  onClick={() => fetchDocuments(selectedLibrary, selectedCollection, currentPage + 1)}
                                  disabled={!pagination.has_next || documentsLoading}
                                  className={`px-3 py-1 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${THEME.buttons.secondary}`}
                                >
                                  Next
                                </button>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Documents Cards */}
                        <div className={`divide-y ${THEME.borders.table}`}>
                          {documents.map((doc, idx) => (
                            <div key={doc.id} className={`p-6 ${THEME.interactive.hover} transition-colors`}>
                              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                                {/* Main Content */}
                                <div className="flex-1 min-w-0">
                                  {/* Header with Title and Metadata */}
                                  <div className="flex flex-wrap items-center gap-2 mb-3">
                                    <h4 className={`text-lg font-medium ${THEME.text.primary} truncate`}>
                                      {doc.title || doc.name || doc.symbol || `Document ${idx + 1}`}
                                    </h4>
                                    <span className={`px-2 py-1 rounded text-xs font-medium ${THEME.status.info.background} ${THEME.status.info.text}`}>
                                      {doc.collection}
                                    </span>
                                    {(doc.content_type || doc.category || doc.type) && (
                                      <span className={`px-2 py-1 rounded text-xs ${THEME.containers.secondary} ${THEME.text.primary}`}>
                                        {doc.content_type || doc.category || doc.type}
                                      </span>
                                    )}
                                    <span className={`text-xs ${THEME.text.muted}`}>
                                      ID: {doc.id}
                                    </span>
                                  </div>

                                  {/* Document Content */}
                                  <div className="mb-3">
                                    <div className={`text-sm ${THEME.text.secondary} leading-relaxed`}>
                                      {(doc.text || doc.content || doc.description || '').length > 0 ? (
                                        <div>
                                          {(doc.text || doc.content || doc.description || '').substring(0, 300)}
                                          {(doc.text || doc.content || doc.description || '').length > 300 && (
                                            <span className={THEME.text.muted}>...</span>
                                          )}
                                        </div>
                                      ) : (
                                        <span className={`${THEME.text.muted} italic`}>No content available</span>
                                      )}
                                    </div>
                                  </div>

                                  {/* Source Information */}
                                  {(doc.source || doc.source_file || doc.library) && (
                                    <div className="mb-2">
                                      <div className={`text-xs ${THEME.text.muted}`}>
                                        <span className="font-medium">Source:</span>
                                        <span className={`ml-1 px-2 py-1 rounded max-w-xs inline-block truncate ${THEME.containers.secondary}`}>
                                          {doc.source || doc.source_file || doc.library}
                                        </span>
                                      </div>
                                    </div>
                                  )}

                                  {/* Additional Metadata */}
                                  <div className={`flex flex-wrap gap-4 text-xs ${THEME.text.muted}`}>
                                    {doc.created_at && (
                                      <span>
                                        <span className="font-medium">Created:</span> {new Date(doc.created_at).toLocaleDateString()}
                                      </span>
                                    )}
                                    {doc.updated_at && (
                                      <span>
                                        <span className="font-medium">Updated:</span> {new Date(doc.updated_at).toLocaleDateString()}
                                      </span>
                                    )}
                                    {doc.score && (
                                      <span>
                                        <span className="font-medium">Score:</span> {(doc.score * 100).toFixed(1)}%
                                      </span>
                                    )}
                                  </div>
                                </div>

                                {/* Actions */}
                                <div className="flex lg:flex-col gap-1 lg:ml-4 text-sm">
                                  <button
                                    onClick={() => fetchDocumentDetails(selectedLibrary, doc.id)}
                                    className={`px-3 py-1 rounded transition-colors whitespace-nowrap ${THEME.status.info.text} ${THEME.status.info.background}`}
                                  >
                                    View
                                  </button>
                                  <button
                                    onClick={() => deleteDocument(doc.id)}
                                    className={`px-3 py-1 rounded transition-colors whitespace-nowrap ${THEME.status.error.text} ${THEME.status.error.background}`}
                                  >
                                    Delete
                                  </button>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* Pagination Footer */}
                        {pagination && pagination.total_pages > 1 && (
                          <div className={`px-6 py-3 border-t ${THEME.borders.default} ${THEME.containers.secondary}`}>
                            <div className="flex items-center justify-center space-x-1">
                              <button
                                onClick={() => fetchDocuments(selectedLibrary, selectedCollection, 1)}
                                disabled={currentPage === 1 || documentsLoading}
                                className={`px-3 py-1 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${THEME.buttons.secondary}`}
                              >
                                First
                              </button>
                              {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                                const page = Math.max(1, Math.min(pagination.total_pages - 4, currentPage - 2)) + i;
                                return (
                                  <button
                                    key={page}
                                    onClick={() => fetchDocuments(selectedLibrary, selectedCollection, page)}
                                    disabled={documentsLoading}
                                    className={`px-3 py-1 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${
                                      page === currentPage
                                        ? THEME.buttons.primary
                                        : THEME.buttons.secondary
                                    }`}
                                  >
                                    {page}
                                  </button>
                                );
                              })}
                              <button
                                onClick={() => fetchDocuments(selectedLibrary, selectedCollection, pagination.total_pages)}
                                disabled={currentPage === pagination.total_pages || documentsLoading}
                                className={`px-3 py-1 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${THEME.buttons.secondary}`}
                              >
                                Last
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {documentsLoading && (
                      <div className={`${THEME.containers.card} rounded-lg shadow p-8 text-center border ${THEME.borders.default}`}>
                        <div className={`animate-spin rounded-full h-8 w-8 border-b-2 ${THEME.status.info.border} mx-auto mb-4`}></div>
                        <p className={THEME.text.muted}>Loading documents...</p>
                      </div>
                    )}

                    {documents.length === 0 && !documentsLoading && activeTab === 'documents' && (
                      <div className={`${THEME.containers.card} rounded-lg shadow p-6 text-center border ${THEME.borders.default}`}>
                        <p className={THEME.text.muted}>No documents found</p>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'search' && (
                  <div className="w-full">
                    {searchResults ? (
                      <div className={`${THEME.containers.card} rounded-lg shadow border ${THEME.borders.default}`}>
                        <div className={`px-6 py-4 border-b ${THEME.borders.default}`}>
                          <div className="flex items-center justify-between">
                            <h3 className={`text-lg font-semibold ${THEME.text.primary}`}>
                              Search Results ({searchResults.total_results})
                            </h3>
                            <div className={`flex items-center space-x-4 text-sm ${THEME.text.muted}`}>
                              <span>Query: "{searchQuery}"</span>
                              {selectedCollection ? (
                                <span className={`px-2 py-1 rounded ${THEME.status.info.background} ${THEME.status.info.text}`}>
                                  Collection: {selectedCollection}
                                </span>
                              ) : (
                                <span className={`px-2 py-1 rounded ${THEME.containers.secondary} ${THEME.text.primary}`}>
                                  All Collections
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="p-6">
                          {(searchResults?.results || []).length > 0 ? (
                            <div className="space-y-4">
                              {(searchResults.results || []).map((result, idx) => (
                                <div key={idx} className={`border ${THEME.borders.default} rounded-lg p-4 ${THEME.containers.secondary} hover:shadow-md transition-shadow`}>
                                  <div className="flex items-start justify-between">
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center space-x-2 mb-2">
                                        <h4 className={`text-sm font-medium ${THEME.text.primary}`}>
                                          {result.title || result.name || result.symbol || `Result ${idx + 1}`}
                                        </h4>
                                        {result.collection && (
                                          <span className={`text-xs px-2 py-1 rounded ${THEME.containers.panel} ${THEME.text.secondary}`}>
                                            {result.collection}
                                          </span>
                                        )}
                                      </div>
                                      <p className={`text-sm ${THEME.text.secondary} mt-1 line-clamp-3`}>
                                        {result.description || result.content || result.text || result.narrative || 'No description available'}
                                      </p>
                                      <div className={`flex items-center space-x-4 mt-2 text-xs ${THEME.text.muted}`}>
                                        {result.score && (
                                          <span className={`px-2 py-1 rounded ${THEME.status.info.background} ${THEME.status.info.text}`}>
                                            Similarity: {(result.score * 100).toFixed(1)}%
                                          </span>
                                        )}
                                        {result.category && (
                                          <span>Category: {result.category}</span>
                                        )}
                                        {result.content_type && (
                                          <span>Type: {result.content_type}</span>
                                        )}
                                        {result.source_file && (
                                          <span>Source: {result.source_file}</span>
                                        )}
                                      </div>
                                    </div>
                                    <div className="ml-4 flex-shrink-0">
                                      <button
                                        onClick={() => {
                                          if (result.id) {
                                            fetchDocumentDetails(selectedLibrary, result.id);
                                          } else {
                                            // If no ID available, create a mock document details view
                                            setDocumentDetails({
                                              id: result.id || `search-result-${idx}`,
                                              collection: result.collection || selectedCollection || 'unknown',
                                              library: selectedLibrary,
                                              document: result,
                                              source_info: {
                                                collection: result.collection || selectedCollection || 'unknown',
                                                indexed_at: result.indexed_at || new Date().toISOString(),
                                                source_file: result.source_file || 'Search Result',
                                                content_type: result.content_type || 'search_result',
                                                metadata: Object.fromEntries(
                                                  Object.entries(result).filter(([key, value]) => 
                                                    !['text', 'content', 'description', 'title', 'name', 'id'].includes(key) && 
                                                    value != null
                                                  )
                                                )
                                              }
                                            });
                                          }
                                        }}
                                        className={`px-3 py-1 text-sm rounded transition-colors ${THEME.buttons.primary}`}
                                      >
                                        View Document
                                      </button>
                                    </div>
                                  </div>
                                  
                                  {/* Show additional structured data for complete methods/workflows */}
                                  {result.method_structure && (
                                    <div className={`mt-3 pt-3 border-t ${THEME.borders.default}`}>
                                      <h5 className={`text-xs font-medium ${THEME.text.secondary} mb-2`}>Method Structure</h5>
                                      <div className={`text-xs ${THEME.text.muted}`}>
                                        <p><span className="font-medium">Steps:</span> {result.num_steps || result.method_structure?.steps?.length || 0}</p>
                                        {result.step_categories && result.step_categories.length > 0 && (
                                          <p><span className="font-medium">Categories:</span> {result.step_categories.join(', ')}</p>
                                        )}
                                      </div>
                                    </div>
                                  )}
                                  
                                  {result.workflow_steps && (
                                    <div className={`mt-3 pt-3 border-t ${THEME.borders.default}`}>
                                      <h5 className={`text-xs font-medium ${THEME.text.secondary} mb-2`}>Workflow Structure</h5>
                                      <div className={`text-xs ${THEME.text.muted}`}>
                                        <p><span className="font-medium">Steps:</span> {result.num_steps || result.workflow_steps?.length || 0}</p>
                                        {result.workflow_type && (
                                          <p><span className="font-medium">Type:</span> {result.workflow_type}</p>
                                        )}
                                        {result.complexity && (
                                          <p><span className="font-medium">Complexity:</span> {result.complexity}</p>
                                        )}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className={`${THEME.text.muted} text-center py-8`}>No results found</p>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className={`${THEME.containers.card} rounded-lg shadow p-6 text-center border ${THEME.borders.default}`}>
                        <div className="space-y-4">
                          <p className={THEME.text.muted}>Enter a search query to find documents in this library</p>
                          {libraryDetails?.collections && libraryDetails.collections.length > 0 && (
                            <div className={`text-sm ${THEME.text.muted}`}>
                              <p className="mb-2">Available collections:</p>
                              <div className="flex flex-wrap justify-center gap-2">
                                {libraryDetails.collections.map((collection) => (
                                  <span key={collection.name} className={`px-2 py-1 rounded text-xs ${THEME.containers.secondary} ${THEME.text.secondary}`}>
                                    {collection.name} ({(collection.documents_count || 0).toLocaleString()})
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'extraction' && (
                  <div className="w-full">
                    <div className="mb-6">
                      <h3 className={`text-xl font-bold ${THEME.text.primary} mb-2`}>
                        Document Extraction for {libraryDetails?.library.name}
                      </h3>
                      <p className={THEME.text.secondary}>
                        Extract and index documents directly into this library.
                      </p>
                    </div>
                    <DocumentExtraction 
                      targetLibrary={selectedLibrary}
                      libraryDetails={libraryDetails}
                      onIndexComplete={() => {
                        // Refresh the library details after successful indexing
                        fetchLibraryDetails(selectedLibrary);
                        // Show success message
                        alert('Documents indexed successfully!');
                        // Optionally switch to documents tab to see new content
                        setActiveTab('documents');
                      }}
                    />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
        </div>

      {/* Document Details Modal */}
      {documentDetails && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className={`${THEME.containers.card} rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] flex flex-col border ${THEME.borders.default}`}>
            <div className={`px-6 py-4 border-b ${THEME.borders.default} flex items-center justify-between flex-shrink-0`}>
              <div>
                <h3 className={`text-lg font-semibold ${THEME.text.primary}`}>
                  {documentDetails.document.title || documentDetails.document.name || documentDetails.document.symbol || 'Document Details'}
                </h3>
                <p className={`text-sm ${THEME.text.muted}`}>
                  Collection: {documentDetails.collection} • Library: {documentDetails.library}
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => deleteDocument(documentDetails.id)}
                  className={`px-3 py-1 text-sm rounded transition-colors ${THEME.status.error.text} ${THEME.status.error.background}`}
                >
                  Delete
                </button>
                <button
                  onClick={() => {
                    setDocumentDetails(null);
                    setSelectedDocument(null);
                  }}
                  className={`px-3 py-1 text-sm rounded transition-colors ${THEME.buttons.primary}`}
                >
                  Close
                </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto">
              <div className="p-6">
                {/* Document Content - Full width */}
                <div>
                    <h4 className={`text-md font-semibold ${THEME.text.primary} mb-3`}>Full Document Content</h4>
                    
                    {/* Special handling for complete methods */}
                    {documentDetails.document.content_type === 'complete_method' && documentDetails.document.method_structure ? (
                      <div className="space-y-4">
                        {/* Method Overview */}
                        <div className={`p-4 rounded border ${THEME.status.info.background} ${THEME.status.info.border}`}>
                          <h5 className={`font-semibold ${THEME.status.info.text} mb-2`}>Method: {documentDetails.document.method_name}</h5>
                          <p className={`text-sm ${THEME.status.info.text}`}>{documentDetails.document.description}</p>
                          <div className="flex items-center space-x-4 mt-2 text-xs">
                            <span className={`px-2 py-1 rounded ${THEME.status.info.background} ${THEME.status.info.text}`}>
                              {documentDetails.document.num_steps} steps
                            </span>
                            {documentDetails.document.step_categories && (
                              <span className={`px-2 py-1 rounded ${THEME.status.success.background} ${THEME.status.success.text}`}>
                                {documentDetails.document.step_categories.join(', ')}
                              </span>
                            )}
                          </div>
                        </div>
                        
                        {/* Method Steps */}
                        <div>
                          <h5 className={`font-semibold ${THEME.text.primary} mb-3`}>Method Steps</h5>
                          <div className="space-y-3">
                            {(documentDetails.document.method_structure.steps || []).map((step, idx) => (
                              <div key={idx} className={`p-4 rounded border ${THEME.containers.secondary} ${THEME.borders.default}`}>
                                <div className="flex items-start justify-between mb-2">
                                  <h6 className={`font-medium ${THEME.text.primary}`}>
                                    Step {step.step_number || idx + 1}
                                  </h6>
                                  {step.category && (
                                    <span className={`text-xs px-2 py-1 rounded ${THEME.containers.panel} ${THEME.text.secondary}`}>
                                      {step.category}
                                    </span>
                                  )}
                                </div>
                                <p className={`text-sm ${THEME.text.secondary} mb-2`}>{step.description}</p>
                                {step.inputs && step.inputs.length > 0 && (
                                  <div className="mb-2">
                                    <span className={`text-xs font-medium ${THEME.text.muted}`}>Inputs: </span>
                                    <span className={`text-xs ${THEME.text.muted}`}>{step.inputs.join(', ')}</span>
                                  </div>
                                )}
                                {step.outputs && step.outputs.length > 0 && (
                                  <div className="mb-2">
                                    <span className={`text-xs font-medium ${THEME.text.muted}`}>Outputs: </span>
                                    <span className={`text-xs ${THEME.text.muted}`}>{step.outputs.join(', ')}</span>
                                  </div>
                                )}
                                {step.keywords && step.keywords.length > 0 && (
                                  <div>
                                    <span className={`text-xs font-medium ${THEME.text.muted}`}>Keywords: </span>
                                    <span className={`text-xs ${THEME.text.muted}`}>{step.keywords.join(', ')}</span>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : documentDetails.document.content_type === 'complete_workflow' && documentDetails.document.workflow_steps ? (
                      /* Special handling for complete workflows */
                      <div className="space-y-4">
                        {/* Workflow Overview */}
                        <div className={`p-4 rounded border ${THEME.status.success.background} ${THEME.status.success.border}`}>
                          <h5 className={`font-semibold ${THEME.status.success.text} mb-2`}>Workflow: {documentDetails.document.title}</h5>
                          <p className={`text-sm ${THEME.status.success.text}`}>{documentDetails.document.description}</p>
                          <div className="flex items-center space-x-4 mt-2 text-xs">
                            <span className={`px-2 py-1 rounded ${THEME.status.success.background} ${THEME.status.success.text}`}>
                              {documentDetails.document.num_steps} steps
                            </span>
                            {documentDetails.document.workflow_type && (
                              <span className={`px-2 py-1 rounded ${THEME.status.info.background} ${THEME.status.info.text}`}>
                                {documentDetails.document.workflow_type}
                              </span>
                            )}
                            {documentDetails.document.complexity && (
                              <span className={`px-2 py-1 rounded ${THEME.status.warning.background} ${THEME.status.warning.text}`}>
                                {documentDetails.document.complexity}
                              </span>
                            )}
                          </div>
                        </div>
                        
                        {/* Workflow Steps */}
                        <div>
                          <h5 className={`font-semibold ${THEME.text.primary} mb-3`}>Workflow Steps</h5>
                          <div className="space-y-3">
                            {(documentDetails.document.workflow_steps || []).map((step, idx) => (
                              <div key={idx} className={`p-4 rounded border ${THEME.containers.secondary} ${THEME.borders.default}`}>
                                <div className="flex items-start justify-between mb-2">
                                  <h6 className={`font-medium ${THEME.text.primary}`}>
                                    Step {step.step_number || idx + 1}
                                  </h6>
                                  {step.step_type && (
                                    <span className={`text-xs px-2 py-1 rounded ${THEME.containers.panel} ${THEME.text.secondary}`}>
                                      {step.step_type}
                                    </span>
                                  )}
                                </div>
                                <p className={`text-sm ${THEME.text.secondary} mb-2`}>{step.description}</p>
                                {step.code && (
                                  <div className="mt-2">
                                    <span className={`text-xs font-medium ${THEME.text.muted}`}>Code:</span>
                                    <pre className={`text-xs p-2 rounded mt-1 overflow-x-auto ${THEME.containers.code}`}>
                                      {step.code}
                                    </pre>
                                  </div>
                                )}
                                {step.defined_names && step.defined_names.length > 0 && (
                                  <div className="mt-2">
                                    <span className={`text-xs font-medium ${THEME.text.muted}`}>Defines: </span>
                                    <span className={`text-xs ${THEME.text.muted}`}>{step.defined_names.join(', ')}</span>
                                  </div>
                                )}
                                {step.used_names && step.used_names.length > 0 && (
                                  <div className="mt-2">
                                    <span className={`text-xs font-medium ${THEME.text.muted}`}>Uses: </span>
                                    <span className={`text-xs ${THEME.text.muted}`}>{step.used_names.join(', ')}</span>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : (
                      /* Collection-specific content display */
                      <div className="space-y-4">
                        {/* Debug info - remove this later */}
                        {/* {process.env.NODE_ENV === 'development' && (
                          <div className="text-xs text-neutral-500 dark:text-neutral-400 bg-yellow-50 dark:bg-yellow-900/20 p-2 rounded">
                            Collection: {documentDetails.collection} | 
                            Has code: {!!documentDetails.document.code} | 
                            Has signature: {!!documentDetails.document.signature} | 
                            Has sparql: {!!documentDetails.document.sparql} | 
                            Has query: {!!documentDetails.document.query} | 
                            Has entity_id: {!!documentDetails.document.entity_id} | 
                            Has uri: {!!documentDetails.document.uri}
                          </div>
                        )} */}
                        
                        {/* Description - Always show first */}
                        {(documentDetails.document.description || documentDetails.document.text || documentDetails.document.content) && (
                          <div>
                            <h5 className={`text-sm font-semibold ${THEME.text.primary} mb-2`}>Description</h5>
                            <div className={`p-4 rounded border ${THEME.containers.code} ${THEME.borders.default}`}>
                              <div className={`text-sm ${THEME.text.primary} whitespace-pre-wrap`}>
                                {documentDetails.document.description || documentDetails.document.text || documentDetails.document.content || 'No description available'}
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Collection-specific content */}
                        {documentDetails.document.code && (
                          <div>
                            <h5 className={`text-sm font-semibold ${THEME.text.primary} mb-2`}>Code</h5>
                            <div className={`rounded border ${THEME.containers.syntax} ${THEME.borders.default} overflow-hidden`}>
                              <SyntaxHighlighter
                                language="python"
                                style={isDarkMode() ? oneDark : oneLight}
                                customStyle={{
                                  margin: 0,
                                  padding: '1rem',
                                  backgroundColor: 'transparent',
                                  fontSize: '13px',
                                  fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
                                }}
                              >
                                {documentDetails.document.code}
                              </SyntaxHighlighter>
                            </div>
                          </div>
                        )}

                        {documentDetails.collection === 'readthedocs_symbols' && documentDetails.document.signature && (
                          <div>
                            <h5 className={`text-sm font-semibold ${THEME.text.primary} mb-2`}>Signature</h5>
                            <div className={`rounded border ${THEME.containers.syntax} ${THEME.borders.default} overflow-hidden`}>
                              <SyntaxHighlighter
                                language="python"
                                style={isDarkMode() ? oneDark : oneLight}
                                customStyle={{
                                  margin: 0,
                                  padding: '1rem',
                                  backgroundColor: 'transparent',
                                  fontSize: '13px',
                                  fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
                                }}
                              >
                                {documentDetails.document.signature}
                              </SyntaxHighlighter>
                            </div>
                          </div>
                        )}

                        {documentDetails.collection === 'ontology_entities' && (documentDetails.document.entity_id || documentDetails.document.uri) && (
                          <div>
                            <h5 className={`text-sm font-semibold ${THEME.text.primary} mb-2`}>Entity ID</h5>
                            <div className={`p-4 rounded border ${THEME.containers.code} ${THEME.borders.default}`}>
                              <code className={`text-sm font-mono ${THEME.text.primary} break-all`}>
                                {documentDetails.document.entity_id || documentDetails.document.uri}
                              </code>
                            </div>
                          </div>
                        )}

                        {(documentDetails.document.sparql_query) && (
                          <div>
                            <h5 className={`text-sm font-semibold ${THEME.text.primary} mb-2`}>SPARQL Query</h5>
                            <div className={`rounded border ${THEME.containers.syntax} ${THEME.borders.default} overflow-hidden`}>
                              <SyntaxHighlighter
                                language="sparql"
                                style={isDarkMode() ? oneDark : oneLight}
                                customStyle={{
                                  margin: 0,
                                  padding: '1rem',
                                  backgroundColor: 'transparent',
                                  fontSize: '13px',
                                  fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
                                }}
                              >
                                {documentDetails.document.sparql_query || ''}
                              </SyntaxHighlighter>
                            </div>
                          </div>
                        )}

                      </div>
                    )}
                    
                    {/* Additional Fields - always show */}
                    <div className="mt-4">
                      <h5 className={`text-sm font-semibold ${THEME.text.primary} mb-3`}>Additional Document Fields</h5>
                      <AdditionalFieldsViewer document={documentDetails.document} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
      )}

      {/* Add Document Modal */}
      {showAddDocument && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className={`${THEME.containers.card} rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col border ${THEME.borders.default}`}>
            <div className={`px-6 py-4 border-b ${THEME.borders.default} flex items-center justify-between flex-shrink-0`}>
              <div>
                <h3 className={`text-lg font-semibold ${THEME.text.primary}`}>Add New Document</h3>
                <p className={`text-sm ${THEME.text.secondary} mt-1`}>
                  Add a new document to <span className="font-medium">{libraryDetails?.library.name}</span>
                </p>
              </div>
              <button
                onClick={() => {
                  setShowAddDocument(false);
                  setNewDocumentText('');
                  setNewDocumentMetadata({});
                }}
                className={`${THEME.text.muted} hover:${THEME.text.secondary} text-xl transition-colors`}
              >
                ×
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto">
              <div className="p-6">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Document Settings - Sidebar */}
                  <div className="lg:col-span-1">
                    <h4 className={`text-md font-semibold ${THEME.text.primary} mb-4`}>Document Settings</h4>
                    
                    <div className="space-y-4">
                      {/* Collection Selection */}
                      <div className={`p-4 rounded border ${THEME.containers.secondary} ${THEME.borders.default}`}>
                        <label className={`block text-sm font-medium ${THEME.text.secondary} mb-2`}>
                          Target Collection
                        </label>
                        <select
                          value={selectedCollection || ''}
                          onChange={(e) => setSelectedCollection(e.target.value || null)}
                          className={`w-full px-3 py-2 border rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${THEME.borders.default} ${THEME.containers.card} ${THEME.text.primary}`}
                        >
                          <option value="">Use default collection</option>
                          {(libraryDetails?.collections || []).map((collection) => (
                            <option key={collection.name} value={collection.name}>
                              {collection.name} ({(collection.documents_count || 0).toLocaleString()} docs)
                            </option>
                          ))}
                        </select>
                        <p className={`text-xs ${THEME.text.muted} mt-1`}>
                          Choose which collection to add this document to
                        </p>
                      </div>

                      {/* Document Info */}
                      <div className={`p-4 rounded border ${THEME.status.info.background} ${THEME.status.info.border}`}>
                        <h5 className={`text-sm font-semibold ${THEME.status.info.text} mb-2`}>Document Information</h5>
                        <div className={`space-y-2 text-xs ${THEME.status.info.text}`}>
                          <div>
                            <span className="font-medium">Library:</span> {libraryDetails?.library.name}
                          </div>
                          <div>
                            <span className="font-medium">Type:</span> {libraryDetails?.library.type?.replace(/_/g, ' ') || 'unknown'}
                          </div>
                          <div>
                            <span className="font-medium">Target Collection:</span> {selectedCollection || 'Default'}
                          </div>
                        </div>
                      </div>

                      {/* Quick Tips */}
                      <div className={`p-4 rounded border ${THEME.status.warning.background} ${THEME.status.warning.border}`}>
                        <h5 className={`text-sm font-semibold ${THEME.status.warning.text} mb-2`}>💡 Tips</h5>
                        <ul className={`text-xs ${THEME.status.warning.text} space-y-1`}>
                          <li>• Use clear, descriptive document content</li>
                          <li>• Add relevant metadata for better searchability</li>
                          <li>• Consider the target collection's purpose</li>
                          <li>• Use the form editor for easier metadata input</li>
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* Document Content - Main area */}
                  <div className="lg:col-span-2">
                    <h4 className={`text-md font-semibold ${THEME.text.primary} mb-4`}>Document Content</h4>
                    
                    <div className="space-y-6">
                      {/* Document Text */}
                      <div>
                        <label className={`block text-sm font-medium ${THEME.text.secondary} mb-2`}>
                          Document Text *
                        </label>
                        <div className="relative">
                          <textarea
                            value={newDocumentText}
                            onChange={(e) => setNewDocumentText(e.target.value)}
                            placeholder="Enter the document content here...

Examples:
- Scientific method description
- Research findings
- Analysis workflow
- Data analysis steps
- Technical documentation"
                            rows={12}
                            className={`w-full px-3 py-2 border rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${THEME.borders.default} ${THEME.containers.card} ${THEME.text.primary}`}
                          />
                          <div className={`absolute bottom-2 right-2 text-xs ${THEME.text.muted}`}>
                            {newDocumentText.length} characters
                          </div>
                        </div>
                        <p className={`text-xs ${THEME.text.muted} mt-1`}>
                          The main content of your document. This will be indexed and made searchable.
                        </p>
                      </div>

                      {/* Metadata */}
                      <div className={`border-t ${THEME.borders.default} pt-6`}>
                        <MetadataEditor
                          metadata={newDocumentMetadata}
                          onChange={(metadata) => setNewDocumentMetadata(metadata)}
                        />
                        <p className={`text-xs ${THEME.text.muted} mt-2`}>
                          Metadata helps categorize and find your document later. Common fields include title, author, category, source, date, etc.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer Actions */}
            <div className={`px-6 py-4 border-t ${THEME.borders.default} flex items-center justify-between flex-shrink-0`}>
              <div className={`text-sm ${THEME.text.muted}`}>
                {!newDocumentText.trim() && (
                  <span className={THEME.status.error.text}>⚠ Document text is required</span>
                )}
              </div>
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => {
                    setShowAddDocument(false);
                    setNewDocumentText('');
                    setNewDocumentMetadata({});
                  }}
                  disabled={loading}
                  className={`px-4 py-2 text-sm rounded disabled:opacity-50 transition-colors ${THEME.buttons.secondary}`}
                >
                  Cancel
                </button>
                <button
                  onClick={addDocument}
                  disabled={!newDocumentText.trim() || loading}
                  className={`px-6 py-2 text-sm rounded disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 transition-colors ${THEME.buttons.primary}`}
                >
                  {loading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      <span>Adding...</span>
                    </>
                  ) : (
                    <>
                      <span>✓</span>
                      <span>Add Document</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading Overlay */}
      {loading && (
        <div className="fixed inset-0 bg-black bg-opacity-25 flex items-center justify-center z-40">
          <div className={`${THEME.containers.card} rounded-lg p-4 shadow-xl`}>
            <div className="flex items-center space-x-3">
              <div className={`animate-spin rounded-full h-6 w-6 border-b-2 ${THEME.status.info.border}`}></div>
              <span className={THEME.text.primary}>Loading...</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard; 
