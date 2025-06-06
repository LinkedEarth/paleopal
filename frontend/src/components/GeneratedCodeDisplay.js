import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';

const GeneratedCodeDisplay = ({ code }) => {
  const copyToClipboard = (text) => navigator.clipboard.writeText(text).catch(() => {});
  if (!code) return null;
  return (
    <div className="generated-code-display">
      <div className="code-header">
        <h4>Generated Python Code</h4>
        <button className="copy-code-button" onClick={() => copyToClipboard(code)}>📋 Copy</button>
      </div>
      <div className="code-block">
        <SyntaxHighlighter language="python" style={tomorrow} showLineNumbers wrapLines customStyle={{ margin: 0, borderRadius: '8px', fontSize: '14px' }}>
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  );
};

export default GeneratedCodeDisplay; 