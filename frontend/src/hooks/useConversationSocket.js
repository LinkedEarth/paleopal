import { useEffect, useRef, useCallback } from 'react';
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
  const connectionStateRef = useRef('disconnected'); // 'connecting', 'connected', 'disconnected'
  const reconnectTimeoutRef = useRef(null);
  const currentConversationRef = useRef(null);

  // Memoize the callback to prevent unnecessary re-renders
  const stableOnEvent = useCallback((event) => {
    if (onEventRef.current) {
      onEventRef.current(event);
    }
  }, []);

  // Keep the latest callback without re-establishing the WS connection
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  // Cleanup function
  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (socketRef.current) {
      const ws = socketRef.current;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        console.debug('🔌 Closing WebSocket for conversation:', currentConversationRef.current);
        ws.close();
      }
      socketRef.current = null;
    }
    connectionStateRef.current = 'disconnected';
  }, []);

  // Reconnection logic
  const attemptReconnect = useCallback((convId, delay = 1000) => {
    if (!convId || currentConversationRef.current !== convId) {
      return; // Don't reconnect if conversation changed
    }
    
    console.debug('🔄 Attempting WebSocket reconnection in', delay, 'ms for conversation:', convId);
    reconnectTimeoutRef.current = setTimeout(() => {
      if (currentConversationRef.current === convId && connectionStateRef.current === 'disconnected') {
        console.debug('🔄 Reconnecting WebSocket for conversation:', convId);
        connectWebSocket(convId);
      }
    }, delay);
  }, []);

  // Main connection function
  const connectWebSocket = useCallback((convId) => {
    if (!convId) {
      connectionStateRef.current = 'disconnected';
      return;
    }

    // Don't create duplicate connections
    if (socketRef.current && 
        (socketRef.current.readyState === WebSocket.OPEN || socketRef.current.readyState === WebSocket.CONNECTING)) {
      console.debug('🔌 WebSocket already connected/connecting for conversation:', convId);
      return;
    }

    cleanup(); // Clean up any existing connection

    connectionStateRef.current = 'connecting';
    currentConversationRef.current = convId;
    
    const wsUrl = buildWsUrl(convId);
    console.debug('🔌 Connecting WebSocket to:', wsUrl);
    
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      console.debug('✅ WebSocket connected for conversation:', convId);
      connectionStateRef.current = 'connected';
      // Clear any pending reconnection attempts
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        console.debug('📨 WebSocket message received:', data.type, data);
        if (data?.type === 'progress') {
          console.debug(
            'WS progress',
            data.message.node_name,
            data.message.phase,
            data.message.id,
          );
        }        
        stableOnEvent(data);
      } catch (error) {
        console.warn('Failed to parse WebSocket message:', error, e.data);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error for conversation:', convId, error);
      connectionStateRef.current = 'disconnected';
    };

    ws.onclose = (event) => {
      console.debug('🔌 WebSocket closed for conversation:', convId, 'Code:', event.code, 'Reason:', event.reason);
      socketRef.current = null;
      connectionStateRef.current = 'disconnected';
      
      // Attempt reconnection if this is still the current conversation and closure wasn't intentional
      if (currentConversationRef.current === convId && event.code !== 1000) {
        console.debug('🔄 WebSocket closed unexpectedly, scheduling reconnection');
        attemptReconnect(convId, 2000); // Reconnect after 2 seconds
      }
    };
  }, [cleanup, stableOnEvent, attemptReconnect]);

  useEffect(() => {
    if (!conversationId) {
      cleanup();
      currentConversationRef.current = null;
      return;
    }

    // If conversation changed, clean up and connect to new one
    if (currentConversationRef.current !== conversationId) {
      console.debug('🔄 Conversation changed from', currentConversationRef.current, 'to', conversationId);
      cleanup();
      connectWebSocket(conversationId);
    }

    return cleanup;
  }, [conversationId, connectWebSocket, cleanup]);

  // Return connection state for debugging
  return {
    isConnected: connectionStateRef.current === 'connected',
    connectionState: connectionStateRef.current
  };
}; 