# Proposal: Slice 1.3 — Plate Detector + OCR Backends

## Intent

Deliver the first plate-reading slice after vehicle tracking: detect/crop plates, pass crops through a swappable OCR backend, and emit normalized `PLATE_READ` without raw frames on the EventBus.

## Scope

### In Scope
- Keep the first slice under ~400 changed lines for HU-007, HU-009, and HU-012.
- Introduce `PlateDetector` as owner of plate bbox + crop production from `VEHICLE_DETECTED`/`FrameStore` input.
- Emit `PLATE_CROPPED` as the explicit boundary before OCR, then `PLATE_READ` as the final OCR result.
- Add a swappable OCR backend contract/config selector with PaddleOCR as the first functional backend path.

### Out of Scope
- Training/tuning models, multi-backend orchestration, cloud OCR, persistence, UI overlays, or SQLite output.
- Moving crop generation into `PlateTracker`; it remains lifecycle, best-frame, and OCR-cache state only.
- Full production pipeline wiring beyond the minimal event handlers needed to prove the boundary.

## Capabilities

### New Capabilities
- `plate-detector-ocr`: Plate crop production, `PLATE_CROPPED` contract, swappable OCR backend selection, and normalized `PLATE_READ` payload.

### Modified Capabilities
- None; `openspec/specs/` has no existing capability specs to modify.

## Approach

Mirror `vehicle_yolo`: use injectable adapters, keep frames/crops in stores by reference, and publish serializable payloads only. `PlateDetector` consumes vehicle detections, fetches the source frame, crops the vehicle/plate, stores a crop reference, and publishes `PLATE_CROPPED`. The selected OCR backend consumes the crop reference, normalizes text/confidence/errors, and publishes `PLATE_READ`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/gryps/plugins/detectors/` | New | Plate detector plugin/handler and crop payloads. |
| `src/gryps/plugins/ocr_backends/` | New | OCR backend contract, selector, and first functional backend. |
| `src/gryps/core/frame_store.py` | Modified | Reuse/extend references for plate crops if needed. |
| `tests/unit/` | New | Contract, event payload, selector, and fake-adapter tests. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Real OCR dependencies are unavailable in CI | Med | Keep backend optional and adapter-injected; test with fakes. |
| Scope exceeds 400 changed lines | Med | Limit to contracts, one backend path, and unit coverage. |
| Event payload drift | Low | Spec `PLATE_CROPPED` -> `PLATE_READ` explicitly before design. |

## Rollback Plan

Revert the Slice 1.3 change set: remove new detector/OCR modules, config selector entries, and tests. Vehicle detection, `PlateTracker`, and outputs remain unchanged.

## Dependencies

- Existing `VehicleDetectorHandler`, `FrameStore`, `LocalEventBus`, and `PlateTracker` from prior slices.
- Optional runtime OCR dependency for the first functional path, isolated behind the backend adapter.

## Success Criteria

- [ ] `PlateDetector` publishes `PLATE_CROPPED` with `track_id`, plate bbox, vehicle bbox, and crop reference.
- [ ] A configured OCR backend consumes `PLATE_CROPPED` and publishes normalized `PLATE_READ`.
- [ ] Unknown OCR backend configuration fails with a clear list of valid options.
- [ ] Unit tests cover no-plate, OCR failure/unknown text, and successful text normalization.
