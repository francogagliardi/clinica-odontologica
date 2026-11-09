# Proposal

## Why

Las nueve rutas de la SPA ya funcionan —reserva pública, agenda, reportes, usuarios, auditoría, privacidad y enlace del paciente— pero se sirven sin una sola hoja de estilos: el navegador aplica sus defaults, los formularios y tablas pierden jerarquía, y la experiencia no transmite la confianza que un consultorio odontológico necesita. El backend está completo y estable, así que la brecha que queda para la entrega es exclusivamente visual y de accesibilidad; C-17 la cierra sin reabrir contratos ni flujos.

## What Changes

- **Sistema de diseño propio** para la SPA React + TypeScript + Vite, sin librería externa de UI ni framework de utilidades: tokens de color, tipografía, espaciado, radios, bordes, foco y movimiento, más una hoja global única organizada por capas.
- **Identidad visual concreta** para un consultorio odontológico profesional: paleta mineral con un verde clínico, tipografía serif editorial para titulares, sans del sistema para interfaz y mono solo para datos máquina (hash, IDs, IP, timestamps). Documentada con contrastes WCAG AA calculados.
- **Shells de navegación**: backoffice con rail lateral (Agenda, Reportes, Usuarios, Auditoría) y pie de sesión; páginas públicas con encabezado sobrio y enlace a privacidad; 404 público. El login no muestra navegación protegida.
- **Inventario de componentes compartidos** en `src/shared/ui`: `Button`, `Input`, `Select`, `Card`, `Table`, `Badge`, `EstadoBadge`, `EmptyState`, `ErrorBanner`, `Loading` y `PageHeader`, con estados default, hover, foco, deshabilitado, cargando y error.
- **Layouts para las nueve rutas existentes** (`/`, `/reservar`, `/reservar/gestion/:token`, `/agenda`, `/reportes`, `/usuarios`, `/auditoria`, `/privacidad`, 404), conservando el marcado semántico, los textos exactos de etiquetas y el comportamiento funcional.
- **Estados de UX uniformes**: carga anunciada, vacío con acción, error de API mostrado verbatim (403/409/422/410), token vencido, controles deshabilitados y tablas desbordadas con scroll propio.
- **Accesibilidad y responsive**: WCAG 2.2 AA en contraste y foco, navegación por teclado, skip link, un `h1` por página, targets táctiles, `prefers-reduced-motion` y una hoja de impresión para reportes.
- **Sin cambios de contrato**: no se agregan endpoints ni se modifican respuestas; el token de sesión sigue en memoria (nunca `localStorage`), no se mueve lógica de negocio al cliente y la suite existente debe quedar en verde.

## Capabilities

### New Capabilities

- `platform/design-system`: identidad visual, tokens, hoja global, shells de navegación, componentes compartidos, estados de UX, accesibilidad, responsive, movimiento reducido e impresión de la SPA, sin alterar contratos ni comportamiento funcional.

### Modified Capabilities

<!-- Ninguna. `platform/frontend-baseline` sigue vigente: C-17 la cumple y no cambia sus requisitos. -->

## Impact

- **Frontend**: `src/styles/` (tokens, base, componentes, impresión), `src/shared/ui/`, `src/shared/layout/`, `src/pages/*`, `src/features/agenda/components.tsx`, `src/features/auth/LoginForm.tsx`, `src/features/status/ApiStatus.tsx`, `src/App.tsx`, `src/main.tsx`, `index.html` (metadatos y `theme-color`).
- **Pruebas**: nuevos tests RTL de roles, etiquetas, foco, navegación, estados y contraste de tokens; se conservan los 64 tests actuales, `npm run typecheck` y `npm run build`.
- **Dependencias**: ninguna nueva de aplicación ni de testing; sin Tailwind, sin CSS-in-JS y sin fuentes remotas.
- **Backend / API / Compose / migraciones**: sin cambios. No se toca ningún endpoint, contrato, worker ni esquema.
- **Fuera de alcance**: funcionalidades nuevas (historia clínica, presupuestos o caja no tienen pantalla y siguen sin tenerla), cambios de flujo clínico/facturación, modo oscuro, fotografías o ilustraciones de stock, rediseño de marca más allá de los tokens y componentes descritos, y aceptación visual final (la hace el usuario sobre la página completa).
