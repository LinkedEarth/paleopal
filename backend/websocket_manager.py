from typing import Dict, List, Any
import asyncio
import logging
import json
from datetime import datetime
from fastapi import WebSocket

logger = logging.getLogger(__name__)

def make_json_serializable(obj, _seen=None):
    """Convert objects to JSON-serializable format with circular reference detection."""
    if _seen is None:
        _seen = set()
    
    # Check for circular references
    obj_id = id(obj)
    if obj_id in _seen:
        return f"<Circular reference to {type(obj).__name__}>"
    
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (list, tuple)):
        _seen.add(obj_id)
        try:
            result = [make_json_serializable(item, _seen) for item in obj]
        finally:
            _seen.remove(obj_id)
        return result
    elif isinstance(obj, dict):
        _seen.add(obj_id)
        try:
            result = {key: make_json_serializable(value, _seen) for key, value in obj.items()}
        finally:
            _seen.remove(obj_id)
        return result
    elif hasattr(obj, 'dict'):
        # Pydantic model - convert to dict first
        _seen.add(obj_id)
        try:
            result = make_json_serializable(obj.dict(), _seen)
        finally:
            _seen.remove(obj_id)
        return result
    elif hasattr(obj, '__dict__'):
        # Object with attributes - convert to dict with size limit for safety
        _seen.add(obj_id)
        try:
            obj_dict = obj.__dict__
            # Limit the number of attributes to prevent massive serialization
            if len(obj_dict) > 50:
                return f"<{type(obj).__name__} object with {len(obj_dict)} attributes>"
            result = make_json_serializable(obj_dict, _seen)
        except Exception:
            # If serialization fails, just return a string representation
            result = f"<{type(obj).__name__} object>"
        finally:
            _seen.remove(obj_id)
        return result
    else:
        # Fallback - convert to string
        return str(obj)

class WebSocketManager:
    """Central manager for per-conversation WebSocket connections"""
    def __init__(self):
        # {conv_id: [WebSocket, ...]}
        self.active: Dict[str, List[WebSocket]] = {}
        self._main_loop = None

    def set_event_loop(self, loop):
        """Set the main event loop for thread-safe operations."""
        self._main_loop = loop

    async def connect(self, conv_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(conv_id, []).append(websocket)
        
        # Store the event loop if not already stored
        if self._main_loop is None:
            try:
                self._main_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        
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

        # Send to all connections with proper async handling
        disconnected = []
        for ws in connections:
            try:
                # Check if we're in an async context
                try:
                    current_loop = asyncio.get_running_loop()
                    # We're in an async context - create task
                    asyncio.create_task(self._send_message(ws, message_json))
                except RuntimeError:
                    # No running event loop - we're in a sync context (like thread pool)
                    # Use the stored main loop if available
                    if self._main_loop and self._main_loop.is_running():
                        try:
                            # Schedule the coroutine to run in the main event loop
                            future = asyncio.run_coroutine_threadsafe(
                                self._send_message(ws, message_json), 
                                self._main_loop
                            )
                            # Don't wait for the result to avoid blocking
                            logger.debug(f"📤 Scheduled WebSocket message from thread to main loop")
                        except Exception as e:
                            logger.warning(f"Failed to schedule WebSocket message: {e}")
                            # Don't disconnect on scheduling failures - the connection might still be good
                    else:
                        logger.warning(f"No main event loop available for WebSocket message")
                        # Don't disconnect - the loop might become available later
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                # Only disconnect on actual connection errors, not scheduling errors
                if "connection" in str(e).lower() or "closed" in str(e).lower():
                    disconnected.append(ws)

        # Clean up only actually disconnected WebSockets
        for ws in disconnected:
            self.disconnect(conv_id, ws)

        sent_count = len(connections) - len(disconnected)
        if sent_count > 0:
            logger.debug(f"📡 Broadcasted message to {sent_count} WebSocket connections for conversation {conv_id}")
        else:
            logger.warning(f"⚠️ Failed to send message to any WebSocket connections for conversation {conv_id}")

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

    def send_to_conversation(self, conv_id: str, message: Dict[str, Any]):
        """Alias for broadcast method for better readability."""
        self.broadcast(conv_id, message)

    def send_execution_update(self, conv_id: str, execution_id: str, status: str, **kwargs):
        """Send an execution status update to all clients in a conversation."""
        message = {
            "type": "execution_update",
            "execution_id": execution_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        self.send_to_conversation(conv_id, message)

# Global instance
ws_manager = WebSocketManager() 
websocket_manager = ws_manager  # Alias for consistency 