import { useEffect, useRef } from 'react';
import API_CONFIG from '../config/api';

/**
 * Builds a WebSocket URL that points at the same host/port as the REST API
 * (if explicitly configured) – otherwise it falls back to the current page
 * host. This lets us develop with a React dev-server on :3000 talking to a
 * FastAPI backend on :8000 while seamlessly working in production where both
 * are served behind the same origin.
 */
const buildWsUrl = (conversationId) => {
  // Default to current page host (works in production / Docker)
  let host = window.location.host;
  let proto = window.location.protocol === 'https:' ? 'wss' : 'ws';

  // If an explicit REST base URL is configured (e.g. http://localhost:8000)
  // then point the WebSocket at that same host instead of the dev server.
  if (API_CONFIG?.BASE_URL) {
    try {
      const url = new URL(API_CONFIG.BASE_URL);
      host = url.host;
      proto = url.protocol === 'https:' ? 'wss' : 'ws';
    } catch (_) {
      // BASE_URL may be relative – ignore and keep defaults
    }
  }

  return `${proto}://${host}/ws/conversations/${conversationId}`;
};

/**
 * Establishes a WebSocket connection for a conversation and forwards
 * incoming events to the provided callback.
 *
 * @param {string|null} conversationId
 * @param {(event:object)=>void} onEvent
 */
export const useConversationSocket = (conversationId, onEvent) => {
  const socketRef = useRef(null);
  const onEventRef = useRef(onEvent);

  // Keep the latest callback without re-establishing the WS connection
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!conversationId) return;

    const wsUrl = buildWsUrl(conversationId);
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data?.type === 'progress') {
          console.debug(
            'WS progress',
            data.message.node_name,
            data.message.phase,
            data.message.id,
          );
        }        
        onEventRef.current && onEventRef.current(data);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      socketRef.current = null;
    };

    return () => {
      ws.close();
    };
  }, [conversationId]);
}; 