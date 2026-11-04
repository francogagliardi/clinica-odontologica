# Verificación de escenarios — c-07-reserva-online-publica

Fecha: 2026-11-03. Backend con PostgreSQL descartable en `127.0.0.1:15432`; frontend con Vitest/Testing Library.

## Matriz escenario → test

### `agenda/reserva-publica` — API (30 escenarios)

| Requirement / escenario | Test |
|---|---|
| Consultorio público con catálogo | `test_publico.py::test_catalogo_publico_sin_token` |
| Consultorio inexistente o dado de baja | `test_catalogo_de_consultorio_inexistente` |
| Recursos inactivos excluidos | `test_catalogo_excluye_recursos_inactivos` |
| Sin JWT de sesión | `test_catalogo_publico_sin_token` (sin header) |
| Slots públicos con la duración de la prestación | `test_disponibilidad_publica` |
| Recurso inexistente o inactivo | `test_disponibilidad_con_recurso_inexistente` |
| Fecha inválida o parámetro extra | `test_disponibilidad_fecha_invalida_o_parametro_extra` |
| Día sin atención | `test_disponibilidad_dia_sin_atencion` |
| Paciente nuevo reserva con éxito | `test_reserva_publica_crea_paciente_y_turno` |
| Paciente existente con el mismo teléfono | `test_reserva_reutiliza_paciente_con_mismo_telefono` |
| DNI existente con otro teléfono | `test_reserva_con_dni_y_telefono_distinto_es_409` |
| Teléfono o DNI inválido | `test_reserva_invalida_no_deja_residuos` |
| Slot tomado por otra reserva concurrente | `test_dos_reservas_publicas_concurrentes` |
| Turno público que se solapa o cae en bloqueo | `test_reserva_con_solape_o_bloqueo` |
| Elige un sillón libre | `test_sillon_ocupado_por_otro_profesional` |
| Prefiere sillones habilitados | `test_prefiere_sillones_habilitados` |
| Sin sillón disponible | `test_prefiere_sillones_habilitados` (único habilitado ocupado → 409) |
| Intento de imponer sillón | `test_sillon_id_no_permitido` |
| Prestación con seña | `test_reserva_con_sena_pendiente` |
| Prestación sin seña | `test_reserva_sin_sena` |
| Prestación inexistente o inactiva | `test_reserva_con_prestacion_inexistente` |
| Reserva devuelve el enlace de gestión | `test_token_guardado_solo_como_hash` |
| Consultar el resumen no consume | `test_get_gestion_no_consume` |
| Token usado / vencido / ajeno | `test_token_usado_vencido_o_ajeno` |
| Confirmación válida | `test_confirmar_desde_el_enlace` |
| Confirmación inválida | `test_confirmar_turno_invalido_no_consume` |
| Cancelación dentro del plazo | `test_cancelar_dentro_y_fuera_del_plazo` |
| Cancelación fuera del plazo | `test_cancelar_dentro_y_fuera_del_plazo` |
| Cancelación concurrente con el mismo token | `test_cancelaciones_concurrentes_con_el_mismo_token` |
| Encolado exitoso | `test_whatsapp_encolado` |
| Redis caído | `test_whatsapp_caido_no_rompe_la_reserva` |

### `agenda/reserva-publica` — Frontend (4 escenarios)

| Escenario | Test |
|---|---|
| Carga inicial de la página | `ReservaPage.test.tsx::muestra el catálogo y los slots reales` |
| Reserva exitosa desde la página | `muestra el enlace de gestión tras reservar` |
| Error de negocio visible | `muestra el error de la API tal cual` |
| Gestión desde el enlace | `GestionTurnoPage::muestra el turno y permite cancelar` |

### Persistencia, migración y configuración

| Verificación | Test |
|---|---|
| `turnos.sena_estado` y CHECK | `tests/unit/test_models_metadata.py::test_turno_guarda_el_estado_de_la_sena` |
| Head `0007` y cadena desde `0006` | `tests/test_migrations_env.py` |
| Downgrade/upgrade `0007` ⇄ `0006` | `test_migration.py::test_c07_downgrade_y_upgrade_restaura_la_sena` |
| Schemas públicos (sin sillón, identidad normalizada) | `tests/unit/test_publico_schemas.py` |
| TTL configurable del token | `tests/test_settings.py::test_gestion_token_ttl_default_and_override` |

## Resultado

- **Backend**: **412 passed, 0 failed** (367 previos + 45 nuevos entre integración, unitarios y settings).
- **Frontend**: 11 tests en verde (`npm test`), typecheck limpio.
- Smoke público: catálogo 200 sin token (1 profesional, 5 prestaciones), disponibilidad 6 slots, reserva 201 `reservado` + `whatsapp=encolada`, solape 409, DNI con otro teléfono 409, reserva ENDO 201 con seña `pendiente` y monto 10000.00, gestión GET dos veces 200, confirmar 200 y reuso 410, cancelar dentro de plazo 200 con `sena_perdida=false`; datos de smoke eliminados y cola `whatsapp:send` limpiada. Todo verificado el 2026-11-03.
