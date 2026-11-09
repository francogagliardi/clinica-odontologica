# security/core-models Specification

## Purpose
Fija las entidades de identidad y trazabilidad del sistema (consultorio, usuario, rol, vínculo usuario-rol y auditoría inmutable) y el seed mínimo reproducible, para que auth/RBAC y todo el dominio posterior se apoyen en un esquema estable y auditado desde el primer registro.

Nota de alcance: el seed de este change es deliberadamente mínimo (5 roles + consultorio demo + administrador demo). Sillones, prestaciones, obra social, pacientes y turnos del seed completo de `04_modelo_de_datos.md` dependen de entidades de C-04/C-05/C-06, y los usuarios demo odontólogo/recepcionista corresponden a C-16 (seed demo completo). Los roles y el administrador son el mínimo que C-03 necesita para autenticar.

Procedencia de las decisiones: UUID v4, baja lógica, atributos de `Consultorio` (slug/nombre) y la variable `SEED_ADMIN_PASSWORD` no son reglas `RN-*` de la KB; provienen de `design.md` de este change (governance CRÍTICO, sujeto a aprobación) y de R-04/R-08. Se declaran aquí para que nadie las lea como regla de negocio inventada.

## Requirements

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

El sistema SHALL proveer un seed reproducible e idempotente que cree los cinco roles, el consultorio demo, un administrador con `SEED_ADMIN_PASSWORD`, y el elenco demo completo (odontólogo, recepcionista, asistente y auditor con `SEED_DEMO_PASSWORD`), profesional vinculado, dos sillones, prestaciones, OS Demo, pacientes y turnos ficticios. Ejecutarlo dos veces no SHALL duplicar ni reescribir credenciales.

#### Scenario: Primera ejecución del seed

- **WHEN** se ejecuta el seed con `SEED_ADMIN_PASSWORD` y `SEED_DEMO_PASSWORD` sobre una base migrada y vacía
- **THEN** quedan exactamente 5 roles, 1 consultorio demo, 5 usuarios (administrador y el elenco demo), 1 profesional vinculado al odontólogo, 2 sillones, las prestaciones demo, 1 “OS Demo”, 3 pacientes ficticios y 3 turnos futuros sin solapamiento
- **AND** las contraseñas almacenadas son hashes verificables, no texto plano

#### Scenario: Cada rol demo puede iniciar sesión

- **WHEN** se hace login con cada uno de los cinco usuarios demo
- **THEN** los cinco responden HTTP 200 con sus roles activos y el administrador conserva el rol `administrador`

#### Scenario: Seed sin contraseña configurada

- **WHEN** se ejecuta el seed sin `SEED_ADMIN_PASSWORD`
- **THEN** el proceso aborta con un mensaje que nombra la variable faltante y no deja roles, consultorio ni usuario creados a medias

#### Scenario: Seed sin contraseña del elenco demo

- **WHEN** se ejecuta el seed sin `SEED_DEMO_PASSWORD`
- **THEN** el proceso aborta nombrando la variable faltante y la transacción no deja ningún registro nuevo

#### Scenario: Segunda ejecución no duplica

- **WHEN** se ejecuta el seed dos veces seguidas sobre la misma base
- **THEN** los conteos de roles, usuarios, profesional, sillones, prestaciones, obras sociales, pacientes y turnos son idénticos a los de la primera ejecución y el proceso termina sin error

#### Scenario: Reejecución con otra contraseña no cambia credenciales

- **WHEN** se ejecuta el seed de nuevo con contraseñas distintas a las de la primera corrida
- **THEN** los hashes de los usuarios existentes se conservan intactos y los conteos no varían

#### Scenario: Dos seeds simultáneos no fallan

- **WHEN** se lanzan dos procesos de seed en paralelo sobre la misma base
- **THEN** ambos terminan sin error de unicidad y el resultado sigue siendo un registro por clave natural y exactamente un elenco demo

#### Scenario: Base parcialmente sembrada

- **WHEN** el seed corre sobre una base que ya tiene algunos roles, pacientes o prestaciones pero le faltan otros registros demo
- **THEN** completa solo los faltantes, respeta los existentes y deja los conteos esperados sin duplicar

#### Scenario: Datos ficticios, sin PII real

- **WHEN** se inspeccionan los usuarios, pacientes y turnos creados por el seed
- **THEN** todos usan dominios `.test`, nombres “Demo” y documentos/teléfonos ficticios, sin datos de personas reales

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
