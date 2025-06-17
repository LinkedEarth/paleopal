import React, { useState, useRef, useEffect } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
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
  hideHeader = false,
  isEditingExternal = null,
  clearVariablesExternal = null,
  onExecutionComplete,
  onError,
  onEdit,
  onCopy,
  onCancel,
  onExecuteRef
}) => {
  const [isEditingInternal, setIsEditingInternal] = useState(false);
  const [editedCode, setEditedCode] = useState(code || '');
  const [editedSparql, setEditedSparql] = useState(sparqlQuery || '');
  const [isExecuting, setIsExecuting] = useState(false);
  const [showCopyNotification, setShowCopyNotification] = useState(false);
  const [clearVariablesInternal, setClearVariablesInternal] = useState(true);
  
  const editorRef = useRef(null);

  // Use external editing state if provided, otherwise use internal state
  const isEditing = isEditingExternal !== null ? isEditingExternal : isEditingInternal;
  
  // Use external clear variables state if provided, otherwise use internal state
  const clearVariables = clearVariablesExternal !== null ? clearVariablesExternal : clearVariablesInternal;

  // Pass execute function to parent via ref callback
  useEffect(() => {
    if (onExecuteRef) {
      onExecuteRef(() => handleExecute()); // always pass a fresh function referencing latest state
    }
  }, [onExecuteRef, editedCode, editedSparql, clearVariables]);

  // Ensure SPARQL language is registered only once per page
  const sparqlRegisteredRef = useRef(false);

  // Monaco Editor configuration


  const getEditorTheme = () => {
    return isDarkMode ? 'prism-dark' : 'prism-light';
  };

  const getEditorOptions = () => {
    return {
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      fontSize: 13,
      fontFamily: '"Fira Code", "Fira Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace',
      lineNumbers: 'on',
      roundedSelection: false,
      scrollbar: {
        vertical: 'auto',
        horizontal: 'auto',
        verticalScrollbarSize: 8,
        horizontalScrollbarSize: 8,
      },
      automaticLayout: true,
      wordWrap: 'off',
      tabSize: 2,
      insertSpaces: true,
      renderLineHighlight: 'line',
      selectionHighlight: false,
      occurrencesHighlight: false,
      renderWhitespace: 'none',
    //   folding: false,
    //   glyphMargin: false,
    //   lineDecorationsWidth: 0,
    //   lineNumbersMinChars: 0,
    //   foldingHighlight: false,
    //   showFoldingControls: false,
      matchBrackets: 'always',
      autoIndent: 'full',
      formatOnPaste: true,
      formatOnType: true,
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

    // Register custom themes (idempotent inside util)
    createPrismLightTheme(monaco);
    createPrismDarkTheme(monaco);
    
    // Focus the editor when it mounts during editing
    if (isEditing) {
      editor.focus();
    }
  };

  const copyToClipboard = async (text) => {
    if (onCopy) {
      onCopy(text);
      return;
    }
    
    try {
      await navigator.clipboard.writeText(text);
      setShowCopyNotification(true);
      setTimeout(() => setShowCopyNotification(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleEdit = () => {
    if (onEdit) {
      onEdit();
      return;
    }
    
    setIsEditingInternal(true);
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    } else {
      setIsEditingInternal(false);
    }
    setEditedCode(code || '');
    setEditedSparql(sparqlQuery || '');
  };

  const handleExecute = async () => {
    if (!messageId) {
      onError?.('No message ID provided for execution');
      return;
    }

    setIsExecuting(true);
    try {
      const requestData = {
        clear_variables: clearVariables
      };

      // Add the appropriate content based on agent type
      if (agentType === 'sparql' && editedSparql) {
        requestData.generated_sparql = editedSparql;
      }
      if (editedCode) {
        requestData.generated_code = editedCode;
      }

      const url = buildApiUrl(`${API_CONFIG.ENDPOINTS.MESSAGES}/${messageId}/edit-and-execute`);
      const response = await apiRequest(url, {
        method: 'POST',
        body: JSON.stringify(requestData)
      });

      if (response.success) {
        setIsEditingInternal(false);
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

  const getSyntaxLanguage = () => {
    return agentType === 'sparql' ? 'sparql' : 'python';
  };

  const getDisplayContent = () => {
    if (isEditing) {
      if (agentType === 'sparql' && editedSparql) {
        return editedSparql;
      }
      return editedCode;
    }
    
    if (agentType === 'sparql' && sparqlQuery) {
      return sparqlQuery;
    }
    return code || '';
  };

  const getIcon = () => {
    if (agentType === 'sparql' && sparqlQuery) {
      return <Icon name="database" className="w-4 h-4" />;
    }
    return <Icon name="code" className="w-4 h-4" />;
  };

  const displayContent = getDisplayContent();

  if (!displayContent) {
    return null;
  }

  return (
    <div className={hideHeader ? '' : `border ${THEME.borders.default} rounded-lg ${THEME.containers.panel} relative group`}>
      {/* Copy notification */}
      {!hideHeader && showCopyNotification && (
        <div className={`absolute top-2 left-2 z-20 px-3 py-1 ${THEME.status.success.background} ${THEME.status.success.text} text-xs rounded-lg shadow-lg`}>
          ✓ Copied!
        </div>
      )}
      
      {/* Header with actions */}
      {!hideHeader && (
        <div className={`flex justify-between items-center p-3 border-b ${THEME.borders.default} ${THEME.containers.card} rounded-t-lg`}>
          <h4 className={`${THEME.text.primary} font-medium text-sm m-0 flex items-center gap-2`}>
            {isEditing && (
              <span className={`text-xs px-2 py-1 rounded ${THEME.status.info.background} ${THEME.status.info.text}`}>
                Editing
              </span>
            )}
          </h4>
          
          <div className="flex items-center gap-2">
            {!isEditing && (
              <>
                <button 
                  className={`p-1.5 ${THEME.containers.card} border ${THEME.borders.default} rounded opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${THEME.interactive.hover}`}
                  onClick={() => copyToClipboard(displayContent)}
                  title="Copy to clipboard"
                >
                  <Icon name="copy" className={`w-4 h-4 ${THEME.text.secondary}`} />
                </button>
                
                <button 
                  className={`p-1.5 ${THEME.containers.card} border ${THEME.borders.default} rounded opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${THEME.interactive.hover}`}
                  onClick={handleEdit}
                  title="Edit and re-execute"
                >
                  <Icon name="edit" className={`w-4 h-4 ${THEME.text.secondary}`} />
                </button>
              </>
            )}
            
            {isEditing && (
              <>
                <button 
                  className={`px-3 py-1.5 text-sm ${THEME.buttons.secondary} rounded transition-colors duration-200`}
                  onClick={handleCancel}
                  disabled={isExecuting}
                >
                  Cancel
                </button>
                
                <button 
                  className={`px-3 py-1.5 text-sm ${THEME.buttons.primary} rounded transition-colors duration-200 flex items-center gap-2`}
                  onClick={handleExecute}
                  disabled={isExecuting}
                >
                  {isExecuting ? (
                    <>
                      <Icon name="spinner" />
                      Executing...
                    </>
                  ) : (
                    "Save and Execute"
                  )}
                </button>
              </>
            )}
          </div>
        </div>
      )}
      
      {/* Options for editing */}
      {isEditing && !hideHeader && (
        <div className={`p-3 border-b ${THEME.borders.default} ${THEME.containers.secondary}`}>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={clearVariables}
              onChange={(e) => setClearVariablesInternal(e.target.checked)}
              className={`rounded border ${THEME.borders.default} ${THEME.forms.checkbox}`}
            />
            <span className={THEME.text.secondary}>
              Clear previous variables before execution
            </span>
          </label>
        </div>
      )}
      
      {/* Content area */}
      <div className={hideHeader ? '' : 'p-3'}>
        {isEditing ? (
          <div className="space-y-3">
            {/* SPARQL editing for SPARQL agents */}
            {agentType === 'sparql' && sparqlQuery ? (
              <div>
                <div className={`border ${THEME.borders.default} rounded overflow-hidden`} style={{ height: '380px' }}>
                  <Editor
                    height="380px"
                    language="sparql"
                    theme={getEditorTheme()}
                    value={editedSparql}
                    onChange={(value) => setEditedSparql(value || '')}
                    onMount={handleEditorDidMount}
                    options={getEditorOptions()}
                    loading={
                      <div className="flex items-center justify-center h-full">
                        <Icon name="spinner" className={`${THEME.text.secondary} w-5 h-5`} />
                      </div>
                    }
                  />
                </div>
                <p className={`text-xs ${THEME.text.muted} mt-2`}>
                  Python code will be automatically generated to execute this SPARQL query.
                </p>
              </div>
            ) : (
              /* Python code editing for non-SPARQL agents */
              <div>
                <div className={`border ${THEME.borders.default} rounded overflow-hidden`} style={{ height: '380px' }}>
                  <Editor
                    height="380px"
                    language="python"
                    theme={getEditorTheme()}
                    value={editedCode}
                    onChange={(value) => {console.log(value); setEditedCode(value || '')}}
                    onMount={handleEditorDidMount}
                    options={getEditorOptions()}
                    loading={
                      <div className="flex items-center justify-center h-full">
                        <Icon name="spinner" className={`${THEME.text.secondary} w-5 h-5`} />
                      </div>
                    }
                  />
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className={`${THEME.containers.card} rounded border ${THEME.borders.default} overflow-hidden max-h-96 overflow-y-auto`}>
            <SyntaxHighlighter 
              language={getSyntaxLanguage()}
              style={{
                ...(isDarkMode ? oneDark : oneLight),
                'code[class*="language-"]': {
                  ...(isDarkMode ? oneDark : oneLight)['code[class*="language-"]'],
                  background: 'transparent',
                  backgroundColor: 'transparent'
                },
                'pre[class*="language-"]': {
                  ...(isDarkMode ? oneDark : oneLight)['pre[class*="language-"]'],
                  background: 'transparent',
                  backgroundColor: 'transparent'
                }
              }}
              className="!m-0"
              customStyle={{ 
                margin: 0, 
                padding: '1rem', 
                background: 'transparent',
                backgroundColor: 'transparent', 
                fontSize: '13px',
                fontFamily: '"Fira Code", "Fira Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace'
              }}
            >
              {displayContent}
            </SyntaxHighlighter>
          </div>
        )}
      </div>
    </div>
  );
};

export default EditableCodeDisplay; 