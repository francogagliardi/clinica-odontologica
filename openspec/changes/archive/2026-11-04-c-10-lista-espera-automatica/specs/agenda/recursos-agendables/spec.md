# Spec Delta

## MODIFIED Requirements

### Requirement: Disponibilidad base por profesional

El sistema SHALL calcular los slots disponibles de un profesional para una fecha: día fuera de `dias_atencion` devuelve lista vacía; la duración es la de la prestación o `duracion_base_min` (RN-TU-02); genera intervalos consecutivos descartando el último incompleto; y excluye los solapados con bloqueos del profesional o del sillón (RN-TU-07), con turnos en estado activo (RN-TU-01) y con retenciones vigentes de lista de espera (RN-TU-05). Con C-06 la disponibilidad es real, no solo base.

**Trazabilidad**: RN-TU-01, RN-TU-02, RN-TU-05, RN-TU-07, `06_funcionalidades.md` US-001/CA-1, `07_flujos_principales.md` §Flujo 1, `agenda/lista-espera` §Retención atómica del hueco ofrecido.

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

#### Scenario: Retención vigente oculta el slot del backoffice
- **WHEN** una oferta de lista de espera vigente retiene un intervalo del profesional consultado
- **THEN** ese slot no aparece en `GET /profesionales/{id}/disponibilidad` aunque no exista un turno activo

#### Scenario: Retención vencida no oculta el slot del backoffice
- **WHEN** la retención tiene `oferta_expira_en` en el pasado y el worker todavía no la barrió
- **THEN** el slot vuelve a aparecer en la disponibilidad del backoffice
