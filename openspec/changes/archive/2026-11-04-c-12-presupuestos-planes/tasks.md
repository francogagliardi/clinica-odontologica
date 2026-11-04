# Tasks

## 0. Confirmación de alcance

- [x] 0.1 Confirmar con el usuario la decisión D8 sobre consentimiento: (a) diferir la exigencia al registro de la práctica (alcance actual) o (b) agregar `requiere_consentimiento` a `Prestacion` y gatear la aceptación. **Confirmado (a) el 2026-11-04**: no se gatea la aceptación; el consentimiento se exige al registrar la práctica.

## 1. Dominio puro del presupuesto (TDD)

- [x] 1.1 Escribir `backend/tests/unit/test_presupuestos_domain.py` con transiciones rojas: válidas (`borrador→aceptado`, `borrador→rechazado`, `aceptado→en_curso`, `en_curso→finalizado`), inválidas (`borrador→en_curso`, `aceptado→rechazado`, desde `rechazado`/`finalizado`, destino `borrador`) e idempotencia del estado actual; verificar que falla porque `app/domain/presupuestos.py` no existe
- [x] 1.2 Implementar `_TRANSICIONES`, `ESTADOS`, `ESTADOS_COBERTURA` y `puede_transicionar` en `app/domain/presupuestos.py`; verificar `pytest backend/tests/unit/test_presupuestos_domain.py -q` en verde
- [x] 1.3 Agregar tests rojos de cálculo: 60 % sobre 2 × 10.000,00 → cobertura 12.000,00 y copago 8.000,00; cobertura 0 % y 100 %; sin convenio; redondeo `33,33 × 60 % = 20,00` con copago 13,33; totales iguales a la suma; `cobertura_item + copago_item = total_item` sobre una lista de precios variados
- [x] 1.4 Implementar `calcular_item` y `calcular_presupuesto` con `Decimal`, `quantize` y `ROUND_HALF_UP`; verificar 1.3 en verde y que el invariante de suma se cumple sin excepciones

## 2. Modelos y migración `0011_presupuestos`

- [x] 2.1 Ampliar `backend/tests/unit/test_models_metadata.py` para exigir las tablas `presupuestos` e `items_presupuesto`, sus FKs y los nombres de CHECKs/índices de design D3; verificar rojo
- [x] 2.2 Crear `Presupuesto` e `ItemPresupuesto` en `app/models/comercial.py` (con `AuditMixin`) y exportarlos en `app/models/__init__.py`; verificar los tests de metadata en verde
- [x] 2.3 Ampliar `backend/tests/integration/test_migration.py` para exigir head `0011_presupuestos`, tablas, índices y CHECKs, y que `downgrade 0010_historia_clinica` las elimine; verificar rojo
- [x] 2.4 Escribir a mano `backend/alembic/versions/0011_presupuestos.py` con `down_revision = "0010_historia_clinica"`, tablas, índices y CHECKs; verificar `alembic upgrade head` y el test de 2.3
- [x] 2.5 Agregar tests de integración rojos por SQL directo: `cantidad=0` → `23514`, pieza `19/49/86` → `23514`, `cobertura_item + copago_item ≠ precio_unitario * cantidad` → `23514`, `subtotal ≠ cobertura_calculada + copago` → `23514`, baja lógica incoherente → `23514`; verificar que la migración los rechaza
- [x] 2.6 Documentar en la migración qué CHECK cubre cada invariante y el orden de borrado del downgrade; verificar `alembic downgrade 0010_historia_clinica` y `alembic upgrade head` sin pérdida de tablas de C-01–C-11

## 3. Repositorios y UnitOfWork

- [x] 3.1 Escribir tests de integración rojos de `PresupuestoRepository`/`ItemPresupuestoRepository`: `get` con solo ítems activos, listado por paciente/profesional/estado ordenado descendente y baja lógica de ítems reemplazados
- [x] 3.2 Implementar ambos repositorios en `app/infrastructure/repositories.py` y registrarlos en `app/infrastructure/uow.py`; verificar 3.1 en verde

## 4. Cobertura y alta de presupuesto

- [x] 4.1 Escribir tests rojos de `LocalCoberturaProvider`: paciente sin obra social → cobertura conocida de 0 %, convenio activo con porcentaje y prestación cubierta, prestación fuera de la lista, porcentaje ausente → `None`, convenio con baja lógica → `None`, reglas no interpretables → `None`
- [x] 4.2 Implementar `CoberturaConvenio`, `CoberturaNoDisponible`, `CoberturaProvider`, `LocalCoberturaProvider` y `get_cobertura_provider` en `app/application/presupuestos.py`; verificar 4.1 en verde
- [x] 4.3 Escribir tests de integración rojos de `POST /presupuestos`: 201 con OS Demo y dos ítems (cobertura 12.000,00), paciente sin obra social, prestación no cubierta, 422 con `precio_unitario`/totales en el cuerpo, 422 sin ítems, 404 de paciente/profesional/prestación inexistente o inactivo, 422 por `cantidad <= 0` y por pieza FDI inválida
- [x] 4.4 Implementar `app/schemas/presupuestos.py`, el servicio de alta y `app/api/presupuestos.py` (solo `POST` por ahora), registrando el router en `app/main.py`; verificar 4.3 en verde
- [x] 4.5 Escribir tests rojos del modo pendiente: convenio sin porcentaje, convenio inactivo y proveedor que lanza `CoberturaNoDisponible` mediante `app.dependency_overrides[get_cobertura_provider]`; deben responder 201 con `pendiente_verificacion`, cobertura 0 y filas persistidas
- [x] 4.6 Implementar la captura de `CoberturaNoDisponible` y el armado del resultado pendiente en el servicio; verificar 4.5 en verde
- [x] 4.7 Agregar aserción SQL de totales tras el alta (`subtotal = cobertura_calculada + copago` y encabezado = suma de ítems) y verificar que una cobertura del 0 % no se confunde con pendiente

## 5. Consulta, edición y recálculo

- [x] 5.1 Escribir tests rojos de `GET /presupuestos` y `GET /presupuestos/{id}`: ficha con ítems y totales, filtros por paciente/profesional/estado, orden descendente, 422 por query desconocida y 404 por presupuesto inexistente o de otro consultorio
- [x] 5.2 Implementar listado y ficha; verificar 5.1 en verde
- [x] 5.3 Escribir tests rojos de `PUT /presupuestos/{id}`: reemplazo total con recálculo, 409 fuera de `borrador` sin cambios, 422 con importes del cliente, cambio de paciente que recalcula contra la nueva cobertura y re-snapshot del `precio_base` vigente
- [x] 5.4 Implementar el `PUT` del borrador con baja lógica de los ítems reemplazados y re-snapshot de precios; verificar 5.3 en verde
- [x] 5.5 Escribir tests rojos de `POST /presupuestos/{id}/recalcular`: pendiente → calculada tras definir `cobertura_porcentaje`, precios sin cambios, 409 fuera de `borrador` y 422 con campos extra en el cuerpo
- [x] 5.6 Implementar el recálculo de cobertura (sin tocar precios); verificar 5.5 en verde
- [x] 5.7 Agregar tests de snapshot: cambio de `precio_base` en el catálogo no altera un presupuesto existente ni uno aceptado, y la baja lógica de la prestación no rompe la ficha; verificar en verde

## 6. Estados y baja lógica

- [x] 6.1 Escribir tests rojos de `PATCH /presupuestos/{id}/estado`: camino completo, saltos inválidos 422, estados terminales 422, destino inexistente/`borrador` 422 e idempotencia 200 sin auditoría extra
- [x] 6.2 Implementar el cambio de estado reutilizando `puede_transicionar`; verificar 6.1 en verde
- [x] 6.3 Escribir tests rojos de `DELETE /presupuestos/{id}`: 204 sobre borrador, 409 sobre aceptado y desaparición del listado; implementar y verificar en verde

## 7. RBAC

- [x] 7.1 Escribir `backend/tests/integration/test_presupuestos_rbac.py` en rojo: administrador CRUD sobre cualquier profesional, odontólogo propio 201 y ajeno 403, odontólogo sin fila en `profesionales` 403, `profesional_id` ajeno en el cuerpo 403, recepción lectura 200 y escritura 403, asistente y auditor lectura 200 y escritura 403, paciente sin turno vigente 403, presupuesto de otro odontólogo 403 y sin token 401
- [x] 7.2 Implementar `require_role` y los helpers de propiedad de design D9 en todos los endpoints; verificar 7.1 en verde

## 8. Auditoría

- [x] 8.1 Escribir tests rojos de auditoría: `presupuesto.crear`, `editar`, `recalcular`, `eliminar`, `aceptar`, `rechazar`, `en_curso` y `finalizar` con usuario, IP y `User-Agent`; rechazos (422/403/409) sin fila; `UPDATE`/`DELETE` directo sobre la auditoría → `P0001`
- [x] 8.2 Instrumentar `audit.registrar` en el servicio dentro de la misma transacción; verificar 8.1 en verde y que la suite de auditoría de C-02 sigue verde

## 9. Integración, smoke y evidencia

- [x] 9.1 Correr la suite completa `pytest backend/tests -q` contra PostgreSQL real y verificar todo en verde sin tests omitidos por dependencia de base
- [x] 9.2 Levantar `docker compose up -d --build`, correr `alembic upgrade head` y ejecutar un smoke HTTP: alta con OS Demo, alta con convenio sin reglas (pendiente), aceptación de un pendiente, edición de borrador, recálculo tras corregir las reglas, transición inválida (422), `PUT` fuera de borrador (409), escritura por recepción (403) y revisión de filas de auditoría; guardar comandos y salidas
- [x] 9.3 Escribir `docs/skills-mcp/evidencias/c-12-verificacion-escenarios.md` con la matriz requirement→escenario→test→resultado, incluyendo SQLSTATE observados (`23514`, `P0001`) y el resultado del smoke
- [x] 9.4 Ejecutar `openspec validate c-12-presupuestos-planes --strict` y corregir cualquier warning de descripción o escenario hasta que pase
- [x] 9.5 Preparar el resumen en lenguaje no técnico (qué se aplicó, qué no cambia, qué se probó y qué falta) y agregar el bloque C-12 a `docs/validacion-manual-pendiente.md`; cierre sin espera de prueba manual por change, según la decisión del usuario (2026-11-03)

## Workflow follow-up

- Bajar el stack si no se está usando.
- Cerrar con suite + smoke + resumen no técnico y archivar/marcar `CHANGES.md`/commitear/pushear según el proceso acordado (2026-11-03), sin espera de prueba manual por change.
- Archivar el change, marcar `[x]` en `CHANGES.md` y commitear/pushear el cierre sin co-autoría IA (R-13), solo cuando el usuario lo pida.
