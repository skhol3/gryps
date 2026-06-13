# Apply Progress: Slice 1.3 — Plate Detector + OCR Backends

## Status

Partial success — PR 1 (`frame_ref` + plate crop boundary / `PLATE_CROPPED`) is implemented and verified. PR 2 OCR selector/PaddleOCR/`PLATE_READ` work remains pending.

## Delivery Boundary

- Strategy: chained PRs, `stacked-to-main`
- Current slice: PR 1
- Start state: existing `VehicleDetectorHandler` emitted `VEHICLE_DETECTED` without `frame_ref`; no plate detector boundary existed.
- End state: `VEHICLE_DETECTED` carries `frame_ref`; `PlateDetectorHandler` resolves the frame, stores plate crops by `crop_ref`, and emits `PLATE_CROPPED` without raw media payloads.
- Out of scope for this slice: OCR backend selector, PaddleOCR adapter, OCR handler, `PLATE_READ`, and `pyproject.toml` PaddleOCR extra.

## Completed Tasks

- [x] 1.1 Update `src/gryps/plugins/detectors/vehicle_yolo/handler.py` to include `frame_ref` in `VEHICLE_DETECTED` payload.
- [x] 2.1 Create `src/gryps/plugins/detectors/plate_detector/plugin.py`, `handler.py`, and `plugin.yaml` for plate bbox/crop production.
- [x] 3.1 Add `tests/unit/test_plate_detector_handler.py` for success, no-plate, and no-raw-payload scenarios.
- [x] 4.2 Confirm task slice 1 stays under budget; OCR wiring remains deferred to PR 2.

## Remaining Tasks

- [ ] 1.2 Define complete `PLATE_READ` payload/backend interface contracts in OCR modules.
- [ ] 1.3 Add optional `paddleocr` extra to `pyproject.toml` without making it a default install dependency.
- [ ] 2.2 Create OCR backend base and selector with config validation.
- [ ] 2.3 Create PaddleOCR adapter with runtime import.
- [ ] 2.4 Create OCR handler to consume `PLATE_CROPPED` and emit `PLATE_READ`.
- [ ] 3.2 Add OCR backend tests.
- [ ] 3.3 Add `VEHICLE_DETECTED -> PLATE_CROPPED -> PLATE_READ` event chain test.
- [ ] 3.4 Run full requested verification (`uv run pytest -v --cov=gryps tests/`, `uv run ruff check .`, `uv run mypy .`).
- [ ] 4.1 Update inline docstrings/comments for the full `PLATE_CROPPED` -> `PLATE_READ` boundary.

## Verification

- `uv run pytest tests/unit/test_vehicle_detector_handler.py tests/unit/test_plate_detector_handler.py -q` — PASS, 12 passed.
- `uv run ruff check src/gryps/plugins/detectors/vehicle_yolo/handler.py src/gryps/plugins/detectors/plate_detector tests/unit/test_vehicle_detector_handler.py tests/unit/test_plate_detector_handler.py` — PASS.
- `uv run mypy src/gryps/plugins/detectors/vehicle_yolo/handler.py src/gryps/plugins/detectors/plate_detector tests/unit/test_vehicle_detector_handler.py tests/unit/test_plate_detector_handler.py` — PASS.
- `uv run pytest tests/unit -q` — PASS, 255 passed.

## Notes

- OpenSpec `openspec/config.yaml` still reports `strict_tdd: true`, but the orchestrator explicitly resolved this apply run as Standard mode using current project context/stale config guidance.
- No raw frames/crops are added to EventBus payloads; crops are stored in `FrameStore` under opaque refs.
