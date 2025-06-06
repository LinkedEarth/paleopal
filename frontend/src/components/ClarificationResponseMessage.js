import React from 'react';

// Component to render clarification responses in a nice format
const ClarificationResponseMessage = ({ content }) => {
    console.log('ClarificationResponseMessage rendering with content:', content);
    console.log('Content type:', typeof content);
    console.log('Content length:', content ? content.length : 'null/undefined');
    
    // Fallback for empty or invalid content
    if (!content || typeof content !== 'string' || content.trim().length === 0) {
      console.error('ClarificationResponseMessage: Invalid or empty content');
      return (
        <div className="clarification-response-content">
          <div className="clarification-response-header">
            <span className="response-icon">⚠</span>
            Error: No content to display
          </div>
          <div style={{ padding: '1rem', backgroundColor: 'rgba(255, 0, 0, 0.1)' }}>
            Content is empty or invalid. Raw content: {JSON.stringify(content)}
          </div>
        </div>
      );
    }
    
    // Parse the Q&A pairs and additional comments from the content
    const lines = content.split('\n');
    const qaPairs = [];
    let additionalComment = '';
    
    let currentQ = '';
    let currentA = '';
    let inAdditionalComment = false;
    
    console.log('Parsing lines:', lines);
    
    for (const line of lines) {
      if (line.startsWith('Q: ')) {
        // If we have a previous Q&A pair, save it
        if (currentQ && currentA) {
          qaPairs.push({ question: currentQ, answer: currentA });
        }
        currentQ = line.substring(3);
        currentA = '';
        inAdditionalComment = false;
      } else if (line.startsWith('A: ')) {
        currentA = line.substring(3);
      } else if (line.startsWith('Additional comment: ')) {
        additionalComment = line.substring(20);
        inAdditionalComment = true;
      } else if (inAdditionalComment && line.trim()) {
        additionalComment += '\n' + line;
      }
    }
    
    // Add the last Q&A pair if it exists
    if (currentQ && currentA) {
      qaPairs.push({ question: currentQ, answer: currentA });
    }
    
    console.log('Parsed qaPairs:', qaPairs);
    console.log('Additional comment:', additionalComment);
    
    // If no Q&A pairs found, treat the entire content as a single response
    if (qaPairs.length === 0) {
      console.log('No Q&A pairs found, treating as plain text response');
      return (
        <div className="clarification-response-content">
          <div className="clarification-response-header">
            <span className="response-icon">✓</span>
            Clarification Responses
          </div>
          <div style={{ 
            padding: '1rem', 
            backgroundColor: 'white', 
            borderRadius: '0.75rem',
            border: '1px solid rgba(46, 204, 113, 0.2)',
            minHeight: '60px'
          }}>
            <div style={{ fontSize: '0.95rem', lineHeight: '1.4', color: '#333' }}>
              {content}
            </div>
          </div>
        </div>
      );
    }
    
    return (
      <div className="clarification-response-content">
        <div className="clarification-response-header">
          <span className="response-icon">✓</span>
          Clarification Responses
        </div>
        
        <div className="clarification-qa-pairs">
          {qaPairs.map((pair, index) => (
            <div key={index} className="qa-pair">
              <div className="qa-question">
                <span className="qa-label">Q:</span>
                <span className="qa-text">{pair.question}</span>
              </div>
              <div className="qa-answer">
                <span className="qa-label">A:</span>
                <span className="qa-text">{pair.answer}</span>
              </div>
            </div>
          ))}
        </div>
        
        {additionalComment && (
          <div className="additional-comment">
            <div className="comment-label">Additional comment:</div>
            <div className="comment-text">{additionalComment}</div>
          </div>
        )}
      </div>
    );
};

export default ClarificationResponseMessage; 