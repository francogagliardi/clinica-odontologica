# Design

## Context

C-01–C-10 dejaron el esqueleto operativo: identidad/RBAC y auditoría append-only (C-02/C-03), agenda con anti-solapamiento (C-04/C-06), pacientes (C-05), reserva pública, WhatsApp y lista de espera. El head de Alembic es `0009_lista_espera`; el "006" que menciona `CHANGES.md` para este change está desactualizado y la migración real es `0010_historia_clinica`.

Restricciones que mandan sobre el diseño:

- Governance **CRÍTICO**: inmutabilidad clínica, auditoría y RBAC son contractuales (R-03, R-04, R-11, RN-CL-01/03/04, RN-SE-02).
- Patrones existentes que se reutilizan: `AuditMixin` y baja lógica, `RegistroAuditoria` + triggers `P0001` (C-02), `UnitOfWork`/repositorios que nunca commitean, Pydantic `extra='forbid'`, `require_role`, tests de integración contra PostgreSQL real.
- Single-tenant demo (`get_consultorio_demo_id`), datos ficticios del seed.
- Sin UI clínica en v1: C-11 entrega API + evidencia; la página de ficha queda para un change posterior.

## Goals / Non-Goals

**Goals:**

- Persistir historia, evoluciones, odontograma, adjuntos y consentimientos con integridad en PostgreSQL, no solo en la capa de servicio.
- Hacer imposible (API + trigger) editar o borrar una evolución firmada, una versión de odontograma o un consentimiento; la corrección clínica es un acto nuevo y enlazado.
- Versionar el odontograma como snapshots completos e inmutables, con numeración sin huecos ni duplicados.
- Guardar adjuntos de forma autocontenida y segura, sin filesystem ni rutas construidas con input del usuario.
- Auditar cada escritura clínica en la misma transacción, con usuario/IP/dispositivo.
- Aplicar la matriz RBAC con una definición explícita y testeable de "paciente propio" y "paciente asistido".

**Non-Goals:**

- Cálculo de presupuestos/copagos (C-12), UI, firma digital certificada, antivirus, object storage, edición de fichas de pacientes sin turno, borrado de registros clínicos.
- Cambiar requisitos de capacidades existentes: C-11 solo consume `turnos`, `pacientes`, `security/core-models` y RBAC.
- Migrar datos históricos: no existen historias previas.

## Decisions

### D1 — Dos capacidades: `clinica/historia-clinica` y `clinica/odontograma`

`historia-clinica` agrupa el expediente y sus actos documentales (apertura, evoluciones, adjuntos, consentimientos, auditoría y RBAC). `odontograma` agrupa el estado dental versionado, que tiene una mecánica propia (snapshots, FDI, versiones) y va a evolucionar con C-12 y reportes. Se descartó una única `clinica/ficha-clinica` porque mezclaría dos ciclos de vida distintos (actos firmados vs. snapshots numerados) y haría crecer un requirement de odontograma dentro de un capability de expediente. También se descartaron cuatro capabilities (una por entidad): fragmentaría RBAC/auditoría en cuatro copias.

### D2 — Migración `0010_historia_clinica`, escrita a mano

`down_revision = "0009_lista_espera"`. Se escribe a mano (como `0002_core_models_seguridad.py`) porque autogenerate no detecta índices únicos parciales, CHECKs de FDI ni triggers. El upgrade crea tablas, índices, CHECKs, funciones y triggers; el downgrade los elimina en orden inverso. No se toca ninguna tabla existente.

### D3 — Modelo de datos

| Tabla | Columnas principales | Protección |
|---|---|---|
| `historias_clinicas` | `id`, `consultorio_id`, `paciente_id`, `abierta_por`, `fecha_apertura` + `AuditMixin` | Índice único parcial `uq_historias_clinicas_paciente_activa (paciente_id) WHERE deleted_at IS NULL`; sin endpoint de baja |
| `evoluciones` | `id`, `historia_id`, `profesional_id`, `creado_por`, `fecha`, `texto`, `firmada`, `firmada_por`, `fecha_firma`, `rectifica_a` + `AuditMixin` | CHECK `firma_coherente`; único parcial `uq_evoluciones_rectificacion_activa (rectifica_a) WHERE rectifica_a IS NOT NULL AND deleted_at IS NULL`; trigger de inmutabilidad |
| `odontogramas` | `id`, `historia_id`, `version`, `created_at` | Único `(historia_id, version)`; CHECK `version > 0`; trigger que rechaza todo UPDATE/DELETE |
| `hallazgos_dentales` | `id`, `odontograma_id`, `pieza`, `cara`, `estado`, `diagnostico`, `cie10`, `fecha`, `created_at` | CHECKs FDI/cara/estado/CIE-10; único `(odontograma_id, pieza, cara)`; trigger que rechaza UPDATE/DELETE |
| `adjuntos` | `id`, `historia_id`, `nombre`, `mime`, `tamano`, `contenido BYTEA`, `subido_por` + `AuditMixin` | CHECK de MIME, tamaño 1..5 MB, `tamano = octet_length(contenido)`, nombre sin separadores ni `..`; sin endpoint de baja |
| `consentimientos` | `id`, `consultorio_id`, `paciente_id`, `tipo`, `texto_version`, `texto_hash`, `firma_ref`, `fecha`, `registrado_por` | CHECK de tipo, formato `sha256:` y hash hex; trigger append-only |

`odontogramas` y `hallazgos_dentales` no heredan `AuditMixin`: son snapshots append-only, igual que `RegistroAuditoria`, y no admiten baja lógica. `historias_clinicas`, `evoluciones`, `adjuntos` y `consentimientos` sí lo heredan por consistencia con el resto del dominio, pero la API no expone borrado salvo el descarte de un borrador de evolución.

`evoluciones.creado_por` es una adición de diseño (la KB no lista el autor usuario): permite distinguir el usuario que redactó (posible asistente) del profesional responsable y es lo que se audita. `firmada_por` es el usuario que firma y debe ser el odontólogo autor.

### D4 — Inmutabilidad de la evolución firmada: dos capas, un solo camino de corrección

La API rechaza `PUT`/`DELETE` sobre firmadas con 403 antes de tocar la fila. Además, un trigger `BEFORE UPDATE OR DELETE` en `evoluciones`:

1. Rechaza todo `DELETE` físico con `RAISE EXCEPTION ... USING ERRCODE = 'P0001'`.
2. Si `OLD.firmada` es verdadero, rechaza cualquier `UPDATE` (incluido `deleted_at`, texto, `firmada=false` o un nuevo `fecha_firma`).
3. Si es la transición `false → true`, exige que `historia_id`, `profesional_id`, `creado_por`, `fecha`, `texto` y `rectifica_a` no cambien, y que `firmada_por`/`fecha_firma` queden no nulos.
4. Si sigue en borrador, permite editar texto y hacer baja lógica, pero no cambiar historia, profesional, autor ni vínculo de rectificación.

La corrección es una fila nueva con `rectifica_a`; el índice único parcial impide dos rectificatorias activas de la misma original (una segunda responde 409). Se permite rectificar una rectificatoria firmada, formando una cadena trazable; nunca se reescribe un eslabón. Se descartó "versión de evolución" con historial de texto porque la KB y RN-CL-04 piden una nueva evolución, no un diff.

### D5 — Firma: borrador → firma, sin edición posterior

La evolución nace `firmada=false` y `fecha` se fija al crearla (no al firmar), para que la firma no altere la cronología clínica. El autor odontólogo o un asistente sobre un paciente `en_sala` pueden editar/descartar el borrador; solo el odontólogo autor puede firmar. Firmar dos veces es idempotente: la API detecta `firmada=true` y responde 200 sin ejecutar UPDATE (así no choca con el trigger ni duplica auditoría). El endpoint de firma declara un modelo de cuerpo vacío `FirmaRequest` con `extra='forbid'`: `{}` es válido, y cualquier campo extra (`texto`, `fecha_firma`) responde 422, de modo que no se puede colar un cambio al firmar.

Se descartó "nace firmada" porque impediría corregir errores de tipeo durante la consulta y forzaría una rectificatoria por cada borrador.

### D6 — Odontograma: snapshots completos, versión vigente = MAX(version)

Cada cambio crea una fila nueva en `odontogramas` y copia los hallazgos de la versión anterior excepto la pieza/cara modificada, que se inserta con el estado nuevo. No se actualiza ninguna fila: `odontogramas` y `hallazgos_dentales` tienen trigger que rechaza todo `UPDATE`/`DELETE`. "Versión anterior de solo lectura" es total, no selectiva.

Consecuencias:

- La primera escritura crea la versión 1; sin hallazgos no hay fila de odontograma (`version=null` en la lectura).
- La corrección de una cara no deja dos estados contradictorios en la versión vigente: el snapshot contiene a lo sumo un hallazgo por `(pieza, cara)` (constraint único). El estado anterior sobrevive en la versión histórica.
- La escritura se serializa con `SELECT ... FOR UPDATE` sobre la historia clínica y calcula `version = COALESCE(MAX(version), 0) + 1`; el índice único `(historia_id, version)` es la red de seguridad. Se descartó "versión incremental con eventos" (más complejo de leer para la UI y de testear) y "actualizar el hallazgo en el lugar" (rompe la trazabilidad y la inmutabilidad).

FDI se valida con la fórmula `(pieza/10 BETWEEN 1 AND 4 AND pieza%10 BETWEEN 1 AND 8) OR (pieza/10 BETWEEN 5 AND 8 AND pieza%10 BETWEEN 1 AND 5)`, que rechaza 19, 20, 29, 49, 56 y 86 además del rango amplio 11–85. Caras: `mesial, distal, vestibular, lingual, oclusal, incisal, completa` (`completa` cubre estados de pieza entera y `lingual` incluye palatino). Estados: `sano, caries, obturacion, endodoncia, corona, implante, ausente, extraccion_indicada, fractura, sellante, protesis`. CIE-10 opcional con `^[A-Z][0-9]{2}(\.[0-9]{1,2})?$`.

### D7 — Adjuntos: bytes en PostgreSQL, multipart, 5 MB

Se elige `BYTEA` (hasta 5 MB) y no filesystem/volumen:

- R-04 pide persistencia clínica en PostgreSQL; un adjunto es evidencia clínica y debe vivir en la misma transacción/backup que la historia.
- Demo autocontenida: `pg_dump` respalda todo; no hay volumen extra en Compose ni archivos huérfanos si falla la transacción.
- Seguridad: nunca se construye una ruta con el nombre del usuario, así que el path traversal no tiene superficie. El nombre es solo metadata saneada.
- Costo: TOAST y crecimiento de la base. Se acota con 5 MB, allow-list de MIME y ausencia de subida masiva; si un cambio futuro necesita más, se migra a object storage sin cambiar el contrato HTTP.

Se elige `multipart/form-data` sobre base64: `UploadFile` nativo de FastAPI, sin 33 % de overhead, límite aplicable mientras se leen los chunks y compatibilidad directa con `FormData` del navegador. Base64 se descartó por bloat y doble codificación.

Validación de contenido: allow-list `image/jpeg`, `image/png`, `image/webp`, `application/pdf`; se leen los primeros bytes y se verifica la firma real (JPEG `FF D8 FF`, PNG `89 50 4E 47`, WebP `RIFF....WEBP`, PDF `%PDF`). Se rechaza cualquier otro MIME, incluidos HTML/SVG/ejecutables. Nombre saneado a basename, sin `..`, sin separadores y máximo 255 caracteres. Descarga autenticada con `Content-Type` del registro, `Content-Disposition: attachment` y `X-Content-Type-Options: nosniff`.

Se descartó guardar una referencia a filesystem porque obliga a un volumen Compose, a limpiar huérfanos y a proteger rutas, sin beneficio para el TP.

### D8 — "Propio" y "asistido"

"Paciente propio" de un odontólogo = existe un `Turno` no borrado del paciente con `profesional_id` igual al profesional cuyo `usuario_id` es el usuario autenticado, y `estado IN ('reservado','confirmado','en_sala','atendido')`. Cancelado y ausente no otorgan acceso. Esto traza directo a la matriz ("CRUD propios") y al criterio ya usado por `agenda/turnos` para "propios". Un paciente sin turno no puede tener historia: el flujo real pasa por agenda (C-06); si en el futuro se necesitan walk-ins, se agrega un turno express.

"Paciente asistido" de un asistente = paciente con un turno `en_sala` en este momento. No existe en la KB una tabla asistente→profesional, así que **no se inventa**: el asistente puede leer y actualizar borradores de cualquier consulta en curso, pero no crear, firmar, subir adjuntos ni registrar consentimientos. Es una limitación consciente de v1 que se reporta como pregunta abierta; si la cátedra exige "su profesional", el change futuro agrega el vínculo.

Lectura: administrador, recepcionista y auditor leen todo; odontólogo lee solo pacientes propios; asistente solo pacientes `en_sala`. Escritura: odontólogo sobre propios; asistente solo `PUT` de borrador de evolución sobre `en_sala`. Administrador no escribe la ficha aunque sea CRUD en otras columnas de la matriz: la columna "Ficha clínica / Odontograma" dice `R`. Se documenta como decisión fiel a la matriz, no como olvido.

### D9 — Auditoría en la misma transacción

Cada endpoint de escritura recibe `Request`, obtiene IP (`request.client.host`) y `User-Agent` truncado a 120, y llama a `audit.registrar(...)` dentro del `UnitOfWork`, después de persistir la entidad y antes de responder. Si cualquier paso lanza, el `__aexit__` del UoW hace rollback y no queda auditoría ni entidad. Acciones: `historia_clinica.crear`, `evolucion.crear`, `evolucion.editar`, `evolucion.descartar`, `evolucion.firmar`, `evolucion.rectificar`, `odontograma.versionar`, `adjunto.crear`, `consentimiento.registrar`.

Se extrae `client_ip(request)` y `dispositivo(request)` a `app/api/deps.py` (hoy viven privados en `auth.py`) para no duplicar la lógica. No se agrega ninguna operación de update/delete a `AuditoriaRepository`.

### D10 — Consentimiento: hash canónico, sin firma gráfica

El catálogo de textos vive en código (`app/domain/consentimientos.py`) con claves de versión (`v1-2026-11`) y su texto canónico. El cliente envía solo `tipo` y `texto_version`; el servidor:

1. Resuelve el texto de la versión (si no existe → 422) y calcula `texto_hash = sha256(texto_normalizado)`.
2. Calcula `firma_ref = "sha256:" + sha256(texto_hash + paciente_id + fecha_iso)`.
3. Persiste tipo, versión, hashes, fecha y `registrado_por`.

No se almacena imagen ni trazo de firma. Si la cátedra necesita el papel firmado, se sube como adjunto de la historia y queda enlazado por convención (misma fecha/paciente), sin FK adicional en v1. Se descartó HMAC con secreto de app porque agrega rotación de claves sin aportar no repudio real; el hash es integridad verificable, no firma legal. El consentimiento es append-only por trigger: corregir es registrar otro acto.

### D11 — Contratos HTTP

| Método y ruta | Cuerpo | Respuesta |
|---|---|---|
| `POST /historia-clinica` | `{paciente_id}` | 201 historia; 404 paciente; 409 duplicada |
| `GET /historia-clinica/{id}` | — | 200 historia |
| `GET /pacientes/{paciente_id}/historia-clinica` | — | 200 / 404 |
| `GET /historia-clinica/{id}/evoluciones` | — | 200 lista descendente |
| `POST /historia-clinica/{id}/evoluciones` | `{texto, rectifica_a?}` | 201; 422 rectificación inválida; 409 duplicada |
| `GET /historia-clinica/{id}/evoluciones/{evolucion_id}` | — | 200; incluye `rectificada_por` |
| `PUT /historia-clinica/{id}/evoluciones/{evolucion_id}` | `{texto}` | 200 borrador; 403 firmada |
| `DELETE /historia-clinica/{id}/evoluciones/{evolucion_id}` | — | 204 borrador; 403 firmada |
| `POST /historia-clinica/{id}/evoluciones/{evolucion_id}/firmar` | `{}` (`FirmaRequest`, extra forbid) | 200; 403 si no es el autor |
| `GET /historia-clinica/{id}/odontograma` | — | 200 `{version, hallazgos}` |
| `GET /historia-clinica/{id}/odontograma/versiones/{version}` | — | 200 / 404 |
| `POST /historia-clinica/{id}/odontograma/hallazgos` | `{pieza, cara, estado, diagnostico?, cie10?, fecha?}` | 201 versión nueva; 422 |
| `POST /adjuntos` | multipart: `historia_id`, `archivo` | 201; 422; 404 |
| `GET /historia-clinica/{id}/adjuntos` | — | 200 metadata (sin bytes) |
| `GET /adjuntos/{adjunto_id}` | — | 200 binario; 401/404 |
| `POST /pacientes/{paciente_id}/consentimientos` | `{tipo, texto_version}` | 201; 422; 404 |
| `GET /pacientes/{paciente_id}/consentimientos` | — | 200 descendente |

Todos los cuerpos usan modelos Pydantic `extra='forbid'`; los endpoints sin query declaran `reject_unexpected_query_except()`. La subida multipart valida que solo existan las partes `historia_id` y `archivo` (un campo extra → 422) para mantener el borde estricto.

### D12 — Estructura de código y transacciones

- `app/models/clinica.py`: seis modelos; se exportan en `app/models/__init__.py`.
- `app/schemas/clinica.py`: create/response por recurso, con validadores de FDI, cara, estado, CIE-10, nombre de archivo y tipo/versión de consentimiento.
- `app/domain/clinica.py`: constantes (piezas, caras, estados, MIME, límites), parser FDI, saneo de nombre, detección de firma de archivo, catálogo de consentimientos y hash canónico. Funciones puras → tests unitarios.
- `app/infrastructure/repositories.py`: `HistoriaClinicaRepository`, `EvolucionRepository`, `OdontogramaRepository`, `AdjuntoRepository`, `ConsentimientoRepository`; lecturas con `select`, escrituras con `add`, sin commit.
- `app/infrastructure/uow.py`: los cinco repositorios nuevos.
- `app/api/historia_clinica.py` y `app/api/odontograma.py`: routers; se registran en `main.py`.
- Versionado del odontograma: un servicio en `app/application/clinica.py` que abre la transacción, bloquea la historia, copia hallazgos e inserta la versión. La ruta solo orquesta.
- Dependencia de autorización: un helper `paciente_propio(uow, usuario, paciente_id)` y `paciente_en_sala(...)` en `app/api/deps.py` o `app/application/clinica.py`, reutilizado por todos los routers clínicos.

### D13 — Tests

- Unitarios: parser FDI (válidos/inválidos), caras/estados/CIE-10, saneo de nombre, magic bytes, catálogo de consentimientos y hash determinista.
- Integración (PostgreSQL real, patrón `tests/integration`): migración `0010`, unicidad de historia, trigger de evolución firmada (`P0001`), rectificatoria + índice parcial (`23505`), snapshot de odontograma (v1/v2/v3, corrección, concurrencia), triggers de odontograma/hallazgo, adjuntos (tamaño, MIME, magic bytes, path traversal), consentimiento (hashes, versión, tipo), auditoría de cada escritura y RBAC por rol.
- La evidencia va a `docs/skills-mcp/evidencias/c-11-verificacion-escenarios.md` antes de cerrar (R-14). El smoke manual con `docker compose up -d --build` se hace al final del change, con la lista de pruebas para el usuario.

## Risks / Trade-offs

- **[Crecimiento de la base por adjuntos]** → Límite 5 MB, allow-list, sin bulk upload y sin borrado; monitorear `pg_database_size`; migrar a object storage si crece.
- **[El trigger frena cambios legítimos de esquema]** → Cualquier migración futura sobre `evoluciones` debe dropear/recrear el trigger explícitamente; queda documentado en la migración.
- **[Asistente con acceso a cualquier consulta `en_sala`]** → Limitación de v1 sin tabla asistente→profesional; se restringe a lectura/edición de borradores durante la atención y se audita cada acción. Se reporta como pregunta abierta.
- **[Paciente sin turno no puede tener historia]** → Es el flujo real de la clínica; un walk-in requiere crear un turno. Se documenta para que no se lea como bug.
- **[Serialización por `FOR UPDATE` en el odontograma]** → Puede encolar escrituras del mismo paciente; el volumen de una consulta es bajo y se prefiere consistencia a paralelismo.
- **[Hash de consentimiento no es firma legal]** → Integridad y trazabilidad sí; para no repudio se adjunta el papel firmado. Se declara la limitación.
- **[Magic bytes no es antivirus]** → No se permiten ejecutables/HTML/SVG y se sirve como `attachment` con `nosniff`; suficiente para el TP, no para producción.
- **[Admin no puede corregir la ficha]** → Es la matriz; si la cátedra espera lo contrario, se cambia en un requirement explícito, no por conveniencia.

## Migration Plan

1. `alembic upgrade head` crea `0010_historia_clinica` (seis tablas, índices, CHECKs, funciones y triggers).
2. No hay backfill: las historias se crean desde la API.
3. Rollback: `alembic downgrade 0009_lista_espera` dropea triggers/funciones, índices y tablas en orden inverso; no afecta tablas de C-01–C-10.
4. Seed demo (C-16) podrá crear historias de ejemplo; C-11 no modifica el seed.

## Open Questions

- ¿La cátedra espera que el asistente quede vinculado a un profesional concreto? v1 usa `en_sala`; agregar `AsistenteProfesional` cambiaría la matriz y requiere su propio change.
- ¿Se necesita que el administrador pueda escribir la ficha en una urgencia? La matriz dice `R`; se respeta hasta que el usuario pida lo contrario.
- ¿Alcanza el hash + adjunto escaneado como consentimiento para la defensa del TP, o se pide un proveedor de firma digital?
