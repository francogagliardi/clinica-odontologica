# Compose Stack Specification

## Purpose

Provee el stack local contenerizado demo (api, frontend, db, redis) sobre el que corre la demo universitaria y todos los changes futuros.

## Requirements

### Requirement: Compose stack mínimo demo-local

El sistema SHALL proveer un `docker-compose.yml` con los servicios base `api`, `frontend`, `db` y `redis` y los cuatro workers de cola (`recordatorios`, `whatsapp`, `arca`, `reportes`) activos por defecto, cableados por DNS de servicio y configurados solo por variables de entorno. Las herramientas operativas (respaldo) SHALL vivir en un perfil opcional.

#### Scenario: Compose levanta verde

- **WHEN** un operador ejecuta `docker compose up --build` con solo los `.env.example` como referencia para crear sus `.env`
- **THEN** los servicios base y los cuatro workers alcanzan estado healthy/running, `db` persiste en el volumen nombrado `pgdata` y `redis` en `redisdata`

#### Scenario: Orden de arranque con gates

- **WHEN** `api` y los workers declaran dependencia de `db` y `redis`
- **THEN** Compose usa healthchecks + `depends_on` condicionado de modo que ningún proceso acepta trabajo antes de que `db` y `redis` estén healthy

#### Scenario: Perfil de herramientas separado

- **WHEN** se ejecuta `docker compose up` sin `--profile tools`
- **THEN** el servicio de respaldo no arranca y los servicios de la demo no dependen de él

#### Scenario: Reinicio de workers

- **WHEN** un worker de cola termina de forma inesperada
- **THEN** Compose lo reinicia y los servicios base siguen healthy

### Requirement: Imágenes pineadas non-root con secretos fuera de capas

Cada servicio SHALL usar Dockerfile multi-stage con imagen base pineada por versión/digest (nunca `:latest`), etapa de producción mínima corriendo como usuario non-root, y secretos solo vía `env_file`/`.env` gitignorado.

#### Scenario: Auditoría de imagen y secretos

- **WHEN** se inspeccionan `backend/Dockerfile`, `frontend/Dockerfile` y `docker-compose.yml`
- **THEN** no hay tag `:latest`, no hay `USER root` en etapa final, no hay secreto literal en capas ni en control de versiones, y existe `.dockerignore` excluyendo `.git`, `.env`, `node_modules`, `dist`, `__pycache__`

### Requirement: Puertos dev ligados a loopback

En desarrollo los puertos publicados SHALL ligarse a `127.0.0.1` y la configuración dev-only SHALL vivir en override, sin exponer superficies innecesarias.

#### Scenario: Binding loopback en dev

- **WHEN** se revisa la configuración de puertos de Compose para desarrollo
- **THEN** todo puerto publicado bindea `127.0.0.1` y el override dev monta el código para hot-reload con volúmenes anónimos protegiendo dependencias del contenedor
