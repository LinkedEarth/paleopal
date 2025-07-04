import React, { useState } from 'react';
import THEME from '../styles/colorTheme';
import Icon from './Icon';
import InteractiveMap from './InteractiveMap';
import InteractiveMapMapbox from './InteractiveMapMapbox';
import { hasGeographicData, extractDatasetNameFromValue } from '../utils/mapUtils';
import LipdDatasetModal from './LipdDatasetModal';
import usePagedSparql from '../hooks/usePagedSparql';

const QueryResultsDisplay = ({ results, error, hideHeader = false, sparqlQuery=null, autoFetch=true }) => {
  const copyToClipboard = (text) => navigator.clipboard.writeText(text).catch(() => {});

  // State for LiPD dataset modal
  const [selectedDataset, setSelectedDataset] = useState(null);
  
  // State for manual fetch when autofetch is disabled
  const [manualFetchEnabled, setManualFetchEnabled] = useState(false);

  // how many rows to show in table
  const pageSize = 50;
  const [page, setPage] = useState(1);

  const allRows = usePagedSparql(results, sparqlQuery, 500, autoFetch || manualFetchEnabled);

  const totalPages = Math.max(1, Math.ceil(allRows.length / pageSize));

  // Check if results are cut off when autofetch is disabled
  const isResultsCutoff = !autoFetch && !manualFetchEnabled && results && results.length >= 10;
  


  if (error) {
    if (hideHeader) {
      return (
        <div className={`p-3 rounded border text-sm ${THEME.status.error.text} ${THEME.status.error.background} ${THEME.status.error.border}`}>
          {error}
        </div>
      );
    }
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
    if (hideHeader) {
      return (
        <p className={`text-sm ${THEME.text.secondary}`}>No results found.</p>
      );
    }
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

  const headers = Object.keys((allRows[0] || results[0]) || {});
  // Identify dataset-related columns
  const datasetColumns = headers.filter(h => /^(datasetname|dataset_name|datasetid|dataset_id|dsname|dataset)$/i.test(h));
  const showMap = hasGeographicData(allRows);
  
  // Render table content
  const renderTable = () => (
    <div className="space-y-4">
      {/* Cutoff warning when autofetch is disabled */}
      {isResultsCutoff && (
        <div className={`p-3 rounded border ${THEME.status.warning.background} ${THEME.status.warning.border} flex items-center justify-between gap-3`}>
          <div className="flex items-center gap-2">
            <Icon name="alertTriangle" className={`w-4 h-4 ${THEME.status.warning.text}`} />
            <span className={`text-sm ${THEME.status.warning.text}`}>
              Results are limited to 10 items with Auto-fetch disabled. There may be more results available.
            </span>
          </div>
          <button
            onClick={() => setManualFetchEnabled(true)}
            className={`px-3 py-1.5 text-sm rounded font-medium transition-colors ${THEME.buttons.primary}`}
          >
            Fetch All Results
          </button>
        </div>
      )}



      {/* Interactive Map - show above table if geographic data is available */}
      {showMap && (
        (process.env.REACT_APP_MAPBOX_TOKEN ? (
          <InteractiveMapMapbox
            data={allRows}
            height="600px"
            onDatasetClick={setSelectedDataset}
          />
        ) : (
          <InteractiveMap 
            data={allRows} 
            hideHeader={true}
            height="600px"
            onDatasetClick={setSelectedDataset}
          />
        ))
      )}
      
      {/* Data Table */}
      <div className="space-y-2">
        <div className={`${THEME.containers.card} rounded border ${THEME.borders.default} overflow-hidden`}>
          <div className="max-h-80 overflow-y-auto overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead className={`sticky top-0 z-10 ${THEME.containers.secondary}`}>
                <tr>
                  {headers.map(h => (
                    <th key={h} className={`border-b ${THEME.borders.default} px-3 py-2 text-left font-medium ${THEME.text.primary} ${THEME.containers.secondary}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className={THEME.containers.card}>
                {allRows.slice((page-1)*pageSize, page*pageSize).map((row, i) => (
                  <tr key={i} className={THEME.interactive.hover}>
                    {headers.map(h => (
                      <td key={`${i}-${h}`} className={`border-b ${THEME.borders.table} px-3 py-2 ${THEME.text.primary}`}>
                        {(() => {
                          const v = row[h];
                          if (v === null || v === undefined) return '';
                          // If this column contains dataset name/id, render as clickable link
                          if (datasetColumns.includes(h) && typeof v === 'string') {
                            const datasetName = extractDatasetNameFromValue(v);
                            if (datasetName) {
                              return (
                                <button
                                  className="text-blue-600 dark:text-blue-400 underline hover:opacity-80"
                                  onClick={() => setSelectedDataset(v)}
                                  title="Browse LiPD dataset"
                                >
                                  {v}
                                </button>
                              );
                            }
                          }
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
        {/* Pagination */}
        {allRows.length > pageSize && (
          <div className="flex items-center justify-between pt-2">
            <button
              className={`text-xs px-2 py-1 rounded ${THEME.interactive.hover} ${page===1 ? 'opacity-50 cursor-not-allowed' : ''}`}
              disabled={page===1}
              onClick={() => setPage(p=>Math.max(1,p-1))}
            >Prev</button>
            <span className={`text-xs ${THEME.text.secondary}`}>Page {page} / {totalPages}</span>
            <button
              className={`text-xs px-2 py-1 rounded ${THEME.interactive.hover} ${page===totalPages ? 'opacity-50 cursor-not-allowed' : ''}`}
              disabled={page===totalPages}
              onClick={() => setPage(p=>Math.min(totalPages,p+1))}
            >Next</button>
          </div>
        )}
      </div>

      {/* Cutoff warning at bottom when autofetch is disabled */}
      {isResultsCutoff && (
        <div className={`p-3 rounded border ${THEME.status.warning.background} ${THEME.status.warning.border} flex items-center justify-between gap-3`}>
          <div className="flex items-center gap-2">
            <Icon name="alertTriangle" className={`w-4 h-4 ${THEME.status.warning.text}`} />
            <span className={`text-sm ${THEME.status.warning.text}`}>
              Results are limited to 10 items with Auto-fetch disabled. There may be more results available.
            </span>
          </div>
          <button
            onClick={() => setManualFetchEnabled(true)}
            className={`px-3 py-1.5 text-sm rounded font-medium transition-colors ${THEME.buttons.primary}`}
          >
            Fetch All Results
          </button>
        </div>
      )}
    </div>
  );

  // If hideHeader is true, render just the table
  if (hideHeader) {
    return (
      <>
        {renderTable()}
        <LipdDatasetModal
          isOpen={!!selectedDataset}
          onClose={() => setSelectedDataset(null)}
          datasetName={selectedDataset}
        />
      </>
    );
  }

  // Default rendering with header
  return (
    <div className={`border ${THEME.borders.default} rounded-lg ${THEME.containers.panel} relative group`}>
      <div className={`flex justify-between items-center p-3 border-b ${THEME.borders.default} rounded-t-lg ${THEME.containers.header}`}>
        <h4 className={`font-medium text-sm m-0 flex items-center gap-2 ${THEME.text.primary}`}>
          <Icon name={showMap ? "map" : "list"} className="w-4 h-4" />
          Query Results ({!autoFetch && !manualFetchEnabled && results.length >= 10 ? "showing ": ""}{allRows.length} row{allRows.length !== 1 ? 's' : ''})
          {showMap && <span className={`text-xs px-2 py-1 rounded ${THEME.status.info.background} ${THEME.status.info.text}`}>with map</span>}
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
        {renderTable()}
      </div>
      {/* LiPD Dataset Modal */}
      <LipdDatasetModal
        isOpen={!!selectedDataset}
        onClose={() => setSelectedDataset(null)}
        datasetName={selectedDataset}
      />
    </div>
  );
};

export default QueryResultsDisplay; 