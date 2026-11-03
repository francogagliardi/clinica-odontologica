# Tasks

> Cada tarea declara **cómo se verifica** y qué escenario de spec cubre. Ciclo R-09: rojo antes de verde, un slice vertical por ciclo.
> Cobertura total: **38 escenarios** (22 en `pacientes/registro-pacientes`, 16 en `comercial/obras-sociales`).
> Governance **MEDIO**: no requiere aprobación previa de diseño, pero sí el gate R-14 antes de archivar.

## 0. Preparación y dependencias (R-09, R-14)

- [x] 0.1 Auditar las delta specs con la skill `spec-scenario-auditor` y verificar formato con `openspec validate c-05-pacientes-cobertura-base --strict`. Evidencia: `docs/skills-mcp/evidencias/skill-audit-c-05.md`.
- [x] 0.2 Confirmar que `0004_recursos_agendables` es el head de migraciones y que el PostgreSQL descartable responde en `127.0.0.1:15432`. **Verifica:** `alembic current` y `docker compose ps` sin errores.

## 1. Modelos y migración `0005_pacientes_cobertura_base` (R-01, R-04, R-05)

- [x] 1.1 **Rojo**: tests unitarios en `backend/tests/unit/test_models_metadata.py` para `pacientes` y `obras_sociales`: columnas, PK, FKs, CHECKs (baja lógica, DNI `^[0-9]{7,8}$`, teléfono `^\+549[0-9]{10}$`, cobertura coherente, nombre no vacío, `jsonb_typeof`, `validacion_externa = false`) e índices únicos parciales y de búsqueda (`lower(apellido)`, `(consultorio_id, telefono)`, `lower(nombre)`). **Verifica:** estructura observable del esquema, base de `Paciente` y `ObraSocial`.
- [x] 1.2 **Rojo**: actualizar `backend/tests/test_migrations_env.py` y `backend/tests/integration/test_migration.py` para el nuevo head `0005` y las 2 tablas; agregar upgrade/downgrade bidireccional (`0005` ⇄ `0004`). **Verifica:** `pytest tests/test_migrations_env.py tests/integration/test_migration.py`.
- [x] 1.3 **Verde**: implementar `backend/app/models/pacientes.py` (`Paciente`), extender `backend/app/models/comercial.py` (`ObraSocial`), registrar en `backend/app/models/__init__.py` y crear `backend/alembic/versions/0005_pacientes_cobertura_base.py` con `down_revision = "0004_recursos_agendables"` y downgrade en orden inverso. **Verifica:** 1.1 y 1.2 en verde.

## 2. Dominio y schemas de entrada (R-01, R-02)

- [x] 2.1 **Rojo**: tests unitarios en `backend/tests/unit/test_pacientes_domain.py`: `normalizar_dni` (7/8 dígitos, puntos/espacios/guiones, rechazo de 6/9 dígitos y letras) y `normalizar_telefono` (10 dígitos nacionales, `+54 9 …` con separadores, rechazo de fijo 54 sin 9, longitudes inválidas y caracteres no numéricos). **Verifica:** funciones puras de `app/domain/pacientes.py` con entrada/salida explícita.
- [x] 2.2 **Rojo**: tests unitarios de schemas en `backend/tests/unit/test_pacientes_schemas.py`: `extra='forbid'`, teléfono obligatorio o vacío (422), `nro_afiliado` sin obra social (422), `ReglasCobertura` (porcentajes fuera de rango, suma > 100, códigos duplicados, tipo no objeto, `validacion_externa=true`). **Verifica:** validadores de `app/schemas/pacientes.py` aislados del HTTP.
- [x] 2.3 **Verde**: implementar `backend/app/domain/pacientes.py` (funciones puras) y `backend/app/schemas/pacientes.py` (`PacienteCreate/Update/Response`, `BusquedaPaciente`, `ObraSocialCreate/Update/Response`, `ReglasCobertura`). **Verifica:** 2.1 y 2.2 en verde.

## 3. Pacientes: alta, ficha, edición y baja (R-02, R-04, RN-SE-01)

- [x] 3.1 **Rojo**: tests de integración en `backend/tests/integration/test_pacientes.py` con `api_client`: alta admin normaliza DNI/teléfono (201/200 ficha), DNI duplicado aun con puntos (409) y rechazado por SQL directo, baja lógica que libera DNI (201 + 404 de la ficha), teléfono ausente/vacío (422), DNI y teléfono inválidos (422 por variante), edición exitosa (200) y edición de inexistente/baja (404). **Verifica:** los 6 escenarios de `Registro y ficha de pacientes`.
- [x] 3.2 **Verde**: implementar `PacienteRepository` (`get_by_dni`, `get_by_telefono`, `search`), wiring en `UnitOfWork`, `backend/app/api/pacientes.py` (POST, GET ficha, PUT, DELETE lógico) y montar el router en `backend/app/main.py` resolviendo el consultorio demo. **Verifica:** 3.1 en verde con `pytest tests/integration/test_pacientes.py`.

## 4. Pacientes: búsqueda acotada (R-02, R-05, R-07)

- [x] 4.1 **Rojo**: tests en `backend/tests/integration/test_pacientes.py`: prefijo de apellido case-insensitive ordenado, búsqueda por DNI/teléfono formateados, filtros combinados con AND, sin criterio (422), parámetro no declarado como `nombre` (422), sin coincidencias (200 `[]`), pacientes dados de baja excluidos y `EXPLAIN` con `enable_seqscan=off` que usa el índice de expresión. **Verifica:** los 7 escenarios de `Búsqueda de pacientes con criterio obligatorio` y R-05.
- [x] 4.2 **Verde**: implementar `PacienteRepository.search` con allow-list estricta (`reject_unexpected_query_except`), normalización de criterios y orden `apellido, nombre`; exponer `GET /pacientes`. **Verifica:** 4.1 en verde con `pytest tests/integration/test_pacientes.py -k busqueda`.

## 5. Pacientes: cobertura y control de acceso (R-02, R-03, RN-OS-01)

- [x] 5.1 **Rojo**: tests en `backend/tests/integration/test_pacientes.py`: alta con OS Demo y afiliado (201), obra social inexistente/baja (404), `nro_afiliado` sin obra social (422), quitar cobertura limpiando afiliado (200) y conservando afiliado (422), cambio de obra social (200); recepcionista crea/edita (201/200), odontólogo/asistente/auditor escriben (403), recepcionista da de baja (403) y admin (204), sin token (401). **Verifica:** los 5 escenarios de `Cobertura declarada del paciente` y los 4 de `Control de acceso al registro de pacientes`.
- [x] 5.2 **Verde**: implementar la verificación de obra social activa, la coherencia de afiliado y los guards RBAC (`require_role`) en `backend/app/api/pacientes.py`. **Verifica:** 5.1 en verde.

## 6. Obras sociales: CRUD y reglas locales (R-02, R-03, RN-OS-01/RN-OS-02, DD-11)

- [x] 6.1 **Rojo**: tests en `backend/tests/integration/test_obras_sociales.py`: alta admin + lectura odontólogo (201/200), nombre duplicado sin distinguir mayúsculas (409) y rechazado por SQL directo, baja lógica que libera el nombre, recepcionista crea/borra (403) y edita (200), asistente lee (403), inexistente (404), sin token (401). **Verifica:** los 7 escenarios de `Administración de convenios de obra social`.
- [x] 6.2 **Rojo**: tests de reglas: convenio con reglas completas normalizadas (201), suma > 100 (422), porcentaje fuera de rango (422), código inexistente o duplicado (422), convenio sin reglas (201 con `{}`), reglas con forma inválida (422), `validacion_externa=true` (422), valor por defecto `false` (201) y `false` explícito (201). **Verifica:** los 6 escenarios de `Reglas locales de cobertura validadas` y los 3 de `Validación externa deshabilitada en v1`.
- [x] 6.3 **Verde**: implementar `ObraSocialRepository` (unicidad por `lower(nombre)`, listado), validación de `ReglasCobertura` contra `PrestacionRepository` activo, `backend/app/api/obras_sociales.py` con RBAC de la matriz y montaje del router. **Verifica:** 6.1 y 6.2 en verde con `pytest tests/integration/test_obras_sociales.py`.

## 7. Seed demo extendido (R-08, DD-11)

- [x] 7.1 **Rojo**: actualizar `backend/tests/integration/test_seed.py`: OS Demo con `nomenclador_ref = "DEMO-LOCAL"`, `validacion_externa = false` y reglas 60/40 sobre `CONS, LIM, OBT`; 3 pacientes ficticios con DNI/teléfono válidos (dos con OS Demo, uno particular); re-ejecutar no duplica ni reescribe datos. **Verifica:** seed idempotente y datos ficticios de `04_modelo_de_datos.md` §Seed.
- [x] 7.2 **Verde**: extender `backend/app/seed.py` con `ON CONFLICT DO NOTHING` sin objetivo y resolver primero la obra social demo para asociar los pacientes. **Verifica:** 7.1 en verde con `pytest tests/integration/test_seed.py`.

## 8. Verificación integrada del change (R-14)

- [x] 8.1 Ejecutar la suite completa (`pytest backend/tests`) con `TEST_DATABASE_URL` descartable y registrar la matriz escenario → test en `docs/skills-mcp/evidencias/c-05-verificacion-escenarios.md`.
- [x] 8.2 Levantar Docker Compose (`docker compose up -d --build`), entregar la lista de pruebas manuales y el resumen en lenguaje no técnico, y esperar aprobación explícita antes de archivar, marcar `[x]` en `CHANGES.md` y commitear/pushear (R-14). Aprobado por el usuario el 2026-11-03.
