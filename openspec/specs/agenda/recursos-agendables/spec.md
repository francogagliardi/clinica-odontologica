# agenda/recursos-agendables Specification

## Purpose
Entrega los recursos de **oferta** de la agenda: profesionales con su configuración de atención, sillones físicos, la habilitación profesional ↔ sillón y el cálculo de disponibilidad base que C-06 reutiliza para validar anti-solapamiento (RN-TU-01/RN-TU-02) y para hacer efectivos los bloqueos (RN-TU-07).

Nota de alcance: C-04 no crea turnos ni valida solapamientos entre turnos (eso es C-06); la disponibilidad base solo descuenta bloqueos y respeta la agenda del profesional. La zona horaria de v1 es el offset fijo `UTC-3` (Argentina continental sin DST); la zona por consultorio llega con C-06.

## Requirements

### Requirement: Registro de profesionales con agenda configurada

El sistema SHALL permitir alta, consulta y baja lógica de profesionales con matrícula única entre activos, especialidades y `agenda_config` (`duracion_base_min`, `dias_atencion` ISO 0–6, `hora_desde` y `hora_hasta`). La escritura SHALL exigir rol `administrador`; la lectura SHALL estar disponible para los roles de agenda.

**Trazabilidad**: RN-SE-01 (`03_actores_y_roles.md` §Matriz de permisos), RN-TU-02 (`05_reglas_de_negocio.md`), `04_modelo_de_datos.md` §Profesional, DD-07a–DD-07e.

#### Scenario: Alta de profesional y lectura por recepción
- **WHEN** un administrador autenticado hace `POST /profesionales` con matrícula, especialidades y `agenda_config` válida
- **THEN** el sistema responde HTTP 201 con el profesional creado y su `agenda_config` anidada
- **AND** un recepcionista autenticado obtiene HTTP 200 al leer `GET /profesionales` y ve ese profesional

#### Scenario: Matrícula duplicada entre profesionales activos
- **WHEN** un administrador intenta crear un segundo profesional activo con la misma `matricula` en el mismo consultorio
- **THEN** el sistema responde HTTP 409 y no crea una fila nueva
- **AND** el índice único parcial `uq_profesionales_matricula_activo` impide también el duplicado por SQL directo

#### Scenario: Escritura de profesionales por un rol no administrador
- **WHEN** un odontólogo, recepcionista, asistente o auditor intenta `POST /profesionales` o `DELETE /profesionales/{id}`
- **THEN** el sistema responde HTTP 403 con detalle "Permisos insuficientes"

#### Scenario: Baja lógica libera la matrícula
- **WHEN** un administrador da de baja un profesional y luego crea otro activo con la misma matrícula
- **THEN** el alta responde HTTP 201 y la fila anterior conserva `deleted_at` no nulo sin aparecer en `GET /profesionales`

#### Scenario: Agenda base inválida rechazada en el borde
- **WHEN** el alta envía `duracion_base_min <= 0`, `dias_atencion` vacío, con valores fuera de 0–6 o duplicados, o `hora_hasta <= hora_desde`
- **THEN** el sistema responde HTTP 422 y no persiste el profesional
- **AND** los CHECK de PostgreSQL rechazan `duracion_base_min <= 0`, `hora_hasta <= hora_desde`, días vacíos o fuera de 0–6 por SQL directo; los días duplicados se rechazan en el borde porque un CHECK no puede comparar la unicidad interna de un array

#### Scenario: Usuario ya vinculado a otro profesional activo
- **WHEN** un administrador intenta vincular un `usuario_id` que ya pertenece a otro profesional activo
- **THEN** el sistema responde HTTP 409 y mantiene un único vínculo activo por usuario

### Requirement: Sillones y habilitación idempotente profesional ↔ sillón

El sistema SHALL permitir administrar los sillones del consultorio (nombre único entre activos) y habilitar qué profesional puede atender en qué sillón. La habilitación SHALL ser idempotente: repetirla no duplica filas ni devuelve error. La escritura de sillones y habilitaciones SHALL exigir rol `administrador`; la lectura SHALL estar disponible para los roles de agenda.

**Trazabilidad**: RN-SE-01, RN-TU-01 (el sillón es recurso de exclusión), `04_modelo_de_datos.md` §Sillon, DD-07a–DD-07e.

#### Scenario: Alta de sillón y listado
- **WHEN** un administrador hace `POST /sillones` con un nombre no repetido
- **THEN** el sistema responde HTTP 201 con el sillón creado
- **AND** `GET /sillones` devuelve HTTP 200 con ese sillón para un recepcionista

#### Scenario: Sillón duplicado entre activos
- **WHEN** un administrador intenta crear un sillón con el mismo nombre de otro sillón activo del consultorio
- **THEN** el sistema responde HTTP 409 y el índice único parcial lo impide también por SQL directo

#### Scenario: Escritura de sillones por un rol no administrador
- **WHEN** un odontólogo o recepcionista intenta `POST /sillones`, `DELETE /sillones/{id}` o habilitar un sillón
- **THEN** el sistema responde HTTP 403

#### Scenario: Baja lógica de sillón libera el nombre
- **WHEN** un administrador da de baja un sillón y crea otro activo con el mismo nombre
- **THEN** el alta responde HTTP 201 y el sillón anterior no aparece en `GET /sillones`

#### Scenario: Habilitación repetida no duplica
- **WHEN** un administrador llama dos veces a `POST /profesionales/{id}/sillones/{sillon_id}` con los mismos recursos
- **THEN** ambas respuestas son exitosas (HTTP 204) y la tabla `profesionales_sillones` contiene exactamente una fila para ese par

#### Scenario: Habilitación con recurso inexistente o inactivo
- **WHEN** la habilitación referencia un profesional o un sillón inexistente o dado de baja lógica
- **THEN** el sistema responde HTTP 404 y no crea el vínculo

### Requirement: Disponibilidad base por profesional

El sistema SHALL calcular los slots disponibles de un profesional para una fecha: día fuera de `dias_atencion` devuelve lista vacía; la duración es la de la prestación o `duracion_base_min` (RN-TU-02); genera intervalos consecutivos descartando el último incompleto; y excluye los solapados con bloqueos del profesional o del sillón (RN-TU-07) y con turnos en estado activo (RN-TU-01). Con C-06 la disponibilidad es real, no solo base.

**Trazabilidad**: RN-TU-01, RN-TU-02, RN-TU-07, `06_funcionalidades.md` US-001/CA-1, `07_flujos_principales.md` §Flujo 1.

#### Scenario: Slots consecutivos con la duración de la prestación
- **WHEN** se consulta `GET /profesionales/{id}/disponibilidad?fecha=...&prestacion_id=...` para un día habilitado
- **THEN** el sistema responde HTTP 200 con slots consecutivos desde `hora_desde`, cada uno de la duración de la prestación
- **AND** cada slot expone inicio y fin en `UTC-3` y no se solapan entre sí

#### Scenario: Sin prestación usa la duración base del profesional
- **WHEN** se consulta la disponibilidad sin `prestacion_id`
- **THEN** el sistema responde HTTP 200 con slots de `duracion_base_min` (RN-TU-02)

#### Scenario: Profesional inexistente o dado de baja
- **WHEN** se consulta la disponibilidad de un profesional que no existe o tiene baja lógica
- **THEN** el sistema responde HTTP 404 y no calcula slots

#### Scenario: Día fuera de los días de atención
- **WHEN** la fecha consultada cae en un día ISO que no está en `dias_atencion`
- **THEN** el sistema responde HTTP 200 con lista vacía

#### Scenario: Último slot incompleto descartado
- **WHEN** el rango `hora_desde`–`hora_hasta` no es múltiplo exacto de la duración del slot
- **THEN** el sistema no incluye un slot que termine después de `hora_hasta`

#### Scenario: Fecha o prestación inválida en el borde
- **WHEN** la consulta envía una fecha con formato inválido, parámetros extra, o una `prestacion_id` inexistente/inactiva
- **THEN** el sistema responde HTTP 422 para el borde y HTTP 404 para la prestación inexistente/inactiva, sin calcular slots

#### Scenario: Turno activo ocupa el slot
- **WHEN** un turno `reservado`, `confirmado`, `en_sala` o `atendido` se solapa con un slot calculado
- **THEN** ese slot no aparece en la respuesta de disponibilidad

#### Scenario: Cancelación o ausencia libera el slot
- **WHEN** el turno que ocupaba el slot pasa a `cancelado` o `ausente`
- **THEN** el slot vuelve a aparecer como disponible

#### Scenario: Turno de otro profesional no afecta
- **WHEN** existe un turno activo en el mismo horario pero de otro profesional
- **THEN** el slot del profesional consultado sigue disponible

#### Scenario: Día completo sin huecos
- **WHEN** todos los slots del día están ocupados por turnos activos o bloqueos
- **THEN** el sistema responde HTTP 200 con lista vacía
