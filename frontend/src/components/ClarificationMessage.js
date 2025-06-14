import React from 'react';
import { parseMessageParts } from '../utils/parse';
import { THEME } from '../styles/colorTheme';

// Component to render formatted clarification messages
const ClarificationMessage = ({ content, clarificationQuestions, hasSubsequentResponse = false, onAnswerQuestions }) => {
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
        className={`flex items-center gap-3 ${THEME.text.secondary} cursor-pointer ${THEME.interactive.hover} rounded transition-colors p-2 -m-2`}
        onClick={() => setIsCollapsed(!isCollapsed)}
        title={isCollapsed ? 'Expand questions' : 'Collapse questions'}
      >
        <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
          <svg className={`w-5 h-5 ${THEME.text.muted}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div className="flex-1">
          <span className={`text-sm font-medium ${THEME.text.primary}`}>Clarification Questions</span>
          <span className={`text-xs ${THEME.text.muted} ml-2`}>
            {hasSubsequentResponse ? 'Questions that were asked for clarification' : 'Questions requesting clarification'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs ${THEME.text.secondary}`}>{questionCount} {questionCount === 1 ? 'question' : 'questions'}</span>
          {hasSubsequentResponse && (
            <span className={`text-xs px-2 py-1 rounded-full ${THEME.status.success.text} ${THEME.status.success.background}`}>Answered</span>
          )}
          <svg 
            className={`w-4 h-4 ${THEME.text.secondary} transition-transform ${isCollapsed ? 'rotate-180' : ''}`} 
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
              <div key={question.id || index} className={`text-sm ${THEME.text.secondary}`}>
                {clarificationQuestions.length > 1 && (
                  <div className={`font-medium ${THEME.text.primary} mb-1`}>Question {index + 1}</div>
                )}
                <div className={`font-medium mb-1 ${THEME.text.primary}`}>{question.question}</div>
                
                {question.context && (
                  <div className={`text-xs ${THEME.text.secondary} mb-2 pl-3 border-l-2 ${THEME.borders.default}`}>{question.context}</div>
                )}
                
                {question.choices && question.choices.length > 0 && (
                  <div className="mt-1">
                    <div className={`text-xs font-medium ${THEME.text.secondary} mb-1`}>Options:</div>
                    <ul className={`list-disc list-inside space-y-1 text-xs ${THEME.text.secondary} pl-3`}>
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
            {/* Answer Questions button - positioned right after questions */}
            {!hasSubsequentResponse && onAnswerQuestions && (
              <div className="mt-4 flex justify-end">
                <button
                  onClick={onAnswerQuestions}
                  className={`px-4 py-2 rounded transition-colors text-sm ${THEME.buttons.primary}`}
                >
                  Answer Questions
                </button>
              </div>
            )}
          </div>
        );
      }
      
      // Otherwise, try to parse and format the raw text content
      const parts = parseMessageParts(content);
      return (
        <div className="ml-9 mt-2 space-y-2">
          <div className={`text-sm font-medium ${THEME.text.primary}`}>{parts.question}</div>
          
          {parts.context && (
            <div className={`text-xs ${THEME.text.secondary} pl-3 border-l-2 ${THEME.borders.default}`}>{parts.context}</div>
          )}
          
          {parts.options.length > 0 && (
            <div>
              <div className={`text-xs font-medium ${THEME.text.secondary} mb-1`}>Options:</div>
              <ul className={`list-disc list-inside space-y-1 text-xs ${THEME.text.secondary} pl-3`}>
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
          {/* Answer Questions button - positioned right after parsed content */}
            {!hasSubsequentResponse && onAnswerQuestions && (
              <div className="mt-4 flex justify-end">
                <button
                  onClick={onAnswerQuestions}
                  className={`px-4 py-2 rounded transition-colors text-sm ${THEME.buttons.primary}`}
                >
                  Answer Questions
                </button>
              </div>
            )}
        </div>
      );
    };

    return (
      <div>
        {renderHeader()}
        {!isCollapsed && (
          renderContent()
        )}
      </div>
    );
};

export default ClarificationMessage; 