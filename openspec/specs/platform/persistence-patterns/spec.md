# platform/persistence-patterns Specification

## Purpose
Fija los patrones de persistencia que todo el dominio posterior reutiliza: auditoría de columnas con baja lógica, repositorio genérico sin commits propios, unidad de trabajo transaccional y migraciones declarativas verificables, para que C-03 en adelante no reinvente el acceso a datos ni mezcle reglas con sesiones.

## Requirements

### Requirement: AuditMixin con baja lógica

Toda entidad de negocio SHALL heredar `AuditMixin` con `is_active`, `created_at`, `updated_at` y `deleted_at` (timestamps con zona horaria UTC), y la baja SHALL ser lógica: `deleted_at` no nulo e `is_active` falso en la misma operación, sin borrado físico. PostgreSQL SHALL rechazar el estado parcial (uno de los dos campos incoherente con el otro).

#### Scenario: Alta y modificación actualizan auditoría de columnas

- **WHEN** se crea una entidad con el mixin y luego se modifica
- **THEN** en el alta `created_at` y `updated_at` quedan seteados (con zona horaria) y `deleted_at` nulo, y tras la modificación `updated_at` es estrictamente posterior al del alta

#### Scenario: Registro dado de baja no aparece en consultas normales

- **WHEN** una entidad recibe baja lógica y se consulta por el camino habitual (sin pedir inactivos)
- **THEN** la entidad no se devuelve, aunque la fila siga existiendo en la base

#### Scenario: Baja lógica repetida es idempotente

- **WHEN** se aplica baja lógica dos veces sobre la misma entidad
- **THEN** la segunda operación no falla y conserva el `deleted_at` original, sin duplicar estados ni efectos

#### Scenario: Estado parcial de baja rechazado por la base

- **WHEN** se intenta persistir `is_active = false` con `deleted_at` nulo (o `is_active = true` con `deleted_at` no nulo), incluso por SQL directo
- **THEN** PostgreSQL rechaza la fila con violación de CHECK (`SQLSTATE 23514`), igual que la inmutabilidad de auditoría se garantiza en la base y no solo en el código

### Requirement: BaseRepository genérico sin transacciones propias

El sistema SHALL exponer un `BaseRepository[T]` tipado con operaciones `add`, `get`, `list` y `soft_delete`, que no haga `commit` ni `rollback` (la transacción pertenece al `UnitOfWork`) y que no ofrezca borrado físico.

#### Scenario: Alta y lectura por identificador

- **WHEN** se agrega una entidad por el repositorio dentro de una unidad de trabajo aún abierta y se consulta desde otra sesión
- **THEN** la fila todavía no es visible para la otra sesión (el repositorio no commitea), y al releerla por su identificador en la misma unidad de trabajo se obtiene la misma entidad con sus campos persistidos

#### Scenario: Violación de integridad se propaga y no se absorbe

- **WHEN** un `add` viola una restricción de unicidad y el bloque termina por la excepción
- **THEN** el repositorio no captura ni silencia el error, la excepción de integridad llega al llamador y el `UnitOfWork` revierte la transacción sin dejar filas a medias

#### Scenario: Identificador inexistente no explota en el repositorio

- **WHEN** se consulta por un identificador que no existe
- **THEN** el repositorio devuelve `None` sin excepción, y la decisión de responder `404` queda explícitamente fuera de esta capa (la toma la API en C-03)

#### Scenario: Borrado físico no disponible en la interfaz pública

- **WHEN** un llamador busca una operación de borrado físico en el repositorio
- **THEN** no existe ninguna operación pública que lo haga (la única baja es `soft_delete`), de modo que el borrado físico no puede ocurrir por accidente desde el código de aplicación

#### Scenario: Listado excluye inactivos por defecto

- **WHEN** se listan entidades con y sin baja lógica, primero por defecto y luego pidiendo incluir inactivas
- **THEN** el listado por defecto omite las dadas de baja y el listado explícito las incluye

### Requirement: UnitOfWork con transacción por caso de uso

El sistema SHALL exponer un `UnitOfWork` async que agrupe repositorios sobre una única sesión, confirme la transacción al salir sin excepción y haga rollback ante cualquier excepción, dejando la sesión reutilizable y sin conexiones colgadas.

#### Scenario: Commit conjunto de dos escrituras

- **WHEN** se realizan dos escrituras dentro del mismo `UnitOfWork` y el bloque termina sin excepción
- **THEN** ambas quedan persistidas y son visibles desde una sesión nueva

#### Scenario: Excepción revierte todo el bloque

- **WHEN** una escritura se ejecuta y luego el bloque lanza una excepción
- **THEN** ninguna de las escrituras del bloque persiste en la base

#### Scenario: Sesión utilizable tras rollback

- **WHEN** un `UnitOfWork` termina por excepción y se abre otro inmediatamente después
- **THEN** el nuevo bloque puede leer y escribir normalmente, y no quedan conexiones en estado `idle in transaction` atribuibles a la unidad de trabajo anterior

### Requirement: Migración declarativa reversible con índices justificados

Todo cambio de esquema SHALL llegar como migración Alembic versionada (nunca `create_all` ni DDL ad-hoc) con `down_revision` explícita, y el esquema SHALL declarar los índices y constraints que las reglas exigen: índices únicos parciales sobre filas activas (`email`, `slug`, nombre de rol), PK compuesta en `UsuarioRol`, CHECK de coherencia de baja lógica, e índices de consulta por usuario/fecha y por entidad afectada en auditoría.

#### Scenario: Upgrade en base limpia crea esquema e índices

- **WHEN** se ejecuta `alembic upgrade head` sobre una base sin tablas de dominio
- **THEN** existen las cinco tablas, los índices y constraints declarados, verificables en `pg_indexes` y `pg_constraint`

#### Scenario: Base inalcanzable falla sin esquema parcial

- **WHEN** se ejecuta la migración con la base inalcanzable
- **THEN** el comando falla con un error que identifica la conexión y no deja tablas ni índices a medio crear

#### Scenario: Migración reversible

- **WHEN** se ejecuta `upgrade head` y luego `downgrade base` y nuevamente `upgrade head` sobre la misma base
- **THEN** el esquema final es equivalente al inicial y ninguna migración queda en estado inconsistente

#### Scenario: Paridad entre el ORM y el esquema migrado

- **WHEN** se compara la metadata de SQLAlchemy con el esquema resultante de `upgrade head`
- **THEN** tablas, columnas, tipos, claves foráneas e índices coinciden, sin deriva entre el modelo y la migración

#### Scenario: Upgrade repetido es no-op

- **WHEN** se ejecuta `alembic upgrade head` dos veces seguidas
- **THEN** la segunda ejecución no falla y no modifica el esquema ni la versión registrada
