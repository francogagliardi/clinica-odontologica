# Tasks

> Cada tarea declara **cómo se verifica** y qué escenario de spec cubre. Ciclo R-09: rojo antes de verde, un slice vertical por ciclo.
> Cobertura total: **29 escenarios** (10 en `security/jwt-auth`, 10 en `security/rbac-guards`, 9 en `security/single-use-token`).

## 0. Preparación y dependencias (R-01, R-08)

- [x] 0.1 Auditar las delta specs con la skill `spec-scenario-auditor` y verificar formato con `openspec validate --strict`. Evidencia: `docs/skills-mcp/evidencias/skill-audit-c-03.md`.
- [x] 0.2 Agregar `pyjwt` pinnada a `backend/requirements.txt` y verificar `python -c "import jwt"`. **Verifica:** import sin errores.

## 1. Primitivas de seguridad (R-01, R-03, DD-07b)

- [x] 1.1 **Rojo**: tests unitarios en `backend/tests/unit/test_security_jwt.py`: hash/verify bcrypt, comparación ficticia para usuario inexistente, normalización de email, emisión y decodificación, claims `sub`/`typ`/`iat`/`exp` sin `email` ni `roles`, rechazo de token adulterado, expirado, con `typ` incorrecto, con `alg = none` y sin claims obligatorios. **Verifica:** `Autenticación de credenciales` (email con mayúsculas, credenciales inválidas) y `Validación de token de sesión Bearer` (tipo/algoritmo no admitido).
- [x] 1.2 **Verde**: implementar `backend/app/core/security.py` (`get_password_hash`, `verify_password`, `verify_password_with_dummy`, `normalize_email`, `create_access_token`, `decode_access_token`). **Verifica:** 1.1 en verde con `pytest tests/unit/test_security_jwt.py`.

## 2. Throttling anti-fuerza bruta (R-02, R-06)

- [x] 2.1 **Rojo**: tests unitarios en `backend/tests/unit/test_throttling.py` con reloj falso: umbral permitido, bloqueo al superarlo, `retry_after` decreciente con `Retry-After`, reset tras éxito, expiración de ventana, aislamiento entre claves y validación de configuración. **Verifica:** `Protección contra fuerza bruta en inicio de sesión` (los 3 escenarios).
- [x] 2.2 **Verde**: implementar `backend/app/core/throttling.py` con reloj inyectable y `retry_after`; exponer `get_login_limiter` en `backend/app/api/deps.py` para sustitución en tests. Documentar la limitación de un solo proceso. **Verifica:** 2.1 en verde con `pytest tests/unit/test_throttling.py`.

## 3. Endpoint de login, auditoría y anti-enumeración (R-01, R-02, RN-SE-02)

- [x] 3.1 **Rojo**: tests de integración en `backend/tests/integration/test_auth_login.py`: login exitoso con token sin roles/email, email case-insensitive, 401 idéntico para contraseña incorrecta y email inexistente, baja lógica, 422 por campos extra/vacíos, 429 con `Retry-After`, reset del contador y filas de auditoría `login_exitoso`/`login_fallido`. **Verifica:** `Autenticación de credenciales y emisión de access token`, `Auditoría de intentos de autenticación` y `Protección contra fuerza bruta`.
- [x] 3.2 **Verde**: implementar `backend/app/schemas/auth.py` (`extra='forbid'`, longitudes) y `backend/app/api/auth.py`: normalización, comparación ficticia, `uow.commit()` del fallo antes del 401, auditoría de éxito/fallo y 429 sin auditar. **Verifica:** 3.1 en verde con `pytest tests/integration/test_auth_login.py`.

## 4. Guards RBAC sobre endpoints reales (R-02, R-03, RN-SE-01)

- [x] 4.1 **Rojo**: tests en `backend/tests/integration/test_rbac_guards.py` contra `GET /usuarios/me` y `GET /usuarios`: sin header/Basic (401), vencido/adulterado (401), token de usuario dado de baja (401), administrador autorizado (200), recepcionista (403), multi-rol (200 en `/me`), rol revocado en caliente (403 con el mismo token) y claim `roles` inyectado que no autoriza (403). **Verifica:** los 10 escenarios de `security/rbac-guards`.
- [x] 4.2 **Verde**: implementar `get_current_user` y `require_role(*roles)` en `backend/app/api/deps.py`, resolviendo roles desde PostgreSQL; agregar `GET /usuarios/me` y `GET /usuarios` (admin) en `backend/app/api/auth.py`; eliminar el router de prueba montado sobre la app. **Verifica:** 4.1 en verde con `pytest tests/integration/test_rbac_guards.py`.

## 5. Tokens públicos de un solo uso (R-04, RN-NO-03)

- [x] 5.1 Migración declarativa `backend/alembic/versions/0003_tokens_un_solo_uso.py`: tabla `tokens_un_solo_uso` con `token_hash` (único), `tipo`, `entidad_tipo`, `entidad_id`, `usado`, `usado_at`, `expira_at`, `created_at` y CHECK de coherencia. **Verifica:** `pytest tests/test_migrations_env.py tests/integration/test_migration.py`.
- [x] 5.2 **Rojo**: tests de integración en `backend/tests/integration/test_single_use_tokens.py`: emisión/vigencia, digest SHA-256 en reposo y ausencia de valor crudo, token inexistente sin filtrar el valor, propósito distinto, vencimiento, consumo único, reuso y concurrencia exacta. **Verifica:** los 9 escenarios de `security/single-use-token`.
- [x] 5.3 **Verde**: implementar `backend/app/models/token.py` y `backend/app/infrastructure/tokens.py` (`IssuedToken`, `hash_token`, `create_single_use_token`, `verify_single_use_token`, `consume_single_use_token`). **Verifica:** 5.2 en verde con `pytest tests/integration/test_single_use_tokens.py`.

## 6. Verificación integrada del change (R-14)

- [x] 6.1 Ejecutar suite completa (`pytest backend/tests`), verificar migración bidireccional (`upgrade head` / `downgrade 0002_core_models_seguridad` / `upgrade head`) y registrar la matriz escenario → test en `docs/skills-mcp/evidencias/c-03-verificacion-escenarios.md`.
- [x] 6.2 Levantar Docker Compose (`docker compose up -d --build`), entregar la lista de pruebas manuales y el resumen en lenguaje no técnico, y esperar aprobación explícita antes de archivar (R-14). Aprobado por el usuario el 2026-11-02.
