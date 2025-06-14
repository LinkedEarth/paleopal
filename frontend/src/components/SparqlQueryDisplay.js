import React, { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import THEME from '../styles/colorTheme';

const SparqlQueryDisplay = ({ query, agentType = 'sparql', isDarkMode = false }) => {
  const [showCopyNotification, setShowCopyNotification] = useState(false);
  
  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setShowCopyNotification(true);
      setTimeout(() => setShowCopyNotification(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  // Determine syntax language based on agent type
  const getSyntaxLanguage = () => {
    switch (agentType) {
      case 'sparql':
        return 'sparql';
      case 'code':
        return 'python';
      case 'workflow_generation':
        return 'json';
      default:
        return 'sparql';
    }
  };

  // Determine display title based on agent type
  const getDisplayTitle = () => {
    switch (agentType) {
      case 'sparql':
        return (
          <span className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
              <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
              <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"></path>
              <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"></path>
            </svg>
            SPARQL Query
          </span>
        );
      case 'code':
        return (
          <span className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
              <path d="m7 8-4 4 4 4"></path>
              <path d="m17 8 4 4-4 4"></path>
              <path d="m14 4-4 16"></path>
            </svg>
            Generated Code
          </span>
        );
      case 'workflow_generation':
        return (
          <span className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
              <rect width="8" height="8" x="3" y="3" rx="2"></rect>
              <path d="M7 11v4a2 2 0 0 0 2 2h4"></path>
              <rect width="8" height="8" x="13" y="13" rx="2"></rect>
            </svg>
            Workflow Plan
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
            </svg>
            Generated Query
          </span>
        );
    }
  };

  return (
    <div className={`border ${THEME.borders.default} rounded-lg ${THEME.containers.panel} relative group`}>
      {/* Copy notification */}
      {showCopyNotification && (
        <div className={`absolute top-2 left-2 z-20 px-3 py-1 ${THEME.status.success.background} ${THEME.status.success.text} text-xs rounded-lg shadow-lg`}>
          ✓ Copied!
        </div>
      )}
      
      {/* Copy icon overlay */}
        <button 
        className={`absolute top-2 right-2 z-10 p-1.5 ${THEME.containers.card} border ${THEME.borders.default} rounded opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${THEME.interactive.hover}`}
          onClick={() => copyToClipboard(query)}
        title="Copy query to clipboard"
        >
        <svg className={`w-4 h-4 ${THEME.text.secondary}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
        </button>
      
      <div className={`flex justify-between items-center p-3 border-b ${THEME.borders.default} ${THEME.containers.card} rounded-t-lg`}>
        <h4 className={`${THEME.text.primary} font-medium text-sm m-0`}>{getDisplayTitle()}</h4>
      </div>
      <div className="p-3">
        <div className={`${THEME.containers.card} rounded border ${THEME.borders.default} overflow-hidden max-h-96 overflow-y-auto`}>
          <SyntaxHighlighter 
            language={getSyntaxLanguage()}
            style={{
              ...(isDarkMode ? oneDark : oneLight),
              'code[class*="language-"]': {
                ...(isDarkMode ? oneDark : oneLight)['code[class*="language-"]'],
                background: 'transparent',
                backgroundColor: 'transparent'
              },
              'pre[class*="language-"]': {
                ...(isDarkMode ? oneDark : oneLight)['pre[class*="language-"]'],
                background: 'transparent',
                backgroundColor: 'transparent'
              }
            }}
            className="!m-0"
            customStyle={{ 
              margin: 0, 
              padding: '1rem', 
              background: 'transparent',
              backgroundColor: 'transparent', 
              fontSize: '13px',
              fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
            }}
          >
            {query}
          </SyntaxHighlighter>
        </div>
      </div>
    </div>
  );
};

export default SparqlQueryDisplay; 