from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Payload = dict[str, Any]
EventHandler = Callable[["Event"], None]


@dataclass(frozen=True)
class Subscription:
    event_type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    handler: EventHandler | None = None


@dataclass(frozen=True)
class Event:
    """A frozen (shallow-immutable) event dataclass.

    The frozen constraint prevents field reassignment but does not
    deep-freeze mutable fields such as the payload dict. By convention,
    handlers MUST NOT mutate the payload content in-place.

    timestamp uses ``time.time()`` and therefore reflects the platform's
    wall-clock precision (typically microsecond or better on modern
    systems, though not guaranteed monotonic across threads).
    """

    event_id: str
    timestamp: float
    stream_id: str
    frame_id: int
    event_type: str
    payload: Payload

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must be non-empty")
        if not self.stream_id:
            raise ValueError("stream_id must be non-empty")
        if self.frame_id < 0:
            raise ValueError("frame_id must be non-negative")
        if not self.event_type:
            raise ValueError("event_type must be non-empty")
        if not isinstance(self.payload, dict):
            raise TypeError("payload must be a dict")
        import math

        if not isinstance(self.timestamp, (int, float)):
            raise TypeError("timestamp must be a number")
        if self.timestamp < 0:
            raise ValueError("timestamp must be non-negative")
        if math.isnan(self.timestamp):
            raise ValueError("timestamp must not be NaN")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "stream_id": self.stream_id,
            "frame_id": self.frame_id,
            "event_type": self.event_type,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        if not isinstance(data.get("payload"), dict):
            raise TypeError("payload must be a dict")
        return cls(
            event_id=data["event_id"],
            timestamp=data["timestamp"],
            stream_id=data["stream_id"],
            frame_id=data["frame_id"],
            event_type=data["event_type"],
            payload=dict(data["payload"]),
        )

    @classmethod
    def create(
        cls,
        stream_id: str,
        frame_id: int,
        event_type: str,
        payload: Payload | None = None,
    ) -> Event:
        return cls(
            event_id=str(uuid.uuid4()),
            timestamp=time.time(),
            stream_id=stream_id,
            frame_id=frame_id,
            event_type=event_type,
            payload=payload if payload is not None else {},
        )


class EventBus(ABC):

    @abstractmethod
    def publish(self, event: Event) -> None: ...

    @abstractmethod
    def subscribe(self, event_type: str, handler: EventHandler) -> Subscription: ...

    @abstractmethod
    def unsubscribe(self, sub: Subscription) -> None: ...


class LocalEventBus(EventBus):
    """In-process event bus backed by a dict of subscription lists.

    Calls handlers synchronously in subscription order on ``publish``.
    Handler exceptions propagate to the caller — the bus does not
    silently swallow errors. This is deliberate for MVP: failures must
    be visible immediately.

    ``unsubscribe`` is a no-op when the subscription is unknown or was
    already removed.
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[Subscription]] = {}

    def publish(self, event: Event) -> None:
        for sub in list(self._subscriptions.get(event.event_type, ())):
            if sub.handler is not None:
                sub.handler(event)

    def subscribe(self, event_type: str, handler: EventHandler) -> Subscription:
        sub = Subscription(event_type=event_type, handler=handler)
        self._subscriptions.setdefault(event_type, []).append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        subs = self._subscriptions.get(sub.event_type)
        if subs is not None and sub in subs:
            subs.remove(sub)
