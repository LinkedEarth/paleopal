import { useQuery } from '@tanstack/react-query';
import { buildApiUrl, apiRequest } from '../config/api';
import API_CONFIG from '../config/api';

/**
 * Hook that returns the currently running job (if any) for a conversation.
 * It polls less frequently since WebSocket provides real-time updates.
 *
 * Backend endpoint supports filtering by conversation_id and state.
 */
const fetchActiveJob = async (conversationId) => {
  if (!conversationId) return null;
  const url = buildApiUrl(`${API_CONFIG.ENDPOINTS.JOBS}?conversation_id=${conversationId}&state=running`);
  const jobs = await apiRequest(url);
  if (Array.isArray(jobs) && jobs.length > 0) return jobs[0]; // latest running job
  return null;
};

export const useActiveJob = (conversationId, isWebSocketConnected = false) => {
  return useQuery({
    queryKey: ['activeJob', conversationId],
    queryFn: () => fetchActiveJob(conversationId),
    enabled: Boolean(conversationId),
    // Reduce polling frequency when WebSocket is connected, increase when it's not
    refetchInterval: isWebSocketConnected ? 10_000 : 5_000, // 10s with WS, 5s without
    // Reduce background refetching to prevent conflicts
    refetchIntervalInBackground: false,
    // Don't refetch on window focus to reduce noise
    refetchOnWindowFocus: false,
  });
}; 