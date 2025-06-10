import React from 'react';
import { parseMessageParts } from '../utils/parse';

// Component to render formatted clarification messages
const ClarificationMessage = ({ content, clarificationQuestions, hasSubsequentResponse = false }) => {
    const [isCollapsed, setIsCollapsed] = React.useState(hasSubsequentResponse); // Collapse by default if answered

    // Update collapsed state when hasSubsequentResponse changes
    React.useEffect(() => {
        if (hasSubsequentResponse) {
            setIsCollapsed(true);
        }
    }, [hasSubsequentResponse]);

    const questionCount = clarificationQuestions ? clarificationQuestions.length : 1;

    const renderHeader = () => (
      <div 
        className="flex items-center gap-3 text-neutral-600 dark:text-neutral-300 cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-700 rounded transition-colors p-2 -m-2"
        onClick={() => setIsCollapsed(!isCollapsed)}
        title={isCollapsed ? 'Expand questions' : 'Collapse questions'}
      >
        <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
          <svg className="w-5 h-5 text-neutral-500 dark:text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div className="flex-1">
          <span className="text-sm font-medium text-neutral-800 dark:text-neutral-200">Clarification Questions</span>
          <span className="text-xs text-neutral-500 dark:text-neutral-400 ml-2">
            {hasSubsequentResponse ? 'Questions that were asked for clarification' : 'Questions requesting clarification'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-600 dark:text-neutral-400">{questionCount} {questionCount === 1 ? 'question' : 'questions'}</span>
          {hasSubsequentResponse && (
            <span className="text-xs text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/30 px-2 py-1 rounded-full">Answered</span>
          )}
          <svg 
            className={`w-4 h-4 text-neutral-600 dark:text-neutral-400 transition-transform ${isCollapsed ? 'rotate-180' : ''}`} 
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
      // If we have multiple questions, use those
      if (clarificationQuestions && clarificationQuestions.length > 0) {
        return (
          <div className="ml-9 mt-2 space-y-3">
            {clarificationQuestions.map((question, index) => (
              <div key={question.id || index} className="text-sm text-neutral-700 dark:text-neutral-300">
                {clarificationQuestions.length > 1 && (
                  <div className="font-medium text-neutral-800 dark:text-neutral-200 mb-1">Question {index + 1}</div>
                )}
                <div className="font-medium mb-1">{question.question}</div>
                
                {question.context && (
                  <div className="text-xs text-neutral-600 dark:text-neutral-400 mb-2 pl-3 border-l-2 border-neutral-200 dark:border-neutral-600">{question.context}</div>
                )}
                
                {question.choices && question.choices.length > 0 && (
                  <div className="mt-1">
                    <div className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1">Options:</div>
                    <ul className="list-disc list-inside space-y-1 text-xs text-neutral-600 dark:text-neutral-400 pl-3">
                      {question.choices.map((choice, choiceIndex) => {
                        // Handle both string choices and object choices
                        let choiceText;
                        if (typeof choice === 'string') {
                          choiceText = choice;
                        } else if (choice && typeof choice === 'object') {
                          // Handle object choices with value/description or similar structure
                          choiceText = choice.value || choice.description || choice.text || JSON.stringify(choice);
                        } else {
                          choiceText = String(choice);
                        }
                        
                        return (
                          <li key={choiceIndex}>{choiceText}</li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      }
      
      // Otherwise, try to parse and format the raw text content
      const parts = parseMessageParts(content);
      return (
        <div className="ml-9 mt-2 space-y-2">
          <div className="text-sm font-medium text-neutral-700 dark:text-neutral-300">{parts.question}</div>
          
          {parts.context && (
            <div className="text-xs text-neutral-600 dark:text-neutral-400 pl-3 border-l-2 border-neutral-200 dark:border-neutral-600">{parts.context}</div>
          )}
          
          {parts.options.length > 0 && (
            <div>
              <div className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1">Options:</div>
              <ul className="list-disc list-inside space-y-1 text-xs text-neutral-600 dark:text-neutral-400 pl-3">
                {parts.options.map((option, index) => {
                  // Handle both string options and object options
                  let optionText;
                  if (typeof option === 'string') {
                    optionText = option;
                  } else if (option && typeof option === 'object') {
                    // Handle object options with value/description or similar structure
                    optionText = option.value || option.description || option.text || JSON.stringify(option);
                  } else {
                    optionText = String(option);
                  }
                  
                  return (
                    <li key={index}>{optionText}</li>
                  );
                })}
              </ul>
            </div>
          )}
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

export default ClarificationMessage; 