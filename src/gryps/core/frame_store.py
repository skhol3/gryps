from __future__ import annotations


class FrameStore:
    """Associates frame references with their raw frame data.

    Stream sources write frames into this store when they read new
    frames.  Detectors (or other consumers) look up frames by their
    opaque ``frame_ref`` URI to run inference without the raw data
    ever traveling through the EventBus.
    """

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def store(self, ref: str, frame: object) -> None:
        """Associate *frame* with the given *ref*.

        If *ref* already exists the old frame is replaced.
        """
        self._store[ref] = frame

    def get(self, ref: str) -> object | None:
        """Return the frame associated with *ref*, or ``None``."""
        return self._store.get(ref)

    def clear(self) -> None:
        """Remove all stored frames."""
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
