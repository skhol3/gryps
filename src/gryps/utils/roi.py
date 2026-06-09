from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gryps.core import ConfigError

MISSING_ROI_CONFIG_MESSAGE = "Falta roi.yaml. Ejecute gryps.tools.calibrate en su PC."


@dataclass(frozen=True)
class ROI:
    """Rectangular region of interest."""

    x: int
    y: int
    width: int
    height: int

    def as_list(self) -> list[int]:
        return [self.x, self.y, self.width, self.height]


def load_roi(path: str | Path = "config/roi.yaml") -> ROI:
    """Load and validate a static ROI from a minimal YAML file."""
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(MISSING_ROI_CONFIG_MESSAGE)

    data = _parse_roi_yaml(config_path)
    roi_data = data.get("roi", data)
    if not isinstance(roi_data, dict):
        raise ConfigError("roi.yaml field 'roi' must be a mapping")
    return validate_roi(roi_data)


def validate_roi(data: dict[str, Any]) -> ROI:
    """Validate ROI values and return a typed ROI object."""
    missing = [key for key in ("x", "y", "width", "height") if key not in data]
    if missing:
        raise ConfigError(f"roi.yaml missing required field(s): {', '.join(missing)}")

    values: dict[str, int] = {}
    for key in ("x", "y", "width", "height"):
        value = data[key]
        if not isinstance(value, int):
            raise ConfigError(f"roi.yaml field '{key}' must be an integer")
        values[key] = value

    roi = ROI(**values)
    if roi.x < 0 or roi.y < 0:
        raise ConfigError("roi.yaml fields 'x' and 'y' must be non-negative")
    if roi.width <= 0 or roi.height <= 0:
        raise ConfigError("roi.yaml fields 'width' and 'height' must be positive")
    return roi


def crop_frame(frame: object, roi: ROI) -> object:
    """Crop *frame* to *roi* using NumPy-style or list-style slicing."""
    dimensions = _frame_dimensions(frame)
    if dimensions is not None:
        frame_height, frame_width = dimensions
        if roi.x + roi.width > frame_width or roi.y + roi.height > frame_height:
            raise ConfigError(
                "roi.yaml bounds exceed frame dimensions "
                f"({frame_width}x{frame_height}): "
                f"x={roi.x}, y={roi.y}, width={roi.width}, height={roi.height}"
            )

    y_slice = slice(roi.y, roi.y + roi.height)
    x_slice = slice(roi.x, roi.x + roi.width)

    try:
        return frame[y_slice, x_slice]  # type: ignore[index]
    except TypeError:
        rows = frame[y_slice]  # type: ignore[index]
        return [row[x_slice] for row in rows]


def _frame_dimensions(frame: object) -> tuple[int, int] | None:
    shape = getattr(frame, "shape", None)
    if isinstance(shape, tuple) and len(shape) >= 2:
        height, width = shape[:2]
        if isinstance(height, int) and isinstance(width, int):
            return height, width

    try:
        height = len(frame)  # type: ignore[arg-type]
    except TypeError:
        return None

    if height == 0:
        return 0, 0

    try:
        first_row = frame[0]  # type: ignore[index]
        width = len(first_row)
    except (IndexError, TypeError):
        return None
    return height, width


def _parse_roi_yaml(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    parents: list[tuple[int, dict[str, Any]]] = [(-1, result)]

    for raw_line in path.read_text("utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise ConfigError(f"Invalid roi.yaml line: {stripped}")

        indent = len(raw_line) - len(raw_line.lstrip())
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()

        while parents and indent <= parents[-1][0]:
            parents.pop()
        current = parents[-1][1]

        if raw_value:
            current[key] = _parse_scalar(raw_value)
        else:
            child: dict[str, Any] = {}
            current[key] = child
            parents.append((indent, child))

    return result


def _parse_scalar(value: str) -> Any:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value
