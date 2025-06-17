from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websocket_manager import ws_manager

router = APIRouter(prefix="/ws", tags=["websocket"])

@router.websocket("/conversations/{conv_id}")
async def conversation_socket(websocket: WebSocket, conv_id: str):
    await ws_manager.connect(conv_id, websocket)
    try:
        while True:
            # We don't expect messages from client; just keep alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(conv_id, websocket) 