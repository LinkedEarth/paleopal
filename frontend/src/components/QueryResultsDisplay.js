import React from 'react';

const QueryResultsDisplay = ({ results, error }) => {
  const copyToClipboard = (text) => navigator.clipboard.writeText(text).catch(() => {});

  if (error) {
    return (
      <div className="query-results-error">
        <div className="results-header"><h4>❌ Query Error</h4></div>
        <div className="error-message">{error}</div>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className="query-results-empty">
        <div className="results-header"><h4>📊 Query Results</h4></div>
        <p>No results found.</p>
      </div>
    );
  }

  const headers = Object.keys(results[0]);
  return (
    <div className="query-results-container">
      <div className="results-header">
        <h4>📊 Query Results ({results.length} row{results.length !== 1 ? 's' : ''})</h4>
        <button className="copy-results-button" onClick={() => copyToClipboard(JSON.stringify(results, null, 2))}>📋 Copy JSON</button>
      </div>
      <div className="results-table-wrapper">
        <table className="inline-results-table">
          <thead><tr>{headers.map(h => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>
            {results.map((row, i) => (
              <tr key={i}>{headers.map(h => <td key={`${i}-${h}`}>{row[h]}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default QueryResultsDisplay; 