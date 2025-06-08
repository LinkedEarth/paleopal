import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import axios from 'axios';
import { AgentProgressDisplay } from './AgentProgressDisplay';
import QueryAndResultsMessage from './QueryAndResultsMessage';
import ClarificationMessage from './ClarificationMessage';
import ClarificationResponseMessage from './ClarificationResponseMessage';
import GeneratedCodeDisplay from './GeneratedCodeDisplay';
import { buildApiUrl, apiRequest } from '../config/api';

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
    description: 'Query paleoclimate databases with SPARQL',
    placeholder: 'Ask about paleoclimate data, proxies, time periods...'
  },
  { 
    id: 'code', 
    name: 'Code',
    capability: 'generate_code', 
    description: 'Generate Python code for data analysis',
    placeholder: 'Describe the analysis you want to perform...'
  },  
  { 
    id: 'workflow_generation', 
    name: 'Workflow',
    capability: 'plan_workflow', 
    description: 'Plan multi-step paleoclimate analysis workflows',
    placeholder: 'Describe the analysis workflow you want to plan...'
  }
];

// Message service utility for new API
const messageService = {
  async createMessage(conversationId, role, content, messageType = 'chat', agentType = null) {
    const url = buildApiUrl('/messages/');
    return await apiRequest(url, {
      method: 'POST',
      body: JSON.stringify({
        conversation_id: conversationId,
        role,
        content,
        message_type: messageType,
        agent_type: agentType
      })
    });
  },

  async updateMessage(messageId, updateData) {
    const url = buildApiUrl(`/messages/${messageId}`);
    return await apiRequest(url, {
      method: 'PUT',
      body: JSON.stringify(updateData)
    });
  },

  async getConversationMessages(conversationId, includeProgress = false) {
    const url = buildApiUrl(`/messages/conversation/${conversationId}?include_progress=${includeProgress}`);
    console.log(`🔍 Fetching messages from: ${url}`);
    const result = await apiRequest(url);
    console.log(`📝 Messages API response:`, result);
    return result;
  },

  async createProgressMessage(ownerMessageId, nodeName, phase, content = '', metadata = null) {
    const url = buildApiUrl('/messages/progress');
    return await apiRequest(url, {
      method: 'POST',
      body: JSON.stringify({
        owner_message_id: ownerMessageId,
        node_name: nodeName,
        phase,
        content,
        metadata
      })
    });
  }
};

// Utility function to convert backend message format to frontend format
const convertBackendMessagesToFrontend = (backendMessages) => {
  return backendMessages.map(msg => {
    const baseMessage = {
      id: msg.id,
      role: msg.role,
      content: msg.content,
      timestamp: msg.created_at,
      agentType: msg.agent_type,
      messageType: msg.message_type,
      
      // Agent results
      sparqlQuery: msg.query_generated,
      queryResults: msg.query_results,
      generatedCode: msg.query_generated,
      executionResults: msg.execution_results,
      
      // Workflow data - default mapping
      workflowPlan: msg.workflow_plan,
      workflowId: msg.workflow_id,
      failedSteps: msg.failed_steps,
      
      // Progress tracking
      isNodeProgress: msg.is_node_progress,
      ownerId: msg.owner_message_id,
      phase: msg.phase,
      nodeName: msg.node_name,
      
      // UI flags - these are crucial for special UIs!
      hasQueryResults: msg.has_query_results,
      hasGeneratedCode: msg.has_generated_code,
      hasWorkflowPlan: msg.has_workflow_plan,
      hasWorkflowExecution: msg.has_workflow_execution,
      
      // Similar results for display
      similarResults: msg.similar_results,
      entityMatches: msg.entity_matches,
      
      // Clarification
      needsClarification: msg.needs_clarification,
      clarificationQuestions: msg.clarification_questions,
      
      // Check if this is a clarification response message
      isCombinedAnswers: msg.message_type === 'clarification_response',
      
      // Metadata
      metadata: msg.metadata
    };

    // Special handling for workflow agent: JSON workflow is stored in query_generated
    if (msg.agent_type === 'workflow_generation' && msg.query_generated) {
      try {
        // Try to parse as JSON workflow
        const workflowData = JSON.parse(msg.query_generated);
        if (workflowData && workflowData.steps && Array.isArray(workflowData.steps)) {
          baseMessage.workflowPlan = msg.query_generated; // This is the JSON workflow
          baseMessage.isJsonWorkflow = true; // Flag to indicate this is JSON format
        }
      } catch (e) {
        // If not valid JSON, check if it's a Mermaid flowchart (backward compatibility)
        if (msg.query_generated.includes('flowchart')) {
          baseMessage.workflowPlan = msg.query_generated; // This is the Mermaid code
          baseMessage.isJsonWorkflow = false; // Flag to indicate this is legacy Mermaid format
        }
      }
    }

    return baseMessage;
  });
};

const ChatWindow = ({ conversation = {}, onConversationUpdate }) => {
  // Debug logging to see what conversation object we're receiving
  // console.log('💬 ChatWindow received conversation:', conversation);
  // console.log('💬 Conversation ID:', conversation.id);
  // console.log('💬 Conversation messages:', conversation.messages);
  
  // Use conversation data if provided, otherwise default greeting
  const defaultGreeting = [{
    id: 1,
    role: 'assistant',
    content: 'Hi! I can help you with paleoclimate data analysis. Choose an agent and let me know what you need!'
  }];

  const [messages, setMessages] = useState(conversation.messages?.length ? conversation.messages : defaultGreeting);
  const [inputValue, setInputValue] = useState('');
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
  const messagesContainerRef = useRef(null);
  const lastVisibleMessageCountRef = useRef(0);

  // Keep track of when we're updating from conversation prop to avoid loops
  const updatingFromPropRef = useRef(false);
  
  // Previous conversation ID to detect conversation switches
  const prevConversationIdRef = useRef(null);

  // Add refs for step execution tracking
  const stepCompletionResolver = useRef(null);
  const stepExecutionInProgress = useRef(false);
  
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
  }, [conversation.id, conversation.title, conversation.messages, messages, waitingForClarification, 
      clarificationQuestions, clarificationAnswers, originalRequestContext, llmProvider, 
      selectedAgent, isLoading, error, enableClarification, clarificationThreshold, executionStartTime]);

  // Effect to notify parent about conversation updates
  useEffect(() => {
    // Only update parent if we're not currently updating from props (avoid circular updates)
    // AND we're not in the middle of polling updates
    if (!updatingFromPropRef.current && onConversationUpdate && typeof onConversationUpdate === 'function') {
      console.log('🔄 Updating parent with conversation data');
      onConversationUpdate(conversationData);
    } else if (updatingFromPropRef.current) {
      console.log('⏸️ Skipping parent update (updating from props or polling)');
    }
  }, [conversationData, onConversationUpdate]);

  // Effect to sync with conversation prop changes (when switching conversations)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    // console.log('🔄 ChatWindow useEffect triggered!');
    // console.log('🔄 Current conversation.id:', conversation.id);
    // console.log('🔄 Previous conversation ID:', prevConversationIdRef.current);
    
    // Only sync when the conversation ID actually changes (conversation switch)
    if (conversation.id && conversation.id !== prevConversationIdRef.current) {
      console.log('✅ Conversation ID changed, loading messages...');
      updatingFromPropRef.current = true;
      
      // Load messages from the new API
      const loadMessages = async () => {
        try {
          console.log(`🔍 Loading messages for conversation ${conversation.id}...`);
          const loadedMessages = await messageService.getConversationMessages(conversation.id, true);
          console.log(`📝 Raw messages from API:`, loadedMessages);
          
          if (loadedMessages.length > 0) {
            console.log(`✅ Found ${loadedMessages.length} messages`);
            // Convert backend message format to frontend format
            const convertedMessages = convertBackendMessagesToFrontend(loadedMessages);
            console.log(`�� Converted messages:`, convertedMessages);
            setMessages(convertedMessages);
            
            // Check if we need to restore clarification state from messages
            // This handles cases where the last message is asking for clarification
            const lastAssistantMessage = convertedMessages
              .filter(msg => msg.role === 'assistant' && !msg.isNodeProgress)
              .pop(); // Get the most recent assistant message
              
            if (lastAssistantMessage && lastAssistantMessage.needsClarification && lastAssistantMessage.clarificationQuestions) {
              console.log('🔄 Detected clarification state from messages, will restore UI');
              // Set clarification state after a brief delay to ensure other state is set
              setTimeout(() => {
                setWaitingForClarification(true);
                setClarificationQuestions(lastAssistantMessage.clarificationQuestions);
                // Clear any existing answers to start fresh
                setClarificationAnswers({});
              }, 100);
            }
      } else {
            console.log('⚠️ No messages found, using default greeting');
        setMessages(defaultGreeting);
      }
        } catch (error) {
          console.error('❌ Failed to load messages:', error);
          console.error('❌ Error details:', {
            message: error.message,
            conversationId: conversation.id
          });
          setMessages(defaultGreeting);
        }
      };
      
      loadMessages();
      
      // Restore conversation state from the conversation object
      setWaitingForClarification(conversation.waiting_for_clarification || false);
      setClarificationQuestions(conversation.clarification_questions || []);
      setClarificationAnswers(conversation.clarification_answers || {});
      setOriginalRequestContext(conversation.original_request || null);
      setLlmProvider(conversation.llm_provider || 'google');
      setSelectedAgent(conversation.selected_agent || 'sparql');
      setEnableClarification(conversation.enable_clarification ?? true);
      setClarificationThreshold(conversation.clarification_threshold || 'conservative');
      setExecutionStartTime(null); // Reset execution time
      
      // Reset UI state for new conversation
      setIsLoading(false);
      setError(null);
      
      // Clear input value when switching conversations
      setInputValue('');
      
      // Update ref to track current conversation
      prevConversationIdRef.current = conversation.id;
      
      // Reset the flag after a brief delay to allow state updates to settle
      setTimeout(() => {
        updatingFromPropRef.current = false;
      }, 100);
    } else {
      // console.log('❌ Not loading messages because:');
      // console.log('  - Has conversation.id?', !!conversation.id);
      // console.log('  - ID changed?', conversation.id !== prevConversationIdRef.current);
      // console.log('  - Same as before?', conversation.id === prevConversationIdRef.current);
      // console.log('  - prevConversationIdRef.current:', prevConversationIdRef.current);
    }
  }, [conversation.id, defaultGreeting]);

  // Helper function to check if user has scrolled up
  const isUserScrolledUp = () => {
    if (!messagesContainerRef.current) return false;
    const container = messagesContainerRef.current;
    const scrolledUp = container.scrollTop < container.scrollHeight - container.clientHeight - 100;
    return scrolledUp;
  };

  // Smart scroll to bottom - only when appropriate
  const scrollToBottomIfNeeded = (force = false) => {
    if (force || !isUserScrolledUp()) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // Scroll to bottom only for meaningful message changes, not progress updates
  useEffect(() => {
    const visibleMessages = messages.filter(m => !m.isNodeProgress);
    const currentVisibleCount = visibleMessages.length;
    const lastVisibleCount = lastVisibleMessageCountRef.current;
    
    // Only auto-scroll if:
    // 1. We have new visible (non-progress) messages
    // 2. We're loading (to show loading state)
    // 3. Force scroll on conversation switch
    if (currentVisibleCount > lastVisibleCount) { // || isLoading || updatingFromPropRef.current) {
      scrollToBottomIfNeeded(updatingFromPropRef.current);
    }
    
    lastVisibleMessageCountRef.current = currentVisibleCount;
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
    setError(null);
    
    // Reset the flag after state updates complete
    setTimeout(() => {
      updatingFromPropRef.current = false;
    }, 0);
  }, []);

  // Update clarification answer for a specific question
  const handleClarificationChoice = (questionId, choice) => {
    console.log('🔄 User selected choice for question', questionId, ':', choice);
    
    // Update the local state only - do NOT update the conversation
    setClarificationAnswers(prev => ({
      ...prev,
      [questionId]: choice
    }));
    
    // Note: We no longer update the conversation here. The conversation will only
    // be updated when all answers are submitted and the backend processes them.
  };

  // Update clarification answer input
  const handleClarificationAnswerChange = (questionId, value) => {
    console.log('🔄 User entered answer for question', questionId, ':', value);
    
    // Update the local state only - do NOT update the conversation
    setClarificationAnswers(prev => ({
      ...prev,
      [questionId]: value
    }));
    
    // Note: We no longer update the conversation here. The conversation will only
    // be updated when all answers are submitted and the backend processes them.
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
        agent_type: 'workflow_generation',
        capability: 'execute_workflow',
        user_input: workflowId,
        conversation_id: conversation.id,
        context: { workflow_id: workflowId },
        metadata: {
          llm_provider: llmProvider,
          workflow_id: workflowId,
          enable_clarification: enableClarification,
          clarification_threshold: clarificationThreshold
        }
      };

      // console.log('Executing workflow:', agentRequest);

      // Send request to execute workflow via async endpoint (same as other requests)
      const requestUrl = buildApiUrl('/agents/request/async');
      const result = await apiRequest(requestUrl, {
        method: 'POST',
        body: JSON.stringify(agentRequest)
      });
        
      if (result.error) {
        throw new Error(result.error);
      }

      console.log('Workflow execution request queued:', result);

      // Start polling for new messages (same as other requests)
      startPollingForMessages(conversation.id);

    } catch (error) {
      console.error('Error executing workflow:', error);
      setError(error.response?.data?.detail || error.message || 'Error executing workflow');
      
      // Reset clarification state on error but keep conversation state
      setWaitingForClarification(false);
      setClarificationQuestions([]);
      setClarificationAnswers({});
      setOriginalRequestContext(null);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle step-by-step workflow execution
  const handleExecuteStep = async (stepInfo) => {
    try {
      console.log('Executing workflow step:', stepInfo);
      
      // Set up step execution tracking
      stepExecutionInProgress.current = true;
      
      // Create a promise that will be resolved when the step completes
      const stepCompletionPromise = new Promise((resolve, reject) => {
        stepCompletionResolver.current = resolve;
        
        // Set up a timeout
        setTimeout(() => {
          if (stepCompletionResolver.current) {
            stepCompletionResolver.current = null;
            stepExecutionInProgress.current = false;
            reject(new Error('Step execution timeout - no response received'));
          }
        }, 60000); // 60 second timeout
      });
      
      // Create a user message for this step
      const stepMessage = `Step ${stepInfo.stepNumber}/${stepInfo.totalSteps}: ${stepInfo.stepName}

📋 ${stepInfo.agentType.toUpperCase()} Agent Task:
${stepInfo.input}`;
      
      const userMessage = {
        id: `step_${Date.now()}`,
        role: 'user',
        content: stepMessage
      };
      
      // Add the step message to chat immediately
      setMessages(prev => [...prev, userMessage]);
      
      // Wait a moment for UI to update
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Submit the step input using the existing submit logic (agent type passed directly)
      console.log(`Executing step with agent: ${stepInfo.agentType}`);
      await submitRequest(stepInfo.input, conversation.id, false, stepInfo.agentType);
      
      // Wait for the step to complete
      await stepCompletionPromise;
      
      stepExecutionInProgress.current = false;
      console.log(`Step ${stepInfo.stepNumber} completed successfully`);
      
    } catch (error) {
      stepExecutionInProgress.current = false;
      stepCompletionResolver.current = null;
      console.error('Error executing step:', error);
      throw new Error(`Failed to execute step: ${error.message}`);
    }
  };

  // Update the handleSubmit to also handle clarification responses
  const submitRequest = async (userInput, conversationId, isClariSubmission = false, overrideAgentType = null) => {
    try {
      // Use override agent type if provided, otherwise use current selected agent
      const agentTypeToUse = overrideAgentType || selectedAgent;
      
      // For clarification submissions, include clarification responses in metadata
      const metadata = {
        llm_provider: llmProvider,
        enable_clarification: enableClarification,
        clarification_threshold: clarificationThreshold
      };

      if (isClariSubmission && Object.keys(clarificationAnswers).length > 0) {
        // Convert clarification answers to the format expected by the agent
        const clarificationResponses = Object.entries(clarificationAnswers).map(([questionId, answer]) => ({
          id: questionId,
          answer: answer
        }));
        metadata.clarification_responses = clarificationResponses;
        console.log('Including clarification responses:', clarificationResponses);
      } else if (!isClariSubmission) {
        // Store the original query for potential clarification requests
        setOriginalRequestContext({
          originalQuery: userInput,
          agentType: agentTypeToUse,
          timestamp: new Date().toISOString()
        });
        console.log('🔄 Stored original query for potential clarification:', userInput);
      }

      // Prepare agent request
      const agentRequest = {
        agent_type: agentTypeToUse,
        capability: AGENT_TYPES.find(a => a.id === agentTypeToUse)?.capability || 'generate_query',
        user_input: userInput,
        conversation_id: conversationId,
        context: {},
        metadata: metadata
      };

      console.log('Sending async agent request:', agentRequest);
      console.log(`📋 Using ${agentTypeToUse.toUpperCase()} agent for request:`, userInput.substring(0, 100) + '...');

      // Send async request to agent
      const requestUrl = buildApiUrl('/agents/request/async');
      const result = await apiRequest(requestUrl, {
      method: 'POST',
      body: JSON.stringify(agentRequest)
    });

      if (result.error) {
        throw new Error(result.error);
      }

      console.log('Agent request queued:', result);

      // Start polling for new messages using the correct conversation ID
      startPollingForMessages(conversationId);
      
      // If this was a clarification submission, update clarification state
      if (isClariSubmission) {
        console.log('🔄 Clearing clarification state after submission');
        setWaitingForClarification(false);
        setClarificationQuestions([]);
        setClarificationAnswers({});
        // Keep originalRequestContext until we get the final response
        // It will be cleared by the polling logic when final success is detected
        
        // Note: We no longer create a temporary clarification message here since
        // the backend now creates proper clarification response messages that will
        // appear through polling
      }

    } catch (error) {
      console.error('Error submitting request:', error);
      setError(error.message || 'Failed to send request');
      throw error;
    }
  };

  // Polling function to check for new messages
  const startPollingForMessages = (conversationId) => {
    console.log('🔄 Starting polling for conversation:', conversationId);
    console.log('🔄 Current state when polling starts:', {
      waitingForClarification,
      isLoading
    });
    let pollCount = 0;
    const maxPolls = 120; // 2 minutes with 1-second intervals
    
    const pollInterval = setInterval(async () => {
      try {
        console.log(`Polling attempt ${pollCount + 1} for conversation ${conversationId}`);
        const pollUrl = buildApiUrl(`/messages/conversation/${conversationId}?include_progress=true`);
        const newMessages = await apiRequest(pollUrl);
        console.log(`Received ${newMessages.length} messages from polling`);
        
        // Convert backend message format to frontend format
        const convertedMessages = convertBackendMessagesToFrontend(newMessages);

        // Update messages if we got new ones
        if (convertedMessages.length > messages.length) {
          console.log('Updating messages with new data', {
            oldCount: messages.length,
            newCount: convertedMessages.length,
            newMessages: convertedMessages.slice(messages.length)
          });
          
          // Set a flag to prevent conversation updates during polling
          updatingFromPropRef.current = true;
          setMessages(convertedMessages);
          
          // Check if the latest message indicates completion
          const assistantMessages = convertedMessages.filter(msg => msg.role === 'assistant' && !msg.isNodeProgress);
          const progressMessages = convertedMessages.filter(msg => msg.role === 'assistant' && msg.isNodeProgress);
          
          // Simple approach: Just check the LAST message to determine what to do
          const allMessages = [...assistantMessages, ...progressMessages];
          if (allMessages.length === 0) {
            console.log('🔍 No assistant messages found, continuing to poll...');
            return; // Continue polling
          }
          
          // Get the most recent message (by timestamp)
          const lastMessage = allMessages.reduce((latest, current) => {
            const latestTime = new Date(latest.timestamp || latest.created_at || 0);
            const currentTime = new Date(current.timestamp || current.created_at || 0);
            return currentTime > latestTime ? current : latest;
          });
          
          console.log('🔍 Checking last message for UI decisions:', {
            messageId: lastMessage.id,
            isProgress: lastMessage.isNodeProgress,
            metadata: lastMessage.metadata,
            timestamp: lastMessage.timestamp || lastMessage.created_at
          });
          
          // Parse metadata
          let metadata = lastMessage.metadata;
          if (typeof metadata === 'string') {
            try {
              metadata = JSON.parse(metadata);
            } catch (e) {
              console.warn('Failed to parse metadata for message', lastMessage.id, ':', metadata);
              metadata = {};
            }
          }
          
          // Decision logic based on last message
          const needsClarification = metadata && metadata.status === 'needs_clarification';
          const isFinalSuccess = metadata && metadata.final_response === true && (metadata.status === 'success' || metadata.status === 'error');
          
          console.log('🔍 Decision factors:', {
            needsClarification,
            isFinalSuccess,
            status: metadata?.status,
            final_response: metadata?.final_response
          });
          
          if (isFinalSuccess) {
            // Final success/error - stop polling
            console.log('🎯 Final completion detected, stopping polling');
            clearInterval(pollInterval);
            setIsLoading(false);
            setWaitingForClarification(false);
            setClarificationQuestions([]);
            setClarificationAnswers({});
            setOriginalRequestContext(null);
            
            // Resolve step completion if we're in step execution mode
            if (stepExecutionInProgress.current && stepCompletionResolver.current) {
              console.log('🎯 Resolving step completion');
              stepCompletionResolver.current();
              stepCompletionResolver.current = null;
            }
          } else if (needsClarification) {
            // Agent needs clarification - stop polling and show UI
            console.log('🔄 Clarification needed, stopping polling and showing UI');
            clearInterval(pollInterval);
            setIsLoading(false);
            
            // Find the actual clarification message (non-progress)
            const clarificationMessage = assistantMessages.find(msg => msg.needsClarification && msg.clarificationQuestions);
            if (clarificationMessage) {
              console.log('🔄 Setting up clarification UI from message:', clarificationMessage.id);
              setWaitingForClarification(true);
              setClarificationQuestions(clarificationMessage.clarificationQuestions);
              setClarificationAnswers({});
            } else {
              console.warn('⚠️ Clarification needed but no clarification message found');
            }
          } else {
            // Still processing - continue polling
            console.log('🔍 Agent still processing, continuing to poll...');
          }
          
          // Reset the flag after a brief delay
          setTimeout(() => {
            updatingFromPropRef.current = false;
          }, 100);
        }
        
        pollCount++;
        if (pollCount >= maxPolls) {
          console.log('Polling timeout reached');
          clearInterval(pollInterval);
      setIsLoading(false);
          setError('Request timeout - agent execution took too long');
        }
      } catch (error) {
        console.error('Polling request failed:', error);
        
        pollCount++;
        if (pollCount >= maxPolls) {
          console.log('Polling timeout reached');
          clearInterval(pollInterval);
          setIsLoading(false);
          setError('Request timeout - agent execution took too long');
        }
      }
    }, 1000); // Poll every second
  };

  // Render the clarification options UI
  const renderClarificationOptions = () => {
    if (!waitingForClarification) {
      return null;
    }

    // Determine if we should use compact mode (for many questions)
    const useCompactMode = true; //clarificationQuestions.length > 5;
    
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
    
    const handleKeyDown = (event, questionId) => {
      // Handle keyboard navigation
      if (event.key === 'Tab') {
        // Default tab behavior is fine
        return;
      }
      
      if (event.ctrlKey && event.key === 'Enter') {
        // Quick submit on Ctrl+Enter
        event.preventDefault();
        document.querySelector('.send-button')?.click();
      }
    };

    return (
      <div className={`p-4 bg-yellow-50 border-t border-yellow-200 ${useCompactMode ? 'text-sm' : ''}`}>
        <div className="mb-4 text-lg font-medium text-yellow-800">
          {clarificationQuestions.length > 1 
            ? `Please answer ${clarificationQuestions.length} questions to help me generate the right response:` 
            : "Please provide clarification:"}
        </div>
        
        {/* Progress indicator for multiple questions */}
        {clarificationQuestions.length > 1 && (
          <div className="mb-4 p-3 bg-white rounded border border-yellow-200">
            <div className="text-sm font-medium text-yellow-700 mb-2">
              Progress: {answeredCount} of {clarificationQuestions.length} answered
            </div>
            <div className="flex gap-2">
              {clarificationQuestions.map((question, index) => (
                <div 
                  key={question.id} 
                  className={`w-3 h-3 rounded-full ${
                    isQuestionAnswered(question.id) ? 'bg-green-500' : 
                    index === 0 ? 'bg-yellow-500' : 'bg-gray-300'
                  }`}
                  title={`Question ${index + 1}: ${isQuestionAnswered(question.id) ? 'Answered' : 'Not answered'}`}
                />
              ))}
            </div>
          </div>
        )}
        
        <div className="space-y-4 max-h-96 overflow-y-auto">
          {clarificationQuestions.map((question, index) => {
            const isAnswered = isQuestionAnswered(question.id);
            
            return (
              <div 
                key={question.id} 
                className={`border rounded-lg p-4 transition-colors ${isAnswered ? 'bg-green-50 border-green-200' : 'bg-white border-yellow-200'}`}
                data-question-id={question.id}
              >
                <div className="mb-3">
                  {clarificationQuestions.length > 1 && (
                    <div className="text-sm font-medium text-yellow-700 mb-2">
                      Question {index + 1} {isAnswered && '✓'}
                    </div>
                  )}
                  <div className="text-gray-800 font-medium mb-2">{question.question}</div>
                  {question.context && (
                    <div className="text-sm text-gray-600 p-2 bg-gray-50 rounded border">{question.context}</div>
                  )}
                </div>
                
                <div className="space-y-3">
                  {question.choices && question.choices.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-sm font-medium text-gray-700">Quick options:</div>
                      <div className="flex flex-wrap gap-2">
                        {question.choices.map((choice, choiceIndex) => {
                          // Handle both string choices and object choices
                          let choiceText;
                          let choiceValue;
                          
                          if (typeof choice === 'string') {
                            choiceText = choice;
                            choiceValue = choice;
                          } else if (choice && typeof choice === 'object') {
                            // Handle object choices with value/description or similar structure
                            choiceText = choice.description || choice.text || choice.value || JSON.stringify(choice);
                            choiceValue = choice.value || choice.description || choice.text || JSON.stringify(choice);
                          } else {
                            choiceText = String(choice);
                            choiceValue = String(choice);
                          }
                          
                          const isSelected = clarificationAnswers[question.id] === choiceValue;
                          return (
                            <button
                              key={`${question.id}-choice-${choiceIndex}`}
                              className={`px-3 py-1 rounded text-sm border transition-colors ${
                                isSelected 
                                  ? 'bg-blue-500 text-white border-blue-500' 
                                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                              }`}
                              onClick={(e) => handleChoiceClick(question.id, choiceValue, e)}
                            >
                              {choiceText}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  
                  <div className="space-y-1">
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
                      className={`w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                        isAnswered ? 'bg-green-50 border-green-300' : 'border-gray-300'
                      }`}
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
          <div className="mt-4 p-3 bg-white rounded border border-yellow-200">
            <div className="text-sm font-medium text-yellow-700 mb-2">
              {answeredCount === clarificationQuestions.length 
                ? "All questions answered! Ready to submit." 
                : `${clarificationQuestions.length - answeredCount} questions remaining`}
            </div>
            <div className="text-xs text-gray-600 mb-2">
              <small>💡 Tip: Use Tab/Shift+Tab to navigate, Ctrl+Enter to submit</small>
            </div>
            {answeredCount === clarificationQuestions.length && (
              <button 
                className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 transition-colors"
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

  // Handle deleting a specific message
  const handleDeleteMessage = async (messageIndex) => {
    // Show confirmation dialog
    const confirmDelete = window.confirm(
      `Are you sure you want to delete this message? This action cannot be undone.\n\n` +
      `Message preview: "${messages[messageIndex]?.content?.substring(0, 100)}..."`
    );
    
    if (!confirmDelete) {
      return;
    }

    try {
      const deleteUrl = buildApiUrl(`/conversations/${conversation.id}/messages/${messageIndex}`);
      await apiRequest(deleteUrl, { method: 'DELETE' });

      // Update local state directly by filtering out the deleted message
      setMessages(prev => prev.filter((_, index) => index !== messageIndex));
      
      // Refresh messages from server using proper message service to ensure special UI flags are preserved
      try {
        console.log(`🔍 Reloading messages after deletion for conversation ${conversation.id}...`);
        const loadedMessages = await messageService.getConversationMessages(conversation.id, true);
        console.log(`📝 Reloaded ${loadedMessages.length} messages after deletion`);
        
        if (loadedMessages.length > 0) {
          // Convert backend message format to frontend format (same as in useEffect)
          const convertedMessages = convertBackendMessagesToFrontend(loadedMessages);
          setMessages(convertedMessages);
        } else {
          setMessages([]);
        }
      } catch (reloadError) {
        console.error('Error reloading messages after deletion:', reloadError);
        // If reload fails, keep the local deletion
      }
    } catch (error) {
      console.error('Error deleting message:', error);
      alert('Failed to delete message. Please try again.');
    }
  };

  // Handle deleting messages from a specific index onwards
  const handleDeleteFromIndex = async (fromIndex) => {
    const numToDelete = messages.length - fromIndex;
    const confirmDelete = window.confirm(
      `Are you sure you want to delete this message and all ${numToDelete - 1} messages after it? This action cannot be undone.\n\n` +
      `This will reset the conversation to before: "${messages[fromIndex]?.content?.substring(0, 100)}..."`
    );
    
    if (!confirmDelete) {
      return;
    }

    try {
      const deleteUrl = buildApiUrl(`/conversations/${conversation.id}/messages/from/${fromIndex}`);
      await apiRequest(deleteUrl, { method: 'DELETE' });

      // Update local state directly by keeping only messages before the fromIndex
      setMessages(prev => prev.slice(0, fromIndex));
      
      // Refresh messages from server using proper message service to ensure special UI flags are preserved
      try {
        console.log(`🔍 Reloading messages after bulk deletion for conversation ${conversation.id}...`);
        const loadedMessages = await messageService.getConversationMessages(conversation.id, true);
        console.log(`📝 Reloaded ${loadedMessages.length} messages after bulk deletion`);
        
        if (loadedMessages.length > 0) {
          // Convert backend message format to frontend format (same as in useEffect)
          const convertedMessages = convertBackendMessagesToFrontend(loadedMessages);
          setMessages(convertedMessages);
        } else {
          setMessages([]);
        }
      } catch (reloadError) {
        console.error('Error reloading messages after bulk deletion:', reloadError);
        // If reload fails, keep the local deletion
      }
    } catch (error) {
      console.error('Error deleting messages:', error);
      alert('Failed to delete messages. Please try again.');
    }
  };

  // Helper to render individual chat message
  const renderChatMessage = (message, messageIndex) => {
    const baseClasses = "p-4 mb-4 rounded-lg border shadow-sm";
    const roleClasses = message.role === 'user' 
      ? "bg-blue-50 border-blue-200 text-blue-900" 
      : "bg-gray-50 border-gray-200 text-gray-900";
    const errorClasses = message.isError ? "bg-red-50 border-red-200 text-red-900" : "";
    const clarificationClasses = message.needsClarification ? "bg-yellow-50 border-yellow-200" : "";
    const responseClasses = message.isCombinedAnswers ? "bg-green-50 border-green-200" : "";
    const queryResultsClasses = (message.hasQueryResults || message.hasGeneratedCode || message.hasWorkflowPlan || message.hasWorkflowExecution) ? "bg-white border-gray-300" : "";
    const newConversationClasses = message.isNewConversation ? "bg-purple-50 border-purple-200" : "";
    
    const allClasses = [baseClasses, roleClasses, errorClasses, clarificationClasses, responseClasses, queryResultsClasses, newConversationClasses]
      .filter(Boolean)
      .join(" ");

    return (
          <div 
            key={message.id} 
        className={`${allClasses} relative group`}
      >
        {/* Delete button - only show on hover and for non-loading states */}
        {!isLoading && messageIndex > 0 && message.role === 'user' && messageIndex < messages.length - 1 && (
          <button
            onClick={() => handleDeleteFromIndex(messageIndex)}
            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 text-lg font-medium transition-all duration-200"
            title={`Delete this question and all ${messages.length - messageIndex - 1} messages after it`}
          >
            ×
          </button>
        )}
        
            {message.isCombinedAnswers ? (
              <ClarificationResponseMessage content={message.content} />
      ) : message.hasQueryResults || message.hasGeneratedCode || message.hasWorkflowPlan || message.hasWorkflowExecution ? (
              <QueryAndResultsMessage 
                message={message}
                query={message.sparqlQuery}
                results={message.queryResults}
                error={message.queryError}
                generatedCode={message.generatedCode}
                workflowPlan={message.workflowPlan}
                workflowId={message.workflowId}
                executionResults={message.executionResults}
                failedSteps={message.failedSteps}
                onExecuteWorkflow={handleExecuteWorkflow}
                onExecuteStep={handleExecuteStep}
                agentType={message.agentType}
                isJsonWorkflow={message.isJsonWorkflow}
              />
            ) : message.needsClarification && waitingForClarification ? (
              // When actively waiting for clarification, just show plain text since the interactive UI is shown below
              <div className="text-gray-800">{message.content}</div>
            ) : message.needsClarification ? (
              // When not actively waiting, show the full clarification component (historical view)
              <ClarificationMessage 
                content={message.content}
                clarificationQuestions={message.clarificationQuestions}
              />
            ) : (
          <div className="text-gray-800">{message.content}</div>
            )}
          </div>
  );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    console.log('🔄 Submit button clicked', {
      waitingForClarification,
      inputValue: inputValue.trim(),
      clarificationAnswersCount: Object.keys(clarificationAnswers).length,
      clarificationAnswers,
      isLoading
    });
    
    // For clarification submissions, allow empty input since answers come from clarification form
    // For regular submissions, require input
    if (!waitingForClarification && !inputValue.trim()) return;
    if (isLoading) return;

    // If waiting for clarification, ensure we have at least some answers
    if (waitingForClarification && Object.keys(clarificationAnswers).length === 0) {
      setError('Please provide answers to the clarification questions before submitting.');
      return;
    }

    const userInput = inputValue.trim();
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      // Create user message immediately in local state for immediate feedback
      // Only create a user message if there's actual input content
      if (userInput) {
        const tempUserMessage = {
          id: `temp_${Date.now()}`,
          role: 'user',
          content: userInput,
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, tempUserMessage]);
      }

      // Ensure we have a valid conversation ID
      let conversationId = conversation.id;
      if (!conversationId) {
        throw new Error('No conversation ID available. Please create a new conversation first.');
      }

      // Check if this is a clarification submission
      const isClariSubmission = waitingForClarification && Object.keys(clarificationAnswers).length > 0;
      
      // For clarification submissions, use the original query from context
      // For new queries, use the current input
      let finalUserInput;
      if (isClariSubmission && originalRequestContext && originalRequestContext.originalQuery) {
        finalUserInput = originalRequestContext.originalQuery;
        console.log('🔄 Using original query for clarification submission:', finalUserInput);
      } else {
        finalUserInput = userInput || "No input provided";
      }
      
      console.log('🔄 Submit request details:', {
        userInput: userInput,
        finalUserInput: finalUserInput,
        conversationId,
        isClariSubmission,
        waitingForClarification,
        clarificationAnswersCount: Object.keys(clarificationAnswers).length,
        hasOriginalContext: !!originalRequestContext,
        originalQuery: originalRequestContext?.originalQuery
      });
      
      // Submit the request
      await submitRequest(finalUserInput, conversationId, isClariSubmission);

    } catch (error) {
      console.error('Error submitting request:', error);
      setError(error.message || 'Failed to send request');
      
      // Remove the temporary user message on error (only if we created one)
      if (userInput) {
        setMessages(prev => prev.filter(msg => !msg.id.startsWith('temp_')));
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white">
      <div className="flex-shrink-0 p-4 bg-gray-50 border-b border-gray-200">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2">
            <label htmlFor="llm-provider" className="text-sm font-medium text-gray-700">LLM Provider:</label>
            <select 
              id="llm-provider" 
              value={llmProvider} 
              onChange={handleLlmProviderChange}
              className="px-3 py-1 bg-white border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {LLM_PROVIDERS.map(provider => (
                <option key={provider.id} value={provider.id}>
                  {provider.name}
                </option>
              ))}
            </select>
          </div>
      
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label htmlFor="enable-clarification" className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  id="enable-clarification"
                  type="checkbox"
                  checked={enableClarification}
                  onChange={handleEnableClarificationChange}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                Enable Clarifications
              </label>
            </div>
      
            {enableClarification && (
              <div className="flex items-center gap-2">
                <label htmlFor="clarification-threshold" className="text-sm font-medium text-gray-700">Threshold:</label>
                <select 
                  id="clarification-threshold" 
                  value={clarificationThreshold} 
                  onChange={handleClarificationThresholdChange}
                  className="px-3 py-1 bg-white border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
      
      {/* Messages area */}
      {(()=>{
        const visibleMessages = messages.filter(m=>!m.isNodeProgress);
        const getProgressForOwner = (ownerId)=>messages.filter(m=>m.isNodeProgress && m.ownerId===ownerId);
        return (
          <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={messagesContainerRef}>
            {visibleMessages.map((msg, visibleIndex) => {
              // Find the original index of this message in the full messages array
              const originalIndex = messages.findIndex(m => m.id === msg.id);
              
              const components=[renderChatMessage(msg, originalIndex)];
              if(msg.role==='user'){
                const progressMsgs=getProgressForOwner(msg.id);
                if(progressMsgs.length>0){
                  components.push(
                    <div key={`progress-${msg.id}`} className="p-4 mb-4 rounded-lg border bg-blue-50 border-blue-200">
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
      
      <form className="flex-shrink-0 p-4 bg-gray-50 border-t border-gray-200" onSubmit={handleSubmit}>
        <div className="flex gap-2">
          <select 
            value={selectedAgent} 
            onChange={handleAgentChange}
            className="px-3 py-2 bg-white border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
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
              : messages.length > 1
              ? "Ask me to refine the result or ask a new question..." 
              : AGENT_TYPES.find(agent => agent.id === selectedAgent)?.placeholder || "Enter your request..."}
            className={`flex-1 px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed ${
              waitingForClarification ? 'bg-yellow-50 border-yellow-300' : 'bg-white border-gray-300'
            }`}
          disabled={isLoading}
        />
        <button 
          type="submit" 
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          disabled={isLoading}
        >
          {isLoading ? 'Generating...' : waitingForClarification ? 'Submit Answers' : 'Send'}
        </button>
        </div>
      </form>
    </div>
  );
};

export default ChatWindow; 