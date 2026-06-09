from __future__ import annotations

from gryps.core import (
    Event,
    EventBus,
    EventHandler,
    LocalEventBus,
    PipelineOrchestrator,
    PluginRegistry,
    Subscription,
)


class RecordingEventBus(EventBus):
    """Test double that records every published event.

    Unlike LocalEventBus, this does not filter by event_type —
    every ``publish`` call is captured, so a test using this
    double will fail if the SUT publishes any event, regardless
    of type.
    """

    def __init__(self) -> None:
        self.published: list[Event] = []

    def publish(self, event: Event) -> None:
        self.published.append(event)

    def subscribe(self, event_type: str, _handler: EventHandler) -> Subscription:
        return Subscription(event_type=event_type)

    def unsubscribe(self, sub: Subscription) -> None:
        pass


class TestPipelineOrchestratorInit:
    def test_default_bus_is_local_event_bus(self) -> None:
        orch = PipelineOrchestrator()
        assert isinstance(orch.event_bus, LocalEventBus)

    def test_injected_bus_is_used(self) -> None:
        bus = LocalEventBus()
        orch = PipelineOrchestrator(event_bus=bus)
        assert orch.event_bus is bus

    def test_plugin_registry_defaults_to_none(self) -> None:
        orch = PipelineOrchestrator()
        assert orch.plugin_registry is None

    def test_injected_plugin_registry(self) -> None:
        reg = PluginRegistry()
        orch = PipelineOrchestrator(plugin_registry=reg)
        assert orch.plugin_registry is reg

    def test_starts_stopped(self) -> None:
        orch = PipelineOrchestrator()
        assert not orch.is_running


class TestPipelineOrchestratorLifecycle:
    def test_start_with_zero_streams(self) -> None:
        orch = PipelineOrchestrator()
        orch.start()
        assert orch.is_running

    def test_stop_after_start(self) -> None:
        orch = PipelineOrchestrator()
        orch.start()
        orch.stop()
        assert not orch.is_running

    def test_start_is_idempotent(self) -> None:
        orch = PipelineOrchestrator()
        orch.start()
        orch.start()
        assert orch.is_running

    def test_stop_is_idempotent(self) -> None:
        orch = PipelineOrchestrator()
        orch.start()
        orch.stop()
        orch.stop()
        assert not orch.is_running

    def test_stop_when_stopped_does_not_raise(self) -> None:
        orch = PipelineOrchestrator()
        orch.stop()
        assert not orch.is_running

    def test_restart_cycle(self) -> None:
        orch = PipelineOrchestrator()
        orch.start()
        assert orch.is_running
        orch.stop()
        assert not orch.is_running
        orch.start()
        assert orch.is_running


class TestPipelineOrchestratorNoEventPublishing:
    def test_start_does_not_publish_events(self) -> None:
        bus = RecordingEventBus()
        orch = PipelineOrchestrator(event_bus=bus)
        orch.start()
        assert len(bus.published) == 0

    def test_stop_does_not_publish_events(self) -> None:
        bus = RecordingEventBus()
        orch = PipelineOrchestrator(event_bus=bus)
        orch.start()
        orch.stop()
        assert len(bus.published) == 0
