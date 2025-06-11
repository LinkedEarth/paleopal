import React, { useState } from 'react';
// Use prism syntax highlighter for code snippets
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

// Modal component for showing detailed results
const ResultsModal = ({ isOpen, onClose, title, results, type }) => {
  if (!isOpen) return null;

  const renderResult = (result, index) => {
    return (
      <div key={index} className="mb-4 pb-4 border-b border-neutral-200 dark:border-neutral-600 last:border-b-0">
        <div className="font-medium text-sm text-neutral-800 dark:text-neutral-200 mb-2">
          {result.name || result.title || result.query || `${type} ${index + 1}`}
                </div>
        
                {result.description && (
          <div className="mb-2 text-xs text-neutral-600 dark:text-neutral-400">
                    {result.description}
                  </div>
                )}
                
        {/* SPARQL Query */}
        {(result.sparql || result.sparql_query || result.query) && (
          <div className="mt-2">
            <div className="text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">SPARQL Query:</div>
            <SyntaxHighlighter
              language="sparql"
              style={{
                ...(document.documentElement.classList.contains('dark') ? oneDark : oneLight),
                'code[class*="language-"]': { background: 'transparent', backgroundColor: 'transparent' },
                'pre[class*="language-"]': { background: 'transparent', backgroundColor: 'transparent' }
              }}
              customStyle={{ margin: 0, padding: '1rem', background: 'transparent', fontSize: '13px' }}
              className="!m-0 rounded border border-neutral-200 dark:border-neutral-600"
            >
              {result.sparql || result.sparql_query || result.query}
            </SyntaxHighlighter>
          </div>
        )}
        
        {/* Python Code */}
        {result.code && (
          <div className="mt-2">
            <div className="text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">Python Code:</div>
            <SyntaxHighlighter
              language="python"
              style={{
                ...(document.documentElement.classList.contains('dark') ? oneDark : oneLight),
                'code[class*="language-"]': { background: 'transparent', backgroundColor: 'transparent' },
                'pre[class*="language-"]': { background: 'transparent', backgroundColor: 'transparent' }
              }}
              customStyle={{ margin: 0, padding: '1rem', background: 'transparent', fontSize: '13px' }}
              className="!m-0 rounded border border-neutral-200 dark:border-neutral-600"
            >
              {result.code}
            </SyntaxHighlighter>
          </div>
        )}

        {/* Entity details */}
        {type === 'entity_matches' && (
          <div className="mt-2 text-xs text-neutral-600 dark:text-neutral-400">
            {result.type && <div><span className="font-medium">Type:</span> {result.type}</div>}
            {result.similarity && <div><span className="font-medium">Similarity:</span> {(result.similarity * 100).toFixed(1)}%</div>}
            {result.uri && <div className="mt-1 text-neutral-600 dark:text-neutral-400 font-mono break-all">{result.uri}</div>}
            {result.synonyms && result.synonyms.length > 0 && (
              <div className="mt-1"><span className="font-medium">Synonyms:</span> {result.synonyms.join(', ')}</div>
            )}
          </div>
        )}

        {/* Literature content */}
        {(result.content || result.abstract || result.summary) && (
                  <div className="mt-2">
            <div className="text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                      {result.content ? 'Content:' : result.abstract ? 'Abstract:' : 'Summary:'}
                    </div>
            <div className="text-xs text-neutral-600 dark:text-neutral-400 bg-neutral-50 dark:bg-neutral-700 p-2 rounded max-h-32 overflow-y-auto">
                      {result.content || result.abstract || result.summary}
                    </div>
                  </div>
                )}

        {/* Method steps for literature / notebook methods */}
        {((result.steps && Array.isArray(result.steps)) || (result.method_steps && Array.isArray(result.method_steps))) && (
          <div className="mt-2">
            <div className="text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">Method Steps:</div>
            <ol className="list-decimal pl-5 space-y-1 text-xs text-neutral-600 dark:text-neutral-400">
              {(result.steps || result.method_steps).map((step, i) => (
                <li key={i}>
                  {typeof step === 'string' ? step : (step.title || step.name || step.description || JSON.stringify(step))}
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* Metadata badges */}
        <div className="mt-2 flex flex-wrap gap-1">
                  {result.similarity_score && (
            <span className="bg-neutral-100 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 px-2 py-0.5 rounded text-xs">
                      Similarity: {(result.similarity_score * 100).toFixed(1)}%
                    </span>
                  )}
                  {result.relevance_score && (
            <span className="bg-neutral-100 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 px-2 py-0.5 rounded text-xs">
                      Relevance: {(result.relevance_score * 100).toFixed(1)}%
                    </span>
                  )}
                  {result.source_type && (
            <span className="bg-neutral-100 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 px-2 py-0.5 rounded text-xs">
              {result.source_type}
                    </span>
                  )}
                  {result.author && (
            <span className="bg-neutral-100 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 px-2 py-0.5 rounded text-xs">
              {result.author}
                    </span>
                  )}
                  {result.year && (
            <span className="bg-neutral-100 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 px-2 py-0.5 rounded text-xs">
              {result.year}
                    </span>
                  )}
                </div>
              </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-neutral-900 bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-neutral-800 rounded-lg max-w-4xl w-full max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-neutral-200 dark:border-neutral-600">
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">{title}</h3>
          <button
            onClick={onClose}
            className="text-neutral-400 dark:text-neutral-500 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors"
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
            <div className="text-center text-neutral-500 dark:text-neutral-400 py-8">No results to display</div>
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

  const openModal = (title, results, type) => {
    setModalState({ isOpen: true, title, results, type });
  };

  const closeModal = () => {
    setModalState({ isOpen: false, title: '', results: [], type: '' });
  };

  const statusText = getStatusText();

  const renderStatusIcon = () => {
    if (executionDone) {
      return (
        <svg className="w-5 h-5 text-green-500 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      );
    } else {
      return (
        <svg className="w-5 h-5 text-neutral-500 dark:text-neutral-400 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    }
  };
    
    return (
    <>
      {/* Collapsed view - matches "Sending request..." styling exactly */}
      <div 
        className="flex items-center gap-3 text-neutral-600 dark:text-neutral-300 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {renderStatusIcon()}
        
        <div className="flex-1 min-w-0">
          <span className="text-sm">{statusText}</span>
          {completedNodes.length > 0 && !executionDone && (
            <span className="text-xs text-neutral-500 dark:text-neutral-400 ml-2">
              {completedNodes.filter(n => n.nodeName !== 'Agent Execution').length} steps completed
            </span>
          )}
          </div>
        
        {completedNodes.length > 0 && (
          <button className="text-neutral-400 dark:text-neutral-500 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors">
            <svg className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`} 
                 fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        )}
      </div>

      {/* Expanded view - detailed steps */}
      {isExpanded && completedNodes.length > 0 && (
        <div className="mt-4">
          <div className="p-1">
            <div className="space-y-2">
              {completedNodes
                .filter(n => n.nodeName !== 'Agent Execution')
                .map((node, index) => {
                  const stepId = node.id || index;
                  
                  // Parse metadata if it's a string
                  let metadata = node.metadata;
                  if (typeof metadata === 'string') {
                    try {
                      metadata = JSON.parse(metadata);
                    } catch (e) {
                      metadata = {};
                    }
                  }
                  
                  const nodeOutput = metadata?.node_output || {};
                  
                  // Steps that should show clickable badges
                  const badgeSteps = ['get_similar_queries', 'get_entity_matches', 'search_examples', 'search_context'];
                  const shouldShowBadges = badgeSteps.includes(node.nodeName);
                  // Create a suffix for the matches based on the node name
                  let badgeSuffix = '';
                  let badgeSuffix2 = ''
                  if (node.nodeName === 'get_similar_queries') {
                    badgeSuffix = 'similar queries';
                  } else if (node.nodeName === 'get_entity_matches') {
                    badgeSuffix = 'ontology matches';
                  } else if (node.nodeName === 'search_examples') {
                    badgeSuffix = 'code examples';
                  } else if (node.nodeName === 'search_context') {
                    badgeSuffix = 'notebook methods';
                    badgeSuffix2 = 'literature methods';
                  }
                  
                  // Debug logging for search_examples and search_context steps
                  if (node.nodeName === 'search_examples' || node.nodeName === 'search_context') {
                    console.log(`🔍 Step ${node.nodeName} output:`, nodeOutput);
                  }
                  
                  return (
                    <div key={stepId} className="flex items-center gap-3 p-1 pl-6">
                      <span className="text-green-500 dark:text-green-400 text-sm">✓</span>
                      <span className="flex-1 text-sm text-neutral-700 dark:text-neutral-200">{node.nodeName}</span>
                      
                      <div className="flex items-center gap-2">
                        {node.timestamp && executionStart && (
                          <span className="text-xs text-neutral-500 dark:text-neutral-400">
                            {formatDuration(executionStart, node.timestamp)}
                          </span>
                        )}
                        
                        {/* Show clickable badges for relevant output */}
                        {shouldShowBadges && nodeOutput && (
                          <div className="flex items-center gap-1">
                            {/* Similar results/queries */}
                            {nodeOutput.similar_results && Array.isArray(nodeOutput.similar_results) && nodeOutput.similar_results.length > 0 && (
                              <button 
                                className="px-2 py-0.5 bg-blue-100 dark:bg-blue-800/30 text-blue-800 dark:text-blue-200 rounded hover:bg-blue-200 dark:hover:bg-blue-700 transition-colors text-xs"
                                onClick={() => openModal(
                                  `Similar Queries (${nodeOutput.similar_results.length})`,
                                  nodeOutput.similar_results,
                                  'query_examples'
                                )}
                              >
                                {nodeOutput.similar_results.length} {badgeSuffix}
                              </button>
                            )}
                            
                            {/* Entity matches */}
                            {nodeOutput.entity_matches && Array.isArray(nodeOutput.entity_matches) && nodeOutput.entity_matches.length > 0 && (
                              <button 
                                className="px-2 py-0.5 bg-blue-100 dark:bg-blue-800/30 text-blue-800 dark:text-blue-200 rounded hover:bg-blue-200 dark:hover:bg-blue-700 transition-colors text-xs"
                                onClick={() => openModal(
                                  `Entity Matches (${nodeOutput.entity_matches.length})`,
                                  nodeOutput.entity_matches,
                                  'entity_matches'
                                )}
                              >
                                {nodeOutput.entity_matches.length} {badgeSuffix}
                              </button>
                            )}
                            
                            {/* Code examples - check multiple possible field names */}
                            {(nodeOutput.code_examples || nodeOutput.examples || nodeOutput.search_results) && (
                              (() => {
                                const examples = nodeOutput.code_examples || nodeOutput.examples || nodeOutput.search_results;
                                return Array.isArray(examples) && examples.length > 0 && (
                                  <button 
                                    className="px-2 py-0.5 bg-blue-100 dark:bg-blue-800/30 text-blue-800 dark:text-blue-200 rounded hover:bg-blue-200 dark:hover:bg-blue-700 transition-colors text-xs"
                                    onClick={() => openModal(
                                      `Code Examples (${examples.length})`,
                                      examples,
                                      'code_examples'
                                    )}
                                  >
                                    {examples.length} {badgeSuffix}
                                  </button>
                                );
                              })()
                            )}
                            
                            {/* Context/Literature examples - check multiple possible field names */}
                            {(nodeOutput.literature_examples || nodeOutput.context_examples || nodeOutput.context_results || nodeOutput.search_results) && (
                              (() => {
                                const contextExamples = nodeOutput.literature_examples || nodeOutput.context_examples || nodeOutput.context_results || nodeOutput.search_results;
                                return Array.isArray(contextExamples) && contextExamples.length > 0 && (
                                  <button 
                                    className="px-2 py-0.5 bg-blue-100 dark:bg-blue-800/30 text-blue-800 dark:text-blue-200 rounded hover:bg-blue-200 dark:hover:bg-blue-700 transition-colors text-xs"
                                    onClick={() => openModal(
                                      `Context Examples (${contextExamples.length})`,
                                      contextExamples,
                                      'literature_examples'
                                    )}
                                  >
                                    {contextExamples.length} {badgeSuffix2 ? badgeSuffix2 : badgeSuffix}
                                  </button>
                                );
                              })()
                            )}
                            
                            {/* Generic results count - fallback for any step with results */}
                            {nodeOutput.results_count && (
                              <span className="px-2 py-0.5 bg-neutral-100 dark:bg-neutral-600 text-neutral-700 dark:text-neutral-200 rounded text-xs">
                                {nodeOutput.results_count} {badgeSuffix}
                              </span>
                            )}
                          </div>
                        )}
                </div>
              </div>
            );
                })}
            </div>
            
            {currentRunningNode && currentRunningNode.nodeName !== 'Agent Execution' && (
              <div className="mt-2 flex items-center gap-3 p-1 pl-6">
                <div className="w-4 h-4 border-2 border-neutral-500 dark:border-neutral-400 border-t-transparent rounded-full animate-spin"></div>
                <span className="flex-1 text-sm text-neutral-700 dark:text-neutral-200">{currentRunningNode.nodeName}</span>
                <span className="text-xs text-neutral-600 dark:text-neutral-400">In progress</span>
        </div>
      )}
          </div>
        </div>
      )}

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