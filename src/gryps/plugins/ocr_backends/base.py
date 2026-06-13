from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from gryps.plugins.detectors.base import TrackId

OCRStatus = Literal["read", "no_read", "error"]


@dataclass(frozen=True)
class PlateReadPayload:
    """EventBus-safe ``PLATE_READ`` payload.

    Media stays behind the opaque ``frame_ref`` and ``crop_ref`` identifiers;
    consumers that need pixels must resolve them through ``FrameStore`` or a
    backend-specific adapter instead of reading bytes from EventBus payloads.
    """

    track_id: TrackId | None
    frame_ref: str
    crop_ref: str
    plate_text: str | None
    confidence: float | None
    status: OCRStatus
    error: str | None
    ocr_backend: str

    def to_payload(self) -> dict[str, object]:
        return {
            "track_id": self.track_id,
            "frame_ref": self.frame_ref,
            "crop_ref": self.crop_ref,
            "plate_text": self.plate_text,
            "confidence": self.confidence,
            "status": self.status,
            "error": self.error,
            "ocr_backend": self.ocr_backend,
        }


@dataclass(frozen=True)
class OCRResult:
    """Normalized backend result before it is attached to source refs."""

    text: str | None = None
    confidence: float | None = None
    error: str | None = None

    @property
    def status(self) -> OCRStatus:
        if self.error is not None:
            return "error"
        if normalize_plate_text(self.text):
            return "read"
        return "no_read"

    def as_plate_read(
        self,
        *,
        track_id: TrackId | None,
        frame_ref: str,
        crop_ref: str,
        backend_name: str,
    ) -> PlateReadPayload:
        normalized = normalize_plate_text(self.text)
        status = self.status
        return PlateReadPayload(
            track_id=track_id,
            frame_ref=frame_ref,
            crop_ref=crop_ref,
            plate_text=normalized if status == "read" else None,
            confidence=self.confidence,
            status=status,
            error=self.error,
            ocr_backend=backend_name,
        )


class BaseOCRBackend(ABC):
    """Backend contract for reading a plate crop supplied by the caller."""

    name: str

    @abstractmethod
    def read_plate(self, crop: object) -> OCRResult:
        """Return OCR text/confidence for a crop object without publishing events."""


def normalize_plate_text(text: str | None) -> str:
    """Normalize OCR output into a transport-safe plate candidate."""
    if text is None:
        return ""
    return re.sub(r"[^A-Z0-9]", "", text.upper())
