# Historias de Usuario — Gryps

> **Versión:** 1.1  
> **Fecha:** 2026-06-02  
> **Formato:** Como *[rol]*, quiero *[funcionalidad]*, para *[beneficio]*.  
> **Criterios de aceptación:** Given-When-Then.  
> **Prioridad:** Must / Should / Could / Won't (MoSCoW)

---

## Épica 1: Ingesta y Configuración de Video

### HU-001 — Seleccionar fuente de video
**Como** Administrador de Sistema,  
**quiero** configurar la fuente de video (archivo MP4, cámara USB o stream RTSP),  
**para** que Gryps comience a analizar el tráfico sin importar el tipo de cámara disponible.

**Criterios de aceptación:**
- Given que el sistema está recién instalado, When ejecuto el comando de inicio, Then se me solicita elegir entre `file`, `usb` o `rtsp`.
- Given que elijo `file`, When proporciono una ruta válida, Then el sistema carga el video y comienza el procesamiento.
- Given que elijo `rtsp`, When ingreso una URL válida con credenciales, Then el sistema establece conexión y muestra el primer frame en menos de 5 segundos.

**Prioridad:** Must (MVP)

---

### HU-002 — Configurar ROI sin GUI en el edge
**Como** Administrador de Sistema,  
**quiero** definir la ROI desde un archivo YAML o una herramienta externa,  
**para** que el edge pueda operar headless (sin monitor ni mouse) después de la instalación inicial.

**Criterios de aceptación:**
- Given que el edge está en un rack sin monitor, When inicio el sistema, Then lee `config/roi.yaml` y aplica la ROI sin abrir ventanas.
- Given que no existe `roi.yaml`, When inicio el sistema, Then lanza error claro: *"Falta roi.yaml. Ejecute gryps.tools.calibrate en su PC."*
- Given que soy técnico en campo con laptop, When ejecuto `gryps.tools.calibrate`, Then se abre ventana interactiva con `cv2.selectROI`, guarda el resultado a YAML, y el edge puede usarlo.

**Prioridad:** Must (MVP)

---

### HU-003 — Perfil de hardware adaptable
**Como** Administrador de Sistema,  
**quiero** seleccionar un perfil de hardware (`EDGE_HOUSE`, `EDGE_NVR`, `EDGE_RPI`, `CLOUD_HUB`) en un archivo de configuración,  
**para** que el sistema ajuste automáticamente resolución, skip de frames, backend de OCR y tipos de cámara soportados según la capacidad del equipo.

**Criterios de aceptación:**
- Given que edito `config.py` y cambio el perfil a `EDGE_HOUSE`, When reinicio el sistema, Then se cargan YOLO11n, Tesseract, resolución 640×480, skip=3, y solo cámaras estáticas.
- Given que cambio a `EDGE_NVR`, When reinicio, Then se cargan YOLO11s, PaddleOCR, resolución nativa, skip=1, y se habilitan PTZ, 360° y térmicas.
- Given que configuro `EDGE_RPI`, When reinicio, Then se carga Tesseract sin CLAHE, skip=5, y se deshabilita dewarping (mensaje claro si se intenta).
- Given un perfil desconocido, When inicio el sistema, Then se lanza error indicando los perfiles válidos.

**Prioridad:** Must (MVP)

---

### HU-004 — Seleccionar tipo de cámara
**Como** Administrador de Sistema,  
**quiero** declarar el tipo de cámara en la configuración del stream (`static`, `ptz`, `fisheye`, `thermal`, `mobile`, `triggered`),  
**para** que el sistema cargue automáticamente los preprocessors correctos (dewarping, compensación PTZ, EIS, trigger sync) sin que yo configure manualmente cada uno.

**Criterios de aceptación:**
- Given que configuro `type: fisheye`, When inicio el stream, Then se carga automáticamente el preprocessor `dewarp` con los parámetros del YAML.
- Given que configuro `type: thermal` sin cámara visible emparejada, When inicio, Then se muestra warning: *"Cámara térmica sin visible emparejada: no se realizará LPR."*
- Given que configuro `type: ptz` en perfil `EDGE_HOUSE`, When inicio, Then se lanza error: *"PTZ requiere EDGE_NVR mínimo para compensación de movimiento."*

**Prioridad:** Must (MVP — arquitectura lista; activación por tipo en Post-MVP)

---

## Épica 2: Detección y Tracking de Vehículos

### HU-005 — Detectar vehículos en tiempo real
**Como** Operador de Seguridad,  
**quiero** que el sistema dibuje un rectángulo verde alrededor de cada vehículo que entra en la ROI,  
**para** visualizar que el sistema está detectando correctamente.

**Criterios de aceptación:**
- Given que un carro entra en la ROI, When el sistema procesa el frame, Then aparece un bounding box verde con la etiqueta "car".
- Given que una moto entra, When es detectada, Then aparece el bounding box con etiqueta "motorcycle".
- Given que un peatón camina por la ROI, When no hay detector de personas activo, Then no aparece ningún bounding box (el sistema no debe alucinar vehículos).

**Prioridad:** Must (MVP)

---

### HU-006 — Tracking persistente de vehículos
**Como** Operador de Seguridad,  
**quiero** que cada vehículo mantenga un ID numérico único mientras esté visible,  
**para** saber que el sistema está rastreando el mismo objeto y no confundirlo con otro.

**Criterios de aceptación:**
- Given que un carro entra y permanece 5 segundos en pantalla, When reviso los frames, Then el ID no cambia en ningún frame intermedio.
- Given que dos carros pasan simultáneamente, When son detectados, Then cada uno tiene un ID distinto y los bounding boxes no intercambian etiquetas.
- Given que un vehículo sale de la ROI y vuelve a entrar 10 segundos después, When es re-detectado, Then se le asigna un ID nuevo (no se mantiene el anterior).

**Prioridad:** Must (MVP)

---

### HU-007 — Detección de placas dentro del vehículo
**Como** Operador de Seguridad,  
**quiero** que el sistema detecte automáticamente la región de la placa dentro de cada vehículo,  
**para** no depender de posiciones fijas ni calibraciones manuales.

**Criterios de aceptación:**
- Given que un vehículo es detectado, When el modelo de placas corre sobre el crop del vehículo, Then aparece un bounding box rojo alrededor de la placa.
- Given que un vehículo no tiene placa visible (por ángulo o suciedad), When se analiza, Then no aparece bounding box rojo (sin falsos positivos forzados).
- Given que la placa está en la parte trasera, When el vehículo es detectado, Then el bounding box rojo aparece en la zona trasera del bounding box verde.

**Prioridad:** Must (MVP)

---

### HU-008 — Compensar movimiento de cámara PTZ
**Como** Operador de Seguridad,  
**quiero** que el tracking funcione correctamente incluso cuando la cámara PTZ se mueve,  
**para** que los IDs de vehículos no se pierdan por el movimiento mecánico de la cámara.

**Criterios de aceptación:**
- Given que la cámara PTZ está en posición A y detecta un vehículo con ID 5, When la cámara cambia a posición B y vuelve a A, Then el vehículo recupera el mismo ID 5 si sigue presente (modo patrullaje).
- Given que la cámara PTZ hace zoom 2×, When un vehículo es detectado, Then el bounding box se escala proporcionalmente sin perder el track.
- Given que configuro PTZ en modo tracking continuo, When la cámara sigue un vehículo, Then el sistema compensa el movimiento de fondo y mantiene IDs estables.

**Prioridad:** Should (Post-MVP Fase 2)

---

## Épica 3: OCR y Lectura de Placas

### HU-009 — Leer placa con OCR estándar
**Como** Operador de Seguridad,  
**quiero** que el sistema extraiga el texto de la placa y lo muestre sobre el video,  
**para** identificar inmediatamente el vehículo sin depender de revisión manual.

**Criterios de aceptación:**
- Given que una placa es detectada, When el OCR termina, Then el texto aparece junto al bounding box rojo en formato "Placa: ABC123".
- Given que el OCR no puede leer la placa, When falla la inferencia, Then se muestra "Placa: ???" y no se registra texto vacío en la base de datos.
- Given que la placa tiene espacios, When se extrae el texto, Then los espacios se eliminan y todo se convierte a mayúsculas.

**Prioridad:** Must (MVP)

---

### HU-010 — Estrategia de "mejor frame"
**Como** Administrador de Sistema,  
**quiero** que el sistema no haga OCR en el primer frame donde ve la placa, sino que espere al frame donde la placa sea más grande/nítida,  
**para** maximizar la precisión de lectura y no desperdiciar ciclos de CPU en imágenes lejanas o borrosas.

**Criterios de aceptación:**
- Given que un vehículo aparece lejano, When la placa es pequeña, Then el sistema no ejecuta OCR todavía.
- Given que el vehículo se acerca y la placa crece, When supera el área mínima configurada, Then el sistema actualiza la imagen candidata.
- Given que el vehículo sale de la ROI, When desaparece del frame, Then se ejecuta OCR únicamente sobre la mejor imagen guardada.

**Prioridad:** Must (MVP)

---

### HU-011 — Cache de OCR por vehículo
**Como** Administrador de Sistema,  
**quiero** que el sistema no repita el OCR en cada frame del mismo vehículo,  
**para** poder correr en hardware limitado sin saturar la CPU.

**Criterios de aceptación:**
- Given que un vehículo permanece 3 segundos en pantalla, When se procesan 90 frames, Then el OCR se ejecuta exactamente 1 vez (al final).
- Given que el vehículo vuelve a aparecer después de haber salido, When es detectado de nuevo, Then se ejecuta un nuevo OCR (nueva visita).

**Prioridad:** Must (MVP)

---

### HU-012 — Selección de backend OCR
**Como** Administrador de Sistema,  
**quiero** poder elegir entre PaddleOCR (precisión alta) y Tesseract (velocidad alta) según mi hardware,  
**para** balancear precisión y rendimiento sin cambiar código.

**Criterios de aceptación:**
- Given que configuro `ocr_backend = "paddle"`, When inicio el sistema, Then se carga PaddleOCR y se usan sus modelos.
- Given que configuro `ocr_backend = "tesseract"`, When inicio el sistema, Then se usa Tesseract y el inicio es casi instantáneo.
- Given un backend desconocido, When inicio, Then el sistema lanza un error claro y lista las opciones válidas.

**Prioridad:** Must (MVP)

---

### HU-013 — Tolerar ángulos extremos en cámaras móviles
**Como** Operador de Seguridad en patrulla móvil,  
**quiero** que el OCR lea placas incluso cuando el ángulo de incidencia sea de hasta 45°,  
**para** capturar placas desde vehículos en movimiento sin detenerme.

**Criterios de aceptación:**
- Given que la cámara móvil apunta a 45° respecto a la placa, When el OCR procesa, Then la precisión de lectura es ≥ 60 % (vs 85 % en frontal).
- Given que hay vibración del vehículo, When se capturan 5 frames en burst, Then el OCR elige el frame con menor blur y mayor área de placa.
- Given que no hay GPS disponible, When se lee una placa, Then el evento se registra sin coordenadas (no falla).

**Prioridad:** Could (Post-MVP Fase 3)

---

## Épica 4: Preprocesamiento y Tipos de Cámara

### HU-014 — Dewarping de cámara 360°
**Como** Administrador de Sistema,  
**quiero** que el sistema corrija la distorsión de una cámara fisheye/360° y extraiga vistas planas,  
**para** usar una sola cámara para vigilar toda una intersección sin puntos ciegos.

**Criterios de aceptación:**
- Given que configuro `type: fisheye` con parámetros de calibración válidos, When inicio el stream, Then se generan 4 vistas planas (norte, sur, este, oeste) sin distorsión curva.
- Given que una placa aparece en la vista "sur", When es detectada, Then el OCR la lee correctamente como si fuera una cámara estática.
- Given que configuro dewarping en perfil `EDGE_HOUSE`, When inicio, Then se lanza error: *"Dewarping requiere EDGE_NVR mínimo. Considere cámara con dewarping camera-side."*

**Prioridad:** Should (Post-MVP Fase 2)

---

### HU-015 — Detección térmica sin LPR
**Como** Operador de Seguridad,  
**quiero** que una cámara térmica detecte vehículos/personas en total oscuridad,  
**para** tener vigilancia nocturna sin iluminación IR visible que alerte a intrusos.

**Criterios de aceptación:**
- Given que configuro `type: thermal`, When inicio el stream, Then se detectan blobs de calor como vehículos o personas.
- Given que una cámara térmica detecta un vehículo, When no hay cámara visible emparejada, Then se publica `VEHICLE_DETECTED` con `has_plate: false` y no se intenta OCR.
- Given que hay una cámara visible emparejada, When la térmica detecta un vehículo, Then se activa la visible en modo burst para capturar la placa.

**Prioridad:** Should (Post-MVP Fase 3)

---

### HU-016 — Sincronización con trigger externo
**Como** Administrador de Sistema en peaje de alta velocidad,  
**quiero** que el sistema capture el frame exacto cuando un loop inductivo o radar detecta un vehículo a 80 km/h,  
**para** leer la placa nítida sin motion blur.

**Criterios de aceptación:**
- Given que un vehículo cruza el loop inductivo, When el trigger se activa, Then el sistema captura el frame en < 10 ms con shutter global y flash IR sincronizado.
- Given que el trigger falla (loop roto), When no hay señal en 5 segundos, Then el sistema loguea el error pero continúa operando en modo continuo (sin trigger).
- Given que configuro trigger en perfil `EDGE_HOUSE`, When inicio, Then se lanza warning: *"Trigger externo requiere hardware de interrupción. Verifique GPIO."*

**Prioridad:** Could (Post-MVP Fase 3)

---

## Épica 5: Eventos, Alertas y Comunicación

### HU-017 — Publicar evento de placa leída
**Como** Operador de Seguridad,  
**quiero** que cada placa leída se publique como un evento estructurado en el bus interno,  
**para** que otros módulos (base de datos, alertas) puedan reaccionar sin acoplarse al detector.

**Criterios de aceptación:**
- Given que el OCR lee "LU06153" con confianza 0.89, When finaliza el procesamiento, Then se publica un evento `PLATE_READ` con: track_id, texto, confianza, timestamp, bbox, stream_id.
- Given que un módulo de base de datos está suscrito, When llega el evento, Then se inserta el registro automáticamente.
- Given que no hay suscriptores, When se publica el evento, Then el sistema no falla; el evento se descarta silenciosamente.

**Prioridad:** Must (MVP)

---

### HU-018 — Alerta por placa desconocida
**Como** Operador de Seguridad,  
**quiero** recibir una alerta cuando un vehículo que NO está en la lista blanca ingresa al área,  
**para** tomar decisiones de seguridad en tiempo real.

**Criterios de aceptación:**
- Given que configuro una lista blanca con placas "ABC123" y "XYZ789", When ingresa un vehículo con placa "LMN456", Then se imprime en consola y log: "ALERTA: Vehículo desconocido LMN456".
- Given que ingresa un vehículo de la lista blanca, When es leído, Then no se genera alerta; solo se registra silenciosamente.
- Given que la lista blanca está vacía, When ingresa cualquier vehículo, Then todos se registran sin alertas.

**Prioridad:** Should (Post-MVP Fase 2)

---

### HU-019 — Alerta por Telegram
**Como** Residente / Usuario Final,  
**quiero** recibir un mensaje de Telegram cuando un vehículo desconocido o marcado como sospechoso ingresa,  
**para** estar informado incluso si no estoy frente al monitor de seguridad.

**Criterios de aceptación:**
- Given que configuro un bot token y chat_id, When ocurre una alerta, Then recibo un mensaje con texto, timestamp y crop de la placa adjunto.
- Given que Telegram no está disponible, When falla el envío, Then el sistema guarda el error en log y continúa operando.

**Prioridad:** Could (Post-MVP Fase 2)

---

## Épica 6: Persistencia y Consulta

### HU-020 — Guardar eventos en SQLite
**Como** Operador de Seguridad,  
**quiero** que todas las placas leídas se guarden en una base de datos local ligera,  
**para** consultar históricos sin depender de servidores externos.

**Criterios de aceptación:**
- Given que el sistema corre por 1 hora, When reviso la base de datos, Then existe una tabla `events` con columnas: id, stream_id, track_id, plate_text, confidence, timestamp, image_path.
- Given que consulto por placa "LU06153", When ejecuto la query, Then obtengo todos los registros de ese vehículo ordenados por fecha.
- Given que la base de datos crece, When supera 1 GB, Then el sistema puede archivar automáticamente registros antiguos (configurable).

**Prioridad:** Must (MVP)

---

### HU-021 — Exportar reporte de frecuencia
**Como** Operador de Seguridad,  
**quiero** exportar un CSV con la frecuencia de visitas por placa en un rango de fechas,  
**para** identificar patrones sospechosos (ej. mismo carro todos los días a la misma hora).

**Criterios de aceptación:**
- Given que selecciono rango 2026-06-01 a 2026-06-07, When exporto, Then el CSV contiene: placa, total_visitas, primera_hora, última_hora, días_distintos.
- Given que no hay datos en el rango, When exporto, Then se genera un CSV vacío con headers.

**Prioridad:** Should (Post-MVP Fase 2)

---

### HU-022 — Búsqueda de video por placa
**Como** Operador de Seguridad,  
**quiero** buscar el clip de video exacto donde apareció una placa específica,  
**para** revisar el contexto (¿con quién venía? ¿qué hizo después?).

**Criterios de aceptación:**
- Given que busco "LU06153", When hay coincidencias, Then el sistema me devuelve la ruta al archivo de video y el timestamp aproximado.
- Given que el video fue sobreescrito por rotación de discos, When busco, Then el sistema indica "video no disponible, solo metadatos".

**Prioridad:** Could (Post-MVP Fase 3)

---

## Épica 7: Escalabilidad y Arquitectura de Plugins

### HU-023 — Agregar detector sin tocar el núcleo
**Como** Desarrollador,  
**quiero** crear un nuevo detector (ej. personas) copiando una carpeta a `plugins/detectors/person_yolo/`,  
**para** extender el sistema sin riesgo de romper la detección de placas existente.

**Criterios de aceptación:**
- Given que creo `plugins/detectors/person_yolo/` con `plugin.yaml` y `detector.py`, When reinicio el sistema, Then el bus descubre automáticamente el plugin y comienza a publicar eventos `PERSON_DETECTED`.
- Given que el plugin tiene un error de sintaxis, When inicio el sistema, Then se carga el resto de plugins y se loguea el error del fallido sin crash general.
- Given que desactivo el plugin renombrando la carpeta, When reinicio, Then el bus ignora esa carpeta y no publica eventos de personas.

**Prioridad:** Should (MVP — arquitectura lista; detector de personas en Post-MVP)

---

### HU-024 — Agregar tipo de cámara como preprocessor
**Como** Desarrollador,  
**quiero** implementar soporte para un nuevo tipo de cámara (ej. cámara estéreo) creando un preprocessor plugin,  
**para** que el sistema pueda usar esa cámara sin modificar el núcleo ni los detectores existentes.

**Criterios de aceptación:**
- Given que creo `plugins/preprocessors/stereo_depth/` con `plugin.yaml` y `processor.py`, When configuro `type: stereo` en un stream, Then se carga automáticamente junto con los demás preprocessors.
- Given que el preprocessor genera un frame procesado, When pasa al detector, Then el detector no sabe que viene de una cámara estéreo; opera como si fuera estática.
- Given que el preprocessor falla, When lanza excepción, Then el stream se marca como `DEGRADED` pero los demás streams continúan.

**Prioridad:** Should (MVP — arquitectura lista; nuevos tipos en Post-MVP)

---

### HU-025 — Cambiar de bus local a MQTT
**Como** Administrador de Sistema,  
**quiero** cambiar una línea de configuración para que el Event Bus use MQTT en lugar de memoria local,  
**para** distribuir edges por un pueblo sin reescribir código.

**Criterios de aceptación:**
- Given que configuro `bus_type = "mqtt"` y proporciono `broker_url`, When inicio el sistema, Then los eventos se publican en el broker Mosquitto.
- Given que configuro `bus_type = "local"`, When inicio, Then todo funciona dentro del mismo proceso sin dependencias externas.
- Given que el broker MQTT cae, When el edge intenta publicar, Then encola localmente y reintenta cada 30 segundos.

**Prioridad:** Should (Arquitectura lista en MVP; activación en Post-MVP Fase 3)

---

### HU-026 — Panel web de consulta
**Como** Operador de Seguridad,  
**quiero** acceder a un panel web ligero desde mi celular o laptop,  
**para** buscar placas, ver eventos recientes y configurar alertas sin estar físicamente en el edge.

**Criterios de aceptación:**
- Given que abro `http://<ip-edge>:8080`, When cargo la página, Then veo una tabla con los últimos 50 eventos y un campo de búsqueda por placa.
- Given que filtro por fecha, When aplico el filtro, Then la tabla se actualiza sin recargar la página (AJAX/WebSocket).
- Given que accedo desde el celular, When cargo la página, Then el layout es responsive y legible.

**Prioridad:** Could (Post-MVP Fase 2)

---

## Épica 8: Privacidad y Cumplimiento

### HU-027 — Auto-borrado de datos
**Como** Administrador de Sistema,  
**quiero** configurar un tiempo de retención máximo (ej. 30 días) para imágenes y registros,  
**para** cumplir con leyes locales de protección de datos personales.

**Criterios de aceptación:**
- Given que configuro `retention_days = 30`, When un registro cumple 31 días, Then se elimina automáticamente de SQLite y del disco.
- Given que configuro `retention_days = 0`, When inicio, Then se desactiva el auto-borrado (modo forense).
- Given que un registro está marcado como "evidencia judicial", When llega su fecha de expiración, Then NO se borra y se loguea la retención forzada.

**Prioridad:** Should (Post-MVP Fase 2)

---

### HU-028 — No almacenar rostros
**Como** Residente,  
**quiero** que el sistema nunca guarde imágenes de mi rostro ni del conductor,  
**para** proteger mi privacidad mientras se vigila el acceso vehicular.

**Criterios de aceptación:**
- Given que un vehículo es detectado, When se guarda el crop, Then solo se almacena la región de la placa (bounding box rojo), nunca la zona del parabrisas o conductor.
- Given que se configura un detector de personas (Post-MVP), When detecta peatones, Then los eventos se publican con metadatos (bbox, timestamp) pero sin guardar imagen del peatón.
- Given que un técnico intenta modificar el código para guardar rostros, When el sistema detecta la modificación (hash de archivos), Then se niega a iniciar y loguea "integridad comprometida".

**Prioridad:** Must (MVP — principio arquitectónico)

---

## Mapa de Prioridades (Resumen)

| ID | Historia | Épica | Prioridad | Fase | Componente Arquitectónico | Estado |
|----|----------|-------|-----------|------|--------------------------|--------|
| HU-001 | Fuente de video | Ingesta | Must | MVP | `streams/base.py`, `streams/file_stream`, `usb_stream`, `rtsp_stream` | Planificado |
| HU-002 | ROI sin GUI | Ingesta | Must | MVP | `preprocessors/roi/`, `tools/calibrate.py` | Completado |
| HU-003 | Perfil de hardware | Ingesta | Must | MVP | `config/profiles.py`, `core/registry.py` | Planificado |
| HU-004 | Tipo de cámara | Ingesta | Must | MVP (arquitectura) | `core/pipeline_orchestrator.py`, `streams/base.py` | Planificado |
| HU-005 | Detectar vehículos | Detección | Must | MVP | `plugins/detectors/vehicle_yolo/` | Completado |
| HU-006 | Tracking | Detección | Must | MVP | `tracking/plate_tracker.py` | Completado |
| HU-007 | Detectar placas | Detección | Must | MVP | `plugins/detectors/plate_yolo/` | Planificado |
| HU-008 | Compensar PTZ | Detección | Should | Fase 2 | `preprocessors/roi/ptz_compensated.py`, `streams/ptz_stream.py` | Planificado |
| HU-009 | Leer placa OCR | OCR | Must | MVP | `plugins/ocr_backends/` | Planificado |
| HU-010 | Mejor frame | OCR | Must | MVP | `tracking/plate_tracker.py` | Completado |
| HU-011 | Cache OCR | OCR | Must | MVP | `tracking/plate_tracker.py` | Completado |
| HU-012 | Backend OCR | OCR | Must | MVP | `plugins/ocr_backends/` | Planificado |
| HU-013 | Ángulos extremos móvil | OCR | Could | Fase 3 | `plugins/ocr_backends/` (modelos entrenados) | Planificado |
| HU-014 | Dewarping 360° | Preprocesamiento | Should | Fase 2 | `preprocessors/dewarp/` | Planificado |
| HU-015 | Detección térmica | Preprocesamiento | Should | Fase 3 | `streams/thermal_stream.py`, `plugins/detectors/` | Planificado |
| HU-016 | Trigger externo | Preprocesamiento | Could | Fase 3 | `preprocessors/trigger_sync/`, `streams/triggered_stream.py` | Planificado |
| HU-017 | Event Bus local | Eventos | Must | MVP | `core/bus.py` | Parcial |
| HU-018 | Alerta desconocido | Alertas | Should | Fase 2 | `plugins/outputs/` (whitelist logic) | Planificado |
| HU-019 | Telegram | Alertas | Could | Fase 2 | `plugins/outputs/telegram_bot/` | Planificado |
| HU-020 | SQLite | Persistencia | Must | MVP | `plugins/outputs/sqlite_local/` | Planificado |
| HU-021 | Reporte CSV | Persistencia | Should | Fase 2 | `plugins/outputs/sqlite_local/` (export) | Planificado |
| HU-022 | Búsqueda video | Persistencia | Could | Fase 3 | `plugins/outputs/` (video index) | Planificado |
| HU-023 | Plugin detector | Escalabilidad | Should | MVP (arquitectura) | `core/registry.py`, `plugins/base.py` | Parcial |
| HU-024 | Preprocessor cámara | Escalabilidad | Should | MVP (arquitectura) | `core/registry.py`, `preprocessors/base.py` | Parcial |
| HU-025 | Bus swappable | Escalabilidad | Should | MVP (arquitectura) | `core/bus.py` (MQTT/Redis impls) | Parcial |
| HU-026 | Panel web | Escalabilidad | Could | Fase 2 | `web/` (Post-MVP, no definido en estructura) | Planificado |
| HU-027 | Auto-borrado | Privacidad | Should | Fase 2 | `plugins/outputs/` (retention manager) | Planificado |
| HU-028 | No rostros | Privacidad | Must | MVP | `plugins/detectors/` (crop policy), `core/` (hash integrity) | Planificado |

---

## Trazabilidad HU → Implementación

La columna **Estado** en las tablas siguientes refleja el estado real de cada HU a partir del Slice 1.0.

### Estados posibles

| Estado | Significado |
|--------|-------------|
| Planificado | HU definida y aceptada, pendiente de asignar a un slice |
| En progreso | Slice asignado, implementación en curso |
| Parcial | Arquitectura/componente habilitante existe, pero la funcionalidad completa no está implementada |
| Completado | Slice implementado, tests pasan, DoD cumplido |
| Bloqueado | Dependencia externa no resuelta (hardware, modelo, decisión pendiente) |

### Mapa de trazabilidad HU → Slice

Los slices 0.3–0.9 son infraestructura base (Event Bus, Registry, Pipeline, Streams). No se mapean directamente a HUs de valor funcional, pero habilitan todas las HUs del MVP. El estado de cada slice se registra en `DESARROLLO.md`.

A partir del Slice 1.0, cada slice se vincula explícitamente a una o más HUs:

| Slice | HU(s) | Descripción | ARQUITECTURA § | Tests | Estado |
|-------|-------|-------------|----------------|-------|--------|
| 1.0 | HU-002 | ROI estático desde YAML + herramienta de calibración | §5, §7 | `tests/unit/test_roi_preprocessor.py`, `tests/unit/test_calibrate_tool.py` | Completado |
| 1.1 | HU-005 | Detección de vehículos con YOLO | §7 | `tests/unit/test_vehicle_yolo.py`, `tests/unit/test_detector_base.py`, `tests/unit/test_frame_store.py`, `tests/unit/test_vehicle_detector_handler.py` | Completado |
| 1.2 | HU-006, HU-010, HU-011 | Tracking de mejor-frame y cache por track_id | §7 | `tests/unit/test_plate_tracker.py` | Completado |
| 1.3 | HU-007, HU-009, HU-012 | Detección de placas + OCR (Paddle/Tesseract) | §7 | `tests/integration/test_plate_ocr.py` | Planificado |
| 1.4 | HU-020, HU-017 | Persistencia SQLite + pipeline completo | §4, §7 | `tests/integration/test_pipeline.py` | Planificado; HU-017 parcial por infraestructura base existente |

> A medida que los slices avancen, esta tabla se actualizará reflejando el estado real de cada HU.

---

> *"Cada historia es un contrato entre el usuario y el sistema. Las historias MVP construyen la fundación; las post-MVP construyen el futuro."*
