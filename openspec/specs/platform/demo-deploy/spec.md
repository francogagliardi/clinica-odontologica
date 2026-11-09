# platform/demo-deploy Specification

## Purpose
Define y verifica el stack demo local completo —API, SPA, PostgreSQL, Redis y los cuatro workers—, su exposición pública por túnel y un flujo de demostración reproducible de punta a punta para la entrega universitaria.

## Requirements

### Requirement: Stack demo completo con workers por defecto

`docker compose up -d --build` SHALL iniciar `api`, `frontend`, `db`, `redis` y los workers `recordatorios`, `whatsapp`, `arca` y `reportes` sin perfiles adicionales. Los workers SHALL esperar `db` y `redis` healthy y reiniciarse si caen; `api` y `frontend` SHALL exponer healthchecks. El respaldo SHALL quedar en el perfil `tools`.

**Trazabilidad**: DD-07c/DD-07e, DD-12/P-05, `platform/compose-stack`, `platform/job-queues`, CHANGES.md §C-16.

#### Scenario: Arranque por defecto con todos los servicios

- **WHEN** se ejecuta `docker compose up -d --build` con los `.env` documentados
- **THEN** `docker compose config --services` incluye los cuatro servicios base y los cuatro workers, y todos alcanzan estado running/healthy

#### Scenario: Gates de arranque

- **WHEN** `db` o `redis` todavía no están healthy
- **THEN** `api` y los workers no aceptan trabajo hasta que ambas dependencias estén healthy

#### Scenario: Perfil de herramientas no arranca por defecto

- **WHEN** se levanta el stack sin `--profile tools`
- **THEN** el servicio de respaldo no se inicia y el flujo demo no depende de él

#### Scenario: Reinicio de un worker caído

- **WHEN** un worker termina de forma inesperada
- **THEN** Compose lo reinicia sin afectar a `api`, `frontend`, `db` ni `redis`

### Requirement: Túnel y URL pública documentados

El runbook SHALL documentar cómo exponer la API por túnel, fijar `APP_BASE_URL` a la URL pública y registrar los webhooks de Mercado Pago y WhatsApp con sus secretos. La configuración no SHALL contener URLs ni secretos reales; el flujo local SHALL seguir funcionando si el túnel cae.

**Trazabilidad**: DD-12/P-05, `08_arquitectura_propuesta.md` §Despliegue, R-08/R-12.

#### Scenario: Webhook entrante por túnel

- **WHEN** se publica la API con el túnel documentado y se envía un webhook firmado de WhatsApp o Mercado Pago a la URL pública
- **THEN** el endpoint responde 200 y aplica el evento una sola vez

#### Scenario: Firma inválida por túnel

- **WHEN** el webhook llega sin firma o con firma adulterada
- **THEN** responde 401 y no modifica turnos ni cobros

#### Scenario: Túnel caído

- **WHEN** el túnel se detiene mientras el stack local sigue arriba
- **THEN** la demo local (reserva, agenda, caja, reportes) sigue funcionando y el runbook indica cómo reabrir el túnel y actualizar `APP_BASE_URL`

### Requirement: Entorno documentado y sin secretos reales

`.env.example` SHALL listar todas las variables requeridas, incluidas `SEED_DEMO_PASSWORD`, `BACKUP_PASSPHRASE`, `APP_BASE_URL` y las URLs de webhooks, con placeholders y sin valores reales. Un arranque con un secreto obligatorio faltante SHALL fallar con un mensaje que nombre la variable, sin escribir credenciales en el repositorio.

**Trazabilidad**: R-08 (`AGENTS.md`), `08_arquitectura_propuesta.md` §Variables de entorno, DD-12, R-13.

#### Scenario: Inventario de variables

- **WHEN** se compara `.env.example` con las variables que leen la API, el seed, los workers y el respaldo
- **THEN** todas aparecen documentadas y ninguna tiene un valor real o una clave privada

#### Scenario: Secreto obligatorio faltante

- **WHEN** se arranca sin `JWT_SECRET`, se ejecuta el seed sin `SEED_ADMIN_PASSWORD` o `SEED_DEMO_PASSWORD`, o el respaldo sin `BACKUP_PASSPHRASE`
- **THEN** cada proceso falla con un mensaje que nombra la variable y no crea datos parciales

#### Scenario: Sin secretos en el control de versiones

- **WHEN** se busca en el repo un token de Meta, Mercado Pago o ARCA, una passphrase de respaldo o una contraseña demo real
- **THEN** solo aparecen placeholders y los `.env` reales están gitignored

### Requirement: Flujo demo verde de punta a punta

El runbook SHALL definir el flujo demo verde: stack healthy, migraciones, seed idempotente, reserva pública, confirmación/cancelación por enlace, WhatsApp simulado, agenda, historia, presupuesto, cobro/MP, comprobante ARCA, reporte, exportación, usuarios y auditoría. Cada paso SHALL indicar el resultado observable y un fallo SHALL bloquear el cierre.

**Trazabilidad**: US-040/US-041, RN-SE-01..04, DD-12/P-05, `docs/validacion-manual-pendiente.md`.

#### Scenario: Recorrido completo en verde

- **WHEN** un operador sigue el runbook sobre una base migrada y sembrada
- **THEN** cada paso produce el resultado esperado, desde la reserva pública hasta la consulta de auditoría, sin errores 500

#### Scenario: Fallo representativo de negocio

- **WHEN** el recorrido intenta una acción fuera de la matriz (por ejemplo, recepción exportando el consultorio) o un solapamiento de agenda
- **THEN** la API responde 403 o 409 y la pantalla muestra el mensaje, sin continuar el flujo como si hubiera funcionado

#### Scenario: Reejecución del seed y reinicio del stack

- **WHEN** se vuelve a ejecutar el seed y se reinicia el stack con `docker compose down` y `up`
- **THEN** no se duplican roles, usuarios, pacientes ni turnos, y los volúmenes `pgdata`/`redisdata` conservan los datos de la demo

#### Scenario: Evidencia del cierre

- **WHEN** el flujo termina en verde
- **THEN** quedan guardadas las salidas de tests, el resultado del smoke, la verificación de migración y del respaldo en `docs/skills-mcp/evidencias/c-16/`
