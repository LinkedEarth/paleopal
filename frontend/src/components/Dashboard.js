import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import DocumentExtraction from './DocumentExtraction';
import API_CONFIG from '../config/api';

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
`;

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

  const renderValue = (value, key = '') => {
    if (value === null || value === undefined) {
      return <span className="text-neutral-400 dark:text-neutral-500 italic">null</span>;
    }
    
    if (typeof value === 'boolean') {
      return <span className={`text-xs px-2 py-1 rounded ${value ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300' : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'}`}>
        {value.toString()}
      </span>;
    }
    
    if (typeof value === 'number') {
      return <span className="text-blue-600 dark:text-blue-400 font-mono">{value}</span>;
    }
    
    if (typeof value === 'string') {
      if (value.length > 100) {
        const isExpanded = expandedSections.has(key);
        return (
                  <div>
          <div className="text-sm text-neutral-900 dark:text-neutral-100">
            {isExpanded ? value : `${value.substring(0, 100)}...`}
          </div>
          <button
            onClick={() => toggleSection(key)}
            className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 mt-1"
          >
            {isExpanded ? 'Show less' : 'Show more'}
          </button>
        </div>
      );
    }
    return <span className="text-sm text-neutral-900 dark:text-neutral-100">{value}</span>;
    }
    
    if (Array.isArray(value)) {
      if (value.length === 0) {
        return <span className="text-neutral-400 dark:text-neutral-500 italic">[]</span>;
      }
      
      const isExpanded = expandedSections.has(key);
      return (
        <div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-600 dark:text-neutral-400">Array ({value.length} items)</span>
            <button
              onClick={() => toggleSection(key)}
              className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
            >
              {isExpanded ? '−' : '+'}
            </button>
          </div>
          {isExpanded && (
            <div className="mt-2 space-y-1 max-h-40 overflow-y-auto border-l-2 border-neutral-200 dark:border-neutral-600 pl-3">
              {value.map((item, index) => (
                <div key={index} className="text-xs">
                  <span className="text-neutral-500 dark:text-neutral-400">[{index}]</span> {renderValue(item, `${key}_${index}`)}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }
    
    if (typeof value === 'object') {
      const keys = Object.keys(value);
      if (keys.length === 0) {
        return <span className="text-neutral-400 dark:text-neutral-500 italic">{'{}'}</span>;
      }
      
      const isExpanded = expandedSections.has(key);
      return (
        <div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-600 dark:text-neutral-400">Object ({keys.length} properties)</span>
            <button
              onClick={() => toggleSection(key)}
              className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
            >
              {isExpanded ? '−' : '+'}
            </button>
          </div>
          {isExpanded && (
            <div className="mt-2 space-y-2 max-h-60 overflow-y-auto border-l-2 border-neutral-200 dark:border-neutral-700 pl-3">
              {keys.map((subKey) => (
                <div key={subKey}>
                  <dt className="text-xs font-medium text-neutral-600 dark:text-neutral-400">{subKey}</dt>
                  <dd className="ml-2">{renderValue(value[subKey], `${key}_${subKey}`)}</dd>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }
    
    return <span className="text-sm text-neutral-900 dark:text-neutral-100">{value.toString()}</span>;
  };

  return (
    <div className="bg-neutral-50 dark:bg-neutral-700 p-3 rounded border border-neutral-200 dark:border-neutral-600 max-h-80 overflow-y-auto">
      <div className="space-y-3">
        {Object.entries(metadata).map(([key, value]) => (
          <div key={key} className="border-b border-neutral-200 dark:border-neutral-600 pb-2 last:border-b-0">
            <dt className="text-xs font-medium text-neutral-600 dark:text-neutral-400 uppercase mb-1">{key.replace(/_/g, ' ')}</dt>
            <dd>{renderValue(value, key)}</dd>
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
      return <span className="text-neutral-400 dark:text-neutral-500 italic">null</span>;
    }
    
    if (typeof value === 'object') {
      const isExpanded = expandedFields.has(key);
      return (
        <div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-600 dark:text-neutral-400">
              {Array.isArray(value) ? `Array (${value.length} items)` : `Object (${Object.keys(value).length} properties)`}
            </span>
            <button
              onClick={() => toggleField(key)}
              className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
            >
              {isExpanded ? 'Hide' : 'Show'}
            </button>
          </div>
          {isExpanded && (
            <div className="mt-2 bg-neutral-100 dark:bg-neutral-600 p-2 rounded text-xs font-mono max-h-40 overflow-y-auto">
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
          <div className="text-sm text-neutral-900 dark:text-neutral-100">
            {isExpanded ? value : `${value.substring(0, 200)}...`}
          </div>
          <button
            onClick={() => toggleField(key)}
            className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 mt-1"
          >
            {isExpanded ? 'Show less' : 'Show more'}
          </button>
        </div>
      );
    }
    
    return <span className="text-sm text-neutral-900 dark:text-neutral-100">{value.toString()}</span>;
  };

  const fieldsToShow = Object.entries(document).filter(([key, value]) => 
    !['text', 'content', 'id'].includes(key) && value !== null && value !== undefined
  );

  if (fieldsToShow.length === 0) {
    return <div className="text-sm text-neutral-500 dark:text-neutral-400 italic">No additional fields to display</div>;
  }

  return (
    <div className="bg-neutral-50 dark:bg-neutral-700 p-3 rounded border border-neutral-200 dark:border-neutral-600 max-h-80 overflow-y-auto">
      <div className="space-y-3">
        {fieldsToShow.map(([key, value]) => (
          <div key={key} className="border-b border-neutral-200 dark:border-neutral-600 pb-2 last:border-b-0">
            <dt className="text-xs font-medium text-neutral-600 dark:text-neutral-400 uppercase mb-1">{key.replace(/_/g, ' ')}</dt>
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
        <h4 className="text-sm font-medium text-neutral-900 dark:text-neutral-100">Document Metadata</h4>
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
            className="w-full px-3 py-2 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
          />
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
            Enter valid JSON metadata. Switch to Form Editor for a guided experience.
          </p>
        </div>
      ) : (
        // Form-based Editor
        <div className="space-y-3">
          {metadataFields.length > 0 && (
            <div className="bg-neutral-50 dark:bg-neutral-700 rounded-lg p-3 space-y-3 max-h-60 overflow-y-auto">
              {metadataFields.map((field, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <input
                    type="text"
                    placeholder="Key"
                    value={field.key}
                    onChange={(e) => updateField(index, 'key', e.target.value)}
                    className="flex-1 px-2 py-1 text-sm border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 rounded focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <select
                    value={field.type}
                    onChange={(e) => updateField(index, 'type', e.target.value)}
                    className="px-2 py-1 text-sm border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 rounded focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
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
                      className="flex-1 px-2 py-1 text-sm border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 rounded focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
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
                      className="flex-1 px-2 py-1 text-sm border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 rounded focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
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
            className="w-full px-3 py-2 text-sm border-2 border-dashed border-neutral-300 dark:border-neutral-600 rounded-md text-neutral-600 dark:text-neutral-400 hover:border-neutral-400 dark:hover:border-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors"
          >
            + Add Metadata Field
          </button>
          
          {metadataFields.length === 0 && (
            <p className="text-xs text-neutral-500 dark:text-neutral-400 text-center py-4">
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
      <div className="flex items-center justify-center h-screen">
        <div className="text-lg">Loading dashboard...</div>
      </div>
    );
  }

  if (error && Object.keys(libraries).length === 0) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-red-600 text-lg">{error}</div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-neutral-50 dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100">
      {/* Mobile Overlay */}
      {sidebarOpen && isMobile && (
        <div 
          className="fixed inset-0 bg-neutral-900 bg-opacity-50 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed lg:relative w-64 lg:w-72 h-full bg-white dark:bg-neutral-800 
        border-r border-neutral-200 dark:border-neutral-700 flex flex-col 
        transition-transform duration-300 z-30 shadow-md
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Sidebar Header */}
        <div className="p-4 border-b border-neutral-200 dark:border-neutral-600">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-blue-800 dark:from-blue-500 dark:to-blue-700 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <span className="font-bold text-neutral-900 dark:text-neutral-100 text-lg">PaleoPal</span>
            </div>
            {/* Close button for mobile */}
            {isMobile && (
              <button
                onClick={() => setSidebarOpen(false)}
                className="lg:hidden p-1 rounded-lg text-neutral-500 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-700"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
          
          <h2 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-3">Libraries</h2>
          <button
            onClick={() => {
              setSelectedLibrary(null);
              setLibraryDetails(null);
              setActiveTab('overview');
              fetchLibrariesOverview();
              if (isMobile) setSidebarOpen(false);
            }}
            className="w-full text-left px-3 py-2 rounded-lg text-sm bg-neutral-100 dark:bg-neutral-600 hover:bg-neutral-200 dark:hover:bg-neutral-500 text-neutral-800 dark:text-neutral-100 transition-colors"
          >
            📊 System Overview
          </button>
        </div>
        
        {/* Sidebar Content */}
        <div className="flex-1 overflow-y-auto">
          {Object.entries(libraries || {}).map(([key, library]) => (
            <div key={key} className="border-b border-neutral-100 dark:border-neutral-700">
              <button
                onClick={() => {
                  fetchLibraryDetails(key);
                  if (isMobile) setSidebarOpen(false);
                }}
                className={`w-full text-left p-4 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors ${
                  selectedLibrary === key ? 'bg-blue-50 dark:bg-blue-900/20 border-r-2 border-blue-500 dark:border-blue-400' : ''
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className={`font-medium ${selectedLibrary === key ? 'text-blue-900 dark:text-blue-100' : 'text-neutral-900 dark:text-neutral-100'}`}>{library.name}</h3>
                  <span className="text-xs px-2 py-1 bg-neutral-200 dark:bg-neutral-600 text-neutral-700 dark:text-neutral-300 rounded-full">
                    {library.total_documents || 0}
                  </span>
                </div>
                <p className={`text-sm mb-2 ${selectedLibrary === key ? 'text-blue-700 dark:text-blue-300' : 'text-neutral-600 dark:text-neutral-400'}`}>{library.description}</p>
                <div className="flex flex-wrap gap-1">
                  {(library.collections || []).map((collection) => (
                    <span key={collection} className="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-800/30 text-blue-800 dark:text-blue-300 rounded">
                      {collection.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </button>
            </div>
          ))}
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-neutral-200 dark:border-neutral-600">
          <Link
            to="/"
            className="flex items-center gap-2 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors text-sm"
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
        <div className="sticky top-0 z-10 bg-white dark:bg-neutral-800 shadow-sm border-b border-neutral-200 dark:border-neutral-700 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              {/* Hamburger Menu for Mobile */}
              {isMobile && (
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="lg:hidden p-2 rounded-lg text-neutral-500 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-700"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
              )}
              
              <div className="flex items-center space-x-3">
                {!isMobile && (
                  <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-blue-800 dark:from-blue-500 dark:to-blue-700 rounded-lg flex items-center justify-center">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                  </div>
                )}
                <div>
                  <h1 className={`font-bold text-neutral-900 dark:text-neutral-100 ${isMobile ? 'text-lg' : 'text-2xl'}`}>
                    {isMobile ? 'Libraries' : 'Libraries Dashboard'}
                  </h1>
                  {!isMobile && (
                    <p className="text-neutral-600 dark:text-neutral-400 mt-1">Browse and search indexed paleoclimate libraries</p>
                  )}
                </div>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className="text-sm text-neutral-500 dark:text-neutral-400 hidden sm:block">
                <span className="font-medium">{systemStatus.total_libraries || 0}</span> libraries •{' '}
                <span className="font-medium">{(systemStatus.total_documents || 0).toLocaleString()}</span> documents
              </div>
              <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                systemStatus.qdrant_status === 'connected' 
                  ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300' 
                  : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
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
                <h2 className="text-xl font-bold text-neutral-900 dark:text-neutral-100 mb-6">System Overview</h2>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                  <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg shadow border border-neutral-200 dark:border-neutral-700">
                    <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mb-2">Libraries</h3>
                    <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">{systemStatus.total_libraries || 0}</p>
                    <p className="text-sm text-neutral-600 dark:text-neutral-400">Active libraries</p>
                  </div>
                  <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg shadow border border-neutral-200 dark:border-neutral-700">
                    <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mb-2">Collections</h3>
                    <p className="text-3xl font-bold text-green-600 dark:text-green-400">{systemStatus.total_collections || 0}</p>
                    <p className="text-sm text-neutral-600 dark:text-neutral-400">Qdrant collections</p>
                  </div>
                  <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg shadow border border-neutral-200 dark:border-neutral-700">
                    <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mb-2">Documents</h3>
                    <p className="text-3xl font-bold text-purple-600 dark:text-purple-400">{(systemStatus.total_documents || 0).toLocaleString()}</p>
                    <p className="text-sm text-neutral-600 dark:text-neutral-400">Indexed documents</p>
                  </div>
                </div>

                <div className="bg-white dark:bg-neutral-800 rounded-lg shadow overflow-hidden border border-neutral-200 dark:border-neutral-700">
                  <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-600">
                    <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">Library Details</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-neutral-200 dark:divide-neutral-700">
                      <thead className="bg-neutral-50 dark:bg-neutral-700">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Library</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Type</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Collections</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Documents</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white dark:bg-neutral-800 divide-y divide-neutral-200 dark:divide-neutral-700">
                        {Object.entries(libraries || {}).map(([key, library]) => (
                          <tr
                            key={key}
                            onClick={() => fetchLibraryDetails(key)}
                            className="hover:bg-neutral-50 dark:hover:bg-neutral-700 cursor-pointer"
                          >
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div>
                                <div className="text-sm font-medium text-neutral-900 dark:text-neutral-100">{library.name}</div>
                                <div className="text-sm text-neutral-500 dark:text-neutral-400">{library.description}</div>
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 dark:bg-blue-800/30 text-blue-800 dark:text-blue-300">
                                {library.type?.replace(/_/g, ' ') || 'unknown'}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-neutral-500 dark:text-neutral-400">
                              {library.collections?.length || 0}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-neutral-900 dark:text-neutral-100">
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
              <div className="bg-white dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-neutral-900 dark:text-neutral-100">{libraryDetails?.library.name}</h2>
                    <p className="text-neutral-600 dark:text-neutral-400">{libraryDetails?.library.description}</p>
                  </div>
                  <div className="flex items-center space-x-4">
                    <span className="text-sm text-neutral-500 dark:text-neutral-400">
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
                          ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                          : 'border-transparent text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-300 hover:border-neutral-300 dark:hover:border-neutral-600'
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
                          className="w-full px-3 py-2 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
                          className="w-full px-3 py-2 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
                        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        Search
                      </button>
                    </div>
                    {selectedCollection && (
                      <div className="text-sm text-neutral-600 dark:text-neutral-400">
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
                      <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg shadow border border-neutral-200 dark:border-neutral-700">
                        <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mb-4">Library Info</h3>
                        <dl className="space-y-2">
                          <div>
                            <dt className="text-sm font-medium text-neutral-600 dark:text-neutral-400">Type</dt>
                            <dd className="text-sm text-neutral-900 dark:text-neutral-100">{libraryDetails.library.type?.replace(/_/g, ' ') || 'unknown'}</dd>
                          </div>
                          <div>
                            <dt className="text-sm font-medium text-neutral-600 dark:text-neutral-400">Collections</dt>
                            <dd className="text-sm text-neutral-900 dark:text-neutral-100">{libraryDetails.library.collections?.length || 0}</dd>
                          </div>
                          <div>
                            <dt className="text-sm font-medium text-neutral-600 dark:text-neutral-400">Total Documents</dt>
                            <dd className="text-sm text-neutral-900 dark:text-neutral-100">{(libraryDetails?.library.total_documents || 0).toLocaleString()}</dd>
                          </div>
                        </dl>
                      </div>
                      <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg shadow border border-neutral-200 dark:border-neutral-700">
                        <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mb-4">Available Filters</h3>
                        <div className="space-y-2">
                          {Object.entries(libraryDetails.library.available_filters || {}).map(([key, values]) => (
                            <div key={key}>
                              <dt className="text-sm font-medium text-neutral-600 dark:text-neutral-400">{key.replace(/_/g, ' ')}</dt>
                              <dd className="text-sm text-neutral-900 dark:text-neutral-100">
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

                    <div className="bg-white dark:bg-neutral-800 rounded-lg shadow border border-neutral-200 dark:border-neutral-700">
                      <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-600">
                        <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">Collections</h3>
                      </div>
                      <div className="p-6">
                        <div className="grid gap-4">
                          {(libraryDetails?.collections || []).map((collection) => (
                            <div key={collection.name} className="border border-neutral-200 dark:border-neutral-600 rounded-lg p-4 bg-neutral-50 dark:bg-neutral-700">
                              <div className="flex items-center justify-between mb-2">
                                <h4 className="font-medium text-neutral-900 dark:text-neutral-100">{collection.name}</h4>
                                <div className="flex items-center space-x-2">
                                  <span className="text-sm text-neutral-500 dark:text-neutral-400">
                                    {(collection.documents_count || 0).toLocaleString()} docs
                                  </span>
                                  <span className={`px-2 py-1 text-xs rounded-full ${
                                    collection.status === 'green'
                                      ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
                                      : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300'
                                  }`}>
                                    {collection.status || 'unknown'}
                                  </span>
                                </div>
                              </div>
                              {(collection.sample_documents || []).length > 0 && (
                                <div className="mt-3">
                                  <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">Sample Documents:</p>
                                  <div className="space-y-1">
                                    {(collection.sample_documents || []).slice(0, 2).map((doc, idx) => (
                                      <div key={idx} className="text-xs text-neutral-600 dark:text-neutral-400 bg-neutral-100 dark:bg-neutral-600 p-2 rounded">
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
                        <div key={collection.name} className="bg-white dark:bg-neutral-800 rounded-lg shadow border border-neutral-200 dark:border-neutral-700">
                          <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-600">
                            <div className="flex items-center justify-between">
                              <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">{collection.name}</h3>
                              <div className="flex items-center space-x-4">
                                <span className="text-sm text-neutral-500 dark:text-neutral-400">
                                  {(collection.documents_count || 0).toLocaleString()} documents
                                </span>
                                <button
                                  onClick={() => {
                                    setSelectedCollection(collection.name);
                                    setActiveTab('search');
                                  }}
                                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                                >
                                  Search
                                </button>
                              </div>
                            </div>
                          </div>
                          <div className="p-6">
                            {(collection.sample_documents || []).length > 0 ? (
                              <div>
                                <h4 className="font-medium text-neutral-900 dark:text-neutral-100 mb-3">Sample Documents</h4>
                                <div className="space-y-3">
                                  {(collection.sample_documents || []).map((doc, idx) => (
                                    <div key={idx} className="border border-neutral-200 dark:border-neutral-600 rounded p-3 bg-neutral-50 dark:bg-neutral-700">
                                      <div className="flex items-start justify-between">
                                        <div className="flex-1 min-w-0">
                                          <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">
                                            {doc.title || doc.name || 'Untitled'}
                                          </p>
                                          <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">
                                            {doc.content || doc.description || doc.text || ''}
                                          </p>
                                          {doc.score && (
                                            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
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
                              <p className="text-neutral-500 dark:text-neutral-400">No sample documents available</p>
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
                        <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">Documents</h3>
                        <p className="text-sm text-neutral-600 dark:text-neutral-400">
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
                          className="px-3 py-1 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 rounded text-sm"
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
                          className="px-4 py-2 bg-green-600 text-white rounded text-sm hover:bg-green-700 transition-colors"
                        >
                          + Add Document
                        </button>
                        <button
                          onClick={() => fetchDocuments()}
                          disabled={documentsLoading}
                          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
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
                          className="px-6 py-3 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                        >
                          Load Documents
                        </button>
                      </div>
                    )}

                    {/* Documents List */}
                    {documents.length > 0 && (
                      <div className="bg-white dark:bg-neutral-800 rounded-lg shadow overflow-hidden border border-neutral-200 dark:border-neutral-700">
                        {/* Pagination Header */}
                        {pagination && (
                          <div className="px-6 py-3 border-b border-neutral-200 dark:border-neutral-600 bg-neutral-50 dark:bg-neutral-700">
                            <div className="flex items-center justify-between">
                              <div className="text-sm text-neutral-600 dark:text-neutral-400">
                                Showing {((currentPage - 1) * pagination.limit) + 1} to {Math.min(currentPage * pagination.limit, pagination.total)} of {pagination.total.toLocaleString()} documents
                              </div>
                              <div className="flex items-center space-x-2">
                                <button
                                  onClick={() => fetchDocuments(selectedLibrary, selectedCollection, currentPage - 1)}
                                  disabled={!pagination.has_prev || documentsLoading}
                                  className="px-3 py-1 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-neutral-100 dark:hover:bg-neutral-600 transition-colors"
                                >
                                  Previous
                                </button>
                                <span className="text-sm text-neutral-600 dark:text-neutral-400">
                                  Page {currentPage} of {pagination.total_pages}
                                </span>
                                <button
                                  onClick={() => fetchDocuments(selectedLibrary, selectedCollection, currentPage + 1)}
                                  disabled={!pagination.has_next || documentsLoading}
                                  className="px-3 py-1 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-neutral-100 dark:hover:bg-neutral-600 transition-colors"
                                >
                                  Next
                                </button>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Documents Cards */}
                        <div className="divide-y divide-neutral-200 dark:divide-neutral-600">
                          {documents.map((doc, idx) => (
                            <div key={doc.id} className="p-6 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors">
                              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                                {/* Main Content */}
                                <div className="flex-1 min-w-0">
                                  {/* Header with Title and Metadata */}
                                  <div className="flex flex-wrap items-center gap-2 mb-3">
                                    <h4 className="text-lg font-medium text-neutral-900 dark:text-neutral-100 truncate">
                                      {doc.title || doc.name || doc.symbol || `Document ${idx + 1}`}
                                    </h4>
                                    <span className="px-2 py-1 bg-blue-100 dark:bg-blue-800/30 text-blue-800 dark:text-blue-300 rounded text-xs font-medium">
                                      {doc.collection}
                                    </span>
                                    {(doc.content_type || doc.category || doc.type) && (
                                      <span className="px-2 py-1 bg-neutral-100 dark:bg-neutral-600 text-neutral-700 dark:text-neutral-300 rounded text-xs">
                                        {doc.content_type || doc.category || doc.type}
                                      </span>
                                    )}
                                    <span className="text-xs text-neutral-500 dark:text-neutral-400">
                                      ID: {doc.id}
                                    </span>
                                  </div>

                                  {/* Document Content */}
                                  <div className="mb-3">
                                    <div className="text-sm text-neutral-700 dark:text-neutral-300 leading-relaxed">
                                      {(doc.text || doc.content || doc.description || '').length > 0 ? (
                                        <div>
                                          {(doc.text || doc.content || doc.description || '').substring(0, 300)}
                                          {(doc.text || doc.content || doc.description || '').length > 300 && (
                                            <span className="text-neutral-500 dark:text-neutral-400">...</span>
                                          )}
                                        </div>
                                      ) : (
                                        <span className="text-neutral-400 dark:text-neutral-500 italic">No content available</span>
                                      )}
                                    </div>
                                  </div>

                                  {/* Source Information */}
                                  {(doc.source || doc.source_file || doc.library) && (
                                    <div className="mb-2">
                                      <div className="text-xs text-neutral-500 dark:text-neutral-400">
                                        <span className="font-medium">Source:</span>
                                        <span className="ml-1 bg-neutral-100 dark:bg-neutral-600 px-2 py-1 rounded max-w-xs inline-block truncate">
                                          {doc.source || doc.source_file || doc.library}
                                        </span>
                                      </div>
                                    </div>
                                  )}

                                  {/* Additional Metadata */}
                                  <div className="flex flex-wrap gap-4 text-xs text-neutral-500 dark:text-neutral-400">
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
                                    className="px-3 py-1 text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors whitespace-nowrap"
                                  >
                                    View
                                  </button>
                                  <button
                                    onClick={() => deleteDocument(doc.id)}
                                    className="px-3 py-1 text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors whitespace-nowrap"
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
                          <div className="px-6 py-3 border-t border-neutral-200 dark:border-neutral-600 bg-neutral-50 dark:bg-neutral-700">
                            <div className="flex items-center justify-center space-x-1">
                              <button
                                onClick={() => fetchDocuments(selectedLibrary, selectedCollection, 1)}
                                disabled={currentPage === 1 || documentsLoading}
                                className="px-3 py-1 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-neutral-100 dark:hover:bg-neutral-600 transition-colors"
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
                                    className={`px-3 py-1 border rounded text-sm ${
                                      page === currentPage
                                        ? 'bg-blue-600 text-white border-blue-600'
                                        : 'border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-600'
                                    } disabled:opacity-50 disabled:cursor-not-allowed transition-colors`}
                                  >
                                    {page}
                                  </button>
                                );
                              })}
                              <button
                                onClick={() => fetchDocuments(selectedLibrary, selectedCollection, pagination.total_pages)}
                                disabled={currentPage === pagination.total_pages || documentsLoading}
                                className="px-3 py-1 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-neutral-100 dark:hover:bg-neutral-600 transition-colors"
                              >
                                Last
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {documentsLoading && (
                      <div className="bg-white dark:bg-neutral-800 rounded-lg shadow p-8 text-center border border-neutral-200 dark:border-neutral-700">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
                        <p className="text-neutral-500 dark:text-neutral-400">Loading documents...</p>
                      </div>
                    )}

                    {documents.length === 0 && !documentsLoading && activeTab === 'documents' && (
                      <div className="bg-white dark:bg-neutral-800 rounded-lg shadow p-6 text-center border border-neutral-200 dark:border-neutral-700">
                        <p className="text-neutral-500 dark:text-neutral-400">No documents found</p>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'search' && (
                  <div className="w-full">
                    {searchResults ? (
                      <div className="bg-white dark:bg-neutral-800 rounded-lg shadow border border-neutral-200 dark:border-neutral-700">
                        <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-600">
                          <div className="flex items-center justify-between">
                            <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
                              Search Results ({searchResults.total_results})
                            </h3>
                            <div className="flex items-center space-x-4 text-sm text-neutral-500 dark:text-neutral-400">
                              <span>Query: "{searchQuery}"</span>
                              {selectedCollection ? (
                                <span className="bg-blue-100 dark:bg-blue-800/30 text-blue-800 dark:text-blue-300 px-2 py-1 rounded">
                                  Collection: {selectedCollection}
                                </span>
                              ) : (
                                <span className="bg-neutral-100 dark:bg-neutral-600 text-neutral-800 dark:text-neutral-300 px-2 py-1 rounded">
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
                                <div key={idx} className="border border-neutral-200 dark:border-neutral-600 rounded-lg p-4 bg-neutral-50 dark:bg-neutral-700 hover:shadow-md transition-shadow">
                                  <div className="flex items-start justify-between">
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center space-x-2 mb-2">
                                        <h4 className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                                          {result.title || result.name || result.symbol || `Result ${idx + 1}`}
                                        </h4>
                                        {result.collection && (
                                          <span className="text-xs bg-neutral-100 dark:bg-neutral-600 text-neutral-700 dark:text-neutral-300 px-2 py-1 rounded">
                                            {result.collection}
                                          </span>
                                        )}
                                      </div>
                                      <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1 line-clamp-3">
                                        {result.description || result.content || result.text || result.narrative || 'No description available'}
                                      </p>
                                      <div className="flex items-center space-x-4 mt-2 text-xs text-neutral-500 dark:text-neutral-400">
                                        {result.score && (
                                          <span className="bg-blue-100 dark:bg-blue-800/30 text-blue-800 dark:text-blue-300 px-2 py-1 rounded">
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
                                        className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                                      >
                                        View Document
                                      </button>
                                    </div>
                                  </div>
                                  
                                  {/* Show additional structured data for complete methods/workflows */}
                                  {result.method_structure && (
                                    <div className="mt-3 pt-3 border-t border-neutral-100 dark:border-neutral-600">
                                      <h5 className="text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-2">Method Structure</h5>
                                      <div className="text-xs text-neutral-600 dark:text-neutral-400">
                                        <p><span className="font-medium">Steps:</span> {result.num_steps || result.method_structure?.steps?.length || 0}</p>
                                        {result.step_categories && result.step_categories.length > 0 && (
                                          <p><span className="font-medium">Categories:</span> {result.step_categories.join(', ')}</p>
                                        )}
                                      </div>
                                    </div>
                                  )}
                                  
                                  {result.workflow_steps && (
                                    <div className="mt-3 pt-3 border-t border-neutral-100 dark:border-neutral-600">
                                      <h5 className="text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-2">Workflow Structure</h5>
                                      <div className="text-xs text-neutral-600 dark:text-neutral-400">
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
                            <p className="text-neutral-500 dark:text-neutral-400 text-center py-8">No results found</p>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="bg-white dark:bg-neutral-800 rounded-lg shadow p-6 text-center border border-neutral-200 dark:border-neutral-700">
                        <div className="space-y-4">
                          <p className="text-neutral-500 dark:text-neutral-400">Enter a search query to find documents in this library</p>
                          {libraryDetails?.collections && libraryDetails.collections.length > 0 && (
                            <div className="text-sm text-neutral-400 dark:text-neutral-500">
                              <p className="mb-2">Available collections:</p>
                              <div className="flex flex-wrap justify-center gap-2">
                                {libraryDetails.collections.map((collection) => (
                                  <span key={collection.name} className="bg-neutral-100 dark:bg-neutral-600 text-neutral-600 dark:text-neutral-300 px-2 py-1 rounded text-xs">
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
                      <h3 className="text-xl font-bold text-neutral-900 dark:text-neutral-100 mb-2">
                        Document Extraction for {libraryDetails?.library.name}
                      </h3>
                      <p className="text-neutral-600 dark:text-neutral-400">
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
          <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] flex flex-col border border-neutral-200 dark:border-neutral-700">
            <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-600 flex items-center justify-between flex-shrink-0">
              <div>
                <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
                  {documentDetails.document.title || documentDetails.document.name || documentDetails.document.symbol || 'Document Details'}
                </h3>
                <p className="text-sm text-neutral-500 dark:text-neutral-400">
                  Collection: {documentDetails.collection} • Library: {documentDetails.library}
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => deleteDocument(documentDetails.id)}
                  className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
                >
                  Delete
                </button>
                <button
                  onClick={() => {
                    setDocumentDetails(null);
                    setSelectedDocument(null);
                  }}
                  className="px-3 py-1 text-sm bg-neutral-300 dark:bg-neutral-600 text-neutral-700 dark:text-neutral-300 rounded hover:bg-neutral-400 dark:hover:bg-neutral-500 transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto">
              <div className="p-6">
                <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
                  {/* Source Information - Sidebar */}
                  <div className="xl:col-span-1">
                    <h4 className="text-md font-semibold text-neutral-900 dark:text-neutral-100 mb-3">Source Information</h4>
                    <div className="bg-neutral-50 dark:bg-neutral-700 p-4 rounded border border-neutral-200 dark:border-neutral-600 space-y-3">
                      <div>
                        <dt className="text-xs font-medium text-neutral-600 dark:text-neutral-400 uppercase">Document ID</dt>
                        <dd className="text-sm text-neutral-900 dark:text-neutral-100 font-mono break-all">{documentDetails.id}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium text-neutral-600 dark:text-neutral-400 uppercase">Collection</dt>
                        <dd className="text-sm text-neutral-900 dark:text-neutral-100">{documentDetails.collection}</dd>
                      </div>
                      {documentDetails.source_info.source_file && (
                        <div>
                          <dt className="text-xs font-medium text-neutral-600 dark:text-neutral-400 uppercase">Source File</dt>
                          <dd className="text-sm text-neutral-900 dark:text-neutral-100 break-all">{documentDetails.source_info.source_file}</dd>
                        </div>
                      )}
                      {documentDetails.source_info.content_type && (
                        <div>
                          <dt className="text-xs font-medium text-neutral-600 dark:text-neutral-400 uppercase">Content Type</dt>
                          <dd className="text-sm text-neutral-900 dark:text-neutral-100">{documentDetails.source_info.content_type}</dd>
                        </div>
                      )}
                      {documentDetails.source_info.indexed_at && (
                        <div>
                          <dt className="text-xs font-medium text-neutral-600 dark:text-neutral-400 uppercase">Indexed At</dt>
                          <dd className="text-sm text-neutral-900 dark:text-neutral-100">{new Date(documentDetails.source_info.indexed_at).toLocaleString()}</dd>
                        </div>
                      )}
                    </div>

                    {/* Metadata */}
                    {Object.keys(documentDetails.source_info.metadata || {}).length > 0 && (
                      <div className="mt-4">
                        <h5 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-2">Metadata</h5>
                        <MetadataViewer metadata={documentDetails.source_info.metadata} />
                      </div>
                    )}
                  </div>

                  {/* Document Content - Main area */}
                  <div className="xl:col-span-3">
                    <h4 className="text-md font-semibold text-neutral-900 dark:text-neutral-100 mb-3">Full Document Content</h4>
                    
                    {/* Special handling for complete methods */}
                    {documentDetails.document.content_type === 'complete_method' && documentDetails.document.method_structure ? (
                      <div className="space-y-4">
                        {/* Method Overview */}
                        <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded border border-blue-200 dark:border-blue-700">
                          <h5 className="font-semibold text-blue-900 dark:text-blue-300 mb-2">Method: {documentDetails.document.method_name}</h5>
                          <p className="text-sm text-blue-800 dark:text-blue-300">{documentDetails.document.description}</p>
                          <div className="flex items-center space-x-4 mt-2 text-xs">
                            <span className="bg-blue-200 dark:bg-blue-800/30 text-blue-800 dark:text-blue-300 px-2 py-1 rounded">
                              {documentDetails.document.num_steps} steps
                            </span>
                            {documentDetails.document.step_categories && (
                              <span className="bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 px-2 py-1 rounded">
                                {documentDetails.document.step_categories.join(', ')}
                              </span>
                            )}
                          </div>
                        </div>
                        
                        {/* Method Steps */}
                        <div>
                          <h5 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-3">Method Steps</h5>
                          <div className="space-y-3">
                            {(documentDetails.document.method_structure.steps || []).map((step, idx) => (
                              <div key={idx} className="bg-neutral-50 dark:bg-neutral-700 p-4 rounded border border-neutral-200 dark:border-neutral-600">
                                <div className="flex items-start justify-between mb-2">
                                  <h6 className="font-medium text-neutral-900 dark:text-neutral-100">
                                    Step {step.step_number || idx + 1}
                                  </h6>
                                  {step.category && (
                                    <span className="text-xs bg-neutral-200 dark:bg-neutral-600 text-neutral-700 dark:text-neutral-300 px-2 py-1 rounded">
                                      {step.category}
                                    </span>
                                  )}
                                </div>
                                <p className="text-sm text-neutral-700 dark:text-neutral-300 mb-2">{step.description}</p>
                                {step.inputs && step.inputs.length > 0 && (
                                  <div className="mb-2">
                                    <span className="text-xs font-medium text-neutral-600 dark:text-neutral-400">Inputs: </span>
                                    <span className="text-xs text-neutral-600 dark:text-neutral-400">{step.inputs.join(', ')}</span>
                                  </div>
                                )}
                                {step.outputs && step.outputs.length > 0 && (
                                  <div className="mb-2">
                                    <span className="text-xs font-medium text-neutral-600 dark:text-neutral-400">Outputs: </span>
                                    <span className="text-xs text-neutral-600 dark:text-neutral-400">{step.outputs.join(', ')}</span>
                                  </div>
                                )}
                                {step.keywords && step.keywords.length > 0 && (
                                  <div>
                                    <span className="text-xs font-medium text-neutral-600 dark:text-neutral-400">Keywords: </span>
                                    <span className="text-xs text-neutral-600 dark:text-neutral-400">{step.keywords.join(', ')}</span>
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
                        <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded border border-green-200 dark:border-green-700">
                          <h5 className="font-semibold text-green-900 dark:text-green-300 mb-2">Workflow: {documentDetails.document.title}</h5>
                          <p className="text-sm text-green-800 dark:text-green-300">{documentDetails.document.description}</p>
                          <div className="flex items-center space-x-4 mt-2 text-xs">
                            <span className="bg-green-200 dark:bg-green-800/30 text-green-800 dark:text-green-300 px-2 py-1 rounded">
                              {documentDetails.document.num_steps} steps
                            </span>
                            {documentDetails.document.workflow_type && (
                              <span className="bg-blue-100 dark:bg-blue-800/30 text-blue-800 dark:text-blue-300 px-2 py-1 rounded">
                                {documentDetails.document.workflow_type}
                              </span>
                            )}
                            {documentDetails.document.complexity && (
                              <span className="bg-yellow-100 dark:bg-yellow-800/30 text-yellow-800 dark:text-yellow-300 px-2 py-1 rounded">
                                {documentDetails.document.complexity}
                              </span>
                            )}
                          </div>
                        </div>
                        
                        {/* Workflow Steps */}
                        <div>
                          <h5 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-3">Workflow Steps</h5>
                          <div className="space-y-3">
                            {(documentDetails.document.workflow_steps || []).map((step, idx) => (
                              <div key={idx} className="bg-neutral-50 dark:bg-neutral-700 p-4 rounded border border-neutral-200 dark:border-neutral-600">
                                <div className="flex items-start justify-between mb-2">
                                  <h6 className="font-medium text-neutral-900 dark:text-neutral-100">
                                    Step {step.step_number || idx + 1}
                                  </h6>
                                  {step.step_type && (
                                    <span className="text-xs bg-neutral-200 dark:bg-neutral-600 text-neutral-700 dark:text-neutral-300 px-2 py-1 rounded">
                                      {step.step_type}
                                    </span>
                                  )}
                                </div>
                                <p className="text-sm text-neutral-700 dark:text-neutral-300 mb-2">{step.description}</p>
                                {step.code && (
                                  <div className="mt-2">
                                    <span className="text-xs font-medium text-neutral-600 dark:text-neutral-400">Code:</span>
                                    <pre className="text-xs bg-neutral-100 dark:bg-neutral-600 p-2 rounded mt-1 overflow-x-auto">
                                      {step.code}
                                    </pre>
                                  </div>
                                )}
                                {step.defined_names && step.defined_names.length > 0 && (
                                  <div className="mt-2">
                                    <span className="text-xs font-medium text-neutral-600 dark:text-neutral-400">Defines: </span>
                                    <span className="text-xs text-neutral-600 dark:text-neutral-400">{step.defined_names.join(', ')}</span>
                                  </div>
                                )}
                                {step.used_names && step.used_names.length > 0 && (
                                  <div className="mt-2">
                                    <span className="text-xs font-medium text-neutral-600 dark:text-neutral-400">Uses: </span>
                                    <span className="text-xs text-neutral-600 dark:text-neutral-400">{step.used_names.join(', ')}</span>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : (
                      /* Default content display */
                      <div className="bg-neutral-50 dark:bg-neutral-700 p-4 rounded border border-neutral-200 dark:border-neutral-600 max-h-96 overflow-y-auto">
                        <pre className="text-sm whitespace-pre-wrap font-mono text-neutral-900 dark:text-neutral-100">
                          {documentDetails.document.text || documentDetails.document.content || 'No content available'}
                        </pre>
                      </div>
                    )}
                    
                    {/* Additional Fields - only show for non-structured documents */}
                    {documentDetails.document.content_type !== 'complete_method' && 
                     documentDetails.document.content_type !== 'complete_workflow' && (
                      <div className="mt-4">
                        <h5 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-3">Additional Document Fields</h5>
                        <AdditionalFieldsViewer document={documentDetails.document} />
                      </div>
                    )}
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
          <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col border border-neutral-200 dark:border-neutral-700">
            <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-600 flex items-center justify-between flex-shrink-0">
              <div>
                <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">Add New Document</h3>
                <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">
                  Add a new document to <span className="font-medium">{libraryDetails?.library.name}</span>
                </p>
              </div>
              <button
                onClick={() => {
                  setShowAddDocument(false);
                  setNewDocumentText('');
                  setNewDocumentMetadata({});
                }}
                className="text-neutral-400 dark:text-neutral-500 hover:text-neutral-600 dark:hover:text-neutral-300 text-xl transition-colors"
              >
                ×
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto">
              <div className="p-6">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Document Settings - Sidebar */}
                  <div className="lg:col-span-1">
                    <h4 className="text-md font-semibold text-neutral-900 dark:text-neutral-100 mb-4">Document Settings</h4>
                    
                    <div className="space-y-4">
                      {/* Collection Selection */}
                      <div className="bg-neutral-50 dark:bg-neutral-700 p-4 rounded border border-neutral-200 dark:border-neutral-600">
                        <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                          Target Collection
                        </label>
                        <select
                          value={selectedCollection || ''}
                          onChange={(e) => setSelectedCollection(e.target.value || null)}
                          className="w-full px-3 py-2 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                        >
                          <option value="">Use default collection</option>
                          {(libraryDetails?.collections || []).map((collection) => (
                            <option key={collection.name} value={collection.name}>
                              {collection.name} ({(collection.documents_count || 0).toLocaleString()} docs)
                            </option>
                          ))}
                        </select>
                        <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                          Choose which collection to add this document to
                        </p>
                      </div>

                      {/* Document Info */}
                      <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded border border-blue-200 dark:border-blue-700">
                        <h5 className="text-sm font-semibold text-blue-900 dark:text-blue-300 mb-2">Document Information</h5>
                        <div className="space-y-2 text-xs text-blue-800 dark:text-blue-300">
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
                      <div className="bg-yellow-50 dark:bg-yellow-900/20 p-4 rounded border border-yellow-200 dark:border-yellow-700">
                        <h5 className="text-sm font-semibold text-yellow-900 dark:text-yellow-300 mb-2">💡 Tips</h5>
                        <ul className="text-xs text-yellow-800 dark:text-yellow-300 space-y-1">
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
                    <h4 className="text-md font-semibold text-neutral-900 dark:text-neutral-100 mb-4">Document Content</h4>
                    
                    <div className="space-y-6">
                      {/* Document Text */}
                      <div>
                        <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
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
                            className="w-full px-3 py-2 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                          />
                          <div className="absolute bottom-2 right-2 text-xs text-neutral-400 dark:text-neutral-500">
                            {newDocumentText.length} characters
                          </div>
                        </div>
                        <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                          The main content of your document. This will be indexed and made searchable.
                        </p>
                      </div>

                      {/* Metadata */}
                      <div className="border-t border-neutral-200 dark:border-neutral-600 pt-6">
                        <MetadataEditor
                          metadata={newDocumentMetadata}
                          onChange={(metadata) => setNewDocumentMetadata(metadata)}
                        />
                        <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-2">
                          Metadata helps categorize and find your document later. Common fields include title, author, category, source, date, etc.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer Actions */}
            <div className="px-6 py-4 border-t border-neutral-200 dark:border-neutral-600 flex items-center justify-between flex-shrink-0">
              <div className="text-sm text-neutral-500 dark:text-neutral-400">
                {!newDocumentText.trim() && (
                  <span className="text-red-500 dark:text-red-400">⚠ Document text is required</span>
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
                  className="px-4 py-2 text-sm bg-neutral-300 dark:bg-neutral-600 text-neutral-700 dark:text-neutral-300 rounded hover:bg-neutral-400 dark:hover:bg-neutral-500 disabled:opacity-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={addDocument}
                  disabled={!newDocumentText.trim() || loading}
                  className="px-6 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 transition-colors"
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
          <div className="bg-white rounded-lg p-4 shadow-xl">
            <div className="flex items-center space-x-3">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
              <span>Loading...</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard; 
