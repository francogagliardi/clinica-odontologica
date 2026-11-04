# Spec Delta

## ADDED Requirements

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
