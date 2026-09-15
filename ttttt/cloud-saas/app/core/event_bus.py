"""
Pluggable EventBus Architecture with Redis Streams Backend
===========================================================
Decoupled event pipeline supporting Redis Streams (hot operational log),
with pluggable backend interfaces (NATS/Kafka ready) and strict fail-visible semantics.
"""

import os
import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EventBusException(Exception):
    """Raised when event publication or subscription fails (strict fail-visible standard)."""
    pass


class EventBusBackend(ABC):
    """Abstract interface for all EventBus transport backends (Redis Streams, Kafka, NATS)."""

    @abstractmethod
    def publish(self, topic: str, event: Dict[str, Any], maxlen: int = 10000) -> str:
        """Publish an event to the stream/topic. Returns the message ID or offset."""
        pass

    @abstractmethod
    def create_consumer_group(self, topic: str, group_name: str, start_id: str = "$") -> bool:
        """Ensure a consumer group exists for the topic/stream."""
        pass

    @abstractmethod
    def read_group(
        self,
        topic: str,
        group_name: str,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 2000
    ) -> List[Dict[str, Any]]:
        """Read pending/new messages for a consumer group."""
        pass

    @abstractmethod
    def ack(self, topic: str, group_name: str, message_ids: List[str]) -> int:
        """Acknowledge processed message IDs."""
        pass

    @abstractmethod
    def close(self):
        """Close connection to backend."""
        pass


class RedisStreamsBackend(EventBusBackend):
    """Redis Streams implementation for hot operational event streaming."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            import redis
            self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)
            # Test connectivity immediately on initialization
            self.client.ping()
            logger.info(f"RedisStreamsBackend connected to {self.redis_url.split('@')[-1]}")
        except Exception as e:
            logger.error(f"RedisStreamsBackend connection error: {e}")
            raise EventBusException(f"Failed to connect to Redis at {self.redis_url}: {str(e)}")

    def publish(self, topic: str, event: Dict[str, Any], maxlen: int = 10000) -> str:
        try:
            # Flatten payload to JSON string inside stream dictionary
            stream_entry = {
                "event_id": event.get("event_id", str(uuid.uuid4())),
                "event_type": event.get("event_type", "UNKNOWN"),
                "source": event.get("source", "system"),
                "worker_id": event.get("worker_id", event.get("source", "system")),
                "tenant_id": str(event.get("tenant_id") or ""),
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "payload": json.dumps(event.get("payload", {}))
            }
            msg_id = self.client.xadd(topic, stream_entry, maxlen=maxlen, approximate=True)
            return str(msg_id)
        except Exception as e:
            logger.error(f"Redis Streams publish failed for topic '{topic}': {e}")
            raise EventBusException(f"Redis Streams publish failed: {str(e)}")

    def create_consumer_group(self, topic: str, group_name: str, start_id: str = "$") -> bool:
        try:
            self.client.xgroup_create(topic, group_name, id=start_id, mkstream=True)
            return True
        except Exception as e:
            # BUSYGROUP Consumer Group name already exists
            if "BUSYGROUP" in str(e):
                return False
            logger.error(f"Failed to create consumer group '{group_name}' on '{topic}': {e}")
            raise EventBusException(f"Consumer group creation failed: {str(e)}")

    def read_group(
        self,
        topic: str,
        group_name: str,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 2000
    ) -> List[Dict[str, Any]]:
        try:
            raw_entries = self.client.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={topic: ">"},
                count=count,
                block=block_ms
            )
            if not raw_entries:
                return []

            parsed_events = []
            for stream_name, messages in raw_entries:
                for msg_id, fields in messages:
                    payload_raw = fields.get("payload", "{}")
                    try:
                        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
                    except Exception:
                        payload = {"raw": payload_raw}

                    parsed_events.append({
                        "msg_id": msg_id,
                        "event_id": fields.get("event_id"),
                        "event_type": fields.get("event_type"),
                        "source": fields.get("source"),
                        "worker_id": fields.get("worker_id", fields.get("source")),
                        "tenant_id": fields.get("tenant_id"),
                        "timestamp": fields.get("timestamp"),
                        "payload": payload
                    })
            return parsed_events
        except Exception as e:
            logger.error(f"Redis Streams read_group failed: {e}")
            raise EventBusException(f"Redis Streams read failed: {str(e)}")

    def ack(self, topic: str, group_name: str, message_ids: List[str]) -> int:
        if not message_ids:
            return 0
        try:
            return self.client.xack(topic, group_name, *message_ids)
        except Exception as e:
            logger.error(f"Redis Streams ack failed: {e}")
            raise EventBusException(f"Redis Streams ack failed: {str(e)}")

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass


class InMemoryTestBackend(EventBusBackend):
    """In-memory event bus backend for testing and local verification."""

    def __init__(self):
        self.streams: Dict[str, List[Dict[str, Any]]] = {}
        self.groups: Dict[str, Dict[str, int]] = {}
        self.counter = 0

    def publish(self, topic: str, event: Dict[str, Any], maxlen: int = 10000) -> str:
        if topic not in self.streams:
            self.streams[topic] = []
        self.counter += 1
        msg_id = f"{int(datetime.now().timestamp()*1000)}-{self.counter}"
        entry = dict(event)
        entry["msg_id"] = msg_id
        if "timestamp" not in entry:
            entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.streams[topic].append(entry)
        if len(self.streams[topic]) > maxlen:
            self.streams[topic] = self.streams[topic][-maxlen:]
        return msg_id

    def create_consumer_group(self, topic: str, group_name: str, start_id: str = "$") -> bool:
        if topic not in self.groups:
            self.groups[topic] = {}
        if group_name in self.groups[topic]:
            return False
        start_idx = len(self.streams.get(topic, [])) if start_id == "$" else 0
        self.groups[topic][group_name] = start_idx
        return True

    def read_group(
        self,
        topic: str,
        group_name: str,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 2000
    ) -> List[Dict[str, Any]]:
        if topic not in self.streams:
            return []
        if topic not in self.groups or group_name not in self.groups[topic]:
            self.create_consumer_group(topic, group_name, start_id="0")

        idx = self.groups[topic][group_name]
        items = self.streams[topic][idx:idx+count]
        self.groups[topic][group_name] += len(items)
        return items

    def ack(self, topic: str, group_name: str, message_ids: List[str]) -> int:
        return len(message_ids)

    def close(self):
        self.streams.clear()
        self.groups.clear()


class EventBusFacade:
    """Singleton facade coordinating event publishing across pluggable backends."""

    def __init__(self):
        self._backend: Optional[EventBusBackend] = None

    def initialize(self, backend_type: Optional[str] = None, **kwargs) -> EventBusBackend:
        b_type = (backend_type or os.getenv("EVENTBUS_BACKEND", "redis")).lower()
        if b_type == "redis":
            redis_url = kwargs.get("redis_url") or os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self._backend = RedisStreamsBackend(redis_url=redis_url)
        elif b_type in ["inmemory", "test"]:
            self._backend = InMemoryTestBackend()
        else:
            raise EventBusException(f"Unsupported EventBus backend: {b_type}")
        return self._backend

    @property
    def backend(self) -> EventBusBackend:
        if self._backend is None:
            self.initialize()
        return self._backend

    def publish(
        self,
        topic: str,
        event_type: str,
        payload: Dict[str, Any],
        source: str = "system",
        worker_id: Optional[str] = None,
        tenant_id: Optional[int] = None,
        event_id: Optional[str] = None
    ) -> str:
        """Publishes an event to the specified topic/stream. Strict fail-visible semantics."""
        envelope = {
            "event_id": event_id or str(uuid.uuid4()),
            "event_type": event_type,
            "source": source,
            "worker_id": worker_id or source,
            "tenant_id": tenant_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload
        }
        return self.backend.publish(topic, envelope)


# Global Singleton Instance
event_bus = EventBusFacade()
