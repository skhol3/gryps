# Handoff de desarrollo

Este documento existe para poder clonar el repo en otra PC y continuar sin depender de memoria externa como Engram.

## Estado actual

| Área | Estado |
|------|--------|
| Rama base estable | `main` |
| Último slice mergeado | Slice 1.0 / HU-002 — ROI estático sin GUI |
| Rama actual de trabajo | `feat/slice-1.1-vehicle-yolo` |
| Slice actual | Slice 1.1 / HU-005 — detector de vehículos |
| Enfoque actual | Contrato de detector + boundary de `VehicleYOLO`, sin dependencia real de YOLO todavía |

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

La rama actual contiene dos commits listos para PR:

```text
75da353 feat(detectors): add base detector contract
3de397d feat(detectors): add vehicle YOLO plugin boundary
```

### Qué se implementó

- `BaseDetectorPlugin`.
- `DetectionResult`.
- Boundary de `VehicleYOLOPlugin` con adapter de inferencia inyectado.
- Manifest `vehicle_yolo/plugin.yaml` discoverable por `PluginRegistry`.
- Tests con fake model, sin descargar pesos ni instalar Ultralytics.

### Decisiones importantes

- Todavía no se agregó `ultralytics`, OpenCV, pesos de modelo ni descargas de red.
- `VehicleYOLOPlugin` recibe un adapter/modelo inyectado para mantener testabilidad.
- No hay wiring de pipeline ni publicación de eventos todavía.
- Raw frames no viajan por `EventBus`; los detectores devuelven resultados serializables y otro componente decidirá cómo publicar eventos.
- `bbox` está definido como coordenadas de píxel `xyxy`:

  ```text
  (x_min, y_min, x_max, y_max)
  ```

  en el frame procesado, después de preprocessors como ROI.

- Los bounds son half-open: `x_min`/`y_min` inclusivos, `x_max`/`y_max` exclusivos.
- `track_id` es opcional y no representa tracking persistente; HU-006 debe encargarse de tracking real.
- Clases vehiculares actuales: `car`, `motorcycle`, `bus`, `truck`.
- `person`/peatones se ignoran porque HU-005 no activa detector de personas.

## Próximo paso recomendado

Terminar el PR del Slice 1.1 actual y mergearlo antes de seguir.

Después de mergear, crear una rama nueva desde `main` para el siguiente work unit. Opciones razonables:

1. `feat/slice-1.1-vehicle-events` — consumir `NEW_FRAME` y publicar `VEHICLE_DETECTED` con fake resolver/model.
2. `feat/slice-1.1-ultralytics-adapter` — agregar adapter real opcional de Ultralytics, sin pesos en Git.
3. `docs/slice-1.1-detector-flow` — documentar trazabilidad de HU-005 si se decide cerrar primero la base.

Recomendación: avanzar primero con eventos/wiring fake antes de meter Ultralytics real. La dependencia pesada debe llegar cuando la frontera ya esté probada.

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
- No hay adapter real de Ultralytics todavía.
- No hay pesos YOLO en el repo.
- No hay tracking persistente todavía.
- No hay publicación real de `VEHICLE_DETECTED` todavía.
