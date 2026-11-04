# Spec Delta

## MODIFIED Requirements

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
