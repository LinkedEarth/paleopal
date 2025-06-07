import React, { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';

// Stand-alone progress widget used by ChatWindow
export const AgentProgressDisplay = ({ messages, executionStart }) => {
  const progressMessages = messages.filter(m => m.isNodeProgress);
  const completedNodes = progressMessages.filter(m => m.phase === 'complete');
  const currentRunningNode = progressMessages.find(
    m => m.phase === 'start' && !completedNodes.some(c => c.nodeName === m.nodeName)
  );

  const [showCompleted, setShowCompleted] = useState(false);
  const [expandedMatches, setExpandedMatches] = useState({});

  const formatDuration = (start, end) => {
    if (!start || !end) return '';
    const d = end - start;
    return d < 1000 ? `${d}ms` : `${(d / 1000).toFixed(1)}s`;
  };

  const toggleCompleted = () => setShowCompleted(p => !p);

  const toggleMatchesExpanded = (nodeId, matchType) => {
    const key = `${nodeId}_${matchType}`;
    setExpandedMatches(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const renderMatchesList = (matches, type, nodeId) => {
    if (!matches || !Array.isArray(matches) || matches.length === 0) return null;

    const key = `${nodeId}_${type}`;
    const isExpanded = expandedMatches[key];

    // Try to detect agent type from the node name or matches structure
    const isCodeAgent = progressMessages.some(m => 
      m.nodeName && (
        m.nodeName.toLowerCase().includes('code') ||
        m.nodeName.toLowerCase().includes('generate_code') ||
        m.nodeName.toLowerCase().includes('search_code')
      )
    );
    
    const isSparqlAgent = progressMessages.some(m => 
      m.nodeName && (
        m.nodeName.toLowerCase().includes('sparql') ||
        m.nodeName.toLowerCase().includes('query') ||
        m.nodeName.toLowerCase().includes('generate_query')
      )
    );

    // Get display label for the type
    const getTypeLabel = (type) => {
      const labels = {
        'similar_results': 'Similar Results',
        'entity_matches': 'Entity Matches',
        'query_examples': 'Query Examples',
        'code_examples': 'Code Examples', 
        'literature_examples': 'Literature Examples'
      };
      return labels[type] || type.replace('_', ' ');
    };

    return (
      <div className="mt-2">
        <button
          className="px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
          onClick={() => toggleMatchesExpanded(nodeId, type)}
        >
          {isExpanded ? '▾' : '▸'} View {getTypeLabel(type)} ({matches.length})
        </button>
        {isExpanded && (
          <div className="mt-2 p-3 bg-gray-100 rounded border max-h-96 overflow-y-auto">
            {matches.map((result, idx) => (
              <div key={idx} className="mb-4 pb-3 border-b border-gray-300 last:border-b-0">
                <div className="font-medium text-sm text-gray-800 mb-2">
                  {result.name || result.query || result.title || `${getTypeLabel(type)} ${idx + 1}`}
                </div>
                {result.description && (
                  <div className="mb-2 text-xs text-gray-600">
                    {result.description}
                  </div>
                )}
                
                {/* Handle Code Examples and Code Generation Agent - show Python code */}
                {(type === 'code_examples' || isCodeAgent) && result.code && (
                  <div className="mt-2">
                    <div className="text-xs font-medium text-gray-700 mb-1">Python Code:</div>
                    <div className="bg-gray-800 rounded overflow-hidden">
                      <SyntaxHighlighter 
                        language="python" 
                        style={tomorrow}
                        className="!m-0 text-xs"
                        customStyle={{ margin: 0, padding: '0.5rem', fontSize: '11px' }}
                      >
                        {result.code}
                      </SyntaxHighlighter>
                    </div>
                  </div>
                )}
                
                {/* Handle Query Examples and SPARQL Agent - show SPARQL queries */}
                {((type === 'query_examples' || isSparqlAgent) || (!isCodeAgent && (result.sparql || result.sparql_query))) && (result.sparql || result.sparql_query) && (
                  <div className="mt-2">
                    <div className="text-xs font-medium text-gray-700 mb-1">SPARQL Query:</div>
                    <div className="bg-gray-800 rounded overflow-hidden">
                      <SyntaxHighlighter 
                        language="sparql" 
                        style={tomorrow}
                        className="!m-0 text-xs"
                        customStyle={{ margin: 0, padding: '0.5rem', fontSize: '11px' }}
                      >
                        {result.sparql || result.sparql_query}
                      </SyntaxHighlighter>
                    </div>
                  </div>
                )}

                {/* Handle Literature Examples - show content/abstract */}
                {type === 'literature_examples' && (result.content || result.abstract || result.summary) && (
                  <div className="mt-2">
                    <div className="text-xs font-medium text-gray-700 mb-1">
                      {result.content ? 'Content:' : result.abstract ? 'Abstract:' : 'Summary:'}
                    </div>
                    <div className="text-xs text-gray-600 leading-relaxed bg-gray-50 p-2 rounded border max-h-32 overflow-y-auto">
                      {result.content || result.abstract || result.summary}
                    </div>
                  </div>
                )}

                {/* Show imports for code examples */}
                {result.imports && Array.isArray(result.imports) && result.imports.length > 0 && (
                  <div className="mt-2">
                    <div className="text-xs font-medium text-gray-700 mb-1">Required Imports:</div>
                    <div className="text-xs text-gray-600 font-mono bg-gray-50 p-2 rounded border">
                      {result.imports.join('\n')}
                    </div>
                  </div>
                )}

                {/* Handle Entity Matches - special formatting */}
                {type === 'entity_matches' && (
                  <div className="mt-2">
                    <div className="text-xs text-gray-600">
                      <span className="font-medium">Type:</span> {result.type || 'Unknown'}
                      {result.similarity && ` | `}
                      {result.similarity && <span className="font-medium">Similarity:</span>}
                      {result.similarity && ` ${(result.similarity * 100).toFixed(1)}%`}
                    </div>
                    {result.uri && (
                      <div className="mt-1 text-xs text-blue-600 font-mono break-all">
                        {result.uri}
                      </div>
                    )}
                    {result.synonyms && result.synonyms.length > 0 && (
                      <div className="mt-2 text-xs text-gray-500">
                        <span className="font-medium">Synonyms:</span> {result.synonyms.join(', ')}
                      </div>
                    )}
                  </div>
                )}
                
                {/* Show additional metadata */}
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  {result.similarity_score && (
                    <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded">
                      Similarity: {(result.similarity_score * 100).toFixed(1)}%
                    </span>
                  )}
                  {result.relevance_score && (
                    <span className="bg-green-100 text-green-800 px-2 py-1 rounded">
                      Relevance: {(result.relevance_score * 100).toFixed(1)}%
                    </span>
                  )}
                  {result.source_type && (
                    <span className="bg-gray-100 text-gray-800 px-2 py-1 rounded">
                      Source: {result.source_type}
                    </span>
                  )}
                  {result.categories && result.categories.length > 0 && (
                    <span className="bg-purple-100 text-purple-800 px-2 py-1 rounded">
                      {result.categories.join(', ')}
                    </span>
                  )}
                  {result.author && (
                    <span className="bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
                      Author: {result.author}
                    </span>
                  )}
                  {result.year && (
                    <span className="bg-indigo-100 text-indigo-800 px-2 py-1 rounded">
                      Year: {result.year}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderNodeOutput = (message) => {
    // Parse metadata if it's a string
    let metadata = message.metadata;
    if (typeof metadata === 'string') {
      try {
        metadata = JSON.parse(metadata);
      } catch (e) {
        console.warn('Failed to parse metadata:', metadata);
        metadata = {};
      }
    }

    // Get node_output from metadata
    const nodeOutput = metadata?.node_output;
    if (!nodeOutput || Object.keys(nodeOutput).length === 0) {
      // Fallback to legacy outputSummary
      const output = message.outputSummary;
      if (!output || Object.keys(output).length === 0) return null;
      
      return (
        <div className="mt-2 p-3 bg-gray-50 rounded border">
          {Object.entries(output).map(([k, v]) => (
            <div key={k} className="mb-2 last:mb-0">
              <strong className="text-gray-700">{k.replace(/_/g, ' ')}:</strong> <span className="text-gray-600">{String(v)}</span>
            </div>
          ))}
        </div>
      );
    }
    
    return (
      <div className="mt-2 p-3 bg-gray-50 rounded border">
        {/* Display similar_results_count prominently */}
        {nodeOutput.similar_results_count !== undefined && (
          <div className="mb-3 text-sm">
            <span className="font-medium text-gray-700">Search Results:</span>
            <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
              {nodeOutput.similar_results_count} found
            </span>
          </div>
        )}

        {/* Handle special cases for detailed search results */}
        {nodeOutput.similar_results && Array.isArray(nodeOutput.similar_results) && (
          renderMatchesList(nodeOutput.similar_results, 'similar_results', message.id || 'unknown')
        )}
        
        {nodeOutput.entity_matches && Array.isArray(nodeOutput.entity_matches) && (
          renderMatchesList(nodeOutput.entity_matches, 'entity_matches', message.id || 'unknown')
        )}

        {/* Handle other types of results */}
        {nodeOutput.query_examples && Array.isArray(nodeOutput.query_examples) && (
          renderMatchesList(nodeOutput.query_examples, 'query_examples', message.id || 'unknown')
        )}

        {nodeOutput.code_examples && Array.isArray(nodeOutput.code_examples) && (
          renderMatchesList(nodeOutput.code_examples, 'code_examples', message.id || 'unknown')
        )}

        {nodeOutput.literature_examples && Array.isArray(nodeOutput.literature_examples) && (
          renderMatchesList(nodeOutput.literature_examples, 'literature_examples', message.id || 'unknown')
        )}

        {/* Display other metadata fields */}
        {Object.entries(nodeOutput).map(([k, v]) => {
          // Skip arrays we've already handled
          if (['similar_results', 'entity_matches', 'query_examples', 'code_examples', 'literature_examples'].includes(k)) {
            return null;
          }
          
          // Skip similar_results_count as we handle it above
          if (k === 'similar_results_count') {
            return null;
          }
          
          // Special handling for generated code preview
          if (k === 'generated_code_preview' && v) {
            return (
              <div key={k} className="mb-3">
                <div className="text-sm font-medium text-gray-700 mb-1">Generated Code Preview:</div>
                <div className="bg-gray-800 rounded overflow-hidden">
                  <SyntaxHighlighter 
                    language="python" 
                    style={tomorrow}
                    className="!m-0 text-xs"
                    customStyle={{ margin: 0, padding: '0.5rem', fontSize: '11px' }}
                  >
                    {v}
                  </SyntaxHighlighter>
                </div>
              </div>
            );
          }

          // Special handling for generated query preview
          if (k === 'generated_query_preview' && v) {
            return (
              <div key={k} className="mb-3">
                <div className="text-sm font-medium text-gray-700 mb-1">Generated Query Preview:</div>
                <div className="bg-gray-800 rounded overflow-hidden">
                  <SyntaxHighlighter 
                    language="sparql" 
                    style={tomorrow}
                    className="!m-0 text-xs"
                    customStyle={{ margin: 0, padding: '0.5rem', fontSize: '11px' }}
                  >
                    {v}
                  </SyntaxHighlighter>
                </div>
              </div>
            );
          }
          
          return (
            <div key={k} className="mb-2 last:mb-0">
              <strong className="text-gray-700">{k.replace(/_/g, ' ')}:</strong> <span className="text-gray-600">{String(v)}</span>
            </div>
          );
        })}
      </div>
    );
  };

  const lastProgress = progressMessages[progressMessages.length - 1];
  const executionDone = lastProgress && lastProgress.phase === 'complete' && lastProgress.nodeName === 'Agent Execution';
  const statusText = currentRunningNode
    ? `Running: ${currentRunningNode.nodeName}`
    : executionDone
    ? 'Execution completed'
    : completedNodes.length > 0
    ? 'Processing…'
    : 'Starting agent execution…';

  // Determine the appropriate icon based on execution state
  const statusIcon = executionDone ? '✅' : '⏳';

  return (
    <div className="border border-blue-200 rounded-lg p-4 bg-blue-50">
      <div className="flex justify-between items-center mb-3">
        <div className="text-blue-800 font-medium">{statusIcon}&nbsp;&nbsp;{statusText}</div>
        {executionStart && (
          <div className="text-xs text-blue-600">
            Started: {new Date(executionStart).toLocaleTimeString()}
          </div>
        )}
        {completedNodes.length > 0 && (
          <button 
            className="px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
            onClick={toggleCompleted}
          >
            {showCompleted ? '▾ Hide Steps' : '▸ Show Steps'}
          </button>
        )}
      </div>

      {completedNodes.length > 0 && showCompleted && (
        <div className="mt-3">
          <h4 className="text-sm font-medium text-blue-800 mb-2">Completed Steps:</h4>
          {completedNodes.map(n => (
            <div key={n.id} className="mb-3 p-3 bg-white rounded border border-green-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-green-600 mr-2">✅</span>
                <span className="flex-1 font-medium text-gray-800">{n.nodeName}</span>
                <span className="text-xs text-gray-500">
                  {n.timestamp && executionStart && formatDuration(executionStart, n.timestamp)}
                </span>
              </div>
              {renderNodeOutput(n)}
            </div>
          ))}
        </div>
      )}

      {currentRunningNode && (
        <div className="mt-3">
          <div className="p-3 bg-yellow-50 rounded border border-yellow-200">
            <div className="flex items-center">
              <span className="text-yellow-600 mr-2">⏳</span>
              <span className="flex-1 font-medium text-gray-800">{currentRunningNode.nodeName}</span>
              <span className="text-sm text-yellow-600">In Progress…</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}; 