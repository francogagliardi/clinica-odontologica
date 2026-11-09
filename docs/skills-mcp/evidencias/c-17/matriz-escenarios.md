# C-17 — Matriz de escenarios

> Fuente: `openspec/changes/c-17-frontend-design-system/specs/platform/design-system/spec.md`.
> Cobertura: **11 requirements / 41 escenarios**. Cada fila indica el test o la
> revisión que lo verifica y el borde observable. Evidencia de ejecución:
> `frontend/npm-test.txt`, `frontend/npm-typecheck.txt`, `frontend/npm-build.txt`,
> `frontend/final/mediciones.txt`, `frontend/final/teclado.txt` y las capturas
> `frontend/final/*.png`. Resultado: **199/199 tests en verde**.

## R1 — Tokens de diseño como fuente única (3)

| # | Escenario | Verificación | Borde observable |
|---|---|---|---|
| 1 | Inventario completo de tokens | `src/styles/tokens.test.ts` → “declara los grupos requeridos con valor no vacío” | 74 custom properties en `tokens.css` agrupadas por color, tipografía, espaciado, radios, bordes, foco, sombra, movimiento y layout |
| 2 | Componente con color literal | `tokens.test.ts` → “no deja colores literales fuera de tokens.css” + self-test del guard | `app.css` no contiene hex/`rgb()`/`hsl()`; el guard falla ante un literal de prueba |
| 3 | Cambio global de un token | `tokens.test.ts` → “solo referencia tokens declarados”; grep de `var(--color-primary)` en `app.css` | Botones, enlaces, foco y badges consumen `var(--color-primary)`; cambiar el token no requiere tocar componentes |

## R2 — Identidad tipográfica y contraste AA (3)

| # | Escenario | Verificación | Borde observable |
|---|---|---|---|
| 4 | Pares de tokens conformes | `tokens.test.ts` → “recalcula la matriz de contraste de design.md §D3” | 17 pares texto/fondo recalculados desde los hex; coinciden con la tabla D3 |
| 5 | Par de contraste insuficiente | `tokens.test.ts` → “mantiene los umbrales AA” | El mensaje nombra el par y el ratio; falla si texto < 4.5:1 o interfaz < 3:1 |
| 6 | Zoom y reflujo | `responsive.test.ts` + `final/mediciones.txt` + capturas 320/900/1280 | Ninguna ruta supera `scrollWidth > innerWidth` a 320 px (incluido el hash de `/privacidad`, corregido con `overflow-wrap`) |

## R3 — Shell de backoffice con navegación protegida (4)

| # | Escenario | Verificación | Borde observable |
|---|---|---|---|
| 7 | Sesión activa en agenda | `shared/layout/BackofficeShell.test.tsx` → rail y `aria-current`; `routes.test.tsx`; `final-agenda-1280.png` | Los cuatro módulos, Agenda con `aria-current="page"`, identidad y Salir |
| 8 | Backoffice sin sesión | `BackofficeShell.test.tsx` → “no expone enlaces protegidos”; `routes.test.tsx` → “sin sesión no expone enlaces protegidos” | `nav` ausente, sin Salir; solo marca y acceso |
| 9 | Ruta desconocida | `routes.test.tsx` → 404 público; `final-404-*.png` | `h1` “Página no encontrada” + 404, navegación pública, sin rail |
| 10 | Salir conserva el comportamiento | `BackofficeShell.test.tsx` → “Salir descarta la sesión en memoria”; `session.test.ts` | `getSession()` pasa a `null`; sin escritura en almacenamiento |

## R4 — Shell público de reserva y privacidad (3)

| # | Escenario | Verificación | Borde observable |
|---|---|---|---|
| 11 | Reserva pública | `PublicShell.test.tsx`, `routes.test.tsx`, `final-reservar-*.png` | Marca, Reservar y Privacidad; sin enlaces de Agenda/Reportes/Usuarios/Auditoría |
| 12 | Enlace de gestión válido | `ReservaPage.test.tsx` bloque `GestionTurnoPage` → resumen y acciones | Card “Resumen del turno”, badge, Confirmar/Cancelar dentro del shell público |
| 13 | Enlace vencido o usado | `ReservaPage.test.tsx` → 410 verbatim; `final-gestion-410-*.png` | Alerta `410` + “Pedí un enlace nuevo en la clínica.”, sin acciones |

## R5 — Componentes compartidos y estados (4)

| # | Escenario | Verificación | Borde observable |
|---|---|---|---|
| 14 | Operación por teclado | `a11y.test.tsx`; `final/teclado.txt` | Primer Tab enfoca “Saltar al contenido” en `/` y `/agenda`; controles alcanzables |
| 15 | Control deshabilitado | `components.test.tsx` → Button disabled; páginas (Reservar, Descargar ZIP) | `disabled` nativo, no dispara `onClick` ni llamadas de red |
| 16 | Error y carga anunciados | `components.test.tsx` → Loading/ErrorBanner | `role="status"` con “Cargando…”; `role="alert"` con mensaje verbatim |
| 17 | Etiqueta accesible exacta | `components.test.tsx` → Input/Select; `a11y.test.tsx` login | Nombre = etiqueta visible; ayuda/error por `aria-describedby` |

## R6 — Estados de UX y errores de API verbatim (5)

| # | Escenario | Verificación | Borde observable |
|---|---|---|---|
| 18 | Conflicto 409 | `ReservaPage.test.tsx`, `GestionTurnoPage` y `AgendaPage.test.tsx` | Alerta con `409` y detalle del servidor; la pantalla conserva turno/selección |
| 19 | Permiso 403 | `UsuariosPage.test.tsx`, `AuditoriaPage.test.tsx`, `ReportesPage.test.tsx` | Mensaje verbatim; sin controles de escritura ni tabla cuando la API prohíbe |
| 20 | Validación 422 | `UsuariosPage.test.tsx` → alta vacía | Se envía el POST tal cual y se muestra `422` + detalle del backend |
| 21 | Lista vacía | `components.test.tsx` EmptyState; vacíos de agenda, usuarios y auditoría | Título, explicación y acción opcional; sin filas ni totales inventados |
| 22 | Token vencido | `ReservaPage.test.tsx` 410; captura `final-gestion-410-*.png` | 410 verbatim + enlace nuevo; sin Confirmar/Cancelar |

## R7 — Layout de las nueve rutas existentes (5)

| # | Escenario | Verificación | Borde observable |
|---|---|---|---|
| 23 | Inventario de rutas | `routes.test.tsx`, `a11y.test.tsx`, `final/mediciones.txt` | 9 rutas con un `main`, un `h1`, shell correcto y sin overflow a 320/900/1280 |
| 24 | Portada con doble entrada | `routes.test.tsx` → dos entradas; `final-home-*.png` | `h1` “Clínica Odontológica” + “Reservar turno” e “Ingresar al backoffice” |
| 25 | Agenda en sus tres vistas | `AgendaPage.test.tsx`; `final-agenda-*.png`, `final-agenda-semana-*.png`, `final-agenda-mes-*.png` | `.agenda-semana`/`.agenda-mes`, `[data-hora]`, `aria-label` de turno, sobreturno y bloqueo |
| 26 | Reportes y exportación | `ReportesPage.test.tsx`; `final-reportes-*.png` | Cuatro tableros, totales, tablas en región y estados `pendiente`/`generando`/`lista`/`fallida` |
| 27 | Privacidad de lectura larga | `PrivacidadPage.test.tsx`; `final-privacidad-*.png` | Artículo con medida, versión/fecha y hash monoespaciado; sin checkbox |

## R8 — Diseño responsive y tablas desbordadas (4)

| # | Escenario | Verificación | Borde observable |
|---|---|---|---|
| 28 | Ancho mínimo de 320 px | `responsive.test.ts`; `final/mediciones.txt` (todas las filas `overflow=no`) | `scrollWidth === innerWidth` en las 9 rutas; menú disponible donde corresponde |
| 29 | Transición de rail a barra superior | `responsive.test.ts`; mediciones `menu=visible` a 320/900 y `menu=oculto` a 1280 | Rail de 232 px desde 1024 px; botón Menú solo por debajo |
| 30 | Tabla más ancha que la pantalla | `a11y.test.tsx` contrato de tablas; `responsive.test.ts` | Cada tabla vive en `role="region"` con `aria-label`, `tabIndex=0` y scroll propio |
| 31 | Objetivos táctiles | `responsive.test.ts`; `mediciones.txt` “objetivos táctiles 320” | Acción principal 44 px; enlaces y acciones secundarias ≥ 24 px |

## R9 — Movimiento reducido y preferencias (3)

| # | Escenario | Verificación | Borde observable |
|---|---|---|---|
| 32 | Preferencia de movimiento reducido | `motion.test.ts`; mediciones `transitionDuration=1e-05s` | `transition-duration`/`animation-duration` = `--motion-reduced`, sin scroll suave |
| 33 | Página en reposo | `motion.test.ts` | Sin `@keyframes` ni `animation: infinite` en `app.css` |
| 34 | Movimiento que explica un cambio | `motion.test.ts` + revisión visual de foco/hover/menú | Solo transiciones de estado de 120/180 ms; sin animaciones decorativas |

## R10 — Impresión legible de reportes (3)

| # | Escenario | Verificación | Borde observable |
|---|---|---|---|
| 35 | Impresión de reportes | `ReportesPage.test.tsx` (CSS); `final-reportes-impresion-1280.png` | Sin topbar/rail/filtros/botones/exportación; negro sobre blanco |
| 36 | Tabla que cruza páginas | `ReportesPage.test.tsx` + CSS | `thead { display: table-header-group }`, `tr { page-break-inside: avoid }` |
| 37 | Impresión de una ruta pública | `final-privacidad-impresion-1280.png` | Texto legible sin menú ni acciones; versión y hash conservados |

## R11 — Presentación sin cambios de contrato ni de sesión (4)

| # | Escenario | Verificación | Borde observable |
|---|---|---|---|
| 38 | Sesión en memoria | `session.test.ts`; `git diff --name-only` sin `session.ts` | `getSession()`/`logout()` intactos; sin `localStorage`/cookies |
| 39 | Mismas llamadas de red | Suite de `features/*/api.test.ts` y páginas; diff sin `features/*/api.ts` ni `shared/api/client.ts` | Mismos endpoints, métodos y cuerpos |
| 40 | Suite y build | `npm-test.txt` (199/199), `npm-typecheck.txt`, `npm-build.txt` | 64 tests preexistentes + 135 nuevos, typecheck y build en verde |
| 41 | Regresión funcional | Page tests de reserva, agenda, reportes, usuarios, auditoría y privacidad | Mismos textos, roles y comportamiento observable; solo cambia la presentación |

## Bug post-cierre: navegación interna

El enlace del rail era un `<a href>` nativo y `App.tsx` no escuchaba cambios de
`pathname`; navegar de Agenda a Reportes recargaba el documento y perdía el JWT en
memoria. Corregido con `navigate`/`usePathname`/`Link` (R-03 se mantiene: sin
`localStorage`). Cobertura nueva:

- **R3 — Sc. 7/8/10** (shell con sesión, sin sesión y Salir): `src/navigation.test.tsx`
  confirma que la sesión y la identidad sobreviven a Agenda→Reportes y a Atrás.
- **R11 — Sc. 38** (sesión en memoria): sin persistencia nueva; el token sigue en
  `features/auth/session.ts`.
- **R5 — Sc. 14** (teclado): `Link` conserva `href` y foco; los modificadores y
  `target="_blank"` no se interceptan.
- Evidencia de navegador: `frontend/final/navegacion.txt` (marcador JS intacto,
  `performance.navigation` = 1 y sesión activa) y `final-navegacion-sin-recarga.png`.
- Detalle del fix: `frontend/fix-navegacion.md`.

## Ajuste post-cierre: login y layout de autenticación

El login del backoffice usaba HTML crudo y quedaba pegado a la izquierda (además,
sin sesión el contenido ocupaba la columna del rail inexistente). Ahora
`LoginForm` usa `PageHeader`/`Card`/`Input`/`Button`/`ErrorBanner` dentro de
`.ds-auth`, con panel de 440 px centrado en ambos ejes y shell
`.ds-shell--signed-out` sin rail. Cobertura:

- **R3 — Sc. 8** (backoffice sin sesión): `routes.test.tsx` verifica login centrado,
  `.ds-shell--signed-out` y ausencia de `nav` en `/agenda`, `/reportes`, `/usuarios`
  y `/auditoria`.
- **R5 — Sc. 17** (etiqueta exacta) y **R6 — Sc. 18/19** (errores): `LoginForm.test.tsx`
  conserva `Email`, `Contraseña`, `Ingresar`, `role="alert"` verbatim y
  `aria-invalid`/`aria-describedby`.
- **R7 — Sc. 23** y **R8 — Sc. 28**: `styles/auth.test.ts` + `final/login-layout.txt`
  confirman panel 440 px, márgenes simétricos y `overflow=no` a 320/900/1280.
- Capturas: `final-login-agenda-{320,900,1280}.png`, `final-login-{reportes,usuarios,auditoria}-1280.png`
  y `final-login-error-900.png`.

## Ajuste post-cierre: aceptación visual

- **Portada (R7 Sc. 24, R8 Sc. 28)**: `HomePage.test.tsx` + `styles/home.test.ts`
  verifican `.ds-home` centrado (44 rem), eyebrow/`h1`/descripción/acciones y
  `ApiStatus`; `home-layout.txt` mide offset superior y márgenes simétricos a
  320/900/1280.
- **Estado del backend (R6 Sc. 21, R8)**: `ApiStatus.test.tsx` cubre sano (3
  success), API caída (solo API danger + error verbatim), db caída (solo db
  danger) y carga en `role="status"`; `final-home-error-900.png`.
- **Privacidad centrada (R7 Sc. 27, R10 Sc. 37)**: `PrivacidadPage.test.tsx` +
  `styles/reading.test.ts`; columna de 587 px centrada (347/347 a 1280) y sin
  overflow a 320.
- **Volver real (R5 Sc. 14, R11)**: `shared/navigation.test.tsx` prueba
  `goBack` con y sin `appIndex`; mediciones reales portada→privacidad→portada,
  reservar→privacidad→reservar y entrada directa→`/`.
- **Auditoría de centrado**: `home-layout.txt` recorre las 9 rutas a 1280 sin
  overflow; el backoffice conserva `.ds-content` tras el rail de 232 px.
- **Título público (aprobado)**: la portada usa `h1` “Clínica Odontológica” y
  eyebrow “Turnos online”; “Backoffice” queda solo en el login. Tests
  `App.test.tsx`, `a11y.test.tsx` y `HomePage.test.tsx` actualizados; capturas
  `final-home-*` regeneradas.

## Cobertura manual pendiente

- Enlace de gestión **válido** con token real y datos del seed (el test usa fixture; la captura real disponible es el estado 410).
- Zoom real al 200 % y reflujo en navegador (los cortes de 320 px y las mediciones cubren el caso extremo).
- Impresión física y fuentes serif en macOS/Linux.
- Recorrido completo con los cinco roles demo (el bloque final de `docs/validacion-manual-pendiente.md` lo enumera).
