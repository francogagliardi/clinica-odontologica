# Tasks

> Cobertura: **22 escenarios** en `agenda/agenda-backoffice-ui`. Sin cambios de backend ni migraciones.
> Ciclo R-09: rojo antes de verde en cada componente. Proceso acordado 2026-11-03: cierre con tests + smoke y checklist acumulado.

## 0. Preparación

- [x] 0.1 Auditar la spec con `spec-scenario-auditor` y validar `openspec validate c-08-agenda-backoffice-ui --strict`. Evidencia: `docs/skills-mcp/evidencias/skill-audit-c-08.md`.
- [x] 0.2 Confirmar que el frontend compila (`npm run typecheck`) y que los endpoints de C-06 responden en el stack.

## 1. Sesión y login en memoria (R-03)

- [x] 1.1 **Rojo**: tests de `session.ts` y `LoginForm`: login exitoso guarda token en memoria y no toca `localStorage`/`sessionStorage`; 401 muestra el mensaje; logout limpia; recarga simulada deja sin token. **Verifica:** `features/auth/session.test.tsx`.
- [x] 1.2 **Verde**: implementar `features/auth/session.ts`, `LoginForm` y el guard de `AgendaPage`. **Verifica:** 1.1 en verde.

## 2. Cliente API y cálculo de rangos (R-07)

- [x] 2.1 **Rojo**: tests de `calendar.ts`: rango día, semana ISO lunes–domingo, mes completo, navegación ±1 día/semana/mes y mes ≤ 31 días. **Verifica:** `features/agenda/calendar.test.ts`.
- [x] 2.2 **Rojo**: tests de `api.ts`: agrega `Authorization`, arma query de rango/filtros, `reprogramarTurno` manda `inicio` ISO y propaga `ApiError`. **Verifica:** `features/agenda/api.test.ts`.
- [x] 2.3 **Verde**: implementar `calendar.ts` y `api.ts`. **Verifica:** 2.1 y 2.2 en verde.

## 3. Vista día (US-002/CA-1)

- [x] 3.1 **Rojo**: test de render: grilla de horas, turno ubicado por hora, filtro por profesional/sillón en la llamada, mensaje vacío. **Verifica:** los escenarios `Vista día`, `Filtro por profesional y sillón` y `Día sin turnos`.
- [x] 3.2 **Verde**: implementar `AgendaDay` y `AgendaPage` con selects de profesional/sillón. **Verifica:** 3.1 en verde.

## 4. Vistas semana y mes (US-002/CA-1)

- [x] 4.1 **Rojo**: tests: semana con siete columnas y turnos por día; mes con grilla y chips; navegación anterior/siguiente consulta el rango correcto; rango inválido muestra 422. **Verifica:** `Vista semana`, `Vista mes` y `Navegación de fechas`.
- [x] 4.2 **Verde**: implementar `AgendaWeek`, `AgendaMonth` y el selector de vista. **Verifica:** 4.1 en verde.

## 5. Colores, bloqueos y sobreturnos (US-002/CA-1–2)

- [x] 5.1 **Rojo**: tests: cada estado tiene clase/etiqueta distinta; bloqueo visible con motivo; sobreturno con badge y color del backend; cancelado atenuado. **Verifica:** los 4 escenarios de `Diferenciación visual…`.
- [x] 5.2 **Verde**: implementar `TurnoCard`, `BloqueoCard` y el mapa de estilos. **Verifica:** 5.1 en verde.

## 6. Drag & drop y errores de la API (US-002/CA-3, R-07)

- [x] 6.1 **Rojo**: tests: drop válido llama `PATCH` con el inicio correcto y refresca; 409 muestra el mensaje y no mueve; 422 de turno cerrado; el nuevo inicio incluye `-03:00`; no hay cálculo local de solapamiento. **Verifica:** los 4 escenarios de `Reprogramación por arrastre…`.
- [x] 6.2 **Verde**: implementar drag & drop en día/semana/mes y el manejo de `ApiError`. **Verifica:** 6.1 en verde.

## 7. Permisos visuales por rol (RN-SE-01)

- [x] 7.1 **Rojo**: tests: recepcionista arrastra todo; odontólogo solo su profesional; asistente/auditor sin drag; 403 forzado se muestra. **Verifica:** los 4 escenarios de `Acciones según el rol`.
- [x] 7.2 **Verde**: implementar `puedeReprogramar(turno, sesión, profesionales)` y deshabilitar drag según rol. **Verifica:** 7.1 en verde.

## 8. Verificación integrada

- [x] 8.1 `npm run typecheck` + `npm test` + suite backend sin regresiones; matriz escenario → test en `docs/skills-mcp/evidencias/c-08-verificacion-escenarios.md`.
- [x] 8.2 Levantar el stack, probar login, vistas, filtros, bloqueo, sobreturno y una reprogramación válida/inválida; agregar el bloque C-08 a `docs/validacion-manual-pendiente.md`; cerrar/archivar/commitear.
