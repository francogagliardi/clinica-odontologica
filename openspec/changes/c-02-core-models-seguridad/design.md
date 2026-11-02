# Design

## Context

C-01 dejó infraestructura sin dominio: la base contiene solo `alembic_version` (verificado con la herramienta `execute_sql` del MCP `postgres`, evidencia en `docs/skills-mcp/evidencias/mcp-execute-sql.json`). C-02 introduce las primeras tablas y, con ellas, los patrones que C-03–C-16 van a reutilizar. Constraints: R-01 (snake_case + hints), R-04 (SQLAlchemy 2.x + migraciones declarativas), R-05 (índices justificados), R-06 (Redis no guarda dominio), RN-SE-02 (trazabilidad inmutable), governance **CRÍTICO** (las decisiones de este documento requieren aprobación explícita antes de escribir código).

## Goals / Non-Goals

**Goals:**

- Cinco tablas de seguridad con UUID, constraints e índices verificables.
- Patrones reutilizables (`AuditMixin`, `BaseRepository[T]`, `UnitOfWork`) con semántica de transacción explícita.
- Auditoría inmutable a nivel PostgreSQL, no solo por convención de código.
- Seed idempotente que C-03 pueda usar para el login demo.

**Non-Goals:**

- Endpoints HTTP, login, JWT o guards RBAC — son C-03. C-02 no expone rutas.
- Multitenencia por consultorio en usuarios (ver Open Questions).
- Sillones, prestaciones, obra social, pacientes y turnos del seed completo de la KB (C-04–C-06), y los usuarios demo odontólogo/recepcionista (C-16).
- Optimización de performance sin datos: los índices se justifican por regla de consulta, no por benchmark.

## Decisions

- **PK UUID v4 generado en la aplicación (`sqlalchemy.Uuid`), no enteros secuenciales.** Evita enumeración de recursos en rutas públicas futuras (tokens de C-07/C-09) y no filtra volumen de la clínica. Alternativa rechazada: `BigInteger` autoincremental (simple, pero obliga a sumar un identificador público aparte en cada entidad expuesta).
- **`Consultorio` es la raíz de tenant, con `slug` único; `Usuario` NO se vincula a consultorio en C-02.** La KB (`04_modelo_de_datos.md`) no define esa relación y `03_actores_y_roles.md` describe roles globales; inventarla ahora condicionaría C-03/C-04. Queda como pregunta abierta con dueño (C-03 si el RBAC necesita scope, C-04 si el consultorio define agenda).
- **Unicidad de `usuario.email`, `consultorio.slug` y `rol.nombre` como índices únicos parciales `WHERE deleted_at IS NULL`.** Un valor liberado por una baja lógica debe poder reutilizarse sin borrar historia (requisito de auditoría), y tratar el email distinto de los otros dos sería una inconsistencia que nadie eligió. Alternativa rechazada: `UNIQUE` plano (rompe la reutilización y bloquea nombres para siempre) o validación solo en aplicación (sujeta a carrera).
- **`UsuarioRol` con PK compuesta `(usuario_id, rol_id)` y asignación idempotente (`ON CONFLICT DO NOTHING`).** Asignar dos veces el mismo rol es una operación repetible, no un error de negocio: así lo trata cualquier reintento de UI o de seed.
- **CHECK de coherencia de baja lógica: `(deleted_at IS NULL) = is_active`.** Es un invariante de dos columnas que el ORM puede violar (por ejemplo, setear una sola) y que PostgreSQL puede garantizar sin costo; mismo criterio que RN-SE-02: la garantía vive en la base. Alternativa rechazada: validación solo en el mixin (un `UPDATE` directo deja filas incoherentes).
- **Auditoría append-only con tres capas: (1) tabla sin `updated_at`/`deleted_at`, (2) trigger de fila `BEFORE UPDATE OR DELETE`, (3) trigger de sentencia `BEFORE TRUNCATE`.** PostgreSQL no dispara triggers de fila en `TRUNCATE`, así que una protección solo de fila deja un agujero que vacía el historial en un statement. Alternativa rechazada: inmutable solo por código (un `UPDATE` por SQL directo lo rompe; RN-SE-02 exige la base como garantía).
- **`SEED_ADMIN_PASSWORD` obligatoria, sin default, y el seed no reescribe un hash existente.** Un default cómodo en código es un secreto compartido por todos los clones (R-08); y volver a sembrar no debe cambiar la credencial demo de forma silenciosa (una demo que "deja de andar" sin explicación es peor que un error explícito). El seed falla nombrando la variable y corre entero en una transacción: no deja roles creados a medias. Los upserts usan `ON CONFLICT` sobre las claves naturales (`rol.nombre`, `consultorio.slug`, `usuario.email`, `(usuario_id, rol_id)`) para que dos ejecuciones simultáneas no terminen en `23505`.
- **`UnitOfWork` dueño de la transacción; repositorios sin `commit`.** Un `commit` dentro de un repositorio fragmenta casos de uso que escriben dos entidades (usuario + vínculo de rol) y rompe el rollback conjunto.
- **Migración `0002_core_models_seguridad` escrita a mano (no autogenerate).** `autogenerate` no detecta índices parciales, CHECKs ni triggers, y el diff quedaría incompleto. Se verifica con `upgrade → downgrade base → upgrade`, con `upgrade` repetido (debe ser no-op) y con una comparación de paridad `Base.metadata` ↔ esquema migrado, que es el riesgo real de escribir la migración a mano. Alternativa rechazada: confiar en el autogenerate y corregir después (la deriva se descubre en producción).
- **Tests de integración contra PostgreSQL real, marcados `integration`, ejecutados con `TEST_DATABASE_URL`.** Constraints, índices parciales y triggers no existen en SQLite: testear con SQLite daría un verde falso. Alternativa rechazada: mocks del motor (no prueban lo que importa).

## Risks / Trade-offs

- [Riesgo] UUID encarece índices frente a enteros → Mitigación: volumen de demo y consultorio único; se acepta el costo por no filtrar identificadores. Revisar solo si aparece un cuello real (R-05: sin `EXPLAIN` no se optimiza).
- [Riesgo] El dueño de la tabla puede deshabilitar triggers → Mitigación: documentado como límite (un DBA con superusuario siempre puede; RN-SE-02 protege contra la aplicación y el SQL accidental, no contra el DBA). En producción se sumaría rol sin privilegios de owner (C-16).
- [Trade-off] `Usuario` sin `consultorio_id` obliga a un cambio de esquema cuando se defina multitenencia → Aceptado: mejor una migración futura chica que un modelo inventado ahora.
- [Riesgo] `TRUNCATE` bloqueado complica limpiar la tabla en tests → Mitigación: los tests usan una base de test descartable y borran por `downgrade`/drop, no truncando auditoría.
- [Trade-off] `401`/`404` no existen en C-02 porque no hay HTTP → Aceptado y declarado: los errores de negocio verificables en esta capa son de persistencia (unicidad, inmutabilidad, transacción).

## Migration Plan

1. `alembic upgrade head` en el Compose local crea `consultorios`, `roles`, `usuarios`, `usuario_roles`, `registro_auditoria` + índices + triggers.
2. Seed: `SEED_ADMIN_PASSWORD=... python -m app.seed` (idempotente; se puede repetir).
3. Rollback: `alembic downgrade base` (los tests de reversibilidad lo comprueban). No hay datos productivos: la demo es descartable.
4. C-03 consume `Usuario`/`Rol` para login; no requiere cambios de esquema.

## Open Questions

- ¿`Usuario` pertenece a un `Consultorio`? (Dueño: C-03/C-04; hoy no se modela.)
- ¿Los roles son globales o por consultorio? (Hoy: globales, catálogo único.)
- ¿Política de contraseña (largo, complejidad, expiración) para C-03? (Fuera de C-02; el seed solo exige valor no vacío.)
