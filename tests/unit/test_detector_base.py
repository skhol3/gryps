from __future__ import annotations

from typing import Any

import pytest

from gryps.plugins.detectors import BaseDetectorPlugin, DetectionResult


class TestDetectionResult:
    def test_serializes_required_fields_with_xyxy_bbox(self) -> None:
        result = DetectionResult(
            bbox=(1.0, 2.0, 30.0, 40.0),
            class_name="vehicle",
            confidence=0.98,
        )

        assert result.to_payload() == {
            "bbox": [1.0, 2.0, 30.0, 40.0],
            "class_name": "vehicle",
            "confidence": 0.98,
        }

    def test_serializes_optional_track_id(self) -> None:
        result = DetectionResult(
            bbox=(1.0, 2.0, 30.0, 40.0),
            class_name="vehicle",
            confidence=0.98,
            track_id="track-1",
        )

        assert result.to_payload()["track_id"] == "track-1"

    @pytest.mark.parametrize(
        ("bbox", "error"),
        [
            ((1.0, 2.0, 3.0), "exactly four"),
        ],
    )
    def test_validates_bbox_shape(self, bbox: tuple[float, ...], error: str) -> None:
        with pytest.raises(ValueError, match=error):
            DetectionResult(bbox=bbox, class_name="vehicle", confidence=0.5)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "bbox",
        [
            (-1.0, 2.0, 3.0, 4.0),
            (1.0, -2.0, 3.0, 4.0),
            (1.0, 2.0, -3.0, 4.0),
            (1.0, 2.0, 3.0, -4.0),
        ],
    )
    def test_validates_bbox_non_negative_coordinates(
        self,
        bbox: tuple[float, float, float, float],
    ) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            DetectionResult(bbox=bbox, class_name="vehicle", confidence=0.5)

    @pytest.mark.parametrize(
        ("bbox", "error"),
        [
            ((1.0, 2.0, 1.0, 4.0), "x_max"),
            ((2.0, 2.0, 1.0, 4.0), "x_max"),
            ((1.0, 2.0, 3.0, 2.0), "y_max"),
            ((1.0, 3.0, 3.0, 2.0), "y_max"),
        ],
    )
    def test_validates_bbox_xyxy_half_open_geometry(
        self,
        bbox: tuple[float, float, float, float],
        error: str,
    ) -> None:
        with pytest.raises(ValueError, match=error):
            DetectionResult(bbox=bbox, class_name="vehicle", confidence=0.5)

    def test_rejects_non_numeric_bbox_coordinate(self) -> None:
        with pytest.raises(TypeError, match="numbers"):
            DetectionResult(
                bbox=(1.0, 2.0, "3.0", 4.0),  # type: ignore[arg-type]
                class_name="vehicle",
                confidence=0.5,
            )

    def test_validates_class_name(self) -> None:
        with pytest.raises(ValueError, match="class_name"):
            DetectionResult(bbox=(1.0, 2.0, 3.0, 4.0), class_name="", confidence=0.5)

    @pytest.mark.parametrize("confidence", [-0.1, 1.1])
    def test_validates_confidence(self, confidence: float) -> None:
        with pytest.raises(ValueError, match="confidence"):
            DetectionResult(
                bbox=(1.0, 2.0, 3.0, 4.0),
                class_name="vehicle",
                confidence=confidence,
            )

    def test_payload_has_no_raw_frame_data(self) -> None:
        payload = DetectionResult(
            bbox=(1.0, 2.0, 3.0, 4.0),
            class_name="vehicle",
            confidence=0.5,
        ).to_payload()

        raw_keys = {"data", "frame", "image", "ndarray", "bytes", "raw"}
        assert raw_keys.isdisjoint(payload)

    def test_rejects_non_serializable_track_id(self) -> None:
        with pytest.raises(TypeError, match="track_id"):
            DetectionResult(
                bbox=(1.0, 2.0, 3.0, 4.0),
                class_name="vehicle",
                confidence=0.5,
                track_id=object(),  # type: ignore[arg-type]
            )

    def test_documents_bbox_contract(self) -> None:
        docstring = DetectionResult.__doc__ or ""

        assert "xyxy" in docstring
        assert "(x_min, y_min, x_max, y_max)" in docstring
        assert "processed-frame coordinate space" in docstring
        assert "half-open" in docstring


class TestBaseDetectorPlugin:
    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            BaseDetectorPlugin()  # type: ignore[abstract]

    def test_concrete_detector_contract_shape(self) -> None:
        class FakeDetector(BaseDetectorPlugin):
            def detect(
                self,
                frame: object,
                metadata: dict[str, Any],
            ) -> tuple[DetectionResult, ...]:
                assert frame == "frame-ref-owned-by-caller"
                assert metadata["frame_ref"] == "mem://stream/0"
                return (
                    DetectionResult(
                        bbox=(10.0, 20.0, 30.0, 40.0),
                        class_name="vehicle",
                        confidence=0.9,
                        track_id=7,
                    ),
                )

        detections = FakeDetector().detect(
            "frame-ref-owned-by-caller",
            {"frame_ref": "mem://stream/0"},
        )

        assert detections == (
            DetectionResult(
                bbox=(10.0, 20.0, 30.0, 40.0),
                class_name="vehicle",
                confidence=0.9,
                track_id=7,
            ),
        )

    def test_imports_from_detector_package(self) -> None:
        assert BaseDetectorPlugin.__name__ == "BaseDetectorPlugin"
        assert DetectionResult.__name__ == "DetectionResult"
