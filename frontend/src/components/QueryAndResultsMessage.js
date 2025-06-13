import React, { useState } from 'react';
import SparqlQueryDisplay from './SparqlQueryDisplay';
import GeneratedCodeDisplay from './GeneratedCodeDisplay';
import QueryResultsDisplay from './QueryResultsDisplay';
import WorkflowViewer from './WorkflowViewer';
import ExecutionResultsDisplay from './ExecutionResultsDisplay';

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
  isDarkMode = false
}) => {
  
  return (
    <div className="space-y-4">
      {/* Display SPARQL query if available (SPARQL agent only) */}
      {agentType === 'sparql' && message.generatedSparql && (
        <SparqlQueryDisplay 
          query={query} 
          agentType={agentType}
          isDarkMode={isDarkMode}
          onExecute={() => {}} 
          canExecute={false} 
        />
      )}
      {/* Display query results */}
      {agentType === 'sparql' && results && (
        <QueryResultsDisplay 
          results={results} 
          isDarkMode={isDarkMode}
        />       
      )}

      {/* Display generated code if available (all agents) */}
      {agentType === 'code' && generatedCode && (
        <GeneratedCodeDisplay 
          code={generatedCode} 
          agentType={agentType} 
          isDarkMode={isDarkMode} 
        />
      )}

      {/* Display execution results (unified for all agents) */}
      {executionResults && (
        <ExecutionResultsDisplay 
          executionResults={executionResults} 
          isDarkMode={isDarkMode}
        />
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
        />
      )}
    </div>
  );
};

export default QueryAndResultsMessage; 