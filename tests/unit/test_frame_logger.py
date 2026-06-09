from __future__ import annotations

from pathlib import Path

from gryps.core import Event
from gryps.core.registry import PluginRegistry
from gryps.plugins.outputs.base import BaseOutputPlugin
from gryps.plugins.outputs.frame_logger.output import FrameLogger

SRC = Path(__file__).parent.parent.parent / "src"


class TestFrameLogger:
    def test_new_frame_prints_expected_line(self) -> None:
        lines: list[str] = []
        logger = FrameLogger(writer=lines.append)

        event = Event.create(
            stream_id="file_01",
            frame_id=0,
            event_type="NEW_FRAME",
            payload={"frame_ref": "mem://file_01/0"},
        )
        logger.handle(event)

        assert len(lines) == 1
        assert "[CONSOLE] Frame 1 | Stream: file_01" in lines[0]

    def test_one_based_display(self) -> None:
        lines: list[str] = []
        logger = FrameLogger(writer=lines.append)

        for frame_id in range(3):
            event = Event.create(
                stream_id="cam_01",
                frame_id=frame_id,
                event_type="NEW_FRAME",
                payload={"frame_ref": f"mem://cam_01/{frame_id}"},
            )
            logger.handle(event)

        assert len(lines) == 3
        assert "[CONSOLE] Frame 1 | Stream: cam_01" in lines[0]
        assert "[CONSOLE] Frame 2 | Stream: cam_01" in lines[1]
        assert "[CONSOLE] Frame 3 | Stream: cam_01" in lines[2]

    def test_non_new_frame_event_prints_nothing(self) -> None:
        lines: list[str] = []
        logger = FrameLogger(writer=lines.append)

        event = Event.create(
            stream_id="cam_01",
            frame_id=1,
            event_type="PLATE_READ",
            payload={"plate_text": "ABC123"},
        )
        logger.handle(event)

        assert lines == []

    def test_handle_unknown_event_no_error(self) -> None:
        logger = FrameLogger(writer=lambda _: None)

        event = Event.create(stream_id="s", frame_id=0, event_type="UNKNOWN")
        logger.handle(event)

    def test_handle_system_alert_ignored(self) -> None:
        lines: list[str] = []
        logger = FrameLogger(writer=lines.append)

        event = Event.create(
            stream_id="s",
            frame_id=0,
            event_type="SYSTEM_ALERT",
            payload={"message": "test"},
        )
        logger.handle(event)

        assert lines == []

    def test_default_writer_is_print(self) -> None:
        logger = FrameLogger()
        assert logger._writer is print

    def test_is_base_output_plugin(self) -> None:
        assert issubclass(FrameLogger, BaseOutputPlugin)


class TestFrameLoggerPluginRegistry:
    def test_discoverable_by_registry(self) -> None:
        plugin_dir = SRC / "gryps" / "plugins" / "outputs" / "frame_logger"

        reg = PluginRegistry(roots=[str(plugin_dir)])
        reg.discover()

        assert "frame_logger" in reg.plugins
        info = reg.plugins["frame_logger"]
        assert info.loaded_class is not None
        assert info.loaded_class.__name__ == "FrameLogger"
        loaded_instance = info.loaded_class()
        assert isinstance(loaded_instance, BaseOutputPlugin)
