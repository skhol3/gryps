from __future__ import annotations

from gryps.core import FrameStore
from gryps.streams import FileStream

from .test_streams import SyntheticFrameReader


class TestRunFile:
    def test_run_file_processes_all_frames(self) -> None:
        reader = SyntheticFrameReader(num_frames=3)
        stream = FileStream(
            stream_id="test", source_path="dummy", reader=reader, frame_store=FrameStore(),
        )
        lines: list[str] = []

        from gryps.__main__ import run_file

        run_file(stream, writer=lines.append)

        assert len(lines) == 3
        assert "[CONSOLE] Frame 1 | Stream: test" in lines[0]
        assert "[CONSOLE] Frame 2 | Stream: test" in lines[1]
        assert "[CONSOLE] Frame 3 | Stream: test" in lines[2]

    def test_run_file_empty_stream_prints_nothing(self) -> None:
        reader = SyntheticFrameReader(num_frames=0)
        stream = FileStream(
            stream_id="empty", source_path="dummy", reader=reader, frame_store=FrameStore(),
        )
        lines: list[str] = []

        from gryps.__main__ import run_file

        run_file(stream, writer=lines.append)

        assert lines == []

    def test_run_file_closes_stream(self) -> None:
        reader = SyntheticFrameReader(num_frames=2)
        stream = FileStream(
            stream_id="close", source_path="dummy", reader=reader, frame_store=FrameStore(),
        )

        from gryps.__main__ import run_file

        run_file(stream, writer=lambda _: None)

        assert reader.closed

    def test_run_file_single_frame(self) -> None:
        reader = SyntheticFrameReader(num_frames=1)
        stream = FileStream(
            stream_id="single", source_path="dummy", reader=reader, frame_store=FrameStore(),
        )
        lines: list[str] = []

        from gryps.__main__ import run_file

        run_file(stream, writer=lines.append)

        assert len(lines) == 1
        assert "Frame 1" in lines[0]
        assert "Stream: single" in lines[0]
