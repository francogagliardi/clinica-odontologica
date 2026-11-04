# Tasks

> Cada tarea declara **cómo se verifica** y qué escenario de spec cubre. Ciclo R-09: rojo antes de verde.
> Cobertura total: **46 escenarios** (36 en `agenda/turnos` y 10 en la disponibilidad modificada de `agenda/recursos-agendables`).
> Governance **CRÍTICO**: la constraint de exclusión y la prueba de concurrencia son obligatorias; no se acepta solo validación en aplicación.
> **Proceso acordado con el usuario (2026-11-03)**: la validación manual se acumula para el final; cada change se cierra con suite completa + smoke de API y se registra en `docs/validacion-manual-pendiente.md`.

## 0. Preparación y dependencias

- [x] 0.1 Auditar las delta specs con la skill `spec-scenario-auditor` y verificar `openspec validate c-06-turnos-anti-solapamiento --strict`. Evidencia: `docs/skills-mcp/evidencias/skill-audit-c-06.md`.
- [x] 0.2 Confirmar head `0005_pacientes_cobertura_base`, PostgreSQL descartable en `127.0.0.1:15432` y que el usuario `clinica` puede `CREATE EXTENSION btree_gist`. **Verifica:** `alembic current`, `docker compose ps` y `CREATE EXTENSION IF NOT EXISTS btree_gist` en una transacción de prueba.

## 1. Modelo `Turno`, plazo de cancelación y migración `0006` (R-01, R-04, R-10)

- [x] 1.1 **Rojo**: tests unitarios en `backend/tests/unit/test_models_metadata.py`: tabla `turnos`, columnas, FKs, CHECKs (`fin > inicio`, estados, orígenes, coherencia de sobreturno/color, `plazo_cancelacion_horas`), constraints de exclusión `ex_turnos_profesional`/`ex_turnos_sillon` e índices `(profesional_id, inicio)`, `(sillon_id, inicio)`, `estado`, `uq_turnos_token_publico`. **Verifica:** estructura del esquema vía `Base.metadata`.
- [x] 1.2 **Rojo**: actualizar `backend/tests/test_migrations_env.py` y `backend/tests/integration/test_migration.py` al head `0006`, 1 tabla nueva y columna nueva; agregar upgrade/downgrade `0006` ⇄ `0005` y verificación de `btree_gist` + constraints por SQL. **Verifica:** `pytest tests/test_migrations_env.py tests/integration/test_migration.py`.
- [x] 1.3 **Verde**: implementar `Turno` en `backend/app/models/agenda.py`, `Consultorio.plazo_cancelacion_horas`, registrar en `__init__.py` y crear `0006_turnos_anti_solapamiento.py` con `CREATE EXTENSION IF NOT EXISTS btree_gist`, las dos constraints de exclusión y downgrade en orden inverso. **Verifica:** 1.1 y 1.2 en verde.

## 2. Dominio puro de turnos (R-01, R-10)

- [x] 2.1 **Rojo**: tests unitarios en `backend/tests/unit/test_turnos_domain.py`: cálculo de `fin` con prestación y sin prestación, ventana de agenda (día inhábil, inicio antes de hora_desde, fin después de hora_hasta, borde exacto permitido), solapamiento `[inicio, fin)` (consecutivos no solapan, contenidos y parciales sí), y matriz de transiciones válidas/terminales/idempotentes. **Verifica:** funciones puras de `app/domain/turnos.py`.
- [x] 2.2 **Verde**: implementar `app/domain/turnos.py` (`calcular_fin`, `validar_ventana`, `se_solapan`, `puede_transicionar`, `ESTADOS_ACTIVOS`, `ESTADOS_TERMINALES`). **Verifica:** 2.1 en verde.

## 3. Schemas de turno (R-02, R-10)

- [x] 3.1 **Rojo**: tests unitarios en `backend/tests/unit/test_turnos_schemas.py`: `extra='forbid'`, estado inicial fijo, origen válido, `fin` rechazado si lo manda el cliente, color hex obligatorio con sobreturno y prohibido sin él, reprogramación con al menos un campo. **Verifica:** validadores de `app/schemas/turnos.py`.
- [x] 3.2 **Verde**: implementar `app/schemas/turnos.py` (`TurnoCreate`, `TurnoReprogramar`, `TurnoEstadoUpdate`, `TurnoResponse`, `TurnoListado`). **Verifica:** 3.1 en verde.

## 4. Alta de turno con duración y recursos (R-02, RN-TU-02)

- [x] 4.1 **Rojo**: tests de integración en `backend/tests/integration/test_turnos.py`: alta con prestación (fin correcto, 201, estado `reservado`), alta sin prestación (duración base), recurso inexistente/baja (404 por cada uno), fuera de agenda (422), `fin <= inicio` rechazado también por CHECK, campos extra/estado/origen inválidos (422). **Verifica:** los 6 escenarios de `Alta de turno con duración derivada`.
- [x] 4.2 **Verde**: implementar `TurnoRepository` (alta, lectura, listado por rango), wiring en `UnitOfWork`, `app/api/turnos.py` (POST, GET lista, GET ficha) y montar el router en `main.py`. **Verifica:** 4.1 en verde.

## 5. Anti-solapamiento transaccional (RN-TU-01, R-10)

- [x] 5.1 **Rojo**: tests de integración: mismo profesional solapado (409), mismo sillón con otro profesional (409), consecutivos permitidos (201), recursos distintos en el mismo horario (201), cancelado/ausente no bloquea (201), dos altas concurrentes con `asyncio.gather` (una 201 y una 409, una sola fila) y `INSERT` directo solapado rechazado con SQLSTATE `23P01`. **Verifica:** los 7 escenarios de `Anti-solapamiento por profesional y por sillón`.
- [x] 5.2 **Verde**: implementar `list_solapados` con `inicio < fin AND fin > inicio`, traducción de `23P01` a 409 y chequeo previo con `exclude_id`. **Verifica:** 5.1 en verde, incluida la carrera real.

## 6. Sobreturnos (RN-TU-06)

- [x] 6.1 **Rojo**: tests: sobreturno con color sobre slot ocupado (201 y respuesta marcada), sin color (422), color sin marca (422), turno normal contra sobreturno existente (409) y constraint de base que no rechaza el sobreturno. **Verifica:** los 4 escenarios de `Sobreturno con marca y color explícitos`.
- [x] 6.2 **Verde**: completar la validación de sobreturno en schemas/servicio y asegurar que las constraints de exclusión usan `NOT es_sobreturno` en el predicado. **Verifica:** 6.1 en verde.

## 7. Bloqueos (RN-TU-07, R-10)

- [x] 7.1 **Rojo**: tests: solape con bloqueo de profesional (409), con bloqueo de sillón (409), bloqueo adyacente permitido (201) y bloqueo de otro recurso sin efecto (201). **Verifica:** los 4 escenarios de `Los bloqueos impiden reservar`.
- [x] 7.2 **Verde**: integrar `BloqueoRepository` en la validación de alta y reprogramación usando el mismo criterio de solapamiento. **Verifica:** 7.1 en verde.

## 8. Estados y reprogramación (RN-TU-01/03, R-10)

- [x] 8.1 **Rojo**: tests: transiciones válidas (`reservado→confirmado→en_sala→atendido`), transiciones inválidas (422 y estado intacto), cancelación desde `reservado`/`confirmado`, repetir estado (200 idempotente), turno inexistente/ajeno (404); reprogramación libre (200 con fin recalculado), a slot ocupado (409 y original intacto), fuera de agenda (422), sobre bloqueo (409), turno terminal (422) y reprogramaciones concurrentes (una 200, una 409). **Verifica:** los 5 escenarios de `Máquina de estados del turno` y los 5 de `Reprogramación con la misma garantía`.
- [x] 8.2 **Verde**: implementar `PATCH /turnos/{id}/estado` con la matriz de transiciones y `PATCH /turnos/{id}/reprogramar` con recálculo y validaciones completas. **Verifica:** 8.1 en verde.

## 9. Disponibilidad real y RBAC (RN-TU-01, RN-SE-01)

- [x] 9.1 **Rojo**: tests: turno activo oculta el slot, cancelado/ausente lo libera, turno de otro profesional no afecta, día completo devuelve `[]`; actualizar los tests de C-04 al nuevo parámetro de turnos. **Verifica:** los 10 escenarios de `Disponibilidad base por profesional` y que los 6 originales siguen pasando.
- [x] 9.2 **Rojo**: tests de RBAC: recepción crea/reprograma/cambia estado (201/200), odontólogo opera su turno (200) y recibe 403 en el ajeno y al crear, asistente/auditor solo leen (200/403) y sin token 401. **Verifica:** los 5 escenarios de `Acceso a turnos por rol`.
- [x] 9.3 **Verde**: integrar turnos activos en `app/domain/agenda.py`, consultarlos en el endpoint de disponibilidad y aplicar los guards RBAC/propiedad en `app/api/turnos.py`. **Verifica:** 9.1 y 9.2 en verde.

## 10. Verificación integrada del change

- [x] 10.1 Ejecutar la suite completa (`pytest backend/tests`) con `TEST_DATABASE_URL` descartable y registrar la matriz escenario → test en `docs/skills-mcp/evidencias/c-06-verificacion-escenarios.md`.
- [x] 10.2 Levantar el stack (`docker compose up -d --build`), ejecutar el smoke de API del flujo de turnos (alta, 409 por solape, sobreturno, bloqueo, estados, reprogramación, disponibilidad real y 401), limpiar los datos de smoke y agregar las pruebas manuales pendientes a `docs/validacion-manual-pendiente.md`. Cerrar, archivar y commitear sin esperar validación manual (decisión del usuario 2026-11-03); la aceptación funcional queda en la prueba final de la página completa.
