# Proposal

## Why

C-02 estableció los modelos de identidad (`Usuario`, `Rol`, `UsuarioRol`, `Consultorio`), la auditoría append-only y el seed demo, pero el sistema aún no tiene autenticación ni autorización: no hay forma de iniciar sesión, ni de verificar identidad con tokens, ni de proteger rutas según roles.

Sin C-03 no se pueden construir las rutas protegidas de recursos agendables (C-04), pacientes (C-05) ni turnos (C-06), porque ninguna podría aplicar la matriz de `03_actores_y_roles.md` ni identificar al actor. Además, C-07 y C-09 necesitan tokens públicos opacos de un solo uso con vencimiento para enlaces sin login (RN-NO-03).

## What Changes

- Agrega `pyjwt` pinneada para firmar y verificar access tokens HS256.
- Expone `POST /usuarios/login` (email + contraseña) que valida bcrypt contra PostgreSQL y devuelve un JWT corto (DD-07b) con los datos del usuario y sus roles activos.
- Emite JWT con claims mínimos (`sub`, `typ`, `iat`, `exp`): **sin** `email` ni `roles`. La autorización se resuelve siempre contra la base, por lo que un rol revocado deja de aplicar de inmediato.
- Audita cada intento de login en `registro_auditoria` (RN-SE-02): `login_exitoso` y `login_fallido` con usuario (si existe), IP y dispositivo. El fallo se commitea antes del 401.
- Evita enumeración de cuentas: comparación bcrypt ficticia cuando el email no existe y respuesta 401 idéntica; el email se normaliza (case-insensitive).
- Aplica throttling anti-fuerza bruta por IP + email (5 fallos / 5 min) con respuesta HTTP 429 y `Retry-After`. El limitador es inyectable y, en v1, de un solo proceso (documentado).
- Implementa en `backend/app/api/deps.py`:
  - `get_current_user`: valida firma, algoritmo, `typ`, vigencia y claims; relee el usuario y descarta inactivos o dados de baja.
  - `require_role(*roles)`: guard RBAC contra los roles activos leídos de PostgreSQL.
- Expone dos endpoints reales para ejercitar el RBAC: `GET /usuarios/me` (cualquier autenticado) y `GET /usuarios` (solo administrador).
- Agrega `tokens_un_solo_uso` (migración `0003`) con propósito (`tipo`), entidad, vencimiento y consumo; persiste **solo el digest SHA-256** y devuelve el valor crudo una única vez.
- Implementa el servicio `single_use_token` con verificación de propósito, consumo atómico (un solo uso) y errores tipados (`TokenNotFoundError`, `TokenAlreadyUsedError`, `TokenExpiredError`, `TokenPurposeError`) que C-07/C-09 mapean a HTTP 404/410.
- Suite unitaria y de integración (TDD) con 29 escenarios verificables en bordes HTTP y PostgreSQL.

## Capabilities

### New Capabilities
- `security/jwt-auth`: login con bcrypt, JWT corto, auditoría de intentos, anti-enumeración y throttling.
- `security/rbac-guards`: validación de Bearer y autorización por roles contra PostgreSQL (RN-SE-01), con endpoints reales.
- `security/single-use-token`: tokens opacos hasheados, con propósito y consumo atómico para flujos públicos (RN-NO-03).

### Modified Capabilities
- Ninguna: C-01 y C-02 no definieron capacidades de autenticación ni tokens de enlace.

## Impact

- **Backend**:
  - `pyjwt` en `backend/requirements.txt`.
  - `backend/app/core/security.py` (bcrypt, JWT, normalización, comparación ficticia).
  - `backend/app/core/throttling.py` (limitador inyectable).
  - `backend/app/api/auth.py`, `backend/app/schemas/auth.py`, `backend/app/api/deps.py` (login, auditoría, `/me`, RBAC).
  - `backend/app/models/token.py`, `backend/app/infrastructure/tokens.py`, migración `0003_tokens_un_solo_uso.py`.
  - `backend/app/infrastructure/repositories.py` (búsqueda de email case-insensitive) y `uow.py` (`commit()` explícito).
  - Tests en `backend/tests/unit/` e `backend/tests/integration/`.
- **API Surface**:
  - `POST /usuarios/login` (público con throttling).
  - `GET /usuarios/me` (autenticado) y `GET /usuarios` (administrador).
- **Riesgos y mitigaciones**:
  - Sin refresh token en v1 → expiración corta configurable y re-login.
  - Fuerza bruta → throttling por IP + email con `Retry-After`.
  - Reuso de token público → consumo atómico con `usado` y CHECK de coherencia.
  - Filtración de base → solo se guarda el hash SHA-256 del token.
