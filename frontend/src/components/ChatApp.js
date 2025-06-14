import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import ChatWindow from './ChatWindow';
import ServerStatus from './ServerStatus';
import { testApiConnectivity } from '../config/api';
import API_CONFIG from '../config/api';
import THEME from '../styles/colorTheme';

// Configure axios defaults
axios.defaults.baseURL = process.env.REACT_APP_API_URL || 
                         (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000');

// Helper to generate a simple unique id (timestamp based)
const generateId = () => `c_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

const ChatApp = () => {
  // Conversations will be loaded from backend; start with empty list
  const [conversations, setConversations] = useState([]);
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [deletingConversations, setDeletingConversations] = useState(new Set());

  const [activeId, setActiveId] = useState(conversations[0]?.id || null);
  
  // Responsive sidebar state management
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  // Dark mode toggle functionality
  const [isDarkMode, setIsDarkMode] = useState(() => {
    // Check localStorage or system preference
    const stored = localStorage.getItem('darkMode');
    if (stored !== null) {
      return JSON.parse(stored);
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  // Apply dark mode to document
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('darkMode', JSON.stringify(isDarkMode));
  }, [isDarkMode]);

  const toggleDarkMode = () => {
    setIsDarkMode(!isDarkMode);
  };

  // Track which conversations have been persisted to backend to avoid duplicate POSTs
  const persistedIdsRef = React.useRef(new Set());
  const savingIdsRef = React.useRef(new Set());

  // Auto-close sidebar on mobile and detect screen size changes
  useEffect(() => {
    const checkIsMobile = () => {
      const mobile = window.innerWidth < 1024;
      setIsMobile(mobile);
      if (mobile) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };
    
    checkIsMobile();
    window.addEventListener('resize', checkIsMobile);
    return () => window.removeEventListener('resize', checkIsMobile);
  }, []);

  // Fetch conversations from backend on mount (fallback to a new one on error/empty)
  useEffect(() => {
    const fetchConversations = async () => {
      setConversationsLoading(true);
      
      // Test API connectivity first
      // console.log('🧪 Testing API connectivity before fetching conversations...');
      const isConnected = await testApiConnectivity();
      if (!isConnected) {
        console.error('❌ Cannot connect to API, skipping conversation fetch');
        setConversationsLoading(false);
        return;
      }
      
      try {
        // console.log('🔍 Fetching conversations from backend...');
        // console.log('📍 Axios base URL:', axios.defaults.baseURL);
        const resp = await axios.get(API_CONFIG.ENDPOINTS.CONVERSATIONS);
        // console.log('✅ Conversations response:', resp);
        // console.log('📝 Conversations data:', resp.data);
        
        if (Array.isArray(resp.data) && resp.data.length) {
          // console.log(`✅ Found ${resp.data.length} conversations`);
          // Sort conversations by updated_at then created_at in descending order (latest first)
          const sortedConversations = resp.data.sort((a, b) => 
            new Date(b.updated_at || b.updatedAt || b.created_at) - new Date(a.updated_at || a.updatedAt || a.created_at)
          );
          setConversations(sortedConversations);
          setActiveId(sortedConversations[0].id);
        } else {
          console.log('⚠️ No conversations found in response');
        }
      } catch (err) {
        console.error('❌ Could not fetch conversations from backend', err);
        console.error('❌ Error details:', {
          message: err.message,
          config: err.config,
          response: err.response
        });
      } finally {
        setConversationsLoading(false);
      }

      // // Backend returned no conversations or failed – start a fresh one locally (will POST on first save)
      // const newConv = {
      //   id: generateId(),
      //   title: 'New Chat',
      //   messages: [],
      //   stateId: null,
      //   createdAt: new Date().toISOString(),
      //   updatedAt: new Date().toISOString()
      // };
      // setConversations([newConv]);
      // setActiveId(newConv.id);
    };
    fetchConversations();
  }, []);

  // Callback to receive updates from ChatWindow
  const handleConversationUpdate = useCallback(
    (updatedConv) => {
      setConversations((prev) => {
        const exists = prev.find((c) => c.id === updatedConv.id);
        let updatedConversations;
        if (exists) {
          updatedConversations = prev.map((c) => (c.id === updatedConv.id ? { ...exists, ...updatedConv, updatedAt: new Date().toISOString() } : c));
        } else {
          // New conversation (should not happen here but fallback)
          updatedConversations = [...prev, { ...updatedConv, updatedAt: new Date().toISOString() }];
        }
        
        // Sort conversations by updated_at then created_at in descending order (latest first)
        return updatedConversations.sort((a, b) => 
          new Date(b.updated_at || b.updatedAt || b.created_at) - new Date(a.updated_at || a.updatedAt || a.created_at)
        );
      });

      // Persist to backend only if the conversation is not currently loading
      if (!updatedConv.isLoading) {
        saveConversationToBackend(updatedConv);
      }
    },
    []
  );

  const handleNewChat = () => {
    // Warn if there's a current active conversation with a request
    const currentConv = conversations.find(c => c.id === activeId);
    if (currentConv && currentConv.isLoading) {
      const shouldContinue = window.confirm(
        'The current conversation is processing a request. ' +
        'Creating a new chat may interrupt the process. Continue?'
      );
      if (!shouldContinue) return;
    }

    const newConv = {
      id: generateId(),
      title: 'New Chat',
      messages: [],
      waitingForClarification: false,
      clarificationQuestions: [],
      clarificationAnswers: {},
      llmProvider: 'google',
      selectedAgent: 'sparql',
      isLoading: false,
      error: null,
      enableClarification: true,
      clarificationThreshold: 'conservative',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    setConversations((prev) => [newConv, ...prev]);
    setActiveId(newConv.id);

    // Auto-close sidebar on mobile when creating new chat
    if (isMobile) {
      setSidebarOpen(false);
    }

    // Persist
    saveConversationToBackend(newConv);
  };

  // Delete conversation
  const handleDeleteConversation = async (convId, force = false) => {
    const conv = conversations.find(c => c.id === convId);
    if (!conv) return;
    
    // If conversation is loading and not forced, show confirmation
    if (conv.isLoading && !force) {
      const shouldForceDelete = window.confirm(
        'This conversation is currently processing a request. ' +
        'Deleting it will cancel the request. Are you sure you want to continue?'
      );
      if (!shouldForceDelete) return;
    } else if (!force) {
      if (!window.confirm('Delete this conversation? This action cannot be undone.')) return;
    }
    
    // Set loading state for this conversation
    setDeletingConversations(prev => new Set([...prev, convId]));
    
    try {
      await axios.delete(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/${convId}`);
      
      // Remove from conversations list on success
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      
      // Reset activeId if needed
      if (activeId === convId) {
        const remaining = conversations.filter((c) => c.id !== convId);
        setActiveId(remaining[0]?.id || null);
      }
    } catch (err) {
      console.error('Failed to delete conversation on backend', err);
      // You might want to show an error message to the user here
    } finally {
      // Remove loading state
      setDeletingConversations(prev => {
        const newSet = new Set(prev);
        newSet.delete(convId);
        return newSet;
      });
    }
  };

  // Add a function to clear stuck loading states
  const handleClearStuckLoading = (convId) => {
    setConversations((prev) => 
      prev.map((c) => 
        c.id === convId 
          ? { ...c, isLoading: false, waitingForClarification: false }
          : c
      )
    );
  };

  // Add a timeout mechanism to automatically clear stuck loading states
  useEffect(() => {
    const checkStuckRequests = () => {
      setConversations((prev) => 
        prev.map((conv) => {
          // If a conversation has been loading for more than 5 minutes, clear it
          if (conv.isLoading && conv.updatedAt) {
            const timeSinceUpdate = Date.now() - new Date(conv.updatedAt).getTime();
            const fiveMinutes = 5 * 60 * 1000;
            
            if (timeSinceUpdate > fiveMinutes) {
              console.warn(`Clearing stuck loading state for conversation ${conv.id}`);
              return { 
                ...conv, 
                isLoading: false, 
                waitingForClarification: false,
                updatedAt: new Date().toISOString()
              };
            }
          }
          return conv;
        })
      );
    };

    // Check for stuck requests every minute
    const interval = setInterval(checkStuckRequests, 60000);
    
    return () => clearInterval(interval);
  }, []);

  // Rename conversation
  const handleRenameConversation = async (convId) => {
    const conv = conversations.find((c) => c.id === convId);
    if (!conv) return;
    const newTitle = window.prompt('Rename conversation', conv.title || 'Untitled');
    if (!newTitle || newTitle.trim() === '' || newTitle === conv.title) return;
    const updated = { ...conv, title: newTitle.trim() };
    saveConversationToBackend(updated);
    setConversations((prev) => prev.map((c) => (c.id === convId ? updated : c)));
  };

  const activeConversation = conversations.find((c) => c.id === activeId);
  
  // Check if there's an active request in progress
  const hasActiveRequest = activeConversation && activeConversation.isLoading;

  // Helper to POST/PUT conversation
  const saveConversationToBackend = async (conv) => {
    // Avoid concurrent saves for the same conversation
    if (savingIdsRef.current.has(conv.id)) {
      return;
    }

    try {
      savingIdsRef.current.add(conv.id);
      // Try PUT first; if 404 then POST
      const filteredMessages = (conv.messages || []).filter(m => !m.isNodeProgress);
      // For PUT requests, only send ConversationUpdate fields
      const updateData = {
        title: conv.title,
        llm_provider: conv.llmProvider || conv.llm_provider || 'google',
        selected_agent: conv.selectedAgent || conv.selected_agent || 'sparql',
        enable_clarification: conv.enableClarification !== undefined ? conv.enableClarification : (conv.enable_clarification !== undefined ? conv.enable_clarification : true),
        clarification_threshold: conv.clarificationThreshold || conv.clarification_threshold || 'conservative',
        waiting_for_clarification: conv.waitingForClarification || conv.waiting_for_clarification || false,
        clarification_questions: conv.clarificationQuestions || conv.clarification_questions || [],
        clarification_answers: conv.clarificationAnswers || conv.clarification_answers || {},
        original_request: conv.originalRequestContext || conv.original_request || null,
        metadata: conv.metadata || null
      };

      // If we've already POSTed this conversation before, skip straight to PUT
      if (persistedIdsRef.current.has(conv.id)) {
        await axios.put(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/${conv.id}`, updateData);
        return;
      }

      await axios.put(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/${conv.id}`, updateData);
    } catch (err) {
      if (err.response && (err.response.status === 404 || err.response.status === 422)) {
        try {
          const filteredMessages = (conv.messages || []).filter(m => !m.isNodeProgress);
          // For POST requests, use ConversationCreate schema
          const createData = {
            id: conv.id,
            title: conv.title,
            llm_provider: conv.llmProvider || conv.llm_provider || 'google',
            selected_agent: conv.selectedAgent || conv.selected_agent || 'sparql',
            enable_clarification: conv.enableClarification !== undefined ? conv.enableClarification : (conv.enable_clarification !== undefined ? conv.enable_clarification : true),
            clarification_threshold: conv.clarificationThreshold || conv.clarification_threshold || 'conservative',
            metadata: conv.metadata || null
          };

          if (!persistedIdsRef.current.has(conv.id)) {
            await axios.post(API_CONFIG.ENDPOINTS.CONVERSATIONS, createData);
            // Mark as persisted to prevent future duplicate POSTs
            persistedIdsRef.current.add(conv.id);
          }
        } catch (postErr) {
          console.error('Failed to save conversation (POST)', postErr);
        }
      } else {
        console.error('Failed to save conversation (PUT)', err);
      }
    } finally {
      savingIdsRef.current.delete(conv.id);
    }
  };

  return (
    <div className={`flex h-screen ${THEME.containers.background} ${THEME.text.primary}`}>
      {/* Mobile overlay */}
      {sidebarOpen && isMobile && (
        <div 
          className="fixed inset-0 bg-slate-900 bg-opacity-50 z-20 lg:hidden transition-opacity duration-300"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
              <aside className={`fixed lg:relative w-64 lg:w-72 h-full ${THEME.containers.card} border-r ${THEME.borders.default} flex flex-col transition-transform duration-300 z-30 shadow-md ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0`}>
        {/* Sidebar Header */}
        <div className="flex-shrink-0 p-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gradient-to-br from-emerald-600 to-emerald-800 dark:from-emerald-500 dark:to-emerald-700 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h2 className={`text-lg font-semibold ${THEME.text.primary}`}>PaleoPal</h2>
            </div>
            {/* Close button for mobile */}
            <button
              className={`w-8 h-8 rounded-lg lg:hidden flex items-center justify-center ${THEME.text.secondary} ${THEME.interactive.hover} transition-colors duration-200`}
              onClick={() => setSidebarOpen(false)}
              title="Close sidebar"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          {/* New Chat Button */}
          <button 
            className={`w-full flex items-center justify-center gap-2 px-4 py-3 ${THEME.buttons.primary} rounded-lg transition-colors duration-200 group`}
            onClick={handleNewChat}
          >
            <svg className="w-5 h-5 transition-transform duration-200 group-hover:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span className="font-medium">New Chat</span>
          </button>
        </div>

        {/* Conversations Section */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden">
          <div className="px-4 py-3">
            <h3 className={`text-xs font-semibold ${THEME.text.tertiary} uppercase tracking-wider mb-3`}>
              Recent Conversations
            </h3>
          </div>
          {conversationsLoading ? (
            <div className="p-6 text-center">
              <div className={`w-16 h-16 ${THEME.containers.secondary} rounded-full flex items-center justify-center mx-auto mb-4`}>
                <svg className={`w-8 h-8 ${THEME.text.secondary} animate-spin`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <p className={`${THEME.text.primary} text-sm font-medium`}>Loading conversations...</p>
              <p className={`${THEME.text.tertiary} text-xs mt-1`}>Fetching your chat history</p>
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-6 text-center">
              <div className={`w-16 h-16 ${THEME.containers.secondary} rounded-full flex items-center justify-center mx-auto mb-4`}>
                <svg className={`w-8 h-8 ${THEME.text.tertiary}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <p className={`${THEME.text.secondary} text-sm`}>No conversations yet</p>
              <p className={`${THEME.text.tertiary} text-xs mt-1`}>Click the + button to start a new chat</p>
            </div>
          ) : (
            <div className="px-4 pb-4">
              <ul className="list-none m-0 space-y-1">
          {conversations.map((conv) => (
                <li key={conv.id} className="relative group">
                  <div
                    className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all duration-200 ${
                      conv.id === activeId 
                        ? `${THEME.status.info.background} border ${THEME.status.info.border} shadow-sm` 
                        : `${THEME.interactive.hover} border border-transparent`
                    } ${
                      conv.isLoading 
                        ? `${THEME.status.warning.background} border ${THEME.status.warning.border}` 
                        : ''
                    }`}
                    onClick={() => {
                      setActiveId(conv.id);
                      // Auto-close sidebar on mobile when selecting conversation
                      if (isMobile) {
                        setSidebarOpen(false);
                      }
                    }}
                    onDoubleClick={() => handleRenameConversation(conv.id)}
                    title={conv.isLoading && conv.id !== activeId ? "Click to switch" : ""}
                  >
                    {/* Conversation Icon */}
                    <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${
                      conv.id === activeId 
                        ? `${THEME.status.info.background} ${THEME.status.info.text}` 
                        : conv.isLoading 
                        ? `${THEME.status.warning.background} ${THEME.status.warning.text}` 
                        : `${THEME.containers.secondary} ${THEME.text.tertiary}`
                    }`}>
                      {conv.isLoading ? (
                        <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                        </svg>
                      )}
                    </div>

                    {/* Conversation Details */}
                    <div className="flex-1 min-w-0 relative">
                      {/* Deletion overlay */}
                      {deletingConversations.has(conv.id) && (
                        <div className={`absolute inset-0 ${THEME.status.error.background} bg-opacity-90 flex items-center justify-center rounded z-10`}>
                          <div className={`flex items-center gap-2 ${THEME.status.error.text}`}>
                            <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span className="text-sm font-medium">Deleting conversation...</span>
                          </div>
                        </div>
                      )}
                      
                      <div className="flex items-center justify-between">
                        <h3 className={`text-sm font-medium truncate ${
                          conv.id === activeId ? THEME.status.info.text : THEME.text.primary
                        } ${deletingConversations.has(conv.id) ? 'opacity-50' : ''}`}>
                  {conv.title && conv.title !== 'New Chat' ? conv.title : 'Untitled'}
                        </h3>
                {conv.isLoading && (
                          <div className="flex items-center space-x-1 ml-2">
                            <div className="w-2 h-2 bg-amber-400 rounded-full animate-pulse"></div>
                            <div className="w-2 h-2 bg-amber-400 rounded-full animate-pulse" style={{animationDelay: '0.2s'}}></div>
                            <div className="w-2 h-2 bg-amber-400 rounded-full animate-pulse" style={{animationDelay: '0.4s'}}></div>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center justify-between mt-1">
                        <p className={`text-xs truncate ${
                          conv.id === activeId ? THEME.status.info.text : THEME.text.secondary
                        } ${deletingConversations.has(conv.id) ? 'opacity-50' : ''}`}>
                          {conv.updated_at || conv.updatedAt 
                            ? new Date(conv.updated_at || conv.updatedAt).toLocaleString()
                            : conv.created_at 
                            ? new Date(conv.created_at).toLocaleString()
                            : 'Recently created'
                          }
                        </p>
                        <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                          <button
                            className={`w-7 h-7 ${THEME.buttons.secondary} rounded-md flex items-center justify-center transition-colors duration-200`}
                            title="Rename"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRenameConversation(conv.id);
                            }}
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            className={`w-7 h-7 rounded-md flex items-center justify-center transition-colors duration-200 ${
                              deletingConversations.has(conv.id)
                                ? `${THEME.status.error.background} ${THEME.status.error.text} cursor-not-allowed`
                                : THEME.buttons.danger
                            }`}
                            title={deletingConversations.has(conv.id) ? "Deleting..." : conv.isLoading ? "Force delete (cancels current request)" : "Delete"}
                            disabled={deletingConversations.has(conv.id)}
                            onClick={(e) => {
                              e.stopPropagation();
                              if (!deletingConversations.has(conv.id)) {
                                handleDeleteConversation(conv.id);
                              }
                            }}
                          >
                            {deletingConversations.has(conv.id) ? (
                              <svg className="w-3.5 h-3.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            ) : (
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            )}
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Loading indicator with clear button for stuck states */}
                    {conv.isLoading && (conv.updated_at || conv.updatedAt) && (Date.now() - new Date(conv.updated_at || conv.updatedAt).getTime()) > 2 * 60 * 1000 && (
                      <button
                        className={`absolute top-2 right-2 w-6 h-6 ${THEME.status.warning.background} ${THEME.status.warning.text} hover:bg-amber-200 hover:text-amber-800 rounded-full flex items-center justify-center transition-colors duration-200 text-xs`}
                        title="Clear stuck loading state"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleClearStuckLoading(conv.id);
                        }}
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}
                  </div>
                </li>
          ))}
              </ul>
            </div>
          )}
        </div>

        {/* Footer Section */}
        <div className="flex-shrink-0 px-4 py-3 border-t border-slate-200 dark:border-slate-700">
          <div className="space-y-2">
            {/* Dark/Light Mode Toggle */}
            <button
              onClick={toggleDarkMode}
              className={`w-full flex items-center gap-3 px-3 py-2 text-sm ${THEME.text.primary} ${THEME.interactive.hover} rounded-lg transition-colors duration-200`}
            >
              <div className="w-5 h-5">
                {isDarkMode ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                )}
              </div>
              <span className="flex-1 text-left">{isDarkMode ? 'Light Mode' : 'Dark Mode'}</span>
            </button>
            
            {/* Dashboard Link */}
            <Link
              to="/dashboard"
              className={`w-full flex items-center gap-3 px-3 py-2 text-sm ${THEME.text.primary} ${THEME.interactive.hover} rounded-lg transition-colors duration-200`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              <span className="flex-1 text-left">Libraries Dashboard</span>
            </Link>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className={`flex-1 flex flex-col overflow-hidden ${THEME.containers.background}`}>
        {/* Header Component */}
        <header className={`sticky top-0 z-10 ${THEME.containers.card} border-b border-slate-200 dark:border-slate-700 flex items-center justify-between px-4 py-3`}>
          {/* Mobile: Hamburger menu + title */}
          <div className="flex items-center gap-3 lg:hidden">
            <button
              className={`w-9 h-9 ${THEME.buttons.secondary} rounded-lg flex items-center justify-center transition-colors duration-200`}
              onClick={() => setSidebarOpen(true)}
              title="Open sidebar"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <h1 className={`text-lg font-semibold ${THEME.text.primary}`}>PaleoPal</h1>
          </div>

          {/* Desktop: Title + search bar */}
          <div className="hidden lg:flex items-center gap-4">
            <h1 className={`text-lg font-semibold ${THEME.text.primary}`}>
              {activeConversation?.title || 'PaleoPal Chat'}
            </h1>
          </div>

          {/* User actions */}
          <div className="flex items-center gap-2">
            {/* Server Status */}
            <ServerStatus />
            
            {/* Theme toggle for mobile */}
            <button
              onClick={toggleDarkMode}
              className={`w-9 h-9 ${THEME.buttons.secondary} rounded-lg flex items-center justify-center transition-colors duration-200 lg:hidden`}
              title={isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {isDarkMode ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              )}
            </button>
          </div>
        </header>
        
        {/* Scrollable Main Content */}
        <div 
          className="flex-1 flex flex-col overflow-hidden" 
          onClick={() => isMobile && sidebarOpen && setSidebarOpen(false)}
        >
        {conversationsLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className={`w-16 h-16 ${THEME.containers.secondary} rounded-full flex items-center justify-center mx-auto mb-4`}>
                <svg className={`w-8 h-8 animate-spin ${THEME.text.secondary}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className={`text-lg font-medium ${THEME.text.primary} mb-2`}>Loading conversations...</h3>
              <p className={THEME.text.secondary}>Please wait while we fetch your chat history</p>
            </div>
          </div>
        ) : activeConversation ? (
          <ChatWindow 
            conversation={activeConversation} 
            onConversationUpdate={handleConversationUpdate}
            isDarkMode={isDarkMode}
          />
        ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className={`w-24 h-24 ${THEME.containers.secondary} rounded-full flex items-center justify-center mx-auto mb-6`}>
                  <svg className={`w-12 h-12 ${THEME.text.tertiary}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
                <h3 className={`text-xl font-semibold ${THEME.text.primary} mb-2`}>Welcome to PaleoPal</h3>
                <p className={`${THEME.text.secondary} mb-6`}>Select a conversation or start a new chat to begin</p>
                <button
                  onClick={handleNewChat}
                  className={`inline-flex items-center px-6 py-3 ${THEME.buttons.primary} font-medium rounded-lg transition-colors duration-200 shadow-sm hover:shadow-md`}
                >
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Start New Conversation
                </button>
              </div>
            </div>
        )}
        </div>
      </main>
    </div>
  );
};

export default ChatApp;