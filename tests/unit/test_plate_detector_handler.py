from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from gryps.core import Event, LocalEventBus
from gryps.core.frame_store import FrameStore
from gryps.plugins.detectors.base import BoundingBox
from gryps.plugins.detectors.plate_detector import PlateDetectorHandler, PlateDetectorPlugin


class FakeLocator:
    def __init__(self, results: tuple[Mapping[str, Any], ...]) -> None:
        self._results = results
        self.calls: list[tuple[object, BoundingBox, Mapping[str, Any]]] = []

    def __call__(
        self,
        frame: object,
        vehicle_bbox: BoundingBox,
        metadata: Mapping[str, Any],
    ) -> Iterable[Mapping[str, Any]]:
        self.calls.append((frame, vehicle_bbox, metadata))
        return self._results


def cropper(
    _frame: object,
    vehicle_bbox: BoundingBox,
    plate_bbox: BoundingBox,
) -> dict[str, object]:
    return {"vehicle_bbox": vehicle_bbox, "plate_bbox": plate_bbox}


class TestPlateDetectorHandler:
    def test_publishes_plate_cropped_with_refs_and_bboxes(self) -> None:
        bus = LocalEventBus()
        store = FrameStore()
        frame = object()
        store.store("mem://cam_01/7", frame)
        locator = FakeLocator(({"bbox": (11, 22, 33, 44), "confidence": 0.86},))
        detector = PlateDetectorPlugin(locator=locator, cropper=cropper)

        PlateDetectorHandler(bus=bus, detector=detector, frame_store=store)
        captured: list[Event] = []
        bus.subscribe("PLATE_CROPPED", captured.append)

        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=7,
                event_type="VEHICLE_DETECTED",
                payload={
                    "frame_ref": "mem://cam_01/7",
                    "bbox": [10.0, 20.0, 100.0, 120.0],
                    "track_id": "t1",
                },
            ),
        )

        assert len(captured) == 1
        event = captured[0]
        assert event.event_type == "PLATE_CROPPED"
        assert event.stream_id == "cam_01"
        assert event.frame_id == 7
        assert event.payload == {
            "track_id": "t1",
            "frame_ref": "mem://cam_01/7",
            "crop_ref": "mem://cam_01/7/plate/t1",
            "vehicle_bbox": [10.0, 20.0, 100.0, 120.0],
            "plate_bbox": [11.0, 22.0, 33.0, 44.0],
            "confidence": 0.86,
        }
        assert store.get("mem://cam_01/7/plate/t1") == {
            "vehicle_bbox": (10.0, 20.0, 100.0, 120.0),
            "plate_bbox": (11.0, 22.0, 33.0, 44.0),
        }
        assert locator.calls == [
            (
                frame,
                (10.0, 20.0, 100.0, 120.0),
                {
                    "frame_ref": "mem://cam_01/7",
                    "stream_id": "cam_01",
                    "frame_id": 7,
                    "track_id": "t1",
                },
            )
        ]

    def test_does_not_publish_when_no_plate_region_found(self) -> None:
        bus = LocalEventBus()
        store = FrameStore()
        store.store("mem://cam_01/7", object())
        detector = PlateDetectorPlugin(locator=FakeLocator(()), cropper=cropper)

        PlateDetectorHandler(bus=bus, detector=detector, frame_store=store)
        captured: list[Event] = []
        bus.subscribe("PLATE_CROPPED", captured.append)

        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=7,
                event_type="VEHICLE_DETECTED",
                payload={"frame_ref": "mem://cam_01/7", "bbox": [10.0, 20.0, 100.0, 120.0]},
            ),
        )

        assert captured == []

    def test_does_not_publish_when_frame_ref_is_missing_from_store(self) -> None:
        bus = LocalEventBus()
        locator = FakeLocator(({"bbox": (11, 22, 33, 44)},))
        detector = PlateDetectorPlugin(locator=locator, cropper=cropper)

        PlateDetectorHandler(bus=bus, detector=detector, frame_store=FrameStore())
        captured: list[Event] = []
        bus.subscribe("PLATE_CROPPED", captured.append)

        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=7,
                event_type="VEHICLE_DETECTED",
                payload={"frame_ref": "mem://cam_01/missing", "bbox": [10, 20, 100, 120]},
            ),
        )

        assert captured == []
        assert locator.calls == []

    def test_plate_cropped_payload_has_no_raw_media(self) -> None:
        bus = LocalEventBus()
        store = FrameStore()
        store.store("mem://cam_01/7", object())
        detector = PlateDetectorPlugin(
            locator=FakeLocator(({"bbox": (11, 22, 33, 44)},)),
            cropper=cropper,
        )

        PlateDetectorHandler(bus=bus, detector=detector, frame_store=store)
        captured: list[Event] = []
        bus.subscribe("PLATE_CROPPED", captured.append)

        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=7,
                event_type="VEHICLE_DETECTED",
                payload={"frame_ref": "mem://cam_01/7", "bbox": [10, 20, 100, 120]},
            ),
        )

        assert len(captured) == 1
        raw_keys = {"data", "frame", "image", "ndarray", "bytes", "raw", "crop"}
        assert raw_keys.isdisjoint(captured[0].payload)
        assert captured[0].payload["frame_ref"] == "mem://cam_01/7"
        assert captured[0].payload["crop_ref"] == "mem://cam_01/7/plate/0"
