# C-17 — Fix: login y layout de autenticación centrado

## Bug reportado

1. El login del backoffice seguía con HTML crudo (`main`/`h1`/`form`/`label`/
   `input`/`button`), sin `Card`, `PageHeader`, `Input`, `Button` ni estilos del
   design system.
2. El contenido no quedaba centrado: el login aparecía pegado a la izquierda.
   Sin sesión, el shell de backoffice seguía reservando la columna del rail
   (232 px) aunque el rail no se renderizara.

## Fix

- `frontend/src/features/auth/LoginForm.tsx`:
  - `main.ds-auth` + `.ds-auth__panel` (panel de 440 px).
  - `PageHeader` con `h1` “Backoffice”.
  - `Card` “Acceso del equipo”.
  - `Input` para `Email` y `Contraseña` (etiquetas exactas, `aria-invalid` y
    `aria-describedby` al error).
  - `Button type="submit"` “Ingresar”.
  - `ErrorBanner` con `id` y `role="alert"`, mensaje 401/422 verbatim.
- `frontend/src/shared/layout/BackofficeShell.tsx`: agrega
  `.ds-shell--signed-out` cuando no hay sesión.
- `frontend/src/styles/app.css`:
  - `.ds-shell--signed-out`: flex column con `min-height: 100vh`.
  - `.ds-shell--signed-out .ds-content`: `flex: 1` + centrado en ambos ejes;
    el contenido ocupa todo el ancho (sin columna de rail fantasma).
  - `.ds-auth`: flex centrado, ancho 100%, padding vertical.
  - `.ds-auth__panel`: `max-width: 27.5rem` (440 px) y `margin-inline: auto`.
  - Botón de login a ancho completo.
- `frontend/src/shared/ui/Input.tsx` y `Select.tsx`: aceptan `aria-invalid` y
  `aria-describedby` del consumidor y los combinan con hint/error propios, para
  que el banner del login quede asociado a los dos campos.
- `frontend/src/shared/ui/ErrorBanner.tsx`: prop opcional `id` (necesaria para
  `aria-describedby`).

## Tests nuevos (10)

- `frontend/src/features/auth/LoginForm.test.tsx` (2):
  - estructura `main.ds-auth` → `.ds-auth__panel` → `.ds-card`, `h1` Backoffice,
    labels exactos, botón `Ingresar` y controles del design system;
  - error 401 verbatim en `.ds-error-banner`, `role="alert"` y campos con
    `aria-invalid="true"` + `aria-describedby` apuntando al banner.
- `frontend/src/styles/auth.test.ts` (4): centrado de `.ds-auth`, panel de 440 px
  con `margin-inline:auto`, shell signed-out a alto completo y `body` sin
  `overflow-x`.
- `frontend/src/routes.test.tsx` (+4): `/agenda`, `/reportes`, `/usuarios` y
  `/auditoria` sin sesión muestran login centrado y no muestran rail/nav.

## Verificación

- `npm test`: **184/184** en 27 archivos.
- `npm run typecheck`: sin errores.
- `npm run build`: OK.
- Navegador real (`:8080` + API demo `:8000`), `final/login-layout.txt`:
  - panel **440 px** con márgenes izquierdo/derecho simétricos (420/420 a 1280 px;
    230/230 a 900 px; 16/16 a 320 px);
  - espacio superior/inferior simétrico (236/236) dentro del área disponible;
  - `overflow=no` en los tres anchos;
  - mismo resultado en `/reportes`, `/usuarios` y `/auditoria`.
- Contenedores públicos (`.ds-content`) centrados y sin overflow a 1280 px.
- Capturas: `final/final-login-agenda-{320,900,1280}.png`,
  `final/final-login-{reportes,usuarios,auditoria}-1280.png`,
  `final/final-login-error-900.png`.

## Limitaciones

- El panel se centra dentro del área disponible (viewport menos topbar). En
  pantallas muy bajas aparece scroll vertical normal; no hay overflow horizontal.
- Las grillas/tablas internas de las páginas no cambiaron: el fix es de contenedor
  y de la pantalla de acceso.
