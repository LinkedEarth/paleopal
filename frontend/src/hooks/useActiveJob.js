import { useQuery } from '@tanstack/react-query';
import { buildApiUrl, apiRequest } from '../config/api';
import API_CONFIG from '../config/api';

/**
 * Hook that returns the currently running job (if any) for a conversation.
 * It polls until no running job is returned (i.e., job finished).
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

export const useActiveJob = (conversationId) => {
  return useQuery({
    queryKey: ['activeJob', conversationId],
    queryFn: () => fetchActiveJob(conversationId),
    enabled: Boolean(conversationId),
    refetchInterval: 2_000,
  });
}; 