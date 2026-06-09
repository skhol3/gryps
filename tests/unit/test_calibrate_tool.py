from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from gryps.tools import calibrate
from gryps.utils.roi import ROI, load_roi


def fake_cv2(
    image: object | None = object(),
    selection: tuple[int, int, int, int] = (1, 2, 3, 4),
) -> tuple[SimpleNamespace, dict[str, Any]]:
    state: dict[str, Any] = {"destroyed": False}

    def imread(path: str) -> object | None:
        state["path"] = path
        return image

    def select_roi(*_args: Any, **_kwargs: Any) -> tuple[int, int, int, int]:
        return selection

    def destroy_all_windows() -> None:
        state["destroyed"] = True

    return SimpleNamespace(
        imread=imread,
        selectROI=select_roi,
        destroyAllWindows=destroy_all_windows,
    ), state


def test_calibrate_writes_yaml_accepted_by_runtime_loader(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.jpg"
    output_path = tmp_path / "config" / "roi.yaml"

    roi = calibrate.calibrate(
        image_path,
        output_path,
        selector=lambda _: ROI(x=10, y=20, width=30, height=40),
    )

    assert roi == ROI(x=10, y=20, width=30, height=40)
    assert load_roi(output_path) == roi
    assert output_path.read_text(encoding="utf-8") == (
        "roi:\n"
        "  x: 10\n"
        "  y: 20\n"
        "  width: 30\n"
        "  height: 40\n"
    )


def test_select_roi_with_opencv_imports_cv2_lazily(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cv2, state = fake_cv2(selection=(5, 6, 7, 8))
    monkeypatch.setattr(calibrate, "_load_cv2", lambda: cv2)

    roi = calibrate.select_roi_with_opencv(tmp_path / "frame.jpg")

    assert roi == ROI(x=5, y=6, width=7, height=8)
    assert state["destroyed"] is True


def test_load_cv2_reports_missing_opencv() -> None:
    def missing_cv2(_name: str) -> object:
        raise ImportError("No module named cv2")

    with pytest.raises(calibrate.CalibrationError, match="requiere OpenCV"):
        calibrate._load_cv2(missing_cv2)


def test_select_roi_with_opencv_cleans_up_window_when_selection_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cv2, state = fake_cv2(selection=(0, 0, 0, 10))
    monkeypatch.setattr(calibrate, "_load_cv2", lambda: cv2)

    with pytest.raises(calibrate.CalibrationError, match="ancho y alto positivos"):
        calibrate.select_roi_with_opencv(tmp_path / "frame.jpg")

    assert state["destroyed"] is True


def test_main_returns_failure_for_calibration_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        calibrate,
        "calibrate",
        lambda *_args: (_ for _ in ()).throw(calibrate.CalibrationError("fallo claro")),
    )

    exit_code = calibrate.main(["frame.jpg"])

    assert exit_code == 1
    assert "fallo claro" in capsys.readouterr().err


def test_main_prints_saved_roi(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_calibrate(image_path: Path, output_path: Path) -> ROI:
        assert image_path == Path("frame.jpg")
        assert output_path == Path("custom.yaml")
        return ROI(x=1, y=2, width=3, height=4)

    monkeypatch.setattr(calibrate, "calibrate", fake_calibrate)

    exit_code = calibrate.main(["frame.jpg", "--output", "custom.yaml"])

    assert exit_code == 0
    assert "ROI guardada en custom.yaml: [1, 2, 3, 4]" in capsys.readouterr().out


def test_calibrate_module_does_not_import_cv2_at_import_time() -> None:
    assert "cv2" not in calibrate.__dict__
