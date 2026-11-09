# Clínica Odontológica — Sistema de gestión (Argentina)

SaaS para consultorios y clínicas dentales argentinas: agenda, historia clínica y administración en una sola plataforma.

## 🎬 Video del proyecto

[![Video de presentación / demo del proyecto](https://img.youtube.com/vi/z9Po8tLB0S8/maxresdefault.jpg)](https://youtu.be/z9Po8tLB0S8)

👉 [Ver video de presentación / demo del proyecto](https://youtu.be/z9Po8tLB0S8)

[![YouTube](https://img.shields.io/badge/YouTube-Ver_video-red?logo=youtube)](https://youtu.be/z9Po8tLB0S8)

## Qué es

Plataforma SaaS que centraliza la agenda multi-profesional/multi-sillón, la historia clínica odontológica y la administración de consultorios y clínicas argentinas.

Reemplaza la gestión manual por WhatsApp/papel/planillas: reserva online 24/7, confirmación y recordatorios por WhatsApp, ficha clínica con odontograma FDI, presupuestos, caja con Mercado Pago, facturación ARCA y validación de obras sociales.

MVP definido en 5 épicas (US-001–US-041) con 26 reglas de negocio. Detalle en `knowledge-base/01_vision_y_objetivos.md`.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python + FastAPI (async) |
| Auth | JWT Bearer (backoffice) + tokens opacos de un solo uso (rutas públicas) |
| ORM / DB | SQLAlchemy 2.x + PostgreSQL 16 |
| Colas / jobs | Redis 7 (`whatsapp:send`, `recordatorios:due`, `arca:emitir`) |
| Frontend | React + TypeScript + Vite (SPA) |
| Contenedores | Docker / Docker Compose (`api`, `frontend`, `db`, `redis` + workers `recordatorios`, `whatsapp`, `arca`, `reportes`; `backup` en perfil `tools`) |
| Integraciones v1 | WhatsApp Business API, Mercado Pago y ARCA en sandbox/homologación |

## Quickstart (demo local)

Requisitos: Docker y Docker Compose.

```bash
cp backend/.env.example backend/.env
# Editá backend/.env: JWT_SECRET, POSTGRES_PASSWORD, SEED_ADMIN_PASSWORD,
# SEED_DEMO_PASSWORD y BACKUP_PASSPHRASE (todos obligatorios, sin defaults).
docker compose up -d --build
docker compose exec -T api alembic upgrade head
docker compose exec -T api python -m app.seed
```

| Servicio | URL |
|---|---|
| Frontend | http://127.0.0.1:8080 |
| API / Swagger | http://127.0.0.1:8000/docs |
| Healthcheck | http://127.0.0.1:8000/health |
| PostgreSQL | 127.0.0.1:5432 |
| Redis | 127.0.0.1:6379 |

El stack por defecto levanta **ocho servicios** (base + cuatro workers). El
respaldo cifrado no arranca con la demo: se ejecuta con `--profile tools`. Ver
el runbook completo —túnel, webhooks, credenciales demo, respaldo/verificación y
flujo demo verde— en [docs/demo.md](docs/demo.md). La API expone `GET /health`
(y readiness) para los healthchecks de Compose. Los secretos van solo por
variables de entorno (`.env`, gitignored); nunca hay valores reales en el repo.

## Estructura del repo

```text
.
├── backend/            # FastAPI (app/, Dockerfile, .env.example, Alembic)
├── frontend/           # React + TS + Vite (src/, Dockerfile, .env.example)
├── docker-compose.yml  # 8 servicios: api, frontend, db, redis + 4 workers
├── ops/backup/         # Imagen de herramientas: pg_dump + openssl + backup.sh
├── knowledge-base/     # Fuente de verdad del dominio (12 archivos)
├── openspec/           # Changes spec-driven (proposal/design/specs/tasks)
├── docs/               # Discovery, runbook de demo, documentación de apoyo
├── CHANGES.md          # Roadmap: 16 changes C-01–C-16 en 7 fases
└── AGENTS.md           # Reglas duras R-01–R-14 para agentes
```

## Documentación y roadmap

- [knowledge-base/](knowledge-base/) — dominio, reglas de negocio, arquitectura e integraciones.
- [CHANGES.md](CHANGES.md) — secuencia de implementación (dependencias, gates y camino crítico).
- [openspec/](openspec/) — specs activas y archivo de changes completados.
- [docs/demo.md](docs/demo.md) — runbook de demo local: variables, 8 servicios, seed, túnel, respaldo y flujo verde.
- [docs/](docs/) — discovery (`docs/discovery/`), material de apoyo y `docs/skills-mcp/` (ficha de investigación, informe de aplicación y evidencias).
- [AGENTS.md](AGENTS.md) — stack, skills por rol y reglas duras R-01–R-14.

## Skill propia y MCP

El proyecto incorpora dos herramientas de trabajo del agente, documentadas en [docs/skills-mcp/](docs/skills-mcp/):

| Herramienta | Qué aporta | Dónde está |
|---|---|---|
| **Skill `spec-scenario-auditor`** | Audita las specs de un change contra la KB: exige escenarios esperado / error de negocio / borde, trazables y verificables, con tarea de verificación | [`.agents/skills/spec-scenario-auditor/SKILL.md`](.agents/skills/spec-scenario-auditor/SKILL.md) · registrada en [`.atl/skill-registry.md`](.atl/skill-registry.md) |
| **MCP `postgres`** (Postgres MCP Pro, solo lectura) | Inspecciona el esquema real de PostgreSQL (tablas, índices, constraints, triggers, versión de Alembic) durante la preparación y verificación de changes | [docs/skills-mcp/mcp.md](docs/skills-mcp/mcp.md) — requisitos, config reproducible, comprobación de conexión y límites |

Configuración del MCP (sin secretos en el repo):

```jsonc
// %USERPROFILE%\.config\opencode\opencode.json  →  clave "mcp"
{
  "postgres": {
    "type": "local",
    "command": [
      "docker", "run", "-i", "--rm", "-e", "DATABASE_URI",
      "crystaldba/postgres-mcp@sha256:dbbd346860d29f1543e991f30f3284bf4ab5f096d049ecc3426528f20b1b6e6b",
      "--access-mode=restricted"
    ],
    "environment": { "DATABASE_URI": "postgresql://clinica:CAMBIAR_PASSWORD@host.docker.internal:15432/clinica" },
    "enabled": true,
    "timeout": 60000
  }
}
```

Requisito: la base demo del Compose levantada (`docker compose up -d db`) y Docker corriendo. La imagen se fija por digest (no `:latest`, R-08). Guía completa y solución de problemas: [docs/skills-mcp/mcp.md](docs/skills-mcp/mcp.md).

## Estado

- ✅ **C-01 a C-15** implementados y verificados por change (suite, migraciones y smoke guardados en `docs/skills-mcp/evidencias/`).
- 🟡 **C-16 admin-roles-auditoria-deploy** implementado (acceso/roles/auditoría, privacidad publicada, seed completo, Compose con 8 servicios, respaldo cifrado y runbook). Cierre verificado: suite completa, ciclo de migración `0015`, smoke de los 8 servicios y respaldo/verificación. Pendiente: aceptación funcional final sobre la página completa (decisión del 2026-11-03).
- 📘 Runbook de demo: [docs/demo.md](docs/demo.md). Roadmap y dependencias: [CHANGES.md](CHANGES.md).

## Autor y materia

Franco Nicolás Gagliardi — Metodología I, proyecto universitario.
