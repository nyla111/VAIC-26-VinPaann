import logging
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.models import SystemState
from app.state import state_manager

logger = logging.getLogger(__name__)
router = APIRouter()

class ConnectionManager:
    """
    Manages active client WebSocket connections for real-time state streaming.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, state: SystemState):
        """
        Sends the SystemState JSON payload to all connected clients.
        """
        if not self.active_connections:
            return
            
        # Serialize model using Pydantic model_dump_json()
        payload = state.model_dump_json()
        
        disconnected_clients = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.error(f"Error broadcasting state to client: {e}")
                disconnected_clients.append(connection)

        # Cleanup failed connections
        for client in disconnected_clients:
            self.disconnect(client)


# Global WebSocket connection manager instance
ws_manager = ConnectionManager()


@router.websocket("/ws/status")
async def websocket_status_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.
    Sends current state immediately upon connection, then maintains a keep-alive listener.
    """
    await ws_manager.connect(websocket)
    
    # Send initial state snapshot immediately
    try:
        current_state = await state_manager.get_state()
        await websocket.send_text(current_state.model_dump_json())
    except Exception as e:
        logger.error(f"Failed to send initial state to socket: {e}")
        ws_manager.disconnect(websocket)
        return

    # Keep connection open and handle client-side disconnects
    try:
        while True:
            # We don't expect client messages, but reading is required to detect disconnection
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket execution error: {e}")
        ws_manager.disconnect(websocket)
