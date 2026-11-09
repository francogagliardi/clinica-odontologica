# Proposal

## Why

El sistema ya agenda, atiende, cobra, factura, liquida y reporta, pero todavía no se puede administrar el acceso (usuarios y roles), no existe una superficie para leer la auditoría que la base ya protege, el alcance del enlace del paciente no está especificado como mínimo privilegio, y faltan la política de privacidad publicada y el respaldo cifrado que exige RN-SE-04. Además, el Compose actual no levanta los workers `arca` ni `reportes` y el seed no tiene el elenco ni los turnos ficticios que la demo necesita, por lo que US-040 y la entrega local (DD-12/P-05) quedan incompletas. C-16 es el último change del roadmap y cierra esa brecha.

## What Changes

- **Administración de acceso** (API + UI funcional):
  - `GET/POST /usuarios`, `GET/PATCH /usuarios/{id}`, `PUT /usuarios/{id}/roles` y `POST /usuarios/{id}/password`, solo para `administrador`. La API es la autoridad; la UI solo oculta lo que la API ya prohíbe.
  - Catálogo fijo de los cinco roles de la matriz (sin alta/edición/baja de roles nuevos); `GET /roles` de solo lectura.
  - Activación/desactivación lógica de cuentas, sin borrado físico; el login de una cuenta desactivada falla de inmediato.
  - Invariante del **último administrador activo**: desactivar o quitar el rol `administrador` que dejaría al sistema sin administrador responde `409` y no cambia nada, incluso con dos operaciones concurrentes.
  - Toda mutación aceptada deja una fila en `registro_auditoria`; las rechazadas no dejan filas.
- **Visor de auditoría** (`/auditoria`, solo lectura): `GET /auditoria` para `administrador` y `auditor`, con filtros por usuario, entidad, acción y rango de fechas, paginación acotada y orden estable. No existe endpoint de escritura y el visor no agrega filas de auditoría. UI funcional con filtros y tabla, sin controles de edición.
- **Paciente por enlace**: el enlace tokenizado sigue siendo por turno y de mínimo privilegio: cada token muestra solo su turno y datos de catálogo (profesional, prestación, seña, políticas); nunca el nombre/DNI/teléfono/email del paciente, otros turnos, historia clínica, presupuestos o cobros. No se agrega portal ni listado público de turnos (P-10: v1 solo enlaces tokenizados).
- **Privacidad y respaldo** (RN-SE-04):
  - Política de privacidad versionada en código, publicada sin autenticación en `GET /privacidad` y `GET /privacidad/{version}`, con texto completo y hash SHA-256. La página `/reservar` muestra un enlace informativo a la política, sin checkbox ni bloqueo.
  - La reserva pública NO cambia de contrato: `POST /reservar/{slug}/turnos` sigue funcionando sin campos de privacidad y no devuelve 422 ni 409 por este motivo. El consentimiento informado para prácticas invasivas sigue siendo de C-11.
  - Respaldo cifrado reproducible con un servicio Compose bajo perfil `tools`: `pg_dump` formato custom + cifrado AES-256/PBKDF2 con `BACKUP_PASSPHRASE` obligatoria, checksum SHA-256 y comando de verificación (descifra y lista el contenido). Los artefactos van a `backups/` (gitignored); no hay claves ni secretos en el repo.
  - El alcance legal (Ley 25.326/26.529) se documenta como validación humana/asesoramiento: el código no declara cumplimiento normativo.
- **Demo local y despliegue**:
  - Compose demo por defecto con `api` (Uvicorn), `frontend` servido, `db`, `redis` y los cuatro workers (`recordatorios`, `whatsapp`, `arca`, `reportes`); el respaldo vive en el perfil opcional `tools`.
  - Túnel documentado (cloudflared/ngrok) para publicar webhooks de Mercado Pago/WhatsApp, con `APP_BASE_URL` y secretos por `.env`; runbook de demo y definición de “flujo demo verde”.
  - Seed demo completo e idempotente: cinco roles, administrador, odontólogo, recepcionista, asistente y auditor; profesional vinculado; dos sillones; prestaciones; “OS Demo”; pacientes ficticios y turnos de la próxima jornada hábil. Nuevas variables `SEED_DEMO_PASSWORD` y `BACKUP_PASSPHRASE`, sin defaults.
- **Migración `0015_admin_auditoria`**: solo índices para el visor (`timestamp`, `acción+fecha`, `entidad+fecha`). No crea tablas de dominio, no agrega índices de aceptación y no altera datos.
- **Pruebas**: matriz RBAC e2e por rol (403/401 donde corresponde), invariante del último administrador y concurrencia, auditor no escribe, paciente no ve datos ajenos, publicación de política y enlace informativo, reserva pública sin cambio de contrato, seed idempotente, `docker compose config`/arranque, respaldo cifrado (ida y vuelta, passphrase incorrecta, sin texto plano) y flujo demo documentado.

## Capabilities

### New Capabilities

- `admin/gestion-acceso`: alta, edición, activación y desactivación de usuarios del backoffice, asignación de los roles fijos, contraseñas y la invariante que impide quedarse sin administrador, con RBAC y auditoría de cada mutación.
- `admin/auditoria`: consulta paginada y filtrable del registro append-only para administrador y auditor, sin ninguna vía de escritura ni alteración del historial.
- `privacy/privacidad-respaldo`: publicación versionada de la política de privacidad y respaldo cifrado verificable, con el alcance legal documentado como validación humana.
- `platform/demo-deploy`: stack demo local completo con workers, exposición pública por túnel, variables documentadas y flujo demo de punta a punta reproducible.

### Modified Capabilities

- `agenda/reserva-publica`: se agrega solo el alcance mínimo privilegiado del enlace del paciente; no cambia el contrato de reserva ni se agrega aceptación de privacidad.
- `security/core-models`: el seed deja de ser mínimo y pasa a crear el elenco y los datos ficticios de la demo, manteniendo idempotencia y credenciales por entorno.
- `platform/compose-stack`: el stack base incorpora los cuatro workers por defecto y un perfil opcional de herramientas para el respaldo.

## Impact

- **Backend**: `app/api/usuarios.py` (nuevo; se separa de `auth.py`), `app/api/roles.py` (o rutas en el anterior), `app/api/auditoria.py`, `app/api/privacidad.py`, `app/application/acceso.py`, `app/application/auditoria.py`, `app/application/privacidad.py`, `app/domain/privacidad.py`, `app/schemas/usuarios.py`, `app/schemas/auditoria.py`, `app/schemas/privacidad.py`, `app/infrastructure/repositories.py`, `app/infrastructure/uow.py`, `app/infrastructure/audit.py`, `app/seed.py`, `app/core/settings.py`.
- **Migración**: `backend/alembic/versions/0015_admin_auditoria.py` (`down_revision='0014_reportes'`): solo índices del visor; sin tablas nuevas y sin índice de aceptación. `downgrade` elimina solo esos índices.
- **Frontend**: `features/usuarios/api.ts`, `features/auditoria/api.ts`, `features/privacidad/api.ts`, `pages/UsuariosPage.tsx`, `pages/AuditoriaPage.tsx`, `pages/PrivacidadPage.tsx`, enlace informativo a la política en `ReservaPage.tsx` (sin checkbox ni bloqueo) y rutas en `App.tsx`; pruebas Vitest. Sin sistema de diseño (C-17).
- **Compose / operaciones**: `docker-compose.yml` (workers `arca` y `reportes`, perfil `tools`, servicio `backup`), `ops/backup/Dockerfile` y `ops/backup/backup.sh`, `docs/demo.md` (runbook, túnel, respaldo), `README.md`/`docs/validacion-manual-pendiente.md`, `.env.example`, `.gitignore` (`backups/`).
- **Configuración**: `SEED_DEMO_PASSWORD` y `BACKUP_PASSPHRASE` (obligatorias, sin default), más las URLs públicas del túnel documentadas. Ningún secreto real en el repo.
- **Dependencias**: ninguna biblioteca nueva de aplicación; el respaldo usa `postgres:16-alpine` + `openssl` en una imagen de herramientas separada. `fpdf2` y el resto del stack quedan igual.
- **Fuera de alcance**: portal o cuentas de paciente (US-052), CRUD de roles nuevos, diseño visual (C-17), validación legal automática, aceptación de privacidad al reservar (el consentimiento informado clínico sigue en C-11), hospedaje pago o nube obligatoria (P-05 sigue con default local), purga de auditoría o de exportaciones, y restauración automática de respaldos.
