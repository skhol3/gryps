from __future__ import annotations

import enum
from dataclasses import dataclass, replace

from gryps.plugins.detectors.base import BoundingBox, TrackId


class OcrStatus(enum.Enum):
    UNCACHED = "uncached"
    PENDING = "pending"
    CACHED = "cached"
    FAILED = "failed"


@dataclass(frozen=True)
class TrackState:
    track_id: TrackId
    bbox: BoundingBox
    confidence: float
    best_frame_ref: str
    best_confidence: float
    last_seen_frame_id: int
    last_seen_timestamp: float
    ocr_status: OcrStatus = OcrStatus.UNCACHED
    lost: bool = False
    lost_at_frame: int | None = None


class PlateTracker:
    def __init__(self, gap_threshold: int = 30) -> None:
        self._gap_threshold = gap_threshold
        self._tracks: dict[TrackId, TrackState] = {}

    def update(
        self,
        track_id: TrackId | None,
        bbox: BoundingBox,
        confidence: float,
        frame_ref: str,
        frame_id: int,
        timestamp: float,
    ) -> None:
        if track_id is None:
            raise ValueError("track_id must not be None")

        if track_id in self._tracks:
            existing = self._tracks[track_id]
            best_confidence = existing.best_confidence
            best_frame_ref = existing.best_frame_ref
            if confidence > best_confidence:
                best_confidence = confidence
                best_frame_ref = frame_ref
            self._tracks[track_id] = replace(
                existing,
                bbox=bbox,
                confidence=confidence,
                best_frame_ref=best_frame_ref,
                best_confidence=best_confidence,
                last_seen_frame_id=frame_id,
                last_seen_timestamp=timestamp,
                lost=False,
                lost_at_frame=None,
            )
        else:
            self._tracks[track_id] = TrackState(
                track_id=track_id,
                bbox=bbox,
                confidence=confidence,
                best_frame_ref=frame_ref,
                best_confidence=confidence,
                last_seen_frame_id=frame_id,
                last_seen_timestamp=timestamp,
            )

    def lost_tracks(self, current_frame_id: int) -> list[TrackState]:
        lost: list[TrackState] = []
        for tid, state in self._tracks.items():
            gap = current_frame_id - state.last_seen_frame_id
            if gap > self._gap_threshold:
                updated = replace(
                    state,
                    lost=True,
                    lost_at_frame=current_frame_id,
                )
                self._tracks[tid] = updated
                lost.append(updated)
        return lost

    def active_tracks(self) -> list[TrackState]:
        return [s for s in self._tracks.values() if not s.lost]

    def get_state(self, track_id: TrackId) -> TrackState | None:
        return self._tracks.get(track_id)

    def ocr_enqueue(self, track_id: TrackId) -> None:
        state = self._tracks.get(track_id)
        if state is None:
            raise ValueError(f"track_id {track_id!r} not found")
        if state.ocr_status is not OcrStatus.UNCACHED:
            raise ValueError(
                f"cannot enqueue track {track_id!r}: "
                f"current ocr_status is {state.ocr_status.value!r}"
            )
        self._tracks[track_id] = replace(state, ocr_status=OcrStatus.PENDING)

    def ocr_resolve(self, track_id: TrackId, status: OcrStatus) -> None:
        state = self._tracks.get(track_id)
        if state is None:
            raise ValueError(f"track_id {track_id!r} not found")
        if state.ocr_status is not OcrStatus.PENDING:
            raise ValueError(
                f"cannot resolve track {track_id!r}: "
                f"current ocr_status is {state.ocr_status.value!r}"
            )
        if status not in (OcrStatus.CACHED, OcrStatus.FAILED):
            raise ValueError(
                f"cannot resolve to {status.value!r}: only CACHED or FAILED allowed"
            )
        self._tracks[track_id] = replace(state, ocr_status=status)
