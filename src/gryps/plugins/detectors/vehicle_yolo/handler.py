from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gryps.core import Event
from gryps.core.frame_store import FrameStore
from gryps.plugins.detectors import BaseDetectorPlugin
from gryps.streams import FrameMetadata

if TYPE_CHECKING:
    from gryps.core import EventBus


class VehicleDetectorHandler:
    """Subscribes to ``NEW_FRAME`` and publishes ``VEHICLE_DETECTED``.

    For each ``NEW_FRAME`` event:
      1. Resolve the raw frame from the ``FrameStore`` using ``frame_ref``.
      2. Run the injected ``BaseDetectorPlugin`` on that frame.
      3. Publish one ``VEHICLE_DETECTED`` event per detection result.

    The handler is registered on init — constructing it is enough to
    start receiving frames.
    """

    def __init__(
        self,
        bus: EventBus,
        detector: BaseDetectorPlugin,
        frame_store: FrameStore,
    ) -> None:
        self._bus = bus
        self._detector = detector
        self._frame_store = frame_store

        bus.subscribe(FrameMetadata.NEW_FRAME, self._handle_new_frame)

    def _handle_new_frame(self, event: Event) -> None:
        frame_ref = event.payload.get("frame_ref", "")
        frame = self._frame_store.get(frame_ref)
        if frame is None:
            return

        metadata: dict[str, Any] = {
            "frame_ref": frame_ref,
        }

        detections = self._detector.detect(frame, metadata)

        for result in detections:
            payload = result.to_payload()
            payload["frame_ref"] = frame_ref
            self._bus.publish(
                Event.create(
                    stream_id=event.stream_id,
                    frame_id=event.frame_id,
                    event_type="VEHICLE_DETECTED",
                    payload=payload,
                ),
            )
