# Proposal

## Why

No existe scaffolding ejecutable del sistema: sin Compose (api/frontend/db/redis), sin baseline FastAPI ni SPA Vite, sin gestión de env vars ni migraciones, los 15 changes siguientes (C-02–C-16) no tienen dónde integrar código ni cómo demostrar la demo universitaria (Metodología I, demo-driven). C-01 es la cabeza del camino crítico y no tiene dependencias.

## What Changes

- Agrega `docker-compose.yml` con servicios mínimos `api`, `frontend`, `db` (PostgreSQL), `redis`, con healthchecks, `depends_on` condicionado, volúmenes nombrados (`pgdata`, `redisdata`) y DNS por nombre de servicio (`db`, `redis`).
- Agrega `backend/` con `Dockerfile` multi-stage pineado non-root, layout `app/` (`domain/ application/ infrastructure/ models/ schemas/ api/ (deps.py) core/ workers/ main.py`), FastAPI mínima con `GET /health` y `GET /ready` (liveness vs. readiness DB+Redis), config por env vars, cliente Redis cableado solo para colas.
- Agrega `frontend/` con `Dockerfile` multi-stage pineado, `vite.config.ts`, layout `src/` (`features/ shared/ pages/` con placeholder backoffice + reserva pública), cliente API con base URL por env.
- Agrega `backend/.env.example` + `frontend/.env.example` con `DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, WHATSAPP_API_TOKEN, WHATSAPP_PHONE_ID, MP_ACCESS_TOKEN, ARCA_CUIT, ARCA_CERT, ARCA_KEY, APP_BASE_URL` — secretos sin defaults hardcodeados, archivos `.env` reales gitignorados.
- Inicializa Alembic (config + `versions/` vacío, sin migraciones de dominio; las tablas llegan en C-02+).
- Reserva la topología de colas Redis `whatsapp:send`, `recordatorios:due`, `arca:emitir` como contrato nominal (sin workers funcionales aún; workers en C-09/C-13/C-14).
- Agrega `.dockerignore` en backend/frontend y verificación `docker compose up --build` + `GET /health` verde como criterio de aceptación.

## Capabilities

### New Capabilities

- `platform/compose-stack`: stack local contenerizado demo (servicios api/frontend/db/redis, healthchecks, volúmenes, wiring por env, `compose up` verde).
- `platform/backend-baseline`: baseline FastAPI ejecutable (layout `app/`, health/readiness, config por env vars, `api/deps.py` stub, Alembic inicializado, RORO/Pydantic/async desde el día uno).
- `platform/frontend-baseline`: shell SPA React+TS+Vite (layout `features/shared/pages`, build/preview servido, config por env, placeholders backoffice + reserva pública sin lógica de negocio).
- `platform/job-queues`: contrato de colas Redis reservadas (`whatsapp:send`, `recordatorios:due`, `arca:emitir`) y regla Redis-solo-jobs (nunca fuente de verdad; estado durable en PostgreSQL).

### Modified Capabilities

- Ninguna (repo greenfield: `openspec list --specs` retorna cero specs; no hay comportamiento previo que cambiar).

## Impact

- Archivos nuevos bajo `backend/`, `frontend/`, `docker-compose.yml`, `.env.example`s, config Alembic; ningún código de dominio (turnos, clínica, caja) ni endpoints de negocio.
- Desbloquea C-02 (modelos/seed necesitan DB+migraciones) y todo el roadmap; sin impacto en producción (no hay producción en v1; default demo local DD-12, P-05 abierta).
- Riesgos: drift de versiones de imágenes (mitigado con pines, R-08); secretos accidentales en capas/git (mitigado con `env_file`/gitignore, R-08); falsas promesas comerciales — cifras de ausentismo (~40 % declarada por proveedores) se tratan como **No evidenciado** hasta medir con datos propios (IN-01/IN-02); distinción comprobada-vs-comercial aplica a decisiones de hospedaje/integraciones, no a este scaffolding.
