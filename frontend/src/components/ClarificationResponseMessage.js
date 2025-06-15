import React from 'react';
import Icon from './Icon';

// Component to render clarification responses in a nice format
const ClarificationResponseMessage = ({ content, clarificationResponses }) => {
    const [isCollapsed, setIsCollapsed] = React.useState(true); // Collapsed by default

    const renderHeader = () => (
        <div 
            className="flex items-center gap-3 text-neutral-600 dark:text-neutral-300 cursor-pointer rounded transition-colors p-2 -m-2"
            onClick={() => setIsCollapsed(!isCollapsed)}
            title={isCollapsed ? 'Expand response' : 'Collapse response'}
        >
            <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
                <Icon name="check" className="w-5 h-5 text-green-500 dark:text-green-400" />
            </div>
            <div className="flex-1">
                <span className="text-sm font-medium text-neutral-800 dark:text-neutral-200">Clarification Response</span>
                <span className="text-xs text-neutral-500 dark:text-neutral-400 ml-2">Answers to clarification questions</span>
            </div>
            <div className="flex items-center gap-2">
                <span className="text-xs text-neutral-600 dark:text-neutral-400">
                    {clarificationResponses ? `${clarificationResponses.length} answers provided` : 'Questions answered'}
                </span>
                <span className="text-xs text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/30 px-2 py-1 rounded-full">Completed</span>
                <Icon name="chevronDown" className={`w-4 h-4 text-neutral-600 dark:text-neutral-400 transition-transform ${isCollapsed ? 'rotate-180' : ''}`} />
            </div>
        </div>
    );

    const renderContent = () => {
        // If we have structured clarification responses, use those
        if (clarificationResponses && Array.isArray(clarificationResponses) && clarificationResponses.length > 0) {
            return (
                <div className="ml-9 mt-2 space-y-3">
                    {clarificationResponses.map((response, index) => (
                        <div key={index} className="text-sm text-neutral-700 dark:text-neutral-300">
                            <div className="font-medium text-neutral-800 dark:text-neutral-200 mb-1">
                                {response.question || `Question ${index + 1}`}
                            </div>
                            <div className="text-neutral-700 dark:text-neutral-300 pl-3 border-l-2 border-neutral-200 dark:border-neutral-600">
                                {response.answer || 'No answer provided'}
                            </div>
                        </div>
                    ))}
                </div>
            );
        }

        // Fallback to plain text content for backward compatibility
        return (
            <div className="ml-9 mt-2">
                <div className="text-sm text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">{content}</div>
            </div>
        );
    };

    return (
        <div>
            {renderHeader()}
            {!isCollapsed && renderContent()}
        </div>
    );
};

export default ClarificationResponseMessage; 