# Evidencia — verificación de los 32 escenarios de C-02

Fecha: 2026-11-01 · Change: `c-02-core-models-seguridad` · Commit previo: `18d8929`

## Cómo se corrió

```powershell
# base de datos del Compose (los tests resetean el schema por caso)
docker compose -f docker-compose.yml -f <override> up -d db
cd backend
$env:TEST_DATABASE_URL = "postgresql+asyncpg://clinica:<password>@127.0.0.1:15432/clinica"
python -m pytest tests -q
```

Resultado: **64 passed** (28 unitarios + 36 de integración contra PostgreSQL real).

Los tests de integración construyen el esquema con `alembic upgrade head` sobre un
schema `public` recién creado: no usan `create_all`, así que el DDL probado es el
mismo que se aplica en el entorno.

## Trazabilidad escenario → prueba

### `security/core-models` (15)

| # | Escenario | Prueba que lo verifica | Resultado |
|---|---|---|---|
| 1 | Alta de identidad y asignación de rol | `test_core_models.py::test_alta_de_identidad_y_roles` | ✅ |
| 2 | Valor único duplicado rechazado por la base | `test_core_models.py::test_email_duplicado_activo_rechazado_23505`, `::test_slug_duplicado_activo_rechazado_23505`, `::test_rol_duplicado_activo_rechazado_23505` | ✅ |
| 3 | Email reutilizable tras la baja lógica | `test_core_models.py::test_email_reutilizable_tras_baja_logica` | ✅ |
| 4 | Asignación repetida del mismo rol | `test_core_models.py::test_asignacion_repetida_de_rol_no_duplica` | ✅ |
| 5 | Nombre de rol y slug liberados por la baja lógica | `test_core_models.py::test_slug_y_rol_reutilizables_tras_baja` | ✅ |
| 6 | Primera ejecución del seed | `test_seed.py::test_seed_crea_roles_consultorio_y_admin` | ✅ |
| 7 | Seed sin contraseña configurada | `test_seed.py::test_seed_sin_password_aborta_sin_escribir` + `::test_cli_sin_variable_de_entorno_aborta` | ✅ |
| 8 | Segunda ejecución no duplica | `test_seed.py::test_seed_es_idempotente` | ✅ |
| 9 | Reejecución con otra contraseña no cambia credenciales | `test_seed.py::test_seed_no_reescribe_el_hash` | ✅ |
| 10 | Dos seeds simultáneos no fallan | `test_seed.py::test_seed_concurrente_no_falla` | ✅ |
| 11 | Registro de una acción auditable | `test_core_models.py::test_auditoria_registra_usuario_y_sistema` + `unit/test_models_metadata.py::test_auditoria_no_expone_columnas_de_modificacion` | ✅ |
| 12 | Acción del sistema sin usuario | `test_core_models.py::test_auditoria_registra_usuario_y_sistema` | ✅ |
| 13 | Modificación o borrado rechazado por la base | `test_core_models.py::test_auditoria_rechaza_update_y_delete` | ✅ |
| 14 | Vaciado masivo también rechazado | `test_core_models.py::test_auditoria_rechaza_truncate` | ✅ |
| 15 | Baja lógica del usuario no rompe el historial | `test_core_models.py::test_baja_de_usuario_conserva_auditoria` | ✅ |

### `platform/persistence-patterns` (17)

| # | Escenario | Prueba que lo verifica | Resultado |
|---|---|---|---|
| 16 | Alta y modificación actualizan auditoría de columnas | `test_repositories.py::test_alta_y_modificacion_actualizan_timestamps` | ✅ |
| 17 | Registro dado de baja no aparece en consultas normales | `test_repositories.py::test_list_oculta_bajas_y_include_inactive_las_muestra` | ✅ |
| 18 | Baja lógica repetida es idempotente | `test_repositories.py::test_soft_delete_es_idempotente` | ✅ |
| 19 | Estado parcial de baja rechazado por la base | `test_core_models.py::test_baja_logica_incoherente_rechazada_por_check` | ✅ |
| 20 | Alta y lectura por identificador | `test_repositories.py::test_add_no_commitea_y_otra_sesion_no_lo_ve` + `::test_get_devuelve_entidad_y_none_si_no_existe` | ✅ |
| 21 | Violación de integridad se propaga y no se absorbe | `test_repositories.py::test_violacion_de_unicidad_se_propaga` + `test_uow.py::test_excepcion_revierte_todo` | ✅ |
| 22 | Identificador inexistente no explota en el repositorio | `test_repositories.py::test_get_devuelve_entidad_y_none_si_no_existe` | ✅ |
| 23 | Borrado físico no disponible en la interfaz pública | `test_repositories.py::test_repositorio_no_expone_borrado_fisico` | ✅ |
| 24 | Listado excluye inactivos por defecto | `test_repositories.py::test_list_oculta_bajas_y_include_inactive_las_muestra` | ✅ |
| 25 | Commit conjunto de dos escrituras | `test_uow.py::test_commit_conjunto_publica_todas_las_escrituras` | ✅ |
| 26 | Excepción revierte todo el bloque | `test_uow.py::test_excepcion_revierte_todo` | ✅ |
| 27 | Sesión utilizable tras rollback | `test_uow.py::test_sesion_utilizable_tras_rollback` + `::test_no_deja_transacciones_abiertas` | ✅ |
| 28 | Upgrade en base limpia crea esquema e índices | `test_migration.py::test_upgrade_crea_tablas_columnas_e_indices` | ✅ |
| 29 | Base inalcanzable falla sin esquema parcial | `test_migration.py::test_base_inalcanzable_falla_sin_esquema_parcial` | ✅ |
| 30 | Migración reversible | `test_migration.py::test_downgrade_y_upgrade_restaura_el_esquema` | ✅ |
| 31 | Paridad entre el ORM y el esquema migrado | `test_migration.py::test_paridad_orm_esquema` + `::test_indices_unicos_son_parciales` + los 7 unitarios de `unit/test_models_metadata.py` | ✅ |
| 32 | Upgrade repetido es no-op | `test_migration.py::test_upgrade_repetido_es_no_op` | ✅ |

## Verificación manual (R-14)

Además de la suite, se levantó el stack completo y se verificó desde afuera:

| Chequeo | Comando | Resultado observado |
|---|---|---|
| Servicios | `docker compose ps` | api/db/redis/frontend `healthy` |
| Migración aplicada | `docker compose exec api python -m alembic current` | `0002_core_models_seguridad (head)` |
| Seed idempotente | `docker compose exec api python -m app.seed` (2×) | sin error, sin duplicados |
| Datos demo | `select` de conteos | 5 roles / 1 consultorio / 1 usuario / 1 vínculo |
| Esquema desde el MCP | `information_schema`, `pg_indexes`, `pg_trigger` | ver `mcp-verificacion-c-02.md` |
| Endpoints | `GET /health`, `GET /ready` | `ok` / `db: up, redis: up` |

## Defectos encontrados durante la implementación

1. **Nombre de CHECK duplicado.** La convención de SQLAlchemy agrega `ck_<tabla>_`
   al nombre declarado; la migración pasaba el nombre ya completo y PostgreSQL
   terminaba con `ck_consultorios_ck_consultorios_baja_logica_coherente`. Lo detectó
   el test de paridad ORM↔esquema (escenario 31). Corregido pasando el nombre corto
   en la migración.
2. **Dos escenarios sin prueba al cerrar.** Las rondas de auditoría no habían dejado
   una prueba explícita para «`updated_at` avanza» (16) ni para «base inalcanzable»
   (29). Se escribieron antes de marcar las tareas como completas.

## Nota de alcance

No se probó con pacientes ni datos reales: toda la verificación usa la base demo del
Compose con datos ficticios (`admin@clinica.test`, `Consultorio Demo`).
