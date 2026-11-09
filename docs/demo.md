# Demo local de punta a punta (C-16)

Runbook reproducible para la entrega universitaria. Todo corre con Docker
Compose y datos ficticios: no hay pacientes, tokens ni claves reales en el
repositorio.

## 1. Requisitos

- Docker Desktop con Compose v2.
- Puertos libres: `8000` (API), `8080` (SPA), `5432` (PostgreSQL) y `6379`
  (Redis). Si alguno está ocupado, usá un override local (ver §10).
- No hace falta Python, Node ni PostgreSQL en el host.

## 2. Variables de entorno

```bash
cp backend/.env.example backend/.env
```

Editá `backend/.env` (gitignored) y generá valores propios. Mínimo obligatorio:

| Variable | Para qué | Default |
|---|---|---|
| `JWT_SECRET` | firma de tokens del backoffice | **sin default** |
| `POSTGRES_PASSWORD` | inicializa el contenedor `db`; debe coincidir con `DATABASE_URL` | **sin default real** |
| `DATABASE_URL` | conexión de la API (`...@db:5432/clinica`) | placeholders |
| `REDIS_URL` | colas y jobs (`redis://redis:6379/0`) | placeholders |
| `SEED_ADMIN_PASSWORD` | contraseña del administrador demo | **sin default** |
| `SEED_DEMO_PASSWORD` | contraseña de los cuatro usuarios del elenco | **sin default** |
| `BACKUP_PASSPHRASE` | cifra el respaldo AES-256 | **sin default** |
| `APP_BASE_URL` | URL pública para enlaces de gestión y webhooks | `http://127.0.0.1:8080` |
| `WHATSAPP_*`, `MP_*`, `ARCA_*` | integraciones sandbox/homologación | placeholders |

Nunca commitees `backend/.env`. El seed y el respaldo abortan nombrando la
variable si falta un secreto, antes de escribir datos.

## 3. Arranque

```bash
docker compose up -d --build
docker compose ps
```

Esperado: **8 servicios** `running`/`healthy`: `db`, `redis`, `api`,
`frontend`, `worker-recordatorios`, `worker-whatsapp`, `worker-arca` y
`worker-reportes`. El respaldo (`backup`) no arranca: vive en el perfil `tools`.

| Servicio | URL local |
|---|---|
| SPA | http://127.0.0.1:8080 |
| API / Swagger | http://127.0.0.1:8000/docs |
| Health / readiness | http://127.0.0.1:8000/health · `/ready` |
| PostgreSQL | 127.0.0.1:5432 |
| Redis | 127.0.0.1:6379 |

## 4. Migraciones y seed

```bash
docker compose exec -T api alembic upgrade head
docker compose exec -T api python -m app.seed
```

El seed es idempotente y serializa corridas concurrentes con un advisory lock:

- 5 roles, 1 consultorio `demo`, 2 sillones, 5 prestaciones, “OS Demo”.
- 5 usuarios: administrador + odontólogo, recepción, asistente y auditor.
- 1 profesional `MP-DEMO-1` vinculado al odontólogo y habilitado en los dos sillones.
- 3 pacientes ficticios (Ana, Bruno y Carla Demo).
- 3 turnos de la próxima jornada hábil (09:00, 10:00 y 11:00) en estados
  `reservado`, `confirmado` y `en_sala`.
- Reejecutarlo no duplica filas ni reescribe contraseñas ya guardadas.

## 5. Credenciales demo

Las contraseñas **no** están en el repo: son las que definas en `backend/.env`.

| Usuario | Email | Rol |
|---|---|---|
| Administrador | `admin@clinica.test` | `administrador` |
| Odontólogo | `odonto.demo@clinica.test` | `odontologo` |
| Recepción | `recepcion.demo@clinica.test` | `recepcionista` |
| Asistente | `asistente.demo@clinica.test` | `asistente` |
| Auditor | `auditor.demo@clinica.test` | `auditor` |

El administrador usa `SEED_ADMIN_PASSWORD`; los otros cuatro usan
`SEED_DEMO_PASSWORD`. Cambiarlas en `.env` y volver a sembrar **no** rota los
hashes existentes (para resetear credenciales hay que recrear el volumen).

## 6. Túnel público (webhooks)

La demo local funciona sin túnel. Para recibir webhooks de Mercado Pago o
WhatsApp, publicá la API:

```bash
# cloudflared
cloudflared tunnel --url http://127.0.0.1:8000

# o ngrok
ngrok http 8000
```

Luego:

1. Copiá la URL pública (por ejemplo `https://algo.trycloudflare.com`).
2. Ajustá `APP_BASE_URL` en `backend/.env` a la URL del **frontend** o de la API
   según corresponda al enlace que quieras emitir y reiniciá `api`:
   `docker compose up -d api`.
3. Registrá en Mercado Pago/WhatsApp los webhooks:
   - `POST {URL_PUBLICA}/webhooks/mercadopago`
   - `POST {URL_PUBLICA}/webhooks/whatsapp`
   usando `MP_WEBHOOK_SECRET` y `WHATSAPP_APP_SECRET` del `.env`.
4. Si el túnel cae, el stack local sigue funcionando (reserva, agenda, caja y
   reportes). Reabrí el túnel y actualizá `APP_BASE_URL` cuando vuelva a estar
   disponible.

## 7. Respaldo cifrado y verificación

El servicio `backup` vive en el perfil `tools` y monta `./backups` (gitignored).

```bash
# crear respaldo (pg_dump -Fc + AES-256-CBC/PBKDF2)
docker compose --profile tools run --rm backup backup

# verificar: checksum + descifra hacia `pg_restore --list` sin escribir claro
docker compose --profile tools run --rm backup verify /backups/clinica-<UTC>.dump.enc
```

Resultados esperados:

- Se crean `clinica-<UTC>.dump.enc` y `.sha256` en `backups/`.
- La verificación correcta imprime `OK`.
- Con `BACKUP_PASSPHRASE` incorrecta falla sin imprimir el contenido.
- Alterar un byte hace fallar el checksum antes de descifrar.
- El archivo cifrado no contiene `CREATE TABLE` ni nombres de pacientes.

## 8. Flujo demo verde

| # | Paso | Resultado observable |
|---|---|---|
| 1 | `docker compose ps` | 8 servicios running/healthy |
| 2 | `/health` y `/ready` | `ok` / `ready` con `db=up` y `redis=up` |
| 3 | `GET /privacidad` | 200 con versión, texto, hash y `alcance_legal_validado=false` |
| 4 | Abrir `/reservar`, elegir profesional, prestación y horario | catálogo y slots reales, sin login |
| 5 | Completar la reserva | 201; enlace de gestión; sin checkbox de privacidad |
| 6 | Abrir el enlace de gestión | 200 con el turno y datos de catálogo, sin PII del paciente |
| 7 | Login de los cinco roles | 200 con el rol esperado |
| 8 | `/agenda` con el odontólogo | agenda con los tres turnos demo |
| 9 | Historia clínica / presupuesto / caja (Swagger o UI) | 200/201 según matriz de roles |
| 10 | `POST /exportaciones` como admin y worker `reportes` | 202 → `lista`; ZIP descargable |
| 11 | `GET /auditoria` como admin y auditor | 200 con filas trazables; lectura no agrega filas |
| 12 | Respaldo + verificación | archivo cifrado, checksum y `OK` |

Un `500`, un 403 inesperado o un ZIP sin manifiesto bloquean el cierre.

Nota de privacidad: la política se **publica y enlaza** desde `/reservar`; la
reserva **no** exige aceptación (decisión C-16/D7). El consentimiento clínico de
prácticas invasivas sigue en C-11.

## 9. Reejecución y limpieza

```bash
docker compose exec -T api python -m app.seed   # idempotente
docker compose down                              # conserva pgdata/redisdata
docker compose up -d                            # los datos siguen ahí
docker compose down -v                          # borra volúmenes (demo desde cero)
```

## 10. Conflictos de puerto

Si `5432`, `6379`, `8000` o `8080` están ocupados, creá un override **local**
(gitignored) o un archivo temporal fuera del repo:

```yaml
services:
  db:
    ports: !override
      - "127.0.0.1:15433:5432"
  redis:
    ports: !override
      - "127.0.0.1:6380:6379"
  api:
    ports: !override
      - "127.0.0.1:18000:8000"
  frontend:
    ports: !override
      - "127.0.0.1:18080:8080"
```

Y ejecutá `docker compose -f docker-compose.yml -f <override> up -d --build`.
No commitees overrides con datos del host.

## 11. Límites conocidos

- No hay sistema de diseño (C-17): las pantallas son funcionales.
- Datos ficticios de demo; no cargar información de pacientes reales.
- El respaldo verifica el dump; la restauración automatizada queda como
  procedimiento manual y fuera de C-16.
- El alcance legal de la política de privacidad requiere asesoramiento humano;
  el código no declara cumplimiento normativo.
