# Spec Delta

## Purpose

Hace efectiva la regla de que **los bloqueos bloquean** (RN-TU-07): licencias, feriados y cierres administrativos por profesional o por sillón, con rango temporal válido y un único recurso afectado. El bloqueo se refleja en la disponibilidad base de C-04 y C-06 lo reutiliza al validar turnos.

Nota de procedencia: que `profesionales.usuario_id` sea nullable y que un profesional sin usuario no pueda reclamar bloqueos propios proviene de `design.md` D2 de este change (el usuario odontólogo demo se crea en C-16), no de una regla `RN-*`.

## ADDED Requirements

### Requirement: Alta de bloqueo por profesional o por sillón

El sistema SHALL registrar bloqueos con `desde`, `hasta` y `motivo`, afectando **exactamente uno** de los dos recursos: `profesional_id` o `sillon_id`. El rango SHALL cumplir `hasta > desde`. Los bloqueos solapados entre sí SHALL permitirse porque su efecto (excluir el rango) es idempotente.

**Trazabilidad**: RN-TU-07, `04_modelo_de_datos.md` §Bloqueo, R-10 (`AGENTS.md`).

#### Scenario: Recepción crea un bloqueo de profesional
- **WHEN** un recepcionista autenticado hace `POST /bloqueos` con `profesional_id`, `desde`, `hasta` y `motivo`
- **THEN** el sistema responde HTTP 201 con el bloqueo creado
- **AND** `GET /bloqueos` lo devuelve para el rango consultado

#### Scenario: Bloqueo con los dos recursos o con ninguno
- **WHEN** el alta envía `profesional_id` y `sillon_id` a la vez, o no envía ninguno de los dos
- **THEN** el sistema responde HTTP 422 y el CHECK XOR de PostgreSQL impide la fila por SQL directo

#### Scenario: Rango temporal inválido
- **WHEN** el alta envía `hasta` igual o anterior a `desde`
- **THEN** el sistema responde HTTP 422 y no persiste el bloqueo

#### Scenario: Bloqueo con recurso inexistente o inactivo
- **WHEN** el alta referencia un profesional o sillón inexistente o con baja lógica
- **THEN** el sistema responde HTTP 404 y no crea el bloqueo

#### Scenario: Bloqueos solapados entre sí
- **WHEN** un administrador crea dos bloqueos del mismo profesional con rangos que se superponen
- **THEN** ambos se persisten con HTTP 201 y la disponibilidad excluye la unión de los rangos sin duplicar slots

### Requirement: Control de acceso a bloqueos por rol y propiedad

El sistema SHALL autorizar la escritura de bloqueos según la matriz: `administrador` y `recepcionista` pueden bloquear cualquier profesional o sillón; `odontologo` solo puede bloquear el profesional cuyo `usuario_id` coincide con su usuario autenticado; `asistente` y `auditor` solo leen. La baja lógica de un bloqueo SHALL seguir la misma regla de propiedad.

**Trazabilidad**: RN-SE-01, RN-TU-07, `03_actores_y_roles.md` §Matriz de permisos (Agenda/Turnos: odontólogo `RU (propios)`).

#### Scenario: Odontólogo bloquea su propio profesional
- **WHEN** un odontólogo vinculado a un profesional crea o elimina un bloqueo de ese mismo profesional
- **THEN** el sistema responde HTTP 201 o 204 respectivamente

#### Scenario: Odontólogo intenta bloquear a otro profesional
- **WHEN** un odontólogo vinculado al profesional A intenta crear o eliminar un bloqueo del profesional B
- **THEN** el sistema responde HTTP 403 y no modifica bloqueos ajenos

#### Scenario: Odontólogo intenta bloquear un sillón
- **WHEN** un odontólogo intenta crear un bloqueo con `sillon_id`
- **THEN** el sistema responde HTTP 403, porque la propiedad solo se define sobre su propio profesional

#### Scenario: Asistente o auditor intenta escribir bloqueos
- **WHEN** un asistente o un auditor hace `POST /bloqueos` o `DELETE /bloqueos/{id}`
- **THEN** el sistema responde HTTP 403, aunque puedan leer `GET /bloqueos`

#### Scenario: Profesional sin usuario vinculado no puede ser reclamado
- **WHEN** un odontólogo intenta bloquear un profesional cuyo `usuario_id` es nulo (todavía no vinculado)
- **THEN** el sistema responde HTTP 403 porque la propiedad no puede establecerse; solo un administrador o recepcionista puede crear ese bloqueo

### Requirement: Efecto del bloqueo en la disponibilidad

El sistema SHALL excluir de la disponibilidad base todo slot que se solape con un bloqueo vigente del profesional consultado y, cuando se consulta un sillón, con los bloqueos de ese sillón. Un bloqueo fuera del horario de atención o de otro recurso no SHALL alterar la disponibilidad, y un bloqueo con baja lógica SHALL dejar de excluir slots. Un sillón inexistente o inactivo en la consulta SHALL responder 404.

**Trazabilidad**: RN-TU-07, RN-TU-01 (los recursos bloqueados no son reservables), `07_flujos_principales.md` §Flujo 1.

#### Scenario: Bloqueo dentro del horario quita slots
- **WHEN** existe un bloqueo vigente que cubre parte del horario de atención y se consulta la disponibilidad del profesional
- **THEN** los slots que se solapan con el bloqueo no aparecen en la respuesta HTTP 200

#### Scenario: Bloqueo fuera del horario no cambia la disponibilidad
- **WHEN** el bloqueo cubre un rango anterior a `hora_desde` o posterior a `hora_hasta`
- **THEN** la respuesta HTTP 200 conserva exactamente los mismos slots que sin el bloqueo

#### Scenario: Bloqueo de otro profesional no afecta
- **WHEN** existe un bloqueo del profesional A y se consulta la disponibilidad del profesional B en el mismo rango
- **THEN** la disponibilidad de B no se reduce por el bloqueo de A

#### Scenario: Bloqueo de sillón afecta la consulta con sillón
- **WHEN** se consulta la disponibilidad indicando un `sillon_id` que tiene un bloqueo vigente en parte del horario
- **THEN** los slots solapados con el bloqueo del sillón no aparecen, aunque el profesional no esté bloqueado

#### Scenario: Baja lógica del bloqueo restaura slots
- **WHEN** un administrador da de baja lógicamente un bloqueo y vuelve a consultar la disponibilidad
- **THEN** los slots que el bloqueo excluía vuelven a aparecer en la respuesta HTTP 200

#### Scenario: Consulta de disponibilidad con sillón inexistente o inactivo
- **WHEN** se consulta la disponibilidad indicando un `sillon_id` que no existe o tiene baja lógica
- **THEN** el sistema responde HTTP 404 y no calcula slots, porque un sillón no reservable no puede condicionar la disponibilidad
