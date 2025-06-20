import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ChatApp from './components/ChatApp';
import Dashboard from './components/Dashboard';

function App() {
  // Apply persisted dark mode preference on initial load (works on any route)
  useEffect(() => {
    const stored = localStorage.getItem('darkMode');
    const prefersDark = stored !== null ? JSON.parse(stored) : window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (prefersDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  return (
    <div className="h-screen w-screen overflow-hidden">
      <Router>
        <Routes>
          <Route path="/" element={<ChatApp />} />
          <Route path="/chat/:conversationId" element={<ChatApp />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </Router>
    </div>
  );
}

export default App; 