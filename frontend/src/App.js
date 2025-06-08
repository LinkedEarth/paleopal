import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ChatApp from './components/ChatApp';
import Dashboard from './components/Dashboard';

function App() {
  return (
    <div className="h-screen w-screen overflow-hidden">
      <Router>
        <Routes>
          <Route path="/" element={<ChatApp />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </Router>
    </div>
  );
}

export default App; 