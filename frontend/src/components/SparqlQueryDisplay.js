import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';

const SparqlQueryDisplay = ({ query }) => {
  const copyToClipboard = (text) => navigator.clipboard.writeText(text).catch(() => {});
  if (!query) return null;
  return (
    <div className="sparql-query-display">
      <div className="query-header">
        <span className="query-label">Generated SPARQL Query:</span>
        <button className="copy-button" onClick={() => copyToClipboard(query)}>📋 Copy</button>
      </div>
      <div className="query-content">
        <SyntaxHighlighter language="sparql" style={tomorrow} customStyle={{ margin: 0, borderRadius: '0.5rem', fontSize: '0.9rem' }}>
          {query}
        </SyntaxHighlighter>
      </div>
    </div>
  );
};

export default SparqlQueryDisplay; 