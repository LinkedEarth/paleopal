import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import axios from 'axios';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './ChatWindow.css';

const LLM_PROVIDERS = [
  { id: 'openai', name: 'OpenAI' },  
  { id: 'google', name: 'Google' },  
  { id: 'anthropic', name: 'Anthropic' },
  { id: 'grok', name: 'XAI Grok' },
  { id: 'ollama', name: 'Ollama' }
];

const AGENT_TYPES = [
  { 
    id: 'workflow_manager', 
    name: 'Workflow Planner',
    capability: 'plan_workflow', 
    description: 'Plan multi-step paleoclimate analysis workflows',
    placeholder: 'Describe the analysis workflow you want to plan...'
  },
  { 
    id: 'code', 
    name: 'Code Generator',
    capability: 'generate_code', 
    description: 'Generate Python code for data analysis',
    placeholder: 'Describe the analysis you want to perform...'
  },  
  { 
    id: 'sparql', 
    name: 'SPARQL Query Generator',
    capability: 'generate_query',
    description: 'Generate SPARQL queries for paleoclimate data',
    placeholder: 'Ask a question to generate a SPARQL query...'
  }
];

// Enhanced Loading/Progress indicator component that shows detailed agent execution progress
const AgentProgressDisplay = ({ messages, currentNode, executionStart }) => {
  const progressMessages = messages.filter(m => m.isNodeProgress);
  const completedNodes = progressMessages.filter(m => m.phase === 'complete');
  const currentRunningNode = progressMessages.find(m => m.phase === 'start' && 
    !completedNodes.some(c => c.nodeName === m.nodeName));

  const formatDuration = (startTime, endTime) => {
    if (!startTime || !endTime) return '';
    const duration = endTime - startTime;
    return duration < 1000 ? `${duration}ms` : `${(duration / 1000).toFixed(1)}s`;
  };

  const getNodeIcon = (status) => {
    switch (status) {
      case 'running': return '⏳';
      case 'completed': return '✅';
      case 'error': return '❌';
      default: return '⏳';
    }
  };

  const renderNodeOutput = (outputSummary) => {
    if (!outputSummary || Object.keys(outputSummary).length === 0) return null;

    return (
      <div className="node-output-details">
        {outputSummary.generated_code_preview && (
          <div className="output-item">
            <strong>Generated Code Preview:</strong>
            <pre className="code-preview">{outputSummary.generated_code_preview}</pre>
    </div>
        )}
        {outputSummary.execution_results_count && (
          <div className="output-item">
            <strong>Results:</strong> {outputSummary.execution_results_count} items found
          </div>
        )}
        {outputSummary.similar_results_count && (
          <div className="output-item">
            <strong>Similar Examples:</strong> {outputSummary.similar_results_count} found
          </div>
        )}
        {outputSummary.entity_matches_count && (
          <div className="output-item">
            <strong>Entity Matches:</strong> {outputSummary.entity_matches_count} found
          </div>
        )}
        {outputSummary.clarification_questions_count && (
          <div className="output-item">
            <strong>Clarification Questions:</strong> {outputSummary.clarification_questions_count} generated
          </div>
        )}
        {outputSummary.error && (
          <div className="output-item error">
            <strong>Error:</strong> {outputSummary.error}
          </div>
        )}
        {/* Show other outputs as key-value pairs */}
        {Object.entries(outputSummary)
          .filter(([key]) => !['generated_code_preview', 'execution_results_count', 'similar_results_count', 'entity_matches_count', 'clarification_questions_count', 'error'].includes(key))
          .map(([key, value]) => (
            <div key={key} className="output-item">
              <strong>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:</strong> {String(value)}
            </div>
          ))}
  </div>
);
  };

  const [showCompleted, setShowCompleted] = useState(false);

  const toggleCompleted = () => setShowCompleted(prev=>!prev);

  // Determine if execution is finished (last message is agent-complete)
  const lastProgress = progressMessages[progressMessages.length-1];
  const executionDone = lastProgress && lastProgress.phase==='complete' && lastProgress.nodeName==='Agent Execution';
  const statusIcon = currentRunningNode? '⏳' : executionDone? '✅' : '⏳';
  const statusText = currentRunningNode && currentRunningNode.nodeName? `Running: ${currentRunningNode.nodeName}` : executionDone? 'Execution completed' : completedNodes.length>0? 'Processing...' : 'Starting agent execution...';

  return (
    <div className="agent-progress-display">
      <div className="progress-header">
        <div className="current-status">
          {statusIcon}
          &nbsp;&nbsp;
          {statusText}
          &nbsp;&nbsp;
        </div>
        {executionStart && (
          <div className="execution-time">
            Started: {new Date(executionStart).toLocaleTimeString()}
          </div>
        )}
        {completedNodes.length>0 && (
          <button className="toggle-completed-btn" onClick={toggleCompleted} title={showCompleted?"Hide completed steps":"Show completed steps"}>
            {showCompleted?"▾ Hide Steps":"▸ Show Steps"}
          </button>
        )}
      </div>

      {/* Show completed steps */}
      {completedNodes.length > 0 && showCompleted && (
        <div className="completed-steps">
          <h4>Completed Steps:</h4>
          {completedNodes.map((node, index) => (
            <div key={node.id} className="progress-step completed">
              <div className="step-header">
                <span className="step-icon">✅</span>
                <span className="step-name">{node.nodeName}</span>
                <span className="step-timing">
                  {node.timestamp && executionStart && formatDuration(executionStart, node.timestamp)}
                </span>
              </div>
              
              {/* Show state information */}
              {node.summary && Object.keys(node.summary).length > 0 && (
                <div className="step-state">
                  <strong>State:</strong> {Object.entries(node.summary).map(([k,v]) => `${k}: ${v}`).join(', ')}
                </div>
              )}
              
              {/* Show output details */}
              {renderNodeOutput(node.outputSummary)}
            </div>
          ))}
        </div>
      )}

      {/* Show current running step */}
      {currentRunningNode && currentRunningNode.nodeName && (
        <div className="current-step">
          <div className="progress-step running">
            <div className="step-header">
              <span className="step-icon">⏳</span>
              <span className="step-name">{currentRunningNode.nodeName}</span>
              <span className="step-status">In Progress...</span>
            </div>
            
            {/* Show current state */}
            {currentRunningNode.summary && Object.keys(currentRunningNode.summary).length > 0 && (
              <div className="step-state">
                <strong>State:</strong> {Object.entries(currentRunningNode.summary).map(([k,v]) => `${k}: ${v}`).join(', ')}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// Component to render formatted clarification messages
const ClarificationMessage = ({ content, clarificationQuestions }) => {
  // If we have multiple questions, use those
  if (clarificationQuestions && clarificationQuestions.length > 0) {
    return (
      <div className="clarification-message-content">
        {clarificationQuestions.map((question, index) => (
          <div key={question.id || index} className="clarification-question-group">
            {clarificationQuestions.length > 1 && (
              <div className="question-number">Question {index + 1}</div>
            )}
            <div className="clarification-question">{question.question}</div>
            
            {question.context && (
              <div className="clarification-context">{question.context}</div>
            )}
            
            {question.choices && question.choices.length > 0 && (
              <div className="clarification-choices">
                <div className="choices-label">Options:</div>
                <ul className="choices-list">
                  {question.choices.map((choice, choiceIndex) => (
                    <li key={choiceIndex} className="choice-item">{choice}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }
  
  // Otherwise, try to parse and format the raw text content
  const parts = parseMessageParts(content);
  return (
    <div className="clarification-message-content">
      <div className="clarification-question">{parts.question}</div>
      
      {parts.context && (
        <div className="clarification-context">{parts.context}</div>
      )}
      
      {parts.options.length > 0 && (
        <div className="clarification-choices">
          <div className="choices-label">Options:</div>
          <ul className="choices-list">
            {parts.options.map((option, index) => (
              <li key={index} className="choice-item">{option}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

// Component to render clarification responses in a nice format
const ClarificationResponseMessage = ({ content }) => {
  console.log('ClarificationResponseMessage rendering with content:', content);
  console.log('Content type:', typeof content);
  console.log('Content length:', content ? content.length : 'null/undefined');
  
  // Fallback for empty or invalid content
  if (!content || typeof content !== 'string' || content.trim().length === 0) {
    console.error('ClarificationResponseMessage: Invalid or empty content');
    return (
      <div className="clarification-response-content">
        <div className="clarification-response-header">
          <span className="response-icon">⚠</span>
          Error: No content to display
        </div>
        <div style={{ padding: '1rem', backgroundColor: 'rgba(255, 0, 0, 0.1)' }}>
          Content is empty or invalid. Raw content: {JSON.stringify(content)}
        </div>
      </div>
    );
  }
  
  // Parse the Q&A pairs and additional comments from the content
  const lines = content.split('\n');
  const qaPairs = [];
  let additionalComment = '';
  
  let currentQ = '';
  let currentA = '';
  let inAdditionalComment = false;
  
  console.log('Parsing lines:', lines);
  
  for (const line of lines) {
    if (line.startsWith('Q: ')) {
      // If we have a previous Q&A pair, save it
      if (currentQ && currentA) {
        qaPairs.push({ question: currentQ, answer: currentA });
      }
      currentQ = line.substring(3);
      currentA = '';
      inAdditionalComment = false;
    } else if (line.startsWith('A: ')) {
      currentA = line.substring(3);
    } else if (line.startsWith('Additional comment: ')) {
      additionalComment = line.substring(20);
      inAdditionalComment = true;
    } else if (inAdditionalComment && line.trim()) {
      additionalComment += '\n' + line;
    }
  }
  
  // Add the last Q&A pair if it exists
  if (currentQ && currentA) {
    qaPairs.push({ question: currentQ, answer: currentA });
  }
  
  console.log('Parsed qaPairs:', qaPairs);
  console.log('Additional comment:', additionalComment);
  
  // If no Q&A pairs found, treat the entire content as a single response
  if (qaPairs.length === 0) {
    console.log('No Q&A pairs found, treating as plain text response');
    return (
      <div className="clarification-response-content">
        <div className="clarification-response-header">
          <span className="response-icon">✓</span>
          Clarification Responses
        </div>
        <div style={{ 
          padding: '1rem', 
          backgroundColor: 'white', 
          borderRadius: '0.75rem',
          border: '1px solid rgba(46, 204, 113, 0.2)',
          minHeight: '60px'
        }}>
          <div style={{ fontSize: '0.95rem', lineHeight: '1.4', color: '#333' }}>
            {content}
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="clarification-response-content">
      <div className="clarification-response-header">
        <span className="response-icon">✓</span>
        Clarification Responses
      </div>
      
      <div className="clarification-qa-pairs">
        {qaPairs.map((pair, index) => (
          <div key={index} className="qa-pair">
            <div className="qa-question">
              <span className="qa-label">Q:</span>
              <span className="qa-text">{pair.question}</span>
            </div>
            <div className="qa-answer">
              <span className="qa-label">A:</span>
              <span className="qa-text">{pair.answer}</span>
            </div>
          </div>
        ))}
      </div>
      
      {additionalComment && (
        <div className="additional-comment">
          <div className="comment-label">Additional comment:</div>
          <div className="comment-text">{additionalComment}</div>
        </div>
      )}
    </div>
  );
};

// Component to render SPARQL query results in a table
const QueryResultsDisplay = ({ results, error }) => {
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
      .then(() => {
        alert('Copied to clipboard!');
      })
      .catch(err => {
        console.error('Could not copy text: ', err);
      });
  };

  if (error) {
    return (
      <div className="query-results-error">
        <div className="results-header">
          <h4>❌ Query Error</h4>
        </div>
        <div className="error-message">{error}</div>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className="query-results-empty">
        <div className="results-header">
          <h4>📊 Query Results</h4>
        </div>
        <p>No results found.</p>
      </div>
    );
  }

  // Extract headers from the first result
  const headers = Object.keys(results[0]);

  return (
    <div className="query-results-container">
      <div className="results-header">
        <h4>📊 Query Results ({results.length} row{results.length !== 1 ? 's' : ''})</h4>
        <button 
          className="copy-results-button"
          onClick={() => copyToClipboard(JSON.stringify(results, null, 2))}
          title="Copy results as JSON"
        >
          📋 Copy JSON
        </button>
      </div>
      <div className="results-table-wrapper">
        <table className="inline-results-table">
          <thead>
            <tr>
              {headers.map(header => (
                <th key={header}>{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {headers.map(header => (
                  <td key={`${rowIndex}-${header}`}>
                    {row[header]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Component to display SPARQL queries with syntax highlighting
const SparqlQueryDisplay = ({ query }) => {
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      // Could add a toast notification here
    }).catch(err => {
      console.error('Failed to copy text: ', err);
      });
  };

  return (
    <div className="sparql-query-display">
      <div className="query-header">
        <span className="query-label">Generated SPARQL Query:</span>
        <button 
          className="copy-button" 
          onClick={() => copyToClipboard(query)}
          title="Copy query to clipboard"
        >
          📋 Copy
        </button>
      </div>
      <div className="query-content">
        <SyntaxHighlighter 
          language="sparql" 
          style={tomorrow} 
          customStyle={{
            margin: 0,
            borderRadius: '0.5rem',
            fontSize: '0.9rem'
          }}
        >
          {query}
        </SyntaxHighlighter>
      </div>
    </div>
  );
};

// Component to display generated Python code with syntax highlighting
const GeneratedCodeDisplay = ({ code }) => {
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      // Simple feedback - you could enhance this with a toast notification
      console.log('Code copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy code:', err);
    });
  };

  return (
    <div className="generated-code-display">
      <div className="code-header">
        <h4>Generated Python Code</h4>
        <button 
          className="copy-code-button"
          onClick={() => copyToClipboard(code)}
          title="Copy code to clipboard"
        >
          📋 Copy
        </button>
      </div>
      <div className="code-block">
        <SyntaxHighlighter 
          language="python" 
          style={tomorrow}
          showLineNumbers={true}
          wrapLines={true}
          customStyle={{
            margin: 0,
            borderRadius: '8px',
            fontSize: '14px'
          }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  );
};

// Component to display workflow plans
const WorkflowPlanDisplay = ({ workflowPlan, workflowId, onExecuteWorkflow }) => {
  const [showExamplesModal, setShowExamplesModal] = useState(false);
  const [modalExamples, setModalExamples] = useState([]);
  const [modalType, setModalType] = useState('');
  const [modalTitle, setModalTitle] = useState('');

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      console.log('Workflow plan copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy workflow plan:', err);
    });
  };

  const handleShowWorkflowExamples = () => {
    const examples = workflowPlan.context_used?.workflow_examples || [];
    setModalExamples(examples);
    setModalType('workflows');
    setModalTitle(`Workflow Examples (${examples.length})`);
    setShowExamplesModal(true);
  };

  const handleShowMethodExamples = () => {
    const examples = workflowPlan.context_used?.method_examples || [];
    setModalExamples(examples);
    setModalType('methods');
    setModalTitle(`Method Examples (${examples.length})`);
    setShowExamplesModal(true);
  };

  const formatWorkflowPlan = (plan) => {
    let output = `Workflow Plan (ID: ${workflowId})\n`;
    output += `===========================================\n\n`;
    
    if (plan.context_used) {
      output += `Context Used:\n`;
      output += `- Workflows found: ${plan.context_used.workflows_found}\n`;
      output += `- Methods found: ${plan.context_used.methods_found}\n\n`;
    }
    
    output += `Steps:\n`;
    plan.steps.forEach((step, index) => {
      output += `${index + 1}. [${step.agent_type.toUpperCase()}] ${step.user_input}\n`;
      if (step.dependencies && step.dependencies.length > 0) {
        output += `   Dependencies: ${step.dependencies.join(', ')}\n`;
      }
      if (step.rationale) {
        output += `   Rationale: ${step.rationale}\n`;
      }
      output += `\n`;
    });
    
    return output;
  };
  
  return (
    <div className="workflow-plan-display">
      <div className="workflow-header">
        <h4>Workflow Plan</h4>
        <div className="workflow-actions">
          <button 
            className="copy-workflow-button"
            onClick={() => copyToClipboard(formatWorkflowPlan(workflowPlan))}
            title="Copy workflow plan to clipboard"
          >
            📋 Copy
          </button>
          <button 
            className="execute-workflow-button"
            onClick={() => onExecuteWorkflow(workflowId)}
            title="Execute this workflow"
          >
            ▶️ Instantiate
          </button>
        </div>
      </div>
      
      <div className="workflow-content">
        {workflowPlan.context_used && (
          <div className="workflow-context">
            <h5>Context Used:</h5>
            <div className="context-stats">
              <button 
                className="context-stat clickable"
                onClick={handleShowWorkflowExamples}
                title="Click to view workflow examples"
                disabled={!workflowPlan.context_used.workflow_examples || workflowPlan.context_used.workflow_examples.length === 0}
              >
                📊 {workflowPlan.context_used.workflows_found} workflow examples
              </button>
              <button 
                className="context-stat clickable"
                onClick={handleShowMethodExamples}
                title="Click to view method examples"
                disabled={!workflowPlan.context_used.method_examples || workflowPlan.context_used.method_examples.length === 0}
              >
                📄 {workflowPlan.context_used.methods_found} method examples
              </button>
            </div>
          </div>
        )}
        
        <div className="workflow-steps">
          <h5>Planned Steps:</h5>
          {workflowPlan.steps.map((step, index) => (
            <div key={step.step_id || index} className="workflow-step">
              <div className="step-header">
                <span className="step-number">{index + 1}</span>
                <span className={`step-agent-type ${step.agent_type}`}>
                  {step.agent_type === 'sparql' ? '🔍 SPARQL' : '🐍 CODE'}
                </span>
                <span className="step-id">{step.step_id}</span>
              </div>
              <div className="step-content">
                <div className="step-description">{step.user_input}</div>
                {step.dependencies && step.dependencies.length > 0 && (
                  <div className="step-dependencies">
                    <strong>Dependencies:</strong> {step.dependencies.join(', ')}
                  </div>
                )}
                {step.rationale && (
                  <div className="step-rationale">
                    <strong>Rationale:</strong> {step.rationale}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Examples Modal */}
      <ExamplesModal
        isOpen={showExamplesModal}
        onClose={() => setShowExamplesModal(false)}
        examples={modalExamples}
        type={modalType}
        title={modalTitle}
      />
    </div>
  );
};

// Component to display workflow execution results
const WorkflowExecutionDisplay = ({ executionResults, failedSteps, workflowId }) => {
  const [expandedSteps, setExpandedSteps] = useState(new Set());

  const toggleStepExpansion = (stepId) => {
    setExpandedSteps(prev => {
      const newExpanded = new Set(prev);
      if (newExpanded.has(stepId)) {
        newExpanded.delete(stepId);
      } else {
        newExpanded.add(stepId);
      }
      return newExpanded;
    });
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      console.log('Execution results copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy execution results:', err);
    });
  };

  const copyStepCode = (code, stepId) => {
    navigator.clipboard.writeText(code).then(() => {
      console.log(`Step ${stepId} code copied to clipboard`);
    }).catch(err => {
      console.error(`Failed to copy step ${stepId} code:`, err);
    });
  };

  const formatExecutionResults = (results, failed) => {
    let output = `Workflow Execution Results (ID: ${workflowId})\n`;
    output += `====================================================\n\n`;
    
    if (results && results.length > 0) {
      output += `Successful Steps:\n`;
      results.forEach((result, index) => {
        output += `${index + 1}. Step ${result.step_id}: ${result.status}\n`;
        if (result.result && result.result.generated_code) {
          output += `   Generated code:\n${result.result.generated_code}\n`;
        }
        output += `\n`;
      });
    }
    
    if (failed && failed.length > 0) {
      output += `Failed Steps:\n`;
      failed.forEach((failure, index) => {
        output += `${index + 1}. Step ${failure.step_id}: ${failure.error}\n`;
      });
    }
    
    return output;
  };

  const totalSteps = (executionResults?.length || 0) + (failedSteps?.length || 0);
  const successfulSteps = executionResults?.length || 0;

  return (
    <div className="workflow-execution-display">
      <div className="execution-header">
        <h4>Workflow Execution Results</h4>
        <div className="execution-actions">
          <button 
            className="copy-execution-button"
            onClick={() => copyToClipboard(formatExecutionResults(executionResults, failedSteps))}
            title="Copy execution results to clipboard"
          >
            📋 Copy
          </button>
        </div>
      </div>
      
      <div className="execution-content">
        <div className="execution-summary">
          <div className={`execution-status ${failedSteps && failedSteps.length > 0 ? 'has-failures' : 'success'}`}>
            {failedSteps && failedSteps.length > 0 ? '⚠️' : '✅'} 
            {successfulSteps}/{totalSteps} steps completed successfully
          </div>
        </div>
        
        {executionResults && executionResults.length > 0 && (
          <div className="successful-steps">
            <h5>Successful Steps:</h5>
            {executionResults.map((result, index) => {
              const stepId = result.step_id;
              const isExpanded = expandedSteps.has(stepId);
              const hasCode = result.result && result.result.generated_code;
              const generatedCode = hasCode ? result.result.generated_code : '';
              
              // Detect if this is a SPARQL step or code step based on content
              const isSparqlStep = generatedCode.trim().toLowerCase().includes('prefix') || 
                                  generatedCode.trim().toLowerCase().includes('select') ||
                                  generatedCode.trim().toLowerCase().includes('sparql');
              
              return (
                <div key={stepId} className="execution-step success">
                  <div className="step-header">
                    <span className="step-number">{index + 1}</span>
                    <span className="step-id">{stepId}</span>
                    <span className="step-status success">✅ {result.status}</span>
                    {hasCode && (
                      <button 
                        className="expand-step-button"
                        onClick={() => toggleStepExpansion(stepId)}
                        title={isExpanded ? "Collapse code" : "Expand code"}
                      >
                        {isExpanded ? '📄 Collapse' : '📄 View Code'}
                      </button>
                    )}
                  </div>
                  
                  {result.result && (
                    <div className="step-result">
                      {hasCode && (
                        <div className="generated-code-section">
                          <div className="code-section-header">
                            <strong>{isSparqlStep ? 'Generated SPARQL Query:' : 'Generated Python Code:'}</strong>
                            <button 
                              className="copy-step-code-button"
                              onClick={() => copyStepCode(generatedCode, stepId)}
                              title="Copy code to clipboard"
                            >
                              📋 Copy Code
                            </button>
                          </div>
                          
                          {isExpanded ? (
                            <div className="full-code-display">
                              <SyntaxHighlighter
                                language={isSparqlStep ? "sparql" : "python"}
                                style={tomorrow}
                                showLineNumbers={true}
                                wrapLines={true}
                                customStyle={{
                                  margin: 0,
                                  borderRadius: '8px',
                                  fontSize: '13px',
                                  maxHeight: '400px',
                                  overflow: 'auto'
                                }}
                              >
                                {generatedCode}
                              </SyntaxHighlighter>
                            </div>
                          ) : (
                            <div className="code-preview-collapsed">
                              <pre className="code-preview">
                                {generatedCode.substring(0, 200)}
                                {generatedCode.length > 200 ? '...' : ''}
                              </pre>
                              {generatedCode.length > 200 && (
                                <div className="code-preview-hint">
                                  Click "View Code" to see the full {isSparqlStep ? 'query' : 'code'} ({generatedCode.length} characters)
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                      
                      {result.result.execution_results && (
                        <div className="execution-info">
                          <strong>Results:</strong> {JSON.stringify(result.result.execution_results).substring(0, 100)}...
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        
        {failedSteps && failedSteps.length > 0 && (
          <div className="failed-steps">
            <h5>Failed Steps:</h5>
            {failedSteps.map((failure, index) => (
              <div key={failure.step_id} className="execution-step failure">
                <div className="step-header">
                  <span className="step-number">{executionResults.length + index + 1}</span>
                  <span className="step-id">{failure.step_id}</span>
                  <span className="step-status failure">❌ {failure.status}</span>
                </div>
                <div className="step-error">
                  <strong>Error:</strong> {failure.error}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

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

// Helper to parse message parts
const parseMessageParts = (content) => {
  // Default structure
  const result = {
    question: content,
    options: [],
    context: ''
  };
  
  try {
    // Check if the content has multiple questions
    const questionBlocks = content.split(/Question \d+:/);
    
    if (questionBlocks.length > 1) {
      // We have multiple questions - parse the first one for display
      const firstBlock = questionBlocks[1] || '';
      
      // Extract the main question (first line of the block)
      const lines = firstBlock.split('\n').filter(line => line.trim());
      if (lines.length > 0) {
        result.question = lines[0].trim();
      }
      
      // Extract options if present
      if (firstBlock.includes('Options:')) {
        const optionsSection = firstBlock.split('Options:')[1].split('\n\n')[0];
        result.options = optionsSection
          .split('\n')
          .filter(line => line.trim().startsWith('-'))
          .map(line => line.trim().substring(2).trim());
      }
      
      // Extract context (text after options, before state_id)
      const contextMatch = firstBlock.match(/(?:Options:[^]*?\n\n)?(.*?)$/s);
      if (contextMatch && contextMatch[1].trim()) {
        result.context = contextMatch[1].trim();
      }
      
      return result;
    }
    
    // Original single question parsing logic
    // Extract the main question (usually the first paragraph)
    const paragraphs = content.split('\n\n').filter(p => p.trim().length > 0);
    if (paragraphs.length > 0) {
      result.question = paragraphs[0].trim();
    }
    
    // Extract options if present
    if (content.includes('Options:')) {
      const optionsSection = content.split('Options:')[1].split('\n\n')[0];
      result.options = optionsSection
        .split('\n')
        .filter(line => line.trim().startsWith('-'))
        .map(line => line.trim().substring(2).trim());
    }
    
    // Try to extract context (usually the last paragraph if not options)
    if (paragraphs.length > 1 && !paragraphs[paragraphs.length - 1].includes('Options:') && 
        true) {
      result.context = paragraphs[paragraphs.length - 1].trim();
    }
    
    return result;
  } catch (error) {
    console.error('Error parsing message parts:', error);
    return result;
  }
};

// Parse multiple clarification questions from content
const parseClarificationQuestions = (content) => {
  // Check if we have multiple questions
  const questionBlocks = content.split(/Question \d+:/);
  
  if (questionBlocks.length <= 1) {
    // Single question format - use existing parser
    const parts = parseMessageParts(content);
    return [{
      id: 'q1',
      question: parts.question,
      choices: parts.options,
      context: parts.context
    }];
  }
  
  // We have multiple questions - parse each block
  const questions = [];
  
  for (let i = 1; i < questionBlocks.length; i++) {
    const block = questionBlocks[i];
    if (!block.trim()) continue;
    
    const questionParts = {
      id: `q${i}`,
      question: '',
      choices: [],
      context: ''
    };
    
    // Extract the main question (first line of the block)
    const lines = block.split('\n').filter(line => line.trim());
    if (lines.length > 0) {
      questionParts.question = lines[0].trim();
    }
    
    // Extract options if present
    if (block.includes('Options:')) {
      const optionsSection = block.split('Options:')[1].split('\n\n')[0];
      questionParts.choices = optionsSection
        .split('\n')
        .filter(line => line.trim().startsWith('-'))
        .map(line => line.trim().substring(2).trim());
    }
    
    // Extract context (text after options, before next question or state_id)
    const contextMatch = block.match(/(?:Options:[^]*?\n\n)?(.*?)$/s);
    if (contextMatch && contextMatch[1].trim()) {
      questionParts.context = contextMatch[1].trim();
    }
    
    questions.push(questionParts);
  }
  
  return questions;
};

// Component to display workflow examples in a modal
const ExamplesModal = ({ isOpen, onClose, examples, type, title }) => {
  if (!isOpen) return null;

  const copyExample = (example) => {
    const text = type === 'workflows' 
      ? `Workflow: ${example.title || 'Unknown'}\nSteps: ${example.step_count || 'Unknown'}\nDescription: ${example.description || 'N/A'}`
      : `Method: ${example.method_name || 'Unknown'}\nPaper: ${example.paper_title || 'Unknown'}\nSummary: ${example.searchable_summary || 'N/A'}`;
    
    navigator.clipboard.writeText(text).then(() => {
      console.log('Example copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy example:', err);
    });
  };

  return (
    <div className="examples-modal-overlay" onClick={onClose}>
      <div className="examples-modal-content" onClick={e => e.stopPropagation()}>
        <div className="examples-modal-header">
          <h3>{title}</h3>
          <button className="examples-modal-close" onClick={onClose}>×</button>
        </div>
        
        <div className="examples-modal-body">
          {examples.length === 0 ? (
            <p>No examples found.</p>
          ) : (
            examples.map((example, index) => (
              <div key={index} className="example-item">
                <div className="example-header">
                  <span className="example-number">#{index + 1}</span>
                  {type === 'workflows' ? (
                    <h4 className="example-title">{example.title || 'Unknown Workflow'}</h4>
                  ) : (
                    <h4 className="example-title">{example.method_name || 'Unknown Method'}</h4>
                  )}
                  <button 
                    className="example-copy-button"
                    onClick={() => copyExample(example)}
                    title="Copy example details"
                  >
                    📋
                  </button>
                </div>
                
                <div className="example-content">
                  {type === 'workflows' ? (
                    <>
                      <div className="example-meta">
                        <span className="meta-item">
                          <strong>Similarity:</strong> {(example.similarity_score || 0).toFixed(3)}
                        </span>
                        <span className="meta-item">
                          <strong>Steps:</strong> {example.step_count || 'Unknown'}
                        </span>
                      </div>
                      
                      {example.workflow_steps && example.workflow_steps.length > 0 && (
                        <div className="workflow-steps">
                          <strong>Steps:</strong>
                          <ul>
                            {example.workflow_steps.map((step, stepIndex) => (
                              <li key={stepIndex}>
                                {typeof step === 'string' ? step : step.step_description || step}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      
                      {example.description && (
                        <div className="example-description">
                          <strong>Description:</strong> {example.description}
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <div className="example-meta">
                        <span className="meta-item">
                          <strong>Similarity:</strong> {(example.similarity_score || 0).toFixed(3)}
                        </span>
                        {example.paper_title && (
                          <span className="meta-item">
                            <strong>From Paper:</strong> {example.paper_title}
                          </span>
                        )}
                      </div>
                      
                      {example.searchable_summary && (
                        <div className="example-description">
                          <strong>Summary:</strong> {example.searchable_summary}
                        </div>
                      )}
                      
                      {example.category && (
                        <div className="example-category">
                          <strong>Category:</strong> {example.category}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

const ChatWindow = ({ conversation = {}, onConversationUpdate }) => {
  // Use conversation data if provided, otherwise default greeting
  const defaultGreeting = [{
    id: 1,
    role: 'assistant',
    content: 'Hi! I can help you with paleoclimate data analysis. Choose an agent above and let me know what you need!'
  }];

  const [messages, setMessages] = useState(conversation.messages?.length ? conversation.messages : defaultGreeting);
  const [inputValue, setInputValue] = useState('');
  const [stateId, setStateId] = useState(conversation.stateId || null);
  const [waitingForClarification, setWaitingForClarification] = useState(conversation.waitingForClarification || false);
  const [clarificationQuestions, setClarificationQuestions] = useState(conversation.clarificationQuestions || []);
  const [llmProvider, setLlmProvider] = useState(conversation.llmProvider || 'google');
  const [selectedAgent, setSelectedAgent] = useState(conversation.selectedAgent || 'workflow_manager');
  const [isLoading, setIsLoading] = useState(conversation.isLoading || false);
  const [error, setError] = useState(conversation.error || null);
  // Track answers to clarification questions
  const [clarificationAnswers, setClarificationAnswers] = useState(conversation.clarificationAnswers || {});
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  // Track the original request context when clarification is needed
  const [originalRequestContext, setOriginalRequestContext] = useState(conversation.originalRequestContext || null);
  
  // Clarification settings
  const [enableClarification, setEnableClarification] = useState(conversation.enableClarification ?? false);
  const [clarificationThreshold, setClarificationThreshold] = useState(conversation.clarificationThreshold || 'conservative');
  
  // Add state to track execution timing
  const [executionStartTime, setExecutionStartTime] = useState(conversation.executionStartTime || null);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Keep track of when we're updating from conversation prop to avoid loops
  const updatingFromPropRef = useRef(false);
  
  // Previous conversation ID to detect conversation switches
  const prevConversationIdRef = useRef(conversation.id);
  
  // Memoize conversation data to prevent unnecessary updates
  const conversationData = useMemo(() => {
      const firstUserMsg = messages.find((m) => m.role === 'user');
      // Only auto-generate title from first user message if current title is still the default
      const title = firstUserMsg && conversation.title === 'New Chat' 
        ? firstUserMsg.content.slice(0, 50) 
        : conversation.title || 'New Chat';

      return {
        id: conversation.id,
        title,
        messages,
        stateId,
        waitingForClarification,
        clarificationQuestions,
        clarificationAnswers,
        originalRequestContext,
        llmProvider,
        selectedAgent,
        isLoading,
        error,
        enableClarification,
        clarificationThreshold,
        executionStartTime,
      };
  }, [conversation.id, conversation.title, messages, stateId, waitingForClarification, 
      clarificationQuestions, clarificationAnswers, originalRequestContext, llmProvider, 
      selectedAgent, isLoading, error, enableClarification, clarificationThreshold, executionStartTime]);

  // Effect to notify parent about conversation updates
  useEffect(() => {
    // Only update parent if we're not currently updating from props (avoid circular updates)
    if (!updatingFromPropRef.current && onConversationUpdate && typeof onConversationUpdate === 'function') {
      onConversationUpdate(conversationData);
    }
  }, [conversationData, onConversationUpdate]);

  // Effect to sync with conversation prop changes (when switching conversations)
  useEffect(() => {
    // Only sync when the conversation ID actually changes (conversation switch)
    if (conversation.id && conversation.id !== prevConversationIdRef.current) {
      updatingFromPropRef.current = true;
      
      // If we're switching away from a conversation with an active request,
      // we need to be more careful about state management
      const isNewConversation = !conversation.messages || conversation.messages.length === 0;
      
      // Update messages if the conversation has different messages
      if (conversation.messages?.length) {
        setMessages(conversation.messages);
      } else {
        setMessages(defaultGreeting);
      }
      
      // Restore all states from conversation
      setStateId(conversation.stateId || null);
      setWaitingForClarification(conversation.waitingForClarification || false);
      setClarificationQuestions(conversation.clarificationQuestions || []);
      setClarificationAnswers(conversation.clarificationAnswers || {});
      setOriginalRequestContext(conversation.originalRequestContext || null);
      setLlmProvider(conversation.llmProvider || 'google');
      setSelectedAgent(conversation.selectedAgent || 'workflow_manager');
      setEnableClarification(conversation.enableClarification ?? true);
      setClarificationThreshold(conversation.clarificationThreshold || 'conservative');
      setExecutionStartTime(conversation.executionStartTime || null);
      
      // For new conversations, force loading to false regardless of stored state
      // This prevents loading state from carrying over when creating new conversations
      setIsLoading(isNewConversation ? false : (conversation.isLoading || false));
      setError(conversation.error || null);
      
      // Clear input value when switching conversations
      setInputValue('');
      
      // Update ref to track current conversation
      prevConversationIdRef.current = conversation.id;
      
      // Reset the flag after a brief delay to allow state updates to settle
      setTimeout(() => {
        updatingFromPropRef.current = false;
      }, 0);
    }
  }, [conversation.id, defaultGreeting]);

  // Scroll to bottom whenever messages change or loading state changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Focus input field on load
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleInputChange = (e) => {
    setInputValue(e.target.value);
  };

  const handleLlmProviderChange = (e) => {
    setLlmProvider(e.target.value);
  };

  const handleEnableClarificationChange = (e) => {
    setEnableClarification(e.target.checked);
  };

  const handleClarificationThresholdChange = (e) => {
    setClarificationThreshold(e.target.value);
  };

  const handleAgentChange = useCallback((e) => {
    const newAgent = e.target.value;
    
    // Batch state updates to prevent multiple re-renders
    updatingFromPropRef.current = true;
    
    setSelectedAgent(newAgent);
    // Reset conversation state when switching agents
    setStateId(null);
    setWaitingForClarification(false);
    setClarificationQuestions([]);
    setClarificationAnswers({});
    setOriginalRequestContext(null);
    setError(null);
    
    // Reset the flag after state updates complete
    setTimeout(() => {
      updatingFromPropRef.current = false;
    }, 0);
  }, []);

  // Start a new query conversation
  const handleNewQuery = () => {
    setStateId(null);
    setWaitingForClarification(false);
    setClarificationQuestions([]);
    setClarificationAnswers({});
    setOriginalRequestContext(null);
    setError(null);
    
    // Add a separator message to show new conversation
    const newConversationMessage = {
      id: Date.now(),
      role: 'assistant',
      content: 'Starting a new query conversation. What would you like to search for?',
      isNewConversation: true
    };
    setMessages(prev => [...prev, newConversationMessage]);
  };

  // Update clarification answer for a specific question
  const handleClarificationChoice = (questionId, choice) => {
    setClarificationAnswers(prev => ({
      ...prev,
      [questionId]: choice
    }));
  };

  // Update clarification answer input
  const handleClarificationAnswerChange = (questionId, value) => {
    setClarificationAnswers(prev => ({
      ...prev,
      [questionId]: value
    }));
  };

  // Handle workflow execution
  const handleExecuteWorkflow = async (workflowId) => {
    setIsLoading(true);
    setError(null);

    // Add user message to show workflow execution request
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: `Execute workflow: ${workflowId}`
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      // Prepare request for workflow execution
      const agentRequest = {
        agent_type: 'workflow_manager',
        capability: 'execute_workflow',
        user_input: workflowId,
        conversation_id: stateId,
        context: { workflow_id: workflowId },
        metadata: {
          llm_provider: llmProvider,
          workflow_id: workflowId,
          enable_clarification: enableClarification,
          clarification_threshold: clarificationThreshold
        }
      };

      console.log('Executing workflow:', agentRequest);

      // Send request to execute workflow
      const response = await axios.post('/agents/request', agentRequest);
      const data = response.data;

      console.log('Workflow execution response:', data);

      if (data.status === 'needs_clarification') {
        // Handle clarification for workflow execution
        setStateId(data.conversation_id);
        setWaitingForClarification(true);
        setClarificationAnswers({});
        
        // Store the original request context for workflow execution
        setOriginalRequestContext({
          agentType: 'workflow_manager',
          capability: 'execute_workflow',
          workflowId: workflowId,
          context: { workflow_id: workflowId },
          metadata: {
            llm_provider: llmProvider,
            workflow_id: workflowId,
            enable_clarification: enableClarification,
            clarification_threshold: clarificationThreshold
          }
        });
        
        if (data.clarification_questions && data.clarification_questions.length > 0) {
          setClarificationQuestions(data.clarification_questions);
        } else {
          const parsedQuestions = parseClarificationQuestions(data.message);
          setClarificationQuestions(parsedQuestions);
        }
        
        const assistantMessage = { 
          id: Date.now(), 
          role: 'assistant', 
          content: data.message,
          needsClarification: true,
          clarificationQuestions: data.clarification_questions
        };
        setMessages(prev => [...prev, assistantMessage]);
      } else if (data.status === 'success') {
        // Handle successful workflow execution
        setStateId(data.conversation_id);
        
        const executionResults = data.result?.execution_results;
        const failedSteps = data.result?.failed_steps;
        
        const resultsMessage = {
          id: Date.now(),
          role: 'assistant',
          content: data.message || 'Workflow executed successfully!',
          hasWorkflowExecution: true,
          workflowId: workflowId,
          executionResults: executionResults,
          failedSteps: failedSteps
        };
        
        setMessages(prev => [...prev, resultsMessage]);
        setOriginalRequestContext(null);
      } else {
        // Handle error
        console.error('Workflow execution error:', data.status);
        setError(data.message || 'Error executing workflow');
        
        const errorMessage = {
          id: Date.now(),
          role: 'assistant',
          content: `Sorry, I encountered an error executing the workflow: ${data.message || 'Unknown error'}`,
          isError: true
        };
        setMessages(prev => [...prev, errorMessage]);
      }
    } catch (error) {
      console.error('Error executing workflow:', error);
      setError(error.response?.data?.detail || 'Error executing workflow');
      
      const errorMessage = {
        id: Date.now(),
        role: 'assistant',
        content: `Sorry, I encountered an error executing the workflow: ${error.response?.data?.detail || error.message}`,
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
      
      // Reset clarification state on error but keep conversation state
      setWaitingForClarification(false);
      setClarificationQuestions([]);
      setClarificationAnswers({});
      setOriginalRequestContext(null);
    } finally {
      setIsLoading(false);
    }
  };


  /**
   * Stream an agent request via /agents/request/stream and update the chat with progress.
   */
  const streamAgentRequest = async (agentRequest, ownerId) => {
    // Clear any previous progress messages before starting new request
    setMessages(prev => prev.filter(m => !m.isNodeProgress));
    
    const startTime = Date.now();
    setExecutionStartTime(startTime);
    
    const resp = await fetch('/agents/request/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/plain'
      },
      body: JSON.stringify(agentRequest)
    });

    if (!resp.ok || !resp.body) {
      throw new Error(`Streaming request failed: ${resp.status}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResponse = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';

      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        let data;
        try {
          data = JSON.parse(part.slice(6));
        } catch (err) {
          console.warn('Failed to parse SSE chunk', err);
          continue;
        }

        if (data.type === 'start') {
          console.log('Agent execution started:', data.message);
          // Add a start message to track the beginning
          const startMsg = {
            id: `${Date.now()}_${Math.random().toString(36).substr(2,6)}`,
            role: 'assistant',
            isNodeProgress: true,
            phase: 'start',
            nodeName: 'Agent Execution',
            timestamp: startTime,
            summary: { message: data.message },
            ownerId
          };
          setMessages(prev => [...prev, startMsg]);
        } else if (data.type === 'node_start') {
          const startMsg = {
            id: `${Date.now()}_${Math.random().toString(36).substr(2,6)}`,
            role: 'assistant',
            isNodeProgress: true,
            phase: 'start',
            nodeName: data.node_name,
            timestamp: Date.now(),
            summary: data.current_state || {},
            ownerId
          };
          setMessages(prev => [...prev, startMsg]);
        } else if (data.type === 'node_complete') {
          // Mark node completion but keep loading state until final completion
          const compMsg = {
            id: `${Date.now()}_${Math.random().toString(36).substr(2,6)}`,
            role: 'assistant',
            isNodeProgress: true,
            phase: 'complete',
            nodeName: data.node_name,
            timestamp: Date.now(),
            summary: data.current_state || {},
            outputSummary: data.node_output || {},
            ownerId
          };
          setMessages(prev => [...prev, compMsg]);
        } else if (data.type === 'error') {
          throw new Error(data.message || 'Unknown streaming error');
        } else if (data.type === 'complete') {
          finalResponse = data.response;
          // Add completion timestamp
          const completeMsg = {
            id: `${Date.now()}_${Math.random().toString(36).substr(2,6)}`,
            role: 'assistant',
            isNodeProgress: true,
            phase: 'complete',
            nodeName: 'Agent Execution',
            timestamp: Date.now(),
            summary: { status: 'completed' },
            ownerId
          };
          setMessages(prev => [...prev, completeMsg]);
        }
      }
    }

    if (!finalResponse) {
      throw new Error('No final response received from streaming');
    }

    return finalResponse;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const currentUserInput = inputValue.trim();
    let userMessageId = Date.now(); // unique id for this user request

    // For clarification responses, collect all answers BEFORE resetting state
    let clarificationResponses = [];
    if (waitingForClarification) {
      // Collect all answered questions
      clarificationResponses = Object.entries(clarificationAnswers)
        .filter(([_, answer]) => answer && answer.trim())
        .map(([questionId, answer]) => ({
          question_id: questionId,
          response: answer.trim()
        }));
      
      // Don't proceed if no answers provided
      if (clarificationResponses.length === 0 && !currentUserInput) {
        return;
      }
      
      // Create a summary message showing all answers
      let summaryContent = '';
      if (clarificationResponses.length > 0) {
        summaryContent = clarificationResponses.map((answer) => {
          const question = clarificationQuestions.find(q => q.id === answer.question_id);
          const questionText = question ? question.question : `Question ${answer.question_id}`;
          return `Q: ${questionText}\nA: ${answer.response}`;
        }).join('\n\n');
        
        if (currentUserInput) {
          summaryContent += `\n\nAdditional comment: ${currentUserInput}`;
        }
      } else {
        summaryContent = currentUserInput;
      }
      
      // Add user message to chat
      userMessageId = Date.now();
      const userMessage = { 
        id: userMessageId, 
        role: 'user', 
        content: summaryContent,
        isCombinedAnswers: true
      };
      setMessages(prev => [...prev, userMessage]);
      
      // Hide clarification UI immediately after submission
      setWaitingForClarification(false);
      setClarificationQuestions([]);
      setClarificationAnswers({});
      // Clear original request context immediately to prevent it from affecting subsequent requests
      setOriginalRequestContext(null);
    } else {
      // Regular query - don't proceed if no input
      if (!currentUserInput) return;
      
      // Add user message to chat
      userMessageId = Date.now();
      const userMessage = { id: userMessageId, role: 'user', content: currentUserInput };
      setMessages(prev => [...prev, userMessage]);
    }
    
    // Clear input and set loading
    setInputValue('');
    setIsLoading(true);
    setError(null);
    
    try {
      // For clarification responses, use the original request context
      let agentType, capability;
      let tempOriginalContext = null;
      // Find the last assistant message that has an agentType (i.e., was produced by an agent run)
      const prevAssistantMsg = [...messages].reverse().find(m => m.role === 'assistant' && !m.isNodeProgress && m.agentType);
      const prevAgentType = prevAssistantMsg?.agentType;
      
      if (waitingForClarification && originalRequestContext && clarificationResponses.length > 0) {
        // Use original context only when we have clarification responses
        tempOriginalContext = originalRequestContext;
        agentType = originalRequestContext.agentType;
        capability = originalRequestContext.capability;
      } else {
        // Get the selected agent configuration for new requests
        const agentConfig = AGENT_TYPES.find(agent => agent.id === selectedAgent);
        if (!agentConfig) {
          throw new Error('Invalid agent selected');
        }
        agentType = selectedAgent;
        capability = agentConfig.capability;
      }
      
      // Determine if this is a refinement or cross-agent request
      let conversationIdForRequest = stateId;
      const extraContext = {};
      
      if (prevAssistantMsg) {
        // Same agent => refinement retains conversation id
        if (prevAgentType === agentType) {
          conversationIdForRequest = stateId;
        } else {
          // Different agent => new conversation
          conversationIdForRequest = null;
        }

        // Gather previous outputs into context regardless of agent type
        if (prevAssistantMsg.sparqlQuery) {
          extraContext.prev_sparql_query = prevAssistantMsg.sparqlQuery;
        }
        if (prevAssistantMsg.queryResults) {
          extraContext.prev_query_results = prevAssistantMsg.queryResults;
        }
        if (prevAssistantMsg.generatedCode) {
          extraContext.prev_generated_code = prevAssistantMsg.generatedCode;
        }
        if (prevAssistantMsg.workflowPlan) {
          extraContext.prev_workflow_plan = prevAssistantMsg.workflowPlan;
        }
        if (prevAssistantMsg.executionResults) {
          extraContext.prev_execution_results = prevAssistantMsg.executionResults;
        }
      }
      
      // Prepare request payload for the new multi-agent API
      const agentRequest = {
        agent_type: agentType,
        capability: capability,
        user_input: currentUserInput,
        conversation_id: conversationIdForRequest,
        context: extraContext,
        metadata: {
          llm_provider: llmProvider,
          enable_clarification: enableClarification,
          clarification_threshold: clarificationThreshold
        }
      };
      
      // If we have clarification responses to send, add them
      if (clarificationResponses.length > 0) {
        agentRequest.metadata.clarification_responses = clarificationResponses;
      }
      
      // If this is a clarification response for workflow execution, preserve the workflow context
      if (tempOriginalContext) {
        // Only override user_input for the main workflow execution capability, not for individual steps
        if (tempOriginalContext.workflowId && capability === 'execute_workflow') {
          agentRequest.user_input = tempOriginalContext.workflowId;
        }
        // Merge the original context and metadata
        if (tempOriginalContext.context) {
          agentRequest.context = { ...agentRequest.context, ...tempOriginalContext.context };
        }
        if (tempOriginalContext.metadata) {
          agentRequest.metadata = { ...agentRequest.metadata, ...tempOriginalContext.metadata };
        }
      }
      
      console.log('Sending agent request:', agentRequest);
      
      // Send request via streaming endpoint so we can show progress
      const data = await streamAgentRequest(agentRequest, userMessageId);
      
      // Update conversation ID from successful response so future requests are treated as refinements
      if (data.conversation_id) {
        setStateId(data.conversation_id);
      }
      
      // if backend wrapped useful fields under .result, unwrap
      const effectiveData = data.result ? { ...data, ...data.result } : data;
        
        console.log('Processing success response:', {
        generatedContent: !!effectiveData.generated_code,
        generatedContentLength: effectiveData.generated_code?.length,
        queryResults: !!data.execution_results,
        queryResultsLength: data.execution_results?.length,
        queryError: !!data.error,
        executionInfo: !!data.execution_info,
        workflowPlan: !!data.workflow_plan,
        workflowId: !!data.workflow_id,
        executionResults: !!data.execution_results,
        failedSteps: !!data.failed_steps,
          selectedAgent,
          fullData: data
        });
        
      // Get agent config for the agent that was actually used
      const usedAgentConfig = AGENT_TYPES.find(agent => agent.id === agentType) || 
                              AGENT_TYPES.find(agent => agent.id === selectedAgent);
      
      if (effectiveData.generated_code || effectiveData.workflow_plan || effectiveData.execution_results || effectiveData.failed_steps) {
        // Show results for code/SPARQL generation, workflow planning, or workflow execution
          const resultsMessage = { 
            id: Date.now() + 1, 
            role: 'assistant', 
            content: data.message || `${usedAgentConfig?.name || 'Agent'} completed successfully!`,
            agentType: agentType,
            hasQueryResults: agentType === 'sparql' && !!effectiveData.generated_code,
            hasGeneratedCode: agentType === 'code' && !!effectiveData.generated_code,
            hasWorkflowPlan: agentType === 'workflow_manager' && !!effectiveData.workflow_plan,
            hasWorkflowExecution: agentType === 'workflow_manager' && !!(effectiveData.execution_results || effectiveData.failed_steps),
            sparqlQuery: agentType === 'sparql' ? effectiveData.generated_code : undefined,
            generatedCode: agentType === 'code' ? effectiveData.generated_code : undefined,
            workflowPlan: effectiveData.workflow_plan,
            workflowId: effectiveData.workflow_id,
            executionResults: effectiveData.execution_results,
            failedSteps: effectiveData.failed_steps,
            queryResults: effectiveData.execution_results,
            queryError: effectiveData.error
          };
          
          setMessages(prev => [...prev, resultsMessage]);
          
        // Add agent-specific helpful messages
        let refinementMessage = null;
        if (agentType === 'sparql') {
          refinementMessage = {
            id: Date.now() + 2,
            role: 'assistant',
            content: "You can ask me to refine this query further! For example:\n• \"Add a filter for temperature > 20°C\"\n• \"Show only data from the last 100 years\"\n• \"Include location information\"\n• \"Sort by date descending\""
          };
        } else if (agentType === 'code') {
          refinementMessage = {
            id: Date.now() + 2,
            role: 'assistant',
            content: "You can ask me to modify this code! For example:\n• \"Add error handling\"\n• \"Include data visualization\"\n• \"Add comments to explain the code\"\n• \"Optimize for performance\""
          };
        } else if (agentType === 'workflow_manager' && effectiveData.workflow_plan) {
          refinementMessage = {
            id: Date.now() + 2,
            role: 'assistant',
            content: "Your workflow plan is ready! You can:\n• Click the \"Execute\" button to run the workflow\n• Ask me to modify the plan: \"Add a data visualization step\"\n• Request a different approach: \"Use a different statistical method\"\n• Plan a new workflow with a different request"
          };
        } else if (agentType === 'workflow_manager' && (effectiveData.execution_results || effectiveData.failed_steps)) {
          const successCount = effectiveData.execution_results?.length || 0;
          const totalSteps = successCount + (effectiveData.failed_steps?.length || 0);
          refinementMessage = {
            id: Date.now() + 2,
            role: 'assistant',
            content: effectiveData.failed_steps && effectiveData.failed_steps.length > 0 
              ? `Workflow completed with ${successCount}/${totalSteps} steps successful. You can:\n• Ask me to retry failed steps\n• Request modifications to the workflow\n• Plan a new workflow based on the results`
              : `Workflow completed successfully! All ${successCount} steps executed. You can:\n• Plan a follow-up workflow\n• Request analysis of the results\n• Ask for modifications or improvements`
          };
        }
        
        if (refinementMessage) {
          setMessages(prev => [...prev, refinementMessage]);
        }
        } else {
          // Add assistant message to chat
          const assistantMessage = { 
            id: Date.now(), 
            role: 'assistant', 
            content: data.message || `${usedAgentConfig?.name || 'Agent'} completed successfully!`,
            agentType: agentType
          };
          setMessages(prev => [...prev, assistantMessage]);
        }
    } catch (error) {
      console.error('Error calling agent API:', error);
      setError(error.response?.data?.detail || 'Error generating query');
      
      // Add error message to chat
      const errorMessage = { 
        id: Date.now(), 
        role: 'assistant', 
        content: `Sorry, I encountered an error: ${error.response?.data?.detail || error.message}`,
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
      
      // Reset clarification state on error but keep conversation state
      setWaitingForClarification(false);
      setClarificationQuestions([]);
      setClarificationAnswers({});
      setOriginalRequestContext(null);
    } finally {
      setIsLoading(false);
      setExecutionStartTime(null);
      
      // Keep progress messages visible after completion for user reference
    }
  };

  // Render the clarification options UI
  const renderClarificationOptions = () => {
    if (!waitingForClarification || clarificationQuestions.length === 0) {
      return null;
    }

    // Determine if we should use compact mode (for many questions)
    const useCompactMode = clarificationQuestions.length > 5;
    
    // Calculate progress
    const answeredCount = Object.keys(clarificationAnswers).filter(
      key => clarificationAnswers[key] && clarificationAnswers[key].trim() !== ''
    ).length;
    
    // Helper function to check if a question is answered
    const isQuestionAnswered = (questionId) => {
      return clarificationAnswers[questionId] && clarificationAnswers[questionId].trim() !== '';
    };
    
    // Helper function to handle choice selection with visual feedback
    const handleChoiceClick = (questionId, choice, event) => {
      handleClarificationChoice(questionId, choice);
      
      // Add visual feedback
      const button = event.target;
      button.classList.add('selected');
      setTimeout(() => {
        button.classList.remove('selected');
      }, 2000);
      
      // Auto-advance to next unanswered question
      const currentIndex = clarificationQuestions.findIndex(q => q.id === questionId);
      const nextUnansweredIndex = clarificationQuestions.findIndex((q, index) => 
        index > currentIndex && (!clarificationAnswers[q.id] || clarificationAnswers[q.id].trim() === '')
      );
      
      if (nextUnansweredIndex !== -1) {
        setTimeout(() => {
          const nextQuestionElement = document.querySelector(`[data-question-id="${clarificationQuestions[nextUnansweredIndex].id}"]`);
          if (nextQuestionElement) {
            nextQuestionElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 500);
      }
    };
    
    // Handle keyboard navigation
    const handleKeyDown = (event, questionId) => {
      if (event.key === 'Enter' && event.ctrlKey) {
        // Ctrl+Enter to submit
        const submitButton = document.querySelector('.send-button');
        if (submitButton) {
          submitButton.click();
        }
      } else if (event.key === 'Tab' && event.shiftKey) {
        // Shift+Tab to go to previous question
        event.preventDefault();
        const currentIndex = clarificationQuestions.findIndex(q => q.id === questionId);
        if (currentIndex > 0) {
          const prevQuestionElement = document.querySelector(`[data-question-id="${clarificationQuestions[currentIndex - 1].id}"] input`);
          if (prevQuestionElement) {
            prevQuestionElement.focus();
          }
        }
      } else if (event.key === 'Tab' && !event.shiftKey) {
        // Tab to go to next question
        event.preventDefault();
        const currentIndex = clarificationQuestions.findIndex(q => q.id === questionId);
        if (currentIndex < clarificationQuestions.length - 1) {
          const nextQuestionElement = document.querySelector(`[data-question-id="${clarificationQuestions[currentIndex + 1].id}"] input`);
          if (nextQuestionElement) {
            nextQuestionElement.focus();
          }
        }
      }
    };

    return (
      <div className={`clarification-options ${useCompactMode ? 'compact-mode' : ''}`}>
        <div className="clarification-title">
          {clarificationQuestions.length > 1 
            ? `Please answer ${clarificationQuestions.length} questions to help me generate the right response:` 
            : "Please provide clarification:"}
        </div>
        
        {/* Progress indicator for multiple questions */}
        {clarificationQuestions.length > 1 && (
          <div className="clarification-progress">
            <div className="progress-text">
              Progress: {answeredCount} of {clarificationQuestions.length} answered
            </div>
            <div className="progress-dots">
              {clarificationQuestions.map((question, index) => (
                <div 
                  key={question.id} 
                  className={`progress-dot ${
                    isQuestionAnswered(question.id) ? 'answered' : 
                    index === 0 ? 'current' : ''
                  }`}
                  title={`Question ${index + 1}: ${isQuestionAnswered(question.id) ? 'Answered' : 'Not answered'}`}
                />
              ))}
            </div>
          </div>
        )}
        
        <div className="clarification-questions-container">
          {clarificationQuestions.map((question, index) => {
            const isAnswered = isQuestionAnswered(question.id);
            
            return (
              <div 
                key={question.id} 
                className={`clarification-question-item ${isAnswered ? 'answered' : ''}`}
                data-question-id={question.id}
              >
                <div className="question-header">
                  {clarificationQuestions.length > 1 && (
                    <div className="question-number">
                      Question {index + 1} {isAnswered && '✓'}
                    </div>
                  )}
                  <div className="question-text">{question.question}</div>
                  {question.context && (
                    <div className="question-context">{question.context}</div>
                  )}
                </div>
                
                <div className="question-details">
                  {question.choices && question.choices.length > 0 && (
                    <div className="question-choices">
                      <div className="choices-label">Quick options:</div>
                      <div className="choices-buttons">
                        {question.choices.map((choice, choiceIndex) => {
                          const isSelected = clarificationAnswers[question.id] === choice;
                          return (
                            <button
                              key={choiceIndex}
                              className={`choice-button ${isSelected ? 'selected' : ''}`}
                              onClick={(e) => handleChoiceClick(question.id, choice, e)}
                            >
                              {choice}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  
                  <div className="question-answer">
                    <input
                      type="text"
                      value={clarificationAnswers[question.id] || ''}
                      onChange={(e) => handleClarificationAnswerChange(question.id, e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e, question.id)}
                      placeholder={
                        question.choices && question.choices.length > 0 
                          ? "Choose from options above or enter custom answer..."
                          : "Enter your answer..."
                      }
                      className={`clarification-answer-input ${isAnswered ? 'answered' : ''}`}
                      title="Use Tab/Shift+Tab to navigate, Ctrl+Enter to submit"
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        
        {/* Navigation/summary for many questions */}
        {clarificationQuestions.length > 3 && (
          <div className="clarification-navigation">
            <div className="nav-info">
              {answeredCount === clarificationQuestions.length 
                ? "All questions answered! Ready to submit." 
                : `${clarificationQuestions.length - answeredCount} questions remaining`}
            </div>
            <div className="keyboard-shortcuts">
              <small>💡 Tip: Use Tab/Shift+Tab to navigate, Ctrl+Enter to submit</small>
            </div>
            {answeredCount === clarificationQuestions.length && (
              <button 
                className="nav-button"
                onClick={() => {
                  // Scroll to submit button
                  const submitButton = document.querySelector('.send-button');
                  if (submitButton) {
                    submitButton.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    submitButton.focus();
                  }
                }}
              >
                Go to Submit →
              </button>
            )}
          </div>
        )}
      </div>
    );
  };

  // Helper to render individual chat message
  const renderChatMessage = (message) => (
    <div 
      key={message.id}
      className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'} ${message.isError ? 'error-message' : ''} ${message.needsClarification ? 'clarification-message' : ''} ${message.isCombinedAnswers ? 'clarification-response-message' : ''} ${(message.hasQueryResults || message.hasGeneratedCode || message.hasWorkflowPlan || message.hasWorkflowExecution) ? 'query-results-message' : ''} ${message.isNewConversation ? 'new-conversation-message' : ''}`}
    >
      {message.isCombinedAnswers ? (
        <ClarificationResponseMessage content={message.content} />
      ) : message.hasQueryResults || message.hasGeneratedCode || message.hasWorkflowPlan || message.hasWorkflowExecution ? (
        <QueryAndResultsMessage 
          query={message.sparqlQuery}
          results={message.queryResults}
          error={message.queryError}
          generatedCode={message.generatedCode}
          workflowPlan={message.workflowPlan}
          workflowId={message.workflowId}
          executionResults={message.executionResults}
          failedSteps={message.failedSteps}
          onExecuteWorkflow={handleExecuteWorkflow}
        />
      ) : message.needsClarification && waitingForClarification ? (
        <div className="message-content">{message.content}</div>
      ) : message.needsClarification ? (
        <ClarificationMessage 
          content={message.content}
          clarificationQuestions={message.clarificationQuestions}
        />
      ) : (
        <div className="message-content">{message.content}</div>
      )}
    </div>
  );

  return (
    <div className="chat-window">
      <div className="chat-header">
        <div className="header-controls">
          <div className="agent-selector">
            <label htmlFor="agent-type">Agent:</label>
            <select 
              id="agent-type" 
              value={selectedAgent} 
              onChange={handleAgentChange}
              className="agent-select"
            >
              {AGENT_TYPES.map(agent => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          </div>
          
          <div className="llm-provider-selector">
            <label htmlFor="llm-provider">LLM Provider:</label>
            <select 
              id="llm-provider" 
              value={llmProvider} 
              onChange={handleLlmProviderChange}
              className="llm-provider-select"
            >
              {LLM_PROVIDERS.map(provider => (
                <option key={provider.id} value={provider.id}>
                  {provider.name}
                </option>
              ))}
            </select>
          </div>
          
          <div className="clarification-settings">
            <div className="clarification-enable">
              <label htmlFor="enable-clarification">
                <input
                  id="enable-clarification"
                  type="checkbox"
                  checked={enableClarification}
                  onChange={handleEnableClarificationChange}
                  className="clarification-checkbox"
                />
                Enable Clarifications
              </label>
      </div>
      
            {enableClarification && (
              <div className="clarification-threshold">
                <label htmlFor="clarification-threshold">Threshold:</label>
                <select 
                  id="clarification-threshold" 
                  value={clarificationThreshold} 
                  onChange={handleClarificationThresholdChange}
                  className="clarification-threshold-select"
                >
                  <option value="permissive">Permissive</option>
                  <option value="conservative">Conservative</option>
                  <option value="strict">Strict</option>
                </select>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Partition messages to place progress widget before results */}
      {(()=>{
        const visibleMessages = messages.filter(m=>!m.isNodeProgress);
        const getProgressForOwner = (ownerId)=>messages.filter(m=>m.isNodeProgress && m.ownerId===ownerId);
        return (
          <div className="chat-messages">
            {visibleMessages.map(msg=>{
              const components=[renderChatMessage(msg)];
              if(msg.role==='user'){
                const progressMsgs=getProgressForOwner(msg.id);
                if(progressMsgs.length>0){
                  components.push(
                    <div key={`progress-${msg.id}`} className="message assistant-message loading-message">
                      <AgentProgressDisplay messages={progressMsgs} />
                    </div>
                  );
                }
              }
              return components;
            })}
            <div ref={messagesEndRef}/>
          </div>
        );
      })()}
      
      {renderClarificationOptions()}
      
      <form className="chat-input-form" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          placeholder={waitingForClarification 
            ? "Additional comments (optional)..." 
            : stateId 
              ? "Ask me to refine the result or ask a new question..." 
              : AGENT_TYPES.find(agent => agent.id === selectedAgent)?.placeholder || "Enter your request..."}
          className={`chat-input ${waitingForClarification ? 'clarification-input' : ''}`}
          disabled={isLoading}
        />
        <button 
          type="submit" 
          className="send-button"
          disabled={isLoading}
        >
          {isLoading ? 'Generating...' : waitingForClarification ? 'Submit Answers' : 'Send'}
        </button>
      </form>
    </div>
  );
};

export default ChatWindow; 