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
| Contenedores | Docker / Docker Compose (`api`, `frontend`, `db`, `redis`) |
| Integraciones v1 | WhatsApp Business API, Mercado Pago y ARCA en sandbox/homologación |

## Quickstart (demo local)

Requisitos: Docker y Docker Compose.

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

| Servicio | URL |
|---|---|
| Frontend | http://127.0.0.1:8080 |
| API | http://127.0.0.1:8000 |
| Healthcheck | http://127.0.0.1:8000/health |
| PostgreSQL | 127.0.0.1:5432 |
| Redis | 127.0.0.1:6379 |

La API expone `GET /health` (y readiness) para los healthchecks de Compose. Los secretos van solo por variables de entorno (`.env`, gitignored); nunca hay valores reales en el repo.

## Estructura del repo

```text
.
├── backend/            # FastAPI (app/, Dockerfile, .env.example, Alembic)
├── frontend/           # React + TS + Vite (src/, Dockerfile, .env.example)
├── docker-compose.yml  # api + frontend + db (PostgreSQL) + redis
├── knowledge-base/     # Fuente de verdad del dominio (12 archivos)
├── openspec/           # Changes spec-driven (proposal/design/specs/tasks)
├── docs/               # Discovery, documentación de apoyo y guía de skills/MCP
├── CHANGES.md          # Roadmap: 16 changes C-01–C-16 en 7 fases
└── AGENTS.md           # Reglas duras R-01–R-14 para agentes
```

## Documentación y roadmap

- [knowledge-base/](knowledge-base/) — dominio, reglas de negocio, arquitectura e integraciones.
- [CHANGES.md](CHANGES.md) — secuencia de implementación (dependencias, gates y camino crítico).
- [openspec/](openspec/) — specs activas y archivo de changes completados.
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

- ✅ `C-01 foundation-setup` completado y archivado (`openspec/changes/archive/2026-10-13-c-01-foundation-setup/`): scaffolding, Compose con 4 servicios, FastAPI con health check, shell Vite, `.env.example`, Alembic init y colas Redis reservadas.
- 🟡 `C-02 core-models-seguridad` **preparado, no implementado**: proposal, design, specs y tasks validados (`openspec validate --strict`), auditados con la skill propia. Pendiente de aprobación de las decisiones de `design.md` antes de codificar.
- ⬜ `C-03`–`C-16` pendientes según [CHANGES.md](CHANGES.md). Camino crítico: `C-01 → C-02 → C-03 → C-04 → C-06 → C-09 → C-13 → C-14`.

## Autor y materia

Franco Nicolás Gagliardi — Metodología I, proyecto universitario.
