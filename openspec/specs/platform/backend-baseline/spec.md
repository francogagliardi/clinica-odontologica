# Backend Baseline Specification

## Purpose

Establece el baseline ejecutable del backend FastAPI (layout, health, config por entorno, migraciones) sobre el que se montan dominio, auth y workers.

## Requirements

### Requirement: Layout FastAPI baseline con health y readiness

El backend SHALL exponer `GET /health` (liveness, sin dependencias) y `GET /ready` (readiness: PostgreSQL y Redis alcanzables) en respuestas JSON versionadas, con el layout `app/` (`domain/ application/ infrastructure/ models/ schemas/ api/ core/ workers/ main.py`) y `api/deps.py` como punto de DI.

#### Scenario: Liveness sin dependencias

- **WHEN** un orquestador llama `GET /health` con `db` y `redis` caídos
- **THEN** responde `200` con `{"status": "ok", "service": "api"}` sin intentar conexiones externas

#### Scenario: Readiness refleja dependencias

- **WHEN** un operador llama `GET /ready` con `db` y `redis` sanos
- **THEN** responde `200` con checks `{"db": "up", "redis": "up"}`; si alguna dependencia cae responde `503` identificando cuál

### Requirement: Configuración solo por variables de entorno

La configuración SHALL leerse exclusivamente de variables de entorno documentadas en `backend/.env.example` (`DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, WHATSAPP_API_TOKEN, WHATSAPP_PHONE_ID, MP_ACCESS_TOKEN, ARCA_CUIT, ARCA_CERT, ARCA_KEY, APP_BASE_URL`), sin defaults hardcodeados para secretos.

#### Scenario: Falta secreto obligatorio

- **WHEN** se arranca `api` sin `JWT_SECRET` o `DATABASE_URL`
- **THEN** el arranque falla con mensaje que nombra la variable faltante y no usa ningún fallback inseguro

### Requirement: Fronteras RORO async con errores tipados

Todo borde HTTP del baseline SHALL usar routers + esquemas Pydantic v2 (`extra="forbid"`), firmas con type hints completos en `snake_case`, `async def` para I/O y `HTTPException` con código específico ante errores esperados.

#### Scenario: Payload con campo extra es rechazado

- **WHEN** un cliente envía a cualquier endpoint baseline un JSON con un campo no declarado en el esquema
- **THEN** la API responde `422` y no procesa la petición

### Requirement: Alembic inicializado sin migraciones de dominio

El repo SHALL incluir Alembic configurado contra `DATABASE_URL` con directorio `versions/` sin migraciones de dominio; todo cambio futuro de esquema SHALL llegar como migración declarativa versionada, nunca DDL ad-hoc.

#### Scenario: Estado migratorio limpio

- **WHEN** se ejecuta `alembic heads` y `alembic history` sobre un checkout fresco
- **THEN** existe exactamente una head base (sin tablas de dominio) y el historial no contiene `CREATE TABLE` de dominio
