import React from 'react';

const QueryResultsDisplay = ({ results, error }) => {
  const copyToClipboard = (text) => navigator.clipboard.writeText(text).catch(() => {});

  if (error) {
    return (
      <div className="border border-red-300 rounded-lg p-4 bg-red-50">
        <div className="flex justify-between items-center mb-2">
          <h4 className="text-red-700 font-medium m-0">❌ Query Error</h4>
        </div>
        <div className="text-red-600 bg-white p-3 rounded border border-red-200">{error}</div>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className="border border-gray-300 rounded-lg p-4 bg-gray-50">
        <div className="flex justify-between items-center mb-2">
          <h4 className="text-gray-700 font-medium m-0">📊 Query Results</h4>
        </div>
        <p className="text-gray-600">No results found.</p>
      </div>
    );
  }

  const headers = Object.keys(results[0]);
  return (
    <div className="border border-gray-300 rounded-lg p-4 bg-white">
      <div className="flex justify-between items-center mb-3">
        <h4 className="text-gray-800 font-medium m-0">📊 Query Results ({results.length} row{results.length !== 1 ? 's' : ''})</h4>
        <button 
          className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 transition-colors"
          onClick={() => copyToClipboard(JSON.stringify(results, null, 2))}
        >
          📋 Copy JSON
        </button>
      </div>
      <div className="overflow-x-auto max-h-96 overflow-y-auto">
        <table className="w-full border-collapse border border-gray-300 text-sm">
          <thead className="sticky top-0 bg-gray-100">
            <tr className="bg-gray-100">
              {headers.map(h => (
                <th key={h} className="border border-gray-300 px-3 py-2 text-left font-medium text-gray-700">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((row, i) => (
              <tr key={i} className="hover:bg-gray-50">
                {headers.map(h => (
                  <td key={`${i}-${h}`} className="border border-gray-300 px-3 py-2 text-gray-800">
                    {row[h]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default QueryResultsDisplay; 