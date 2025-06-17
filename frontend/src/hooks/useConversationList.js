import { useQuery } from '@tanstack/react-query';
import { buildApiUrl, apiRequest } from '../config/api';
import API_CONFIG from '../config/api';

const fetchConversations = async () => {
  const url = buildApiUrl(`${API_CONFIG.ENDPOINTS.CONVERSATIONS}/`);
  return apiRequest(url);
};

/**
 * React-Query hook that returns the list of conversations.
 * Automatically refetches every 10 s so the UI stays fresh.
 */
export const useConversationList = () => {
  return useQuery({
    queryKey: ['conversations'],
    queryFn: fetchConversations,
    staleTime: 30_000,   // data considered fresh for 30 s
    refetchInterval: 10_000,
  });
}; 