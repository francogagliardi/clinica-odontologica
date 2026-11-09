# C-17 — Ajustes de aceptación visual

## Hallazgos

1. La portada arrancaba pegada al borde superior y apilada a la izquierda.
2. `ApiStatus` mostraba texto plano, sin semáforo ni señal accesible por fila.
3. `/privacidad` quedaba alineada a la izquierda del `.ds-content`.
4. “Volver a reservar” siempre iba a `/reservar`, aunque se hubiera entrado desde
   la portada.
5. Faltaba documentar los patrones y auditar el centrado de todas las rutas.

## Cambios

- **Portada** (`HomePage.tsx` + `.ds-home`/`.ds-home__inner`):
  eyebrow, `h1` “Backoffice”, descripción, dos entradas y `ApiStatus`; columna de
  44 rem, `text-align: center`, `padding-block: clamp(var(--space-8), 6vw, var(--space-12))`,
  acciones en columna y fila desde 640 px.
- **Estado** (`ApiStatus.tsx`):
  `Card` “Estado del sistema”; tres filas con `role="group"` y `aria-label`
  (`API`, `Base de datos`, `Redis`), `Badge` success/danger y texto visible
  “Operativo”/“Con error”; `db`/`redis` solo son success con `"up"`; errores
  `describeFailure` verbatim en `.ds-status__error.ds-mono`; carga con `Loading`
  “Consultando estado del backend…” (`role="status"`, `aria-live="polite"`).
- **Privacidad** (`PrivacidadPage.tsx` + `.ds-reading`):
  `main.ds-reading` con `max-width: var(--measure-public)`, `margin-inline: auto`
  y `padding-block: var(--space-8)`; header y artículo en la misma columna.
- **Volver real** (`navigation.tsx` + `PrivacidadPage.tsx`):
  `navigate` guarda `appIndex` en `history.state`; `goBack(fallback = "/")` usa
  `history.back()` con índice interno > 0 y `navigate(fallback)` si se entró
  directo. `PageHeader.actions` incluye “Volver” ghost y el artículo un CTA
  `Button href="/reservar"` “Reservar turno”.
- **Documentación**: `docs/design-system.md` §5.1 con `.ds-home`, `.ds-reading` y
  `.ds-status`.

## Tests nuevos (15)

- `HomePage.test.tsx` (1): hero, `h1` “Clínica Odontológica”, entradas y estado.
- `ApiStatus.test.tsx` (4): sano, API caída, db caída y carga.
- `styles/home.test.ts` (3) y `styles/reading.test.ts` (2): layout y centrado.
- `shared/navigation.test.tsx` (+3): `appIndex`, `goBack` con historial y fallback.
- `PrivacidadPage.test.tsx` (+2): `main.ds-reading`, botón Volver y CTA con
  `ds-button`.

## Verificación real

- `npm test`: **199/199** en 31 archivos. `typecheck` y `build` en verde.
- `final/home-layout.txt`:
  - home 320/900/1280: columna 288/704/704 px, márgenes 16/98/288 simétricos,
    `scrollWidth === viewport`;
  - lectura: 288/587/587 px, márgenes 16/157/347 simétricos;
  - estado con error: `API=Con error`, `db/redis=Operativo`, error
    `API 503: {"detail":"Sin conexión con la API"}`;
  - Volver: portada→privacidad→`/`; reservar→privacidad→`/reservar`; directo→`/`;
  - auditoría a 1280: públicas 1280 px; backoffice 1048 px con rail de 232 px,
    sin overflow.
- Capturas: `final-home-{320,900,1280}.png`, `final-home-error-900.png`,
  `final-privacidad-{320,900,1280}.png`.

## Desvíos / límites

- `final-home-1280.png` y `final-privacidad-*` se regeneraron después de forzar
  que el dev server de :8080 releyera `app.css` (su caché de transformación no
  había tomado las reglas `.ds-status`); no se reinició ni bajó el servidor.
- La auditoría mide a 1280 px; a anchos mayores `.ds-content` mantiene el máximo
  de 1280 y se centra.
- Sin cambios en backend, contratos, `session.ts`, red, `localStorage`,
  `CHANGES.md`, specs ni Compose.
