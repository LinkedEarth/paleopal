import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { AgentProgressDisplay } from './AgentProgressDisplay';
import AgentResultsDisplay from './AgentResultsDisplay';
import ClarificationMessage from './ClarificationMessage';
import ClarificationResponseMessage from './ClarificationResponseMessage';
import ClarificationDialog from './ClarificationDialog';
import { buildApiUrl, apiRequest } from '../config/api';
import API_CONFIG from '../config/api';
import AgentIcon from './AgentIcon';
import THEME, { getAgentTheme } from '../styles/colorTheme';
import Icon from './Icon';
// React-Query hooks
import { useConversationMessages } from '../hooks/useConversationMessages';
import { useActiveJob } from '../hooks/useActiveJob';
import { useConversationSocket } from '../hooks/useConversationSocket';

const LLM_PROVIDERS = [
  { id: 'openai', name: 'OpenAI' },  
  { id: 'google', name: 'Google' },  
  { id: 'anthropic', name: 'Anthropic' },
  { id: 'grok', name: 'XAI Grok' },
  { id: 'ollama', name: 'Ollama' }
];

// LLM Provider badge styles - consistent with agent styling
const LLM_PROVIDER_BADGES = {
  openai: 'bg-green-50 dark:bg-green-950/30 border border-green-200/60 dark:border-green-800/40 text-green-700 dark:text-green-300 shadow-sm',
  google: 'bg-blue-50 dark:bg-blue-950/30 border border-blue-200/60 dark:border-blue-800/40 text-blue-700 dark:text-blue-300 shadow-sm',
  anthropic: 'bg-purple-50 dark:bg-purple-950/30 border border-purple-200/60 dark:border-purple-800/40 text-purple-700 dark:text-purple-300 shadow-sm',
  grok: 'bg-yellow-50 dark:bg-yellow-950/30 border border-yellow-200/60 dark:border-yellow-800/40 text-yellow-700 dark:text-yellow-300 shadow-sm',
  ollama: 'bg-gray-50 dark:bg-gray-950/30 border border-gray-200/60 dark:border-gray-800/40 text-gray-700 dark:text-gray-300 shadow-sm'
};

// LLM Provider focus states - consistent with agent focus styling
const LLM_PROVIDER_FOCUS = {
  openai: 'focus:border-green-500 focus:ring-2 focus:ring-green-500/20 dark:focus:border-green-400 dark:focus:ring-green-400/20',
  google: 'focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:focus:border-blue-400 dark:focus:ring-blue-400/20',
  anthropic: 'focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 dark:focus:border-purple-400 dark:focus:ring-purple-400/20',
  grok: 'focus:border-yellow-500 focus:ring-2 focus:ring-yellow-500/20 dark:focus:border-yellow-400 dark:focus:ring-yellow-400/20',
  ollama: 'focus:border-gray-500 focus:ring-2 focus:ring-gray-500/20 dark:focus:border-gray-400 dark:focus:ring-gray-400/20'
};

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

// Agent styles using centralized theme
const AGENT_STYLES = {
  sparql: {
    badgeBg: getAgentTheme('sparql').badge,
    accent: getAgentTheme('sparql').accent,
    iconColor: getAgentTheme('sparql').icon,
  },
  code: {
    badgeBg: getAgentTheme('code').badge,
    accent: getAgentTheme('code').accent,
    iconColor: getAgentTheme('code').icon,
  },
  workflow_generation: {
    badgeBg: getAgentTheme('workflow_generation').badge,
    accent: getAgentTheme('workflow_generation').accent,
    iconColor: getAgentTheme('workflow_generation').icon,
  },
};

// Agent border classes using new theme
const AGENT_BORDER_CLASSES = {
  sparql: getAgentTheme('sparql').focus,
  code: getAgentTheme('code').focus,
  workflow_generation: getAgentTheme('workflow_generation').focus,
};

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

// Conversation service utility for updating conversation settings
const conversationService = {
  async updateConversation(conversationId, updateData) {
    const url = buildApiUrl(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/${conversationId}`);
    return await apiRequest(url, {
      method: 'PUT',
      body: JSON.stringify(updateData)
    });
  }
};

// Utility function to convert backend message format to frontend format (unified schema)
const convertBackendMessagesToFrontend = (backendMessages) => {
  return backendMessages.map(msg => {
    const baseMessage = {
      id: msg.id,
      role: msg.role,
      content: msg.content,
      timestamp: msg.created_at,
      agentType: msg.agent_type,
      messageType: msg.message_type,
      
      // Unified generation results
      generatedCode: msg.generated_code,
      generatedSparql: msg.agent_metadata?.generated_sparql,
      executionResults: msg.execution_results,
      resultVariableNames: msg.result_variable_names,
      
      // Agent-specific metadata (unified)
      agentMetadata: msg.agent_metadata,
      
      // Legacy fields for backward compatibility
      sparqlQuery: msg.agent_metadata?.generated_sparql || null,
      queryResults: msg.agent_metadata?.generated_results || null,
      sparqlMetadata: msg.agent_metadata?.sparql_stats,
      
      // Progress tracking
      isNodeProgress: msg.is_node_progress,
      ownerId: msg.owner_message_id,
      phase: msg.phase,
      nodeName: msg.node_name,
      
      // UI flags - updated for unified schema
      hasQueryResults: msg.has_execution_results,
      hasGeneratedCode: msg.has_generated_code,
      hasWorkflowPlan: msg.agent_metadata && Object.keys(msg.agent_metadata).length > 0 && msg.agent_type === 'workflow_generation',
      hasWorkflowExecution: msg.has_execution_results && msg.agent_type === 'workflow_generation',
      
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

    // Special handling for workflow agent: JSON workflow is stored in generated_code
    if (msg.agent_type === 'workflow_generation') {
      // First check generated_code (current format)
      if (msg.generated_code) {
        try {
          // Try to parse as JSON workflow
          const workflowData = JSON.parse(msg.generated_code);
          if (workflowData && workflowData.steps && Array.isArray(workflowData.steps)) {
            baseMessage.workflowPlan = msg.generated_code; // This is the JSON workflow
            baseMessage.isJsonWorkflow = true; // Flag to indicate this is JSON format
          }
        } catch (e) {
          // If not valid JSON, treat as legacy format
          baseMessage.workflowPlan = msg.generated_code;
          baseMessage.isJsonWorkflow = false;
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
  const [waitingForClarification, setWaitingForClarification] = useState(false);
  const [clarificationQuestions, setClarificationQuestions] = useState([]);
  const [llmProvider, setLlmProvider] = useState('google');
  const [selectedAgent, setSelectedAgent] = useState('sparql');
  const [isLoading, setIsLoading] = useState(false);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [deletingMessages, setDeletingMessages] = useState(new Set());
  const [error, setError] = useState(null);
  // Track answers to clarification questions
  const [clarificationAnswers, setClarificationAnswers] = useState({});
  // Track the original request context when clarification is needed
  const [originalRequestContext, setOriginalRequestContext] = useState(null);
  
  // Clarification settings - use defaults instead of conversation prop
  const [enableClarification, setEnableClarification] = useState(true);
  const [clarificationThreshold, setClarificationThreshold] = useState('conservative');
  
  // Add state to track execution timing
  const [executionStartTime, setExecutionStartTime] = useState(null);
  
  // Clarification dialog state
  const [showClarificationDialog, setShowClarificationDialog] = useState(false);
  const [clarificationDialogData, setClarificationDialogData] = useState(null);
  const [isSubmittingClarification, setIsSubmittingClarification] = useState(false);
  
  const [enableExecution, setEnableExecution] = useState(true);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const [autoFetchEnabled, setAutoFetchEnabled] = useState(false);
  
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
  
  // Legacy polling refs (no longer used after React-Query refactor)
  const currentPollingInterval = useRef(null);
  const currentPollingConversationId = useRef(null);
  
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
    // Only sync when the conversation ID actually changes (conversation switch)
    if (conversation.id && conversation.id !== prevConversationIdRef.current && !updatingFromPropRef.current) {
      // console.log('✅ Conversation ID changed, loading messages...');
      updatingFromPropRef.current = true;
      
      // Stop any existing polling from the previous conversation
      stopPolling();
      
      // Immediately clear messages to prevent showing old conversation data
      setMessages([]);
      
      // Also immediately clear conversation-specific state to prevent bleeding
      setWaitingForClarification(false);
      setClarificationQuestions([]);
      setClarificationAnswers({});
      setOriginalRequestContext(null);
      setIsLoading(false);
      setError(null);
      setInputValue('');
      
      // Load messages from the new API
      const loadMessages = async () => {
        setMessagesLoading(true);
        
        // First, reset all settings to defaults to prevent cross-conversation bleeding
        setWaitingForClarification(false);
        setClarificationQuestions([]);
        setClarificationAnswers({});
        setOriginalRequestContext(null);
        setLlmProvider('google');
        setSelectedAgent('sparql');
        setEnableClarification(true);
        setClarificationThreshold('conservative');
        setEnableExecution(true);
        setExecutionStartTime(null);
        setIsLoading(false);
        setError(null);
        setInputValue('');
        
        try {
          // Load conversation settings from backend first
          try {
            const conversationUrl = buildApiUrl(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/${conversation.id}`);
            const conversationDetails = await apiRequest(conversationUrl);
            
            // Apply conversation-specific settings if they exist
            if (conversationDetails) {
              setLlmProvider(conversationDetails.llm_provider || 'google');
              setSelectedAgent(conversationDetails.selected_agent || 'sparql');
              setEnableClarification(conversationDetails.enable_clarification ?? true);
              setClarificationThreshold(conversationDetails.clarification_threshold || 'conservative');
              setEnableExecution(conversationDetails.enable_execution ?? true);
              setWaitingForClarification(conversationDetails.waiting_for_clarification || false);
              setClarificationQuestions(conversationDetails.clarification_questions || []);
              setClarificationAnswers(conversationDetails.clarification_answers || {});
              setOriginalRequestContext(conversationDetails.original_request || null);
            }
          } catch (settingsError) {
            console.warn('Failed to load conversation settings, using defaults:', settingsError);
            // Continue with defaults - don't fail the entire loading process
          }
          
          const loadedMessages = await messageService.getConversationMessages(conversation.id, true);
          
          if (loadedMessages.length > 0) {
            // Convert backend message format to frontend format
            const convertedMessages = convertBackendMessagesToFrontend(loadedMessages);
            setMessages(convertedMessages);
            
            // Check if the conversation has a pending request that needs polling
            // Look for the last user message and check if there's a corresponding completed assistant response
            const userMessages = convertedMessages.filter(msg => msg.role === 'user' && !msg.isNodeProgress);
            const assistantMessages = convertedMessages.filter(msg => msg.role === 'assistant' && !msg.isNodeProgress);
            
            if (userMessages.length > 0) {
              const lastUserMessage = userMessages[userMessages.length - 1];
              const lastUserMessageTime = new Date(lastUserMessage.timestamp || lastUserMessage.created_at || 0);
              
              // Check if there's a completed assistant response after the last user message
              const hasCompletedResponse = assistantMessages.some(msg => {
                const msgTime = new Date(msg.timestamp || msg.created_at || 0);
                const isAfterUserMessage = msgTime > lastUserMessageTime;
                const hasResults = msg.hasQueryResults || 
                  msg.hasGeneratedCode || 
                  msg.hasWorkflowPlan ||
                  msg.hasWorkflowExecution ||
                  msg.needsClarification;
                
                return isAfterUserMessage && hasResults;
              });
              
              // Check if request is too old (more than 5 minutes)
              const timeSinceLastUserMessage = Date.now() - lastUserMessageTime.getTime();
              const fiveMinutes = 5 * 60 * 1000;
              
              if (!hasCompletedResponse) {
                if (timeSinceLastUserMessage > fiveMinutes) {
                  setError('Request timed out - the agent took too long to respond');
                  setIsLoading(false);
                } else {
                  setIsLoading(true);
                }
              }
            }
            
            // Check if we need to restore clarification state from messages
            // This handles cases where the last message is asking for clarification
            const lastAssistantMessage = convertedMessages
              .filter(msg => msg.role === 'assistant' && !msg.isNodeProgress)
              .pop(); // Get the most recent assistant message
              
            if (lastAssistantMessage && lastAssistantMessage.needsClarification && lastAssistantMessage.clarificationQuestions) {
              // Set clarification state after a brief delay to ensure other state is set
              setTimeout(() => {
                setWaitingForClarification(true);
                setClarificationQuestions(lastAssistantMessage.clarificationQuestions);
                // Clear any existing answers to start fresh
                setClarificationAnswers({});
              }, 100);
            }
          } else {
            const greeting = [{
              id: 1,
              role: 'assistant',
              content: 'Hi! I can help you with paleoclimate data analysis. Choose an agent and let me know what you need!'
            }];
            setMessages(greeting);
          }
        } catch (error) {
          console.error('❌ Failed to load messages:', error);
          console.error('❌ Error details:', {
            message: error.message,
            conversationId: conversation.id
          });
          const greeting = [{
            id: 1,
            role: 'assistant',
            content: 'Hi! I can help you with paleoclimate data analysis. Choose an agent and let me know what you need!'
          }];
          setMessages(greeting);
        } finally {
          setMessagesLoading(false);
        }
      };
      
      loadMessages();
      
      // Update ref to track current conversation
      prevConversationIdRef.current = conversation.id;
      
      // Reset the flag after state updates complete
      setTimeout(() => {
        updatingFromPropRef.current = false;
      }, 100);
    } 
  }, [conversation.id]);

  // Helper function to check if user has scrolled up
  const isUserScrolledUp = () => {
    if (!messagesContainerRef.current) return false;
    const container = messagesContainerRef.current;
    const scrolledUp = container.scrollTop < container.scrollHeight - container.clientHeight - 100;
    return scrolledUp;
  };

  // Smart scroll to bottom - only when appropriate
  const scrollToBottomIfNeeded = (force = false) => {
    if (!autoScrollEnabled && !force) return;
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

  // Cleanup effect placeholder (legacy polling removed)
  useEffect(() => { /* no polling to clean up */ }, []);

  // Legacy polling stubs – kept for backward-compat references
  const stopPolling = () => {};

  const handleInputChange = (e) => {
    setInputValue(e.target.value);
  };

  const handleLlmProviderChange = (e) => {
    const newProvider = e.target.value;
    setLlmProvider(newProvider);
    
    // Persist to backend
    if (conversation.id) {
      conversationService.updateConversation(conversation.id, {
        llm_provider: newProvider
      }).catch(error => {
        console.error('Failed to update LLM provider:', error);
        setError('Failed to save LLM provider setting');
      });
    }
    
    // Update parent immediately
    updateParentConversation();
  };

  const handleEnableClarificationChange = (checked) => {
    setEnableClarification(checked);
    
    // Persist to backend
    if (conversation.id) {
      conversationService.updateConversation(conversation.id, {
        enable_clarification: checked
      }).catch(error => {
        console.error('Failed to update clarification setting:', error);
        setError('Failed to save clarification setting');
      });
    }
    
    // Update parent immediately
    updateParentConversation();
  };

  const handleExecutionToggle = (checked) => {
    setEnableExecution(checked);
    
    // Persist to backend
    if (conversation.id) {
      conversationService.updateConversation(conversation.id, {
        enable_execution: checked
      }).catch(error => {
        console.error('Failed to update execution setting:', error);
        setError('Failed to save execution setting');
      });
    }
    
    // Update parent immediately
    updateParentConversation();
  };

  const handleClarificationThresholdChange = (e) => {
    const newThreshold = e.target.value;
    setClarificationThreshold(newThreshold);
    
    // Persist to backend
    if (conversation.id) {
      conversationService.updateConversation(conversation.id, {
        clarification_threshold: newThreshold
      }).catch(error => {
        console.error('Failed to update clarification threshold:', error);
        setError('Failed to save clarification threshold');
      });
    }
    
    updateParentConversation();
  };

  const handleAgentChange = useCallback((e) => {
    const newAgent = e.target.value;
    
    setSelectedAgent(newAgent);
    // Reset conversation state when switching agents
    setError(null);
    
    // Persist to backend
    if (conversation.id) {
      conversationService.updateConversation(conversation.id, {
        selected_agent: newAgent
      }).catch(error => {
        console.error('Failed to update selected agent:', error);
        setError('Failed to save agent selection');
      });
    }
    
    // Update parent immediately
    updateParentConversation();
  }, [updateParentConversation, conversation.id]);
  

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
            reject(new Error('Step execution timeout (10 min) – no response received'));
          }
        }, 600000); // 10-minute timeout
      });
      
      // Build context with step input and dependency outputs
      const stepContext = {
        workflow_step: {
          step_id: stepInfo.stepId,
          step_number: stepInfo.stepNumber,
          step_name: stepInfo.stepName,
          step_input: stepInfo.input,
          expected_output: stepInfo.expectedOutput,
          dependencies: stepInfo.dependencies || []
        }
      };
      
      // Add previous result variable information for cross-agent variable sharing
      const previousMessages = messages.filter(msg => msg.role === 'assistant' && !msg.isNodeProgress);
      if (previousMessages.length > 0) {
        const lastMessage = previousMessages[previousMessages.length - 1];
        
        if (lastMessage.resultVariableNames && lastMessage.resultVariableNames.length > 0) {
          if (lastMessage.resultVariableNames.length === 1) {
            stepContext.previous_result_variable = lastMessage.resultVariableNames[0];
            console.log(`🔗 Adding previous result variable to context: ${lastMessage.resultVariableNames[0]} from ${lastMessage.agentType} agent`);
          } else {
            stepContext.previous_result_variables = lastMessage.resultVariableNames;
            console.log(`🔗 Adding ${lastMessage.resultVariableNames.length} previous result variables to context: ${lastMessage.resultVariableNames.join(', ')} from ${lastMessage.agentType} agent`);
          }
          stepContext.previous_agent_type = lastMessage.agentType;
        }
      }
      
      // Add dependency outputs to context if available
      if (stepInfo.dependencies && stepInfo.dependencies.length > 0 && stepInfo.allWorkflowSteps) {
        stepContext.dependency_outputs = {};
        
        // Find completed dependency steps and their outputs from previous messages
        stepInfo.dependencies.forEach(depId => {
          const depStep = stepInfo.allWorkflowSteps.find(s => s.id === depId);
          if (depStep) {
            // Look for the output of this dependency step in previous messages
            // This is a simplified approach - in a more sophisticated system,
            // we would track step outputs more systematically
            stepContext.dependency_outputs[depId] = {
              step_name: depStep.name,
              step_description: depStep.description,
              expected_output: depStep.expected_output,
              // Note: Actual output would need to be retrieved from conversation history
              // For now, we include the expected output as a reference
              status: 'completed' // Assuming dependency is completed if we're executing this step
            };
          }
        });
      }
      
      // Create a user message for this step - show the description as the main task
      const stepMessage = `Step ${stepInfo.stepNumber}/${stepInfo.totalSteps}: ${stepInfo.stepName}

📋 ${stepInfo.agentType.toUpperCase()} Agent Task:
${stepInfo.description || stepInfo.input}

${stepInfo.input !== stepInfo.description ? `🔧 Step Input: ${stepInfo.input}` : ''}
${stepInfo.dependencies && stepInfo.dependencies.length > 0 ? `📦 Dependencies: ${stepInfo.dependencies.join(', ')}` : ''}`;
      
      const userMessage = {
        id: `step_${Date.now()}`,
        role: 'user',
        content: stepMessage
      };
      
      // Add the step message to chat immediately
      setMessages(prev => [...prev, userMessage]);
      
      // Wait a moment for UI to update
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Submit the step description as user_input with step context
      console.log(`Executing step with agent: ${stepInfo.agentType}`);
      console.log('Step context:', stepContext);
      
      // Use description as the main user input, with step details in context
      const userInputForAgent = stepInfo.description || stepInfo.input;
      await submitRequest(userInputForAgent, conversation.id, false, stepInfo.agentType, null, stepContext);
      
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
  const submitRequest = async (userInput, conversationId, isClariSubmission = false, overrideAgentType = null, clarificationResponses = null, stepContext = null) => {
    try {
      // Use override agent type if provided, otherwise use current selected agent
      const agentTypeToUse = overrideAgentType || selectedAgent;
      
      // For clarification submissions, include clarification responses in metadata
      const metadata = {
        llm_provider: llmProvider,
        enable_clarification: enableClarification,
        clarification_threshold: clarificationThreshold,
        enable_execution: enableExecution,
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

      // Build context for the request
      let requestContext = stepContext || {};
      
      // If no stepContext provided (regular chat), add previous result variable information
      if (!stepContext) {
        const previousMessages = messages.filter(msg => msg.role === 'assistant' && !msg.isNodeProgress);
        if (previousMessages.length > 0) {
          const lastMessage = previousMessages[previousMessages.length - 1];
          if (lastMessage.resultVariableNames && lastMessage.resultVariableNames.length > 0) {
            if (lastMessage.resultVariableNames.length === 1) {
              requestContext.previous_result_variable = lastMessage.resultVariableNames[0];
              console.log(`🔗 Adding previous result variable to regular chat context: ${lastMessage.resultVariableNames[0]} from ${lastMessage.agentType} agent`);
            } else {
              requestContext.previous_result_variables = lastMessage.resultVariableNames;
              console.log(`🔗 Adding ${lastMessage.resultVariableNames.length} previous result variables to regular chat context: ${lastMessage.resultVariableNames.join(', ')} from ${lastMessage.agentType} agent`);
            }
            requestContext.previous_agent_type = lastMessage.agentType;
          }
        }
      }

      // Prepare agent request
      const agentRequest = {
        agent_type: agentTypeToUse,
        capability: AGENT_TYPES.find(a => a.id === agentTypeToUse)?.capability || 'generate_query',
        user_input: isClariSubmission ? "" : userInput, // For clarification, send empty user_input - backend will retrieve original from conversation history
        conversation_id: conversationId,
        context: requestContext,
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

      // React-Query will stream new messages – no manual polling
      
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
      throw error;
    }
  };

  // Legacy polling stub (no longer needed)
  const startPollingForMessages = () => {};

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
      
      // Scroll down immediately when clarification is submitted
      setTimeout(() => scrollToBottomIfNeeded(true), 0);
      
      // Submit clarification responses using the new structured format
      // The submitRequest will automatically use the originalRequestContext.originalQuery for clarification submissions
      const response = await submitRequest(
        "", // Empty userInput - submitRequest will use originalRequestContext.originalQuery
        conversation.id,
        true, // isClariSubmission
        selectedAgent,
        clarificationResponses, // Pass the structured responses directly
        null // No step context for clarification submissions
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

  // Handle downloading conversation as notebook
  const handleDownloadNotebook = async () => {
    if (!conversation.id) {
      setError('No conversation ID available for export');
      return;
    }

    try {
      setIsLoading(true);
      
      const url = buildApiUrl(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/${conversation.id}/export/notebook`);
      const response = await apiRequest(url);
      
      if (response.notebook && response.filename) {
        // Create a blob with the notebook data
        const notebookJson = JSON.stringify(response.notebook, null, 2);
        const blob = new Blob([notebookJson], { type: 'application/json' });
        
        // Create download link
        const downloadUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = response.filename;
        
        // Trigger download
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Clean up
        window.URL.revokeObjectURL(downloadUrl);
        
        console.log(`📓 Downloaded notebook: ${response.filename}`);
      } else {
        throw new Error('Invalid response format');
      }
      
    } catch (error) {
      console.error('Error downloading notebook:', error);
      setError(`Failed to download notebook: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Helper to render individual chat message
  const renderChatMessage = (message, messageIndex) => {
    let baseClasses = "p-4 mb-4 rounded-lg border shadow-sm";
    if (message.hasQueryResults || message.hasGeneratedCode || message.hasWorkflowPlan || message.hasWorkflowExecution) {
      baseClasses += " w-full sm:w-[90%]";
    }
    const roleClasses = message.role === 'user' 
      ? `${THEME.messages.user.bg} ${THEME.messages.user.border} ${THEME.messages.user.text}` 
      : `${THEME.messages.assistant.bg} ${THEME.messages.assistant.border} ${THEME.messages.assistant.text}`;
    const errorClasses = message.isError ? `bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800/30 ${THEME.status.error}` : "";
    const queryResultsClasses = (message.hasQueryResults || message.hasGeneratedCode || message.hasWorkflowPlan || message.hasWorkflowExecution) ? `${THEME.containers.card}` : "";
    const newConversationClasses = message.isNewConversation ? `${THEME.containers.panel}` : "";
    
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
    
    const accentClass = message.agentType ? AGENT_STYLES[message.agentType]?.accent : '';
    const allClasses = [baseClasses, roleClasses, errorClasses, queryResultsClasses, newConversationClasses, deletingClasses, accentClass]
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
                <Icon name="spinner" className="w-4 h-4 animate-spin text-red-500 dark:text-red-400" />
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
                <Icon name="spinner" className="w-4 h-4 animate-spin" />
              ) : (
                <Icon name="delete" className="w-4 h-4" />
              )}
            </button>
          )}
          
          {message.isCombinedAnswers ? (
            <ClarificationResponseMessage 
              content={message.content} 
              clarificationResponses={message.clarificationResponses}
            />
          ) : message.hasQueryResults || message.hasGeneratedCode || message.hasWorkflowPlan || message.hasWorkflowExecution ? (
            <AgentResultsDisplay 
              message={message}
              query={message.sparqlQuery}
              results={message.queryResults}
              error={message.queryError}
              generatedCode={message.generatedCode}
              workflowPlan={message.workflowPlan}
              workflowId={message.workflowId}
              executionResults={message.executionResults}
              failedSteps={message.failedSteps}
              onExecuteStep={handleExecuteStep}
              agentType={message.agentType}
              isJsonWorkflow={message.isJsonWorkflow}
              messageIndex={messageIndex}
              allMessages={messages}
              enableExecution={enableExecution}
              isDarkMode={isDarkMode}
              autoFetch={autoFetchEnabled}
              onMessageUpdate={(updatedMessage) => {
                // Convert backend message format to frontend format
                const convertedMessage = convertBackendMessagesToFrontend([updatedMessage])[0];
                
                // Update the message in the messages array
                setMessages(prevMessages => 
                  prevMessages.map(msg => 
                    msg.id === updatedMessage.id ? { ...msg, ...convertedMessage } : msg
                  )
                );
              }}
              onError={(error) => {
                setError(error);
                setTimeout(() => setError(''), 5000);
              }}
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
            <div className={`flex items-center gap-3 ${THEME.text.secondary}`}>
              <Icon name="spinner" className={`w-5 h-5 animate-spin ${THEME.text.muted}`} />
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
                      <Icon name="user" className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                    </div>
                  ) : (
                    <div className="w-6 h-6 bg-neutral-100 dark:bg-neutral-600 border border-neutral-200 dark:border-neutral-500 rounded-full flex items-center justify-center">
                      <Icon name="computer" className="w-3.5 h-3.5 text-neutral-600 dark:text-neutral-400" />
                    </div>
                  )}
                </div>
                
                {/* Content area with agent badge for user messages */}
                <div className="flex-1 min-w-0">
                  {message.role === 'user' && message.agentType && (
                    <div className="mb-2">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border ${
                          AGENT_STYLES[message.agentType]?.badgeBg || 'bg-blue-100 dark:bg-blue-800/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-700/50'
                        }`}
                      >
                        <AgentIcon
                          agentType={message.agentType}
                          className={`w-3.5 h-3.5 ${AGENT_STYLES[message.agentType]?.iconColor || 'text-blue-600 dark:text-blue-400'}`}
                        />
                        {AGENT_TYPES.find(agent => agent.id === message.agentType)?.name || message.agentType}
                      </span>
                    </div>
                  )}
                  <div className={THEME.text.primary}>{message.content}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Check if any agent is currently busy processing
  const isAgentBusy = () => {
    // Get all progress messages
    const progressMessages = messages.filter(m => m.isNodeProgress);
    
    if (progressMessages.length === 0) {
      return false;
    }
    
    // Group progress messages by owner (user message that triggered them)
    const progressByOwner = {};
    progressMessages.forEach(msg => {
      if (!progressByOwner[msg.ownerId]) {
        progressByOwner[msg.ownerId] = [];
      }
      progressByOwner[msg.ownerId].push(msg);
    });
    
    // Check if any owner has incomplete execution
    for (const ownerId in progressByOwner) {
      const ownerProgress = progressByOwner[ownerId];
      const lastProgress = ownerProgress[ownerProgress.length - 1];
      
      // If the last progress message is not a complete "Agent Execution", the agent is still busy
      const executionDone = lastProgress && 
                           lastProgress.phase === 'complete' && 
                           lastProgress.nodeName === 'Agent Execution';
      
      if (!executionDone) {
        return true;
      }
    }
    
    return false;
  };

  // ---------------------------------------------------------------------------
  // WebSocket: live updates for this conversation
  // ---------------------------------------------------------------------------
  const { isConnected: isWebSocketConnected, connectionState } = useConversationSocket(conversation.id, (evt) => {
    if (!evt || !evt.type) return;
    switch (evt.type) {
      case 'message_created': {
        const incoming = convertBackendMessagesToFrontend([evt.message])[0];
        setMessages((prev) => {
          let next = [...prev];

          // 1. If we previously added a temporary user message or loading stub, replace/remove them.
          if (incoming.role === 'user') {
            // Remove ALL temp user messages when receiving a real user message (more robust)
            next = next.filter((m) => !(m.id.startsWith('temp_') && m.role === 'user'));
          } else {
            // For assistant/progress etc. remove the loading spinner placeholder
            next = next.filter((m) => !m.isLoading);
          }

          // 2. Check if this message already exists to prevent duplicates
          const existingIndex = next.findIndex(m => m.id === incoming.id);
          if (existingIndex !== -1) {
            // Replace existing message
            next[existingIndex] = incoming;
            return next;
          }

          return [...next, incoming];
        });
        break;
      }
      case 'progress': {
        const newMsg = convertBackendMessagesToFrontend([evt.message])[0];
        setMessages((prev) => {
          const withoutSpinner = prev.filter((m) => !m.isLoading);
          
          // Check if this progress message already exists to prevent duplicates
          const existingIndex = withoutSpinner.findIndex(m => m.id === newMsg.id);
          if (existingIndex !== -1) {
            // Replace existing progress message
            const updated = [...withoutSpinner];
            updated[existingIndex] = newMsg;
            return updated;
          }
          
          return [...withoutSpinner, newMsg];
        });
        break;
      }
      case 'job_updated': {
        if (evt.job.state === 'running') setIsLoading(true);
        else setIsLoading(false);
        break;
      }
      case 'message_updated': {
        const updated = convertBackendMessagesToFrontend([evt.message])[0];
        setMessages((prev) => {
          // Replace existing message with same id (if present) else append
          const exists = prev.findIndex((m) => m.id === updated.id);
          if (exists !== -1) {
            const copy = [...prev];
            copy[exists] = { ...copy[exists], ...updated };
            return copy;
          }
          return [...prev, updated];
        });
        break;
      }
      default:
        break;
    }
  });

  // ---------------------------------------------------------------------------
  // React-Query hooks: messages & jobs for this conversation
  // ---------------------------------------------------------------------------
  const conversationIdForJobPolling = isLoading ? conversation.id : null;
  const { data: activeJob } = useActiveJob(conversationIdForJobPolling, isWebSocketConnected);

  // Poll messages as fallback when WebSocket is not connected OR when loading/waiting for responses
  const shouldPollMessages = !isWebSocketConnected || isLoading || waitingForClarification || Boolean(activeJob);
  const { data: backendMessages = [], isFetching: messagesFetching } = useConversationMessages(
    conversation.id,
    true,
    shouldPollMessages,
    isWebSocketConnected,
  );

  // Sync backend messages into local UI state (with fallback when WebSocket fails)
  useEffect(() => {
    if (!backendMessages) return;
    
    const converted = backendMessages.length > 0
      ? convertBackendMessagesToFrontend(backendMessages)
      : defaultGreeting;

    setMessages((prev) => {
      // Enhanced comparison to avoid redundant updates
      if (prev.length === converted.length) {
        const same = prev.every((m, i) => {
          const convertedMsg = converted[i];
          return m.id === convertedMsg.id && 
                 m.updated_at === convertedMsg.updated_at &&
                 m.content === convertedMsg.content;
        });
        if (same) return prev; // no change
      }
      
      // Update if there are meaningful differences
      const source = isWebSocketConnected ? 'WebSocket backup' : 'polling fallback';
      console.debug(`📝 Syncing backend messages to local state (${source})`);
      return converted;
    });
  }, [backendMessages, isWebSocketConnected]);

  // Reflect running job status into loading indicator
  useEffect(() => {
    if (activeJob) {
      setIsLoading(true);
    } else if (!messagesFetching) {
      setIsLoading(false);
    }
  }, [activeJob, messagesFetching]);

  // ---------------------------------------------------------------------------
  // Derived UI state: whether any agent is currently busy
  // ---------------------------------------------------------------------------
  const agentBusy = Boolean(activeJob) || isAgentBusy();

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
        
        // Remove welcome message if this is the first user message
        setMessages(prev => {
          const isFirstUserMessage = prev.length === 1 && prev[0].id === 1 && prev[0].role === 'assistant';
          if (isFirstUserMessage) {
            // Replace welcome message with user message and loading indicator
            return [tempUserMessage, loadingMessage];
          } else {
            // Add to existing messages
            return [...prev, tempUserMessage, loadingMessage];
          }
        });
        
        // Scroll down immediately when user sends a message
        setTimeout(() => scrollToBottomIfNeeded(true), 0);
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
      await submitRequest(userInput, conversationId, false, null, null, null);
      
      // Update conversation title if it's still the default and this is a new user message
      if (userInput && (conversation.title === 'New Chat' || conversation.title === 'Untitled' || !conversation.title)) {
        const newTitle = userInput.slice(0, 50); // Limit title length
        
        // Persist title change to backend
        if (conversation.id) {
          conversationService.updateConversation(conversation.id, {
            title: newTitle
          }).catch(error => {
            console.error('Failed to update conversation title:', error);
            setError('Failed to save conversation title');
          });
        }
        
        // Update the conversation data with the new title
        const updatedConversationData = {
          ...conversationData,
          title: newTitle
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
        setMessages(prev => {
          const filteredMessages = prev.filter(msg => !msg.id.startsWith('temp_') && !msg.id.startsWith('loading_'));
          
          // If we removed the welcome message and now have no messages, restore it
          if (filteredMessages.length === 0) {
            return defaultGreeting;
          }
          
          return filteredMessages;
        });
      }
    } finally {
      setIsLoading(false);
    }
  };



  return (
    <div className={`flex flex-col h-full ${THEME.containers.main}`}>
      <div className={`flex-shrink-0 p-2 ${THEME.containers.header}`}>
        <div className="flex flex-wrap gap-2 sm:gap-4 items-center justify-between">
          <div className="flex flex-wrap gap-2 sm:gap-4 items-center">
          <div className="relative flex-shrink-0">
            <select 
              id="llm-provider" 
              value={llmProvider} 
              onChange={handleLlmProviderChange}
              className={`px-3 sm:px-4 py-2 rounded text-sm disabled:cursor-not-allowed appearance-none ${LLM_PROVIDER_BADGES[llmProvider]} border ${LLM_PROVIDER_FOCUS[llmProvider] || ''} pr-8 transition-all duration-200`}
            >
              {LLM_PROVIDERS.map(provider => (
                <option key={provider.id} value={provider.id}>
                  {provider.name}
                </option>
              ))}
            </select>
            <div className="absolute right-2 top-1/2 transform -translate-y-1/2 pointer-events-none">
              <Icon name="chevronDown" className="w-4 h-4 text-slate-400" />
            </div>
          </div>
      
          <div className="flex items-center gap-1 sm:gap-2">
            {/* Toggle Buttons */}
            
            {/* Clarifications Toggle */}
            <button
              onClick={() => handleEnableClarificationChange(!enableClarification)}
              className={`p-2 rounded-md transition-colors border flex items-center gap-2 ${
                enableClarification 
                  ? `${THEME.status.success.background} ${THEME.status.success.border} ${THEME.status.success.text}` 
                  : `${THEME.containers.card} ${THEME.borders.default} ${THEME.text.secondary} ${THEME.interactive.hover}`
              }`}
              title="Toggle Clarifications"
            >
              <Icon name="question" className="w-4 h-4" />
              <span className="hidden sm:inline text-xs font-medium">
                {enableClarification ? 'Clarifications On' : 'Clarifications Off'}
              </span>
            </button>

            {/* Execution Toggle */}
            <button
              onClick={() => handleExecutionToggle(!enableExecution)}
              className={`p-2 rounded-md transition-colors border flex items-center gap-2 ${
                enableExecution 
                  ? `${THEME.status.success.background} ${THEME.status.success.border} ${THEME.status.success.text}` 
                  : `${THEME.containers.card} ${THEME.borders.default} ${THEME.text.secondary} ${THEME.interactive.hover}`
              }`}
              title="Toggle Code Execution"
            >
              <Icon name="play" className="w-4 h-4" />
              <span className="hidden sm:inline text-xs font-medium">
                {enableExecution ? 'Execution On' : 'Execution Off'}
              </span>
            </button>

            {/* Auto-fetch Toggle */}
            <button
              onClick={() => setAutoFetchEnabled(!autoFetchEnabled)}
              className={`p-2 rounded-md transition-colors border flex items-center gap-2 ${
                autoFetchEnabled 
                  ? `${THEME.status.success.background} ${THEME.status.success.border} ${THEME.status.success.text}` 
                  : `${THEME.containers.card} ${THEME.borders.default} ${THEME.text.secondary} ${THEME.interactive.hover}`
              }`}
              title="Toggle Auto Fetch"
            >
              <Icon name="download" className="w-4 h-4" />
              <span className="hidden sm:inline text-xs font-medium">
                {autoFetchEnabled ? 'Auto-fetch On' : 'Auto-fetch Off'}
              </span>
            </button>
          </div>
          </div>
          
          {/* Download button */}
          {conversation.id && messages.length > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleDownloadNotebook}
                disabled={isLoading || agentBusy}
                className={`flex items-center gap-2 px-3 py-2 rounded transition-colors text-sm disabled:cursor-not-allowed ${THEME.buttons.primary} disabled:bg-slate-400 dark:disabled:bg-slate-600`}
                title="Download conversation as Jupyter notebook"
              >
                <Icon name="download" className="w-4 h-4" />
                <span className="hidden sm:inline">
                  {isLoading ? 'Exporting...' : 'Download Notebook'}
                </span>
              </button>
            </div>
          )}
        </div>
      </div>
      
      {/* Messages area */}
      {messagesLoading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className={`w-12 h-12 ${THEME.containers.secondary} rounded-full flex items-center justify-center mx-auto mb-3`}>
              <Icon name="spinner" className={`w-6 h-6 ${THEME.text.secondary} animate-spin`} />
            </div>
            <p className={`text-sm font-medium ${THEME.text.primary}`}>Loading messages...</p>
            <p className={`text-xs mt-1 ${THEME.text.muted}`}>Fetching conversation history</p>
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
      
      <form className={`flex-shrink-0 w-full p-2 ${THEME.containers.footer}`} onSubmit={handleSubmit}>
        <div className="flex gap-2 w-full">
          <div className="relative flex-shrink-0">
            <select
              value={selectedAgent}
              onChange={handleAgentChange}
              className={`pl-8 pr-3 sm:pr-8 py-2 rounded text-sm disabled:cursor-not-allowed appearance-none ${THEME.agentBadges[selectedAgent]} border ${AGENT_BORDER_CLASSES[selectedAgent] || ''} w-10 sm:w-auto`}
              disabled={isLoading || agentBusy}
            >
              {AGENT_TYPES.map(agent => (
                <option key={agent.id} value={agent.id}>
                  <span className="hidden sm:inline">{agent.name}</span>
                  <span className="sm:hidden">&nbsp;</span>
                </option>
              ))}
            </select>
            <div className={`absolute left-2 top-1/2 transform -translate-y-1/2 pointer-events-none w-5 h-5 ${getAgentTheme(selectedAgent).icon}`}>
              <AgentIcon agentType={selectedAgent} className="w-full h-full" />
            </div>
            <div className="absolute right-2 top-1/2 transform -translate-y-1/2 pointer-events-none hidden sm:block">
              <Icon name="chevronDown" className="w-4 h-4 text-slate-400" />
            </div>
          </div>
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={handleInputChange}
            placeholder={messages.length > 1
              ? "Ask me to refine the result or ask a new question..." 
              : AGENT_TYPES.find(agent => agent.id === selectedAgent)?.placeholder || "Enter your request..."}
            className={`flex-1 px-3 py-2 rounded disabled:cursor-not-allowed ${THEME.forms.input} min-w-0`}
            disabled={isLoading || agentBusy || hasUnansweredClarificationQuestions()}
          />
          <button 
            type="submit" 
            className={`px-3 sm:px-4 py-2 rounded transition-colors disabled:cursor-not-allowed ${THEME.buttons.primary} disabled:bg-slate-400 dark:disabled:bg-slate-600 flex-shrink-0 flex items-center gap-2`}
            disabled={isLoading || agentBusy}
          >
            <Icon name={
              isLoading ? 'spinner' : 
              agentBusy ? 'circle' : 
              hasUnansweredClarificationQuestions() ? 'question' : 
              'send'
            } className="w-4 h-4" />
            <span className="hidden sm:inline">
              {isLoading ? 'Generating...' : agentBusy ? 'Agent Busy...' : hasUnansweredClarificationQuestions() ? 'Answer Questions' : 'Send'}
            </span>
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
