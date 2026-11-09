# C-17 — Fix: navegación interna sin recarga

## Bug reportado

Al iniciar sesión como administrador y navegar de **Agenda** a **Reportes**
(también Usuarios o Auditoría), la SPA hacía una recarga completa. Como el JWT
vive solo en memoria (`features/auth/session.ts`, R-03), la sesión se perdía y
había que volver a ingresar.

## Causa

- Los enlaces del rail, la marca y los enlaces públicos eran `<a href>` nativos.
- `App.tsx` leía `window.location.pathname` una sola vez, sin escuchar cambios.
- No existía un router ni un helper de navegación client-side.

## Fix

- `frontend/src/shared/navigation.tsx`:
  - `navigate(to)`: `history.pushState` + evento custom `app:navigate`.
  - `usePathname()`: estado inicial desde `window.location.pathname`, escucha
    `popstate` y `app:navigate`.
  - `Link`: renderiza un `<a href>` real; intercepta solo click izquierdo sin
    `metaKey`/`ctrlKey`/`shiftKey`/`altKey`, sin `target` distinto de `_self` y
    solo para rutas internas (`/…`). `AppLink` queda como alias.
- `App.tsx` usa `usePathname()` y vuelve a renderizar al navegar.
- Migrados a `Link`: rail y marca de `BackofficeShell`, marca y navegación de
  `PublicShell`, `Button` con `href` (portada y 404), enlace de privacidad de
  `/reservar` y “Volver a reservar” de `/privacidad`.
- Se mantienen como `<a>` nativos:
  - el skip link `#contenido` (salto dentro del documento);
  - el enlace de gestión `reserva.gestion_url`, que puede ser absoluto/externo;
  - cualquier futuro enlace externo (`Link` tampoco lo intercepta).

## Tests nuevos (9)

- `frontend/src/shared/navigation.test.tsx` (7):
  - click normal conserva `href` y navega;
  - `ctrl`, `meta`, `shift` y `alt` no se interceptan;
  - `target="_blank"` no se intercepta;
  - `popstate` (Atrás) actualiza `usePathname()`.
- `frontend/src/navigation.test.tsx` (2):
  - Agenda → Reportes: `window.location.pathname` cambia, `getSession()` sigue
    activa, se renderiza el `h1` de Reportes y sus datos, y la identidad sigue en
    el rail;
  - Atrás del navegador vuelve a Agenda con la sesión intacta.

## Verificación

- `npm test`: **174/174** en 25 archivos (165 previos + 9 nuevos).
- `npm run typecheck`: sin errores.
- `npm run build`: OK.
- Navegador real (`:8080` + API demo `:8000`, `final/navegacion.txt`):
  - `forward`: `/reportes`, marcador JS `alive` (sin recarga), sesión
    `admin@clinica.test`, `performance` con **1** entrada de navegación;
  - `back`: `/agenda`, marcador y sesión intactos;
  - `forward-again`: `/reportes`, marcador intacto.
- Captura: `final/final-navegacion-sin-recarga.png`.

## Limitaciones

- Recargar la página (F5) sigue perdiendo la sesión: es el comportamiento
  deliberado de R-03 (token solo en memoria).
- Los enlaces externos siguen siendo navegación del navegador; solo se
  interceptan rutas internas que empiezan con `/` y no `//`.
- No se agregó router, `localStorage` ni `sessionStorage`.
