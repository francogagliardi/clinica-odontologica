# Tasks

> Convención: cada grupo abre en rojo (test o verificación que falla) y cierra en verde. Todo el trabajo es de presentación: no se tocan endpoints, contratos, sesión ni `localStorage`.
> Decisiones: `design.md` D1–D12. Escenarios: `specs/platform/design-system/spec.md`.
> Restricción dura: no cambiar textos de etiquetas, `aria-label` de turnos/bloqueos, nombres de botones, clases legacy (`.agenda-*`, `.turno`, `.bloqueo`, `.estado-*`, `.reportes-filtros`) ni los textos `Cargando…` / `Turno cancelado.` — los 64 tests existentes dependen de ellos.

## 1. Tokens, hoja global y metadatos

- [x] 1.1 Escribir en rojo `frontend/src/styles/tokens.test.ts`: grupos requeridos (color, tipografía, espaciado, radios, bordes, foco, movimiento), matriz de ratios de `design.md` D3 recalculada desde los hex, y fallo si un par baja de 4.5:1 (texto) o 3:1 (interfaz). **Verifica:** `npm run test -- --run src/styles/tokens.test.ts` falla antes de crear los tokens.
- [x] 1.2 Crear `frontend/src/styles/tokens.css` con los roles y valores de D3/D4 y `frontend/src/styles/app.css` con reset acotado, `@layer reset, base, layout, components, utilities`, base tipográfica y utilidades mínimas; importar ambas desde `main.tsx`. **Verifica:** test 1.1 en verde y `npm run typecheck` sin errores.
- [x] 1.3 Agregar en `index.html` `meta name="theme-color"`, `meta name="color-scheme" content="light"` y `meta name="description"` en español, sin fuentes ni assets remotos. **Verifica:** `npm run build` genera el bundle y el HTML contiene los metadatos.
- [x] 1.4 Escribir en rojo en el mismo `tokens.test.ts` un guard que lea `app.css` con `?raw` y falle si encuentra hex, `rgb()` o `hsl()` fuera de `tokens.css` (excepto la excepción documentada del `color_sobreturno` inline). **Verifica:** el guard falla si se introduce un color literal y pasa con la hoja actual.
- [x] 1.5 Crear `docs/design-system.md` con dirección visual, tabla de tokens y ratios, escala tipográfica, shells, inventario de componentes, breakpoints, accesibilidad e impresión; enlazarlo desde `AGENTS.md` solo si el orquestador lo pide (no editar `CHANGES.md`). **Verifica:** cada token documentado existe en `tokens.css` y la tabla coincide con la matriz de D3.

## 2. Componentes compartidos: primitivas de formulario y feedback

- [x] 2.1 Escribir en rojo `frontend/src/shared/ui/components.test.tsx` para `Button`, `Input`, `Select`, `Loading` y `ErrorBanner`: `button` vs `a` según `href`, `disabled` nativo, nombre accesible exacto con hint/error por `aria-describedby`, `role="status"` con `Cargando…` y `role="alert"` con el mensaje verbatim. **Verifica:** el test falla antes de los componentes.
- [x] 2.2 Implementar `frontend/src/shared/ui/Button.tsx`, `Input.tsx`, `Select.tsx`, `Loading.tsx` y `ErrorBanner.tsx` con `useId`, tipos estrictos y sin lógica de negocio; estilarlos en `app.css` con tokens. **Verifica:** test 2.1 en verde y `grep` sin `any` en `shared/ui`.
- [x] 2.3 Escribir en rojo en `components.test.tsx` los casos de `Card`, `Table`, `Badge`, `EstadoBadge`, `EmptyState` y `PageHeader`: nivel de encabezado, `th[scope]`, región de tabla con nombre accesible, tono de estado sin traducir el texto, vacío con acción y `h1` único del encabezado. **Verifica:** el test falla antes de los componentes.
- [x] 2.4 Implementar `Card.tsx`, `Table.tsx`, `Badge.tsx`, `EstadoBadge.tsx`, `EmptyState.tsx` y `PageHeader.tsx`; `EstadoBadge` mapea estado crudo a tono (desconocido → neutral) sin cambiar el texto visible. **Verifica:** test 2.3 en verde y `npm run build` sin errores.
- [x] 2.5 Documentar en `docs/design-system.md` la API y los estados de cada componente con un ejemplo de uso por cada uno. **Verifica:** los nombres de props documentados existen en los tipos y no hay componentes fuera de `shared/ui`.

## 3. Shells de navegación y clasificación de rutas

- [x] 3.1 Escribir en rojo `frontend/src/shared/layout/BackofficeShell.test.tsx`: rail con Agenda/Reportes/Usuarios/Auditoría, `aria-current="page"` en la ruta activa, nombre/email de sesión, `Salir` que llama a `logout`, skip link primero y menú móvil con `aria-expanded`/`aria-controls`. **Verifica:** el test falla antes del shell.
- [x] 3.2 Escribir en rojo `frontend/src/shared/layout/PublicShell.test.tsx`: marca, enlace a `/reservar` y `/privacidad`, ausencia de enlaces protegidos y de datos de sesión. **Verifica:** el test falla antes del shell.
- [x] 3.3 Implementar `BackofficeShell.tsx`, `PublicShell.tsx` y `SkipLink`/wrapper `#contenido`; en `App.tsx` clasificar rutas públicas vs backoffice sin introducir router; quitar el botón `Salir` duplicado de `AgendaPage`, `ReportesPage`, `UsuariosPage` y `AuditoriaPage`. **Verifica:** tests 3.1/3.2 en verde, `App.test.tsx` sigue en verde y `npm run test` completo sin regresiones.
- [x] 3.4 Escribir en rojo `frontend/src/routes.test.tsx`: un solo `h1` por ruta, shell correcto, portada `/` con las dos entradas (reservar e ingresar) y 404 público sin navegación protegida. **Verifica:** el test falla antes de ajustar la portada y el 404.
- [x] 3.5 Ajustar la portada y el 404 al shell público para que el test 3.4 pase, conservando un `h1` único en `/` (hoy “Clínica Odontológica”). **Verifica:** `routes.test.tsx` en verde y `App.test.tsx` sin cambios.
- [x] 3.6 Navegación interna sin recarga: helper `navigate`/`usePathname`/`Link`, `App.tsx` reactivo al pathname, shells y enlaces internos migrados; la sesión en memoria sobrevive y back/forward funcionan. **Verifica:** `src/shared/navigation.test.tsx` (click, modificadores, `target`, `popstate`) + `src/navigation.test.tsx` (Agenda→Reportes conserva `getSession()` y vuelve con Atrás), suite completa/typecheck/build y navegador real (`navegacion.txt`).
- [x] 3.7 Login y layout de autenticación centrado: `LoginForm` con `PageHeader`/`Card`/`Input`/`Button`/`ErrorBanner`, panel `.ds-auth` de 440 px centrado horizontal y verticalmente en el alto disponible, shell sin sesión con `.ds-shell--signed-out` (sin rail) y contenedor `.ds-content` consistente en todas las rutas. **Verifica:** `src/features/auth/LoginForm.test.tsx`, `src/styles/auth.test.ts`, `routes.test.tsx` (login centrado en las 4 rutas) y capturas `final-login-*` a 320/900/1280.

## 4. Páginas públicas: reserva, gestión, privacidad y 404

- [x] 4.1 Escribir en rojo en `ReservaPage.test.tsx`, incluido el bloque `GestionTurnoPage` del mismo archivo: secciones con jerarquía, grilla de horarios seleccionable, estado vacío de horarios, error 409 verbatim, 410 de token vencido y ausencia de acciones cuando no se puede operar. **Verifica:** los casos nuevos fallan antes del layout.
- [x] 4.2 Implementar el layout de `/reservar` con `PageHeader`, `Input`/`Select`, grilla de huecos y confirmación; conservar textos exactos (`Reservar`, `Turno reservado`, enlace `Gestionar mi turno`, enlace de privacidad sin checkbox). **Verifica:** `ReservaPage.test.tsx` completo en verde.
- [x] 4.3 Implementar `/reservar/gestion/:token` con resumen en `Card`, `EstadoBadge`, acciones y `ErrorBanner` para 410/409; conservar `role="status"` con `Turno cancelado.` exacto. **Verifica:** el bloque `GestionTurnoPage` del test en verde.
- [x] 4.4 Implementar `/privacidad` con texto de lectura larga, versión/fecha destacadas y hash en `--font-mono`, y el 404 con salida a reservar; conservar `role="alert"` verbatim y el enlace a `/reservar`. **Verifica:** `PrivacidadPage.test.tsx` y `App.test.tsx` (404) en verde.
- [x] 4.5 Actualizar `docs/validacion-manual-pendiente.md` con el bloque C-17 de rutas públicas: qué mirar, en qué ancho y resultado esperado. **Verifica:** las rutas y textos del bloque coinciden con las páginas implementadas.

## 5. Backoffice: agenda

- [x] 5.1 Escribir en rojo en `AgendaPage.test.tsx` los casos visuales: toolbar en una fila, `.agenda-semana`/`.agenda-mes` conservados, `EstadoBadge` con tono por estado, sobreturno y bloqueo visibles, scroll interno de la grilla en móvil y foco visible en drop targets. **Verifica:** los casos nuevos fallan antes del CSS/refactor.
- [x] 5.2 Implementar el layout de agenda con el shell, `PageHeader`, filtros con `Input`/`Select` y grilla estilada en `app.css`; mantener clases, `data-hora`, `aria-label` de turno/bloqueo y el drag & drop intactos. **Verifica:** `AgendaPage.test.tsx` completo en verde, incluidos 409 y roles de solo lectura.
- [x] 5.3 Verificar la agenda a 320 px y 900 px con la grilla desplazándose dentro de su contenedor y el menú en la barra superior. **Verifica:** revisión en navegador con captura en `docs/skills-mcp/evidencias/c-17/frontend/` y sin scroll horizontal de página.

## 6. Backoffice: reportes e impresión

- [x] 6.1 Escribir en rojo en `ReportesPage.test.tsx` los casos de jerarquía de los cuatro tableros, totales legibles, tablas dentro de región desplazable, vacío de detalle y estados de exportación (`pendiente`, `generando`, `lista`, `fallida`). **Verifica:** los casos nuevos fallan antes del layout.
- [x] 6.2 Implementar el layout de `/reportes` con `PageHeader`, filtros, `Card` por tablero, `Table` y estados de exportación; conservar los textos que los tests verifican (`Turnos totales: 99`, `Estado: pendiente`, `Descargar ZIP`). **Verifica:** `ReportesPage.test.tsx` completo en verde.
- [x] 6.3 Implementar `@media print` para reportes (sin rail/filtros/botones, negro sobre blanco, `thead` repetido, filas sin cortar) y verificarlo en la vista previa del navegador. **Verifica:** captura de la vista previa en la evidencia y CSS de impresión presente en `app.css`.

## 7. Backoffice: usuarios y auditoría

- [x] 7.1 Escribir en rojo en `UsuariosPage.test.tsx` los casos de tabla en región desplazable, vacío, 403/409/422 verbatim y controles de escritura ocultos cuando la API prohíbe. **Verifica:** los casos nuevos fallan antes del layout.
- [x] 7.2 Implementar `/usuarios` con `PageHeader`, formulario de alta en `Card`, tabla densa con badges de estado y acciones agrupadas; conservar nombres exactos (`Nombre`, `Email`, `Contraseña`, `Crear usuario`, `Guardar roles`, `Desactivar`, `activo`/`inactivo`). **Verifica:** `UsuariosPage.test.tsx` completo en verde.
- [x] 7.3 Implementar `/auditoria` con filtros, tabla paginada y sin controles de escritura; conservar `Total: 120`, nombres de filtros y botones `Anterior`/`Siguiente`. **Verifica:** `AuditoriaPage.test.tsx` completo en verde.

## 8. Responsive, accesibilidad y movimiento

- [x] 8.1 Escribir en rojo `frontend/src/a11y.test.tsx`: skip link primero en el DOM, un `main` por ruta, un `h1`, `th[scope="col"]` en tablas, regiones de tabla con nombre accesible y foco que no se elimina. **Verifica:** el test falla antes de completar el marcado.
- [x] 8.2 Corregir el marcado que falte (scope de encabezados, `aria-label` de regiones, `aria-invalid`/`aria-describedby` en errores) hasta que 8.1 pase. **Verifica:** `a11y.test.tsx` en verde y `npm run typecheck` sin errores.
- [x] 8.3 Implementar y verificar los cortes 640/900/1024/1280, el rail fijo y la barra superior móvil; agregar al test de estilos una aserción de que existen los `@media` y de que `body` no declara `overflow-x`. **Verifica:** test en verde y revisión manual a 320/900/1280 px.
- [x] 8.4 Implementar `prefers-reduced-motion` y verificar que no hay `@keyframes` en bucle; documentar en `docs/design-system.md` la política de movimiento. **Verifica:** test de estilos en verde y emulación de movimiento reducido en el navegador sin transiciones.

## 9. Integración, evidencia y cierre

- [x] 9.1 Correr la suite completa del frontend (`npm run test`), `npm run typecheck` y `npm run build`; confirmar que los 64 tests preexistentes siguen en verde y que no hay cambios en llamadas de red ni en `session.ts`. **Verifica:** salida de los tres comandos guardada en `docs/skills-mcp/evidencias/c-17/frontend/`.
- [x] 9.2 Escribir `docs/skills-mcp/evidencias/c-17/matriz-escenarios.md` con cada escenario de `specs/platform/design-system/spec.md`, su test o revisión manual y el borde observable; confirmar que no queda ninguno sin cobertura. **Verifica:** la matriz cubre los 11 requisitos y todos sus escenarios.
- [x] 9.3 Completar `docs/validacion-manual-pendiente.md` con el bloque C-17 de backoffice y la prueba visual final: recorrido de las nueve rutas, anchos 320/900/1280, teclado, contraste, impresión de reportes y estados 403/409/410/422. **Verifica:** el bloque enumera cada ruta con resultado esperado y queda listo para la aceptación del usuario.
- [x] 9.4 Revisar que `git diff --stat` solo toque `frontend/`, `docs/` y los artefactos del change, sin backend, `CHANGES.md`, Compose ni specs existentes. **Verifica:** `git status` y `git diff --stat` sin archivos fuera de alcance.

## 10. Ajustes de aceptación visual

- [x] 10.1 Portada como hero vertical centrado: `.ds-home` con eyebrow “Turnos online”, `h1` “Clínica Odontológica”, descripción, entradas en columna/fila y `ApiStatus` debajo; columna de 44 rem y aire vertical con tokens. **Verifica:** `HomePage.test.tsx`, `styles/home.test.ts` y capturas `final-home-{320,900,1280}.png`.
- [x] 10.2 Estado del backend con semáforo: tres filas (`API`, `Base de datos`, `Redis`) con `Badge` success/danger, texto “Operativo”/“Con error”, errores verbatim en mono y carga en `role="status"`. **Verifica:** `ApiStatus.test.tsx` (sano, API caída, db caída, carga) y `final-home-error-900.png`.
- [x] 10.3 Privacidad centrada: `main.ds-reading` con `max-width: var(--measure-public)` y `margin-inline: auto`; header y artículo en la misma columna; hash sin desbordar a 320 px. **Verifica:** `PrivacidadPage.test.tsx`, `styles/reading.test.ts` y capturas `final-privacidad-{320,900,1280}.png`.
- [x] 10.4 Volver real desde privacidad: `goBack(fallback)` con índice `appIndex` en `history.state`; botón “Volver” (ghost) y CTA “Reservar turno” con `Button` del sistema. **Verifica:** `shared/navigation.test.tsx` (con/sin historial interno), `PrivacidadPage.test.tsx` y mediciones reales portada→privacidad→portada, reservar→privacidad→reservar y entrada directa→`/`.
- [x] 10.5 Auditoría de centrado de las rutas y documentación de `.ds-home`, `.ds-reading` y `.ds-status`. **Verifica:** `home-layout.txt` (9 rutas a 1280, sin overflow) y `docs/design-system.md`.
- [x] 10.6 Portada con título público: `h1` “Clínica Odontológica” y eyebrow “Turnos online”; `Backoffice` queda solo en el login de las cuatro rutas del backoffice. **Verifica:** `App.test.tsx`, `a11y.test.tsx`, `HomePage.test.tsx` actualizados, login sin sesión con `h1` Backoffice y capturas `final-home-*` regeneradas.

## Workflow follow-up

- El usuario corre la prueba visual final sobre `docker compose up -d --build` (o `npm run dev`) y aprueba la página completa; no hay gate de aprobación manual change por change (decisión 2026-11-03).
- Con la aprobación, correr `/opsx-archive`, marcar `[x]` en `CHANGES.md` y commitear/pushear el cierre con conventional-commits, sin co-autoría IA (R-13).
