import React, { useState, useRef, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import THEME from '../styles/colorTheme';
import { buildApiUrl, apiRequest } from '../config/api';
import API_CONFIG from '../config/api';
import { registerSparqlLanguage } from '../utils/sparql_monaco_definition';
import { createPrismLightTheme, createPrismDarkTheme } from '../utils/monaco_themes';
import Icon from './Icon';

const EditableCodeDisplay = ({ 
  code, 
  sparqlQuery,
  agentType = 'code', 
  messageId,
  isDarkMode = false,
  onExecutionComplete,
  onError,
  onSave,
  onIndex,
  allMessages = [],
  hasCode = false,
  hasSparql = false
}) => {
  const [editedCode, setEditedCode] = useState(code || '');
  const [editedSparql, setEditedSparql] = useState(sparqlQuery || '');
  const [isExecuting, setIsExecuting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showCopyNotification, setShowCopyNotification] = useState(false);
  const [showSaveNotification, setShowSaveNotification] = useState(false);
  const [showIndexModal, setShowIndexModal] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(false);
  
  const editorRef = useRef(null);
  const sparqlRegisteredRef = useRef(false);

  // Get initial content based on agent type
  const getInitialContent = () => {
    if (agentType === 'sparql' && sparqlQuery) {
      return sparqlQuery;
    }
    return code || '';
  };

  const [originalContent, setOriginalContent] = useState(getInitialContent());

  // Get current edited content
  const getCurrentContent = () => {
    if (agentType === 'sparql' && sparqlQuery) {
      return editedSparql;
    }
    return editedCode;
  };

  // Check if content has been modified (dirty state)
  const isDirty = () => {
    const currentContent = getCurrentContent();
    return currentContent !== originalContent;
  };

  // Update original content when props change
  useEffect(() => {
    const initialContent = getInitialContent();
    if (agentType === 'sparql' && sparqlQuery) {
      setEditedSparql(sparqlQuery);
    } else if (code) {
      setEditedCode(code);
    }
    setOriginalContent(initialContent);
  }, [code, sparqlQuery, agentType]);

  // Get editor language
  const getEditorLanguage = () => {
    return agentType === 'sparql' ? 'sparql' : 'python';
  };

  // Check if any operation is in progress
  const isOperationInProgress = () => {
    return isSaving || isExecuting;
  };

  // Monaco Editor configuration
  const getEditorTheme = () => {
    // Use default themes initially to avoid race condition
    // Custom themes will be applied after registration in handleEditorDidMount
    return isDarkMode ? 'vs-dark' : 'vs';
  };

  const getEditorOptions = () => {
    const isMobile = window.innerWidth < 640; // Tailwind's sm breakpoint
    
    return {
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      fontSize: isMobile ? 12 : 13,
      fontFamily: '"Fira Code", "Fira Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace',
      lineNumbers: isMobile ? 'off' : 'on',
      lineDecorationsWidth: isMobile ? 0 : undefined,
      lineNumbersMinChars: isMobile ? 0 : undefined,
      glyphMargin: false,
      folding: isMobile ? false : true,
      roundedSelection: false,
      automaticLayout: true,
      wordWrap: 'off',
      tabSize: 2,
      insertSpaces: true,
      renderLineHighlight: 'line',
      selectionHighlight: false,
      occurrencesHighlight: false,
      renderWhitespace: 'none',
      matchBrackets: 'always',
      autoIndent: 'full',
      formatOnPaste: true,
      formatOnType: true,
      // Allow default scrollbars and behaviour
      overviewRulerLanes: 0,
      // Disable hover widgets on mobile
      hover: {
        enabled: !isMobile
      },
      // Disable parameter hints on mobile
      parameterHints: {
        enabled: !isMobile
      },
      // Disable suggestions widget on mobile
      suggest: {
        enabled: !isMobile
      },
      // Disable editor when operation is in progress
      readOnly: isOperationInProgress(),
    };
  };

  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;

    if (agentType === 'sparql' && !sparqlRegisteredRef.current) {
      try {
        registerSparqlLanguage(monaco);
        sparqlRegisteredRef.current = true;
      } catch (err) {
        console.warn('SPARQL language registration failed:', err);
      }
    }

    // Register custom themes
    createPrismLightTheme(monaco);
    createPrismDarkTheme(monaco);
    
    // Apply the custom theme after registration
    const customTheme = isDarkMode ? 'prism-dark' : 'prism-light';
    monaco.editor.setTheme(customTheme);
  };

  // Update theme when dark mode changes
  useEffect(() => {
    if (editorRef.current && editorRef.current.getModel()) {
      const customTheme = isDarkMode ? 'prism-dark' : 'prism-light';
      // Apply theme directly to the editor instance
      try {
        editorRef.current.updateOptions({ theme: customTheme });
      } catch (err) {
        // If custom themes aren't registered yet, ignore
        console.warn('Custom theme not available yet');
      }
    }
  }, [isDarkMode]);

  // Update editor options when focus state changes
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.updateOptions(getEditorOptions());
    }
  }, [isSaving, isExecuting]);

  // Update editor read-only state when operation status changes
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.updateOptions({ readOnly: isOperationInProgress() });
    }
  }, [isSaving, isExecuting]);

  // Update editor options on window resize for mobile optimization
  useEffect(() => {
    const handleResize = () => {
      if (editorRef.current) {
        editorRef.current.updateOptions(getEditorOptions());
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [isOperationInProgress]);

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setShowCopyNotification(true);
      setTimeout(() => setShowCopyNotification(false), 2000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  const handleSave = async () => {
    if (!onSave || !isDirty() || isOperationInProgress()) return;
    
    setIsSaving(true);
    try {
      const currentContent = getCurrentContent();
      
      const url = buildApiUrl(`/api/messages/${messageId}`);
      const response = await apiRequest(url, {
        method: 'PUT',
        body: JSON.stringify({
          ...(agentType === 'sparql' && sparqlQuery ? { sparql_query: currentContent } : { code: currentContent })
        })
      });
      
      if (response.success) {
        // Update the original content reference to mark as clean
        setOriginalContent(currentContent);
        
        setShowSaveNotification(true);
        setTimeout(() => setShowSaveNotification(false), 2000);
        
        if (onSave) {
          onSave(currentContent);
        }
      } else {
        onError?.('Failed to save changes');
      }
    } catch (error) {
      console.error('Error saving changes:', error);
      onError?.(error.message || 'Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };

  const handleExecute = async () => {
    if (isOperationInProgress() || !messageId) return;
    
    setIsExecuting(true);
    try {
      const currentContent = getCurrentContent();
      
      // Prepare request data based on agent type
      const requestData = {
        clear_variables: false // Don't clear variables by default
      };
      
      if (agentType === 'sparql' && sparqlQuery) {
        requestData.generated_sparql = currentContent;
      } else {
        requestData.generated_code = currentContent;
      }
      
      const url = buildApiUrl(`/api/messages/${messageId}/edit-and-execute`);
      const response = await apiRequest(url, {
        method: 'POST',
        body: JSON.stringify(requestData)
      });
      
      if (response.success) {
        onExecutionComplete?.(response);
      } else {
        onError?.('Execution failed');
      }
    } catch (error) {
      console.error('Error executing code:', error);
      onError?.(error.message || 'Failed to execute code');
    } finally {
      setIsExecuting(false);
    }
  };

  const handleIndex = () => {
    if (onIndex) {
      onIndex();
    } else {
      setShowIndexModal(true);
    }
  };

  const displayContent = getInitialContent();

  if (!displayContent) {
    return null;
  }

  return (
    <div className={`space-y-4 ${isFullScreen ? 'fixed inset-0 z-[9999] bg-white dark:bg-slate-900 p-4 overflow-auto' : ''}`}>
      {/* Copy notification */}
      {showCopyNotification && (
        <div className={`absolute top-2 right-2 z-20 px-3 py-1 ${THEME.status.success.background} ${THEME.status.success.text} text-xs rounded-lg shadow-lg`}>
          ✓ Copied!
        </div>
      )}
      
      {/* Save notification */}
      {showSaveNotification && (
        <div className={`absolute top-2 right-2 z-20 px-3 py-1 ${THEME.status.success.background} ${THEME.status.success.text} text-xs rounded-lg shadow-lg`}>
          ✓ Saved!
        </div>
      )}
      
      {/* Header with title and action buttons */}
      <div className="space-y-2">
        <div className={`flex justify-between items-center ${isOperationInProgress() ? 'opacity-75' : ''}`}>
          <div className={`flex items-center gap-2 ${THEME.text.primary}`}>
            {agentType === 'sparql' ? (
              <>
                <Icon name="database" className="w-4 h-4" />
                <span className="font-medium">Generated SPARQL</span>
              </>
            ) : (
              <>
                <Icon name="code" className="w-4 h-4" />
                <span className="font-medium">Generated Code</span>
              </>
            )}
            {/* Dirty state indicator */}
            {isDirty() && !isOperationInProgress() && (
              <span className={`text-xs px-2 py-1 rounded ${THEME.status.warning.background} ${THEME.status.warning.text} flex items-center gap-1`}>
                <div className="w-2 h-2 bg-current rounded-full"></div>
                Modified
              </span>
            )}
            {/* Operation status indicator */}
            {isSaving && (
              <span className={`text-xs px-2 py-1 rounded ${THEME.status.info.background} ${THEME.status.info.text} flex items-center gap-1`}>
                <Icon name="spinner" className="w-3 h-3 animate-spin" />
                Saving...
              </span>
            )}
            {isExecuting && (
              <span className={`text-xs px-2 py-1 rounded ${THEME.status.warning.background} ${THEME.status.warning.text} flex items-center gap-1`}>
                <Icon name="spinner" className="w-3 h-3 animate-spin" />
                Executing...
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {/* Full-screen toggle */}
            <button
              className={`p-1.5 ${THEME.containers.card} border ${THEME.borders.default} rounded ${THEME.interactive.hover} transition-colors duration-200`}
              onClick={() => setIsFullScreen((prev) => !prev)}
              title={isFullScreen ? 'Exit full screen' : 'Full screen'}
            >
              <Icon name={isFullScreen ? 'fullscreenExit' : 'fullscreen'} className={`w-4 h-4 ${THEME.text.secondary}`} />
            </button>
            
            {/* Save button - icon only */}
            <button 
              className={`p-1.5 ${isDirty() ? THEME.buttons.primary : THEME.containers.card} border ${isDirty() ? 'border-transparent' : THEME.borders.default} rounded transition-colors duration-200 ${isSaving ? 'opacity-75' : ''} ${isExecuting ? 'opacity-50 cursor-not-allowed' : ''} ${isDirty() ? 'hover:opacity-90' : THEME.interactive.hover}`}
              onClick={handleSave}
              disabled={isOperationInProgress()}
              title={isDirty() ? "Save changes" : "No changes to save"}
            >
              <Icon name={isSaving ? "spinner" : "save"} className={`w-4 h-4 ${isDirty() ? 'text-white' : THEME.text.secondary} ${isSaving ? 'animate-spin' : ''}`} />
            </button>
            
            {/* Execute button - icon only */}
            <button 
              className={`p-1.5 ${THEME.buttons.primary} rounded transition-colors duration-200 ${isExecuting ? 'opacity-75' : ''} ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
              onClick={handleExecute}
              disabled={isOperationInProgress()}
              title="Execute code"
            >
              <Icon name={isExecuting ? "spinner" : "play"} className={`w-4 h-4 text-white ${isExecuting ? 'animate-spin' : ''}`} />
            </button>
            
            {/* Index button */}
            <button 
              className={`p-1.5 ${THEME.containers.card} border ${THEME.borders.default} rounded ${THEME.interactive.hover} transition-colors duration-200 ${isOperationInProgress() ? 'opacity-50 cursor-not-allowed' : ''}`}
              onClick={handleIndex}
              disabled={isOperationInProgress()}
              title="Index as learned content"
            >
              <Icon name="index" className={`w-4 h-4 ${THEME.text.secondary}`} />
            </button>
          </div>
        </div>
        <hr className={`border-t ${THEME.borders.default}`} />
      </div>
      
      {/* Editor - always visible, no viewer mode */}
      <div className="relative">
        {/* Loading overlay */}
        {isOperationInProgress() && (
          <div className="absolute inset-0 bg-black bg-opacity-10 z-10 flex items-center justify-center rounded">
            <div className={`${THEME.containers.card} px-4 py-2 rounded-lg shadow-lg border ${THEME.borders.default} flex items-center gap-2`}>
              <Icon name="spinner" className={`w-4 h-4 ${THEME.text.primary} animate-spin`} />
              <span className={`text-sm ${THEME.text.primary}`}>
                {isSaving ? 'Saving changes...' : 'Executing code...'}
              </span>
            </div>
          </div>
        )}
        
        <div className={`overflow-hidden ${isOperationInProgress() ? 'opacity-60' : ''}`}>
          <Editor
            height={isFullScreen ? "calc(100vh - 100px)" : "400px"}
            language={getEditorLanguage()}
            theme={getEditorTheme()}
            value={getCurrentContent()}
            onChange={(value) => {
              if (agentType === 'sparql' && sparqlQuery) {
                setEditedSparql(value || '');
              } else {
                setEditedCode(value || '');
              }
            }}
            onMount={handleEditorDidMount}
            options={getEditorOptions()}
            loading={
              <div className="flex items-center justify-center h-48">
                <Icon name="spinner" className={`${THEME.text.secondary} w-5 h-5 animate-spin`} />
              </div>
            }
          />
        </div>
        {agentType === 'sparql' && sparqlQuery && (
          <p className={`text-xs ${THEME.text.muted} pt-2 ${isOperationInProgress() ? 'opacity-60' : ''}`}>
            Python code will be automatically generated to execute this SPARQL query.
          </p>
        )}
      </div>
      
      {/* Index Modal - if not handled externally */}
      {showIndexModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className={`${THEME.containers.card} rounded-lg p-6 max-w-md w-full mx-4`}>
            <h3 className={`text-lg font-medium ${THEME.text.primary} mb-4`}>Index as Learned Content</h3>
            <p className={`text-sm ${THEME.text.secondary} mb-4`}>
              This will save the code/query as learned content for future reference.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowIndexModal(false)}
                className={`px-3 py-2 text-sm ${THEME.buttons.secondary} rounded`}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowIndexModal(false);
                  // Implement indexing logic here
                }}
                className={`px-3 py-2 text-sm ${THEME.buttons.primary} rounded`}
              >
                Index
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EditableCodeDisplay; 