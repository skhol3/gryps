# Handoff de desarrollo

Este documento existe para poder clonar el repo en otra PC y continuar sin depender de memoria externa como Engram.

## Estado actual

| Área | Estado |
|------|--------|
| Rama base estable | `main` |
| Último slice mergeado | Slice 1.1 / HU-005 — detector de vehículos (PR #8) |
| Rama actual de trabajo | `feat/slice-1.1-frame-store-wiring` |
| Slice actual | Slice 1.1 / HU-005 — FrameStore wiring en stream sources |
| Enfoque actual | `FileStream` inyecta `FrameStore` y almacena frames raw antes de publicar `NEW_FRAME` |

## Cómo levantar el proyecto en otra PC

```bash
git clone git@github.com:skhol3/gryps.git
cd gryps
uv sync --dev
uv run pytest
uv run ruff check src tests
uv run mypy src tests
```

Si necesitás trabajar sobre el slice actual:

```bash
git fetch origin
git checkout feat/slice-1.1-vehicle-yolo
```

## Flujo profesional usado

1. Cada slice se implementa en una rama `feat/slice-X.Y-descripcion`.
2. Cada commit representa un work unit revisable.
3. Tests, código y docs viajan juntos cuando explican el mismo comportamiento.
4. Antes de PR se hace revisión fresca de la rama.
5. Cada PR debe enlazar un issue aprobado y tener exactamente un label `type:*`.
6. Si un PR supera mucho el presupuesto de revisión, se parte en PRs encadenados.

## Slice 1.0 / HU-002 — ROI sin GUI

Ya está mergeado en `main` mediante PR #4.

### Qué se implementó

- `BasePreprocessorPlugin`.
- `ROIStatic`, que carga `config/roi.yaml` y recorta frames headlessly.
- Utilidades de ROI en `src/gryps/utils/roi.py`.
- Herramienta `gryps.tools.calibrate` para generar YAML de ROI fuera del runtime.
- Tests unitarios para ROI, metadata, bounds y calibración.

### Decisiones importantes

- El runtime del edge no importa OpenCV.
- OpenCV solo se usa en la herramienta de calibración.
- La invocación correcta del proyecto es con `uv`, por ejemplo:

  ```bash
  uv run python -m gryps.tools.calibrate referencia.jpg --output config/roi.yaml
  ```

- `crop_frame()` valida que la ROI no se salga del tamaño del frame, porque slicing de Python/NumPy puede recortar silenciosamente.

## Slice 1.1 / HU-005 — detector de vehículos

### PR #8 (merged) — FrameStore + VehicleDetectorHandler

```text
6b8caac chore(sdd): align generated SDD config
...
75da353 feat(detectors): add base detector contract
```

- `BaseDetectorPlugin`.
- `DetectionResult`.
- Boundary de `VehicleYOLOPlugin` con adapter de inferencia inyectado.
- Manifest `vehicle_yolo/plugin.yaml` discoverable por `PluginRegistry`.
- `FrameStore` — contenedor que asocia `frame_ref` → raw frame.
- `VehicleDetectorHandler` — wiring que suscribe a `NEW_FRAME`, resuelve el frame vía `FrameStore`, ejecuta el detector inyectado y publica `VEHICLE_DETECTED`.

### Rama actual — FrameStore wiring en stream sources

- `FileStream` ahora recibe `FrameStore` por DI (parámetro `frame_store`).
- `read_next()` almacena el frame raw en `FrameStore` con key `mem://<stream_id>/<frame_id>`.
- `publish_next()` también almacena antes de publicar el evento.
- Se eliminó el `_frame_cache` interno — `FrameStore` es el único repositorio.
- `close()` ya no limpia el store (es compartido entre streams).
- Tests en `TestFileStreamFrameStoreIntegration` cubren store/publish/flujo multi-stream.

## Slice 1.1 / HU-005 — Ultralytics adapter

### Rama actual (`feat/slice-1.1-ultralytics-adapter`)

```text
Pendiente de PR: `feat(detectors): add optional Ultralytics adapter for vehicle detection`
```

- `UltralyticsAdapter` en `src/gryps/plugins/detectors/vehicle_yolo/ultralytics_adapter.py`.
- Wraplea un `ultralytics.YOLO` para usar como `InferenceAdapter` en `VehicleYOLOPlugin`.
- No importa ultralytics a nivel módulo — solo usa conversiones Python estándar.
- Tests con fakes de ultralytics (`FakeBoxes`, `FakeUltralyticsResults`, `FakeUltralyticsYOLO`).
- `ultralytics` es dependencia opcional: `uv sync --extra ultralytics`.

### Cómo usar

```python
from ultralytics import YOLO
from gryps.plugins.detectors.vehicle_yolo import VehicleYOLOPlugin
from gryps.plugins.detectors.vehicle_yolo.ultralytics_adapter import UltralyticsAdapter

model = YOLO("yolov8n.pt")
adapter = UltralyticsAdapter(model)
plugin = VehicleYOLOPlugin(model=adapter)
detections = plugin.detect(frame, metadata)
```

## Próximo paso recomendado

Opciones razonables:

1. `feat/slice-1.2-plate-detector` — comenzar con detector de placas (HU-004).
2. `feat/slice-1.1-stream-registry` — integration test end-to-end con `PipelineOrchestrator`.
3. `feat/slice-1.1-ultralytics-e2e` — integration test que instale ultralytics y pruebe el adapter real.

## Comandos útiles

```bash
uv run pytest tests/unit/test_detector_base.py tests/unit/test_vehicle_yolo.py
uv run pytest
uv run ruff check src tests
uv run mypy src tests
git diff --check main...HEAD
```

## Qué NO asumir

- No hay RTSP real todavía.
- No hay `RTSPStream`.
- Ya hay adapter real opcional de Ultralytics (ver abajo).
- No hay pesos YOLO en el repo.
- No hay tracking persistente todavía.
- `VEHICLE_DETECTED` conserva `stream_id`/`frame_id` en el evento; el payload contiene solo la detección serializable.
