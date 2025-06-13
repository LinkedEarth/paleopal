import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import axios from 'axios';
import { AgentProgressDisplay } from './AgentProgressDisplay';
import QueryAndResultsMessage from './QueryAndResultsMessage';
import ClarificationMessage from './ClarificationMessage';
import ClarificationResponseMessage from './ClarificationResponseMessage';
import ClarificationDialog from './ClarificationDialog';
import GeneratedCodeDisplay from './GeneratedCodeDisplay';
import { buildApiUrl, apiRequest } from '../config/api';
import API_CONFIG from '../config/api';

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
    const url = buildApiUrl(`${API_CONFIG.ENDPOINTS.MESSAGES}/`);
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
    const url = buildApiUrl(`${API_CONFIG.ENDPOINTS.MESSAGES}/${messageId}`);
    return await apiRequest(url, {
      method: 'PUT',
      body: JSON.stringify(updateData)
    });
  },

  async getConversationMessages(conversationId, includeProgress = false) {
    const url = buildApiUrl(`${API_CONFIG.ENDPOINTS.MESSAGES}/conversation/${conversationId}?include_progress=${includeProgress}`);
    // console.log(`🔍 Fetching messages from: ${url}`);
    const result = await apiRequest(url);
    // console.log(`📝 Messages API response:`, result);
    return result;
  },

  async createProgressMessage(ownerMessageId, nodeName, phase, content = '', metadata = null) {
    const url = buildApiUrl(`${API_CONFIG.ENDPOINTS.MESSAGES}/progress`);
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
      clarificationResponses: msg.clarification_responses,
      
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

const ChatWindow = ({ conversation = {}, onConversationUpdate, isDarkMode = false }) => {
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
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [deletingMessages, setDeletingMessages] = useState(new Set());
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
  
  // Clarification dialog state
  const [showClarificationDialog, setShowClarificationDialog] = useState(false);
  const [clarificationDialogData, setClarificationDialogData] = useState(null);
  const [isSubmittingClarification, setIsSubmittingClarification] = useState(false);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const lastVisibleMessageCountRef = useRef(0);

  // Keep track of when we're updating from conversation prop to avoid loops
  const updatingFromPropRef = useRef(false);
  
  // Previous conversation ID to detect conversation switches
  const prevConversationIdRef = useRef(null);
  
  // Track when conversation updates should be allowed


  // Add refs for step execution tracking
  const stepCompletionResolver = useRef(null);
  const stepExecutionInProgress = useRef(false);
  
  // Memoize conversation data to prevent unnecessary updates
  const conversationData = useMemo(() => {
    // Simple title logic - just use the conversation title as-is
    const title = conversation.title || 'New Chat';

    return {
      id: conversation.id,
      title,
      messages: messages, // Use local messages for UI rendering but don't trigger updates on message loading
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
  }, [conversation.id, conversation.title, conversation.messages, waitingForClarification, 
      clarificationQuestions, clarificationAnswers, originalRequestContext, llmProvider, 
      selectedAgent, isLoading, error, enableClarification, clarificationThreshold, executionStartTime]);

  // Helper function to update parent conversation (only call on user actions)
  const updateParentConversation = useCallback(() => {
    if (onConversationUpdate && typeof onConversationUpdate === 'function') {
      onConversationUpdate({...conversationData, messages});
    }
  }, [conversationData, messages, onConversationUpdate]);

  // Effect to sync with conversation prop changes (when switching conversations)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    // console.log('🔄 ChatWindow useEffect triggered!');
    // console.log('🔄 Current conversation.id:', conversation.id);
    // console.log('🔄 Previous conversation ID:', prevConversationIdRef.current);
    
    // Only sync when the conversation ID actually changes (conversation switch)
    if (conversation.id && conversation.id !== prevConversationIdRef.current) {
      // console.log('✅ Conversation ID changed, loading messages...');
      updatingFromPropRef.current = true;
      
      // Load messages from the new API
      const loadMessages = async () => {
        setMessagesLoading(true);
        try {
          // console.log(`🔍 Loading messages for conversation ${conversation.id}...`);
          const loadedMessages = await messageService.getConversationMessages(conversation.id, true);
          // console.log(`📝 Raw messages from API:`, loadedMessages);
          
          if (loadedMessages.length > 0) {
            // console.log(`✅ Found ${loadedMessages.length} messages`);
            // Convert backend message format to frontend format
            const convertedMessages = convertBackendMessagesToFrontend(loadedMessages);
            // console.log(` Converted messages:`, convertedMessages);
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
        } finally {
          setMessagesLoading(false);
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
      
      // Reset the flag after state updates complete
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
    if (currentVisibleCount > lastVisibleCount || isLoading || updatingFromPropRef.current) {
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
    // Update parent after state change
    setTimeout(() => updateParentConversation(), 0);
  };

  const handleEnableClarificationChange = (e) => {
    setEnableClarification(e.target.checked);
    // Update parent after state change
    setTimeout(() => updateParentConversation(), 0);
  };

  const handleClarificationThresholdChange = (e) => {
    setClarificationThreshold(e.target.value);
    // Update parent after state change
    setTimeout(() => updateParentConversation(), 0);
  };

  const handleAgentChange = useCallback((e) => {
    const newAgent = e.target.value;
    
    setSelectedAgent(newAgent);
    // Reset conversation state when switching agents
    setError(null);
    
    // Update parent after state change
    setTimeout(() => updateParentConversation(), 0);
  }, [updateParentConversation]);

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
      const requestUrl = buildApiUrl(`${API_CONFIG.ENDPOINTS.AGENTS}/request/async`);
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
        
        // If the step takes too long (default 5 minutes), reject to avoid indefinite hanging
        setTimeout(() => {
          if (stepCompletionResolver.current) {
            stepCompletionResolver.current = null;
            stepExecutionInProgress.current = false;
            reject(new Error('Step execution timeout (5 min) – no response received'));
          }
        }, 300000); // 5-minute timeout
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
  const submitRequest = async (userInput, conversationId, isClariSubmission = false, overrideAgentType = null, clarificationResponses = null) => {
    try {
      // Use override agent type if provided, otherwise use current selected agent
      const agentTypeToUse = overrideAgentType || selectedAgent;
      
      // For clarification submissions, include clarification responses in metadata
      const metadata = {
        llm_provider: llmProvider,
        enable_clarification: enableClarification,
        clarification_threshold: clarificationThreshold
      };

      if (isClariSubmission && clarificationResponses) {
        // Use the structured clarification responses passed from the dialog
        metadata.clarification_responses = clarificationResponses;
        console.log('Including structured clarification responses:', clarificationResponses);
      } else if (isClariSubmission && Object.keys(clarificationAnswers).length > 0) {
        // Fallback: Convert old format clarification answers to the format expected by the agent
        const legacyClarificationResponses = Object.entries(clarificationAnswers).map(([questionId, answer]) => ({
          id: questionId,
          answer: answer
        }));
        metadata.clarification_responses = legacyClarificationResponses;
        console.log('Including legacy clarification responses:', legacyClarificationResponses);
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
        user_input: isClariSubmission ? "" : userInput, // For clarification, send empty user_input - backend will retrieve original from conversation history
        conversation_id: conversationId,
        context: {},
        metadata: metadata
      };

      console.log('Sending async agent request:', agentRequest);
      console.log(`📋 Using ${agentTypeToUse.toUpperCase()} agent for request:`, userInput.substring(0, 100) + '...');

      // Send async request to agent
      const requestUrl = buildApiUrl(`${API_CONFIG.ENDPOINTS.AGENTS}/request/async`);
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
    const maxPolls = 300; // 5 minutes with 1-second intervals
    const pollIntervalSeconds = 2; // 2 seconds
    
    const pollInterval = setInterval(async () => {
      try {
        console.log(`Polling attempt ${pollCount + 1} for conversation ${conversationId}`);
        const pollUrl = buildApiUrl(`${API_CONFIG.ENDPOINTS.MESSAGES}/conversation/${conversationId}?include_progress=true`);
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
          
          // Clean up any temporary loading messages since we got actual responses
          const cleanedMessages = convertedMessages.filter(msg => !msg.id.startsWith('loading_'));
          
          // For user messages that don't have agentType from backend, try to preserve it from our local state
          const messagesWithAgentType = cleanedMessages.map(msg => {
            if (msg.role === 'user' && !msg.agentType) {
              // Find the corresponding temp message in our current state to get the agentType
              const tempMsg = messages.find(m => m.content === msg.content && m.role === 'user' && m.agentType);
              if (tempMsg && tempMsg.agentType) {
                return { ...msg, agentType: tempMsg.agentType };
              }
            }
            return msg;
          });
          
          setMessages(messagesWithAgentType);
          
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
          
          // Check if we have any recent assistant messages with actual results (not just progress)
          // Only consider messages that come after the current polling session started
          const currentUserMessageCount = convertedMessages.filter(msg => msg.role === 'user').length;
          const recentAssistantMessage = assistantMessages
            .filter(msg => !msg.isNodeProgress && msg.role === 'assistant')
            .sort((a, b) => new Date(b.timestamp || b.created_at || 0) - new Date(a.timestamp || a.created_at || 0))
            .find(msg => {
              // Find this message's position in the convertedMessages array
              const messageIndex = convertedMessages.findIndex(m => m.id === msg.id);
              // Only consider messages that come after the latest user message
              const lastUserMessageIndex = convertedMessages.map((m, i) => m.role === 'user' ? i : -1).filter(i => i >= 0).pop() || -1;
              return messageIndex > lastUserMessageIndex;
            });
          
          // Decision logic based on last message
          const needsClarification = metadata && metadata.status === 'needs_clarification' && metadata.final_response !== true;
          
          // Also check for any assistant message that has needsClarification flag (from message conversion)
          // But only count clarification messages that don't have subsequent responses
          const hasClarificationMessage = assistantMessages.some((msg, index) => {
            // Find the actual index in the full messages array
            const messageIndex = convertedMessages.findIndex(m => m.id === msg.id);
            
            // Check for subsequent clarification responses in the convertedMessages array
            const hasSubsequent = messageIndex >= 0 ? 
              convertedMessages.slice(messageIndex + 1).some(m => 
                m.isCombinedAnswers || m.messageType === 'clarification_response'
              ) : false;
            
            return msg.needsClarification && 
                   msg.clarificationQuestions && 
                   messageIndex >= 0 && 
                   !hasSubsequent;
          });
          
          // Only check for final success on NON-progress messages (progress messages can have final_response=true but aren't actual completion)
          const isFinalSuccess = !lastMessage.isNodeProgress && metadata && metadata.final_response === true && (metadata.status === 'success' || metadata.status === 'error');
          
          // Also check if we have an assistant message with query results or generated content (indicates completion)
          const hasCompletionMessage = recentAssistantMessage && (
            recentAssistantMessage.hasQueryResults || 
            recentAssistantMessage.hasGeneratedCode || 
            recentAssistantMessage.hasWorkflowPlan ||
            recentAssistantMessage.hasWorkflowExecution
          );
          
          console.log('🔍 Decision factors:', {
            needsClarification,
            hasClarificationMessage,
            isFinalSuccess,
            hasCompletionMessage,
            status: metadata?.status,
            final_response: metadata?.final_response,
            recentAssistantMessageId: recentAssistantMessage?.id
          });
          
          if (isFinalSuccess || hasCompletionMessage) {
            // Final success/error or we have actual results - stop polling
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
          } else if (needsClarification || hasClarificationMessage) {
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
    }, pollIntervalSeconds * 1000); // Poll every second
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

    // Set loading state for bulk deletion using a special key
    setDeletingMessages(prev => new Set([...prev, `bulk_${fromIndex}`]));

    try {
      const deleteUrl = buildApiUrl(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/${conversation.id}/messages/from/${fromIndex}`);
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
    } finally {
      // Remove loading state
      setDeletingMessages(prev => {
        const newSet = new Set(prev);
        newSet.delete(`bulk_${fromIndex}`);
        return newSet;
      });
    }
  };

  // Helper function to check if a clarification message has subsequent responses
  const hasSubsequentClarificationResponse = (messageIndex) => {
    // Look for any clarification response message after this one
    for (let i = messageIndex + 1; i < messages.length; i++) {
      if (messages[i].isCombinedAnswers || messages[i].messageType === 'clarification_response') {
        return true;
      }
    }
    return false;
  };

  // Handler to open clarification dialog
  const handleAnswerQuestions = (message) => {
    setClarificationDialogData({
      messageId: message.id,
      questions: message.clarificationQuestions,
      originalQuery: message.content
    });
    setShowClarificationDialog(true);
  };

  // Handler to submit clarification answers via dialog
  const handleClarificationSubmit = async (clarificationResponses) => {
    if (!clarificationDialogData) return;

    setIsSubmittingClarification(true);
    
    try {
      // Set loading state to show progress during execution
      setIsLoading(true);
      
      // Add a temporary loading indicator assistant message so the user sees immediate feedback
      const loadingMessage = {
        id: `loading_${Date.now()}`,
        role: 'assistant',
        content: '',
        isLoading: true,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, loadingMessage]);
      
      // Submit clarification responses using the new structured format
      // The submitRequest will automatically use the originalRequestContext.originalQuery for clarification submissions
      const response = await submitRequest(
        "", // Empty userInput - submitRequest will use originalRequestContext.originalQuery
        conversation.id,
        true, // isClariSubmission
        selectedAgent,
        clarificationResponses // Pass the structured responses directly
      );

      // Close dialog on success
      setShowClarificationDialog(false);
      setClarificationDialogData(null);
      setWaitingForClarification(false);
      setClarificationQuestions([]);
      setClarificationAnswers({});
      setOriginalRequestContext(null);
      
      // Note: isLoading will be cleared by the polling logic when completion is detected
      
    } catch (error) {
      console.error('❌ Failed to submit clarification:', error);
      setError(`Failed to submit clarification: ${error.message || 'Unknown error'}`);
      // Clear loading state on error
      setIsLoading(false);
    } finally {
      setIsSubmittingClarification(false);
    }
  };

  // Helper to check if there are unanswered clarification questions in current messages
  const hasUnansweredClarificationQuestions = () => {
    return messages.some(msg => 
      msg.needsClarification && 
      msg.clarificationQuestions && 
      msg.clarificationQuestions.length > 0 &&
      !hasSubsequentClarificationResponse(messages.indexOf(msg))
    );
  };

  // Helper to render individual chat message
  const renderChatMessage = (message, messageIndex) => {
    const baseClasses = "p-4 mb-4 rounded-lg border shadow-sm max-w-[90%]";
    const roleClasses = message.role === 'user' 
      ? "bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800/30 text-neutral-900 dark:text-neutral-100" 
      : "bg-neutral-50 dark:bg-neutral-700 border-neutral-200 dark:border-neutral-600 text-neutral-900 dark:text-neutral-100";
    const errorClasses = message.isError ? "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-700 text-red-900 dark:text-red-100" : "";
    const queryResultsClasses = (message.hasQueryResults || message.hasGeneratedCode || message.hasWorkflowPlan || message.hasWorkflowExecution) ? "bg-white dark:bg-neutral-800 border-neutral-300 dark:border-neutral-600" : "";
    const newConversationClasses = message.isNewConversation ? "bg-neutral-100 dark:bg-neutral-600 border-neutral-200 dark:border-neutral-500" : "";
    
    // Check if this message or any subsequent messages are being deleted
    const isBeingDeleted = deletingMessages.has(`bulk_${messageIndex}`);
    // Check if this message will be deleted as part of a bulk deletion from an earlier message
    const willBeDeleted = Array.from(deletingMessages).some(key => {
      if (key.startsWith('bulk_')) {
        const deletionStartIndex = parseInt(key.replace('bulk_', ''));
        return messageIndex >= deletionStartIndex;
      }
      return false;
    });
    const deletingClasses = (isBeingDeleted || willBeDeleted) ? "opacity-50 pointer-events-none" : "";
    
    const allClasses = [baseClasses, roleClasses, errorClasses, queryResultsClasses, newConversationClasses, deletingClasses]
      .filter(Boolean)
      .join(" ");

    const wrapperClass = message.role === 'user' ? 'flex justify-end' : 'flex justify-start';
    const deleteBtnPos = message.role === 'user' ? 'right-2' : 'left-2';

    return (
      <div key={message.id} className={`${wrapperClass} group`}>
        <div 
          className={`${allClasses} relative transition-all duration-300`}
        >
          {/* Deletion overlay */}
          {(isBeingDeleted || willBeDeleted) && (
            <div className="absolute inset-0 bg-red-100 dark:bg-red-900/50 bg-opacity-75 rounded-lg flex items-center justify-center">
              <div className="flex items-center gap-2 bg-white dark:bg-neutral-800 px-3 py-2 rounded-lg shadow-md">
                <svg className="w-4 h-4 animate-spin text-red-500 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-sm font-medium text-red-700 dark:text-red-300">
                  {isBeingDeleted ? 'Deleting messages...' : 'Will be deleted...'}
                </span>
              </div>
            </div>
          )}

          {/* Delete button - only show on hover and for non-loading states */}
          {!isLoading && message.role === 'user' && messageIndex < messages.length - 1 && (
            <button
              onClick={() => !deletingMessages.has(`bulk_${messageIndex}`) && handleDeleteFromIndex(messageIndex)}
              disabled={deletingMessages.has(`bulk_${messageIndex}`)}
              className={`absolute -bottom-5 ${deleteBtnPos} w-7 h-7 rounded-md flex items-center justify-center transition-opacity transition-colors duration-200 ${
                deletingMessages.has(`bulk_${messageIndex}`)
                  ? 'opacity-100 bg-red-200 dark:bg-red-900/30 text-red-400 dark:text-red-500 cursor-not-allowed'
                  : 'opacity-0 group-hover:opacity-100 bg-red-100 dark:bg-red-900/20 hover:bg-red-200 dark:hover:bg-red-900/40 text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300'
              }`}
              title={deletingMessages.has(`bulk_${messageIndex}`) 
                ? 'Deleting messages...' 
                : `Delete this question and all ${messages.length - messageIndex - 1} messages after it`}
            >
              {deletingMessages.has(`bulk_${messageIndex}`) ? (
                <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              )}
            </button>
          )}
          
          {message.isCombinedAnswers ? (
            <ClarificationResponseMessage 
              content={message.content} 
              clarificationResponses={message.clarificationResponses}
            />
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
              messageIndex={messageIndex}
              allMessages={messages}
              isDarkMode={isDarkMode}
            />
          ) : message.needsClarification ? (
            // Show clarification questions - use main form button to answer
            <ClarificationMessage 
              content={message.content}
              clarificationQuestions={message.clarificationQuestions}
              hasSubsequentResponse={hasSubsequentClarificationResponse(messageIndex)}
              onAnswerQuestions={() => handleAnswerQuestions(message)}
            />
          ) : message.isLoading ? (
            <div className="flex items-center gap-3 text-neutral-600 dark:text-neutral-300">
              <svg className="w-5 h-5 animate-spin text-neutral-500 dark:text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm">Sending request...</span>
            </div>
          ) : (
            <div>
              {/* Show role indicator and content */}
              <div className="flex items-start gap-3">
                {/* Role indicator */}
                <div className="flex-shrink-0 mt-1">
                  {message.role === 'user' ? (
                    <div className="w-6 h-6 bg-blue-100 dark:bg-blue-800/30 border border-blue-200 dark:border-blue-700/50 rounded-full flex items-center justify-center">
                      <svg className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                    </div>
                  ) : (
                    <div className="w-6 h-6 bg-neutral-100 dark:bg-neutral-600 border border-neutral-200 dark:border-neutral-500 rounded-full flex items-center justify-center">
                      <svg className="w-3.5 h-3.5 text-neutral-600 dark:text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                      </svg>
                    </div>
                  )}
                </div>
                
                {/* Content area with agent badge for user messages */}
                <div className="flex-1 min-w-0">
                  {message.role === 'user' && message.agentType && (
                    <div className="mb-2">
                      <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 dark:bg-blue-800/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700/50">
                        {AGENT_TYPES.find(agent => agent.id === message.agentType)?.name || message.agentType}
                      </span>
                    </div>
                  )}
                  <div className="text-neutral-800 dark:text-neutral-200">{message.content}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Check if there are unanswered clarification questions
    if (hasUnansweredClarificationQuestions()) {
      // Find the first unanswered clarification message and open dialog
      const unansweredMessage = messages.find(msg => 
        msg.needsClarification && 
        msg.clarificationQuestions && 
        msg.clarificationQuestions.length > 0 &&
        !hasSubsequentClarificationResponse(messages.indexOf(msg))
      );
      
      if (unansweredMessage) {
        handleAnswerQuestions(unansweredMessage);
      }
      return;
    }
    
    console.log('🔄 Submit button clicked', {
      waitingForClarification,
      inputValue: inputValue.trim(),
      clarificationAnswersCount: Object.keys(clarificationAnswers).length,
      clarificationAnswers,
      isLoading
    });
    
    // For regular submissions, require input
    if (!inputValue.trim()) return;
    if (isLoading) return;



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
          timestamp: new Date().toISOString(),
          agentType: selectedAgent // Store which agent this message was sent to
        };
        
        // Add a loading indicator message that appears while request is being sent
        const loadingMessage = {
          id: `loading_${Date.now()}`,
          role: 'assistant',
          content: '',
          timestamp: new Date().toISOString(),
          isLoading: true
        };
        
        setMessages(prev => [...prev, tempUserMessage, loadingMessage]);
      }

      // Ensure we have a valid conversation ID
      let conversationId = conversation.id;
      if (!conversationId) {
        throw new Error('No conversation ID available. Please create a new conversation first.');
      }

      // No longer handle clarification submissions here - they go through the dialog
      
      console.log('🔄 Submit request details:', {
        userInput: userInput,
        conversationId
      });
      
      // Submit the request
      await submitRequest(userInput, conversationId, false);
      
      // Update conversation title if it's still the default and this is a new user message
      if (userInput && (conversation.title === 'New Chat' || conversation.title === 'Untitled' || !conversation.title)) {
        // Update the conversation data with the new title
        const updatedConversationData = {
          ...conversationData,
          title: userInput.slice(0, 50) // Limit title length
        };
        
        // Directly call parent update with the new title
        if (onConversationUpdate && typeof onConversationUpdate === 'function') {
          onConversationUpdate({...updatedConversationData, messages});
        }
      } else {
        // Regular parent update for message addition
        setTimeout(() => updateParentConversation(), 0);
      }

    } catch (error) {
      console.error('Error submitting request:', error);
      setError(error.message || 'Failed to send request');
      
      // Remove the temporary user message and loading message on error (only if we created one)
      if (userInput) {
        setMessages(prev => prev.filter(msg => !msg.id.startsWith('temp_') && !msg.id.startsWith('loading_')));
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-neutral-800">
      <div className="flex-shrink-0 p-4 bg-neutral-100 dark:bg-neutral-700 border-b border-neutral-200 dark:border-neutral-600">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2">
            <label htmlFor="llm-provider" className="text-sm font-medium text-neutral-700 dark:text-neutral-200">LLM Provider:</label>
            <select 
              id="llm-provider" 
              value={llmProvider} 
              onChange={handleLlmProviderChange}
              className="px-3 py-1 bg-white dark:bg-neutral-600 border border-neutral-300 dark:border-neutral-500 rounded text-sm text-neutral-900 dark:text-neutral-100 focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500"
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
              <label htmlFor="enable-clarification" className="flex items-center gap-2 text-sm text-neutral-700 dark:text-neutral-200">
                <input
                  id="enable-clarification"
                  type="checkbox"
                  checked={enableClarification}
                  onChange={handleEnableClarificationChange}
                  className="rounded border-neutral-300 dark:border-neutral-500 text-neutral-600 dark:text-neutral-400 focus:ring-neutral-500 dark:bg-neutral-600"
                />
                Enable Clarifications
              </label>
            </div>
      
            {enableClarification && (
              <div className="flex items-center gap-2">
                <label htmlFor="clarification-threshold" className="text-sm font-medium text-neutral-700 dark:text-neutral-200">Threshold:</label>
                <select 
                  id="clarification-threshold" 
                  value={clarificationThreshold} 
                  onChange={handleClarificationThresholdChange}
                  className="px-3 py-1 bg-white dark:bg-neutral-600 border border-neutral-300 dark:border-neutral-500 rounded text-sm text-neutral-900 dark:text-neutral-100 focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500"
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
      {messagesLoading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="w-12 h-12 bg-neutral-100 dark:bg-neutral-600 rounded-full flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-neutral-500 dark:text-neutral-300 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-neutral-600 dark:text-neutral-300 text-sm font-medium">Loading messages...</p>
            <p className="text-neutral-400 dark:text-neutral-500 text-xs mt-1">Fetching conversation history</p>
          </div>
        </div>
      ) : (()=>{
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
                    <div key={`progress-${msg.id}`} className="flex justify-start">
                      <div className="mb-2 max-w-[90%]">
                        <AgentProgressDisplay messages={progressMsgs} />
                      </div>
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
      
      <form className="flex-shrink-0 p-4 bg-neutral-100 dark:bg-neutral-700 border-t border-neutral-200 dark:border-neutral-600" onSubmit={handleSubmit}>
        <div className="flex gap-2">
          <select 
            value={selectedAgent} 
            onChange={handleAgentChange}
            className="px-3 py-2 bg-white dark:bg-neutral-600 border border-neutral-300 dark:border-neutral-500 rounded text-sm text-neutral-900 dark:text-neutral-100 focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500 disabled:bg-neutral-100 dark:disabled:bg-neutral-600 disabled:cursor-not-allowed"
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
          placeholder={messages.length > 1
            ? "Ask me to refine the result or ask a new question..." 
            : AGENT_TYPES.find(agent => agent.id === selectedAgent)?.placeholder || "Enter your request..."}
          className="flex-1 px-3 py-2 border border-neutral-300 dark:border-neutral-500 rounded focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500 disabled:bg-neutral-100 dark:disabled:bg-neutral-600 disabled:cursor-not-allowed bg-white dark:bg-neutral-600 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-500 dark:placeholder:text-neutral-400"
          disabled={isLoading || hasUnansweredClarificationQuestions()}
        />
        <button 
          type="submit" 
          className="px-4 py-2 bg-blue-600 dark:bg-blue-700 text-white rounded hover:bg-blue-700 dark:hover:bg-blue-600 disabled:bg-neutral-400 dark:disabled:bg-neutral-600 disabled:cursor-not-allowed transition-colors focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          disabled={isLoading}
        >
          {isLoading ? 'Generating...' : hasUnansweredClarificationQuestions() ? 'Answer Questions' : 'Send'}
        </button>
        </div>
      </form>

      {/* Clarification Dialog */}
      <ClarificationDialog
        isOpen={showClarificationDialog}
        onClose={() => setShowClarificationDialog(false)}
        clarificationQuestions={clarificationDialogData?.questions || []}
        onSubmit={handleClarificationSubmit}
        isSubmitting={isSubmittingClarification}
      />
    </div>
  );
};

export default ChatWindow; 