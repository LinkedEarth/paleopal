from typing import Dict, List, Any
import asyncio
import logging
import json
from datetime import datetime
from fastapi import WebSocket

logger = logging.getLogger(__name__)

def make_json_serializable(obj):
    """Convert objects to JSON-serializable format."""
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif hasattr(obj, 'dict'):
        # Pydantic model - convert to dict first
        return make_json_serializable(obj.dict())
    elif hasattr(obj, '__dict__'):
        # Object with attributes - convert to dict
        return make_json_serializable(obj.__dict__)
    else:
        # Fallback - convert to string
        return str(obj)

class WebSocketManager:
    """Central manager for per-conversation WebSocket connections"""
    def __init__(self):
        # {conv_id: [WebSocket, ...]}
        self.active: Dict[str, List[WebSocket]] = {}

    async def connect(self, conv_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(conv_id, []).append(websocket)
        logger.info(f"✅ WebSocket connected for conversation {conv_id}. Total connections: {len(self.active.get(conv_id, []))}")

    def disconnect(self, conv_id: str, websocket: WebSocket):
        conns = self.active.get(conv_id)
        if conns and websocket in conns:
            conns.remove(websocket)
            logger.info(f"❌ WebSocket disconnected for conversation {conv_id}. Remaining connections: {len(conns)}")
            if not conns:
                del self.active[conv_id]
                logger.info(f"🔌 All WebSocket connections closed for conversation {conv_id}")

    def broadcast(self, conv_id: str, message: Dict[str, Any]):
        """Send a message to all active WebSocket connections for a conversation."""
        connections = self.active.get(conv_id, [])
        if not connections:
            logger.debug(f"No active WebSocket connections for conversation {conv_id}")
            return

        # Make the message JSON serializable
        try:
            serializable_message = make_json_serializable(message)
            message_json = json.dumps(serializable_message)
        except Exception as e:
            logger.error(f"❌ Failed to serialize WebSocket message: {e}")
            logger.error(f"Message data: {message}")
            return

        # Send to all connections
        disconnected = []
        for ws in connections:
            try:
                # Use asyncio.create_task to avoid blocking
                asyncio.create_task(self._send_message(ws, message_json))
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                disconnected.append(ws)

        # Clean up disconnected WebSockets
        for ws in disconnected:
            self.disconnect(conv_id, ws)

        logger.debug(f"📡 Broadcasted message to {len(connections) - len(disconnected)} WebSocket connections for conversation {conv_id}")

    async def _send_message(self, websocket: WebSocket, message_json: str):
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_text(message_json)
        except Exception as e:
            logger.warning(f"Failed to send message to WebSocket: {e}")
            raise

    def get_connection_count(self, conv_id: str) -> int:
        """Get the number of active connections for a conversation"""
        return len(self.active.get(conv_id, []))

    def get_all_connections(self) -> Dict[str, int]:
        """Get connection counts for all conversations"""
        return {conv_id: len(conns) for conv_id, conns in self.active.items()}

# Global instance
ws_manager = WebSocketManager() 