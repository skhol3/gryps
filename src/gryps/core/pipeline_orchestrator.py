from __future__ import annotations

from gryps.core.bus import EventBus, LocalEventBus
from gryps.core.registry import PluginRegistry


class PipelineState:
    STOPPED = "stopped"
    RUNNING = "running"


class PipelineOrchestrator:
    """Coordinates streams, preprocessors, bus, and plugins.

    Minimal MVP implementation: owns an EventBus (injected or default
    LocalEventBus) and optionally a PluginRegistry.  Lifecycle is
    idempotent: repeated ``start()`` / ``stop()`` calls are safe.

    Starting with zero streams and zero plugins must not fail.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        plugin_registry: PluginRegistry | None = None,
    ) -> None:
        self._event_bus = event_bus or LocalEventBus()
        self._plugin_registry = plugin_registry
        self._state = PipelineState.STOPPED

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def plugin_registry(self) -> PluginRegistry | None:
        return self._plugin_registry

    @property
    def is_running(self) -> bool:
        return self._state == PipelineState.RUNNING

    def start(self) -> None:
        if self._state == PipelineState.RUNNING:
            return
        self._state = PipelineState.RUNNING

    def stop(self) -> None:
        if self._state == PipelineState.STOPPED:
            return
        self._state = PipelineState.STOPPED
