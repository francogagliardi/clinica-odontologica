# Evidencia — invocación del MCP `postgres` desde el cliente

**Fecha:** 2026-11-01
**Servidor:** Postgres MCP Pro (`crystaldba/postgres-mcp`, imagen fijada por digest) en `--access-mode=restricted`.
**Cliente:** OpenCode, MCP declarado en `%USERPROFILE%\.config\opencode\opencode.json` (ver `docs/skills-mcp/mcp.md`).
**Base:** PostgreSQL 16 del Compose del proyecto (demo, datos ficticios).

## Solicitud 1 — `list_schemas`

- **Pedido:** "listá los schemas de la base".
- **Resultado:** `information_schema`, `pg_catalog`, `pg_toast`, `public`.
- **Aporte:** confirma conexión y que el schema objetivo es `public`.

## Solicitud 2 — `list_objects(schema_name="public")`

- **Resultado:** una sola tabla, `alembic_version` (`BASE TABLE`).
- **Aporte:** prueba que C-01 no dejó tablas de dominio; el diseño de C-02 parte de un esquema vacío y no de un supuesto.

## Solicitud 3 — `execute_sql`

```sql
SELECT version_num AS alembic_version FROM alembic_version;
```

- **Resultado:** `[{'alembic_version': '0001_base'}]`
- **Aporte:** la migración base está aplicada; la migración nueva de C-02 debe declarar `down_revision = "0001_base"` y no crear otra head.

## Solicitud 4 — `execute_sql` (índices)

```sql
SELECT indexname FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1;
```

- **Resultado:** `[{'indexname': 'alembic_version_pkc'}]`
- **Aporte:** no hay índices de dominio preexistentes; los índices únicos parciales y el de auditoría de C-02 se crean desde cero y se pueden verificar por nombre en el test de migración.

## Incidencia real durante la integración

El primer intento desde el cliente devolvió `Error: Connection attempt failed: the pool 'pool-2' is closed`. Causa: la URI de la config apuntaba a `127.0.0.1:15432`, que **dentro del contenedor** es el propio contenedor, no el host. Se corrigió a `host.docker.internal:15432` y las tres herramientas respondieron. Queda documentado en la tabla de solución de problemas de `docs/skills-mcp/mcp.md`.

## Reproducibilidad sin el cliente

Los transcripts crudos de la misma sesión vía stdio están en:

- `mcp-list-schemas.json` (initialize + tools/list + `list_schemas`)
- `mcp-execute-sql.json` (initialize + tools/list + `execute_sql`)
- `mcp-stdio-driver.js` (script usado; requiere Node y `DATABASE_URI`/`MCP_CMD` en el entorno)
