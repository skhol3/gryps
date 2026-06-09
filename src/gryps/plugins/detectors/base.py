from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

BoundingBox = tuple[float, float, float, float]
TrackId = int | str


@dataclass(frozen=True)
class DetectionResult:
    """Serializable detector output for one object candidate.

    ``bbox`` uses pixel coordinates in ``xyxy`` order:
    ``(x_min, y_min, x_max, y_max)``. Coordinates are non-negative numbers
    in processed-frame coordinate space after preprocessors such as ROI.
    Bounds are half-open: ``x_min``/``y_min`` are inclusive and
    ``x_max``/``y_max`` are exclusive.
    """

    bbox: BoundingBox
    class_name: str
    confidence: float
    track_id: TrackId | None = None

    def __post_init__(self) -> None:
        if len(self.bbox) != 4:
            raise ValueError("bbox must contain exactly four values")
        if any(not isinstance(value, int | float) for value in self.bbox):
            raise TypeError("bbox values must be numbers")
        if any(value < 0 for value in self.bbox):
            raise ValueError("bbox values must be non-negative")
        x_min, y_min, x_max, y_max = self.bbox
        if x_max <= x_min:
            raise ValueError("bbox x_max must be greater than x_min")
        if y_max <= y_min:
            raise ValueError("bbox y_max must be greater than y_min")
        if not self.class_name:
            raise ValueError("class_name must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.track_id is not None and not isinstance(self.track_id, int | str):
            raise TypeError("track_id must be an int, str, or None")

    def to_payload(self) -> dict[str, object]:
        """Return an EventBus-safe payload fragment with no raw frame data."""
        payload: dict[str, object] = {
            "bbox": list(self.bbox),
            "class_name": self.class_name,
            "confidence": self.confidence,
        }
        if self.track_id is not None:
            payload["track_id"] = self.track_id
        return payload


class BaseDetectorPlugin(ABC):
    """Abstract base for detector plugins.

    Detectors inspect an in-memory frame supplied by the caller and return
    serializable detection results. They must not publish raw frames to the
    EventBus; callers decide how events and frame references are emitted.
    """

    @abstractmethod
    def detect(self, frame: object, metadata: dict[str, Any]) -> tuple[DetectionResult, ...]:
        """Return detections for the supplied frame and metadata."""
