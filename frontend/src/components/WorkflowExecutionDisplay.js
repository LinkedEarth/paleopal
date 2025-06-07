import React, { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';

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
      <div className="border border-green-300 rounded-lg p-4 bg-green-50">
        <div className="flex justify-between items-center mb-4">
          <h4 className="text-green-800 font-medium m-0">⚡ Workflow Execution Results</h4>
          <div className="flex gap-2">
            <button 
              className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600 transition-colors"
              onClick={() => copyToClipboard(formatExecutionResults(executionResults, failedSteps))}
              title="Copy execution results to clipboard"
            >
              📋 Copy
            </button>
          </div>
        </div>
        
        <div className="space-y-4">
          <div className="bg-white rounded border border-green-200 p-3">
            <div className={`text-lg font-medium ${failedSteps && failedSteps.length > 0 ? 'text-yellow-700' : 'text-green-700'}`}>
              {failedSteps && failedSteps.length > 0 ? '⚠️' : '✅'} 
              {successfulSteps}/{totalSteps} steps completed successfully
            </div>
          </div>
          
          {executionResults && executionResults.length > 0 && (
            <div className="bg-white rounded border border-green-200 p-3">
              <h5 className="text-sm font-medium text-green-700 mb-3 m-0">✅ Successful Steps:</h5>
              <div className="space-y-3">
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
                    <div key={stepId} className="border border-gray-200 rounded p-3 bg-gray-50">
                      <div className="flex items-center justify-between mb-2">
                        <span className="bg-green-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium flex-shrink-0">
                          {index + 1}
                        </span>
                        <span className="flex-1 mx-3 text-sm font-medium text-gray-800">{stepId}</span>
                        <span className="text-sm text-green-600">✅ {result.status}</span>
                        {hasCode && (
                          <button 
                            className="ml-2 px-2 py-1 bg-blue-500 text-white rounded text-xs hover:bg-blue-600 transition-colors"
                            onClick={() => toggleStepExpansion(stepId)}
                            title={isExpanded ? "Collapse code" : "Expand code"}
                          >
                            {isExpanded ? '📄 Collapse' : '📄 View Code'}
                          </button>
                        )}
                      </div>
                      
                      {result.result && (
                        <div className="space-y-2">
                          {hasCode && (
                            <div className="space-y-2">
                              <div className="flex items-center justify-between">
                                <strong className="text-sm text-gray-700">
                                  {isSparqlStep ? 'Generated SPARQL Query:' : 'Generated Python Code:'}
                                </strong>
                                <button 
                                  className="px-2 py-1 bg-gray-500 text-white rounded text-xs hover:bg-gray-600 transition-colors"
                                  onClick={() => copyStepCode(generatedCode, stepId)}
                                  title="Copy code to clipboard"
                                >
                                  📋 Copy Code
                                </button>
                              </div>
                              
                              {isExpanded ? (
                                <div className="bg-white rounded border overflow-hidden">
                                  <SyntaxHighlighter
                                    language={isSparqlStep ? "sparql" : "python"}
                                    className="!m-0 !bg-white text-xs"
                                    customStyle={{
                                      margin: 0,
                                      padding: '0.75rem',
                                      backgroundColor: 'white',
                                      fontSize: '0.75rem',
                                      maxHeight: '400px',
                                      overflow: 'auto'
                                    }}
                                  >
                                    {generatedCode}
                                  </SyntaxHighlighter>
                                </div>
                              ) : (
                                <div className="bg-white rounded border p-3">
                                  <pre className="text-xs text-gray-700 whitespace-pre-wrap">
                                    {generatedCode.substring(0, 200)}
                                    {generatedCode.length > 200 ? '...' : ''}
                                  </pre>
                                  {generatedCode.length > 200 && (
                                    <div className="text-xs text-gray-500 mt-2">
                                      Click "View Code" to see the full {isSparqlStep ? 'query' : 'code'} ({generatedCode.length} characters)
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                          
                          {result.result.execution_results && (
                            <div className="text-sm text-gray-700 bg-white p-2 rounded border">
                              <strong>Results:</strong> {JSON.stringify(result.result.execution_results).substring(0, 100)}...
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          
          {failedSteps && failedSteps.length > 0 && (
            <div className="bg-white rounded border border-red-200 p-3">
              <h5 className="text-sm font-medium text-red-700 mb-3 m-0">❌ Failed Steps:</h5>
              <div className="space-y-3">
                {failedSteps.map((failure, index) => (
                  <div key={failure.step_id} className="border border-red-200 rounded p-3 bg-red-50">
                    <div className="flex items-center justify-between mb-2">
                      <span className="bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium flex-shrink-0">
                        {executionResults.length + index + 1}
                      </span>
                      <span className="flex-1 mx-3 text-sm font-medium text-gray-800">{failure.step_id}</span>
                      <span className="text-sm text-red-600">❌ {failure.status}</span>
                    </div>
                    <div className="text-sm text-red-700 bg-white p-2 rounded border border-red-200">
                      <strong>Error:</strong> {failure.error}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
};

export default WorkflowExecutionDisplay; 