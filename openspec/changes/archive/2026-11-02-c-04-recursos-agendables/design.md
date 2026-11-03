# Design

## Context

C-02 dejó `Consultorio`, `Usuario`, `Rol` y auditoría; C-03 cerró login, JWT, RBAC y tokens públicos. C-04 abre la rama de **oferta** del GATE 3 y debe entregar los recursos que C-06 necesita para validar anti-solapamiento y que C-11/C-12 necesitan para presupuestar.

Constraints: R-01 (snake_case, hints, Pydantic v2 `extra='forbid'`), R-02 (routers + RORO, async, `deps.py`), R-03 (RBAC en API según `03_actores_y_roles.md`), R-04 (SQLAlchemy 2.x + Alembic), R-05 (índices justificados), R-10 (bloqueos bloquean y el solapamiento nunca es silencioso), RN-TU-02/RN-TU-07/RN-TU-08, governance **MEDIO**.

## Goals / Non-Goals

**Goals:**
- Cinco tablas nuevas con constraints verificables y baja lógica coherente.
- CRUD de profesionales, sillones y prestaciones con RBAC por rol.
- Habilitación idempotente profesional ↔ sillón.
- Bloqueos por profesional **o** sillón, con efecto real en la disponibilidad base.
- Disponibilidad base calculada desde la agenda del profesional (RN-TU-02, RN-TU-07).
- Seed demo idempotente con 2 sillones y catálogo mínimo.

**Non-Goals:**
- Turnos, anti-solapamiento transaccional, sobreturnos y lista de espera (C-06).
- Agenda visual, calendario o drag & drop (C-08).
- Obras sociales, pacientes y presupuestos (C-05/C-12).
- Multisucursal real: v1 usa el consultorio demo, aunque las tablas ya llevan `consultorio_id`.
- Zona horaria configurable por consultorio: v1 usa offset fijo `UTC-3`.

## Decisions

### D1 — Tablas y nombres ASCII

Se agregan `profesionales`, `sillones`, `profesionales_sillones`, `prestaciones` y `bloqueos`. Las entidades de negocio heredan `AuditMixin` (baja lógica + timestamps) y el CHECK `(deleted_at IS NULL) = is_active`; los vínculos (`profesionales_sillones`) usan PK compuesta sin baja lógica, igual que `usuario_roles`.

Se usa `requiere_sena` / `monto_sena` (ASCII) para evitar identificadores Unicode; la correspondencia con `requiere_seña` de RN-TU-08 queda documentada en la spec y en el schema de API.

### D2 — Profesional ↔ Usuario

`profesionales.usuario_id` es **nullable** y único entre filas activas. C-04 no crea usuarios odontólogos (eso es C-16); el seed demo solo crea sillones y prestaciones. Cuando exista el usuario del profesional, se vincula y habilita el chequeo de «bloqueo propio». Un `usuario_id` nulo no puede reclamar bloqueos propios.

### D3 — `agenda_config`: columnas explícitas, esquema anidado en la API

La KB pide `agenda_config (duración base, horarios, días)`. Se implementa con columnas explícitas —`duracion_base_min`, `dias_atencion`, `hora_desde`, `hora_hasta`— para poder validar con CHECKs en PostgreSQL y testear por SQL. La API expone el objeto anidado `agenda_config` para mantener el contrato de la KB.

- `dias_atencion`: array de enteros ISO `0=lunes … 6=domingo`, no vacío, sin duplicados y con todos los valores en 0–6.
- `hora_hasta > hora_desde` y `duracion_base_min > 0` verificados por CHECK además de Pydantic.

### D4 — Disponibilidad base como función pura

`app/domain/agenda.py` calcula slots sin tocar la base:

1. Si el día de `fecha` no está en `dias_atencion`, devuelve lista vacía.
2. La duración del slot es la de la prestación si se pasa `prestacion_id`; si no, `duracion_base_min` (RN-TU-02).
3. Genera intervalos consecutivos entre `hora_desde` y `hora_hasta`; descarta el último si no entra completo.
4. Excluye los slots que se solapan con bloqueos vigentes del profesional y, si se pide un sillón, los de ese sillón (RN-TU-07).

La zona horaria de v1 es un offset fijo `UTC-3` (Argentina no aplica DST). La zona por consultorio y el descuento de turnos existentes llegan con C-06.

### D5 — Bloqueos: exactamente un recurso y rango válido

`bloqueos` exige `(profesional_id IS NOT NULL) XOR (sillon_id IS NOT NULL)` y `hasta > desde`, ambos por CHECK. Un bloqueo puede solaparse con otro (no hay daño: ambos excluyen). El borrado es lógico.

### D6 — RBAC aplicado a la matriz

- **Lectura** de profesionales, sillones, prestaciones y bloqueos: cualquier rol que opera agenda (`administrador`, `odontologo`, `recepcionista`, `asistente`, `auditor`). Sin lectura no pueden reservar ni consultar.
- **Escritura de catálogo** (profesionales, sillones, prestaciones y habilitaciones): solo `administrador` (columna «Configuración / Roles» de la matriz).
- **Escritura de bloqueos**: `administrador` y `recepcionista` (columna «Agenda/Turnos»), y `odontologo` solo cuando el bloqueo es de **su propio** profesional (`profesionales.usuario_id = current_user.id`). Un odontólogo que intenta bloquear a otro profesional o un sillón recibe 403.
- `asistente` y `auditor` solo leen.

Esta lectura amplia es deliberadamente más permisiva en lectura y más restrictiva en escritura que una interpretación literal; queda trazada a RN-SE-01 y se justifica en la spec.

### D7 — Idempotencia y unicidad parcial

- `(consultorio_id, matricula)` único solo en filas activas.
- `(consultorio_id, nombre)` único para sillones activos.
- `codigo` único para prestaciones activas.
- `usuario_id` único entre profesionales activos con usuario.
- La habilitación profesional↔sillón usa `ON CONFLICT DO NOTHING`: repetirla no falla ni duplica.
- Una baja lógica libera el valor para reutilizarlo, como en C-02.

### D8 — Validación en dos capas

Pydantic valida el borde HTTP (422 con `extra='forbid'`); PostgreSQL valida la integridad incluso por SQL directo (CHECK + índices). No se confía solo en el cliente ni solo en la app. En particular: duraciones positivas, precios no negativos, rango horario coherente, días 0–6 no vacíos, `requiere_sena=true` exige `monto_sena` **estrictamente positivo**, y `requiere_sena=false` exige `monto_sena` nulo (coherencia del dato, no regla `RN-*`).

### D9 — Seed idempotente

Se extiende `app/seed.py` con `ON CONFLICT DO NOTHING` sobre los índices parciales:

- 2 sillones (`Sillón 1`, `Sillón 2`) del consultorio demo.
- 5 prestaciones ficticias: `CONS`, `LIM`, `OBT`, `ENDO`, `EXO`, con duraciones 30/45/60/90/60 y precios ficticios; `ENDO` con `requiere_sena=true` y `monto_sena` para demostrar RN-TU-08.

Reejecutar el seed no duplica ni cambia datos existentes.

### D10 — Migración `0004_recursos_agendables`

`down_revision = "0003_tokens_un_solo_uso"`. Crea las cinco tablas, sus índices únicos parciales y de consulta (`(profesional_id, desde)`, `(sillon_id, desde)`) y los CHECKs. El downgrade elimina en orden inverso.

## Risks / Trade-offs

- **Sin turnos todavía**: la disponibilidad no descuenta turnos; C-06 la extiende. Riesgo acotado y explícito.
- **Offset fijo UTC-3**: correcto para Argentina continental sin DST; no soporta otras zonas hasta C-06.
- **Odontólogo sin usuario vinculado**: no puede crear bloqueos propios (recibe 403). Se resuelve en C-16 al crear el usuario demo.
- **Lectura amplia del catálogo**: cualquier rol autenticado ve precios y matrículas; son datos operativos, no clínicos. La escritura queda restringida.
- **Bloqueos solapados**: se permiten; no hay invariante que los prohíba porque el efecto es idempotente (excluir el rango).

## Migration Plan

1. `alembic upgrade head` aplica `0004`.
2. Reversión: `alembic downgrade 0003_tokens_un_solo_uso`.
3. Verificación: `pytest tests` contra la base descartable del Compose y paridad ORM↔esquema en `test_migration.py`.
