import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import axios from 'axios';
import './ChatWindow.css';
import { AgentProgressDisplay } from './AgentProgressDisplay';
import QueryAndResultsMessage from './QueryAndResultsMessage';
import ClarificationMessage from './ClarificationMessage';
import ClarificationResponseMessage from './ClarificationResponseMessage';
import { parseClarificationQuestions } from '../utils/parse';

const LLM_PROVIDERS = [
  { id: 'openai', name: 'OpenAI' },  
  { id: 'google', name: 'Google' },  
  { id: 'anthropic', name: 'Anthropic' },
  { id: 'grok', name: 'XAI Grok' },
  { id: 'ollama', name: 'Ollama' }
];

const AGENT_TYPES = [
  { 
    id: 'sparql', 
    name: 'SPARQL',
    capability: 'generate_query',
    description: 'Generate SPARQL queries for paleoclimate data',
    placeholder: 'Ask a question to generate a SPARQL query...'
  },
  { 
    id: 'code', 
    name: 'Code',
    capability: 'generate_code', 
    description: 'Generate Python code for data analysis',
    placeholder: 'Describe the analysis you want to perform...'
  },  
  { 
    id: 'workflow_manager', 
    name: 'Workflow',
    capability: 'plan_workflow', 
    description: 'Plan multi-step paleoclimate analysis workflows',
    placeholder: 'Describe the analysis workflow you want to plan...'
  }
];


const ChatWindow = ({ conversation = {}, onConversationUpdate }) => {
  // Use conversation data if provided, otherwise default greeting
  const defaultGreeting = [{
    id: 1,
    role: 'assistant',
    content: 'Hi! I can help you with paleoclimate data analysis. Choose an agent and let me know what you need!'
  }];

  const [messages, setMessages] = useState(conversation.messages?.length ? conversation.messages : defaultGreeting);
  const [inputValue, setInputValue] = useState('');
  const [stateId, setStateId] = useState(conversation.stateId || null);
  const [waitingForClarification, setWaitingForClarification] = useState(conversation.waitingForClarification || false);
  const [clarificationQuestions, setClarificationQuestions] = useState(conversation.clarificationQuestions || []);
  const [llmProvider, setLlmProvider] = useState(conversation.llmProvider || 'google');
  const [selectedAgent, setSelectedAgent] = useState(conversation.selectedAgent || 'sparql');
  const [isLoading, setIsLoading] = useState(conversation.isLoading || false);
  const [error, setError] = useState(conversation.error || null);
  // Track answers to clarification questions
  const [clarificationAnswers, setClarificationAnswers] = useState(conversation.clarificationAnswers || {});
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
    // console.log('creating conversation title from messages for conversation', conversation.id)
    // console.log('current conversation.title', conversation.title)
    // console.log('local messages state', messages)
    // console.log('conversation.messages prop', conversation.messages)
    
    // Use local messages state for title calculation when we're actively working on this conversation
    // Use conversation.messages only when switching conversations (to avoid stale local state)
    // The key insight: if conversation.messages length doesn't match local messages length,
    // we're likely in the middle of an update and should trust local state
    const conversationId = conversation.id;
    const isActivelySameConversation = conversationId === prevConversationIdRef.current;
    const hasLocalChanges = messages.length !== (conversation.messages?.length || 0);
    
    let messagesToUseForTitle;
    if (isActivelySameConversation && hasLocalChanges) {
      // We're actively updating this conversation, use local state
      messagesToUseForTitle = messages;
      // console.log('Using local messages for title (active conversation with changes)');
    } else {
      // We're switching conversations or no local changes, use prop
      messagesToUseForTitle = conversation.messages?.length ? conversation.messages : [];
      // console.log('Using conversation.messages prop for title (conversation switch or no changes)');
    }
    
    const firstUserMsg = messagesToUseForTitle.find((m) => m.role === 'user');
    
    // Only auto-generate title from first user message if current title is still the default
    const title = firstUserMsg && conversation.title === 'New Chat' 
      ? firstUserMsg.content.slice(0, 50) 
      : conversation.title || 'New Chat';

    // console.log('new title', title)

    return {
      id: conversation.id,
      title,
      messages, // Still use local messages state for UI rendering (real-time updates)
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
  }, [conversation.id, conversation.title, conversation.messages, messages, stateId, waitingForClarification, 
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
      setSelectedAgent(conversation.selectedAgent || 'sparql');
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

      // console.log('Executing workflow:', agentRequest);

      // Send request to execute workflow
      const response = await axios.post('/agents/request', agentRequest);
      const data = response.data;

      // console.log('Workflow execution response:', data);

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
          // console.log('Agent execution started:', data.message);
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
          // Different agent => new conversation, except for workflow_manager
          // Workflow plans should always be associated with the current conversation
          if (agentType === 'workflow_manager') {
            // For workflow manager, use the conversation.id to maintain association
            conversationIdForRequest = conversation.id || stateId;
          } else {
            conversationIdForRequest = null;
          }
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
      } else if (agentType === 'workflow_manager') {
        // Even if no previous message, workflow plans should be associated with the conversation
        conversationIdForRequest = conversation.id || stateId;
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
      
      // console.log('Sending agent request:', agentRequest);
      
      // Send request via streaming endpoint so we can show progress
      const data = await streamAgentRequest(agentRequest, userMessageId);
      
      // Update conversation ID from successful response so future requests are treated as refinements
        if (data.conversation_id) {
          setStateId(data.conversation_id);
        }
        
      // if backend wrapped useful fields under .result, unwrap
      const effectiveData = data.result ? { ...data, ...data.result } : data;
        
        // console.log('Processing success response:', {
        // generatedContent: !!effectiveData.generated_code,
        // generatedContentLength: effectiveData.generated_code?.length,
        // queryResults: !!data.execution_results,
        // queryResultsLength: data.execution_results?.length,
        // queryError: !!data.error,
        // executionInfo: !!data.execution_info,
        // workflowPlan: !!data.workflow_plan,
        // workflowId: !!data.workflow_id,
        // executionResults: !!data.execution_results,
        // failedSteps: !!data.failed_steps,
        //   selectedAgent,
        //   fullData: data
        // });
        
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
        <div className="input-with-agent">
          <select 
            value={selectedAgent} 
            onChange={handleAgentChange}
            className="compact-agent-select"
            disabled={isLoading}
          >
            {AGENT_TYPES.map(agent => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
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
        </div>
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