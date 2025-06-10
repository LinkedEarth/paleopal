import React, { useState } from 'react';

// Modal component for showing detailed results
const ResultsModal = ({ isOpen, onClose, title, results, type }) => {
  if (!isOpen) return null;

  const renderResult = (result, index) => {
    return (
      <div key={index} className="mb-4 pb-4 border-b border-gray-200 last:border-b-0">
        <div className="font-medium text-sm text-gray-800 mb-2">
          {result.name || result.title || result.query || `${type} ${index + 1}`}
        </div>
        
        {result.description && (
          <div className="mb-2 text-xs text-gray-600">
            {result.description}
          </div>
        )}

        {/* SPARQL Query */}
        {(result.sparql || result.sparql_query || result.query) && (
          <div className="mt-2">
            <div className="text-xs font-medium text-gray-700 mb-1">SPARQL Query:</div>
            <div className="bg-gray-800 text-green-400 p-2 rounded text-xs font-mono overflow-x-auto">
              {result.sparql || result.sparql_query || result.query}
            </div>
          </div>
        )}

        {/* Python Code */}
        {result.code && (
          <div className="mt-2">
            <div className="text-xs font-medium text-gray-700 mb-1">Python Code:</div>
            <div className="bg-gray-800 text-blue-400 p-2 rounded text-xs font-mono overflow-x-auto">
              {result.code}
            </div>
          </div>
        )}

        {/* Entity details */}
        {type === 'entity_matches' && (
          <div className="mt-2 text-xs text-gray-600">
            {result.type && <div><span className="font-medium">Type:</span> {result.type}</div>}
            {result.similarity && <div><span className="font-medium">Similarity:</span> {(result.similarity * 100).toFixed(1)}%</div>}
            {result.uri && <div className="mt-1 text-blue-600 font-mono break-all">{result.uri}</div>}
            {result.synonyms && result.synonyms.length > 0 && (
              <div className="mt-1"><span className="font-medium">Synonyms:</span> {result.synonyms.join(', ')}</div>
            )}
          </div>
        )}

        {/* Literature content */}
        {(result.content || result.abstract || result.summary) && (
          <div className="mt-2">
            <div className="text-xs font-medium text-gray-700 mb-1">
              {result.content ? 'Content:' : result.abstract ? 'Abstract:' : 'Summary:'}
            </div>
            <div className="text-xs text-gray-600 bg-gray-50 p-2 rounded max-h-32 overflow-y-auto">
              {result.content || result.abstract || result.summary}
            </div>
          </div>
        )}

        {/* Metadata badges */}
        <div className="mt-2 flex flex-wrap gap-1">
          {result.similarity_score && (
            <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs">
              Similarity: {(result.similarity_score * 100).toFixed(1)}%
            </span>
          )}
          {result.relevance_score && (
            <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">
              Relevance: {(result.relevance_score * 100).toFixed(1)}%
            </span>
          )}
          {result.source_type && (
            <span className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded text-xs">
              {result.source_type}
            </span>
          )}
          {result.author && (
            <span className="bg-purple-100 text-purple-700 px-2 py-0.5 rounded text-xs">
              {result.author}
            </span>
          )}
          {result.year && (
            <span className="bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded text-xs">
              {result.year}
            </span>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4">
          {results && results.length > 0 ? (
            results.map((result, index) => renderResult(result, index))
          ) : (
            <div className="text-center text-gray-500 py-8">No results to display</div>
          )}
        </div>
      </div>
    </div>
  );
};

// Simplified progress widget used by ChatWindow
export const AgentProgressDisplay = ({ messages, executionStart }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState(new Set());
  const [modalState, setModalState] = useState({ isOpen: false, title: '', results: [], type: '' });
  
  const progressMessages = messages.filter(m => m.isNodeProgress);
  const completedNodes = progressMessages.filter(m => m.phase === 'complete');
  
  // Get the current running node
  const currentRunningNode = progressMessages.find(
    m => m.phase === 'start' && !completedNodes.some(c => c.nodeName === m.nodeName)
  );

  // Get execution status
  const lastProgress = progressMessages[progressMessages.length - 1];
  const executionDone = lastProgress && lastProgress.phase === 'complete' && lastProgress.nodeName === 'Agent Execution';
  
  // Simple status text
  const getStatusText = () => {
    if (executionDone) {
      return 'Agent execution completed';
    }
    
    if (currentRunningNode && currentRunningNode.nodeName !== 'Agent Execution') {
      return `Running: ${currentRunningNode.nodeName}`;
    }
    
    if (completedNodes.length > 0) {
      const recentCompletedNode = completedNodes
        .filter(n => n.nodeName !== 'Agent Execution')
        .sort((a, b) => new Date(b.timestamp || b.created_at || 0) - new Date(a.timestamp || a.created_at || 0))[0];
      
      if (recentCompletedNode) {
        return `Processing... (last: ${recentCompletedNode.nodeName})`;
      }
    }
    
    return 'Starting agent execution...';
  };

  const toggleStepExpanded = (stepId) => {
    setExpandedSteps(prev => {
      const newSet = new Set(prev);
      if (newSet.has(stepId)) {
        newSet.delete(stepId);
      } else {
        newSet.add(stepId);
      }
      return newSet;
    });
  };

  const openModal = (title, results, type) => {
    setModalState({ isOpen: true, title, results, type });
  };

  const closeModal = () => {
    setModalState({ isOpen: false, title: '', results: [], type: '' });
  };

  const renderStepDetails = (node) => {
    // Parse metadata if it's a string
    let metadata = node.metadata;
    if (typeof metadata === 'string') {
      try {
        metadata = JSON.parse(metadata);
      } catch (e) {
        metadata = {};
      }
    }

    const nodeOutput = metadata?.node_output;
    if (!nodeOutput || Object.keys(nodeOutput).length === 0) {
      return null;
    }

    const getTypeLabel = (type) => {
      switch (type) {
        case 'entity_matches': return 'Entities';
        case 'query_examples': return 'Queries';
        case 'code_examples': return 'Code';
        case 'literature_examples': return 'Literature';
        default: return type.replace(/_/g, ' ');
      }
    };

    return (
      <div className="p-3 bg-gray-50 border-t border-gray-200">
        {/* Show counts for array outputs */}
        {nodeOutput.similar_results_count && (
          <div className="mb-2">
            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
              {nodeOutput.similar_results_count} similar results found
            </span>
          </div>
        )}
        
        {nodeOutput.entity_matches && Array.isArray(nodeOutput.entity_matches) && nodeOutput.entity_matches.length > 0 && (
          <div className="mb-2">
            <button 
              className="px-2 py-0.5 bg-green-100 text-green-700 rounded hover:bg-green-200 transition-colors text-xs"
              onClick={() => openModal(
                `Entity Matches (${nodeOutput.entity_matches.length})`,
                nodeOutput.entity_matches,
                'entity_matches'
              )}
            >
              {nodeOutput.entity_matches.length} entities matched
            </button>
          </div>
        )}

        {nodeOutput.query_examples && Array.isArray(nodeOutput.query_examples) && nodeOutput.query_examples.length > 0 && (
          <div className="mb-2">
            <button 
              className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded hover:bg-purple-200 transition-colors text-xs"
              onClick={() => openModal(
                `Query Examples (${nodeOutput.query_examples.length})`,
                nodeOutput.query_examples,
                'query_examples'
              )}
            >
              {nodeOutput.query_examples.length} similar queries
            </button>
          </div>
        )}

        {nodeOutput.code_examples && Array.isArray(nodeOutput.code_examples) && nodeOutput.code_examples.length > 0 && (
          <div className="mb-2">
            <button 
              className="px-2 py-0.5 bg-orange-100 text-orange-700 rounded hover:bg-orange-200 transition-colors text-xs"
              onClick={() => openModal(
                `Code Examples (${nodeOutput.code_examples.length})`,
                nodeOutput.code_examples,
                'code_examples'
              )}
            >
              {nodeOutput.code_examples.length} code examples
            </button>
          </div>
        )}

        {nodeOutput.literature_examples && Array.isArray(nodeOutput.literature_examples) && nodeOutput.literature_examples.length > 0 && (
          <div className="mb-2">
            <button 
              className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200 transition-colors text-xs"
              onClick={() => openModal(
                `Literature Examples (${nodeOutput.literature_examples.length})`,
                nodeOutput.literature_examples,
                'literature_examples'
              )}
            >
              {nodeOutput.literature_examples.length} literature examples
            </button>
          </div>
        )}
        
        {/* Show other simple metadata */}
        {Object.entries(nodeOutput).map(([key, value]) => {
          if (key === 'similar_results_count' || Array.isArray(value)) return null;
          
          return (
            <div key={key} className="mb-1">
              <span className="font-medium text-gray-600">{key.replace(/_/g, ' ')}:</span>
              <span className="ml-1 text-gray-700">{String(value)}</span>
            </div>
          );
        })}
      </div>
    );
  };

  const statusText = getStatusText();
  const statusColor = 'text-gray-700';

  const renderStatusIcon = () => {
    if (executionDone) {
      return (
        <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      );
    } else {
      return (
        <svg className="w-5 h-5 text-blue-500 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    }
  };

  return (
    <>
      <div className="p-4">
        {/* Collapsed view - simple loading display styling */}
        <div 
          className="cursor-pointer"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center gap-3 text-gray-600">
            {renderStatusIcon()}
            
            <div className="flex-1 min-w-0">
              <span className="text-sm">{statusText}</span>
              {completedNodes.length > 0 && !executionDone && (
                <span className="text-xs text-gray-500 ml-2">
                  {completedNodes.filter(n => n.nodeName !== 'Agent Execution').length} steps completed
                </span>
              )}
            </div>
            
            {completedNodes.length > 0 && (
              <button className="text-gray-400 hover:text-gray-600 transition-colors">
                <svg className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`} 
                     fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* Expanded view - detailed steps */}
        {isExpanded && completedNodes.length > 0 && (
          <div className="mt-4 p-3 bg-white border rounded-lg">
            <div className="space-y-2">
              {completedNodes
                .filter(n => n.nodeName !== 'Agent Execution')
                .map((node, index) => {
                  const stepId = node.id || index;
                  const hasDetails = node.metadata && 
                    (typeof node.metadata === 'string' ? node.metadata.includes('node_output') : node.metadata.node_output);
                  
                  return (
                    <div key={stepId} className="border border-gray-200 rounded">
                      <div 
                        className={`flex items-center gap-3 p-2 ${hasDetails ? 'cursor-pointer hover:bg-gray-50' : 'bg-gray-50'} transition-colors`}
                        onClick={() => hasDetails && toggleStepExpanded(stepId)}
                      >
                        <span className="text-green-500 text-sm">✓</span>
                        <span className="flex-1 text-sm text-gray-700">{node.nodeName}</span>
                        <div className="flex items-center gap-2">
                          {node.timestamp && executionStart && (
                            <span className="text-xs text-gray-500">
                              {formatDuration(executionStart, node.timestamp)}
                            </span>
                          )}
                          {hasDetails && (
                            <button className="text-gray-400 hover:text-gray-600 transition-colors">
                              <svg className={`w-3 h-3 transition-transform ${expandedSteps.has(stepId) ? 'rotate-180' : ''}`} 
                                   fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                              </svg>
                            </button>
                          )}
                        </div>
                      </div>
                      
                      {hasDetails && expandedSteps.has(stepId) && renderStepDetails(node)}
                    </div>
                  );
                })}
            </div>
            
            {currentRunningNode && currentRunningNode.nodeName !== 'Agent Execution' && (
              <div className="mt-2 flex items-center gap-3 p-2 bg-orange-50 rounded border border-orange-200">
                <div className="w-4 h-4 border-2 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
                <span className="flex-1 text-sm text-orange-700">{currentRunningNode.nodeName}</span>
                <span className="text-xs text-orange-600">In progress</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Results Modal */}
      <ResultsModal 
        isOpen={modalState.isOpen}
        onClose={closeModal}
        title={modalState.title}
        results={modalState.results}
        type={modalState.type}
      />
    </>
  );
};

// Helper function
const formatDuration = (start, end) => {
  if (!start || !end) return '';
  const d = new Date(end) - new Date(start);
  return d < 1000 ? `${d}ms` : `${(d / 1000).toFixed(1)}s`;
}; 