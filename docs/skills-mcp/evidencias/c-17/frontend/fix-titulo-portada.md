# C-17 — Cambio aprobado: título público de la portada

## Decisión

La portada pública `/` ya no se titula “Backoffice”. Ahora:

- `h1` → **“Clínica Odontológica”**.
- eyebrow → **“Turnos online”** (evita repetir la marca).
- El `h1` **“Backoffice”** queda reservado al login del backoffice
  (`/agenda`, `/reportes`, `/usuarios`, `/auditoria` sin sesión).

## Archivos

- `frontend/src/pages/HomePage.tsx`.
- Tests actualizados: `App.test.tsx` (test legacy renombrado a portada pública),
  `a11y.test.tsx` (tabla ruta→heading) y `HomePage.test.tsx` (h1 y eyebrow).
- Contrato: `openspec/changes/c-17-frontend-design-system/design.md` (contexto y
  D5), `docs/design-system.md` (§5.1), `tasks.md` (3.5, 10.1 y nueva 10.6).
- `docs/validacion-manual-pendiente.md` y `matriz-escenarios.md` alineados.

## Verificación

- `npm test`: **199/199** en 31 archivos (el número no cambia: se actualizaron
  expectativas, no se agregaron tests).
- `npm run typecheck` y `npm run build`: en verde.
- `final/home-layout.txt`:
  - 320/900/1280: eyebrow “Turnos online”, título “Clínica Odontológica”,
    columna 288/704/704 px, `scrollWidth === viewport`;
  - estado con error conserva el título público y el mensaje verbatim;
  - login de las cuatro rutas del backoffice: `h1=Backoffice`.
- Capturas regeneradas: `final/final-home-320.png`, `final-home-900.png`,
  `final-home-1280.png` y `final-home-error-900.png`.

## Límites

- No se tocaron backend, contratos de API, `session.ts`, `CHANGES.md`, specs ni
  Compose. Sin commit ni archive.
