# Spec Delta

## Purpose

Provee control de acceso basado en roles (RBAC) para los endpoints de la API: valida el JWT Bearer, resuelve el usuario y sus roles contra PostgreSQL en cada petición, y aplica la matriz de permisos de `03_actores_y_roles.md`.

## ADDED Requirements

### Requirement: Validación de token de sesión Bearer

El sistema SHALL validar firma, algoritmo, tipo de token, estructura y vigencia del JWT presentado en `Authorization`, y SHALL verificar contra PostgreSQL que el usuario exista y esté activo.

**Trazabilidad**: DD-07b, RN-SE-01, `08_arquitectura_propuesta.md` §Flujo de autenticación JWT.

#### Scenario: Token Bearer válido y vigente
- **WHEN** una solicitud a `GET /usuarios/me` incluye `Authorization: Bearer <token_valido>`
- **THEN** el sistema responde HTTP 200 con la identidad del usuario autenticado

#### Scenario: Token expirado o con firma adulterada
- **WHEN** la solicitud incluye un token vencido o firmado con otro secreto
- **THEN** el sistema responde HTTP 401 sin procesar el recurso

#### Scenario: Encabezado ausente o esquema distinto de Bearer
- **WHEN** la solicitud no trae `Authorization` o usa un esquema como `Basic`
- **THEN** el sistema responde HTTP 401

#### Scenario: Token con tipo o algoritmo no admitido
- **WHEN** el token declara `typ` distinto de "access", omite un claim obligatorio o fue firmado con `alg = none`
- **THEN** el sistema responde HTTP 401

#### Scenario: Usuario dado de baja con token todavía vigente
- **WHEN** un usuario con baja lógica presenta un token válido y no vencido
- **THEN** el sistema responde HTTP 401 porque relee `deleted_at`/`is_active` desde PostgreSQL

### Requirement: Control de acceso estricto por roles (RBAC)

El sistema SHALL autorizar cada endpoint protegido comparando los roles activos leídos de PostgreSQL contra los roles requeridos, sin confiar en roles embebidos en el token.

**Trazabilidad**: RN-SE-01, `03_actores_y_roles.md` §Matriz de permisos.

#### Scenario: Usuario con rol autorizado accede al recurso
- **WHEN** un administrador autenticado invoca `GET /usuarios` (endpoint que exige rol `administrador`)
- **THEN** el sistema responde HTTP 200 con la lista de usuarios activos

#### Scenario: Usuario con rol insuficiente es denegado
- **WHEN** un recepcionista autenticado invoca `GET /usuarios`
- **THEN** el sistema responde HTTP 403 con detalle "Permisos insuficientes"

#### Scenario: Usuario con múltiples roles donde uno es suficiente
- **WHEN** un usuario con roles `odontologo` y `asistente` invoca `GET /usuarios/me`
- **THEN** el sistema responde HTTP 200 y devuelve ambos roles activos

#### Scenario: Rol revocado en caliente invalida la autorización
- **WHEN** un administrador obtiene un token y, antes de que expire, se le revoca el rol `administrador` en la base
- **THEN** el mismo token sigue autenticando (`/usuarios/me` responde 200) pero `GET /usuarios` responde HTTP 403

#### Scenario: Roles declarados dentro del token no autorizan
- **WHEN** un atacante firma un token válido para un recepcionista agregando un claim `roles = ["administrador"]`
- **THEN** el sistema responde HTTP 403, porque los permisos se resuelven solo contra la base
