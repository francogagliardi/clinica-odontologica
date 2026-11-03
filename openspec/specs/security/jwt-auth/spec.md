# security/jwt-auth Specification

## Purpose
Provee autenticación de usuarios de backoffice mediante credenciales y emisión de access tokens JWT firmados con HS256, con auditoría inmutable de cada intento (RN-SE-02) y mitigación de fuerza bruta por limitación de tasa.

## Requirements

### Requirement: Autenticación de credenciales y emisión de access token

El sistema SHALL autenticar usuarios por email y contraseña en `POST /usuarios/login`, comparando bcrypt contra PostgreSQL y emitiendo un access token JWT de vida corta que identifica al usuario sin transportar roles.

**Trazabilidad**: DD-07b (`09_decisiones_y_supuestos.md`), RN-SE-01 (`05_reglas_de_negocio.md`), `08_arquitectura_propuesta.md` §Flujo de autenticación JWT.

#### Scenario: Inicio de sesión exitoso
- **WHEN** un usuario activo envía `POST /usuarios/login` con email y contraseña correctos
- **THEN** el sistema responde HTTP 200 con `access_token`, `token_type` "bearer", `expires_in` y un objeto `usuario` con id, nombre, email y roles activos
- **AND** el JWT contiene solo `sub`, `typ` = "access", `iat` y `exp` (sin `email` ni `roles`)

#### Scenario: Credenciales inválidas sin enumeración de cuentas
- **WHEN** un cliente envía `POST /usuarios/login` con contraseña incorrecta o con un email que no existe
- **THEN** el sistema responde HTTP 401 con el mismo cuerpo en ambos casos, sin emitir token
- **AND** el tiempo de respuesta del email inexistente incluye una comparación bcrypt ficticia, de modo que no revela si la cuenta existe

#### Scenario: Usuario dado de baja intenta autenticarse
- **WHEN** un usuario con baja lógica (`deleted_at IS NOT NULL`) o inactivo (`is_active = false`) envía credenciales correctas
- **THEN** el sistema responde HTTP 401 sin emitir token

#### Scenario: Email con mayúsculas o espacios
- **WHEN** un usuario activo envía un email con mayúsculas y espacios alrededor (`  ADMIN@CLINICA.LOCAL `)
- **THEN** el sistema normaliza el valor y autentica correctamente, respondiendo HTTP 200

### Requirement: Auditoría de intentos de autenticación

El sistema SHALL registrar cada intento de login en la tabla append-only `registro_auditoria` con usuario (cuando se conoce), acción, IP y dispositivo (RN-SE-02), persistiendo el registro incluso cuando la respuesta es un error.

**Trazabilidad**: US-040 CA-2 (`06_funcionalidades.md`), RN-SE-02 (`05_reglas_de_negocio.md`).

#### Scenario: Login exitoso auditado
- **WHEN** un usuario inicia sesión correctamente
- **THEN** se inserta un registro con `accion = "login_exitoso"`, `usuario_id`, `entidad = "usuario"`, IP y dispositivo

#### Scenario: Login fallido auditado antes del 401
- **WHEN** un login falla por contraseña incorrecta, cuenta inexistente o cuenta dada de baja
- **THEN** se inserta un registro con `accion = "login_fallido"` y el `usuario_id` correspondiente si la cuenta existe (o `NULL` si no existe)
- **AND** el registro queda commiteado antes de devolver HTTP 401, pese al rollback del `UnitOfWork` ante excepción

#### Scenario: Intento bloqueado por throttling no se audita
- **WHEN** un intento es rechazado con HTTP 429 por exceso de fallos
- **THEN** no se inserta un registro de auditoría
- **AND** la cantidad de filas en `registro_auditoria` no crece con los reintentos bloqueados (la tabla es append-only y no se expone a escritura ilimitada)

### Requirement: Protección contra fuerza bruta en inicio de sesión

El sistema SHALL limitar los intentos fallidos de `POST /usuarios/login` por par IP + email para prevenir fuerza bruta, informando el tiempo de espera al cliente.

**Trazabilidad**: `08_arquitectura_propuesta.md` §Seguridad, `CHANGES.md` C-03.

#### Scenario: Intentos dentro del umbral permitido
- **WHEN** un cliente acumula menos fallos que el umbral configurado en la ventana vigente
- **THEN** cada intento fallido responde HTTP 401 y se permiten nuevos reintentos

#### Scenario: Bloqueo temporal por exceso de intentos fallidos
- **WHEN** un cliente alcanza el umbral máximo de fallos dentro de la ventana
- **THEN** el sistema responde HTTP 429 con encabezado `Retry-After` mayor que cero, incluso si las credenciales enviadas son correctas

#### Scenario: Restablecimiento y expiración de la ventana
- **WHEN** un cliente bloqueado inicia sesión correctamente con anterioridad al bloqueo, o deja transcurrir la ventana completa
- **THEN** el contador se restablece (login exitoso) o el bloqueo expira, permitiendo nuevos intentos
