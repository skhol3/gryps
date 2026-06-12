# Guía de Desarrollo — Gryps

> **Versión:** 0.2
> **Fecha:** 2026-06-12
> **Audiencia:** Desarrolladores del proyecto

---

## 1. Estado Actual del Desarrollo

Gryps está en **fase de implementación de MVP — Slices 1.0 a 1.2 completados**.

### Lo que existe

| Artefacto | Estado | Notas |
|-----------|--------|-------|
| `src/gryps/core/` | Implementado | EventBus, Event dataclasses, PluginRegistry, PipelineOrchestrator, base exceptions |
| `src/gryps/streams/` | Implementado | `BaseStreamSource`, `FileStream` con `FrameStore` wiring |
| `src/gryps/preprocessors/` | Parcial | `BasePreprocessorPlugin`, `ROIStatic` con carga YAML + calibración headless |
| `src/gryps/plugins/detectors/` | Parcial | `BaseDetectorPlugin`, `VehicleYOLOPlugin` boundary, `UltralyticsAdapter` opcional |
| `src/gryps/tracking/` | Implementado | `PlateTracker` con ciclo de vida, mejor frame y estado de cache OCR |
| `src/gryps/tools/` | Implementado | `gryps.tools.calibrate` — generación de YAML de ROI |
| `config/` | Parcial | `config/roi.yaml` esperado en runtime (requiere calibración) |
| `tests/` | Implementado | Tests unitarios con pytest; tests de integración pendientes |
| `pyproject.toml` | Configurado | Ruff, mypy, pytest, extras opcionales (ultralytics) |
| `.github/workflows/` | Configurado | CI con ruff + mypy + pytest |
| `docs/VISION.md` | Completo | Visión de producto, alcance MVP vs futuro |
| `docs/ARQUITECTURA.md` | Completo | Arquitectura, ADRs, roadmap |
| `docs/HISTORIAS_USUARIO.md` | Completo | 28 HU con criterios de aceptación y trazabilidad |
| Validaciones de concepto | Externo a Gryps | Notebooks/scripts probaron YOLO11n, l.pt, PaddleOCR, Tesseract en i5 2014 |

### Lo que NO existe (debe construirse)

- Detector de placas (HU-007)
- Backends de OCR (HU-009, HU-012)
- Persistencia SQLite (HU-020)
- Integración completa de EventBus local con `PLATE_READ` y pipeline persistente (HU-017 — parcial)
- Perfiles de hardware (HU-003)
- Selección de tipo de cámara (HU-004)
- Streams RTSP/USB reales

---

## 2. Stack Tecnológico

| Capa | Tecnología | Versión | Razón |
|------|-----------|---------|-------|
| Lenguaje | Python | >= 3.12 | Ecosistema de visión, tipado moderno |
| Gestor de paquetes | uv | Última estable | Velocidad, resolución determinística |
| Detección | Ultralytics (YOLO11) | Última | ONNX export, tracking integrado, edge-friendly |
| OCR | PaddleOCR / Tesseract | Últimas | Trade-off precisión vs velocidad |
| Base de datos | SQLite (MVP) | stdlib | Sin servidor, embebido, suficiente para MVP |
| Event Bus | Local in-process (MVP) | Propio | Sin dependencias externas en MVP |

---

## 3. Prerrequisitos: Tooling de Calidad

Antes de escribir cualquier feature, configurar el tooling de calidad. Esto no es opcional: sin calidad desde el inicio, la deuda técnica se vuelve irreversible en un proyecto de esta complejidad.

### 3.1 Configuración Inicial

Agregar a `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "ARG", "PTH"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
```

Dependencias de desarrollo (`uv add --dev`):

- `pytest>=8` — test runner
- `pytest-cov` — cobertura
- `ruff` — linter + formatter
- `mypy` — type checker
- `pre-commit` — hooks de calidad

### 3.2 Hooks de Pre-commit

Configurar `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.9.0
    hooks:
      - id: mypy
```

### 3.3 Scripts de desarrollo (pyproject.toml)

```toml
[tool.uv.scripts]
lint = "ruff check src/"
format = "ruff format src/"
typecheck = "mypy src/"
test = "pytest -v --cov=src tests/"
check-all = "ruff check src/ && mypy src/ && pytest -v --cov=src tests/"
```

### 3.4 CI/CD (GitHub Actions)

```yaml
# .github/workflows/ci.yml — crear al primer commit de código
name: CI
on: [push, pull_request]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run ruff check src/
      - run: uv run mypy src/
      - run: uv run pytest -v --cov=src tests/
```

---

## 4. Primer Slice de Implementación

Se recomienda comenzar por el **núcleo de infraestructura** antes que cualquier feature visible. Este slice inicial (~1 semana) establece la base sobre la que todo lo demás se apoya.

### Slice 0.5: Infraestructura Base

| Orden | Tarea | Archivos | Depende de | Verificado por |
|-------|-------|----------|------------|----------------|
| 0.1 | Estructura de directorios | Crear `core/`, `streams/`, `plugins/`, `preprocessors/`, `tracking/`, `utils/`, `tools/`, `tests/` con `__init__.py` | Nada | `ls -R` |
| 0.2 | Tooling de calidad | Configurar ruff, mypy, pytest, pre-commit, CI | 0.1 | `uv run check-all` pasa |
| 0.3 | `Event` dataclass + interfaz `EventBus` | `core/bus.py` | Nada | Tests de creación y serialización |
| 0.4 | `LocalEventBus` implementación in-process | `core/bus.py` | 0.3 | Test: publicar 1000 eventos, verificar suscriptores |
| 0.5 | `PluginRegistry` base (scan + load) | `core/registry.py` | 0.4 | Test: cargar plugin dummy desde `tests/fixtures/` |
| 0.6 | `PipelineOrchestrator` mínimo | `core/pipeline_orchestrator.py` | 0.4, 0.5 | Test: arrancar pipeline con 0 streams (no falla) |
| 0.7 | `BaseStreamSource` + `FileStream` | `streams/base.py`, `streams/file_stream.py` | 0.4 | Test: leer video de fixture, publicar `NEW_FRAME` |
| 0.8 | `ConsoleOutput` plugin | `plugins/outputs/console_logger/` | 0.4, 0.5 | Test: evento `PLATE_READ` se imprime en consola |
| 0.9 | `main.py` funcional que orquesta 0.4–0.8 | `main.py` | Todo lo anterior | `python main.py --file test.mp4` procesa sin errores |

### Criterio de éxito del Slice 0.5

```
$ uv run check-all  # lint + types + tests → todo verde
$ python main.py --file tests/fixtures/sample_traffic.mp4
[CONSOLE] Frame 1 | Stream: file_01
[CONSOLE] Frame 2 | Stream: file_01
...
```

No hay detección de vehículos, ni OCR, ni persistencia. Pero la infraestructura está viva y testeada.

### Plantilla para Documentar un Slice

Cada slice nuevo debe registrarse con esta plantilla (en este documento) al planificarse:

| Campo | Descripción |
|-------|-------------|
| **Slice** | ID del slice (ej. 1.0, 1.1) |
| **HU** | ID de la(s) historia(s) de usuario que cubre |
| **Depende de** | Slice(s) previo(s) requerido(s) |
| **Archivos** | Rutas a crear o modificar |
| **Eventos nuevos / contratos** | Nuevos tipos de evento en el bus o cambios en contratos existentes |
| **Criterio de éxito** | Verificación funcional observable |
| **Tests** | Tests unitarios y de integración requeridos |
| **Documentación / trazabilidad** | Enlaces a ARQUITECTURA §, HU, docs actualizados |
| **Duración estimada** | Días hábiles |

### Siguientes Slices Recomendados (1.0 — 1.4)

Completados los Slices 0.5 (infraestructura), 1.0 (ROI), 1.1 (detección de vehículos) y 1.2 (tracking). Los siguientes slices completan el pipeline MVP con trazabilidad a HU:

| Slice | HU | Tarea | Depende de |
|-------|------|-------|------------|
| 1.0 | HU-002 | `BasePreprocessorPlugin` + `ROIStatic` | 0.5 |
| 1.1 | HU-005 | `BaseDetectorPlugin` + `VehicleYOLO` | 1.0 |
| 1.2 | HU-006, HU-010, HU-011 | `PlateTracker` (mejor-frame + cache) | 1.1 |
| 1.3 | HU-007, HU-009, HU-012 | `PlateDetector` + OCR Backends | 1.2 |
| 1.4 | HU-020, HU-017 | `SQLiteOutput` + pipeline wiring | 1.3 |

### Slice 1.0: ROI estático sin GUI en el edge

| Campo | Detalle |
|-------|---------|
| **Slice** | 1.0 |
| **HU** | HU-002 |
| **Depende de** | Slice 0.5 |
| **Archivos** | `src/gryps/preprocessors/base.py`, `src/gryps/preprocessors/roi/static.py`, `src/gryps/utils/roi.py`, `src/gryps/tools/calibrate.py`, `tests/unit/test_roi_preprocessor.py`, `tests/unit/test_calibrate_tool.py` |
| **Eventos nuevos / contratos** | No introduce eventos nuevos. `ROIStatic` recibe frame + metadata y devuelve frame recortado + metadata enriquecida. |
| **Criterio de éxito** | El técnico genera `config/roi.yaml` con la herramienta de calibración; luego el edge carga `ROIStatic` headless y aplica esa ROI sin abrir ventanas. |
| **Tests** | Validación/crop de ROI, carga de `roi.yaml`, metadata de `ROIStatic`, manifest del plugin, escritura de YAML de calibración y errores de OpenCV diferido. |
| **Documentación / trazabilidad** | HU-002 en `docs/HISTORIAS_USUARIO.md`; arquitectura §5 y §7. |
| **Duración estimada** | 1-2 días hábiles |

#### Camino feliz HU-002

1. El técnico toma o recibe una imagen de referencia de la cámara.
2. En una laptop con entorno gráfico, ejecuta la herramienta de calibración y selecciona una ROI rectangular:

   ```bash
   python -m gryps.tools.calibrate referencia.jpg --output config/roi.yaml
   ```

3. La herramienta escribe un YAML compatible con runtime:

   ```yaml
   roi:
     x: 100
     y: 80
     width: 640
     height: 360
   ```

4. En el edge, `ROIStatic` carga `config/roi.yaml`, recorta cada frame y agrega `roi_applied` y `preprocessors_applied` a la metadata.
5. Si falta `config/roi.yaml`, el runtime falla con un mensaje accionable para ejecutar la calibración fuera del edge.

#### Fuera de alcance del Slice 1.0

- Cableado automático del preprocessor en perfiles o configuración de streams.
- ROI poligonal, PTZ, auto-motion o dewarping.
- Tests de GUI real con OpenCV; la GUI queda detrás de una frontera diferida para mantener CI headless.

### Slice 1.1: Detección de vehículos

| Campo | Detalle |
|-------|---------|
| **Slice** | 1.1 |
| **HU** | HU-005 |
| **Depende de** | Slice 1.0 |
| **Archivos** | `src/gryps/plugins/detectors/base.py`, `src/gryps/plugins/detectors/vehicle_yolo/`, `src/gryps/core/frame_store.py`, `src/gryps/streams/file_stream.py`, `tests/` |
| **Eventos nuevos / contratos** | `VEHICLE_DETECTED` con `stream_id`/`frame_id` y payload serializable. `FrameStore` como repositorio central de frames raw. |
| **Criterio de éxito** | `FileStream` publica `NEW_FRAME`, `VehicleDetectorHandler` suscribe, resuelve frame vía `FrameStore`, ejecuta detector inyectado y publica `VEHICLE_DETECTED`. Detector opcional con `UltralyticsAdapter`. |
| **Tests** | Unitarios de `BaseDetectorPlugin`, `DetectionResult`, `VehicleYOLOPlugin` con adapter fake. Integración de `FrameStore` + `FileStream`. Tests de `UltralyticsAdapter` con fakes de ultralytics. |
| **Documentación / trazabilidad** | HU-005 en `docs/HISTORIAS_USUARIO.md`; PRs #8, #10, #12 mergeados. |
| **Duración estimada** | 2-3 días hábiles |

#### Eventos del Slice 1.1

| Evento | Contenido | Publicado por |
|--------|-----------|--------------|
| `NEW_FRAME` | `stream_id`, `frame_id`, `timestamp` | `FileStream` |
| `VEHICLE_DETECTED` | `stream_id`, `frame_id`, `detections[]` (label, confidence, bbox) | `VehicleDetectorHandler` |

#### Decisiones importantes del Slice 1.1

- `FrameStore` es el repositorio único de frames raw; `FileStream` ya no cachea frames internamente.
- El adapter de inferencia (`InferenceAdapter`) es inyectado — `VehicleYOLOPlugin` no conoce Ultralytics.
- `UltralyticsAdapter` es dependencia opcional (`uv sync --extra ultralytics`).
- Los frames NO viajan por el EventBus — solo referencias (`stream_id`/`frame_id`).

#### Fuera de alcance del Slice 1.1

- Tracking persistente de vehículos (HU-006, Slice 1.2).
- Detección de placas ni OCR (Slice 1.3).
- Streams RTSP o USB reales.

---

## Próximo slice recomendado

**Slice 1.3 — Detección de placas + OCR (HU-007, HU-009, HU-012)**

Implementar el detector de placas y los contratos de OCR sobre el estado de tracking ya disponible, manteniendo modelos reales como dependencias opcionales cuando corresponda.

Ver roadmap en tabla de Siguientes Slices (sección anterior) y detalle en HU correspondientes.

---

## 5. Estrategia de Tests

### 5.1 Niveles

| Nivel | Qué probar | Herramienta | Ubicación |
|-------|-----------|-------------|-----------|
| **Unitario** | Lógica pura: serialización de eventos, validación de config, cálculo de ROI, normalización de OCR, dataclasses de tracking | pytest | `tests/unit/` |
| **Integración** | Flujo entre componentes: EventBus + plugins, preprocessor chain, pipeline completo con video de prueba corto | pytest + fixtures | `tests/integration/` |
| **Aceptación** | Historias de usuario: HU-001 a HU-028 simulando escenarios reales | pytest + fixtures | `tests/integration/` |
| **Rendimiento** | FPS sostenido, latencia de OCR, consumo de RAM | pytest-benchmark | `tests/performance/` |

### 5.2 Fixtures

- `tests/fixtures/videos/` — clips cortos (3–5 seg) de tráfico real con placas conocidas
- `tests/fixtures/images/` — crops de placas para tests de OCR sin pipeline completo
- `tests/fixtures/calibrations/` — YAML de configuración válidos e inválidos
- `tests/conftest.py` — `LocalEventBus` fixture, `PluginRegistry` fixture, perfil `EDGE_HOUSE` fixture

### 5.3 Principios

- No hacer mock del EventBus en tests de integración. Usar `LocalEventBus` real.
- Los detectores YOLO se cachean una vez por sesión de test (descargar modelo una vez).
- Los tests de OCR usan imágenes predefinidas, no el pipeline completo.
- Cada test de integración limpia sus eventos suscritos al terminar.

---

## 6. Flujo de Trabajo

```bash
# Clonar e instalar
git clone <repo>
cd gryps
uv sync

# Desarrollo
uv run ruff check src/    # lint
uv run ruff format src/   # formatear
uv run mypy src/          # tipos
uv run pytest -v tests/   # tests

# Pre-commit (se ejecuta automático al hacer git commit)
pre-commit install
```

### Convenciones

- **Ramas:** `main` (protección), `feat/<nombre>` para features, `fix/<nombre>` para bugs
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- **Pull Requests:** Al menos 1 approval. Todos los checks deben pasar.
- **Archivos nuevos:** Siempre incluir `__init__.py` y tests.
- **Errores:** Usar `GrypsError` y subclases de `core/exceptions.py`. Nunca `raise Exception`.

---

## 7. Trazabilidad entre Documentos

### Jerarquía de Autoridad

| Documento | Propósito | Autoridad |
|-----------|-----------|-----------|
| `VISION.md` | Para qué / alcance MVP | Define el QUÉ y el POR QUÉ |
| `ARQUITECTURA.md` | Cómo / constraints arquitectónicas | Define el CÓMO y los límites técnicos |
| `HISTORIAS_USUARIO.md` | Qué valor / HU con criterios de aceptación | Define el PARA QUIÉN |
| `DESARROLLO.md` | Orden técnico de implementación | Guía de implementación — no fuente de requisitos |
| `CUADERNO_ESTUDIO.md` | Notas pedagógicas | Sin autoridad de planificación — solo enseñanza |

> **Regla:** Un slice nuevo debe referenciar HU-ID(s), la sección de ARQUITECTURA que aplica, el orden en DESARROLLO, los tests que lo verifican, y su estado actual.

### Mapa de Relaciones

```
VISION.md                    ───→  ARQUITECTURA.md     ───→  HISTORIAS_USUARIO.md
  ┃                                  ┃                         ┃
  ┃  Define el QUÉ                ┃  Define el CÓMO         ┃  Define el PARA QUIÉN
  ┃  (producto, alcance,          ┃  (componentes,          ┃  (roles, criterios de
  ┃   roadmap, métricas)           ┃   patrones, ADRs)       ┃   aceptación)
  ┃                                  ┃                         ┃
  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━┛
                                  ┃
                                  ┃  Ambos referencian HU por ID
                                  ▼
                          DESARROLLO.md
                              ┃
                          Guía de implementación:
                          slice recomendado, tooling,
                          estrategia de tests, workflow
```

- `VISION.md` → define Fases y MVP items
- `ARQUITECTURA.md` §11 → mapea Fases a HU concretas
- `HISTORIAS_USUARIO.md` → tabla de trazabilidad con componente y estado
- `DESARROLLO.md` → slice de implementación con orden y dependencias

---

## 8. Definición de Completado (Definition of Done)

Un slice se considera completado solo cuando cumple TODOS los siguientes criterios:

| Criterio | Descripción | Verificación |
|----------|-------------|--------------|
| **Código implementado** | El código del slice está escrito y mergeado a `main` | `git log` muestra el commit |
| **Tests pasan** | Tests unitarios y de integración del slice existen y pasan | `uv run pytest -v tests/` verde |
| **Code review fresco** | El código fue revisado por al menos un par | PR aprobado sin cambios pendientes |
| **Trazabilidad a HU** | El commit o PR referencia el HU-ID correspondiente | Mensaje de commit o PR incluye `HU-NNN` |
| **Glosario de eventos actualizado** | Si el slice introduce nuevos eventos de bus, el glosario en `ARQUITECTURA.md` §4.3 se actualiza | `grep` del nuevo evento en §4.3 |
| **Contexto persistente** | El contexto del slice y sus decisiones quedan registradas (Engram, PR description) | Entrada en memoria persistente o PR describe trade-offs |
| **Documentación actualizada** | Si el slice cambia el comportamiento esperado, los docs relevantes se actualizan | Revisión de docs afectados |

> **Importante:** `CUADERNO_ESTUDIO.md` contiene notas pedagógicas sobre el por qué y para qué de las decisiones técnicas. No es fuente de planificación ni autoridad de requisitos. Los criterios anteriores son los que determinan el completado de un slice.

## 9. Riesgos Inmediatos para el Desarrollo

1. **Sin tooling de calidad desde el inicio** → riesgo máximo. No escribir una línea de feature sin ruff + mypy + pytest configurados.
2. **Dependencia de modelos de IA pesados** → YOLO11n y PaddleOCR requieren descargas de varios GB. Asegurar fixtures de test ligeros (frames estáticos, no videos completos).
3. **Hardware de prueba limitado** → conseguir el i5 2014 / 8 GB RAM lo antes posible para validar FPS reales.
4. **Uso de `cv2.imshow` en tests** → prohibido. Los tests deben correr en CI headless. Usar `cv2.imwrite` para validación visual manual.
5. **Serialización de `np.ndarray`** → los frames NO deben viajar por el EventBus. Solo referencias o paths. El bus transporta metadatos.
