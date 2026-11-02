# Informe de aplicación — Skill propia + MCP en el proyecto

**Proyecto:** Clínica Odontológica · **Fecha:** 2026-11-01 · **Integrante:** Franco Nicolás Gagliardi
**Change preparado:** `C-02 core-models-seguridad` (pendiente, **sin implementar, verificar ni archivar**)

## 1. Resultado

| Incorporación | Estado | Dónde quedó |
|---|---|---|
| **Skill propia `spec-scenario-auditor`** | Creada con `skill-creator`, versionada, registrada y usada en 3 rondas sobre C-02 (la última en una sesión nueva) | `.agents/skills/spec-scenario-auditor/SKILL.md` · `.atl/skill-registry.md` · `AGENTS.md`/`CLAUDE.md` · DD-13 |
| **MCP `postgres`** (Postgres MCP Pro, solo lectura) | Conectado y operativo; se ejecutaron `list_schemas`, `list_objects` y `execute_sql` reales | Config global `%USERPROFILE%\.config\opencode\opencode.json` · guía reproducible en `docs/skills-mcp/mcp.md` · sección en `README.md` y `AGENTS.md` |
| **C-02 preparado** | `proposal.md`, `design.md`, `tasks.md`, 2 delta specs; `openspec validate --strict` → **valid**; `openspec status` → 4/4 artefactos | `openspec/changes/c-02-core-models-seguridad/` · referencia actualizada en `CHANGES.md` (estado `[ ]`, "preparado, no implementado") |

## 2. Aporte concreto al change

**Skill (3 invocaciones).** Ronda 1 sobre las specs recién escritas: matriz de trazabilidad requirement → regla KB y 4 defectos corregidos (§4). Ronda 2, con `tasks.md`: veredicto "LISTO PARA APPLY". Ronda 3 en **sesión nueva independiente** (subagente sin la ruta de la skill): la encontró por `AGENTS.md` → `.agents/skills/` → `.atl/skill-registry.md`, la invocó con la herramienta `skill` y auditó el texto sin el sesgo del autor — encontró 8 huecos que las dos rondas anteriores no vieron y obligó a reescribir ambas specs. Resultado final: **32 escenarios** con las tres clases y tarea de verificación asignada, `openspec validate --strict` en verde.

**MCP (3 herramientas).** `list_schemas` → `public` es el schema objetivo. `list_objects("public")` → una sola tabla, `alembic_version`. `execute_sql` → `version_num = 0001_base`. Eso fijó dos decisiones del design sin adivinar: la migración nueva declara `down_revision = "0001_base"` y no hay tablas de dominio que reciclar. Una consulta extra a `pg_indexes` mostró solo `alembic_version_pkc`, confirmando que los índices de C-02 se crean desde cero.

**Evidencias** (`docs/skills-mcp/evidencias/`):

| Archivo | Contenido |
|---|---|
| `skill-audit-c-02-ronda1.md` | Matriz, 4 hallazgos, deriva de dominio, veredicto BLOQUEADO |
| `skill-audit-c-02-ronda2.md` | Cierre de huecos de la ronda 1 (superada por la ronda 3, se conserva como proceso) |
| `skill-audit-c-02-ronda3.md` | Auditoría en sesión nueva: 8 hallazgos, tabla antes→después y lección sobre el sesgo de contexto |
| `mcp-sesion-cliente.md` | Solicitud, resultado y aporte de las 3 herramientas desde el cliente |
| `mcp-list-schemas.json`, `mcp-execute-sql.json` | Transcripts crudos JSON-RPC (initialize → tools/list → tools/call) |
| `mcp-stdio-driver.js` | Driver reproducible para verificar el MCP sin reiniciar el cliente |

## 3. Archivos modificados y por qué

| Archivo | Motivo |
|---|---|
| `.agents/skills/spec-scenario-auditor/SKILL.md` **(nuevo)** | Skill propia: propósito, activación, entradas, procedimiento, formato de salida y criterios de revisión |
| `.atl/skill-registry.md` | Alta de la skill (trigger, path, compact rules) y corrección de la sección "Project Conventions", que seguía diciendo que no existía `AGENTS.md` |
| `AGENTS.md` + `CLAUDE.md` (idénticos, hash verificado) | 6→7 skills; cuándo usar la propia y cómo revisar su salida; tabla de MCP con propósito, momento y límites |
| `README.md` | Sección "Skill propia y MCP" con config de ejemplo sin secretos; `R-01–R-13` → `R-01–R-14`; estado de C-02 |
| `knowledge-base/09_decisiones_y_supuestos.md` | DD-13: decisión, contexto y trade-offs de incorporar skill + MCP a la fundación |
| `CHANGES.md` | C-02: artefactos preparados y validados, migración `0002` (no `001`), triggers de `TRUNCATE`, sin marcar implementado |
| `openspec/changes/c-02-core-models-seguridad/*` **(nuevo)** | proposal, design (10 decisiones), tasks (verificación por escenario), specs `security/core-models` y `platform/persistence-patterns` |
| `docs/skills-mcp/investigacion.md`, `aplicacion.md`, `mcp.md` **(nuevo)** | Ficha, este informe y guía reproducible del MCP |
| `ENTREGA.md` **(nuevo)** | Integrantes, repo, commit de entrega y video |
| `%USERPROFILE%\.config\opencode\opencode.json` (fuera del repo) | Alta del MCP `postgres` con imagen fijada por digest y `--access-mode=restricted` |

No se tocó código de `backend/` ni `frontend/`: el TP pide preparar el change, no implementarlo.

## 4. Revisión crítica (antes / después)

**Defecto 1 — "error de negocio" que no era error de negocio (detectado por la skill).**
El escenario original del repositorio decía: *"WHEN se consulta por un identificador que no existe THEN el repositorio devuelve `None`, y la decisión de responder 404 queda en la capa de API"*. La skill lo marcó como mal clasificado: devolver `None` es el **contrato** de la capa de persistencia, no una regla de dominio violada, y en C-02 no hay capa HTTP que produzca el 404. Fuente que permitió corregirlo: el propio criterio de clasificación (error de negocio = una regla del dominio impide la operación) + R-04 (la baja es lógica, nunca física).
**Después:** el error de negocio pasó a ser *"un llamador intenta borrar físicamente una entidad → la interfaz pública no expone esa operación (solo `soft_delete`)"*, y el `None` se movió al contrato/borde. El escenario ahora prueba algo que puede fallar.

**Defecto 2 — huecos de borde y de unicidad (detectados por la skill).**
Faltaba la asignación repetida del mismo rol (`UsuarioRol` con PK compuesta) y el duplicado de `Consultorio.slug` (solo se probaba `Rol.nombre`). **Después:** se agregó el escenario idempotente de asignación repetida y el escenario de unicidad se amplió a rol **y** slug, ambos con `SQLSTATE 23505`.

**Defecto 3 — deriva silenciosa del seed.**
La KB pide un seed con 3 usuarios, sillones, prestaciones y turnos; la spec recortaba a 5 roles + 1 consultorio + 1 admin sin decirlo. **Después:** se declaró como nota de alcance en el `Purpose` de la spec y en `design.md`, con dueño (C-04–C-06), en lugar de dejar que un lector asumiera un seed completo.

**Defecto 4 — herramienta: advertencia `--strict`.**
`openspec validate --strict` marcó el requirement de seed por superar 500 caracteres. **Después:** la nota de alcance se movió al `Purpose`; validación final: `Change 'c-02-core-models-seguridad' is valid`.

**Defecto 5 — el más grave: la propia auditoría se auto-confirmaba.**
Las rondas 1 y 2 las corrí en el mismo contexto que redactó las specs, y la ronda 2 declaró "LISTO PARA APPLY". Una **sesión nueva** auditó el texto sin ese contexto y encontró 8 huecos: unicidad plana en `slug`/`rol.nombre` que bloqueaba nombres para siempre (inconsistente con el email), falta de garantía en base para el estado parcial de baja lógica, ningún escenario que probara que el repositorio no commitea, seed sin definir reejecución con otra contraseña ni concurrencia, `usuario_id` nulo sin escenario propio, falta de paridad ORM↔migración, dos `THEN` no falsables y un denominador de escenarios inventado (decía 12; eran 23). Fuente que permitió corregirlo: la propia guía de la skill (checklist de borde + "cada `THEN` observable") aplicada por alguien que no había escrito la spec.
**Después:** se reescribieron ambas specs (**32 escenarios**), se agregó el CHECK `(deleted_at IS NULL) = is_active`, se decidieron índices únicos parciales para los tres valores, el seed ya no reescribe hashes y usa `ON CONFLICT` en todas las claves naturales, y `tasks.md` cubre cada escenario. La lección quedó escrita en `skill-audit-c-02-ronda3.md`: **la auditoría debe correr en una sesión distinta de la que redactó**.

**Problema de entorno resuelto (criterio profesional).** `uvx postgres-mcp` falló con `AttributeError: 'Server' object has no attribute 'list_resources'` (incompatibilidad de `postgres-mcp` 0.3.0 con la versión de `mcp` resuelta por `uvx`). Se resolvió usando la imagen Docker del autor, fijada por digest (también cumple R-08, que prohíbe `:latest`). Además, la primera conexión desde el cliente devolvió `pool 'pool-2' is closed` porque la URI usaba `127.0.0.1`, que dentro del contenedor es el propio contenedor; corregido a `host.docker.internal:15432`. Ambos casos quedaron en la tabla de troubleshooting de `mcp.md`.

## 5. Limitaciones

- **Sesión nueva:** verificado — un subagente sin contexto previo encontró la skill por `AGENTS.md`/`.agents/skills/`/`.atl/skill-registry.md`, la invocó y auditó el change (evidencia en `skill-audit-c-02-ronda3.md`). Lo que **no** existe es un harness de evaluación automática tipo `eval-viewer` de `skill-creator`: los "evals" fueron las tres auditorías reales. Queda como mejora un conjunto de prompts de prueba versionados.
- **El MCP es de solo lectura:** por diseño no puede crear tablas ni probar triggers; eso lo hacen Alembic y los tests de integración al implementar C-02.
- **Config global, no versionada:** el valor real de `DATABASE_URI` vive fuera del repo (demo). En el repo solo hay placeholder; otro integrante debe seguir `mcp.md` y usar su propia contraseña.
- **Puerto 15432:** es un workaround local porque el 5432 está ocupado por otro PostgreSQL; en una máquina limpia se usa el 5432 del Compose.
- **C-02 no está implementado:** las decisiones de `design.md` son governance CRÍTICO y esperan aprobación explícita (R-14 exige además Docker + lista de pruebas antes de archivar).
- **Video:** pendiente de grabación por el integrante (≤5 min).
