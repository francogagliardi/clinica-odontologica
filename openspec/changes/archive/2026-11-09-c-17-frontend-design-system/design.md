# Design

## Context

Ver `proposal.md` §Why. El estado del repo que condiciona el enfoque:

- La SPA tiene 43 archivos en `frontend/src`, 9 rutas y **ninguna hoja de estilos**: `main.tsx` no importa CSS, no hay PostCSS ni Tailwind, y `index.html` solo declara `lang="es"` y el viewport.
- Las páginas ya usan HTML semántico (`main`, `section`, `table`, `label`) y clases globales sueltas: `agenda-toolbar`, `agenda-dia`, `agenda-semana`, `agenda-mes`, `agenda-fila`, `agenda-celda`, `turno`, `bloqueo`, `reportes-filtros`. Los tests consultan esas clases y atributos: `.agenda-semana`, `.agenda-mes`, `.estado-cancelado`, `.estado-reservado`, `[data-hora="10"]`.
- Los tests también dependen de nombres accesibles y textos exactos: `getByLabelText(/Fecha/)`, `getByLabelText(/Vista/)`, `getByLabelText("Nombre")`, `getByRole("button", { name: "Crear usuario" })`, `getByText("activo")`, `role="alert"` con el código HTTP y `role="status"` con `"Turno cancelado."`. Cualquier rediseño que agregue texto a una etiqueta o cambie un nombre rompe la suite.
- La sesión vive en memoria (`features/auth/session.ts`); no hay router ni librería de estado. `App.tsx` decide por `pathname` y las páginas se testean renderizadas solas.
- El login es un `h1` "Backoffice" que cuatro tests usan como señal de "sin sesión"; la portada `/` usa `h1` "Clínica Odontológica" y el `h1` "Backoffice" queda solo en el login del backoffice.
- Stack fijo: React 18.3, TypeScript 5.6 estricto, Vite 6, Vitest 2.1, RTL 16, jsdom 30. Sin dependencias de UI, iconos, fuentes ni animación. `npm run build` ejecuta `tsc --noEmit && vite build`.
- El frontend se sirve como estáticos por nginx en Compose; no hay SSR ni variables de tema por entorno.
- Decisión del usuario (2026-11-03): no hay aprobación manual change por change; la aceptación visual final la hace el usuario sobre la página completa.

## Goals / Non-Goals

**Goals:**

- Una identidad visual concreta y defendible para un consultorio odontológico profesional, no un template de dashboard.
- Un contrato de tokens que permita cambiar la marca sin tocar componentes, con contraste AA verificable por test.
- Shells claros para backoffice y páginas públicas, con navegación por teclado y estado activo.
- Componentes presentacionales pequeños que ordenen estados de carga, vacío, error, deshabilitado y token vencido.
- Layouts terminados en las nueve rutas, responsive hasta 320 px, con impresión legible de reportes.
- Cero regresiones: mismos endpoints, mismos textos funcionales, mismos 64 tests, typecheck y build en verde.

**Non-Goals:**

- Modo oscuro, temas por usuario o `prefers-color-scheme` (se documenta como extensión futura; duplicaría la matriz de contraste).
- Nuevas pantallas o funcionalidades: historia clínica, presupuestos y caja siguen sin UI.
- Iconografía completa, ilustraciones, fotos de stock o fuentes remotas.
- Internacionalización: todo el copy queda en español rioplatense.
- Librería de componentes, de animación o de testing adicional.
- Cambios en `App.tsx` más allá de elegir shell; no se introduce router.

## Decisions

### D1 — Tokens en CSS y una hoja global por capas; sin CSS Modules ni Tailwind

**Decisión**: dos archivos, `src/styles/tokens.css` (solo custom properties en `:root`) y `src/styles/app.css` (reset acotado, base, componentes, layouts y `@media`), importados una vez desde `main.tsx`. `app.css` se organiza con `@layer reset, base, layout, components, utilities` y clases con prefijo `ds-` para lo nuevo. Las clases legacy (`agenda-*`, `turno`, `bloqueo`, `estado-*`, `reportes-filtros`) se conservan y se estilan tal cual.

**Por qué**: las clases globales ya son un contrato observable de los tests (`document.querySelector(".agenda-semana")`); CSS Modules obligaría a renombrarlas y a tocar los tests, y agregaría una capa de hash innecesaria para 9 páginas. Una hoja única con capas resuelve el orden de cascada de forma explícita, no requiere configuración de build y deja los tokens como única fuente de verdad. Tailwind se descarta por impacto de build/scan, por el ruido de utilidades en un equipo de una persona y porque no codifica decisiones de diseño: el valor está en los tokens y en pocos componentes, no en 300 clases utilitarias.

**Alternativa descartada**: CSS Modules por componente. Mejor aislamiento, pero rompe selectores existentes, duplica tokens en cada módulo y hace más difícil auditar contraste global. **Alternativa descartada**: CSS-in-JS. Añade runtime y dependencia sin beneficio en una SPA estática.

**Consecuencia**: la disciplina contra colisiones se apoya en capas + prefijo + revisión; se documenta que un estilo nuevo va en `components` o `layout`, nunca en `utilities` si es específico.

### D2 — Dirección visual: “esmalte y petróleo”, ficha clínica antes que dashboard

**Decisión**: la interfaz se lee como una ficha clínica bien impresa, no como un panel SaaS.

- **Paleta mineral fría**: papel yeso `#F4F8F6`, superficie blanca, tinta grafito-verdosa `#10282C`, un único verde petróleo clínico `#0A5C4E` como acción y foco, y tonos semánticos solo para estado (danger/warning/info). Sin degradados, sin sombras de tarjeta, sin acento terracota.
- **Tipografía**: serif editorial para titulares (`Iowan Old Style`, `Palatino Linotype`, `Palatino`, `Georgia`) y sans del sistema para interfaz; mono del sistema solo para datos máquina (hash, IDs, IP, timestamps). Sin fuentes remotas.
- **Estructura**: hairlines de 1 px, tablas densas con numerales tabulares, radios distintos por función (2 px en tablas, 4 px en controles, 10 px en superficies, pill solo en badges). La jerarquía la lleva el borde y el espaciado, no la sombra.
- **Un solo momento de audacia**: la portada pública de reserva usa el titular serif grande y el selector de horarios como “grilla de huecos”; el backoffice queda deliberadamente quieto y denso.

**Por qué**: el dominio es salud dental: precisa, tranquila, con materiales minerales (esmalte, porcelana, acero). El verde petróleo es el color real de la cruz/odontología sin caer en el mint pastel de plantilla. El serif aporta autoridad de ficha clínica y evita el look “Inter + cards + gradiente”.

**Revisión contra el brief (segunda pasada)**: la primera versión caía en el clúster genérico —fondo crema, serif de alto contraste y acento cálido— y en el kit SaaS de tarjetas idénticas con sombra suave. Se corrigió: fondo frío en vez de crema, un acento verde en vez de terracota, sombras eliminadas, radios diferenciados y titulares serif solo donde hay jerarquía real. También se evitó el eyebrow en mayúsculas, la cadena de metadatos con `·` y el `→` en botones; el único mono queda para datos que realmente son máquina.

**Alternativas descartadas**: azul corporativo + tarjetas redondeadas (genérico), near-black + acento ácido (moda), broadsheet con reglas y cero radio (no funciona para formularios y tablas operativas).

### D3 — Contrato de tokens y matriz de contraste

**Decisión**: los tokens se nombran por rol, no por valor (`--color-primary`, no `--green-700`), y todo par texto/fondo usado se declara en la matriz de contraste, que el test recalcula. Valores y ratios calculados (WCAG 2.x, luminancia relativa):

| Token | Valor | Uso | Par verificado | Ratio |
|---|---|---|---|---|
| `--color-ink` | `#10282C` | texto principal | sobre `paper` / `surface` | 14.39 / 15.42 |
| `--color-ink-soft` | `#4A6265` | texto secundario | sobre `paper` / `surface` | 6.08 / 6.51 |
| `--color-paper` | `#F4F8F6` | fondo de app | — | — |
| `--color-surface` | `#FFFFFF` | tarjetas, tablas | — | — |
| `--color-surface-sunken` | `#E7EFEC` | cabecera de tabla, riel | `ink` sobre sunken | 13.18 |
| `--color-line` | `#D3DFDA` | separadores decorativos | — | — |
| `--color-line-strong` | `#6B847C` | borde de controles | sobre `surface` / `paper` | 4.03 / 3.76 |
| `--color-primary` | `#0A5C4E` | acción, enlace, foco | texto sobre `surface`; blanco sobre primary | 7.91 / 7.91 |
| `--color-primary-hover` | `#084C40` | hover | blanco sobre hover | 9.91 |
| `--color-primary-tint` | `#E3F0EB` | selección, fondo de badge | primary sobre tint | 6.76 |
| `--color-danger` | `#9E2A22` | error | sobre `surface` / `danger-bg` | 7.48 / 6.42 |
| `--color-danger-bg` | `#FBEAE7` | fondo de error | — | — |
| `--color-warning` | `#7A4E0F` | advertencia | sobre `warning-bg` / `surface` | 6.40 / 7.18 |
| `--color-warning-bg` | `#FBF1DC` | fondo de advertencia | — | — |
| `--color-info` | `#245A73` | información | sobre `info-bg` | 6.54 |
| `--color-info-bg` | `#E8F0F4` | fondo informativo | — | — |
| `--color-focus` | `#0A5C4E` | anillo de foco | sobre `surface` | 7.91 |

El anillo de foco se dibuja con `outline: 2px solid var(--color-focus); outline-offset: 2px`, de modo que el offset deja ver el fondo y el contraste no depende del color del control.

**Por qué**: un test que recalcula ratios obliga a mantener la promesa cuando alguien cambia un token; documentar el ratio evita discusiones subjetivas. `line-strong` existe porque `#D3DFDA` solo alcanza 1.37:1 y no puede delimitar un input (WCAG 1.4.11 pide 3:1 para el límite del control).

**Alternativa descartada**: tokens con escala 50–900. Más flexibilidad de la que 9 pantallas necesitan y más pares que auditar; se usan roles semánticos y alias.

### D4 — Tipografía, escala y medida

**Decisión**: tres stacks del sistema y una escala fluida:

| Token | Valor | Uso |
|---|---|---|
| `--font-display` | `"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif` | `h1`, `h2`, portada y cifras grandes |
| `--font-ui` | `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` | cuerpo, controles, tablas |
| `--font-mono` | `ui-monospace, "SFMono-Regular", "Cascadia Mono", Consolas, "Liberation Mono", monospace` | hash, IDs, IP, timestamp, tokens |
| `--text-xs` | `0.75rem/1.4` | metadatos y ayudas |
| `--text-sm` | `0.875rem/1.45` | tablas densas, badges, navegación |
| `--text-base` | `1rem/1.55` | cuerpo y formularios |
| `--text-lg` | `1.125rem/1.5` | subtítulos |
| `--text-xl` | `1.375rem/1.3` | `h2` |
| `--text-2xl` | `1.75rem/1.2` | `h1` de backoffice |
| `--text-3xl` | `clamp(2rem, 1.4rem + 3vw, 3rem)/1.1` | `h1` público |
| `--text-display` | `clamp(2.5rem, 1.6rem + 4.4vw, 4.25rem)/1` | solo hero de `/reservar` y portada |

Reglas: medida de 68ch en párrafos públicos y 78ch en backoffice; `font-variant-numeric: tabular-nums` en tablas, totales e importes; tracking negativo solo en `--text-3xl`/`--text-display`; sin versalitas ni etiquetas en mayúsculas. El peso del display es 400 (los serif del sistema no tienen 500 real) y el énfasis de interfaz usa 600.

**Por qué**: evitar fuentes remotas mantiene el build offline y el Compose sin CDN; los stacks garantizan una serif decente en Windows/macOS/Linux. El mono se restringe a datos que el usuario reconoce como máquina, no como decoración.

**Trade-off**: la serif cambia de forma entre sistemas; se compensa con tamaños de display grandes, line-height corto y sin métricas dependientes del glifo. No se usan números serif en tablas.

### D5 — Shells: rail de backoffice, shell público y portada de doble entrada

**Decisión**: `App.tsx` clasifica la ruta y envuelve el `children` en uno de dos shells; las páginas siguen devolviendo su propio `<main>`.

```
Ruta                         Shell        Navegación
/                            público      marca + Ingresar + Reservar
/reservar                    público      marca + Reservar + Privacidad
/reservar/gestion/:token     público      marca + Privacidad
/privacidad                  público      marca + Reservar
404                          público      marca + Reservar
/agenda /reportes            backoffice   rail + sesión + Salir
/usuarios /auditoria         backoffice   rail + sesión + Salir
```

- `BackofficeShell` usa `useSession()`: con sesión muestra rail y pie con nombre/email; sin sesión muestra una barra mínima con marca y **no** renderiza enlaces protegidos (evita ofrecer navegación que solo llevaría a un login).
- `PublicShell` no consulta sesión ni imprime datos de usuario.
- Los enlaces de navegación son `<a href>` reales (no hay router); la ruta activa se calcula con `window.location.pathname` y se marca `aria-current="page"`.
- El skip link `Saltar al contenido` es el primer enfocable y apunta a un wrapper `#contenido` con `tabIndex={-1}` que envuelve al `<main>` de la página. Así no se reescribe el landmark de cada página.
- En móvil el rail se reemplaza por una barra superior con botón `Menú` (`aria-expanded`, `aria-controls`); el panel se cierra al navegar. En escritorio (≥1024 px) el botón no existe y el rail es fijo de 232 px.
- La acción `Salir` se mueve al shell y se elimina de cada página. Los tests de página no la consultan, así que no hay regresión; el comportamiento (`logout()` + volver al login) es idéntico.

**Por qué**: un solo lugar decide navegación y sesión; las páginas quedan testeables solas como hoy y no se duplica la barra. La portada `/` usa un `h1` "Clínica Odontológica" (título público) y ofrece dos puertas claras: reservar (paciente) e ingresar (equipo); el `h1` "Backoffice" queda reservado al login del backoffice.

**Alternativa descartada**: mover el shell dentro de cada página. Duplica lógica, obliga a tocar 8 páginas para el menú móvil y mezcla layout con dominio. **Alternativa descartada**: `<details>` para el menú móvil. Es nativo, pero forzar el rail abierto en escritorio con CSS sobre `details` es frágil; un botón con estado explícito es más predecible y testeable.

### D6 — Inventario de componentes presentacionales

**Decisión**: `src/shared/ui/` con estos componentes y APIs mínimas, todos sin acceso a red ni reglas de dominio:

| Componente | API | Estados / notas |
|---|---|---|
| `Button` | `variant: primary \| secondary \| ghost \| danger`, `size: sm \| md`, `href?`, `disabled?`, `type?`, `children` | Unión discriminada: con `href` renderiza `<a>` y prohíbe `disabled`; sin `href` renderiza `<button>` y usa el `disabled` nativo |
| `Input` | `label`, `hint?`, `error?`, más props de `<input>` | `useId` para `id`, `aria-describedby`; el hint/error va **fuera** del `<label>` para que el nombre accesible sea exactamente la etiqueta |
| `Select` | `label`, `hint?`, `error?`, `children` | Mismas reglas de etiqueta que `Input` |
| `Card` | `title?`, `description?`, `actions?`, `children` | Superficie con borde, sin sombra; `title` es `h2` salvo `headingLevel` explícito |
| `Table` | `label`, `children` | Envuelve `<table>` en `.ds-table-scroll` con `role="region"`, `aria-label` y `tabIndex={0}` cuando hay overflow; el marcado de columnas queda en la página |
| `Badge` | `tone: neutral \| primary \| success \| warning \| danger \| info`, `children` | Pill con texto; el color nunca es el único portador |
| `EstadoBadge` | `estado: string` | Mapea el estado crudo a un tono **solo visual**; texto visible = estado crudo; desconocido → `neutral` |
| `EmptyState` | `title`, `description`, `action?` | Sin filas falsas ni totales inventados |
| `ErrorBanner` | `message`, `title?`, `action?` | `role="alert"`, muestra el mensaje verbatim; nunca reescribe códigos |
| `Loading` | `label = "Cargando…"` | `role="status"`, `aria-live="polite"`; texto exacto por compatibilidad |
| `PageHeader` | `title`, `description?`, `actions?`, `eyebrow?` | `h1` + acciones; sin eyebrow en mayúsculas |

**Por qué**: el inventario cubre los patrones que las 9 páginas repiten y deja el marcado específico (columnas de reportes, celdas de agenda) en su lugar. `EstadoBadge` no traduce estados ni decide transiciones: el backend sigue siendo la autoridad y la etiqueta visible se mantiene cruda para no romper `getByLabelText(/Turno 09:00 reservado/)`.

**Alternativa descartada**: un `DataTable` genérico con `columns`/`rows` tipados. Termina en genéricos frágiles o en `any` (prohibido por R-07) y no cubre las tablas heterogéneas de reportes. **Alternativa descartada**: una librería headless (Radix/Ark). Aporta accesibilidad de primitivas que aquí no se usan (popover, dialog, combobox) y suma dependencias.

### D7 — Contrato de estados de UX

**Decisión**: cada consulta tiene cuatro estados explícitos y un solo patrón:

- **Carga**: `<Loading />` (texto "Cargando…", `role="status"`). No se muestra vacío mientras carga.
- **Vacío**: `<EmptyState />` con título, explicación y acción opcional (p. ej. "Sin turnos para este rango" → "Cambiar de fecha").
- **Error**: `<ErrorBanner />` con `role="alert"` y el texto de `describeFailure()` sin recortar ni traducir; el código 403/404/409/410/422 queda visible. Si la API prohíbe, no se muestran controles de escritura (comportamiento actual de usuarios/auditoría).
- **Deshabilitado**: acción con `disabled` y razón visible cuando no es obvia (p. ej. "Elegí un horario para reservar").

Casos especiales: token de gestión vencido/usado → banner 410 + indicación "Pedí un enlace nuevo en la clínica", sin botones de confirmar/cancelar; exportación `pendiente`/`generando` → estado con progreso textual y descarga deshabilitada; `sin_agenda`/`sin_cierres` → vacío explicativo, no error.

**Por qué**: hoy cada página inventa su propio `<p>Cargando…</p>` y su `<p role="alert">`; unificarlos reduce inconsistencia y hace que los tests de estados sean reutilizables. Mantener el mensaje verbatim conserva la trazabilidad con el backend y la regla de no reinterpretar.

### D8 — Accesibilidad: objetivos y verificación sin dependencias pesadas

**Decisión**: objetivo WCAG 2.2 AA con estos mínimos verificables:

- Un `h1` por ruta y orden de encabezados sin saltos; landmarks `header`, `nav`, `main`, `footer`.
- Skip link primero en el orden de tabulación; foco visible en todo control con `:focus-visible` y anillo de 2 px + offset 2 px.
- Etiquetas programáticas exactas; ayudas y errores por `aria-describedby`; `aria-invalid` en error.
- Errores en `role="alert"`, cargas en `role="status"` (sin `aria-live="assertive"`).
- Tablas con `<th scope="col">`, región desplazable con nombre accesible y foco.
- Objetivos táctiles ≥44×44 px en acciones principales; ≥24 px en controles secundarios.
- El color no es el único portador: los estados llevan texto y borde/forma además del tono.
- `:focus-visible` nunca se elimina sin reemplazo; contraste de foco 7.91:1.

**Verificación**: RTL con consultas por rol/nombre (`getByRole`, `getByLabelText`, `within`), aserciones de `aria-current`, `aria-expanded`, `aria-describedby`, `role` y orden de tabulación con `userEvent` no disponible → se usa `fireEvent`/`tab` por `document.activeElement`. Para contraste, un test puro lee `tokens.css` con `?raw` de Vite, parsea los hex y recalcula ratios; no se agrega `jest-axe` ni un navegador headless. El resto (zoom, reflujo, impresión, apariencia real) se valida en la prueba visual del usuario.

**Por qué**: jsdom no calcula estilos ni contraste, así que un test de tokens es el único borde automático real; los roles y atributos sí se pueden verificar. Sumar `jest-axe` o Playwright sería una dependencia pesada para un change presentacional y no reemplaza la revisión visual.

**Trade-off**: la ausencia de un motor de estilos en tests deja casos (solapamientos, fuentes) solo para revisión manual; se documenta en la evidencia.

### D9 — Responsive y tablas

**Decisión**: mobile-first con cuatro cortes y contenedores:

| Corte | Cambio |
|---|---|
| `≥640px` | grillas de tarjetas a 2 columnas, formularios en 2 columnas, tablas con más padding |
| `≥900px` | filtros en una fila, agenda semanal visible completa |
| `≥1024px` | rail lateral fijo de 232 px; se oculta el botón Menú |
| `≥1280px` | contenido centrado con máximo 1280 px y gutters de 2.5rem |

Reglas: `body` sin `overflow-x`; la agenda en móvil desplaza **su** grilla dentro de un contenedor con scroll, no la página; las tablas usan `Table` con `.ds-table-scroll { overflow-x:auto }`; formularios apilan labels y controles; el hero público reduce el display con `clamp`.

**Por qué**: 320 px es el mínimo real de un teléfono en Argentina y la agenda semanal es el caso más ancho del producto. Aislar el scroll evita el peor síntoma de responsive: la página entera moviéndose lateralmente.

### D10 — Movimiento sobrio y reducido

**Decisión**: solo `transition` en foco, hover de botón, apertura del menú móvil y selección de horario; 120 ms para color/borde, 180 ms para despliegue. Sin `@keyframes` decorativos, sin parallax, sin auto-scroll. `@media (prefers-reduced-motion: reduce)` fija `transition-duration: 0.01ms`, `animation-duration: 0.01ms` y `scroll-behavior: auto`, y elimina `transform` de los estados.

**Por qué**: el movimiento debe explicar un cambio, no decorar. La preferencia del sistema es un requisito de accesibilidad y es barata de cumplir.

### D11 — Impresión

**Decisión**: `@media print` global oculta `header`, `nav`, `.ds-skip`, botones, filtros y acciones; fuerza `background: #fff; color: #000`; quita sombras y radios; `table { page-break-inside: auto }`, `tr { page-break-inside: avoid }`, `thead { display: table-header-group }`. En `/reportes`, los cuatro tableros se apilan y los totales quedan en una banda superior; en `/privacidad`, el texto conserva medida y el hash se imprime en mono.

**Por qué**: el valor operativo de reportes es imprimible; una captura de pantalla con rail y botones no sirve como comprobante interno.

### D12 — Pruebas y preservación del contrato

**Decisión**: orden de trabajo por slices verticales, cada uno en rojo → verde, con la suite completa al final:

| Borde | Test |
|---|---|
| Tokens y contraste | `src/styles/tokens.test.ts`: grupos requeridos, ratios de la matriz y ausencia de colores literales en `app.css` |
| Componentes | `src/shared/ui/components.test.tsx`: roles, nombres, `aria-describedby`, `disabled`, `role=alert/status`, variantes |
| Shell backoffice | `src/shared/layout/BackofficeShell.test.tsx`: rail, `aria-current`, sin sesión sin enlaces, `Salir`, menú móvil `aria-expanded` |
| Shell público | `src/shared/layout/PublicShell.test.tsx`: marca, enlaces, ausencia de navegación protegida |
| Rutas | `src/routes.test.tsx`: un `h1` por ruta, shell correcto, 404, portada con doble entrada |
| Estados | `src/pages/*.test.tsx` ampliados: vacío, carga, 403/409/410/422 verbatim, token vencido |
| Accesibilidad estructural | `src/a11y.test.tsx`: skip link primero, `th[scope]`, regiones de tabla, un `h1`, `main` único |
| Regresión | los 64 tests existentes + `npm run typecheck` + `npm run build` |

Reglas de compatibilidad: no se cambian textos de etiquetas, `aria-label` de turnos/bloqueos, nombres de botones, clases legacy ni el texto "Cargando…"/"Turno cancelado."; no se agregan `localStorage`, cookies ni fetch nuevos. El rediseño se hace página por página con la suite completa después de cada grupo.

**Por qué**: los tests existentes son el contrato de comportamiento; el riesgo principal de un change visual es romper un selector por accidente. Un test de rutas a nivel `App` cubre lo que las páginas sueltas no ven (shell, skip link, navegación).

**Alternativa descartada**: snapshots visuales. En jsdom no hay layout y en CI no hay navegador; producirían falsos verdes.

## Risks / Trade-offs

| Riesgo | Mitigación |
|---|---|
| Una regla global pisa otra y rompe una página | Capas `@layer`, prefijo `ds-`, revisión por página, `npm run build` y prueba visual |
| El refactor cambia un nombre accesible y rompe un test | Regla explícita de no tocar etiquetas/`aria-label`; correr suite tras cada slice; tests de componentes fijan el contrato |
| La serif del sistema varía y descuadra titulares | Tamaños fluidos con `clamp`, line-height corto, sin métricas dependientes del glifo; verificación en Windows/macOS |
| jsdom no detecta problemas reales de layout o contraste | Test de ratios sobre tokens + revisión visual del usuario + documento de evidencia con capturas |
| Tablas anchas generan doble scroll | Scroll solo en `.ds-table-scroll`; `body` sin overflow-x; prueba a 320 px |
| El menú móvil duplica navegación o queda inaccesible | Un solo `nav` con el mismo DOM; botón con `aria-expanded`/`aria-controls`; test de teclado |
| El rediseño se vuelve un big bang | Slices por ruta con suite completa intermedia; el shell entra primero con páginas aún sin tocar |
| Sin modo oscuro algún usuario lo espera | Se documenta como non-goal y extensión futura; `color-scheme: light` explícito |

## Migration Plan

No hay migración de datos ni de API. El orden es incremental y reversible con un revert del commit de frontend:

1. Tokens + hoja global + import en `main.tsx` y metadatos en `index.html` (sin cambiar componentes).
2. Componentes compartidos y sus tests.
3. Shells + `App.tsx` + skip link; páginas siguen funcionando sin tocarse.
4. Página por página: portada, reserva, gestión, agenda, reportes, usuarios, auditoría, privacidad, 404.
5. Impresión, responsive fino, movimiento reducido y evidencias.
6. `npm run test`, `npm run typecheck`, `npm run build`; revisión visual final del usuario sobre el stack.

Rollback: revertir el commit de C-17 deja la SPA funcional sin estilos, sin tocar backend, base ni Compose.

## Open Questions

- **Nombre comercial para la marca**: el repo habla de "Clínica Odontológica" y el catálogo público trae `nombre` ("Consultorio Demo"). Se usa "Clínica Odontológica" como wordmark genérico y el nombre del catálogo en `/reservar`; si la cátedra pide un nombre propio, se cambia un token de texto sin tocar layout. No bloquea el plan.
- **Alcance de impresión**: se implementa hoja de impresión en todas las rutas y una banda de totales específica en reportes. Si el usuario prefiere imprimir solo reportes, se recorta el CSS sin cambiar requisitos.
