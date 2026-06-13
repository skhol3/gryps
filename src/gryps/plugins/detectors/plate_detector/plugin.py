from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from gryps.plugins.detectors.base import BoundingBox


class PlateLocator(Protocol):
    """Callable boundary for plate localization inside a detected vehicle."""

    def __call__(
        self,
        frame: object,
        vehicle_bbox: BoundingBox,
        metadata: Mapping[str, Any],
    ) -> Iterable[Mapping[str, Any]]: ...


Cropper = Callable[[object, BoundingBox, BoundingBox], object]


@dataclass(frozen=True)
class PlateDetection:
    """Serializable plate crop candidate with media kept behind refs."""

    plate_bbox: BoundingBox
    crop: object
    confidence: float | None = None

    def __post_init__(self) -> None:
        if len(self.plate_bbox) != 4:
            raise ValueError("plate_bbox must contain exactly four values")
        if any(not isinstance(value, int | float) for value in self.plate_bbox):
            raise TypeError("plate_bbox values must be numbers")
        x_min, y_min, x_max, y_max = self.plate_bbox
        if x_max <= x_min:
            raise ValueError("plate_bbox x_max must be greater than x_min")
        if y_max <= y_min:
            raise ValueError("plate_bbox y_max must be greater than y_min")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


class PlateDetectorPlugin:
    """Plate bbox and crop production boundary.

    The locator and cropper are injected so tests and deployments can provide
    lightweight fakes or real model adapters without putting raw media on the
    EventBus.
    """

    def __init__(self, locator: PlateLocator, cropper: Cropper | None = None) -> None:
        self._locator = locator
        self._cropper = cropper or _default_cropper

    def detect_plates(
        self,
        frame: object,
        vehicle_bbox: BoundingBox,
        metadata: dict[str, Any],
    ) -> tuple[PlateDetection, ...]:
        detections: list[PlateDetection] = []
        for raw in self._locator(frame, vehicle_bbox, metadata):
            plate_bbox = _bbox(raw.get("plate_bbox", raw.get("bbox")))
            detections.append(
                PlateDetection(
                    plate_bbox=plate_bbox,
                    crop=self._cropper(frame, vehicle_bbox, plate_bbox),
                    confidence=_confidence(raw.get("confidence")),
                )
            )
        return tuple(detections)


def _default_cropper(frame: object, _vehicle_bbox: BoundingBox, _plate_bbox: BoundingBox) -> object:
    return frame


def _bbox(value: object) -> BoundingBox:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise TypeError("plate bbox must be a sequence of four numbers")
    bbox = tuple(float(item) for item in value)
    if len(bbox) != 4:
        raise ValueError("plate bbox must contain exactly four values")
    return bbox


def _confidence(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float):
        raise TypeError("confidence must be a number or None")
    return float(value)
