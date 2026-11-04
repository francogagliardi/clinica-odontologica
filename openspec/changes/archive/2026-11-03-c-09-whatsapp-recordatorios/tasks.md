# Tasks

> Cobertura: **36 escenarios** (20 en `comunicaciones/recordatorios`, 16 en `comunicaciones/whatsapp-webhook`).
> Ciclo R-09. Governance **ALTO**: idempotencia, reintentos y firma del webhook son obligatorios.
> Proceso acordado 2026-11-03: cierre con suite + smoke y checklist acumulado.

## 0. Preparación

- [x] 0.1 Auditar las specs con `spec-scenario-auditor` y validar `openspec validate c-09-whatsapp-recordatorios --strict`. Evidencia: `docs/skills-mcp/evidencias/skill-audit-c-09.md`.
- [x] 0.2 Confirmar head `0007_reserva_publica`, PostgreSQL/Redis arriba y `btree_gist` disponible.

## 1. Modelos y migración `0008` (R-01, R-04)

- [x] 1.1 **Rojo**: metadata tests: `recordatorios` (columnas, FK, CHECK de ventana/estado, único `(turno_id, ventana)`), `mensajes_whatsapp` (plantilla/estado/respuesta, único `proveedor_mensaje_id`, índices de worker); migración head `0008` y downgrade/upgrade `0008` ⇄ `0007`. **Verifica:** `test_models_metadata.py`, `test_migrations_env.py`, `test_migration.py`.
- [x] 1.2 **Verde**: implementar `app/models/comunicaciones.py`, registrar en `__init__.py` y crear `0008_whatsapp_recordatorios.py`. **Verifica:** 1.1 en verde.

## 2. Programación y cancelación de recordatorios (RN-NO-01)

- [x] 2.1 **Rojo**: tests unitarios/integración con reloj inyectado: turno a 72 h crea 48 y 24; a 30 h solo 24; a 10 h ninguno; reintento no duplica; cancelar turno pasa recordatorios a `cancelado`. **Verifica:** los 5 escenarios de `Programación automática…`.
- [x] 2.2 **Verde**: implementar `app/application/recordatorios.py` (`programar_recordatorios`, `cancelar_recordatorios`) y engancharlo en `crear_turno` y en las cancelaciones de C-06/C-07. **Verifica:** 2.1 en verde.

## 3. Proveedor de prueba y plantillas (R-12, RN-NO-03)

- [x] 3.1 **Rojo**: tests: plantilla de recordatorio arma nombre/fecha/matrícula/`gestion_url`; el token persiste solo como hash; `WHATSAPP_PROVIDER=test` no hace llamadas reales. **Verifica:** los 3 escenarios de `Plantillas mínimas…`.
- [x] 3.2 **Verde**: implementar `app/infrastructure/whatsapp.py`, `app/application/plantillas.py` y settings (`WHATSAPP_PROVIDER`, `WHATSAPP_APP_SECRET`, `WHATSAPP_MAX_INTENTOS`, `WHATSAPP_WORKER_INTERVAL_SECONDS`). **Verifica:** 3.1 en verde.

## 4. Worker de recordatorios vencidos (RN-NO-01, R-06)

- [x] 4.1 **Rojo**: tests con `now` fijo: vencido crea mensaje y encola una sola vez; futuro no se toca; dos workers concurrentes no duplican; turno cancelado no se envía. **Verifica:** los 4 escenarios de `Worker de recordatorios vencidos`.
- [x] 4.2 **Verde**: implementar `procesar_vencidos` con claim atómico `UPDATE ... RETURNING` y encolado a `whatsapp:send`. **Verifica:** 4.1 en verde.

## 5. Worker de WhatsApp y reintentos (RN-NO-01, R-12)

- [x] 5.1 **Rojo**: tests con proveedor falso: éxito marca `enviado`; fallo transitorio incrementa intentos y programa `proximo_intento`; máximo de intentos deja `fallido` + auditoría; mensaje ya enviado no vuelve a llamar. **Verifica:** los 4 escenarios de `Envío con proveedor abstraído…`.
- [x] 5.2 **Verde**: implementar `procesar_entrante`/`procesar_reintentos`, backoff exponencial y auditoría de fallo. **Verifica:** 5.1 en verde.

## 6. Endpoints de consulta y reenvío (RN-SE-01)

- [x] 6.1 **Rojo**: tests: consulta por rango; reenvío manual crea nuevo mensaje y encola; odontólogo/asistente/auditor reciben 403 al reenviar; id inexistente 404. **Verifica:** los 4 escenarios de `Consulta y reenvío de notificaciones`.
- [x] 6.2 **Verde**: implementar `app/api/recordatorios.py`, `app/api/notificaciones.py`, schemas y montaje. **Verifica:** 6.1 en verde.

## 7. Webhook: firma e idempotencia (RN-NO-02/03)

- [x] 7.1 **Rojo**: tests: firma HMAC válida procesa; inválida/ausente 401 sin cambios; cuerpo inválido 422; primer evento `aplicado=true`; duplicado `aplicado=false`; id desconocido 200 `derivado`. **Verifica:** los 3 escenarios de `Webhook autenticado…` y los 3 de `Idempotencia…`.
- [x] 7.2 **Verde**: implementar `app/api/webhooks.py`, verificación HMAC sobre cuerpo crudo y registro idempotente. **Verifica:** 7.1 en verde.

## 8. Webhook: acciones y reprogramación (RN-NO-02, RN-TU-01)

- [x] 8.1 **Rojo**: tests: confirmar 200; cancelar 200 + evento de hueco; acción inválida derivada; reprogramar válido mueve y recalcula fin; colisión deriva sin mover; sin fecha deriva; turno pasado/token vencido/fuera de plazo deriva. **Verifica:** los 4+3+3 escenarios de `Confirmar o cancelar…`, `Reprogramación…` y `Derivación…`.
- [x] 8.2 **Verde**: extraer `reprogramar_turno` al servicio compartido; implementar el procesamiento de acciones y el evento `hueco_liberado` para C-10. **Verifica:** 8.1 en verde.

## 9. CLI de workers, Compose y settings

- [x] 9.1 **Rojo**: test del selector de worker (`recordatorios|whatsapp`) y de las variables de settings (defaults y obligatorias). **Verifica:** `tests/unit/test_worker_entrypoint.py`, `tests/test_settings.py`.
- [x] 9.2 **Verde**: implementar `app/workers/__main__.py`, los loops y el perfil `workers` en Compose; documentar en `.env.example`. **Verifica:** 9.1 y `docker compose config` en verde.

## 10. Verificación integrada

- [x] 10.1 Suite completa, frontend sin regresiones y matriz escenario → test en `docs/skills-mcp/evidencias/c-09-verificacion-escenarios.md`.
- [x] 10.2 Smoke: crear turno a 72 h, correr worker de recordatorios, ver mensaje encolado, simular firma y webhook de confirmación/cancelación/duplicado, reenvío manual y caída del proveedor; limpiar datos y agregar el bloque C-09 a `docs/validacion-manual-pendiente.md`; cerrar/archivar/commitear.
