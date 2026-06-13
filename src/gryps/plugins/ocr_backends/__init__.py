from gryps.plugins.ocr_backends.base import BaseOCRBackend, OCRResult, PlateReadPayload
from gryps.plugins.ocr_backends.handler import OCRHandler
from gryps.plugins.ocr_backends.paddleocr_backend import PaddleOCRBackend
from gryps.plugins.ocr_backends.selector import create_ocr_backend

__all__ = [
    "BaseOCRBackend",
    "OCRHandler",
    "OCRResult",
    "PaddleOCRBackend",
    "PlateReadPayload",
    "create_ocr_backend",
]
