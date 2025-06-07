import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import ChatWindow from './ChatWindow';
import { testApiConnectivity } from '../config/api';

// Configure axios defaults
axios.defaults.baseURL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

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
        const resp = await axios.get('/conversations/');
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
      await axios.delete(`/conversations/${convId}`);
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
        await axios.put(`/conversations/${conv.id}`, clean);
        return;
      }

      await axios.put(`/conversations/${conv.id}`, clean);
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
            await axios.post('/conversations', clean);
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
    <div className="flex h-screen w-screen overflow-hidden font-sans relative">
      {/* Mobile toggle button */}
      <button 
        className="fixed top-2.5 left-2.5 z-50 bg-gray-800 text-gray-200 border-none w-9 h-9 text-lg rounded-md cursor-pointer md:hidden"
        onClick={() => setSidebarOpen((o) => !o)}
      >
        ☰
      </button>

      {/* Sidebar */}
      <aside className={`fixed left-0 top-0 bottom-0 w-80 bg-gray-800 text-gray-200 flex flex-col transition-transform duration-300 ease-in-out z-50 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <h2 className="text-lg font-semibold m-0">Conversations</h2>
          <button 
            className="bg-green-600 border-none text-white w-8 h-8 rounded text-xl leading-8 cursor-pointer transition-colors duration-200 hover:bg-green-700 disabled:bg-gray-500 disabled:cursor-not-allowed disabled:opacity-60"
            onClick={handleNewChat}
            title="New Chat"
          >
            +
          </button>
        </div>
        <ul className="list-none p-0 m-0 overflow-y-auto overflow-x-hidden flex-1">
          {conversations.map((conv) => (
            <li key={conv.id} className={`relative flex items-center border-b border-white/5 transition-colors duration-150 min-h-12 group ${conv.id === activeId ? 'bg-gray-700' : 'hover:bg-white/5'} ${conv.isLoading ? 'bg-yellow-500/20 border-l-3 border-yellow-500' : ''}`}>
              <div
                className="flex-1 flex items-center gap-2 py-3 px-2 pl-4 cursor-pointer rounded-lg transition-colors duration-200 min-w-0 overflow-hidden hover:bg-white/10"
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
                <span className={`flex-1 text-sm leading-tight overflow-hidden text-ellipsis whitespace-nowrap min-w-0 ${conv.isLoading ? 'text-yellow-500 font-medium' : 'text-gray-200'}`}>
                  {conv.title && conv.title !== 'New Chat' ? conv.title : 'Untitled'}
                </span>
                {conv.isLoading && (
                  <div className="flex items-center gap-1 ml-1 flex-shrink-0">
                    <span className="text-xs ml-1 animate-pulse flex-shrink-0">⏳</span>
                    {/* Show clear loading button if conversation has been loading for more than 2 minutes */}
                    {conv.updatedAt && (Date.now() - new Date(conv.updatedAt).getTime()) > 2 * 60 * 1000 && (
                      <button
                        className="bg-transparent border-none text-xs cursor-pointer p-0.5 rounded opacity-70 transition-all duration-200 flex-shrink-0 hover:bg-yellow-500/20 hover:opacity-100"
                        title="Clear stuck loading state"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleClearStuckLoading(conv.id);
                        }}
                      >
                        ⚠️
                      </button>
                    )}
                  </div>
                )}
              </div>
              <button
                className="bg-transparent border-none text-xs cursor-pointer p-1 rounded opacity-0 transition-all duration-200 ml-0.5 text-gray-400 flex-shrink-0 w-6 h-6 flex items-center justify-center hover:bg-white/10 hover:text-white group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-30"
                title="Rename"
                onClick={(e) => {
                  e.stopPropagation();
                  handleRenameConversation(conv.id);
                }}
              >✏️</button>
              <button
                className="bg-transparent border-none text-xs cursor-pointer p-1 rounded opacity-0 transition-all duration-200 ml-0.5 text-gray-400 flex-shrink-0 w-6 h-6 flex items-center justify-center hover:bg-white/10 hover:text-white group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-30"
                title={conv.isLoading ? "Force delete (cancels current request)" : "Delete"}
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteConversation(conv.id);
                }}
              >🗑</button>
            </li>
          ))}
        </ul>
      </aside>

      {/* Main Chat Window */}
      <main className="ml-0 w-full bg-gray-100 flex flex-col h-screen overflow-hidden md:ml-80 md:w-[calc(100vw-320px)]" onClick={() => sidebarOpen && setSidebarOpen(false)}>
        {activeConversation ? (
          <ChatWindow conversation={activeConversation} onConversationUpdate={handleConversationUpdate} />
        ) : (
          <div className="m-auto text-xl text-gray-600">Select or start a conversation.</div>
        )}
      </main>
    </div>
  );
};

export default ChatApp;