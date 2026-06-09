from __future__ import annotations

import pytest

from gryps.core import Event, LocalEventBus
from gryps.streams import BaseStreamSource, FileStream, FrameMetadata, FrameReader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class SyntheticFrameReader(FrameReader):
    """Yields *num_frames* dummy frames, then returns ``None``."""

    def __init__(
        self,
        num_frames: int = 5,
        resolution: tuple[int, int] = (640, 480),
    ) -> None:
        self._limit = num_frames
        self._resolution = resolution
        self._count = 0
        self._is_open = False
        self._is_closed = False

    def open(self, source: str) -> None:  # noqa: ARG002
        self._is_open = True
        self._is_closed = False
        self._count = 0

    def read(self) -> object | None:
        if self._is_closed or self._count >= self._limit:
            return None
        self._count += 1
        return {"dummy": True}  # opaque frame data

    def close(self) -> None:
        self._is_closed = True

    @property
    def closed(self) -> bool:
        return self._is_closed

    @property
    def resolution(self) -> tuple[int, int] | None:
        return self._resolution


class FailingFrameReader(FrameReader):
    """Raises during ``open`` to simulate a missing/corrupt file."""

    def open(self, source: str) -> None:  # noqa: ARG002
        msg = f"Could not open source: {source}"
        raise FileNotFoundError(msg)

    def read(self) -> None:
        return None

    def close(self) -> None:
        pass

    @property
    def closed(self) -> bool:
        return False

    @property
    def resolution(self) -> tuple[int, int] | None:
        return None


def collect_events(
    bus: LocalEventBus, event_type: str
) -> list[Event]:
    """Subscribe to *event_type* on *bus* and return the capture list."""
    results: list[Event] = []
    bus.subscribe(event_type, results.append)
    return results


# ---------------------------------------------------------------------------
# Test FrameMetadata
# ---------------------------------------------------------------------------

class TestFrameMetadata:
    def test_default_fields(self) -> None:
        meta = FrameMetadata(frame_id=0, stream_id="test")
        assert meta.frame_id == 0
        assert meta.stream_id == "test"
        assert meta.timestamp == 0.0
        assert meta.frame_ref == ""
        assert meta.resolution is None
        assert meta.preprocessors_applied == ()

    def test_to_payload_omits_frame_data(self) -> None:
        meta = FrameMetadata(
            frame_id=0,
            stream_id="file_01",
            timestamp=1000.0,
            frame_ref="mem://file_01/0",
            resolution=(640, 480),
            preprocessors_applied=(),
        )
        payload = meta.to_payload()

        assert payload["frame_ref"] == "mem://file_01/0"
        assert payload["timestamp"] == 1000.0
        assert payload["resolution"] == [640, 480]
        assert payload["preprocessors_applied"] == []

        # No raw frame data leaks into the payload
        assert "raw" not in payload
        assert "data" not in payload
        assert all(not isinstance(v, dict) for v in payload.values())

    def test_to_payload_no_resolution(self) -> None:
        meta = FrameMetadata(frame_id=0, stream_id="s")
        payload = meta.to_payload()
        assert payload["resolution"] is None

    def test_new_frame_event_type(self) -> None:
        assert FrameMetadata.NEW_FRAME == "NEW_FRAME"


# ---------------------------------------------------------------------------
# Test BaseStreamSource (via concrete subclass)
# ---------------------------------------------------------------------------

class TestBaseStreamSource:
    def test_read_next_abstract(self) -> None:
        with pytest.raises(TypeError):
            BaseStreamSource()  # type: ignore[abstract]

    def test_publish_next_uses_correct_event(self) -> None:
        reader = SyntheticFrameReader(num_frames=3)
        source = FileStream(stream_id="test", source_path="dummy", reader=reader)
        bus = LocalEventBus()
        captured = collect_events(bus, "NEW_FRAME")

        meta = source.publish_next(bus)
        assert meta is not None
        assert meta.frame_id == 0
        assert meta.stream_id == "test"

        assert len(captured) == 1
        event = captured[0]
        assert event.event_type == "NEW_FRAME"
        assert event.stream_id == "test"
        assert event.frame_id == 0

    def test_publish_next_returns_none_when_exhausted(self) -> None:
        reader = SyntheticFrameReader(num_frames=2)
        source = FileStream(stream_id="ex", source_path="x", reader=reader)
        bus = LocalEventBus()

        assert source.publish_next(bus) is not None
        assert source.publish_next(bus) is not None
        assert source.publish_next(bus) is None


# ---------------------------------------------------------------------------
# Test FileStream
# ---------------------------------------------------------------------------

class TestFileStream:
    def test_init_opens_reader(self) -> None:
        reader = SyntheticFrameReader(num_frames=3)
        source = FileStream(stream_id="f1", source_path="dummy", reader=reader)
        assert source.stream_id == "f1"
        assert source.source_path == "dummy"
        assert source.frame_count == 0

    def test_read_next_returns_metadata(self) -> None:
        reader = SyntheticFrameReader(num_frames=1, resolution=(320, 240))
        source = FileStream(stream_id="f", source_path="x", reader=reader)
        meta = source.read_next()

        assert meta is not None
        assert meta.frame_id == 0
        assert meta.stream_id == "f"
        assert meta.resolution == (320, 240)
        assert meta.frame_ref == "mem://f/0"
        assert isinstance(meta.timestamp, float)
        assert meta.timestamp > 0

    def test_read_next_monotonic_frame_ids(self) -> None:
        reader = SyntheticFrameReader(num_frames=3)
        source = FileStream(stream_id="f", source_path="x", reader=reader)

        ids = []
        while (meta := source.read_next()) is not None:
            ids.append(meta.frame_id)
        assert ids == [0, 1, 2]

    def test_read_next_returns_none_at_end(self) -> None:
        reader = SyntheticFrameReader(num_frames=0)
        source = FileStream(stream_id="f", source_path="x", reader=reader)
        assert source.read_next() is None

    def test_read_next_returns_none_after_exhaustion(self) -> None:
        reader = SyntheticFrameReader(num_frames=1)
        source = FileStream(stream_id="f", source_path="x", reader=reader)
        assert source.read_next() is not None
        assert source.read_next() is None
        assert source.read_next() is None  # still None

    def test_missing_file_raises_on_init(self) -> None:
        reader = FailingFrameReader()
        with pytest.raises(FileNotFoundError, match="missing_video"):
            FileStream(stream_id="f", source_path="missing_video.mp4", reader=reader)

    def test_close_releases_resources(self) -> None:
        reader = SyntheticFrameReader(num_frames=3)
        source = FileStream(stream_id="f", source_path="x", reader=reader)
        source.read_next()
        assert source.frame_count == 1
        source.close()
        # After close, reader is closed
        assert reader.closed
        # Cache is empty
        assert source.read_next() is None

    def test_publishes_new_frame_events(self) -> None:
        reader = SyntheticFrameReader(num_frames=3, resolution=(640, 480))
        source = FileStream(stream_id="file_01", source_path="test.mp4", reader=reader)
        bus = LocalEventBus()
        captured: list[Event] = []
        bus.subscribe("NEW_FRAME", captured.append)

        for _ in range(3):
            source.publish_next(bus)

        assert len(captured) == 3
        for i, event in enumerate(captured):
            assert event.event_type == "NEW_FRAME"
            assert event.stream_id == "file_01"
            assert event.frame_id == i
            assert event.payload["frame_ref"] == f"mem://file_01/{i}"
            assert event.payload["resolution"] == [640, 480]
            assert event.payload["preprocessors_applied"] == []

    def test_raw_frame_not_in_event_payload(self) -> None:
        """Verify the EventBus never receives pixel data."""
        reader = SyntheticFrameReader(num_frames=2)
        source = FileStream(stream_id="safe", source_path="x", reader=reader)
        bus = LocalEventBus()
        captured: list[Event] = []
        bus.subscribe("NEW_FRAME", captured.append)

        for _ in range(2):
            source.publish_next(bus)

        for event in captured:
            payload_keys = set(event.payload)
            # These are the ONLY keys the payload should contain
            assert payload_keys == {"frame_ref", "timestamp", "resolution", "preprocessors_applied"}
            # None of the payload values should be a dict (raw frame)
            for v in event.payload.values():
                assert not isinstance(v, (dict, list)) or isinstance(v, list)

    def test_end_of_stream_does_not_publish(self) -> None:
        reader = SyntheticFrameReader(num_frames=0)
        source = FileStream(stream_id="empty", source_path="x", reader=reader)
        bus = LocalEventBus()
        captured: list[Event] = []
        bus.subscribe("NEW_FRAME", captured.append)

        result = source.publish_next(bus)
        assert result is None
        assert len(captured) == 0

    def test_publish_after_exhaustion(self) -> None:
        reader = SyntheticFrameReader(num_frames=1)
        source = FileStream(stream_id="f", source_path="x", reader=reader)
        bus = LocalEventBus()
        captured: list[Event] = []
        bus.subscribe("NEW_FRAME", captured.append)

        assert source.publish_next(bus) is not None
        assert source.publish_next(bus) is None
        assert len(captured) == 1  # only the valid frame
        assert source.publish_next(bus) is None
        assert len(captured) == 1  # no extra event

    def test_frame_count_tracks_reads(self) -> None:
        reader = SyntheticFrameReader(num_frames=5)
        source = FileStream(stream_id="f", source_path="x", reader=reader)
        assert source.frame_count == 0
        source.read_next()
        assert source.frame_count == 1
        source.read_next()
        assert source.frame_count == 2
