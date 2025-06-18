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
  isWebSocketConnected = false,
  pollingMs = 10_000, // Increased default from 2s to 10s
) => {
  return useQuery({
    queryKey: ['messages', conversationId, includeProgress],
    queryFn: () => fetchMessages(conversationId, includeProgress),
    enabled: Boolean(conversationId),
    // Only poll if explicitly requested AND WebSocket is not connected
    // This prevents conflicts between WebSocket real-time updates and polling
    refetchInterval: (shouldPoll && !isWebSocketConnected) ? pollingMs : false,
    // Reduce background refetching
    refetchIntervalInBackground: false,
    // Don't refetch on window focus to reduce noise
    refetchOnWindowFocus: false,
    // Increase stale time to reduce unnecessary refetches
    staleTime: 30_000, // 30 seconds
  });
}; 