# Design: Slice 1.3 — Plate Detector + OCR Backends

## Technical Approach

Mirror the existing `vehicle_yolo` boundary: handlers own EventBus wiring, plugins/adapters are injected and testable without heavy dependencies, and media stays in `FrameStore` behind opaque refs. `PlateDetectorHandler` subscribes to `VEHICLE_DETECTED`, resolves `frame_ref`, stores a plate crop ref, and emits `PLATE_CROPPED`. `OCRHandler` subscribes to `PLATE_CROPPED`, resolves the crop, invokes the selected OCR backend, normalizes output, updates optional `PlateTracker` OCR state, and emits `PLATE_READ`.

## Architecture Decisions

| Option | Tradeoff | Decision |
|---|---|---|
| Extend `PlateTracker` to crop plates | Centralizes track state but violates ownership and couples image processing to lifecycle state. | Reject. `PlateDetector` owns bbox/crop production; tracker is OCR state/cache only. |
| Put crop bytes on EventBus | Easier handler wiring but breaks existing serializable-event convention. | Reject. Payloads carry `frame_ref`/`crop_ref` only. |
| Hard-code PaddleOCR | Faster first path but blocks HU-012 backend selection. | Reject. Use backend contract + selector; PaddleOCR is first concrete adapter. |
| Require PaddleOCR in CI | Proves real OCR but adds heavy runtime/download risk. | Reject. Make it optional and test selector/normalization with fakes. |

## Data Flow

```text
NEW_FRAME -> VehicleDetectorHandler -> VEHICLE_DETECTED {frame_ref, bbox, track_id}
                                      -> PlateDetectorHandler
FrameStore frame_ref --------------------^   |
                                             v
FrameStore crop_ref <- crop object <- PLATE_CROPPED {crop_ref, plate_bbox, ...}
                                             |
                                             v
OCRHandler -> OCRBackendSelector -> PaddleOCRBackend -> PLATE_READ {plate_text/status}
                      |
                      `-> optional PlateTracker.ocr_enqueue/ocr_resolve
```

`VehicleDetectorHandler` must add the source `frame_ref` to `VEHICLE_DETECTED`; current payloads expose bbox/class/confidence/track only.

## File Changes

| File | Action | Description |
|---|---|---|
| `src/gryps/plugins/detectors/vehicle_yolo/handler.py` | Modify | Include `frame_ref` in `VEHICLE_DETECTED` payload. |
| `src/gryps/plugins/detectors/plate_detector/plugin.py` | Create | `PlateDetectorPlugin` with injected plate locator/cropper; returns plate detections/crops. |
| `src/gryps/plugins/detectors/plate_detector/handler.py` | Create | Subscribes to `VEHICLE_DETECTED`, stores crops in `FrameStore`, emits `PLATE_CROPPED`. |
| `src/gryps/plugins/detectors/plate_detector/plugin.yaml` | Create | Registry manifest. |
| `src/gryps/plugins/ocr_backends/base.py` | Create | `BaseOCRBackend`, `OCRResult`, text normalization helper. |
| `src/gryps/plugins/ocr_backends/selector.py` | Create | Config validation and backend factory; unknown names raise `ConfigError` with valid options. |
| `src/gryps/plugins/ocr_backends/paddleocr_backend.py` | Create | Optional PaddleOCR adapter with runtime import. |
| `src/gryps/plugins/ocr_backends/handler.py` | Create | Consumes `PLATE_CROPPED`, publishes `PLATE_READ`, optionally updates `PlateTracker`. |
| `tests/unit/test_plate_detector_handler.py` | Create | Crop refs, no-plate path, no raw payloads. |
| `tests/unit/test_ocr_backends.py` | Create | Selector, normalization, fake backend, PaddleOCR optional import behavior. |
| `pyproject.toml` | Modify | Add optional `paddleocr` extra only; keep base/dev install light. |

## Interfaces / Contracts

```python
plate_cropped = {
    "track_id": str | int | None,
    "frame_ref": str,
    "crop_ref": str,
    "vehicle_bbox": list[float],
    "plate_bbox": list[float],
    "confidence": float | None,
}

plate_read = {
    "track_id": str | int | None,
    "frame_ref": str,
    "crop_ref": str,
    "plate_text": str | None,
    "confidence": float | None,
    "status": "read" | "no_read" | "error",
    "error": str | None,
    "ocr_backend": str,
}

config = {"ocr": {"backend": "paddleocr", "paddleocr": {"lang": "en"}}}
```

`FrameStore` remains the reusable media store: full frames and crops are stored as objects under refs such as `mem://cam_01/7` and `mem://cam_01/7/plate/t1`. No EventBus payload may contain keys like `frame`, `image`, `bytes`, `raw`, or ndarray objects.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | `PLATE_CROPPED` payloads and crop storage | Fake plate detector/crop object + `LocalEventBus`. |
| Unit | OCR selector and unknown-backend validation | Assert `ConfigError` lists `paddleocr`. |
| Unit | OCR success/no-read/error normalization | Fake backend returning `OCRResult`; no PaddleOCR import. |
| Integration | Event chain shape | Minimal bus test from `VEHICLE_DETECTED` to `PLATE_READ`. |

## Migration / Rollout

No data migration required. Rollout is additive: new handlers are wired only when configured. Rollback is a clean revert of new detector/OCR modules, `frame_ref` payload addition, optional dependency extra, and tests. To stay under ~400 changed lines, implement contracts, one handler path, PaddleOCR adapter shell, and fake-backed tests first; defer model tuning, multi-backend fallback, and production pipeline wiring.

## Open Questions

None.
