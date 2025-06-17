from typing import Dict, List, Any
import asyncio
from fastapi import WebSocket

class WebSocketManager:
    """Central manager for per-conversation WebSocket connections"""
    def __init__(self):
        # {conv_id: [WebSocket, ...]}
        self.active: Dict[str, List[WebSocket]] = {}

    async def connect(self, conv_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(conv_id, []).append(websocket)

    def disconnect(self, conv_id: str, websocket: WebSocket):
        conns = self.active.get(conv_id)
        if conns and websocket in conns:
            conns.remove(websocket)
            if not conns:
                self.active.pop(conv_id, None)

    async def _broadcast(self, conv_id: str, payload: Any):
        conns = list(self.active.get(conv_id, []))
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                # cleanup broken socket
                self.disconnect(conv_id, ws)

    def broadcast(self, conv_id: str, payload: Any):
        """Thread-safe helper usable from sync code. Schedules async send."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self._broadcast(conv_id, payload))
        else:
            # during startup / tests – run directly
            loop.run_until_complete(self._broadcast(conv_id, payload))

# singleton
ws_manager = WebSocketManager() 