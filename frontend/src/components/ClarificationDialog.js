import React, { useState } from 'react';
import { THEME } from '../styles/colorTheme';
import Icon from './Icon';

const ClarificationDialog = ({ 
  isOpen, 
  onClose, 
  clarificationQuestions, 
  onSubmit,
  isSubmitting = false 
}) => {
  const [answers, setAnswers] = useState({});

  // Initialize answers when dialog opens
  React.useEffect(() => {
    if (isOpen && clarificationQuestions) {
      const initialAnswers = {};
      clarificationQuestions.forEach((question) => {
        initialAnswers[question.id] = '';
      });
      setAnswers(initialAnswers);
    }
  }, [isOpen, clarificationQuestions]);

  const handleAnswerChange = (questionId, value) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: value
    }));
  };

  const handleSubmit = () => {
    // Convert answers to the expected format
    const clarificationResponses = clarificationQuestions.map(question => ({
      question_id: question.id,
      question: question.question,
      answer: answers[question.id] || ''
    }));

    onSubmit(clarificationResponses);
  };

  const canSubmit = clarificationQuestions && clarificationQuestions.every(q => 
    answers[q.id] && answers[q.id].trim().length > 0
  );

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-2 sm:p-4">
      <div className={`${THEME.containers.card} rounded-lg shadow-xl max-w-2xl w-full max-h-[95vh] sm:max-h-[90vh] overflow-hidden border ${THEME.borders.default}`}>
        {/* Header */}
        <div className={`flex items-center justify-between p-3 sm:p-6 border-b ${THEME.borders.default}`}>
          <div className="flex items-center gap-2 sm:gap-3">
            <div className={`w-8 h-8 sm:w-10 sm:h-10 ${THEME.containers.secondary} rounded-full flex items-center justify-center`}>
              <Icon name="question" className={`${THEME.text.secondary} w-4 h-4 sm:w-5 sm:h-5`} />
            </div>
            <div>
              <h2 className={`text-base sm:text-lg font-semibold ${THEME.text.primary}`}>Answer Clarification Questions</h2>
              <p className={`text-xs sm:text-sm ${THEME.text.secondary}`}>
                {clarificationQuestions?.length || 0} {(clarificationQuestions?.length || 0) === 1 ? 'question' : 'questions'} require your input
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className={`p-1.5 sm:p-2 rounded-full ${THEME.interactive.hover} transition-colors`}
            disabled={isSubmitting}
          >
            <Icon name="close" className={`${THEME.text.muted} w-4 h-4 sm:w-5 sm:h-5`} />
          </button>
        </div>

        {/* Content */}
        <div className="p-3 sm:p-6 overflow-y-auto max-h-[calc(95vh-140px)] sm:max-h-[calc(90vh-180px)]">
          {clarificationQuestions && clarificationQuestions.length > 0 ? (
            <div className="space-y-4 sm:space-y-6">
              {clarificationQuestions.map((question, index) => (
                <div key={question.id || index} className="space-y-2 sm:space-y-3">
                  <div className="flex items-start gap-2 sm:gap-3">
                    <div className={`w-5 h-5 sm:w-6 sm:h-6 ${THEME.containers.secondary} rounded-full flex items-center justify-center flex-shrink-0 mt-1`}>
                      <span className={`text-xs font-medium ${THEME.text.secondary}`}>{index + 1}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className={`text-sm sm:text-base font-medium ${THEME.text.primary} mb-2`}>
                        {question.question}
                      </h3>
                      
                      {question.context && (
                        <div className={`text-xs sm:text-sm ${THEME.text.secondary} ${THEME.containers.secondary} p-2 sm:p-3 rounded-lg mb-2 sm:mb-3`}>
                          <div className={`font-medium ${THEME.text.primary} mb-1`}>Context:</div>
                          {question.context}
                        </div>
                      )}

                      {question.choices && question.choices.length > 0 && (
                        <div className="space-y-2 sm:space-y-3 mb-3 sm:mb-4">
                          <div className={`text-xs sm:text-sm font-medium ${THEME.text.primary}`}>Available options:</div>
                          <div className="space-y-1.5 sm:space-y-2">
                            {question.choices.map((choice, choiceIndex) => {
                              const choiceValue = typeof choice === 'string' ? choice : (choice.value || choice.description || choice.text || String(choice));
                              return (
                                <label key={choiceIndex} className={`flex items-center gap-2 sm:gap-3 p-2 border ${THEME.borders.default} rounded-lg ${THEME.interactive.hover} cursor-pointer`}>
                                  <input
                                    type="radio"
                                    name={`question-${question.id}`}
                                    value={choiceValue}
                                    checked={answers[question.id] === choiceValue}
                                    onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                                    className={`w-3.5 h-3.5 sm:w-4 sm:h-4 ${THEME.text.secondary} focus:ring-slate-500 ${THEME.containers.secondary}`}
                                  />
                                  <span className={`text-xs sm:text-sm ${THEME.text.primary}`}>{choiceValue}</span>
                                </label>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      <div className="space-y-1.5 sm:space-y-2">
                        <label className={`text-xs sm:text-sm font-medium ${THEME.text.primary}`}>
                          {question.choices && question.choices.length > 0 
                            ? "Your answer (select above or provide custom response):" 
                            : "Your answer:"
                          }
                        </label>
                        <textarea
                          value={answers[question.id] || ''}
                          onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                          placeholder={question.choices && question.choices.length > 0 
                            ? "You can select an option above or type a custom answer here..." 
                            : "Type your answer here..."
                          }
                          className={`w-full px-2 py-2 sm:px-3 sm:py-2 border rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 resize-none text-sm ${THEME.forms.textarea}`}
                          rows={2}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className={`text-center py-6 sm:py-8 ${THEME.text.muted}`}>
              No clarification questions available.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={`flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0 p-3 sm:p-6 border-t ${THEME.borders.default} ${THEME.containers.secondary}`}>
          <div className={`text-xs sm:text-sm ${THEME.text.secondary}`}>
            {clarificationQuestions && canSubmit ? (
              <span className={`${THEME.status.success.text}`}>✓ All questions answered</span>
            ) : (
              <span>Please answer all questions to continue</span>
            )}
          </div>
          <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto">
            <button
              onClick={onClose}
              disabled={isSubmitting}
              className={`flex-1 sm:flex-none px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-lg transition-colors disabled:opacity-50 ${THEME.buttons.secondary}`}
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!canSubmit || isSubmitting}
              className={`flex-1 sm:flex-none px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 ${THEME.buttons.primary}`}
            >
              {isSubmitting && (
                <Icon name="spinner" className="w-3 h-3 sm:w-4 sm:h-4 animate-spin" />
              )}
              Submit Answers
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ClarificationDialog; 