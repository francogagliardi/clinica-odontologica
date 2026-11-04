# Tasks

> Cada tarea declara **cómo se verifica** y qué escenario cubre. Ciclo R-09: rojo antes de verde.
> Cobertura total: **34 escenarios** en `agenda/reserva-publica`.
> Governance **ALTO**: rutas públicas y token de un solo uso; se revisa explícitamente el aislamiento de datos.
> **Proceso acordado (2026-11-03)**: cierre con suite + smoke y checklist acumulado en `docs/validacion-manual-pendiente.md`; sin espera de prueba manual por change.

## 0. Preparación

- [x] 0.1 Auditar la spec con `spec-scenario-auditor` y validar `openspec validate c-07-reserva-online-publica --strict`. Evidencia: `docs/skills-mcp/evidencias/skill-audit-c-07.md`.
- [x] 0.2 Confirmar head `0006_turnos_anti_solapamiento`, PostgreSQL/Redis del Compose arriba y `app_base_url` en settings. **Verifica:** `alembic current`, `docker compose ps`, `GET /ready`.

## 1. `sena_estado` y migración `0007` (R-04, R-10)

- [x] 1.1 **Rojo**: tests de metadata y migración: columna `turnos.sena_estado` NOT NULL default `no_requiere`, CHECK de estados, head `0007`, downgrade/upgrade `0007` ⇄ `0006`. **Verifica:** `test_models_metadata.py`, `test_migrations_env.py`, `test_migration.py`.
- [x] 1.2 **Verde**: agregar `Turno.sena_estado` en `app/models/agenda.py` y `0007_reserva_publica.py` con la constraint. **Verifica:** 1.1 en verde.

## 2. Servicio compartido de alta de turno (R-01, R-10)

- [x] 2.1 **Rojo**: mover/duplicar los tests de alta de C-06 para que el servicio sea el punto de entrada; la suite existente debe seguir verde antes del refactor. **Verifica:** `pytest tests/integration/test_turnos.py`.
- [x] 2.2 **Verde**: extraer `app/application/turnos.py` (`crear_turno`) desde `app/api/turnos.py`, manteniendo comportamiento y mensajes; el router del backoffice pasa a usarlo. **Verifica:** toda la suite de C-06 sigue verde.

## 3. Settings y schemas públicos (R-01, R-02)

- [x] 3.1 **Rojo**: tests unitarios de schemas: `extra='forbid'`, `sillon_id` rechazado, teléfono/DNI inválidos, inicio sin zona, email inválido, respuesta pública sin campos de paciente. **Verifica:** `tests/unit/test_publico_schemas.py`.
- [x] 3.2 **Rojo**: tests de settings para `GESTION_TOKEN_TTL_MINUTES` (default 10080) y `APP_BASE_URL`; actualizar `.env.example`. **Verifica:** `tests/test_settings.py`.
- [x] 3.3 **Verde**: implementar `app/schemas/publico.py` y los settings nuevos. **Verifica:** 3.1 y 3.2 en verde.

## 4. Catálogo y disponibilidad públicos (R-01, RN-TU-01/02/07)

- [x] 4.1 **Rojo**: tests de integración: catálogo 200 sin token con profesionales/prestaciones activas y políticas, sin emails ni tokens; slug inexistente 404; recursos inactivos excluidos; disponibilidad pública 200 con slots reales, 404 de recursos, 422 de fecha/parámetro extra y día inhábil `[]`. **Verifica:** los 4 escenarios de `Catálogo público del consultorio` y los 4 de `Disponibilidad pública real`.
- [x] 4.2 **Verde**: implementar `app/api/publico.py` (catálogo y disponibilidad reutilizando `calcular_disponibilidad`) y montar el router. **Verifica:** 4.1 en verde.

## 5. Reserva pública: paciente y sillón (RN-TU-01, RN-NO-03)

- [x] 5.1 **Rojo**: tests: paciente nuevo (201 + paciente normalizado), DNI existente con mismo teléfono (reutiliza), DNI con otro teléfono (409), DNI/teléfono inválido (422 sin paciente ni turno), solape 409, bloqueo 409, dos reservas concurrentes (una 201, una 409). **Verifica:** los 6 escenarios de `Reserva pública con paciente existente o nuevo`.
- [x] 5.2 **Rojo**: tests de sillón: elige el libre, prefiere habilitados, sin sillón libre 409, `sillon_id` en el body 422. **Verifica:** los 4 escenarios de `Asignación automática de sillón`.
- [x] 5.3 **Verde**: implementar `POST /reservar/{slug}/turnos` con búsqueda/creación de paciente, selección de sillón y uso del servicio de C-06. **Verifica:** 5.1 y 5.2 en verde.

## 6. Seña pendiente (RN-TU-04/08)

- [x] 6.1 **Rojo**: tests: prestación con seña → `sena.estado=pendiente` + monto + políticas; sin seña → `no_requiere`; prestación inexistente/baja 404. **Verifica:** los 3 escenarios de `Seña pendiente y política visible`.
- [x] 6.2 **Verde**: setear `sena_estado` en el servicio y armar el bloque `sena` de la respuesta. **Verifica:** 6.1 en verde.

## 7. Token y acciones de gestión (RN-NO-03, RN-TU-03/04)

- [x] 7.1 **Rojo**: tests: la reserva devuelve `gestion_url` y la base guarda solo el hash; `GET` dos veces no consume; token usado 410; vencido 410 (forzando `expira_at`); propósito distinto 410; token inexistente 410. **Verifica:** los 5 escenarios de `Token de gestión de un solo uso`.
- [x] 7.2 **Rojo**: tests: confirmar 200 y consumo; confirmar inválido 422 sin consumir; cancelar dentro del plazo `sena_perdida=false`; fuera del plazo `true` con seña; dos cancelaciones concurrentes (una 200, una 410). **Verifica:** los 5 escenarios de `Confirmar o cancelar desde el enlace`.
- [x] 7.3 **Verde**: implementar `GET /reservar/gestion/{token}`, `POST .../confirmar`, `POST .../cancelar` con `verify_single_use_token`/`consume_single_use_token` y la regla de plazo. **Verifica:** 7.1 y 7.2 en verde.

## 8. WhatsApp best-effort (R-06, US-001/CA-3)

- [x] 8.1 **Rojo**: tests con un Redis falso inyectado: encolado exitoso informa `encolada` y llama `RPUSH whatsapp:send`; fallo/timeout informa `pendiente_reintento` y la reserva sigue 201. **Verifica:** los 2 escenarios de `Confirmación por WhatsApp best-effort`.
- [x] 8.2 **Verde**: agregar `get_redis` inyectable y el encolado best-effort en la reserva. **Verifica:** 8.1 en verde.

## 9. Página pública y de gestión (R-07)

- [x] 9.1 **Rojo**: tests de componentes: `/reservar` carga catálogo y muestra profesionales/prestaciones; reserva exitosa muestra enlace y seña; error 409/422 se muestra verbatim; `/reservar/gestion/:token` muestra resumen y acciones. **Verifica:** los 4 escenarios de `Página pública de reserva`.
- [x] 9.2 **Verde**: implementar `features/reserva/api.ts`, `ReservaPage`, `GestionTurnoPage`, `postJson` y las rutas en `App.tsx`. **Verifica:** 9.1 en verde con `npm test`/`vitest`.

## 10. Verificación integrada

- [x] 10.1 Suite completa backend (`pytest backend/tests`) + frontend (`npm test`) y matriz escenario → test en `docs/skills-mcp/evidencias/c-07-verificacion-escenarios.md`.
- [x] 10.2 Levantar el stack, ejecutar smoke público (catálogo, disponibilidad, reserva, solape 409, seña pendiente, reuso/vencimiento de token, confirmar/cancelar, WhatsApp encolado/pendiente), limpiar datos de smoke y agregar las pruebas manuales a `docs/validacion-manual-pendiente.md`. Cerrar/archivar/commitear según el proceso acordado.
