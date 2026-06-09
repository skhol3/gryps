from __future__ import annotations

from pathlib import Path

from gryps.core import Event
from gryps.core.registry import PluginRegistry
from gryps.plugins.outputs.base import BaseOutputPlugin
from gryps.plugins.outputs.console_logger.output import ConsoleOutput

SRC = Path(__file__).parent.parent.parent / "src"

PLATE_READ_PAYLOAD: dict[str, object] = {
    "plate_text": "ABC123",
    "track_id": "t1",
    "confidence": 0.95,
    "best_frame_id": 42,
}


class TestConsoleOutput:
    def test_plate_read_prints_expected_line(self) -> None:
        lines: list[str] = []
        output = ConsoleOutput(writer=lines.append)

        event = Event.create(
            stream_id="cam_01",
            frame_id=42,
            event_type="PLATE_READ",
            payload=PLATE_READ_PAYLOAD,
        )
        output.handle(event)

        assert len(lines) == 1
        assert "[CONSOLE] PLATE_READ" in lines[0]
        assert "plate=ABC123" in lines[0]
        assert "track=t1" in lines[0]
        assert "stream=cam_01" in lines[0]
        assert "frame=42" in lines[0]

    def test_non_plate_event_prints_nothing(self) -> None:
        lines: list[str] = []
        output = ConsoleOutput(writer=lines.append)

        event = Event.create(
            stream_id="cam_01",
            frame_id=1,
            event_type="NEW_FRAME",
            payload={"frame_ref": "mem://test/0"},
        )
        output.handle(event)

        assert lines == []

    def test_default_writer_is_print(self) -> None:
        output = ConsoleOutput()
        assert output._writer is print

    def test_handle_accepts_any_event_without_error(self) -> None:
        output = ConsoleOutput(writer=lambda _: None)

        event = Event.create(stream_id="s", frame_id=0, event_type="UNKNOWN")
        output.handle(event)

    def test_console_output_is_base_output_plugin(self) -> None:
        assert issubclass(ConsoleOutput, BaseOutputPlugin)

    def test_payload_has_no_raw_frame_data(self) -> None:
        lines: list[str] = []
        output = ConsoleOutput(writer=lines.append)

        event = Event.create(
            stream_id="cam_01",
            frame_id=42,
            event_type="PLATE_READ",
            payload=PLATE_READ_PAYLOAD,
        )
        raw_keys = {"data", "frame", "image", "ndarray", "bytes", "raw"}
        assert raw_keys.isdisjoint(event.payload)

        output.handle(event)
        assert len(lines) == 1


class TestConsoleOutputPluginRegistry:
    def test_discoverable_by_registry(self) -> None:
        plugin_dir = SRC / "gryps" / "plugins" / "outputs" / "console_logger"

        reg = PluginRegistry(roots=[str(plugin_dir)])
        reg.discover()

        assert "console_logger" in reg.plugins
        info = reg.plugins["console_logger"]
        assert info.loaded_class is not None
        assert info.loaded_class.__name__ == "ConsoleOutput"
        loaded_instance = info.loaded_class()
        assert isinstance(loaded_instance, BaseOutputPlugin)
