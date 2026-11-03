# Verificación de escenarios — c-05-pacientes-cobertura-base

Fecha: 2026-11-03. Suite completa: **285 passed**, 0 fallos (`pytest backend/tests -q` con `TEST_DATABASE_URL` descartable en `127.0.0.1:15432`).

Entorno: PostgreSQL 16 del Compose (schema recreado por test con `DROP SCHEMA public CASCADE` + `alembic upgrade head`), Redis del Compose sin uso en este change.

## Matriz escenario → test

### `pacientes/registro-pacientes` (22 escenarios)

| Requirement / escenario | Test |
|---|---|
| Alta exitosa con DNI y teléfono normalizados | `tests/integration/test_pacientes.py::test_alta_normaliza_y_devuelve_la_ficha` |
| DNI duplicado entre pacientes activos | `test_dni_duplicado_en_api_y_por_sql_directo` (API 409 + `23505` por SQL directo) |
| Baja lógica libera el DNI | `test_baja_logica_libera_el_dni` |
| Teléfono ausente o vacío bloquea el alta | `test_telefono_ausente_bloquea_el_alta` |
| DNI o teléfono con formato inválido | `test_formatos_invalidos_devuelven_422` + `tests/unit/test_pacientes_domain.py` |
| Edición de la ficha | `test_edicion_de_paciente_y_404` |
| Búsqueda por apellido sin distinguir mayúsculas | `test_busqueda_por_apellido_case_insensitive_y_ordenada` |
| Búsqueda por DNI o teléfono formateados | `test_busqueda_por_dni_y_telefono_formateados` |
| Filtros combinados con AND | `test_busqueda_combina_filtros_con_and` |
| Consulta sin ningún criterio | `test_busqueda_sin_criterio_o_con_parametro_extra` |
| Parámetro de búsqueda no declarado | `test_busqueda_sin_criterio_o_con_parametro_extra` |
| Búsqueda sin coincidencias | `test_busqueda_sin_coincidencias_y_bajas_excluidas` |
| Pacientes dados de baja excluidos | `test_busqueda_sin_coincidencias_y_bajas_excluidas` |
| Índice usado para prefijos (R-05) | `test_indice_de_apellido_se_usa_para_prefijos` (`enable_seqscan=off`) |
| Alta con obra social y número de afiliado | `test_alta_con_obra_social_y_afiliado` |
| Obra social inexistente o dada de baja | `test_obra_social_inexistente_o_dada_de_baja` |
| Número de afiliado sin obra social | `test_afiliado_sin_obra_social_devuelve_422` |
| Quitar la cobertura limpia el afiliado | `test_quitar_y_cambiar_cobertura` |
| Cambio de obra social conservando afiliado | `test_quitar_y_cambiar_cobertura` |
| Recepción crea y edita pacientes | `test_recepcion_crea_y_edita_pacientes` |
| Roles clínicos y de auditoría no escriben | `test_roles_clinicos_no_escriben_pacientes` |
| Solo administrador da de baja | `test_solo_administrador_da_de_baja` |
| Petición sin token | `test_pacientes_sin_token_devuelve_401` |

### `comercial/obras-sociales` (16 escenarios)

| Requirement / escenario | Test |
|---|---|
| Alta de convenio y lectura por odontólogo | `tests/integration/test_obras_sociales.py::test_alta_y_lectura_por_odontologo` |
| Nombre duplicado entre convenios activos | `test_nombre_duplicado_sin_distinguir_mayusculas` (API 409 + `23505` por SQL directo) |
| Baja lógica libera el nombre | `test_baja_logica_libera_el_nombre` |
| Escritura según la matriz de roles | `test_recepcion_edita_pero_no_crea_ni_borra` |
| Asistente sin acceso al módulo | `test_asistente_sin_acceso_al_modulo` |
| Convenio inexistente o inactivo | `test_convenio_inexistente_o_dado_de_baja` |
| Petición sin token | `test_obras_sociales_sin_token_devuelve_401` |
| Convenio con reglas locales completas | `test_reglas_completas_se_normalizan` |
| Suma de porcentajes mayor a 100 | `test_reglas_invalidas_devuelven_422[mutacion0]` |
| Porcentaje fuera de rango | `test_reglas_invalidas_devuelven_422[mutacion1/2]` + `tests/unit/test_pacientes_schemas.py` |
| Código de prestación inexistente o duplicado | `test_reglas_invalidas_devuelven_422[mutacion3/4]` + unit |
| Convenio sin reglas | `test_convenio_sin_reglas_acepta_objeto_vacio` |
| Reglas con forma inválida | `test_reglas_con_forma_invalida_devuelven_422` |
| Alta con validación externa solicitada | `test_validacion_externa_rechazada_y_falso_por_defecto` |
| Convenio local por defecto | `test_validacion_externa_rechazada_y_falso_por_defecto` |
| Validación externa explícita en falso | `test_validacion_externa_rechazada_y_falso_por_defecto` |

### Persistencia, migración y seed

| Verificación | Test |
|---|---|
| Tablas, columnas, CHECKs e índices de `pacientes`/`obras_sociales` | `tests/unit/test_models_metadata.py` |
| Head único `0005` y cadena desde `0004` | `tests/test_migrations_env.py` |
| Upgrade crea las 2 tablas y paridad ORM↔esquema | `tests/integration/test_migration.py::test_upgrade_crea_tablas_columnas_e_indices`, `test_paridad_orm_esquema` |
| Índices únicos parciales de DNI y nombre | `test_indices_unicos_son_parciales` |
| Downgrade/upgrade `0005` ⇄ `0004` | `test_c05_downgrade_y_upgrade_restaura_solo_sus_tablas` |
| Seed con OS Demo y 3 pacientes ficticios | `tests/integration/test_seed.py::test_seed_incluye_convenio_y_pacientes_ficticios` |
| Seed idempotente y concurrente | `test_seed_es_idempotente`, `test_seed_concurrente_no_falla` |
| Normalización pura de DNI/teléfono | `tests/unit/test_pacientes_domain.py` |
| Validadores de schemas y reglas de cobertura | `tests/unit/test_pacientes_schemas.py` |

## Resultado

- **285 passed, 0 failed** (88 tests nuevos respecto de C-04).
- Migración reversible verificada en ambos sentidos.
- Sin datos reales: DNI/teléfonos de prueba y convenio ficticio **OS Demo** (DD-11).

Validación manual: stack completo con `docker compose up -d --build`; smoke contra `http://127.0.0.1:8000` (login, 3 pacientes Demo, alta normalizada, búsqueda por DNI formateado, 409 duplicado, 422 código inexistente, 422 validación externa, 401 sin token, baja 204 → ficha 404) y datos de smoke eliminados. **Aprobado por el usuario el 2026-11-03** para archivar, marcar `CHANGES.md` y commitear/pushear.
