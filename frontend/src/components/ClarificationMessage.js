import React from 'react';
import { parseMessageParts } from '../utils/parse';

// Component to render formatted clarification messages
const ClarificationMessage = ({ content, clarificationQuestions }) => {
    // If we have multiple questions, use those
    if (clarificationQuestions && clarificationQuestions.length > 0) {
      return (
        <div className="clarification-message-content">
          {clarificationQuestions.map((question, index) => (
            <div key={question.id || index} className="clarification-question-group">
              {clarificationQuestions.length > 1 && (
                <div className="question-number">Question {index + 1}</div>
              )}
              <div className="clarification-question">{question.question}</div>
              
              {question.context && (
                <div className="clarification-context">{question.context}</div>
              )}
              
              {question.choices && question.choices.length > 0 && (
                <div className="clarification-choices">
                  <div className="choices-label">Options:</div>
                  <ul className="choices-list">
                    {question.choices.map((choice, choiceIndex) => (
                      <li key={choiceIndex} className="choice-item">{choice}</li>
                    ))}
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
      <div className="clarification-message-content">
        <div className="clarification-question">{parts.question}</div>
        
        {parts.context && (
          <div className="clarification-context">{parts.context}</div>
        )}
        
        {parts.options.length > 0 && (
          <div className="clarification-choices">
            <div className="choices-label">Options:</div>
            <ul className="choices-list">
              {parts.options.map((option, index) => (
                <li key={index} className="choice-item">{option}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
};

export default ClarificationMessage; 