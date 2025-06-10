import React from 'react';

const QueryResultsDisplay = ({ results, error }) => {
  const copyToClipboard = (text) => navigator.clipboard.writeText(text).catch(() => {});

  if (error) {
    return (
      <div className="border border-neutral-200 dark:border-neutral-600 rounded-lg bg-neutral-50 dark:bg-neutral-800">
        <div className="flex justify-between items-center p-3 border-b border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 rounded-t-lg">
          <h4 className="text-neutral-800 dark:text-neutral-200 font-medium text-sm m-0">❌ Query Error</h4>
        </div>
        <div className="p-3">
          <div className="text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 p-3 rounded border border-red-200 dark:border-red-600 text-sm">{error}</div>
        </div>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className="border border-neutral-200 dark:border-neutral-600 rounded-lg bg-neutral-50 dark:bg-neutral-800">
        <div className="flex justify-between items-center p-3 border-b border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 rounded-t-lg">
          <h4 className="text-neutral-800 dark:text-neutral-200 font-medium text-sm m-0">📊 Query Results</h4>
        </div>
        <div className="p-3">
          <p className="text-neutral-600 dark:text-neutral-400 text-sm">No results found.</p>
        </div>
      </div>
    );
  }

  const headers = Object.keys(results[0]);
  return (
    <div className="border border-neutral-200 dark:border-neutral-600 rounded-lg bg-neutral-50 dark:bg-neutral-800">
      <div className="flex justify-between items-center p-3 border-b border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 rounded-t-lg">
        <h4 className="text-neutral-800 dark:text-neutral-200 font-medium text-sm m-0">📊 Query Results ({results.length} row{results.length !== 1 ? 's' : ''})</h4>
        <button 
          className="px-3 py-1 bg-neutral-100 dark:bg-neutral-600 text-neutral-700 dark:text-neutral-300 rounded text-xs hover:bg-neutral-200 dark:hover:bg-neutral-500 transition-colors border border-neutral-300 dark:border-neutral-500"
          onClick={() => copyToClipboard(JSON.stringify(results, null, 2))}
        >
          📋 Copy
        </button>
      </div>
      <div className="p-3">
        <div className="bg-white dark:bg-neutral-800 rounded border border-neutral-200 dark:border-neutral-600 overflow-hidden max-h-96 overflow-y-auto">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead className="sticky top-0 bg-neutral-50 dark:bg-neutral-700">
                <tr>
                  {headers.map(h => (
                    <th key={h} className="border-b border-neutral-200 dark:border-neutral-600 px-3 py-2 text-left font-medium text-neutral-700 dark:text-neutral-300 bg-neutral-50 dark:bg-neutral-700">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-neutral-800">
                {results.map((row, i) => (
                  <tr key={i} className="hover:bg-neutral-50 dark:hover:bg-neutral-700">
                    {headers.map(h => (
                      <td key={`${i}-${h}`} className="border-b border-neutral-100 dark:border-neutral-700 px-3 py-2 text-neutral-800 dark:text-neutral-200">
                        {row[h]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default QueryResultsDisplay; 