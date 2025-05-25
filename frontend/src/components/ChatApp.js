import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import ChatWindow from './ChatWindow';
import './ChatApp.css';

// Helper to generate a simple unique id (timestamp based)
const generateId = () => `c_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;

const LOCAL_STORAGE_KEY = 'paleopal_conversations_v1';

const ChatApp = () => {
  // Load conversations from backend first, then fallback to localStorage
  const [conversations, setConversations] = useState(() => {
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch (err) {
      console.error('Error loading conversations from localStorage:', err);
    }
    // Fallback – create a single empty conversation
    const newConv = {
      id: generateId(),
      title: 'New Chat',
      messages: [],
      stateId: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    return [newConv];
  });

  const [activeId, setActiveId] = useState(conversations[0]?.id || null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Fetch conversations from backend on mount
  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const resp = await axios.get('/conversations');
        if (Array.isArray(resp.data) && resp.data.length) {
          setConversations(resp.data);
          setActiveId(resp.data[0].id);
        }
      } catch (err) {
        console.warn('Could not fetch conversations from backend, using localStorage', err);
      }
    };
    fetchConversations();
  }, []);

  // Persist conversations whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(conversations));
    } catch (err) {
      console.error('Error saving conversations to localStorage:', err);
    }
  }, [conversations]);

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
    const newConv = {
      id: generateId(),
      title: 'New Chat',
      messages: [],
      stateId: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    setConversations((prev) => [newConv, ...prev]);
    setActiveId(newConv.id);

    // Persist
    saveConversationToBackend(newConv);
  };

  // Delete conversation
  const handleDeleteConversation = async (convId) => {
    if (!window.confirm('Delete this conversation? This action cannot be undone.')) return;
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

  // Helper to POST/PUT conversation
  const saveConversationToBackend = async (conv) => {
    try {
      // Try PUT first; if 404 then POST
      await axios.put(`/conversations/${conv.id}`, conv);
    } catch (err) {
      if (err.response && err.response.status === 404) {
        try {
          await axios.post('/conversations', conv);
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
          <button className="new-chat-btn" onClick={handleNewChat} title="New Chat">+</button>
        </div>
        <ul className="conversation-list">
          {conversations.map((conv) => (
            <li key={conv.id} className={`conversation-item ${conv.id === activeId ? 'active' : ''}`}>
              <div
                className="conversation-click"
                onClick={() => {
                  setActiveId(conv.id);
                  setSidebarOpen(false);
                }}
                onDoubleClick={() => handleRenameConversation(conv.id)}
              >
                <span className="conversation-title">{conv.title && conv.title !== 'New Chat' ? conv.title : 'Untitled'}</span>
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
                title="Delete"
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
          <ChatWindow key={activeConversation.id} conversation={activeConversation} onConversationUpdate={handleConversationUpdate} />
        ) : (
          <div className="no-chat-selected">Select or start a conversation.</div>
        )}
      </main>
    </div>
  );
};

export default ChatApp;