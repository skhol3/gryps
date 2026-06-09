from __future__ import annotations

from collections.abc import Callable

from gryps.core import Event
from gryps.plugins.outputs.base import BaseOutputPlugin


class FrameLogger(BaseOutputPlugin):
    """Prints ``NEW_FRAME`` events to the console in a stable format.

    Frame numbers are 1-based for display.  Ignores other event types
    silently.  The writer is injectable for testing without stdout
    capture.
    """

    def __init__(self, writer: Callable[[str], None] | None = None) -> None:
        self._writer = writer or print

    def handle(self, event: Event) -> None:
        if event.event_type != "NEW_FRAME":
            return
        self._writer(
            f"[CONSOLE] Frame {event.frame_id + 1} | Stream: {event.stream_id}",
        )
