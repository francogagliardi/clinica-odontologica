# agenda/turnos Specification

## Purpose
Núcleo de la agenda: crea y gestiona turnos con garantía transaccional de no solapamiento por profesional **y** por sillón (RN-TU-01), duración derivada de la prestación (RN-TU-02), bloqueos efectivos (RN-TU-07) y sobreturnos solo con marca explícita (RN-TU-06). Es la base de la reserva online (C-07), la agenda visual (C-08) y los recordatorios (C-09).

Nota de alcance: C-06 no implementa seña/cobro (C-13), lista de espera (C-10) ni enlaces públicos de gestión (C-07); solo persiste `token_publico` para que C-07 lo emita. La zona horaria es el offset fijo `UTC-3` de C-04.

## Requirements

### Requirement: Alta de turno con duración derivada

El sistema SHALL crear turnos en estado `reservado` con paciente, profesional y sillón activos del consultorio, `inicio` y `fin`. El `fin` SHALL calcularse como `inicio + duración` de la prestación o, sin prestación, `inicio + duracion_base_min` del profesional (RN-TU-02). El turno SHALL ubicarse dentro de los días y el horario de atención del profesional.

**Trazabilidad**: RN-TU-01, RN-TU-02 (`05_reglas_de_negocio.md:7–8`), `04_modelo_de_datos.md` §Turno, US-002.

#### Scenario: Alta con prestación calcula el fin
- **WHEN** un recepcionista autenticado hace `POST /turnos` con un paciente, profesional, sillón y prestación de 90 minutos, inicio `2026-11-10T09:00:00-03:00`
- **THEN** el sistema responde HTTP 201 con estado `reservado`, `fin` igual a `10:30` y origen `recepcion`

#### Scenario: Alta sin prestación usa la duración base
- **WHEN** el alta omite `prestacion_id`
- **THEN** el sistema responde HTTP 201 y `fin = inicio + duracion_base_min` del profesional (RN-TU-02)

#### Scenario: Recurso inexistente o dado de baja
- **WHEN** el alta referencia un paciente, profesional, sillón o prestación inexistente o con baja lógica
- **THEN** el sistema responde HTTP 404 con el recurso faltante y no crea el turno

#### Scenario: Turno fuera de la agenda del profesional
- **WHEN** el inicio cae en un día no habilitado o el fin supera `hora_hasta`
- **THEN** el sistema responde HTTP 422 y no crea el turno

#### Scenario: Turno con fin no posterior al inicio
- **WHEN** la prestación o la agenda producen `fin <= inicio`
- **THEN** el sistema responde HTTP 422 y el CHECK de PostgreSQL impide la fila por SQL directo

#### Scenario: Datos inválidos en el borde
- **WHEN** el alta envía un estado distinto de `reservado`, un origen desconocido o un campo extra
- **THEN** el sistema responde HTTP 422

### Requirement: Anti-solapamiento por profesional y por sillón

El sistema SHALL impedir que dos turnos activos (reservado, confirmado, en sala o atendido) se solapen por profesional y por sillón, tanto en el alta como en la reprogramación. La validación SHALL ser transaccional y respaldada por constraints de exclusión en PostgreSQL; los turnos consecutivos que se tocan en el borde SHALL permitirse.

**Trazabilidad**: RN-TU-01 (`05_reglas_de_negocio.md:7`), R-10 (`AGENTS.md`), `04_modelo_de_datos.md` §Turno.

#### Scenario: Mismo profesional en el mismo horario
- **WHEN** se intenta crear un segundo turno activo del mismo profesional que se solapa con otro existente
- **THEN** el sistema responde HTTP 409 y no crea una fila nueva

#### Scenario: Mismo sillón con otro profesional
- **WHEN** se intenta crear un turno en un sillón ya ocupado por otro turno activo, aunque el profesional sea distinto
- **THEN** el sistema responde HTTP 409 y no crea una fila nueva

#### Scenario: Turnos consecutivos en el borde
- **WHEN** un turno termina exactamente a la hora en que empieza el siguiente del mismo profesional y sillón
- **THEN** ambos se crean con HTTP 201 y no se consideran solapados

#### Scenario: Dos altas concurrentes al mismo slot
- **WHEN** dos peticiones simultáneas intentan reservar el mismo profesional y horario
- **THEN** exactamente una responde HTTP 201 y la otra HTTP 409, sin filas duplicadas

#### Scenario: Solapamiento insertado por SQL directo
- **WHEN** se inserta por SQL un turno normal que se solapa con otro activo del mismo profesional o sillón
- **THEN** PostgreSQL rechaza la fila con la constraint de exclusión (SQLSTATE `23P01`)

#### Scenario: Turnos cancelados no bloquean
- **WHEN** el único turno que ocupa un horario está en estado `cancelado` o `ausente`
- **THEN** un turno nuevo en ese horario responde HTTP 201

#### Scenario: Recursos distintos en el mismo horario
- **WHEN** dos turnos usan profesional y sillón distintos a la misma hora
- **THEN** ambos se crean con HTTP 201

### Requirement: Sobreturno con marca y color explícitos

El sistema SHALL permitir un sobreturno únicamente cuando la petición lo marque con `es_sobreturno=true` y un `color_sobreturno` válido. La marca y el color SHALL devolverse en la respuesta y persistirse. Un turno normal SHALL seguir rechazando el solapamiento incluso contra un sobreturno existente.

**Trazabilidad**: RN-TU-06 (`05_reglas_de_negocio.md:12`), US-002/CA-2, R-10.

#### Scenario: Sobreturno marcado se permite solapado
- **WHEN** un recepcionista crea un turno con `es_sobreturno=true`, color `#F97316` y un horario ya ocupado
- **THEN** el sistema responde HTTP 201 y la respuesta conserva la marca y el color

#### Scenario: Sobreturno sin color
- **WHEN** el alta envía `es_sobreturno=true` sin `color_sobreturno`
- **THEN** el sistema responde HTTP 422 y no crea el turno

#### Scenario: Turno normal con color de sobreturno
- **WHEN** el alta envía `es_sobreturno=false` con un color
- **THEN** el sistema responde HTTP 422 porque el color solo aplica a sobreturnos

#### Scenario: Turno normal contra un sobreturno existente
- **WHEN** se intenta crear un turno normal que se solapa con un sobreturno activo
- **THEN** el sistema responde HTTP 409: solo el sobreturno marcado puede solaparse

### Requirement: Los bloqueos impiden reservar

El sistema SHALL rechazar el alta y la reprogramación de cualquier turno que se solape con un bloqueo activo del profesional o del sillón (RN-TU-07). Un bloqueo que termina justo cuando empieza el turno no SHALL afectarlo.

**Trazabilidad**: RN-TU-07 (`05_reglas_de_negocio.md:13`), `agenda/bloqueos`.

#### Scenario: Bloqueo del profesional impide la reserva
- **WHEN** el turno se solapa con un bloqueo activo del profesional
- **THEN** el sistema responde HTTP 409 y no crea el turno

#### Scenario: Bloqueo del sillón impide la reserva
- **WHEN** el turno se solapa con un bloqueo activo del sillón, aunque el profesional esté libre
- **THEN** el sistema responde HTTP 409 y no crea el turno

#### Scenario: Bloqueo adyacente no afecta
- **WHEN** el bloqueo termina exactamente en el `inicio` del turno o empieza exactamente en su `fin`
- **THEN** el turno se crea con HTTP 201

#### Scenario: Bloqueo de otro recurso no afecta
- **WHEN** existe un bloqueo del mismo horario para otro profesional u otro sillón
- **THEN** el turno se crea con HTTP 201

### Requirement: Máquina de estados del turno

El sistema SHALL permitir solo las transiciones `reservado → confirmado → en_sala → atendido`, y `reservado|confirmado → cancelado|ausente`. Repetir el estado actual SHALL ser idempotente; cualquier otra transición SHALL rechazarse con 422 sin modificar el turno.

**Trazabilidad**: `04_modelo_de_datos.md` §Turno (estados), RN-TU-03/RN-TU-05 (cancelación libera el hueco), R-10.

#### Scenario: Transiciones válidas del flujo de atención
- **WHEN** un recepcionista confirma, pasa a sala y marca atendido un turno
- **THEN** cada `PATCH /turnos/{id}/estado` responde HTTP 200 con el nuevo estado

#### Scenario: Transición inválida
- **WHEN** se intenta pasar de `reservado` directamente a `atendido`, o de `cancelado` a `confirmado`
- **THEN** el sistema responde HTTP 422 y el turno conserva su estado anterior

#### Scenario: Cancelación desde estados válidos
- **WHEN** se cancela un turno `reservado` o `confirmado`
- **THEN** el sistema responde HTTP 200 con estado `cancelado` y el horario vuelve a quedar disponible

#### Scenario: Repetir el estado actual
- **WHEN** se envía el mismo estado que ya tiene el turno
- **THEN** el sistema responde HTTP 200 sin cambiar datos ni historial

#### Scenario: Turno inexistente o de otro consultorio
- **WHEN** se intenta cambiar el estado de un turno inexistente o ajeno al consultorio
- **THEN** el sistema responde HTTP 404

### Requirement: Reprogramación con la misma garantía

El sistema SHALL permitir reprogramar un turno activo cambiando fecha, profesional, sillón o prestación, recalculando `fin` y aplicando las mismas validaciones de agenda, bloqueos y anti-solapamiento. Un turno `cancelado` o `atendido` no SHALL reprogramarse.

**Trazabilidad**: RN-TU-01, RN-TU-02, RN-TU-07, US-002/CA-3, Flujo 2.

#### Scenario: Reprogramación a un horario libre
- **WHEN** se reprograma un turno confirmado a un slot libre del mismo profesional
- **THEN** el sistema responde HTTP 200 con el nuevo `inicio`, el `fin` recalculado y el estado `confirmado`

#### Scenario: Reprogramación a un horario ocupado
- **WHEN** el nuevo horario se solapa con otro turno activo
- **THEN** el sistema responde HTTP 409 y el turno original conserva fecha, recursos y estado

#### Scenario: Reprogramación fuera de la agenda o sobre un bloqueo
- **WHEN** el nuevo horario cae fuera del horario de atención o se solapa con un bloqueo
- **THEN** el sistema responde HTTP 422 o HTTP 409 respectivamente y no modifica el turno

#### Scenario: Reprogramar un turno cerrado
- **WHEN** se intenta reprogramar un turno `cancelado` o `atendido`
- **THEN** el sistema responde HTTP 422

#### Scenario: Reprogramaciones concurrentes al mismo slot
- **WHEN** dos reprogramaciones simultáneas apuntan al mismo horario libre
- **THEN** exactamente una responde HTTP 200 y la otra HTTP 409

### Requirement: Acceso a turnos por rol

El alta, la reprogramación y el cambio de estado SHALL exigir rol `administrador` o `recepcionista`; el odontólogo SHALL leer todos los turnos y operar solo los propios (donde `profesionales.usuario_id` coincide con su usuario). Asistente y auditor SHALL solo leer. Toda petición sin token SHALL responder 401.

**Trazabilidad**: RN-SE-01 (`05_reglas_de_negocio.md:44`), `03_actores_y_roles.md` §Matriz (Agenda/Turnos), R-03.

#### Scenario: Recepción opera la agenda
- **WHEN** un recepcionista crea un turno, lo reprograma y cambia su estado
- **THEN** el sistema responde HTTP 201, 200 y 200 respectivamente

#### Scenario: Odontólogo solo opera sus turnos
- **WHEN** un odontólogo vinculado a un profesional intenta cambiar el estado de un turno propio y de uno ajeno
- **THEN** el turno propio responde HTTP 200 y el ajeno HTTP 403

#### Scenario: Odontólogo intenta crear turnos
- **WHEN** un odontólogo hace `POST /turnos`
- **THEN** el sistema responde HTTP 403 porque solo lee y actualiza los propios

#### Scenario: Asistente y auditor solo leen
- **WHEN** un asistente o auditor hace `GET /turnos`
- **THEN** responde HTTP 200; si intenta crear, reprogramar o cambiar estado, responde HTTP 403

#### Scenario: Petición sin token
- **WHEN** cualquier endpoint de turnos se invoca sin Bearer válido
- **THEN** el sistema responde HTTP 401

### Requirement: Reservas bloqueadas por retenciones de lista de espera

Toda alta o reprogramación de turno SHALL rechazar con 409 cuando el intervalo solicitado se solape con una retención vigente de lista de espera (`estado='ofrecido'` y `oferta_expira_en > now`), aunque no exista un turno activo. La validación SHALL cubrir al profesional y al sillón retenidos, aplicarse también a la reserva pública y a los sobreturnos marcados, y permitir los turnos consecutivos en el borde.

**Trazabilidad**: RN-TU-05 (`05_reglas_de_negocio.md:11`), RN-TU-01/RN-TU-06 (`:7,12`), Flujo 5 (`07_flujos_principales.md:51–57`), `agenda/lista-espera` §Retención atómica del hueco ofrecido, R-10.

#### Scenario: Alta que se solapa con una retención vigente
- **WHEN** un recepcionista hace `POST /turnos` en un horario retenido por una oferta vigente, con el mismo profesional o el mismo sillón
- **THEN** el sistema responde HTTP 409 con el detalle de la retención y no crea el turno

#### Scenario: Reprogramación hacia un horario retenido
- **WHEN** se reprograma un turno activo a un intervalo que se solapa con una retención vigente
- **THEN** responde HTTP 409 y el turno original conserva fecha, profesional, sillón y estado

#### Scenario: Reserva pública sobre un horario retenido
- **WHEN** un visitante intenta `POST /reservar/{slug}/turnos` en el horario retenido
- **THEN** responde HTTP 409 y no se crea paciente ni turno nuevo

#### Scenario: Sobreturno marcado contra una retención
- **WHEN** el alta envía `es_sobreturno=true` con un color válido sobre un horario retenido
- **THEN** responde HTTP 409: la marca de sobreturno no habilita pisar una retención de lista de espera

#### Scenario: Retención vencida sin barrido no bloquea
- **WHEN** la retención tiene `oferta_expira_en` en el pasado y el worker todavía no la procesó
- **THEN** el alta responde HTTP 201 y no se considera bloqueada

#### Scenario: Retención de otro recurso no afecta
- **WHEN** la retención pertenece a otro profesional y a otro sillón en el mismo horario
- **THEN** el alta responde HTTP 201

#### Scenario: Turno consecutivo en el borde de la retención
- **WHEN** el turno termina exactamente cuando empieza la retención o empieza exactamente cuando termina
- **THEN** el alta responde HTTP 201 y no se considera solapada

#### Scenario: Retención liberada por conversión
- **WHEN** la oferta se convierte en turno y la retención deja de estar vigente
- **THEN** un segundo turno sobre el mismo intervalo responde HTTP 409 por el turno creado, no por la retención
