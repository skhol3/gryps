from __future__ import annotations

from typing import Any

import pytest

from gryps.plugins.detectors.vehicle_yolo.plugin import InferenceAdapter
from gryps.plugins.detectors.vehicle_yolo.ultralytics_adapter import UltralyticsAdapter


class FakeBoxes:
    """Mimics ``ultralytics.engine.results.Boxes`` for testing without torch/ultralytics."""

    def __init__(
        self,
        xyxy: list[list[float]],
        conf: list[float],
        cls: list[int],
        ids: list[int] | None = None,
    ) -> None:
        self.xyxy = xyxy
        self.conf = conf
        self.cls = cls
        self.id = ids

    def __len__(self) -> int:
        return len(self.xyxy)


class FakeUltralyticsResults:
    """Mimics ``ultralytics.engine.results.Results`` for testing."""

    def __init__(self, boxes: FakeBoxes | None = None) -> None:
        self.boxes = boxes


class FakeUltralyticsYOLO:
    """Mimics ``ultralytics.YOLO`` callable for testing."""

    def __init__(self, results: list[FakeUltralyticsResults]) -> None:
        self._results = results
        self.calls: list[tuple[object, ...]] = []

    def __call__(self, frame: object, *args: Any, **kwargs: Any) -> list[FakeUltralyticsResults]:
        self.calls.append((frame, args, kwargs))
        return self._results


class TestUltralyticsAdapterConformsToProtocol:
    def test_is_callable_with_frame_and_metadata(self) -> None:
        model = FakeUltralyticsYOLO(
            [FakeUltralyticsResults(FakeBoxes(xyxy=[[0, 0, 10, 10]], conf=[0.9], cls=[2]))]
        )
        adapter = UltralyticsAdapter(model)

        result = adapter(object(), {})

        assert len(result) == 1

    def test_satisfies_inference_adapter_protocol(self) -> None:
        model = FakeUltralyticsYOLO(
            [FakeUltralyticsResults(FakeBoxes(xyxy=[[0, 0, 10, 10]], conf=[0.9], cls=[2]))]
        )
        adapter: InferenceAdapter = UltralyticsAdapter(model)

        assert adapter is not None


class TestUltralyticsAdapterMapping:
    def test_converts_box_to_dict_with_class_id_confidence_bbox(self) -> None:
        model = FakeUltralyticsYOLO(
            [FakeUltralyticsResults(
                FakeBoxes(xyxy=[[10.0, 20.0, 30.0, 40.0]], conf=[0.91], cls=[2])
            )]
        )
        adapter = UltralyticsAdapter(model)

        result = adapter(object(), {})

        assert len(result) == 1
        item = result[0]
        assert item["class_id"] == 2
        assert item["confidence"] == 0.91
        assert item["bbox"] == [10.0, 20.0, 30.0, 40.0]

    def test_handles_multiple_detections(self) -> None:
        model = FakeUltralyticsYOLO(
            [FakeUltralyticsResults(
                FakeBoxes(
                    xyxy=[[0, 0, 10, 10], [5, 5, 15, 15]],
                    conf=[0.9, 0.8],
                    cls=[2, 7],
                )
            )]
        )
        adapter = UltralyticsAdapter(model)

        result = adapter(object(), {})

        assert len(result) == 2
        assert result[0]["class_id"] == 2
        assert result[0]["confidence"] == 0.9
        assert result[0]["bbox"] == [0.0, 0.0, 10.0, 10.0]
        assert result[1]["class_id"] == 7
        assert result[1]["confidence"] == 0.8
        assert result[1]["bbox"] == [5.0, 5.0, 15.0, 15.0]

    def test_handles_no_detections(self) -> None:
        model = FakeUltralyticsYOLO(
            [FakeUltralyticsResults(FakeBoxes(xyxy=[], conf=[], cls=[]))]
        )
        adapter = UltralyticsAdapter(model)

        result = adapter(object(), {})

        assert result == []

    def test_handles_none_boxes(self) -> None:
        model = FakeUltralyticsYOLO([FakeUltralyticsResults(boxes=None)])
        adapter = UltralyticsAdapter(model)

        result = adapter(object(), {})

        assert result == []

    def test_includes_optional_track_id(self) -> None:
        model = FakeUltralyticsYOLO(
            [FakeUltralyticsResults(
                FakeBoxes(xyxy=[[0, 0, 10, 10]], conf=[0.9], cls=[2], ids=[1])
            )]
        )
        adapter = UltralyticsAdapter(model)

        result = adapter(object(), {})

        assert len(result) == 1
        assert result[0]["track_id"] == 1

    def test_omits_track_id_when_not_available(self) -> None:
        model = FakeUltralyticsYOLO(
            [FakeUltralyticsResults(
                FakeBoxes(xyxy=[[0, 0, 10, 10]], conf=[0.9], cls=[2])
            )]
        )
        adapter = UltralyticsAdapter(model)

        result = adapter(object(), {})

        assert "track_id" not in result[0]

    def test_passes_frame_to_model(self) -> None:
        fake_model = FakeUltralyticsYOLO(
            [FakeUltralyticsResults(FakeBoxes(xyxy=[[0, 0, 10, 10]], conf=[0.9], cls=[2]))]
        )
        adapter = UltralyticsAdapter(fake_model)
        frame = object()
        metadata = {"frame_id": 7}

        adapter(frame, metadata)

        assert len(fake_model.calls) == 1
        assert fake_model.calls[0][0] is frame

    def test_feeds_vehicle_yolo_plugin_via_adapter(self) -> None:
        from gryps.plugins.detectors.vehicle_yolo.plugin import VehicleYOLOPlugin

        model = FakeUltralyticsYOLO(
            [FakeUltralyticsResults(
                FakeBoxes(
                    xyxy=[[10, 20, 30, 40], [50, 60, 70, 80]],
                    conf=[0.91, 0.82],
                    cls=[2, 7],
                )
            )]
        )
        adapter = UltralyticsAdapter(model)
        plugin = VehicleYOLOPlugin(model=adapter)

        detections = plugin.detect(object(), {})

        assert len(detections) == 2
        assert detections[0].class_name == "car"
        assert detections[0].confidence == 0.91
        assert detections[1].class_name == "truck"
        assert detections[1].confidence == 0.82


class TestUltralyticsAdapterLazyImport:
    def test_module_import_does_not_require_ultralytics(self) -> None:
        import sys

        existing = "ultralytics" in sys.modules
        if existing:
            pytest.skip("ultralytics is already imported in this execution environment")

        # Fresh import — the module should not pull in ultralytics
        from gryps.plugins.detectors.vehicle_yolo import ultralytics_adapter  # noqa: F811,F401

        assert "ultralytics" not in sys.modules
