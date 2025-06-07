import React from 'react';
import { parseMessageParts } from '../utils/parse';

// Component to render formatted clarification messages
const ClarificationMessage = ({ content, clarificationQuestions }) => {
    // If we have multiple questions, use those
    if (clarificationQuestions && clarificationQuestions.length > 0) {
      return (
        <div className="space-y-4">
          {clarificationQuestions.map((question, index) => (
            <div key={question.id || index} className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              {clarificationQuestions.length > 1 && (
                <div className="text-sm font-medium text-yellow-800 mb-2">Question {index + 1}</div>
              )}
              <div className="text-gray-800 font-medium mb-2">{question.question}</div>
              
              {question.context && (
                <div className="text-sm text-gray-600 mb-3 bg-gray-50 p-3 rounded border">{question.context}</div>
              )}
              
              {question.choices && question.choices.length > 0 && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-gray-700">Options:</div>
                  <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
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
                        <li key={choiceIndex} className="text-gray-600">{choiceText}</li>
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
      <div className="space-y-4">
        <div className="text-gray-800 font-medium">{parts.question}</div>
        
        {parts.context && (
          <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded border">{parts.context}</div>
        )}
        
        {parts.options.length > 0 && (
          <div className="space-y-2">
            <div className="text-sm font-medium text-gray-700">Options:</div>
            <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
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
                  <li key={index} className="text-gray-600">{optionText}</li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    );
};

export default ClarificationMessage; 