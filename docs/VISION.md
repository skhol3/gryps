# Visión del Proyecto Gryps

> **Versión:** 1.1  
> **Fecha:** 2026-06-02  
> **Autor:** Equipo Gryps  
> **Estado:** Arquitectura definida — implementación de software no iniciada  
> **Audiencia:** Stakeholders, Desarrolladores, Arquitectos de Solución

---

## 1. RESUMEN EJECUTIVO

- **Nombre del proyecto:** Gryps (License Plate Recognition & Urban Video Analytics Platform)
- **Propósito (en 1 oración):** Construir una plataforma de video-analytics *edge-first* que detecte, rastree y lea placas vehiculares en hardware limitado, evolucionando hacia un sistema de seguridad urbana multi-cámara, multi-detector y multi-tipo-de-cámara.
- **Audiencia principal:** Administradores de seguridad residencial, juntas de acción comunal, pequeñas alcaldías y empresas de vigilancia privada que necesitan control de acceso vehicular y análisis de video sin depender de cloud ni hardware costoso.
- **Estado actual:** Arquitectura definida. Validación de conceptos (detección YOLO11n, OCR PaddleOCR/Tesseract) probada en notebooks/scripts independientes sobre i5 2014 / 8 GB RAM. La plataforma Gryps como software integrado no ha sido implementada: solo existe el esqueleto del proyecto (main.py, pyproject.toml).

---

## 2. OPORTUNIDAD DE NEGOCIO

### 2.1 Problema Actual

- **¿Qué proceso manual o deficiente existe hoy?**
  - Los barrios residenciales y pequeños pueblos controlan el acceso vehicular con guardias de seguridad que anotan placas a mano o con cámaras de video pasivo sin capacidad de lectura automática.
  - No existe trazabilidad de quién entró, cuándo y con qué frecuencia. Los registros manuales son propensos a errores, lentos y no permiten búsquedas retrospectivas.
  - Las soluciones comerciales (VaxALPR, Genetec, etc.) requieren licencias costosas, hardware específico y conectividad a cloud, haciéndolas inaccesibles para presupuestos municipales o residenciales.
  - Los sistemas existentes asumen cámaras estáticas profesionales; no soportan PTZ, 360°, térmicas ni móviles sin reemplazo completo.

- **¿Quién lo sufre y cómo?**
  - **Residentes de conjuntos cerrados:** No tienen registro confiable de visitantes ni alertas de vehículos sospechosos.
  - **Administradores de seguridad:** Dependen de la memoria humana para identificar patrones (ej. "ese carro ha pasado 5 veces esta semana").
  - **Alcaldías de pueblos pequeños:** No pueden justificar la inversión en sistemas enterprise pero sí necesitan control de acceso a zonas peatonales, parques o centros históricos.
  - **Instaladores técnicos:** Deben configurar ROI en campo con monitor y mouse, imposibilitando despliegues remotos o headless.

### 2.2 Solución Propuesta

- **¿Qué va a hacer el software?**
  - Gryps es una plataforma de software que se instala en una PC común o mini-PC edge (incluso uno viejo), conecta a cámaras IP, USB, RTSP, PTZ, 360° o térmicas existentes y, usando inteligencia artificial local, detecta vehículos, lee sus placas y genera un registro consultable con alertas en tiempo real.
  - La arquitectura es modular y *camera-agnostic*: hoy lee placas desde una cámara estática; mañana detecta personas desde una 360°, fuego desde una térmica, o patrulla con una PTZ sin reescribir el núcleo.

- **¿Qué beneficio inmediato genera?**
  - **Costo cero de licencias:** Software open-source con modelos descargables.
  - **Privacidad:** Todo el procesamiento ocurre en el edge; los videos no salen de la red local.
  - **Trazabilidad:** Base de datos local con búsqueda por placa, fecha, hora y frecuencia de visitas.
  - **Escalabilidad:** Un pueblo puede empezar con 1 cámara en una esquina y crecer a 50 cámaras de tipos heterogéneos con un panel central sin cambiar de plataforma.
  - **Despliegue headless:** ROI y calibración se hacen una sola vez en herramienta externa; el edge opera sin monitor ni interacción humana.

---

## 3. DESCRIPCIÓN DEL PRODUCTO

### Módulo A: Ingesta de Video (Video Ingest)

| Funcionalidad | Descripción |
|---------------|-------------|
| Fuente múltiple | Soporta archivos de video, cámaras USB, streams RTSP, ONVIF, cámaras 360° (fisheye/equirectangular), PTZ vía ONVIF, y cámaras térmicas. |
| Abstracción de tipo de cámara | El núcleo no conoce el tipo de cámara; los `preprocessors` específicos (dewarp, PTZ compensation, EIS) se cargan como plugins encadenados. |
| ROI configurable | ROI estático por YAML, poligonal, auto-motion, o interactivo (herramienta externa `gryps.tools.calibrate`). Nunca requiere GUI en el edge. |
| Dewarping 360° | Proyección esférica a múltiples vistas planas (norte, sur, este, oeste) con parámetros intrínsecos calibrables. |
| Ring buffer | Mantiene un buffer circular de los últimos N segundos para poder extraer contexto cuando ocurre un evento. |
| Resolución adaptativa | Escala automáticamente la resolución de entrada según el perfil de hardware (EDGE_HOUSE vs EDGE_NVR). |

### Módulo B: Detección y Tracking (Detection & Tracking)

| Funcionalidad | Descripción |
|---------------|-------------|
| Detección de vehículos | Usa YOLO (configurable: YOLO11n, YOLO11s, etc.) para detectar carros, motos, buses y camiones. |
| Tracking multi-objeto | Mantiene IDs únicos por vehículo a través de frames usando BoT-SORT (vía Ultralytics). |
| Detección de placas | Modelo especializado (l.pt) que recorta la región de la placa dentro del bounding box del vehículo. |
| Compensación PTZ | Egocompensation para tracking con cámaras motorizadas (lee posición ONVIF, ajusta coordenadas). |
| Plugin-ready | Arquitectura de plugins que permite agregar nuevos detectores (personas, fuego, animales) sin tocar el núcleo. |

### Módulo C: Reconocimiento Óptico de Caracteres (OCR / LPR)

| Funcionalidad | Descripción |
|---------------|-------------|
| OCR multi-backend | Soporta PaddleOCR (precisión alta, CPU intensivo) y Tesseract (rápido, ligero) seleccionables por perfil. |
| Mejor-frame | No lee la placa en el primer frame; guarda la mejor imagen (mayor área/nitidez) mientras el vehículo está visible y ejecuta OCR al desaparecer o al alcanzar umbral de calidad. |
| Normalización | Limpia espacios, fuerza mayúsculas y filtra caracteres no alfanuméricos. |
| Cache por track | Evita re-procesar el mismo vehículo múltiples veces. |
| Tolerancia a ángulos | En cámaras móviles o PTZ, tolera incidencias hasta 45° con modelos entrenados específicamente. |

### Módulo D: Event Bus y Orquestación

| Funcionalidad | Descripción |
|---------------|-------------|
| Bus de eventos local | Cola en memoria para hogar (0 latencia, sin dependencias externas). |
| Bus MQTT (futuro) | Publicación de eventos a un broker Mosquitto para arquitecturas distribuidas (pueblo). |
| Bus Redis (futuro) | Agregación multi-pueblo en cloud hub. |
| Vocabulario común | Eventos tipados: `VEHICLE_DETECTED`, `PLATE_READ`, `PERSON_DETECTED`, `FIRE_ALERT`, `PTZ_POSITION_CHANGED`, `EXTERNAL_TRIGGER`, etc. |
| Desacoplamiento | Los detectores, el OCR y los consumidores finales no se conocen entre sí; solo publican/suscriben al bus. |

### Módulo E: Persistencia y Salida (Storage & Output)

| Funcionalidad | Descripción |
|---------------|-------------|
| SQLite local | Base de datos ligera para hogar: placas, timestamps, confianza, imagen de referencia. |
| PostgreSQL (futuro) | Base relacional para NVR central de pueblo con índices geoespaciales y búsqueda full-text. |
| Exportación | CSV, JSON y reportes de frecuencia de visitas. |
| Alertas | Consola local, log de archivo, Telegram bot y webhook HTTP (futuro). |
| Geolocalización | Para cámaras móviles: cada PLATE_READ incluye lat/lon del GPS integrado. |

### Módulo F: Panel de Administración (Futuro Post-MVP)

| Funcionalidad | Descripción |
|---------------|-------------|
| Dashboard web | Visualización de eventos en tiempo real, mapa de calor de tráfico y búsqueda de placas. |
| Gestión de cámaras | Alta/baja de streams, configuración de ROI y horarios de vigilancia por cámara. Soporte multi-tipo (estática, PTZ, 360°, térmica). |
| Calibración remota | Herramienta web para ajustar ROI, dewarping y parámetros PTZ sin estar físicamente en el edge. |
| Listas de control | Listas blancas (residentes) y negras (alerta inmediata). |
| Métricas | FPS promedio, latencia de detección, precisión de OCR, uso de CPU/RAM, carga por tipo de cámara. |

### Módulo G: Herramientas de Calibración (Calibration Tools)

| Funcionalidad | Descripción |
|---------------|-------------|
| ROI picker interactivo | Script con GUI (`gryps.tools.calibrate`) que corre en laptop del técnico, no en el edge. Captura frame, permite dibujar ROI/polígono/dewarp, y genera YAML para el edge. |
| Auto-calibración | Modo `auto_motion` que analiza 300 frames y sugiere ROI basado en blobs de movimiento. |
| Validación de configuración | Al arranque, verifica que los parámetros de dewarping, PTZ o ROI sean consistentes con el tipo de cámara declarado. |

---

## 4. USUARIOS Y ROLES

| Rol | Descripción | Qué puede hacer | Qué NO puede hacer |
|-----|-------------|-----------------|-------------------|
| **Administrador de Sistema** | Instala y configura el software en el edge. Técnico de confianza. | Elegir perfil de hardware, cambiar modelos de IA, definir ROIs (vía herramienta externa o YAML), gestionar plugins, configurar tipos de cámara, calibrar dewarping/PTZ. | Acceder a videos históricos sin permiso del propietario (auditoría). |
| **Operador de Seguridad** | Vigila el tráfico y consulta registros. Guardia de seguridad o administrador del conjunto. | Ver eventos en tiempo real, buscar placas por fecha/hora, exportar reportes, marcar vehículos como sospechosos, consultar mapa de cámaras. | Modificar modelos de IA, cambiar configuración de cámaras, desactivar el sistema, calibrar ROI o dewarping. |
| **Residente / Usuario Final** | Persona que vive en el conjunto o visita el pueblo. | Consultar su propio historial de entradas (si se habilita), recibir alertas de visitas esperadas, ver dashboard público (si existe). | Ver datos de otros residentes, acceder a video de terceros, modificar listas de control. |
| **Instalador Técnico** | Profesional que monta cámaras físicas y calibra el sistema en campo. | Usar `gryps.tools.calibrate` para capturar frames, definir ROI, ajustar dewarping, verificar cobertura de cámara PTZ. | Acceder a base de datos de eventos, modificar perfiles de hardware, instalar plugins de terceros. |
| **Auditor / Fiscalía (futuro)** | Autoridad que requiere evidencia. | Solicitar exportación de eventos en un rango de tiempo con cadena de custodia digital. | Acceso directo al sistema; todo debe ser mediado por el administrador. |

---

## 5. ALCANCE (MVP vs Futuro)

### MVP (primera versión — objetivo: 6-8 semanas)

> **Nota sobre el estado de desarrollo:** Las capacidades individuales (YOLO, OCR) fueron validadas en prototipos aislados, pero ninguna está integrada como funcionalidad de la plataforma Gryps. Todos los ítems siguientes están planificados para el MVP; ninguno está implementado aún.

- [ ] Detección de vehículos con YOLO11n en video de archivo o cámara USB/RTSP estática.
- [ ] Detección de placas con modelo propio (`l.pt`).
- [ ] OCR con PaddleOCR y fallback a Tesseract.
- [ ] Lógica de "mejor frame": guardar la mejor placa y leer al desaparecer el vehículo.
- [ ] Cache por track_id para no repetir OCR.
- [ ] ROI estático por YAML (headless-friendly); herramienta interactiva opcional para calibración inicial.
- [ ] Salida a consola y SQLite local.
- [ ] Arquitectura modular con Event Bus en memoria (preparación para futuro).
- [ ] Perfil de hardware `EDGE_HOUSE` optimizado para CPU vieja (i5 2014, 8 GB RAM).
- [ ] Abstracción de tipo de cámara: cámara estática soportada; arquitectura lista para PTZ, 360°, térmica, móvil.

### Post-MVP — Fase 2: Seguridad Residencial Multi-Cámara (3-6 meses)

- [ ] Soporte para 2-4 cámaras simultáneas en un mismo edge, incluyendo mix de estáticas y una 360°.
- [ ] Preprocessor `dewarp_fisheye` para cámaras 360° (extraer 4 vistas planas).
- [ ] Preprocessor `ptz_compensator` para PTZ en modo patrullaje.
- [ ] Perfil `EDGE_NVR` con PostgreSQL local.
- [ ] Plugin detector de personas como plugin adicional.
- [ ] Alertas por Telegram bot (vehículo desconocido, persona en horario nocturno).
- [ ] Lista blanca/negra de placas con alerta inmediata.
- [ ] Dashboard web ligero (Flask/FastAPI) para consulta de eventos y calibración remota de ROI.

### Post-MVP — Fase 3: Seguridad de Pueblo (6-12 meses)

- [ ] Arquitectura distribuida: edges ligeros (Raspberry Pi / Jetson Nano) por esquina + NVR central.
- [ ] Soporte cámara térmica como detector de intrusión (sin LPR), trigger para cámara visible emparejada.
- [ ] Cámara móvil/vehicular con GPS integrado y estabilización EIS.
- [ ] Event Bus vía MQTT con broker local en el NVR.
- [ ] Panel central web con mapa de cámaras, búsqueda cross-cámara y análisis de patrones.
- [ ] Nuevos detectores: fuego/humo, objetos abandonados, conteo de afluencia peatonal.
- [ ] Integración con sistemas de emergencia (webhook a bomberos/policía).
- [ ] Soporte para cámaras con trigger externo (loop inductivo, radar) para alta velocidad.

### Post-MVP — Fase 4: Inteligencia Predictiva (12+ meses)

- [ ] Análisis de patrones: "este vehículo visita cada martes a las 10 PM".
- [ ] Reconocimiento de comportamiento anómalo (circular en círculos, detención prolongada).
- [ ] Integración con bases de datos vehiculares oficiales (donde la legislación lo permita).
- [ ] App móvil para residentes con notificaciones push.
- [ ] Auto-calibración de ROI basada en análisis de tráfico histórico.

---

## 6. OBJETIVOS Y MÉTRICAS

| Objetivo | Cómo medirlo | Meta MVP |
|----------|--------------|----------|
| **Precisión de lectura de placas** | Porcentaje de placas leídas correctamente vs ground truth en un dataset de prueba. | ≥ 85 % en condiciones diurnas, ≥ 70 % en nocturnas. |
| **Rendimiento en edge** | FPS sostenido en el hardware objetivo (i5 2014, 8 GB RAM, sin GPU). | ≥ 5 FPS con 1 cámara estática a 640×480, skip=3, Tesseract. |
| **Latencia de alerta** | Tiempo desde que el vehículo cruza la ROI hasta que la placa está en la base de datos. | ≤ 3 segundos. |
| **Falsos positivos OCR** | Textos leídos que no son placas (ej. leyó "STOP" o publicidad). | ≤ 10 % de las detecciones. |
| **Uso de recursos** | CPU % y RAM MB durante operación normal. | CPU ≤ 80 %, RAM ≤ 6 GB. |
| **Tiempo de setup** | Desde instalar el software hasta primera detección funcional. | ≤ 30 minutos para un técnico semi-capacitado. |
| **Compatibilidad de cámaras** | Tipos de cámara soportados sin modificar el núcleo. | 1 tipo (estática) en MVP; arquitectura lista para 6+. |

---

## 7. SUPUESTOS Y RESTRICCIONES

### Supuestos

- El usuario tiene acceso físico al lugar donde instalará el edge (PC o mini-PC) y puede conectar cámaras vía USB o red local.
- Las placas vehiculares siguen un formato alfanumérico predecible (latinoamericano / mercosur).
- Las cámaras existentes tienen resolución mínima de 720p y iluminación suficiente para distinguir placas a ≤ 15 metros (cámaras estáticas).
- El hardware edge tiene al menos 4 núcleos de CPU y 4 GB de RAM libres para el software.
- El usuario tiene conectividad a Internet solo para descarga inicial de modelos; el funcionamiento diario es offline-capable.
- Para cámaras no-estáticas (PTZ, 360°, móvil, térmica), el instalador tiene conocimiento técnico para calibrar parámetros específicos (dewarping, ONVIF, GPS, trigger hardware).

### Restricciones

- **Privacidad:** No se almacenarán imágenes de rostros de conductores ni de peatones sin consentimiento explícito. Solo se guardan crops de placas y metadatos.
- **Legal:** El software debe permitir configurar tiempos de retención de datos (ej. auto-borrar después de 30 días) para cumplir con leyes locales de protección de datos.
- **Hardware mínimo:** No se garantiza funcionamiento en hardware inferior a Intel Core i3 4ª gen / 4 GB RAM / sin AVX2 para cámaras estáticas. Cámaras 360° requieren EDGE_NVR mínimo.
- **Open source:** Los modelos de IA deben ser descargables sin licencias propietarias restrictivas (ultralytics, paddleocr, tesseract son compatibles).
- **Sin cloud obligatorio:** El MVP debe funcionar 100 % offline. Las funciones cloud son opt-in futuro.
- **Sin GUI en edge:** El edge opera headless. Toda interacción gráfica (calibración ROI, dewarping) ocurre en herramienta externa o panel web remoto.
- **Cámara térmica:** No realiza LPR directo. Es detector complementario que requiere cámara visible emparejada para lectura de placas.

---

## 8. CRITERIOS DE ÉXITO

1. **El sistema lee correctamente ≥ 85 % de las placas** que pasan por la ROI en condiciones de día con buena iluminación, usando hardware de 2014.
2. **Un administrador no-técnico puede instalar y operar el sistema** en menos de 1 hora sin ayuda externa, siguiendo solo la documentación.
3. **La arquitectura permite agregar un nuevo tipo de cámara** (ej. 360°) o un nuevo detector (ej. personas) en menos de 1 día de desarrollo sin modificar el núcleo del sistema.
4. **El sistema escala de 1 cámara estática en una casa a 20 cámaras heterogéneas en un pueblo** (estáticas, PTZ, 360°, térmicas) sin reescribir el código base; solo cambiando perfiles de configuración y agregando hardware.
5. **La latencia entre detección y registro es imperceptible** para un operador de seguridad (< 3 segundos).
6. **El costo total de hardware para una instalación básica** (1 cámara + PC usada) es menor al 10 % del costo de una solución comercial equivalente.
7. **El edge puede operar indefinidamente sin monitor ni interacción humana** después de la calibración inicial.

---

## 9. GLOSARIO

| Término | Significado |
|---------|-------------|
| **Edge** | Dispositivo de computación local (PC, NUC, Raspberry Pi) donde corre el procesamiento de video, opuesto a "cloud". |
| **Event Bus** | Sistema de comunicación desacoplado donde los componentes publican y suscriben eventos sin conocerse entre sí. |
| **FPS** | Frames Por Segundo. Métrica de rendimiento del pipeline de video. |
| **LPR** | License Plate Recognition. Reconocimiento automático de placas vehiculares. |
| **MVP** | Minimum Viable Product. La versión mínima funcional que resuelve el problema principal. |
| **NVR** | Network Video Recorder. Dispositivo central que recibe, graba y analiza video de múltiples cámaras IP. |
| **OCR** | Optical Character Recognition. Tecnología para convertir imágenes de texto en texto editable. |
| **ONVIF** | Open Network Video Interface Forum. Estándar para comunicación entre cámaras IP y sistemas de vigilancia. |
| **Plugin** | Módulo de software independiente que se carga dinámicamente para extender funcionalidad sin modificar el núcleo. |
| **Preprocessor** | Plugin encadenado antes del detector que transforma el frame (dewarping, ROI, estabilización, etc.). |
| **ROI** | Region of Interest. Área rectangular o poligonal dentro del frame de video donde se restringe el análisis para ahorrar recursos. |
| **RTSP** | Real Time Streaming Protocol. Protocolo estándar para transmitir video en tiempo real desde cámaras IP. |
| **Track ID** | Identificador único numérico asignado a un objeto (vehículo, persona) para seguirlo a través de múltiples frames. |
| **YOLO** | You Only Look Once. Familia de modelos de detección de objetos en tiempo real. |
| **Dewarping** | Corrección de distorsión de lentes ultra-wide (fisheye/360°) para obtener vistas planas usables. |
| **EIS** | Electronic Image Stabilization. Tecnología para compensar vibración en cámaras móviles. |
| **PTZ** | Pan-Tilt-Zoom. Cámara motorizada controlable remotamente. |
| **Global Shutter** | Sensor que expone todos los píxeles simultáneamente, eliminando deformación en objetos en movimiento rápido. |

---

> *"Gryps nace de la necesidad de democratizar la seguridad inteligente. Hoy una casa con una cámara estática, mañana un pueblo con cámaras de todo tipo."*
