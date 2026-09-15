import asyncio
import logging
from fastapi import WebSocket
from typing import List, Optional

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for dc in dead_connections:
            self.disconnect(dc)

manager = ConnectionManager()

def sync_broadcast(message: dict):
    """Safely broadcasts a message from either an async handler or a sync threadpool worker."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(message))
        return
    except RuntimeError:
        pass

    # Threadpool fallback: dispatch to the main event loop if available
    if manager.loop and manager.loop.is_running():
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), manager.loop)
    else:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                manager.loop = loop
                asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)
        except Exception as e:
            logger.debug(f"Could not broadcast message: {e}")

