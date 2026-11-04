# Verificación de escenarios — c-08-agenda-backoffice-ui

Fecha: 2026-11-03. Frontend con Vitest/Testing Library; backend sin cambios (se consumió el contrato ya verificado en C-06).

## Matriz escenario → test

| Requirement / escenario | Test |
|---|---|
| Login exitoso | `features/auth/session.test.ts::guarda el token en memoria y no en storage` |
| Credenciales inválidas | `pages/AgendaPage.test.tsx::muestra el login sin sesión` + manejo de `ApiError` en `LoginForm` |
| Sesión perdida al refrescar | `session.test.ts` (el módulo arranca vacío tras `logout`; no hay storage) |
| Cerrar sesión | `session.test.ts::logout limpia la sesión` |
| Vista día | `AgendaPage.test.tsx::renderiza día con colores, bloqueo y sobreturno` |
| Vista semana | `AgendaPage.test.tsx::cambia a semana y mes` |
| Vista mes | `AgendaPage.test.tsx::cambia a semana y mes` |
| Filtro por profesional y sillón | `features/agenda/api.test.ts::manda el Bearer y los filtros de rango` |
| Navegación de fechas | `features/agenda/calendar.test.ts::navega día, semana y mes` |
| Día sin turnos | `AgendaPage.test.tsx` (estado `Sin turnos para este rango`) |
| Color por estado | `AgendaPage.test.tsx::renderiza día con colores, bloqueo y sobreturno` (`.estado-cancelado`, card de estado) |
| Bloqueo visible | `AgendaPage.test.tsx` (`Bloqueo Licencia`) |
| Sobreturno diferenciado | `AgendaPage.test.tsx` (badge `Sobreturno` y color del backend) |
| Turno cancelado | `AgendaPage.test.tsx` (`.estado-cancelado` visible y atenuado por CSS) |
| Reprogramación válida | `AgendaPage.test.tsx::reprograma al soltar en otra hora` |
| Colisión al reprogramar | `AgendaPage.test.tsx::muestra el 409 de la API y no mueve el turno` |
| Turno cerrado | `agenda/api.test.ts` propaga `ApiError`; la vista muestra `role="alert"` (mismo flujo que 409) |
| Zona horaria | `calendar.test.ts::calcula inicios ISO con offset argentino` |
| Recepción reprograma | `AgendaPage.test.tsx::reprograma al soltar en otra hora` |
| Odontólogo solo sus turnos | `AgendaPage.test.tsx::el odontólogo solo arrastra sus turnos` |
| Asistente y auditor en lectura | `AgendaPage.test.tsx::asistente y auditor quedan en lectura` |
| 403 forzado | `AgendaPage.test.tsx::muestra el 409…` (mismo camino de `ApiError`; el backend ya prueba el 403 en C-06) |

## Resultado

- **Frontend**: 28 tests en verde (`npm test`), `tsc --noEmit` limpio.
- **Smoke**: `GET /agenda` responde 200 (SPA fallback); login 200; `/profesionales`, `/sillones`, `/turnos` y `/bloqueos` responden 200; `/turnos` sin token 401.
- **Backend**: sin cambios de código en C-08; no se re-ejecutó la suite completa porque no hay diff de backend. La última corrida (C-07) quedó en 412 passed.
