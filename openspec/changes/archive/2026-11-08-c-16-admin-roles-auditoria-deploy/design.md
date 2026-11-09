# Design

## Context

Ver `proposal.md` para la motivación. El estado relevante del repo:

- C-15 dejó el head de migraciones en `0014_reportes`. Ya existen `Consultorio`, `Usuario`, `Rol`, `UsuarioRol` y `RegistroAuditoria` append-only (triggers `P0001` para `UPDATE`/`DELETE`/`TRUNCATE`).
- `GET /usuarios` existe solo como smoke de RBAC (lista usuarios activos para `administrador`); no hay alta, edición, activación, asignación de roles ni cambio de contraseña.
- `require_role` relee roles y `is_active` de PostgreSQL en cada request; un rol revocado o una cuenta desactivada pierden acceso sin esperar al vencimiento del JWT.
- El enlace público es por turno: `tokens_un_solo_uso` con `tipo='gestion_turno'`, `GET /reservar/gestion/{token}` y acciones que consumen el token. La respuesta ya omite datos personales del paciente.
- `RegistroAuditoria` no tiene `updated_at`/`deleted_at`; `AuditoriaRepository` solo expone `add/get/list`. No hay endpoint HTTP de lectura.
- `docker-compose.yml` levanta `api`, `frontend`, `db` y `redis`; solo `worker-recordatorios` y `worker-whatsapp` existen bajo el perfil `workers`. Faltan `arca` y `reportes`. El backend es `python:3.12-slim` (tiene `openssl`, no `pg_dump`); `postgres:16-alpine` tiene `pg_dump` y no el CLI de `openssl`.
- `app/seed.py` crea solo los cinco roles, el consultorio y el administrador. `docs/validacion-manual-pendiente.md` ya describe un elenco demo y turnos que el código todavía no crea.
- La SPA usa un router por `pathname` en `App.tsx`, sesión en memoria y `fetchJson`/`postJson`; los errores de la API se muestran verbatim.
- Governance ALTO; C-16 es el último change. La decisión del usuario del 2026-11-03 cierra sin gate de aprobación manual por change: la aceptación funcional se hace al final sobre la página completa.

## Goals / Non-Goals

**Goals:**

- Administrar usuarios y roles desde la API y una UI funcional, sin dejar el sistema sin administrador y con trazabilidad de cada mutación.
- Leer la auditoría append-only sin abrir ninguna vía de escritura.
- Fijar el mínimo privilegio del enlace del paciente y publicar la política de privacidad sin bloquear la reserva.
- Entregar un respaldo cifrado reproducible y verificado.
- Dejar el Compose demo y el seed completos, con un flujo demo verificable de punta a punta.

**Non-Goals:**

- Portal o cuentas de paciente, historial clínico por enlace (US-052).
- CRUD de roles nuevos o permisos configurables; la matriz de `03_actores_y_roles.md` es fija en v1.
- Diseño visual o sistema de componentes (C-17); la UI es funcional.
- Validación legal automática o declaración de cumplimiento normativo.
- Hospedaje pago, nube obligatoria o túnel gestionado por la aplicación.
- Purga de auditoría/exportaciones, restauración automática de respaldos o cifrado de columnas.

## Decisions

### D1 — Cuatro capabilities nuevas y tres deltas acotados

**Decisión**: `admin/gestion-acceso` (usuarios/roles), `admin/auditoria` (visor), `privacy/privacidad-respaldo` (política y respaldo) y `platform/demo-deploy` (stack, túnel y flujo demo). Se modifican `security/core-models` (seed completo), `platform/compose-stack` (workers por defecto) y `agenda/reserva-publica` (solo alcance del enlace del paciente), esta última con requisitos ADDED para no reescribir el contrato de C-07.

**Por qué**: cada capability tiene un borde observable distinto y un dueño claro. Mezclar acceso con auditoría obligaría a que cada cambio de usuarios arrastre el visor; mezclar privacidad con deploy mezclaría datos de salud con operaciones.

**Alternativa descartada**: una sola capability `admin-security`. Menos archivos, pero los escenarios de PII, respaldo y demo quedan diluidos y los deltas de seed/compose se vuelven implícitos.

### D2 — Invariante del último administrador con lock global y 409

**Decisión**: toda operación que pueda desactivar una cuenta o quitar el rol `administrador` ejecuta, al inicio de su transacción, `pg_advisory_xact_lock` con una clave constante del módulo. Luego aplica el cambio, cuenta los usuarios activos con rol `administrador` activo y, si el resultado es cero, lanza HTTP 409 y el `UnitOfWork` revierte. La auto-desactivación se rechaza siempre con 409; la auto-remoción del rol se permite solo si queda otro administrador.

**Por qué**: contar antes y escribir después no es atómico frente a dos transacciones que desactivan a dos administradores distintos: ambas podrían ver dos y confirmar cero. El advisory lock serializa solo las mutaciones de acceso (bajo volumen) y no bloquea al resto del dominio. El 409 expresa un conflicto con el estado actual, no un error de formato (422).

**Alternativa descartada**: `LOCK TABLE usuario_roles` o `usuarios` en modo exclusivo. Funciona, pero bloquea lecturas/repositorios no relacionados y es más difícil de razonar en tests concurrentes. **Alternativa descartada**: un trigger de base que cuente administradores. Pondría una regla de negocio en SQL difícil de mapear a un mensaje HTTP y de testear por API.

### D3 — Catálogo fijo de cinco roles; sin CRUD de roles

**Decisión**: `GET /roles` lista los cinco roles sembrados; `PUT /usuarios/{id}/roles` reemplaza el conjunto. No se crean, renombran ni borran roles por API. Los roles desconocidos y las listas vacías responden 422.

**Por qué**: la matriz de `03_actores_y_roles.md` asigna permisos por nombre de rol y el código usa `require_role("administrador", ...)`. Un rol nuevo no tendría columna en la matriz ni guards, así que crearlo sería una ilusión de permiso. La UI muestra el catálogo, no un formulario de roles.

**Alternativa descartada**: CRUD de roles con permisos configurables. Es un producto distinto (RBAC dinámico), exige tablas de permisos y cambia toda la matriz; queda fuera de v1.

### D4 — Activación lógica, sin borrado físico, y contraseña write-only

**Decisión**: `PATCH /usuarios/{id}` acepta `nombre`, `email` y `activo`. Desactivar pone `is_active=false` y deja `deleted_at` intacto; reactivar lo vuelve a `true`. No hay `DELETE /usuarios`. `POST /usuarios/{id}/password` fija una contraseña nueva con bcrypt. El email se normaliza a minúsculas y el índice parcial de unicidad sigue aplicando a filas con `deleted_at IS NULL`.

**Por qué**: el historial de auditoría, turnos y evoluciones referencia `usuarios.id`; un borrado físico rompería la trazabilidad. La baja lógica de C-02 se reserva para un borrado administrativo futuro; la desactivación es la operación reversible que la demo necesita. No devolver el hash ni la contraseña es R-03.

**Trade-off**: una cuenta desactivada conserva su email y bloquea reutilizarlo hasta una baja lógica; se acepta porque la reactivación es el caso esperado.

### D5 — Visor de auditoría: dos roles, solo lectura, filtros acotados

**Decisión**: `GET /auditoria` para `administrador` y `auditor`, con `usuario_id`, `entidad`, `accion`, `desde`, `hasta`, `limite` (default 100, máximo 500) y `offset` (≥0). Orden `timestamp DESC, id DESC`; `total` antes de paginar; fechas UTC-3 inclusivas; parámetros no declarados 422. El odontólogo no ve la auditoría en v1; recepción y asistente tampoco.

**Por qué**: la matriz no tiene columna “Auditoría”; el actor Auditor está definido como “consulta de trazabilidad”, y el administrador es quien controla accesos. Dar al odontólogo sus propias filas requeriría una regla de alcance que la KB no fija y que el visor no necesita para la demo. La lectura no se audita: RN-SE-02 pide quién registró qué, y auditar cada refresco ahogaría la tabla sin agregar trazabilidad de escritura.

**Alternativa descartada**: cursor keyset. Más eficiente en tablas enormes, pero la demo y el máximo de 500 filas no lo justifican; `offset` es más simple de especificar y testear. Los índices de D11 sostienen el orden y los filtros.

### D6 — Enlace del paciente por turno, sin portal ni listado

**Decisión**: se mantiene un token `gestion_turno` por turno. No se agrega `/mis-turnos` ni un token de paciente. `GET /reservar/gestion/{token}` sigue devolviendo solo el turno y datos de catálogo; el paciente no ve nombre/DNI/teléfono/email, historia, presupuestos ni cobros. No existe listado público de turnos.

**Por qué**: RN-SE-01 exige que el paciente opere solo sus propios turnos/datos, y P-10 confirma que v1 usa enlaces tokenizados, no cuentas. Un token por turno es el mínimo privilegio: un enlace filtrado no enumera la vida clínica del paciente. Un endpoint “mis turnos” con un token de paciente ampliaría el blast radius sin un requisito de producto.

**Alternativa descartada**: token de paciente con listado de turnos. Útil para un portal, pero es US-052 y exige decidir autenticación, revocación y alcance de datos clínicos; fuera de C-16.

### D7 — Privacidad: publicación versionada y enlace informativo, sin aceptación

**Decisión**:

- `app/domain/privacidad.py` contiene `VERSION_ACTUAL`, `VIGENTE_DESDE`, `TEXTOS` y el hash SHA-256 canónico. `GET /privacidad` y `GET /privacidad/{version}` son públicos, no tocan la base y no exponen datos personales.
- `/reservar` muestra un enlace informativo a `/privacidad`. No hay checkbox, paso de aceptación ni bloqueo de la reserva.
- `ReservaCreate` y `POST /reservar/{slug}/turnos` **no cambian**: no se agregan `acepta_privacidad` ni `politica_version`, y una reserva válida sigue respondiendo 201 sin 422/409 por privacidad.
- No se registra un evento `privacidad.aceptada`, no se crea tabla de aceptaciones y no se agrega índice de aceptación. El consentimiento informado para prácticas invasivas sigue siendo el de C-11.

**Por qué** (decisión del usuario, 2026-11-08): publicar la política satisface la parte demostrable de RN-SE-04 sin convertir la reserva en un formulario de consentimiento ni romper C-07. El alcance legal se valida con asesoramiento humano; el código no puede convertir una casilla en cumplimiento normativo. Mezclar privacidad con consentimiento clínico confundiría dos obligaciones distintas.

**Alternativa descartada**: aceptación obligatoria al reservar. Es un cambio breaking de C-07, exige migración/índice y un evento de auditoría, y aun así no aporta validez legal. Si más adelante se exige, será un change propio con su propio contrato y análisis.

**Consecuencia aceptada**: no queda prueba de que el paciente haya leído la política; se documenta como límite y la aceptación clínica sigue en C-11.

### D8 — Respaldo cifrado en una imagen de herramientas separada

**Decisión**: `ops/backup/Dockerfile` parte de `postgres:16-alpine` (pineada por digest), instala `openssl` con `apk add --no-cache` y copia `backup.sh`. El script tiene dos modos:

- `backup`: exige `BACKUP_PASSPHRASE`, ejecuta `pg_dump -Fc --no-owner --no-acl` contra `db`, cifra con `openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:BACKUP_PASSPHRASE` y escribe `/backups/clinica-<UTC>.dump.enc` + `.sha256`.
- `verify`: exige archivo y passphrase, valida el checksum y descifra hacia `pg_restore --list` sin escribir el dump en claro.

Compose lo expone como servicio `backup` bajo `profiles: ["tools"]`, con `env_file: ./backend/.env`, volumen `./backups:/backups` y `depends_on: db healthy`. `backups/` se agrega a `.gitignore`.

**Por qué**: el host es Windows y no se puede asumir `openssl` ni `pg_dump` instalados. Un contenedor con ambas herramientas hace el comando reproducible con solo Docker. `python:3.12-slim` tiene `openssl` pero no `pg_dump`; `postgres:16-alpine` tiene `pg_dump` pero no el CLI de `openssl`; la imagen de herramientas combina ambos sin engordar la API.

**Límite aceptado**: AES-256-CBC con PBKDF2 no es AEAD; el checksum detecta corrupción accidental, no un ataque activo con reemplazo. Para una demo con datos ficticios y artefactos fuera del repo es suficiente; un change posterior puede migrar a `age`/GPG o a un KMS. La passphrase no se guarda en la imagen ni en el repo.

**Alternativa descartada**: `pg_dump` en el host + cifrado con PowerShell. Depende de herramientas del sistema y no es reproducible entre Windows/macOS/Linux. **Alternativa descartada**: guardar el respaldo en PostgreSQL o Redis; contradice R-04/R-06.

### D9 — Compose demo con los cuatro workers por defecto y `tools` para operaciones

**Decisión**: `worker-arca` y `worker-reportes` se agregan al `docker-compose.yml`; los cuatro workers dejan de estar bajo `profiles: ["workers"]` y arrancan con `docker compose up -d --build`. Todos dependen de `db` y `redis` healthy y usan `restart: unless-stopped`. `api` y `frontend` conservan sus healthchecks. El respaldo queda en `profiles: ["tools"]`. El túnel no se contenedoriza: se documenta con cloudflared/ngrok y se configura `APP_BASE_URL`.

**Por qué**: la demo incluye recordatorios, WhatsApp, ARCA y exportaciones; si los workers no arrancan por defecto, esos flujos quedan “pendientes” y el smoke no puede ser verde. El perfil `tools` evita que un respaldo se ejecute en cada arranque.

**“Flujo demo verde”**: `docker compose up -d --build` deja los ocho servicios running/healthy; migraciones y seed corren; el runbook recorre reserva pública, gestión por enlace, WhatsApp simulado, agenda, historia, presupuesto, cobro/MP, comprobante ARCA, reporte, exportación, usuarios y auditoría; cada paso tiene resultado esperado y ningún 500. Un fallo bloquea el cierre.

### D10 — Seed completo, idempotente y con datos ficticios

**Decisión**: `run_seed(session, admin_password, demo_password)`:

1. Toma `pg_advisory_xact_lock` con clave constante para serializar seeds concurrentes.
2. Upserts por clave natural con `ON CONFLICT DO NOTHING`: cinco roles, consultorio `demo`, cinco usuarios (`admin@clinica.test`, `odonto.demo@clinica.test`, `recepcion.demo@clinica.test`, `asistente.demo@clinica.test`, `auditor.demo@clinica.test`), vínculos `UsuarioRol`, profesional `MP-DEMO-1` vinculado al odontólogo, dos sillones, prestaciones, “OS Demo”, tres pacientes y la habilitación profesional↔sillón.
3. Crea tres turnos de la próxima jornada hábil (09:00, 10:00 y 11:00, estados `reservado`, `confirmado`, `en_sala`) solo si el consultorio no tiene turnos; así la reejecución no duplica y una base reseteada vuelve a tener agenda futura.
4. Usa `SEED_ADMIN_PASSWORD` para el administrador y `SEED_DEMO_PASSWORD` para el elenco. Ambas son obligatorias en el CLI; si falta una, aborta antes de escribir.

**Por qué**: el seed de C-02 era deliberadamente mínimo y su spec decía que el elenco era de C-16. La presencia de turnos como guard es más simple que un `ON CONFLICT` sobre una tabla sin clave natural de demo; el advisory lock cubre la carrera de dos seeds. Las fechas relativas evitan un demo con turnos vencidos.

**Límite**: si la base ya tiene turnos de una corrida anterior, el seed no agrega agenda nueva; para una demo fresca se resetea el volumen o se crean turnos desde la UI. Se documenta en el runbook.

### D11 — Migración `0015_admin_auditoria`: solo índices

**Decisión** (`down_revision='0014_reportes'`):

- `ix_registro_auditoria_timestamp` sobre `(timestamp DESC, id DESC)`.
- `ix_registro_auditoria_accion_timestamp` sobre `(accion, timestamp DESC)`.
- `ix_registro_auditoria_entidad_timestamp` sobre `(entidad, timestamp DESC)`.

**Downgrade**: `DROP INDEX` de los tres. No hay tablas nuevas, backfill ni cambios de columnas. No se toca el trigger append-only.

**Por qué**: el visor ordena por timestamp y filtra por acción/entidad; sin índices, el crecimiento de auditoría degrada la consulta (R-05). No se agrega ningún índice de privacidad porque la aceptación ya no forma parte del alcance.

### D12 — Bordes HTTP, códigos y esquemas estrictos

**Decisión**:

- `GET /usuarios?incluir_inactivos=false`, `POST /usuarios`, `GET/PATCH /usuarios/{id}`, `PUT /usuarios/{id}/roles`, `POST /usuarios/{id}/password`, `GET /roles`.
- `GET /auditoria?usuario_id&entidad&accion&desde&hasta&limite&offset`.
- `GET /privacidad`, `GET /privacidad/{version}`.
- Todos los cuerpos Pydantic v2 con `extra='forbid'`; los GET usan `reject_unexpected_query_except` con la lista exacta. 401 sin token, 403 por rol, 404 recurso inexistente, 409 conflicto de estado (último admin, email duplicado; el token inválido de otro turno se mantiene 410) y 422 validación.
- Las respuestas de usuario nunca incluyen `hash_password`; las de auditoría nunca incluyen payloads ni tokens.
- Nombres de acción estables para el visor: `usuario.crear`, `usuario.editar`, `usuario.password`, `usuario.roles`, `usuario.activar`, `usuario.desactivar`; la entidad de las mutaciones de acceso es `usuario` con el `entidad_id` del usuario afectado.

**Por qué**: sigue el patrón RORO/R-02 y los códigos ya usados en C-03..C-15, sin inventar una convención nueva.

### D13 — UI funcional, sin diseño visual

**Decisión**:

- `features/usuarios/api.ts` + `pages/UsuariosPage.tsx` (`/usuarios`): login reutilizado, tabla con estado/roles, formularios de alta/edición, selector de roles, botones activar/desactivar y cambio de contraseña. Los 403/409/422 se muestran con `describeFailure`.
- `features/auditoria/api.ts` + `pages/AuditoriaPage.tsx` (`/auditoria`): filtros, tabla, paginación, sin controles de escritura.
- `features/privacidad/api.ts` + `pages/PrivacidadPage.tsx` (`/privacidad`): texto versionado y enlace informativo desde `/reservar`. Sin checkbox, sin aceptación y sin cambio de contrato en la reserva.
- Rutas nuevas en `App.tsx`; sin `any`, sin lógica de negocio en el cliente (R-07).

**Por qué**: la demo necesita una superficie usable, pero el sistema visual es C-17. La UI no decide permisos ni valida reglas: solo presenta lo que la API devuelve.

### D14 — Estrategia de pruebas

- **Unitarias**: hash/versionado de la política, saneamiento de email, acciones de auditoría, parseo de fechas UTC-3 y lógica de paginación; shell del respaldo con `shellcheck`/revisión estática.
- **Integración con PostgreSQL real**: migración `0015` (solo índices del visor); CRUD de usuarios y roles; 403/401 por rol; email duplicado; contraseña; desactivación y token vigente; invariante del último admin secuencial y concurrente; auditoría por mutación y ausencia en rechazos; `GET /auditoria` filtros/paginación/orden; lectura no audita; `P0001` sigue vigente; reserva pública con el contrato de C-07 sin campos de privacidad; seed completo, idempotente, sin contraseña y en paralelo; exportación C-15 sigue incluyendo las filas de auditoría del paciente.
- **Compose/backup**: `docker compose config` valida servicios/perfiles; arranque real en el smoke; respaldo + verificación con passphrase correcta/incorrecta; ausencia de texto plano; `.gitignore`.
- **Frontend (Vitest)**: render de usuarios/auditoría/privacidad, 403/409 mostrados, enlace informativo a la política sin checkbox ni bloqueo, sin sumas ni validaciones locales.
- **Evidencia**: `docs/skills-mcp/evidencias/c-16/` con suite, smoke, migración, respaldo y matriz escenario→test; `openspec validate --strict`.

## Risks / Trade-offs

- **Sin aceptación registrada** → no hay prueba de que el paciente haya leído la política; es una decisión explícita del usuario. El consentimiento informado clínico de C-11 sigue cubriendo las prácticas invasivas. Si se exigiera aceptación, sería un change aparte con cambio de contrato de C-07.
- **Enlace informativo poco visible** → la política se publica y se enlaza desde `/reservar`, pero nada obliga a leerla; el runbook y la cátedra/asesoría deben evaluar si alcanza para RN-SE-04.
- **Lock global de acceso** → serializa las mutaciones de usuarios/roles; el volumen es bajo y el lock es por transacción, no por sesión. Si en el futuro hay muchas altas concurrentes, se puede migrar a un lock por fila más conteo.
- **Auditoría sin purga** → la tabla crece; el visor está acotado y indexado. Una purga/archivo queda para un change posterior.
- **CBC sin AEAD en el respaldo** → checksum + passphrase + artefactos fuera del repo; un change posterior puede migrar a `age`/GPG. No se promete resistencia a un atacante con acceso de escritura al backup.
- **Seed con fechas relativas** → la agenda demo no se refresca si ya hay turnos; se documenta resetear el volumen para una demo nueva.
- **Workers por defecto** → consumen recursos en cualquier `compose up`; son procesos pequeños y se reinician solos. El respaldo no arranca sin `--profile tools`.
- **Roles fijos** → no se puede crear un rol nuevo; es coherente con la matriz y se documenta como límite de v1.
- **Odontólogo sin visor de auditoría propia** → decisión conservadora; si el usuario la quiere, es un guard y un escenario adicional.
- **Texto legal** → la política es un texto base, no asesoramiento; la validación con la cátedra/asesor queda pendiente y documentada (P-11).

## Migration Plan

1. `alembic upgrade head` aplica `0015_admin_auditoria` (solo índices).
2. Agregar `SEED_DEMO_PASSWORD` y `BACKUP_PASSPHRASE` al `.env` real (nunca al repo); documentarlas en `.env.example` con placeholders.
3. Reconstruir API/workers y levantar `docker compose up -d --build`; correr migraciones y `python -m app.seed`.
4. Verificar login de los cinco roles, CRUD de usuarios, visor de auditoría, reserva pública sin campos de privacidad y respaldo/verificación.
5. Rollback de esquema: `alembic downgrade 0014_reportes` elimina los índices del visor; no hay datos que reconstruir. Rollback funcional: revertir solo el seed y las pantallas nuevas; la reserva pública conserva su contrato original.
6. Cierre: suite + smoke + evidencia, `openspec validate --strict`, archivar y marcar `[x]` en `CHANGES.md` cuando el usuario lo indique (decisión 2026-11-03: sin gate manual por change).

## Open Questions

- **Texto legal definitivo**: la política v1 es un borrador técnico; la cátedra/asesor puede pedir cambios de redacción. Cambiar el texto exige una versión nueva (`v2-...`) y no altera el código del visor ni del respaldo.
- **Purga/archivo de auditoría y respaldos**: no se implementa en C-16. Si la tabla crece en producción, un change posterior puede archivar por rango sin romper el visor.
- **Restauración automatizada**: el runbook verifica el dump; restaurar en una base limpia queda como procedimiento manual documentado, no como comando del change.
- **Aceptación de privacidad**: C-16 publica la política y la enlaza, pero no la exige. Si más adelante se quisiera registrar aceptación, será un change propio con cambio de contrato de C-07, almacenamiento y análisis legal.
- **Hospedaje final (P-05)**: sigue abierto; C-16 entrega el default local y no implementa la variante nube gratuita.
