from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pytest

from gryps.core import ConfigError, Event, LocalEventBus
from gryps.core.frame_store import FrameStore
from gryps.plugins.detectors.base import BaseDetectorPlugin, BoundingBox, DetectionResult
from gryps.plugins.detectors.plate_detector import PlateDetectorHandler, PlateDetectorPlugin
from gryps.plugins.detectors.vehicle_yolo.handler import VehicleDetectorHandler
from gryps.plugins.ocr_backends import BaseOCRBackend, OCRHandler, OCRResult
from gryps.plugins.ocr_backends.base import normalize_plate_text
from gryps.plugins.ocr_backends.paddleocr_backend import PaddleOCRBackend
from gryps.plugins.ocr_backends.selector import create_ocr_backend


class FakeOCRBackend(BaseOCRBackend):
    name = "fake"

    def __init__(self, result: OCRResult) -> None:
        self._result = result
        self.calls: list[object] = []

    def read_plate(self, crop: object) -> OCRResult:
        self.calls.append(crop)
        return self._result


class FakeReader:
    def __init__(self, raw: object | None = None, error: Exception | None = None) -> None:
        self._raw = raw
        self._error = error
        self.calls: list[object] = []

    def predict(self, crop: object) -> object:
        self.calls.append(crop)
        if self._error is not None:
            raise self._error
        return self._raw


class FakeVehicleDetector(BaseDetectorPlugin):
    def detect(self, _frame: object, _metadata: dict[str, Any]) -> tuple[DetectionResult, ...]:
        return (DetectionResult(bbox=(10, 20, 100, 120), class_name="car", confidence=0.91),)


class FakePlateLocator:
    def __call__(
        self,
        frame: object,
        vehicle_bbox: BoundingBox,
        metadata: Mapping[str, Any],
    ) -> Iterable[Mapping[str, Any]]:
        _ = (frame, vehicle_bbox, metadata)
        return ({"bbox": (11, 22, 33, 44), "confidence": 0.86},)


def test_selector_creates_configured_backend() -> None:
    backend = FakeOCRBackend(OCRResult(text="abc123", confidence=0.7))

    selected = create_ocr_backend(
        {"ocr": {"backend": "fake", "fake": {"unused": True}}},
        factories={"fake": lambda _config: backend},
    )

    assert selected is backend


def test_selector_rejects_unknown_backend_with_valid_options() -> None:
    with pytest.raises(ConfigError) as error:
        create_ocr_backend(
            {"ocr": {"backend": "missing"}},
            factories={"fake": lambda _config: FakeOCRBackend(OCRResult())},
        )

    message = str(error.value)
    assert "missing" in message
    assert "fake" in message


def test_normalize_plate_text_removes_formatting_noise() -> None:
    assert normalize_plate_text(" ab-123 cd ") == "AB123CD"


def test_ocr_handler_publishes_read_payload_without_raw_media() -> None:
    bus = LocalEventBus()
    store = FrameStore()
    store.store("mem://cam_01/7/plate/0", object())
    backend = FakeOCRBackend(OCRResult(text=" ab-123 ", confidence=0.93))
    OCRHandler(bus=bus, backend=backend, frame_store=store)
    captured: list[Event] = []
    bus.subscribe("PLATE_READ", captured.append)

    bus.publish(
        Event.create(
            stream_id="cam_01",
            frame_id=7,
            event_type="PLATE_CROPPED",
            payload={
                "track_id": "t1",
                "frame_ref": "mem://cam_01/7",
                "crop_ref": "mem://cam_01/7/plate/0",
            },
        ),
    )

    assert len(captured) == 1
    assert captured[0].payload == {
        "track_id": "t1",
        "frame_ref": "mem://cam_01/7",
        "crop_ref": "mem://cam_01/7/plate/0",
        "plate_text": "AB123",
        "confidence": 0.93,
        "status": "read",
        "error": None,
        "ocr_backend": "fake",
    }
    assert {"data", "frame", "image", "ndarray", "bytes", "raw", "crop"}.isdisjoint(
        captured[0].payload
    )


def test_ocr_handler_marks_no_read_without_empty_success() -> None:
    bus = LocalEventBus()
    store = FrameStore()
    store.store("mem://cam_01/7/plate/0", object())
    OCRHandler(bus=bus, backend=FakeOCRBackend(OCRResult(text="   ")), frame_store=store)
    captured: list[Event] = []
    bus.subscribe("PLATE_READ", captured.append)

    bus.publish(
        Event.create(
            stream_id="cam_01",
            frame_id=7,
            event_type="PLATE_CROPPED",
            payload={"frame_ref": "mem://cam_01/7", "crop_ref": "mem://cam_01/7/plate/0"},
        ),
    )

    assert captured[0].payload["status"] == "no_read"
    assert captured[0].payload["plate_text"] is None


def test_ocr_handler_marks_backend_errors() -> None:
    bus = LocalEventBus()
    store = FrameStore()
    store.store("mem://cam_01/7/plate/0", object())
    OCRHandler(bus=bus, backend=FakeOCRBackend(OCRResult(error="boom")), frame_store=store)
    captured: list[Event] = []
    bus.subscribe("PLATE_READ", captured.append)

    bus.publish(
        Event.create(
            stream_id="cam_01",
            frame_id=7,
            event_type="PLATE_CROPPED",
            payload={"frame_ref": "mem://cam_01/7", "crop_ref": "mem://cam_01/7/plate/0"},
        ),
    )

    assert captured[0].payload["status"] == "error"
    assert captured[0].payload["error"] == "boom"
    assert captured[0].payload["plate_text"] is None


def test_paddleocr_backend_uses_injected_reader_without_optional_import() -> None:
    reader = FakeReader(
        raw=[{"res": {"rec_texts": [" xy-987 ", " ab-123 "], "rec_scores": [0.41, 0.88]}}]
    )

    backend = PaddleOCRBackend(reader_factory=lambda **_options: reader)
    result = backend.read_plate({"crop": True})

    assert result.text == " ab-123 "
    assert result.confidence == 0.88
    assert reader.calls == [{"crop": True}]


def test_paddleocr_backend_accepts_prediction_objects() -> None:
    class FakePrediction:
        def __init__(self) -> None:
            self.rec_texts = ["cd 456"]
            self.rec_scores = [0.73]

    reader = FakeReader(raw=[FakePrediction()])

    result = PaddleOCRBackend(reader_factory=lambda **_options: reader).read_plate(object())

    assert result.text == "cd 456"
    assert result.confidence == 0.73


def test_paddleocr_backend_reports_predict_errors() -> None:
    reader = FakeReader(error=RuntimeError("predict failed"))

    result = PaddleOCRBackend(reader_factory=lambda **_options: reader).read_plate(object())

    assert result.status == "error"
    assert result.error == "predict failed"


def test_paddleocr_backend_reports_missing_optional_dependency() -> None:
    def missing_import(_name: str) -> object:
        raise ModuleNotFoundError("paddleocr")

    with pytest.raises(ConfigError, match="optional 'paddleocr' extra"):
        PaddleOCRBackend(import_module=missing_import)


def test_event_chain_vehicle_to_plate_cropped_to_plate_read_shape() -> None:
    bus = LocalEventBus()
    store = FrameStore()
    store.store("mem://cam_01/7", object())
    vehicle_detector = FakeVehicleDetector()
    plate_detector = PlateDetectorPlugin(
        locator=FakePlateLocator(),
        cropper=lambda _frame, _vehicle_bbox, plate_bbox: {"plate_bbox": plate_bbox},
    )
    ocr_backend = FakeOCRBackend(OCRResult(text="xy 987", confidence=0.81))

    VehicleDetectorHandler(bus=bus, detector=vehicle_detector, frame_store=store)
    PlateDetectorHandler(bus=bus, detector=plate_detector, frame_store=store)
    OCRHandler(bus=bus, backend=ocr_backend, frame_store=store)
    captured: list[Event] = []
    bus.subscribe("PLATE_READ", captured.append)

    bus.publish(
        Event.create(
            stream_id="cam_01",
            frame_id=7,
            event_type="NEW_FRAME",
            payload={"frame_ref": "mem://cam_01/7"},
        ),
    )

    assert len(captured) == 1
    assert captured[0].payload == {
        "track_id": None,
        "frame_ref": "mem://cam_01/7",
        "crop_ref": "mem://cam_01/7/plate/0",
        "plate_text": "XY987",
        "confidence": 0.81,
        "status": "read",
        "error": None,
        "ocr_backend": "fake",
    }
