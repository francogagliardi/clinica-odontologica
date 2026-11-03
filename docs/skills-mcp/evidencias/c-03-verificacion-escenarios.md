# Evidencia — verificación de los 29 escenarios de C-03

Fecha: 2026-11-02 · Change: `c-03-auth-jwt-rbac` · Governance: CRÍTICO

## Cómo se corrió

```powershell
# base descartable del Compose (cada test resetea el schema)
docker compose -f docker-compose.yml -f <override> up -d db
cd backend
$env:TEST_DATABASE_URL = "postgresql+asyncpg://clinica:<password>@127.0.0.1:15432/clinica"
python -m pytest tests -q
```

Resultado: **110 passed** en 107 s.

Los tests de integración construyen el esquema con `alembic upgrade head` sobre
un schema `public` recién creado, por lo que el DDL probado es el mismo que se
aplica en el entorno. `test_migration.py` verifica además `upgrade head` →
`downgrade base` → `upgrade head`, la paridad ORM↔esquema (índices, CHECKs y
triggers) y que el head es `0003_tokens_un_solo_uso`.

## Trazabilidad escenario → prueba

### `security/jwt-auth` (10)

| # | Escenario | Prueba que lo verifica | Resultado |
|---|---|---|---|
| 1 | Inicio de sesión exitoso | `test_auth_login.py::test_login_exitoso_emite_token_y_audita` | ✅ |
| 2 | Credenciales inválidas sin enumeración | `test_auth_login.py::test_login_credenciales_invalidas_sin_enumeracion` + `unit/test_security_jwt.py::test_verify_password_with_dummy_never_accepts_missing_hash` | ✅ |
| 3 | Usuario dado de baja intenta autenticarse | `test_auth_login.py::test_login_usuario_dado_de_baja_rechazado_y_auditado` | ✅ |
| 4 | Email con mayúsculas o espacios | `test_auth_login.py::test_login_email_es_case_insensitive` + `unit/test_security_jwt.py::test_normalize_email_trims_and_lowercases` | ✅ |
| 5 | Login exitoso auditado | `test_auth_login.py::test_login_exitoso_emite_token_y_audita` | ✅ |
| 6 | Login fallido auditado antes del 401 | `test_auth_login.py::test_login_credenciales_invalidas_sin_enumeracion` + `::test_login_usuario_dado_de_baja_rechazado_y_auditado` | ✅ |
| 7 | Intento bloqueado por throttling no se audita | `test_auth_login.py::test_login_throttling_activado_con_retry_after` (assert `len(rows) == 3`) | ✅ |
| 8 | Intentos dentro del umbral permitido | `unit/test_throttling.py::test_throttling_within_threshold_allows_attempts` + los 401 de `test_auth_login.py` | ✅ |
| 9 | Bloqueo temporal por exceso de fallos | `test_auth_login.py::test_login_throttling_activado_con_retry_after` + `unit/test_throttling.py::test_retry_after_is_zero_when_not_blocked` | ✅ |
| 10 | Restablecimiento y expiración de la ventana | `test_auth_login.py::test_login_exitoso_limpia_el_throttling` + `unit/test_throttling.py::test_throttling_window_expiration` + `::test_retry_after_counts_down_and_unblocks` | ✅ |

### `security/rbac-guards` (10)

| # | Escenario | Prueba que lo verifica | Resultado |
|---|---|---|---|
| 11 | Token Bearer válido y vigente | `test_rbac_guards.py::test_usuario_autenticado_lee_su_identidad` | ✅ |
| 12 | Token expirado o con firma adulterada | `test_rbac_guards.py::test_auth_expired_or_tampered_token` | ✅ |
| 13 | Encabezado ausente o esquema distinto de Bearer | `test_rbac_guards.py::test_auth_header_missing_or_invalid_schema` | ✅ |
| 14 | Token con tipo o algoritmo no admitido | `test_rbac_guards.py::test_token_con_tipo_incorrecto_es_rechazado_en_http` + `unit/test_security_jwt.py::test_decode_unsigned_alg_none_token_is_rejected` + `::test_token_missing_required_claim_is_rejected` | ✅ |
| 15 | Usuario dado de baja con token vigente | `test_rbac_guards.py::test_usuario_dado_de_baja_no_autentica` | ✅ |
| 16 | Usuario con rol autorizado accede | `test_rbac_guards.py::test_rbac_admin_lista_solo_usuarios_activos` | ✅ |
| 17 | Usuario con rol insuficiente es denegado | `test_rbac_guards.py::test_rbac_rol_insuficiente_devuelve_403` | ✅ |
| 18 | Múltiples roles donde uno es suficiente | `test_rbac_guards.py::test_rbac_multi_rol_solo_me` | ✅ |
| 19 | Rol revocado en caliente invalida la autorización | `test_rbac_guards.py::test_rol_revocado_en_caliente_invalida_el_token` | ✅ |
| 20 | Roles declarados en el token no autorizan | `test_rbac_guards.py::test_roles_dentro_del_token_no_autorizan` | ✅ |

### `security/single-use-token` (9)

| # | Escenario | Prueba que lo verifica | Resultado |
|---|---|---|---|
| 21 | Emisión y consulta de token válido vigente | `test_single_use_tokens.py::test_emision_y_consulta_token_valido` | ✅ |
| 22 | Token público inexistente | `test_single_use_tokens.py::test_token_inexistente_falla_sin_filtrar_el_valor` | ✅ |
| 23 | Token vencido o de otro propósito | `test_single_use_tokens.py::test_token_vencido_falla` + `::test_token_de_otro_proposito_es_rechazado` | ✅ |
| 24 | Consumo exitoso por primera vez | `test_single_use_tokens.py::test_consumo_exitoso_y_reutilizacion_rechazada` | ✅ |
| 25 | Reutilización de token ya consumido | `test_single_use_tokens.py::test_consumo_exitoso_y_reutilizacion_rechazada` | ✅ |
| 26 | Consumo concurrente del mismo token | `test_single_use_tokens.py::test_consumo_concurrente_exactamente_uno_tiene_exito` | ✅ |
| 27 | Persistencia con digest SHA-256 | `test_single_use_tokens.py::test_token_se_guarda_hasheado_en_reposo` | ✅ |
| 28 | El valor crudo no es recuperable de la base | `test_single_use_tokens.py::test_token_se_guarda_hasheado_en_reposo` | ✅ |
| 29 | Digest único por emisión | `test_single_use_tokens.py::test_token_se_guarda_hasheado_en_reposo` (segundo token con hash distinto) | ✅ |

## Verificación de migraciones

- Head único: `0003_tokens_un_solo_uso` (`tests/test_migrations_env.py::test_single_head_revision`).
- Cadena declarativa: `0003 → 0002 → 0001` (`::test_c03_revision_chains_from_c02`, `::test_c02_revision_chains_from_baseline`).
- DDL y paridad ORM (`tests/integration/test_migration.py`): tablas/columnas/índices/CHECKs/triggers.
- Reversibilidad: `upgrade head` → `downgrade base` → `upgrade head` (`::test_downgrade_y_upgrade_restaura_el_esquema`).
- Idempotencia: `upgrade head` repetido no cambia el esquema (`::test_upgrade_repetido_es_no_op`).

## Nota sobre independencia

La auditoría de escenarios fue hecha por el mismo agente que implementó el
change (el subagente auditor falló por límite de uso gratuito). Ver
`skill-audit-c-03.md` §Alcance y método. La aprobación humana del gate R-14 es
la verificación independiente que cierra esa brecha.
