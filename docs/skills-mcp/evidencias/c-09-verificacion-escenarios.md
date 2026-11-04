# Verificación de escenarios — c-09-whatsapp-recordatorios

Fecha: 2026-11-03. Backend con PostgreSQL descartable y proveedor de WhatsApp de prueba (`WHATSAPP_PROVIDER=test`); sin llamadas reales a Meta (R-12).

## Matriz escenario → test

### `comunicaciones/recordatorios` (20 escenarios)

| Escenario | Test |
|---|---|
| Turno con más de 48 horas | `test_comunicaciones.py::test_programa_48_y_24_y_no_duplica` |
| Turno entre 24 y 48 horas | `test_turno_cercano_solo_programa_24` |
| Turno con menos de 24 horas | `test_programa_48_y_24_y_no_duplica` (programado futuro) |
| Reintento del alta no duplica | `test_programa_48_y_24_y_no_duplica` (dos llamadas) |
| Turno cancelado | `test_cancelar_recordatorios` |
| Recordatorio vencido se encola | `test_worker_encola_vencido_y_no_futuro` |
| Recordatorio futuro no se toca | `test_worker_encola_vencido_y_no_futuro` |
| Dos workers concurrentes | `test_dos_workers_no_duplican` |
| Turno cancelado antes del envío | `test_cancelar_recordatorios` + worker salta terminales |
| Envío exitoso | `test_envio_exitoso_y_fallo_con_reintento` |
| Fallo transitorio | `test_envio_exitoso_y_fallo_con_reintento` + `test_reintentos_vence_backoff` |
| Se agota el máximo de intentos | `test_fallo_agota_intentos_y_audita` |
| Reintento no duplica | `test_reintento_no_reenvia_enviado` |
| Consulta por rango | `test_endpoints_recordatorios_y_reenvio` |
| Reenvío manual | `test_endpoints_recordatorios_y_reenvio` |
| Rol sin permiso de reenvío | `test_endpoints_recordatorios_y_reenvio` (403) |
| Mensaje inexistente | `test_endpoints_recordatorios_y_reenvio` (404) |
| Plantilla de recordatorio | `test_worker_encola_vencido_y_no_futuro` (`gestion_url` en payload) |
| Token no almacenado en claro | `test_worker_encola_vencido_y_no_futuro` + infraestructura de C-03 (hash) |
| Proveedor real deshabilitado | `tests/unit/test_worker_entrypoint.py` y settings (`WHATSAPP_PROVIDER=test`) |

### `comunicaciones/whatsapp-webhook` (16 escenarios)

| Escenario | Test |
|---|---|
| Firma válida | `test_webhook_endpoint_firma_e_idempotencia` |
| Firma inválida o ausente | `test_webhook_endpoint_firma_e_idempotencia` (401) + `test_worker_entrypoint.py` |
| Cuerpo inválido con firma válida | `WebhookRequest` (`extra='forbid'`) + endpoint 422 |
| Primer evento | `test_webhook_firma_y_acciones` |
| Evento duplicado | `test_webhook_firma_y_acciones` |
| Id desconocido sin mensaje | `test_webhook_pasado_y_desconocido_deriva` |
| Confirmación | `test_webhook_firma_y_acciones` |
| Cancelación | `procesar_webhook` (`cancelar`) + auditoría `hueco_liberado` |
| Acción inválida por estado | `procesar_webhook` deriva estados terminales |
| Confirmación duplicada en el cuerpo | idempotencia por `respuesta` |
| Reprogramación válida | `test_webhook_cancelar_y_reprogramar` |
| Reprogramación con colisión | `procesar_webhook` captura `HTTPException` → derivado |
| Reprogramación sin fecha | `procesar_webhook` deriva |
| Turno ya pasado | `test_webhook_pasado_y_desconocido_deriva` |
| Token vencido | C-07 (410) y derivación del webhook sin datos |
| Cancelación fuera del plazo | política de C-07 + derivación |

### Persistencia y migración

| Verificación | Test |
|---|---|
| Tablas/CHECKs/índices de recordatorios y mensajes | `tests/unit/test_models_metadata.py` |
| Head `0008` y cadena desde `0007` | `tests/test_migrations_env.py` |
| Downgrade/upgrade `0008` ⇄ `0007` | `test_migration.py::test_c08_downgrade_y_upgrade_restaura_mensajeria` |

## Resultado

- **Backend**: **432 passed, 0 failed** (412 previos + 20 nuevos entre unitarios, integración y settings).
- **Frontend**: sin cambios; 28 tests de C-08 siguen vigentes.
- **Smoke**: turno 201; 2 recordatorios programados; scheduler encoló; worker WhatsApp marcó `enviado` con id de proveedor test; webhook con firma inválida 401; firma válida 200 `aplicado=true`; duplicado 200 `aplicado=false`; turno final `confirmado`. Datos de smoke eliminados.
