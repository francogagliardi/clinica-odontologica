# Verificación de escenarios — c-06-turnos-anti-solapamiento

Fecha: 2026-11-03. Suite completa ejecutada con `TEST_DATABASE_URL` descartable en `127.0.0.1:15432` (ver resultado al pie).

Entorno: PostgreSQL 16 del Compose con `btree_gist`; el schema se recrea por test (`DROP SCHEMA public CASCADE` + `alembic upgrade head`), así que las constraints de exclusión se prueban sobre DDL real.

## Matriz escenario → test

### `agenda/turnos` (36 escenarios)

| Requirement / escenario | Test |
|---|---|
| Alta con prestación calcula el fin | `test_turnos.py::test_alta_con_prestacion_calcula_el_fin` |
| Alta sin prestación usa la duración base | `test_alta_sin_prestacion_usa_duracion_base` |
| Recurso inexistente o dado de baja | `test_recurso_inexistente_devuelve_404` (paciente, profesional, sillón, prestación) |
| Turno fuera de la agenda del profesional | `test_turno_fuera_de_agenda_devuelve_422` (día inhábil, fin tarde, inicio temprano) |
| Turno con fin no posterior al inicio | `test_fin_no_posterior_es_rechazado_por_la_base` (CHECK `23514`) |
| Datos inválidos en el borde | `test_payload_invalido_devuelve_422` (`fin`, `estado`, `origen`) |
| Mismo profesional en el mismo horario | `test_mismo_profesional_solapado_devuelve_409` |
| Mismo sillón con otro profesional | `test_mismo_sillon_con_otro_profesional_devuelve_409` |
| Turnos consecutivos en el borde | `test_turnos_consecutivos_se_permiten` |
| Dos altas concurrentes al mismo slot | `test_dos_altas_concurrentes_al_mismo_slot` (una 201, una 409, una fila) |
| Solapamiento insertado por SQL directo | `test_solapamiento_por_sql_directo_es_rechazado` (`23P01`) |
| Turnos cancelados no bloquean | `test_turno_cancelado_libera_el_horario` |
| Recursos distintos en el mismo horario | `test_recursos_distintos_en_el_mismo_horario` |
| Sobreturno marcado se permite solapado | `test_sobreturno_marcado_se_permite` |
| Sobreturno sin color | `test_sobreturno_sin_color_devuelve_422` |
| Turno normal con color de sobreturno | `test_color_sin_marca_devuelve_422` |
| Turno normal contra un sobreturno existente | `test_turno_normal_contra_sobreturno_devuelve_409` |
| Bloqueo del profesional impide la reserva | `test_bloqueo_del_profesional_impide_reservar` |
| Bloqueo del sillón impide la reserva | `test_bloqueo_del_sillon_impide_reservar` |
| Bloqueo adyacente no afecta | `test_bloqueo_adyacente_no_afecta` |
| Bloqueo de otro recurso no afecta | `test_bloqueo_de_otro_recurso_no_afecta` |
| Transiciones válidas del flujo de atención | `test_transiciones_validas_del_flujo` |
| Transición inválida | `test_transiciones_invalidas_devuelven_422` (salto y resurrección) |
| Cancelación desde estados válidos | `test_cancelacion_desde_estados_validos` |
| Repetir el estado actual | `test_repetir_estado_es_idempotente` |
| Turno inexistente o de otro consultorio | `test_cambio_de_estado_de_turno_inexistente` |
| Reprogramación a un horario libre | `test_reprogramacion_a_horario_libre` |
| Reprogramación a un horario ocupado | `test_reprogramacion_a_horario_ocupado_deja_intacto` |
| Reprogramación fuera de agenda o sobre bloqueo | `test_reprogramacion_fuera_de_agenda_o_sobre_bloqueo` |
| Reprogramar un turno cerrado | `test_reprogramar_turno_cerrado_devuelve_422` |
| Reprogramaciones concurrentes al mismo slot | `test_reprogramaciones_concurrentes_al_mismo_slot` |
| Recepción opera la agenda | `test_recepcion_opera_la_agenda` |
| Odontólogo solo opera sus turnos | `test_odontologo_solo_opera_sus_turnos` |
| Odontólogo intenta crear turnos | `test_odontologo_no_crea_turnos` |
| Asistente y auditor solo leen | `test_asistente_y_auditor_solo_leen` |
| Petición sin token | `test_turnos_sin_token_devuelve_401` |

### `agenda/recursos-agendables` — disponibilidad real (10 escenarios)

| Requirement / escenario | Test |
|---|---|
| Slots consecutivos con la duración de la prestación | `test_disponibilidad.py` (suite C-04, sigue vigente) |
| Sin prestación usa la duración base | `test_disponibilidad.py` (suite C-04) |
| Profesional inexistente o dado de baja | `test_disponibilidad.py` (suite C-04) |
| Día fuera de los días de atención | `test_disponibilidad.py` (suite C-04) |
| Último slot incompleto descartado | `tests/unit/test_agenda_domain.py` (suite C-04) |
| Fecha o prestación inválida en el borde | `test_disponibilidad.py` (suite C-04) |
| Turno activo ocupa el slot | `test_turnos.py::test_disponibilidad_descuenta_turnos_activos` |
| Cancelación o ausencia libera el slot | `test_cancelacion_libera_el_slot_en_disponibilidad` |
| Turno de otro profesional no afecta | `test_turno_de_otro_profesional_no_afecta` |
| Día completo sin huecos | `test_dia_completo_devuelve_lista_vacia` |

### Persistencia, migración y dominio

| Verificación | Test |
|---|---|
| Tabla `turnos`, CHECKs, exclusiones e índices | `tests/unit/test_models_metadata.py` |
| Plazo de cancelación del consultorio | `test_consultorio_configura_el_plazo_de_cancelacion` |
| Head único `0006` y cadena desde `0005` | `tests/test_migrations_env.py` |
| Constraints de exclusión y token único en la base | `test_migration.py::test_turnos_declara_exclusion_y_token_publico` |
| Downgrade/upgrade `0006` ⇄ `0005` | `test_c06_downgrade_y_upgrade_restaura_turnos` |
| Cálculo de fin, ventana, solapamiento y estados | `tests/unit/test_turnos_domain.py` |
| Validadores de los schemas de turno | `tests/unit/test_turnos_schemas.py` |

## Resultado

- **367 passed, 0 failed** (285 previos + 82 nuevos) — ver `docs/validacion-manual-pendiente.md` para la aceptación funcional diferida.
- Migración reversible en ambos sentidos, con `btree_gist` instalado.
- Prueba de concurrencia real: dos altas simultáneas → una 201 y una 409; dos reprogramaciones simultáneas → una 200 y una 409.
- Sin datos reales: pacientes, profesionales y turnos ficticios.

Validación manual automatizada (smoke de API, 2026-11-03): login 200; alta de profesional 201; turno 201 con fin 09:30; solape 409; sobreturno con color 201; turno normal contra sobreturno 409; fuera de agenda 422; disponibilidad 4 slots; confirmar 200; salto inválido 422; flujo reservado→confirmado→en_sala→atendido 200/200; reprogramación 200; bloqueo 201 y turno en bloqueo 409; cancelación 200; disponibilidad final 3 slots; sin token 401. Datos de smoke eliminados. La aceptación funcional de la página queda en la prueba final acordada.
