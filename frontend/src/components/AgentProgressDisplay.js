import React, { useState } from 'react';
import './ChatWindow.css';

// Stand-alone progress widget used by ChatWindow
export const AgentProgressDisplay = ({ messages, executionStart }) => {
  const progressMessages = messages.filter(m => m.isNodeProgress);
  const completedNodes = progressMessages.filter(m => m.phase === 'complete');
  const currentRunningNode = progressMessages.find(
    m => m.phase === 'start' && !completedNodes.some(c => c.nodeName === m.nodeName)
  );

  const formatDuration = (start, end) => {
    if (!start || !end) return '';
    const d = end - start;
    return d < 1000 ? `${d}ms` : `${(d / 1000).toFixed(1)}s`;
  };

  const renderNodeOutput = output => {
    if (!output || Object.keys(output).length === 0) return null;
    return (
      <div className="node-output-details">
        {Object.entries(output).map(([k, v]) => (
          <div key={k} className="output-item">
            <strong>{k.replace(/_/g, ' ')}:</strong> {String(v)}
          </div>
        ))}
      </div>
    );
  };

  const [showCompleted, setShowCompleted] = useState(false);
  const toggleCompleted = () => setShowCompleted(p => !p);

  const lastProgress = progressMessages[progressMessages.length - 1];
  const executionDone = lastProgress && lastProgress.phase === 'complete' && lastProgress.nodeName === 'Agent Execution';
  const statusText = currentRunningNode
    ? `Running: ${currentRunningNode.nodeName}`
    : executionDone
    ? 'Execution completed'
    : completedNodes.length > 0
    ? 'Processing…'
    : 'Starting agent execution…';

  return (
    <div className="agent-progress-display">
      <div className="progress-header">
        <div className="current-status">⏳&nbsp;&nbsp;{statusText}</div>
        {executionStart && <div className="execution-time">Started: {new Date(executionStart).toLocaleTimeString()}</div>}
        {completedNodes.length > 0 && (
          <button className="toggle-completed-btn" onClick={toggleCompleted}>
            {showCompleted ? '▾ Hide Steps' : '▸ Show Steps'}
          </button>
        )}
      </div>

      {completedNodes.length > 0 && showCompleted && (
        <div className="completed-steps">
          <h4>Completed Steps:</h4>
          {completedNodes.map(n => (
            <div key={n.id} className="progress-step completed">
              <div className="step-header">
                <span className="step-icon">✅</span>
                <span className="step-name">{n.nodeName}</span>
                <span className="step-timing">{n.timestamp && executionStart && formatDuration(executionStart, n.timestamp)}</span>
              </div>
              {renderNodeOutput(n.outputSummary)}
            </div>
          ))}
        </div>
      )}

      {currentRunningNode && (
        <div className="current-step">
          <div className="progress-step running">
            <div className="step-header">
              <span className="step-icon">⏳</span>
              <span className="step-name">{currentRunningNode.nodeName}</span>
              <span className="step-status">In Progress…</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}; 