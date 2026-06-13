# Tasks: Slice 1.3 — Plate Detector + OCR Backends

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~420–560 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: contracts + frame_ref + detector handler; PR 2: OCR selector/backend/handler + tests |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Plate crop boundary + `frame_ref` propagation | PR 1 | Base = current feature branch; include tests for `VEHICLE_DETECTED`/`PLATE_CROPPED` shape |
| 2 | OCR backend contract, PaddleOCR adapter, and `PLATE_READ` wiring | PR 2 | Base = PR 1 branch; keep fake-backed tests and optional extra in same slice |

## Phase 1: Foundation / Contracts

- [x] 1.1 Update `src/gryps/plugins/detectors/vehicle_yolo/handler.py` to include `frame_ref` in `VEHICLE_DETECTED` payload.
- [ ] 1.2 Define `PLATE_CROPPED` / `PLATE_READ` payload contracts and backend interface in new OCR/detector modules.
- [ ] 1.3 Add optional `paddleocr` extra to `pyproject.toml` without making it a default install dependency.

## Phase 2: Core Implementation

- [x] 2.1 Create `src/gryps/plugins/detectors/plate_detector/plugin.py`, `handler.py`, and `plugin.yaml` for plate bbox/crop production.
- [ ] 2.2 Create `src/gryps/plugins/ocr_backends/base.py` and `selector.py` with config validation and unknown-backend errors listing valid options.
- [ ] 2.3 Create `src/gryps/plugins/ocr_backends/paddleocr_backend.py` with runtime import and fake-friendly adapter boundary.
- [ ] 2.4 Create `src/gryps/plugins/ocr_backends/handler.py` to consume `PLATE_CROPPED`, emit `PLATE_READ`, and keep raw media out of events.

## Phase 3: Testing / Verification

- [x] 3.1 Add `tests/unit/test_plate_detector_handler.py` for success, no-plate, and no-raw-payload scenarios.
- [ ] 3.2 Add `tests/unit/test_ocr_backends.py` for backend selection, normalization, no-read/error states, and optional PaddleOCR import behavior.
- [ ] 3.3 Add a minimal EventBus integration-style unit test proving `VEHICLE_DETECTED -> PLATE_CROPPED -> PLATE_READ` shape using fakes.
- [ ] 3.4 Verify with `uv run pytest -v --cov=gryps tests/`, then `uv run ruff check .`, then `uv run mypy .`.

## Phase 4: Cleanup / Documentation

- [ ] 4.1 Update inline docstrings/comments in touched modules to explain opaque refs and the `PLATE_CROPPED` -> `PLATE_READ` boundary.
- [x] 4.2 Confirm task slice 1 stays under budget; if not, keep only PR 1 for the first apply and defer OCR wiring to PR 2.
