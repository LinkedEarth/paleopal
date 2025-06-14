import React, { useEffect, useRef, useState } from 'react';
import THEME from '../styles/colorTheme';

const WorkflowViewer = ({ workflowData, workflowId, onExecuteWorkflow, onExecuteStep, messageIndex, allMessages, enableExecution = true }) => {
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [workflowSteps, setWorkflowSteps] = useState([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [executedSteps, setExecutedSteps] = useState(new Set());
  const [startedSteps, setStartedSteps] = useState(new Set());
  const [isExpanded, setIsExpanded] = useState(false);

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

  // Function to check if a step completed successfully
  const checkStepSuccess = async (stepId, stepNumber) => {
    // Wait a moment for messages to be updated
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    if (!allMessages || !Array.isArray(allMessages)) {
      console.warn('No messages available to check step success');
      return false;
    }

    // Find the most recent assistant message after this step was executed
    const recentAssistantMessages = allMessages
      .filter(msg => msg.role === 'assistant' && !msg.isNodeProgress)
      .sort((a, b) => new Date(b.timestamp || b.created_at || 0) - new Date(a.timestamp || a.created_at || 0));

    if (recentAssistantMessages.length === 0) {
      console.warn('No assistant messages found to check step success');
      return false;
    }

    const latestMessage = recentAssistantMessages[0];
    
    // Check for explicit error indicators
    if (latestMessage.error || latestMessage.queryError) {
      console.log(`Step ${stepNumber} failed: explicit error found`, {
        error: latestMessage.error,
        queryError: latestMessage.queryError
      });
      return false;
    }

    // Check execution results for errors
    if (latestMessage.executionResults && Array.isArray(latestMessage.executionResults)) {
      const hasErrors = latestMessage.executionResults.some(result => 
        result.type === 'error' || 
        result.status === 'error' ||
        (result.error && result.error.trim() !== '')
      );
      
      if (hasErrors) {
        console.log(`Step ${stepNumber} failed: execution errors found`, latestMessage.executionResults);
        return false;
      }
    }

    // Check message content for common error patterns
    if (latestMessage.content) {
      const errorPatterns = [
        /error/i,
        /failed/i,
        /exception/i,
        /traceback/i,
        /syntax error/i,
        /invalid/i,
        /could not/i,
        /unable to/i,
        /not found/i
      ];
      
      const hasErrorInContent = errorPatterns.some(pattern => pattern.test(latestMessage.content));
      if (hasErrorInContent) {
        console.log(`Step ${stepNumber} may have failed: error pattern found in content`);
        // Don't automatically fail for content patterns, as they might be false positives
        // Instead, log a warning but continue
        console.warn('Warning: Potential error detected in message content, but continuing execution');
      }
    }

    // Check if the message has successful completion indicators
    const hasSuccessIndicators = 
      latestMessage.hasQueryResults || 
      latestMessage.hasGeneratedCode || 
      latestMessage.generatedCode ||
      latestMessage.queryResults ||
      (latestMessage.executionResults && latestMessage.executionResults.length > 0 && 
       latestMessage.executionResults.some(result => result.type !== 'error' && result.status !== 'error'));

    if (hasSuccessIndicators) {
      console.log(`Step ${stepNumber} completed successfully: success indicators found`);
      return true;
    }

    // If no clear success indicators but also no clear errors, consider it successful
    // This handles cases where the agent completes but doesn't generate typical outputs
    console.log(`Step ${stepNumber} completed: no clear errors detected, assuming success`);
    return true;
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
        
        // Check if the step completed successfully before proceeding (only if execution is enabled)
        if (enableExecution) {
          const stepSuccess = await checkStepSuccess(step.id, originalStepIndex + 1);
          
          if (!stepSuccess) {
            console.error(`Step ${originalStepIndex + 1} failed or had errors, stopping workflow execution`);
            alert(`Step ${originalStepIndex + 1}: ${step.name} failed or encountered errors.\n\nWorkflow execution stopped. Please review the step results and fix any issues before continuing.`);
            break;
          }
        } else {
          console.log(`Step ${originalStepIndex + 1} completed - execution disabled, skipping success validation`);
        }
        
        // Mark step as executed (will be re-analyzed from messages)
        setExecutedSteps(prev => new Set([...prev, step.id]));
        
        console.log(`Step ${originalStepIndex + 1} completed successfully, proceeding to next step`);
        
        // Wait a bit before next step to let the UI update
        if (i < remainingSteps.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
      } catch (error) {
        console.error(`Failed to execute step ${originalStepIndex + 1}:`, error);
        alert(`Failed to execute step ${originalStepIndex + 1}: ${step.name}\nError: ${error.message}\n\nWorkflow execution stopped.`);
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
        
        // Check if the step completed successfully before proceeding (only if execution is enabled)
        if (enableExecution) {
          const stepSuccess = await checkStepSuccess(step.id, originalStepIndex + 1);
          
          if (!stepSuccess) {
            console.error(`Step ${originalStepIndex + 1} failed or had errors, stopping workflow execution`);
            alert(`Step ${originalStepIndex + 1}: ${step.name} failed or encountered errors.\n\nWorkflow execution stopped. Please review the step results and fix any issues before continuing.`);
            break;
          }
        } else {
          console.log(`Step ${originalStepIndex + 1} completed - execution disabled, skipping success validation`);
        }
        
        setExecutedSteps(prev => new Set([...prev, step.id]));
        
        console.log(`Step ${originalStepIndex + 1} completed successfully, proceeding to next step`);
        
        if (i < remainingSteps.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
      } catch (error) {
        console.error(`Failed to execute step ${originalStepIndex + 1}:`, error);
        alert(`Failed to execute step ${originalStepIndex + 1}: ${step.name}\nError: ${error.message}\n\nWorkflow execution stopped.`);
        break;
      }
    }

    setIsExecuting(false);
    setCurrentStep(-1);
  };

  const getStepIcon = (step) => {
    if (step.status === 'completed') {
      return (
        <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22,4 12,14.01 9,11.01"></polyline>
        </svg>
      );
    } else if (step.status === 'error') {
      return (
        <svg className="w-4 h-4 text-red-600" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
          <path d="m21 21-6-6m0 0a7 7 0 1 1 1.41-1.41L21 21z"></path>
          <circle cx="10" cy="10" r="7"></circle>
          <path d="M10 7v6l4-2"></path>
        </svg>
      );
    } else if (step.status === 'running') {
      return (
        <svg className="w-4 h-4 text-blue-600 animate-spin" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
          <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
        </svg>
      );
    } else {
      return (
        <svg className="w-4 h-4 text-neutral-400" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10"></circle>
        </svg>
      );
    }
  };

  const getActionIcon = (action) => {
    switch (action.type) {
      case 'sparql_query':
        return (
          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
            <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
            <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"></path>
            <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"></path>
          </svg>
        );
      case 'code_execution':
        return (
          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
            <path d="m7 8-4 4 4 4"></path>
            <path d="m17 8 4 4-4 4"></path>
            <path d="m14 4-4 16"></path>
          </svg>
        );
      case 'data_analysis':
        return (
          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
            <polyline points="22,12 18,12 15,21 9,3 6,12 2,12"></polyline>
          </svg>
        );
      default:
        return (
          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
        );
    }
  };

  if (error) {
    return (
      <div className="border border-neutral-200 dark:border-neutral-600 rounded-lg bg-neutral-50 dark:bg-neutral-800">
        <div className="flex justify-between items-center p-3 border-b border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 rounded-t-lg">
          <h4 className="text-neutral-800 dark:text-neutral-200 font-medium text-sm m-0 flex items-center gap-2">
            <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
              <path d="m21 21-6-6m0 0a7 7 0 1 1 1.41-1.41L21 21z"></path>
              <circle cx="10" cy="10" r="7"></circle>
              <path d="M10 7v6l4-2"></path>
            </svg>
            Workflow Error
          </h4>
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
          <div className={`border ${THEME.borders.default} rounded-lg ${THEME.containers.secondary}`}>
        <div className={`flex justify-between items-center p-3 border-b ${THEME.borders.default} ${THEME.containers.card} rounded-t-lg`}>
        <h4 className={`${THEME.text.primary} font-medium text-sm m-0 flex items-center gap-2`}>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
            <polygon points="5,3 19,12 5,21"></polygon>
          </svg>
          Workflow Plan
        </h4>
        <div className="flex gap-2">
          {onExecuteStep && !allCompleted && (
            <button 
              className={`px-3 py-1 ${THEME.buttons.primary} rounded text-xs transition-colors`}
              onClick={handleExecuteStepByStep}
              title={hasStarted ? "Continue execution from next step" : "Execute workflow step by step"}
              disabled={isExecuting}
            >
              {isExecuting ? (
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3 animate-spin" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
                  </svg>
                  Running...
                </span>
              ) : hasStarted ? (
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                    <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path>
                    <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"></path>
                    <path d="M8 12l4 4 4-4"></path>
                  </svg>
                  Continue
                </span>
              ) : (
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                    <polygon points="5,3 19,12 5,21"></polygon>
                  </svg>
                  Execute
                </span>
              )}
            </button>
          )}
          {allCompleted && (
            <span className={`px-3 py-1 ${THEME.status.success.background} ${THEME.status.success.text} rounded text-xs font-medium border ${THEME.status.success.border}`}>
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22,4 12,14.01 9,11.01"></polyline>
                </svg>
                Completed
              </span>
            </span>
          )}
        </div>
      </div>

      <div className="p-4 space-y-4">
            {isLoading && (
              <div className={`text-center py-8 ${THEME.text.secondary}`}>
                Loading workflow...
              </div>
            )}

        {/* Execution Status Summary */}
        {totalSteps > 0 && (
          <div className={`flex items-center justify-between p-3 ${THEME.containers.card} rounded-lg border ${THEME.borders.default}`}>
            <div className={`text-sm font-medium ${allCompleted ? THEME.status.success.text : hasStarted ? THEME.status.warning.text : THEME.text.primary}`}>
              <span className="flex items-center gap-2">
                {allCompleted ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22,4 12,14.01 9,11.01"></polyline>
                  </svg>
                ) : hasStarted ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                    <polyline points="22,12 18,12 15,21 9,3 6,12 2,12"></polyline>
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                    <rect width="8" height="8" x="3" y="3" rx="2"></rect>
                    <path d="M7 11v4a2 2 0 0 0 2 2h4"></path>
                    <rect width="8" height="8" x="13" y="13" rx="2"></rect>
                  </svg>
                )}
                {completedCount}/{totalSteps} steps completed
              </span>
              {startedCount > completedCount && (
                <span className={`ml-2 text-xs ${THEME.status.warning.text}`}>
                  ({startedCount - completedCount} in progress)
                </span>
              )}
              {isExecuting && (
                <span className={`ml-2 text-xs ${THEME.status.warning.text}`}>
                  (Executing step {currentStep + 1}...)
                </span>
              )}
            </div>
            
            {/* Progress bar */}
            <div className="flex-1 max-w-32 ml-4">
              <div className={`w-full ${THEME.containers.secondary} rounded-full h-2`}>
                <div 
                  className={`h-2 rounded-full transition-all duration-300 ${
                    allCompleted ? 'bg-emerald-500 dark:bg-emerald-600' : hasStarted ? 'bg-amber-500 dark:bg-amber-600' : 'bg-slate-500 dark:bg-slate-600'
                  }`}
                  style={{ width: `${totalSteps > 0 ? (completedCount / totalSteps) * 100 : 0}%` }}
                ></div>
              </div>
            </div>
          </div>
        )}

        {/* Workflow Steps */}
        {workflowSteps.length > 0 && (
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
                className={`p-4 rounded-lg border transition-all duration-200 ${
                  isCompleted ? `${THEME.status.success.background} border-emerald-200 dark:border-emerald-600` :
                  isInProgress ? `${THEME.status.warning.background} border-amber-200 dark:border-amber-600` :
                  isCurrent ? `${THEME.status.warning.background} border-amber-300 dark:border-amber-600 ring-2 ring-amber-200 dark:ring-amber-600` :
                  `${THEME.containers.card} border ${THEME.borders.default} hover:border-slate-300 dark:hover:border-slate-600`
                }`}
              >
                <div className="flex items-start gap-3">
                  <span className={`rounded-full w-8 h-8 flex items-center justify-center text-sm font-medium flex-shrink-0 ${
                    isCompleted ? 'bg-emerald-500 dark:bg-emerald-600 text-white' :
                    isInProgress ? 'bg-amber-500 dark:bg-amber-600 text-white' :
                    isCurrent ? 'bg-amber-500 dark:bg-amber-600 text-white' :
                    'bg-slate-500 dark:bg-slate-600 text-white'
                  }`}>
                    {isCompleted ? '✓' : 
                     isInProgress ? '⏳' :
                     isCurrent ? '▶' :
                     index + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <h6 className={`text-sm font-semibold ${THEME.text.primary} m-0`}>{step.name}</h6>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        step.agent === 'sparql' ? `${THEME.agents.sparql.background} ${THEME.agents.sparql.text}` :
                        step.agent === 'code' ? `${THEME.agents.code.background} ${THEME.agents.code.text}` :
                        step.agent === 'workflow' ? `${THEME.agents.workflow.background} ${THEME.agents.workflow.text}` :
                        `${THEME.containers.secondary} ${THEME.text.primary}`
                      }`}>
                        {step.agent.toUpperCase()}
                      </span>
                      {isCompleted && (
                        <span className={`text-xs ${THEME.status.success.text} font-medium flex items-center gap-1`}>
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                          Completed
                        </span>
                      )}
                      {isInProgress && (
                        <span className={`text-xs ${THEME.status.warning.text} font-medium flex items-center gap-1`}>
                          <svg className="w-3 h-3 animate-spin" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          In Progress
                        </span>
                      )}
                      {isCurrent && (
                        <span className={`text-xs ${THEME.status.warning.text} font-medium flex items-center gap-1`}>
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M8 5v14l11-7z"/>
                          </svg>
                          Executing...
                        </span>
                      )}
                      {canExecuteFrom && (
                        <button
                          className={`ml-auto px-3 py-1 ${THEME.buttons.primary} rounded-full text-xs transition-colors`}
                          onClick={() => handleExecuteFromStep(index)}
                          title={`Execute workflow starting from step ${index + 1}`}
                        >
                          <span className="flex items-center gap-1">
                            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M8 5v14l11-7z"/>
                            </svg>
                            Resume from here
                          </span>
                        </button>
                      )}
                    </div>
                    {step.description && (
                      <p className={`text-sm ${THEME.text.secondary} mb-3 m-0`}>{step.description}</p>
                    )}
                    <div className={`text-xs ${THEME.text.secondary} ${THEME.containers.secondary} p-3 rounded-lg border ${THEME.borders.default}`}>
                      <div className="font-medium mb-1">Task Input:</div>
                      <div>{step.input}</div>
                    </div>
                    {step.expected_output && (
                      <div className={`text-xs ${THEME.text.secondary} ${THEME.status.info.background} p-3 rounded-lg border ${THEME.status.info.border} mt-2`}>
                        <div className="font-medium mb-1">Expected Output:</div>
                        <div>{step.expected_output}</div>
                      </div>
                    )}
                    {step.dependencies && step.dependencies.length > 0 && (
                      <div className={`text-xs ${THEME.text.secondary} mt-2`}>
                        <span className="font-medium">Dependencies:</span> {step.dependencies.join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        )}
      </div>
    </div>
  );
};

export default WorkflowViewer; 