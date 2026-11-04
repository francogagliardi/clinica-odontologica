# Design

## Context

C-04 entregó oferta (profesionales, sillones, prestaciones, bloqueos) y C-05 demanda (pacientes, cobertura). C-06 es el JOIN del GATE 3 y el corazón del MVP: sin `Turno` no hay reserva, agenda ni recordatorios. Governance **CRÍTICO**: un solapamiento silencioso es un defecto de negocio, no un bug cosmético.

Constraints: R-01/R-02 (Pydantic, RORO, async), R-03 (RBAC de la matriz), R-04 (SQLAlchemy + Alembic), R-05 (índices y `EXPLAIN`), R-10 (anti-solapamiento, sobreturno marcado, bloqueos efectivos), RN-TU-01/02/06/07, DD-07a–DD-07e.

## Goals / Non-Goals

**Goals:**
- Crear, leer, reprogramar y cambiar de estado turnos con duración derivada.
- Garantizar en PostgreSQL que dos turnos normales no se solapen por profesional ni sillón.
- Permitir sobreturnos solo con marca y color; bloquear el resto.
- Convertir la disponibilidad de C-04 en disponibilidad real (descuenta turnos activos).
- RBAC según la matriz, incluida la propiedad del odontólogo.

**Non-Goals:**
- Seña, cobro y comprobante (C-13/C-14): `seña_id` se agrega cuando exista la tabla.
- Lista de espera y oferta FIFO (C-10).
- Emisión de tokens públicos y enlaces de gestión (C-07): C-06 solo reserva la columna.
- Recordatorios WhatsApp (C-09).
- Agenda visual y drag & drop (C-08).
- Zona horaria por consultorio: se mantiene `UTC-3` fijo.

## Decisions

### D1 — Tabla `turnos` y migración `0006_turnos_anti_solapamiento`

Columnas: `id`, `consultorio_id`, `paciente_id`, `profesional_id`, `sillon_id`, `prestacion_id` (nullable), `inicio` y `fin` (`timestamptz`), `estado`, `origen`, `es_sobreturno`, `color_sobreturno`, `token_publico` (nullable), más `AuditMixin` (baja lógica no usada para cancelar: cancelar es un estado, no un borrado).

`down_revision = "0005_pacientes_cobertura_base"`. Se agrega `consultorios.plazo_cancelacion_horas` (default 24, CHECK 0–720) en la misma migración.

### D2 — Anti-solapamiento en la base: `btree_gist` + exclusion constraints

La garantía dura vive en PostgreSQL, no en la aplicación:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE turnos ADD CONSTRAINT ex_turnos_profesional
  EXCLUDE USING gist (
    profesional_id WITH =,
    tstzrange(inicio, fin, '[)') WITH &&
  )
  WHERE (deleted_at IS NULL AND NOT es_sobreturno
         AND estado IN ('reservado','confirmado','en_sala','atendido'));

ALTER TABLE turnos ADD CONSTRAINT ex_turnos_sillon
  EXCLUDE USING gist (
    sillon_id WITH =,
    tstzrange(inicio, fin, '[)') WITH &&
  )
  WHERE (deleted_at IS NULL AND NOT es_sobreturno
         AND estado IN ('reservado','confirmado','en_sala','atendido'));
```

- `'[)'` hace que turnos consecutivos (fin == próximo inicio) **no** colisionen.
- El predicado parcial saca del índice a cancelados/ausentes y a los sobreturnos, que son la única excepción permitida.
- Un `UPDATE` de estado o de horario pasa por la misma constraint: reprogramar es tan seguro como crear.
- Requiere `btree_gist` (contrib incluido en la imagen oficial de PostgreSQL). El usuario `clinica` del Compose es dueño de la base y puede crear la extensión. El downgrade elimina las constraints y la columna, pero **no** borra la extensión (podría estar en uso por otro esquema).

### D3 — Validación en la aplicación y traducción de errores

Antes de escribir, el servicio consulta solapamientos activos para devolver un 409 con detalle legible. La constraint es la red de seguridad ante la carrera: si dos peticiones pasan el chequeo, el `INSERT`/`UPDATE` de la segunda falla con SQLSTATE `23P01` y la API lo traduce a 409. No se usan locks de aplicación: la constraint resuelve la concurrencia sin deadlocks.

Reglas del chequeo:

- Turno nuevo **normal**: rechaza solapamiento con cualquier turno activo del profesional o del sillón, **incluido un sobreturno** (solo el sobreturno marcado puede invadir).
- Turno nuevo **sobreturno**: se permite aunque haya solapamiento, pero sigue validando bloqueos y agenda.
- Turnos `cancelado`/`ausente` no bloquean.
- Un turno no puede solaparse consigo mismo al reprogramar (`exclude_id`).

### D4 — Duración y ventana de agenda

`fin` se calcula siempre en el servidor (`extra='forbid'` rechaza un `fin` enviado por el cliente):

1. duración de la prestación si hay `prestacion_id`;
2. si no, `duracion_base_min` del profesional (RN-TU-02).

El turno debe caer en un día de `dias_atencion` y cumplir `inicio >= hora_desde` y `fin <= hora_hasta`, evaluado en `UTC-3`. Un sobreturno puede solaparse, pero no salirse del horario de atención. Los CHECK de base validan `fin > inicio` y que los enums estén en su lista; la ventana se valida en la aplicación porque depende de otra tabla.

### D5 — Sobreturno explícito

`es_sobreturno` (bool, default false) y `color_sobreturno` (hex `#RRGGBB`, nullable) con CHECK `es_sobreturno = (color_sobreturno IS NOT NULL)`. Pydantic exige color cuando la marca es true y lo prohíbe cuando es false. La respuesta siempre incluye ambos campos para que C-08 pinte la marca.

### D6 — Máquina de estados

Función pura en `app/domain/turnos.py`:

```
reservado  → confirmado | cancelado | ausente
confirmado → en_sala | cancelado | ausente
en_sala    → atendido
atendido   → (terminal)
cancelado  → (terminal)
ausente    → (terminal)
```

Repetir el estado actual es idempotente (200). Cualquier otra transición es 422 y no modifica la fila. `cancelado`/`ausente`/`atendido` no se reprograman.

### D7 — Reprogramación atómica

`PATCH /turnos/{id}/reprogramar` acepta `inicio`, `profesional_id`, `sillon_id` y `prestacion_id` opcionales; recalcula `fin`, valida agenda, bloqueos y solapamiento excluyendo el propio turno, y actualiza en una sola transacción. Si falla cualquier validación, el turno queda intacto. La constraint de exclusión cubre la carrera entre dos reprogramaciones.

### D8 — Plazo de cancelación por consultorio

`consultorios.plazo_cancelacion_horas` (int, default 24) queda disponible para RN-TU-03. C-06 no cancela por token público (eso es C-07); el valor se expone en la migración para que C-07 lo aplique sin otra alteración de esquema.

### D9 — RBAC y propiedad

- `POST /turnos`, reprogramar y cambiar estado: `administrador` y `recepcionista`.
- `odontologo`: `GET` de todos los turnos y `PATCH /estado` solo si `turno.profesional.usuario_id == current_user.id`; intentar operar el turno de otro → 403.
- `asistente` y `auditor`: solo lectura.
- Sin token → 401.

La lectura amplia se justifica porque la agenda es operativa y el odontólogo necesita ver el día completo.

### D10 — Consultas e índices

`TurnoRepository` expone:

- `list_rango(consultorio_id, desde, hasta, profesional_id?, sillon_id?, estado?)`;
- `list_solapados(profesional_id, sillon_id, inicio, fin, estados_activos, exclude_id?)`;
- `list_activos_en_rango(...)` para disponibilidad.

Índices `(profesional_id, inicio)`, `(sillon_id, inicio)`, `estado` y único parcial `token_publico WHERE token_publico IS NOT NULL`. La consulta de solapamiento usa `inicio < :fin AND fin > :inicio`, que aprovecha `(recurso_id, inicio)`.

### D11 — Disponibilidad real

`app/domain/agenda.py` suma un parámetro `turnos: Sequence[Intervalo]` (default vacío, para no romper los tests de C-04) y descarta los slots que se solapan con turnos activos además de los bloqueos. `GET /profesionales/{id}/disponibilidad` consulta los turnos del día y los pasa al dominio. Así C-07 reutiliza exactamente el mismo cálculo.

### D12 — `token_publico`

Columna `String(64)` nullable con índice único parcial sobre valores no nulos. C-06 no la emite; C-07 la completa al crear la reserva pública. La unicidad se garantiza en la base para que dos enlaces no colisionen.

## Risks / Trade-offs

- **Dependencia de `btree_gist`**: si el entorno no permite extensiones, la migración falla ruidosamente en vez de degradar la garantía. Es preferible un deploy roto a un solapamiento silencioso.
- **Sobreturnos fuera de la constraint**: PostgreSQL no puede expresar «solo si está marcado, permite solapar» sin excluir la fila; la validación de aplicación cubre el caso normal-vs-sobreturno y las pruebas de concurrencia se concentran en turnos normales.
- **Ventana de agenda validada en app**: depende de `profesionales`, no se puede expresar como CHECK de tabla; queda cubierta por tests de integración.
- **Cancelación no borra**: el turno cancelado conserva historia y libera el slot porque sale del índice de exclusión y de la disponibilidad.
- **Sin seña todavía**: `seña_id` se difiere a C-13 para no crear una FK huérfana.

## Migration Plan

1. `alembic upgrade head` aplica `0006` (extensión, columna de consultorio, tabla, índices y constraints).
2. Reversión: `alembic downgrade 0005_pacientes_cobertura_base`.
3. Verificación: migración bidireccional, paridad ORM↔esquema, constraint de exclusión probada por SQL directo y suite completa con prueba de concurrencia.
