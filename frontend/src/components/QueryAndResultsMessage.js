import React from 'react';
import SparqlQueryDisplay from './SparqlQueryDisplay';
import GeneratedCodeDisplay from './GeneratedCodeDisplay';
import WorkflowPlanDisplay from './WorkflowPlanDisplay';
import WorkflowExecutionDisplay from './WorkflowExecutionDisplay';
import QueryResultsDisplay from './QueryResultsDisplay';

// Component to render combined query and results
const QueryAndResultsMessage = ({ query, results, error, generatedCode, workflowPlan, workflowId, executionResults, failedSteps, onExecuteWorkflow }) => {
  return (
    <div className="query-results-container">
      {query && <SparqlQueryDisplay query={query} />}
      {generatedCode && <GeneratedCodeDisplay code={generatedCode} />}
      {workflowPlan && workflowId && (
        <WorkflowPlanDisplay 
          workflowPlan={workflowPlan} 
          workflowId={workflowId} 
          onExecuteWorkflow={onExecuteWorkflow}
        />
      )}
      {(executionResults || failedSteps) && workflowId && (
        <WorkflowExecutionDisplay 
          executionResults={executionResults}
          failedSteps={failedSteps}
          workflowId={workflowId}
        />
      )}
      {results && <QueryResultsDisplay results={results} error={error} />}
    </div>
  );
};

export default QueryAndResultsMessage; 