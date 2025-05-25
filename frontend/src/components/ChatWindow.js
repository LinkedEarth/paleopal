import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './ChatWindow.css';

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
    name: 'SPARQL Query Generator',
    capability: 'generate_query',
    description: 'Generate SPARQL queries for paleoclimate data',
    placeholder: 'Ask a question to generate a SPARQL query...'
  },
  { 
    id: 'code', 
    name: 'Code Generator',
    capability: 'generate_code', 
    description: 'Generate Python code for data analysis',
    placeholder: 'Describe the analysis you want to perform...'
  }
];

// Loading indicator component
const LoadingIndicator = () => (
  <div className="loading-indicator">
    <div className="loading-spinner">
      <div className="spinner-circle"></div>
    </div>
    <div className="loading-text">Processing your request...</div>
  </div>
);

// Component to render formatted clarification messages
const ClarificationMessage = ({ content, clarificationQuestions }) => {
  // If we have multiple questions, use those
  if (clarificationQuestions && clarificationQuestions.length > 0) {
    return (
      <div className="clarification-message-content">
        {clarificationQuestions.map((question, index) => (
          <div key={question.id || index} className="clarification-question-group">
            {clarificationQuestions.length > 1 && (
              <div className="question-number">Question {index + 1}</div>
            )}
            <div className="clarification-question">{question.question}</div>
            
            {question.context && (
              <div className="clarification-context">{question.context}</div>
            )}
            
            {question.choices && question.choices.length > 0 && (
              <div className="clarification-choices">
                <div className="choices-label">Options:</div>
                <ul className="choices-list">
                  {question.choices.map((choice, choiceIndex) => (
                    <li key={choiceIndex} className="choice-item">{choice}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }
  
  // Otherwise, try to parse and format the raw text content
  const parts = parseMessageParts(content);
  return (
    <div className="clarification-message-content">
      <div className="clarification-question">{parts.question}</div>
      
      {parts.context && (
        <div className="clarification-context">{parts.context}</div>
      )}
      
      {parts.options.length > 0 && (
        <div className="clarification-choices">
          <div className="choices-label">Options:</div>
          <ul className="choices-list">
            {parts.options.map((option, index) => (
              <li key={index} className="choice-item">{option}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

// Component to render clarification responses in a nice format
const ClarificationResponseMessage = ({ content }) => {
  console.log('ClarificationResponseMessage rendering with content:', content);
  console.log('Content type:', typeof content);
  console.log('Content length:', content ? content.length : 'null/undefined');
  
  // Fallback for empty or invalid content
  if (!content || typeof content !== 'string' || content.trim().length === 0) {
    console.error('ClarificationResponseMessage: Invalid or empty content');
    return (
      <div className="clarification-response-content">
        <div className="clarification-response-header">
          <span className="response-icon">⚠</span>
          Error: No content to display
        </div>
        <div style={{ padding: '1rem', backgroundColor: 'rgba(255, 0, 0, 0.1)' }}>
          Content is empty or invalid. Raw content: {JSON.stringify(content)}
        </div>
      </div>
    );
  }
  
  // Parse the Q&A pairs and additional comments from the content
  const lines = content.split('\n');
  const qaPairs = [];
  let additionalComment = '';
  
  let currentQ = '';
  let currentA = '';
  let inAdditionalComment = false;
  
  console.log('Parsing lines:', lines);
  
  for (const line of lines) {
    if (line.startsWith('Q: ')) {
      // If we have a previous Q&A pair, save it
      if (currentQ && currentA) {
        qaPairs.push({ question: currentQ, answer: currentA });
      }
      currentQ = line.substring(3);
      currentA = '';
      inAdditionalComment = false;
    } else if (line.startsWith('A: ')) {
      currentA = line.substring(3);
    } else if (line.startsWith('Additional comment: ')) {
      additionalComment = line.substring(20);
      inAdditionalComment = true;
    } else if (inAdditionalComment && line.trim()) {
      additionalComment += '\n' + line;
    }
  }
  
  // Add the last Q&A pair if it exists
  if (currentQ && currentA) {
    qaPairs.push({ question: currentQ, answer: currentA });
  }
  
  console.log('Parsed qaPairs:', qaPairs);
  console.log('Additional comment:', additionalComment);
  
  // If no Q&A pairs found, treat the entire content as a single response
  if (qaPairs.length === 0) {
    console.log('No Q&A pairs found, treating as plain text response');
    return (
      <div className="clarification-response-content">
        <div className="clarification-response-header">
          <span className="response-icon">✓</span>
          Clarification Responses
        </div>
        <div style={{ 
          padding: '1rem', 
          backgroundColor: 'white', 
          borderRadius: '0.75rem',
          border: '1px solid rgba(46, 204, 113, 0.2)',
          minHeight: '60px'
        }}>
          <div style={{ fontSize: '0.95rem', lineHeight: '1.4', color: '#333' }}>
            {content}
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="clarification-response-content">
      <div className="clarification-response-header">
        <span className="response-icon">✓</span>
        Clarification Responses
      </div>
      
      <div className="clarification-qa-pairs">
        {qaPairs.map((pair, index) => (
          <div key={index} className="qa-pair">
            <div className="qa-question">
              <span className="qa-label">Q:</span>
              <span className="qa-text">{pair.question}</span>
            </div>
            <div className="qa-answer">
              <span className="qa-label">A:</span>
              <span className="qa-text">{pair.answer}</span>
            </div>
          </div>
        ))}
      </div>
      
      {additionalComment && (
        <div className="additional-comment">
          <div className="comment-label">Additional comment:</div>
          <div className="comment-text">{additionalComment}</div>
        </div>
      )}
    </div>
  );
};

// Component to render SPARQL query results in a table
const QueryResultsDisplay = ({ results, error }) => {
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
      .then(() => {
        alert('Copied to clipboard!');
      })
      .catch(err => {
        console.error('Could not copy text: ', err);
      });
  };

  if (error) {
    return (
      <div className="query-results-error">
        <div className="results-header">
          <h4>❌ Query Error</h4>
        </div>
        <div className="error-message">{error}</div>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className="query-results-empty">
        <div className="results-header">
          <h4>📊 Query Results</h4>
        </div>
        <p>No results found.</p>
      </div>
    );
  }

  // Extract headers from the first result
  const headers = Object.keys(results[0]);

  return (
    <div className="query-results-container">
      <div className="results-header">
        <h4>📊 Query Results ({results.length} row{results.length !== 1 ? 's' : ''})</h4>
        <button 
          className="copy-results-button"
          onClick={() => copyToClipboard(JSON.stringify(results, null, 2))}
          title="Copy results as JSON"
        >
          📋 Copy JSON
        </button>
      </div>
      <div className="results-table-wrapper">
        <table className="inline-results-table">
          <thead>
            <tr>
              {headers.map(header => (
                <th key={header}>{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {headers.map(header => (
                  <td key={`${rowIndex}-${header}`}>
                    {row[header]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Component to display SPARQL queries with syntax highlighting
const SparqlQueryDisplay = ({ query }) => {
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      // Could add a toast notification here
    }).catch(err => {
      console.error('Failed to copy text: ', err);
      });
  };

  return (
    <div className="sparql-query-display">
      <div className="query-header">
        <span className="query-label">Generated SPARQL Query:</span>
        <button 
          className="copy-button" 
          onClick={() => copyToClipboard(query)}
          title="Copy query to clipboard"
        >
          📋 Copy
        </button>
      </div>
      <div className="query-content">
        <SyntaxHighlighter 
          language="sparql" 
          style={tomorrow} 
          customStyle={{
            margin: 0,
            borderRadius: '0.5rem',
            fontSize: '0.9rem'
          }}
        >
          {query}
        </SyntaxHighlighter>
      </div>
    </div>
  );
};

// Component to display generated Python code with syntax highlighting
const GeneratedCodeDisplay = ({ code }) => {
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      // Could add a toast notification here
    }).catch(err => {
      console.error('Failed to copy text: ', err);
    });
  };

  return (
    <div className="generated-code-display">
      <div className="code-header">
        <span className="code-label">Generated Python Code:</span>
        <button 
          className="copy-button" 
          onClick={() => copyToClipboard(code)}
          title="Copy code to clipboard"
        >
          📋 Copy
        </button>
      </div>
      <div className="code-content">
        <SyntaxHighlighter 
          language="python" 
          style={tomorrow}
          customStyle={{
            margin: 0,
            borderRadius: '0.5rem',
            fontSize: '0.9rem'
          }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  );
};

// Component to render combined query and results
const QueryAndResultsMessage = ({ query, results, error, generatedCode }) => {
  console.log('QueryAndResultsMessage called with:', {
    hasQuery: !!query,
    hasResults: !!results,
    hasError: !!error,
    hasGeneratedCode: !!generatedCode,
    generatedCodeLength: generatedCode?.length
  });
  
  return (
    <div className="query-and-results-message">
      {query && <SparqlQueryDisplay query={query} />}
      {generatedCode && <GeneratedCodeDisplay code={generatedCode} />}
      {query && <QueryResultsDisplay results={results} error={error} />}
    </div>
  );
};

// Helper to parse message parts
const parseMessageParts = (content) => {
  // Default structure
  const result = {
    question: content,
    options: [],
    context: ''
  };
  
  try {
    // Check if the content has multiple questions
    const questionBlocks = content.split(/Question \d+:/);
    
    if (questionBlocks.length > 1) {
      // We have multiple questions - parse the first one for display
      const firstBlock = questionBlocks[1] || '';
      
      // Extract the main question (first line of the block)
      const lines = firstBlock.split('\n').filter(line => line.trim());
      if (lines.length > 0) {
        result.question = lines[0].trim();
      }
      
      // Extract options if present
      if (firstBlock.includes('Options:')) {
        const optionsSection = firstBlock.split('Options:')[1].split('\n\n')[0];
        result.options = optionsSection
          .split('\n')
          .filter(line => line.trim().startsWith('-'))
          .map(line => line.trim().substring(2).trim());
      }
      
      // Extract context (text after options, before state_id)
      const contextMatch = firstBlock.match(/(?:Options:[^]*?\n\n)?(.*?)$/s);
      if (contextMatch && contextMatch[1].trim()) {
        result.context = contextMatch[1].trim();
      }
      
      return result;
    }
    
    // Original single question parsing logic
    // Extract the main question (usually the first paragraph)
    const paragraphs = content.split('\n\n').filter(p => p.trim().length > 0);
    if (paragraphs.length > 0) {
      result.question = paragraphs[0].trim();
    }
    
    // Extract options if present
    if (content.includes('Options:')) {
      const optionsSection = content.split('Options:')[1].split('\n\n')[0];
      result.options = optionsSection
        .split('\n')
        .filter(line => line.trim().startsWith('-'))
        .map(line => line.trim().substring(2).trim());
    }
    
    // Try to extract context (usually the last paragraph if not options)
    if (paragraphs.length > 1 && !paragraphs[paragraphs.length - 1].includes('Options:') && 
        true) {
      result.context = paragraphs[paragraphs.length - 1].trim();
    }
    
    return result;
  } catch (error) {
    console.error('Error parsing message parts:', error);
    return result;
  }
};

// Parse multiple clarification questions from content
const parseClarificationQuestions = (content) => {
  // Check if we have multiple questions
  const questionBlocks = content.split(/Question \d+:/);
  
  if (questionBlocks.length <= 1) {
    // Single question format - use existing parser
    const parts = parseMessageParts(content);
    return [{
      id: 'q1',
      question: parts.question,
      choices: parts.options,
      context: parts.context
    }];
  }
  
  // We have multiple questions - parse each block
  const questions = [];
  
  for (let i = 1; i < questionBlocks.length; i++) {
    const block = questionBlocks[i];
    if (!block.trim()) continue;
    
    const questionParts = {
      id: `q${i}`,
      question: '',
      choices: [],
      context: ''
    };
    
    // Extract the main question (first line of the block)
    const lines = block.split('\n').filter(line => line.trim());
    if (lines.length > 0) {
      questionParts.question = lines[0].trim();
    }
    
    // Extract options if present
    if (block.includes('Options:')) {
      const optionsSection = block.split('Options:')[1].split('\n\n')[0];
      questionParts.choices = optionsSection
        .split('\n')
        .filter(line => line.trim().startsWith('-'))
        .map(line => line.trim().substring(2).trim());
    }
    
    // Extract context (text after options, before next question or state_id)
    const contextMatch = block.match(/(?:Options:[^]*?\n\n)?(.*?)$/s);
    if (contextMatch && contextMatch[1].trim()) {
      questionParts.context = contextMatch[1].trim();
    }
    
    questions.push(questionParts);
  }
  
  return questions;
};

const ChatWindow = ({ conversation = {}, onConversationUpdate }) => {
  // Use conversation data if provided, otherwise default greeting
  const defaultGreeting = [{
    id: 1,
    role: 'assistant',
    content: 'Hi! I can help you with paleoclimate data analysis. Choose an agent above and let me know what you need!'
  }];

  const [messages, setMessages] = useState(conversation.messages?.length ? conversation.messages : defaultGreeting);
  const [inputValue, setInputValue] = useState('');
  const [stateId, setStateId] = useState(conversation.stateId || null);
  const [waitingForClarification, setWaitingForClarification] = useState(false);
  const [clarificationQuestions, setClarificationQuestions] = useState([]);
  const [llmProvider, setLlmProvider] = useState('google');
  const [selectedAgent, setSelectedAgent] = useState('sparql');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  // Track answers to clarification questions
  const [clarificationAnswers, setClarificationAnswers] = useState({});
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Effect to notify parent about conversation updates
  useEffect(() => {
    if (onConversationUpdate && typeof onConversationUpdate === 'function') {
      // Derive title – first user message or default
      const firstUserMsg = messages.find((m) => m.role === 'user');
      const title = firstUserMsg ? firstUserMsg.content.slice(0, 50) : conversation.title || 'New Chat';

      onConversationUpdate({
        id: conversation.id,
        title,
        messages,
        stateId,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, stateId]);

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

  const handleAgentChange = (e) => {
    setSelectedAgent(e.target.value);
    // Reset conversation state when switching agents
    setStateId(null);
    setWaitingForClarification(false);
    setClarificationQuestions([]);
    setClarificationAnswers({});
    setError(null);
  };

  // Start a new query conversation
  const handleNewQuery = () => {
    setStateId(null);
    setWaitingForClarification(false);
    setClarificationQuestions([]);
    setClarificationAnswers({});
    setError(null);
    
    // Add a separator message to show new conversation
    const newConversationMessage = {
      id: Date.now(),
      role: 'assistant',
      content: 'Starting a new query conversation. What would you like to search for?',
      isNewConversation: true
    };
    setMessages(prev => [...prev, newConversationMessage]);
  };

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
  
  // Function to parse clarification options from message content
  const parseClarificationOptions = (content) => {
    try {
      // Check if the message has "Options:" text
      if (content.includes('Options:')) {
        const optionsSection = content.split('Options:')[1].split('\n\n')[0];
        // Extract choices by looking for list items that start with "-"
        const options = optionsSection
          .split('\n')
          .filter(line => line.trim().startsWith('-'))
          .map(line => line.trim().substring(2).trim());
        
        return options.length > 0 ? options : [];
      }
      return [];
    } catch (error) {
      console.error('Error parsing clarification options:', error);
      return [];
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const currentUserInput = inputValue.trim();
    
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
      const userMessageId = Date.now();
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
    } else {
      // Regular query - don't proceed if no input
      if (!currentUserInput) return;
      
      // Add user message to chat
      const userMessageId = Date.now();
      const userMessage = { id: userMessageId, role: 'user', content: currentUserInput };
      setMessages(prev => [...prev, userMessage]);
    }
    
    // Clear input and set loading
    setInputValue('');
    setIsLoading(true);
    setError(null);
    
    try {
      // Get the selected agent configuration
      const agentConfig = AGENT_TYPES.find(agent => agent.id === selectedAgent);
      if (!agentConfig) {
        throw new Error('Invalid agent selected');
      }

      // Prepare request payload for the new multi-agent API
      const agentRequest = {
        agent_type: selectedAgent,
        capability: agentConfig.capability,
        user_input: currentUserInput,
        conversation_id: stateId,
        context: {},
        metadata: {
          llm_provider: llmProvider
        }
      };
      
      // If we have clarification responses to send, add them
      if (clarificationResponses.length > 0) {
        agentRequest.metadata.clarification_responses = clarificationResponses;
      }
      
      console.log('Sending agent request:', agentRequest);
      
      // Send request to new multi-agent API
      const response = await axios.post('/agents/request', agentRequest);
      const data = response.data;
      
      console.log('Agent API Response:', {
        status: data.status,
        has_clarification_questions: !!(data.clarification_questions && data.clarification_questions.length > 0),
        has_generated_code: !!data.generated_code,
        has_result: !!data.result,
        conversation_id: data.conversation_id
      });
      
      // Check if clarification is needed
      if (data.status === 'needs_clarification') {
        console.log('New clarification needed, showing UI');
        setStateId(data.conversation_id);
        setWaitingForClarification(true);
        setClarificationAnswers({});
        
        // Handle clarification questions
        if (data.clarification_questions && data.clarification_questions.length > 0) {
          setClarificationQuestions(data.clarification_questions);
        } else {
          // Parse from the message if structured data not available
          const parsedQuestions = parseClarificationQuestions(data.message);
          setClarificationQuestions(parsedQuestions);
        }
        
        // Add assistant message to chat (simplified for clarification)
        const assistantMessage = { 
          id: Date.now(), 
          role: 'assistant', 
          content: data.clarification_questions && data.clarification_questions.length > 0 
            ? "I need some clarification to generate the right query. Please answer the questions below."
            : data.message,
          needsClarification: true,
          clarificationQuestions: data.clarification_questions
        };
        setMessages(prev => [...prev, assistantMessage]);
      } else if (data.status === 'success') {
        console.log('Success response, processing results');
        // Clear clarification UI state but keep conversation state (stateId) for refinement
        setWaitingForClarification(false);
        setClarificationQuestions([]);
        setClarificationAnswers({});
        
        // Keep the conversation_id from the response for continued conversation
        if (data.conversation_id) {
          setStateId(data.conversation_id);
        }
        
        // Process the results
        const generatedContent = data.result?.generated_code;
        const queryResults = data.result?.execution_results;
        const queryError = data.result?.error;
        const executionInfo = data.result?.execution_info;
        
        console.log('Processing success response:', {
          generatedContent: !!generatedContent,
          generatedContentLength: generatedContent?.length,
          queryResults: !!queryResults,
          queryResultsLength: queryResults?.length,
          queryError: !!queryError,
          executionInfo: !!executionInfo,
          selectedAgent,
          fullData: data
        });
        
        if (generatedContent) {
          // Always show the generated content if we have it
          const resultsMessage = { 
            id: Date.now() + 1, 
            role: 'assistant', 
            content: data.message || `${agentConfig.name} completed successfully!`,
            hasQueryResults: selectedAgent === 'sparql',
            hasGeneratedCode: selectedAgent === 'code',
            sparqlQuery: selectedAgent === 'sparql' ? generatedContent : undefined,
            generatedCode: selectedAgent === 'code' ? generatedContent : undefined,
            queryResults: queryResults,
            queryError: queryError
          };
          
          console.log('Creating results message:', {
            hasQueryResults: resultsMessage.hasQueryResults,
            hasGeneratedCode: resultsMessage.hasGeneratedCode,
            sparqlQuery: !!resultsMessage.sparqlQuery,
            generatedCode: !!resultsMessage.generatedCode,
            generatedCodeLength: resultsMessage.generatedCode?.length,
            selectedAgent: selectedAgent,
            messageStructure: resultsMessage
          });
          
          setMessages(prev => [...prev, resultsMessage]);
          
          // Add a helpful message encouraging refinement
          const refinementMessage = {
            id: Date.now() + 2,
            role: 'assistant',
            content: selectedAgent === 'sparql' 
              ? "You can ask me to refine this query further! For example:\n• \"Add a filter for temperature > 20°C\"\n• \"Show only data from the last 100 years\"\n• \"Include location information\"\n• \"Sort by date descending\""
              : "You can ask me to modify this code! For example:\n• \"Add error handling\"\n• \"Include data visualization\"\n• \"Add comments to explain the code\"\n• \"Optimize for performance\""
          };
          setMessages(prev => [...prev, refinementMessage]);
        } else {
          // Add assistant message to chat
          const assistantMessage = { 
            id: Date.now(), 
            role: 'assistant', 
            content: data.message || `${agentConfig.name} completed successfully!`
          };
          setMessages(prev => [...prev, assistantMessage]);
        }
      } else {
        // Handle error status
        console.error('Agent returned error status:', data.status);
        setError(data.message || 'Error generating query');
        
        // Add error message to chat
        const errorMessage = { 
          id: Date.now(), 
          role: 'assistant', 
          content: `Sorry, I encountered an error: ${data.message || 'Unknown error'}`,
          isError: true
        };
        setMessages(prev => [...prev, errorMessage]);
        
        // Reset clarification state on error but keep conversation state
        setWaitingForClarification(false);
        setClarificationQuestions([]);
        setClarificationAnswers({});
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
    } finally {
      setIsLoading(false);
    }
  };

  // Render the clarification options UI
  const renderClarificationOptions = () => {
    console.log('renderClarificationOptions called:', {
      waitingForClarification,
      clarificationQuestionsLength: clarificationQuestions.length,
      clarificationQuestions: clarificationQuestions.map(q => q.id)
    });
    
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

  return (
    <div className="chat-window">
      <div className="chat-header">
        <div className="header-controls">
          <div className="agent-selector">
            <label htmlFor="agent-type">Agent:</label>
            <select 
              id="agent-type" 
              value={selectedAgent} 
              onChange={handleAgentChange}
              className="agent-select"
            >
              {AGENT_TYPES.map(agent => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          </div>
          
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
        </div>
      </div>
      
      <div className="chat-messages">
        {messages.map(message => (
          <div 
            key={message.id} 
            className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'} ${message.isError ? 'error-message' : ''} ${message.needsClarification ? 'clarification-message' : ''} ${message.isCombinedAnswers ? 'clarification-response-message' : ''} ${(message.hasQueryResults || message.hasGeneratedCode) ? 'query-results-message' : ''} ${message.isNewConversation ? 'new-conversation-message' : ''}`}
          >
            {message.isCombinedAnswers ? (
              <ClarificationResponseMessage content={message.content} />
            ) : (message.hasQueryResults || message.hasGeneratedCode) ? (
              <QueryAndResultsMessage 
                query={message.sparqlQuery}
                results={message.queryResults}
                error={message.queryError}
                generatedCode={message.generatedCode}
              />
            ) : message.needsClarification && waitingForClarification ? (
              // Don't show detailed clarification in chat when UI is active
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
        ))}
        
        {isLoading && (
          <div className="message assistant-message loading-message">
            <LoadingIndicator />
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {renderClarificationOptions()}
      
      <form className="chat-input-form" onSubmit={handleSubmit}>
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