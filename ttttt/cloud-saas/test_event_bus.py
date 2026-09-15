import os
import sys
import unittest
from datetime import datetime

# Add cloud-saas/app to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from core.event_bus import EventBusFacade, InMemoryTestBackend, RedisStreamsBackend, EventBusException, event_bus
from core.outbox import publish_transactional_event
from models import Base, SessionLocal, EventLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestEventBusArchitecture(unittest.TestCase):
    def setUp(self):
        self.bus = EventBusFacade()
        self.bus.initialize(backend_type="inmemory")
        event_bus.initialize(backend_type="inmemory")

    def test_inmemory_publish_and_consume(self):
        topic = "events:test"
        group = "test-group"

        msg_id_1 = self.bus.publish(topic, "SLOT_FOUND", {"slots": 2}, source="scraper-1")
        self.assertTrue(msg_id_1)

        # Read group
        events = self.bus.backend.read_group(topic, group, "worker-1", count=10)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "SLOT_FOUND")
        self.assertEqual(events[0]["payload"]["slots"], 2)
        self.assertEqual(events[0]["source"], "scraper-1")

        # Ack
        acked = self.bus.backend.ack(topic, group, [events[0]["msg_id"]])
        self.assertEqual(acked, 1)

    def test_fail_visible_on_invalid_backend(self):
        bus = EventBusFacade()
        with self.assertRaises(EventBusException):
            bus.initialize(backend_type="non_existent_broker")

    def test_fail_visible_on_unreachable_redis(self):
        bus = EventBusFacade()
        with self.assertRaises(EventBusException):
            # Port 59999 should not have a running Redis
            bus.initialize(backend_type="redis", redis_url="redis://127.0.0.1:59999/0")

    def test_transactional_outbox_consistency(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        TestSession = sessionmaker(bind=engine)
        db = TestSession()

        try:
            # Publish transactional event
            msg_id = publish_transactional_event(
                db=db,
                topic="events:pipeline",
                event_type="BOOKING_DISPATCHED",
                payload={"task_id": 42, "applicant_id": 99},
                source="scheduler:auto_dispatch",
                severity="info"
            )
            self.assertTrue(msg_id)

            # Verify durable DB EventLog was written and committed
            log = db.query(EventLog).filter(EventLog.event_type == "BOOKING_DISPATCHED").first()
            self.assertIsNotNone(log)
            self.assertEqual(log.payload["task_id"], 42)
            self.assertEqual(log.payload["applicant_id"], 99)

            # Verify stream received event
            stream_events = event_bus.backend.read_group("events:pipeline", "audit-group", "tester", count=10)
            self.assertEqual(len(stream_events), 1)
            self.assertEqual(stream_events[0]["event_type"], "BOOKING_DISPATCHED")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
