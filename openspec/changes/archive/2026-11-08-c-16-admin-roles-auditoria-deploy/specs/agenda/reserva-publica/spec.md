# Spec Delta

## ADDED Requirements

### Requirement: Alcance mínimo del enlace del paciente

`GET /reservar/gestion/{token}` y sus acciones SHALL exponer solo el turno vinculado al token y datos de catálogo. SHALL NOT exponer nombre, DNI, teléfono o email del paciente, otros turnos, historia clínica, presupuestos o cobros, ni existir un listado público. Un token de otro turno SHALL NOT autorizar este.

**Trazabilidad**: RN-SE-01, RN-NO-03, P-10 (v1 solo enlaces tokenizados), `security/single-use-token`.

#### Scenario: El enlace muestra solo su turno

- **WHEN** se abre `GET /reservar/gestion/{token}` con un token vigente
- **THEN** responde HTTP 200 con el turno, profesional, prestación, seña y políticas, sin nombre, DNI, teléfono ni email del paciente

#### Scenario: Token de otro turno

- **WHEN** se usa el token del turno A para intentar leer o cancelar el turno B
- **THEN** responde HTTP 410 y el turno B no se modifica ni se revela

#### Scenario: Sin listado público de turnos

- **WHEN** un visitante intenta `GET /reservar/{slug}/turnos` o cualquier listado de turnos sin token
- **THEN** el sistema responde 404/405 y no expone turnos de ningún paciente

#### Scenario: Dos turnos del mismo paciente

- **WHEN** un paciente tiene dos turnos con tokens distintos
- **THEN** cada token devuelve únicamente su propio turno y ninguno permite enumerar o leer el otro

#### Scenario: Token usado, vencido o de otro propósito

- **WHEN** se presenta un token consumido, expirado o emitido para otro propósito
- **THEN** responde HTTP 410 sin revelar datos del turno
