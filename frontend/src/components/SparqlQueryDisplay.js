import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';

const SparqlQueryDisplay = ({ query }) => {
  const copyToClipboard = (text) => navigator.clipboard.writeText(text).catch(() => {});

  return (
    <div className="border border-blue-300 rounded-lg p-4 bg-blue-50">
      <div className="flex justify-between items-center mb-3">
        <h4 className="text-blue-800 font-medium m-0">🔍 SPARQL Query</h4>
        <button 
          className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 transition-colors"
          onClick={() => copyToClipboard(query)}
        >
          📋 Copy Query
        </button>
      </div>
      <div className="bg-white rounded border border-green-200 overflow-hidden max-h-96 overflow-y-auto">
        <SyntaxHighlighter 
          language="sparql" 
          className="!m-0 !bg-white text-xs"
          customStyle={{ margin: 0, padding: '1rem', backgroundColor: 'white', fontSize: '14px' }}
        >
          {query}
        </SyntaxHighlighter>
      </div>
    </div>
  );
};

export default SparqlQueryDisplay; 