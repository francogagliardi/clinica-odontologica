# Sistema de diseño — C-17

> Fuente de verdad de la implementación: `frontend/src/styles/tokens.css` (valores)
> y `frontend/src/styles/app.css` (capas y reglas). Los tests de contrato viven en
> `frontend/src/styles/tokens.test.ts`, `frontend/src/shared/ui/components.test.tsx`,
> `frontend/src/shared/layout/*.test.tsx` y `frontend/src/routes.test.tsx`.

## 1. Dirección visual — “esmalte y petróleo”

La interfaz se lee como una ficha clínica bien impresa, no como un panel SaaS.

- **Paleta mineral fría**: papel yeso, superficie blanca, tinta grafito-verdosa y un
  único verde petróleo clínico como acción y foco. Sin degradados, sin sombras de
  tarjeta, sin acento cálido.
- **Tipografía**: serif editorial del sistema para titulares; sans del sistema para
  interfaz; mono del sistema solo para datos máquina (hash, IDs, IP, timestamps).
  No se descargan fuentes remotas.
- **Estructura**: hairlines de 1 px, tablas densas con numerales tabulares y radios
  distintos por función — 2 px en tablas, 4 px en controles, 10 px en superficies y
  pill solo en badges. La jerarquía la llevan el borde y el espaciado, no la sombra.
- **Un solo momento de audacia**: la portada pública de reserva usa titular serif
  grande y el selector de horarios como grilla de huecos; el backoffice queda
  deliberadamente quieto y denso.

Modo oscuro: **fuera de alcance** en C-17. `color-scheme: light` queda declarado en
los tokens y en `index.html` para que el sistema operativo no invierta controles.

## 2. Tokens y contraste AA

Los tokens se nombran por rol, nunca por valor. `tokens.css` declara los grupos
`color`, `tipografía`, `espaciado`, `radios`, `bordes`, `foco`, `sombra`,
`movimiento` y `layout`; `tokens.test.ts` exige que cada grupo exista y que cada
token tenga valor.

Matriz de contraste (WCAG 2.x, luminancia relativa). El test recalcula cada ratio
desde los hex de `tokens.css` y falla si el valor no coincide o si un par baja de
**4.5:1** en texto y **3:1** en interfaz.

| Token | Valor | Uso | Par verificado | Ratio | Umbral |
|---|---|---|---|---|---|
| `--color-ink` | `#10282C` | texto principal | sobre paper / surface | 14.39 / 15.42 | texto 4.5:1 |
| `--color-ink-soft` | `#4A6265` | texto secundario | sobre paper / surface | 6.08 / 6.51 | texto 4.5:1 |
| `--color-paper` | `#F4F8F6` | fondo de app | — | — | — |
| `--color-surface` | `#FFFFFF` | tarjetas, tablas | — | — | — |
| `--color-surface-sunken` | `#E7EFEC` | cabecera de tabla, riel | ink sobre sunken | 13.18 | texto 4.5:1 |
| `--color-line` | `#D3DFDA` | separadores decorativos | — | — | — |
| `--color-line-strong` | `#6B847C` | borde de controles | sobre surface / paper | 4.03 / 3.76 | interfaz 3:1 |
| `--color-primary` | `#0A5C4E` | acción, enlace, foco | texto sobre surface; surface sobre primary | 7.91 / 7.91 | texto 4.5:1 |
| `--color-primary-hover` | `#084C40` | hover | surface sobre hover | 9.91 | texto 4.5:1 |
| `--color-primary-tint` | `#E3F0EB` | selección, fondo de badge | primary sobre tint | 6.76 | texto 4.5:1 |
| `--color-danger` | `#9E2A22` | error | sobre surface / danger-bg | 7.48 / 6.42 | texto 4.5:1 |
| `--color-danger-bg` | `#FBEAE7` | fondo de error | — | — | — |
| `--color-warning` | `#7A4E0F` | advertencia | sobre warning-bg / surface | 6.40 / 7.18 | texto 4.5:1 |
| `--color-warning-bg` | `#FBF1DC` | fondo de advertencia | — | — | — |
| `--color-info` | `#245A73` | información | sobre info-bg | 6.54 | texto 4.5:1 |
| `--color-info-bg` | `#E8F0F4` | fondo informativo | — | — | — |
| `--color-focus` | `#0A5C4E` | anillo de foco | sobre surface | 7.91 | interfaz 3:1 |
| `--color-print-bg` | `#FFFFFF` | papel de impresión | — | — | — |
| `--color-print-ink` | `#000000` | tinta de impresión | — | — | — |

El anillo se dibuja con `outline: var(--focus-ring); outline-offset: var(--focus-offset)`
(2 px + 2 px), de modo que el contraste no depende del color del control.

`--color-line` es decorativo y no delimita controles: para eso existe
`--color-line-strong`, porque el separador suave no alcanza 3:1.

## 3. Escala tipográfica y medida

| Token | Valor | Uso |
|---|---|---|
| `--font-display` | `"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif` | `h1`, `h2`, portada, cifras grandes |
| `--font-ui` | `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` | cuerpo, controles, tablas |
| `--font-mono` | `ui-monospace, "SFMono-Regular", "Cascadia Mono", Consolas, "Liberation Mono", monospace` | hash, IDs, IP, timestamp, tokens |
| `--text-xs` / `--leading-xs` | `0.75rem` / `1.4` | metadatos y ayudas |
| `--text-sm` / `--leading-sm` | `0.875rem` / `1.45` | tablas densas, badges, navegación |
| `--text-base` / `--leading-base` | `1rem` / `1.55` | cuerpo y formularios |
| `--text-lg` / `--leading-lg` | `1.125rem` / `1.5` | subtítulos |
| `--text-xl` / `--leading-xl` | `1.375rem` / `1.3` | `h2` |
| `--text-2xl` / `--leading-2xl` | `1.75rem` / `1.2` | `h1` de backoffice |
| `--text-3xl` / `--leading-3xl` | `clamp(2rem, 1.4rem + 3vw, 3rem)` / `1.1` | `h1` público |
| `--text-display` / `--leading-display` | `clamp(2.5rem, 1.6rem + 4.4vw, 4.25rem)` / `1` | hero de `/reservar` y portada |
| `--weight-body` / `--weight-ui` | `400` / `600` | display vs. énfasis de interfaz |
| `--measure-public` / `--measure-backoffice` | `68ch` / `78ch` | medida de lectura |
| `--tracking-tight` / `--tracking-normal` | `-0.01em` / `0` | tracking negativo solo en display |

Reglas: `font-variant-numeric: tabular-nums` en tablas, totales e importes; sin
versalitas ni etiquetas en mayúsculas; el peso del display es 400 porque las serif
del sistema no tienen 500 real.

## 4. Espaciado, radios, bordes, foco, sombra y movimiento

| Grupo | Tokens |
|---|---|
| Espaciado | `--space-1` 4 px, `--space-2` 8 px, `--space-3` 12 px, `--space-4` 16 px, `--space-5` 20 px, `--space-6` 24 px, `--space-8` 32 px, `--space-10` 40 px, `--space-12` 48 px, `--space-16` 64 px |
| Radios | `--radius-xs` 2 px (tablas), `--radius-sm` 4 px (controles), `--radius-md` 10 px (superficies), `--radius-pill` 999 px (badges) |
| Bordes | `--border-width` 1 px, `--border-hairline` (separador suave), `--border-control` (límite de control con `line-strong`) |
| Foco | `--focus-width` 2 px, `--focus-offset` 2 px, `--focus-ring` |
| Sombra | `--shadow-surface` = `none` (la elevación se expresa con borde) |
| Movimiento | `--motion-duration-fast` 120 ms, `--motion-duration-slow` 180 ms, `--motion-ease`, `--motion-reduced` 0.01 ms |
| Layout | `--rail-width` 232 px, `--shell-max` 1280 px, `--gutter`, `--touch-target` 44 px, `--tap-target` 24 px |

## 5. Shells de navegación

`App.tsx` clasifica la ruta y elige shell; las páginas siguen devolviendo su propio
`<main>`. No hay router: los enlaces son `<a href>` reales.

| Ruta | Shell | Navegación |
|---|---|---|
| `/` | público | marca + Reservar + Ingresar + Privacidad |
| `/reservar` | público | marca + Reservar + Privacidad |
| `/reservar/gestion/:token` | público | marca + Reservar + Privacidad |
| `/privacidad` | público | marca + Reservar + Privacidad |
| 404 | público | marca + Reservar + Privacidad |
| `/agenda`, `/reportes` | backoffice | rail + sesión + Salir |
| `/usuarios`, `/auditoria` | backoffice | rail + sesión + Salir |

- **`PublicShell`** (`children`, `pathname?`) imprime marca y enlaces públicos;
  nunca lee la sesión ni muestra datos de usuario.
- **`BackofficeShell`** (`children`, `pathname?`) usa `useSession()`: con sesión
  muestra el rail (Agenda, Reportes, Usuarios, Auditoría) con `aria-current="page"`,
  la identidad de la sesión y `Salir` (que llama a `logout()`); sin sesión muestra
  solo la barra de marca y ningún enlace protegido.
- **`SkipLink`** + **`ContentWrapper`**: el skip link `Saltar al contenido` es el
  primer enfocable y apunta a `#contenido`, un wrapper `tabIndex={-1}` alrededor del
  `<main>` de la página. Así cada página conserva su landmark.
- **Sin sesión** el shell agrega `.ds-shell--signed-out`: el contenido ocupa todo el
  ancho (no reserva la columna del rail) y el login se centra en un panel de 440 px
  (`.ds-auth` / `.ds-auth__panel`).
- En móvil el rail se ofrece con el botón `Menú` (`aria-expanded`, `aria-controls`);
  el panel se cierra al navegar. En escritorio (≥1024 px) el botón no se muestra y
  el rail fijo mide `--rail-width`.

## 5.1 Patrones de página

| Patrón | Clase | Regla |
|---|---|---|
| Portada | `.ds-home` + `.ds-home__inner` | Aire vertical `padding-block: clamp(var(--space-8), 6vw, var(--space-12))`; columna centrada de 44 rem (`margin-inline: auto`) con `text-align: center`; eyebrow “Turnos online”, `h1` “Clínica Odontológica”, descripción, acciones en columna y fila desde 640 px; estado del sistema debajo |
| Lectura larga | `.ds-reading` | Columna de `max-width: var(--measure-public)` (68ch) centrada con `margin-inline: auto` y `padding-block: var(--space-8)`; header y artículo comparten la columna; el hash usa `overflow-wrap: anywhere` |
| Estado del sistema | `.ds-status` | Tres filas con nombre (`API`, `Base de datos`, `Redis`) y `Badge` success/danger; el texto visible “Operativo”/“Con error” acompaña siempre al color; los errores van en `.ds-status__error` con `--font-mono` y el mensaje verbatim de la API |

Todas las páginas siguen dentro de `.ds-content` (`max-width: var(--shell-max)` +
`margin-inline: auto`), que aporta el gutter y centra el contenido en pantallas
anchas. La autenticación agrega `.ds-auth`/`.ds-auth__panel` y el shell
`.ds-shell--signed-out` descriptos en §5.

## 6. Inventario de componentes (`frontend/src/shared/ui`)

Todos son presentacionales: reciben datos y callbacks; no validan reglas de negocio
ni llaman a la API. Los estilos usan únicamente tokens.

### `Button`

API: `variant?: "primary" | "secondary" | "ghost" | "danger"`, `size?: "sm" | "md"`,
`href?`, `disabled?`, `type?`, `children`, `onClick?`, `aria-label?`,
`aria-expanded?`, `aria-controls?`, `aria-pressed?`, `aria-current?`.

Estados: default, hover, `:focus-visible`, `disabled` nativo. La unión discriminada
hace que con `href` renderice `<a>` (y prohíba `disabled`) y sin `href` renderice
`<button type="button">` (o el `type` pedido).

```tsx
<Button href="/reservar">Reservar turno</Button>
<Button variant="secondary" size="sm" disabled onClick={() => undefined}>
  Sin horario
</Button>
```

### `Input`

API: `label`, `hint?`, `error?`, `id?` + props nativas de `<input>`.
Estados: normal, con ayuda, con error (`aria-invalid="true"`).

`useId` genera el `id`; la ayuda y el error van **fuera** del `<label>` y se asocian
por `aria-describedby`, para que el nombre accesible sea exactamente la etiqueta.
Acepta `aria-invalid`/`aria-describedby` del consumidor y los combina con la ayuda
y el error propios (lo usa el login para apuntar al `ErrorBanner`).

```tsx
<Input label="Email" type="email" hint="Usá tu correo institucional" />
<Input label="DNI" error="DNI inválido" />
```

### `Select`

API: `label`, `hint?`, `error?`, `id?`, `children` + props nativas de `<select>`.
Mismas reglas de etiqueta y descripción que `Input`.

```tsx
<Select label="Vista" defaultValue="dia">
  <option value="dia">Día</option>
  <option value="semana">Semana</option>
</Select>
```

### `Loading`

API: `label?` (default exacto `Cargando…`), `className?`.
Estado: carga. Renderiza `role="status"` con `aria-live="polite"`.

```tsx
<Loading />
```

### `ErrorBanner`

API: `message`, `title?`, `action?`, `className?`.
Estado: error. Renderiza `role="alert"` y el mensaje **verbatim** (sin traducir
códigos 403/404/409/410/422).

```tsx
<ErrorBanner title="No se pudo reservar" message="409 — el horario ya está ocupado" />
```

### `Card`

API: `title?`, `description?`, `actions?`, `headingLevel?: 2 | 3 | 4` (default 2),
`children?`, `className?`.
Estado: superficie con borde y sin sombra. Con `title` expone una `region` con nombre
accesible mediante `aria-labelledby`.

```tsx
<Card title="Resumen del turno" actions={<Button size="sm">Reprogramar</Button>}>
  <p>Lunes 09:00 · Sillón 1</p>
</Card>
```

### `Table`

API: `label`, `children`, `className?`.
Estado: región desplazable `role="region"` con `aria-label`, `tabIndex={0}` y scroll
propio; el `<table>` interior conserva el marcado de columnas de la página.

```tsx
<Table label="Usuarios">
  <thead>
    <tr>
      <th scope="col">Nombre</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Ana Pérez</td>
    </tr>
  </tbody>
</Table>
```

### `Badge`

API: `tone?: "neutral" | "primary" | "success" | "warning" | "danger" | "info"`
(default `neutral`), `children`, `className?`.
Estados: un tono por significado. El color nunca es el único portador: el texto
siempre está visible.

```tsx
<Badge tone="warning">Pendiente</Badge>
```

### `EstadoBadge`

API: `estado` (string crudo del backend).
Mapea el estado a un tono **solo visual** y muestra el texto sin traducir:
`reservado → info`, `confirmado → primary`, `en_sala → warning`,
`atendido → success`, `cancelado → danger`, `ausente → warning`,
desconocido → `neutral`.

```tsx
<EstadoBadge estado="cancelado" />
```

### `EmptyState`

API: `title`, `description`, `action?`, `className?`.
Estado: vacío, con título `h2`, explicación y acción opcional; sin filas ni totales
inventados.

```tsx
<EmptyState
  title="Sin turnos para este rango"
  description="Probá con otra fecha o profesional."
  action={<Button size="sm">Cambiar de fecha</Button>}
/>
```

### `PageHeader`

API: `title`, `description?`, `actions?`, `eyebrow?`, `className?`.
Estado: encabezado de página con exactamente un `h1`; `eyebrow` es texto pequeño,
nunca un rótulo en mayúsculas.

```tsx
<PageHeader title="Agenda" description="Turnos del día" actions={<Button>Nuevo turno</Button>} />
```

### `SkipLink` y `ContentWrapper`

API: `SkipLink` sin props; `ContentWrapper` recibe `children`.
`SkipLink` es el primer elemento enfocable del shell; `ContentWrapper` renderiza
`<div id="contenido" tabIndex={-1}>` alrededor del `<main>` de la página.

## 7. Contrato de estados de UX

Toda consulta presenta los mismos cuatro estados:

| Estado | Componente | Semántica |
|---|---|---|
| Carga | `Loading` | `role="status"`, `Cargando…` exacto, sin mostrar vacío antes de tiempo |
| Vacío | `EmptyState` | título + explicación + acción opcional |
| Error | `ErrorBanner` | `role="alert"`, mensaje de la API verbatim con su código |
| Deshabilitado | `Button disabled` | `disabled` nativo y razón visible cuando no es obvia |

Casos especiales: token vencido o usado (410) → banner verbatim + indicación de pedir
un enlace nuevo, sin botones de confirmar/cancelar; exportación
`pendiente`/`generando` → progreso textual y descarga deshabilitada; `sin_agenda` /
`sin_cierres` → vacío explicativo, no error. La UI no agrega validaciones ni
mensajes propios (R-02/R-07).

## 8. Breakpoints y layout

Mobile-first, sin scroll horizontal de página desde 320 px:

| Corte | Cambio |
|---|---|
| `≥640px` | grillas de tarjetas a 2 columnas; entrada de portada en 2 columnas |
| `≥900px` | filtros en una fila; agenda semanal completa |
| `≥1024px` | rail fijo de `--rail-width`; se oculta el botón `Menú` |
| `≥1280px` | contenido centrado con máximo `--shell-max` y gutters de `--gutter` |

Reglas: `body` sin `overflow-x`; la agenda desplaza **su** grilla dentro de un
contenedor con scroll; las tablas usan `Table` (`.ds-table-scroll` con
`overflow-x: auto`); los formularios apilan etiqueta y control; el hero público
reduce el display con `clamp`.

## 9. Accesibilidad (WCAG 2.2 AA)

- Un `h1` por ruta, sin saltos de nivel; landmarks `header`, `nav` y `main` (y
  `footer` donde exista).
- Skip link primero en el orden de tabulación.
- `:focus-visible` con anillo de 2 px + offset 2 px; nunca se elimina sin reemplazo.
- Etiquetas programáticas exactas; ayuda y error por `aria-describedby`;
  `aria-invalid` en error.
- Errores en `role="alert"`; cargas en `role="status"` (nunca `assertive`).
- Tablas con `<th scope="col">`, región desplazable con nombre accesible y foco.
- Objetivos táctiles ≥44×44 px en acciones principales (`--touch-target`) y ≥24 px
  en controles secundarios (`--tap-target`).
- El color no es el único portador: los estados llevan texto y borde/forma.
- Contraste verificado por test sobre los tokens de la §2.

## 10. Movimiento

Solo transiciones que explican un cambio de estado: foco, hover de botón, apertura
del menú móvil y selección de horario. 120 ms para color/borde y 180 ms para
despliegue (`--motion-duration-fast`, `--motion-duration-slow`). Sin `@keyframes`
decorativos, sin parallax y sin animaciones en bucle.

Implementación: `prefers-reduced-motion: reduce` fija `animation-duration` y
`transition-duration` en `--motion-reduced` (0.01 ms), `animation-iteration-count: 1`
y `scroll-behavior: auto` sobre `*`, `*::before` y `*::after`; el botón `Menú` usa
la duración de 180 ms. `styles/motion.test.ts` falla si aparece un `@keyframes`,
una animación `infinite` o si la hoja deja de respetar la preferencia.

## 11. Impresión

La hoja de impresión (C-17 §6) usa `--color-print-bg` y `--color-print-ink` para
forzar negro sobre blanco. `@media print` oculta `header`, `nav`, `.ds-skip`,
botones, filtros y acciones; quita sombras y radios; evita cortar filas
(`tr { page-break-inside: avoid }`), repite `thead` y apila los tableros de
reportes. En `/privacidad` el texto conserva la medida y el hash se imprime en
`--font-mono`. Las rutas públicas se imprimen sin menú ni acciones.

## 12. Capas de la hoja global

`app.css` declara `@layer reset, base, layout, components, utilities`:

- **reset**: box-sizing, márgenes, listas y controles acotados.
- **base**: tipografía, enlaces, foco, selección y tablas base.
- **layout**: shells, skip link, rail, barra pública y contenedores.
- **components**: botones, campos, tarjetas, tablas, badges, vacío, encabezado,
  carga, error y las clases legacy observables (`agenda-*`, `turno`, `bloqueo`,
  `estado-*`, `reportes-filtros`).
- **utilities**: `ds-mono`, `ds-visually-hidden`.

Un estilo nuevo va en `components` o `layout`; `utilities` solo aloja helpers
genéricos. `tokens.test.ts` falla si aparece un color literal fuera de
`tokens.css`; la única excepción es el `color_sobreturno` que la API entrega y se
aplica inline en `features/agenda/components.tsx`.
