from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gryps.core import EventBus


@dataclass(frozen=True)
class FrameMetadata:
    """Metadata describing a single video frame.

    The actual pixel data never travels through the EventBus — only
    this metadata object does.  ``frame_ref`` is an opaque reference
    that consumers can use to look up the raw frame from a shared
    ``FrameStore``.

    Fields
    ------
    frame_id : int
        Monotonic frame counter within the stream (0-based).
    stream_id : str
        Logical stream identifier (e.g. ``"cam_01"``, ``"file_01"``).
    timestamp : float
        Time the frame was read (``time.time()``).
    frame_ref : str
        Opaque reference URI (e.g. ``"mem://file_01/0"``).
    resolution : tuple[int, int] | None
        ``(width, height)`` in pixels when known.
    preprocessors_applied : tuple[str, ...]
        Names of preprocessors already applied to this frame (empty
        means the raw frame has not been preprocessed).
    """

    frame_id: int
    stream_id: str
    timestamp: float = 0.0
    frame_ref: str = ""
    resolution: tuple[int, int] | None = None
    preprocessors_applied: tuple[str, ...] = ()

    NEW_FRAME: str = "NEW_FRAME"

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict suitable as an Event payload."""
        return {
            "frame_ref": self.frame_ref,
            "timestamp": self.timestamp,
            "resolution": list(self.resolution) if self.resolution else None,
            "preprocessors_applied": list(self.preprocessors_applied),
        }


class FrameReader(ABC):
    """Abstract adapter for decoding video frames.

    Implementations wrap a specific decoding library (OpenCV, ffmpeg,
    a synthetic generator, etc.).  The adapter is *stateful* — it is
    opened once, yields frames sequentially, and must be closed.
    """

    @abstractmethod
    def open(self, source: str) -> None:
        """Prepare to read frames from *source* (file path, URL, …)."""

    @abstractmethod
    def read(self) -> object | None:
        """Return an opaque frame handle, or *None* when exhausted."""

    @abstractmethod
    def close(self) -> None:
        """Release all held resources."""

    @property
    @abstractmethod
    def closed(self) -> bool: ...

    @property
    @abstractmethod
    def resolution(self) -> tuple[int, int] | None:
        """Detected frame ``(width, height)``, or *None* if unknown."""


class BaseStreamSource(ABC):
    """Abstract base for all Gryps video stream sources.

    A stream source produces frames.  Subclasses decide *how* frames
    are obtained (file, camera, network, synthetic).  Frame data is
    kept local to the source; only :class:`FrameMetadata` objects
    (and the events built from them) leave the source.
    """

    @property
    @abstractmethod
    def stream_id(self) -> str:
        """Unique logical identifier for this stream."""

    @abstractmethod
    def read_next(self) -> FrameMetadata | None:
        """Read the next frame.

        Returns *None* when the stream is exhausted (or fails).
        """

    def publish_next(self, bus: EventBus) -> FrameMetadata | None:
        """Read the next frame and publish a ``NEW_FRAME`` event.

        This is a convenience that combines :meth:`read_next` with
        an ``EventBus.publish`` call.  Subclasses MAY override to
        add pre/post hooks.
        """
        from gryps.core import Event

        meta = self.read_next()
        if meta is not None:
            bus.publish(
                Event(
                    event_id=str(uuid.uuid4()),
                    timestamp=meta.timestamp,
                    stream_id=self.stream_id,
                    frame_id=meta.frame_id,
                    event_type=FrameMetadata.NEW_FRAME,
                    payload=meta.to_payload(),
                ),
            )
        return meta
