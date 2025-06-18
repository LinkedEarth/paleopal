import { useQuery } from '@tanstack/react-query';
import { buildApiUrl, apiRequest } from '../config/api';
import API_CONFIG from '../config/api';

const fetchConversations = async () => {
  const url = buildApiUrl(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/`);
  return apiRequest(url);
};

/**
 * React-Query hook that returns the list of conversations.
 * Polls less frequently since conversation list changes are not time-critical.
 */
export const useConversationList = () => {
  return useQuery({
    queryKey: ['conversations'],
    queryFn: fetchConversations,
    staleTime: 60_000,   // data considered fresh for 60 s (increased from 30s)
    refetchInterval: 30_000, // Poll every 30s instead of 10s
    // Don't refetch in background to reduce noise
    refetchIntervalInBackground: false,
    // Don't refetch on window focus
    refetchOnWindowFocus: false,
  });
}; 