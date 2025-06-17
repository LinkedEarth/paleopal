import { useQuery } from '@tanstack/react-query';
import { buildApiUrl, apiRequest } from '../config/api';
import API_CONFIG from '../config/api';

/**
 * Fetch messages for a conversation.
 * @param {string|null} conversationId - id of conversation
 * @param {boolean} includeProgress - whether to include node progress messages
 */
const fetchMessages = async (conversationId, includeProgress = false) => {
  if (!conversationId) return [];
  const url = buildApiUrl(
    `${API_CONFIG.ENDPOINTS.MESSAGES}/conversation/${conversationId}?include_progress=${includeProgress}`
  );
  return apiRequest(url);
};

export const useConversationMessages = (
  conversationId,
  includeProgress = false,
  shouldPoll = false,
  pollingMs = 2_000,
) => {
  return useQuery({
    queryKey: ['messages', conversationId, includeProgress],
    queryFn: () => fetchMessages(conversationId, includeProgress),
    enabled: Boolean(conversationId),
    refetchInterval: shouldPoll ? pollingMs : false,
  });
}; 