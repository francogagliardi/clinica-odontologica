# Spec Delta

## MODIFIED Requirements

### Requirement: Nombres de cola reservados cableados

El backend SHALL exponer un cliente Redis configurado por `REDIS_URL` que referencia exactamente los nombres reservados `whatsapp:send`, `recordatorios:due`, `arca:emitir` y `reportes:generar`, sin crear otras colas.

#### Scenario: Nombres reservados presentes y exclusivos

- **WHEN** se inspecciona el módulo de colas/workers del backend
- **THEN** los cuatro nombres aparecen como constantes centralizadas y no existe ningún otro nombre de cola hardcodeado en el código

#### Scenario: Exportación encolada en la cola reservada

- **WHEN** se solicita una exportación y el worker `reportes` toma el trabajo
- **THEN** el único nombre de cola usado es `reportes:generar` y ningún otro consumidor procesa ese job

#### Scenario: Cola desconocida rechazada al encolar

- **WHEN** un llamador intenta encolar con un nombre que no está en el conjunto reservado
- **THEN** el encolado falla explícitamente antes de escribir en Redis y el request conserva su respuesta primaria
