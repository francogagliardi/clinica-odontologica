# Design

## Context

C-06 dejó la agenda operativa y el anti-solapamiento garantizado en PostgreSQL. C-07 abre la puerta pública sin JWT: catálogo, disponibilidad, alta de turno y enlace de gestión con token de un solo uso. Toda la lógica de negocio sigue viviendo en el backend (R-07); la SPA solo presenta.

Constraints: R-01/R-02 (Pydantic/RORO), R-03 (rutas públicas solo con token opaco, RN-NO-03), R-06 (Redis solo colas), R-07 (sin lógica en el cliente), R-08 (secretos fuera del repo), RN-TU-01/02/03/04/07/08, RN-NO-01/02/03, governance **ALTO**.

## Goals / Non-Goals

**Goals:**
- Reserva pública 24/7 con disponibilidad real y anti-solapamiento de C-06.
- Paciente encontrado o creado sin duplicar y sin permitir suplantación por DNI.
- Sillón asignado por el backend, nunca por el paciente.
- Seña pendiente y política visible cuando la prestación la exige.
- Enlace de gestión con token opaco de un solo uso y vencimiento.
- Página pública React y página de gestión.

**Non-Goals:**
- Cobro de la seña, webhook de Mercado Pago y comprobante (C-13).
- Envío real de WhatsApp y worker de reintentos (C-09); C-07 solo encola.
- Lista de espera (C-10).
- Rate limiting/anti-bot de endpoints públicos: deuda explícita para C-16.
- Agenda visual del backoffice (C-08).

## Decisions

### D1 — Rutas públicas y aislamiento de datos

`/reservar/{slug}` no usa `get_current_user`. El catálogo devuelve solo lo necesario: nombre del consultorio, profesionales (id, matrícula, especialidades), prestaciones (id, código, nombre, duración, precio, seña), `plazo_cancelacion_horas` y textos de política.

Nunca devuelve emails de usuarios, pacientes, tokens ni IDs internos que no hagan falta. La respuesta de reserva devuelve el turno y el enlace de gestión, pero **no** la ficha completa del paciente.

### D2 — Servicio compartido de alta de turno

La lógica de C-06 (recursos, duración, ventana, bloqueos, solapamiento y traducción de `23P01`) se extrae a `app/application/turnos.py` y la usan tanto el router del backoffice como el público. Sin esto, C-07 duplicaría reglas críticas y podrían divergir.

El servicio recibe el `UnitOfWork`, el consultorio y un comando con paciente/profesional/sillón/prestación/inicio; devuelve el `Turno`. El router decide el estado HTTP.

### D3 — Paciente: buscar o crear con verificación de teléfono

En una sola transacción:

1. Normalizar DNI y teléfono con las funciones de C-05 (422 si son inválidos).
2. Buscar paciente activo por DNI en el consultorio.
3. Si existe y el teléfono normalizado coincide → reutilizarlo.
4. Si existe y el teléfono **no** coincide → 409 «Los datos no coinciden con un paciente registrado» (evita suplantación y sobrescritura).
5. Si no existe → crear el paciente con nombre, apellido, DNI, teléfono y email opcional.

Un error posterior (silla ocupada, bloqueo) revierte todo: no quedan pacientes huérfanos.

### D4 — Asignación automática de sillón

El body público no acepta `sillon_id` (`extra='forbid'`). El servicio:

1. Lista sillones activos del consultorio.
2. Si el profesional tiene habilitaciones en `profesionales_sillones`, restringe a esas; si no tiene, usa todos.
3. Ordena por nombre y devuelve el primero sin solapamiento ni bloqueo en el rango.
4. Si ninguno queda libre → 409.

La constraint de exclusión sigue siendo la red de seguridad de la carrera.

### D5 — Seña pendiente en el turno

Migración `0007_reserva_publica`: agrega `turnos.sena_estado` (`VARCHAR(20)`, NOT NULL, default `no_requiere`) con CHECK en `no_requiere|pendiente|pagada|perdida`.

- Reserva con `requiere_sena=true` → `pendiente`.
- Reserva sin seña → `no_requiere`.
- C-13 será quien pase a `pagada` y emita el comprobante.
- Cancelación fuera de plazo con seña → `perdida` (RN-TU-04); dentro del plazo no se toca el estado (C-13 decide reembolso si estaba pagada).

La respuesta pública arma `sena: {requiere, monto, estado}` y `politica_sena` en texto.

### D6 — Token de gestión

Al crear el turno, dentro de la misma transacción:

- `create_single_use_token(session, tipo="gestion_turno", entidad_tipo="turno", entidad_id=str(turno.id), expires_minutes=settings.gestion_token_ttl_minutes)`.
- Se guarda solo el hash (infraestructura de C-03).
- Se devuelve `gestion_url = f"{settings.app_base_url}/reservar/gestion/{token}"` una única vez.

`GET /reservar/gestion/{token}` usa `verify_single_use_token` (no consume). `POST .../confirmar` y `.../cancelar` usan `consume_single_use_token` (atómico: dos requests concurrentes, una gana).

Errores de token (`TokenNotFoundError`, `TokenAlreadyUsedError`, `TokenExpiredError`, `TokenPurposeError`) → **410**, sin revelar datos del turno. Un token con formato inválido en la ruta también es 410.

Se agrega `GESTION_TOKEN_TTL_MINUTES` a settings (default 10080 = 7 días), documentado en `.env.example`.

### D7 — Confirmar y cancelar

- Confirmar: valida token, verifica que el turno esté `reservado`, aplica `puede_transicionar` y consume el token en la misma transacción. Si la transición es inválida → 422 **sin** consumir.
- Cancelar: valida token y que el turno no esté terminal; calcula `tarde = now > inicio - plazo_cancelacion_horas`. Cancela con `puede_transicionar`; si `tarde` y la prestación requiere seña, `sena_estado = perdida`. Responde `sena_perdida`.
- El token se consume solo si la acción prospera. Para no consumir en un 422, primero se valida el turno y recién después se llama a `consume_single_use_token`.

### D8 — WhatsApp best-effort

Después del `flush` del turno y antes de responder:

```python
payload = {"tipo": "confirmacion_reserva", "turno_id": str(turno.id)}
encolada = await try_enqueue(redis, WHATSAPP_SEND, json.dumps(payload))
```

`get_redis` se inyecta desde `app/api/deps.py` para poder sustituirlo en tests. Si `encolada` es false o el cliente es `None`, se registra un warning y la respuesta informa `whatsapp_confirmacion = pendiente_reintento`. Nunca se hace rollback por Redis (R-06: la verdad está en PostgreSQL).

### D9 — Schemas públicos

- `CatalogoPublico`, `ProfesionalPublico`, `PrestacionPublica`.
- `ReservaCreate` (`extra='forbid'`): nombre, apellido, dni, telefono, email opcional, profesional_id, prestacion_id opcional, inicio.
- `ReservaResponse`: turno_id, inicio, fin, estado, profesional (id/matrícula), prestacion (código/nombre), `sena`, `gestion_url`, `whatsapp_confirmacion`.
- `GestionTurnoResponse`: turno_id, inicio, fin, estado, profesional, prestacion, `sena`, `puede_confirmar`, `puede_cancelar`, `plazo_cancelacion_horas`.
- `AccionResponse`: estado, `sena_perdida`.

### D10 — Frontend

- `src/features/reserva/api.ts`: `fetchCatalogo`, `fetchDisponibilidad`, `crearReserva`, `fetchGestion`, `confirmarTurno`, `cancelarTurno`.
- `src/pages/ReservaPage.tsx`: selects de profesional/prestación/fecha, slots, formulario y resultado con enlace. Muestra errores de `ApiError` tal cual.
- `src/pages/GestionTurnoPage.tsx`: lee el token de la URL, muestra resumen y botones según `puede_confirmar`/`puede_cancelar`.
- `App.tsx` reconoce `/reservar` y `/reservar/gestion/<token>`.
- `client.ts` suma `postJson`; no se agrega validación de negocio local.

### D11 — Migración y despliegue

`0007_reserva_publica` solo agrega la columna y su CHECK; `down_revision = "0006_turnos_anti_solapamiento"`. El downgrade elimina la constraint y la columna. No hay tablas nuevas.

## Risks / Trade-offs

- **Endpoint público sin rate limit**: puede recibir spam; queda documentado y se mitiga en C-16. El anti-solapamiento y la verificación de DNI/teléfono limitan el daño.
- **DNI como identificador**: si dos personas comparten DNI (error de tipeo), la segunda recibe 409; es preferible a mezclar historias clínicas.
- **Sillón automático**: el paciente no controla el box; si la clínica necesita preferencia, se agrega en C-08.
- **Token de 7 días**: suficiente para gestionar un turno; si vence, el paciente debe llamar. Configurable por env.
- **WhatsApp sin worker**: el mensaje se encola pero nadie lo envía hasta C-09; el estado lo informa con honestidad.

## Migration Plan

1. `alembic upgrade head` aplica `0007`.
2. Reversión: `alembic downgrade 0006_turnos_anti_solapamiento`.
3. Verificación: migración bidireccional, suite completa, smoke público (reserva, solape, token reuso/vencido, seña, cancelación) y tests de componentes.
