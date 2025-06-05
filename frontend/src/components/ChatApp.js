import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import ChatWindow from './ChatWindow';
import './ChatApp.css';

// Helper to generate a simple unique id (timestamp based)
const generateId = () => `c_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

const ChatApp = () => {
  // Conversations will be loaded from backend; start with empty list
  const [conversations, setConversations] = useState([]);

  const [activeId, setActiveId] = useState(conversations[0]?.id || null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Fetch conversations from backend on mount (fallback to a new one on error/empty)
  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const resp = await axios.get('/conversations');
        if (Array.isArray(resp.data) && resp.data.length) {
          setConversations(resp.data);
          setActiveId(resp.data[0].id);
          return;
        }
      } catch (err) {
        console.warn('Could not fetch conversations from backend', err);
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

      // Persist to backend
      saveConversationToBackend(updatedConv);
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
      stateId: null,
      // Explicitly reset all state properties to prevent carryover
      waitingForClarification: false,
      clarificationQuestions: [],
      clarificationAnswers: {},
      llmProvider: 'google',
      selectedAgent: 'workflow_manager',
      isLoading: false,
      error: null,
      messages: [],
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
    try {
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

          await axios.post('/conversations', clean);
        } catch (postErr) {
          console.error('Failed to save conversation (POST)', postErr);
        }
      } else {
        console.error('Failed to save conversation (PUT)', err);
      }
    }
  };

  return (
    <div className="chat-app-container">
      {/* Mobile toggle button */}
      <button className="sidebar-toggle" onClick={() => setSidebarOpen((o) => !o)}>
        ☰
      </button>

      {/* Sidebar */}
      <aside className={`chat-sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h2 className="sidebar-title">Conversations</h2>
          <button 
            className={`new-chat-btn`}
            onClick={handleNewChat}
            title="New Chat"
          >
            +
          </button>
        </div>
        <ul className="conversation-list">
          {conversations.map((conv) => (
            <li key={conv.id} className={`conversation-item ${conv.id === activeId ? 'active' : ''} ${conv.isLoading ? 'loading' : ''}`}>
              <div
                className="conversation-click"
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
                <span className="conversation-title">{conv.title && conv.title !== 'New Chat' ? conv.title : 'Untitled'}</span>
                {conv.isLoading && (
                  <div className="conversation-status">
                    <span className="conversation-loading-indicator">⏳</span>
                    {/* Show clear loading button if conversation has been loading for more than 2 minutes */}
                    {conv.updatedAt && (Date.now() - new Date(conv.updatedAt).getTime()) > 2 * 60 * 1000 && (
                      <button
                        className="clear-loading-btn"
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
                className="conversation-rename-btn"
                title="Rename"
                onClick={(e) => {
                  e.stopPropagation();
                  handleRenameConversation(conv.id);
                }}
              >✏️</button>
              <button
                className="conversation-delete-btn"
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
      <main className="chat-main" onClick={() => sidebarOpen && setSidebarOpen(false)}>
        {activeConversation ? (
          <ChatWindow conversation={activeConversation} onConversationUpdate={handleConversationUpdate} />
        ) : (
          <div className="no-chat-selected">Select or start a conversation.</div>
        )}
      </main>
    </div>
  );
};

export default ChatApp;