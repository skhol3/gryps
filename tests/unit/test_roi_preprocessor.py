from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from gryps.core import ConfigError, PluginRegistry
from gryps.preprocessors import BasePreprocessorPlugin
from gryps.preprocessors.roi.static import ROIStatic
from gryps.utils.roi import MISSING_ROI_CONFIG_MESSAGE, ROI, crop_frame, load_roi, validate_roi


def write_roi(path: Path, content: str = "x: 1\ny: 1\nwidth: 2\nheight: 2\n") -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class NumpyStyleFrame:
    def __init__(self) -> None:
        self.index: Any = None

    def __getitem__(self, index: Any) -> str:
        self.index = index
        return "cropped"


class TestBasePreprocessorPlugin:
    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            BasePreprocessorPlugin()  # type: ignore[abstract]


class TestROIConfig:
    def test_missing_roi_yaml_raises_clear_hu_002_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match=MISSING_ROI_CONFIG_MESSAGE):
            load_roi(tmp_path / "roi.yaml")

    def test_loads_flat_roi_yaml(self, tmp_path: Path) -> None:
        path = write_roi(tmp_path / "roi.yaml")

        assert load_roi(path) == ROI(x=1, y=1, width=2, height=2)

    def test_loads_nested_roi_yaml(self, tmp_path: Path) -> None:
        path = write_roi(
            tmp_path / "roi.yaml",
            "roi:\n  x: 3\n  y: 4\n  width: 5\n  height: 6\n",
        )

        assert load_roi(path) == ROI(x=3, y=4, width=5, height=6)

    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(ConfigError, match="width"):
            validate_roi({"x": 0, "y": 0, "height": 10})

    @pytest.mark.parametrize(
        "data",
        [
            {"x": -1, "y": 0, "width": 10, "height": 10},
            {"x": 0, "y": -1, "width": 10, "height": 10},
            {"x": 0, "y": 0, "width": 0, "height": 10},
            {"x": 0, "y": 0, "width": 10, "height": 0},
        ],
    )
    def test_rejects_invalid_bounds(self, data: dict[str, int]) -> None:
        with pytest.raises(ConfigError):
            validate_roi(data)


class TestROICropping:
    def test_crops_list_frame(self) -> None:
        frame = [
            [1, 2, 3, 4],
            [5, 6, 7, 8],
            [9, 10, 11, 12],
        ]

        assert crop_frame(frame, ROI(x=1, y=1, width=2, height=2)) == [[6, 7], [10, 11]]

    def test_uses_numpy_style_two_axis_slicing_when_available(self) -> None:
        frame = NumpyStyleFrame()

        assert crop_frame(frame, ROI(x=2, y=3, width=4, height=5)) == "cropped"
        assert frame.index == (slice(3, 8), slice(2, 6))

    @pytest.mark.parametrize(
        "roi",
        [
            ROI(x=5, y=0, width=2, height=1),
            ROI(x=0, y=5, width=1, height=1),
            ROI(x=1, y=0, width=2, height=1),
            ROI(x=0, y=1, width=1, height=2),
        ],
    )
    def test_rejects_roi_outside_frame_bounds(self, roi: ROI) -> None:
        frame = [[1, 2], [3, 4]]

        with pytest.raises(ConfigError, match="roi.yaml bounds exceed frame dimensions"):
            crop_frame(frame, roi)


class TestROIStatic:
    def test_process_crops_frame_and_enriches_metadata(self, tmp_path: Path) -> None:
        path = write_roi(tmp_path / "roi.yaml")
        plugin = ROIStatic(config_path=path)
        metadata = {"frame_ref": "mem://file/0", "preprocessors_applied": ("existing",)}
        frame = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

        cropped, next_metadata = plugin.process(frame, metadata)

        assert cropped == [[5, 6], [8, 9]]
        assert next_metadata["frame_ref"] == "mem://file/0"
        assert next_metadata["preprocessors_applied"] == ("existing", "roi_static")
        assert next_metadata["roi_applied"] == [1, 1, 2, 2]
        assert "roi_applied" not in metadata

    def test_process_does_not_enrich_metadata_when_crop_fails(self, tmp_path: Path) -> None:
        path = write_roi(tmp_path / "roi.yaml", "x: 1\ny: 1\nwidth: 3\nheight: 3\n")
        plugin = ROIStatic(config_path=path)
        metadata = {"frame_ref": "mem://file/0", "preprocessors_applied": ("existing",)}
        frame = [[1, 2], [3, 4]]

        with pytest.raises(ConfigError, match="roi.yaml bounds exceed frame dimensions"):
            plugin.process(frame, metadata)

        assert metadata == {"frame_ref": "mem://file/0", "preprocessors_applied": ("existing",)}

    def test_modifies_geometry(self, tmp_path: Path) -> None:
        plugin = ROIStatic(config_path=write_roi(tmp_path / "roi.yaml"))

        assert plugin.modifies_geometry is True

    def test_manifest_is_discoverable(self) -> None:
        root = Path(__file__).parents[2] / "src" / "gryps" / "preprocessors" / "roi"
        registry = PluginRegistry(roots=[root])

        plugins = registry.discover()

        loaded_class = plugins["roi_static"].loaded_class
        assert loaded_class is not None
        assert loaded_class.__name__ == "ROIStatic"
        assert issubclass(loaded_class, BasePreprocessorPlugin)
