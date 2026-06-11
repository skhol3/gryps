from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class UltralyticsAdapter:
    """Lazy adapter that maps Ultralytics ``Results`` to the generic dict format.

    Wraps an ``ultralytics.YOLO`` model and satisfies ``InferenceAdapter``
    so it can be injected into ``VehicleYOLOPlugin``.

    Ultralytics is NOT imported at module level — the adapter only depends on
    the model's output shape, not on the ultralytics package itself.
    """

    def __init__(self, model: Any) -> None:
        self._model = model

    def __call__(
        self,
        frame: object,
        metadata: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        _ = metadata  # InferenceAdapter protocol requires metadata parameter
        results = self._model(frame)
        if not results:
            return []

        boxes = results[0].boxes
        if boxes is None:
            return []

        detections: list[dict[str, Any]] = []
        n = len(boxes)
        for i in range(n):
            bbox = [float(v) for v in boxes.xyxy[i]]
            confidence = float(boxes.conf[i])
            class_id = int(boxes.cls[i])

            item: dict[str, Any] = {
                "class_id": class_id,
                "confidence": confidence,
                "bbox": bbox,
            }
            if boxes.id is not None:
                item["track_id"] = int(boxes.id[i])

            detections.append(item)

        return detections
