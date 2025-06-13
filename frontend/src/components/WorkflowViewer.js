import React, { useEffect, useRef, useState } from 'react';

const WorkflowViewer = ({ workflowData, workflowId, onExecuteWorkflow, onExecuteStep, messageIndex, allMessages }) => {
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [workflowSteps, setWorkflowSteps] = useState([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [executedSteps, setExecutedSteps] = useState(new Set());
  const [startedSteps, setStartedSteps] = useState(new Set());

  // Analyze messages after this workflow to determine started and completed steps
  const analyzeWorkflowExecution = () => {
    if (!allMessages || !Array.isArray(allMessages) || messageIndex === undefined) {
      return { started: new Set(), completed: new Set() };
    }

    const started = new Set();
    const completed = new Set();
    
    // Look at messages that come after this workflow plan message
    const subsequentMessages = allMessages.slice(messageIndex + 1);
    
    // Match workflow steps with messages
    workflowSteps.forEach(step => {
      const stepInput = step.input.trim();
      
      // Find user message that contains this step's input (step started)
      const startMessage = subsequentMessages.find(message => {
        if (message.role !== 'user' || !message.content) return false;
        
        const messageContent = message.content.trim();
        
        // Check for step input patterns
        return (
          // Direct match of step input
          messageContent === stepInput ||
          
          // Step execution message that contains the step input
          (messageContent.includes(stepInput) && (
            messageContent.toLowerCase().includes('step ') ||
            messageContent.toLowerCase().includes('agent task')
          )) ||
          
          // Step execution with agent pattern
          (messageContent.toLowerCase().includes(`${step.agent.toLowerCase()} agent task:`) &&
           messageContent.includes(stepInput))
        );
      });
      
      if (startMessage) {
        started.add(step.id);
        
        // Find the index of the start message
        const startMessageIndex = subsequentMessages.indexOf(startMessage);
        
        // Look for assistant response after the start message
        const responseMessage = subsequentMessages.slice(startMessageIndex + 1).find(message => {
          if (message.role !== 'assistant') return false;
          
          // Check if this is a substantial response (completed step)
          return (
            message.hasGeneratedCode || 
            message.generatedCode || 
            message.query || 
            message.sparqlQuery ||
            message.hasQueryResults ||
            message.hasWorkflowPlan ||
            (message.content && message.content.length > 50) // Substantial response content
          );
        });
        
        // If we found a response, mark as completed
        if (responseMessage) {
          completed.add(step.id);
        }
      }
    });

    console.log('🔍 Workflow execution analysis:', {
      workflowSteps: workflowSteps.map(s => ({ 
        id: s.id, 
        name: s.name, 
        agent: s.agent,
        input: s.input.substring(0, 50) + '...'
      })),
      subsequentMessages: subsequentMessages.length,
      userMessages: subsequentMessages.filter(m => m.role === 'user').length,
      assistantMessages: subsequentMessages.filter(m => m.role === 'assistant').length,
      startedSteps: Array.from(started),
      completedSteps: Array.from(completed)
    });

    return { started, completed };
  };

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

        // Transform workflow data for display
        const steps = parsedWorkflow.steps.map(step => ({
            id: step.id,
            name: step.name,
          description: step.description || '',
          agent: step.agent,
          input: step.input,
          expected_output: step.expected_output || '',
          dependencies: step.dependencies || []
        }));

        setWorkflowSteps(steps);
        
        // Analyze execution status from messages
        const { started, completed } = analyzeWorkflowExecution();
        setStartedSteps(started);
        setExecutedSteps(completed);
        
        setIsLoading(false);
      } catch (err) {
        console.error('Error parsing workflow:', err);
        setError(err.message);
        setIsLoading(false);
      }
    };

    parseWorkflow();
  }, [workflowData, allMessages, messageIndex]);

  // Re-analyze when messages change
  useEffect(() => {
    if (workflowSteps.length > 0) {
      const { started, completed } = analyzeWorkflowExecution();
      setStartedSteps(started);
      setExecutedSteps(completed);
    }
  }, [allMessages, workflowSteps, messageIndex]);

  const copyWorkflowData = () => {
    const dataToDownload = typeof workflowData === 'string' ? workflowData : JSON.stringify(workflowData, null, 2);
    navigator.clipboard.writeText(dataToDownload).then(() => {
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

    // Filter out already completed steps
    const remainingSteps = workflowSteps.filter(step => !startedSteps.has(step.id));
    
    if (remainingSteps.length === 0) {
      alert('All workflow steps have already been executed!');
      return;
    }

    setIsExecuting(true);
    setCurrentStep(0);

    // Show confirmation dialog with execution plan
    const confirmed = window.confirm(
      `Execute remaining workflow steps?\n\n` +
      `${remainingSteps.length} of ${workflowSteps.length} steps remaining:\n\n` +
      remainingSteps.map((step, i) => 
        `${workflowSteps.indexOf(step) + 1}. ${step.agent.toUpperCase()} Agent: ${step.name}\n   Task: ${step.input.substring(0, 80)}${step.input.length > 80 ? '...' : ''}`
      ).join('\n\n') +
      `\n\nProceed?`
    );

    if (!confirmed) {
      setIsExecuting(false);
      return;
    }

    // Execute remaining steps one by one
    for (let i = 0; i < remainingSteps.length; i++) {
      const step = remainingSteps[i];
      const originalStepIndex = workflowSteps.indexOf(step);
      setCurrentStep(originalStepIndex);
      
      console.log(`Executing remaining step ${i + 1}/${remainingSteps.length}:`, step);
      
      try {
        // Call the callback to execute this step
        await onExecuteStep({
          stepNumber: originalStepIndex + 1,
          totalSteps: workflowSteps.length,
          agentType: step.agent,
          input: step.input,
          description: step.description,
          stepName: step.name,
          stepId: step.id,
          dependencies: step.dependencies || [],
          expectedOutput: step.expected_output,
          allWorkflowSteps: workflowSteps
        });
        
        // Mark step as executed (will be re-analyzed from messages)
        setExecutedSteps(prev => new Set([...prev, step.id]));
        
        // Wait a bit before next step to let the UI update
        if (i < remainingSteps.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
      } catch (error) {
        console.error(`Failed to execute step ${originalStepIndex + 1}:`, error);
        alert(`Failed to execute step ${originalStepIndex + 1}: ${step.name}\nError: ${error.message}`);
        break;
      }
    }

    setIsExecuting(false);
    setCurrentStep(-1);
    console.log('Workflow execution completed');
  };

  const handleExecuteFromStep = async (startStepIndex) => {
    if (!onExecuteStep) {
      console.error('onExecuteStep callback not provided');
      return;
    }

    // Get steps from the selected point onwards, filtering out completed ones
    const stepsFromIndex = workflowSteps.slice(startStepIndex);
    const remainingSteps = stepsFromIndex.filter(step => !startedSteps.has(step.id));
    
    if (remainingSteps.length === 0) {
      alert('All steps from this point onwards have already been started!');
      return;
    }

    const confirmed = window.confirm(
      `Execute workflow from step ${startStepIndex + 1}?\n\n` +
      `${remainingSteps.length} remaining steps:\n\n` +
      remainingSteps.map((step, i) => 
        `${workflowSteps.indexOf(step) + 1}. ${step.agent.toUpperCase()} Agent: ${step.name}`
      ).join('\n') +
      `\n\nProceed?`
    );

    if (!confirmed) return;

    setIsExecuting(true);
    
    for (let i = 0; i < remainingSteps.length; i++) {
      const step = remainingSteps[i];
      const originalStepIndex = workflowSteps.indexOf(step);
      setCurrentStep(originalStepIndex);
      
      try {
        await onExecuteStep({
          stepNumber: originalStepIndex + 1,
          totalSteps: workflowSteps.length,
          agentType: step.agent,
          input: step.input,
          description: step.description,
          stepName: step.name,
          stepId: step.id,
          dependencies: step.dependencies || [],
          expectedOutput: step.expected_output,
          allWorkflowSteps: workflowSteps
        });
        
        setExecutedSteps(prev => new Set([...prev, step.id]));
        
        if (i < remainingSteps.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
      } catch (error) {
        console.error(`Failed to execute step ${originalStepIndex + 1}:`, error);
        alert(`Failed to execute step ${originalStepIndex + 1}: ${step.name}\nError: ${error.message}`);
        break;
      }
    }

    setIsExecuting(false);
    setCurrentStep(-1);
  };

  if (error) {
    return (
      <div className="border border-neutral-200 dark:border-neutral-600 rounded-lg bg-neutral-50 dark:bg-neutral-800">
        <div className="flex justify-between items-center p-3 border-b border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 rounded-t-lg">
          <h4 className="text-neutral-800 dark:text-neutral-200 font-medium text-sm m-0">❌ Workflow Error</h4>
        </div>
        <div className="p-3">
          <div className="text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 p-3 rounded border border-red-200 dark:border-red-600 text-sm">{error}</div>
        </div>
      </div>
    );
  }

  const completedCount = executedSteps.size;
  const startedCount = startedSteps.size;
  const totalSteps = workflowSteps.length;
  const allCompleted = completedCount === totalSteps;
  const hasStarted = startedCount > 0;

  return (
    <div className="border border-neutral-200 dark:border-neutral-600 rounded-lg bg-neutral-50 dark:bg-neutral-800">
      <div className="flex justify-between items-center p-3 border-b border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 rounded-t-lg">
        <h4 className="text-neutral-800 dark:text-neutral-200 font-medium text-sm m-0">📋 Workflow Plan</h4>
        <div className="flex gap-2">
          <button 
            className="px-3 py-1 bg-blue-100 dark:bg-blue-800/30 text-blue-700 dark:text-blue-300 rounded text-xs hover:bg-blue-200 dark:hover:bg-blue-700/50 transition-colors border border-blue-300 dark:border-blue-600"
            onClick={copyWorkflowData}
            title="Copy workflow data to clipboard"
          >
            📋 Copy
          </button>
          <button 
            className="px-3 py-1 bg-blue-100 dark:bg-blue-800/30 text-blue-700 dark:text-blue-300 rounded text-xs hover:bg-blue-200 dark:hover:bg-blue-700/50 transition-colors border border-blue-300 dark:border-blue-600"
            onClick={downloadWorkflow}
            title="Download workflow file"
          >
            💾 Download
          </button>
          {onExecuteStep && !allCompleted && (
            <button 
                                className="px-3 py-1 bg-blue-600 dark:bg-blue-600 text-white rounded text-xs hover:bg-blue-700 dark:hover:bg-blue-700 transition-colors border border-blue-600 dark:border-blue-600"
              onClick={handleExecuteStepByStep}
              title={hasStarted ? "Continue execution from next step" : "Execute workflow step by step"}
              disabled={isExecuting}
            >
              {isExecuting ? '⏳ Running...' : hasStarted ? '🔄 Continue' : '🚀 Execute'}
            </button>
          )}
          {allCompleted && (
            <span className="px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400 rounded text-xs font-medium border border-green-300 dark:border-green-600">
              ✅ Completed
            </span>
          )}
        </div>
      </div>

      <div className="p-3">
        <div className="bg-white dark:bg-neutral-800 rounded border border-neutral-200 dark:border-neutral-600 overflow-hidden max-h-96 overflow-y-auto">
          <div className="p-4 space-y-4">
            {isLoading && (
              <div className="text-center py-8 text-neutral-600 dark:text-neutral-400">
                Loading workflow...
              </div>
            )}

            {/* Execution Status Summary */}
            {totalSteps > 0 && (
              <div className="bg-neutral-50 dark:bg-neutral-700 rounded border border-neutral-200 dark:border-neutral-600 p-3">
                <div className="flex items-center justify-between">
                  <div className={`text-sm font-medium ${allCompleted ? 'text-green-700 dark:text-green-400' : hasStarted ? 'text-yellow-700 dark:text-yellow-400' : 'text-neutral-700 dark:text-neutral-300'}`}>
                    {allCompleted ? '✅' : hasStarted ? '⚡' : '📋'} 
                    {completedCount}/{totalSteps} steps completed
                    {startedCount > completedCount && (
                      <span className="ml-2 text-xs text-orange-600 dark:text-orange-400">
                        ({startedCount - completedCount} in progress)
                      </span>
                    )}
                    {isExecuting && (
                      <span className="ml-2 text-xs text-yellow-600 dark:text-yellow-400">
                        (Executing step {currentStep + 1}...)
                      </span>
                    )}
                  </div>
                  {hasStarted && !allCompleted && (
                    <div className="text-xs text-neutral-600 dark:text-neutral-400">
                      Workflow can be resumed from any pending step
                    </div>
                  )}
                </div>
                
                {/* Progress bar */}
                <div className="mt-2 w-full bg-neutral-200 dark:bg-neutral-600 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full transition-all duration-300 ${
                      allCompleted ? 'bg-green-500 dark:bg-green-600' : hasStarted ? 'bg-yellow-500 dark:bg-yellow-600' : 'bg-neutral-500 dark:bg-neutral-400'
                    }`}
                    style={{ width: `${totalSteps > 0 ? (completedCount / totalSteps) * 100 : 0}%` }}
                  ></div>
                </div>
              </div>
            )}

            {/* Workflow Steps */}
            {workflowSteps.length > 0 && (
              <div className="bg-neutral-50 dark:bg-neutral-700 rounded border border-neutral-200 dark:border-neutral-600 p-3">
                <h5 className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-3 m-0">
                  Workflow Steps ({workflowSteps.length})
                </h5>
          <div className="space-y-3">
            {workflowSteps.map((step, index) => {
              const isCompleted = executedSteps.has(step.id);
              const isStarted = startedSteps.has(step.id);
              const isInProgress = isStarted && !isCompleted;
              const isCurrent = isExecuting && index === currentStep;
              const canExecuteFrom = !isStarted && onExecuteStep && !isExecuting;
              
              return (
                <div 
                  key={step.id} 
                  className={`border rounded p-3 transition-colors ${
                    isCompleted ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-600' :
                    isInProgress ? 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-600' :
                    isCurrent ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-300 dark:border-yellow-600 ring-2 ring-yellow-200 dark:ring-yellow-600' :
                    'bg-white dark:bg-neutral-800 border-neutral-200 dark:border-neutral-600'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span className={`rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium flex-shrink-0 ${
                      isCompleted ? 'bg-green-500 dark:bg-green-600 text-white' :
                      isInProgress ? 'bg-orange-500 dark:bg-orange-600 text-white' :
                      isCurrent ? 'bg-yellow-500 dark:bg-yellow-600 text-white' :
                      'bg-neutral-500 dark:bg-neutral-600 text-white'
                    }`}>
                      {isCompleted ? '✓' : 
                       isInProgress ? '⏳' :
                       isCurrent ? '▶' :
                       index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          step.agent === 'sparql' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300' :
                          step.agent === 'code' ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300' :
                          'bg-neutral-100 dark:bg-neutral-600 text-neutral-800 dark:text-neutral-200'
                        }`}>
                          {step.agent.toUpperCase()}
                        </span>
                        <span className="text-xs text-neutral-500 dark:text-neutral-400">{step.id}</span>
                        {isCompleted && (
                          <span className="text-xs text-green-600 dark:text-green-400 font-medium">Completed</span>
                        )}
                        {isInProgress && (
                          <span className="text-xs text-orange-600 dark:text-orange-400 font-medium">In Progress</span>
                        )}
                        {isCurrent && (
                          <span className="text-xs text-yellow-600 dark:text-yellow-400 font-medium">Executing...</span>
                        )}
                        {canExecuteFrom && (
                          <button
                            className="ml-auto px-2 py-1 bg-orange-500 dark:bg-orange-600 text-white rounded text-xs hover:bg-orange-600 dark:hover:bg-orange-500 transition-colors"
                            onClick={() => handleExecuteFromStep(index)}
                            title={`Execute workflow starting from step ${index + 1}`}
                          >
                            ▶ Resume from here
                          </button>
                        )}
                      </div>
                      <div className="text-sm font-medium text-neutral-800 dark:text-neutral-200 mb-1">{step.name}</div>
                      {step.description && (
                        <div className="text-sm text-neutral-600 dark:text-neutral-400 mb-2">{step.description}</div>
                      )}
                      <div className="text-xs text-neutral-600 dark:text-neutral-400 bg-neutral-100 dark:bg-neutral-700 p-2 rounded">
                        <strong>Input:</strong> {step.input}
                      </div>
                      {step.expected_output && (
                        <div className="text-xs text-neutral-600 dark:text-neutral-400 bg-blue-50 dark:bg-blue-900/20 p-2 rounded mt-1">
                          <strong>Expected Output:</strong> {step.expected_output}
                        </div>
                      )}
                      {step.dependencies && step.dependencies.length > 0 && (
                        <div className="text-xs text-neutral-600 dark:text-neutral-400 mt-1">
                          <strong>Dependencies:</strong> {step.dependencies.join(', ')}
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
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkflowViewer; 