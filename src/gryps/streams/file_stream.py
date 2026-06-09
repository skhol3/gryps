from __future__ import annotations

import time

from gryps.streams.base import BaseStreamSource, FrameMetadata, FrameReader


class FileStream(BaseStreamSource):
    """Stream source that reads frames from a video file.

    The actual video decoding is delegated to an injected
    :class:`FrameReader` adapter, making this class testable
    without a real codec library.

    Frame data is stored in an internal cache keyed by
    ``mem://<stream_id>/<frame_id>`` URIs.  Only *references*
    (strings) travel through the EventBus — raw pixel arrays
    never leave this object.
    """

    def __init__(
        self,
        stream_id: str,
        source_path: str,
        reader: FrameReader,
    ) -> None:
        self._stream_id = stream_id
        self._source_path = source_path
        self._reader = reader
        self._frame_count = 0
        self._frame_cache: dict[str, object] = {}

        reader.open(source_path)

    # -- BaseStreamSource ---------------------------------------------------

    @property
    def stream_id(self) -> str:
        return self._stream_id

    @property
    def source_path(self) -> str:
        return self._source_path

    @property
    def frame_count(self) -> int:
        """Total frames read so far."""
        return self._frame_count

    def read_next(self) -> FrameMetadata | None:
        if self._reader.closed:
            return None

        raw = self._reader.read()
        if raw is None:
            self._reader.close()
            return None

        frame_id = self._frame_count
        self._frame_count += 1

        frame_ref = f"mem://{self._stream_id}/{frame_id}"
        self._frame_cache[frame_ref] = raw

        return FrameMetadata(
            frame_id=frame_id,
            stream_id=self._stream_id,
            timestamp=time.time(),
            frame_ref=frame_ref,
            resolution=self._reader.resolution,
        )

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        self._reader.close()
        self._frame_cache.clear()
