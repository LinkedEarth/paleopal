import VariableStateDisplay from './VariableStateDisplay';
import THEME from '../styles/colorTheme';
import Icon from './Icon';

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
                    <span className={`${THEME.status.success.text} text-sm flex items-center gap-1`}>
                      <Icon name="success" />
                      Execution Successful
                    </span>
                    {result.execution_time && (
                      <span className={`${THEME.text.muted} text-xs`}>
                        ({result.execution_time.toFixed(2)}s)
                      </span>
                    )}
                  </div>
                  
                  {/* Execution Output */}
                  {result.output && (
                    <div>
                      <div className={`text-xs font-medium ${THEME.text.primary} mb-1`}>Output:</div>
                      <pre className={`text-xs ${THEME.containers.secondary} p-2 rounded border ${THEME.borders.default} overflow-x-auto whitespace-pre-wrap ${THEME.text.primary}`}>
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
                      <div className={`text-xs font-medium ${THEME.text.primary} mb-1`}>Generated Plots:</div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                        {result.plots.map((plotPath, plotIndex) => {
                          // Extract filename
                          const parts = plotPath.split(/[/\\]/);
                          const filename = parts[parts.length - 1];
                          const imgSrc = `${window.location.origin}/plots/${filename}`;
                          return (
                            <div key={plotIndex} className="border rounded-lg overflow-hidden">
                              <img src={imgSrc} alt={`Plot ${plotIndex + 1}`} className="w-full h-auto" />
                            </div>
                          );
                        })}
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
                    <span className={`${THEME.status.error.text} text-sm flex items-center gap-1`}>
                      <Icon name="error" />
                      Execution Failed
                    </span>
                    {result.execution_time && (
                      <span className={`${THEME.text.muted} text-xs`}>
                        ({result.execution_time.toFixed(2)}s)
                      </span>
                    )}
                  </div>
                  
                  {/* Error message */}
                  {result.error && (
                    <div>
                      <div className={`text-xs font-medium ${THEME.status.error.text} mb-1`}>Error:</div>
                      <pre className={`text-xs ${THEME.status.error.background} p-2 rounded border ${THEME.status.error.border} overflow-x-auto whitespace-pre-wrap ${THEME.status.error.text}`}>
                        {result.error}
                      </pre>
                    </div>
                  )}
                  
                  {/* Partial output if any */}
                  {result.output && (
                    <div>
                      <div className={`text-xs font-medium ${THEME.text.primary} mb-1`}>Partial Output:</div>
                      <pre className={`text-xs ${THEME.containers.secondary} p-2 rounded border ${THEME.borders.default} overflow-x-auto whitespace-pre-wrap ${THEME.text.primary}`}>
                        {result.output}
                      </pre>
                    </div>
                  )}
                </div>
              );
            } else {
              // Handle other result types
              return (
                <div key={index} className={`text-xs ${THEME.text.secondary}`}>
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
      <div className={`border ${THEME.borders.default} rounded-lg ${THEME.containers.panel}`}>
        <div className={`flex justify-between items-center p-3 border-b ${THEME.borders.default} ${THEME.containers.card} rounded-t-lg`}>
          <h4 className={`${THEME.text.primary} font-medium text-sm m-0 flex items-center gap-2`}>
            <Icon name="chevronDown" />
            Execution Results
          </h4>
        </div>
        <div className="p-3">
          {renderContent()}
        </div>
      </div>
    );
};


export default ExecutionResultsDisplay; 
