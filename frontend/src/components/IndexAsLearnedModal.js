import React, { useState, useEffect } from 'react';
import { THEME } from '../styles/colorTheme';
import { buildApiUrl, apiRequest } from '../config/api';
import API_CONFIG from '../config/api';
import Icon from './Icon';

const IndexAsLearnedModal = ({ 
  isOpen, 
  onClose, 
  messageId, 
  agentType,
  hasCode,
  hasSparql,
  initialUserPrompt = '',
  allMessages = [],
  onSuccess,
  onError
}) => {
  const [userPrompt, setUserPrompt] = useState(initialUserPrompt);
  const [clarifications, setClarifications] = useState(['']);
  const [tags, setTags] = useState(['']);
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Extract clarifications from conversation
  const extractClarificationsFromConversation = () => {
    const clarificationTexts = [];
    
    // Look for clarification response messages
    allMessages.forEach(msg => {
      if (msg.messageType === 'clarification_response' || msg.role === 'user' && msg.content?.includes('Clarification responses')) {
        // Check if we have structured clarification responses
        if (msg.clarificationResponses && Array.isArray(msg.clarificationResponses) && msg.clarificationResponses.length > 0) {
          msg.clarificationResponses.forEach(response => {
            if (response.answer && response.answer.trim()) {
              clarificationTexts.push(response.answer.trim());
            }
          });
        }
      }
    });
    
    return clarificationTexts.length > 0 ? clarificationTexts : [''];
  };

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setUserPrompt(initialUserPrompt);
      const extractedClarifications = extractClarificationsFromConversation();
      setClarifications(extractedClarifications);
      setTags(['']);
      setDescription('');
    }
  }, [isOpen, initialUserPrompt, allMessages]);

  const handleClose = () => {
    if (!isSubmitting) {
      onClose();
    }
  };

  const addClarification = () => {
    setClarifications([...clarifications, '']);
  };

  const updateClarification = (index, value) => {
    const updated = [...clarifications];
    updated[index] = value;
    setClarifications(updated);
  };

  const removeClarification = (index) => {
    if (clarifications.length > 1) {
      setClarifications(clarifications.filter((_, i) => i !== index));
    }
  };

  const addTag = () => {
    setTags([...tags, '']);
  };

  const updateTag = (index, value) => {
    const updated = [...tags];
    updated[index] = value;
    setTags(updated);
  };

  const removeTag = (index) => {
    if (tags.length > 1) {
      setTags(tags.filter((_, i) => i !== index));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!userPrompt.trim()) {
      onError?.('User prompt is required');
      return;
    }

    // Validate that there's content to index
    const hasContentToIndex = (agentType === 'sparql' && hasSparql) || (agentType !== 'sparql' && hasCode);
    if (!hasContentToIndex) {
      onError?.('No content available to index');
      return;
    }

    setIsSubmitting(true);
    try {
      const requestData = {
        user_prompt: userPrompt.trim(),
        clarifications: clarifications.filter(c => c.trim()).map(c => c.trim()),
        tags: tags.filter(t => t.trim()).map(t => t.trim()),
        description: description.trim()
      };

      const url = buildApiUrl(`${API_CONFIG.ENDPOINTS.MESSAGES}/${messageId}/index-as-learned`);
      const response = await apiRequest(url, {
        method: 'POST',
        body: JSON.stringify(requestData)
      });

      if (response.success) {
        onSuccess?.(response);
        onClose();
      } else {
        onError?.('Failed to index as learned content');
      }
    } catch (error) {
      console.error('Error indexing as learned:', error);
      onError?.(error.message || 'Failed to index as learned content');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className={`${THEME.containers.card} rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto border ${THEME.borders.default}`}>
        {/* Header */}
        <div className={`flex justify-between items-center p-6 border-b ${THEME.borders.default}`}>
          <h2 className={`text-lg font-semibold ${THEME.text.primary} flex items-center gap-2`}>
            <Icon name="index" className="w-5 h-5" />
            Index as Learned Content
          </h2>
          <button
            onClick={handleClose}
            disabled={isSubmitting}
            className={`p-2 rounded ${THEME.interactive.hover} ${THEME.text.secondary}`}
          >
            <Icon name="close" className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Info about what will be indexed */}
          <div className={`p-4 rounded-lg border ${THEME.containers.secondary} ${THEME.borders.default}`}>
            <h3 className={`text-sm font-medium ${THEME.text.primary} mb-2`}>Content to be indexed:</h3>
            <div className="space-y-1 text-sm">
              {hasSparql && (
                <div className={`flex items-center gap-2 ${THEME.text.secondary}`}>
                  <Icon name="database" className="w-4 h-4" />
                  SPARQL Query → learned_sparql collection
                </div>
              )}
              {hasCode && agentType !== 'sparql' && (
                <div className={`flex items-center gap-2 ${THEME.text.secondary}`}>
                  <Icon name="code" className="w-4 h-4" />
                  Python Code → learned_code collection
                </div>
              )}
            </div>
          </div>

          {/* User Prompt */}
          <div>
            <label className={`block text-sm font-medium ${THEME.text.primary} mb-2`}>
              User Prompt *
            </label>
            <textarea
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              className={`w-full h-24 p-3 border ${THEME.borders.default} rounded ${THEME.containers.card} ${THEME.text.primary} resize-y`}
              placeholder="Enter the original user prompt that led to this code/query..."
              required
            />
            <p className={`text-xs ${THEME.text.muted} mt-1`}>
              This helps others understand the context and purpose of the code/query.
            </p>
          </div>

          {/* Clarifications */}
          <div>
            <label className={`block text-sm font-medium ${THEME.text.primary} mb-2`}>
              Clarifications (Optional)
            </label>
            <div className="space-y-2">
              {clarifications.map((clarification, index) => (
                <div key={index} className="flex gap-2">
                  <input
                    type="text"
                    value={clarification}
                    onChange={(e) => updateClarification(index, e.target.value)}
                    className={`flex-1 p-2 border ${THEME.borders.default} rounded ${THEME.containers.card} ${THEME.text.primary}`}
                    placeholder={`Clarification ${index + 1}...`}
                  />
                  {clarifications.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeClarification(index)}
                      className={`p-2 ${THEME.status.error.text} ${THEME.interactive.hover} rounded`}
                    >
                      <Icon name="delete" className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={addClarification}
                className={`text-sm ${THEME.status.info.text} ${THEME.interactive.hover} px-2 py-1 rounded flex items-center gap-1`}
              >
                <Icon name="add" className="w-4 h-4" />
                Add clarification
              </button>
            </div>
            <p className={`text-xs ${THEME.text.muted} mt-1`}>
              Any additional clarifications or refinements that were provided.
            </p>
          </div>

          {/* Tags */}
          <div>
            <label className={`block text-sm font-medium ${THEME.text.primary} mb-2`}>
              Tags (Optional)
            </label>
            <div className="space-y-2">
              {tags.map((tag, index) => (
                <div key={index} className="flex gap-2">
                  <input
                    type="text"
                    value={tag}
                    onChange={(e) => updateTag(index, e.target.value)}
                    className={`flex-1 p-2 border ${THEME.borders.default} rounded ${THEME.containers.card} ${THEME.text.primary}`}
                    placeholder={`Tag ${index + 1}...`}
                  />
                  {tags.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeTag(index)}
                      className={`p-2 ${THEME.status.error.text} ${THEME.interactive.hover} rounded`}
                    >
                      <Icon name="delete" className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={addTag}
                className={`text-sm ${THEME.status.info.text} ${THEME.interactive.hover} px-2 py-1 rounded flex items-center gap-1`}
              >
                <Icon name="add" className="w-4 h-4" />
                Add tag
              </button>
            </div>
            <p className={`text-xs ${THEME.text.muted} mt-1`}>
              Keywords to help categorize and find this content later.
            </p>
          </div>

          {/* Description */}
          <div>
            <label className={`block text-sm font-medium ${THEME.text.primary} mb-2`}>
              Additional Description (Optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={`w-full h-20 p-3 border ${THEME.borders.default} rounded ${THEME.containers.card} ${THEME.text.primary} resize-y`}
              placeholder="Any additional notes or description about this code/query..."
            />
            <p className={`text-xs ${THEME.text.muted} mt-1`}>
              Optional additional context or notes about the solution.
            </p>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={handleClose}
              disabled={isSubmitting}
              className={`px-4 py-2 ${THEME.buttons.secondary} rounded transition-colors duration-200`}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !userPrompt.trim()}
              className={`px-4 py-2 ${THEME.buttons.primary} rounded transition-colors duration-200 flex items-center gap-2`}
            >
              {isSubmitting ? (
                <>
                  <Icon name="spinner" />
                  Indexing...
                </>
              ) : (
                <>
                  <Icon name="index" className="w-4 h-4" />
                  Index as Learned
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default IndexAsLearnedModal; 