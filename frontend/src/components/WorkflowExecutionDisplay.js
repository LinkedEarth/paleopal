import React, { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';

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

export default WorkflowExecutionDisplay; 