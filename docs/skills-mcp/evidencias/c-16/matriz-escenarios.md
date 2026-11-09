# Matriz escenario → verificación — C-16

Cada escenario de las siete specs del change queda trazado a un test o comando
reproducible y a un borde observable (HTTP, DB, UI o artefacto).

## Claves de tests

| Clave | Archivo |
|---|---|
| `TA` | `backend/tests/integration/test_usuarios_api.py` |
| `TR` | `backend/tests/integration/test_roles_api.py` |
| `TUA` | `backend/tests/integration/test_ultimo_admin.py` |
| `TAU` | `backend/tests/integration/test_usuarios_auditoria.py` |
| `AA` | `backend/tests/integration/test_auditoria_api.py` |
| `AR` | `backend/tests/integration/test_auditoria_rbac.py` |
| `TC` | `backend/tests/integration/test_reserva_contrato.py` |
| `TAL` | `backend/tests/integration/test_reserva_alcance.py` |
| `PD` | `backend/tests/unit/test_privacidad_dominio.py` |
| `PA` | `backend/tests/integration/test_privacidad_api.py` |
| `SD` | `backend/tests/integration/test_seed_demo.py` |
| `CC` | `backend/tests/test_compose_config.py` |
| `UU` | `frontend/src/pages/UsuariosPage.test.tsx` |
| `AU` | `frontend/src/pages/AuditoriaPage.test.tsx` |
| `PP` | `frontend/src/pages/PrivacidadPage.test.tsx` |
| `RP` | `frontend/src/pages/ReservaPage.test.tsx` |

Evidencia del smoke y operaciones: `docs/skills-mcp/evidencias/c-16/` (`smoke-*.txt`,
`compose-stack.txt`, `migracion-ciclo*.txt`, `secret-scan.txt`, `suite/**`, `frontend/**`).

## 1. `admin/gestion-acceso`

| Escenario | Verificación | Borde observable |
|---|---|---|
| Alta de usuario con roles | `TA::test_alta_201_email_normalizado_sin_hash` | 201; email normalizado; roles; sin `hash_password`; login 200 |
| Email duplicado | `TA::test_email_duplicado_409_sin_modificar` | 409 en alta y PATCH; filas sin cambios |
| Datos inválidos o rol inexistente | `TA::test_datos_invalidos_422_sin_crear` | 422; conteo de usuarios estable |
| Edición parcial y usuario inexistente | `TA::test_detalle_y_edicion_parcial`, `TA::test_usuario_inexistente_404` | 200 conserva campos; 404 |
| Listado con cuentas inactivas | `TA::test_listado_activos_e_inactivos_sin_hashes` | default sin inactiva; `incluir_inactivos=true` la muestra |
| Acceso denegado por rol o sin token | `TA::test_gestion_solo_administrador_403`, `TA::test_sin_token_401`, `TA::test_me_conserva_prioridad...` | 403/401; `/usuarios/me` 200 |
| Cambio de contraseña exitoso | `TA::test_cambio_de_password_sin_hash` | 200; vieja 401; nueva 200 |
| Contraseña inválida o inexistente | `TA::test_cambio_de_password_sin_hash`, `TA::test_usuario_inexistente_404` | 422/404 |
| El hash no se filtra | `TA::test_alta...`, `TA::test_listado...`, `TA::test_cambio...` | texto sin `hash_password` ni contraseña |
| Asignación y reemplazo de roles | `TR::test_put_reemplaza_el_conjunto` | 200; solo los roles del último PUT |
| Rol desconocido o lista vacía | `TR::test_roles_invalidos_422_conservan_los_anteriores` | 422; roles previos intactos |
| Roles repetidos en la misma petición | `TR::test_duplicados_son_idempotentes` | 200; un vínculo por rol |
| El catálogo no se puede modificar | `TR::test_roles_no_se_pueden_modificar_405` | 405; 5 roles intactos |
| Catálogo restringido al administrador | `TR::test_get_roles_devuelve_los_cinco_solo_al_admin`, `TR::test_put_roles_permisos_y_404` | 403; sin catálogo |
| Desactivación y reactivación | `TA::test_desactivacion_y_reactivacion_invalida_el_token` | 200; login 401 → 200 |
| Token vigente de una cuenta desactivada | mismo test | `/usuarios/me` 401 con el token previo |
| Auto-desactivación | `TUA::test_auto_desactivacion_es_409_aun_con_otro_admin` | 409; cuenta activa |
| Usuario inexistente y sin borrado físico | `TA::test_usuario_inexistente_404`, `TA::test_sin_borrado_fisico_delete_405` | 404/405; fila sigue |
| Quitar el rol al último administrador | `TUA::test_quitar_el_rol_al_ultimo_admin_409` | 409; rol `administrador` intacto |
| Desactivar al último administrador | `TUA::test_desactivar_al_ultimo_admin_409` | 409; cuenta activa |
| Operación permitida con otro administrador | `TUA::test_con_dos_admins_se_puede_desactivar_uno` | 200; queda 1 admin |
| Auto-remoción con otro administrador | `TUA::test_auto_remocion_con_otro_admin_200_y_pierde_acceso` | 200; siguiente request 403 |
| Auto-remoción del último administrador | `TUA::test_auto_remocion_como_ultimo_admin_409` | 409; roles intactos |
| Dos desactivaciones concurrentes | `TUA::test_desactivaciones_concurrentes_una_gana_y_otra_409` | exactamente 200/409; queda 1 admin |
| Fila de auditoría por cambio aceptado | `TAU::test_una_fila_por_mutacion_aceptada` | 6 acciones, actor/IP/dispositivo/entidad |
| Operación rechazada no deja auditoría | `TAU::test_rechazos_y_validaciones_no_dejan_filas` | conteo igual |
| Sin cambios efectivos | `TAU::test_sin_cambios_no_agrega_fila` | 200 sin fila |
| La auditoría no guarda secretos | `TAU::test_la_auditoria_no_guarda_password_ni_hash` | sin password/hash; sin columnas |
| Recorrido de administración | `UU` (lista/alta/roles) | tabla con estado/roles; alta desde pantalla |
| Error de la API visible | `UU` (409 último admin) | alerta verbatim; fila no cambia |
| Sin sesión o rol insuficiente | `UU` (login/403) | login sin sesión; 403 sin acciones |

## 2. `admin/auditoria`

| Escenario | Verificación | Borde observable |
|---|---|---|
| Lectura paginada del historial | `AA::test_paginacion_de_120_filas` | 20 filas, `total=120`, `limite=50`, `offset=100` |
| Intento de escritura sobre auditoría | `AA::test_metodos_de_escritura_405` | 405; conteo intacto |
| Tabla vacía y auditoría de la lectura | `AA::test_tabla_vacia`, `AA::test_lectura_no_agrega_filas` | 200/[]/0; conteo igual |
| Usuario dado de baja sigue trazado | `AA::test_usuario_dado_de_baja_sigue_trazado` | `usuario_id` + email histórico |
| Filtros combinados | `AA::test_filtros_combinados_y_total_antes_de_paginar` | 3 filas, `total=3` |
| Límite, offset y total | `AA::test_paginacion_de_120_filas` | 20 filas de 120; total antes de paginar |
| Parámetros inválidos | `AA::test_parametros_invalidos_422` | 422 en los 7 casos |
| Bordes inclusivos y orden estable | `AA::test_bordes_de_fecha_inclusivos`, `AA::test_listado_orden_estable_y_campos` | 00:00 y 23:59:59.999999 incluidos; id DESC |
| Administrador y auditor leen | `AR::test_admin_y_auditor_leen_y_el_resto_no` | 200 e historial idéntico |
| Roles sin acceso | mismo test | 403 para tres roles |
| Auditor no escribe | `AR::test_auditor_no_escribe_en_ningun_dominio` | 403 en 6 mutaciones; dominio/auditoría iguales |
| Petición sin token | `AR::test_admin_y_auditor_leen_y_el_resto_no` | 401 |
| Recorrido del visor | `AU` (tabla + filtros + paginación) | tabla, filtros y offset 0→100→0 |
| Error de permisos visible | `AU` (403 odontólogo) | alerta 403; sin filtros ni tabla |
| Sin sesión | `AU` (login) | pide login; no consulta `/auditoria` |

## 3. `privacy/privacidad-respaldo`

| Escenario | Verificación | Borde observable |
|---|---|---|
| Consulta de la política vigente | `PA::test_politica_vigente_sin_token`; smoke `/privacidad` | 200, versión, texto, hash, `alcance_legal_validado=false` |
| Versión desconocida | `PA::test_version_desconocida_404_sin_filtrar_texto`, `PD::test_version_desconocida_no_existe` | 404; no filtra el texto vigente |
| Hash estable e inmutabilidad | `PD::test_hash_sha256_estable...`, `PD::test_politica_es_inmutable...` | SHA-256 del texto; misma versión inmutable |
| Sin autenticación y sin datos personales | `PA::test_politica_vigente_sin_token`; smoke | sin Bearer; sin tokens/datos |
| Respaldo y verificación | `smoke-backup.txt`; `docs/demo.md` §7 | `.dump.enc` + `.sha256`; `pg_restore --list` OK |
| Passphrase ausente | `backup-sin-passphrase.txt` | exit 1 nombrando `BACKUP_PASSPHRASE`; sin archivo nuevo |
| Passphrase incorrecta | `smoke-backup.txt` (`verify_wrong_pass_exit=1`) | falla sin imprimir contenido |
| Archivo adulterado | `smoke-backup.txt` (`verify_altered_exit=1`) | checksum falla antes de descifrar |
| El cifrado no filtra texto plano | `smoke-backup.txt` (`plain_create_table=False`, `plain_ana_demo=False`) | binario cifrado sin texto claro |
| La política no promete cumplimiento | `PD::test_texto_no_afirma_cumplimiento_normativo`; `docs/demo.md` §11 | sin afirmaciones; pide asesoramiento humano |
| El procedimiento de respaldo queda documentado | `docs/demo.md` §7 (revisión) | variable, comando, ubicación y verificación |
| Sin secretos en la documentación | `secret-scan.txt` | 0 coincidencias; `.env`/`backups/` ignorados |
| Lectura de la política | `PP` (versión/fecha/texto/hash/enlace) | texto y hash visibles; enlace a `/reservar` |
| Enlace informativo desde la reserva | `RP` (enlace, sin checkbox) | `<a href="/privacidad">`; 0 checkboxes |
| La privacidad no bloquea la reserva | `TC::test_reserva_valida_sin_campos_de_privacidad_es_201`, `RP` | 201 sin campos de privacidad |
| Error de la API | `PP` (404) | alerta 404 verbatim; sin texto inventado |

## 4. `agenda/reserva-publica`

| Escenario | Verificación | Borde observable |
|---|---|---|
| El enlace muestra solo su turno | `TAL::test_cada_token_muestra_solo_su_turno_sin_pii` | 200; claves exactas; sin PII |
| Token de otro turno | `TAL::test_token_a_no_lee_ni_modifica_el_turno_b` | query extra 422; B intacto y 200 con su token |
| Sin listado público de turnos | `TAL::test_no_existe_listado_publico_de_turnos` | 405/404; catálogo sin turnos |
| Dos turnos del mismo paciente | `TAL::test_cada_token_muestra_solo_su_turno_sin_pii` | cada token devuelve solo su `turno_id` |
| Token usado, vencido o de otro propósito | `TAL::test_token_usado_vencido_o_de_otro_proposito_410` | 410 en los cuatro casos |

## 5. `security/core-models` (seed)

| Escenario | Verificación | Borde observable |
|---|---|---|
| Primera ejecución del seed | `SD::test_primera_corrida_conteos_exactos` | 5 roles, 5 usuarios, 1 profesional, 2 sillones, 3 turnos, etc. |
| Cada rol demo puede iniciar sesión | `SD::test_login_de_los_cinco_roles` | 5 logins 200 con su rol |
| Seed sin contraseña configurada | `SD::test_sin_password_admin_aborta_sin_escribir`, `SD::test_cli_nombra_la_variable_faltante` | error nombra la variable; 0 filas |
| Seed sin contraseña del elenco | `SD::test_sin_password_demo_aborta_sin_escribir`, `SD::test_cli...` | error nombra `SEED_DEMO_PASSWORD`; 0 filas |
| Segunda ejecución no duplica | `SD::test_segunda_corrida_es_identica` | conteos idénticos |
| Reejecución con otra contraseña | `SD::test_otra_password_no_reescribe_credenciales` | hashes idénticos |
| Dos seeds simultáneos no fallan | `SD::test_dos_seeds_concurrentes_no_fallan` | sin 23505; conteos exactos |
| Base parcialmente sembrada | `SD::test_base_parcial_se_completa_sin_duplicar` | completa faltantes; respeta existentes |
| Datos ficticios, sin PII real | `SD::test_datos_ficticios_sin_pii_real` | dominios `.test`, apellidos Demo, teléfonos ficticios |

## 6. `platform/compose-stack`

| Escenario | Verificación | Borde observable |
|---|---|---|
| Compose levanta verde | `CC::test_ocho_servicios_por_defecto`, `compose-stack.txt` | 8 servicios; `ps` healthy/running |
| Orden de arranque con gates | `CC::test_workers_por_defecto_con_reinicio_y_gates` | `depends_on` db/redis `service_healthy` |
| Perfil de herramientas separado | `CC::test_backup_solo_bajo_el_perfil_tools` | backup ausente sin `--profile tools` |
| Reinicio de workers | `CC::test_workers_por_defecto_con_reinicio_y_gates`; logs del smoke | `restart: unless-stopped`; workers se recuperan tras migrar |
| Persistencia nombrada | `CC::test_healthchecks_y_volumenes` | `pgdata` y `redisdata` |

## 7. `platform/demo-deploy`

| Escenario | Verificación | Borde observable |
|---|---|---|
| Arranque por defecto con todos los servicios | `CC::test_ocho_servicios_por_defecto`; `compose-stack.txt` | 8 servicios running/healthy |
| Gates de arranque | `CC::test_workers_por_defecto_con_reinicio_y_gates` | dependencias healthy |
| Perfil de herramientas no arranca por defecto | `CC::test_backup_solo_bajo_el_perfil_tools` | backup solo con `tools` |
| Reinicio de un worker caído | `CC::test_workers...`; logs y `ps` del smoke | workers vuelven a `running` |
| Webhook entrante por túnel | `test_comunicaciones.py`, `test_webhook_mp.py`; `docs/demo.md` §6 | 200 y efecto único; firma |
| Firma inválida por túnel | `test_comunicaciones.py`, `test_webhook_mp.py` | 401 sin cambios |
| Túnel caído | `docs/demo.md` §6; smoke local sin túnel | demo local sigue funcionando |
| Inventario de variables | `.env.example`; `CC::test_sin_latest_ni_secretos_literales` | todas documentadas, solo placeholders |
| Secreto obligatorio faltante | `SD::test_sin_password_admin...`, `SD::test_cli...`, `backup-sin-passphrase.txt` | error nombra la variable; sin escritura |
| Sin secretos en el control de versiones | `secret-scan.txt`; `git check-ignore` | 0 coincidencias; `.env` y `backups/` ignorados |
| Recorrido completo en verde | `smoke-http.txt`, `smoke-workers-export.txt`, `smoke-backup.txt` | health/ready, 5 logins, reserva 201, gestión sin PII, auditoría, export lista, backup OK |
| Fallo representativo de negocio | `test_exportaciones_rbac.py` (403), `test_turnos.py` (409 solape) | 403/409 sin continuar el flujo |
| Reejecución del seed y reinicio del stack | `seed-reejecucion.txt`; `compose-stack.txt` | conteos iguales; volúmenes conservados |
| Evidencia del cierre | carpeta `docs/skills-mcp/evidencias/c-16/` | tests, smoke, migración, respaldo y validación |
