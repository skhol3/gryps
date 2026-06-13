from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from gryps.core import ConfigError
from gryps.plugins.ocr_backends.base import BaseOCRBackend, OCRResult

ReaderFactory = Callable[..., object]
ImportModule = Callable[[str], object]


class PaddleOCRBackend(BaseOCRBackend):
    """PaddleOCR adapter with runtime import and injectable reader factory."""

    name = "paddleocr"

    def __init__(
        self,
        *,
        reader_factory: ReaderFactory | None = None,
        import_module: ImportModule = importlib.import_module,
        **reader_options: Any,
    ) -> None:
        self._reader = self._create_reader(reader_factory, import_module, reader_options)

    def read_plate(self, crop: object) -> OCRResult:
        try:
            raw = self._reader.predict(crop)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 - backend failures become PLATE_READ errors.
            return OCRResult(error=str(exc))
        return _best_result(raw)

    @staticmethod
    def _create_reader(
        reader_factory: ReaderFactory | None,
        import_module: ImportModule,
        reader_options: Mapping[str, Any],
    ) -> object:
        factory = reader_factory
        if factory is None:
            try:
                module = import_module("paddleocr")
            except ModuleNotFoundError as exc:
                raise ConfigError(
                    "PaddleOCR backend requires the optional 'paddleocr' extra"
                ) from exc
            factory = module.PaddleOCR  # type: ignore[attr-defined]
        return factory(**dict(reader_options))


def _best_result(raw: object) -> OCRResult:
    candidates = list(_iter_text_confidence(raw))
    if not candidates:
        return OCRResult()
    text, confidence = max(candidates, key=lambda item: item[1] if item[1] is not None else -1.0)
    return OCRResult(text=text, confidence=confidence)


def _iter_text_confidence(raw: object) -> list[tuple[str, float | None]]:
    items: list[tuple[str, float | None]] = []
    if isinstance(raw, str):
        return [(raw, None)]

    prediction = _prediction_mapping(raw)
    if prediction is not None:
        items.extend(_iter_prediction_mapping(prediction))
        if items:
            return items

    if not isinstance(raw, Sequence) or isinstance(raw, bytes | bytearray):
        return items

    for value in raw:
        if isinstance(value, str):
            items.append((value, None))
        elif _looks_like_text_confidence(value):
            text, confidence = value
            items.append((text, float(confidence)))
        else:
            items.extend(_iter_text_confidence(value))
    return items


def _iter_prediction_mapping(raw: Mapping[str, Any]) -> list[tuple[str, float | None]]:
    nested = raw.get("res")
    if isinstance(nested, Mapping):
        nested_items = _iter_prediction_mapping(nested)
        if nested_items:
            return nested_items

    texts = _sequence(raw.get("rec_texts")) or _sequence(raw.get("texts"))
    scores = _sequence(raw.get("rec_scores")) or _sequence(raw.get("scores"))
    if texts is not None:
        return _pair_texts_scores(texts, scores)

    text = raw.get("rec_text") or raw.get("text")
    if isinstance(text, str):
        confidence = _float_or_none(
            raw.get("rec_score") or raw.get("confidence") or raw.get("score")
        )
        return [(text, confidence)]

    return []


def _prediction_mapping(raw: object) -> Mapping[str, Any] | None:
    if isinstance(raw, Mapping):
        return raw

    for method_name in ("to_dict", "json"):
        method = getattr(raw, method_name, None)
        if callable(method):
            value = method()
            if isinstance(value, Mapping):
                return value

    attrs = {
        key: getattr(raw, key)
        for key in ("res", "rec_texts", "rec_scores", "rec_text", "rec_score", "text", "confidence")
        if hasattr(raw, key)
    }
    return attrs or None


def _sequence(raw: object) -> Sequence[object] | None:
    if isinstance(raw, Sequence) and not isinstance(raw, str | bytes | bytearray):
        return raw
    return None


def _pair_texts_scores(
    texts: Sequence[object], scores: Sequence[object] | None
) -> list[tuple[str, float | None]]:
    items: list[tuple[str, float | None]] = []
    for index, text in enumerate(texts):
        if not isinstance(text, str):
            continue
        score = scores[index] if scores is not None and index < len(scores) else None
        items.append((text, _float_or_none(score)))
    return items


def _float_or_none(raw: object) -> float | None:
    if isinstance(raw, int | float):
        return float(raw)
    return None


def _looks_like_text_confidence(value: object) -> bool:
    return (
        isinstance(value, list | tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int | float)
    )
