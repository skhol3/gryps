from __future__ import annotations

from collections.abc import Callable

from gryps.core import Event
from gryps.plugins.outputs.base import BaseOutputPlugin


class ConsoleOutput(BaseOutputPlugin):
    """Prints ``PLATE_READ`` events to the console in a stable format.

    Ignores all other event types silently, making it safe to wire into
    any pipeline without unwanted output.

    The default writer is ``print``.  Inject an alternative writer (e.g.
    ``list.append``) in tests to capture output without parsing stdout.
    """

    def __init__(self, writer: Callable[[str], None] | None = None) -> None:
        self._writer = writer or print

    def handle(self, event: Event) -> None:
        if event.event_type != "PLATE_READ":
            return

        plate = event.payload.get("plate_text", "?")
        track = event.payload.get("track_id", "?")
        conf = event.payload.get("confidence", "?")
        self._writer(
            f"[CONSOLE] PLATE_READ stream={event.stream_id} "
            f"frame={event.frame_id} plate={plate} "
            f"track={track} conf={conf}"
        )
