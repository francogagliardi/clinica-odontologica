# Tasks

> Convención: cada grupo empieza en rojo (test que falla) y cierra en verde. Los tests de integración usan PostgreSQL real vía `TEST_DATABASE_URL`; los unitarios no tocan red ni base.
> Decisiones: `design.md` D1–D15. Escenarios: `specs/reportes/reportes`, `specs/reportes/exportacion` y `specs/platform/job-queues`.
> Las dos preguntas abiertas de `design.md` no bloquean: C-15 verifica contra un dataset determinista de tests y no purga artefactos. Si el usuario decide lo contrario para el seed, se ajusta 11.3 sin cambiar la API.

## 1. Configuración, cuarta cola, modelos y migración

- [x] 1.1 Escribir en rojo `backend/tests/test_queues.py` y `backend/tests/test_settings.py`: `ALL_QUEUES` contiene cuatro nombres incluido `reportes:generar`, ningún otro nombre hardcodeado, y las cinco variables nuevas de exportación/reportes existen con sus defaults; confirmar que fallan antes de tocar el código.
- [x] 1.2 Implementar `REPORTES_GENERAR` en `backend/app/core/queues.py`, las variables `exportacion_max_filas`, `exportacion_max_bytes`, `exportacion_max_intentos`, `reportes_worker_interval_seconds` y `exportacion_claim_timeout_seconds` en `Settings`, documentarlas en `backend/.env.example` y en el entorno falso de `backend/tests/conftest.py`, y pinear `fpdf2` en `backend/requirements.txt`; verificar con `pytest backend/tests/test_queues.py backend/tests/test_settings.py -q` y con `python -c "import fpdf"` dentro de la imagen/entorno.
- [x] 1.3 Escribir en rojo `backend/tests/integration/test_reportes_migracion.py`: espera la tabla `exportaciones`, sus CHECKs (`alcance_paciente_coherente`, `estado_coherente`, `intentos>=0`), los índices `ix_exportaciones_estado_proximo`, `ix_exportaciones_consultorio_fecha`, `ix_exportaciones_paciente`, el índice único parcial `uq_exportaciones_en_curso` y el head `0014_reportes`; confirmar que falla antes de crear la migración.
- [x] 1.4 Implementar `backend/app/models/reportes.py` con `Exportacion` (sin `AuditMixin`, sin baja lógica) y registrarlo en `models/__init__.py`; verificar el test de metadatos.
- [x] 1.5 Crear `backend/alembic/versions/0014_reportes.py` (`down_revision='0013_facturacion_arca'`) con la tabla, CHECKs e índices; verificar `alembic upgrade head` → `downgrade 0013_facturacion_arca` → `upgrade head` sin errores.
- [x] 1.6 Verificar por SQL directo en `test_reportes_migracion.py`: alcance sin `paciente_id` rechazado (`23514`), `paciente_id` con alcance consultorio rechazado (`23514`), `lista` sin contenido rechazada (`23514`), `fallida` sin `ultimo_error` rechazada (`23514`), y dos exportaciones en curso idénticas rechazadas (`23505`).

## 2. Dominio puro de reportes y artefacto

- [x] 2.1 Escribir en rojo `backend/tests/unit/test_reportes_dominio.py`: cálculo de `ocupacion_porcentaje` (incluido denominador cero), tasas de ausentismo con denominador cero, `sin_agenda`/`sin_cierres`, redondeo a dos decimales y backoff exponencial del job con tope.
- [x] 2.2 Implementar `backend/app/domain/reportes.py` con las fórmulas puras, el cálculo de `proximo_intento` y los helpers de fecha UTC-3; verificar el test unitario sin base ni red.
- [x] 2.3 Escribir en rojo `backend/tests/unit/test_exportacion_artefacto.py`: nombres de archivo del ZIP (`exportacion.pdf`, `datos.json`, `manifiesto.json`, `csv/<entidad>.csv`, `adjuntos/<id>_<nombre>`), saneamiento de nombres, conteos del manifiesto y lista de exclusiones.
- [x] 2.4 Implementar en `backend/app/domain/reportes.py` (o módulo vecino) las constantes de entidades, la lista de campos excluidos y el saneamiento de nombres; verificar el test unitario.
- [x] 2.5 Escribir en rojo un test que verifique que el PDF contiene la firma `%PDF-`, al menos una página y el aviso de truncación cuando una sección supera 500 filas; implementar el armado de secciones con `fpdf2` en `backend/app/infrastructure/exportacion.py` y verificar.

## 3. Repositorios, consultas agregadas y UnitOfWork

- [x] 3.1 Escribir en rojo `backend/tests/integration/test_reportes_repos.py`: agregados de agenda por estado/profesional/sillón, minutos disponibles y ocupados, tasas de ausentismo, cobros por medio/estado, movimientos por tipo, cajas del rango y liquidaciones que cruzan el período.
- [x] 3.2 Implementar `ConsultaReportesRepository` (o métodos dedicados) en `backend/app/infrastructure/repositories.py` con SQLAlchemy 2.x y agregados en SQL; exponerlo en `UnitOfWork`; verificar los tests con `EXPLAIN` manual sobre el dataset de prueba.
- [x] 3.3 Escribir en rojo `backend/tests/integration/test_exportaciones_repos.py`: alta, `get`, listado por consultorio/estado/alcance, exportación en curso por combinación, claim con token/vencimiento y pendientes vencidos.
- [x] 3.4 Implementar `ExportacionRepository` en `repositories.py` y exponerlo en `UnitOfWork`; verificar los tests de repositorio en verde.
- [x] 3.5 Documentar en `docs/` (o docstring del repositorio) las fórmulas SQL de D8 y verificar que cada agregado tiene un test que compara contra valores de fuente independiente.

## 4. Reportes de agenda y ausentismo

- [x] 4.1 Escribir en rojo `backend/tests/integration/test_reportes_agenda.py` contra un dataset determinista: 3 atendidos + 1 cancelado + 1 ausente, dos profesionales y dos sillones; totales por estado, ocupación 50 % con 480 minutos disponibles, sobreturnos fuera de la ocupación, rango de 62 días aceptado y 63 días rechazado con 422, turno de las 23:30 UTC-3 contado en el día local.
- [x] 4.2 Implementar `application/reportes.agenda` y `schemas/reportes.py` con los bordes estrictos; verificar los escenarios de agenda.
- [x] 4.3 Escribir en rojo `backend/tests/integration/test_reportes_ausentismo.py`: 6 atendidos + 2 cancelados + 2 ausentes → tasas 0.40/0.20, 5 activos fuera de la tasa, rango sin cierres → 0.00 con `sin_cierres=true`, detalle con paciente/profesional/fecha local y filtro por profesional.
- [x] 4.4 Implementar `application/reportes.ausentismo`; verificar los escenarios de ausentismo y que no se divide por cero.

## 5. Reportes de caja y liquidaciones

- [x] 5.1 Escribir en rojo `backend/tests/integration/test_reportes_caja.py`: 2 efectivo + 1 MP aprobados → 23000.00/15000.00/8000.00; pendiente/rechazado/reembolsado/perdido no suman ingreso; gasto y deuda separados; caja cerrada con diferencia 0.00 y caja abierta con cierre nulo; `medio` inválido y parámetro extra → 422.
- [x] 5.2 Implementar `application/reportes.caja`; verificar los escenarios de caja y que no se recalcula el arqueo de una caja abierta.
- [x] 5.3 Escribir en rojo `backend/tests/integration/test_reportes_liquidaciones.py`: dos liquidaciones (cerrada 60000.00/3 y borrador 20000.00/1) → agregados por estado y por OS; cruce de período octubre/noviembre incluido; prácticas por prestación (`OBT=2`, `CONS=1`); rango vacío; OS de otro consultorio 404; ítem con baja lógica excluido.
- [x] 5.4 Implementar `application/reportes.liquidaciones`; verificar los escenarios de liquidaciones y que los totales de cabecera y de ítems coinciden.

## 6. Bordes, límites y RBAC de reportes

- [x] 6.1 Escribir en rojo `backend/tests/integration/test_reportes_bordes.py`: `limite=500` sobre 1200 filas devuelve 500 con `total_detalle=1200` y totales completos; orden estable por `inicio,id`; `limite=0`, `limite=1001`, `desde` faltante, `desde>hasta` y filtro no declarado → 422; metadatos `generado_en/desde/hasta/zona_horaria`.
- [x] 6.2 Implementar la validación de rango/límite y la metadata común en `schemas/reportes.py` y `application/reportes.py`; verificar los escenarios de borde.
- [x] 6.3 Escribir en rojo `backend/tests/integration/test_reportes_rbac.py`: administrador los cuatro reportes; odontólogo agenda/ausentismo/caja propios y 403 con otro `profesional_id`; odontólogo lee liquidaciones; recepción agenda/ausentismo/caja 200 y liquidaciones 403; auditor los cuatro 200; asistente 403; sin token 401; lectura no agrega auditoría ni modifica filas.
- [x] 6.4 Implementar los guards `require_role` y la resolución del profesional propio en `api/reportes.py`; verificar la matriz completa.

## 7. Generador del artefacto y privacidad

- [x] 7.1 Escribir en rojo `backend/tests/integration/test_exportacion_contenido.py`: ZIP con `exportacion.pdf`, `datos.json`, `manifiesto.json` y CSV por entidad; conteos del manifiesto iguales a JSON/CSV; adjunto de 2 MB incluido como binario; paciente sin datos clínicos exporta secciones vacías sin fallar; PDF `%PDF-` con totales.
- [x] 7.2 Implementar el recolector de entidades por paciente y por consultorio en `application/exportaciones.py` y el armado ZIP/JSON/CSV/PDF en `infrastructure/exportacion.py`; verificar el test de contenido.
- [x] 7.3 Escribir en rojo los escenarios de secretos: inspeccionar todos los archivos y afirmar ausencia de `hash_password`, valores de `token_publico`, tokens de un solo uso, `claim_token`, `link_pago`, secretos de webhook y payloads de proveedores; verificar que CAE/QR fiscal sí están.
- [x] 7.4 Implementar la lista de exclusión en el serializador y el `manifiesto.exclusiones`; verificar el test de secretos y que el directorio de usuarios del consultorio incluye id/nombre/email/roles sin hash.
- [x] 7.5 Escribir en rojo los límites: `EXPORTACION_MAX_FILAS` por entidad y `EXPORTACION_MAX_BYTES` producen `fallida` con `ultimo_error` que nombra el límite, sin ZIP parcial; implementar la verificación y verificar.

## 8. Solicitud, idempotencia, descarga y auditoría

- [x] 8.1 Escribir en rojo `backend/tests/integration/test_exportaciones_api.py`: paciente 202, paciente inexistente/inactivo/ajeno 404, alcance inválido/campo extra 422; consultorio 202 sin rango, `paciente_id` con consultorio 422; estado de otro consultorio 404.
- [x] 8.2 Implementar `schemas/exportaciones.py`, `api/exportaciones.py` (`POST`, `GET` listado, `GET /{id}`) y `application/exportaciones.solicitar`; verificar los escenarios de alta y estado.
- [x] 8.3 Escribir en rojo la idempotencia: dos POST idénticos en curso devuelven el mismo `id` y un solo job; un POST nuevo tras `fallida` o `lista` crea otra exportación; descarga `lista` 200 `application/zip`; `pendiente|generando|fallida` → 409 con el error.
- [x] 8.4 Implementar el índice único en curso, la reutilización de la fila existente, el endpoint `/archivo` y la auditoría `exportacion.solicitar`/`exportacion.descargar`; verificar los escenarios de idempotencia y descarga.
- [x] 8.5 Escribir en rojo `backend/tests/integration/test_exportaciones_rbac.py`: administrador ambos alcances; odontólogo paciente propio 202 y paciente sin vínculo 403; odontólogo consultorio 403; recepción/asistente/auditor 403; sin token 401; listado/estado/archivo ajeno 404 sin filtrar datos.
- [x] 8.6 Implementar los guards y el filtro `solicitado_por` para no administradores; verificar la matriz completa.

## 9. Worker `reportes`

- [x] 9.1 Escribir en rojo `backend/tests/integration/test_reportes_worker.py`: el POST 202 no espera al worker y deja `pendiente` sin artefacto; el worker deja `lista` con `tamano_bytes` y `generada_at`; el mismo id dos veces no duplica artefacto ni retrocede de `lista`; dos workers reclaman y solo uno genera.
- [x] 9.2 Implementar `application/exportaciones.procesar` con claim por token, generación fuera de la transacción y persistencia condicionada al claim; verificar los escenarios de generación y concurrencia.
- [x] 9.3 Escribir en rojo fallos y barrido: fallo transitorio incrementa `intentos` y `proximo_intento` con backoff; al máximo queda `fallida` con `ultimo_error`; con `reportes:generar` vacío o Redis caído (incluido error de `BRPOP`) el barrido procesa pendientes vencidos; auditoría `exportacion.generar`/`exportacion.fallida` con usuario nulo.
- [x] 9.4 Implementar el backoff, el tope, el barrido tolerante a Redis y la auditoría del worker; verificar los escenarios de fallo y recuperación.
- [x] 9.5 Agregar el modo `reportes` a `backend/app/workers/__main__.py` (`run_once_reportes`, loop y `--once`) usando `REPORTES_WORKER_INTERVAL_SECONDS`; verificar con un test de entrypoint y `python -m app.workers reportes --once` contra la base de test.

## 10. UI funcional de reportes

- [x] 10.1 Escribir en rojo `frontend/src/features/reportes/api.test.ts` y `frontend/src/pages/ReportesPage.test.tsx`: render de totales desde una API mockeada, error 403 mostrado verbatim, selector de rango/filtros, botón exportar que sondea hasta `lista` y habilita la descarga, y ausencia de sumas locales.
- [x] 10.2 Implementar `frontend/src/features/reportes/api.ts` con tipos y fetches autenticados (`authHeaders()`), y `ReportesPage.tsx` con login reutilizado, cuatro tableros, filtros, tabla de detalle y exportación con sondeo limpiado al desmontar; agregar la ruta `/reportes` en `App.tsx`.
- [x] 10.3 Verificar `npm run test`, `npm run typecheck` y `npm run build` en `frontend/`, sin `any` y sin lógica de negocio en el cliente (R-07).

## 11. Integración final, smoke y evidencia

- [x] 11.1 Escribir en rojo una matriz de trazabilidad `docs/skills-mcp/evidencias/c-15/matriz-escenarios.md` que liste cada escenario de las tres specs y el test/tarea que lo cubre; confirmar que no hay escenarios sin cobertura.
- [x] 11.2 Correr la suite backend completa (`pytest backend/tests -q`) y confirmar que no hay regresiones en C-01..C-14; correr `npm run test` y `npm run typecheck` en `frontend/`.
- [x] 11.3 Correr el ciclo de migración sobre base descartable (`upgrade head` → `downgrade 0013_facturacion_arca` → `upgrade head`) y verificar que el esquema queda idéntico.
- [x] 11.4 Levantar el stack (`docker compose up -d --build`), correr el worker `reportes` y ejecutar el smoke: login admin, abrir `/reportes`, verificar los cuatro tableros, exportar un paciente y el consultorio, esperar `lista`, descargar el ZIP y validar PDF/JSON/CSV y la ausencia de secretos.
- [x] 11.5 Guardar evidencia en `docs/skills-mcp/evidencias/c-15/` (salidas de tests, `curl` del smoke, ZIP de muestra y verificación de migración) y ejecutar `openspec validate c-15-reportes-exportacion --strict` sin warnings.

## Workflow follow-up

- Archivar el change cuando la suite, el smoke y la evidencia estén en verde, según la decisión del usuario del 2026-11-03 (sin gate de aprobación manual por change); el cierre no incluye diseño visual, que es C-17.
- Marcar `[x]` en `CHANGES.md` §C-15 y registrar la migración `0014_reportes` (no una `008b`).
- Commit y push del cierre con conventional-commits y sin co-autoría IA, solo cuando el usuario lo pida (R-13).
