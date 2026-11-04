# Proposal

## Why

C-06 dejó la agenda operativa por API, pero la recepcionista no tiene una pantalla para verla: hoy solo puede consultar turnos con Swagger. US-002 pide explícitamente una agenda día/semana/mes por profesional y sillón, con colores por estado, bloqueos y sobreturnos diferenciados, y reprogramación por arrastre que respete RN-TU-01.

C-08 es la cara visible de C-06 y corre en paralelo con C-07 (ya cerrado): no agrega reglas de negocio, solo presenta y deja que la API valide.

## What Changes

- Agrega el backoffice React `/agenda` con login en memoria (Bearer JWT, sin `localStorage`):
  - Formulario de login contra `POST /usuarios/login`; el token vive en memoria y se pierde al refrescar (R-03).
  - Selector de profesional, sillón y vista **día / semana / mes**, con navegación de fechas.
  - Turnos coloreados por estado (`reservado`, `confirmado`, `en_sala`, `atendido`, `cancelado`, `ausente`).
  - Bloqueos del profesional/sillón y sobreturnos con marca visual diferenciada.
  - Drag & drop de un turno a otro horario: llama a `PATCH /turnos/{id}/reprogramar` y muestra el error de la API tal cual (409/422), sin recalcular reglas en el cliente.
- Agrega `features/agenda` (cliente API, helpers de rango y componentes de calendario) y `features/auth` (sesión en memoria).
- Restringe la interacción según rol: recepción/administrador pueden reprogramar; odontólogo solo sus propios turnos; asistente/auditor solo lectura. La UI oculta/deshabilita acciones, pero el backend sigue siendo la autoridad.
- Agrega tests de componentes: render día/semana/mes, colores, bloqueos, sobreturnos, reprogramación válida e inválida y permisos por rol.

## Capabilities

### New Capabilities
- `agenda/agenda-backoffice-ui`: login en memoria, vistas de agenda, diferenciación visual y reprogramación por arrastre.

### Modified Capabilities
- Ninguna: la UI consume los requirements ya existentes de `agenda/turnos`, `agenda/recursos-agendables` y `agenda/bloqueos`.

## Impact

- **Frontend**:
  - `src/features/auth/session.ts`, `LoginForm`.
  - `src/features/agenda/api.ts`, `calendar.ts`, `AgendaDay.tsx`, `AgendaWeek.tsx`, `AgendaMonth.tsx`, `TurnoCard.tsx`, `BloqueoCard.tsx`.
  - `src/pages/AgendaPage.tsx`, `src/App.tsx`.
  - Tests de componentes y de integración de la página con fetch mockeado.
- **Backend**: sin cambios. Se consumen `GET /profesionales`, `GET /sillones`, `GET /bloqueos`, `GET /turnos` y `PATCH /turnos/{id}/reprogramar`.
- **API Surface**: ninguna nueva.
- **Riesgos y mitigaciones**:
  - **Token en memoria**: al refrescar se pierde la sesión; es el trade-off exigido por R-03 para evitar XSS con `localStorage`.
  - **Drag & drop en mobile**: se prioriza desktop; los botones de acción siguen disponibles para reprogramar desde el turno.
  - **Zona horaria**: se usa el offset `-03:00` que devuelve la API; la UI no reinterpreta zonas.
  - **RBAC visual**: ocultar acciones no reemplaza al backend; un error 403 se muestra si se fuerza la acción.
