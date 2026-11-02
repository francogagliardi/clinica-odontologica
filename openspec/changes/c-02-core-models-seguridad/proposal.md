# Proposal

## Why

C-01 dejó la infraestructura y una sola tabla (`alembic_version`): no existe ninguna entidad de dominio. Sin usuarios, roles, consultorio ni auditoría no hay dónde apoyar el login/RBAC de C-03, ni pacientes, turnos o caja de los changes siguientes. C-02 es la cabeza del camino crítico después de C-01 y no depende de funcionalidad todavía inexistente: puede prepararse y verificarse contra el Compose existente.

Además, la trazabilidad append-only (RN-SE-02) es un requisito de seguridad que, si se agrega tarde, obliga a reescribir escrituras de toda la aplicación. Se resuelve en el cimiento, no después.

## What Changes

- Agrega modelos SQLAlchemy 2.x async de seguridad: `Consultorio`, `Usuario`, `Rol`, `UsuarioRol` y `RegistroAuditoria` (inmutable).
- Agrega `AuditMixin` (`is_active`, `created_at`, `updated_at`, `deleted_at`) con baja lógica, aplicado a las entidades de negocio.
- Agrega `BaseRepository[T]` genérico y `UnitOfWork` async (una transacción por caso de uso: commit al salir bien, rollback ante excepción).
- Agrega la migración `0002_core_models_seguridad` (down_revision `0001_base`) con tablas, claves foráneas, índices y la protección append-only de auditoría.
- Agrega un seed idempotente: 5 roles (administrador, odontologo, recepcionista, asistente, auditor), consultorio demo y usuario administrador demo con contraseña tomada de entorno (sin default inseguro).
- Agrega tests unitarios y de integración contra PostgreSQL real (Compose): mixin, seed idempotente, auditoría rechaza UPDATE/DELETE/TRUNCATE y unicidad con baja lógica.

## Capabilities

### New Capabilities

- `security/core-models`: entidades de identidad (consultorio, usuario, rol, vínculo usuario-rol), seed mínimo idempotente y auditoría inmutable append-only (RN-SE-02).
- `platform/persistence-patterns`: patrones de persistencia reutilizables (AuditMixin con baja lógica, `BaseRepository[T]`, `UnitOfWork` transaccional y migraciones declarativas con índices).

### Modified Capabilities

- Ninguna: C-01 no definió comportamiento de dominio; solo baseline de plataforma. No hay requisitos existentes que cambien.

## Impact

- Archivos nuevos en `backend/app/models/`, `backend/app/infrastructure/`, `backend/alembic/versions/0002_*.py`, `backend/app/seed*.py` y `backend/tests/`; migración aditiva sobre el esquema vacío.
- Sin endpoints HTTP nuevos: el login y los guards RBAC son C-03. Este change entrega el modelo y los patrones, no la superficie de API.
- Desbloquea C-03 (auth/JWT), C-04 (consultorio/profesional/sillón) y toda la rama clínica; la auditoría append-only queda disponible para cada escritura posterior.
- Riesgos: contraseña demo reutilizada en una demo pública (mitigado: `SEED_ADMIN_PASSWORD` obligatoria por entorno, nunca en el repo); deriva entre ORM y migración (mitigado: la migración se escribe a mano y se verifica con `alembic upgrade/downgrade` en base limpia); rendimiento prematuro (no hay tablas calientes aún: los índices se justifican por regla, no por benchmark — R-05).
