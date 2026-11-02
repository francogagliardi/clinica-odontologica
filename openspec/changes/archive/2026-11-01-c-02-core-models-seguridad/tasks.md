# Tasks

> Cada tarea declara **cómo se verifica** y qué escenario de spec cubre. Ciclo R-09: rojo antes de verde, un slice vertical por ciclo. Los tests de integración se marcan `integration` y requieren `TEST_DATABASE_URL` (PostgreSQL real del Compose), porque constraints, índices parciales, CHECKs y triggers no existen en SQLite.
>
> Cobertura total: **32 escenarios** (15 en `security/core-models`, 17 en `platform/persistence-patterns`).

## 0. Preparación asistida (ya ejecutada, no es implementación)

- [x] 0.1 Auditar las delta specs con la skill `spec-scenario-auditor` antes de escribir tasks; corregir los huecos detectados. Evidencias: `docs/skills-mcp/evidencias/skill-audit-c-02-ronda1.md` (primera ronda) y `skill-audit-c-02-ronda3.md` (sesión nueva independiente).
- [x] 0.2 Verificar el estado real del esquema antes de diseñar con la herramienta `execute_sql` del MCP `postgres`: la base solo tiene `alembic_version` en `0001_base`. Evidencia: `docs/skills-mcp/evidencias/mcp-execute-sql.json`.

## 1. Modelos y mixin (R-01, R-04)

- [x] 1.1 **Rojo → verde**: tests unitarios (sin base) sobre la metadata: columnas de las cinco tablas, tipo UUID en las PK, ausencia de `updated_at`/`deleted_at` en auditoría, PK compuesta de `UsuarioRol` y presencia del CHECK de baja lógica. **Verifica:** `Entidades de identidad` — contrato de esquema (parte observable sin DB); `AuditMixin` — columnas y constraint declarados.
- [x] 1.2 Implementar `app/models/base.py` (`Base`, `AuditMixin` con timestamps `timezone=True` y regla de baja atómica) y `app/models/security.py` (entidades con `Mapped[...]` y hints completos). **Verifica:** 1.1 en verde.

## 2. Repositorios y UnitOfWork (R-02, R-04)

- [x] 2.1 **Rojo**: tests de integración del contrato del repositorio y del mixin: `add` dentro de un UoW abierto no es visible desde otra sesión; `add` + `get` devuelve la misma entidad; `get` inexistente → `None`; `soft_delete` setea `deleted_at` e `is_active=False`; doble `soft_delete` conserva el `deleted_at` original; `list` excluye inactivos por defecto e incluye con `include_inactive=True`; no existe operación pública de borrado físico; `created_at`/`updated_at` tienen zona horaria y `updated_at` avanza. **Verifica:** `BaseRepository` — los 5 escenarios; `AuditMixin` — Alta/modificación, Baja invisible y Baja repetida.
- [x] 2.2 **Verde**: `app/infrastructure/repositories.py` con `BaseRepository[T]` genérico sobre `AsyncSession` (sin `commit`/`rollback`). **Verifica:** 2.1 en verde.
- [x] 2.3 **Rojo → verde**: tests del `UnitOfWork`: dos escrituras confirman juntas; excepción en el bloque no deja ninguna fila (incluida una violación de unicidad que debe propagarse, no absorberse); un `UnitOfWork` posterior al rollback opera normal y no deja conexiones `idle in transaction`. **Verifica:** `UnitOfWork` — los 3 escenarios y el error de propagación de `BaseRepository`.

## 3. Migración declarativa (R-04, R-05)

- [x] 3.1 Escribir `backend/alembic/versions/0002_core_models_seguridad.py` a mano (`down_revision = "0001_base"`): tablas, FKs, PK compuesta, tres índices únicos parciales (email, slug, nombre de rol), CHECK de baja lógica, índices de auditoría, función y triggers append-only (fila + sentencia `TRUNCATE`). **Verifica:** `Migración declarativa` — upgrade en base limpia; `Entidades de identidad` — unicidad; `AuditMixin` — CHECK.
- [x] 3.2 **Rojo → verde**: test de integración que aplica `upgrade head` sobre base sin tablas y exige en `pg_indexes`/`pg_constraint` los índices únicos parciales, la PK compuesta y el CHECK; intenta `INSERT` duplicado de rol y de `slug` (espera `23505`); intenta el estado parcial de baja (espera `23514`); compara `Base.metadata` con el esquema migrado (paridad ORM↔migración) y ejecuta `upgrade head` dos veces (segunda debe ser no-op). **Verifica:** `Migración declarativa` — Upgrade en base limpia, Paridad ORM↔esquema y Upgrade repetido; `Entidades de identidad` — Valor único duplicado; `AuditMixin` — Estado parcial rechazado.
- [x] 3.3 Test de integración de fallo y reversibilidad: migrar con `DATABASE_URL` inalcanzable falla identificando la conexión y sin tablas creadas; `upgrade head → downgrade base → upgrade head` deja el esquema equivalente. **Verifica:** `Migración declarativa` — Base inalcanzable y Migración reversible.

## 4. Auditoría append-only (RN-SE-02)

- [x] 4.1 **Rojo**: tests de integración que insertan auditoría con usuario y sin usuario (`usuario_id` nulo); intentan `UPDATE`, `DELETE` y `TRUNCATE` por SQL directo (los tres fallan con `SQLSTATE P0001` y la fila queda intacta); dan de baja lógica al usuario referenciado y comprueban que la baja se completa y la auditoría sigue consultable. **Verifica:** `Auditoría append-only` — los 5 escenarios.
- [x] 4.2 **Verde**: triggers y función de 3.1 activos + `app/infrastructure/audit.py` (registro append-only, sin `update`/`delete` expuestos). **Verifica:** 4.1 en verde.

## 5. Seed idempotente (R-08, RN-SE-01)

- [x] 5.1 **Rojo**: tests de integración del seed: con `SEED_ADMIN_PASSWORD` crea exactamente 5 roles, 1 consultorio demo y 1 administrador con hash verificable; sin la variable aborta nombrando `SEED_ADMIN_PASSWORD` y no deja registros; ejecutarlo dos veces mantiene conteos; reejecutarlo con otra contraseña **no** reescribe el hash existente; dos procesos en paralelo terminan sin `23505` y con filas únicas. **Verifica:** `Seed idempotente` — los 5 escenarios.
- [x] 5.2 **Verde**: `app/seed.py` (upsert por clave natural con `ON CONFLICT`, transacción única, bcrypt directo (paquete `bcrypt`; se descartó `passlib` por incompatibilidad con bcrypt 4/5)), entrypoint `python -m app.seed` y `SEED_ADMIN_PASSWORD` documentada en `backend/.env.example` y en `knowledge-base/08_arquitectura_propuesta.md`. **Verifica:** 5.1 en verde.
- [x] 5.3 Tests de integración de reutilización de valores: email de usuario dado de baja puede reutilizarse; `nombre` de rol y `slug` de consultorio dados de baja también; asignar dos veces el mismo rol no duplica el vínculo. **Verifica:** `Entidades de identidad` — Email reutilizable, Rol/slug liberados y Asignación repetida.

## 6. Verificación integrada (R-14)

- [x] 6.1 Levantar el Compose, correr `alembic upgrade head`, ejecutar el seed y la suite completa (`unit` + `integration`), y registrar evidencia por escenario (comando + salida) en `docs/skills-mcp/evidencias/`, con una tabla de **32 filas** (15 + 17). **Verifica:** los 32 escenarios de las dos specs, uno por uno.
- [x] 6.2 Entregar la lista de pruebas manuales (endpoints no aplican: verificar esquema, seed y append-only vía `psql`/MCP) y esperar aprobación del usuario antes de archivar (R-14).
