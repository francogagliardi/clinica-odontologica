# Spec Delta

## Purpose

Fija las entidades de identidad y trazabilidad del sistema (consultorio, usuario, rol, vínculo usuario-rol y auditoría inmutable) y el seed mínimo reproducible, para que auth/RBAC y todo el dominio posterior se apoyen en un esquema estable y auditado desde el primer registro.

Nota de alcance: el seed de este change es deliberadamente mínimo (5 roles + consultorio demo + administrador demo). Sillones, prestaciones, obra social, pacientes y turnos del seed completo de `04_modelo_de_datos.md` dependen de entidades de C-04/C-05/C-06, y los usuarios demo odontólogo/recepcionista corresponden a C-16 (seed demo completo). Los roles y el administrador son el mínimo que C-03 necesita para autenticar.

Procedencia de las decisiones: UUID v4, baja lógica, atributos de `Consultorio` (slug/nombre) y la variable `SEED_ADMIN_PASSWORD` no son reglas `RN-*` de la KB; provienen de `design.md` de este change (governance CRÍTICO, sujeto a aprobación) y de R-04/R-08. Se declaran aquí para que nadie las lea como regla de negocio inventada.

## ADDED Requirements

### Requirement: Entidades de identidad con identificadores opacos

El sistema SHALL persistir `Consultorio` (slug, nombre), `Usuario` (nombre, email, hash de contraseña, activo), `Rol` (nombre) y el vínculo `UsuarioRol`, usando identificadores UUID v4 generados por la aplicación (nunca secuenciales expuestos) y relaciones consultables usuario→roles. La unicidad de `email`, `slug` y `nombre` de rol SHALL aplicar solo a filas activas (índice único parcial sobre `deleted_at IS NULL`).

#### Scenario: Alta de identidad y asignación de rol

- **WHEN** se crea un consultorio, un usuario y dos roles, y se asigna un rol al usuario dentro de una transacción
- **THEN** al releer el usuario desde la base aparecen sus roles asignados, y el tipo de `id` es `uuid` con valor de versión 4 (no un entero secuencial)

#### Scenario: Valor único duplicado rechazado por la base

- **WHEN** se intenta crear un segundo rol con un nombre existente, o un segundo consultorio con un `slug` existente, estando ambos activos
- **THEN** PostgreSQL rechaza la operación con violación de unicidad (SQLSTATE `23505`) y sigue existiendo un solo registro activo con ese valor

#### Scenario: Email reutilizable tras la baja lógica

- **WHEN** un usuario con email `demo@clinica.test` recibe baja lógica (`deleted_at` no nulo) y se registra otro usuario con ese mismo email
- **THEN** el alta es aceptada porque la unicidad aplica solo a filas activas, y el usuario dado de baja permanece consultable con su historial

#### Scenario: Asignación repetida del mismo rol

- **WHEN** se asigna dos veces el mismo rol al mismo usuario
- **THEN** la segunda asignación no duplica el vínculo, no falla y el usuario conserva exactamente un vínculo con ese rol

#### Scenario: Nombre de rol y slug liberados por la baja lógica

- **WHEN** un rol o un consultorio recibe baja lógica y se crea otro registro activo con el mismo `nombre` o `slug`
- **THEN** el alta se acepta y el registro dado de baja conserva su valor histórico, sin bloquear el valor para siempre

### Requirement: Seed idempotente y seguro por entorno

El sistema SHALL proveer un seed reproducible que cree exactamente los roles `administrador`, `odontologo`, `recepcionista`, `asistente` y `auditor`, un consultorio demo y un usuario administrador demo cuyo hash proviene de la variable de entorno `SEED_ADMIN_PASSWORD` (sin default en código), de modo que ejecutarlo dos veces no duplique, no falle y no reescriba credenciales ya existentes.

#### Scenario: Primera ejecución del seed

- **WHEN** se ejecuta el seed con `SEED_ADMIN_PASSWORD` definida sobre una base migrada y vacía
- **THEN** quedan exactamente 5 roles, 1 consultorio demo y 1 usuario administrador con rol `administrador`, y la contraseña almacenada es un hash verificable, no texto plano

#### Scenario: Seed sin contraseña configurada

- **WHEN** se ejecuta el seed sin `SEED_ADMIN_PASSWORD`
- **THEN** el proceso aborta con un mensaje que nombra la variable faltante y no deja roles, consultorio ni usuario creados a medias

#### Scenario: Segunda ejecución no duplica

- **WHEN** se ejecuta el seed dos veces seguidas sobre la misma base
- **THEN** los conteos de roles, consultorios y usuarios son idénticos a los de la primera ejecución y el proceso termina sin error

#### Scenario: Reejecución con otra contraseña no cambia credenciales

- **WHEN** se ejecuta el seed de nuevo con un `SEED_ADMIN_PASSWORD` distinto al de la primera corrida
- **THEN** el hash del administrador existente se conserva intacto (no hay cambio silencioso de credencial demo) y los conteos no varían

#### Scenario: Dos seeds simultáneos no fallan

- **WHEN** se lanzan dos procesos de seed en paralelo sobre la misma base
- **THEN** ambos terminan sin error de unicidad y el resultado sigue siendo exactamente un rol por nombre, un consultorio demo y un administrador

### Requirement: Auditoría append-only a nivel de base

El sistema SHALL registrar trazabilidad de quién hizo qué y cuándo en `RegistroAuditoria` (`usuario_id` opcional, `accion`, `entidad`, `entidad_id`, IP, dispositivo, `timestamp`), sin columnas de modificación, y SHALL impedir en PostgreSQL toda alteración o borrado del registro histórico (RN-SE-02), no solo en la capa de aplicación. `usuario_id` SHALL ser opcional porque los actores automáticos (sistema / bot de WhatsApp, `03_actores_y_roles.md`) no son personas.

#### Scenario: Registro de una acción auditable

- **WHEN** se registra una acción sobre una entidad
- **THEN** queda una fila consultable con usuario, acción, entidad, identificador afectado y timestamp, y la tabla no expone `updated_at` ni `deleted_at`

#### Scenario: Acción del sistema sin usuario

- **WHEN** se registra una acción originada por el sistema (sin persona responsable)
- **THEN** la fila se inserta con `usuario_id` nulo y es consultable igual que las demás

#### Scenario: Modificación o borrado rechazado por la base

- **WHEN** se ejecuta un `UPDATE` o un `DELETE` sobre una fila de auditoría, incluso por SQL directo
- **THEN** PostgreSQL aborta la operación con excepción (`SQLSTATE P0001`) y la fila original permanece intacta

#### Scenario: Vaciado masivo también rechazado

- **WHEN** se ejecuta `TRUNCATE registro_auditoria`
- **THEN** la operación es rechazada con excepción, porque la protección no puede depender solo de triggers de fila

#### Scenario: Baja lógica del usuario no rompe el historial

- **WHEN** se da de baja lógica al usuario que originó registros de auditoría
- **THEN** la baja se completa sin error y los registros siguen consultables con la referencia al usuario original
