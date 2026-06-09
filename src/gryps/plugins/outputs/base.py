from __future__ import annotations

from abc import ABC, abstractmethod

from gryps.core import Event


class BaseOutputPlugin(ABC):
    """Abstract base for all output plugins.

    Output plugins are terminal consumers in the event pipeline — they
    receive events (typically ``PLATE_READ`` or ``SYSTEM_ALERT``) and
    persist, display, or forward them somewhere outside the bus.
    """

    @abstractmethod
    def handle(self, event: Event) -> None:
        """Process an output event.

        Implementations should be resilient: catch exceptions rather than
        letting them propagate, since output failures should not crash
        the pipeline.
        """
