// Helper to parse message parts
export const parseMessageParts = (content) => {
    // Default structure
    const result = {
      question: content,
      options: [],
      context: ''
    };
    
    try {
      // Check if the content has multiple questions
      const questionBlocks = content.split(/Question \d+:/);
      
      if (questionBlocks.length > 1) {
        // We have multiple questions - parse the first one for display
        const firstBlock = questionBlocks[1] || '';
        
        // Extract the main question (first line of the block)
        const lines = firstBlock.split('\n').filter(line => line.trim());
        if (lines.length > 0) {
          result.question = lines[0].trim();
        }
        
        // Extract options if present
        if (firstBlock.includes('Options:')) {
          const optionsSection = firstBlock.split('Options:')[1].split('\n\n')[0];
          result.options = optionsSection
            .split('\n')
            .filter(line => line.trim().startsWith('-'))
            .map(line => line.trim().substring(2).trim());
        }
        
        // Extract context (text after options, before state_id)
        const contextMatch = firstBlock.match(/(?:Options:[^]*?\n\n)?(.*?)$/s);
        if (contextMatch && contextMatch[1].trim()) {
          result.context = contextMatch[1].trim();
        }
        
        return result;
      }
      
      // Original single question parsing logic
      // Extract the main question (usually the first paragraph)
      const paragraphs = content.split('\n\n').filter(p => p.trim().length > 0);
      if (paragraphs.length > 0) {
        result.question = paragraphs[0].trim();
      }
      
      // Extract options if present
      if (content.includes('Options:')) {
        const optionsSection = content.split('Options:')[1].split('\n\n')[0];
        result.options = optionsSection
          .split('\n')
          .filter(line => line.trim().startsWith('-'))
          .map(line => line.trim().substring(2).trim());
      }
      
      // Try to extract context (usually the last paragraph if not options)
      if (paragraphs.length > 1 && !paragraphs[paragraphs.length - 1].includes('Options:') && 
          true) {
        result.context = paragraphs[paragraphs.length - 1].trim();
      }
      
      return result;
    } catch (error) {
      console.error('Error parsing message parts:', error);
      return result;
    }
};