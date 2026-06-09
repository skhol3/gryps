from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Protocol

from gryps.plugins.detectors import BaseDetectorPlugin, DetectionResult

VEHICLE_CLASSES = frozenset({"car", "motorcycle", "bus", "truck"})

COCO_CLASS_NAMES: dict[int, str] = {
    0: "person",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


class InferenceAdapter(Protocol):
    """Callable boundary for model inference adapters."""

    def __call__(
        self,
        frame: object,
        metadata: Mapping[str, Any],
    ) -> Iterable[Mapping[str, Any]]: ...


class VehicleYOLOPlugin(BaseDetectorPlugin):
    """Vehicle detector boundary for YOLO-like model outputs.

    The model is injected so this plugin can be tested without importing
    Ultralytics, downloading weights, or owning event publication.
    """

    def __init__(
        self,
        model: InferenceAdapter | None = None,
        class_names: Mapping[int, str] | None = None,
    ) -> None:
        self._model = model
        self._class_names = dict(class_names or COCO_CLASS_NAMES)

    def detect(self, frame: object, metadata: dict[str, Any]) -> tuple[DetectionResult, ...]:
        if self._model is None:
            raise RuntimeError("VehicleYOLOPlugin requires an injected inference adapter")

        detections: list[DetectionResult] = []
        for raw in self._model(frame, metadata):
            class_name = self._class_name(raw)
            if class_name not in VEHICLE_CLASSES:
                continue

            detections.append(
                DetectionResult(
                    bbox=self._bbox(raw),
                    class_name=class_name,
                    confidence=self._confidence(raw),
                    track_id=self._track_id(raw),
                )
            )
        return tuple(detections)

    def _class_name(self, raw: Mapping[str, Any]) -> str:
        class_name = raw.get("class_name")
        if isinstance(class_name, str):
            return class_name

        class_id = raw.get("class_id")
        if isinstance(class_id, int):
            return self._class_names.get(class_id, "")

        return ""

    @staticmethod
    def _bbox(raw: Mapping[str, Any]) -> tuple[float, float, float, float]:
        bbox = raw.get("bbox")
        if not isinstance(bbox, Sequence) or isinstance(bbox, str | bytes):
            raise TypeError("bbox must be a sequence of four numbers")
        values = tuple(float(value) for value in bbox)
        if len(values) != 4:
            raise ValueError("bbox must contain exactly four values")
        return values

    @staticmethod
    def _confidence(raw: Mapping[str, Any]) -> float:
        confidence = raw.get("confidence")
        if not isinstance(confidence, int | float):
            raise TypeError("confidence must be a number")
        return float(confidence)

    @staticmethod
    def _track_id(raw: Mapping[str, Any]) -> int | str | None:
        track_id = raw.get("track_id")
        if track_id is None or isinstance(track_id, int | str):
            return track_id
        raise TypeError("track_id must be an int, str, or None")
