# Cuaderno de Estudio — Gryps

Este cuaderno acompaña la implementación de Gryps con notas pensadas para estudiar y enseñar. No reemplaza la arquitectura ni la documentación de desarrollo: explica los conceptos usados, por qué se eligieron y qué preguntas conviene hacerle a estudiantes.

---

## Slice 0.3 — `Event` + `EventBus`

### Qué problema resuelve

El sistema necesita que módulos como cámaras, detectores, OCR y salidas se comuniquen sin depender directamente unos de otros.

Sin un bus, el flujo terminaría acoplado:

```text
Detector → OCR → SQLite → Telegram
```

Con un Event Bus, cada componente publica hechos y otros componentes deciden si les interesan:

```text
Detector → EventBus → Suscriptores interesados
```

Esto permite agregar, quitar o cambiar módulos sin reescribir toda la cadena.

### Conceptos usados

| Concepto | Qué significa en Gryps |
|----------|-------------------------|
| Event-driven architecture | El sistema reacciona a eventos como `NEW_FRAME`, `VEHICLE_DETECTED` o `PLATE_READ`. |
| Publish/subscribe | Un componente publica un evento; otros se suscriben al tipo de evento que les interesa. |
| `dataclass(frozen=True)` | Evita reasignar campos del evento después de crearlo. |
| Inmutabilidad superficial | El evento no permite cambiar campos, pero el `payload` es un `dict` y sus contenidos pueden mutarse si alguien lo hace mal. |
| Abstract Base Class | `EventBus` define el contrato que toda implementación futura debe cumplir. |
| Serialización | `Event.to_dict()` y `Event.from_dict()` convierten eventos a estructuras nativas de Python. |

### Código relacionado

- `src/gryps/core/bus.py` — define `Event`, `Subscription`, `EventBus`, `Payload` y `EventHandler`.
- `src/gryps/core/__init__.py` — expone la API pública de `gryps.core`.
- `tests/unit/test_bus.py` — prueba creación, validación, serialización, inmutabilidad superficial y contrato abstracto.

### Modelo mental

Un evento es una frase estructurada:

```text
En el stream cam_01, frame 42, ocurrió VEHICLE_DETECTED con estos datos.
```

En código:

```python
from gryps.core import Event

event = Event.create(
    stream_id="cam_01",
    frame_id=42,
    event_type="VEHICLE_DETECTED",
    payload={
        "track_id": "vehicle_123",
        "bbox": [10, 20, 200, 120],
        "confidence": 0.91,
    },
)
```

El detector no sabe quién escuchará ese evento. Solo publica un hecho. Después, OCR, logger, SQLite o Telegram pueden reaccionar si están suscritos.

### Decisiones importantes

1. **No pasar frames por el bus.**
   El bus transporta metadatos o referencias, no imágenes pesadas ni `numpy.ndarray`. Esto protege memoria y latencia en hardware edge.

2. **Primero contrato, después implementación.**
   En 0.3 se define `EventBus`, pero todavía no existe `LocalEventBus`. Eso llega en 0.4. Separar contrato de implementación permite cambiar el transporte más adelante.

3. **Payload mutable por convención.**
   `Event` es frozen, pero `payload` es un diccionario. Los handlers no deben mutarlo. Si un handler modifica el payload, puede afectar a otros suscriptores que reciben el mismo evento.

4. **Serialización nativa.**
   `to_dict()` y `from_dict()` usan estructuras simples de Python para facilitar logs, persistencia futura o transporte por MQTT/Redis.

### Qué todavía no hace

Este slice no publica eventos reales. Todavía no existe una implementación concreta del bus.

Eso significa que todavía no podemos hacer:

```text
publish → ejecutar handlers suscritos
```

Eso corresponde al Slice 0.4 (ya implementado): `LocalEventBus`.

### Preguntas para estudiantes

- ¿Qué problema aparece si `Detector` llama directamente a `OCR`?
- ¿Por qué conviene publicar eventos en lugar de llamar módulos concretos?
- ¿Por qué el bus no debería transportar imágenes completas?
- ¿Qué diferencia hay entre inmutabilidad superficial e inmutabilidad profunda?
- ¿Por qué definir primero una interfaz puede facilitar cambios futuros?

### Ejercicio sugerido

Crear un evento manualmente y serializarlo:

```python
from gryps.core import Event

event = Event.create(
    stream_id="cam_01",
    frame_id=1,
    event_type="NEW_FRAME",
    payload={"frame_ref": "frames/cam_01/000001.jpg"},
)

data = event.to_dict()
copy = Event.from_dict(data)

assert copy == event
```

La pregunta clave del ejercicio no es “¿funciona?”, sino: **¿qué ventajas tiene que este mensaje sea serializable y no dependa de una clase concreta de detector?**

---

## Slice 0.4 — `LocalEventBus` (implementación in-process)

### Qué problema resuelve

El Slice 0.3 definió el contrato (`EventBus` ABC), pero no había código que realmente publicara eventos y llamara a handlers. `LocalEventBus` es esa implementación concreta, diseñada para correr en el mismo proceso, sin red, sin hilos, sin colas.

### Cómo funciona

```python
from gryps.core import LocalEventBus, Event

bus = LocalEventBus()
received = []

bus.subscribe("NEW_FRAME", received.append)
bus.publish(Event.create(stream_id="cam_01", frame_id=1, event_type="NEW_FRAME"))

assert len(received) == 1
```

El bus mantiene un `dict[str, list[Subscription]]`. Cuando se publica un evento:
1. Busca el `event_type` en el diccionario.
2. Itera los suscriptores de ese tipo.
3. Llama a cada handler con el evento.

Es sincrónico: `publish()` no retorna hasta que todos los handlers terminaron (o uno lanza excepción).

### Decisión de diseño: excepciones visibles

Un handler que falla **propaga la excepción al llamador de `publish`**. No se traga silenciosamente. Esto es intencional para MVP: si algo falla, queremos saberlo ya, no descubrirlo horas después cuando los logs están llenos de errores silenciados.

Consecuencias:
- Los handlers deben ser responsables de sus propios try/except si quieren aislar fallos.
- El bus no es tolerante a fallos de handlers individuales por sí mismo (el `PluginRegistry` en 0.5 añadirá aislamiento).
- Si un handler falla, los handlers posteriores del mismo evento NO se ejecutan (el orden de suscripción importa).

### Por qué es sincrónico y sin colas

| Alternativa | Costo para MVP |
|-------------|----------------|
| Hilo por handler | Overhead de thread pool, sincronización, debugging complejo |
| Cola asincrónica | Dependencia de `asyncio`, latencia no determinística, testing más complejo |
| Ejecución diferida | Dificulta razonar sobre el orden de eventos |
| **Sincrónico directo** (elegido) | Simple, determinístico, fácil de testear |

En MVP (1 cámara, pocos plugins), la latencia de cada handler es el cuello de botella, no el dispatch. Si un detector tarda 200ms por frame, la llamada directa vs cola es irrelevante.

### Por qué es solo para MVP

El `LocalEventBus` no escala fuera del proceso. En una casa con 1-4 cámaras en una PC, funciona perfecto. Pero cuando Gryps evolucione a múltiples edges (Fase 3), se necesitará un bus de red (MQTT/Redis).

La interfaz `EventBus` está diseñada para que cambiar de implementación sea transparente: cualquier código que recibe un `EventBus` no sabe (ni necesita saber) si los handlers están en el mismo proceso o en otra máquina.

### Código relacionado

- `src/gryps/core/bus.py:113` — clase `LocalEventBus`.
- `src/gryps/core/__init__.py` — exporta `LocalEventBus`.
- `tests/unit/test_bus.py:239` — tests de `TestLocalEventBus`.

### Preguntas para estudiantes

- ¿Qué pasa si un handler modifica el `payload` del evento? ¿Afecta a otros suscriptores del mismo `publish`?
- ¿Por qué `unsubscribe` es no-op si la suscripción no existe, en lugar de lanzar error?
- ¿Qué ventaja tiene que `publish` sea sincrónico en MVP?
- Si un handler lanza excepción, ¿los handlers que se registraron después se ejecutan?
- ¿En qué escenario `LocalEventBus` sería insuficiente?

### Ejercicio sugerido

```python
from gryps.core import LocalEventBus, Event

bus = LocalEventBus()
results = []

bus.subscribe("A", lambda e: results.append("a1"))
bus.subscribe("A", lambda e: results.append("a2"))
bus.subscribe("B", lambda e: results.append("b"))

bus.publish(Event.create(stream_id="s", frame_id=0, event_type="A"))
bus.publish(Event.create(stream_id="s", frame_id=0, event_type="B"))

print(results)  # ¿Qué orden esperás?
```


---

## Slice 0.5 — `PluginRegistry` (scan + load)

### Qué problema resuelve

Un framework de plugins necesita una manera de descubrir qué plugins existen en el sistema de archivos, validar que su metadata esté completa y cargar las clases correspondientes sin saber de antemano qué hay instalado.

El `PluginRegistry` es el componente que hace eso. Escanea directorios en busca de `plugin.yaml`, parsea el manifiesto, valida campos obligatorios (`name`, `version`, `entrypoint`, `class`) y carga la clase del plugin mediante `importlib`.

Sin Registry, cada plugin tendría que registrarse manualmente en el código del núcleo. Con Registry, agregar un plugin es solo crear un directorio con `plugin.yaml` y el módulo Python.

### Cómo funciona

```python
from gryps.core import PluginRegistry

registry = PluginRegistry(roots=["tests/fixtures/plugins/"])
registry.discover()

info = registry.plugins["dummy_plugin"]
plugin = info.loaded_class()  # instancia DummyPlugin
```

Flujo interno:

```text
scan()      → recorre roots, busca plugin.yaml, parsea YAML → lista de PluginManifest
discover()  → scan + validate + load → dict[str, PluginInfo]
```

Cada paso está separado: `scan()` solo encuentra y parsea. `discover()` agrega validación e importación. Esto permite inspeccionar manifests sin cargar código.

### plugin.yaml — el contrato mínimo

```yaml
name: vehicle_yolo
version: 1.0.0
type: detector
entrypoint: detector.py    # archivo relativo al directorio del plugin
class: VehicleYOLOPlugin   # clase a importar
```

Cuatro campos obligatorios para MVP:
- `name` — identificador único del plugin (se usa como clave en el registry)
- `version` — semver o string descriptivo
- `entrypoint` — ruta al archivo Python relativa al directorio del plugin
- `class` — nombre de la clase dentro del módulo entrypoint

El manifiesto puede contener más campos (`type`, listas de eventos, requisitos de hardware). Se almacenan en `raw` para uso futuro, pero el Registry MVP solo valida los cuatro obligatorios.

### Carga dinámica con importlib

`PluginRegistry` usa `importlib.util.spec_from_file_location` para cargar módulos desde archivos específicos. Esto evita modificar `sys.path` y funciona para plugins fuera del paquete `gryps`.

```python
spec = importlib.util.spec_from_file_location(module_name, str(full_path))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cls = getattr(module, class_name)
```

No se instancia la clase durante el discover — solo se obtiene la referencia. La instanciación queda a cargo del `PipelineOrchestrator` (Slice 0.6).

### Por qué Registry está separado del Bus

| Componente | Responsabilidad |
|------------|-----------------|
| `EventBus` | Transporte de eventos entre componentes en runtime |
| `PluginRegistry` | Descubrimiento y carga estática de plugins al arranque |

El Registry no publica eventos, no conoce el Bus, ni sabe qué hace el plugin una vez cargado. Su trabajo termina cuando devuelve la clase. Esta separación permite:

1. Probar el Registry sin tener un Bus corriendo.
2. Cambiar la estrategia de descubrimiento (ej. escanear un ZIP, leer una base de datos) sin tocar el Bus.
3. El `PipelineOrchestrator` (próximo slice) orquesta ambos: usa Registry para cargar plugins, luego los conecta al Bus.

### Validación pragmática

El Registry valida que los campos requeridos existan y no estén vacíos. No valida que el `entrypoint` exista en disco ni que la `class` sea importable en esta etapa — esas validaciones ocurren durante `discover()`.

Si un manifiesto pasa la validación pero el entrypoint no existe, se obtiene un `PluginLoadError` con el path exacto. Esto es intencional: errores tempranos y claros.

### ¿Por qué no usar PyYAML?

El proyecto no tiene dependencias externas. El manifiesto `plugin.yaml` usa un subconjunto minimalista de YAML (pares clave:valor, listas indentadas con `-`, anidamiento simple). En lugar de agregar PyYAML como dependencia solo para parsear 10 líneas, el Registry incluye un parser mínimo de ~90 líneas.

Si en el futuro los manifests se vuelven complejos (anclas, tipos explícitos, documentos múltiples), se evaluará agregar PyYAML.

### Código relacionado

- `src/gryps/core/registry.py` — `PluginRegistry`, `PluginManifest`, `PluginInfo`, parser YAML mínimo.
- `src/gryps/core/exceptions.py` — `GrypsError`, `PluginLoadError`, `PluginValidationError`, `ConfigError`.
- `src/gryps/core/__init__.py` — exporta toda la API pública del core.
- `tests/fixtures/plugins/dummy_plugin/` — plugin de prueba con `plugin.yaml` y `plugin.py`.
- `tests/unit/test_registry.py` — 36 tests: parser YAML, validación, scan, discover, duplicados, errores de carga.

### Preguntas para estudiantes

- ¿Por qué `scan()` y `discover()` son métodos separados en lugar de uno solo?
- ¿Qué ventaja tiene no instanciar la clase durante el discover?
- ¿Por qué el Registry no debería conocer el EventBus?
- ¿Qué pasa si dos plugins tienen el mismo nombre en directorios distintos?
- ¿Por qué usamos `importlib.util.spec_from_file_location` en lugar de `importlib.import_module`?

### Ejercicio sugerido

```python
from gryps.core import PluginRegistry
from pathlib import Path

# Crear un plugin de prueba temporal
tmp = Path("/tmp/test_plugin")
(tmp / "detector.py").write_text("class MyPlugin: pass\n")
(tmp / "plugin.yaml").write_text(
    "name: test_plugin\nversion: 0.1.0\nentrypoint: detector.py\nclass: MyPlugin\n"
)

registry = PluginRegistry(roots=[str(tmp)])
registry.discover()

info = registry.plugins["test_plugin"]
assert info.loaded_class.__name__ == "MyPlugin"
```

La pregunta clave: **¿qué cambiaría si `entrypoint` fuera un dotted path como `gryps.plugins.detector.MyPlugin` en lugar de un archivo relativo?**

---

## Slice 0.6 — `PipelineOrchestrator` (mínimo)

### Qué problema resuelve

El EventBus y PluginRegistry existen como componentes independientes, pero alguien tiene que coordinarlos. El `PipelineOrchestrator` es ese "alguien": el componente que orquesta el ciclo de vida del sistema completo.

En MVP hace muy poco —solo administra estado— porque los streams, preprocessors y plugins todavía no existen como runtime. Pero la semilla está: `start()` y `stop()` establecen el contrato que el orquestador completo cumplirá después.

### Relación con EventBus y PluginRegistry

```
PipelineOrchestrator
├── EventBus        → Transporte de eventos en runtime
└── PluginRegistry  → Descubrimiento y carga de plugins (opcional en MVP)
```

| Componente | Responsabilidad | Conoce a |
|------------|----------------|----------|
| `EventBus` | Publicar y suscribir eventos | Nadie |
| `PluginRegistry` | Escanear, validar y cargar plugins | Solo el filesystem |
| `PipelineOrchestrator` | Iniciar/detener el sistema completo | Bus y Registry |

El orquestador recibe el bus por inyección de dependencias. Si no se le pasa uno, crea un `LocalEventBus` por defecto. El `PluginRegistry` es opcional: en el MVP mínimo, el orquestador funciona sin plugins.

### Lifecycle state

```python
orch = PipelineOrchestrator()
assert not orch.is_running

orch.start()
assert orch.is_running

orch.stop()
assert not orch.is_running
```

Estados internos:
- **STOPPED** → estado inicial y post-stop
- **RUNNING** → post-start, mientras el pipeline procesa

El ciclo es simétrico: se puede pasar de STOPPED → RUNNING → STOPPED → RUNNING sin restricciones.

### Decisión de diseño: idempotencia

`start()` sobre un orquestador ya corriendo es no-op (no falla). `stop()` sobre uno ya detenido también. Esto es deliberado:

- **A favor**: los llamadores no necesitan verificar estado antes de llamar. Especialmente útil cuando el orquestador se integre con señales del sistema, context managers o scripts de despliegue que pueden llamar `stop()` múltiples veces.
- **En contra**: podría ocultar bugs donde el código llama `start()` dos veces cuando no debería. Se mitiga con tests de idempotencia y monitoreo de logs en futuros slices.

Alternativa considerada: lanzar `PipelineStateError` en llamadas inválidas. Se rechazó por pragmatismo MVP —cuando el orquestador haga trabajo real (gestionar streams, plugins, threads), se puede endurecer si es necesario.

### Por qué 0 streams es un test válido

El orquestador MVP no tiene streams. Pero su constructor y `start()` deben funcionar sin ellos. Esto prueba que:

1. La inyección de dependencias funciona: el orquestador acepta bus sin necesidad de streams.
2. El ciclo de vida es independiente de la configuración: se puede crear, arrancar y parar un orquestador "vacío".
3. El contrato de `start()` no depende de recursos externos.

Cuando lleguen los streams (slices 0.7+), el orquestador evolucionará para administrarlos. Pero si el test de "0 streams" falla ahora, el problema está en el orquestador, no en los streams.

### Código relacionado

- `src/gryps/core/pipeline_orchestrator.py` — `PipelineOrchestrator`, `PipelineState`.
- `src/gryps/core/__init__.py` — exporta `PipelineOrchestrator` y `PipelineState`.
- `tests/unit/test_pipeline_orchestrator.py` — init, lifecycle, idempotencia, sin eventos al start/stop.

### Preguntas para estudiantes

- ¿Por qué el `PipelineOrchestrator` crea un `LocalEventBus` por defecto en lugar de requerir uno siempre?
- ¿Qué ventaja tiene que `PluginRegistry` sea opcional en el constructor?
- ¿Por qué `start()` y `stop()` son idempotentes en lugar de lanzar error si se llaman en estado incorrecto?
- ¿Qué cambiaría si `start()` publicara un evento `PIPELINE_STARTED`?
- ¿Es `PipelineState` un enum? ¿Por qué es una clase con constantes en lugar de un `StrEnum` de Python 3.11+?
- ¿Qué pasaría si el orquestador recibiera un bus que ya está en uso por otro orquestador?

### Ejercicio sugerido

```python
from gryps.core import PipelineOrchestrator, LocalEventBus

bus = LocalEventBus()
events = []

bus.subscribe("*", events.append)

orch = PipelineOrchestrator(event_bus=bus)
orch.start()
orch.stop()

# Pregunta: ¿cuántos eventos hay en `events`?
# Respuesta: 0 — el orquestador MVP no publica eventos al iniciar/detener.
```

---

## Slice 0.7 — `BaseStreamSource` + `FileStream` (Stream Sources)

### Qué problema resuelve

Hasta 0.6, el sistema tenía EventBus y PluginRegistry, pero no había una fuente de datos. Gryps procesa video, pero ningún componente sabía leer frames.

Los Stream Sources llenan ese vacío: son los componentes que producen frames — desde archivos, cámaras IP, streams RTSP o generadores sintéticos — y los convierten en eventos que el bus puede transportar.

### Arquitectura: dos capas (adapter + source)

| Capa | Responsabilidad | Ejemplo |
|------|-----------------|---------|
| `FrameReader` | Decodificar frames de un medio específico | OpenCV, ffmpeg, generador sintético |
| `BaseStreamSource` | Orquestar lectura + publicación de eventos | `FileStream`, `CameraStream` |

El `FrameReader` es un adaptador (patrón Adapter). No sabe nada de eventos, de buses ni de metadatos. Solo sabe abrir un medio, leer el próximo frame y cerrar. Esto permite intercambiar la biblioteca de decodificación sin tocar la lógica de negocio.

El `BaseStreamSource` es el que entiende de eventos. Toma lo que el reader devuelve y construye `FrameMetadata` + eventos `NEW_FRAME` para publicar en el bus.

### FrameMetadata vs raw frame

Esta es la decisión más importante del slice. El bus **nunca** transporta datos de píxeles. Solo transporta `FrameMetadata`:

```python
@dataclass(frozen=True)
class FrameMetadata:
    frame_id: int
    stream_id: str
    timestamp: float
    frame_ref: str          # referencia opaca (ej. "mem://file_01/0")
    resolution: tuple[int, int] | None
    preprocessors_applied: tuple[str, ...]
```

El frame raw (el `numpy.ndarray`, los bytes decodificados) se queda en el stream source. Quien necesite los píxeles debe pedirlos por `frame_ref` al source que los posee.

Esto es intencional y fundamental:

| Problema | Solución |
|----------|----------|
| Una imagen 1080p ocupa ~8MB | El bus transporta ~200 bytes de metadata |
| Si 5 suscriptores reciben el frame, son 40MB en memoria | El source mantiene una copia; los suscriptores acceden por referencia |
| El frame viaja por la red (futuro MQTT) | Metadata cabe en un mensaje; el frame se sirve por otro canal |

El método `to_payload()` convierte `FrameMetadata` a un `dict` plano para el evento:

```python
{
    "frame_ref": "mem://file_01/0",
    "timestamp": 1000.0,
    "resolution": [640, 480],
    "preprocessors_applied": [],
}
```

Notar que `frame_id` y `stream_id` **no** van en el payload: ya están en los campos nativos del `Event`.

### NEW_FRAME — el primer evento de dominio

```python
FrameMetadata.NEW_FRAME = "NEW_FRAME"
```

Este es el primer evento de dominio (no de infraestructura) del sistema. Cuando un stream source lee un frame, publica un evento `NEW_FRAME` con la metadata correspondiente.

La constante está sobre `FrameMetadata` por pragmatismo: era el lugar más simple disponible al momento de implementar. En retrospectiva, pertenecería más a un namespace de eventos de dominio (`gryps.events.NEW_FRAME`). Para MVP es aceptable.

### Cómo funciona `publish_next`

```python
def publish_next(self, bus: EventBus) -> FrameMetadata | None:
    meta = self.read_next()
    if meta is not None:
        bus.publish(Event(
            event_id=str(uuid.uuid4()),
            timestamp=meta.timestamp,
            stream_id=self.stream_id,
            frame_id=meta.frame_id,
            event_type=FrameMetadata.NEW_FRAME,
            payload=meta.to_payload(),
        ))
    return meta
```

El método:
1. Lee el próximo frame (delega a `read_next()` que usa el `FrameReader`).
2. Si hay frame, construye un `Event` y lo publica en el bus.
3. Retorna la metadata (o `None` si el stream se agotó).

Importante: `read_next()` no publica eventos. `publish_next()` sí. Esto separa la lectura (infraestructura) de la publicación (dominio).

Si el stream se agotó, no se publica ningún evento — `publish_next()` retorna `None` y el bus no recibe mensajes espurios.

### FileStream — implementación concreta

```python
class FileStream(BaseStreamSource):
    def __init__(self, stream_id, source_path, reader):
        self._stream_id = stream_id
        self._source_path = source_path
        self._reader = reader
        self._frame_count = 0
        self._frame_cache: dict[int, object] = {}
        reader.open(source_path)
```

`FileStream` lee frames de un archivo de video. Usa un `FrameReader` inyectado para la decodificación real y mantiene un `_frame_cache` con los frames raw (accesibles por `frame_ref` como `mem://file_01/0`).

La relación es siempre 1 FileStream → 1 archivo de video.

### Tests: fixture determinística + adapter sintético

Los tests de streams no usan archivos de video reales. Usan `SyntheticFrameReader`, un adaptador que genera frames dummy:

```python
class SyntheticFrameReader(FrameReader):
    def __init__(self, num_frames=5, resolution=(640, 480)):
        self._limit = num_frames
        self._count = 0
        ...

    def read(self):
        if self._count >= self._limit:
            return None
        self._count += 1
        return {"dummy": True}
```

Esto da:
- **Determinismo**: mismo `num_frames` produce siempre el mismo resultado.
- **Velocidad**: no hay decode real, los tests corren en milisegundos.
- **Aislamiento**: si un test falla, el problema no es el codec de video.

Y `FailingFrameReader` para probar errores:

```python
class FailingFrameReader(FrameReader):
    def open(self, source):
        raise FileNotFoundError(f"Could not open source: {source}")
```

Esto permite probar `FileNotFoundError` sin tener archivos corruptos en el repo.

### Lo que el bus NO transporta

Los tests verifican explícitamente que el payload del evento `NEW_FRAME` **no** contiene datos raw:

```python
def test_raw_frame_not_in_event_payload(self):
    ...
    for event in captured:
        payload_keys = set(event.payload)
        assert payload_keys == {"frame_ref", "timestamp", "resolution", "preprocessors_applied"}
```

Si en el futuro alguien intenta agregar `"data": frame.raw` al payload, este test falla. Es un guardián intencional.

### Código relacionado

- `src/gryps/streams/base.py` — `FrameMetadata`, `FrameReader` (ABC), `BaseStreamSource` (ABC).
- `src/gryps/streams/file_stream.py` — `FileStream` (implementación concreta).
- `src/gryps/streams/__init__.py` — exporta `BaseStreamSource`, `FileStream`, `FrameMetadata`, `FrameReader`.
- `tests/unit/test_streams.py` — 25 tests: metadata, source abstracto, FileStream con reader sintético.

### Preguntas para estudiantes

- ¿Por qué separar `FrameReader` de `BaseStreamSource` en lugar de tener una sola clase?
- ¿Qué ventaja tiene que el bus transporte solo metadata y no píxeles?
- ¿Qué pasa si un suscriptor necesita los píxeles de un frame? ¿Cómo los obtiene?
- ¿Por qué `publish_next()` retorna la metadata si ya la publicó en el bus?
- ¿Qué garantía da `NEW_FRAME`? ¿Quién puede publicarlo y quién escucharlo?
- ¿Por qué los tests usan `SyntheticFrameReader` en lugar de un archivo .mp4 de prueba?
- ¿Qué pasaría si el bus transportara `numpy.ndarray`?

### Ejercicio sugerido

```python
from gryps.core import LocalEventBus
from gryps.streams import FileStream, FrameMetadata

# Usar el SyntheticFrameReader de los tests
from tests.unit.test_streams import SyntheticFrameReader

reader = SyntheticFrameReader(num_frames=3)
source = FileStream(stream_id="demo", source_path="dummy", reader=reader)
bus = LocalEventBus()

captured = []
bus.subscribe(FrameMetadata.NEW_FRAME, captured.append)

while source.publish_next(bus) is not None:
    pass

print(f"Se publicaron {len(captured)} eventos NEW_FRAME")
for ev in captured:
    print(f"  frame {ev.frame_id}: {ev.payload['frame_ref']}")
```

Pregunta clave: **¿qué contendría `event.payload` si el frame fuera 4K en lugar de 640×480?** Respuesta: lo mismo. La resolución cambia el valor de `resolution` en la metadata, pero el payload no crece. El frame raw (que sí crece) nunca entra al bus.

---

## Slice 0.8 — `ConsoleOutput` (Output Plugin)

### Qué problema resuelve

Hasta 0.7 teníamos fuentes de video que publican `NEW_FRAME`, pero ningún componente que muestre resultados al usuario. Los output plugins son los consumidores terminales del pipeline: reciben eventos (normalmente `PLATE_READ`) y los persisten, muestran o reenvían fuera del bus.

El `ConsoleOutput` es el output más simple posible: imprime en consola cuando se lee una placa. No tiene dependencias externas, no necesita base de datos ni conexión de red. Es útil para depuración, desarrollo, y como plantilla para outputs reales (SQLite, Telegram, Webhook).

### Output plugins como consumidores

En la arquitectura de Gryps, los plugins se dividen en dos grandes familias según cómo participan en el flujo de eventos:

| Familia | Producen eventos | Consumen eventos | Ejemplo |
|---------|-----------------|------------------|---------|
| **Detectores / análisis** | Sí (e.g. `VEHICLE_DETECTED`, `PLATE_READ`) | Sí (e.g. `NEW_FRAME`) | VehicleYOLO, PlateDetector, OCRBackend |
| **Outputs** | No (en MVP) | Sí (e.g. `PLATE_READ`, `SYSTEM_ALERT`) | ConsoleOutput, SQLiteOutput, TelegramBot |

Los outputs son **consumidores puros**: reciben eventos y hacen algo con ellos (imprimir, guardar, notificar), pero nunca publican nuevos eventos en el bus. Esto mantiene el flujo unidireccional y evita ciclos.

### `BaseOutputPlugin` — contrato mínimo

```python
class BaseOutputPlugin(ABC):
    @abstractmethod
    def handle(self, event: Event) -> None:
        """Process an output event."""
```

Solo un método abstracto: `handle(event)`. No hay lifecycle, no hay suscripción automática, no hay configuración. El contrato es deliberadamente mínimo para que cualquier output futuro (SQLite, Telegram, Webhook) implemente exactamente lo que necesita sin cargar con interfaz pesada.

### `ConsoleOutput` — implementación

```python
class ConsoleOutput(BaseOutputPlugin):
    def __init__(self, writer: Callable[[str], None] | None = None) -> None:
        self._writer = writer or print

    def handle(self, event: Event) -> None:
        if event.event_type != "PLATE_READ":
            return
        # ... imprime línea formateada
```

Tres decisiones de diseño importantes:

1. **Writer inyectable.** El `print` se reemplaza por un `Callable` que por defecto es `print`, pero en tests se puede pasar `list.append` para capturar la salida sin parsear stdout. Es el mismo patrón que vimos en `SyntheticFrameReader` (Slice 0.7): inyectar dependencias para testear sin efectos secundarios.

2. **Filtro por tipo de evento.** `handle()` ignora silenciosamente eventos que no son `PLATE_READ`. Esto es intencional: el output puede conectarse al bus sin suscripción selectiva. Si recibe un `NEW_FRAME`, no imprime nada — no falla, no se queja. Esto simplifica la integración: el PipelineOrchestrator puede pasarle todos los eventos sin preocuparse por filtros.

3. **Sin suscripción automática.** ConsoleOutput no se suscribe al bus por sí mismo. No conoce el EventBus. Alguien externo (un test, el PipelineOrchestrator) debe llamar a `handle()` cuando corresponda. Esto mantiene la separación de responsabilidades: el output sabe *qué hacer* con un evento, no *cuándo recibirlo*.

### Por qué output plugins están separados del EventBus

Esta es una pregunta recurrente y vale la pena entenderla bien.

| Componente | Responsabilidad |
|------------|-----------------|
| `EventBus` | Transporte — mueve eventos del publicador al suscriptor |
| `BaseOutputPlugin` | Procesamiento terminal — qué hacer cuando llega un evento |

El bus NO sabe qué hace un output con el evento. El output NO sabe cómo llegan los eventos. Esta separación permite:

1. **Outputs sin bus.** Podemos probar `ConsoleOutput.handle()` directamente sin instanciar un EventBus. Solo necesitamos un `Event`. El test es puro y rápido.

2. **Bus sin outputs.** El EventBus funciona con cualquier handler, no solo outputs. Un detector se suscribe igual que un output.

3. **Composición explícita.** Quien conecta output y bus (el PipelineOrchestrator o un test) decide qué eventos recibe cada output. Esto es explícito, no mágico.

```python
# En un test: conexión explícita entre bus y output
bus = LocalEventBus()
output = ConsoleOutput()
bus.subscribe("PLATE_READ", output.handle)
```

### Cómo prepara testing de cámara/archivo

Antes de este slice, el pipeline terminaba en el EventBus — publicábamos `NEW_FRAME` pero no había nadie del otro lado. Con ConsoleOutput tenemos un consumidor real que podemos verificar.

El flujo de un test de integración ahora es completo:

```
FileStream → publish(NEW_FRAME) → EventBus → (simular detector) → publish(PLATE_READ) → ConsoleOutput → assert en consola
```

En otras palabras: ahora podemos probar **end-to-end** desde un stream hasta la salida visible, sin mockear nada del bus. El `ConsoleOutput` es el "eslabón final" que cierra la cadena y permite validar que el pipeline completo funciona.

### Código relacionado

- `src/gryps/plugins/outputs/base.py` — `BaseOutputPlugin` ABC.
- `src/gryps/plugins/outputs/__init__.py` — exporta `BaseOutputPlugin` y `ConsoleOutput`.
- `src/gryps/plugins/outputs/console_logger/plugin.yaml` — manifiesto del plugin (descubrible por `PluginRegistry`).
- `src/gryps/plugins/outputs/console_logger/output.py` — `ConsoleOutput` con writer inyectable.
- `src/gryps/plugins/outputs/console_logger/__init__.py` — exporta `ConsoleOutput`.
- `tests/unit/test_console_output.py` — 7 tests: PLATE_READ imprime, otros eventos no, payload sin raw, carga vía Registry.

### Preguntas para estudiantes

- ¿Por qué `BaseOutputPlugin` tiene un solo método abstracto en lugar de 5-10 métodos de lifecycle?
- ¿Qué ventaja tiene inyectar el writer en lugar de llamar a `print()` directamente?
- ¿Por qué `ConsoleOutput` no se suscribe al bus automáticamente?
- ¿Qué pasaría si un output lanzara una excepción en `handle()`? ¿Debería atraparla él mismo o dejarla propagar?
- ¿Cómo cambiarías `ConsoleOutput` para que también imprima eventos `SYSTEM_ALERT`?
- ¿Por qué los outputs no deberían publicar eventos en el bus?

### Ejercicio sugerido

```python
from gryps.core import LocalEventBus, Event
from gryps.plugins.outputs import ConsoleOutput

bus = LocalEventBus()
lines: list[str] = []
output = ConsoleOutput(writer=lines.append)

bus.subscribe("PLATE_READ", output.handle)

# Simular un detector publicando PLATE_READ
bus.publish(Event.create(
    stream_id="cam_01", frame_id=100,
    event_type="PLATE_READ",
    payload={"plate_text": "XYZ789", "track_id": "v42", "confidence": 0.88},
))

# Verificar que el output imprimió la línea
print(lines[0])
# "[CONSOLE] PLATE_READ stream=cam_01 frame=100 plate=XYZ789 track=v42 conf=0.88"
```

La pregunta clave: **¿qué tendríamos que cambiar para que ConsoleOutput guarde en archivo en lugar de imprimir?** Respuesta: solo el writer — pasar `file.write` en lugar de `print`. El resto del código no cambia.

---

## Slice 0.9 — `main.py` funcional (primer smoke test end-to-end)

### Qué problema resuelve

Hasta 0.8 teníamos todos los componentes de infraestructura: EventBus, PluginRegistry, PipelineOrchestrator, FileStream y ConsoleOutput. Pero no había un punto de entrada que los orquestara. Cada componente se probaba de forma aislada.

Slice 0.9 agrega el `main()` que los conecta: es la primera vez que el sistema completo se puede ejecutar de principio a fin, desde un archivo de video hasta la salida en consola. No hay detección, OCR ni persistencia — solo el esqueleto de infraestructura funcionando.

### Composición (wiring)

El flujo completo es:

```text
FileStream.publish_next()
  → EventBus.publish(NEW_FRAME)
    → FrameLogger.handle(NEW_FRAME)
      → print("[CONSOLE] Frame N | Stream: ...")
```

En código:

```python
# gryps/__main__.py — run_file()
bus = LocalEventBus()
logger = FrameLogger(writer=...)
bus.subscribe("NEW_FRAME", logger.handle)

while stream.publish_next(bus) is not None:
    pass
```

Tres decisiones de diseño en esta composición:

| Decisión | Explicación |
|----------|-------------|
| **FrameLogger como plugin separado** | No modificar ConsoleOutput (que solo maneja PLATE_READ). FrameLogger es un output plugin específico para NEW_FRAME, con writer inyectable. |
| **`run_file()` pública y testeable** | Acepta un `FileStream` y un `writer` opcional. Los tests la llaman directamente con un `SyntheticFrameReader`, sin necesidad de subprocess ni de OpenCV. |
| **`main()` delgada** | Solo parsea args y delega a `_run_file_cli()` (CLI path) o `run_file()` (path testeable). La lógica de negocio está en `run_file()`. |

### `FrameLogger` — nuevo output plugin

`FrameLogger` es simétrico a `ConsoleOutput` pero para `NEW_FRAME`:

```python
class FrameLogger(BaseOutputPlugin):
    def __init__(self, writer=None):
        self._writer = writer or print

    def handle(self, event: Event) -> None:
        if event.event_type != "NEW_FRAME":
            return
        self._writer(f"[CONSOLE] Frame {event.frame_id + 1} | Stream: {event.stream_id}")
```

- **Writer inyectable**: igual que ConsoleOutput. Tests usan `list.append`.
- **Filtro por tipo**: ignora todo excepto `NEW_FRAME`.
- **Sin auto-suscripción**: al igual que ConsoleOutput, no conoce el bus.
- **1-based display**: el frame_id interno es 0-based, pero la salida al usuario es 1-based.

### CLI vs test path

```text
main()                     # argparse
  ├── --file PATH          # CLI real
  │   └── _run_file_cli()  # intenta OpenCVReader; si no, error y exit(1)
  │       └── run_file()   # wiring puro (testeable)
  │
  └── sin args             # muestra versión + usage
```

El CLI real requiere OpenCV (aún no es dependencia del proyecto). Los tests usan `SyntheticFrameReader`, que es determinístico y no necesita codecs.

### Por qué este es el primer smoke path end-to-end

Aunque Gryps no hace nada útil todavía (no detecta vehículos, no lee patentes, no guarda nada), este es el primer momento en que podemos ejecutar el sistema completo:

1. Un stream produce datos (aunque sean sintéticos).
2. El bus transporta eventos (NEW_FRAME).
3. Un output plugin consume eventos y muestra resultado.

Este "triángulo" (source → bus → output) es la base sobre la que se construirá todo lo demás. Cuando lleguen los detectores y OCR, se insertarán como nuevos eslabones: reciben un tipo de evento y publican otro.

### Código relacionado

- `src/gryps/__main__.py` — `main()`, `run_file()`, `_run_file_cli()`, `_open_file()`.
- `src/gryps/plugins/outputs/frame_logger/output.py` — `FrameLogger`.
- `src/gryps/plugins/outputs/frame_logger/plugin.yaml` — manifiesto descubrible por PluginRegistry.
- `src/gryps/plugins/outputs/__init__.py` — exporta `FrameLogger`.
- `tests/unit/test_frame_logger.py` — 9 tests: impresión, 1-based, filtro por tipo, registry.
- `tests/unit/test_main.py` — 4 tests: `run_file()` con 0, 1, 3 frames, verifica cierre.

### Qué todavía no hace

- **No procesa video real** — requiere OpenCV (futuro slice 1.0+).
- **No detecta vehículos** — no hay detector conectado al bus.
- **No lee patentes** — no hay OCR.
- **No persiste nada** — no hay SQLiteOutput.
- **No tiene auto-suscripción de plugins** — el PipelineOrchestrator no suscribe plugins automáticamente.
- **No hay manejo de errores real** — el bus propaga excepciones; los plugins no aíslan fallos (intencional para MVP).

### Preguntas para estudiantes

- ¿Por qué `run_file()` acepta un `FileStream` y un `writer` en lugar de crear todo internamente?
- ¿Qué ventaja tiene separar `FrameLogger` de `ConsoleOutput` en lugar de unificarlos?
- ¿Por qué `_open_file()` está separada de `run_file()`?
- ¿Cómo probarías que `main()` con `--file` funciona sin instalar OpenCV?
- ¿Qué cambiaría si quisieramos que `run_file()` procese 2 streams en paralelo?
- ¿Por qué `FrameLogger` usa 1-based para display pero el Event usa 0-based?

### Ejercicio sugerido

```python
from gryps.__main__ import run_file
from gryps.streams import FileStream
from tests.unit.test_streams import SyntheticFrameReader

reader = SyntheticFrameReader(num_frames=5)
stream = FileStream(stream_id="demo", source_path="dummy", reader=reader)

lines: list[str] = []
run_file(stream, writer=lines.append)

assert len(lines) == 5
assert "[CONSOLE] Frame 5 | Stream: demo" in lines[-1]
```

Pregunta clave: **¿Qué pasa si `SyntheticFrameReader(num_frames=0)`?** Respuesta: `lines == []`. El while loop nunca ejecuta el cuerpo porque `publish_next()` retorna inmediatamente `None`.

