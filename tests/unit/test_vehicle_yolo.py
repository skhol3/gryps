from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from gryps.core.registry import PluginRegistry
from gryps.plugins.detectors import BaseDetectorPlugin, DetectionResult
from gryps.plugins.detectors.vehicle_yolo.plugin import VehicleYOLOPlugin

SRC = Path(__file__).parent.parent.parent / "src"


class FakeModel:
    def __init__(self, outputs: list[Mapping[str, Any]]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[object, Mapping[str, Any]]] = []

    def __call__(self, frame: object, metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        self.calls.append((frame, metadata))
        return self.outputs


class TestVehicleYOLOPlugin:
    def test_converts_vehicle_outputs_to_detection_results(self) -> None:
        model = FakeModel(
            [
                {
                    "class_name": "car",
                    "confidence": 0.91,
                    "bbox": [10, 20, 30, 40],
                    "track_id": "track-1",
                },
                {
                    "class_name": "truck",
                    "confidence": 0.82,
                    "bbox": (1.5, 2.5, 11.5, 22.5),
                },
            ]
        )
        plugin = VehicleYOLOPlugin(model=model)

        detections = plugin.detect("processed-frame", {"frame_id": 7})

        assert model.calls == [("processed-frame", {"frame_id": 7})]
        assert detections == (
            DetectionResult(
                bbox=(10.0, 20.0, 30.0, 40.0),
                class_name="car",
                confidence=0.91,
                track_id="track-1",
            ),
            DetectionResult(
                bbox=(1.5, 2.5, 11.5, 22.5),
                class_name="truck",
                confidence=0.82,
            ),
        )

    def test_filters_to_hu_005_vehicle_classes_and_ignores_person(self) -> None:
        model = FakeModel(
            [
                {"class_name": "car", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
                {"class_name": "motorcycle", "confidence": 0.8, "bbox": [1, 1, 11, 11]},
                {"class_name": "bus", "confidence": 0.7, "bbox": [2, 2, 12, 12]},
                {"class_name": "truck", "confidence": 0.6, "bbox": [3, 3, 13, 13]},
                {"class_name": "person", "confidence": 0.99, "bbox": [4, 4, 14, 14]},
                {"class_name": "bicycle", "confidence": 0.5, "bbox": [5, 5, 15, 15]},
            ]
        )

        detections = VehicleYOLOPlugin(model=model).detect(object(), {})

        assert [detection.class_name for detection in detections] == [
            "car",
            "motorcycle",
            "bus",
            "truck",
        ]

    def test_maps_coco_class_ids_to_vehicle_names(self) -> None:
        model = FakeModel(
            [
                {"class_id": 0, "confidence": 0.99, "bbox": [0, 0, 10, 10]},
                {"class_id": 2, "confidence": 0.9, "bbox": [1, 1, 11, 11]},
                {"class_id": 3, "confidence": 0.8, "bbox": [2, 2, 12, 12]},
                {"class_id": 5, "confidence": 0.7, "bbox": [3, 3, 13, 13]},
                {"class_id": 7, "confidence": 0.6, "bbox": [4, 4, 14, 14]},
            ]
        )

        detections = VehicleYOLOPlugin(model=model).detect(object(), {})

        assert [detection.class_name for detection in detections] == [
            "car",
            "motorcycle",
            "bus",
            "truck",
        ]

    def test_uses_processed_frame_xyxy_half_open_bbox_contract(self) -> None:
        model = FakeModel(
            [
                {"class_name": "car", "confidence": 0.9, "bbox": [10, 20, 30, 40]},
                {"class_name": "car", "confidence": 0.9, "bbox": [10, 20, 10, 40]},
            ]
        )

        with pytest.raises(ValueError, match="x_max"):
            VehicleYOLOPlugin(model=model).detect("processed-frame", {})

    def test_requires_injected_model_for_detection(self) -> None:
        with pytest.raises(RuntimeError, match="injected inference adapter"):
            VehicleYOLOPlugin().detect(object(), {})

    def test_payload_has_no_raw_frame_data(self) -> None:
        model = FakeModel(
            [{"class_name": "car", "confidence": 0.9, "bbox": [10, 20, 30, 40]}]
        )

        payload = VehicleYOLOPlugin(model=model).detect(object(), {})[0].to_payload()

        raw_keys = {"data", "frame", "image", "ndarray", "bytes", "raw"}
        assert raw_keys.isdisjoint(payload)


class TestVehicleYOLOPluginRegistry:
    def test_discoverable_by_registry(self) -> None:
        plugin_dir = SRC / "gryps" / "plugins" / "detectors" / "vehicle_yolo"

        reg = PluginRegistry(roots=[str(plugin_dir)])
        reg.discover()

        assert "vehicle_yolo" in reg.plugins
        info = reg.plugins["vehicle_yolo"]
        assert info.loaded_class is not None
        assert info.loaded_class.__name__ == "VehicleYOLOPlugin"
        loaded_instance = info.loaded_class()
        assert isinstance(loaded_instance, BaseDetectorPlugin)
