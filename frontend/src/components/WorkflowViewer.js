import React, { useEffect, useRef, useState } from 'react';
import THEME from '../styles/colorTheme';
import Icon from './Icon';
// Use prism syntax highlighter for execution output
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { buildApiUrl, apiRequest } from '../config/api';

// Modal component for showing workflow step execution results
const WorkflowExecutionModal = ({ isOpen, onClose, title, executionData, stepName }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className={`${THEME.containers.card} rounded-lg border ${THEME.borders.default} max-w-4xl w-full max-h-[80vh] overflow-hidden`}>
        {/* Modal Header */}
        <div className={`flex justify-between items-center p-4 border-b ${THEME.borders.default}`}>
          <h3 className={`text-lg font-semibold ${THEME.text.primary} m-0`}>
            {title}
          </h3>
          <button
            className={`p-1 hover:bg-neutral-100 dark:hover:bg-neutral-600 rounded transition-colors`}
            onClick={onClose}
          >
            <Icon name="close" className="w-5 h-5" />
          </button>
        </div>
        
        {/* Modal Content */}
        <div className="p-4 overflow-y-auto max-h-[calc(80vh-120px)]">
          {executionData && (
            <div className="space-y-4">
              {/* Step Information */}
              <div>
                <h4 className={`font-medium ${THEME.text.primary} mb-2`}>Step: {stepName}</h4>
              </div>
              
              {/* Execution Status */}
              <div className="flex items-center gap-2">
                <span className={`text-sm font-medium ${
                  executionData.execution_successful 
                    ? THEME.status.success.text
                    : THEME.status.error.text
                }`}>
                  {executionData.execution_successful ? '✓ Execution Successful' : '✗ Execution Failed'}
                </span>
                {executionData.execution_time && (
                  <span className={`${THEME.text.muted} text-xs`}>
                    ({executionData.execution_time.toFixed(2)}s)
                  </span>
                )}
              </div>
              
              {/* Generated Code */}
              {executionData.code && (
                <div>
                  <div className={`text-sm font-medium ${THEME.text.primary} mb-2`}>Generated Code:</div>
                  <SyntaxHighlighter
                    language="python"
                    style={{
                      ...(document.documentElement.classList.contains('dark') ? oneDark : oneLight),
                      'code[class*="language-"]': { background: 'transparent', backgroundColor: 'transparent' },
                      'pre[class*="language-"]': { background: 'transparent', backgroundColor: 'transparent' }
                    }}
                    customStyle={{ margin: 0, padding: '1rem', background: 'transparent', fontSize: '13px' }}
                    className={`!m-0 rounded border ${THEME.borders.default}`}
                  >
                    {executionData.code}
                  </SyntaxHighlighter>
                </div>
              )}
              
              {/* SPARQL Query */}
              {executionData.sparql && (
                <div>
                  <div className={`text-sm font-medium ${THEME.text.primary} mb-2`}>SPARQL Query:</div>
                  <SyntaxHighlighter
                    language="sparql"
                    style={{
                      ...(document.documentElement.classList.contains('dark') ? oneDark : oneLight),
                      'code[class*="language-"]': { background: 'transparent', backgroundColor: 'transparent' },
                      'pre[class*="language-"]': { background: 'transparent', backgroundColor: 'transparent' }
                    }}
                    customStyle={{ margin: 0, padding: '1rem', background: 'transparent', fontSize: '13px' }}
                    className={`!m-0 rounded border ${THEME.borders.default}`}
                  >
                    {executionData.sparql}
                  </SyntaxHighlighter>
                </div>
              )}
              
              {/* Execution Output */}
              {executionData.execution_output && (
                <div>
                  <div className={`text-sm font-medium ${THEME.text.primary} mb-2`}>Output:</div>
                  <pre className={`text-sm ${THEME.containers.secondary} p-3 rounded border ${THEME.borders.default} overflow-x-auto whitespace-pre-wrap ${THEME.text.primary} max-h-64 overflow-y-auto`}>
                    {executionData.execution_output}
                  </pre>
                </div>
              )}
              
              {/* Execution Error */}
              {executionData.execution_error && (
                <div>
                  <div className={`text-sm font-medium ${THEME.status.error.text} mb-2`}>Error:</div>
                  <pre className={`text-sm ${THEME.status.error.background} p-3 rounded border ${THEME.status.error.border} overflow-x-auto whitespace-pre-wrap ${THEME.status.error.text} max-h-64 overflow-y-auto`}>
                    {executionData.execution_error}
                  </pre>
                </div>
              )}
              
              {/* Variable State */}
              {executionData.variable_summary && (
                <div>
                  <div className={`text-sm font-medium ${THEME.text.primary} mb-2`}>Variable State:</div>
                  <div className={`text-sm ${THEME.containers.secondary} p-3 rounded border ${THEME.borders.default} overflow-x-auto`}>
                    <pre className={`whitespace-pre-wrap ${THEME.text.primary}`}>
                      {typeof executionData.variable_summary === 'string' 
                        ? executionData.variable_summary 
                        : JSON.stringify(executionData.variable_summary, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const WorkflowViewer = ({ workflowData, onExecuteStep, messageIndex, allMessages, enableExecution = true, conversationId, onMessagesUpdate, messagesVersion = 0 }) => {
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [workflowSteps, setWorkflowSteps] = useState([]);
  const [executedSteps, setExecutedSteps] = useState(new Set());
  const [startedSteps, setStartedSteps] = useState(new Set());
  const [failedSteps, setFailedSteps] = useState(new Set());
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [lastMessageCount, setLastMessageCount] = useState(0);
  const [reAnalysisTimer, setReAnalysisTimer] = useState(null);
  const [executionModal, setExecutionModal] = useState({ isOpen: false, title: '', data: null, stepName: '' });
  const [stepExecutionData, setStepExecutionData] = useState(new Map()); // Store execution data for each step
  const [lastCompletedCount, setLastCompletedCount] = useState(0); // Track completed steps for auto-execution
  const [editingSteps, setEditingSteps] = useState(new Set()); // Track which steps are being edited
  const [isSaving, setIsSaving] = useState(false); // Track if we're saving to backend
  
  // Get the workflow message ID from allMessages
  const workflowMessageId = allMessages && messageIndex !== undefined ? allMessages[messageIndex]?.id : null;

  // Analyze messages after this workflow to determine started and completed steps
  const analyzeWorkflowExecution = () => {
    if (!allMessages || !Array.isArray(allMessages) || messageIndex === undefined) {
      return { started: new Set(), completed: new Set(), failed: new Set(), executionData: new Map() };
    }

    const started = new Set();
    const completed = new Set();
    const failed = new Set();
    const executionData = new Map();
    
    // Look at messages that come after this workflow plan message
    const subsequentMessages = allMessages.slice(messageIndex + 1);
    
    // Look for workflow step markers in user messages
    workflowSteps.forEach((step, index) => {
      const stepNumber = index + 1;
      
      // Look for the step marker pattern: [WORKFLOW STEP X/Y: StepName]
      const stepMarkerPattern = new RegExp(`\\[WORKFLOW STEP ${stepNumber}/\\d+:.*?\\]`);
      
      const stepMessage = subsequentMessages.find(message => {
        if (message.role !== 'user' || !message.content) return false;
        return stepMarkerPattern.test(message.content);
      });
      
      if (stepMessage) {
        started.add(step.id);
        console.log(`✅ Found workflow step ${stepNumber} marker in message:`, stepMessage.content.substring(0, 100));
        
        // Look for assistant response after the step message
        const stepMessageIndex = subsequentMessages.indexOf(stepMessage);
        const responseMessage = subsequentMessages.slice(stepMessageIndex + 1).find(message => {
          if (message.role !== 'assistant' || message.isNodeProgress) return false;
          
          // Check if this is a substantial response (completed step)
          return (
            message.hasGeneratedCode || 
            message.generatedCode || 
            message.query || 
            message.sparqlQuery ||
            message.hasQueryResults ||
            message.hasWorkflowPlan ||
            (message.content && message.content.length > 50)
          );
        });
         
        if (responseMessage) {
          console.log(`🔍 Found response for step ${stepNumber}:`, {
            id: responseMessage.id,
            hasGeneratedCode: responseMessage.hasGeneratedCode,
            hasQueryResults: responseMessage.hasQueryResults,
            hasExecutionResults: responseMessage.executionResults?.length > 0,
            error: responseMessage.error,
            queryError: responseMessage.queryError,
            contentLength: responseMessage.content?.length || 0
          });
          
          // Extract execution data for the modal
          const stepExecutionInfo = {
            code: responseMessage.generatedCode || responseMessage.code,
            sparql: responseMessage.generatedSparql || responseMessage.sparqlQuery || responseMessage.query,
            execution_successful: false,
            execution_output: '',
            execution_error: '',
            execution_time: null,
            variable_summary: null
          };
          
          // Check execution results
          if (responseMessage.executionResults && Array.isArray(responseMessage.executionResults)) {
            const executionResult = responseMessage.executionResults.find(result => 
              result.type === 'execution_success' || result.type === 'execution_error'
            );
            
            if (executionResult) {
              stepExecutionInfo.execution_successful = executionResult.type === 'execution_success';
              stepExecutionInfo.execution_output = executionResult.output || '';
              stepExecutionInfo.execution_error = executionResult.error || '';
              stepExecutionInfo.execution_time = executionResult.execution_time;
              stepExecutionInfo.variable_summary = executionResult.variable_summary;
            }
          }
          
          // Store execution data for this step
          executionData.set(step.id, stepExecutionInfo);
          
          // Enhanced failure detection - check multiple error indicators
          const hasExplicitErrors = responseMessage.error || responseMessage.queryError;
          
          const hasExecutionErrors = responseMessage.executionResults && Array.isArray(responseMessage.executionResults) && 
                           responseMessage.executionResults.some(result => 
                             result.type === 'error' || 
                             result.status === 'error' ||
                             (result.error && result.error.trim() !== '') ||
                             (typeof result.output === 'string' && (
                               result.output.includes('Traceback') ||
                               result.output.includes('Error:') ||
                               result.output.includes('Exception:') ||
                               result.output.includes('SyntaxError') ||
                               result.output.includes('ValueError') ||
                               result.output.includes('TypeError') ||
                               result.output.includes('AttributeError') ||
                               result.output.includes('NameError') ||
                               result.output.includes('KeyError')
                             ))
                           );
          
          // Check message content for error patterns
          const hasContentErrors = responseMessage.content && (
            responseMessage.content.includes('I apologize') ||
            responseMessage.content.includes('I cannot') ||
            responseMessage.content.includes('failed to') ||
            responseMessage.content.includes('error occurred') ||
            responseMessage.content.includes('not available') ||
            responseMessage.content.includes('unable to') ||
            /sorry.{0,20}(error|issue|problem|fail)/i.test(responseMessage.content) ||
            /could not.{0,20}(execute|run|process|load|find|connect)/i.test(responseMessage.content)
          );
          
          // Check if response lacks expected success indicators
          const hasSuccessIndicators = responseMessage.hasGeneratedCode || 
                                     responseMessage.generatedCode || 
                                     responseMessage.hasQueryResults || 
                                     responseMessage.queryResults ||
                                     responseMessage.hasWorkflowPlan ||
                                     responseMessage.workflowPlan ||
                                     (responseMessage.executionResults && 
                                      responseMessage.executionResults.length > 0 &&
                                      responseMessage.executionResults.some(result => 
                                        result.type !== 'error' && 
                                        result.status !== 'error' && 
                                        !result.error
                                      ));
          
          const hasErrors = hasExplicitErrors || hasExecutionErrors || hasContentErrors;
          const lacksSucessIndicators = !hasSuccessIndicators;
          
          if (hasErrors || lacksSucessIndicators) {
            // Mark as failed if there are errors OR if lacking success indicators
            failed.add(step.id);
            console.log(`❌ Workflow step ${stepNumber} failed:`, {
              hasExplicitErrors,
              hasExecutionErrors, 
              hasContentErrors,
              lacksSucessIndicators,
              messageContent: responseMessage.content?.substring(0, 200)
            });
          } else {
            // Only mark as completed if there are no errors AND has success indicators
            completed.add(step.id);
            console.log(`✅ Workflow step ${stepNumber} completed successfully`);
          }
        } else {
          console.log(`⏳ No response found yet for step ${stepNumber} (step started but not completed)`);
        }
      }
    });

    console.log(`Workflow analysis: ${started.size} started, ${completed.size} completed, ${failed.size} failed out of ${workflowSteps.length} total steps`);
    return { started, completed, failed, executionData };
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
        
        // No need to initialize local mappings - we'll work directly with workflowSteps
        
        // Analyze execution status from messages
        const { started, completed, failed, executionData } = analyzeWorkflowExecution();
        setStartedSteps(started);
        setExecutedSteps(completed);
        setFailedSteps(failed);
        setStepExecutionData(executionData);
        
        setIsLoading(false);
      } catch (err) {
        console.error('Error parsing workflow:', err);
        setError(err.message);
        setIsLoading(false);
      }
    };

    parseWorkflow();
  }, [workflowData, allMessages, messageIndex, messagesVersion]);

  // Re-analyze when messages change
  useEffect(() => {
    if (workflowSteps.length > 0) {
      console.log(`🔍 Re-analyzing workflow execution (triggered by messages change):`, {
        totalMessages: allMessages?.length || 0,
        workflowSteps: workflowSteps.length,
        messageIndex,
        isExecuting
      });
      
      const { started, completed, failed, executionData } = analyzeWorkflowExecution();
      
      // Check if there are any changes to avoid unnecessary re-renders
      const startedChanged = started.size !== startedSteps.size || ![...started].every(x => startedSteps.has(x));
      const completedChanged = completed.size !== executedSteps.size || ![...completed].every(x => executedSteps.has(x));
      const failedChanged = failed.size !== failedSteps.size || ![...failed].every(x => failedSteps.has(x));
      
      if (startedChanged || completedChanged || failedChanged) {
        console.log(`📊 Workflow status changed:`, {
          started: `${startedSteps.size} → ${started.size}`,
          completed: `${executedSteps.size} → ${completed.size}`,
          failed: `${failedSteps.size} → ${failed.size}`
        });
        
        setStartedSteps(started);
        setExecutedSteps(completed);
        setFailedSteps(failed);
        setStepExecutionData(executionData);
        
        // Auto-execution logic: if a new step completed successfully, execute the next step
        // Only proceed if NO steps have failed and we have a new completion
        if (completed.size > lastCompletedCount && completed.size > 0 && failed.size === 0 && !isExecuting) {
          // Find the most recently completed step
          const completedStepIds = [...completed];
          const lastCompletedStepIndex = workflowSteps.findIndex(step => 
            step.id === completedStepIds[completedStepIds.length - 1]
          );
          
          // Only auto-execute if:
          // 1. We found the completed step
          // 2. There's a next step available
          // 3. No failures have occurred
          if (lastCompletedStepIndex >= 0 && lastCompletedStepIndex < workflowSteps.length - 1 && failed.size === 0) {
            const nextStepIndex = lastCompletedStepIndex + 1;
            const nextStep = workflowSteps[nextStepIndex];
            
            // Check if next step is not already started
            if (!started.has(nextStep.id)) {
              console.log(`🚀 Auto-executing next step ${nextStepIndex + 1}: ${nextStep.name} (no failures detected)`);
              
              // Delay auto-execution slightly to allow UI to update
              setTimeout(() => {
                handleExecuteFromStep(nextStepIndex);
              }, 1000);
            }
          }
        }
        
        // If any step failed, stop auto-execution and log it
        if (failed.size > 0 && failed.size > (failedSteps?.size || 0)) {
          console.log(`❌ Auto-execution halted due to ${failed.size} failed step(s)`);
        }
        
        setLastCompletedCount(completed.size);
      }
      
      // If all steps are completed, make sure execution state is reset
      if (completed.size === workflowSteps.length && isExecuting) {
        console.log('✅ All workflow steps completed, resetting execution state');
        setIsExecuting(false);
        setCurrentStep(-1);
      }
    }
  }, [allMessages, workflowSteps, messageIndex, isExecuting, messagesVersion]);

  // Cleanup execution state on unmount
  useEffect(() => {
    return () => {
      setIsExecuting(false);
      setCurrentStep(-1);
      if (reAnalysisTimer) {
        clearTimeout(reAnalysisTimer);
      }
    };
  }, [reAnalysisTimer]);

  // Force re-analysis when message count changes (to catch timing issues)
  useEffect(() => {
    const currentMessageCount = allMessages?.length || 0;
    
    if (currentMessageCount !== lastMessageCount && workflowSteps.length > 0) {
      console.log(`📨 Message count changed: ${lastMessageCount} → ${currentMessageCount}, scheduling re-analysis`);
      
      // Clear any existing timer
      if (reAnalysisTimer) {
        clearTimeout(reAnalysisTimer);
      }
      
      // Schedule a delayed re-analysis to catch any timing issues
      const timer = setTimeout(() => {
        console.log(`⏰ Delayed re-analysis triggered after message count change`);
        const { started, completed, failed } = analyzeWorkflowExecution();
        
        const startedChanged = started.size !== startedSteps.size || ![...started].every(x => startedSteps.has(x));
        const completedChanged = completed.size !== executedSteps.size || ![...completed].every(x => executedSteps.has(x));
        const failedChanged = failed.size !== failedSteps.size || ![...failed].every(x => failedSteps.has(x));
        
        if (startedChanged || completedChanged || failedChanged) {
          console.log(`🔄 Delayed analysis found changes:`, {
            started: `${startedSteps.size} → ${started.size}`,
            completed: `${executedSteps.size} → ${completed.size}`,
            failed: `${failedSteps.size} → ${failed.size}`
          });
          
          setStartedSteps(started);
          setExecutedSteps(completed);
          setFailedSteps(failed);
        }
      }, 1000); // 1 second delay to allow message processing to complete
      
      setReAnalysisTimer(timer);
      setLastMessageCount(currentMessageCount);
    }
  }, [allMessages, workflowSteps, lastMessageCount, reAnalysisTimer, startedSteps, executedSteps, failedSteps, messagesVersion]);

  // Function to check if a step completed successfully - STRICT MODE
  const checkStepSuccess = async (stepId, stepNumber) => {
    // Wait longer for messages to be updated and execution to complete
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    if (!allMessages || !Array.isArray(allMessages)) {
      console.error(`Step ${stepNumber} failed: No messages available to check step success`);
      return false;
    }

    // Find the most recent assistant message after this step was executed
    const recentAssistantMessages = allMessages
      .filter(msg => msg.role === 'assistant' && !msg.isNodeProgress)
      .sort((a, b) => new Date(b.timestamp || b.created_at || 0) - new Date(a.timestamp || a.created_at || 0));

    if (recentAssistantMessages.length === 0) {
      console.error(`Step ${stepNumber} failed: No assistant messages found to check step success`);
      return false;
    }

    const latestMessage = recentAssistantMessages[0];
    console.log(`Checking step ${stepNumber} success for message:`, {
      id: latestMessage.id,
      hasGeneratedCode: latestMessage.hasGeneratedCode,
      hasQueryResults: latestMessage.hasQueryResults,
      executionResults: latestMessage.executionResults?.length || 0,
      error: latestMessage.error,
      content: latestMessage.content?.substring(0, 100) + '...'
    });
    
    // 1. Check for explicit error indicators (HARD FAIL)
    if (latestMessage.error || latestMessage.queryError) {
      console.error(`Step ${stepNumber} FAILED: Explicit error found`, {
        error: latestMessage.error,
        queryError: latestMessage.queryError
      });
      return false;
    }

    // 2. Check execution results for errors (HARD FAIL)
    if (latestMessage.executionResults && Array.isArray(latestMessage.executionResults)) {
      const errorResults = latestMessage.executionResults.filter(result => 
        result.type === 'error' || 
        result.status === 'error' ||
        (result.error && result.error.trim() !== '')
      );
      
      if (errorResults.length > 0) {
        console.error(`Step ${stepNumber} FAILED: Execution errors found`, errorResults);
        return false;
      }
      
      // Check for Python exceptions in execution output
      const hasExceptions = latestMessage.executionResults.some(result => {
        const output = result.output || result.value || '';
        return typeof output === 'string' && (
          output.includes('Traceback') ||
          output.includes('Error:') ||
          output.includes('Exception:') ||
          output.includes('SyntaxError') ||
          output.includes('ValueError') ||
          output.includes('TypeError') ||
          output.includes('AttributeError') ||
          output.includes('NameError') ||
          output.includes('KeyError')
        );
      });
      
      if (hasExceptions) {
        console.error(`Step ${stepNumber} FAILED: Python exceptions found in execution output`);
        return false;
      }
    }

    // 3. Check message content for strong error indicators (HARD FAIL)
    if (latestMessage.content) {
      const strongErrorPatterns = [
        /traceback \(most recent call last\)/i,
        /^error:/i,
        /^exception:/i,
        /syntax error:/i,
        /name error:/i,
        /type error:/i,
        /value error:/i,
        /attribute error:/i,
        /key error:/i,
        /import error:/i,
        /module not found error:/i,
        /file not found error:/i,
        /permission error:/i,
        /connection error:/i,
        /timeout error:/i,
        /failed to execute/i,
        /execution failed/i,
        /query failed/i,
        /could not connect/i,
        /no such file/i,
        /access denied/i
      ];
      
      const hasStrongError = strongErrorPatterns.some(pattern => pattern.test(latestMessage.content));
      if (hasStrongError) {
        console.error(`Step ${stepNumber} FAILED: Strong error pattern found in content:`, latestMessage.content.substring(0, 200));
        return false;
      }
    }

    // 4. REQUIRE positive success indicators - don't assume success
    const hasCodeGeneration = latestMessage.hasGeneratedCode || latestMessage.generatedCode;
    const hasQueryResults = latestMessage.hasQueryResults || latestMessage.queryResults;
    const hasWorkflowPlan = latestMessage.hasWorkflowPlan || latestMessage.workflowPlan;
    const hasSuccessfulExecution = latestMessage.executionResults && 
      latestMessage.executionResults.length > 0 && 
      latestMessage.executionResults.some(result => 
        result.type !== 'error' && 
        result.status !== 'error' &&
        !result.error
      );

    const hasSuccessIndicators = hasCodeGeneration || hasQueryResults || hasWorkflowPlan || hasSuccessfulExecution;

    if (hasSuccessIndicators) {
      console.log(`Step ${stepNumber} SUCCESS: Positive success indicators found`, {
        hasCodeGeneration,
        hasQueryResults, 
        hasWorkflowPlan,
        hasSuccessfulExecution
      });
      return true;
    }

    // 5. If no success indicators found, this is considered a failure
    console.error(`Step ${stepNumber} FAILED: No success indicators found - agent may not have completed properly`);
    console.error(`Expected at least one of: generated code, query results, workflow plan, or successful execution results`);
    return false;
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

    try {
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
            input: step.input, // Use edited input if available
            description: step.description, // Use edited description if available
            stepName: step.name,
            stepId: step.id,
            dependencies: step.dependencies || [],
            expectedOutput: step.expected_output, // Use edited expected output if available
            allWorkflowSteps: workflowSteps
          });
          
          // Check if the step completed successfully before proceeding (only if execution is enabled)
          if (enableExecution) {
            const stepSuccess = await checkStepSuccess(step.id, originalStepIndex + 1);
            
            if (!stepSuccess) {
              console.error(`Step ${originalStepIndex + 1} failed or had errors, stopping workflow execution`);
              alert(`❌ Step ${originalStepIndex + 1} Failed: ${step.name}\n\n` +
                    `The step encountered errors or did not complete successfully.\n\n` +
                    `🔍 Check the chat messages above for:\n` +
                    `• Error messages or exceptions\n` +
                    `• Failed code execution\n` +
                    `• Missing expected outputs\n\n` +
                    `⏸️ Workflow execution stopped. Please fix the issues and resume from this step.`);
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
    } catch (error) {
      console.error('Workflow execution failed:', error);
    } finally {
      // Always reset execution state, even if there are errors
      setIsExecuting(false);
      setCurrentStep(-1);
      console.log('Workflow execution completed');
    }
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
    
    try {
      for (let i = 0; i < remainingSteps.length; i++) {
        const step = remainingSteps[i];
        const originalStepIndex = workflowSteps.indexOf(step);
        setCurrentStep(originalStepIndex);
        
        try {
          await onExecuteStep({
            stepNumber: originalStepIndex + 1,
            totalSteps: workflowSteps.length,
            agentType: step.agent,
            input: step.input, // Use edited input if available
            description: step.description, // Use edited description if available
            stepName: step.name,
            stepId: step.id,
            dependencies: step.dependencies || [],
            expectedOutput: step.expected_output, // Use edited expected output if available
            allWorkflowSteps: workflowSteps
          });
          
          // Check if the step completed successfully before proceeding (only if execution is enabled)
          if (enableExecution) {
            const stepSuccess = await checkStepSuccess(step.id, originalStepIndex + 1);
            
            if (!stepSuccess) {
              console.error(`Step ${originalStepIndex + 1} failed or had errors, stopping workflow execution`);
              alert(`❌ Step ${originalStepIndex + 1} Failed: ${step.name}\n\n` +
                    `The step encountered errors or did not complete successfully.\n\n` +
                    `🔍 Check the chat messages above for:\n` +
                    `• Error messages or exceptions\n` +
                    `• Failed code execution\n` +
                    `• Missing expected outputs\n\n` +
                    `⏸️ Workflow execution stopped. Please fix the issues and resume from this step.`);
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
    } catch (error) {
      console.error('Workflow execution failed:', error);
    } finally {
      // Always reset execution state, even if there are errors
      setIsExecuting(false);
      setCurrentStep(-1);
    }
  };

  const handleRetryStep = async (stepIndex) => {
    const step = workflowSteps[stepIndex];
    const stepNumber = stepIndex + 1;
    
    const confirmed = window.confirm(
      `Retry Step ${stepNumber}: ${step.name}?\n\n` +
      `This will:\n` +
      `• Delete the failed step execution and response messages\n` +
      `• Re-run the step from scratch\n\n` +
      `Are you sure you want to proceed?`
    );

    if (!confirmed) return;

    try {
      // Find the step marker message and its response
      const subsequentMessages = allMessages.slice(messageIndex + 1);
      const stepMarkerPattern = new RegExp(`\\[WORKFLOW STEP ${stepNumber}/\\d+:.*?\\]`);
      
      const stepMessage = subsequentMessages.find(message => {
        if (message.role !== 'user' || !message.content) return false;
        return stepMarkerPattern.test(message.content);
      });

      if (!stepMessage) {
        alert(`Cannot find the failed step message to delete. Please retry manually.`);
        return;
      }

      // Find the assistant response after the step message
      const stepMessageIndex = subsequentMessages.indexOf(stepMessage);
      const responseMessage = subsequentMessages.slice(stepMessageIndex + 1).find(message => {
        if (message.role !== 'assistant' || message.isNodeProgress) return false;
        return (
          message.hasGeneratedCode || 
          message.generatedCode || 
          message.query || 
          message.sparqlQuery ||
          message.hasQueryResults ||
          message.hasWorkflowPlan ||
          (message.content && message.content.length > 50)
        );
      });

      // Calculate the actual message index in the full conversation
      const fullStepMessageIndex = messageIndex + 1 + stepMessageIndex;
      
      // Delete messages starting from the step message
      let actualConversationId = conversationId;
      if (!actualConversationId) {
        // Try to extract from the first message as fallback
        const fallbackConversationId = allMessages?.[0]?.conversation_id;
        if (!fallbackConversationId) {
          throw new Error('Conversation ID not available - cannot delete messages. Please refresh the page and try again.');
        }
        console.warn('Using fallback conversation ID from first message');
        actualConversationId = fallbackConversationId;
      }
      
      // Use the same API base URL pattern as other parts of the app
      const apiBase = process.env.REACT_APP_API_BASE_URL || 
                     (window.location.hostname === 'localhost' ? 'http://localhost:8000' : window.location.origin);
      const deleteUrl = `${apiBase}/api/conversations/${actualConversationId}/messages/from/${fullStepMessageIndex}`;
      
      console.log(`Deleting failed step messages starting from index ${fullStepMessageIndex}`);
      const response = await fetch(deleteUrl, { method: 'DELETE' });
      
      if (!response.ok) {
        throw new Error(`Failed to delete messages: ${response.statusText}`);
      }

      console.log(`Successfully deleted failed step messages`);
      
      // Update the UI state to remove deleted messages
      if (onMessagesUpdate) {
        const updatedMessages = allMessages.slice(0, fullStepMessageIndex);
        onMessagesUpdate(updatedMessages);
        console.log(`Updated UI to remove ${allMessages.length - fullStepMessageIndex} messages from index ${fullStepMessageIndex}`);
      }
      
      // Optimistically update step status in local state so the UI reflects changes immediately
      setFailedSteps(prev => {
        if (!prev.has(step.id)) return prev;
        const newSet = new Set([...prev]);
        newSet.delete(step.id);
        return newSet;
      });
      setStartedSteps(prev => {
        if (prev.has(step.id)) return prev;
        const newSet = new Set([...prev, step.id]);
        return newSet;
      });
      setExecutedSteps(prev => {
        // Remove from executed in case it was incorrectly marked
        if (!prev.has(step.id)) return prev;
        const newSet = new Set([...prev]);
        newSet.delete(step.id);
        return newSet;
      });
      
      // Wait a moment for the state update to propagate
      await new Promise(resolve => setTimeout(resolve, 300));
      
      // Re-execute the step
      console.log(`Re-executing step ${stepNumber}: ${step.name}`);
      await onExecuteStep({
        stepNumber: stepNumber,
        totalSteps: workflowSteps.length,
        agentType: step.agent,
        input: step.input, // Use edited input if available
        description: step.description, // Use edited description if available
        stepName: step.name,
        stepId: step.id,
        dependencies: step.dependencies || [],
        expectedOutput: step.expected_output, // Use edited expected output if available
        allWorkflowSteps: workflowSteps
      });

      // After execution, verify success and automatically proceed to next step
      const success = await checkStepSuccess(step.id, stepNumber);
      if (success) {
        console.log(`✅ Step ${stepNumber} succeeded after retry – automatically executing next step if any`);
        const nextIndex = stepIndex + 1;
        if (nextIndex < workflowSteps.length) {
          await handleExecuteFromStep(nextIndex);
        } else {
          console.log('🚀 All workflow steps completed after retry sequence');
        }
      } else {
        console.warn(`❌ Step ${stepNumber} retry did not succeed – workflow halted`);
      }

    } catch (error) {
      console.error(`Failed to retry step ${stepNumber}:`, error);
      alert(`Failed to retry step: ${error.message}`);
    }
  };

  // Modal functions for execution results
  const openExecutionModal = (stepId, stepName) => {
    const executionData = stepExecutionData.get(stepId);
    if (executionData) {
      setExecutionModal({
        isOpen: true,
        title: `Step Execution: ${stepName}`,
        data: executionData,
        stepName: stepName
      });
    }
  };

  const closeExecutionModal = () => {
    setExecutionModal({ isOpen: false, title: '', data: null, stepName: '' });
  };

  // Step editing functions
  const startEditingStep = (stepId) => {
    setEditingSteps(prev => new Set([...prev, stepId]));
  };

  const stopEditingStep = (stepId) => {
    setEditingSteps(prev => {
      const newSet = new Set(prev);
      newSet.delete(stepId);
      return newSet;
    });
  };

  const updateStepField = (stepId, field, value) => {
    // Update the step in the local state immediately for responsive UI
    setWorkflowSteps(prev => prev.map(step => 
      step.id === stepId 
        ? { ...step, [field]: value }
        : step
    ));
  };

  const saveStepEdit = async (stepId) => {
    if (!workflowMessageId) {
      console.error('No workflow message ID available for saving');
      return;
    }

    setIsSaving(true);
    try {
      // Create the updated workflow JSON
      const updatedWorkflow = {
        steps: workflowSteps,
        // Include any other workflow metadata that might exist
      };

      // Update the message on the backend
      const response = await apiRequest(buildApiUrl(`/api/messages/${workflowMessageId}`), {
        method: 'PUT',
        body: JSON.stringify({
          generated_code: JSON.stringify(updatedWorkflow, null, 2)
        })
      });

      if (response.success) {
        console.log('✅ Workflow updated successfully on backend');
        
        // Update parent messages if callback provided
        if (onMessagesUpdate) {
          // Trigger a refresh of messages to get the updated workflow
          // The parent component will handle re-fetching from backend
          const updatedMessage = response.message;
          if (updatedMessage) {
            // Convert and update the specific message
            onMessagesUpdate(prev => 
              prev.map(msg => 
                msg.id === workflowMessageId 
                  ? { ...msg, generatedCode: updatedMessage.generated_code, workflowPlan: updatedMessage.generated_code }
                  : msg
              )
            );
          }
        }
        
        stopEditingStep(stepId);
      } else {
        console.error('Failed to save workflow changes:', response);
        alert('Failed to save workflow changes. Please try again.');
      }
    } catch (error) {
      console.error('Error saving workflow changes:', error);
      alert(`Failed to save workflow changes: ${error.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const cancelStepEdit = (stepId) => {
    // Revert to original workflow data by re-parsing
    try {
      let parsedWorkflow;
      if (typeof workflowData === 'string') {
        parsedWorkflow = JSON.parse(workflowData);
      } else {
        parsedWorkflow = workflowData;
      }

      if (parsedWorkflow && parsedWorkflow.steps) {
        const originalSteps = parsedWorkflow.steps.map(step => ({
          id: step.id,
          name: step.name,
          description: step.description || '',
          agent: step.agent,
          input: step.input,
          expected_output: step.expected_output || '',
          dependencies: step.dependencies || []
        }));
        
        setWorkflowSteps(originalSteps);
      }
    } catch (error) {
      console.error('Error reverting workflow changes:', error);
    }
    
    stopEditingStep(stepId);
  };

  const getStepIcon = (step) => {
    if (step.status === 'completed') {
      return <Icon name="check" className="w-4 h-4 text-green-600" />;
    }
    if (step.status === 'error') {
      return <Icon name="error" className="w-4 h-4 text-red-600" />;
    }
    if (step.status === 'running') {
      return <Icon name="spinner" className="w-4 h-4 text-blue-600 animate-spin" />;
    }
    return <Icon name="circle" className="w-4 h-4 text-neutral-400" />;
  };

  const getActionIcon = (action) => {
    switch (action.type) {
      case 'sparql_query':
        return <Icon name="database" className="w-3 h-3" />;
      case 'code_execution':
        return <Icon name="code" className="w-3 h-3" />;
      case 'data_analysis':
        return <Icon name="activity" className="w-3 h-3" />;
      default:
        return <Icon name="settings" className="w-3 h-3" />;
    }
  };

  if (error) {
    return (
      <div className="border border-neutral-200 dark:border-neutral-600 rounded-lg bg-neutral-50 dark:bg-neutral-800">
        <div className="flex justify-between items-center p-3 border-b border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 rounded-t-lg">
          <h4 className="text-neutral-800 dark:text-neutral-200 font-medium text-sm m-0 flex items-center gap-2">
            <Icon name="error" className="w-4 h-4 text-red-500" />
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
  const failedCount = failedSteps.size;
  const totalSteps = workflowSteps.length;
  const allCompleted = completedCount === totalSteps;
  const hasStarted = startedCount > 0;
  const hasFailed = failedCount > 0;

  return (
          <div className={`border ${THEME.borders.default} rounded-lg ${THEME.containers.secondary}`}>
        <div className={`flex justify-between items-center p-3 border-b ${THEME.borders.default} ${THEME.containers.card} rounded-t-lg`}>
        <h4 className={`${THEME.text.primary} font-medium text-sm m-0 flex items-center gap-2`}>
          <Icon name="play" className="w-4 h-4" />
          Workflow Plan
        </h4>
        <div className="flex gap-2">
          {onExecuteStep && !allCompleted && !hasFailed && (
            <button 
              className={`px-3 py-1 ${THEME.buttons.primary} rounded text-xs transition-colors`}
              onClick={handleExecuteStepByStep}
              title={hasStarted ? "Continue execution from next step" : "Execute workflow step by step"}
              disabled={isExecuting}
            >
              {isExecuting ? (
                <span className="flex items-center gap-1">
                  <Icon name="spinner" className="w-3 h-3 animate-spin" />
                  Running...
                </span>
              ) : hasStarted ? (
                <span className="flex items-center gap-1">
                  <Icon name="play" className="w-3 h-3" />
                  Continue
                </span>
              ) : (
                <span className="flex items-center gap-1">
                  <Icon name="play" className="w-3 h-3" />
                  Execute
                </span>
              )}
            </button>
          )}
          {hasFailed && (
            <span className={`px-3 py-1 ${THEME.status.error.background} ${THEME.status.error.text} rounded text-xs font-medium border ${THEME.status.error.border}`}>
              <span className="flex items-center gap-1">
                <Icon name="error" className="w-3 h-3" />
                {failedCount} Step{failedCount > 1 ? 's' : ''} Failed
              </span>
            </span>
          )}
          {allCompleted && (
            <span className={`px-3 py-1 ${THEME.status.success.background} ${THEME.status.success.text} rounded text-xs font-medium border ${THEME.status.success.border}`}>
              <span className="flex items-center gap-1">
                <Icon name="check" className="w-3 h-3" />
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
            <div className={`text-sm font-medium ${allCompleted ? THEME.status.success.text : hasFailed ? THEME.status.error.text : hasStarted ? THEME.status.warning.text : THEME.text.primary}`}>
              <span className="flex items-center gap-2">
                {allCompleted ? (
                  <Icon name="check" className="w-4 h-4" />
                ) : hasFailed ? (
                  <Icon name="error" className="w-4 h-4" />
                ) : hasStarted ? (
                  <Icon name="activity" className="w-4 h-4" />
                ) : (
                  <Icon name="square" className="w-4 h-4" />
                )}
                {completedCount}/{totalSteps} steps completed
                {hasFailed && (
                  <span className={`text-xs ${THEME.status.error.text}`}>
                    ({failedCount} failed)
                  </span>
                )}
              </span>
              {startedCount > completedCount + failedCount && (
                <span className={`ml-2 text-xs ${THEME.status.warning.text}`}>
                  ({startedCount - completedCount - failedCount} in progress)
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
                    allCompleted ? 'bg-emerald-500 dark:bg-emerald-600' : 
                    hasFailed ? 'bg-red-500 dark:bg-red-600' : 
                    hasStarted ? 'bg-amber-500 dark:bg-amber-600' : 
                    'bg-slate-500 dark:bg-slate-600'
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
              const isFailed = failedSteps.has(step.id);
              const isInProgress = isStarted && !isCompleted && !isFailed;
              const isCurrent = isExecuting && index === currentStep;
              const canExecuteFrom = !isStarted && onExecuteStep && !isExecuting;
              const canRetry = isFailed && onExecuteStep && !isExecuting;
              const isEditing = editingSteps.has(step.id);
              const canEdit = (!isStarted || isFailed) && !isExecuting; // Can edit steps that haven't started or have failed
              
            return (
              <div 
                key={step.id} 
                className={`p-4 rounded-lg border transition-all duration-200 ${
                  isCompleted ? `${THEME.status.success.background} border-emerald-200 dark:border-emerald-600` :
                  isFailed ? `${THEME.status.error.background} border-red-200 dark:border-red-600` :
                  isInProgress ? `${THEME.status.warning.background} border-amber-200 dark:border-amber-600` :
                  isCurrent ? `${THEME.status.warning.background} border-amber-300 dark:border-amber-600 ring-2 ring-amber-200 dark:ring-amber-600` :
                  `${THEME.containers.card} border ${THEME.borders.default} hover:border-slate-300 dark:hover:border-slate-600`
                }`}
              >
                <div className="flex items-start gap-3">
                  <span className={`rounded-full w-8 h-8 flex items-center justify-center text-sm font-medium flex-shrink-0 ${
                    isCompleted ? 'bg-emerald-500 dark:bg-emerald-600 text-white' :
                    isFailed ? 'bg-red-500 dark:bg-red-600 text-white' :
                    isInProgress ? 'bg-amber-500 dark:bg-amber-600 text-white' :
                    isCurrent ? 'bg-amber-500 dark:bg-amber-600 text-white' :
                    'bg-slate-500 dark:bg-slate-600 text-white'
                  }`}>
                    {isCompleted ? '✓' : 
                     isFailed ? '✗' :
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
                          <Icon name="check" className="w-3 h-3" />
                          Completed
                        </span>
                      )}
                      {isFailed && (
                        <span className={`text-xs ${THEME.status.error.text} font-medium flex items-center gap-1`}>
                          <Icon name="error" className="w-3 h-3" />
                          Failed
                        </span>
                      )}
                      {isInProgress && (
                        <span className={`text-xs ${THEME.status.warning.text} font-medium flex items-center gap-1`}>
                          <Icon name="spinner" className="w-3 h-3 animate-spin" />
                          In Progress
                        </span>
                      )}
                      {isCurrent && (
                        <span className={`text-xs ${THEME.status.warning.text} font-medium flex items-center gap-1`}>
                          <Icon name="play" className="w-3 h-3" />
                          Executing...
                        </span>
                      )}
                      {/* Edit button for unstarted steps */}
                      {canEdit && !isEditing && (
                        <button
                          className={`px-2 py-1 ${THEME.containers.secondary} ${THEME.text.primary} border ${THEME.borders.default} rounded text-xs transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-600`}
                          onClick={() => startEditingStep(step.id)}
                          title="Edit step description"
                        >
                          <span className="flex items-center gap-1">
                            <Icon name="edit" className="w-3 h-3" />
                            Edit
                          </span>
                        </button>
                      )}
                      {canExecuteFrom && (
                        <button
                          className={`ml-auto px-3 py-1 ${THEME.buttons.primary} rounded-full text-xs transition-colors`}
                          onClick={() => handleExecuteFromStep(index)}
                          title={`Execute workflow starting from step ${index + 1}`}
                        >
                          <span className="flex items-center gap-1">
                            <Icon name="play" className="w-3 h-3" />
                            Resume from here
                          </span>
                        </button>
                      )}
                      {canRetry && (
                        <button
                          className={`ml-auto px-3 py-1 ${THEME.status.error.background} ${THEME.status.error.text} border ${THEME.status.error.border} rounded-full text-xs transition-colors hover:opacity-80`}
                          onClick={() => handleRetryStep(index)}
                          title={`Retry step ${index + 1} - will delete failed messages and re-run`}
                        >
                          <span className="flex items-center gap-1">
                            <Icon name="refresh" className="w-3 h-3" />
                            Retry
                          </span>
                        </button>
                      )}
                      {/* Show execution output button for completed steps */}
                      {isCompleted && stepExecutionData.has(step.id) && (
                        <button
                          className={`px-3 py-1 ${THEME.status.success.background} ${THEME.status.success.text} border ${THEME.status.success.border} rounded-full text-xs transition-colors hover:opacity-80`}
                          onClick={() => openExecutionModal(step.id, step.name)}
                          title="View execution details"
                        >
                          <span className="flex items-center gap-1">
                            <Icon name="eye" className="w-3 h-3" />
                            View Output
                          </span>
                        </button>
                      )}
                      {/* Show execution output button for failed steps */}
                      {isFailed && stepExecutionData.has(step.id) && (
                        <button
                          className={`px-3 py-1 ${THEME.status.error.background} ${THEME.status.error.text} border ${THEME.status.error.border} rounded-full text-xs transition-colors hover:opacity-80`}
                          onClick={() => openExecutionModal(step.id, step.name)}
                          title="View execution error details"
                        >
                          <span className="flex items-center gap-1">
                            <Icon name="eye" className="w-3 h-3" />
                            View Error
                          </span>
                        </button>
                      )}
                    </div>
                    {/* Editable Description */}
                    {(step.description || isEditing) && (
                      <div className="mb-3">
                        {isEditing ? (
                          <div className="space-y-2">
                            <div className={`text-sm font-medium ${THEME.text.primary}`}>Description:</div>
                            <textarea
                              value={step.description || ''}
                              onChange={(e) => updateStepField(step.id, 'description', e.target.value)}
                              className={`w-full p-2 text-sm ${THEME.containers.card} border ${THEME.borders.default} rounded resize-none ${THEME.text.primary}`}
                              rows={2}
                              placeholder="Enter step description..."
                            />
                          </div>
                        ) : (
                          <p className={`text-sm ${THEME.text.secondary} m-0`}>
                            {step.description}
                          </p>
                        )}
                      </div>
                    )}
                    
                    {/* Editable Task Input */}
                    <div className={`text-xs ${THEME.text.secondary} ${THEME.containers.secondary} p-3 rounded-lg border ${THEME.borders.default} mb-3`}>
                      <div className="font-medium mb-1">Task Input:</div>
                      {isEditing ? (
                        <textarea
                          value={step.input}
                          onChange={(e) => updateStepField(step.id, 'input', e.target.value)}
                          className={`w-full p-2 text-sm ${THEME.containers.card} border ${THEME.borders.default} rounded resize-none ${THEME.text.primary}`}
                          rows={4}
                          placeholder="Enter task input..."
                        />
                      ) : (
                        <div>{step.input}</div>
                      )}
                    </div>
                    
                    {/* Editable Expected Output */}
                    {(step.expected_output || isEditing) && (
                      <div className={`text-xs ${THEME.text.secondary} ${THEME.status.info.background} p-3 rounded-lg border ${THEME.status.info.border} mb-3`}>
                        <div className="font-medium mb-1">Expected Output:</div>
                        {isEditing ? (
                          <textarea
                            value={step.expected_output || ''}
                            onChange={(e) => updateStepField(step.id, 'expected_output', e.target.value)}
                            className={`w-full p-2 text-sm ${THEME.containers.card} border ${THEME.borders.default} rounded resize-none ${THEME.text.primary}`}
                            rows={3}
                            placeholder="Enter expected output..."
                          />
                        ) : (
                          <div>{step.expected_output}</div>
                        )}
                      </div>
                    )}
                    
                    {/* Save/Cancel buttons for editing mode */}
                    {isEditing && (
                      <div className="flex gap-2 mb-3">
                        <button
                          className={`px-3 py-1 ${THEME.status.success.background} ${THEME.status.success.text} border ${THEME.status.success.border} rounded text-xs transition-colors hover:opacity-80 disabled:opacity-50 disabled:cursor-not-allowed`}
                          onClick={() => saveStepEdit(step.id)}
                          disabled={isSaving}
                        >
                          <span className="flex items-center gap-1">
                            {isSaving ? (
                              <Icon name="spinner" className="w-3 h-3 animate-spin" />
                            ) : (
                              <Icon name="check" className="w-3 h-3" />
                            )}
                            {isSaving ? 'Saving...' : 'Save Changes'}
                          </span>
                        </button>
                        <button
                          className={`px-3 py-1 ${THEME.containers.secondary} ${THEME.text.primary} border ${THEME.borders.default} rounded text-xs transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-600 disabled:opacity-50 disabled:cursor-not-allowed`}
                          onClick={() => cancelStepEdit(step.id)}
                          disabled={isSaving}
                        >
                          <span className="flex items-center gap-1">
                            <Icon name="close" className="w-3 h-3" />
                            Cancel
                          </span>
                        </button>
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
      
      {/* Execution Results Modal */}
      <WorkflowExecutionModal
        isOpen={executionModal.isOpen}
        onClose={closeExecutionModal}
        title={executionModal.title}
        executionData={executionModal.data}
        stepName={executionModal.stepName}
      />
    </div>
  );
};

export default WorkflowViewer; 