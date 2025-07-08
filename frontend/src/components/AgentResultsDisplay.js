import React, { useState } from 'react';
import EditableCodeDisplay from './EditableCodeDisplay';
import IndexAsLearnedModal from './IndexAsLearnedModal';
import QueryResultsDisplay from './QueryResultsDisplay';
import WorkflowViewer from './WorkflowViewer';
import ExecutionResultsDisplay from './ExecutionResultsDisplay';
import THEME from '../styles/colorTheme';
import Icon from './Icon';

// Component to render combined query and results with simplified design
const AgentResultsDisplay = ({ 
  message, 
  results,
  workflowPlan, 
  executionResults,
  onExecuteStep, 
  agentType, 
  isJsonWorkflow,
  messageIndex,
  allMessages,
  enableExecution = true,
  isDarkMode = false,
  autoFetch = true,
  onMessageUpdate,
  onError,
  conversationId,
  onMessagesUpdate,
  messagesVersion,
  executionUpdates = {}
}) => {
  const [showIndexModal, setShowIndexModal] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  // Handle execution completion from EditableCodeDisplay
  const handleExecutionComplete = (payload) => {
    // payload can be either the direct API response (sync execution) or a WebSocket execution_update
    if (!payload) return;

    // If payload contains a full message (sync path), update directly
    if (payload.success && payload.message) {
      onMessageUpdate?.(payload.message);
      setSuccessMessage('Code executed successfully!');
      setTimeout(() => setSuccessMessage(''), 3000);
      return;
    }

    // If payload is a WebSocket update with status completed, trigger a refresh via the parent callback
    if (payload.status === 'completed') {
      // Parent ChatWindow listens for message_updated events, but we can still show a quick toast
      setSuccessMessage('Execution completed');
      setTimeout(() => setSuccessMessage(''), 3000);
    } else if (payload.status === 'error' || payload.status === 'failed') {
      setSuccessMessage('Execution failed');
      setTimeout(() => setSuccessMessage(''), 3000);
    }
  };

  // Handle indexing success
  const handleIndexSuccess = (response) => {
    setSuccessMessage(`Successfully indexed ${response.indexed_items.length} item(s) as learned content!`);
    setTimeout(() => setSuccessMessage(''), 5000);
  };

  // Simple section header component
  const SectionHeader = ({ icon, title }) => (
    <div className="space-y-2">
      <div className={`flex items-center gap-2 ${THEME.text.primary}`}>
        {icon}
        <span className="font-medium">{title}</span>
      </div>
      <hr className={`border-t ${THEME.borders.default}`} />
    </div>
  );
  
  // Check if we have code or SPARQL to display (but not for workflow agent)
  const hasCodeOrSparql = (message.generatedCode || message.generatedSparql) && agentType !== 'workflow_generation';
  
  // Get user prompt from conversation context
  const getUserPrompt = (messageId) => {
    if (allMessages && allMessages.length > 0) {
      // Find the most recent user message (not progress message)
      // Work backwards through the messages to find the latest user prompt
      let startChecking = false;
      for (let i = allMessages.length - 1; i >= 0; i--) {
        const msg = allMessages[i];
        if (msg.id === messageId) {
          startChecking = true;
        }
        if (startChecking && msg.role === 'user' && !msg.isNodeProgress) {
          return msg.content || '';
        }
      }
    }
    return '';
  };


  return (
    <div className="space-y-6">
      {/* Success message */}
      {successMessage && (
        <div className={`p-3 rounded-lg ${THEME.status.success.background} ${THEME.status.success.text} text-sm flex items-center gap-2`}>
          <Icon name="check" className="w-4 h-4" />
          {successMessage}
        </div>
      )}

      {/* Workflow display for JSON workflows */}
      {workflowPlan && isJsonWorkflow && (
        <div className="space-y-4">
          <SectionHeader 
            icon={<Icon name="activity" className="w-4 h-4" />}
            title="Workflow Plan"
          />
          <WorkflowViewer
            workflowData={workflowPlan}
            onExecuteStep={onExecuteStep}
            messageIndex={messageIndex}
            allMessages={allMessages}
            enableExecution={enableExecution}
            conversationId={conversationId}
            onMessagesUpdate={onMessagesUpdate}
            messagesVersion={messagesVersion}
          />
        </div>
      )}

      {/* Code/SPARQL Editor - clean display */}
      {hasCodeOrSparql && (
        <EditableCodeDisplay 
          code={message.generatedCode} 
          sparqlQuery={message.generatedSparql}
          agentType={agentType} 
          messageId={message.id}
          conversationId={conversationId}
          isDarkMode={isDarkMode}
          onExecutionComplete={handleExecutionComplete}
          onError={onError}
          onIndex={() => setShowIndexModal(true)}
          allMessages={allMessages}
          hasCode={!!message.generatedCode}
          hasSparql={!!message.generatedSparql}
          executionUpdates={executionUpdates}
        />
      )}

      {/* Display query results for SPARQL agents */}
      {agentType === 'sparql' && results && (
        <div className="space-y-4">
          <SectionHeader 
            icon={<Icon name="list" className="w-4 h-4" />}
            title="Query Results"
          />
          <QueryResultsDisplay 
            results={results} 
            isDarkMode={isDarkMode}
            hideHeader={true}
            sparqlQuery={message.generatedSparql}
            autoFetch={autoFetch}
            message={message}
          />
        </div>
      )}      

      {/* Display execution results (unified for all agents) */}
      {agentType !== 'workflow_generation' && executionResults && executionResults.length > 0 && (
        <div className="space-y-4">
          <SectionHeader 
            icon={<Icon name="activity" className="w-4 h-4" />}
            title="Execution Results"
          />
          <ExecutionResultsDisplay 
            executionResults={executionResults} 
            isDarkMode={isDarkMode}
            hideHeader={true}
          />
        </div>
      )}

      {/* Index as Learned Modal */}
      <IndexAsLearnedModal
        isOpen={showIndexModal}
        onClose={() => setShowIndexModal(false)}
        messageId={message.id}
        agentType={agentType}
        hasCode={!!message.generatedCode}
        hasSparql={!!message.generatedSparql}
        initialUserPrompt={getUserPrompt(message.id)}
        allMessages={allMessages}
        onSuccess={handleIndexSuccess}
        onError={onError}
      />
    </div>
  );
};

const areEqual = (prevProps, nextProps) => {
  // Only re-render if the message object or dark mode/execution flags actually change
  return (
    prevProps.message === nextProps.message &&
    prevProps.isDarkMode === nextProps.isDarkMode &&
    prevProps.enableExecution === nextProps.enableExecution &&
    prevProps.messagesVersion === nextProps.messagesVersion
  );
};

export default React.memo(AgentResultsDisplay, areEqual); 