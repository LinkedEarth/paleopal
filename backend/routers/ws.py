from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websocket_manager import ws_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

@router.websocket("/conversations/{conv_id}")
async def conversation_socket(websocket: WebSocket, conv_id: str):
    logger.info(f"🔌 WebSocket connection attempt for conversation: {conv_id}")
    try:
        await ws_manager.connect(conv_id, websocket)
        logger.info(f"✅ WebSocket connection established for conversation: {conv_id}")
        
        while True:
            # We don't expect messages from client; just keep alive
            # This will block until client sends something or disconnects
            await websocket.receive_text()
            logger.debug(f"📨 Received keep-alive from WebSocket for conversation: {conv_id}")
            
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected for conversation: {conv_id}")
        ws_manager.disconnect(conv_id, websocket)
    except Exception as e:
        logger.error(f"❌ WebSocket error for conversation {conv_id}: {e}")
        ws_manager.disconnect(conv_id, websocket)

@router.get("/debug/connections")
async def get_websocket_connections():
    """Debug endpoint to check WebSocket connection status"""
    return {
        "active_connections": ws_manager.get_all_connections(),
        "total_conversations": len(ws_manager.active),
        "total_connections": sum(len(conns) for conns in ws_manager.active.values())
    } 