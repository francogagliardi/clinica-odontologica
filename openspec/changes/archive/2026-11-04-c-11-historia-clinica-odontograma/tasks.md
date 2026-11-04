# Tasks

## 1. Dominio clínico puro (TDD)

- [x] 1.1 Escribir `backend/tests/unit/test_clinica_domain.py` con casos FDI válidos (`11`, `18`, `48`, `51`, `55`, `85`) e inválidos (`19`, `20`, `29`, `49`, `56`, `86`, `99`, `0`, `9`), caras y estados válidos/inválidos y CIE-10 (`K02.1` ok; `caries`, `k021` inválidos); verificar que falla en rojo porque `app/domain/clinica.py` no existe
- [x] 1.2 Implementar en `app/domain/clinica.py` las constantes y funciones `pieza_fdi_valida`, `cara_valida`, `estado_valido` y `cie10_valido`; verificar `pytest backend/tests/unit/test_clinica_domain.py -q` en verde
- [x] 1.3 Agregar tests rojos de saneo de nombre (`..\..\etc\passwd` → `passwd`), límite de 5 MB, allow-list de MIME y detección de firma JPEG/PNG/WebP/PDF vs. contenido que no coincide
- [x] 1.4 Implementar `sanear_nombre`, `mime_permitido` y `firma_coincide_con_mime`; verificar los tests de 1.3 en verde
- [x] 1.5 Agregar tests rojos del catálogo de consentimientos (`v1-2026-11` existe, `v0` no) y del hash determinista (`texto_hash` de 64 hex; `firma_ref` con prefijo `sha256:`), incluyendo que dos llamadas con los mismos datos producen el mismo digest
- [x] 1.6 Implementar `app/domain/consentimientos.py` con el catálogo y `calcular_hashes`; verificar los tests de 1.5 en verde

## 2. Modelos y migración `0010_historia_clinica`

- [x] 2.1 Escribir `backend/tests/unit/test_models_metadata.py` (ampliación) que exija las tablas `historias_clinicas`, `evoluciones`, `odontogramas`, `hallazgos_dentales`, `adjuntos` y `consentimientos`, sus FKs y los nombres de constraints; verificar rojo
- [x] 2.2 Crear `app/models/clinica.py` con los seis modelos, CHECKs e índices descritos en design D3 y exportarlos en `app/models/__init__.py`; verificar los tests de metadata en verde
- [x] 2.3 Escribir `backend/tests/integration/test_migration.py` (ampliación) para exigir head `0010_historia_clinica` y la existencia de tablas, índices únicos parciales, CHECKs y triggers; verificar rojo
- [x] 2.4 Escribir a mano `backend/alembic/versions/0010_historia_clinica.py` con `down_revision = "0009_lista_espera"`, tablas, índices y CHECKs; verificar `alembic upgrade head` y que el test de 2.3 avanza hasta los triggers faltantes
- [x] 2.5 Agregar tests de integración rojos de base: `UPDATE`/`DELETE` sobre `evoluciones` firmadas, `odontogramas`, `hallazgos_dentales` y `consentimientos` deben fallar con SQLSTATE `P0001`; un `INSERT` de pieza `19` o de versión duplicada debe fallar con `23505`/`23514`
- [x] 2.6 Implementar las funciones y triggers `P0001` de evolución, odontograma, hallazgo y consentimiento en la migración; verificar los tests de 2.5 y 2.3 en verde y que `alembic downgrade 0009_lista_espera` deja la base sin las seis tablas

## 3. Repositorios, UnitOfWork y autorización

- [x] 3.1 Escribir tests de integración rojos de repositorios: unicidad de historia activa por paciente, rectificatoria única activa, cálculo de la próxima versión del odontograma y listado de consentimientos/adjuntos por historia
- [x] 3.2 Implementar `HistoriaClinicaRepository`, `EvolucionRepository`, `OdontogramaRepository`, `AdjuntoRepository` y `ConsentimientoRepository` en `app/infrastructure/repositories.py` y registrarlos en `app/infrastructure/uow.py`; verificar los tests de 3.1 en verde
- [x] 3.3 Escribir tests rojos de `paciente_propio` y `paciente_en_sala`: propio con turno `reservado/confirmado/en_sala/atendido`, ajeno con otro profesional, y `cancelado/ausente` sin acceso; en sala solo con `en_sala`
- [x] 3.4 Implementar los helpers de autorización en `app/application/clinica.py` (consultan `Turno`/`Profesional`) y mover `client_ip`/`dispositivo` a `app/api/deps.py` reutilizándolos desde `auth.py`; verificar 3.3 y `pytest backend/tests/integration/test_auth_login.py -q` en verde

## 4. Historia clínica

- [x] 4.1 Escribir tests de integración rojos de `POST /historia-clinica`, `GET /historia-clinica/{id}` y `GET /pacientes/{paciente_id}/historia-clinica`: 201, 409 duplicada, 404 paciente baja/inexistente, 404 sin historia y 404 de otro consultorio
- [x] 4.2 Implementar `app/schemas/clinica.py` (historia) y `app/api/historia_clinica.py`, registrando el router en `app/main.py`; verificar los tests de 4.1 en verde
- [x] 4.3 Agregar test de auditoría de la apertura (`historia_clinica.crear` con usuario/IP/User-Agent) y de que una apertura rechazada no deja fila; verificar en verde tras 4.2

## 5. Evoluciones: borrador, firma y rectificatoria

- [x] 5.1 Escribir tests de integración rojos de alta de borrador, edición por autor, firma con `firmada_por`/`fecha_firma`, firma idempotente y firma con cuerpo inesperado (422)
- [x] 5.2 Escribir tests rojos de inmutabilidad: `PUT`/`DELETE` sobre firmada → 403 y texto intacto; `UPDATE`/`DELETE` directo → `P0001`; descarte de borrador → 204
- [x] 5.3 Escribir tests rojos de rectificatoria: alta enlazada, original intacta, firma y `rectificada_por`, referencia a borrador/otra historia → 422, inexistente → 404, segunda activa → 409 y `INSERT` directo → `23505`, y cadena de rectificatorias
- [x] 5.4 Implementar schemas, servicio y rutas de evoluciones (`GET/POST/PUT/DELETE` y `/firmar`) con la auditoría `evolucion.*`; verificar los tests de 5.1–5.3 en verde

## 6. Odontograma FDI versionado

- [x] 6.1 Escribir tests de integración rojos de alta de hallazgo: pieza permanente y temporaria válidas, piezas `19/20/29/49/56/86/99` → 422, cara/estado/CIE-10 inválidos → 422, historia inexistente → 404 y ausencia de versión creada
- [x] 6.2 Escribir tests rojos de versionado: primera versión = 1, segundo hallazgo crea v2 con dos hallazgos, corrección de la misma pieza/cara crea v3 con un único estado nuevo y v2 conserva el anterior; versión vigente = MAX(version)
- [x] 6.3 Escribir tests rojos de concurrencia (dos escrituras simultáneas no repiten número), lectura de versión histórica, versión inexistente → 404, `PUT/DELETE /odontograma/hallazgos/{id}` → 405 y triggers `P0001`
- [x] 6.4 Implementar el servicio de snapshots (bloqueo `FOR UPDATE` de la historia + copia de hallazgos), schemas y `app/api/odontograma.py`; verificar los tests de 6.1–6.3 en verde
- [x] 6.5 Agregar test de auditoría `odontograma.versionar` por versión creada y de que un hallazgo inválido no deja versión ni auditoría; verificar en verde

## 7. Adjuntos clínicos

- [x] 7.1 Escribir tests de integración rojos de `POST /adjuntos` multipart: PNG/PDF válidos (201 y bytes persistidos), falta de `historia_id` → 422, historia inexistente → 404, parte extra → 422
- [x] 7.2 Escribir tests rojos de seguridad: MIME no permitido (`application/x-msdownload`, `text/html`, `.exe`) → 422, archivo >5 MB → 422 y CHECK de tamaño, MIME declarado vs. magic bytes → 422, nombre `..\..\etc\passwd` saneado a `passwd`
- [x] 7.3 Escribir tests rojos de descarga: `GET /adjuntos/{id}` con token devuelve 200, MIME y bytes idénticos; sin token → 401; inexistente → 404; `Content-Disposition` sin `..` ni separadores
- [x] 7.4 Implementar schemas multipart, validación de partes, lectura acotada a 5 MB, rutas de subida/listado/descarga y auditoría `adjunto.crear`; verificar los tests de 7.1–7.3 en verde

## 8. Consentimientos

- [x] 8.1 Escribir tests de integración rojos de `POST /pacientes/{id}/consentimientos`: tipo `procedimiento_invasivo` + `v1-2026-11` → 201 con hashes, tipo inválido → 422, versión desconocida → 422, campos `texto`/`texto_hash`/`firma_ref` en el body → 422, paciente inexistente/baja → 404
- [x] 8.2 Escribir tests rojos de dos consentimientos del mismo tipo/versión (dos filas independientes ordenadas por fecha descendente) y de que `UPDATE`/`DELETE` directo falla con `P0001`
- [x] 8.3 Implementar schemas, rutas de alta/listado y auditoría `consentimiento.registrar` usando el catálogo y `calcular_hashes` de 1.6; verificar los tests de 8.1–8.2 en verde

## 9. RBAC transversal y auditoría de la matriz

- [x] 9.1 Escribir `backend/tests/integration/test_clinica_rbac.py` en rojo: administrador lee y no escribe (403), odontólogo propio 201/ajeno 403, odontólogo sin profesional 403, recepcionista lectura 200/escritura 403, asistente `en_sala` 200 y `confirmado` 403, asistente no crea/firma, auditor lectura 200/escritura 403, sin token 401
- [x] 9.2 Aplicar `require_role` y los helpers de propiedad a todos los routers clínicos, incluyendo la restricción de firma al odontólogo autor; verificar 9.1 en verde
- [x] 9.3 Agregar test transversal de auditoría: cada acción de la matriz (`historia_clinica.crear`, `evolucion.crear/editar/descartar/firmar/rectificar`, `odontograma.versionar`, `adjunto.crear`, `consentimiento.registrar`) genera exactamente una fila con el usuario correcto, y una escritura rechazada no genera ninguna; verificar en verde

## 10. Integración, smoke y evidencia

- [x] 10.1 Correr la suite completa `pytest backend/tests -q` contra PostgreSQL real y verificar que todo queda en verde sin tests omitidos por dependencia de base
- [x] 10.2 Levantar `docker compose up -d --build`, correr `alembic upgrade head` y ejecutar un smoke HTTP de los flujos: abrir historia, crear/firmar evolución, intentar editar firmada (403), crear rectificatoria, registrar hallazgo FDI válido e inválido, subir/descargar adjunto, registrar consentimiento y comprobar las filas de auditoría; guardar comandos y salidas
- [x] 10.3 Escribir `docs/skills-mcp/evidencias/c-11-verificacion-escenarios.md` con la matriz requirement→escenario→test→resultado, incluyendo los SQLSTATE observados (`P0001`, `23505`, `23514`) y el resultado del smoke
- [x] 10.4 Ejecutar `openspec validate c-11-historia-clinica-odontograma --strict` y corregir cualquier warning de descripción o escenario hasta que pase
- [x] 10.5 Preparar el resumen en lenguaje no técnico (qué se aplicó, qué no cambia, qué se probó y qué falta) y agregar el bloque C-11 a `docs/validacion-manual-pendiente.md`. Cerrar sin esperar prueba manual por change, según la decisión del usuario (2026-11-03); la aceptación funcional queda en la prueba final de la página.

## Workflow follow-up

- Bajar el stack si no se está usando; el usuario lo dejó arriba para sus pruebas.
- Archivar el change, marcar `[x]` en `CHANGES.md` y commitear/pushear el cierre sin co-autoría IA (R-13), con suite + smoke verdes (proceso acordado 2026-11-03).
- Dejar la validación manual de la página de ficha clínica para cuando exista el change de frontend clínico; C-11 cierra con smoke HTTP y evidencia de API.
