# Apply Progress: Slice 1.3 — Plate Detector + OCR Backends

## Status

Success — PR 1 (`frame_ref` + plate crop boundary / `PLATE_CROPPED`) and PR 2 (OCR backend selector, PaddleOCR adapter, OCR handler, and `PLATE_READ`) are implemented and verified. All tasks are complete.

## Delivery Boundary

- Strategy: chained PRs, `stacked-to-main`
- Current slice: PR 2 functional OCR only; dependency/lockfile work was split and merged separately in PR #23.
- Start state: PR 1 was merged into `main`; `VEHICLE_DETECTED` carried `frame_ref`, and `PlateDetectorHandler` emitted `PLATE_CROPPED` with opaque `crop_ref` payloads.
- End state: OCR modules define `PLATE_READ`/backend contracts, select configured backends, expose a PaddleOCR 3.x-compatible optional adapter, consume `PLATE_CROPPED`, and emit normalized `PLATE_READ` without raw media payloads.
- Out of scope for this slice: real model downloads, CI dependency on PaddleOCR, persistence/SQLite output, UI overlays, cloud OCR, and additional production OCR backends.

## Completed Tasks

- [x] 1.1 Update `src/gryps/plugins/detectors/vehicle_yolo/handler.py` to include `frame_ref` in `VEHICLE_DETECTED` payload.
- [x] 1.2 Define `PLATE_CROPPED` / `PLATE_READ` payload contracts and backend interface in new OCR/detector modules.
- [x] 1.3 Add optional `paddleocr` extra to `pyproject.toml` without making it a default install dependency. Completed by dependency PR #23; not part of the current functional OCR PR diff.
- [x] 2.1 Create `src/gryps/plugins/detectors/plate_detector/plugin.py`, `handler.py`, and `plugin.yaml` for plate bbox/crop production.
- [x] 2.2 Create `src/gryps/plugins/ocr_backends/base.py` and `selector.py` with config validation and unknown-backend errors listing valid options.
- [x] 2.3 Create `src/gryps/plugins/ocr_backends/paddleocr_backend.py` with runtime import and fake-friendly adapter boundary.
- [x] 2.4 Create `src/gryps/plugins/ocr_backends/handler.py` to consume `PLATE_CROPPED`, emit `PLATE_READ`, and keep raw media out of events.
- [x] 3.1 Add `tests/unit/test_plate_detector_handler.py` for success, no-plate, and no-raw-payload scenarios.
- [x] 3.2 Add `tests/unit/test_ocr_backends.py` for backend selection, normalization, no-read/error states, and optional PaddleOCR import behavior.
- [x] 3.3 Add a minimal EventBus integration-style unit test proving `VEHICLE_DETECTED -> PLATE_CROPPED -> PLATE_READ` shape using fakes.
- [x] 3.4 Verify with `uv run pytest -v --cov=gryps tests/`, then `uv run ruff check .`, then `uv run mypy .`.
- [x] 4.1 Update inline docstrings/comments in touched modules to explain opaque refs and the `PLATE_CROPPED` -> `PLATE_READ` boundary.
- [x] 4.2 Confirm task slice 1 stays under budget; OCR wiring remains deferred to PR 2.

## Remaining Tasks

None.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/unit/test_ocr_backends.py` — PASS, 11 passed after updating fake-backed PaddleOCR coverage to model 3.x `predict(...)` output.
- `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/` — PASS, 267 passed.
- `uv run ruff check .` — PASS.
- `uv run mypy src tests` — PASS, 66 source files.
- `uv lock --check` — PASS, resolved 125 packages after PR #23 dependency/lockfile merge.
- `git diff --check` — PASS.
- Current PR diff intentionally excludes `pyproject.toml` and `uv.lock`.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| PR readiness fix: PaddleOCR 3.x adapter compatibility | `tests/unit/test_ocr_backends.py` | Unit | ✅ 9/9 existing OCR tests passed before changes | ✅ Added failing fake-backed `predict(...)` tests for dict and object prediction shapes plus predict errors | ✅ 11/11 OCR tests passed after adapter update | ✅ 3 PaddleOCR adapter cases cover best-confidence dict output, object output, and backend error path | ✅ Extracted parser helpers and reran focused tests/ruff/mypy |

## Notes

- OpenSpec `openspec/config.yaml` reports `strict_tdd: true`; this fix followed a strict TDD cycle for the PaddleOCR compatibility blocker.
- No raw frames/crops are added to EventBus payloads; OCR events carry refs and metadata only.
- PaddleOCR remains optional: dependency metadata and lockfile updates were handled by PR #23; this PR contains only functional OCR code, tests, and SDD artifact updates.
- `PaddleOCRBackend` uses the PaddleOCR 3.x `predict(...)` path and parses dictionary/object prediction shapes such as `res.rec_texts` plus `res.rec_scores`; tests remain fake-backed and do not import/download PaddleOCR.
