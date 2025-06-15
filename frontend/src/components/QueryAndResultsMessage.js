import React, { useState, useRef, useEffect } from 'react';
import EditableCodeDisplay from './EditableCodeDisplay';
import IndexAsLearnedModal from './IndexAsLearnedModal';
import QueryResultsDisplay from './QueryResultsDisplay';
import WorkflowViewer from './WorkflowViewer';
import ExecutionResultsDisplay from './ExecutionResultsDisplay';
import THEME from '../styles/colorTheme';
import Icon from './Icon';

// Component to render combined query and results with unified schema
const QueryAndResultsMessage = ({ 
  message, 
  query,
  results,
  error,
  workflowPlan, 
  generatedCode, 
  workflowId, 
  executionResults,
  onExecuteWorkflow, 
  onExecuteStep, 
  agentType, 
  isJsonWorkflow,
  messageIndex,
  allMessages,
  enableExecution = true,
  isDarkMode = false,
  onMessageUpdate,
  onError
}) => {
  // Default states: code agent has sections open, others collapsed
  const [isCodeExpanded, setIsCodeExpanded] = useState(true);
  const [isExecutionExpanded, setIsExecutionExpanded] = useState(true);
  const [showIndexModal, setShowIndexModal] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [showCopyNotification, setShowCopyNotification] = useState(false);
  const [clearVariables, setClearVariables] = useState(true);
  const [isExecuting, setIsExecuting] = useState(false);
  
  // Ref to access EditableCodeDisplay execute function
  const executeRef = useRef(null);

  // Handle execution completion from EditableCodeDisplay
  const handleExecutionComplete = (response) => {
    if (response.success && response.message) {
      onMessageUpdate?.(response.message);
      setSuccessMessage('Code executed successfully!');
      setTimeout(() => setSuccessMessage(''), 3000);
      setIsEditing(false);
    }
    setIsExecuting(false);
  };

  // Handle execute button click
  const handleExecuteClick = () => {
    if (executeRef.current) {
      setIsExecuting(true);
      executeRef.current();
    }
  };

  // Handle indexing success
  const handleIndexSuccess = (response) => {
    setSuccessMessage(`Successfully indexed ${response.indexed_items.length} item(s) as learned content!`);
    setTimeout(() => setSuccessMessage(''), 5000);
  };

  // Handle copy to clipboard
  const handleCopy = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setShowCopyNotification(true);
      setTimeout(() => setShowCopyNotification(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  // Handle edit button click
  const handleEditClick = () => {
    setIsEditing(true);
  };

  // Get the content to display and edit
  const getContentInfo = () => {
    if (agentType === 'sparql' && message.generatedSparql) {
      return {
        title: 'Generated SPARQL',
        content: message.generatedSparql,
        icon: (
          <Icon name="database" className="w-4 h-4" />
        )
      };
    } else if (message.generatedCode) {
      return {
        title: 'Generated Code',
        content: message.generatedCode,
        icon: (
          <Icon name="code" className="w-4 h-4" />
        )
      };
    }
    return null;
  };

  // Get user prompt from conversation context
  const getUserPrompt = () => {
    // Look for the original user message that started this conversation
    if (allMessages && allMessages.length > 0) {
      const userMessage = allMessages.find(msg => msg.role === 'user' && !msg.isNodeProgress);
      return userMessage?.content || '';
    }
    return '';
  };

  // Collapsible section component
  const CollapsibleSection = ({ title, isExpanded, onToggle, children, icon, actions }) => (
    <div className={`border ${THEME.borders.default} rounded-lg overflow-hidden`}>
      <div className={`w-full flex items-center justify-between p-3 ${THEME.containers.secondary} transition-colors`}>
        <button
          onClick={onToggle}
          className={`flex items-center gap-2 ${THEME.interactive.hover} transition-colors text-left flex-1 p-1 -m-1 rounded`}
        >
          {icon}
          <span className={`text-sm font-medium ${THEME.text.primary}`}>{title}</span>
        </button>
        <div className="flex items-center gap-2">
          {actions}
          <button
            onClick={onToggle}
            className={`p-1 ${THEME.interactive.hover} transition-colors rounded`}
          >
            <Icon name="chevronDown" className={`w-4 h-4 ${THEME.text.secondary} transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>
      {isExpanded && (
        <div className={`p-3 ${THEME.containers.card} border-t ${THEME.borders.default}`}>
          {children}
        </div>
      )}
    </div>
  );
  
  return (
    <div className="space-y-4">
      {/* Success message */}
      {successMessage && (
        <div className={`p-3 rounded-lg ${THEME.status.success.background} ${THEME.status.success.text} text-sm flex items-center gap-2`}>
          <Icon name="check" className="w-4 h-4" />
          {successMessage}
        </div>
      )}

      {/* Copy notification */}
      {showCopyNotification && (
        <div className={`fixed top-4 right-4 z-50 px-3 py-1 ${THEME.status.success.background} ${THEME.status.success.text} text-xs rounded-lg shadow-lg`}>
          ✓ Copied!
        </div>
      )}

      {/* Workflow display for JSON workflows */}
      {workflowPlan && isJsonWorkflow && (
        <WorkflowViewer
          workflowData={workflowPlan}
          workflowId={workflowId || 'unknown'}
          onExecuteWorkflow={onExecuteWorkflow}
          onExecuteStep={onExecuteStep}
          messageIndex={messageIndex}
          allMessages={allMessages}
          enableExecution={enableExecution}
        />
      )}

      {/* Unified Code/SPARQL Section */}
      {(() => {
        const contentInfo = getContentInfo();
        if (!contentInfo) return null;

        return (
          <CollapsibleSection
            title={
              <div className="flex items-center gap-2">
                <span>{contentInfo.title}</span>
                {isEditing && (
                  <span className={`text-xs px-2 py-1 rounded ${THEME.status.info.background} ${THEME.status.info.text}`}>
                    Editing
                  </span>
                )}
              </div>
            }
            icon={contentInfo.icon}
            isExpanded={isCodeExpanded}
            onToggle={() => setIsCodeExpanded(!isCodeExpanded)}
            actions={
              <div className="flex items-center gap-2">
                {!isEditing ? (
                  <>
                    {/* Copy button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCopy(contentInfo.content);
                      }}
                      className={`p-1.5 ${THEME.containers.card} border ${THEME.borders.default} rounded ${THEME.interactive.hover} transition-colors duration-200`}
                      title="Copy to clipboard"
                    >
                      <Icon name="copy" className={`w-4 h-4 ${THEME.text.secondary}`} />
                    </button>

                    {/* Edit button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEditClick();
                      }}
                      className={`p-1.5 ${THEME.containers.card} border ${THEME.borders.default} rounded ${THEME.interactive.hover} transition-colors duration-200`}
                      title="Edit and re-execute"
                    >
                      <Icon name="edit" className={`w-4 h-4 ${THEME.text.secondary}`} />
                    </button>

                    {/* Index button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowIndexModal(true);
                      }}
                      className={`p-1.5 ${THEME.containers.card} border ${THEME.borders.default} rounded ${THEME.interactive.hover} transition-colors duration-200`}
                      title="Index as learned content"
                    >
                      <Icon name="index" className={`w-4 h-4 ${THEME.text.secondary}`} />
                    </button>
                  </>
                ) : (
                  <>
                    {/* Cancel button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setIsEditing(false);
                      }}
                      className={`px-3 py-1.5 text-sm ${THEME.buttons.secondary} rounded transition-colors duration-200`}
                      disabled={isExecuting}
                    >
                      Cancel
                    </button>
                    
                    {/* Execute button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleExecuteClick();
                      }}
                      className={`px-3 py-1.5 text-sm ${THEME.buttons.primary} rounded transition-colors duration-200 flex items-center gap-2`}
                      disabled={isExecuting}
                    >
                      {isExecuting ? (
                        <>
                          <Icon name="spinner" />
                          Executing...
                        </>
                      ) : (
                        <>
                          <Icon name="play" className="w-4 h-4" />
                          Execute
                        </>
                      )}
                    </button>
                  </>
                )}
              </div>
            }
          >
            <EditableCodeDisplay 
              code={message.generatedCode} 
              sparqlQuery={message.generatedSparql}
              agentType={agentType} 
              messageId={message.id}
              isDarkMode={isDarkMode}
              hideHeader={true}
              isEditingExternal={isEditing}
              clearVariablesExternal={clearVariables}
              onExecutionComplete={handleExecutionComplete}
              onError={onError}
              onEdit={() => setIsEditing(true)}
              onCopy={handleCopy}
              onCancel={() => setIsEditing(false)}
              onExecuteRef={(executeFunction) => { executeRef.current = executeFunction; }}
            />
          </CollapsibleSection>
        );
      })()}

      {/* Display query results for SPARQL agents */}
      {agentType === 'sparql' && results && (
        <QueryResultsDisplay 
          results={results} 
          isDarkMode={isDarkMode}
        />       
      )}      

      {/* Display execution results (unified for all agents) */}
      {agentType !== 'workflow_generation' && executionResults && executionResults.length > 0 && (
        <CollapsibleSection
          title="Execution Results"
          icon={
            <Icon name="activity" className="w-4 h-4" />
          }
          isExpanded={isExecutionExpanded}
          onToggle={() => setIsExecutionExpanded(!isExecutionExpanded)}
        >
          <ExecutionResultsDisplay 
            executionResults={executionResults} 
            isDarkMode={isDarkMode}
            hideHeader={true}
          />
        </CollapsibleSection>
      )}

      {/* Index as Learned Modal */}
      <IndexAsLearnedModal
        isOpen={showIndexModal}
        onClose={() => setShowIndexModal(false)}
        messageId={message.id}
        agentType={agentType}
        hasCode={!!message.generatedCode}
        hasSparql={!!message.generatedSparql}
        initialUserPrompt={getUserPrompt()}
        allMessages={allMessages}
        onSuccess={handleIndexSuccess}
        onError={onError}
      />
    </div>
  );
};

export default QueryAndResultsMessage; 