import React from 'react';
import SparqlQueryDisplay from './SparqlQueryDisplay';
import GeneratedCodeDisplay from './GeneratedCodeDisplay';
import QueryResultsDisplay from './QueryResultsDisplay';
import WorkflowViewer from './WorkflowViewer';

// Component to render combined query and results
const QueryAndResultsMessage = ({ 
  message, 
  workflowPlan, 
  generatedCode, 
  workflowId, 
  onExecuteWorkflow, 
  onExecuteStep, 
  agentType, 
  isJsonWorkflow,
  messageIndex,
  allMessages,
  isDarkMode = false
}) => {
  return (
    <div className="space-y-4">
      {/* {message.content && (
        <div className="prose max-w-none">
          <div>{message.content}</div>
        </div>
      )} */}

      {/* Display workflow query if available */}
      {message.query && (
        <SparqlQueryDisplay 
          query={message.query} 
          agentType={agentType}
          isDarkMode={isDarkMode}
          onExecute={() => {}} 
          canExecute={agentType === 'sparql'} 
        />
      )}

      {/* Display generated code if available */}
      {generatedCode && <GeneratedCodeDisplay code={generatedCode} agentType={agentType} isDarkMode={isDarkMode} />}

      {/* Workflow display for JSON workflows */}
      {workflowPlan && isJsonWorkflow && (
        <WorkflowViewer
          workflowData={workflowPlan}
          workflowId={workflowId || 'unknown'}
          onExecuteWorkflow={onExecuteWorkflow}
          onExecuteStep={onExecuteStep}
          messageIndex={messageIndex}
          allMessages={allMessages}
        />
      )}

      {/* Display query results if available - only for SPARQL agent */}
      {message.queryResults && agentType === 'sparql' && (
        <QueryResultsDisplay results={message.queryResults} />
      )}
    </div>
  );
};

export default QueryAndResultsMessage; 