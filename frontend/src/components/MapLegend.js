import React from 'react';
import THEME from '../styles/colorTheme';
import { createArchiveMarkerHTML } from '../utils/mapUtils';

const MapLegend = ({ archiveTypes, className = '' }) => {
  if (!archiveTypes || archiveTypes.length === 0) return null;

  return (
    <div className={`absolute top-2 right-2 z-[1000] ${THEME.containers.card} border ${THEME.borders.default} rounded-lg shadow-lg max-w-[200px] w-48 ${className}`}>
      {/* Header */}
      <div className={`px-3 py-2 border-b ${THEME.borders.default}`}>
        <h4 className={`text-xs font-semibold ${THEME.text.primary}`}>
          Archive Types ({archiveTypes.length})
        </h4>
      </div>
      
      {/* Scrollable content */}
      <div className="max-h-48 overflow-y-auto p-2 map-legend-scroll">
        <div className="space-y-1.5">
          {archiveTypes.map((item, index) => (
            <div key={index} className="flex items-center gap-2 py-1">
              <div 
                className="w-6 h-6 flex items-center justify-center flex-shrink-0"
                title={item.config.name}
                style={{ 
                  fontSize: '16px',
                  color: item.config.color,
                  fontWeight: '900',
                  lineHeight: '1'
                }}
              >
                {item.config.symbol}
              </div>
              <div className="flex-1 min-w-0">
                <div className={`text-xs font-medium ${THEME.text.primary} truncate leading-tight`}>
                  {item.config.name}
                </div>
                <div className={`text-xs ${THEME.text.secondary} leading-tight`}>
                  {item.count} location{item.count !== 1 ? 's' : ''}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default MapLegend; 