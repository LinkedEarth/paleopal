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
  // Default states: code agent has sections open, others collapsed
  const defaultOpen = agentType === 'code';
  const [isCodeExpanded, setIsCodeExpanded] = useState(defaultOpen);
  const [isExecutionExpanded, setIsExecutionExpanded] = useState(defaultOpen);

  // Collapsible section component
  const CollapsibleSection = ({ title, isExpanded, onToggle, children, icon = "💻" }) => (
    <div className="border border-neutral-200 dark:border-neutral-600 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 bg-neutral-50 dark:bg-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-600 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm">{icon}</span>
          <span className="text-sm font-medium text-neutral-800 dark:text-neutral-200">{title}</span>
        </div>
        <svg 
          className={`w-4 h-4 text-neutral-600 dark:text-neutral-400 transition-transform duration-200 ${
            isExpanded ? 'rotate-180' : ''
          }`} 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isExpanded && (
        <div className="p-3 bg-white dark:bg-neutral-800 border-t border-neutral-200 dark:border-neutral-600">
          {children}
        </div>
      )}
    </div>
  );
  
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
      {message.generatedCode && (
        <CollapsibleSection
          title="Generated Code"
          icon="💻"
          isExpanded={isCodeExpanded}
          onToggle={() => setIsCodeExpanded(!isCodeExpanded)}
        >
          <GeneratedCodeDisplay 
            code={message.generatedCode} 
            agentType={agentType} 
            isDarkMode={isDarkMode}
            hideHeader={true}
          />
        </CollapsibleSection>
      )}

      {/* Display execution results (unified for all agents) */}
      {executionResults && executionResults.length > 0 && (
        <CollapsibleSection
          title="Execution Results"
          icon="⚡"
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