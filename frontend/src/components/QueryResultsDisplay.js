import React from 'react';
import THEME from '../styles/colorTheme';
import Icon from './Icon';

const QueryResultsDisplay = ({ results, error }) => {
  const copyToClipboard = (text) => navigator.clipboard.writeText(text).catch(() => {});

  if (error) {
    return (
      <div className={`rounded-lg ${THEME.containers.panel}`}>
        <div className={`flex justify-between items-center p-3 border-b ${THEME.borders.default} rounded-t-lg ${THEME.containers.header}`}>
          <h4 className={`font-medium text-sm m-0 flex items-center gap-2 ${THEME.text.primary}`}>
            <Icon name="search" className={`w-4 h-4 ${THEME.status.error.text}`} />
            Query Error
          </h4>
        </div>
        <div className="p-3">
          <div className={`p-3 rounded border text-sm ${THEME.status.error.text} ${THEME.status.error.background} ${THEME.status.error.border}`}>{error}</div>
        </div>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className={`rounded-lg ${THEME.containers.panel}`}>
        <div className={`flex justify-between items-center p-3 border-b ${THEME.borders.default} rounded-t-lg ${THEME.containers.header}`}>
          <h4 className={`font-medium text-sm m-0 flex items-center gap-2 ${THEME.text.primary}`}>
            <Icon name="list" className="w-4 h-4" />
            Query Results
          </h4>
        </div>
        <div className="p-3">
          <p className={`text-sm ${THEME.text.secondary}`}>No results found.</p>
        </div>
      </div>
    );
  }

  const headers = Object.keys(results[0]);
  return (
    <div className={`border ${THEME.borders.default} rounded-lg ${THEME.containers.panel} relative group`}>
      <div className={`flex justify-between items-center p-3 border-b ${THEME.borders.default} rounded-t-lg ${THEME.containers.header}`}>
        <h4 className={`font-medium text-sm m-0 flex items-center gap-2 ${THEME.text.primary}`}>
          <Icon name="list" className="w-4 h-4" />
          Query Results ({results.length === 50 ? "limiting to ": ""}{results.length} row{results.length !== 1 ? 's' : ''})
        </h4>
        <button 
          className={`top-2 right-2 z-10 p-1.5 ${THEME.containers.card} border ${THEME.borders.default} rounded opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${THEME.interactive.hover}`}
          onClick={() => copyToClipboard(JSON.stringify(results, null, 2))}
        >
          <span className="flex items-center gap-1">
            <Icon name="copy" className={`w-4 h-4 ${THEME.text.secondary}`} />
          </span>
        </button>
      </div>
      <div className="p-3">
        <div className={`${THEME.containers.card} rounded border ${THEME.borders.default} overflow-hidden max-h-96 overflow-y-auto`}>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead className={`sticky top-0 ${THEME.containers.secondary}`}>
                <tr>
                  {headers.map(h => (
                    <th key={h} className={`border-b ${THEME.borders.default} px-3 py-2 text-left font-medium ${THEME.text.primary} ${THEME.containers.secondary}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className={THEME.containers.card}>
                {results.map((row, i) => (
                  <tr key={i} className={THEME.interactive.hover}>
                    {headers.map(h => (
                      <td key={`${i}-${h}`} className={`border-b ${THEME.borders.table} px-3 py-2 ${THEME.text.primary}`}>
                        {(() => {
                          const v = row[h];
                          if (v === null || v === undefined) return '';
                          if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return v;
                          try {
                            return JSON.stringify(v);
                          } catch (e) {
                            return String(v);
                          }
                        })()}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        {/* Show a note if results are truncated to the maximum limit */}
        {results.length === 50 && (
          <p className={`text-xs ${THEME.text.muted} mb-2`}>Displaying first 50 results (limited).</p>
        )}
      </div>
    </div>
  );
};

export default QueryResultsDisplay; 