from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from gryps.core import ConfigError
from gryps.plugins.ocr_backends.base import BaseOCRBackend
from gryps.plugins.ocr_backends.paddleocr_backend import PaddleOCRBackend

BackendFactory = Callable[[Mapping[str, Any]], BaseOCRBackend]


def create_ocr_backend(
    config: Mapping[str, Any],
    *,
    factories: Mapping[str, BackendFactory] | None = None,
) -> BaseOCRBackend:
    """Create the configured OCR backend and fail fast on unknown names."""
    registry = dict(factories or {"paddleocr": _create_paddleocr_backend})
    ocr_config = _ocr_config(config)
    backend_name = _backend_name(ocr_config.get("backend", "paddleocr"))

    factory = registry.get(backend_name)
    if factory is None:
        valid = ", ".join(sorted(registry))
        raise ConfigError(f"Unknown OCR backend '{backend_name}'. Valid options: {valid}")

    backend_config = ocr_config.get(backend_name, {})
    if not isinstance(backend_config, Mapping):
        raise ConfigError(f"OCR backend '{backend_name}' configuration must be a mapping")
    return factory(backend_config)


def _create_paddleocr_backend(config: Mapping[str, Any]) -> BaseOCRBackend:
    return PaddleOCRBackend(**dict(config))


def _ocr_config(config: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = config.get("ocr", config)
    if not isinstance(raw, Mapping):
        raise ConfigError("OCR configuration must be a mapping")
    return raw


def _backend_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("OCR backend name must be a non-empty string")
    return value.strip().lower()
