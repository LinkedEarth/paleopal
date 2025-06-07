import React, { useEffect, useRef, useState } from 'react';

const WorkflowViewer = ({ workflowData, workflowId, onExecuteWorkflow, onExecuteStep }) => {
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [workflowSteps, setWorkflowSteps] = useState([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [executedSteps, setExecutedSteps] = useState(new Set());

  useEffect(() => {
    if (!workflowData) return;

    const parseWorkflow = () => {
      try {
        setIsLoading(true);
        setError(null);

        let parsedWorkflow;
        
        // If workflowData is a string, try to parse it as JSON
        if (typeof workflowData === 'string') {
          try {
            parsedWorkflow = JSON.parse(workflowData);
          } catch (parseError) {
            throw new Error(`Invalid JSON workflow: ${parseError.message}`);
          }
        } else {
          parsedWorkflow = workflowData;
        }

        // Validate the workflow structure
        if (!parsedWorkflow || !parsedWorkflow.steps || !Array.isArray(parsedWorkflow.steps)) {
          throw new Error('Invalid workflow structure - missing steps array');
        }

        // Extract and validate steps
        const steps = parsedWorkflow.steps.map(step => {
          if (!step.id || !step.name || !step.agent) {
            throw new Error(`Invalid step structure: ${JSON.stringify(step)}`);
          }
          
          if (!['sparql', 'code'].includes(step.agent.toLowerCase())) {
            throw new Error(`Invalid agent type: ${step.agent}. Must be 'sparql' or 'code'`);
          }

          return {
            id: step.id,
            name: step.name,
            agent: step.agent.toLowerCase(),
            description: step.description || step.name,
            input: step.input || step.description || step.name,
            expectedOutput: step.expected_output || `Output from ${step.name}`,
            dependencies: step.dependencies || [],
            originalTaskName: step.name
          };
        });

        setWorkflowSteps(steps);
        console.log(`Parsed ${steps.length} workflow steps:`, steps);
        setIsLoading(false);

      } catch (err) {
        console.error('Error parsing workflow:', err);
        setError('Failed to parse workflow: ' + err.message);
        setIsLoading(false);
      }
    };

    parseWorkflow();
  }, [workflowData, workflowId]);

  const copyWorkflowData = () => {
    const dataToCopy = typeof workflowData === 'string' ? workflowData : JSON.stringify(workflowData, null, 2);
    navigator.clipboard.writeText(dataToCopy).then(() => {
      console.log('Workflow data copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy workflow data:', err);
    });
  };

  const downloadWorkflow = () => {
    const dataToDownload = typeof workflowData === 'string' ? workflowData : JSON.stringify(workflowData, null, 2);
    const blob = new Blob([dataToDownload], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workflow-${workflowId || 'unknown'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleExecuteStepByStep = async () => {
    if (!onExecuteStep) {
      console.error('onExecuteStep callback not provided');
      return;
    }

    if (workflowSteps.length === 0) {
      alert('No executable steps found in workflow');
      return;
    }

    setIsExecuting(true);
    setCurrentStep(0);
    setExecutedSteps(new Set());

    // Show confirmation dialog
    const confirmed = window.confirm(
      `Execute workflow step by step?\n\n` +
      `This will send ${workflowSteps.length} requests:\n\n` +
      workflowSteps.map((step, i) => 
        `${i + 1}. ${step.agent.toUpperCase()} Agent: ${step.name}\n   Task: ${step.input.substring(0, 80)}${step.input.length > 80 ? '...' : ''}`
      ).join('\n\n') +
      `\n\nProceed?`
    );

    if (!confirmed) {
      setIsExecuting(false);
      return;
    }

    // Execute steps one by one
    for (let i = 0; i < workflowSteps.length; i++) {
      const step = workflowSteps[i];
      setCurrentStep(i);
      
      console.log(`Executing step ${i + 1}/${workflowSteps.length}:`, step);
      
      try {
        // Call the callback to execute this step
        await onExecuteStep({
          stepNumber: i + 1,
          totalSteps: workflowSteps.length,
          agentType: step.agent,
          input: step.input,
          stepName: step.name,
          stepId: step.id
        });
        
        // Mark step as executed
        setExecutedSteps(prev => new Set([...prev, step.id]));
        
        // Wait a bit before next step to let the UI update
        if (i < workflowSteps.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
      } catch (error) {
        console.error(`Failed to execute step ${i + 1}:`, error);
        alert(`Failed to execute step ${i + 1}: ${step.name}\nError: ${error.message}`);
        break;
      }
    }

    setIsExecuting(false);
    setCurrentStep(-1);
    console.log('Workflow execution completed');
  };

  if (error) {
    return (
      <div className="border border-red-300 rounded-lg p-4 bg-red-50">
        <div className="flex justify-between items-center mb-4">
          <h4 className="text-red-800 font-medium m-0">⚠️ Workflow (Error)</h4>
          <div className="flex gap-2">
            <button 
              className="px-3 py-1 bg-gray-500 text-white rounded text-sm hover:bg-gray-600 transition-colors"
              onClick={copyWorkflowData}
              title="Copy workflow data to clipboard"
            >
              📋 Copy Data
            </button>
          </div>
        </div>
        <div className="text-red-700 text-sm">
          {error}
        </div>
        <details className="mt-3">
          <summary className="text-red-700 cursor-pointer text-sm">Show Workflow Data</summary>
          <pre className="mt-2 p-2 bg-red-100 rounded text-xs overflow-x-auto">
            {typeof workflowData === 'string' ? workflowData : JSON.stringify(workflowData, null, 2)}
          </pre>
        </details>
      </div>
    );
  }

  return (
    <div className="border border-purple-300 rounded-lg p-4 bg-purple-50">
      <div className="flex justify-between items-center mb-4">
        <h4 className="text-purple-800 font-medium m-0">📋 Workflow Plan</h4>
        <div className="flex gap-2">
          <button 
            className="px-3 py-1 bg-gray-500 text-white rounded text-sm hover:bg-gray-600 transition-colors"
            onClick={copyWorkflowData}
            title="Copy workflow data to clipboard"
          >
            📋 Copy Data
          </button>
          <button 
            className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 transition-colors"
            onClick={downloadWorkflow}
            title="Download workflow file"
          >
            💾 Download
          </button>
          {onExecuteWorkflow && workflowId && (
            <button 
              className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600 transition-colors"
              onClick={() => onExecuteWorkflow(workflowId)}
              title="Execute this workflow"
            >
              ▶️ Execute
            </button>
          )}
          {onExecuteStep && (
            <button 
              className="px-3 py-1 bg-yellow-500 text-white rounded text-sm hover:bg-yellow-600 transition-colors"
              onClick={handleExecuteStepByStep}
              title="Execute workflow step by step"
            >
              🚀 Execute Step by Step
            </button>
          )}
        </div>
      </div>

      {isLoading && (
        <div className="text-center py-8 text-gray-600">
          Loading workflow...
        </div>
      )}

      {/* Workflow Steps */}
      {workflowSteps.length > 0 && (
        <div className="bg-white rounded border border-purple-200 p-3">
          <h5 className="text-sm font-medium text-purple-700 mb-3 m-0">
            Workflow Steps ({workflowSteps.length})
            {isExecuting && (
              <span className="ml-2 text-xs text-yellow-600">
                Executing step {currentStep + 1}...
              </span>
            )}
          </h5>
          <div className="space-y-3">
            {workflowSteps.map((step, index) => {
              const isExecuted = executedSteps.has(step.id);
              const isCurrent = isExecuting && index === currentStep;
              
              return (
                <div 
                  key={step.id} 
                  className={`border rounded p-3 transition-colors ${
                    isExecuted ? 'bg-green-50 border-green-200' :
                    isCurrent ? 'bg-yellow-50 border-yellow-300 ring-2 ring-yellow-200' :
                    'bg-gray-50 border-gray-200'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span className={`rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium flex-shrink-0 ${
                      isExecuted ? 'bg-green-500 text-white' :
                      isCurrent ? 'bg-yellow-500 text-white' :
                      'bg-purple-500 text-white'
                    }`}>
                      {isExecuted ? '✓' : 
                       isCurrent ? '▶' :
                       index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          step.agent === 'sparql' ? 'bg-blue-100 text-blue-800' :
                          step.agent === 'code' ? 'bg-green-100 text-green-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {step.agent.toUpperCase()}
                        </span>
                        <span className="text-xs text-gray-500">{step.id}</span>
                        {isExecuted && (
                          <span className="text-xs text-green-600 font-medium">Completed</span>
                        )}
                        {isCurrent && (
                          <span className="text-xs text-yellow-600 font-medium">Executing...</span>
                        )}
                      </div>
                      <div className="text-sm font-medium text-gray-800 mb-1">{step.name}</div>
                      {step.description && (
                        <div className="text-sm text-gray-600 mb-2">{step.description}</div>
                      )}
                      {step.dependencies && step.dependencies.length > 0 && (
                        <div className="text-xs text-gray-500">
                          <strong>Depends on:</strong> {step.dependencies.join(', ')}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Workflow ID */}
      {workflowId && (
        <div className="mt-3 text-xs text-gray-600">
          <strong>Workflow ID:</strong> {workflowId}
        </div>
      )}

      {/* JSON Data Display */}
      <details className="mt-3">
        <summary className="text-purple-700 cursor-pointer text-sm font-medium">Show JSON Data</summary>
        <pre className="mt-2 p-2 bg-purple-100 rounded text-xs overflow-x-auto">
          {typeof workflowData === 'string' ? workflowData : JSON.stringify(workflowData, null, 2)}
        </pre>
      </details>
    </div>
  );
};

export default WorkflowViewer; 