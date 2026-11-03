# Design

## Context

C-02 dejó operativas las tablas base (`consultorios`, `roles`, `usuarios`, `usuario_roles`, `registro_auditoria`), los patrones de persistencia (`AuditMixin`, `BaseRepository[T]`, `UnitOfWork`) y el seed demo. C-03 construye la capa de autenticación y autorización previa a cualquier endpoint de dominio.

Constraints: R-01 (snake_case, hints completos, Pydantic v2 `extra='forbid'`), R-02 (FastAPI RORO, async I/O, `api/deps.py`, `HTTPException` específico), R-03 (RBAC en API, JWT en memoria, tokens públicos opacos con vencimiento), R-04 (migraciones declarativas), R-05 (índices justificados), R-06 (Redis no guarda dominio durable), RN-SE-01/RN-SE-02/RN-NO-03, governance **CRÍTICO**.

Durante la revisión del borrador inicial se detectaron defectos de seguridad que este diseño corrige explícitamente: token público persistido en claro, login sin auditoría, rutas de prueba montadas sobre la app real, throttling global no inyectable, email case-sensitive, ausencia de comparación ficticia (enumeración por tiempo) y mensajes de error que incluían el token crudo.

## Goals / Non-Goals

**Goals:**
- `POST /usuarios/login` con bcrypt, JWT corto, auditoría y throttling anti-fuerza bruta.
- `get_current_user` y `require_role(*roles)` en `backend/app/api/deps.py`, con roles resueltos siempre desde PostgreSQL.
- Invalidación inmediata ante baja lógica o rol revocado, sin esperar el vencimiento del token.
- Tabla `tokens_un_solo_uso` (migración `0003`) con digest SHA-256, propósito y consumo atómico.
- Endpoints reales mínimos para ejercitar el RBAC: `GET /usuarios/me` y `GET /usuarios` (solo administrador).
- Cobertura verificable en bordes HTTP y PostgreSQL.

**Non-Goals:**
- Refresh tokens o rotación (DD-07b: expiración corta y re-login).
- Recuperación de contraseñas, alta/edición de usuarios o gestión de roles (no v1 en este change).
- Endpoints públicos de negocio (C-07/C-09); C-03 entrega el servicio y el contrato de error.
- Interfaz gráfica de login (C-07/C-08).

## Decisions

### D1 — Librería JWT: `pyjwt` pinneada

Estándar mantenido para HS256, sin dependencias pesadas. `decode` se invoca siempre con una lista explícita de algoritmos y `require` de `exp`, `iat`, `sub` y `typ`; un token `alg = none` o de otro tipo es rechazado.

### D2 — Claims mínimos: identidad, no permisos

El JWT contiene solo `sub` (UUID), `typ = "access"`, `iat` y `exp`. **No** incluye `email` ni `roles`. La autorización se resuelve contra la base en cada request:

- Un cambio de rol aplica de inmediato, sin revocar tokens.
- Un token con `roles` inyectado por un atacante no otorga nada: el guard ignora ese claim.
- Un usuario dado de baja deja de autenticar aunque su token siga vigente.

Costo: una lectura de usuario + roles por request (índice por PK; `roles` se carga con `selectin`). Aceptable para el volumen de un consultorio.

### D3 — bcrypt + comparación ficticia y email normalizado

`bcrypt.checkpw` sobre el hash almacenado. Si el email no existe se compara contra un hash ficticio generado una vez por proceso, para que el tiempo de respuesta no distinga cuentas existentes. El email se normaliza (`strip().lower()`) y la búsqueda usa `lower(email)` en SQL, por lo que el login es case-insensitive. El cuerpo del 401 es idéntico para contraseña incorrecta, email inexistente y cuenta inactiva.

### D4 — Throttling en memoria, inyectable y de un solo proceso

`LoginRateLimiter` implementa ventana deslizante por clave `IP + email` (5 fallos / 5 minutos por defecto). El reloj es inyectable para tests sin `sleep`. Se expone por `get_login_limiter` para sustituirlo en pruebas.

Limitación documentada: el estado vive en el proceso. El demo corre un único worker; si la API se escala horizontalmente, el contador debe moverse a Redis (R-06 permite contadores/colas allí, nunca dominio durable).

El 429 devuelve `Retry-After` y **no se audita**: `registro_auditoria` es append-only y un atacante podría hacerla crecer sin límite. Es un trade-off explícito entre trazabilidad y resistencia a abuso.

### D5 — Auditoría de login con commit explícito

`registro_auditoria` registra `login_exitoso` y `login_fallido` con usuario (si existe), IP y `User-Agent` truncado. El `UnitOfWork` hace rollback cuando la petición termina en excepción, así que el fallo se audita con `uow.commit()` **antes** de lanzar el 401. Para un email inexistente se guarda `usuario_id = NULL` y el identificador intentado como `entidad_id` (truncado a 64).

### D6 — Tokens públicos: hash en reposo y propósito obligatorio

- Se genera `secrets.token_urlsafe(32)` (256 bits) y se persiste solo `sha256(token)` en `token_hash` (64 hex). El valor crudo se devuelve una vez en `IssuedToken.token` y no se guarda.
- `tipo` identifica el propósito (confirmación, recordatorio, seña…). `verify`/`consume` aceptan `expected_tipo` y rechazan un token de otro propósito sin consumirlo.
- Los errores (`TokenNotFoundError`, `TokenAlreadyUsedError`, `TokenExpiredError`, `TokenPurposeError`) no incluyen el valor crudo.
- `usado` y `usado_at` cambian juntos; un CHECK `(usado) = (usado_at IS NOT NULL)` lo garantiza incluso por SQL directo.
- Índices: único en `token_hash` y compuesto `(tipo, entidad_tipo, entidad_id)` para las consultas de C-07/C-09.

C-03 **no** monta endpoints públicos: los escenarios de token se verifican en el borde del servicio (pytest). El mapeo a HTTP 410 Gone pertenece a C-07/C-09 y queda declarado como contrato.

### D7 — Consumo atómico

`UPDATE ... WHERE token_hash = :hash AND usado = false AND expira_at > :now [AND tipo = :tipo] RETURNING *`. Solo una transacción actualiza la fila; la otra recibe 0 filas y el servicio relee para distinguir «no existe», «ya usado», «vencido» o «propósito incorrecto». Sin doble ejecución.

### D8 — Endpoints reales en lugar de router de prueba

El borrador montaba un router `/test-rbac` sobre la app real. Se elimina: el RBAC se prueba contra `GET /usuarios/me` (cualquier autenticado) y `GET /usuarios` (solo `administrador`), que además quedan como superficie mínima útil para el backoffice.

## Risks / Trade-offs

- **Sin refresh token**: la sesión expira según `JWT_EXPIRE_MINUTES` (30 por defecto). Mitigación: DD-07b, re-login en la SPA.
- **Throttling por proceso**: no protege ante múltiples workers. Mitigación: documentado; migrar a Redis al escalar.
- **429 no auditado**: un ataque sostenido no deja rastro en la tabla inmutable. Mitigación: logs de aplicación; se evita el crecimiento ilimitado de una tabla append-only.
- **Lectura de usuario por request**: costo lineal con el tráfico. Mitigación: PK indexada y `selectin` de roles; es el precio de invalidar roles en caliente.
- **Hash SHA-256 sin sal**: correcto para tokens de alta entropía (no son passwords); un atacante no puede precomputar 2^256 valores.

## Migration Plan

1. `python -m alembic upgrade head` aplica `0003_tokens_un_solo_uso` (`down_revision = "0002_core_models_seguridad"`).
2. Reversión: `alembic downgrade 0002_core_models_seguridad` elimina índices y tabla.
3. Verificación: `pytest tests` con `TEST_DATABASE_URL` apuntando a la base descartable del Compose.
