import React, { useState } from 'react';

const VariableStateDisplay = ({ variableState, isDarkMode = false }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!variableState || Object.keys(variableState).length === 0) {
    return null;
  }

  // Filter out variables that are modules
  const filteredVariables = Object.entries(variableState).filter(([name, info]) => {
    return info.type !== 'module' && 
           (!info.module || !info.module.includes('module')) &&
           (!info.value || !info.value.includes('(module)'));
  });

  if (filteredVariables.length === 0) {
    return null;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
          Variables Available in State ({filteredVariables.length})
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 flex items-center gap-1"
        >
          {isExpanded ? 'Collapse' : 'Expand'}
          <svg className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} 
               fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>
      
      {isExpanded && (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {filteredVariables.map(([name, info]) => (
            <div key={name} className="text-xs bg-blue-50 dark:bg-blue-900/20 p-2 rounded border border-blue-200 dark:border-blue-800">
              <div className="font-medium text-blue-800 dark:text-blue-200">
                {name} <span className="font-normal text-blue-600 dark:text-blue-300">({info.type})</span>
              </div>
              <div className="text-blue-700 dark:text-blue-300 mt-1 font-mono text-xs break-all">
                {(() => {
                  if (info === null || info === undefined) return String(info);
                  const v = info.value;
                  if (v === null || v === undefined) return String(v);
                  // If it's already a string, show as is
                  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
                    return String(v);
                  }
                  // For objects / arrays, stringify with fallback
                  try {
                    return JSON.stringify(v, null, 2);
                  } catch (err) {
                    return String(v);
                  }
                })()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default VariableStateDisplay; 