import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';

const GeneratedCodeDisplay = ({ code }) => {
  const copyToClipboard = (text) => navigator.clipboard.writeText(text).catch(() => {});

  return (
    <div className="border border-green-300 rounded-lg p-4 bg-green-50">
      <div className="flex justify-between items-center mb-3">
        <h4 className="text-green-800 font-medium m-0">💻 Generated Code</h4>
        <button 
          className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600 transition-colors"
          onClick={() => copyToClipboard(code)}
        >
          📋 Copy Code
        </button>
      </div>
      <div className="bg-white rounded border border-green-200 overflow-hidden max-h-96 overflow-y-auto">
        <SyntaxHighlighter 
          language="python" 
          className="!m-0 !bg-white text-xs"
          customStyle={{ margin: 0, padding: '1rem', backgroundColor: 'white', fontSize: '14px' }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  );
};

export default GeneratedCodeDisplay; 