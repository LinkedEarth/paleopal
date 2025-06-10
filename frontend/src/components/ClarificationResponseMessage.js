import React from 'react';

// Component to render clarification responses in a nice format
const ClarificationResponseMessage = ({ content, clarificationResponses }) => {
    const [isCollapsed, setIsCollapsed] = React.useState(true); // Collapsed by default

    const renderHeader = () => (
        <div 
            className="flex items-center gap-3 text-gray-600 cursor-pointer hover:bg-gray-50 rounded transition-colors p-2 -m-2"
            onClick={() => setIsCollapsed(!isCollapsed)}
            title={isCollapsed ? 'Expand response' : 'Collapse response'}
        >
            <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            </div>
            <div className="flex-1">
                <span className="text-sm font-medium text-gray-800">Clarification Response</span>
                <span className="text-xs text-gray-500 ml-2">Answers to clarification questions</span>
            </div>
            <div className="flex items-center gap-2">
                <span className="text-xs text-gray-600">
                    {clarificationResponses ? `${clarificationResponses.length} answers provided` : 'Questions answered'}
                </span>
                <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">Completed</span>
                <svg 
                    className={`w-4 h-4 text-gray-600 transition-transform ${isCollapsed ? 'rotate-180' : ''}`} 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                </svg>
            </div>
        </div>
    );

    const renderContent = () => {
        // If we have structured clarification responses, use those
        if (clarificationResponses && Array.isArray(clarificationResponses) && clarificationResponses.length > 0) {
            return (
                <div className="ml-9 mt-2 space-y-3">
                    {clarificationResponses.map((response, index) => (
                        <div key={index} className="text-sm text-gray-700">
                            <div className="font-medium text-gray-800 mb-1">
                                {response.question || `Question ${index + 1}`}
                            </div>
                            <div className="text-gray-700 pl-3 border-l-2 border-gray-200">
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
                <div className="text-sm text-gray-700 whitespace-pre-wrap">{content}</div>
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