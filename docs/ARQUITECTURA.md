# Arquitectura de Software — Gryps

> **Versión:** 1.1  
> **Fecha:** 2026-06-02  
> **Autor:** Equipo Gryps  
> **Estado:** Aprobado para implementación  
> **Audiencia:** Desarrolladores, DevOps, Arquitectos de Solución

---

## Navegación Rápida

| Sección | Contenido |
|---------|-----------|
| [§1](#1-visión-arquitectónica) Visión Arquitectónica | Patrones, principios fundamentales |
| [§2](#2-diagrama-de-componentes) Diagrama de Componentes | Arquitectura visual del sistema |
| [§3](#3-estructura-de-directorios) Estructura de Directorios | Árbol del proyecto con descripciones |
| [§4](#4-el-event-bus--contrato-central) Event Bus | Contrato central, vocabulario, implementaciones |
| [§5](#5-preprocessors--chain-of-responsibility) Preprocessors | Chain of Responsibility, cadena por tipo de cámara |
| [§6](#6-plugin-registry--ciclo-de-vida) Plugin Registry | Ciclo de vida, filtrado, aislamiento de fallos |
| [§7](#7-flujo-de-datos-frame-a-frame-mvp--cámara-estática) Flujo de Datos | Pipeline frame a frame (MVP cámara estática) |
| [§8](#8-perfiles-de-hardware) Perfiles de Hardware | EDGE_HOUSE, EDGE_NVR, EDGE_RPI, CLOUD_HUB |
| [§9](#9-decisiones-arquitectónicas-y-trade-offs) ADRs | Decisiones arquitectónicas y trade-offs |
| [§10](#10-seguridad-y-privacidad-en-la-arquitectura) Seguridad y Privacidad | Medidas por capa |
| [§11](#11-roadmap-de-evolución-arquitectónica) Roadmap | Fases con trazabilidad a HU |
| [§12](#12-riesgos-y-brechas-de-decisión) Riesgos y Brechas | Decisiones pendientes, riesgos técnicos |
| [§13](#13-glosario-arquitectónico) Glosario | Términos arquitectónicos |

---

## 1. VISIÓN ARQUITECTÓNICA

### 1.1 Declaración

Gryps es una plataforma de video-analytics **edge-first** diseñada para evolucionar desde una instalación monolítica en una PC doméstica (Intel i5 2014, 8 GB RAM, sin GPU) hasta una red distribuida de cámaras en un pueblo con un NVR central y edges ligeros (Raspberry Pi, Jetson Nano).

La arquitectura debe soportar **tipos de cámara heterogéneos**: estáticas, PTZ, 360° fisheye, térmicas, móviles y dual-chip con trigger externo. El núcleo no conoce el tipo de cámara; los preprocessors específicos se cargan como plugins encadenados.

La arquitectura no debe reescribirse para escalar; solo debe **cambiar de perfil**.

### 1.2 Patrón Arquitectónico Principal

**Modular Edge-First with Dual Event Bus**

Es una arquitectura híbrida que combina tres patrones según la capa:

| Capa | Patrón | Razón |
|------|--------|-------|
| **Núcleo / Orquestación** | Microkernel + Plugin Registry | Carga dinámica de detectores, OCRs, preprocessors y outputs según perfil de hardware. Un cambio de `EDGE_HOUSE` a `EDGE_NVR` es solo un cambio de configuración. |
| **Comunicación Inter-Plugin** | Event Bus (Local in-process -> MQTT distribuido) | Desacoplamiento total. Un plugin de detección de fuego puede coexistir con el de placas sin que ninguno conozca la existencia del otro. |
| **Procesamiento Interno de un Plugin** | Pipeline / Pipes-and-Filters (pragmático) | Dentro de un plugin de visión (ej. LPR), el flujo frame -> resize -> detect -> crop -> enhance -> OCR es secuencial y natural. Se usa numpy/OpenCV directamente sin mappers de dominio. |
| **Preprocesamiento de Cámara** | Chain of Responsibility | Cada cámara declara una cadena de preprocessors (ROI, dewarping, estabilización, compensación PTZ) que se ejecutan secuencialmente antes de que el frame llegue al detector. |

**No es Hexagonal pura.** En edge, convertir cada `np.ndarray` a entidades de dominio inmutables y mapear de vuelta introduce latencia y consumo de RAM inaceptables en hardware limitado. El dominio "conoce" numpy y OpenCV sin vergüenza porque es un sistema de visión por computadora, no un core bancario.

**No es Actor Model.** Python carece de un runtime de actores maduro y la serialización de frames entre actores mataría el rendimiento en un i5 de 4 núcleos.

---

## 2. DIAGRAMA DE COMPONENTES

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GRYPS PLATFORM                                  │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │   Stream    │    │   Stream    │    │   Stream    │    │   Stream    │   │
│  │  "cam_01"   │    │  "cam_02"   │    │  "cam_usb"  │    │  "file_01"  │   │
│  │  (RTSP)     │    │  (PTZ)      │    │  (USB)      │    │  (MP4)      │   │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘   │
│         │                  │                  │                  │            │
│         │    ┌─────────────┴──────────────────┴──────────────────┐            │
│         │    │              PREPROCESSORS CHAIN                  │            │
│         │    │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │            │
│         │    │  │ dewarp │ │  ROI   │ │  EIS   │ │  PTZ   │  │            │
│         │    │  │(fisheye│ │(static │ │(mobile │ │(comp.  │  │            │
│         │    │  │  only) │ │/poly/  │ │ only)  │ │ only)  │  │            │
│         │    │  │        │ │ motion)│ │        │ │        │  │            │
│         │    │  └────────┘ └────────┘ └────────┘ └────────┘  │            │
│         │    └─────────────────────────────────────────────────┘            │
│         │                  │                                                │
│         └──────────────────┴──────────────────┘                            │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        LOCAL EVENT BUS                              │   │
│  │   (In-process dict/callbacks en MVP; MQTT broker en distribuido)    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│         ┌──────────────┬───────────┴───────────┬──────────────┐             │
│         │              │                       │              │             │
│         ▼              ▼                       ▼              ▼             │
│  ┌─────────────┐ ┌─────────────┐       ┌─────────────┐ ┌─────────────┐    │
│  │  Plugin     │ │  Plugin     │       │  Plugin     │ │  Plugin     │    │
│  │  Vehicle    │ │  Person     │       │  Plate      │ │  Fire       │    │
│  │  Detector   │ │  Detector   │       │  OCR        │ │  Detector   │    │
│  │  (YOLO)     │ │  (YOLO)     │       │  (Paddle/   │ │  (ONNX)     │    │
│  │             │ │             │       │  Tesseract) │ │             │    │
│  └──────┬──────┘ └──────┬──────┘       └──────┬──────┘ └──────┬──────┘    │
│         │               │                     │               │           │
│         │               │                     │               │           │
│         └───────────────┴─────────────────────┴───────────────┘           │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        OUTPUT PLUGINS                               │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │   │
│  │  │ SQLite   │  │ Console  │  │ Telegram │  │ Webhook  │            │   │
│  │  │ Local    │  │ Logger   │  │ Bot      │  │ HTTP     │            │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    MICROKERNEL / CORE                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │   │
│  │  │   Config     │  │   Registry   │  │   Resource Monitor     │   │   │
│  │  │  Profiles    │  │  (Plugin     │  │  (CPU/RAM throttling,  │   │   │
│  │  │  Loader      │  │   Scanner)   │  │   frame drop, bus      │   │   │
│  │  └──────────────┘  └──────────────┘  │   health)              │   │   │
│  │                                        └──────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. ESTRUCTURA DE DIRECTORIOS

```
gryps/
├── README.md
├── pyproject.toml                  # uv/pip, dependencias por perfil
├── uv.lock
├── Makefile                        # lint, format, typecheck, test, check-all
├── .pre-commit-config.yaml
├── .python-version
├── .github/
│   └── workflows/ci.yml            # CI: ruff, mypy, pytest con cobertura
│
├── src/                            # Código fuente empaquetado (src layout)
│   └── gryps/                      # Paquete Python — evita imports accidentales del directorio raíz
│       ├── __init__.py             # Versión del paquete
│       ├── __main__.py             # Punto de entrada: python -m gryps
│       │
│       ├── config/                 # Perfiles de hardware y configuración
│       │   ├── __init__.py
│       │   ├── profiles.py         # EDGE_HOUSE, EDGE_NVR, EDGE_RPI, CLOUD_HUB
│       │   └── settings.yaml       # Overrides locales (no versionar)
│       │
│       ├── core/                   # Núcleo del Microkernel
│       │   ├── __init__.py
│       │   ├── bus.py              # Interfaz EventBus + implementaciones Local/MQTT/Redis
│       │   ├── registry.py         # PluginRegistry: descubre, valida, carga plugins
│       │   ├── resource_monitor.py # Throttling, frame drop, health checks, bus health
│       │   ├── pipeline_orchestrator.py  # Coordina streams -> preprocessors -> bus -> plugins
│       │   └── exceptions.py       # GrypsError, PluginLoadError, BusError, ConfigError
│       │
│       ├── streams/               # Fuentes de video (una instancia por cámara)
│       │   ├── __init__.py
│       │   ├── base.py            # StreamSource ABC
│       │   ├── file_stream.py     # Video MP4/AVI/MKV
│       │   ├── usb_stream.py      # Cámara USB (OpenCV VideoCapture)
│       │   ├── rtsp_stream.py     # Cámaras IP ONVIF/RTSP
│       │   ├── ptz_stream.py      # PTZ vía ONVIF (posición, control)
│       │   ├── fisheye_stream.py  # 360° con dewarping camera-side o VMS-side
│       │   ├── thermal_stream.py  # Térmica (solo metadatos, no frames visibles)
│       │   ├── mobile_stream.py   # USB + GPS + EIS
│       │   ├── triggered_stream.py # Loop/radar/láser + global shutter
│       │   └── frame_buffer.py    # Ring buffer para no bloquear el bus
│       │
│       ├── preprocessors/          # Plugins de transformación de frame (Chain of Responsibility)
│       │   ├── __init__.py
│       │   ├── base.py             # BasePreprocessorPlugin ABC
│       │   ├── roi/
│       │   │   ├── plugin.yaml
│       │   │   ├── static.py       # ROI rectangular/poligonal de archivo
│       │   │   ├── interactive.py  # Herramienta externa (no en edge)
│       │   │   ├── auto_motion.py  # Detección automática de zona de interés
│       │   │   └── ptz_compensated.py  # ROI recalculado según posición PTZ
│       │   ├── dewarp/
│       │   │   ├── plugin.yaml
│       │   │   ├── fisheye.py      # Proyección esférica a plana (K1-K3, P1-P2)
│       │   │   └── multi_view.py   # Extraer N vistas (norte, sur, este, oeste)
│       │   ├── stabilize/
│       │   │   ├── plugin.yaml
│       │   │   └── eis.py          # Electronic Image Stabilization (móvil)
│       │   └── trigger_sync/
│       │       ├── plugin.yaml
│       │       └── hardware_trigger.py  # Sincronización con loop/radar/láser
│       │
│       ├── plugins/                # Plugins de análisis (productores/consumidores de eventos)
│       │   ├── __init__.py
│       │   ├── base.py             # BasePlugin ABC + metadata
│       │   │
│       │   ├── detectors/          # Plugins productores de eventos
│       │   │   ├── __init__.py
│       │   │   ├── base.py         # BaseDetectorPlugin
│       │   │   └── vehicle_yolo/
│       │   │       ├── plugin.yaml
│       │   │       ├── detector.py
│       │   │       └── models/
│       │   │           └── yolo11n.pt
│       │   │
│       │   ├── ocr_backends/       # Plugins consumidores de PLATE_CROPPED / TRACK_LOST
│       │   │   ├── __init__.py
│       │   │   ├── base.py         # BaseOCRPlugin
│       │   │   ├── paddle/
│       │   │   │   ├── plugin.yaml
│       │   │   │   └── ocr.py
│       │   │   └── tesseract/
│       │   │       ├── plugin.yaml
│       │   │       └── ocr.py
│       │   │
│       │   └── outputs/            # Plugins consumidores finales
│       │       ├── __init__.py
│       │       ├── base.py         # BaseOutputPlugin
│       │       └── sqlite_local/
│       │           ├── plugin.yaml
│       │           └── output.py
│       │
│       ├── tracking/               # Lógica de estado temporal (servicio core, no plugin)
│       │   ├── __init__.py
│       │   ├── plate_tracker.py    # Mejor-frame + cache por track_id
│       │   ├── track_state.py      # Dataclasses de estado
│       │   └── ptz_track_mapper.py # Mapea coordenadas del frame a coordenadas del mundo
│       │
│       └── utils/
│           ├── __init__.py
│           ├── roi.py              # Dibujo, validación, serialización
│           ├── preprocess.py       # LAB+CLAHE, resize, binarización
│           ├── draw.py             # Dibujo OpenCV para visualización
│           ├── image_ops.py        # Dewarping, estabilización, transformaciones geométricas
│           └── calibration_tools.py # Herramientas para cálculo de parámetros intrínsecos
│
├── tools/                          # Utilidades de calibración (no parte del runtime edge)
│   ├── calibrate.py                # ROI picker interactivo con cv2.selectROI
│   ├── fisheye_calibrate.py        # Cálculo de K1-K3, P1-P2, centro óptico
│   ├── ptz_test.py                 # Prueba de conectividad ONVIF y posiciones
│   └── auto_roi.py                 # Análisis de movimiento para sugerir ROI
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│       ├── videos/
│       ├── images/
│       └── calibrations/           # YAML de ejemplo para tests
│
├── docs/
│   └── ARQUITECTURA.md             # Este documento
│
└── main.py                         # (legacy — redirige a gryps.__main__)
```

---

## 4. EL EVENT BUS — CONTRATO CENTRAL

El Event Bus es el **único mecanismo de comunicación** entre plugins. Ningún plugin importa a otro.

### 4.1 Interfaz

```python
# Conceptual — ver implementación en core/bus.py
class EventBus(ABC):
    def publish(self, event: Event) -> None: ...
    def subscribe(self, event_type: str, handler: Callable) -> Subscription: ...
    def unsubscribe(self, sub: Subscription) -> None: ...
```

### 4.2 Esquema de Eventos

Todo evento es inmutable y serializable (dict nativo de Python).

```python
Event {
    "event_id": uuid,
    "timestamp": float,           # time.time()
    "stream_id": str,             # "cam_front_porch"
    "frame_id": int,              # Contador monotónico del stream
    "event_type": str,            # VEHICLE_DETECTED | PLATE_READ | PERSON_DETECTED | FIRE_ALERT | PTZ_POSITION_CHANGED | EXTERNAL_TRIGGER | ...
    "payload": dict               # Datos específicos del evento
}
```

### 4.3 Vocabulario de Eventos (MVP)

| Evento | Productor | Payload clave | Consumidores |
|--------|-----------|---------------|--------------|
| `NEW_FRAME` | StreamSource (post-preprocessors) | `frame_ref`, `timestamp`, `resolution`, `preprocessors_applied` | Todos los detectores |
| `VEHICLE_DETECTED` | VehicleDetector | `track_id`, `bbox`, `class_name`, `confidence` | PlateDetector, Logger |
| `PLATE_CROPPED` | PlateDetector | `track_id`, `plate_bbox`, `crop_ref`, `vehicle_bbox` | OCRBackend |
| `PLATE_READ` | OCRBackend | `track_id`, `plate_text`, `confidence`, `best_frame_id` | SQLite, Logger, Telegram |
| `TRACK_LOST` | PlateTracker | `track_id`, `last_seen`, `reason`, `best_plate_crop_ref` | OCRBackend (trigger final), SQLite |
| `PTZ_POSITION_CHANGED` | PTZStream | `pan`, `tilt`, `zoom`, `timestamp` | PTZCompensatedROI, Logger |
| `EXTERNAL_TRIGGER` | TriggerSyncPreprocessor | `trigger_type`, `gpio_pin`, `timestamp` | StreamSource (burst capture) |
| `SYSTEM_ALERT` | ResourceMonitor | `level`, `message`, `metric`, `stream_id` | Console, Telegram |

### 4.4 Implementaciones Swappable

| Implementación | Modo | Latencia | Uso | Requiere |
|----------------|------|----------|-----|----------|
| `LocalEventBus` | Dict de callbacks in-process | 0 ms (llamada directa) | MVP casa, 1-4 cámaras | Nada |
| `MQTTEventBus` | Cliente Paho-MQTT | 1-5 ms (broker local) | Pueblo, edges + NVR central | Broker Mosquitto |
| `RedisEventBus` | Redis Pub/Sub | 1-3 ms | Cloud hub, agregación multi-pueblo | Servidor Redis |

**Cambiar de bus es una línea en `config/settings.yaml`:**
```yaml
bus:
  type: local          # local | mqtt | redis
  # mqtt:
  #   broker: 192.168.1.100
  #   port: 1883
```

---

## 5. PREPROCESSORS — CHAIN OF RESPONSIBILITY

Los preprocessors transforman el frame antes de que llegue al detector. Se declaran por stream y se ejecutan secuencialmente.

### 5.1 Interfaz

```python
class BasePreprocessorPlugin(ABC):
    @abstractmethod
    def process(self, frame: np.ndarray, metadata: dict) -> Tuple[np.ndarray, dict]:
        # Retorna frame transformado y metadata enriquecida
        pass

    @property
    @abstractmethod
    def modifies_geometry(self) -> bool:
        # True si cambia coordenadas (dewarping, PTZ compensation).
        # Los detectores deben saberlo para ajustar bounding boxes.
        pass
```

### 5.2 Cadena por Tipo de Cámara

| Tipo de Cámara | Cadena de Preprocessors | Restricción de Perfil |
|----------------|------------------------|----------------------|
| **Estática** | `roi_static` | Ninguna |
| **PTZ** | `ptz_compensated_roi` | `EDGE_NVR` mínimo |
| **360° Fisheye** | `dewarp_fisheye` -> `multi_view` -> `roi_static_per_view` | `EDGE_NVR` mínimo (dewarping CPU intensivo) |
| **Térmica** | `thermal_normalization` (contrast enhancement) | Ninguna (pero no hace LPR) |
| **Móvil** | `eis_stabilize` -> `roi_auto_motion` | `EDGE_RPI` móvil con acelerador |
| **Dual-Chip Trigger** | `trigger_sync` -> `roi_static` | `EDGE_NVR` + hardware GPIO |

### 5.3 Configuración por Stream

```yaml
streams:
  - id: "cam_plaza"
    type: fisheye
    source: "rtsp://192.168.1.12/stream1"
    preprocessors:
      - name: dewarp
        params:
          cx: 960
          cy: 540
          r: 900
          k1: -0.3
          k2: 0.1
          views: ["north", "south", "east", "west"]
          fov: 90
      - name: roi
        params:
          mode: static_per_view
          views:
            north: [100, 50, 400, 300]
            south: [100, 50, 400, 300]
            east: [50, 100, 300, 400]
            west: [50, 100, 300, 400]
```

### 5.4 Validación al Arranque

El `PipelineOrchestrator` valida la cadena antes de iniciar el stream:
- ¿Todos los preprocessors declarados existen como plugins? Si no -> error claro.
- ¿El perfil de hardware soporta este preprocessor? Si no -> error con sugerencia de perfil.
- ¿Los parámetros son válidos (ej. `cx`, `cy` dentro del frame)? Si no -> error con rango esperado.

---

## 6. PLUGIN REGISTRY — CICLO DE VIDA

### 6.1 Descubrimiento

El `PluginRegistry` escanea `plugins/` y `preprocessors/` al iniciar. Cada plugin debe contener `plugin.yaml`:

```yaml
name: vehicle_yolo
version: 1.0.0
type: detector              # detector | ocr | output | preprocessor
category: analysis          # analysis | preprocessing | output
entrypoint: detector.py     # Módulo Python relativo
class: VehicleYOLOPlugin    # Clase a instanciar

# Contrato de eventos
events_produced:
  - VEHICLE_DETECTED
events_consumed:
  - NEW_FRAME

# Recursos
models:
  - models/yolo11n.pt

# Requisitos de hardware (para filtrado por perfil)
min_ram_mb: 512
min_cpu_cores: 2
preferred_backend: [onnx, openvino]   # Orden de preferencia

# Restricciones de tipo de cámara
supported_camera_types: [static, ptz, fisheye, mobile, triggered]
unsupported_camera_types: [thermal]   # O lista vacía si todas

# Preprocessors requeridos (para detectores)
required_preprocessors: [roi]
```

### 6.2 Filtrado por Perfil y Tipo de Cámara

El `Registry` filtra plugins según el perfil activo Y el tipo de cámara del stream:

```python
# Pseudocódigo del Registry
def load_for_stream(stream_config: StreamConfig, profile: Profile) -> List[BasePlugin]:
    candidates = scan_directories(["plugins/", "preprocessors/"])
    for p in candidates:
        # Filtro hardware
        if p.min_ram_mb > available_ram:
            log.warning(f"Plugin {p.name} omitido: RAM insuficiente")
            continue
        if p.name not in profile.enabled_plugins:
            log.info(f"Plugin {p.name} deshabilitado por perfil")
            continue

        # Filtro tipo de cámara
        if stream_config.type not in p.supported_camera_types:
            log.warning(f"Plugin {p.name} no soporta cámara {stream_config.type}")
            continue

        # Validar preprocessors requeridos
        for req in p.required_preprocessors:
            if req not in [pp.name for pp in stream_config.preprocessors]:
                log.error(f"Plugin {p.name} requiere preprocessor '{req}' no declarado")
                raise ConfigError(...)

        yield p.load()
```

### 6.3 Aislamiento de Fallos

Si un plugin crashea (excepción no manejada), el Registry:
1. Captura la excepción.
2. Loguea el error con stack trace.
3. Marca el plugin como `FAILED`.
4. **No reinicia el sistema.** Los demás plugins continúan.
5. Reintenta cargar el plugin en el siguiente ciclo de health-check (configurable).
6. Si el stream queda sin plugins funcionales, se marca como `DEGRADED` y se notifica vía `SYSTEM_ALERT`.

---

## 7. FLUJO DE DATOS FRAME A FRAME (MVP — Cámara Estática)

```
Frame N desde StreamSource (RTSP/USB/File)
│
├─► Preprocessor: ROI Static (recorte del frame)
│   └─► Frame recortado + metadata {roi_applied: [x,y,w,h]}
│
├─► LocalEventBus.publish(NEW_FRAME {frame_ref, metadata})
│
├─► VehicleYOLOPlugin.consume(NEW_FRAME)
│   ├─► YOLO11n inference (imgsz=320 o 640 según perfil)
│   ├─► Tracking (BoT-SORT vía Ultralytics)
│   └─► Por cada vehículo detectado:
│       └─► Bus.publish(VEHICLE_DETECTED {track_id, bbox, ...})
│
├─► PlateDetectorPlugin.consume(VEHICLE_DETECTED)
│   ├─► Crop del vehículo del frame original (usando bbox + ROI offset)
│   ├─► YOLO `l.pt` inference sobre crop
│   ├─► PlateTracker.evaluate_plate(track_id, crop, bbox)
│   │   ├─► ¿Área > min_area? Sí -> guardar como candidato
│   │   └─¿Es mejor que el anterior? Sí -> reemplazar
│   └─► Si placa detectada:
│       └─► Bus.publish(PLATE_CROPPED {track_id, crop_ref, ...})
│
├─► PlateTracker.consume(VEHICLE_DETECTED | TRACK_LOST)
│   ├─► ¿Vehículo desapareció de la ROI?
│   │   └─► Sí -> Bus.publish(TRACK_LOST {track_id, best_plate_crop_ref})
│   └─► ¿Timeout (X segundos sin mejorar)?
│       └─► Sí -> Bus.publish(TRACK_LOST {track_id, reason: timeout})
│
├─► OCRBackend.consume(TRACK_LOST)        # OCR al desaparecer
│   ├─► Recupera mejor crop del PlateTracker
│   ├─► Preprocesamiento (LAB+CLAHE o skip según perfil)
│   ├─► PaddleOCR.predict() o Tesseract.image_to_string()
│   └─► Bus.publish(PLATE_READ {track_id, plate_text, confidence})
│
├─► SQLiteOutput.consume(PLATE_READ)
│   └─► INSERT INTO events (...)
│
└─► ConsoleOutput.consume(PLATE_READ | SYSTEM_ALERT)
    └─► print(f"[ID {tid}] Placa: {text}")
```

**Nota clave:** El OCR no corre en cada frame. Corre **una vez por vehículo**, cuando el `PlateTracker` decide que ya no hay mejores frames disponibles (desaparición o timeout).

---

## 8. PERFILES DE HARDWARE

Los perfiles son objetos inmutables que configuran todo el sistema. No hay lógica condicional esparcida en el código; solo una tabla de lookup.

| Perfil | Hardware objetivo | Plugins típicos | Preprocessors soportados | Bus | Resolución | Skip | OCR |
|--------|-------------------|-----------------|-------------------------|-----|------------|------|-----|
| `EDGE_HOUSE` | PC vieja, i5 2014, 8 GB, sin GPU | VehicleYOLO, PlateYOLO, TesseractOCR, SQLite, Console | `roi_static`, `roi_auto_motion` | Local | 640×480 | 3 | Tesseract |
| `EDGE_RPI` | Raspberry Pi 4/5, 4 GB | VehicleYOLO-nano, PlateYOLO-nano, TesseractOCR, MQTT-Pub | `roi_static`, `eis_stabilize` | Local | 480×360 | 5 | Tesseract (no CLAHE) |
| `EDGE_NVR` | Xeon/i7 moderno, 16 GB | VehicleYOLO-s, PlateYOLO, PaddleOCR, PostgreSQL, MQTT-Broker | Todos: `roi_*`, `dewarp_*`, `ptz_*`, `trigger_*` | MQTT local | 1280×720 | 1 | Paddle |
| `CLOUD_HUB` | Servidor cloud, GPU opcional | Agregadores, Dashboard, Analytics | N/A (recibe eventos, no frames) | Redis/MQTT | N/A | N/A | N/A |

**Ejemplo de activación:**
```python
# main.py
from config.profiles import EDGE_HOUSE
from core.pipeline_orchestrator import PipelineOrchestrator

profile = EDGE_HOUSE
orchestrator = PipelineOrchestrator(profile)
orchestrator.run()
```

---

## 9. DECISIONES ARQUITECTÓNICAS Y TRADE-OFFS

### ADR-001: No usar Arquitectura Hexagonal pura en el edge

**Contexto:** Se evaluó Hexagonal / Clean Architecture para desacoplar completamente el dominio de OpenCV/numpy.

**Decisión:** Rechazada para la capa de procesamiento de video. Se adopta una "Pipeline Pragmática" dentro de cada plugin de visión.

**Razón:** Mapear cada `np.ndarray` (frame de 1920×1080×3 ≈ 6 MB) a entidades de dominio puras y de vuelta a numpy introduce latencia de 10-30 ms por frame y duplica el consumo de RAM. En un edge con 8 GB y sin GPU, eso es el 20 % del presupuesto de memoria.

**Consecuencia:** Los plugins de visión trabajan directamente con numpy. La testeabilidad se logra mediante extracción de utilidades puras (`utils/preprocess.py`) y tests de integración con fixtures de video cortos.

---

### ADR-002: Event Bus in-process (local) como default

**Contexto:** Se evaluó usar MQTT desde el MVP para "pensar en grande".

**Decisión:** El bus default es un diccionario de callbacks en memoria (`LocalEventBus`). MQTT es una implementación swappable que se activa por configuración.

**Razón:** MQTT introduce dependencia de broker, latencia de red (incluso localhost) y complejidad de deployment. Para una casa con 1-4 cámaras, es overkill. Para un pueblo, es esencial.

**Consecuencia:** El código del núcleo nunca asume que el bus es local o remoto. Todos los eventos son serializables desde el día 1.

---

### ADR-003: OCR diferido (mejor-frame) vs OCR inmediato

**Contexto:** ¿Hacer OCR en el primer frame donde aparece la placa, o esperar al mejor frame?

**Decisión:** OCR diferido con estrategia de "mejor frame" por área.

**Razón:** En el primer frame un vehículo puede estar lejano, borroso o de perfil. Esperar al frame de máxima área de placa aumenta la precisión de OCR del 60 % al 85 %+ en pruebas. Además, reduce la carga de CPU al ejecutar OCR una sola vez por vehículo.

**Consecuencia:** Se requiere un `PlateTracker` con estado temporal (cache de crops por `track_id`). Esto añade complejidad de memoria: los crops se mantienen en RAM hasta que el vehículo desaparece. Se mitiga con un timeout configurable (ej. 10 segundos máximo).

---

### ADR-004: SQLite como base default, no PostgreSQL en MVP

**Contexto:** Se necesita persistencia local ligera.

**Decisión:** SQLite en MVP. PostgreSQL en `EDGE_NVR` y superiores.

**Razón:** SQLite no requiere servidor, ocupa < 1 MB de RAM y es suficiente para miles de eventos diarios. PostgreSQL añade proceso daemon, mantenimiento y configuración de red innecesarios en una casa.

**Consecuencia:** El plugin `sqlite_local` y el futuro `postgresql` comparten una interfaz `BaseStoragePlugin`. La migración es transparente.

---

### ADR-005: Ultralytics como framework de detección, no Detectron2 ni MMDetection

**Contexto:** Se evaluaron múltiples frameworks de detección.

**Decisión:** Ultralytics YOLOv8/YOLO11 para todo.

**Razón:** Ultralytics ofrece exportación nativa a ONNX, OpenVINO, TensorRT y CoreML con una línea de código (`model.export()`). Tiene tracking integrado (BoT-SORT). Es la opción con menor fricción para edge. Detectron2 es pesado y depende de PyTorch con CUDA; MMDetection tiene curva de aprendizaje alta.

**Consecuencia:** Estamos atados al ecosistema Ultralytics. Si el proyecto fracasa o cambia de licencia, deberemos migrar. Mitigación: los plugins de detector implementan `BaseDetectorPlugin`, no importan Ultralytics directamente en el core.

---

### ADR-006: No soportar dewarping en `EDGE_HOUSE`

**Contexto:** El dewarping de 360° consume ~30–50 % de una CPU de 4 núcleos.

**Decisión:** El preprocessor `dewarp` rechaza cargarse en perfiles `EDGE_HOUSE` y `EDGE_RPI`. Lanza error claro: *"Dewarping requiere EDGE_NVR mínimo. Considere cámara con dewarping camera-side."*

**Consecuencia:** Los usuarios de hardware limitado deben comprar cámaras con dewarping integrado o usar cámaras estáticas múltiples.

---

### ADR-007: El plugin térmico nunca publica `PLATE_READ`

**Contexto:** Los usuarios podrían esperar que una cámara térmica lea placas.

**Decisión:** El plugin `thermal_detector` solo publica `VEHICLE_DETECTED` con `has_plate: false`. Si no hay cámara visible emparejada, el evento se registra sin placa. No se intenta OCR sobre imagen térmica.

**Consecuencia:** Requiere documentación clara y validación de configuración al arranque (warning si hay térmica sin visible emparejada).

---

### ADR-008: PTZ en modo "patrullaje" por defecto, no tracking continuo

**Contexto:** El tracking continuo con PTZ introduce latencia mecánica y pérdida de IDs.

**Decisión:** El modo default de `ptz_controller` es `patrol` (posiciones predefinidas con dwell time). El modo `track` requiere explícito `mode: track` y un perfil `EDGE_NVR`.

**Consecuencia:** Mejor precisión de LPR a costa de no seguir vehículos en movimiento. El modo `track` es experimental y documentado como tal.

---

### ADR-009: Preprocessors como plugins de primera clase

**Contexto:** ¿Dónde vive la lógica de dewarping, EIS, compensación PTZ? ¿En el stream? ¿En el detector?

**Decisión:** Los preprocessors son plugins independientes en `preprocessors/`, con su propio `plugin.yaml`, ciclo de vida y registro en el PluginRegistry. Se declaran por stream y se encadenan.

**Razón:** Un dewarping de 360° no es propiedad del stream (el stream solo entrega bytes) ni del detector (el detector no debe saber de lentes fisheye). Es una transformación intermedia reusable. Además, permite que el mismo detector trabaje sobre frames de cualquier tipo de cámara sin modificaciones.

**Consecuencia:** Mayor complejidad de configuración por stream. Mitigación: templates de configuración por tipo de cámara (`templates/camera_static.yaml`, `templates/camera_fisheye.yaml`).

---

### ADR-010: Herramientas de calibración fuera del runtime edge

**Contexto:** ¿Cómo calibrar ROI, dewarping, PTZ sin monitor en el edge?

**Decisión:** Toda interacción gráfica (`cv2.selectROI`, visualización de dewarping, prueba de posiciones PTZ) vive en `tools/`, no en el runtime. Son scripts que el técnico ejecuta en su laptop, generan YAML, y suben al edge vía SCP/SSH/OTA.

**Razón:** El edge debe ser 100 % headless. Abrir ventanas X11/Wayland en un servidor remoto es frágil (requiere forwarding, dependencias Qt, resolución de display). Es un anti-patrón de DevOps.

**Consecuencia:** El flujo de instalación requiere un paso manual o semi-automático: técnico calibra en laptop -> sube YAML -> edge arranca. Para auto-calibración, ver `tools/auto_roi.py`.

---

## 10. SEGURIDAD Y PRIVACIDAD EN LA ARQUITECTURA

| Capa | Medida |
|------|--------|
| **Ingesta** | Las cámaras se conectan vía RTSP sobre red local o VPN. No se expone el stream a internet. Las cámaras móviles usan VPN móvil o almacenamiento local con sync diferido. |
| **Preprocesamiento** | El dewarping, EIS y compensación PTZ ocurren en el edge. Ningún frame en crudo sale del dispositivo. |
| **Procesamiento** | Todo el análisis de IA ocurre en el edge. Los frames en crudo **nunca** salen del dispositivo. |
| **Eventos** | El bus solo transmite metadatos (bbox, texto, timestamp). Los crops de placas se guardan opcionalmente en disco local con rotación. Los eventos MQTT/Redis viajan cifrados (TLS). |
| **Persistencia** | SQLite es un archivo local con permisos `600`. No hay credenciales hardcodeadas. PostgreSQL usa conexiones TLS con certificados de cliente. |
| **Retención** | Plugin `retention_manager` (Post-MVP) auto-borra registros e imágenes > N días según GDPR/local. |
| **Rostros** | El sistema **no** almacena ni procesa rostros de conductores ni peatones. Los crops son de placas únicamente. El detector de personas (Post-MVP) publica metadatos (bbox, timestamp) pero no guarda imagen del peatón. |
| **Integridad** | Hash SHA-256 de archivos del núcleo al arranque. Si un técnico modifica el código para guardar rostros, el sistema detecta la alteración y se niega a iniciar. |

---

## 11. ROADMAP DE EVOLUCIÓN ARQUITECTÓNICA

> La trazabilidad a historias de usuario (→ HU-NNN) indica qué requerimientos cubre cada entregable.

### Fase 1: MVP Casa (Semanas 1-8) [→ HU-001..HU-007, HU-009..HU-012, HU-017, HU-020, HU-023..HU-025, HU-028]
- `LocalEventBus` implementado. [→ HU-017, HU-025]
- Preprocessors: `roi_static`, `roi_auto_motion`. [→ HU-002]
- Plugins: `vehicle_yolo`, `plate_yolo`, `tesseract_ocr`, `sqlite_local`, `console_logger`. [→ HU-001, HU-005, HU-007, HU-009, HU-012]
- Perfil `EDGE_HOUSE` funcional en i5 2014. [→ HU-003]
- Tracking de mejor-frame y cache por `track_id`. [→ HU-006, HU-010, HU-011]
- Herramienta `tools/calibrate.py` para ROI interactivo en laptop. [→ HU-002]
- **Tipos de cámara soportados:** estática, USB, RTSP, archivo. [→ HU-001, HU-004]
- **Persistencia:** SQLite local. [→ HU-020]

### Fase 2: Residencial Multi-Cámara (Meses 3-6) [→ HU-008, HU-014, HU-018, HU-019, HU-021, HU-026, HU-027]
- Soporte para 2-4 cámaras simultáneas en un mismo edge.
- Preprocessor `dewarp_fisheye` para cámaras 360° (extraer 4 vistas planas). [→ HU-014]
- Preprocessor `ptz_compensated_roi` para PTZ en modo patrullaje. [→ HU-008]
- Perfil `EDGE_NVR` con PostgreSQL local.
- Plugin detector de personas como plugin adicional. [→ HU-023]
- Alertas por Telegram bot. [→ HU-019]
- Lista blanca/negra de placas con alerta inmediata. [→ HU-018]
- Dashboard web ligero (FastAPI) para consulta de eventos. [→ HU-026]
- Auto-borrado y retención de datos. [→ HU-027]
- Exportación CSV de frecuencia. [→ HU-021]
- **Tipos de cámara nuevos:** 360° fisheye, PTZ.

### Fase 3: Seguridad de Pueblo (Meses 6-12) [→ HU-013, HU-015, HU-016, HU-022, HU-025]
- Arquitectura distribuida: edges ligeros (Raspberry Pi / Jetson Nano) por esquina + NVR central.
- Soporte cámara térmica como detector de intrusión (sin LPR), trigger para cámara visible emparejada. [→ HU-015]
- Cámara móvil/vehicular con GPS integrado y estabilización EIS. [→ HU-013]
- Event Bus vía MQTT con broker local en el NVR. [→ HU-025]
- Panel central web con mapa de cámaras, búsqueda cross-cámara y análisis de patrones. [→ HU-022]
- Nuevos detectores: fuego/humo, objetos abandonados, conteo de afluencia peatonal.
- Integración con sistemas de emergencia (webhook a bomberos/policía).
- Soporte para cámaras con trigger externo (loop inductivo, radar) para alta velocidad. [→ HU-016]
- **Tipos de cámara nuevos:** térmica, móvil, dual-chip triggered.

### Fase 4: Inteligencia Predictiva (12+ meses)
- Análisis de patrones: "este vehículo visita cada martes a las 10 PM".
- Reconocimiento de comportamiento anómalo (circular en círculos, detención prolongada).
- Integración con bases de datos vehiculares oficiales (donde la legislación lo permita).
- App móvil para residentes con notificaciones push.
- Auto-calibración de ROI basada en análisis de tráfico histórico.
- **Tipos de cámara nuevos:** cámaras estéreo (profundidad), cámaras event-based (neuromórficas).

---

## 12. RIESGOS Y BRECHAS DE DECISIÓN

### 12.1 Riesgos Técnicos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| **Rendimiento no validado en arquitectura completa** — Las métricas objetivo (5 FPS en i5 2014) se basan en prototipos aislados, no en el pipeline completo con Event Bus, preprocessors y plugins simultáneos. | Alto: el MVP podría no alcanzar FPS objetivo con la sobrecarga de la arquitectura de plugins. | Implementar el pipeline completo temprano y medir. Tener YOLO-nano y skip=5 como plan de contingencia. |
| **Dependencia de Ultralytics** — ADR-005 documenta el riesgo. Si Ultralytics cambia licencia o descontinúa YOLO11, el núcleo queda expuesto. | Medio: migración a ONNX Runtime directo es posible pero costosa. | Mantener abstracción `BaseDetectorPlugin`. No importar Ultralytics fuera de plugins de detector. |
| **GIL de Python para multi-cámara** — El procesamiento de N streams en un solo proceso está limitado por el GIL. | Bajo en MVP (1 cámara); Alto en Fase 2 (4+ cámaras). | MVP es single-stream. Para Fase 2, evaluar multiprocessing con streams en procesos separados + EventBus como IPC. Decisión postergada (ver §12.2). |
| **Consumo de RAM del PlateTracker** — Cachear crops de múltiples vehículos simultáneos puede agotar 8 GB en zona de alto tráfico. | Medio: timeout mal configurado + alta concurrencia = OOM. | Timeout configurable por track (default 10 s). Limitar crops a 80×40 px. Monitorear heap size. |
| **Modelos de IA sin pipeline de actualización** — No hay mecanismo para reentrenar o actualizar modelos (YOLO, l.pt) sin intervención manual. | Medio: los modelos existentes pueden volverse obsoletos para ciertas regiones. | Documentar como deuda técnica. Evaluar `model download` command + hash verification en Fase 2. |
| **Sin tests ni tooling de calidad** — No existe test runner, linter, type checker ni formatter. El riesgo de regresión es máximo desde el primer commit. | Crítico: sin calidad desde el inicio, la deuda técnica se acumula irreversiblemente. | Implementar tooling antes del primer feature. Ver `docs/DESARROLLO.md`. |

### 12.2 Brechas de Decisión (ADR Pendientes)

| Decisión | Contexto | Propuesta | Bloquea a |
|----------|----------|-----------|-----------|
| **Formato de serialización de eventos** | Los eventos deben ser serializables desde el día 1 (ADR-002). ¿JSON, MessagePack, Protobuf? | JSON para MVP (simple, debuggable). MessagePack si latencia es problema. | HU-025 |
| **Estrategia de multiprocesamiento** | ¿Cómo escalar a N streams sin que el GIL limite? ¿Threading? ¿Multiprocessing + pipes? ¿Asyncio? | No decidido. MVP es single-stream. Documentar como deuda técnica para Fase 2. | Fase 2 |
| **Ubicación del PlateTracker** | ¿Debe ser plugin o servicio core como está diseñado? | Se definió como servicio core (`tracking/`). Reevaluar si se vuelve complejo. | HU-010, HU-011 |
| **Formato de imágenes almacenadas** | Crops de placas: ¿PNG, JPEG, WebP? ¿Calidad fija o adaptativa? | JPEG calidad 85 como default. Postergar hasta implementar SQLite output. | HU-020 |
| **Estrategia de logging** | ¿Logging estructurado (JSON/structlog) o texto plano? ¿Rotación? | No decidido. Python logging + RotatingFileHandler como base. | — |
| **CI/CD pipeline** | ¿Qué proveedor? ¿Cuándo configurarlo? ¿Tests en cada PR? | GitHub Actions + pytest + ruff + mypy desde el primer commit. | Todo el desarrollo |

---

## 13. GLOSARIO ARQUITECTÓNICO

| Término | Significado |
|---------|-------------|
| **ADR** | Architecture Decision Record. Documento que registra por qué se tomó una decisión técnica. |
| **Bus** | Event Bus. Canal de comunicación desacoplado entre plugins. |
| **Chain of Responsibility** | Patrón donde una solicitud pasa por una cadena de handlers hasta que uno la procesa. En Gryps: los preprocessors forman una cadena sobre cada frame. |
| **Dewarping** | Corrección de distorsión de lentes ultra-wide (fisheye/360°) para obtener vistas planas usables. |
| **EIS** | Electronic Image Stabilization. Tecnología para compensar vibración en cámaras móviles. |
| **Edge** | Dispositivo de computación local (PC, NUC, Raspberry Pi) donde corre el procesamiento de video, opuesto a "cloud". |
| **Evento** | Mensaje inmutable que circula por el bus, con tipo, timestamp y payload. |
| **Global Shutter** | Sensor que expone todos los píxeles simultáneamente, eliminando deformación en objetos en movimiento rápido. |
| **Mejor-frame** | Estrategia de esperar al frame de máxima calidad de placa antes de ejecutar OCR. |
| **Microkernel** | Núcleo mínimo que carga, coordena y monitorea plugins sin conocer su lógica interna. |
| **ONVIF** | Open Network Video Interface Forum. Estándar para comunicación entre cámaras IP y sistemas de vigilancia. |
| **Perfil** | Configuración inmutable que define qué plugins, resoluciones, buses y tipos de cámara usar según hardware. |
| **Plugin** | Módulo de software independiente que se carga dinámicamente para extender funcionalidad sin modificar el núcleo. |
| **Preprocessor** | Plugin de transformación de frame que se ejecuta antes del detector (dewarping, ROI, estabilización, etc.). |
| **PTZ** | Pan-Tilt-Zoom. Cámara motorizada controlable remotamente. |
| **Registry** | Componente que escanea, valida e instancia plugins al arranque. |
| **ROI** | Region of Interest. Área rectangular o poligonal dentro del frame de video donde se restringe el análisis para ahorrar recursos. |
| **RTSP** | Real Time Streaming Protocol. Protocolo estándar para transmitir video en tiempo real desde cámaras IP. |
| **Stream** | Fuente continua de frames: archivo, cámara USB, stream de red, o vista dewarped de una 360°. |
| **Track ID** | Identificador único numérico asignado a un objeto (vehículo, persona) para seguirlo a través de múltiples frames. |
| **YOLO** | You Only Look Once. Familia de modelos de detección de objetos en tiempo real. |

---

> *"La arquitectura no predice el futuro; solo lo deja entrar sin romper el presente."*
