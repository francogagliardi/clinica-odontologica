# Tasks

> ConvenciÃ³n: cada grupo empieza en rojo (test que falla) y cierra en verde. Los tests de integraciÃ³n usan PostgreSQL real vÃ­a `TEST_DATABASE_URL`; los unitarios no tocan red ni base.
> Decisiones de diseÃ±o: `design.md` D1â€“D14. Escenarios: `specs/fiscal/comprobantes-arca` y `specs/comercial/liquidaciones-obras-sociales`.
> Preguntas abiertas de `design.md` Â§Open Questions: antes de 9.2, confirmar con el usuario la fuente de "prÃ¡ctica realizada" y si se acepta liquidar con la OS actual del paciente; si cambian, se ajusta la consulta de 9.2 sin cambiar la API. El resto del plan no depende de ellas.

## 1. ConfiguraciÃ³n, modelos y migraciÃ³n

- [x] 1.1 Agregar `arca_provider`, `arca_punto_venta`, `arca_condicion_emisor`, `arca_max_intentos` y `arca_worker_interval_seconds` a `Settings`, documentarlos en `backend/.env.example` y en el entorno falso de `backend/tests/conftest.py`; verificar con un test que falle si `ARCA_PROVIDER` es invÃ¡lido y con `pytest backend/tests/test_settings.py -q`.
- [x] 1.2 Escribir en rojo `backend/tests/integration/test_fiscal_migracion.py`: espera las tablas `comprobantes`, `comprobantes_envios`, `secuencias_comprobantes`, `liquidaciones_obras_sociales`, `items_liquidacion`, sus CHECKs, Ã­ndices Ãºnicos y el head `0013_facturacion_arca`; confirmar que falla antes de crear la migraciÃ³n.
- [x] 1.3 Implementar `backend/app/models/fiscal.py` con `Comprobante`, `ComprobanteEnvio` y `SecuenciaComprobante`, y `backend/app/models/liquidaciones.py` con `LiquidacionObraSocial` e `ItemLiquidacion`, usando `AuditMixin`, los CHECKs de D12 y los Ã­ndices Ãºnicos parciales; registrarlos en `models/__init__.py` y verificar el test de metadatos.
- [x] 1.4 Crear `backend/alembic/versions/0013_facturacion_arca.py` (`down_revision='0012_caja_cobros'`) con las cinco tablas, la exclusion constraint de perÃ­odo y `btree_gist` ya existente; verificar `alembic upgrade head` + `downgrade 0012_caja_cobros` + `upgrade head` sin errores.
- [x] 1.5 Verificar por SQL directo los rechazos: segundo comprobante del mismo cobro (`23505`), CAE duplicado (`23505`), nÃºmero fiscal duplicado (`23505`), nÃºmero interno duplicado (`23505`), `importe <= 0` y estado fiscal incoherente (`23514`), y perÃ­odo solapado (`23P01`); cada caso con su assert en `test_fiscal_migracion.py`.

## 2. Dominio puro fiscal y de liquidaciones

- [x] 2.1 Escribir en rojo `backend/tests/unit/test_fiscal_dominio.py`: QR fiscal decodificable (CAE, punto de venta, nÃºmero, importe), QR interno sin CAE, transiciones `pendienteâ†’emitido|fallido`, `emitido` terminal, backoff exponencial y fecha de emisiÃ³n UTC-3.
- [x] 2.2 Implementar `backend/app/domain/fiscal.py` con el constructor/decodificador de QR, la mÃ¡quina de estados, el cÃ¡lculo de `proximo_intento` y los helpers de fecha; verificar el test unitario sin base ni red.
- [x] 2.3 Escribir en rojo `backend/tests/unit/test_liquidaciones_dominio.py`: suma de coberturas, cantidad de prÃ¡cticas, transiciÃ³n `borradorâ†’cerrada`, cierre idempotente y perÃ­odo vÃ¡lido/invertido/contiguo.
- [x] 2.4 Implementar `backend/app/domain/liquidaciones.py` con las transiciones y los totales; verificar el test unitario.

## 3. Proveedor ARCA simulado

- [x] 3.1 Escribir en rojo `backend/tests/unit/test_arca_provider.py`: CAE de 14 dÃ­gitos determinista por clave, vencimiento, mismo CAE en dos llamadas, fallo inyectable, cliente con `ARCA_PROVIDER != 'test'` que falla explÃ­citamente, y ausencia de sockets/lectura de certificados.
- [x] 3.2 Implementar `backend/app/infrastructure/arca.py` con `ResultadoEmision`, `ArcaClient`, `TestArcaClient` y `get_arca_client(settings)`; exponer la dependencia en `api/deps.py`; verificar el test unitario y que un test de integraciÃ³n no toca la red.

## 4. Repositorios y UnitOfWork

- [x] 4.1 Escribir en rojo `backend/tests/integration/test_fiscal_repos.py`: comprobante por cobro, pendientes vencidos, claim con token y vencimiento, secuencia interna/fiscal, liquidaciÃ³n con Ã­tems y bÃºsqueda de Ã­tems ya liquidados.
- [x] 4.2 Implementar `ComprobanteRepository`, `ComprobanteEnvioRepository`, `SecuenciaComprobanteRepository`, `LiquidacionRepository` e `ItemLiquidacionRepository` en `infrastructure/repositories.py` y exponerlos en `UnitOfWork`; verificar los tests de repositorio en verde.

## 5. CreaciÃ³n del comprobante y hooks de cobro

- [x] 5.1 Escribir en rojo `backend/tests/integration/test_comprobantes_efectivo.py`: cobro en efectivo 201 con comprobante `pendiente`, nÃºmero interno, tipo B, importe y QR interno; cobro pendiente/rechazado sin comprobante; alta rechazada sin comprobante ni numeraciÃ³n consumida.
- [x] 5.2 Implementar `application/comprobantes.crear_para_cobro` (snapshot del receptor, tipo segÃºn emisor, secuencia interna, QR interno, auditorÃ­a `comprobante.crear`) y el hook en `application/cobros.crear_cobro`; verificar los escenarios de alta en efectivo.
- [x] 5.3 Escribir en rojo `backend/tests/integration/test_comprobantes_mp.py`: webhook aprobado crea un comprobante; webhook rechazado no crea; webhook repetido no duplica; aprobaciÃ³n concurrente deja un solo comprobante.
- [x] 5.4 Implementar el hook en `application/cobros.conciliar_pago` dentro de la misma transacciÃ³n del cobro; verificar los escenarios de Mercado Pago.
- [x] 5.5 Escribir en rojo `backend/tests/integration/test_comprobantes_numeracion.py`: dos altas concurrentes obtienen nÃºmeros distintos y consecutivos, una transacciÃ³n revertida no consume nÃºmero, y el nÃºmero fiscal reciÃ©n se asigna al persistir el Ã©xito.
- [x] 5.6 Implementar el servicio de secuencias con `UPDATE ... RETURNING` y los Ã­ndices Ãºnicos; verificar numeraciÃ³n interna/fiscal y concurrencia.
- [x] 5.7 Escribir en rojo `backend/tests/integration/test_comprobantes_creacion_auditoria.py`: `comprobante.crear` con usuario en efectivo y actor sistema en webhook, y ausencia de auditorÃ­a cuando el cobro se rechaza; implementar y verificar en el mismo grupo.

## 6. Worker `arca:emitir`, reintentos e idempotencia

- [x] 6.1 Escribir en rojo `backend/tests/integration/test_arca_worker.py`: procesa un job encolado, emite y persiste CAE/QR/nÃºmero fiscal; `emitido` no vuelve a llamar; fallo incrementa `intentos` y `proximo_intento` con backoff; al llegar al mÃ¡ximo queda `fallido` con el Ãºltimo error.
- [x] 6.2 Implementar `application/comprobantes.procesar_comprobante` con claim por token, llamada al proveedor fuera de la transacciÃ³n y persistencia `emitido|fallido` (incluida auditorÃ­a `comprobante.emitir`/`comprobante.emitir_fallido`); verificar los escenarios de emisiÃ³n y reintento.
- [x] 6.3 Escribir en rojo los escenarios de concurrencia e idempotencia: dos workers reclaman el mismo comprobante y solo uno emite; el mismo id aparece dos veces en la cola y hay un solo CAE; el CAE se obtiene pero falla la persistencia y el reintento devuelve el mismo CAE.
- [x] 6.4 Implementar el vencimiento del claim (`reclamado_at` + 5 minutos), el descarte seguro de resultados sin claim vigente y la unicidad de CAE; verificar concurrencia, job duplicado y fallo de persistencia.
- [x] 6.5 Escribir en rojo el escenario de barrido sin Redis: con `arca:emitir` vacÃ­o o Redis caÃ­do (incluido un error de `BRPOP`), el worker encuentra los `pendiente` vencidos y los procesa; implementar el barrido tolerante a Redis y verificar que un comprobante `pendiente` no se pierde.
- [x] 6.6 Agregar el modo `arca` a `backend/app/workers/__main__.py` (`run_once_arca`, loop y `--once`), reutilizando `ARCA_WORKER_INTERVAL_SECONDS`; verificar con un test de entrypoint y un `python -m app.workers arca --once` contra la base de test.

## 7. API de comprobantes, envÃ­o y reintento manual

- [x] 7.1 Escribir en rojo `backend/tests/integration/test_comprobantes_api.py`: `GET /comprobantes?cobro_id&paciente_id&estado&desde&hasta&tipo` devuelve el comprobante, `GET /comprobantes/{id}` lo detalla con CAE/QR cuando corresponde, y un filtro no declarado responde 422.
- [x] 7.2 Implementar `schemas/comprobantes.py` (bordes `extra='forbid'`), `api/comprobantes.py` y los filtros con `reject_unexpected_query_except`; verificar consulta y borde estricto.
- [x] 7.3 Escribir en rojo los escenarios de envÃ­o: comprobante `emitido` 201 con `canal='whatsapp'`, destino, estado y proveedor de prueba; repeticiÃ³n 200 sin duplicar envÃ­o ni auditorÃ­a; `pendiente|fallido` 409; destino invÃ¡lido 422; cero llamadas de red.
- [x] 7.4 Implementar `POST /comprobantes/{id}/enviar`, `ComprobanteEnvio` y la llamada a `TestWhatsAppClient` con plantilla `"factura"`; verificar los escenarios de envÃ­o.
- [x] 7.5 Escribir en rojo los escenarios de reintento manual: `fallido` vuelve a `pendiente` y encola, `emitido` es no-op 200, inexistente 404; implementar `POST /comprobantes/{id}/reintentar` y verificar.

## 8. ValidaciÃ³n preventiva de cobertura

- [x] 8.1 Escribir en rojo `backend/tests/integration/test_cobertura.py`: prÃ¡ctica cubierta 60/40 con montos, paciente sin OS `no_cubierta`, prÃ¡ctica fuera del convenio `no_cubierta`, convenio inactivo/sin reglas `pendiente_verificacion` con montos nulos, paciente con OS pero sin `nro_afiliado` `pendiente_verificacion`, paciente/prestaciÃ³n inexistente 404 y cero escrituras.
- [x] 8.2 Implementar `application/cobertura.py` reutilizando `get_cobertura_provider()` y `calcular_item`, `schemas/cobertura.py` y el router `GET /obras-sociales/cobertura` antes de `/{obra_social_id}`; verificar los escenarios de cobertura.
- [x] 8.3 Escribir en rojo el escenario "solo local": sin topes/frecuencias/nomenclador en la respuesta y sin llamada externa; verificar con un proveedor inyectado que no se invoca red y que un convenio sin reglas nunca inventa cobertura.

## 9. Liquidaciones de obras sociales

- [x] 9.1 Escribir en rojo `backend/tests/integration/test_liquidaciones_alta.py`: alta con Ã­tems trazables a presupuesto/Ã­tem/cobro y total correcto, sin prÃ¡cticas 422, pagos parciales sin duplicar, Ã­tem ya liquidado excluido, Ã­tems con cobertura 0 o de otra OS excluidos, presupuesto sin cobro aprobado en el perÃ­odo excluido.
- [x] 9.2 Implementar `application/liquidaciones.crear` con la selecciÃ³n de D9, snapshots y totales; verificar los escenarios de alta y trazabilidad.
- [x] 9.3 Escribir en rojo `backend/tests/integration/test_liquidaciones_periodo.py`: perÃ­odo de un dÃ­a vÃ¡lido, fechas invertidas 422, solapamiento 409, solapamiento por SQL directo `23P01`, perÃ­odos contiguos permitidos y obra social inexistente/inactiva 404.
- [x] 9.4 Implementar la validaciÃ³n de perÃ­odo y la exclusion constraint; verificar los escenarios de perÃ­odo.
- [x] 9.5 Escribir en rojo `backend/tests/integration/test_liquidaciones_estado.py`: cierre 200 con totales congelados, cierre repetido idempotente, ediciÃ³n/borrado de cerrada 409, borrado de borrador 204 que libera perÃ­odo, y recepciÃ³n no cierra.
- [x] 9.6 Implementar `cerrar`, `actualizar observaciones` y borrado lÃ³gico de borrador con sus guards; verificar los escenarios de estado.
- [x] 9.7 Escribir en rojo los escenarios de consulta: listado por obra social/estado/perÃ­odo, ficha con Ã­tems y totales, y filtro no declarado 422; implementar `schemas/liquidaciones.py` y `api/liquidaciones.py`; verificar.

## 10. RBAC y auditorÃ­a transversal

- [x] 10.1 Escribir en rojo `backend/tests/integration/test_comprobantes_rbac.py`: lectura para administrador/recepciÃ³n/odontÃ³logo/auditor, reintento y envÃ­o para administrador/recepciÃ³n, asistente 403, odontÃ³logo 403 en escritura y peticiÃ³n sin token 401.
- [x] 10.2 Implementar los guards `require_role` en los endpoints de comprobantes y verificar la matriz completa.
- [x] 10.3 Escribir en rojo `backend/tests/integration/test_liquidaciones_rbac.py` y los casos de cobertura: lectura por los cuatro roles, alta/cierre/borrado solo administrador, observaciones administrador/recepciÃ³n, odontÃ³logo 403 en escritura, asistente 403 y 401 sin token.
- [x] 10.4 Implementar los guards de liquidaciones y cobertura; verificar la matriz completa.
- [x] 10.5 Escribir en rojo `backend/tests/integration/test_fiscal_auditoria.py`: acciones `comprobante.crear`, `comprobante.emitir`, `comprobante.emitir_fallido`, `comprobante.reintentar`, `comprobante.enviar`, `liquidacion.crear`, `liquidacion.editar`, `liquidacion.cerrar` y `liquidacion.eliminar` con usuario/IP/dispositivo, sin auditorÃ­a en escrituras rechazadas y append-only (`P0001`).
- [x] 10.6 Implementar las llamadas a `infrastructure/audit.registrar` en todos los casos de uso y verificar las nueve acciones y los rechazos.

## 11. IntegraciÃ³n final, smoke y evidencia

- [x] 11.1 Correr la suite backend completa (`pytest backend/tests -q`) y confirmar que no hay regresiones en C-01..C-13.
- [x] 11.2 Correr el ciclo de migraciÃ³n sobre base descartable (`upgrade head` â†’ `downgrade 0012_caja_cobros` â†’ `upgrade head`) y verificar que el esquema queda idÃ©ntico.
- [x] 11.3 Levantar el stack (`docker compose up -d --build`) y ejecutar el smoke: cobrar efectivo, consultar comprobante pendiente, correr el worker `arca`, verificar CAE/QR, enviar por WhatsApp simulado, validar cobertura y crear/cerrar una liquidaciÃ³n.
- [x] 11.4 Guardar evidencia en `docs/skills-mcp/evidencias/c-14/` (salidas de tests, `curl` del smoke y verificaciÃ³n de migraciÃ³n) y dejar una matriz que confirme que cada escenario de las dos specs tiene al menos un test o tarea que lo cubre.
- [x] 11.5 Ejecutar `openspec validate c-14-facturacion-arca-obras-sociales --strict` y confirmar que no hay warnings de escenarios, longitud de requirements ni propÃ³sito.

## Workflow follow-up

- Cerrar el change segÃºn la decisiÃ³n del usuario del 2026-11-03 (sin gate de aprobaciÃ³n manual por change): con la suite, el smoke y la evidencia en verde, archivar con `/opsx:archive`.
- Marcar `[x]` en `CHANGES.md` Â§C-14 y corregir la migraciÃ³n indicada (`0013_facturacion_arca`, no `008b`).
- Commit y push del cierre con conventional-commits, sin co-autorÃ­a IA (solo cuando el usuario lo pida).
