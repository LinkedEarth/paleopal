import React, { useState, useEffect } from 'react';
import { buildApiUrl } from '../config/api';
import { THEME } from '../styles/colorTheme';
import Icon from './Icon';

const ServerStatus = () => {
  const [status, setStatus] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchStatus = async () => {
    try {
      const response = await fetch(buildApiUrl('/api/status'));
      const data = await response.json();
      setStatus(data);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Failed to fetch server status:', error);
      setStatus({
        backend: { status: 'error' },
        qdrant: { status: 'error' },
        llm_providers: {}
      });
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  if (!status) {
    return (
      <div className={`flex items-center gap-2 text-sm ${THEME.text.muted}`}>
        <div className={`w-2 h-2 ${THEME.text.muted} rounded-full animate-pulse`}></div>
        <span>Loading...</span>
      </div>
    );
  }

  const getStatusColor = (statusValue) => {
    if (statusValue === 'healthy' || statusValue === 'connected') return 'bg-green-500';
    if (statusValue === 'error' || statusValue === 'connection failed') return 'bg-red-500';
    return 'bg-yellow-500';
  };

  const getStatusIcon = (statusValue) => {
    if (statusValue === 'healthy' || statusValue === 'connected') return '✓';
    if (statusValue === 'error' || statusValue === 'connection failed') return '✗';
    return '?';
  };

  const connectedLLMs = Object.entries(status.llm_providers || {})
    .filter(([_, provider]) => provider.available)
    .map(([name, _]) => name);

  const totalLLMs = Object.keys(status.llm_providers || {}).length;

  return (
    <div className="relative">
      <div 
        className={`flex items-center gap-2 text-sm cursor-pointer ${THEME.interactive.hover} px-2 py-1 rounded transition-colors`}
        onClick={() => setIsExpanded(!isExpanded)}
        title="Click to view detailed status"
      >
        {/* Backend Status */}
        <div className="flex items-center gap-1">
          <div className={`w-2 h-2 rounded-full ${getStatusColor(status.backend?.status)}`}></div>
          <span className={THEME.text.secondary}>API</span>
        </div>

        {/* Qdrant Status */}
        <div className="flex items-center gap-1">
          <div className={`w-2 h-2 rounded-full ${getStatusColor(status.qdrant?.status)}`}></div>
          <span className={THEME.text.secondary}>DB</span>
        </div>

        {/* LLM Status */}
        <div className="flex items-center gap-1">
          <div className={`w-2 h-2 rounded-full ${connectedLLMs.length > 0 ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span className={THEME.text.secondary}>
            LLM ({connectedLLMs.length}/{totalLLMs})
          </span>
        </div>

        {/* Expand/Collapse Icon */}
        <Icon 
          name="chevronDown" 
          className={`w-3 h-3 ${THEME.text.muted} transition-transform ${isExpanded ? 'rotate-180' : ''}`} 
        />
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div className={`absolute top-full right-0 mt-1 ${THEME.containers.card} border ${THEME.borders.default} rounded-lg shadow-lg p-3 min-w-64 z-50`}>
          <div className={`text-xs font-medium ${THEME.text.primary} mb-2`}>
            Server Status
          </div>
          
          {/* Backend */}
          <div className="flex items-center justify-between mb-2">
            <span className={`text-sm ${THEME.text.secondary}`}>Backend API</span>
            <div className="flex items-center gap-1">
              <span className="text-xs">{getStatusIcon(status.backend?.status)}</span>
              <span className="text-xs capitalize">{status.backend?.status}</span>
            </div>
          </div>

          {/* Qdrant */}
          <div className="flex items-center justify-between mb-2">
            <span className={`text-sm ${THEME.text.secondary}`}>Vector DB</span>
            <div className="flex items-center gap-1">
              <span className="text-xs">{getStatusIcon(status.qdrant?.status)}</span>
              <span className="text-xs capitalize">{status.qdrant?.status}</span>
              {status.qdrant?.collections > 0 && (
                <span className={`text-xs ${THEME.text.muted}`}>({status.qdrant.collections} collections)</span>
              )}
            </div>
          </div>

          {/* LLM Providers */}
          <div className={`border-t ${THEME.borders.default} pt-2`}>
            <div className={`text-xs font-medium ${THEME.text.primary} mb-1`}>
              LLM Providers
            </div>
            {Object.entries(status.llm_providers || {}).map(([name, provider]) => (
              <div key={name} className="flex items-center justify-between text-xs">
                <span className={`${THEME.text.secondary} capitalize`}>{name}</span>
                <div className="flex items-center gap-1">
                  <span>{getStatusIcon(provider.status)}</span>
                  <span className="capitalize">{provider.status}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Last Updated */}
          {lastUpdated && (
            <div className={`border-t ${THEME.borders.default} pt-2 mt-2`}>
              <div className={`text-xs ${THEME.text.muted}`}>
                Updated: {lastUpdated.toLocaleTimeString()}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ServerStatus; 