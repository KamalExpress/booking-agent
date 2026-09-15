"""
WebSocket Manager & Pure Transport Bridge Consumer
===================================================
WebSocket is strictly a downstream transport bridge/consumer, NOT an event source.
WebSocketBridgeConsumer reads from Redis Streams group 'ws-bridge' and relays to UI clients.
"""

import asyncio
import logging
from typing import List, Optional
from fastapi import WebSocket

from core.event_bus import event_bus, EventBusException

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active browser WebSocket connections for live UI rendering."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_to_clients(self, message: dict):
        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for dc in dead_connections:
            self.disconnect(dc)


manager = ConnectionManager()


class WebSocketBridgeConsumer:
    """
    Dedicated background consumer subscribing to Redis Streams topic 'events:pipeline'
    via consumer group 'ws-bridge' and relaying to connected browser clients.
    """

    def __init__(self, topic: str = "events:pipeline", group_name: str = "ws-bridge", consumer_name: str = "ws-worker-1"):
        self.topic = topic
        self.group_name = group_name
        self.consumer_name = consumer_name
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self._running = True
        backend = event_bus.backend
        try:
            backend.create_consumer_group(self.topic, self.group_name, start_id="$")
        except Exception as e:
            logger.debug(f"Consumer group setup info: {e}")

        self._task = asyncio.create_task(self._consume_loop())
        logger.info(f"WebSocketBridgeConsumer started on topic '{self.topic}' (group: '{self.group_name}')")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _consume_loop(self):
        backend = event_bus.backend
        while self._running:
            try:
                # Non-blocking async sleep with thread-safe execution of read_group
                events = await asyncio.to_thread(
                    backend.read_group,
                    self.topic,
                    self.group_name,
                    self.consumer_name,
                    count=20,
                    block_ms=1000
                )

                if events:
                    ack_ids = []
                    for ev in events:
                        msg_id = ev.get("msg_id")
                        if msg_id:
                            ack_ids.append(msg_id)

                        # Relay formatted event envelope to connected UI browsers
                        await manager.broadcast_to_clients({
                            "event_type": ev.get("event_type"),
                            "worker_id": ev.get("worker_id"),
                            "source": ev.get("source"),
                            "payload": ev.get("payload"),
                            "timestamp": ev.get("timestamp")
                        })

                    if ack_ids:
                        await asyncio.to_thread(backend.ack, self.topic, self.group_name, ack_ids)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"WebSocketBridgeConsumer poll error: {e}")
                await asyncio.sleep(2)


ws_bridge = WebSocketBridgeConsumer()
