# Tasks

> Convención: cada grupo empieza en rojo (test que falla) y cierra en verde. Los tests de integración usan PostgreSQL real vía `TEST_DATABASE_URL`; los unitarios no tocan red ni base.
> Decisiones de diseño: `design.md` D1–D12. Escenarios: `specs/caja/cobros`, `specs/caja/arqueo`, `specs/agenda/turnos`.

## 1. Configuración y migración base

- [x] 1.1 Agregar `mp_provider: str = "test"` y `mp_webhook_secret: str` a `Settings`, documentarlos en `backend/.env.example` y en el entorno falso de `backend/tests/conftest.py`; verificar con `pytest backend/tests/test_settings.py -q` y un test nuevo que falle si falta `MP_WEBHOOK_SECRET`.
- [x] 1.2 Escribir el test de migración en rojo (`backend/tests/integration/test_caja_migracion.py`): espera las tablas `cobros`, `cajas_diarias`, `movimientos_caja`, sus CHECKs e índices únicos, y el head `0012_caja_cobros`; verificar que falla antes de crear la migración.
- [x] 1.3 Implementar `backend/app/models/caja.py` (`Cobro`, `CajaDiaria`, `MovimientoCaja`) con `AuditMixin`, CHECKs de D9 e índices únicos parciales de D7; registrarlos en `models/__init__.py`.
- [x] 1.4 Crear `backend/alembic/versions/0012_caja_cobros.py` (`down_revision='0011_presupuestos'`) y verificar `alembic upgrade head` + `alembic downgrade 0011_presupuestos` + `upgrade head` sin errores.
- [x] 1.5 Verificar por SQL directo los rechazos: segunda seña viva (`23505`), `proveedor_pago_id` duplicado (`23505`), dos movimientos para el mismo cobro (`23505`), `monto <= 0` (`23514`) y combinación tipo/referencias inválida (`23514`).

## 2. Dominio puro de caja y cobros

- [x] 2.1 Escribir en rojo `backend/tests/unit/test_caja_dominio.py`: fecha local UTC-3 (incluido el cruce `02:30Z`), cálculo de `monto_sistema_efectivo`, diferencia de cierre, transiciones válidas de cobro y reglas de monto/tipo/referencias.
- [x] 2.2 Implementar `backend/app/domain/caja.py` con `fecha_local()`, totales de arqueo, diferencia y validadores puros; verificar que el test unitario pasa sin base ni red.

## 3. Repositorios y UnitOfWork

- [x] 3.1 Escribir en rojo tests de repositorio (`backend/tests/integration/test_caja_repos.py`): búsqueda de seña viva por turno, suma de cobros de tratamiento aprobados, caja por consultorio/fecha, movimientos por caja y bloqueo `FOR UPDATE` al cerrar.
- [x] 3.2 Implementar `CobroRepository`, `CajaDiariaRepository` y `MovimientoCajaRepository` en `infrastructure/repositories.py` y exponerlos en `UnitOfWork`; verificar los tests de repositorio en verde.

## 4. Proveedor de Mercado Pago y firma

- [x] 4.1 Escribir en rojo `backend/tests/unit/test_mercadopago_provider.py`: preferencia simulada con `test-pref-*`, link ficticio, `consultar_pago` desde el diccionario de simulación, fallo explícito con `MP_PROVIDER != 'test'` y cero llamadas de red.
- [x] 4.2 Implementar `backend/app/infrastructure/mercadopago.py` con `MercadoPagoClient`, `PagoNormalizado` y `TestMercadoPagoClient`; verificar el test unitario.
- [x] 4.3 Escribir en rojo `backend/tests/unit/test_mercadopago_firma.py` para HMAC válido, firma adulterada, encabezado ausente y `ts` fuera de tolerancia.
- [x] 4.4 Implementar el validador de firma (`x-signature` `ts`/`v1`) contra `MP_WEBHOOK_SECRET` y la dependencia de proveedor en `api/deps.py`; verificar los cuatro casos de firma.

## 5. Alta de cobros en efectivo

- [x] 5.1 Escribir en rojo `backend/tests/integration/test_cobros_efectivo.py`: alta 201 aprobada con movimiento de ingreso, monto 0/negativo 422, campo extra 422, paciente inexistente/inactivo 404 y caja cerrada 409.
- [x] 5.2 Implementar `schemas/caja.py` (bordes `extra='forbid'`), `application/cobros.py` (validación de paciente y alta efectivo) y `api/cobros.py` (`POST /cobros`); verificar los escenarios de alta en efectivo.
- [x] 5.3 Implementar la resolución de la caja del día: cobro en efectivo y movimiento manual exigen caja abierta (409 si no existe o está cerrada), la conciliación de Mercado Pago crea la caja con apertura 0 y la carrera por único `(consultorio_id, fecha)` se resuelve releyendo; verificar los escenarios de caja automática, sin caja y caja cerrada.

## 6. Seña y tratamiento

- [x] 6.1 Escribir en rojo `backend/tests/integration/test_cobros_sena.py`: seña válida marca `Turno.sena_estado='pagada'`, prestación sin `requiere_sena` 422, turno sin prestación 422, monto distinto 422, turno cancelado/ausente 422, segunda seña viva 409, reintento tras `rechazado` 201 y concurrencia 201/409.
- [x] 6.2 Implementar la validación de seña en `application/cobros.py` (turno activo, prestación, `monto_sena`, único lógico) y la conciliación `pagada` en la misma transacción; verificar los escenarios de seña.
- [x] 6.3 Escribir en rojo `backend/tests/integration/test_cobros_tratamiento.py`: pago parcial 201 con saldo, presupuesto `borrador|rechazado|finalizado` 409, exceso sobre `copago` 409, paciente distinto 422, presupuesto ajeno 404 y pagos parciales que suman exactamente el copago.
- [x] 6.4 Implementar la validación de tratamiento contra presupuesto y el cálculo de `saldo_pendiente`; verificar los escenarios de tratamiento.

## 7. Webhook y conciliación Mercado Pago

- [x] 7.1 Escribir en rojo `backend/tests/integration/test_cobros_mp.py`: alta MP 201 `pendiente` con link, proveedor no disponible 503 sin cobro huérfano y respuesta sin secretos.
- [x] 7.2 Implementar `POST /cobros` con `medio='mercadopago'`, creación de preferencia y persistencia de `proveedor_preferencia_id`/`link_pago`; verificar los escenarios de preferencia.
- [x] 7.3 Escribir en rojo `backend/tests/integration/test_webhook_mp.py`: aprobado concilia cobro/seña/movimiento, rechazado no cobra, duplicado 200 sin segundo ingreso, tardío sobre reembolsado/perdido 200 sin cambio, monto/moneda distinta 409, referencia desconocida 404, segundo pago para seña aprobada 409 y firma inválida 401.
- [x] 7.4 Implementar `POST /webhooks/mercadopago` público: firma, `consultar_pago`, conciliación transaccional, idempotencia por `proveedor_pago_id` con captura de `23505` y auditoría `cobro.conciliar`; verificar todos los escenarios del webhook.

## 8. Pérdida de seña y paridad de agenda

- [x] 8.1 Escribir en rojo `backend/tests/integration/test_sena_perdida.py`: cancelación tardía desde backoffice marca `perdida` y el cobro `perdido`; cancelación dentro del plazo conserva `pagada`; límite exacto no pierde; `ausente` pierde; turno `no_requiere` no cambia; repetición idempotente; cancelación pública mantiene la política.
- [x] 8.2 Implementar en `api/turnos.py` el cálculo de plazo para `cancelado` y la pérdida para `ausente`, y en `api/publico.py` el hook posterior a `Turno.sena_estado='perdida'`.
- [x] 8.3 Implementar `sincronizar_sena_perdida` en `application/cobros.py` (cobro vivo → `perdido`, sin reversión de ingreso, auditoría `cobro.perder`) y verificar los escenarios de pérdida.

## 9. Caja diaria y arqueo

- [x] 9.1 Escribir en rojo `backend/tests/integration/test_caja_arqueo.py`: apertura 201, segunda apertura 409, apertura negativa 422, movimiento a las 23:30 local en el día correcto, gasto/deuda suman, ingreso de cobro duplicado 409, movimiento sobre caja cerrada 409, arqueo con efectivo/MP/deudas separados y fecha sin caja con ceros.
- [x] 9.2 Implementar `application/caja.py` y `api/caja.py` para abrir, listar movimientos y consultar arqueo; verificar los escenarios de apertura, movimientos y arqueo.
- [x] 9.3 Escribir en rojo los escenarios de cierre: cuadrado 200, faltante 409, sobrante 409, repetido 409, `monto_contado` inválido 422 y fecha sin caja 404.
- [x] 9.4 Implementar `POST /caja/cerrar` con snapshot `monto_sistema_efectivo`, bloqueo `FOR UPDATE`, diferencia cero obligatoria y auditoría `caja.cerrar`; verificar los escenarios de cierre.

## 10. RBAC y auditoría

- [x] 10.1 Escribir en rojo `backend/tests/integration/test_caja_rbac.py`: administrador, recepción CRU sin borrado, odontólogo solo cobros propios (ficha ajena 403), asistente 403 en cobros y caja, auditor solo lectura, odontólogo 403 en caja y petición sin token 401 salvo webhook.
- [x] 10.2 Implementar los guards `require_role` y el filtro "propio" del odontólogo por `turno.profesional_id`/`presupuesto.profesional_id`; verificar la matriz completa.
- [x] 10.3 Escribir en rojo `backend/tests/integration/test_caja_auditoria.py`: `cobro.crear`, `cobro.conciliar`, `cobro.reembolsar`, `cobro.perder`, `caja.abrir`, `caja.movimiento` y `caja.cerrar` con usuario/IP/dispositivo, sin auditoría en escrituras rechazadas y append-only (`P0001`).
- [x] 10.4 Implementar las llamadas a `infrastructure/audit.registrar` en cada caso de uso y verificar las siete acciones y los rechazos.

## 11. Reembolso y consulta

- [x] 11.1 Escribir en rojo los escenarios de reembolso y consulta: reembolso 200 con auditoría, estados no aprobados 409, repetición idempotente, sin llamada al proveedor, inexistente 404, listado con filtros declarados y 422 por filtro no declarado.
- [x] 11.2 Implementar `POST /cobros/{id}/reembolsar`, `GET /cobros` y `GET /cobros/{id}` con `reject_unexpected_query_except`; verificar los escenarios.

## 12. Integración final, smoke y evidencia

- [x] 12.1 Correr la suite backend completa (`pytest backend/tests -q`) y confirmar que no hay regresiones en C-01..C-12.
- [x] 12.2 Correr el ciclo de migración sobre base descartable (`upgrade head` → `downgrade 0011` → `upgrade head`) y verificar que el esquema queda idéntico.
- [x] 12.3 Levantar el stack (`docker compose up -d --build`) y ejecutar el smoke: abrir caja, cobrar efectivo, crear seña MP, simular webhook aprobado, consultar arqueo y cerrar cuadrado.
- [x] 12.4 Guardar evidencia en `docs/skills-mcp/evidencias/c-13/` (salidas de tests, `curl` del smoke y verificación de migración) y verificar que cada escenario de las tres specs tiene al menos una tarea o test que lo cubre.
- [x] 12.5 Ejecutar `openspec validate c-13-caja-cobros-mercadopago --strict` y confirmar que no hay warnings de escenarios ni de longitud de requirements.

## Workflow follow-up

- Cerrar el change según la decisión del usuario del 2026-11-03 (sin gate de aprobación manual por change): con la suite, el smoke y la evidencia en verde, archivar con `/opsx:archive`.
- Marcar `[x]` en `CHANGES.md` §C-13 y actualizar la migración indicada (`0012_caja_cobros`, no `008a`).
- Commit y push del cierre con conventional-commits, sin co-autoría IA (solo cuando el usuario lo pida).
