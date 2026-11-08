# Spec Delta

## ADDED Requirements

### Requirement: Pérdida de seña por cancelación tardía y ausentismo

El sistema SHALL marcar `Turno.sena_estado='perdida'` cuando un turno con seña `pendiente` o `pagada` pase a `ausente`, y cuando pase a `cancelado` después del límite `inicio - plazo_cancelacion_horas` del consultorio. Dentro del plazo la cancelación SHALL ser libre. La regla SHALL aplicar tanto a la ruta pública como al backoffice y repetir el estado SHALL ser idempotente.

**Trazabilidad**: RN-TU-03, RN-TU-04, RN-TU-08, US-030/CA-2, `agenda/reserva-publica` §Confirmar o cancelar desde el enlace.

#### Scenario: Cancelación tardía desde el backoffice pierde la seña
- **WHEN** un recepcionista cancela un turno que empieza en 2 horas, con plazo de 24 horas y seña `pagada`
- **THEN** el turno pasa a `cancelado` y `sena_estado='perdida'`

#### Scenario: Cancelación dentro del plazo no pierde la seña
- **WHEN** se cancela un turno que empieza en 48 horas, con plazo de 24 horas y seña `pagada`
- **THEN** el turno pasa a `cancelado` y conserva `sena_estado='pagada'`

#### Scenario: Exactamente en el límite del plazo
- **WHEN** la cancelación ocurre exactamente en `inicio - plazo_cancelacion_horas`
- **THEN** no se considera tardía y la seña no se pierde

#### Scenario: Ausentismo pierde la seña
- **WHEN** un turno con seña `pagada` se marca `ausente`
- **THEN** el turno queda `ausente` con `sena_estado='perdida'`

#### Scenario: Turno sin seña exigida
- **WHEN** un turno con `sena_estado='no_requiere'` se cancela tarde o se marca ausente
- **THEN** `sena_estado` sigue siendo `no_requiere`

#### Scenario: Repetición del estado
- **WHEN** se vuelve a enviar `ausente` sobre un turno ya `ausente` y en `perdida`
- **THEN** responde HTTP 200 sin cambiar datos ni duplicar efectos en caja

#### Scenario: Cancelación pública mantiene la misma política
- **WHEN** el paciente cancela con el enlace público fuera del plazo
- **THEN** el turno queda `cancelado` con `sena_estado='perdida'`, igual que desde el backoffice
