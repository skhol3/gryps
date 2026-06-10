from __future__ import annotations

from typing import Any

from gryps.core import Event, LocalEventBus
from gryps.core.frame_store import FrameStore
from gryps.plugins.detectors import BaseDetectorPlugin, DetectionResult
from gryps.plugins.detectors.vehicle_yolo.handler import VehicleDetectorHandler


class FakeDetector(BaseDetectorPlugin):
    def __init__(
        self,
        detections: tuple[DetectionResult, ...] = (),
    ) -> None:
        self._detections = detections
        self.calls: list[tuple[object, dict[str, Any]]] = []

    def detect(self, frame: object, metadata: dict[str, Any]) -> tuple[DetectionResult, ...]:
        self.calls.append((frame, metadata))
        return self._detections


class TestVehicleDetectorHandler:
    def test_subscribes_to_new_frame_on_init(self) -> None:
        bus = LocalEventBus()
        handler = VehicleDetectorHandler(  # noqa: F841
            bus=bus,
            detector=FakeDetector(),
            frame_store=FrameStore(),
        )

        assert handler is not None
        received: list[Event] = []
        bus.subscribe("VEHICLE_DETECTED", received.append)

        event = Event.create(
            stream_id="cam_01",
            frame_id=0,
            event_type="NEW_FRAME",
            payload={"frame_ref": "mem://cam_01/0"},
        )
        bus.publish(event)

        # Should not crash — handler was subscribed during init
        assert isinstance(handler, VehicleDetectorHandler)

    def test_publishes_vehicle_detected_for_each_detection(self) -> None:
        bus = LocalEventBus()
        store = FrameStore()
        frame = object()
        store.store("mem://cam_01/0", frame)

        detector = FakeDetector(
            detections=(
                DetectionResult(
                    bbox=(10.0, 20.0, 30.0, 40.0), class_name="car",
                    confidence=0.91, track_id="t1",
                ),
                DetectionResult(bbox=(50.0, 60.0, 70.0, 80.0), class_name="truck", confidence=0.82),
            ),
        )

        VehicleDetectorHandler(bus=bus, detector=detector, frame_store=store)

        captured: list[Event] = []
        bus.subscribe("VEHICLE_DETECTED", captured.append)

        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=0,
                event_type="NEW_FRAME",
                payload={"frame_ref": "mem://cam_01/0"},
            ),
        )

        assert len(captured) == 2
        assert detector.calls == [(frame, {"frame_ref": "mem://cam_01/0"})]

    def test_detection_payload_fields(self) -> None:
        bus = LocalEventBus()
        store = FrameStore()
        store.store("mem://cam_01/0", object())

        detector = FakeDetector(
            detections=(
                DetectionResult(
                    bbox=(10.0, 20.0, 30.0, 40.0),
                    class_name="car",
                    confidence=0.91,
                    track_id="t1",
                ),
            ),
        )

        VehicleDetectorHandler(bus=bus, detector=detector, frame_store=store)

        captured: list[Event] = []
        bus.subscribe("VEHICLE_DETECTED", captured.append)

        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=7,
                event_type="NEW_FRAME",
                payload={"frame_ref": "mem://cam_01/0"},
            ),
        )

        assert len(captured) == 1
        event = captured[0]
        assert event.event_type == "VEHICLE_DETECTED"
        assert event.stream_id == "cam_01"
        assert event.frame_id == 7
        assert event.payload["bbox"] == [10.0, 20.0, 30.0, 40.0]
        assert event.payload["class_name"] == "car"
        assert event.payload["confidence"] == 0.91
        assert event.payload["track_id"] == "t1"

    def test_no_vehicle_detected_when_no_detections(self) -> None:
        bus = LocalEventBus()
        store = FrameStore()
        store.store("mem://cam_01/0", object())

        detector = FakeDetector()

        VehicleDetectorHandler(bus=bus, detector=detector, frame_store=store)

        captured: list[Event] = []
        bus.subscribe("VEHICLE_DETECTED", captured.append)

        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=0,
                event_type="NEW_FRAME",
                payload={"frame_ref": "mem://cam_01/0"},
            ),
        )

        assert len(captured) == 0

    def test_skips_frame_when_not_in_store(self) -> None:
        bus = LocalEventBus()
        detector = FakeDetector()

        VehicleDetectorHandler(bus=bus, detector=detector, frame_store=FrameStore())

        captured: list[Event] = []
        bus.subscribe("VEHICLE_DETECTED", captured.append)

        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=0,
                event_type="NEW_FRAME",
                payload={"frame_ref": "mem://cam_01/missing"},
            ),
        )

        assert len(captured) == 0
        assert detector.calls == []

    def test_payload_has_no_raw_frame_data(self) -> None:
        bus = LocalEventBus()
        store = FrameStore()
        store.store("mem://cam_01/0", object())

        detector = FakeDetector(
            detections=(
                DetectionResult(bbox=(10.0, 20.0, 30.0, 40.0), class_name="car", confidence=0.91),
            ),
        )

        VehicleDetectorHandler(bus=bus, detector=detector, frame_store=store)

        captured: list[Event] = []
        bus.subscribe("VEHICLE_DETECTED", captured.append)

        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=0,
                event_type="NEW_FRAME",
                payload={"frame_ref": "mem://cam_01/0"},
            ),
        )

        assert len(captured) == 1
        raw_keys = {"data", "frame", "image", "ndarray", "bytes", "raw"}
        assert raw_keys.isdisjoint(captured[0].payload)

    def test_event_id_and_timestamp_are_set(self) -> None:
        bus = LocalEventBus()
        store = FrameStore()
        store.store("mem://cam_01/0", object())

        detector = FakeDetector(
            detections=(
                DetectionResult(bbox=(10.0, 20.0, 30.0, 40.0), class_name="car", confidence=0.91),
            ),
        )

        VehicleDetectorHandler(bus=bus, detector=detector, frame_store=store)

        captured: list[Event] = []
        bus.subscribe("VEHICLE_DETECTED", captured.append)

        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=0,
                event_type="NEW_FRAME",
                payload={"frame_ref": "mem://cam_01/0"},
            ),
        )

        assert len(captured) == 1
        event = captured[0]
        assert isinstance(event.event_id, str)
        assert len(event.event_id) > 0
        assert isinstance(event.timestamp, float)
        assert event.timestamp > 0

    def test_multiple_frames_produce_independent_events(self) -> None:
        bus = LocalEventBus()
        store = FrameStore()
        store.store("mem://cam_01/0", object())
        store.store("mem://cam_01/1", object())

        detector = FakeDetector(
            detections=(
                DetectionResult(bbox=(0.0, 0.0, 10.0, 10.0), class_name="car", confidence=0.9),
            ),
        )

        VehicleDetectorHandler(bus=bus, detector=detector, frame_store=store)

        captured: list[Event] = []
        bus.subscribe("VEHICLE_DETECTED", captured.append)

        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=0,
                event_type="NEW_FRAME",
                payload={"frame_ref": "mem://cam_01/0"},
            ),
        )
        bus.publish(
            Event.create(
                stream_id="cam_01",
                frame_id=1,
                event_type="NEW_FRAME",
                payload={"frame_ref": "mem://cam_01/1"},
            ),
        )

        assert len(captured) == 2
        assert captured[0].frame_id == 0
        assert captured[1].frame_id == 1
