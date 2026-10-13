# Tasks

## 1. Compose stack + contratos env (docker-patterns, R-08)

- [x] 1.1 Crear `docker-compose.yml` (api/frontend/db/redis, DNS `db`/`redis`, healthchecks `pg_isready`/`redis-cli ping`, `depends_on` healthy, volúmenes `pgdata`/`redisdata`, puertos dev en `127.0.0.1`) y verificar con `docker compose config` válido.
- [x] 1.2 Crear `backend/Dockerfile` + `frontend/Dockerfile` multi-stage pineados non-root con `.dockerignore` (excluye `.git`, `.env`, `node_modules`, `dist`, `__pycache__`) y verificar que ningún tag es `:latest` y la etapa final no corre como root (`docker build` de ambas imágenes exitoso).
- [x] 1.3 Crear `backend/.env.example` + `frontend/.env.example` con las 12 vars (`DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, WHATSAPP_API_TOKEN, WHATSAPP_PHONE_ID, MP_ACCESS_TOKEN, ARCA_CUIT, ARCA_CERT, ARCA_KEY, APP_BASE_URL` + `VITE_API_BASE_URL`) sin secretos reales y verificar que `.gitignore` ignora `.env` reales y que `grep` no halla secretos literales.

## 2. Backend baseline (fastapi-python, supabase-postgres-best-practices, tdd R-09)

- [x] 2.1 Red: test de `GET /health` (200 `{"status":"ok"}` sin tocar DB/Redis) y de `GET /ready` (200 con `db/redis: up`, 503 identificando dependencia caída); Green: routers + esquemas Pydantic v2 `extra="forbid"`, `async def`, `HTTPException` tipados; verificar con suite backend en verde.
- [x] 2.2 Implementar config `core/settings.py` con Pydantic `BaseSettings` (fallo rápido nombrando la var ausente, sin defaults para secretos; `snake_case` + hints completos) y `api/deps.py` stub de DI, y verificar arrancando sin `JWT_SECRET` (falla nombrándola) y con env completo (arranca).
- [x] 2.3 Crear layout `app/` (`domain/ application/ infrastructure/ models/ schemas/ api/ core/ workers/ main.py` con lifespan abriendo/cerrando SQLAlchemy + Redis) + cliente Redis con constantes `WHATSAPP_SEND="whatsapp:send"`, `RECORDATORIOS_DUE="recordatorios:due"`, `ARCA_EMITIR="arca:emitir"` y verificar import + `GET /health` en local sin Docker.
- [x] 2.4 Inicializar Alembic (`env.py` leyendo `DATABASE_URL`, `versions/` sin migraciones de dominio) y verificar `alembic heads` (una head base) y `alembic upgrade head` (sin crear tablas de dominio).

## 3. Frontend baseline (solo reglas cliente/bundle/re-render; R-07)

- [x] 3.1 Red: test de render de rutas `/` (placeholder backoffice) y `/reservar` (placeholder reserva) + 404; Green: `vite.config.ts`, `src/` (`features/ shared/ pages/`), `tsconfig` estricto sin `any`, componentes `PascalCase` sin anidamiento ni barrel files, y verificar `tsc --noEmit` + `vite build` + tests en verde.
- [x] 3.2 Cablear cliente API con base por `VITE_API_BASE_URL`, fetches independientes con `Promise.all`, presentación directa de errores 409/422 sin lógica de negocio, y verificar cambiando la env (llamadas usan la nueva base) y simulando 409 (se muestra tal cual).

## 4. Verificación integrada demo-local

- [x] 4.1 Levantar `docker compose up --build`, verificar `GET /health → 200`, `GET /ready → 200` (con `db`+`redis` sanos), frontend `/` y `/reservar` sirviendo placeholders, y `docker compose down -v` limpio; registrar evidencia (logs/status) para la review sin commitear (R-13).
