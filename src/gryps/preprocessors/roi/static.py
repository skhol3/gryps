from __future__ import annotations

from pathlib import Path
from typing import Any

from gryps.preprocessors.base import BasePreprocessorPlugin
from gryps.utils.roi import ROI, crop_frame, load_roi


class ROIStatic(BasePreprocessorPlugin):
    """Static ROI crop loaded from ``config/roi.yaml`` by default."""

    name = "roi_static"

    def __init__(self, config_path: str | Path = "config/roi.yaml") -> None:
        self._roi = load_roi(config_path)

    @property
    def roi(self) -> ROI:
        return self._roi

    @property
    def modifies_geometry(self) -> bool:
        return True

    def process(self, frame: object, metadata: dict[str, Any]) -> tuple[object, dict[str, Any]]:
        cropped = crop_frame(frame, self._roi)
        next_metadata = dict(metadata)
        applied = tuple(next_metadata.get("preprocessors_applied", ()))
        next_metadata["preprocessors_applied"] = (*applied, self.name)
        next_metadata["roi_applied"] = self._roi.as_list()
        return cropped, next_metadata
