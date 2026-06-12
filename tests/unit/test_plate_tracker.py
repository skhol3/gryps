from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from gryps.tracking.plate_tracker import OcrStatus, PlateTracker, TrackState


class TestOcrStatus:
    def test_has_four_members(self) -> None:
        assert len(OcrStatus) == 4

    def test_uncached_value(self) -> None:
        assert OcrStatus.UNCACHED.value == "uncached"

    def test_pending_value(self) -> None:
        assert OcrStatus.PENDING.value == "pending"

    def test_cached_value(self) -> None:
        assert OcrStatus.CACHED.value == "cached"

    def test_failed_value(self) -> None:
        assert OcrStatus.FAILED.value == "failed"

    def test_members_are_unique(self) -> None:
        values = [m.value for m in OcrStatus]
        assert len(values) == len(set(values))


class TestTrackState:
    def test_is_frozen(self) -> None:
        state = TrackState(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            best_frame_ref="mem://stream/5",
            best_confidence=0.85,
            last_seen_frame_id=5,
            last_seen_timestamp=1000.0,
        )
        with pytest.raises(FrozenInstanceError):
            state.bbox = (1.0, 2.0, 3.0, 4.0)  # type: ignore[misc]

    def test_has_all_design_fields(self) -> None:
        state = TrackState(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            best_frame_ref="mem://stream/5",
            best_confidence=0.85,
            last_seen_frame_id=5,
            last_seen_timestamp=1000.0,
        )
        assert state.track_id == 42
        assert state.bbox == (0.0, 0.0, 10.0, 20.0)
        assert state.confidence == 0.85
        assert state.best_frame_ref == "mem://stream/5"
        assert state.best_confidence == 0.85
        assert state.last_seen_frame_id == 5
        assert state.last_seen_timestamp == 1000.0

    def test_default_ocr_status_is_uncached(self) -> None:
        state = TrackState(
            track_id=1,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.9,
            best_frame_ref="mem://stream/1",
            best_confidence=0.9,
            last_seen_frame_id=1,
            last_seen_timestamp=100.0,
        )
        assert state.ocr_status == OcrStatus.UNCACHED

    def test_default_lost_is_false(self) -> None:
        state = TrackState(
            track_id=1,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.9,
            best_frame_ref="mem://stream/1",
            best_confidence=0.9,
            last_seen_frame_id=1,
            last_seen_timestamp=100.0,
        )
        assert state.lost is False

    def test_default_lost_at_frame_is_none(self) -> None:
        state = TrackState(
            track_id=1,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.9,
            best_frame_ref="mem://stream/1",
            best_confidence=0.9,
            last_seen_frame_id=1,
            last_seen_timestamp=100.0,
        )
        assert state.lost_at_frame is None

    def test_accepts_explicit_ocr_status(self) -> None:
        state = TrackState(
            track_id=1,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.9,
            best_frame_ref="mem://stream/1",
            best_confidence=0.9,
            last_seen_frame_id=1,
            last_seen_timestamp=100.0,
            ocr_status=OcrStatus.PENDING,
        )
        assert state.ocr_status == OcrStatus.PENDING

    def test_accepts_explicit_lost_and_lost_at_frame(self) -> None:
        state = TrackState(
            track_id=1,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.9,
            best_frame_ref="mem://stream/1",
            best_confidence=0.9,
            last_seen_frame_id=1,
            last_seen_timestamp=100.0,
            lost=True,
            lost_at_frame=50,
        )
        assert state.lost is True
        assert state.lost_at_frame == 50


class TestPlateTracker:
    def test_new_track_from_first_observation(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        state = tracker.get_state(42)
        assert state is not None
        assert state.track_id == 42
        assert state.bbox == (0.0, 0.0, 10.0, 20.0)
        assert state.confidence == 0.85
        assert state.best_frame_ref == "mem://stream/5"
        assert state.best_confidence == 0.85
        assert state.lost is False
        assert state.ocr_status == OcrStatus.UNCACHED

    def test_existing_track_updated(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.update(
            track_id=42,
            bbox=(5.0, 5.0, 15.0, 25.0),
            confidence=0.92,
            frame_ref="mem://stream/10",
            frame_id=10,
            timestamp=1001.0,
        )
        state = tracker.get_state(42)
        assert state is not None
        assert state.bbox == (5.0, 5.0, 15.0, 25.0)
        assert state.last_seen_frame_id == 10
        assert state.lost is False

    def test_track_lost_after_gap(self) -> None:
        tracker = PlateTracker(gap_threshold=30)
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=10,
            timestamp=1000.0,
        )
        lost = tracker.lost_tracks(current_frame_id=45)
        assert len(lost) == 1
        assert lost[0].track_id == 42
        assert lost[0].lost is True

    def test_re_acquire_previously_lost_track(self) -> None:
        tracker = PlateTracker(gap_threshold=30)
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=10,
            timestamp=1000.0,
        )
        tracker.lost_tracks(current_frame_id=45)
        tracker.update(
            track_id=42,
            bbox=(5.0, 5.0, 15.0, 25.0),
            confidence=0.92,
            frame_ref="mem://stream/46",
            frame_id=46,
            timestamp=1002.0,
        )
        state = tracker.get_state(42)
        assert state is not None
        assert state.lost is False
        assert state.lost_at_frame is None
        assert state.last_seen_frame_id == 46

    def test_track_not_lost_within_gap(self) -> None:
        tracker = PlateTracker(gap_threshold=30)
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=20,
            timestamp=1000.0,
        )
        lost = tracker.lost_tracks(current_frame_id=45)
        assert len(lost) == 0
        state = tracker.get_state(42)
        assert state is not None
        assert state.lost is False

    def test_gap_threshold_at_boundary(self) -> None:
        tracker = PlateTracker(gap_threshold=30)
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=15,
            timestamp=1000.0,
        )
        lost = tracker.lost_tracks(current_frame_id=45)
        assert len(lost) == 0

    def test_two_concurrent_tracks_independent(self) -> None:
        tracker = PlateTracker(gap_threshold=30)
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.update(
            track_id=99,
            bbox=(10.0, 10.0, 20.0, 30.0),
            confidence=0.90,
            frame_ref="mem://stream/50",
            frame_id=50,
            timestamp=1001.0,
        )
        lost = tracker.lost_tracks(current_frame_id=60)
        lost_ids = {t.track_id for t in lost}
        assert 42 in lost_ids
        assert 99 not in lost_ids

    def test_reject_none_track_id(self) -> None:
        tracker = PlateTracker()
        with pytest.raises(ValueError, match="track_id"):
            tracker.update(
                track_id=None,
                bbox=(0.0, 0.0, 10.0, 20.0),
                confidence=0.85,
                frame_ref="mem://stream/5",
                frame_id=5,
                timestamp=1000.0,
            )

    def test_active_tracks_returns_non_lost(self) -> None:
        tracker = PlateTracker(gap_threshold=5)
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.update(
            track_id=99,
            bbox=(10.0, 10.0, 20.0, 30.0),
            confidence=0.90,
            frame_ref="mem://stream/59",
            frame_id=59,
            timestamp=1001.0,
        )
        tracker.lost_tracks(current_frame_id=60)
        active = tracker.active_tracks()
        active_ids = {t.track_id for t in active}
        assert 42 not in active_ids
        assert 99 in active_ids

    def test_get_state_returns_none_for_unknown(self) -> None:
        tracker = PlateTracker()
        assert tracker.get_state(999) is None


class TestBestFrameSelection:
    def test_higher_confidence_replaces_best(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.update(
            track_id=42,
            bbox=(5.0, 5.0, 15.0, 25.0),
            confidence=0.93,
            frame_ref="mem://stream/12",
            frame_id=12,
            timestamp=1001.0,
        )
        state = tracker.get_state(42)
        assert state is not None
        assert state.best_confidence == 0.93
        assert state.best_frame_ref == "mem://stream/12"

    def test_lower_confidence_does_not_replace(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.update(
            track_id=42,
            bbox=(5.0, 5.0, 15.0, 25.0),
            confidence=0.80,
            frame_ref="mem://stream/12",
            frame_id=12,
            timestamp=1001.0,
        )
        state = tracker.get_state(42)
        assert state is not None
        assert state.best_confidence == 0.85
        assert state.best_frame_ref == "mem://stream/5"

    def test_tie_does_not_replace_first_best_wins(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.update(
            track_id=42,
            bbox=(5.0, 5.0, 15.0, 25.0),
            confidence=0.85,
            frame_ref="mem://stream/12",
            frame_id=12,
            timestamp=1001.0,
        )
        state = tracker.get_state(42)
        assert state is not None
        assert state.best_confidence == 0.85
        assert state.best_frame_ref == "mem://stream/5"


class TestOcrCache:
    def test_new_track_starts_uncached(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        state = tracker.get_state(42)
        assert state is not None
        assert state.ocr_status == OcrStatus.UNCACHED

    def test_enqueue_transitions_to_pending(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.ocr_enqueue(42)
        state = tracker.get_state(42)
        assert state is not None
        assert state.ocr_status == OcrStatus.PENDING

    def test_resolve_to_cached(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.ocr_enqueue(42)
        tracker.ocr_resolve(42, OcrStatus.CACHED)
        state = tracker.get_state(42)
        assert state is not None
        assert state.ocr_status == OcrStatus.CACHED

    def test_resolve_to_failed(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.ocr_enqueue(42)
        tracker.ocr_resolve(42, OcrStatus.FAILED)
        state = tracker.get_state(42)
        assert state is not None
        assert state.ocr_status == OcrStatus.FAILED

    def test_rejects_backward_transition(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.ocr_enqueue(42)
        tracker.ocr_resolve(42, OcrStatus.CACHED)
        with pytest.raises(ValueError, match="ocr_status"):
            tracker.ocr_enqueue(42)
        state = tracker.get_state(42)
        assert state is not None
        assert state.ocr_status == OcrStatus.CACHED

    def test_rejects_enqueue_from_cached_directly(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.ocr_enqueue(42)
        tracker.ocr_resolve(42, OcrStatus.FAILED)
        with pytest.raises(ValueError, match="ocr_status"):
            tracker.ocr_enqueue(42)
        state = tracker.get_state(42)
        assert state is not None
        assert state.ocr_status == OcrStatus.FAILED

    def test_resolve_from_uncached_rejected(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        with pytest.raises(ValueError, match="ocr_status"):
            tracker.ocr_resolve(42, OcrStatus.CACHED)

    def test_resolve_from_cached_rejected(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.ocr_enqueue(42)
        tracker.ocr_resolve(42, OcrStatus.CACHED)
        with pytest.raises(ValueError, match="ocr_status"):
            tracker.ocr_resolve(42, OcrStatus.FAILED)

    def test_resolve_from_failed_rejected(self) -> None:
        tracker = PlateTracker()
        tracker.update(
            track_id=42,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.85,
            frame_ref="mem://stream/5",
            frame_id=5,
            timestamp=1000.0,
        )
        tracker.ocr_enqueue(42)
        tracker.ocr_resolve(42, OcrStatus.FAILED)
        with pytest.raises(ValueError, match="ocr_status"):
            tracker.ocr_resolve(42, OcrStatus.CACHED)
