# Design

## Context

Repo greenfield: solo KB, CHANGES.md y openspec existen; no hay `backend/`, `frontend/` ni Compose. Ver `proposal.md` (Why) para la motivación. Constraints: DD-07a–DD-07e (stack exacto), DD-12 (default demo local; P-05 hospedaje final abierta), R-08 (Docker: pines, non-root, sin secretos en capas), R-09 (TDD por slice vertical), R-13 (sin commit/push). Ver specs `platform/*` para los requisitos.

## Goals / Non-Goals

**Goals:**

- `docker compose up --build` verde con `api/frontend/db/redis` y `GET /health` + `GET /ready` operativos.
- Layouts backend/frontend finales desde el día uno para que C-02+ solo agregue archivos, no reestructure.
- Contrato de colas + `.env.example` estables para que C-03/C-09/C-13/C-14 no renombren nada.

**Non-Goals:**

- Ningún dominio (tablas, endpoints de negocio, auth real, workers funcionales) — eso es C-02+.
- Ningún secreto real, túnel de webhooks ni despliegue nube — C-16.
- Optimización de performance/índices — sin tablas calientes aún (R-05 no aplica hasta C-02+).

## Decisions

- **Compose con `db: postgres:16-alpine` + `redis:7-alpine` pineados, volúmenes `pgdata/redisdata`, healthchecks `pg_isready` / `redis-cli ping`, `depends_on: condition: service_healthy` para `api`.** Alternativa: imágenes `latest` o sin gates — rechazada (drift + arranques en falso). Aplica docker-patterns (service-name DNS, gates, volúmenes nombrados).
- **Backend `python:3.12-slim` multi-stage (deps→production), `USER appuser`, Uvicorn como único proceso, lifespan manager que abre/cierra pool SQLAlchemy + cliente Redis.** Alternativa: imagen full o root — rechazada por R-08. Aplica fastapi-python (lifespan, DI, `async def`).
- **`GET /health` vs `GET /ready` separados.** Liveness nunca toca red; readiness hace `SELECT 1` + `PING` con timeout corto. Alternativa: un solo endpoint — rechazada (orquestador mataría el contenedor ante una caída transitoria de DB).
- **Config con Pydantic `BaseSettings` (`extra="forbid"`), fallo rápido ante secreto ausente.** Alternativa: defaults cómodos — rechazada (oculta mala config; R-08 exige sin defaults hardcodeados para secretos).
- **Alembic con `versions/` vacío + `env.py` leyendo `DATABASE_URL`.** Alternativa: SQLAlchemy `create_all` — rechazada (R-04 exige migraciones declarativas; aplica supabase-postgres-best-practices).
- **Frontend `node:20-alpine` build → `nginx:1.27-alpine` non-root sirviendo `dist/`, `VITE_API_BASE_URL` por env, placeholders en `/` y `/reservar`.** Alternativa: `vite preview` en prod — rechazada (superficie y peso mayores). Solo reglas cliente/bundle/re-render de vercel-react-best-practices (las RSC/Next no aplican a esta SPA Vite).
- **Colas como constantes centralizadas (`WHATSAPP_SEND`, `RECORDATORIOS_DUE`, `ARCA_EMITIR`) sin workers.** Alternativa: workers stub que consumen y descartan — rechazada (falso verde; C-09/C-13 implementan consumo real con reintento).

## Risks / Trade-offs

- [Riesgo] Versiones pineadas quedan obsoletas → Mitigación: pines por minor (`16`, `7`, `3.12`, `20`, `1.27`) + nota en tasks para bump trimestral; `dependabot` fuera de scope C-01.
- [Riesgo] `.env` reales committeados por error → Mitigación: `.gitignore` + arranque que falla sin secretos + `.env.example` como única referencia versionada (R-08/R-13).
- [Riesgo] Confundir `health` con `ready` en Compose/K8s futuro → Mitigación: healthcheck Docker usa `/health`; `depends_on` y readiness externa usan `/ready`; documentado en design, no solo en código.
- [Trade-off] Sin workers, las colas no se drenan — aceptado: el contrato nominal es el deliverable; encolar real llega con C-07/C-09 (documentado como Non-Goal para no prometer comportamiento inexistente).
- Cifras comerciales (p. ej. ~40 % ausentismo de proveedores): **No evidenciado** — no se usan como criterio de aceptación en este change.

## Migration Plan

Greenfield: sin migración ni rollback de datos. Despliegue = `cp backend/.env.example backend/.env` (+ frontend), `docker compose up --build`, verificar `GET /health → 200` y `GET /ready → 200`. Rollback = `docker compose down -v` (volúmenes de demo descartables; nada de producción afectado).

## Open Questions

- Ninguna que cambie specs/enfoque/tasks. P-05 (hospedaje final nube vs. local) queda abierta por KB y la resuelve C-16; C-01 no la necesita.
