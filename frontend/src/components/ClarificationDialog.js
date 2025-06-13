import React, { useState } from 'react';

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
    <div className="fixed inset-0 bg-neutral-900 bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-neutral-200 dark:border-neutral-600">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-neutral-100 dark:bg-neutral-600 rounded-full flex items-center justify-center">
              <svg className="w-5 h-5 text-neutral-600 dark:text-neutral-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">Answer Clarification Questions</h2>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                {clarificationQuestions?.length || 0} {(clarificationQuestions?.length || 0) === 1 ? 'question' : 'questions'} require your input
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
            disabled={isSubmitting}
          >
            <svg className="w-5 h-5 text-neutral-500 dark:text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-180px)]">
          {clarificationQuestions && clarificationQuestions.length > 0 ? (
            <div className="space-y-6">
              {clarificationQuestions.map((question, index) => (
                <div key={question.id || index} className="space-y-3">
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 bg-neutral-100 dark:bg-neutral-600 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                      <span className="text-xs font-medium text-neutral-600 dark:text-neutral-300">{index + 1}</span>
                    </div>
                    <div className="flex-1">
                      <h3 className="text-base font-medium text-neutral-900 dark:text-neutral-100 mb-2">
                        {question.question}
                      </h3>
                      
                      {question.context && (
                        <div className="text-sm text-neutral-600 dark:text-neutral-400 bg-neutral-50 dark:bg-neutral-700 p-3 rounded-lg mb-3">
                          <div className="font-medium text-neutral-700 dark:text-neutral-300 mb-1">Context:</div>
                          {question.context}
                        </div>
                      )}

                      {question.choices && question.choices.length > 0 && (
                        <div className="space-y-3 mb-4">
                          <div className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Available options:</div>
                          <div className="space-y-2">
                            {question.choices.map((choice, choiceIndex) => {
                              const choiceValue = typeof choice === 'string' ? choice : (choice.value || choice.description || choice.text || String(choice));
                              return (
                                <label key={choiceIndex} className="flex items-center gap-3 p-2 border border-neutral-200 dark:border-neutral-600 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-700 cursor-pointer">
                                  <input
                                    type="radio"
                                    name={`question-${question.id}`}
                                    value={choiceValue}
                                    checked={answers[question.id] === choiceValue}
                                    onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                                    className="w-4 h-4 text-neutral-600 dark:text-neutral-400 focus:ring-neutral-500 dark:bg-neutral-600"
                                  />
                                  <span className="text-sm text-neutral-700 dark:text-neutral-300">{choiceValue}</span>
                                </label>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      <div className="space-y-2">
                        <label className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
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
                          className="w-full px-3 py-2 border border-neutral-200 dark:border-neutral-600 rounded-lg focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500 resize-none bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-500 dark:placeholder:text-neutral-400"
                          rows={3}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-neutral-500 dark:text-neutral-400">
              No clarification questions available.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-neutral-200 dark:border-neutral-600 bg-neutral-50 dark:bg-neutral-700">
          <div className="text-sm text-neutral-600 dark:text-neutral-400">
            {clarificationQuestions && canSubmit ? (
              <span className="text-green-600 dark:text-green-400">✓ All questions answered</span>
            ) : (
              <span>Please answer all questions to continue</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm font-medium text-neutral-700 dark:text-neutral-300 bg-white dark:bg-neutral-600 border border-neutral-300 dark:border-neutral-500 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-500 transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!canSubmit || isSubmitting}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 dark:bg-blue-600 rounded-lg hover:bg-blue-700 dark:hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isSubmitting && (
                <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
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