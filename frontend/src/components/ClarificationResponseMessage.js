import React from 'react';

// Component to render clarification responses in a nice format
const ClarificationResponseMessage = ({ content }) => {
    // Parse the clarification response content
    const parseContent = (text) => {
        if (!text) return { originalQuery: '', responses: [] };
        
        // Look for the pattern "Clarification responses for: "
        const originalQueryMatch = text.match(/Clarification responses for: "([^"]+)"/);
        const originalQuery = originalQueryMatch ? originalQueryMatch[1] : '';
        
        // Remove the header part to get the Q&A content
        let qaContent = text;
        if (originalQueryMatch) {
            qaContent = text.substring(originalQueryMatch.index + originalQueryMatch[0].length).trim();
        }
        
        // Try to parse question-answer pairs
        // Look for patterns like "Question text?: Answer text."
        const responses = [];
        
        // Split by sentence-ending punctuation followed by capital letters or common question words
        const sentences = qaContent.split(/(?<=[.!?])\s+(?=[A-Z]|Regarding|What|How|Which|Should|Do|Can|Will)/);
        
        let currentQuestion = '';
        let currentAnswer = '';
        
        for (let sentence of sentences) {
            sentence = sentence.trim();
            if (!sentence) continue;
            
            // Check if this looks like a question (ends with ?)
            if (sentence.includes('?')) {
                // If we have a previous Q&A pair, save it
                if (currentQuestion && currentAnswer) {
                    responses.push({
                        question: currentQuestion,
                        answer: currentAnswer
                    });
                }
                
                // Split question and answer if they're in the same sentence
                const parts = sentence.split('?');
                if (parts.length >= 2) {
                    currentQuestion = parts[0] + '?';
                    currentAnswer = parts.slice(1).join('?').replace(/^:\s*/, '').trim();
                } else {
                    currentQuestion = sentence;
                    currentAnswer = '';
                }
            } else if (currentQuestion && !currentAnswer) {
                // This sentence is likely the answer to the previous question
                currentAnswer = sentence;
            } else if (currentAnswer) {
                // Continue building the answer
                currentAnswer += ' ' + sentence;
            } else {
                // Standalone sentence, treat as both question and answer
                responses.push({
                    question: sentence.includes(':') ? sentence.split(':')[0] + '?' : sentence,
                    answer: sentence.includes(':') ? sentence.split(':').slice(1).join(':').trim() : 'Yes'
                });
            }
        }
        
        // Don't forget the last Q&A pair
        if (currentQuestion && currentAnswer) {
            responses.push({
                question: currentQuestion,
                answer: currentAnswer
            });
        }
        
        return { originalQuery, responses };
    };

    const { originalQuery, responses } = parseContent(content);

    return (
        <div className="space-y-4 bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <div className="text-sm font-medium text-green-800">Clarification Responses</div>
            </div>
            
            {originalQuery && (
                <div className="mb-4">
                    <div className="text-sm font-medium text-gray-700 mb-1">Original Request:</div>
                    <div className="text-gray-800 bg-white p-3 rounded border italic">"{originalQuery}"</div>
                </div>
            )}
            
            {responses.length > 0 ? (
                <div className="space-y-3">
                    <div className="text-sm font-medium text-gray-700">Your Answers:</div>
                    {responses.map((response, index) => (
                        <div key={index} className="bg-white border border-green-200 rounded-lg p-3">
                            <div className="text-sm font-medium text-gray-800 mb-2">
                                Q{responses.length > 1 ? ` ${index + 1}` : ''}: {response.question}
                            </div>
                            <div className="text-sm text-gray-700 bg-green-50 p-2 rounded border-l-3 border-l-green-400">
                                <strong>A:</strong> {response.answer}
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                // Fallback: just display the content with better formatting
                <div className="text-gray-800 bg-white p-3 rounded border">
                    {content}
                </div>
            )}
        </div>
    );
};

export default ClarificationResponseMessage; 