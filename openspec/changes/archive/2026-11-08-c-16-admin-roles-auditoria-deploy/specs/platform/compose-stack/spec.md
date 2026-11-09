# Spec Delta

## MODIFIED Requirements

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
