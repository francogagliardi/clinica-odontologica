# agenda/reserva-publica Specification

## Purpose
Permite que un paciente reserve un turno 24/7 desde un enlace público sin sesión: muestra disponibilidad real, crea el turno con las mismas garantías de C-06, marca la seña pendiente cuando corresponde y entrega un enlace de gestión protegido por un token opaco de un solo uso (RN-NO-03). Incluye la página pública que consume esos endpoints.

## Requirements

### Requirement: Catálogo público del consultorio

El sistema SHALL exponer `GET /reservar/{slug}` sin autenticación con los datos mínimos para reservar: nombre del consultorio, profesionales activos, prestaciones activas (duración, precio y seña) y las políticas de cancelación y seña. No SHALL incluir datos de contacto de usuarios, pacientes ni tokens.

**Trazabilidad**: US-001/CA-1 (`06_funcionalidades.md`), Flujo 1 (`07_flujos_principales.md`), RN-TU-04/RN-TU-08, `03_actores_y_roles.md` §Rutas públicas, RN-NO-03.

#### Scenario: Consultorio público con catálogo
- **WHEN** un visitante sin token hace `GET /reservar/demo`
- **THEN** el sistema responde HTTP 200 con el consultorio, sus profesionales y prestaciones activas
- **AND** incluye `plazo_cancelacion_horas`, el texto de política de seña y `validacion_externa: false` sin exponer emails ni credenciales

#### Scenario: Consultorio inexistente o dado de baja
- **WHEN** el slug no corresponde a un consultorio activo
- **THEN** el sistema responde HTTP 404

#### Scenario: Recursos inactivos excluidos
- **WHEN** un profesional o una prestación tiene baja lógica
- **THEN** no aparece en el catálogo público

#### Scenario: Sin JWT de sesión
- **WHEN** el visitante no envía encabezado Authorization
- **THEN** el catálogo responde HTTP 200: estas rutas son públicas por diseño

### Requirement: Disponibilidad pública real

El sistema SHALL exponer `GET /reservar/{slug}/disponibilidad` sin autenticación, con los mismos slots reales que C-06 (agenda, bloqueos, turnos activos y retenciones vigentes de lista de espera), filtrables por fecha, profesional y prestación. La consulta SHALL rechazar parámetros no declarados y recursos inexistentes o inactivos.

**Trazabilidad**: US-001/CA-1, Flujo 1 paso 1, RN-TU-01/RN-TU-02/RN-TU-05/RN-TU-07 (`05_reglas_de_negocio.md:7–11`), RN-NO-03, `agenda/lista-espera` §Retención atómica del hueco ofrecido.

#### Scenario: Slots públicos con la duración de la prestación
- **WHEN** se consulta una fecha habilitada con `profesional_id` y `prestacion_id`
- **THEN** responde HTTP 200 con los slots libres de esa duración, sin los turnos activos ni bloqueos

#### Scenario: Recurso inexistente o inactivo
- **WHEN** el profesional o la prestación no existen o están dados de baja
- **THEN** el sistema responde HTTP 404 y no calcula slots

#### Scenario: Fecha inválida o parámetro extra
- **WHEN** la fecha tiene formato inválido o se envía un parámetro no declarado
- **THEN** el sistema responde HTTP 422

#### Scenario: Día sin atención
- **WHEN** la fecha cae fuera de los días de atención del profesional
- **THEN** responde HTTP 200 con lista vacía

#### Scenario: Retención vigente oculta el slot
- **WHEN** una oferta de lista de espera vigente retiene un intervalo del profesional consultado
- **THEN** ese slot no aparece en la respuesta pública aunque no exista un turno activo

#### Scenario: Retención vencida no oculta el slot
- **WHEN** la retención tiene `oferta_expira_en` en el pasado y el worker todavía no la barrió
- **THEN** el slot vuelve a aparecer en la disponibilidad pública

### Requirement: Reserva pública con paciente existente o nuevo

El sistema SHALL crear un turno `reservado` desde `POST /reservar/{slug}/turnos` sin JWT, con nombre, apellido, DNI y teléfono del paciente, profesional, prestación opcional e inicio. SHALL normalizar DNI y teléfono, buscar al paciente por DNI y reutilizarlo si el teléfono coincide. SHALL calcular el fin con la duración de C-06 y aplicar anti-solapamiento y bloqueos.

**Trazabilidad**: US-001/CA-2, Flujo 1 pasos 1–2, RN-TU-01/RN-TU-02/RN-TU-07, `04_modelo_de_datos.md` §Paciente.

#### Scenario: Paciente nuevo reserva con éxito
- **WHEN** el visitante envía datos válidos de un DNI inexistente y un slot libre
- **THEN** responde HTTP 201 con estado `reservado`, el `fin` derivado y un `paciente_id` nuevo
- **AND** el paciente se crea con DNI y teléfono normalizados

#### Scenario: Paciente existente con el mismo teléfono
- **WHEN** el DNI ya existe y el teléfono normalizado coincide
- **THEN** responde HTTP 201, reutiliza el paciente y no duplica la fila

#### Scenario: DNI existente con otro teléfono
- **WHEN** el DNI ya existe pero el teléfono no coincide
- **THEN** responde HTTP 409 y no crea turno ni modifica al paciente

#### Scenario: Teléfono o DNI inválido
- **WHEN** el teléfono no es un celular argentino válido o el DNI no tiene 7–8 dígitos
- **THEN** responde HTTP 422 y la transacción no deja paciente ni turno creado

#### Scenario: Slot tomado por otra reserva concurrente
- **WHEN** dos reservas públicas simultáneas apuntan al mismo slot
- **THEN** exactamente una responde HTTP 201 y la otra HTTP 409

#### Scenario: Turno público que se solapa o cae en bloqueo
- **WHEN** el slot se solapa con un turno activo o con un bloqueo
- **THEN** responde HTTP 409 y no crea nada

### Requirement: Asignación automática de sillón

El sistema SHALL elegir un sillón activo libre para la reserva pública, prefiriendo los habilitados para el profesional. Si no hay ninguno libre, SHALL responder 409 sin crear el turno. El paciente no SHALL poder imponer un sillón.

**Trazabilidad**: RN-TU-01 (el sillón es recurso de exclusión), `04_modelo_de_datos.md` §Sillon/§ProfesionalSillon, US-001.

#### Scenario: Elige un sillón libre
- **WHEN** hay dos sillones y uno está ocupado en ese horario
- **THEN** el turno se crea en el sillón libre

#### Scenario: Prefiere sillones habilitados
- **WHEN** el profesional tiene habilitado un subconjunto de sillones
- **THEN** solo se consideran esos sillones para la asignación

#### Scenario: Sin sillón disponible
- **WHEN** todos los sillones activos están ocupados o bloqueados en el horario
- **THEN** responde HTTP 409 y no crea el turno

#### Scenario: Intento de imponer sillón
- **WHEN** el body público incluye `sillon_id` o cualquier campo no declarado
- **THEN** responde HTTP 422 porque el paciente no elige el recurso físico

### Requirement: Seña pendiente y política visible

Cuando la prestación tenga `requiere_sena=true`, el turno público SHALL nacer con `sena_estado = pendiente` y la respuesta SHALL informar monto y política de pérdida (RN-TU-04) además de la política de cancelación del consultorio. Sin seña, `sena_estado` SHALL ser `no_requiere`.

**Trazabilidad**: RN-TU-04/RN-TU-08 (`05_reglas_de_negocio.md:10,14`), DD-10, Flujo 1 paso 4.

#### Scenario: Prestación con seña
- **WHEN** se reserva una prestación con `requiere_sena=true`
- **THEN** responde HTTP 201 con `sena.estado = pendiente`, el monto y ambas políticas visibles

#### Scenario: Prestación sin seña
- **WHEN** la prestación no requiere seña (o no hay prestación)
- **THEN** responde HTTP 201 con `sena.estado = no_requiere` y monto nulo

#### Scenario: Prestación inexistente o inactiva
- **WHEN** el body referencia una prestación que no existe o está dada de baja
- **THEN** responde HTTP 404 y no crea el turno

### Requirement: Token de gestión de un solo uso

El sistema SHALL emitir al reservar un token opaco de 256 bits, guardar solo su hash y devolver una sola vez el enlace `gestion_url`. `GET /reservar/gestion/{token}` SHALL mostrar el resumen sin consumirlo; los endpoints de acción SHALL consumirlo atómicamente. Un token usado, vencido, inexistente o de otro propósito SHALL responder 410 (404 solo si el formato es inválido).

**Trazabilidad**: RN-NO-03 (`05_reglas_de_negocio.md:40`), RN-TU-03, `04_modelo_de_datos.md` §Comunicaciones, `security/single-use-token`.

#### Scenario: Reserva devuelve el enlace de gestión
- **WHEN** la reserva pública se crea
- **THEN** la respuesta incluye `gestion_url` con el token en claro una sola vez
- **AND** la base guarda solo el hash y el tipo `gestion_turno`

#### Scenario: Consultar el resumen no consume
- **WHEN** se hace `GET /reservar/gestion/{token}` dos veces antes de una acción
- **THEN** ambas responden HTTP 200 con el mismo resumen

#### Scenario: Token usado
- **WHEN** se intenta confirmar o cancelar con un token ya consumido
- **THEN** responde HTTP 410

#### Scenario: Token vencido
- **WHEN** el token superó su `expira_at`
- **THEN** responde HTTP 410 sin revelar datos del turno

#### Scenario: Token de otro propósito
- **WHEN** se usa un token de recordatorio en la ruta de gestión
- **THEN** responde HTTP 410

### Requirement: Confirmar o cancelar desde el enlace

`POST /reservar/gestion/{token}/confirmar` SHALL pasar el turno a `confirmado` si la transición es válida. `POST .../cancelar` SHALL cancelarlo respetando el plazo del consultorio: dentro del plazo la cancelación es libre; fuera del plazo SHALL marcar pérdida de seña cuando la prestación la requería (RN-TU-04). Ambas acciones consumen el token.

**Trazabilidad**: RN-NO-02/RN-NO-03, RN-TU-03 (`05_reglas_de_negocio.md:9`), RN-TU-04, Flujo 2.

#### Scenario: Confirmación válida
- **WHEN** el paciente confirma un turno `reservado` con token vigente
- **THEN** responde HTTP 200 con estado `confirmado` y el token queda usado

#### Scenario: Confirmación inválida
- **WHEN** el turno está cancelado o atendido
- **THEN** responde HTTP 422 y el token no se consume

#### Scenario: Cancelación dentro del plazo
- **WHEN** faltan más horas que `plazo_cancelacion_horas` para el inicio
- **THEN** responde HTTP 200 con estado `cancelado` y `sena_perdida = false`

#### Scenario: Cancelación fuera del plazo
- **WHEN** falta menos que el plazo configurado
- **THEN** responde HTTP 200 con estado `cancelado` y `sena_perdida = true` si la prestación requiere seña

#### Scenario: Cancelación concurrente con el mismo token
- **WHEN** dos cancelaciones simultáneas usan el mismo token
- **THEN** exactamente una responde HTTP 200 y la otra HTTP 410

### Requirement: Confirmación por WhatsApp best-effort

Tras persistir la reserva, el sistema SHALL intentar encolar un mensaje en `whatsapp:send` con el id del turno. Un fallo de Redis no SHALL romper la reserva: SHALL informar `whatsapp_confirmacion = pendiente_reintento` (o `encolada` si se pudo).

**Trazabilidad**: US-001/CA-3, RN-NO-01, R-06 (Redis solo colas), `platform/job-queues`.

#### Scenario: Encolado exitoso
- **WHEN** Redis responde y la cola `whatsapp:send` acepta el trabajo
- **THEN** la respuesta 201 informa `whatsapp_confirmacion = encolada`

#### Scenario: Redis caído
- **WHEN** el encolado falla o expira
- **THEN** la reserva sigue siendo HTTP 201 y responde `pendiente_reintento` sin rollback

### Requirement: Página pública de reserva

La SPA SHALL renderizar `/reservar` con el catálogo público, selección de profesional/prestación/fecha, slots reales y formulario; al reservar SHALL mostrar el enlace de gestión o el error de la API tal cual. `/reservar/gestion/:token` SHALL mostrar el resumen y las acciones de confirmar/cancelar. No SHALL duplicar validaciones de negocio en el cliente.

**Trazabilidad**: US-001, Flujo 1, R-07 (sin lógica de negocio en el cliente), `platform/frontend-baseline`.

#### Scenario: Carga inicial de la página
- **WHEN** el usuario abre `/reservar`
- **THEN** la página pide el catálogo público y muestra profesionales y prestaciones sin errores de consola

#### Scenario: Reserva exitosa desde la página
- **WHEN** el usuario completa el formulario y el backend responde 201
- **THEN** la página muestra el enlace de gestión y el estado de la seña

#### Scenario: Error de negocio visible
- **WHEN** el backend responde 409 o 422
- **THEN** la página muestra el mensaje del backend sin reinterpretarlo

#### Scenario: Gestión desde el enlace
- **WHEN** se abre `/reservar/gestion/:token`
- **THEN** la página muestra el turno y permite confirmar o cancelar según corresponda
