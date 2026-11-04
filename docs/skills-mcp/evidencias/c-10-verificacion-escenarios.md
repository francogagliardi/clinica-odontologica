# Verificación de escenarios — c-10-lista-espera-automatica

Fecha: 2026-11-04. Backend con PostgreSQL descartable, proveedor de WhatsApp de prueba
(`WHATSAPP_PROVIDER=test`) y Redis de Compose. Sin llamadas reales a Meta ni a Mercado Pago
(R-12). Rutas de test relativas a `backend/tests/integration/`.

Cobertura: **67 escenarios nuevos/ajustados** (30 `agenda/lista-espera`, 25
`comunicaciones/ofertas-hueco`, 8 `agenda/turnos`, 2 `agenda/reserva-publica`, 2
`agenda/recursos-agendables`) + la re-verificación de los escenarios copiados en las dos
deltas MODIFIED.

## Matriz escenario → test

### `agenda/lista-espera` — Alta de entrada en la lista de espera (4)

| Escenario | Test |
|---|---|
| Alta válida toma el siguiente orden | `test_lista_espera.py::test_alta_valida_toma_el_siguiente_orden` |
| Entrada pendiente duplicada | `test_lista_espera.py::test_alta_duplicada_devuelve_409[False/True]` |
| Recurso inexistente, inactivo o de otro consultorio | `test_lista_espera.py::test_alta_con_recurso_inexistente_devuelve_404[...]`, `::test_alta_con_paciente_o_profesional_inactivo_devuelve_404`, `::test_alta_de_recurso_de_otro_consultorio_devuelve_404` |
| Cuerpo inválido o campo extra | `test_lista_espera.py::test_alta_con_cuerpo_invalido_devuelve_422` |

### `agenda/lista-espera` — Baja de una entrada pendiente (4)

| Escenario | Test |
|---|---|
| Baja de una entrada pendiente | `test_lista_espera.py::test_baja_de_pendiente_la_quita_y_libera_el_duplicado` |
| Baja de una entrada ofrecida | `test_lista_espera.py::test_baja_de_una_entrada_ofrecida_devuelve_409` |
| Entrada inexistente o de otro consultorio | `test_lista_espera.py::test_baja_de_una_entrada_inexistente_devuelve_404`, `::test_entrada_de_otro_consultorio_no_es_visible` |
| Una entrada dada de baja no recibe ofertas | `test_lista_espera_ofertas.py::test_entrada_dada_de_baja_no_recibe_oferta` |

### `agenda/lista-espera` — Selección FIFO con compatibilidad (4)

| Escenario | Test |
|---|---|
| Dos entradas compatibles | `test_lista_espera_ofertas.py::test_fifo_gana_la_entrada_de_menor_orden` |
| Primera entrada incompatible por profesional | `test_lista_espera_ofertas.py::test_fifo_saltea_la_entrada_incompatible_y_usa_los_recursos_liberados` |
| Entrada sin profesional acepta cualquier hueco | `test_lista_espera_ofertas.py::test_fifo_saltea_la_entrada_incompatible_y_usa_los_recursos_liberados` (profesional y sillón liberados) |
| Sin entradas compatibles | `test_lista_espera_ofertas.py::test_sin_candidatas_no_retiene_ni_mensajea_ni_encola` |

### `agenda/lista-espera` — Oferta con vencimiento y rotación (4)

| Escenario | Test |
|---|---|
| Vencimiento rota al siguiente | `test_ofertas_vencimiento.py::test_vencimiento_en_el_borde_exacto_libera_y_rota` |
| Hueco ya ocupado al rotar | `test_ofertas_vencimiento.py::test_vencida_con_el_hueco_ya_tomado_no_rota` |
| Vencimiento en el borde exacto | `test_ofertas_vencimiento.py::test_vencimiento_en_el_borde_exacto_libera_y_rota` (+ `::test_vencer_fuera_de_ventana_no_procesa`) |
| Última entrada sin aceptación | `test_ofertas_vencimiento.py::test_la_ultima_oferta_vencida_devuelve_el_hueco_a_disponibilidad` |

### `agenda/lista-espera` — Conversión a turno sin solapamiento (4)

| Escenario | Test |
|---|---|
| Aceptación convierte la entrada | `test_ofertas_aceptacion.py::test_aceptar_crea_el_turno_con_los_recursos_retenidos` |
| Retención vencida y horario ya tomado | `test_ofertas_aceptacion.py::test_aceptar_retencion_vencida_con_el_horario_tomado_devuelve_409` |
| Dos aceptaciones concurrentes | `test_ofertas_aceptacion.py::test_dos_aceptaciones_concurrentes_crean_un_solo_turno` |
| Reserva pública simultánea al vencer la retención | `test_ofertas_aceptacion.py::test_reserva_publica_simultanea_al_vencer_deja_un_solo_turno` |

### `agenda/lista-espera` — Retención atómica del hueco ofrecido (6)

| Escenario | Test |
|---|---|
| La cancelación retiene el hueco | `test_lista_espera_ofertas.py::test_patch_cancelado_retiene_audita_y_encola` + `test_lista_espera_retencion.py::test_retencion_vigente_oculta_el_slot_en_el_backoffice` |
| La aceptación libera la retención | `test_ofertas_aceptacion.py::test_la_conversion_no_deja_retencion_activa` + `::test_aceptar_marca_el_mensaje_de_oferta_como_consumido` |
| Dos cancelaciones no retienen dos veces el mismo horario | `test_lista_espera_ofertas.py::test_dos_cancelaciones_concurrentes_dejan_una_sola_oferta`, `test_lista_espera_retencion.py::test_dos_retenciones_solapadas_por_profesional_violan_la_exclusion`, `::test_dos_retenciones_solapadas_por_sillon_violan_la_exclusion`, `::test_dos_retenciones_concurrentes_dejan_una_sola` |
| Retención vencida sin barrido no bloquea | `test_lista_espera_retencion.py::test_retencion_vencida_sin_barrido_no_oculta_ni_bloquea` |
| El rechazo libera y el siguiente retiene | `test_ofertas_vencimiento.py::test_rechazo_libera_y_rota_al_siguiente_con_el_mismo_sillon` |
| Nadie acepta y no queda retención | `test_ofertas_vencimiento.py::test_la_ultima_oferta_vencida_devuelve_el_hueco_a_disponibilidad`, `::test_rechazo_sin_siguiente_devuelve_el_hueco_a_disponibilidad` |

### `agenda/lista-espera` — Acceso a la lista de espera por rol (4)

| Escenario | Test |
|---|---|
| Recepción administra la lista | `test_lista_espera.py::test_recepcion_administra_la_lista` |
| Odontólogo intenta crear o borrar | `test_lista_espera.py::test_odontologo_solo_lee_sus_propias_entradas` |
| Asistente y auditor solo leen | `test_lista_espera.py::test_asistente_y_auditor_solo_leen[asistente/auditor]` |
| Sin token o consultorio ajeno | `test_lista_espera.py::test_sin_token_devuelve_401`, `::test_entrada_de_otro_consultorio_no_es_visible` |

### `comunicaciones/ofertas-hueco` — Mensaje de oferta (4)

| Escenario | Test |
|---|---|
| Oferta encolada | `test_lista_espera_ofertas.py::test_patch_cancelado_retiene_audita_y_encola` |
| Redis caído al ofrecer | `test_lista_espera_ofertas.py::test_redis_caido_deja_el_mensaje_pendiente_y_la_cancelacion_responde_200` |
| Mensaje sin turno asociado | `test_lista_espera_ofertas.py::test_patch_cancelado_retiene_audita_y_encola` (`turno_id is None`) |
| Reintento no duplica | `test_lista_espera_ofertas.py::test_repetir_la_cancelacion_no_duplica_oferta_ni_auditoria` |

### `comunicaciones/ofertas-hueco` — Token de oferta de propósito propio (5)

| Escenario | Test |
|---|---|
| Emisión del token | `test_lista_espera_ofertas.py::test_token_de_oferta_guarda_solo_hash_y_vence_con_la_oferta` |
| Token reutilizado | `test_ofertas_aceptacion.py::test_aceptar_dos_veces_devuelve_410`, `test_ofertas_vencimiento.py::test_rechazo_repetido_devuelve_410` |
| Token vencido | `test_ofertas_aceptacion.py::test_aceptar_una_oferta_vencida_y_libre_devuelve_410` |
| Token de otro propósito | `test_lista_espera_ofertas.py::test_consulta_de_oferta_con_token_de_otro_proposito_devuelve_410`, `test_ofertas_aceptacion.py::test_aceptar_con_token_invalido_o_de_otro_proposito`, `test_ofertas_vencimiento.py::test_rechazo_con_token_de_otro_proposito_devuelve_410` |
| Entrada que ya no está ofrecida | `test_lista_espera_ofertas.py::test_consulta_de_oferta_ya_no_ofrecida_devuelve_410`, `test_ofertas_vencimiento.py::test_rechazo_de_una_oferta_convertida_devuelve_410` |

### `comunicaciones/ofertas-hueco` — Consulta pública de la oferta (4)

| Escenario | Test |
|---|---|
| Consulta de una oferta vigente | `test_lista_espera_ofertas.py::test_consulta_publica_de_la_oferta_no_consume_ni_expone_datos_sensibles` |
| Consultar dos veces no consume | `test_lista_espera_ofertas.py::test_consulta_publica_de_la_oferta_no_consume_ni_expone_datos_sensibles` |
| Oferta vencida | `test_lista_espera_ofertas.py::test_consulta_de_oferta_vencida_devuelve_410` |
| Respuesta sin datos sensibles | `test_lista_espera_ofertas.py::test_la_oferta_publica_no_declara_campos_sensibles[telefono/dni]` |

### `comunicaciones/ofertas-hueco` — Aceptación de la oferta por enlace (4)

| Escenario | Test |
|---|---|
| Aceptación exitosa | `test_ofertas_aceptacion.py::test_aceptar_crea_el_turno_con_los_recursos_retenidos` |
| Retención vencida y hueco tomado | `test_ofertas_aceptacion.py::test_aceptar_retencion_vencida_con_el_horario_tomado_devuelve_409` |
| Aceptaciones concurrentes del mismo enlace | `test_ofertas_aceptacion.py::test_dos_aceptaciones_concurrentes_crean_un_solo_turno` |
| Aceptar una oferta ya vencida | `test_ofertas_aceptacion.py::test_aceptar_una_oferta_vencida_y_libre_devuelve_410` |

### `comunicaciones/ofertas-hueco` — Rechazo de la oferta por enlace (4)

| Escenario | Test |
|---|---|
| Rechazo con siguiente entrada | `test_ofertas_vencimiento.py::test_rechazo_libera_y_rota_al_siguiente_con_el_mismo_sillon` |
| Rechazo sin siguiente entrada | `test_ofertas_vencimiento.py::test_rechazo_sin_siguiente_devuelve_el_hueco_a_disponibilidad` |
| Rechazo repetido | `test_ofertas_vencimiento.py::test_rechazo_repetido_devuelve_410` |
| Rechazo de una oferta ya convertida | `test_ofertas_vencimiento.py::test_rechazo_de_una_oferta_convertida_devuelve_410` |

### `comunicaciones/ofertas-hueco` — Aceptación o rechazo por WhatsApp (4)

| Escenario | Test |
|---|---|
| Aceptar desde WhatsApp | `test_ofertas_webhook.py::test_aceptar_por_whatsapp_crea_el_turno` |
| Rechazar desde WhatsApp | `test_ofertas_webhook.py::test_rechazar_por_whatsapp_libera_y_rota` |
| Evento duplicado del proveedor | `test_ofertas_webhook.py::test_evento_duplicado_no_crea_un_segundo_turno` |
| Acción no aplicable a una oferta | `test_ofertas_webhook.py::test_accion_no_aplicable_a_una_oferta_deriva[confirmar/reprogramar]` |

### `agenda/turnos` — Reservas bloqueadas por retenciones (8)

| Escenario | Test |
|---|---|
| Alta que se solapa con una retención vigente | `test_lista_espera_retencion.py::test_alta_que_se_solapa_con_una_retencion_devuelve_409` |
| Reprogramación hacia un horario retenido | `test_lista_espera_retencion.py::test_reprogramacion_hacia_un_horario_retenido_devuelve_409` |
| Reserva pública sobre un horario retenido | `test_lista_espera_retencion.py::test_reserva_publica_sobre_una_retencion_devuelve_409_sin_residuos` |
| Sobreturno marcado contra una retención | `test_lista_espera_retencion.py::test_sobreturno_marcado_contra_una_retencion_devuelve_409` |
| Retención vencida sin barrido no bloquea | `test_lista_espera_retencion.py::test_retencion_vencida_sin_barrido_no_oculta_ni_bloquea` |
| Retención de otro recurso no afecta | `test_lista_espera_retencion.py::test_retencion_de_otro_recurso_no_afecta` |
| Turno consecutivo en el borde de la retención | `test_lista_espera_retencion.py::test_turno_consecutivo_en_el_borde_se_permite` |
| Retención liberada por conversión | `test_lista_espera_retencion.py::test_conversion_libera_la_retencion_y_el_turno_pasa_a_bloquear` |

### `agenda/reserva-publica` — Disponibilidad pública real (2 nuevos, MODIFIED)

| Escenario | Test |
|---|---|
| Retención vigente oculta el slot | `test_lista_espera_retencion.py::test_retencion_vigente_oculta_el_slot_en_la_disponibilidad_publica` |
| Retención vencida no oculta el slot | `test_lista_espera_retencion.py::test_retencion_vencida_sin_barrido_no_oculta_ni_bloquea` |

### `agenda/recursos-agendables` — Disponibilidad base por profesional (2 nuevos, MODIFIED)

| Escenario | Test |
|---|---|
| Retención vigente oculta el slot del backoffice | `test_lista_espera_retencion.py::test_retencion_vigente_oculta_el_slot_en_el_backoffice` |
| Retención vencida no oculta el slot del backoffice | `test_lista_espera_retencion.py::test_retencion_vencida_sin_barrido_no_oculta_ni_bloquea` |

## Re-verificación de escenarios copiados en deltas MODIFIED

| Delta | Escenarios copiados | Re-verificado por |
|---|---|---|
| `agenda/reserva-publica` | Slots públicos con la duración, recurso inexistente/inactivo, fecha inválida o parámetro extra, día sin atención | `test_publico.py` (suite completa, sin regresiones) |
| `agenda/recursos-agendables` | Slots consecutivos, duración base, profesional inexistente, día fuera de atención, último slot incompleto, borde 422/404, turno activo, cancelación/ausencia, otro profesional, día completo | `test_disponibilidad.py`, `test_turnos.py` (suite completa, sin regresiones) |
| `agenda/turnos` | Alta/reprogramación/sobresalida y anti-solapamiento de C-06 | `test_turnos.py` (suite completa) |

## Persistencia y migración

| Verificación | Test |
|---|---|
| Tabla, columnas de retención, CHECKs, índices y exclusion constraints | `tests/unit/test_models_metadata.py` |
| Head `0009` y cadena desde `0008` | `tests/test_migrations_env.py` |
| Upgrade/downgrade `0009` ⇄ `0008` y nulabilidad de `mensajes_whatsapp.turno_id` | `test_migration.py::test_c10_downgrade_y_upgrade_restaura_la_lista_de_espera` |
| `23P01` de retenciones solapadas por SQL directo | `test_lista_espera_retencion.py::test_dos_retenciones_solapadas_*` |

## Reconciliación de spec

- **`Retención vencida y horario ya tomado`** (aceptación) pide 409 y «se ofrece al
  siguiente»; **`Hueco ya ocupado al rotar`** (vencimiento) prohíbe ofrecer un rango que
  ya no está libre. Se aplica la regla más estricta y segura: 409, entrada `vencido`,
  auditoría `oferta_hueco_perdida` y rotación **solo si** el rango sigue libre. Con el
  horario tomado no se crea una oferta imposible de aceptar.

## Resultado de la suite

- Backend: **516 passed** en `pytest tests -q` (22 min 29 s, PostgreSQL descartable,
  incluidos los 23 tests nuevos de este slice) + 1 test agregado después del arranque de esa
  corrida (`test_rechazo_sin_siguiente_devuelve_el_hueco_a_disponibilidad`), verificado con
  `test_ofertas_vencimiento.py` → **10 passed**. Total efectivo **517**.
- Frontend: **28 passed** (`npm test`) y `npm run typecheck` sin errores (sin cambios de UI).

## Smoke con Docker

Ver `docs/validacion-manual-pendiente.md` §C-10 y el detalle paso a paso al final de este
documento.

### Smoke ejecutado (2026-11-04)

**Resultado: OK en todos los pasos.**

- Profesional, sillón, 4 pacientes y 2 entradas FIFO creados (201).
- Cancelación por `PATCH /turnos/{id}/estado` (200) con auditoría `hueco_liberado` única.
- Primera entrada queda `ofrecido`; retención con profesional y sillón liberados.
- El slot retenido no aparece en disponibilidad pública ni de backoffice.
- `POST /turnos`, sobreturno y reprogramación hacia el horario retenido → 409; turno original intacto.
- Worker `recordatorios --once`: mensaje `oferta_hueco` persistido con `oferta_url`; `GET /reservar/oferta/{token}` 200 dos veces sin consumir.
- `POST .../aceptar` 200: turno creado en los recursos retenidos, entrada `convertido`, horario bloqueado.
- Segunda cancelación rota a la siguiente entrada; `POST .../rechazar` 200, auditoría `oferta_hueco_rechazada`, rotación al siguiente.
- Vencimiento forzado + worker: entrada `vencido`; sin más entradas, el hueco vuelve a disponibilidad.
- Limpieza de datos de smoke completada.

**Suite backend final: 432 previos + 84 nuevos = 516 passed, 0 failed.** Frontend: 28 passed y typecheck limpio.

**Re-ejecución independiente del smoke (misma sesión, 2026-11-04):** 41 verificaciones OK
(profesional/sillón/4 pacientes, 2 entradas FIFO, cancelación con auditoría única, slot
oculto en ambas disponibilidades, 409 en alta/sobreturno/reprogramación, worker tick,
mensaje/token, consulta doble sin consumir, aceptación con recursos retenidos, rechazo con
rotación, vencimiento forzado con rotación y vuelta a disponibilidad). Limpieza verificada:
0 turnos, 0 entradas, 0 pacientes/profesional/mensajes de smoke. El stack quedó **arriba**
(`api`, `db`, `redis`) por pedido del usuario; `registro_auditoria` conserva las filas del
smoke (append-only, RN-SE-02).
