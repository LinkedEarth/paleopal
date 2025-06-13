import VariableStateDisplay from './VariableStateDisplay';

// Helper function to render unified execution results
const ExecutionResultsDisplay = ({ executionResults, isDarkMode, hideHeader = false }) => {

    if (!executionResults || !Array.isArray(executionResults) || executionResults.length === 0) {
      return null;
    }

    // Render the content without the outer container and header
    const renderContent = () => (
      <div className="space-y-3">
        {executionResults.map((result, index) => {
          if (result.type === 'execution_success') {
            return (
              <div key={index} className="space-y-2">
                {/* Success indicator */}
                <div className="flex items-center gap-2">
                  <span className="text-green-600 dark:text-green-400 text-sm">✓ Execution Successful</span>
                  {result.execution_time && (
                    <span className="text-neutral-500 dark:text-neutral-400 text-xs">
                      ({result.execution_time.toFixed(2)}s)
                    </span>
                  )}
                </div>
                
                {/* Execution Output */}
                {result.output && (
                  <div>
                    <div className="text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">Output:</div>
                    <pre className="text-xs bg-neutral-100 dark:bg-neutral-700 p-2 rounded border overflow-x-auto whitespace-pre-wrap text-neutral-800 dark:text-neutral-200">
                      {result.output}
                    </pre>
                  </div>
                )}
                
                {/* Variable State - Unified for all agents */}
                {result.variable_summary && (
                  <VariableStateDisplay 
                    variableState={result.variable_summary} 
                    isDarkMode={isDarkMode} 
                  />
                )}
                
                {/* Plot outputs */}
                {result.plots && result.plots.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">Generated Plots:</div>
                    <div className="space-y-2">
                      {result.plots.map((plotPath, plotIndex) => (
                        <div key={plotIndex} className="text-xs text-neutral-600 dark:text-neutral-400">
                          📊 {plotPath}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          } else if (result.type === 'execution_error') {
            return (
              <div key={index} className="space-y-2">
                {/* Error indicator */}
                <div className="flex items-center gap-2">
                  <span className="text-red-600 dark:text-red-400 text-sm">✗ Execution Failed</span>
                  {result.execution_time && (
                    <span className="text-neutral-500 dark:text-neutral-400 text-xs">
                      ({result.execution_time.toFixed(2)}s)
                    </span>
                  )}
                </div>
                
                {/* Error message */}
                {result.error && (
                  <div>
                    <div className="text-xs font-medium text-red-700 dark:text-red-300 mb-1">Error:</div>
                    <pre className="text-xs bg-red-50 dark:bg-red-900/20 p-2 rounded border border-red-200 dark:border-red-800 overflow-x-auto whitespace-pre-wrap text-red-800 dark:text-red-200">
                      {result.error}
                    </pre>
                  </div>
                )}
                
                {/* Partial output if any */}
                {result.output && (
                  <div>
                    <div className="text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">Partial Output:</div>
                    <pre className="text-xs bg-neutral-100 dark:bg-neutral-700 p-2 rounded border overflow-x-auto whitespace-pre-wrap text-neutral-800 dark:text-neutral-200">
                      {result.output}
                    </pre>
                  </div>
                )}
              </div>
            );
          } else {
            // Handle other result types
            return (
              <div key={index} className="text-xs text-neutral-600 dark:text-neutral-400">
                {result.message || JSON.stringify(result)}
              </div>
            );
          }
        })}
      </div>
    );

    // If hideHeader is true, render just the content
    if (hideHeader) {
      return renderContent();
    }

    // Default rendering with header
    return (
      <div className="border border-neutral-200 dark:border-neutral-600 rounded-lg bg-neutral-50 dark:bg-neutral-800">
        <div className="flex justify-between items-center p-3 border-b border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 rounded-t-lg">
          <h4 className="text-neutral-800 dark:text-neutral-200 font-medium text-sm m-0">⚡ Execution Results</h4>
        </div>
        <div className="p-3">
          {renderContent()}
        </div>
      </div>
    );
};


export default ExecutionResultsDisplay; 
