from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from gryps.core import Event, EventBus, LocalEventBus, Subscription


class TestEventCreation:
    def test_explicit_values(self) -> None:
        event = Event(
            event_id="e1",
            timestamp=1000.0,
            stream_id="cam_1",
            frame_id=42,
            event_type="TEST_EVENT",
            payload={"key": "value"},
        )
        assert event.event_id == "e1"
        assert event.timestamp == 1000.0
        assert event.stream_id == "cam_1"
        assert event.frame_id == 42
        assert event.event_type == "TEST_EVENT"
        assert event.payload == {"key": "value"}

    def test_create_factory(self) -> None:
        t0 = time.time()
        event = Event.create(
            stream_id="cam_1",
            frame_id=0,
            event_type="NEW_FRAME",
            payload={"ref": "abc"},
        )
        t1 = time.time()
        assert isinstance(event.event_id, str)
        assert uuid.UUID(event.event_id)
        assert isinstance(event.timestamp, float)
        assert t0 <= event.timestamp <= t1
        assert event.stream_id == "cam_1"
        assert event.frame_id == 0
        assert event.event_type == "NEW_FRAME"
        assert event.payload == {"ref": "abc"}

    def test_create_default_payload(self) -> None:
        event = Event.create(stream_id="cam_1", frame_id=1, event_type="PING")
        assert event.payload == {}

    def test_uuid_uniqueness(self) -> None:
        e1 = Event.create(stream_id="s", frame_id=0, event_type="T")
        e2 = Event.create(stream_id="s", frame_id=0, event_type="T")
        assert e1.event_id != e2.event_id


class TestEventSerialization:
    def test_to_dict(self) -> None:
        event = Event(
            event_id="e1",
            timestamp=1000.0,
            stream_id="cam_1",
            frame_id=42,
            event_type="TEST",
            payload={"nested": {"a": 1}},
        )
        d = event.to_dict()
        assert d == {
            "event_id": "e1",
            "timestamp": 1000.0,
            "stream_id": "cam_1",
            "frame_id": 42,
            "event_type": "TEST",
            "payload": {"nested": {"a": 1}},
        }

    def test_round_trip(self) -> None:
        original = Event.create(
            stream_id="cam_1",
            frame_id=5,
            event_type="PLATE_READ",
            payload={"plate": "ABC123"},
        )
        restored = Event.from_dict(original.to_dict())
        assert restored == original
        assert restored.event_id == original.event_id
        assert restored.timestamp == original.timestamp
        assert restored.payload == original.payload

    def test_from_dict_independent_copy(self) -> None:
        data: dict[str, Any] = {
            "event_id": "e1",
            "timestamp": 1.0,
            "stream_id": "s",
            "frame_id": 0,
            "event_type": "T",
            "payload": {"key": [1, 2, 3]},
        }
        event = Event.from_dict(data)
        assert event.payload is not data["payload"]


class TestEventImmutability:
    def test_cannot_modify_field(self) -> None:
        event = Event.create(stream_id="s", frame_id=0, event_type="T")
        with pytest.raises(FrozenInstanceError):
            event.event_id = "other"  # type: ignore[misc]

    def test_cannot_modify_payload_in_place(self) -> None:
        event = Event.create(
            stream_id="s",
            frame_id=0,
            event_type="T",
            payload={"items": [1]},
        )
        event.payload["extra"] = "sneaky"
        assert "extra" in event.payload


class TestEventValidation:
    def test_empty_stream_id(self) -> None:
        with pytest.raises(ValueError, match="stream_id must be non-empty"):
            Event(
                event_id="e", timestamp=0.0, stream_id="",
                frame_id=0, event_type="T", payload={},
            )

    def test_negative_frame_id(self) -> None:
        with pytest.raises(ValueError, match="frame_id must be non-negative"):
            Event(
                event_id="e", timestamp=0.0, stream_id="s",
                frame_id=-1, event_type="T", payload={},
            )

    def test_empty_event_type(self) -> None:
        with pytest.raises(ValueError, match="event_type must be non-empty"):
            Event(
                event_id="e", timestamp=0.0, stream_id="s",
                frame_id=0, event_type="", payload={},
            )

    def test_non_dict_payload(self) -> None:
        with pytest.raises(TypeError, match="payload must be a dict"):
            Event(
                event_id="e", timestamp=0.0, stream_id="s",
                frame_id=0, event_type="T", payload="not_a_dict",  # type: ignore[arg-type]
            )

    def test_zero_frame_id_valid(self) -> None:
        event = Event(
            event_id="e", timestamp=0.0, stream_id="s",
            frame_id=0, event_type="T", payload={},
        )
        assert event.frame_id == 0

    def test_empty_event_id(self) -> None:
        with pytest.raises(ValueError, match="event_id must be non-empty"):
            Event(
                event_id="", timestamp=0.0, stream_id="s",
                frame_id=0, event_type="T", payload={},
            )

    def test_negative_timestamp(self) -> None:
        with pytest.raises(ValueError, match="timestamp must be non-negative"):
            Event(
                event_id="e", timestamp=-1.0, stream_id="s",
                frame_id=0, event_type="T", payload={},
            )

    def test_nan_timestamp(self) -> None:
        with pytest.raises(ValueError, match="timestamp must not be NaN"):
            Event(
                event_id="e", timestamp=float("nan"), stream_id="s",
                frame_id=0, event_type="T", payload={},
            )

    def test_from_dict_non_dict_payload(self) -> None:
        with pytest.raises(TypeError, match="payload must be a dict"):
            Event.from_dict({
                "event_id": "e",
                "timestamp": 0.0,
                "stream_id": "s",
                "frame_id": 0,
                "event_type": "T",
                "payload": "not_a_dict",
            })


class TestEventBusAbstract:
    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            EventBus()  # type: ignore[abstract]

    def test_concrete_subclass(self) -> None:
        class FakeBus(EventBus):
            def publish(self, event: Event) -> None:
                self._published = event

            def subscribe(
                self, event_type: str, handler: Callable[[Event], None],
            ) -> Subscription:
                return Subscription(event_type=event_type, handler=handler)

            def unsubscribe(self, sub: Subscription) -> None:
                self._unsubscribed = sub

        bus = FakeBus()
        event = Event.create(stream_id="s", frame_id=0, event_type="T")
        bus.publish(event)
        assert bus._published == event

        sub = bus.subscribe("T", lambda _: None)
        assert sub.event_type == "T"

        bus.unsubscribe(sub)
        assert bus._unsubscribed == sub


class TestSubscription:
    def test_default_id(self) -> None:
        s1 = Subscription(event_type="T")
        s2 = Subscription(event_type="T")
        assert s1.id != s2.id
        assert uuid.UUID(s1.id)

    def test_explicit_values(self) -> None:
        def handler(event: Event) -> None:
            pass

        sub = Subscription(event_type="T", handler=handler)
        assert sub.event_type == "T"
        assert sub.handler is handler


class TestLocalEventBus:
    def test_publish_calls_subscriber(self) -> None:
        bus: LocalEventBus = LocalEventBus()
        received: list[Event] = []

        bus.subscribe("T", received.append)
        event = Event.create(stream_id="s", frame_id=0, event_type="T")
        bus.publish(event)

        assert received == [event]

    def test_publish_multiple_subscribers_same_type(self) -> None:
        bus = LocalEventBus()
        received_1: list[Event] = []
        received_2: list[Event] = []

        bus.subscribe("T", received_1.append)
        bus.subscribe("T", received_2.append)
        event = Event.create(stream_id="s", frame_id=0, event_type="T")
        bus.publish(event)

        assert received_1 == [event]
        assert received_2 == [event]

    def test_event_type_filtering(self) -> None:
        bus = LocalEventBus()
        received: list[Event] = []

        bus.subscribe("A", received.append)
        bus.subscribe("B", received.append)
        event_a = Event.create(stream_id="s", frame_id=0, event_type="A")
        event_b = Event.create(stream_id="s", frame_id=0, event_type="B")

        bus.publish(event_a)
        assert len(received) == 1
        assert received[0] == event_a

        bus.publish(event_b)
        assert len(received) == 2
        assert received[1] == event_b

    def test_unsubscribe_removes_handler(self) -> None:
        bus = LocalEventBus()
        received: list[Event] = []

        sub = bus.subscribe("T", received.append)
        event = Event.create(stream_id="s", frame_id=0, event_type="T")
        bus.publish(event)
        assert len(received) == 1

        bus.unsubscribe(sub)
        bus.publish(event)
        assert len(received) == 1  # no second call

    def test_unsubscribe_unknown_event_type_noop(self) -> None:
        bus = LocalEventBus()
        sub = Subscription(event_type="UNKNOWN")
        bus.unsubscribe(sub)  # should not raise

    def test_unsubscribe_unknown_subscription_noop(self) -> None:
        bus = LocalEventBus()
        sub = bus.subscribe("T", lambda _: None)
        bus.unsubscribe(sub)
        bus.unsubscribe(sub)  # already removed — should not raise

    def test_exception_propagates(self) -> None:
        bus = LocalEventBus()

        def failing(_: Event) -> None:
            msg = "handler failed"
            raise RuntimeError(msg)

        bus.subscribe("T", failing)
        event = Event.create(stream_id="s", frame_id=0, event_type="T")

        with pytest.raises(RuntimeError, match="handler failed"):
            bus.publish(event)

    def test_exception_does_not_affect_prior_handlers(self) -> None:
        bus = LocalEventBus()
        received: list[Event] = []

        bus.subscribe("T", received.append)
        bus.subscribe("T", lambda _: (_ for _ in ()).throw(RuntimeError("fail")))
        bus.subscribe("T", received.append)  # never called

        event = Event.create(stream_id="s", frame_id=0, event_type="T")

        with pytest.raises(RuntimeError, match="fail"):
            bus.publish(event)

        assert len(received) == 1  # first handler ran before exception

    def test_publish_no_subscribers_noop(self) -> None:
        bus = LocalEventBus()
        event = Event.create(stream_id="s", frame_id=0, event_type="T")
        bus.publish(event)  # should not raise

    def test_publish_1000_events(self) -> None:
        bus = LocalEventBus()
        received: list[Event] = []

        bus.subscribe("T", received.append)

        for _ in range(1000):
            event = Event.create(stream_id="s", frame_id=0, event_type="T")
            bus.publish(event)

        assert len(received) == 1000

    def test_subscribe_returns_subscription(self) -> None:
        bus = LocalEventBus()
        sub = bus.subscribe("MY_EVENT", lambda _: None)
        assert isinstance(sub, Subscription)
        assert sub.event_type == "MY_EVENT"
        assert sub.handler is not None
        assert uuid.UUID(sub.id)  # valid UUID

    def test_publish_wrong_type_not_delivered(self) -> None:
        bus = LocalEventBus()
        received: list[Event] = []

        bus.subscribe("A", received.append)
        event_b = Event.create(stream_id="s", frame_id=0, event_type="B")
        bus.publish(event_b)

        assert len(received) == 0

    def test_publish_snapshot_unsubscribe_during_iteration(self) -> None:
        """Unsubscribing another handler during publish does not skip it."""
        bus = LocalEventBus()
        results: list[str] = []

        def handler_a(_: Event) -> None:
            results.append("A")

        def handler_b(_: Event) -> None:
            bus.unsubscribe(sub_a)
            results.append("B")

        sub_a = bus.subscribe("T", handler_a)
        bus.subscribe("T", handler_b)

        event = Event.create(stream_id="s", frame_id=0, event_type="T")
        bus.publish(event)

        assert results == ["A", "B"]

        bus.publish(event)
        assert results == ["A", "B", "B"]  # A is gone now

    def test_publish_snapshot_subscribe_during_iteration(self) -> None:
        """Subscribing a new handler during publish does not call it until
        a later publish."""
        bus = LocalEventBus()
        results: list[str] = []

        def handler_b(_: Event) -> None:
            results.append("B")

        def handler_a(_: Event) -> None:
            bus.subscribe("T", handler_b)
            results.append("A")

        bus.subscribe("T", handler_a)

        event = Event.create(stream_id="s", frame_id=0, event_type="T")
        # handler_b is subscribed during the snapshot — not called yet
        bus.publish(event)
        assert results == ["A"]

        # handler_b is now in the subscription list for future publishes
        bus.publish(event)
        assert results == ["A", "A", "B"]
