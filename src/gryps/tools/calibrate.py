from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gryps.core import ConfigError
from gryps.utils.roi import ROI, validate_roi

DEFAULT_OUTPUT_PATH = Path("config/roi.yaml")
WINDOW_NAME = "Gryps ROI Calibration"
OPENCV_REQUIRED_MESSAGE = (
    "La herramienta de calibracion requiere OpenCV. "
    "Instale opencv-python para generar roi.yaml."
)


class CalibrationError(Exception):
    """Raised when ROI calibration cannot complete."""


ROISelector = Callable[[Path], ROI]


def calibrate(image_path: Path, output_path: Path, selector: ROISelector | None = None) -> ROI:
    """Select a rectangular ROI from *image_path* and write it as ROI YAML."""
    if selector is None:
        selector = select_roi_with_opencv
    roi = selector(image_path)
    write_roi_yaml(output_path, roi)
    return roi


def select_roi_with_opencv(image_path: Path) -> ROI:
    """Load an image and select a rectangular ROI using OpenCV's GUI tools."""
    cv2 = _load_cv2()
    image = cv2.imread(str(image_path))
    if image is None:
        raise CalibrationError(f"No se pudo abrir la imagen: {image_path}")

    try:
        selected = cv2.selectROI(WINDOW_NAME, image, showCrosshair=True, fromCenter=False)
    finally:
        cv2.destroyAllWindows()

    try:
        x, y, width, height = (int(value) for value in selected)
    except (TypeError, ValueError) as exc:
        raise CalibrationError("OpenCV devolvio una ROI invalida.") from exc

    try:
        return validate_roi({"x": x, "y": y, "width": width, "height": height})
    except ConfigError as exc:
        raise CalibrationError("Seleccione una ROI con ancho y alto positivos.") from exc


def write_roi_yaml(path: Path, roi: ROI) -> None:
    """Write ROI values in the format accepted by gryps.utils.roi.load_roi."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "roi:\n"
        f"  x: {roi.x}\n"
        f"  y: {roi.y}\n"
        f"  width: {roi.width}\n"
        f"  height: {roi.height}\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera config/roi.yaml seleccionando una region rectangular.",
    )
    parser.add_argument("image", type=Path, help="Imagen de referencia para calibrar la ROI")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Ruta de salida para roi.yaml",
    )
    args = parser.parse_args(argv)

    try:
        roi = calibrate(args.image, args.output)
    except CalibrationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"ROI guardada en {args.output}: {roi.as_list()}")
    return 0


def _load_cv2(import_module: Callable[[str], Any] = importlib.import_module) -> Any:
    try:
        return import_module("cv2")
    except ImportError as exc:
        raise CalibrationError(OPENCV_REQUIRED_MESSAGE) from exc


if __name__ == "__main__":
    raise SystemExit(main())
