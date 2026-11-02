# MCP del proyecto — PostgreSQL (Postgres MCP Pro)

> Documento de integración del servidor MCP. **No es una skill**: un MCP es una integración que expone herramientas de un sistema externo; las skills son instrucciones. Este archivo describe requisitos, configuración, verificación y límites.

## Para qué lo usa el proyecto

Inspeccionar el esquema real de PostgreSQL durante la preparación y verificación de un change: qué tablas existen, qué índices y constraints tiene una tabla, y si una migración quedó aplicada. Evita diseñar contra supuestos (fue lo que confirmó que C-01 solo dejó `alembic_version` antes de preparar C-02).

Ejemplos de uso:

- "listá las tablas del schema `public` y decime si `registro_auditoria` ya existe".
- "mostrame los índices de `usuarios`" (antes de dar por buena una migración).
- "¿qué versión de Alembic está aplicada en la base de demo?".

## Servidor elegido y alternativa comparada

| | **Postgres MCP Pro** (elegido) | Reference PostgreSQL MCP Server |
|---|---|---|
| Autor / fuente | Crystal DBA (`github.com/crystaldba/postgres-mcp`), MIT | Equipo MCP (`github.com/modelcontextprotocol/servers-archived/src/postgres`) |
| Estado | Mantenido, PyPI `postgres-mcp` 0.3.0, imagen Docker | **Archivado** (movido a `servers-archived`) |
| Herramientas | `list_schemas`, `list_objects`, `get_object_details`, `execute_sql`, `explain_query`, `analyze_db_health`, índices y consultas lentas | Un solo `query` de solo lectura + recursos de esquema |
| Modo seguro | `--access-mode=restricted` = transacciones read-only + parseo de SQL (rechaza `COMMIT`/`ROLLBACK`) | Solo lectura por transacción, sin parseo |
| Requisitos | Docker **o** Python 3.12+; opcional `pg_stat_statements`/`hypopg` para tuning | Node/npx, sin extras |
| Costo | Gratis, sin credenciales de terceros | Gratis |

Se eligió Postgres MCP Pro porque el reference está archivado y porque las herramientas de esquema/índices son exactamente lo que la preparación de C-02 necesita (verificar constraints, índices parciales y triggers). Alternativa descartada: usar `context7` para esto (consulta documentación, no el estado real de la base).

## Requisitos

- Docker con el motor Linux corriendo (Docker Desktop en Windows).
- La base del Compose levantada: `docker compose up -d db`.
- Credenciales de **demo**, nunca de producción (ver Límites).
- Opcional para pruebas sin Docker: `uvx` (Python 3.12+).

## Configuración (cliente OpenCode)

Archivo **global** del cliente: `%USERPROFILE%\.config\opencode\opencode.json` (en este equipo, `C:\Users\Franco Gagliardi\.config\opencode\opencode.json`), dentro de la clave `mcp`.

Configuración real usada (imagen **fijada por digest**, no por `latest`, para respetar R-08):

```jsonc
{
  "mcp": {
    "postgres": {
      "type": "local",
      "command": [
        "docker", "run", "-i", "--rm",
        "-e", "DATABASE_URI",
        "crystaldba/postgres-mcp@sha256:dbbd346860d29f1543e991f30f3284bf4ab5f096d049ecc3426528f20b1b6e6b",
        "--access-mode=restricted"
      ],
      "environment": {
        "DATABASE_URI": "postgresql://clinica:CAMBIAR_PASSWORD@127.0.0.1:15432/clinica"
      },
      "enabled": true,
      "timeout": 60000
    }
  }
}
```

Notas de reproducción:

- `-e DATABASE_URI` sin valor reenvía la variable del proceso `docker`; el valor real vive en `environment` del cliente (fuera del repo).
- El puerto es **15432** porque en este equipo el 5432 está ocupado por un PostgreSQL local; se usa el override de Compose (`docker-compose.override` temporal, no versionado).
- En otra máquina: reemplazar digest por el vigente (`docker pull crystaldba/postgres-mcp` → copiar `Digest:`) y ajustar puerto/credenciales.
- Si se prefiere Python: `uvx postgres-mcp --access-mode=restricted` con `DATABASE_URI` en el entorno (ver Solución de problemas).

## Comprobación de conexión

1. **Por el cliente (recomendado, requiere reiniciar OpenCode para que levante el MCP):** pedir "usá la herramienta `postgres` y listá los schemas". Debe devolver `information_schema`, `pg_catalog`, `pg_toast` y `public`.
2. **Sin reiniciar el cliente (lo usado como evidencia):** hablar JSON-RPC con el servidor por stdio. El script versionado en `docs/skills-mcp/evidencias/mcp-stdio-driver.js` hace `initialize` → `tools/list` → `tools/call` y guarda el transcript. Ejemplo:

```powershell
$env:DATABASE_URI="postgresql://clinica:<password-demo>@host.docker.internal:15432/clinica"
$env:MCP_CMD="docker run -i --rm -e DATABASE_URI crystaldba/postgres-mcp@sha256:<digest> --access-mode=restricted"
$env:TOOL_ARGS_JSON='{"sql":"SELECT table_name FROM information_schema.tables WHERE table_schema = $$public$$"}'
node docs/skills-mcp/evidencias/mcp-stdio-driver.js execute_sql
```

Resultado registrado: `docs/skills-mcp/evidencias/mcp-execute-sql.json` y `mcp-list-schemas.json`.

## Solución de problemas

| Síntoma | Causa | Solución aplicada |
|---|---|---|
| `Error: Connection attempt failed: the pool 'pool-2' is closed` | URI con `127.0.0.1`, que dentro del contenedor apunta al propio contenedor | Cambiar a `host.docker.internal`; el pool se recuperó sin reiniciar el cliente |
| `AttributeError: 'Server' object has no attribute 'list_resources'` al arrancar con `uvx postgres-mcp` | `postgres-mcp` 0.3.0 quedó incompatible con la versión de `mcp` que resuelve `uvx` (la API de decoradores cambió) | Se usa la **imagen Docker** que publica el autor (dependencias resueltas). Alternativa: `uvx --with "mcp<1.20" postgres-mcp` o `pipx install postgres-mcp` con versión fijada |
| `connection refused` al conectar desde el contenedor | `127.0.0.1` dentro del contenedor es el propio contenedor | Usar `host.docker.internal:15432` (la imagen remapea `localhost`, pero la URI explícita evita ambigüedad) |
| El cliente no ve las tools | OpenCode carga `mcp` al iniciar | Reiniciar OpenCode; mientras tanto, verificar con el driver stdio |
| Error de autenticación | Password demo distinto al del Compose | Tomar la de `backend/.env` (`DATABASE_URL`) o del `POSTGRES_PASSWORD` con que se levantó el stack |

## Límites de acceso (política del proyecto)

- **Solo lectura:** `--access-mode=restricted`; el servidor rechaza escrituras y parsea el SQL para bloquear evasiones (`COMMIT`/`ROLLBACK`). No puede crear tablas por sí mismo: las migraciones se corren con Alembic.
- **Datos de prueba únicamente:** se conecta a la base demo del Compose (`clinica`), con datos ficticios. Nunca a una base con datos de pacientes reales (regla del TP y RN-SE-02).
- **Sin secretos en el repo:** el valor de `DATABASE_URI` vive en la config global del cliente; en documentación y ejemplos se usa `CAMBIAR_PASSWORD`.
- **Costo de contexto:** cada MCP suma herramientas al contexto; por eso se mantienen solo dos servidores de datos (`context7`, `postgres`) además de `engram`, y se evita habilitar MCP que aporten decenas de tools.
