# Tasks

> Convención: cada grupo empieza en rojo (test que falla) y cierra en verde. Los tests de integración usan PostgreSQL real vía `TEST_DATABASE_URL`; los unitarios no tocan red ni base.
> Decisiones: `design.md` D1–D14. Escenarios: `specs/admin/gestion-acceso`, `specs/admin/auditoria`, `specs/privacy/privacidad-respaldo`, `specs/platform/demo-deploy`, `specs/agenda/reserva-publica`, `specs/security/core-models` y `specs/platform/compose-stack`.
> La privacidad se publica y se enlaza desde `/reservar`, pero no cambia el contrato de `POST /reservar/{slug}/turnos` ni exige aceptación.

## 1. Migración `0015_admin_auditoria`

- [x] 1.1 Escribir en rojo `backend/tests/integration/test_admin_migracion.py`: espera el head `0015_admin_auditoria` y los índices `ix_registro_auditoria_timestamp`, `ix_registro_auditoria_accion_timestamp` e `ix_registro_auditoria_entidad_timestamp`; confirmar que falla antes de crear la migración. **Verifica:** `pytest backend/tests/integration/test_admin_migracion.py -q` en rojo.
- [x] 1.2 Crear `backend/alembic/versions/0015_admin_auditoria.py` (`down_revision='0014_reportes'`) solo con los tres índices y sin tablas nuevas; verificar `alembic upgrade head` → `downgrade 0014_reportes` → `upgrade head` sin errores y con el esquema idéntico. **Verifica:** ciclo de migración y test 1.1 en verde.
- [x] 1.3 Verificar por SQL directo en el mismo test que la auditoría sigue rechazando `UPDATE`/`DELETE` con `P0001` y `TRUNCATE`, sin agregar índices ni filas de aceptación de privacidad. **Verifica:** los asserts de SQLSTATE pasan y no existe ningún índice de aceptación de privacidad.

## 2. Dominio y repositorios de acceso

- [x] 2.1 Escribir en rojo `backend/tests/unit/test_acceso_dominio.py`: normalización de email, catálogo de cinco roles, nombres de acción de auditoría, validación de lista de roles (vacía/duplicada/desconocida) y cálculo de paginación del visor. **Verifica:** el test unitario falla antes de implementar.
- [x] 2.2 Implementar los helpers puros en `backend/app/domain/acceso.py` (o módulo vecino) y verificar el test 2.1 sin base ni red. **Verifica:** `pytest backend/tests/unit/test_acceso_dominio.py -q` en verde.
- [x] 2.3 Escribir en rojo `backend/tests/integration/test_acceso_repos.py`: `list_all` con inactivos, reemplazo atómico de roles, conteo de administradores activos y consulta de auditoría con filtros/orden/total. **Verifica:** el test falla antes de tocar repositorios.
- [x] 2.4 Implementar en `backend/app/infrastructure/repositories.py` los métodos de usuario/rol y el listado filtrado de auditoría; exponerlos en `UnitOfWork`; verificar el test 2.3. **Verifica:** repositorios en verde y `EXPLAIN` manual del listado usa un índice de 0015.

## 3. API de gestión de acceso

- [x] 3.1 Escribir en rojo `backend/tests/integration/test_usuarios_api.py`: alta 201 sin hash, listado con activos/inactivos, detalle, `PATCH` parcial, email duplicado 409, rol/contraseña/email inválidos 422, inexistente 404, roles sin permiso 403 y sin token 401. **Verifica:** el archivo falla antes del router.
- [x] 3.2 Implementar `backend/app/schemas/usuarios.py` y `backend/app/api/usuarios.py` (alta, listado, detalle, edición y contraseña) con `extra='forbid'`; mover el listado `GET /usuarios` desde `auth.py` al nuevo router, dejando `login` y `me` en auth, y registrar el router después de `auth.router` para que `/usuarios/me` y `/usuarios/login` conserven prioridad sobre `/{id}`; verificar todos los escenarios de `admin/gestion-acceso` §Alta y §Contraseña. **Verifica:** test 3.1 en verde, `/usuarios/me` sigue en 200 y respuestas sin `hash_password`.
- [x] 3.3 Escribir en rojo `backend/tests/integration/test_roles_api.py`: `GET /roles` con los cinco nombres solo para admin (403 para los otros roles), `PUT /usuarios/{id}/roles` reemplaza, duplicados idempotentes, rol desconocido/lista vacía 422 y `POST/PATCH/DELETE /roles` 405. **Verifica:** el test falla antes del endpoint.
- [x] 3.4 Implementar `GET /roles` y `PUT /usuarios/{id}/roles` con reemplazo transaccional; verificar el escenario “catálogo fijo” completo. **Verifica:** test 3.3 en verde.
- [x] 3.5 Escribir en rojo `backend/tests/integration/test_ultimo_admin.py`: quitar el rol al último admin 409, desactivarlo 409, con dos admins 200, auto-desactivación 409, auto-remoción del rol con otro admin 200 / como último 409, y dos desactivaciones concurrentes con `asyncio.gather` → exactamente un 200 y un 409, dejando un admin activo. **Verifica:** el test falla antes del lock/invariante.
- [x] 3.6 Implementar `pg_advisory_xact_lock` y el conteo de administradores activos en la transacción de mutación; verificar todos los escenarios de §Invariante y el rollback íntegro. **Verifica:** test 3.5 en verde, incluida la carrera.
- [x] 3.7 Escribir en rojo `backend/tests/integration/test_usuarios_auditoria.py`: una fila por alta/edición/roles/contraseña/desactivación, ninguna por 409 o no-op, columnas usuario/entidad/IP/dispositivo y ausencia de contraseñas/hashes. **Verifica:** el test falla antes de instrumentar.
- [x] 3.8 Instrumentar `infrastructure/audit.registrar` en cada mutación aceptada y verificar el test 3.7; comprobar que la auditoría sigue append-only. **Verifica:** escenarios de §Auditoría de las mutaciones en verde.

## 4. UI funcional de usuarios

- [x] 4.1 Escribir en rojo `frontend/src/features/usuarios/api.test.ts` y `frontend/src/pages/UsuariosPage.test.tsx`: listado con estado/roles, alta, asignación de roles, activación/desactivación, 403 y 409 mostrados verbatim, sin validaciones locales. **Verifica:** `npm run test -- --run` falla antes de la página.
- [x] 4.2 Implementar `features/usuarios/api.ts`, `pages/UsuariosPage.tsx` y la ruta `/usuarios` en `App.tsx`, reutilizando login y `describeFailure`; verificar `npm run test`, `npm run typecheck` y `npm run build`. **Verifica:** escenarios de `admin/gestion-acceso` §UI en verde y sin `any`.

## 5. API de auditoría

- [x] 5.1 Escribir en rojo `backend/tests/integration/test_auditoria_api.py`: orden `timestamp DESC, id DESC`, filtros combinados, `total` antes de paginar, `limite/offset`, bordes inclusivos, tabla vacía, usuario con baja lógica, 422 por límite/offset/rango/filtro no declarado y 405 en métodos de escritura. **Verifica:** el test falla antes del router.
- [x] 5.2 Implementar `app/schemas/auditoria.py` y `app/api/auditoria.py` con `reject_unexpected_query_except`; verificar todos los escenarios de `admin/auditoria` §Consulta y §Filtros. **Verifica:** test 5.1 en verde.
- [x] 5.3 Escribir en rojo `backend/tests/integration/test_auditoria_rbac.py`: admin/auditor 200; odontólogo/recepción/asistente 403; sin token 401; auditor 403 en mutaciones de usuarios, roles, turnos, historia, caja y exportaciones; lectura no agrega filas. **Verifica:** el test falla antes de los guards.
- [x] 5.4 Aplicar los guards y verificar el escenario §Acceso a la auditoría por rol; comparar el conteo de auditoría antes/después de una lectura. **Verifica:** test 5.3 en verde.

## 6. UI funcional de auditoría

- [x] 6.1 Escribir en rojo `frontend/src/features/auditoria/api.test.ts` y `frontend/src/pages/AuditoriaPage.test.tsx`: filtros por usuario/entidad/acción/fecha, tabla paginada, 403 visible, sin controles de escritura y sin consulta sin sesión. **Verifica:** `npm run test -- --run` falla antes de la página.
- [x] 6.2 Implementar `features/auditoria/api.ts`, `pages/AuditoriaPage.tsx` y la ruta `/auditoria`; verificar `npm run test`, `npm run typecheck` y `npm run build`. **Verifica:** escenarios de `admin/auditoria` §UI en verde.

## 7. Privacidad publicada y alcance del enlace

- [x] 7.1 Escribir en rojo `backend/tests/unit/test_privacidad_dominio.py`: versión vigente, texto canónico, hash SHA-256 estable, versión desconocida y ausencia de claims de cumplimiento. **Verifica:** el test unitario falla antes del módulo.
- [x] 7.2 Implementar `backend/app/domain/privacidad.py` y `backend/app/api/privacidad.py` (`GET /privacidad` y `GET /privacidad/{version}`), registrar el router y verificar el test 7.1 más los escenarios de §Política pública. **Verifica:** endpoints 200/404 sin autenticación y con el hash correcto.
- [x] 7.3 Escribir `backend/tests/integration/test_reserva_contrato.py` como test de regresión: una reserva válida con el body de C-07, sin campos de privacidad, responde 201; no se agregan `acepta_privacidad`/`politica_version`; un campo extra sigue dando 422; no se crea ninguna fila `privacidad.aceptada`. **Verifica:** el test queda en verde y falla si alguien reintroduce el requisito de aceptación.
- [x] 7.4 Escribir en rojo `backend/tests/integration/test_reserva_alcance.py`: token A solo su turno, token B no lee A, sin listado público, dos turnos del mismo paciente aislados, token usado/vencido 410 y respuesta sin nombre/DNI/teléfono/email. **Verifica:** el test falla si aparece cualquier dato personal o cruce.
- [x] 7.5 Ajustar `GestionTurnoResponse` y las rutas públicas para el mínimo privilegio de §Alcance del enlace; verificar el test 7.4 y los escenarios de `agenda/reserva-publica`. **Verifica:** aislamiento A/B en verde.

## 8. UI de privacidad y enlace informativo

- [x] 8.1 Escribir en rojo `frontend/src/features/privacidad/api.test.ts`, `frontend/src/pages/PrivacidadPage.test.tsx` y el caso de `ReservaPage.test.tsx`: texto versionado, enlace visible a `/privacidad` desde `/reservar`, ausencia de checkbox/bloqueo, 404 y errores mostrados verbatim. **Verifica:** `npm run test -- --run` falla antes de la UI.
- [x] 8.2 Implementar `features/privacidad/api.ts`, `pages/PrivacidadPage.tsx`, la ruta `/privacidad` y el enlace informativo en `ReservaPage`; verificar `npm run test`, `npm run typecheck` y `npm run build`. **Verifica:** escenarios de `privacy/privacidad-respaldo` §Página pública en verde y reserva sin checkbox.

## 9. Seed demo completo

- [x] 9.1 Escribir en rojo `backend/tests/integration/test_seed_demo.py`: primera corrida con conteos exactos (5 roles, 1 consultorio, 5 usuarios, 1 profesional, 2 sillones, prestaciones, 1 OS, 3 pacientes, 3 turnos sin solape), login de los cinco roles, falta de `SEED_ADMIN_PASSWORD`/`SEED_DEMO_PASSWORD` sin registros, segunda corrida idéntica, contraseñas distintas sin reescritura, dos seeds concurrentes sin `23505`, base parcial completada y datos ficticios. **Verifica:** el test falla antes de ampliar el seed.
- [x] 9.2 Ampliar `backend/app/seed.py` con advisory lock, upserts por clave natural y turnos de la próxima jornada hábil; actualizar la firma de `run_seed` y los tests de C-02; verificar los escenarios de `security/core-models` §Seed. **Verifica:** test 9.1 y `backend/tests/integration/test_seed.py` en verde.
- [x] 9.3 Documentar `SEED_DEMO_PASSWORD` y las credenciales demo como placeholders en `backend/.env.example` y `docs/demo.md`; verificar que ningún valor real quede en el repo. **Verifica:** búsqueda de secretos sin coincidencias y seed reproducible con el `.env.example`.

## 10. Compose, workers y respaldo cifrado

- [x] 10.1 Escribir en rojo `backend/tests/test_compose_config.py` (o verificación shell equivalente): servicios `api`, `frontend`, `db`, `redis`, `worker-recordatorios`, `worker-whatsapp`, `worker-arca`, `worker-reportes`; `backup` solo en `tools`; sin `:latest`; sin secretos literales. **Verifica:** `docker compose config --services` y el test fallan antes de editar Compose.
- [x] 10.2 Agregar `worker-arca` y `worker-reportes`, quitar el perfil `workers` de los cuatro, agregar `restart: unless-stopped` y el servicio `backup` bajo `profiles: ["tools"]`; verificar `docker compose config`. **Verifica:** test 10.1 en verde y `docker compose up -d --build` con los ocho servicios running/healthy.
- [x] 10.3 Crear `ops/backup/Dockerfile` (base `postgres:16-alpine` pineada + `openssl`) y `ops/backup/backup.sh` con modos `backup`/`verify`; verificar sintaxis shell y build de la imagen. **Verifica:** `docker compose --profile tools build backup` sin errores.
- [x] 10.4 Ejecutar respaldo y verificación sobre la base demo: archivo `.dump.enc` + `.sha256`, `pg_restore --list` correcto, passphrase incorrecta y byte alterado fallan, y el cifrado no contiene `CREATE TABLE` ni “Ana Demo”. **Verifica:** escenarios de `privacy/privacidad-respaldo` §Respaldo cifrado.
- [x] 10.5 Agregar `backups/` a `.gitignore`, `BACKUP_PASSPHRASE` a `.env.example` y el procedimiento a `docs/demo.md`; verificar que la passphrase real no está en el repo ni en la imagen. **Verifica:** búsqueda de secretos y revisión de la imagen.
- [x] 10.6 Escribir `docs/demo.md` con el runbook completo: requisitos, `.env`, túnel cloudflared/ngrok, `APP_BASE_URL`, webhooks MP/WhatsApp, migraciones, seed, recorrido de los ocho servicios, respaldo/verificación y definición de “flujo demo verde”; actualizar el quickstart/estado de `README.md`; verificar que cada comando documentado existe y que el túnel no filtra secretos. **Verifica:** revisión del runbook y ejecución de los comandos de configuración.

## 11. Integración final, smoke y evidencia

- [x] 11.1 Escribir `docs/skills-mcp/evidencias/c-16/matriz-escenarios.md` con cada escenario de las siete specs, su test/comando y el borde observable; confirmar que no queda ninguno sin cobertura. **Verifica:** matriz completa y revisión de huecos.
- [x] 11.2 Correr la suite backend completa (`pytest backend/tests -q`), `npm run test`, `npm run typecheck` y `npm run build` en `frontend/`; corregir regresiones de C-01..C-15, en especial los tests de reserva pública y seed, y confirmar que la reserva sigue sin exigir campos de privacidad. **Verifica:** suites en verde y sin fallos preexistentes atribuibles a C-16.
- [x] 11.3 Ejecutar el ciclo de migración sobre base descartable (`upgrade head` → `downgrade 0014_reportes` → `upgrade head`), levantar `docker compose up -d --build`, correr migraciones + seed y ejecutar el smoke completo de punta a punta —reserva pública sin aceptación de privacidad incluida— más el respaldo/verificación. **Verifica:** flujo demo verde y evidencia guardada.
- [x] 11.4 Guardar en `docs/skills-mcp/evidencias/c-16/` las salidas de tests, migración, `docker compose config`, smoke y respaldo; agregar el bloque C-16 con resumen no técnico a `docs/validacion-manual-pendiente.md`; ejecutar `openspec validate c-16-admin-roles-auditoria-deploy --strict`. **Verifica:** validación sin warnings y evidencia completa.

## Workflow follow-up

- Archivar el change cuando la suite, el smoke, el respaldo y la evidencia estén en verde, según la decisión del usuario del 2026-11-03 (sin gate de aprobación manual por change). La aceptación funcional final se hace sobre la página completa.
- Marcar `[x]` en `CHANGES.md` §C-16 y registrar la migración `0015_admin_auditoria`.
- Commit y push del cierre con conventional-commits y sin co-autoría IA, solo cuando el usuario lo pida (R-13).












