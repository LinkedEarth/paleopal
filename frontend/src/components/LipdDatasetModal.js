import React, { useEffect, useState } from 'react';
import { LiPD } from 'lipdjs';
import THEME from '../styles/colorTheme';
import Icon from './Icon';
import LipdDatasetViewer from './LipdDatasetViewer';
import { extractDatasetNameFromValue } from '../utils/mapUtils';

/**
 * Modal for browsing a LiPD dataset.
 * Loads dataset using lipdjs from the public LiPDVerse GraphDB endpoint.
 * If loading fails, displays an error message.
 * Supports both dataset names and URIs (extracts localname from URIs).
 */
const LipdDatasetModal = ({ isOpen, onClose, datasetName: rawDatasetName }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [lipdInstance, setLipdInstance] = useState(null);

  // Extract actual dataset name from URI or use as-is
  const datasetName = extractDatasetNameFromValue(rawDatasetName);

  useEffect(() => {
    if (!isOpen || !datasetName) return;

    const fetchDataset = async () => {
      setLoading(true);
      setError('');
      setLipdInstance(null);

      try {
        const lipd = new LiPD();
        // Use direct GraphDB endpoint
        lipd.setEndpoint('https://linkedearth.graphdb.mint.isi.edu/repositories/LiPDVerse-dynamic');
        await lipd.loadRemoteDatasets(datasetName);
        setLipdInstance(lipd);
      } catch (err) {
        console.error('Failed to load LiPD dataset:', err);
        setError(
          err?.message ||
            'Failed to load dataset. It may not be available in LiPDVerse.'
        );
      } finally {
        setLoading(false);
      }
    };

    fetchDataset();
  }, [isOpen, datasetName]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999] p-4"
      onClick={onClose}
    >
      <div
        className={`${THEME.containers.card} rounded-lg shadow-xl max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col border ${THEME.borders.default}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className={`flex items-center justify-between p-4 border-b ${THEME.borders.default}`}
        >
          <h3 className={`text-lg font-semibold ${THEME.text.primary}`}>
            LiPD Dataset: {datasetName}
            {rawDatasetName !== datasetName && (
              <span className={`text-sm font-normal ${THEME.text.secondary} ml-2`}>
                (from {rawDatasetName})
              </span>
            )}
          </h3>
          <button
            onClick={onClose}
            className={`p-1.5 rounded-full ${THEME.interactive.hover}`}
          >
            <Icon name="close" className={`w-5 h-5 ${THEME.text.secondary}`} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 text-sm">
          {loading && (
            <div className="flex items-center gap-2">
              <Icon
                name="spinner"
                className={`w-4 h-4 animate-spin ${THEME.text.secondary}`}
              />
              <span className={`${THEME.text.secondary}`}>Loading dataset…</span>
            </div>
          )}

          {error && (
            <div
              className={`p-3 rounded border ${THEME.status.error.text} ${THEME.status.error.background} ${THEME.status.error.border}`}
            >
              {error}
            </div>
          )}

          {lipdInstance && (
            <LipdDatasetViewer lipdInstance={lipdInstance} datasetName={datasetName} />
          )}
        </div>
      </div>
    </div>
  );
};

export default LipdDatasetModal; 