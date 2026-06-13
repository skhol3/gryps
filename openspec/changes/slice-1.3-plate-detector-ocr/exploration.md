## Exploration: Slice 1.3 — Plate Detector + OCR Backends

### Current State
The codebase already has the event pipeline, `FrameStore`, `LocalEventBus`, detector base contracts, and a working vehicle detector boundary (`VehicleYOLOPlugin` + `VehicleDetectorHandler`). `PlateTracker` already covers best-frame selection, OCR cache state, and track-lost lifecycle, but there is no plate detector plugin or OCR backend implementation yet. The docs mark HU-007, HU-009, and HU-012 as planned for Slice 1.3.

### Affected Areas
- `src/gryps/plugins/detectors/base.py` — detector contract and payload shape already exist.
- `src/gryps/plugins/detectors/vehicle_yolo/*` — shows the plugin/handler pattern Slice 1.3 should mirror.
- `src/gryps/tracking/plate_tracker.py` — already provides best-frame and OCR cache state.
- `src/gryps/core/bus.py` — event envelope and synchronous bus semantics.
- `src/gryps/core/frame_store.py` — raw frames stay out of the bus and are fetched by reference.
- `docs/ARQUITECTURA.md` — defines `VEHICLE_DETECTED`, `PLATE_CROPPED`, `PLATE_READ`, and `TRACK_LOST` flow.
- `docs/HISTORIAS_USUARIO.md` — source of HU-007 / HU-009 / HU-012 acceptance criteria.
- `docs/DESARROLLO.md` — explicitly names Slice 1.3 as the next slice.

### Approaches
1. **Minimal detector + backend interfaces** — add a `PlateDetectorPlugin` boundary and a generic OCR backend interface/registry, with tests around payloads, backend selection, and event wiring.
   - Pros: reviewable under 400 LOC, fits existing plugin patterns, keeps heavy models optional.
   - Cons: does not deliver real OCR inference or crop generation logic.
   - Effort: Low

2. **End-to-end plate detection flow** — implement plate cropping, `PLATE_CROPPED` emission, OCR selection, and `PLATE_READ` emission in one slice.
   - Pros: closer to user-visible behavior.
   - Cons: likely exceeds review budget, couples several still-unstable boundaries, higher risk without a plate plugin contract already in place.
   - Effort: High

### Recommendation
Start with the minimal detector/backend interfaces. For Slice 1.3, the reviewable first slice should cover: HU-007 plate detector boundary on top of `VEHICLE_DETECTED`, HU-009 OCR backend contract plus normalized `PLATE_READ` payload shape, and HU-012 backend selection/config validation. Reuse `PlateTracker` as the lifecycle source of truth rather than expanding its responsibility.

### Risks
- `ocr_backends/` is empty, so the backend contract and selection layer still need a first concrete shape.
- The exact plate crop source is unclear: docs assume vehicle crop + ROI offset, but current code does not yet expose a plate-crop producer.
- Event naming/payloads in docs include `PLATE_CROPPED` and `TRACK_LOST`, but no producer exists yet in code, so proposal must decide whether Slice 1.3 introduces them or only prepares for them.

### Ready for Proposal
Yes — but only after the orchestrator clarifies product scope for plate crop ownership, backend fallback behavior, and whether Slice 1.3 must include real OCR inference or just contracts + selection.
