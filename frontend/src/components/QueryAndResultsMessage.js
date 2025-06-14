import React, { useState } from 'react';
import SparqlQueryDisplay from './SparqlQueryDisplay';
import GeneratedCodeDisplay from './GeneratedCodeDisplay';
import QueryResultsDisplay from './QueryResultsDisplay';
import WorkflowViewer from './WorkflowViewer';
import ExecutionResultsDisplay from './ExecutionResultsDisplay';
import THEME from '../styles/colorTheme';

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
  isDarkMode = false
}) => {
  // Default states: code agent has sections open, others collapsed
  const defaultOpen = agentType === 'code';
  const [isCodeExpanded, setIsCodeExpanded] = useState(defaultOpen);
  const [isExecutionExpanded, setIsExecutionExpanded] = useState(defaultOpen);

  // Collapsible section component
  const CollapsibleSection = ({ title, isExpanded, onToggle, children, icon }) => (
    <div className={`border ${THEME.borders.default} rounded-lg overflow-hidden`}>
      <button
        onClick={onToggle}
        className={`w-full flex items-center justify-between p-3 ${THEME.containers.secondary} ${THEME.interactive.hover} transition-colors text-left`}
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className={`text-sm font-medium ${THEME.text.primary}`}>{title}</span>
        </div>
        <svg 
          className={`w-4 h-4 ${THEME.text.secondary} transition-transform duration-200 ${
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
        <div className={`p-3 ${THEME.containers.card} border-t ${THEME.borders.default}`}>
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

      {/* Display generated code if available (all agents) */}
      {message.generatedCode && (
        <CollapsibleSection
          title="Generated Code"
          icon={
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              <path d="m7 8-4 4 4 4"></path>
              <path d="m17 8 4 4-4 4"></path>
              <path d="m14 4-4 16"></path>
            </svg>
          }
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
      {agentType !== 'workflow_generation' && executionResults && executionResults.length > 0 && (
        <CollapsibleSection
          title="Execution Results"
          icon={
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              <polyline points="22,12 18,12 15,21 9,3 6,12 2,12"></polyline>
            </svg>
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
    </div>
  );
};

export default QueryAndResultsMessage; 