import React from 'react';
import SparqlQueryDisplay from './SparqlQueryDisplay';
import GeneratedCodeDisplay from './GeneratedCodeDisplay';
import WorkflowPlanDisplay from './WorkflowPlanDisplay';
import WorkflowExecutionDisplay from './WorkflowExecutionDisplay';
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
  isJsonWorkflow 
}) => {
  return (
    <div className="space-y-4">
      {message.content && (
        <div className="prose max-w-none">
          <div>{message.content}</div>
        </div>
      )}

      {/* Display workflow query if available */}
      {message.query && (
        <SparqlQueryDisplay 
          query={message.query} 
          onExecute={() => {}} 
          canExecute={agentType === 'sparql'} 
        />
      )}

      {/* Display generated code if available */}
      {generatedCode && <GeneratedCodeDisplay code={generatedCode} />}

      {/* Workflow display for JSON workflows */}
      {workflowPlan && isJsonWorkflow && (
        <WorkflowViewer
          workflowData={workflowPlan}
          workflowId={workflowId || 'unknown'}
          onExecuteWorkflow={onExecuteWorkflow}
          onExecuteStep={onExecuteStep}
        />
      )}

      {/* Legacy workflow display for older Mermaid workflows */}
      {workflowPlan && workflowId && !isJsonWorkflow && (
        <WorkflowPlanDisplay 
          plan={workflowPlan} 
          workflowId={workflowId}
          onExecute={onExecuteWorkflow}
        />
      )}

      {/* Display execution results if available */}
      {message.executionResults && (
        <WorkflowExecutionDisplay results={message.executionResults} />
      )}

      {/* Display query results if available */}
      {message.queryResults && (
        <QueryResultsDisplay 
          results={message.queryResults} 
          agentType={agentType}
        />
      )}
    </div>
  );
};

export default QueryAndResultsMessage; 