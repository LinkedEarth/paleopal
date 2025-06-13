import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

const SparqlQueryDisplay = ({ query, agentType = 'sparql', isDarkMode = false }) => {
  const copyToClipboard = (text) => navigator.clipboard.writeText(text).catch(() => {});

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
        return '🔍 SPARQL Query';
      case 'code':
        return '💻 Generated Code';
      case 'workflow_generation':
        return '📋 Workflow Plan';
      default:
        return '🔍 Generated Query';
    }
  };

  return (
    <div className="border border-neutral-200 dark:border-neutral-600 rounded-lg bg-neutral-50 dark:bg-neutral-800">
      <div className="flex justify-between items-center p-3 border-b border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 rounded-t-lg">
        <h4 className="text-neutral-800 dark:text-neutral-200 font-medium text-sm m-0">{getDisplayTitle()}</h4>
        <button 
          className="px-3 py-1 bg-blue-100 dark:bg-blue-800/30 text-blue-700 dark:text-blue-300 rounded text-xs hover:bg-blue-200 dark:hover:bg-blue-700/50 transition-colors border border-blue-300 dark:border-blue-600"
          onClick={() => copyToClipboard(query)}
        >
          📋 Copy
        </button>
      </div>
      <div className="p-3">
        <div className="bg-white dark:bg-neutral-800 rounded border border-neutral-200 dark:border-neutral-600 overflow-hidden max-h-96 overflow-y-auto">
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