# Tasks

> Cobertura: **67 escenarios nuevos/ajustados** (30 en `agenda/lista-espera`, 25 en `comunicaciones/ofertas-hueco`, 8 en `agenda/turnos`, 2 en `agenda/reserva-publica`, 2 en `agenda/recursos-agendables`). Las deltas de `reserva-publica` y `recursos-agendables` repiten los escenarios vigentes del requirement modificado; esos bloques se re-verifican al correr la suite existente.
> Ciclo R-09 (rojo → verde). Governance **MEDIO**: FIFO, retención atómica, vencimiento y conversión son el núcleo verificable.
> Regla de cierre acordada: el usuario no prueba cada change; la validación manual se acumula en `docs/validacion-manual-pendiente.md` para el test de páginas final (R-14).

## 0. Preparación

- [x] 0.1 Auditar las cinco deltas (`agenda/lista-espera`, `comunicaciones/ofertas-hueco`, `agenda/turnos`, `agenda/reserva-publica`, `agenda/recursos-agendables`) con `spec-scenario-auditor` contra RN-TU-05/RN-TU-01 y corregir huecos; guardar evidencia en `docs/skills-mcp/evidencias/c-10-spec-audit.md`. **Verifica:** cada requirement tiene escenario esperado, de error de negocio y de borde, y `openspec validate c-10-lista-espera-automatica --strict` pasa.
- [x] 0.2 Confirmar head `0008_whatsapp_recordatorios`, PostgreSQL/Redis arriba, `btree_gist` disponible y suite base en verde. **Verifica:** `alembic current` y `pytest -q` sin fallos previos.

## 1. Modelos y migración `0009` con retención (R-01, R-04)

- [x] 1.1 **Rojo**: tests de metadata y migración: `entradas_lista_espera` con columnas de retención (`oferta_profesional_id`, `oferta_sillon_id`, `oferta_inicio`, `oferta_fin`, `oferta_expira_en`), CHECKs de coherencia, índices de cola/vencimiento/retención, único parcial de pendientes y las dos exclusion constraints (`ex_lista_espera_profesional`, `ex_lista_espera_sillon`); `mensajes_whatsapp` con `turno_id` nullable, `lista_espera_id` y respuestas `aceptado`/`rechazado`; head `0009` y upgrade/downgrade `0009` ⇄ `0008`. **Verifica:** `tests/unit/test_models_metadata.py`, `tests/test_migrations_env.py`, `tests/integration/test_single_use_tokens.py`/`test_migration.py` y un INSERT por SQL directo de dos retenciones solapadas que devuelve `23P01`.
- [x] 1.2 **Verde**: implementar `app/models/lista_espera.py`, ajustar `app/models/comunicaciones.py`, registrar en `app/models/__init__.py`, agregar repositorio y atributo al `UnitOfWork`, y crear `backend/alembic/versions/0009_lista_espera.py` con las constraints. **Verifica:** 1.1 en verde y `alembic upgrade head` seguido de `alembic downgrade -1` + `upgrade head` sobre la base demo.

## 2. Alta, listado y baja de entradas (RN-TU-05, RN-SE-01)

- [x] 2.1 **Rojo**: tests de integración de `POST /lista-espera` (201 con `orden` creciente, duplicado 409, recurso inexistente/inactivo/otro consultorio 404, cuerpo inválido o campo extra 422), `GET /lista-espera` ordenado por `orden`, `GET /lista-espera/{id}` y `DELETE` de `pendiente` (200, desaparece del listado) contra `ofrecido` 409 e inexistente 404. **Verifica:** los escenarios de `Alta de entrada…` y `Baja de una entrada pendiente`.
- [x] 2.2 **Verde**: implementar `app/schemas/lista_espera.py`, `app/api/lista_espera.py` y montar el router; baja lógica y filtros con `reject_unexpected_query_except`. **Verifica:** 2.1 en verde.
- [x] 2.3 **Rojo**: tests RBAC: recepción 201/200/200; odontólogo 403 en alta/baja y 200 en lectura de sus profesionales; asistente/auditor 200 lectura y 403 escritura; sin token 401; entrada de otro consultorio 404. **Verifica:** los 4 escenarios de `Acceso a la lista de espera por rol`.
- [x] 2.4 **Verde**: aplicar `require_role` y el filtro por consultorio/profesional en el router y el repositorio. **Verifica:** 2.3 en verde.

## 3. Retención: disponibilidad y bloqueo de altas (RN-TU-05, D2/D7)

- [x] 3.1 **Rojo**: tests: una entrada `ofrecido` oculta el slot en `GET /reservar/{slug}/disponibilidad` y en `GET /profesionales/{id}/disponibilidad`; `POST /turnos`, `PATCH /turnos/{id}/reprogramar`, `POST /reservar/{slug}/turnos` y el sobreturno marcado responden 409 si se solapan; turnos consecutivos en el borde y retención de otro recurso responden 201; retención vencida sin barrido no bloquea ni oculta; dos retenciones concurrentes solapadas dejan una sola oferta (`23P01`); convertir libera la retención y el turno pasa a ser el bloqueo. **Verifica:** los 6 escenarios de `Retención atómica del hueco ofrecido`, los 8 de `Reservas bloqueadas por retenciones de lista de espera`, los 2 nuevos de `Disponibilidad pública real` y los 2 nuevos de `Disponibilidad base por profesional`.
- [x] 3.2 **Verde**: implementar `retenciones_vigentes(...)` en el repositorio, sumarlas a `calcular_disponibilidad` en ambos endpoints y consultarlas en `validar_solapamiento` antes del retorno por sobreturno; agregar `retencion_excluida` a `crear_turno`/`validar_solapamiento` para la conversión. **Verifica:** 3.1 en verde y los tests de disponibilidad de C-04/C-06/C-07 sin regresiones.

## 4. Disparo del hueco liberado y selección FIFO (RN-TU-05, D1/D3/D4)

- [x] 4.1 **Rojo**: tests de que las **tres** cancelaciones (`PATCH /turnos/{id}/estado`, `POST /reservar/gestion/{token}/cancelar`, rama cancelar del webhook) escriben `RegistroAuditoria(accion="hueco_liberado")` una sola vez, retienen el rango y disparan la oferta; más FIFO compatible: menor `orden` gana, incompatible por profesional se saltea, entrada sin profesional toma el profesional y el sillón liberados, sin candidatas no hay retención/mensaje/cola. **Verifica:** los 4 escenarios de `Selección FIFO con compatibilidad` y el escenario `Una entrada dada de baja no recibe ofertas`.
- [x] 4.2 **Verde**: implementar `registrar_hueco_liberado` y `ofrecer_hueco`/`ofrecer_siguiente` en `app/application/lista_espera.py`; migrar el registro de auditoría desde `application/webhooks.py` y llamar al servicio en los tres puntos de cancelación. **Verifica:** 4.1 en verde.

## 5. Mensaje, token y consulta pública de la oferta (RN-NO-03, D8/D9)

- [x] 5.1 **Rojo**: tests: mensaje `oferta_hueco` persistido con `lista_espera_id`, `turno_id` nulo y variables (paciente, fecha/hora `UTC-3`, matrícula, `oferta_url`); id encolado en `whatsapp:send`; Redis caído deja `pendiente` con `proximo_intento` y la cancelación responde 200; reprocesar no duplica; token `oferta_hueco` con solo hash y TTL ≤ oferta; reuso/vencido/otro propósito/entrada no ofrecida → 410; `GET /reservar/oferta/{token}` 200 dos veces sin consumir, 410 vencida y sin teléfono/DNI. **Verifica:** los escenarios de `Mensaje de oferta…`, `Token de oferta…` y `Consulta pública de la oferta`.
- [x] 5.2 **Verde**: implementar `variables_oferta_hueco` en `app/application/plantillas.py`, el alta de mensaje/token y el encolado en `app/application/ofertas_hueco.py`, y `app/api/ofertas.py` con la consulta pública. **Verifica:** 5.1 en verde.

## 6. Vencimiento, rotación y rechazo con liberación (US-003/CA-2, D5)

- [x] 6.1 **Rojo**: tests con reloj inyectado: vencimiento en el borde exacto libera la retención, rota al siguiente y encola un mensaje nuevo; si el hueco ya fue tomado no re-retiene ni ofrece; última entrada vence y el hueco vuelve a `GET /reservar/{slug}/disponibilidad`; rechazo por enlace libera y el siguiente retiene el mismo sillón; rechazo repetido 410; rechazo de una convertida 410. **Verifica:** los 4 escenarios de `Oferta con vencimiento y rotación` y los 4 de `Rechazo de la oferta por enlace`.
- [x] 6.2 **Verde**: implementar `procesar_ofertas_vencidas` con `UPDATE ... RETURNING`, `flush` de liberación antes de retener al siguiente, el enganche en `run_once_recordatorios`/`loop_recordatorios`, y el endpoint `POST /reservar/oferta/{token}/rechazar`. **Verifica:** 6.1 en verde.

## 7. Aceptación y conversión con recursos retenidos (RN-TU-01, D6/D10)

- [x] 7.1 **Rojo**: tests: aceptar crea turno en el profesional, sillón y horario retenidos, entrada `convertido` con `turno_id`, retención liberada y recordatorios programados; retención vencida con horario ya tomado → 409, entrada `vencido`, sin turno y siguiente ofrecida; dos aceptaciones concurrentes → una 200 y otra 409/410, un solo turno; reserva pública simultánea al vencer la retención → un solo turno. **Verifica:** los 4 escenarios de `Conversión a turno sin solapamiento` y los 4 de `Aceptación de la oferta por enlace`.
- [x] 7.2 **Verde**: implementar `aceptar_oferta` con `FOR UPDATE`, savepoint, `retencion_excluida` y resultado explícito (sin rollback del token); usar los recursos retenidos en `ComandoTurno`; endpoint `POST .../aceptar`. **Verifica:** 7.1 en verde.

## 8. Respuesta de la oferta por WhatsApp (RN-NO-02, D9)

- [x] 8.1 **Rojo**: tests del webhook: «aceptar» crea turno con los recursos retenidos y registra `respuesta=aceptado`; «rechazar» libera, marca vencido, rota y registra `respuesta=rechazado`; duplicado del mismo `proveedor_mensaje_id` responde `aplicado=false` sin segundo turno; «confirmar»/«reprogramar» sobre una oferta responde `aplicado=false, derivado=true` sin cambios. **Verifica:** los 4 escenarios de `Aceptación o rechazo por respuesta de WhatsApp`.
- [x] 8.2 **Verde**: ramificar en `procesar_webhook` por `plantilla == "oferta_hueco"` antes de resolver el turno, reutilizando la idempotencia de C-09. **Verifica:** 8.1 en verde y los tests de C-09 del webhook sin regresiones.

## 9. Verificación integrada

- [x] 9.1 Correr la suite backend completa y el build/test del frontend (sin cambios esperados); armar la matriz escenario → test en `docs/skills-mcp/evidencias/c-10-verificacion-escenarios.md`, incluyendo la re-verificación de los escenarios copiados en las deltas MODIFIED. **Verifica:** 67 escenarios nuevos/ajustados con test o smoke asociado y suite en verde.
- [x] 9.2 Smoke con `docker compose up -d --build`: seed, dos entradas FIFO, cancelar un turno, comprobar que el slot desaparece de la disponibilidad pública y del backoffice y que `POST /turnos`/reprogramación responden 409, correr el worker `recordatorios --once`, verificar mensaje/oferta/token, aceptar por enlace con el sillón retenido, repetir con rechazo y con vencimiento, confirmar que al vencer la retención el hueco vuelve a disponibilidad; limpiar datos, bajar el stack y agregar el bloque C-10 a `docs/validacion-manual-pendiente.md`. **Verifica:** resultados del smoke anotados en la evidencia.
- [x] 9.3 Validar `openspec validate c-10-lista-espera-automatica --strict` y `openspec status --change c-10-lista-espera-automatica`. **Verifica:** salida sin errores ni warnings y artefactos en `done`.

## Workflow follow-up

- La validación manual del usuario se difiere al test de páginas final; no se pide probar C-10 por separado.
- Archivar el change solo con aprobación explícita, bajar el stack antes de `/opsx:archive`, marcar `[x]` en `CHANGES.md` y recién entonces commitear/pushear (R-13/R-14).
