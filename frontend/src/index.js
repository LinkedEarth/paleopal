import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

// React Query setup
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Create a client with default options (can be customized later)
const queryClient = new QueryClient();

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
); 