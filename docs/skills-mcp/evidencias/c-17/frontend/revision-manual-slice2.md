# C-17 slice 2 — revisión visual (agenda y reportes)

> Evidencia de las tareas 5.3 y 6.3. Capturas generadas con Chromium headless
> (Playwright) contra `npm run dev` (`http://127.0.0.1:5173`). Las respuestas de la
> API se sustituyeron por fixtures determinísticos en el navegador porque el stack
> local levantado en `:8000` no tenía el seed demo disponible (login 401); esto es
> evidencia de **layout y estados**, no una prueba funcional E2E. La suite de tests
> cubre el comportamiento con mocks equivalentes.

## Capturas

| Archivo | Ruta | Ancho | Qué muestra |
|---|---|---|---|
| `portada-320.png` | `/` | 320 px | Portada pública con marca y dos entradas |
| `reserva-320.png` | `/reservar` | 320 px | Filtros apilados, grilla de huecos y formulario en una columna |
| `reserva-900.png` | `/reservar` | 900 px | Filtros en fila y formulario a dos columnas |
| `agenda-320.png` | `/agenda` | 320 px | Barra superior con `Menú`; toolbar envuelto; grilla de día completa |
| `agenda-900.png` | `/agenda` | 900 px | Toolbar en una fila; estados con badge; sobreturno y bloqueo visibles |
| `agenda-semana-320.png` | `/agenda` (Semana) | 320 px | Grilla semanal con scroll interno (745 px dentro de 288 px) |
| `agenda-semana-900.png` | `/agenda` (Semana) | 900 px | Grilla semanal completa |
| `agenda-mes-320.png` | `/agenda` (Mes) | 320 px | Grilla mensual con scroll interno (673 px dentro de 288 px) |
| `agenda-mes-900.png` | `/agenda` (Mes) | 900 px | Grilla mensual completa |
| `reportes-900.png` | `/reportes` | 900 px | Cuatro tableros, totales, tablas y exportación |
| `reportes-impresion-900.png` | `/reportes` (media print) | 900 px | Sin rail/topbar/filtros/botones/exportación; negro sobre blanco; `thead` repetido |
| `usuarios-900.png` | `/usuarios` | 900 px | Alta en Card, tabla densa con badges y acciones agrupadas |
| `auditoria-900.png` | `/auditoria` | 900 px | Filtros en grilla, total y tabla paginada sin escritura |
| `privacidad-900.png` | `/privacidad` | 900 px | Lectura larga con versión/fecha y hash monoespaciado |

## Verificaciones medidas

- **Sin scroll horizontal de página** a 320 px y 900 px en agenda, reportes,
  reserva, usuarios y auditoría: `document.documentElement.scrollWidth` igual al
  ancho del viewport.
- **Scroll interno de la agenda**: a 320 px la semana mide 745 px de contenido
  dentro de un contenedor de 288 px; el mes, 673 px dentro de 288 px. La página no
  se desplaza.
- **Menú móvil**: a 900 px (por debajo de 1024 px) se ve el botón `Menú`; a 1024 px
  o más se muestra el rail fijo de 232 px y el botón desaparece.
- **Toolbar de agenda**: a 900 px los filtros quedan en una sola fila; a 320 px se
  apilan sin desbordar.
- **Estados de turno**: `reservado` (info), `confirmado` (primary), `cancelado`
  (danger), sobreturno como badge warning con borde punteado y bloqueo con trama
  propia; los textos crudos de estado se conservan.
- **Impresión**: con `emulateMedia({ media: "print" })` desaparecen barra superior,
  rail, filtros, acciones y panel de exportación; los totales y tablas se imprimen
  en negro sobre blanco y el `thead` queda como `table-header-group`.

## Pendiente para la aceptación final

- Repetir estas capturas sobre `docker compose up -d --build` con el seed demo real
  y sesión de cada rol (admin, recepción, odontólogo, asistente, auditor).
- Revisar el foco visible real con teclado en los destinos de arrastre y el
  comportamiento táctil del menú móvil.
