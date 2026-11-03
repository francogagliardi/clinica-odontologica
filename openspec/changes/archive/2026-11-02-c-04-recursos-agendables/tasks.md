# Tasks

> Cada tarea declara **cómo se verifica** y qué escenario de spec cubre. Ciclo R-09: rojo antes de verde, un slice vertical por ciclo.
> Cobertura total: **44 escenarios** (18 en `agenda/recursos-agendables`, 10 en `comercial/prestaciones`, 16 en `agenda/bloqueos`).
> Governance **MEDIO**: no requiere aprobación previa de diseño, pero sí el gate R-14 antes de archivar.

## 0. Preparación y dependencias (R-09, R-14)

- [x] 0.1 Auditar las delta specs con la skill `spec-scenario-auditor` y verificar formato con `openspec validate c-04-recursos-agendables --strict`. Evidencia: `docs/skills-mcp/evidencias/skill-audit-c-04.md`.
- [x] 0.2 Confirmar que `0003_tokens_un_solo_uso` es el head de migraciones y que el Compose/PostgreSQL descartable responde en `127.0.0.1:15432`. **Verifica:** `alembic current` y `docker compose ps` sin errores.

## 1. Modelos y migración `0004_recursos_agendables` (R-01, R-04, R-05)

- [x] 1.1 **Rojo**: tests unitarios en `backend/tests/unit/test_models_metadata.py` para las 5 tablas nuevas (`profesionales`, `sillones`, `profesionales_sillones`, `prestaciones`, `bloqueos`): columnas, PK, FKs, CHECKs (`baja_logica_coherente`, XOR de bloqueo, rango de bloqueo, seña coherente, duración/precio) e índices únicos parciales y de consulta. **Verifica:** estructura observable del esquema, base de `Profesional`, `Sillon`, `Prestacion` y `Bloqueo`.
- [x] 1.2 **Rojo**: actualizar `backend/tests/test_migrations_env.py` y `backend/tests/integration/test_migration.py` para el nuevo head y las 5 tablas; agregar upgrade/downgrade bidireccional (`0004` ⇄ `0003`). **Verifica:** `pytest tests/test_migrations_env.py tests/integration/test_migration.py`.
- [x] 1.3 **Verde**: implementar `backend/app/models/agenda.py` (`Profesional`, `Sillon`, `ProfesionalSillon`, `Bloqueo`) y `backend/app/models/comercial.py` (`Prestacion`), registrar en `backend/app/models/__init__.py` y crear `backend/alembic/versions/0004_recursos_agendables.py` con `down_revision = "0003_tokens_un_solo_uso"` y downgrade en orden inverso. **Verifica:** 1.1 y 1.2 en verde.

## 2. Profesionales: CRUD con RBAC y unicidad (R-02, R-03, RN-SE-01)

- [x] 2.1 **Rojo**: tests de integración en `backend/tests/integration/test_profesionales.py`: alta admin (201) + lectura recepcionista (200), matrícula duplicada (409), escritura por odontólogo/recepcionista/asistente/auditor (403), baja lógica que libera matrícula, `agenda_config` inválida (422 por cada variante: duración ≤ 0, días vacíos/fuera de rango/duplicados, `hora_hasta <= hora_desde`) y `usuario_id` ya vinculado (409). **Verifica:** los 6 escenarios de `Registro de profesionales con agenda configurada`.
- [x] 2.2 **Verde**: implementar `ProfesionalRepository`, wiring en `UnitOfWork`, `backend/app/schemas/recursos.py` (`AgendaConfig`, `ProfesionalCreate/Update/Response` con `extra='forbid'`), `backend/app/api/profesionales.py` y montar el router en `backend/app/main.py`. **Verifica:** 2.1 en verde con `pytest tests/integration/test_profesionales.py`.

## 3. Sillones y habilitación idempotente (R-02, R-03, RN-TU-01)

- [x] 3.1 **Rojo**: tests en `backend/tests/integration/test_sillones.py`: alta y listado (201/200), nombre duplicado (409), escritura por no administrador (403), baja lógica que libera nombre, habilitación repetida con una sola fila y dos respuestas 204, habilitación con profesional/sillón inexistente o inactivo (404). **Verifica:** los 6 escenarios de `Sillones y habilitación idempotente profesional ↔ sillón`.
- [x] 3.2 **Verde**: implementar `SillonRepository` y `ProfesionalSillonRepository` (alta `ON CONFLICT DO NOTHING`, listado por profesional/sillón, baja del vínculo), schemas y `backend/app/api/sillones.py` con las rutas de habilitación. **Verifica:** 3.1 en verde con `pytest tests/integration/test_sillones.py`.

## 4. Prestaciones y seña opcional (R-02, R-03, RN-TU-02, RN-TU-08, DD-10)

- [x] 4.1 **Rojo**: tests en `backend/tests/integration/test_prestaciones.py`: alta admin + lectura recepcionista (201/200), código duplicado (409), escritura por no administrador (403), baja lógica que libera código, duración ≤ 0 y precio < 0 (422), seña con monto visible, `requiere_sena=true` sin monto (422), `requiere_sena=false` con monto (422), monto ≤ 0 (422) y quitar la seña dejando `monto_sena = null` (200). **Verifica:** los 10 escenarios de `comercial/prestaciones`.
- [x] 4.2 **Verde**: implementar `PrestacionRepository`, schemas con validador de seña, `backend/app/api/prestaciones.py` (GET lista, POST, PUT, DELETE lógico) y montaje del router. **Verifica:** 4.1 en verde con `pytest tests/integration/test_prestaciones.py`.

## 5. Bloqueos: CRUD, XOR, rango y propiedad (R-02, R-03, R-10, RN-TU-07)

- [x] 5.1 **Rojo**: tests en `backend/tests/integration/test_bloqueos.py`: recepcionista crea bloqueo de profesional (201), dos recursos o ninguno (422), `hasta <= desde` (422), recurso inexistente/inactivo (404), bloqueos solapados permitidos, odontólogo bloquea su propio profesional (201/204), odontólogo bloquea otro profesional (403), odontólogo bloquea sillón (403), asistente/auditor escriben (403) y odontólogo sobre un profesional con `usuario_id` nulo (403). **Verifica:** los 10 escenarios de `Alta de bloqueo por profesional o por sillón` y `Control de acceso a bloqueos por rol y propiedad`.
- [x] 5.2 **Verde**: implementar `BloqueoRepository` (listado por rango y recurso, alta, baja lógica), schemas con validación XOR y rango, `backend/app/api/bloqueos.py` con la regla de propiedad (`profesionales.usuario_id == current_user.id`) y montaje del router. **Verifica:** 5.1 en verde con `pytest tests/integration/test_bloqueos.py`.

## 6. Dominio de disponibilidad base (R-01, RN-TU-02, RN-TU-07)

- [x] 6.1 **Rojo**: tests unitarios en `backend/tests/unit/test_agenda_domain.py` con fechas fijas y offset `UTC-3`: día no habilitado → lista vacía, slots consecutivos con duración de prestación, duración base sin prestación, último slot incompleto descartado, exclusión por bloqueo de profesional, bloqueo fuera de horario sin efecto, bloqueo de otro profesional sin efecto y bloqueo de sillón al consultar con sillón. **Verifica:** los 6 escenarios de `Disponibilidad base por profesional` y 5 de `Efecto del bloqueo en la disponibilidad` (lógica pura).
- [x] 6.2 **Verde**: implementar `backend/app/domain/agenda.py` como función pura (sin I/O) reutilizable por C-06. **Verifica:** 6.1 en verde con `pytest tests/unit/test_agenda_domain.py`.
- [x] 6.3 **Rojo + verde**: test de integración `backend/tests/integration/test_disponibilidad.py` para `GET /profesionales/{id}/disponibilidad`: 200 con slots, 404 de profesional inexistente/inactivo, 404 de sillón inexistente/inactivo, 200 con lista vacía por día no habilitado, 422 por fecha inválida/parámetros extra y 404 por prestación inexistente/inactiva. **Verifica:** el escenario de borde de `Disponibilidad base por profesional` y el de error de negocio de `Efecto del bloqueo en la disponibilidad` contra la base real.

## 7. Seed demo extendido (R-08, DD-11)

- [x] 7.1 **Rojo**: actualizar `backend/tests/integration/test_seed.py`: 2 sillones (`Sillón 1`, `Sillón 2`) y 5 prestaciones (`CONS`, `LIM`, `OBT`, `ENDO`, `EXO`) con duraciones 30/45/60/90/60, precios ficticios y `ENDO` con `requiere_sena = true` y `monto_sena > 0`; re-ejecutar no duplica ni reescribe datos. **Verifica:** seed idempotente y catálogo mínimo de `04_modelo_de_datos.md` §Seed.
- [x] 7.2 **Verde**: extender `backend/app/seed.py` con `ON CONFLICT DO NOTHING` sobre los índices parciales y resolver el `consultorio_id` demo. **Verifica:** 7.1 en verde con `pytest tests/integration/test_seed.py`.

## 8. Verificación integrada del change (R-14)

- [x] 8.1 Ejecutar la suite completa (`pytest backend/tests`) con `TEST_DATABASE_URL` descartable y registrar la matriz escenario → test en `docs/skills-mcp/evidencias/c-04-verificacion-escenarios.md`.
- [x] 8.2 Levantar Docker Compose (`docker compose up -d --build`), entregar la lista de pruebas manuales y el resumen en lenguaje no técnico, y esperar aprobación explícita antes de archivar, marcar `[x]` en `CHANGES.md` y commitear/pushear (R-14). Aprobado por el usuario el 2026-11-02.
