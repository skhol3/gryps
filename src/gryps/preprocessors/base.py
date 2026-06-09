from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BasePreprocessorPlugin(ABC):
    """Abstract base for frame preprocessing plugins.

    Preprocessors transform an in-memory frame before detection. They must not
    publish frame payloads to the EventBus; callers decide how processed frames
    are stored and referenced.
    """

    @abstractmethod
    def process(self, frame: object, metadata: dict[str, Any]) -> tuple[object, dict[str, Any]]:
        """Return the transformed frame and enriched metadata."""

    @property
    @abstractmethod
    def modifies_geometry(self) -> bool:
        """Whether this preprocessor changes the frame coordinate space."""
