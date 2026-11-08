# Job Queues Specification

## Purpose

Fija el contrato nominal de colas Redis reservadas y la regla Redis-solo-jobs, para que recordatorios, WhatsApp y ARCA compartan nombres estables desde el día uno.

## Requirements

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

### Requirement: Redis nunca es fuente de verdad

El sistema SHALL usar Redis exclusivamente para colas/jobs transitorios; ningún dato de dominio (turnos, clínica, caja, auditoría) SHALL persistirse solo en Redis — el estado durable vive en PostgreSQL.

#### Scenario: Caída de Redis no pierde dominio

- **WHEN** Redis se vacía/reinicia con la API en marcha y sin workers funcionales
- **THEN** ningún dato de dominio se pierde ni se corrompe (las colas pueden reencolarse; PostgreSQL sigue siendo la fuente consultable) y la API lo señala vía `/ready` sin inventar estado

### Requirement: Encolado baseline no bloqueante

Cualquier encolado presente en el baseline SHALL ser no bloqueante para el request: si Redis no está disponible, el request completa su respuesta primaria y registra el fallo para reintento futuro en lugar de romper.

#### Scenario: Redis caído no rompe health de API

- **WHEN** Redis está caído y se llama `GET /health` y `GET /ready`
- **THEN** `/health` sigue `200` y `/ready` responde `503` indicando `redis: down`, sin excepciones no manejadas ni timeouts que cuelguen el worker web
