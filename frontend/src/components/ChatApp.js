import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import ChatWindow from './ChatWindow';
import { testApiConnectivity } from '../config/api';
import API_CONFIG from '../config/api';

// Configure axios defaults
axios.defaults.baseURL = process.env.REACT_APP_API_URL || 
                         (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000');

// Helper to generate a simple unique id (timestamp based)
const generateId = () => `c_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

const ChatApp = () => {
  // Conversations will be loaded from backend; start with empty list
  const [conversations, setConversations] = useState([]);

  const [activeId, setActiveId] = useState(conversations[0]?.id || null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Track which conversations have been persisted to backend to avoid duplicate POSTs
  const persistedIdsRef = React.useRef(new Set());
  const savingIdsRef = React.useRef(new Set());

  // Fetch conversations from backend on mount (fallback to a new one on error/empty)
  useEffect(() => {
    const fetchConversations = async () => {
      // Test API connectivity first
      console.log('🧪 Testing API connectivity before fetching conversations...');
      const isConnected = await testApiConnectivity();
      if (!isConnected) {
        console.error('❌ Cannot connect to API, skipping conversation fetch');
        return;
      }
      
      try {
        console.log('🔍 Fetching conversations from backend...');
        console.log('📍 Axios base URL:', axios.defaults.baseURL);
        const resp = await axios.get(API_CONFIG.ENDPOINTS.CONVERSATIONS);
        console.log('✅ Conversations response:', resp);
        console.log('📝 Conversations data:', resp.data);
        
        if (Array.isArray(resp.data) && resp.data.length) {
          console.log(`✅ Found ${resp.data.length} conversations`);
          setConversations(resp.data);
          setActiveId(resp.data[0].id);
          return;
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
        if (exists) {
          return prev.map((c) => (c.id === updatedConv.id ? { ...exists, ...updatedConv, updatedAt: new Date().toISOString() } : c));
        }
        // New conversation (should not happen here but fallback)
        return [...prev, { ...updatedConv, updatedAt: new Date().toISOString() }];
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
      enableClarification: false,
      clarificationThreshold: 'conservative',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    setConversations((prev) => [newConv, ...prev]);
    setActiveId(newConv.id);

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
    
    try {
      await axios.delete(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/${convId}`);
    } catch (err) {
      console.error('Failed to delete conversation on backend', err);
    }
    
    setConversations((prev) => prev.filter((c) => c.id !== convId));
    
    // Reset activeId if needed
    if (activeId === convId) {
      const remaining = conversations.filter((c) => c.id !== convId);
      setActiveId(remaining[0]?.id || null);
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
      const clean = {
        id: conv.id,
        title: conv.title,
        agent_type: conv.agent_type || conv.selectedAgent || 'unknown',
        messages: filteredMessages,
        created_at: conv.createdAt || conv.created_at || new Date().toISOString(),
        updated_at: conv.updatedAt || conv.updated_at || new Date().toISOString(),
        status: conv.status || 'active',
        context: conv.context || {}
      };

      // If we've already POSTed this conversation before, skip straight to PUT
      if (persistedIdsRef.current.has(conv.id)) {
        await axios.put(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/${conv.id}`, clean);
        return;
      }

      await axios.put(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/${conv.id}`, clean);
    } catch (err) {
      if (err.response && (err.response.status === 404 || err.response.status === 422)) {
        try {
          const filteredMessages = (conv.messages || []).filter(m => !m.isNodeProgress);
          const clean = {
            id: conv.id,
            title: conv.title,
            agent_type: conv.agent_type || conv.selectedAgent || 'unknown',
            messages: filteredMessages,
            created_at: conv.createdAt || conv.created_at || new Date().toISOString(),
            updated_at: conv.updatedAt || conv.updated_at || new Date().toISOString(),
            status: conv.status || 'active',
            context: conv.context || {}
          };

          if (!persistedIdsRef.current.has(conv.id)) {
            await axios.post(API_CONFIG.ENDPOINTS.CONVERSATIONS, clean);
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
    <div className="flex h-screen w-screen overflow-hidden font-sans relative bg-gray-100">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden transition-opacity duration-300"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`fixed left-0 top-0 bottom-0 w-80 bg-white border-r border-gray-200 flex flex-col transition-transform duration-300 ease-in-out z-40 shadow-xl md:shadow-none ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-gray-50/80 backdrop-blur-sm">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-gray-900">Conversations</h2>
          </div>
          <div className="flex items-center space-x-2">
          <button 
              className="w-9 h-9 bg-blue-600 hover:bg-blue-700 text-white rounded-lg flex items-center justify-center transition-colors duration-200 shadow-sm hover:shadow-md group"
            onClick={handleNewChat}
            title="New Chat"
          >
              <svg className="w-5 h-5 transition-transform duration-200 group-hover:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
            {/* Close button for mobile */}
            <button
              className="w-9 h-9 bg-gray-600 hover:bg-gray-700 text-white rounded-lg md:hidden flex items-center justify-center transition-colors duration-200"
              onClick={() => setSidebarOpen(false)}
              title="Close sidebar"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
          </button>
          </div>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden">
          {conversations.length === 0 ? (
            <div className="p-6 text-center">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <p className="text-gray-500 text-sm">No conversations yet</p>
              <p className="text-gray-400 text-xs mt-1">Click the + button to start a new chat</p>
            </div>
          ) : (
            <ul className="list-none p-2 m-0 space-y-1">
          {conversations.map((conv) => (
                <li key={conv.id} className="relative group">
                  <div
                    className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all duration-200 ${
                      conv.id === activeId 
                        ? 'bg-blue-50 border border-blue-200 shadow-sm' 
                        : 'hover:bg-gray-50 border border-transparent'
                    } ${
                      conv.isLoading 
                        ? 'bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200' 
                        : ''
                    }`}
                onClick={() => {
                  // Warn if switching away from a conversation with an active request
                  if (hasActiveRequest && conv.id !== activeId) {
                    const shouldSwitch = window.confirm(
                      'The current conversation is processing a request. ' +
                      'Switching away may interrupt the process. Continue?'
                    );
                    if (!shouldSwitch) return;
                  }
                  setActiveId(conv.id);
                  setSidebarOpen(false);
                }}
                onDoubleClick={() => handleRenameConversation(conv.id)}
                title={conv.isLoading && conv.id !== activeId ? "Click to switch (will warn about active request)" : ""}
              >
                    {/* Conversation Icon */}
                    <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${
                      conv.id === activeId 
                        ? 'bg-blue-100 text-blue-600' 
                        : conv.isLoading 
                        ? 'bg-amber-100 text-amber-600' 
                        : 'bg-gray-100 text-gray-500'
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
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <h3 className={`text-sm font-medium truncate ${
                          conv.id === activeId ? 'text-blue-900' : 'text-gray-900'
                        }`}>
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
                          conv.id === activeId ? 'text-blue-600' : 'text-gray-500'
                        }`}>
                          {conv.messages && conv.messages.length > 0 
                            ? `${conv.messages.length} message${conv.messages.length === 1 ? '' : 's'}`
                            : 'No messages yet'
                          }
                        </p>
                        <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                          <button
                            className="w-7 h-7 bg-gray-100 hover:bg-gray-200 text-gray-600 hover:text-gray-800 rounded-md flex items-center justify-center transition-colors duration-200"
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
                            className="w-7 h-7 bg-red-100 hover:bg-red-200 text-red-600 hover:text-red-800 rounded-md flex items-center justify-center transition-colors duration-200"
                            title={conv.isLoading ? "Force delete (cancels current request)" : "Delete"}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteConversation(conv.id);
                            }}
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Loading indicator with clear button for stuck states */}
                    {conv.isLoading && conv.updatedAt && (Date.now() - new Date(conv.updatedAt).getTime()) > 2 * 60 * 1000 && (
                      <button
                        className="absolute top-2 right-2 w-6 h-6 bg-amber-100 hover:bg-amber-200 text-amber-600 hover:text-amber-800 rounded-full flex items-center justify-center transition-colors duration-200 text-xs"
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
          )}
        </div>
        
        {/* Dashboard Link at bottom */}
        <div className="border-t border-gray-200 p-4 bg-gray-50/50">
          <Link
            to="/dashboard"
            className="flex items-center gap-3 w-full text-left px-4 py-3 rounded-xl text-sm text-gray-700 hover:bg-white hover:text-gray-900 transition-all duration-200 border border-transparent hover:border-gray-200 hover:shadow-sm group"
          >
            <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-600 rounded-lg flex items-center justify-center group-hover:scale-105 transition-transform duration-200">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <div>
              <div className="font-medium">Libraries Dashboard</div>
              <div className="text-xs text-gray-500">Browse paleoclimate data</div>
            </div>
            <svg className="w-4 h-4 text-gray-400 ml-auto group-hover:text-gray-600 transition-colors duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      </aside>

      {/* Main Chat Window */}
      <main className="ml-0 w-full bg-gray-100 flex flex-col h-screen overflow-hidden md:ml-80 md:w-[calc(100vw-320px)] transition-all duration-300" onClick={() => sidebarOpen && setSidebarOpen(false)}>
        {/* Mobile header with menu button */}
        <div className="md:hidden bg-white border-b border-gray-200 p-6 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center cursor-pointer" onClick={() => setSidebarOpen(true)}>
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h1 className="text-lg font-semibold text-gray-900">Conversations</h1>
          </div>
          <button 
            className="w-9 h-9 bg-blue-600 hover:bg-blue-700 text-white rounded-lg flex items-center justify-center transition-colors duration-200 shadow-sm hover:shadow-md group"
            onClick={handleNewChat}
            title="New Chat"
          >
            <svg className="w-5 h-5 transition-transform duration-200 group-hover:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>
        
        <div className="flex-1 flex flex-col overflow-hidden">
        {activeConversation ? (
          <ChatWindow conversation={activeConversation} onConversationUpdate={handleConversationUpdate} />
        ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="w-24 h-24 bg-gray-200 rounded-full flex items-center justify-center mx-auto mb-6">
                  <svg className="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">Welcome to PaleoPal</h3>
                <p className="text-gray-600 mb-6">Select a conversation or start a new chat to begin</p>
                <button
                  onClick={handleNewChat}
                  className="inline-flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors duration-200 shadow-sm hover:shadow-md"
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