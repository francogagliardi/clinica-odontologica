# Verificación de escenarios — c-04-recursos-agendables

Fecha: 2026-11-02. Suite completa: **188 passed**, 0 fallos (`pytest backend/tests -q` con `TEST_DATABASE_URL` descartable en `127.0.0.1:15432`).

Validación manual: stack completo levantado con `docker compose up -d --build`; smoke contra `http://127.0.0.1:8000` (login, listados, alta de profesional, disponibilidad 3 → bloqueo → 2 slots, 401 sin token). **Aprobado por el usuario el 2026-11-02** para archivar, marcar `CHANGES.md` y commitear/pushear.

Migración: `0004_recursos_agendables` aplicada sobre `0003_tokens_un_solo_uso`; el test `test_downgrade_y_upgrade_restaura_el_esquema` baja a `base` y vuelve a `head` verificando tablas, índices, CHECKs y triggers. `test_upgrade_repetido_es_no_op` confirma idempotencia del deploy.

> Convención: `TP` = `tests/integration/test_profesionales.py`, `TS` = `test_sillones.py`, `TT` = `test_prestaciones.py`, `TB` = `test_bloqueos.py`, `TD` = `test_disponibilidad.py`, `UA` = `tests/unit/test_agenda_domain.py`.

## agenda/recursos-agendables (18)

| Escenario | Clase | Verificación | Resultado |
|---|---|---|---|
| Alta de profesional y lectura por recepción | esperado | `TP::test_alta_de_profesional_y_lectura_por_recepcion` (201 + 200) | OK |
| Matrícula duplicada entre activos | error de negocio | `TP::test_matricula_duplicada_devuelve_409` (409 + índice parcial) | OK |
| Escritura por rol no administrador | error de negocio | `TP::test_escritura_por_rol_no_administrador_devuelve_403` (4 roles) | OK |
| Baja lógica libera la matrícula | borde | `TP::test_baja_logica_libera_la_matricula` (204 → 201, id distinto) | OK |
| Agenda base inválida | borde | `TP::test_agenda_invalida_devuelve_422` (7 variantes) + CHECKs en `test_models_metadata.py` | OK |
| Usuario ya vinculado a otro profesional | borde | `TP::test_usuario_ya_vinculado_devuelve_409` (409 y 404 de usuario) | OK |
| Alta de sillón y listado | esperado | `TS::test_alta_de_sillon_y_listado` (201 + 200) | OK |
| Sillón duplicado entre activos | error de negocio | `TS::test_sillon_duplicado_devuelve_409` | OK |
| Escritura de sillones por no administrador | error de negocio | `TS::test_escritura_de_sillones_por_no_administrador` (odontólogo/recepción) | OK |
| Baja lógica libera el nombre | borde | `TS::test_baja_logica_de_sillon_libera_el_nombre` | OK |
| Habilitación repetida no duplica | borde | `TS::test_habilitacion_repetida_no_duplica` (2×204, 1 fila, DELETE 204) | OK |
| Habilitación con recurso inexistente/inactivo | error de negocio | `TS::test_habilitacion_con_recurso_inexistente_o_inactivo` (404) | OK |
| Slots con duración de la prestación | esperado | `TD::test_disponibilidad_usa_duracion_de_la_prestacion` (CONS 30 min → 6 slots) | OK |
| Sin prestación usa duración base | esperado | `TD::test_disponibilidad_con_duracion_base` (60 min → 3 slots) | OK |
| Profesional inexistente o inactivo | error de negocio | `TD::test_disponibilidad_de_profesional_inexistente_o_inactivo` (404) | OK |
| Día fuera de atención | borde | `TD::test_dia_fuera_de_atencion_devuelve_lista_vacia` (200 `[]`) | OK |
| Último slot incompleto descartado | borde | `UA::test_ultimo_slot_incompleto_se_descarta` | OK |
| Fecha/prestación inválida en el borde | borde | `TD::test_fecha_invalida_o_parametros_extra` (422) + `TD::test_prestacion_inexistente_o_inactiva` (404) | OK |

## comercial/prestaciones (10)

| Escenario | Clase | Verificación | Resultado |
|---|---|---|---|
| Alta de prestación y lectura | esperado | `TT::test_alta_de_prestacion_y_lectura` | OK |
| Código duplicado entre activas | error de negocio | `TT::test_codigo_duplicado_devuelve_409` (también `dup` → `DUP`) | OK |
| Escritura por rol no administrador | error de negocio | `TT::test_escritura_por_rol_no_administrador` (POST/PUT/DELETE) | OK |
| Baja lógica libera el código | borde | `TT::test_baja_logica_libera_el_codigo` | OK |
| Duración o precio fuera de rango | borde | `TT::test_duracion_o_precio_fuera_de_rango` (3 variantes) + CHECKs | OK |
| Prestación con seña y monto visible | esperado | `TT::test_prestacion_con_sena_y_monto_visible` | OK |
| Seña exigida sin monto | error de negocio | `TT::test_sena_exigida_sin_monto_devuelve_422` | OK |
| Monto sin seña exigida | borde | `TT::test_monto_sin_seña_exigida_devuelve_422` | OK |
| Monto de seña no positivo | borde | `TT::test_monto_de_sena_no_positivo_devuelve_422` (0 y negativo) | OK |
| Quitar la seña deja monto nulo | borde | `TT::test_quitar_la_sena_persiste_monto_nulo` | OK |

## agenda/bloqueos (16)

| Escenario | Clase | Verificación | Resultado |
|---|---|---|---|
| Recepción crea bloqueo de profesional | esperado | `TB::test_recepcion_crea_bloqueo_de_profesional` (201 + listado) | OK |
| Dos recursos o ninguno | error de negocio | `TB::test_bloqueo_con_dos_o_ningun_recurso` (422) + CHECK XOR | OK |
| Rango temporal inválido | error de negocio | `TB::test_rango_temporal_invalido` (igual y anterior → 422) | OK |
| Recurso inexistente o inactivo | error de negocio | `TB::test_bloqueo_con_recurso_inexistente_o_inactivo` (404) | OK |
| Bloqueos solapados | borde | `TB::test_bloqueos_solapados_se_permiten` (2×201) | OK |
| Odontólogo bloquea su propio profesional | esperado | `TB::test_odontologo_gestiona_su_propio_profesional` (201 + DELETE 204) | OK |
| Odontólogo bloquea a otro profesional | error de negocio | `TB::test_odontologo_no_bloquea_a_otro_profesional` (403 POST y DELETE) | OK |
| Odontólogo bloquea un sillón | error de negocio | `TB::test_odontologo_no_bloquea_sillones` (403) | OK |
| Asistente o auditor escriben | error de negocio | `TB::test_asistente_y_auditor_no_escriben_bloqueos` (403 POST, 200 GET) | OK |
| Profesional sin usuario vinculado | borde | `TB::test_odontologo_no_reclama_profesional_sin_usuario` (403) | OK |
| Bloqueo dentro del horario quita slots | esperado | `UA::test_bloqueo_dentro_del_horario_quita_slots` + `TD::test_bloqueo_de_profesional_quita_slots_y_su_baja_los_restaura` | OK |
| Bloqueo fuera del horario no cambia | borde | `UA::test_bloqueo_fuera_del_horario_no_cambia_nada` | OK |
| Bloqueo de otro profesional no afecta | borde | `TD::test_bloqueo_de_otro_profesional_no_afecta` + `UA::test_sin_bloqueos_del_profesional_consultado` | OK |
| Bloqueo de sillón afecta consulta con sillón | esperado | `TD::test_bloqueo_de_sillon_solo_afecta_la_consulta_con_sillon` | OK |
| Baja lógica del bloqueo restaura slots | borde | `TD::test_bloqueo_de_profesional_quita_slots_y_su_baja_los_restaura` | OK |
| Sillón inexistente o inactivo en disponibilidad | error de negocio | `TD::test_disponibilidad_de_sillon_inexistente_o_inactivo` (404) | OK |

## Verificación de esquema (transversal)

| Contrato | Verificación |
|---|---|
| 5 tablas nuevas + columnas + FKs | `tests/unit/test_models_metadata.py`, `tests/integration/test_migration.py::test_upgrade_crea_tablas_columnas_e_indices` |
| Índices únicos parciales (matrícula, usuario, sillón, código) | `test_unicidad_parcial_de_recursos_activos` + `test_indices_unicos_son_parciales` |
| CHECK XOR de bloqueo y rango | `test_bloqueo_exige_un_solo_recurso_y_rango_valido` |
| CHECK de seña coherente | `test_prestacion_exige_sena_coherente` |
| CHECK de agenda (duración, horario, días) | `test_profesional_valida_agenda_en_la_base` |
| PK compuesta de habilitación | `test_profesional_sillon_tiene_pk_compuesta` |
| `usuario_id` nullable | `test_profesional_puede_no_tener_usuario_vinculado` |
| Seed idempotente y catálogo mínimo | `tests/integration/test_seed.py` (2 sillones, 5 prestaciones, ENDO con seña) |
| Un solo head `0004` y cadena desde `0003` | `tests/test_migrations_env.py` |
