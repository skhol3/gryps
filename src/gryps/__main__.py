"""CLI entrypoint for Gryps.

Usage
-----
::

    gryps --file <path>

Orchestrates the core infrastructure (EventBus + FileStream + FrameLogger)
so that ``NEW_FRAME`` events from a video file are printed to the console.

This is the first end-to-end smoke path — it proves that streams, bus,
and output plugins are wired correctly.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from gryps.core import LocalEventBus
from gryps.plugins.outputs.frame_logger.output import FrameLogger
from gryps.streams import FileStream


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gryps — Video Analytics Microkernel",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to a video file to process",
    )
    args = parser.parse_args()

    if args.file:
        _run_file_cli(args.file)
    else:
        from gryps import __version__

        print(f"gryps v{__version__}")
        parser.print_usage()


def _run_file_cli(path: str) -> None:
    """CLI path: build a FileStream for *path* and process all frames.

    Exits with code 1 if the stream cannot be opened (e.g. missing
    OpenCV dependency).
    """
    stream = _open_file(path)
    if stream is None:
        sys.exit(1)
    try:
        run_file(stream)
    finally:
        stream.close()


def _open_file(path: str) -> FileStream | None:
    """Attempt to build a FileStream with an OpenCV reader.

    Returns *None* and prints a diagnostic when OpenCV is not installed.
    """
    try:
        from gryps.streams.readers.opencv_reader import OpenCVFrameReader

        reader = OpenCVFrameReader()
        return FileStream(stream_id="file_01", source_path=path, reader=reader)
    except ImportError:
        print(
            "OpenCV is not available. Install opencv-python to process video files.",
            file=sys.stderr,
        )
        return None


def run_file(stream: FileStream, writer: Callable[[str], None] | None = None) -> None:
    """Wire *stream* through EventBus to FrameLogger and process all frames.

    This is the public wiring function that tests can call directly with
    a synthetic stream and a captured writer — no subprocess needed.
    """
    bus = LocalEventBus()
    logger = FrameLogger(writer=writer)
    bus.subscribe("NEW_FRAME", logger.handle)

    while stream.publish_next(bus) is not None:
        pass


if __name__ == "__main__":
    main()
