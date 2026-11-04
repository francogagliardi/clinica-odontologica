# Design

## Context

C-06 ya expone turnos, reprogramación, estados, bloqueos y RBAC. C-08 es una SPA de presentación: no agrega endpoints ni reglas. Debe permitir operar la agenda sin Swagger y sin duplicar validaciones (R-07).

Constraints: R-03 (JWT en memoria), R-07 (sin lógica de negocio ni `any`), US-002/CA-1–CA-3, RN-TU-01/06/07, matriz de roles.

## Goals / Non-Goals

**Goals:**
- Login con token en memoria y logout.
- Vistas día/semana/mes, filtros por profesional/sillón y navegación.
- Colores por estado, bloqueos y sobreturnos diferenciados.
- Drag & drop que delega en la API y muestra errores.
- Permisos visuales por rol.

**Non-Goals:**
- Crear turnos desde la agenda (C-02/C-06 ya tienen API; la UI de alta puede venir después).
- Notificaciones en tiempo real o WebSockets.
- Vista mobile-first: se prioriza desktop; la grilla se adapta con scroll.
- Recalcular disponibilidad o solapamientos en el cliente.
- Persistir la sesión entre recargas.

## Decisions

### D1 — Sesión en memoria

`features/auth/session.ts` mantiene un módulo con `{token, usuario}`. `login()` llama a `POST /usuarios/login`; `logout()` limpia el objeto. No se usa `localStorage`, `sessionStorage` ni cookies. Al refrescar, el módulo arranca vacío y `/agenda` muestra el login. Esto cumple R-03 y es el trade-off aceptado en el proposal.

El usuario de la respuesta (`usuario.roles`) se usa solo para habilitar/ocultar acciones; el backend sigue validando.

### D2 — Cliente API de agenda

`features/agenda/api.ts` expone:

- `fetchProfesionales()`, `fetchSillones()`, `fetchBloqueos(desde, hasta, filtros)`.
- `fetchTurnos(desde, hasta, profesionalId?, sillonId?)`.
- `reprogramarTurno(id, inicio)` → `PATCH /turnos/{id}/reprogramar`.

Todas las llamadas autenticadas agregan `Authorization: Bearer <token>` desde la sesión. Se reutiliza `ApiError` para mostrar el `detail` del backend.

### D3 — Rangos y navegación

`features/agenda/calendar.ts` calcula:

- día: `[fecha, fecha]`;
- semana: lunes a domingo de la semana ISO;
- mes: primer día a último día del mes (≤ 31 días, dentro del límite de 62 de la API).

La navegación suma/resta 1 día, 7 días o 1 mes. La fecha se maneja como `YYYY-MM-DD` local, sin `Date` con hora para evitar corrimientos de zona; los turnos se muestran con el `inicio` ISO que devuelve la API (`-03:00`).

### D4 — Render de la grilla

- **Día**: filas por hora (08:00–20:00) y una columna; cada turno se ubica por la hora de `inicio`.
- **Semana**: siete columnas (lun–dom) × horas; misma lógica.
- **Mes**: grilla de semanas con un chip por turno (hora + paciente no disponible: se muestra matrícula/prestación) y contador.

Los turnos se identifican por `id`; no se inventan datos de paciente porque `TurnoResponse` no los trae (solo IDs). Se muestra hora, profesional (matrícula), prestación si el objeto está disponible desde el catálogo, estado y marca de sobreturno.

### D5 — Colores y marcas

Mapa fijo por estado:

| Estado | Color |
|---|---|
| reservado | azul |
| confirmado | verde |
| en_sala | ámbar |
| atendido | gris |
| cancelado | rojo atenuado |
| ausente | violeta atenuado |

Los sobreturnos llevan borde punteado, badge “Sobreturno” y el `color_sobreturno` del backend. Los bloqueos se dibujan como franja gris con el motivo.

### D6 — Drag & drop

Se usa HTML5 drag & drop nativo (sin dependencias nuevas):

- `draggable` solo si el usuario puede reprogramar ese turno.
- `onDragStart` guarda el turno; `onDrop` calcula el nuevo `inicio` combinando la fecha de la celda con la hora de la fila y el offset `-03:00`.
- Llama a `reprogramarTurno`; si responde 200, refresca; si 409/422/403, guarda el mensaje en estado y no mueve nada.
- No se calcula solapamiento local: el backend es la única autoridad (R-07).

### D7 — Permisos visuales

- `administrador` y `recepcionista`: todos los turnos arrastrables.
- `odontologo`: solo turnos cuyo `profesional_id` corresponde a un profesional con `usuario_id == usuario.id` (se obtiene de `GET /profesionales`).
- `asistente` y `auditor`: sin drag.
- Un error 403 de la API siempre se muestra.

### D8 — Estados de carga y error

Cada vista muestra “Cargando…” mientras consulta y un `role="alert"` con el mensaje de `ApiError` si falla. Una respuesta vacía muestra “Sin turnos para este rango”. No se silencian errores de red.

### D9 — Rutas

`App.tsx` reconoce `/agenda`; el resto del backoffice sigue en `/`. El login es un componente dentro de `AgendaPage` (no una ruta separada) para no perder el token al navegar.

## Risks / Trade-offs

- **Sesión perdida al refrescar**: obliga a loguearse de nuevo; es el precio de no usar almacenamiento accesible por XSS.
- **Sin datos de paciente en la grilla**: `TurnoResponse` solo trae `paciente_id`; mostrar nombre requeriría otro endpoint o exponer datos. Se muestra matrícula/prestación y se deja como mejora para C-16.
- **Drag & drop nativo**: menos pulido que una librería, pero sin dependencias y suficiente para el TP.
- **Mes con muchos turnos**: chips compactos; el detalle está en día/semana.

## Migration Plan

Sin migraciones ni cambios de backend. Se valida con `npm run typecheck`, `npm test` y smoke manual contra el stack.
