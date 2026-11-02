# Ficha de investigación — Skill propia + servidor MCP

**Proyecto:** Clínica Odontológica (SaaS de gestión, Argentina) · **Fecha:** 2026-11-01
**Integrante:** Franco Nicolás Gagliardi · **Repo:** https://github.com/francogagliardi/clinica-odontologica
**Agente:** OpenCode (skills en `.agents/skills/` del repo + `%USERPROFILE%\.config\opencode\skills\` globales; MCP configurados en `opencode.json`).

## 1. Necesidad detectada

El proyecto es spec-driven: cada change se prepara con `proposal.md`, `design.md`, specs y `tasks.md` antes de escribir código. La tarea repetible que más retrabajo genera es **revisar si una spec realmente prueba lo que promete**: en C-01 los escenarios se escribieron rápido y nadie garantizaba que cada regla tuviera camino feliz, error de negocio y borde, ni que cada `THEN` pudiera observarse en un borde real. Esa revisión se hacía a ojo, distinto en cada change, y sin trazabilidad contra la knowledge base (`RN-*`, `DD-*`).

La segunda necesidad es de **acceso al estado real del entorno**: al preparar un change con migraciones hay que saber qué tablas, índices, constraints, triggers y versión de Alembic existen, y no confiar en el recuerdo ni en lo que dice el ORM. Sin eso se diseña contra supuestos.

Ambas necesidades se resuelven con las dos incorporaciones del TP: una **skill** (procedimiento repetible de auditoría de specs) y un **MCP** (lectura del esquema PostgreSQL en vivo).

## 2. Change elegido: `C-02 core-models-seguridad`

Pendiente en `CHANGES.md`, cabeza del camino crítico después de C-01 y **preparable sin funcionalidad inexistente**: C-01 ya dejó Compose, Alembic y PostgreSQL funcionando, y las cinco tablas que C-02 define no dependen de turnos, pacientes ni integraciones.

- La **skill** aporta al preparar y revisar sus 15 escenarios (2 capacidades: `security/core-models` y `platform/persistence-patterns`), detectando huecos antes de implementar.
- El **MCP** aporta el punto de partida verificado: la base solo contiene `alembic_version` en `0001_base`, lo que fija el `down_revision` de la migración nueva y confirma que no hay tablas que reciclar.

## 3. Skill creadora y diseño de la skill propia

**Creadora: `skill-creator`** — autor Anthropic, repo oficial `anthropics/skills`, ruta `skills/skill-creator`.
Compatibilidad con OpenCode: formato `SKILL.md` con frontmatter `name` + `description`; el agente la descubre por el catálogo de skills y la invoca con la herramienta `skill`.
Instalación reproducible: `git clone https://github.com/anthropics/skills` → copiar `skills/skill-creator/` a `%USERPROFILE%\.config\opencode\skills\skill-creator\` (OpenCode la lista al reiniciar; se comprobó invocándola para generar la skill propia).

**Diseño de la skill propia: `spec-scenario-auditor`** (`.agents/skills/spec-scenario-auditor/SKILL.md`)

| Aspecto | Definición |
|---|---|
| Propósito | Auditar delta specs de un change contra la KB: tres clases de escenario por requirement, trazabilidad a `RN-*`/`DD-*`, verificabilidad en borde observable y tarea de verificación |
| Cuándo se activa | Al preparar/revisar un change; frases "revisá los escenarios", "faltan casos borde", "trazabilidad RN"; siempre antes de `/opsx:apply` |
| Entradas | Nombre del change (o ruta a `specs/**/spec.md`); opcional: capacidades y profundidad (`rápida`/`completa`) |
| Procedimiento | 1) leer proposal/specs/design/tasks · 2) leer la KB declarada en "Leer antes" · 3) matriz de trazabilidad · 4) clasificar escenarios (esperado / error de negocio / borde) · 5) marcar huecos · 6) verificar borde observable · 7) cruzar con tasks · 8) reportar sin reescribir la spec |
| Resultado esperado | Matriz + huecos con escenario sugerido + no verificables + escenarios sin tarea + deriva KB/spec + veredicto |
| Criterios de revisión | Cada requirement con las tres clases o hueco nombrado; toda regla citada existe en KB; ningún escenario inventa dominio; cada `THEN` observable sin leer código interno; veredicto accionable |
| Dónde vive | Versionada en el repo (`.agents/skills/`), registrada en `.atl/skill-registry.md`, referenciada en `AGENTS.md`/`CLAUDE.md` y en la KB (DD-13) |

## 4. Comparación de servidores MCP y elección

| Criterio | **Postgres MCP Pro** (elegido) | Reference PostgreSQL MCP Server |
|---|---|---|
| Autor / fuente | Crystal DBA — `github.com/crystaldba/postgres-mcp` (MIT) | Equipo MCP — `github.com/modelcontextprotocol/servers-archived/src/postgres` |
| Propósito | Administración/asistencia de PostgreSQL para agentes | Consultas SQL de solo lectura |
| Capacidades | `list_schemas`, `list_objects`, `get_object_details`, `execute_sql`, `explain_query`, `analyze_db_health`, análisis de índices | Un único `query` + recursos de esquema |
| Estado | Activo (PyPI `postgres-mcp`, imagen Docker) | **Archivado** (movido a `servers-archived`) |
| Compatibilidad | Cliente MCP estándar (stdio); OpenCode vía `type: local` | Igual, pero sin mantenimiento |
| Requisitos | Docker (o Python 3.12+); opcional `pg_stat_statements`/`hypopg` | Node/npx |
| Permisos / credenciales | URI de conexión; `--access-mode=restricted` fuerza solo lectura y parsea SQL | URI; solo lectura por transacción |
| Costos | Gratuito, sin servicios pagos | Gratuito |

**Elección:** Postgres MCP Pro. El reference está archivado y su única herramienta no alcanza para inspeccionar índices y constraints, que es justo lo que C-02 necesita verificar. Alternativa descartada: `context7` (ya disponible) porque documenta librerías, no el estado real de la base.

## 5. Instalación y configuración

1. `docker pull crystaldba/postgres-mcp` → anotar el **digest** (se fija por digest, no `:latest`, R-08).
2. Declarar el MCP en `%USERPROFILE%\.config\opencode\opencode.json`:
   ```jsonc
   "postgres": {
     "type": "local",
     "command": ["docker","run","-i","--rm","-e","DATABASE_URI",
       "crystaldba/postgres-mcp@sha256:dbbd346…","--access-mode=restricted"],
     "environment": { "DATABASE_URI": "postgresql://clinica:CAMBIAR_PASSWORD@host.docker.internal:15432/clinica" },
     "enabled": true, "timeout": 60000
   }
   ```
3. Variable de entorno necesaria: `DATABASE_URI` (credenciales demo; en el repo solo aparece el placeholder). Requisito previo: `docker compose up -d db`.
4. Reiniciar el cliente y comprobar con `list_schemas`; documentación completa y troubleshooting en `docs/skills-mcp/mcp.md`.

## 6. Archivos de la fundación a actualizar

`.atl/skill-registry.md` (registro + compact rules + convenciones) · `AGENTS.md` + `CLAUDE.md` (skill: cuándo usarla, qué necesita, cómo revisar; MCP: propósito, momento, límites) · `README.md` (sección Skill+MCP y config de ejemplo) · `knowledge-base/09_decisiones_y_supuestos.md` (DD-13) · `CHANGES.md` (C-02 preparado, sin marcar implementado) · `docs/skills-mcp/` (ficha, informe, `mcp.md`, evidencias).

## 7. Fuentes (consultadas 2026-11-01)

- Anthropic — `skill-creator`: https://github.com/anthropics/skills/tree/main/skills/skill-creator
- Crystal DBA — Postgres MCP Pro: https://github.com/crystaldba/postgres-mcp · https://pypi.org/project/postgres-mcp/
- MCP — servidor PostgreSQL archivado: https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres
- OpenCode — documentación de MCP servers: https://opencode.ai/docs/mcp-servers/
- PostgreSQL 16 — triggers y `TRUNCATE`: https://www.postgresql.org/docs/16/sql-createtrigger.html
