from __future__ import annotations

from typing import TYPE_CHECKING

from gryps.core import Event
from gryps.core.frame_store import FrameStore
from gryps.plugins.detectors.base import BoundingBox, TrackId
from gryps.plugins.detectors.plate_detector.plugin import PlateDetectorPlugin

if TYPE_CHECKING:
    from gryps.core import EventBus


class PlateDetectorHandler:
    """Consumes ``VEHICLE_DETECTED`` and publishes ``PLATE_CROPPED`` refs."""

    def __init__(
        self,
        bus: EventBus,
        detector: PlateDetectorPlugin,
        frame_store: FrameStore,
    ) -> None:
        self._bus = bus
        self._detector = detector
        self._frame_store = frame_store

        bus.subscribe("VEHICLE_DETECTED", self._handle_vehicle_detected)

    def _handle_vehicle_detected(self, event: Event) -> None:
        frame_ref = event.payload.get("frame_ref")
        if not isinstance(frame_ref, str) or not frame_ref:
            return

        frame = self._frame_store.get(frame_ref)
        if frame is None:
            return

        vehicle_bbox = _bbox(event.payload.get("bbox"))
        track_id = _track_id(event.payload.get("track_id"))
        metadata = {
            "frame_ref": frame_ref,
            "stream_id": event.stream_id,
            "frame_id": event.frame_id,
            "track_id": track_id,
        }

        for index, plate in enumerate(self._detector.detect_plates(frame, vehicle_bbox, metadata)):
            crop_ref = self._crop_ref(frame_ref, track_id, index)
            self._frame_store.store(crop_ref, plate.crop)
            payload: dict[str, object] = {
                "track_id": track_id,
                "frame_ref": frame_ref,
                "crop_ref": crop_ref,
                "vehicle_bbox": list(vehicle_bbox),
                "plate_bbox": list(plate.plate_bbox),
                "confidence": plate.confidence,
            }
            self._bus.publish(
                Event.create(
                    stream_id=event.stream_id,
                    frame_id=event.frame_id,
                    event_type="PLATE_CROPPED",
                    payload=payload,
                ),
            )

    @staticmethod
    def _crop_ref(frame_ref: str, track_id: TrackId | None, index: int) -> str:
        suffix = track_id if track_id is not None else index
        return f"{frame_ref}/plate/{suffix}"


def _bbox(value: object) -> BoundingBox:
    if not isinstance(value, list | tuple) or isinstance(value, str | bytes):
        raise TypeError("vehicle bbox must be a sequence of four numbers")
    bbox = tuple(float(item) for item in value)
    if len(bbox) != 4:
        raise ValueError("vehicle bbox must contain exactly four values")
    return bbox


def _track_id(value: object) -> TrackId | None:
    if value is None or isinstance(value, int | str):
        return value
    raise TypeError("track_id must be an int, str, or None")
