# Proposal

## Why

C-06 dejó la agenda operativa desde el backoffice, pero el paciente todavía no puede reservar: no existe ningún endpoint público ni enlace. US-001 —reservar 24/7 sin depender del horario de recepción— es el criterio de producto central del MVP y el disparador del Flujo 1 (disponibilidad → turno reservado → confirmación por WhatsApp → seña si corresponde).

C-07 abre la cara pública del sistema sin debilitar la seguridad: rutas sin JWT de sesión, token opaco de un solo uso con vencimiento (RN-NO-03) y toda la validación de negocio reutilizada de C-06.

## What Changes

- Expone la API pública bajo `/reservar/{consultorio}`:
  - `GET /reservar/{consultorio}`: datos mínimos del consultorio, profesionales y prestaciones activas, política de cancelación y de seña.
  - `GET /reservar/{consultorio}/disponibilidad`: disponibilidad real por fecha/profesional/prestación, reutilizando el cálculo de C-06.
  - `POST /reservar/{consultorio}/turnos`: crea el turno `reservado` sin JWT; busca o crea el paciente por DNI, valida teléfono/DNI argentinos, asigna un sillón libre y aplica anti-solapamiento, bloqueos y agenda.
- Si la prestación requiere seña, el turno nace con `sena_estado = pendiente` y la respuesta muestra el monto y la política de pérdida (RN-TU-04); el cobro real queda para C-13.
- Emite un token de un solo uso (`tipo = gestion_turno`) y devuelve el enlace de gestión del turno.
- Agrega endpoints de gestión por token:
  - `GET /reservar/gestion/{token}`: resumen del turno (no consume).
  - `POST /reservar/gestion/{token}/confirmar` y `/cancelar`: consumen el token, respetan el plazo del consultorio (RN-TU-03) y marcan pérdida de seña si corresponde (RN-TU-04).
  - Token usado o vencido responde 410.
- Encola la confirmación en `whatsapp:send` de forma best-effort: si Redis falla, la reserva igual se crea y se registra el fallo para reintento (C-09 implementa el worker).
- Implementa la página pública React `/reservar`: profesionales, prestaciones, disponibilidad y formulario; y la página `/reservar/gestion/:token` con confirmar/cancelar.
- Agrega migración `0007_reserva_publica` con `turnos.sena_estado`.
- Tests: doble reserva pública concurrente (una 201, una 409), reutilización de token 410, token vencido 410, teléfono inválido sin turno ni paciente creado, seña pendiente, cancelación dentro/fuera de plazo y render de la página.

## Capabilities

### New Capabilities
- `agenda/reserva-publica`: reserva 24/7 sin sesión, token de gestión de un solo uso, seña pendiente y página pública.

### Modified Capabilities
- Ninguna: la creación pública reutiliza los requirements de `agenda/turnos`; no cambia su comportamiento, solo agrega una puerta de entrada.

## Impact

- **Backend**:
  - `app/models/agenda.py` (`Turno.sena_estado`) y migración `0007`.
  - `app/application/turnos.py` (servicio compartido de alta/reprogramación extraído de C-06).
  - `app/api/publico.py`, `app/schemas/publico.py`, montaje en `app/main.py`.
  - `app/api/deps.py` (cliente Redis inyectable) y `app/core/settings.py` (TTL del token de gestión).
  - Tests unitarios e integración; actualización del head de migraciones.
- **Frontend**:
  - `src/pages/ReservaPage.tsx` (reemplaza el placeholder), `src/pages/GestionTurnoPage.tsx`, `src/features/reserva/*`, `src/shared/api/client.ts` (POST) y `src/App.tsx`.
  - Tests de componentes con Vitest/Testing Library.
- **API Surface**: `/reservar/{slug}`, `/reservar/{slug}/disponibilidad`, `/reservar/{slug}/turnos` y `/reservar/gestion/{token}[...]`.
- **Riesgos y mitigaciones**:
  - **Abuso de endpoints públicos**: v1 no agrega rate limiting (queda como deuda explícita); el token es opaco y de un solo uso, y el anti-solapamiento no depende del cliente.
  - **Suplantación por DNI**: si el DNI ya existe con otro teléfono, la reserva se rechaza con 409 en lugar de sobrescribir datos del paciente.
  - **Mensaje sin worker**: el encolado es best-effort y no bloquea la reserva; el turno queda persistido.
  - **Seña**: C-07 solo marca `pendiente`; el cobro, el webhook y el comprobante son C-13.
  - **Sillón**: el paciente no lo elige; el backend busca uno libre y habilitado para el profesional.
