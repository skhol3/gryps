from __future__ import annotations

from typing import TYPE_CHECKING

from gryps.core import Event
from gryps.core.frame_store import FrameStore
from gryps.plugins.detectors.base import TrackId
from gryps.plugins.ocr_backends.base import BaseOCRBackend, OCRResult

if TYPE_CHECKING:
    from gryps.core import EventBus


class OCRHandler:
    """Consumes ``PLATE_CROPPED`` refs and publishes normalized ``PLATE_READ``."""

    def __init__(self, bus: EventBus, backend: BaseOCRBackend, frame_store: FrameStore) -> None:
        self._bus = bus
        self._backend = backend
        self._frame_store = frame_store

        bus.subscribe("PLATE_CROPPED", self._handle_plate_cropped)

    def _handle_plate_cropped(self, event: Event) -> None:
        frame_ref = _required_ref(event.payload.get("frame_ref"), "frame_ref")
        crop_ref = _required_ref(event.payload.get("crop_ref"), "crop_ref")
        track_id = _track_id(event.payload.get("track_id"))

        crop = self._frame_store.get(crop_ref)
        result = (
            OCRResult(error=f"Crop ref not found: {crop_ref}")
            if crop is None
            else self._backend.read_plate(crop)
        )
        payload = result.as_plate_read(
            track_id=track_id,
            frame_ref=frame_ref,
            crop_ref=crop_ref,
            backend_name=self._backend.name,
        ).to_payload()

        self._bus.publish(
            Event.create(
                stream_id=event.stream_id,
                frame_id=event.frame_id,
                event_type="PLATE_READ",
                payload=payload,
            ),
        )


def _required_ref(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _track_id(value: object) -> TrackId | None:
    if value is None or isinstance(value, int | str):
        return value
    raise TypeError("track_id must be an int, str, or None")
